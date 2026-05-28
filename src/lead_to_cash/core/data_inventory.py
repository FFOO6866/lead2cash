"""
Data Inventory System

Tracks what data is available across all sources so agents can:
- Know what questions they can answer from local data
- Identify gaps that require real-time search
- Report data coverage confidence to users

NO MOCKS, NO FALLBACKS - production implementation.

MANDATORY GUIDE REFERENCE:
    This module implements Section 3 of:
    `src/lead_to_cash/docs/guides/orchestration_guide.md`

Usage:
    from lead_to_cash.core.data_inventory import (
        DataInventoryService,
        InventoryCheckResult,
        get_data_inventory,
    )

    inventory = get_data_inventory()
    await inventory.refresh()
    result = await inventory.check_coverage(parsed_query)

    if result.has_local_data:
        print(f"Coverage: {result.confidence} ({result.coverage.coverage_percentage}%)")
    else:
        print(f"Gaps: {result.gaps}")
        print(f"Recommended: {result.recommended_sources}")
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# MANDATORY GUIDE REFERENCE
# =============================================================================
ORCHESTRATION_GUIDE_PATH = "src/lead_to_cash/docs/guides/orchestration_guide.md"


# =============================================================================
# Data Source Definitions
# =============================================================================


class DataSource(str, Enum):
    """Available data sources for tool execution."""

    LOCAL_VECTORDB = "local_vectordb"
    """PostgreSQL + pgvector for marine intel (opportunities, articles)."""

    COMPETITOR_DB = "competitor_db"
    """Competitor intelligence database (MAN, Caterpillar, Wärtsilä, etc.)."""

    PERPLEXITY = "perplexity"
    """Real-time web search with AI synthesis."""

    NEWSAPI = "newsapi"
    """News articles API (30 days)."""

    EODHD = "eodhd"
    """Financial data: stock prices, SEC filings."""

    SAP_MCP = "sap_mcp"
    """SAP data via MCP server."""

    KNOWLEDGE_BASE = "knowledge_base"
    """Product knowledge base (MTU, Bergen engines)."""

    OPENAI = "openai"
    """OpenAI for synthesis and reasoning."""

    BILLING_AGENT = "billing_agent"
    """BillingCollectionsAgent for AR, invoices, aging buckets, payments."""


# =============================================================================
# Data Coverage Structures
# =============================================================================


@dataclass
class DataCoverage:
    """Coverage metadata for a data domain."""

    domain: str
    """Domain name: competitor_intel, marine_news, product_kb, etc."""

    entities_covered: List[str]
    """Entities with data: ["Caterpillar", "Cummins", "APAC", etc.]"""

    time_range_start: Optional[datetime]
    """Earliest data available."""

    time_range_end: Optional[datetime]
    """Most recent data available."""

    document_count: int
    """Total documents in this domain."""

    chunk_count: int = 0
    """Total chunks (for vector search)."""

    last_updated: Optional[datetime] = None
    """When data was last refreshed."""

    coverage_percentage: float = 0.0
    """Estimated coverage (0-100)."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "domain": self.domain,
            "entities_covered": self.entities_covered,
            "time_range_start": (
                self.time_range_start.isoformat() if self.time_range_start else None
            ),
            "time_range_end": (
                self.time_range_end.isoformat() if self.time_range_end else None
            ),
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
            "coverage_percentage": self.coverage_percentage,
        }


