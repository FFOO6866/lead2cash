"""
Retention Service for Marine Intelligence

Implements tiered data retention policy:
- Hot (0-12 months): Full content, embeddings, all metadata
- Warm (12-24 months): Summary + embeddings, content removed
- Cold (24-36 months): Summary + embeddings, minimal metadata
- Delete (>36 months): Removed from database

Embeddings are PRESERVED across all tiers for semantic search.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_db = None


def _get_db():
    """Get database instance (lazy load to avoid circular imports)."""
    global _db
    if _db is None:
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db

        _db = get_marine_intel_db()
    return _db


@dataclass
class RetentionPolicy:
    """Configuration for data retention tiers."""

    # Days before transitioning from hot to warm
    hot_to_warm_days: int = 365  # 12 months

    # Days before transitioning from warm to cold
    warm_to_cold_days: int = 730  # 24 months

    # Days before deletion
    cold_to_delete_days: int = 1095  # 36 months

    # Maximum articles to process per job run
    batch_size: int = 100


# Default policy
DEFAULT_POLICY = RetentionPolicy()


@dataclass
class RetentionJobResult:
    """Result of a retention job run."""

    hot_to_warm: int = 0
    warm_to_cold: int = 0
    deleted: int = 0
    errors: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "hot_to_warm": self.hot_to_warm,
            "warm_to_cold": self.warm_to_cold,
            "deleted": self.deleted,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.completed_at and self.started_at
                else None
            ),
        }


class RetentionService:
    """
    Manages data retention lifecycle for marine intelligence articles.

    Implements tiered retention with automatic transitions:
    - Hot → Warm: Remove full content, keep summary and embedding
    - Warm → Cold: Minimize metadata, keep summary and embedding
    - Cold → Delete: Remove from database

    Embeddings are preserved across all tiers to maintain semantic
    search capability for historical data.
    """

    def __init__(self, policy: Optional[RetentionPolicy] = None):
        """
        Initialize retention service with policy.

        Args:
            policy: Retention policy configuration (uses default if not provided)
        """
        self.policy = policy or DEFAULT_POLICY

    async def run_retention_job(self) -> RetentionJobResult:
        """
        Run full retention job: transition articles between tiers and delete old ones.

        Each phase runs independently - if one phase fails, subsequent phases still run.
        Failed batches will be retried in the next job run.

        Returns:
            RetentionJobResult with counts and timing
        """
        result = RetentionJobResult()
        db = _get_db()
        await db.initialize()

        logger.info("Starting retention job")

        # Phase 1: Hot → Warm (articles > 12 months old)
        try:
            result.hot_to_warm = await self._transition_hot_to_warm(db)
        except Exception as e:
            logger.error(f"Phase 1 (hot→warm) failed: {e}")
            result.errors += 1

        # Phase 2: Warm → Cold (articles > 24 months old)
        try:
            result.warm_to_cold = await self._transition_warm_to_cold(db)
        except Exception as e:
            logger.error(f"Phase 2 (warm→cold) failed: {e}")
            result.errors += 1

        # Phase 3: Delete old articles (> 36 months old)
        try:
            result.deleted = await self._delete_old_articles(db)
        except Exception as e:
            logger.error(f"Phase 3 (delete) failed: {e}")
            result.errors += 1

        result.completed_at = datetime.now(timezone.utc)

        logger.info(
            f"Retention job complete: "
            f"hot→warm={result.hot_to_warm}, "
            f"warm→cold={result.warm_to_cold}, "
            f"deleted={result.deleted}, "
            f"errors={result.errors}"
        )

        return result

    async def _transition_hot_to_warm(self, db) -> int:
        """
        Transition articles from hot to warm tier.

        Removes full content, keeps summary and embedding.
        Uses transaction for atomic batch updates - entire batch succeeds or fails.
        Failed articles will be retried in the next job run.
        """
        # Get articles eligible for transition
        articles = await db.get_articles_for_retention_transition(
            current_tier="hot",
            min_age_days=self.policy.hot_to_warm_days,
            limit=self.policy.batch_size,
        )

        if not articles:
            return 0

        count = 0

        # Process entire batch in a single transaction for atomicity
        # If any article fails, the entire batch rolls back and will be retried
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                for article in articles:
                    # Get summary/content within transaction
                    row = await conn.fetchrow(
                        "SELECT summary, content FROM marine_articles WHERE id = $1",
                        article.id,
                    )
                    if not row:
                        continue

                    # Keep first 500 chars of content as excerpt if no summary
                    summary = row["summary"]
                    if not summary and row["content"]:
                        summary = (
                            row["content"][:500] + "..."
                            if len(row["content"]) > 500
                            else row["content"]
                        )

                    await conn.execute(
                        """
                        UPDATE marine_articles
                        SET retention_tier = 'warm',
                            content = NULL,
                            summary = COALESCE($1, summary),
                            updated_at = NOW()
                        WHERE id = $2
                    """,
                        summary,
                        article.id,
                    )
                    count += 1
                    logger.debug(f"Transitioned article {article.id} to warm tier")

        if count > 0:
            logger.info(f"Transitioned {count} articles from hot to warm tier")

        return count

    async def _transition_warm_to_cold(self, db) -> int:
        """
        Transition articles from warm to cold tier.

        Minimizes metadata, keeps summary and embedding.
        Uses transaction for atomic batch updates - entire batch succeeds or fails.
        Failed articles will be retried in the next job run.
        """
        # Get articles eligible for transition
        articles = await db.get_articles_for_retention_transition(
            current_tier="warm",
            min_age_days=self.policy.warm_to_cold_days,
            limit=self.policy.batch_size,
        )

        if not articles:
            return 0

        count = 0

        # Process entire batch in a single transaction for atomicity
        # If any article fails, the entire batch rolls back and will be retried
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                for article in articles:
                    await conn.execute(
                        """
                        UPDATE marine_articles
                        SET retention_tier = 'cold',
                            content = NULL,
                            metadata = '{}',
                            updated_at = NOW()
                        WHERE id = $1
                    """,
                        article.id,
                    )
                    count += 1
                    logger.debug(f"Transitioned article {article.id} to cold tier")

        if count > 0:
            logger.info(f"Transitioned {count} articles from warm to cold tier")

        return count

    async def _delete_old_articles(self, db) -> int:
        """
        Delete articles older than retention period.
        """
        try:
            count = await db.delete_old_articles(
                min_age_days=self.policy.cold_to_delete_days,
                limit=self.policy.batch_size,
            )
            if count > 0:
                logger.info(
                    f"Deleted {count} articles older than {self.policy.cold_to_delete_days} days"
                )
            return count
        except Exception as e:
            logger.error(f"Error deleting old articles: {e}")
            return 0

    async def get_retention_stats(self) -> dict:
        """
        Get statistics about data in each retention tier.

        Returns:
            Statistics dictionary with counts and storage estimates
        """
        db = _get_db()
        await db.initialize()

        # Get embedding stats which includes tier breakdown
        stats = await db.get_embedding_stats()

        # Estimate storage per tier (rough estimates)
        # Hot: ~5KB content + 6KB embedding = ~11KB per article
        # Warm: ~500B summary + 6KB embedding = ~6.5KB per article
        # Cold: ~200B summary + 6KB embedding = ~6.2KB per article
        tier_counts = stats.get("by_retention_tier", {})

        storage_estimates = {
            "hot_mb": round(tier_counts.get("hot", 0) * 11 / 1024, 2),
            "warm_mb": round(tier_counts.get("warm", 0) * 6.5 / 1024, 2),
            "cold_mb": round(tier_counts.get("cold", 0) * 6.2 / 1024, 2),
        }
        storage_estimates["total_mb"] = sum(storage_estimates.values())

        return {
            "total_articles": stats["total_articles"],
            "with_embedding": stats["with_embedding"],
            "without_embedding": stats["without_embedding"],
            "embedding_coverage_pct": stats["embedding_coverage_pct"],
            "by_tier": tier_counts,
            "storage_estimates_mb": storage_estimates,
            "policy": {
                "hot_to_warm_days": self.policy.hot_to_warm_days,
                "warm_to_cold_days": self.policy.warm_to_cold_days,
                "cold_to_delete_days": self.policy.cold_to_delete_days,
            },
        }

    async def preview_retention_job(self) -> dict:
        """
        Preview what a retention job would do without making changes.

        Returns:
            Dictionary with counts of articles that would be affected
        """
        db = _get_db()
        await db.initialize()

        # Get counts of articles eligible for each transition
        hot_to_warm = await db.get_articles_for_retention_transition(
            current_tier="hot",
            min_age_days=self.policy.hot_to_warm_days,
            limit=self.policy.batch_size,
        )

        warm_to_cold = await db.get_articles_for_retention_transition(
            current_tier="warm",
            min_age_days=self.policy.warm_to_cold_days,
            limit=self.policy.batch_size,
        )

        # For deletion preview, we need to count cold articles older than threshold
        cold_articles = await db.get_articles_for_retention_transition(
            current_tier="cold",
            min_age_days=self.policy.cold_to_delete_days,
            limit=self.policy.batch_size,
        )

        return {
            "would_transition_hot_to_warm": len(hot_to_warm),
            "would_transition_warm_to_cold": len(warm_to_cold),
            "would_delete": len(cold_articles),
            "batch_size": self.policy.batch_size,
            "note": "Actual counts may be higher; limited to batch_size per category",
        }


# Singleton instance
_retention_service: Optional[RetentionService] = None


def get_retention_service(policy: Optional[RetentionPolicy] = None) -> RetentionService:
    """Get or create the retention service singleton."""
    global _retention_service
    if _retention_service is None:
        _retention_service = RetentionService(policy)
    return _retention_service


async def run_retention_job(
    policy: Optional[RetentionPolicy] = None,
) -> RetentionJobResult:
    """
    Convenience function to run a retention job.

    Args:
        policy: Optional custom retention policy

    Returns:
        RetentionJobResult with counts and timing
    """
    service = get_retention_service(policy)
    return await service.run_retention_job()
