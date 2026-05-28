"""
Knowledge Base Data Quality Validation

Provides comprehensive data quality checks for the knowledge base:
- Orphaned entities (models without manufacturers)
- Duplicate embeddings (near-duplicate vectors)
- Stale embeddings (outdated model versions)
- Missing embeddings (null vectors)

Usage:
    validator = get_data_quality_validator()
    await validator.initialize()

    # Run individual checks
    orphans = await validator.check_orphaned_entities()
    duplicates = await validator.check_duplicate_embeddings()
    stale = await validator.check_stale_embeddings()
    missing = await validator.check_missing_embeddings()

    # Generate full report
    report = await validator.generate_quality_report()
    print(f"Health Score: {report.summary['health_score']}/100")
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from lead_to_cash.config import config
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QualityIssue:
    """
    Represents a data quality issue.

    Attributes:
        category: Type of issue (orphaned, duplicate, stale, missing)
        severity: Issue severity (critical, warning, info)
        entity_type: Type of entity affected
        entity_id: ID of the affected entity
        description: Human-readable description
        suggested_action: Recommended remediation
        details: Additional context
    """

    category: str  # orphaned, duplicate, stale, missing
    severity: str  # critical, warning, info
    entity_type: str
    entity_id: str
    description: str
    suggested_action: str
    details: Optional[dict] = None


@dataclass
class QualityReport:
    """
    Data quality report.

    Attributes:
        generated_at: Report generation timestamp (ISO format)
        total_issues: Total number of issues found
        critical_count: Number of critical severity issues
        warning_count: Number of warning severity issues
        info_count: Number of info severity issues
        issues: List of individual issues
        summary: Aggregated statistics
    """

    generated_at: str
    total_issues: int
    critical_count: int
    warning_count: int
    info_count: int
    issues: list[QualityIssue]
    summary: dict[str, Any]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "generated_at": self.generated_at,
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "entity_type": i.entity_type,
                    "entity_id": i.entity_id,
                    "description": i.description,
                    "suggested_action": i.suggested_action,
                    "details": i.details,
                }
                for i in self.issues
            ],
            "summary": self.summary,
        }


class DataQualityValidator:
    """
    Validates data quality in the Knowledge Base.

    Checks performed:
    1. Orphaned entities - Models without manufacturers, aliases without parents
    2. Duplicate embeddings - Near-duplicate vectors (potential data duplication)
    3. Stale embeddings - Outdated model versions
    4. Missing embeddings - Entities without vector embeddings
    """

    # Similarity threshold for duplicate detection
    DUPLICATE_THRESHOLD = 0.99

    # Maximum issues per category to return (prevents huge reports)
    MAX_ISSUES_PER_CATEGORY = 100

    def __init__(self, db: Optional[KnowledgeBaseDatabase] = None):
        """
        Initialize validator.

        Args:
            db: Database instance. Defaults to singleton.
        """
        self._db = db
        self._initialized = False

    @property
    def db(self) -> KnowledgeBaseDatabase:
        """Get database instance."""
        if self._db is None:
            raise ValueError("Database not initialized. Call initialize() first.")
        return self._db

    async def initialize(self) -> None:
        """Initialize database connection."""
        if self._initialized:
            return

        if self._db is None:
            self._db = get_knowledge_base_db()
            await self._db.initialize()

        self._initialized = True
        logger.info("Data quality validator initialized")

    async def check_orphaned_entities(self) -> list[QualityIssue]:
        """
        Check for orphaned entities.

        Finds:
        - Engine models without series
        - Engine series without manufacturers
        - Aliases referencing non-existent entities

        Returns:
            List of orphaned entity issues
        """
        if not self._initialized:
            await self.initialize()

        issues = []

        async with self.db.pool.acquire() as conn:
            # Engine models without series
            orphan_models = await conn.fetch(
                """
                SELECT em.id, em.model_name
                FROM kb_engine_models em
                LEFT JOIN kb_engine_series es ON em.series_id = es.id
                WHERE es.id IS NULL
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in orphan_models:
                issues.append(
                    QualityIssue(
                        category="orphaned",
                        severity="critical",
                        entity_type="engine_model",
                        entity_id=row["id"],
                        description=f"Engine model '{row['model_name']}' has no parent series",
                        suggested_action="Delete orphan or assign to valid series",
                    )
                )

            # Engine series without manufacturers
            orphan_series = await conn.fetch(
                """
                SELECT es.id, es.series_name
                FROM kb_engine_series es
                LEFT JOIN kb_manufacturers m ON es.manufacturer_id = m.id
                WHERE m.id IS NULL
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in orphan_series:
                issues.append(
                    QualityIssue(
                        category="orphaned",
                        severity="critical",
                        entity_type="engine_series",
                        entity_id=row["id"],
                        description=f"Engine series '{row['series_name']}' has no manufacturer",
                        suggested_action="Delete orphan or assign to valid manufacturer",
                    )
                )

            # Aliases with invalid entity references (manufacturers)
            orphan_aliases_mfr = await conn.fetch(
                """
                SELECT a.id, a.alias_text, a.entity_type, a.entity_id
                FROM kb_entity_aliases a
                WHERE a.entity_type = 'manufacturer'
                AND NOT EXISTS (
                    SELECT 1 FROM kb_manufacturers m WHERE m.id = a.entity_id
                )
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in orphan_aliases_mfr:
                issues.append(
                    QualityIssue(
                        category="orphaned",
                        severity="warning",
                        entity_type="alias",
                        entity_id=row["id"],
                        description=f"Alias '{row['alias_text']}' references non-existent manufacturer",
                        suggested_action="Delete orphaned alias",
                        details={"referenced_entity_id": row["entity_id"]},
                    )
                )

            # Aliases with invalid entity references (engine models)
            orphan_aliases_model = await conn.fetch(
                """
                SELECT a.id, a.alias_text, a.entity_type, a.entity_id
                FROM kb_entity_aliases a
                WHERE a.entity_type = 'engine_model'
                AND NOT EXISTS (
                    SELECT 1 FROM kb_engine_models em WHERE em.id = a.entity_id
                )
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in orphan_aliases_model:
                issues.append(
                    QualityIssue(
                        category="orphaned",
                        severity="warning",
                        entity_type="alias",
                        entity_id=row["id"],
                        description=f"Alias '{row['alias_text']}' references non-existent engine model",
                        suggested_action="Delete orphaned alias",
                        details={"referenced_entity_id": row["entity_id"]},
                    )
                )

        return issues

    async def check_duplicate_embeddings(
        self, threshold: float = DUPLICATE_THRESHOLD
    ) -> list[QualityIssue]:
        """
        Check for near-duplicate embeddings.

        Uses pgvector cosine similarity to find embeddings that are
        almost identical, which may indicate duplicate data.

        Args:
            threshold: Similarity threshold (default 0.99)

        Returns:
            List of duplicate embedding issues
        """
        if not self._initialized:
            await self.initialize()

        issues = []

        async with self.db.pool.acquire() as conn:
            # Find near-duplicate aliases
            # Using 1 - cosine distance to get similarity
            duplicates = await conn.fetch(
                """
                SELECT
                    a1.id as id1, a1.alias_text as text1,
                    a2.id as id2, a2.alias_text as text2,
                    1 - (a1.embedding <=> a2.embedding) as similarity
                FROM kb_entity_aliases a1
                JOIN kb_entity_aliases a2 ON a1.id < a2.id
                WHERE a1.embedding IS NOT NULL
                AND a2.embedding IS NOT NULL
                AND 1 - (a1.embedding <=> a2.embedding) > $1
                ORDER BY similarity DESC
                LIMIT $2
                """,
                threshold,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in duplicates:
                issues.append(
                    QualityIssue(
                        category="duplicate",
                        severity="warning",
                        entity_type="alias",
                        entity_id=row["id1"],
                        description=f"Alias '{row['text1']}' is near-duplicate of '{row['text2']}'",
                        suggested_action="Review and merge or differentiate aliases",
                        details={
                            "duplicate_id": row["id2"],
                            "similarity": float(row["similarity"]),
                        },
                    )
                )

        return issues

    async def check_stale_embeddings(self) -> list[QualityIssue]:
        """
        Check for embeddings using outdated models.

        Finds embeddings that were generated with a different model
        version than the current configuration.

        Returns:
            List of stale embedding issues
        """
        if not self._initialized:
            await self.initialize()

        issues = []
        current_model = config.knowledge_base.embedding_model

        async with self.db.pool.acquire() as conn:
            # Check aliases with stale embeddings
            stale_aliases = await conn.fetch(
                """
                SELECT id, alias_text, embedding_model
                FROM kb_entity_aliases
                WHERE embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                LIMIT $2
                """,
                current_model,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in stale_aliases:
                issues.append(
                    QualityIssue(
                        category="stale",
                        severity="info",
                        entity_type="alias",
                        entity_id=row["id"],
                        description=f"Alias '{row['alias_text']}' uses outdated embedding model",
                        suggested_action="Re-generate embedding with current model",
                        details={
                            "current_model": row["embedding_model"],
                            "expected_model": current_model,
                        },
                    )
                )

            # Check manufacturers with stale embeddings
            stale_mfrs = await conn.fetch(
                """
                SELECT id, name, embedding_model
                FROM kb_manufacturers
                WHERE name_embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                LIMIT $2
                """,
                current_model,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in stale_mfrs:
                issues.append(
                    QualityIssue(
                        category="stale",
                        severity="info",
                        entity_type="manufacturer",
                        entity_id=row["id"],
                        description=f"Manufacturer '{row['name']}' uses outdated embedding model",
                        suggested_action="Re-generate embedding with current model",
                        details={
                            "current_model": row["embedding_model"],
                            "expected_model": current_model,
                        },
                    )
                )

            # Check engine models with stale embeddings
            stale_models = await conn.fetch(
                """
                SELECT id, model_name, embedding_model
                FROM kb_engine_models
                WHERE model_embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                LIMIT $2
                """,
                current_model,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in stale_models:
                issues.append(
                    QualityIssue(
                        category="stale",
                        severity="info",
                        entity_type="engine_model",
                        entity_id=row["id"],
                        description=f"Engine model '{row['model_name']}' uses outdated embedding model",
                        suggested_action="Re-generate embedding with current model",
                        details={
                            "current_model": row["embedding_model"],
                            "expected_model": current_model,
                        },
                    )
                )

        return issues

    async def check_missing_embeddings(self) -> list[QualityIssue]:
        """
        Check for entities without embeddings.

        Finds active entities that should have embeddings but don't.

        Returns:
            List of missing embedding issues
        """
        if not self._initialized:
            await self.initialize()

        issues = []

        async with self.db.pool.acquire() as conn:
            # Aliases without embeddings
            missing_aliases = await conn.fetch(
                """
                SELECT id, alias_text
                FROM kb_entity_aliases
                WHERE embedding IS NULL
                AND is_active = TRUE
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in missing_aliases:
                issues.append(
                    QualityIssue(
                        category="missing",
                        severity="warning",
                        entity_type="alias",
                        entity_id=row["id"],
                        description=f"Alias '{row['alias_text']}' has no embedding",
                        suggested_action="Run embedding backfill",
                    )
                )

            # Manufacturers without embeddings
            missing_mfrs = await conn.fetch(
                """
                SELECT id, name
                FROM kb_manufacturers
                WHERE name_embedding IS NULL
                AND is_active = TRUE
                LIMIT $1
                """,
                self.MAX_ISSUES_PER_CATEGORY,
            )

            for row in missing_mfrs:
                issues.append(
                    QualityIssue(
                        category="missing",
                        severity="warning",
                        entity_type="manufacturer",
                        entity_id=row["id"],
                        description=f"Manufacturer '{row['name']}' has no embedding",
                        suggested_action="Run embedding backfill",
                    )
                )

        return issues

    async def generate_quality_report(self) -> QualityReport:
        """
        Generate comprehensive data quality report.

        Runs all checks and aggregates results with statistics.

        Returns:
            QualityReport with all issues and summary
        """
        if not self._initialized:
            await self.initialize()

        # Run all checks
        orphans = await self.check_orphaned_entities()
        duplicates = await self.check_duplicate_embeddings()
        stale = await self.check_stale_embeddings()
        missing = await self.check_missing_embeddings()

        all_issues = orphans + duplicates + stale + missing

        # Count by severity
        critical = sum(1 for i in all_issues if i.severity == "critical")
        warning = sum(1 for i in all_issues if i.severity == "warning")
        info = sum(1 for i in all_issues if i.severity == "info")

        # Get entity counts
        async with self.db.pool.acquire() as conn:
            counts = {
                "manufacturers": await conn.fetchval(
                    "SELECT COUNT(*) FROM kb_manufacturers WHERE is_active = TRUE"
                ),
                "series": await conn.fetchval(
                    "SELECT COUNT(*) FROM kb_engine_series WHERE is_current = TRUE"
                ),
                "models": await conn.fetchval(
                    "SELECT COUNT(*) FROM kb_engine_models WHERE is_current_production = TRUE"
                ),
                "aliases": await conn.fetchval(
                    "SELECT COUNT(*) FROM kb_entity_aliases WHERE is_active = TRUE"
                ),
            }

        return QualityReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_issues=len(all_issues),
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            issues=all_issues,
            summary={
                "entity_counts": counts,
                "issues_by_category": {
                    "orphaned": len(orphans),
                    "duplicate": len(duplicates),
                    "stale": len(stale),
                    "missing": len(missing),
                },
                "health_score": self._calculate_health_score(
                    counts, critical, warning, info
                ),
            },
        )

    def _calculate_health_score(
        self,
        counts: dict,
        critical: int,
        warning: int,
        info: int,
    ) -> float:
        """
        Calculate overall health score (0-100).

        Uses weighted penalties for different severity levels:
        - Critical: -10 points per issue
        - Warning: -3 points per issue
        - Info: -1 point per issue

        Score is normalized to 0-100 range based on total entities.

        Args:
            counts: Entity counts by type
            critical: Number of critical issues
            warning: Number of warning issues
            info: Number of info issues

        Returns:
            Health score from 0 (poor) to 100 (excellent)
        """
        total_entities = sum(counts.values())
        if total_entities == 0:
            return 100.0

        # Weighted penalty
        penalty = (critical * 10 + warning * 3 + info * 1) / total_entities * 100
        score = max(0, 100 - penalty)

        return round(score, 1)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_validator: Optional[DataQualityValidator] = None


def get_data_quality_validator() -> DataQualityValidator:
    """
    Get singleton validator instance.

    Returns:
        DataQualityValidator instance
    """
    global _validator
    if _validator is None:
        _validator = DataQualityValidator()
    return _validator


async def initialize_data_quality_validator() -> DataQualityValidator:
    """
    Initialize and return validator instance.

    Returns:
        Initialized DataQualityValidator instance
    """
    validator = get_data_quality_validator()
    await validator.initialize()
    return validator


def reset_data_quality_validator() -> None:
    """
    Reset singleton instance. For testing only.
    """
    global _validator
    _validator = None