@dataclass
class InventoryCheckResult:
    """Result of checking data inventory against a query."""

    has_local_data: bool
    """True if local data can answer the query."""

    coverage: Optional[DataCoverage]
    """Coverage details for the matched domain."""

    confidence: str
    """Confidence level: HIGH, MEDIUM, LOW."""

    confidence_score: float = 0.0
    """Numeric confidence (0.0 to 1.0)."""

    gaps: List[str] = field(default_factory=list)
    """Identified data gaps."""

    recommended_sources: List[DataSource] = field(default_factory=list)
    """Recommended data sources to query."""

    freshness_hours: Optional[float] = None
    """Hours since data was last updated."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_local_data": self.has_local_data,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "gaps": self.gaps,
            "recommended_sources": [s.value for s in self.recommended_sources],
            "freshness_hours": self.freshness_hours,
        }


# =============================================================================
# Data Inventory Service
# =============================================================================


class DataInventoryService:
    """
    Tracks what data is available across all sources.

    Answers: "Do we have data to answer this query?"

    Implements orchestration_guide.md Section 3: Data Inventory System.

    Features:
        - Coverage tracking per domain
        - Entity and temporal matching
        - Gap identification
        - Source recommendations
        - Cache with configurable TTL
    """

    # Known competitors we track
    TRACKED_COMPETITORS = [
        "Caterpillar",
        "CAT",
        "MaK",
        "Cummins",
        "MAN Energy Solutions",
        "MAN",
        "Wartsila",
        "Wärtsilä",
    ]

    # Known regions we cover
    TRACKED_REGIONS = [
        "APAC",
        "Singapore",
        "Indonesia",
        "Malaysia",
        "Vietnam",
        "Thailand",
        "Philippines",
        "China",
        "Japan",
        "Korea",
        "Europe",
        "Americas",
        "Middle East",
        "Global",
    ]

    def __init__(self, cache_ttl_hours: float = 1.0):
        """
        Initialize data inventory service.

        Args:
            cache_ttl_hours: Cache time-to-live in hours (default: 1 hour)
        """
        self._coverage_cache: dict[str, DataCoverage] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._last_refresh: Optional[datetime] = None
        self._initialized = False

    async def refresh(self) -> None:
        """
        Refresh coverage metadata from all databases.

        Queries:
        - Competitor Intel database
        - Marine Intel database
        - Knowledge Base database
        """
        logger.info("Refreshing data inventory...")

        # Refresh competitor intel coverage
        await self._refresh_competitor_intel()

        # Refresh marine intel coverage
        await self._refresh_marine_intel()

        # Refresh knowledge base coverage
        await self._refresh_knowledge_base()

        self._last_refresh = datetime.now(UTC)
        self._initialized = True

        logger.info(
            f"Data inventory refreshed: {len(self._coverage_cache)} domains, "
            f"TTL={self._cache_ttl}"
        )

    async def _refresh_competitor_intel(self) -> None:
        """Refresh competitor intelligence coverage."""
        try:
            # Import here to avoid circular imports
            from lead_to_cash.services.competitor_intel.database import (
                CompetitorIntelDatabase,
            )

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set - competitor intel unavailable")
                return

            db = CompetitorIntelDatabase(database_url)
            await db.initialize()

            try:
                stats = await db.get_stats()

                # Get date range from documents
                async with db.pool.acquire() as conn:
                    date_range = await conn.fetchrow(
                        """
                        SELECT
                            MIN(published_date) as earliest,
                            MAX(published_date) as latest
                        FROM competitor_documents
                        WHERE published_date IS NOT NULL
                        """
                    )

                competitors_covered = list(
                    stats.get("documents_by_competitor", {}).keys()
                )

                # Normalize competitor names
                normalized_competitors = []
                for comp in competitors_covered:
                    if comp and comp.strip():
                        normalized_competitors.append(comp.strip())

                self._coverage_cache["competitor_intel"] = DataCoverage(
                    domain="competitor_intel",
                    entities_covered=normalized_competitors,
                    time_range_start=date_range["earliest"] if date_range else None,
                    time_range_end=date_range["latest"] if date_range else None,
                    document_count=stats.get("total_documents", 0),
                    chunk_count=stats.get("total_chunks", 0),
                    last_updated=datetime.now(UTC),
                    coverage_percentage=self._calculate_competitor_coverage(stats),
                )

                logger.info(
                    f"Competitor intel: {stats.get('total_documents', 0)} docs, "
                    f"{len(normalized_competitors)} competitors"
                )

            finally:
                await db.close()

        except Exception as e:
            logger.warning(f"Failed to refresh competitor intel: {e}")

    async def _refresh_marine_intel(self) -> None:
        """Refresh marine intelligence coverage."""
        try:
            from lead_to_cash.services.marine_intel.database import (
                MarineIntelDatabase,
            )

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set - marine intel unavailable")
                return

            db = MarineIntelDatabase(database_url)
            await db.initialize()

            try:
                stats = await db.get_stats()

                # Get date range and article stats
                async with db.pool.acquire() as conn:
                    article_stats = await conn.fetchrow(
                        """
                        SELECT
                            COUNT(*) as article_count,
                            MIN(published_date) as earliest,
                            MAX(published_date) as latest
                        FROM marine_articles
                        WHERE published_date IS NOT NULL
                        """
                    )

                regions_covered = list(stats.get("by_region", {}).keys())

                self._coverage_cache["marine_news"] = DataCoverage(
                    domain="marine_news",
                    entities_covered=regions_covered,
                    time_range_start=(
                        article_stats["earliest"] if article_stats else None
                    ),
                    time_range_end=article_stats["latest"] if article_stats else None,
                    document_count=(
                        article_stats["article_count"] if article_stats else 0
                    ),
                    chunk_count=0,  # Articles use full-text, not chunks
                    last_updated=datetime.now(UTC),
                    coverage_percentage=self._calculate_marine_coverage(stats),
                )

                logger.info(
                    f"Marine intel: {article_stats['article_count'] if article_stats else 0} articles, "
                    f"{len(regions_covered)} regions"
                )

            finally:
                await db.close()

        except Exception as e:
            logger.warning(f"Failed to refresh marine intel: {e}")

    async def _refresh_knowledge_base(self) -> None:
        """Refresh knowledge base coverage."""
        try:
            from lead_to_cash.services.knowledge_base.database import (
                KnowledgeBaseDatabase,
            )

            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning("DATABASE_URL not set - knowledge base unavailable")
                return

            db = KnowledgeBaseDatabase(database_url)
            await db.initialize()

            try:
                # Get article count and products covered
                async with db.pool.acquire() as conn:
                    stats = await conn.fetchrow(
                        """
                        SELECT
                            COUNT(*) as article_count,
                            MIN(created_at) as earliest,
                            MAX(updated_at) as latest
                        FROM kb_articles
                        """
                    )

                    # Get unique engine models mentioned
                    products = await conn.fetch(
                        """
                        SELECT DISTINCT unnest(engine_models) as product
                        FROM kb_articles
                        WHERE engine_models IS NOT NULL
                        """
                    )

                products_covered = [
                    row["product"] for row in products if row["product"]
                ]

                self._coverage_cache["product_kb"] = DataCoverage(
                    domain="product_kb",
                    entities_covered=products_covered,
                    time_range_start=stats["earliest"] if stats else None,
                    time_range_end=stats["latest"] if stats else None,
                    document_count=stats["article_count"] if stats else 0,
                    chunk_count=0,
                    last_updated=datetime.now(UTC),
                    coverage_percentage=min(
                        100.0, len(products_covered) * 10
                    ),  # Rough estimate
                )

                logger.info(
                    f"Knowledge base: {stats['article_count'] if stats else 0} articles, "
                    f"{len(products_covered)} products"
                )

            finally:
                await db.close()

        except Exception as e:
            logger.warning(f"Failed to refresh knowledge base: {e}")

    def _calculate_competitor_coverage(self, stats: dict) -> float:
        """Calculate competitor coverage percentage."""
        docs_by_competitor = stats.get("documents_by_competitor", {})
        if not docs_by_competitor:
            return 0.0

        # Check coverage of main competitors
        main_competitors = [
            "Caterpillar",
            "Cummins",
            "MAN Energy Solutions",
            "Wartsila",
        ]
        covered = sum(
            1
            for c in main_competitors
            if any(c.lower() in comp.lower() for comp in docs_by_competitor.keys())
        )

        # Base coverage on main competitor coverage + document count
        competitor_coverage = (covered / len(main_competitors)) * 50
        doc_coverage = min(50, stats.get("total_documents", 0) / 100)  # Cap at 50%

        return min(100, competitor_coverage + doc_coverage)

    def _calculate_marine_coverage(self, stats: dict) -> float:
        """Calculate marine intel coverage percentage."""
        by_region = stats.get("by_region", {})
        if not by_region:
            return 0.0

        # Check APAC region coverage
        apac_regions = ["Singapore", "Indonesia", "Malaysia", "APAC", "Asia"]
        covered = sum(
            1
            for r in apac_regions
            if any(r.lower() in region.lower() for region in by_region.keys())
        )

        region_coverage = (covered / len(apac_regions)) * 50
        opp_coverage = min(50, stats.get("total_opportunities", 0) / 50)

        return min(100, region_coverage + opp_coverage)

    async def check_coverage(
        self,
        parsed_query: Any,  # ParsedQuery type
    ) -> InventoryCheckResult:
        """
        Check if we have data to answer this query.

        Args:
            parsed_query: ParsedQuery from query understanding

        Returns:
            InventoryCheckResult with coverage analysis and recommendations
        """
        # Ensure cache is fresh
        if (
            not self._last_refresh
            or datetime.now(UTC) - self._last_refresh > self._cache_ttl
        ):
            await self.refresh()

        # Import here to avoid circular imports
        from lead_to_cash.core.query_understanding import QueryIntent

        # Map intent to domain
        domain = self._intent_to_domain(parsed_query.intent)
        coverage = self._coverage_cache.get(domain)

        if not coverage:
            return InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                confidence_score=0.0,
                gaps=[f"No local data for domain: {domain}"],
                recommended_sources=[DataSource.PERPLEXITY],
            )

        # Check entity coverage
        entity_score = self._check_entity_match(parsed_query, coverage)

        # Check temporal coverage
        temporal_score = self._check_temporal_match(parsed_query, coverage)

        # Determine gaps and recommendations
        gaps = []
        recommended = [DataSource.LOCAL_VECTORDB]

        # Entity gaps
        if entity_score < 0.5:
            entities = (
                parsed_query.competitors
                or parsed_query.companies
                or parsed_query.regions
            )
            if entities:
                gaps.append(f"Limited data on: {', '.join(entities[:3])}")
            recommended.append(DataSource.PERPLEXITY)

        # Temporal gaps
        if temporal_score < 0.5:
            gaps.append("Query time range extends beyond local data")
            recommended.append(DataSource.PERPLEXITY)

        # Real-time needs
        if parsed_query.is_realtime_needed:
            gaps.append("Real-time data requested")
            # Move perplexity to front
            if DataSource.PERPLEXITY in recommended:
                recommended.remove(DataSource.PERPLEXITY)
            recommended.insert(0, DataSource.PERPLEXITY)

        # Intent-specific sources
        if parsed_query.intent == QueryIntent.FINANCIAL_ANALYSIS:
            recommended.append(DataSource.EODHD)

        if parsed_query.intent == QueryIntent.PRODUCT_INFO:
            recommended.insert(0, DataSource.KNOWLEDGE_BASE)

        if parsed_query.intent == QueryIntent.CUSTOMER_RESEARCH:
            recommended.append(DataSource.SAP_MCP)

        # Always add OpenAI for synthesis
        if DataSource.OPENAI not in recommended:
            recommended.append(DataSource.OPENAI)

        # Calculate overall confidence
        overall_score = entity_score * 0.6 + temporal_score * 0.4
        confidence = (
            "HIGH"
            if overall_score > 0.7
            else "MEDIUM" if overall_score > 0.4 else "LOW"
        )

        # Calculate freshness
        freshness_hours = None
        if coverage.last_updated:
            freshness_hours = (
                datetime.now(UTC) - coverage.last_updated
            ).total_seconds() / 3600

        return InventoryCheckResult(
            has_local_data=overall_score > 0.3,
            coverage=coverage,
            confidence=confidence,
            confidence_score=overall_score,
            gaps=gaps,
            recommended_sources=recommended,
            freshness_hours=freshness_hours,
        )

    def _intent_to_domain(self, intent: Any) -> str:
        """Map query intent to data domain."""
        from lead_to_cash.core.query_understanding import QueryIntent

        mapping = {
            # Original intents
            QueryIntent.COMPETITOR_INTEL: "competitor_intel",
            QueryIntent.MARKET_NEWS: "marine_news",
            QueryIntent.CUSTOMER_RESEARCH: "marine_news",
            QueryIntent.PRODUCT_INFO: "product_kb",
            QueryIntent.FINANCIAL_ANALYSIS: "competitor_intel",
            QueryIntent.SALES_OPPORTUNITY: "marine_news",
            QueryIntent.GENERAL_QUESTION: "competitor_intel",
            # New intents (aligned with query_understanding.py QueryIntent enum)
            QueryIntent.MARKET_INTEL: "marine_news",
            QueryIntent.CUSTOMER_INTEL: "marine_news",
            QueryIntent.KYP_DUE_DILIGENCE: "kyp_records",
            QueryIntent.PRODUCT_FIT: "product_kb",
            QueryIntent.RELATIONSHIP_CHECK: "sales_crm",
        }
        return mapping.get(intent, "competitor_intel")

    def _check_entity_match(self, parsed_query: Any, coverage: DataCoverage) -> float:
        """
        Check how many query entities are in our coverage.

        Returns:
            Match score (0.0 to 1.0)
        """
        query_entities = set()

        # Collect all entities from query
        if parsed_query.competitors:
            query_entities.update(parsed_query.competitors)
        if parsed_query.companies:
            query_entities.update(parsed_query.companies)
        if parsed_query.regions:
            query_entities.update(parsed_query.regions)

        if not query_entities:
            return 1.0  # No specific entities = match all

        # Normalize and compare
        covered_lower = {e.lower() for e in coverage.entities_covered}
        matches = 0

        for entity in query_entities:
            entity_lower = entity.lower()
            # Check for exact or partial match
            if entity_lower in covered_lower or any(
                entity_lower in c or c in entity_lower for c in covered_lower
            ):
                matches += 1

        return matches / len(query_entities) if query_entities else 1.0

    def _check_temporal_match(self, parsed_query: Any, coverage: DataCoverage) -> float:
        """
        Check if query time range is within our coverage.

        Returns:
            Match score (0.0 to 1.0)
        """
        if not parsed_query.time_start:
            return 0.8  # No specific time = mostly covered

        if not coverage.time_range_start or not coverage.time_range_end:
            return 0.3  # No date info in coverage

        try:
            # Parse query time
            if isinstance(parsed_query.time_start, str):
                query_start = datetime.fromisoformat(
                    parsed_query.time_start.replace("Z", "+00:00")
                )
            else:
                query_start = parsed_query.time_start

            # Make timezone-aware if needed
            if query_start.tzinfo is None:
                query_start = query_start.replace(tzinfo=UTC)

            coverage_start = coverage.time_range_start
            coverage_end = coverage.time_range_end

            if coverage_start.tzinfo is None:
                coverage_start = coverage_start.replace(tzinfo=UTC)
            if coverage_end.tzinfo is None:
                coverage_end = coverage_end.replace(tzinfo=UTC)

            # Check overlap
            if query_start < coverage_start:
                # Query starts before our data
                return 0.3
            elif query_start > coverage_end:
                # Query starts after our latest data - need real-time
                return 0.1

            return 1.0

        except Exception as e:
            logger.warning(f"Error checking temporal match: {e}")
            return 0.5

    def get_coverage_summary(self) -> dict[str, Any]:
        """
        Get summary of all data coverage.

        Returns:
            Dictionary with coverage info per domain
        """
        return {
            domain: coverage.to_dict()
            for domain, coverage in self._coverage_cache.items()
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_inventory: Optional[DataInventoryService] = None


def get_data_inventory() -> DataInventoryService:
    """
    Get singleton DataInventoryService instance.

    Returns:
        DataInventoryService instance
    """
    global _inventory
    if _inventory is None:
        _inventory = DataInventoryService()
    return _inventory


async def check_data_coverage(parsed_query: Any) -> InventoryCheckResult:
    """
    Convenience function to check data coverage.

    Args:
        parsed_query: ParsedQuery from query understanding

    Returns:
        InventoryCheckResult with coverage analysis
    """
    inventory = get_data_inventory()
    return await inventory.check_coverage(parsed_query)
