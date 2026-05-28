"""
News Intelligence Orchestrator

Unified orchestration layer for all maritime news intelligence collection.
Coordinates multiple data sources with scheduling, prioritization, and reporting.

Components:
- NewsAPI collection (recent news)
- RSS feed aggregation (continuous monitoring)
- Perplexity research (historical/AI-powered)
- Press room scraping (official sources)

Features:
- Configurable collection schedules
- Priority-based source selection
- Unified statistics and reporting
- Error resilience and recovery

Usage:
    from lead_to_cash.services.news_intelligence_orchestrator import NewsIntelligenceOrchestrator

    orchestrator = NewsIntelligenceOrchestrator()
    result = await orchestrator.run_full_collection()
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Collection Types and Results
# =============================================================================


class CollectionType(str, Enum):
    """Types of news collection."""

    NEWSAPI = "newsapi"
    RSS = "rss"
    PERPLEXITY = "perplexity"
    PRESS_ROOM = "press_room"


@dataclass
class CollectionJobResult:
    """Result of a single collection job."""

    job_id: str
    collection_type: str
    status: str  # "success", "partial", "failed"
    articles_found: int
    articles_saved: int
    duplicates_skipped: int
    errors: int
    duration_seconds: float
    started_at: datetime
    completed_at: datetime
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "collection_type": self.collection_type,
            "status": self.status,
            "articles_found": self.articles_found,
            "articles_saved": self.articles_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "details": self.details,
        }


@dataclass
class OrchestrationResult:
    """Result of full orchestration run."""

    run_id: str
    status: str  # "success", "partial", "failed"
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    total_articles_found: int
    total_articles_saved: int
    total_duplicates: int
    total_errors: int
    jobs: list[CollectionJobResult]
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_articles_found": self.total_articles_found,
            "total_articles_saved": self.total_articles_saved,
            "total_duplicates": self.total_duplicates,
            "total_errors": self.total_errors,
            "jobs": [j.to_dict() for j in self.jobs],
            "summary": self.summary,
        }


class NewsIntelligenceOrchestrator:
    """
    Unified orchestrator for maritime news intelligence collection.

    Coordinates all collection sources:
    - NewsAPI for recent news (last 30 days)
    - RSS feeds for continuous monitoring
    - Perplexity for AI-powered research
    - Press room scraping for official sources

    Supports:
    - Full collection (all sources)
    - Priority collection (urgent sources only)
    - Category-based collection
    - Historical backfill
    """

    def __init__(
        self,
        newsapi_enabled: bool = True,
        rss_enabled: bool = True,
        perplexity_enabled: bool = True,
        press_room_enabled: bool = True,
    ):
        """
        Initialize orchestrator.

        Args:
            newsapi_enabled: Enable NewsAPI collection
            rss_enabled: Enable RSS feed aggregation
            perplexity_enabled: Enable Perplexity research
            press_room_enabled: Enable press room scraping
        """
        self.newsapi_enabled = newsapi_enabled
        self.rss_enabled = rss_enabled
        self.perplexity_enabled = perplexity_enabled
        self.press_room_enabled = press_room_enabled

    async def _run_newsapi_collection(
        self,
        categories: Optional[list[str]] = None,
        days_back: int = 30,
    ) -> CollectionJobResult:
        """Run NewsAPI collection."""
        from lead_to_cash.services.news_collector import NewsCollector

        job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        try:
            collector = NewsCollector()

            if categories:
                result = await collector.collect_by_category(
                    categories=categories,
                    days_back=days_back,
                )
            else:
                result = await collector.collect_from_newsapi(
                    queries=collector.MARINE_QUERIES,
                    days_back=days_back,
                )

            await collector.close()

            completed_at = datetime.now(timezone.utc)
            status = "success" if result.errors == 0 else "partial"

            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.NEWSAPI.value,
                status=status,
                articles_found=result.articles_found,
                articles_saved=result.articles_saved,
                duplicates_skipped=result.duplicates_skipped,
                errors=result.errors,
                duration_seconds=result.duration_seconds,
                started_at=started_at,
                completed_at=completed_at,
                details={
                    "queries_executed": result.queries_executed,
                    "categories": categories,
                    "days_back": days_back,
                    "queries_by_category": getattr(result, "queries_by_category", {}),
                },
            )

        except Exception as e:
            logger.error(f"NewsAPI collection failed: {e}")
            completed_at = datetime.now(timezone.utc)
            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.NEWSAPI.value,
                status="failed",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                details={"error": str(e)},
            )

    async def _run_rss_collection(
        self,
        categories: Optional[list[str]] = None,
    ) -> CollectionJobResult:
        """Run RSS feed aggregation."""
        from lead_to_cash.services.rss_aggregator import RSSAggregator

        job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        try:
            aggregator = RSSAggregator()
            result = await aggregator.collect_all_feeds(categories=categories)
            await aggregator.close()

            completed_at = datetime.now(timezone.utc)
            status = "success" if result.errors == 0 else "partial"

            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.RSS.value,
                status=status,
                articles_found=result.articles_found,
                articles_saved=result.articles_saved,
                duplicates_skipped=result.duplicates_skipped,
                errors=result.errors,
                duration_seconds=result.duration_seconds,
                started_at=started_at,
                completed_at=completed_at,
                details={
                    "feeds_processed": result.feeds_processed,
                    "feeds_failed": result.feeds_failed,
                    "by_feed": result.by_feed,
                    "by_category": result.by_category,
                },
            )

        except Exception as e:
            logger.error(f"RSS collection failed: {e}")
            completed_at = datetime.now(timezone.utc)
            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.RSS.value,
                status="failed",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                details={"error": str(e)},
            )

    async def _run_perplexity_research(
        self,
        research_type: str = "daily",
        days: int = 7,
    ) -> CollectionJobResult:
        """Run Perplexity research."""
        from lead_to_cash.services.perplexity_research import PerplexityResearch

        job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        try:
            research = PerplexityResearch()
            result = await research.research_daily_news(days=days)
            await research.close()

            completed_at = datetime.now(timezone.utc)

            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.PERPLEXITY.value,
                status="success",
                articles_found=1,  # Perplexity returns consolidated research
                articles_saved=1,
                duplicates_skipped=0,
                errors=0,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                details={
                    "research_type": result.research_type,
                    "tokens_used": result.tokens_used,
                    "citations_count": len(result.citations),
                    "model": result.model,
                },
            )

        except Exception as e:
            logger.error(f"Perplexity research failed: {e}")
            completed_at = datetime.now(timezone.utc)
            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.PERPLEXITY.value,
                status="failed",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                details={"error": str(e)},
            )

    async def _run_press_room_scraping(
        self,
        source_types: Optional[list[str]] = None,
    ) -> CollectionJobResult:
        """Run press room scraping."""
        from lead_to_cash.services.press_room_scraper import (
            PressRoomScraper,
            SourceType,
        )

        job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        try:
            scraper = PressRoomScraper()
            types = [SourceType(t) for t in source_types] if source_types else None
            result = await scraper.scrape_all_sources(source_types=types)
            await scraper.close()

            completed_at = datetime.now(timezone.utc)
            status = "success" if result.errors == 0 else "partial"

            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.PRESS_ROOM.value,
                status=status,
                articles_found=result.items_found,
                articles_saved=result.items_saved,
                duplicates_skipped=result.duplicates_skipped,
                errors=result.errors,
                duration_seconds=result.duration_seconds,
                started_at=started_at,
                completed_at=completed_at,
                details={
                    "sources_scraped": result.sources_scraped,
                    "sources_failed": result.sources_failed,
                    "by_source": result.by_source,
                    "by_type": result.by_type,
                },
            )

        except Exception as e:
            logger.error(f"Press room scraping failed: {e}")
            completed_at = datetime.now(timezone.utc)
            return CollectionJobResult(
                job_id=job_id,
                collection_type=CollectionType.PRESS_ROOM.value,
                status="failed",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
                details={"error": str(e)},
            )

    async def run_full_collection(
        self,
        newsapi_categories: Optional[list[str]] = None,
        newsapi_days: int = 30,
        rss_categories: Optional[list[str]] = None,
        perplexity_days: int = 7,
        press_room_types: Optional[list[str]] = None,
    ) -> OrchestrationResult:
        """
        Run full news intelligence collection from all sources.

        Args:
            newsapi_categories: NewsAPI category filter
            newsapi_days: Days of history for NewsAPI
            rss_categories: RSS feed category filter
            perplexity_days: Days for Perplexity research
            press_room_types: Press room source type filter

        Returns:
            OrchestrationResult with all job results
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        jobs: list[CollectionJobResult] = []

        logger.info(f"Starting full news intelligence collection (run_id={run_id})")

        # Run collections sequentially to manage rate limits
        if self.newsapi_enabled:
            logger.info("Running NewsAPI collection...")
            job = await self._run_newsapi_collection(
                categories=newsapi_categories,
                days_back=newsapi_days,
            )
            jobs.append(job)
            logger.info(f"NewsAPI: {job.articles_saved} articles saved")

        if self.rss_enabled:
            logger.info("Running RSS aggregation...")
            job = await self._run_rss_collection(categories=rss_categories)
            jobs.append(job)
            logger.info(f"RSS: {job.articles_saved} articles saved")

        if self.perplexity_enabled:
            logger.info("Running Perplexity research...")
            job = await self._run_perplexity_research(days=perplexity_days)
            jobs.append(job)
            logger.info(f"Perplexity: {job.status}")

        if self.press_room_enabled:
            logger.info("Running press room scraping...")
            job = await self._run_press_room_scraping(source_types=press_room_types)
            jobs.append(job)
            logger.info(f"Press rooms: {job.articles_saved} articles saved")

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        # Aggregate statistics
        total_found = sum(j.articles_found for j in jobs)
        total_saved = sum(j.articles_saved for j in jobs)
        total_duplicates = sum(j.duplicates_skipped for j in jobs)
        total_errors = sum(j.errors for j in jobs)

        # Determine overall status
        failed_jobs = [j for j in jobs if j.status == "failed"]
        if len(failed_jobs) == len(jobs):
            status = "failed"
        elif len(failed_jobs) > 0:
            status = "partial"
        else:
            status = "success"

        # Build summary
        summary = {
            "by_source": {j.collection_type: j.articles_saved for j in jobs},
            "success_rate": (
                f"{((len(jobs) - len(failed_jobs)) / len(jobs) * 100):.1f}%"
                if jobs
                else "0%"
            ),
            "enabled_sources": {
                "newsapi": self.newsapi_enabled,
                "rss": self.rss_enabled,
                "perplexity": self.perplexity_enabled,
                "press_room": self.press_room_enabled,
            },
        }

        result = OrchestrationResult(
            run_id=run_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            total_articles_found=total_found,
            total_articles_saved=total_saved,
            total_duplicates=total_duplicates,
            total_errors=total_errors,
            jobs=jobs,
            summary=summary,
        )

        logger.info(
            f"Full collection complete: {total_saved} articles saved, "
            f"{total_duplicates} duplicates, {total_errors} errors "
            f"in {duration:.1f}s"
        )

        return result

    async def run_priority_collection(self) -> OrchestrationResult:
        """
        Run priority collection (fast, essential sources only).

        Collects from:
        - RSS feeds (priority=1 only)
        - Press rooms (regulatory only)
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        jobs: list[CollectionJobResult] = []

        logger.info(f"Starting priority collection (run_id={run_id})")

        # RSS priority feeds only
        if self.rss_enabled:
            from lead_to_cash.services.rss_aggregator import RSS_FEEDS, RSSAggregator

            priority_feeds = [f for f in RSS_FEEDS if f.priority == 1 and f.enabled]
            aggregator = RSSAggregator(feeds=priority_feeds)
            result = await aggregator.collect_all_feeds()
            await aggregator.close()

            jobs.append(
                CollectionJobResult(
                    job_id=str(uuid.uuid4()),
                    collection_type="rss_priority",
                    status="success" if result.errors == 0 else "partial",
                    articles_found=result.articles_found,
                    articles_saved=result.articles_saved,
                    duplicates_skipped=result.duplicates_skipped,
                    errors=result.errors,
                    duration_seconds=result.duration_seconds,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    details={"by_feed": result.by_feed},
                )
            )

        # Regulatory press rooms only
        if self.press_room_enabled:
            job = await self._run_press_room_scraping(source_types=["regulatory"])
            jobs.append(job)

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        total_saved = sum(j.articles_saved for j in jobs)
        total_errors = sum(j.errors for j in jobs)

        return OrchestrationResult(
            run_id=run_id,
            status="success" if total_errors == 0 else "partial",
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            total_articles_found=sum(j.articles_found for j in jobs),
            total_articles_saved=total_saved,
            total_duplicates=sum(j.duplicates_skipped for j in jobs),
            total_errors=total_errors,
            jobs=jobs,
            summary={"type": "priority"},
        )

    async def run_historical_backfill(
        self,
        topics: Optional[list[str]] = None,
    ) -> OrchestrationResult:
        """
        Run historical research backfill using Perplexity.

        Args:
            topics: List of research topics (uses defaults if None)

        Returns:
            OrchestrationResult with research results
        """
        from lead_to_cash.services.perplexity_research import PerplexityResearch

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        logger.info(f"Starting historical backfill (run_id={run_id})")

        research = PerplexityResearch()
        try:
            results = await research.run_historical_backfill(topics=topics)
        finally:
            await research.close()

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        jobs = [
            CollectionJobResult(
                job_id=str(uuid.uuid4()),
                collection_type="perplexity_historical",
                status="success",
                articles_found=len(results),
                articles_saved=len(results),
                duplicates_skipped=0,
                errors=0,
                duration_seconds=duration,
                started_at=started_at,
                completed_at=completed_at,
                details={
                    "topics_researched": len(results),
                    "total_tokens": sum(r.tokens_used for r in results),
                },
            )
        ]

        return OrchestrationResult(
            run_id=run_id,
            status="success",
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            total_articles_found=len(results),
            total_articles_saved=len(results),
            total_duplicates=0,
            total_errors=0,
            jobs=jobs,
            summary={"type": "historical_backfill"},
        )

    async def run_competitor_research(
        self,
        competitors: Optional[list[str]] = None,
    ) -> OrchestrationResult:
        """
        Run competitor intelligence research.

        Args:
            competitors: List of competitors to research

        Returns:
            OrchestrationResult with competitor research
        """
        from lead_to_cash.services.perplexity_research import PerplexityResearch

        if competitors is None:
            competitors = [
                "Wartsila",
                "MAN Energy Solutions",
                "Caterpillar MaK",
                "HiMSEN Hyundai",
                "Bergen Engines",
                "Cummins Marine",
            ]

        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        jobs: list[CollectionJobResult] = []

        logger.info(f"Starting competitor research for {len(competitors)} competitors")

        research = PerplexityResearch()
        try:
            for competitor in competitors:
                job_start = datetime.now(timezone.utc)
                try:
                    result = await research.research_competitor(competitor)
                    jobs.append(
                        CollectionJobResult(
                            job_id=str(uuid.uuid4()),
                            collection_type=f"competitor_{competitor.lower().replace(' ', '_')}",
                            status="success",
                            articles_found=1,
                            articles_saved=1,
                            duplicates_skipped=0,
                            errors=0,
                            duration_seconds=(
                                datetime.now(timezone.utc) - job_start
                            ).total_seconds(),
                            started_at=job_start,
                            completed_at=datetime.now(timezone.utc),
                            details={
                                "competitor": competitor,
                                "tokens_used": result.tokens_used,
                            },
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to research {competitor}: {e}")
                    jobs.append(
                        CollectionJobResult(
                            job_id=str(uuid.uuid4()),
                            collection_type=f"competitor_{competitor.lower().replace(' ', '_')}",
                            status="failed",
                            articles_found=0,
                            articles_saved=0,
                            duplicates_skipped=0,
                            errors=1,
                            duration_seconds=(
                                datetime.now(timezone.utc) - job_start
                            ).total_seconds(),
                            started_at=job_start,
                            completed_at=datetime.now(timezone.utc),
                            details={"error": str(e)},
                        )
                    )

                # Rate limiting between competitors
                await asyncio.sleep(3.0)

        finally:
            await research.close()

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        return OrchestrationResult(
            run_id=run_id,
            status="success" if all(j.status == "success" for j in jobs) else "partial",
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            total_articles_found=sum(j.articles_found for j in jobs),
            total_articles_saved=sum(j.articles_saved for j in jobs),
            total_duplicates=0,
            total_errors=sum(j.errors for j in jobs),
            jobs=jobs,
            summary={"type": "competitor_research", "competitors": competitors},
        )


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_full_intelligence_collection() -> OrchestrationResult:
    """Run full news intelligence collection."""
    orchestrator = NewsIntelligenceOrchestrator()
    return await orchestrator.run_full_collection()


async def run_priority_intelligence_collection() -> OrchestrationResult:
    """Run priority news intelligence collection."""
    orchestrator = NewsIntelligenceOrchestrator()
    return await orchestrator.run_priority_collection()


async def run_intelligence_backfill() -> OrchestrationResult:
    """Run historical intelligence backfill."""
    orchestrator = NewsIntelligenceOrchestrator()
    return await orchestrator.run_historical_backfill()


async def run_competitor_intelligence() -> OrchestrationResult:
    """Run competitor intelligence research."""
    orchestrator = NewsIntelligenceOrchestrator()
    return await orchestrator.run_competitor_research()


def get_collection_status() -> dict[str, Any]:
    """Get current collection configuration status."""
    from lead_to_cash.services.news_collector import NewsCollector
    from lead_to_cash.services.press_room_scraper import get_source_registry
    from lead_to_cash.services.rss_aggregator import get_feed_registry

    return {
        "newsapi": {
            "categories": list(NewsCollector.MARINE_QUERY_CATEGORIES.keys()),
            "competitor_count": len(NewsCollector.COMPETITOR_QUERIES),
        },
        "rss": {
            "feed_count": len(get_feed_registry()),
            "feeds": get_feed_registry(),
        },
        "press_rooms": {
            "source_count": len(get_source_registry()),
            "sources": get_source_registry(),
        },
    }
