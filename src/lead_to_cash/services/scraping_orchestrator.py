"""
Unified Scraping Orchestrator

Coordinates all 54 sources from the source registry across multiple scraping methods:
- RSS feeds (automated, 12 sources)
- Press rooms (LLM-powered, 12 sources)
- NewsAPI (API-based, 6 query categories)
- Perplexity (AI research, 5 templates)

Integrates with:
- marine_intel database (existing storage)
- unified_content pipeline (new consolidated storage)

Usage:
    from lead_to_cash.services.scraping_orchestrator import (
        run_phase1_scraping,
        run_full_scraping,
        run_historical_backfill,
    )

    # Phase 1: RSS + Press Rooms
    result = await run_phase1_scraping()

    # Full scraping: all sources
    result = await run_full_scraping()

    # Historical backfill: 3-year coverage via Perplexity
    result = await run_historical_backfill(years_back=3)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from lead_to_cash.services.source_registry import (
    get_priority_sources,
    get_source_stats,
)

logger = logging.getLogger(__name__)


@dataclass
class ScrapingStats:
    """Statistics from a scraping run."""

    rss_feeds_processed: int = 0
    rss_articles_saved: int = 0
    rss_duplicates: int = 0
    rss_errors: int = 0

    press_rooms_processed: int = 0
    press_items_saved: int = 0
    press_duplicates: int = 0
    press_errors: int = 0

    newsapi_queries_run: int = 0
    newsapi_articles_saved: int = 0
    newsapi_duplicates: int = 0
    newsapi_errors: int = 0

    perplexity_queries_run: int = 0
    perplexity_articles_saved: int = 0
    perplexity_errors: int = 0

    total_duration_seconds: float = 0.0
    by_source: dict = field(default_factory=dict)
    errors_detail: list = field(default_factory=list)

    @property
    def total_saved(self) -> int:
        return (
            self.rss_articles_saved
            + self.press_items_saved
            + self.newsapi_articles_saved
            + self.perplexity_articles_saved
        )

    @property
    def total_duplicates(self) -> int:
        return self.rss_duplicates + self.press_duplicates + self.newsapi_duplicates

    @property
    def total_errors(self) -> int:
        return (
            self.rss_errors
            + self.press_errors
            + self.newsapi_errors
            + self.perplexity_errors
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rss": {
                "feeds_processed": self.rss_feeds_processed,
                "articles_saved": self.rss_articles_saved,
                "duplicates": self.rss_duplicates,
                "errors": self.rss_errors,
            },
            "press_rooms": {
                "sources_processed": self.press_rooms_processed,
                "items_saved": self.press_items_saved,
                "duplicates": self.press_duplicates,
                "errors": self.press_errors,
            },
            "newsapi": {
                "queries_run": self.newsapi_queries_run,
                "articles_saved": self.newsapi_articles_saved,
                "duplicates": self.newsapi_duplicates,
                "errors": self.newsapi_errors,
            },
            "perplexity": {
                "queries_run": self.perplexity_queries_run,
                "articles_saved": self.perplexity_articles_saved,
                "errors": self.perplexity_errors,
            },
            "total": {
                "saved": self.total_saved,
                "duplicates": self.total_duplicates,
                "errors": self.total_errors,
            },
            "duration_seconds": self.total_duration_seconds,
            "by_source": self.by_source,
        }


class ScrapingOrchestrator:
    """
    Unified orchestrator for all maritime news scraping.

    Coordinates multiple scraping methods:
    - RSS feeds (RSSAggregator)
    - Press rooms (PressRoomScraper)
    - NewsAPI (NewsCollector)
    - Perplexity (PerplexityResearch)

    Features:
    - Priority-based source ordering
    - Rate limiting between sources
    - Error isolation per source
    - Unified statistics tracking
    """

    def __init__(
        self,
        delay_between_sources: float = 2.0,
        enable_unified_pipeline: bool = True,
    ):
        """
        Initialize scraping orchestrator.

        Args:
            delay_between_sources: Delay between source scrapes (rate limiting)
            enable_unified_pipeline: Also save to unified content pipeline
        """
        self.delay_between_sources = delay_between_sources
        self.enable_unified_pipeline = enable_unified_pipeline
        self.stats = ScrapingStats()

    async def run_rss_scraping(
        self,
        categories: Optional[list[str]] = None,
        max_feeds: Optional[int] = None,
    ) -> ScrapingStats:
        """
        Run RSS feed scraping.

        Args:
            categories: Filter by feed categories
            max_feeds: Maximum feeds to process

        Returns:
            ScrapingStats for RSS scraping
        """
        from lead_to_cash.services.rss_aggregator import RSSAggregator

        logger.info("Starting RSS feed scraping")
        start_time = datetime.now()

        try:
            aggregator = RSSAggregator()
            result = await aggregator.collect_all_feeds(
                categories=categories,
                max_feeds=max_feeds,
            )
            await aggregator.close()

            self.stats.rss_feeds_processed = result.feeds_processed
            self.stats.rss_articles_saved = result.articles_saved
            self.stats.rss_duplicates = result.duplicates_skipped
            self.stats.rss_errors = result.errors

            # Track by source
            for feed_name, count in result.by_feed.items():
                self.stats.by_source[f"rss:{feed_name}"] = count

            logger.info(
                f"RSS scraping complete: {result.feeds_processed} feeds, "
                f"{result.articles_saved} saved, {result.duplicates_skipped} duplicates"
            )

        except Exception as e:
            logger.error(f"RSS scraping failed: {e}")
            self.stats.rss_errors += 1
            self.stats.errors_detail.append(f"RSS: {e}")

        self.stats.total_duration_seconds += (
            datetime.now() - start_time
        ).total_seconds()
        return self.stats

    async def run_press_room_scraping(
        self,
        source_types: Optional[list[str]] = None,
        max_sources: Optional[int] = None,
    ) -> ScrapingStats:
        """
        Run press room scraping.

        Args:
            source_types: Filter by source types
            max_sources: Maximum sources to scrape

        Returns:
            ScrapingStats for press room scraping
        """
        from lead_to_cash.services.press_room_scraper import (
            PressRoomScraper,
            SourceType,
        )

        logger.info("Starting press room scraping")
        start_time = datetime.now()

        try:
            types = [SourceType(t) for t in source_types] if source_types else None
            scraper = PressRoomScraper()
            result = await scraper.scrape_all_sources(
                source_types=types,
                max_sources=max_sources,
            )
            await scraper.close()

            self.stats.press_rooms_processed = result.sources_scraped
            self.stats.press_items_saved = result.items_saved
            self.stats.press_duplicates = result.duplicates_skipped
            self.stats.press_errors = result.errors

            # Track by source
            for source_name, count in result.by_source.items():
                self.stats.by_source[f"press:{source_name}"] = count

            logger.info(
                f"Press room scraping complete: {result.sources_scraped} sources, "
                f"{result.items_saved} saved, {result.duplicates_skipped} duplicates"
            )

        except Exception as e:
            logger.error(f"Press room scraping failed: {e}")
            self.stats.press_errors += 1
            self.stats.errors_detail.append(f"Press room: {e}")

        self.stats.total_duration_seconds += (
            datetime.now() - start_time
        ).total_seconds()
        return self.stats

    async def run_newsapi_collection(
        self,
        categories: Optional[list[str]] = None,
        days_back: int = 7,
    ) -> ScrapingStats:
        """
        Run NewsAPI collection.

        Args:
            categories: Query categories to run
            days_back: Days of history to collect

        Returns:
            ScrapingStats for NewsAPI collection
        """
        from lead_to_cash.services.news_collector import NewsCollector

        logger.info("Starting NewsAPI collection")
        start_time = datetime.now()

        try:
            collector = NewsCollector()
            categories_to_run = categories or list(
                collector.MARINE_QUERY_CATEGORIES.keys()
            )

            total_saved = 0
            total_duplicates = 0

            for category in categories_to_run:
                try:
                    result = await collector.collect_by_category(
                        categories=[category],
                        days_back=days_back,
                    )
                    self.stats.newsapi_queries_run += len(
                        collector.MARINE_QUERY_CATEGORIES.get(category, [])
                    )
                    total_saved += result.articles_saved
                    total_duplicates += result.duplicates_skipped
                    self.stats.by_source[f"newsapi:{category}"] = result.articles_saved

                    # Rate limiting between categories
                    await asyncio.sleep(self.delay_between_sources)

                except Exception as e:
                    logger.error(f"NewsAPI category '{category}' failed: {e}")
                    self.stats.newsapi_errors += 1
                    self.stats.errors_detail.append(f"NewsAPI {category}: {e}")

            self.stats.newsapi_articles_saved = total_saved
            self.stats.newsapi_duplicates = total_duplicates

            logger.info(
                f"NewsAPI collection complete: {self.stats.newsapi_queries_run} queries, "
                f"{total_saved} saved, {total_duplicates} duplicates"
            )

        except Exception as e:
            logger.error(f"NewsAPI collection failed: {e}")
            self.stats.newsapi_errors += 1
            self.stats.errors_detail.append(f"NewsAPI: {e}")

        self.stats.total_duration_seconds += (
            datetime.now() - start_time
        ).total_seconds()
        return self.stats

    async def run_perplexity_research(
        self,
        templates: Optional[list[str]] = None,
        custom_topics: Optional[list[str]] = None,
    ) -> ScrapingStats:
        """
        Run Perplexity AI research.

        Args:
            templates: Research templates to use
            custom_topics: Custom research topics

        Returns:
            ScrapingStats for Perplexity research
        """
        from lead_to_cash.services.perplexity_research import PerplexityResearch

        logger.info("Starting Perplexity research")
        start_time = datetime.now()

        try:
            researcher = PerplexityResearch()
            templates_to_run = templates or ["DAILY_NEWS"]

            for template in templates_to_run:
                try:
                    result = await researcher.research(template=template)
                    self.stats.perplexity_queries_run += 1
                    if result and result.get("content"):
                        self.stats.perplexity_articles_saved += 1
                    self.stats.by_source[f"perplexity:{template}"] = 1

                    # Rate limiting
                    await asyncio.sleep(self.delay_between_sources)

                except Exception as e:
                    logger.error(f"Perplexity template '{template}' failed: {e}")
                    self.stats.perplexity_errors += 1
                    self.stats.errors_detail.append(f"Perplexity {template}: {e}")

            if custom_topics:
                for topic in custom_topics:
                    try:
                        result = await researcher.research(
                            template="COMPETITOR", topic=topic
                        )
                        self.stats.perplexity_queries_run += 1
                        if result and result.get("content"):
                            self.stats.perplexity_articles_saved += 1

                        await asyncio.sleep(self.delay_between_sources)

                    except Exception as e:
                        logger.error(f"Perplexity topic '{topic}' failed: {e}")
                        self.stats.perplexity_errors += 1

            logger.info(
                f"Perplexity research complete: {self.stats.perplexity_queries_run} queries"
            )

        except Exception as e:
            logger.error(f"Perplexity research failed: {e}")
            self.stats.perplexity_errors += 1
            self.stats.errors_detail.append(f"Perplexity: {e}")

        self.stats.total_duration_seconds += (
            datetime.now() - start_time
        ).total_seconds()
        return self.stats

    async def run_historical_backfill(
        self,
        years_back: int = 3,
    ) -> ScrapingStats:
        """
        Run historical backfill via Perplexity.

        Args:
            years_back: Number of years to backfill

        Returns:
            ScrapingStats for historical backfill
        """
        from lead_to_cash.services.perplexity_research import PerplexityResearch

        logger.info(f"Starting historical backfill for {years_back} years")
        start_time = datetime.now()

        try:
            researcher = PerplexityResearch()
            results = await researcher.run_historical_backfill(years_back=years_back)

            self.stats.perplexity_queries_run = len(results)
            successful = sum(1 for r in results if r.get("content"))
            self.stats.perplexity_articles_saved = successful
            self.stats.perplexity_errors = len(results) - successful

            logger.info(
                f"Historical backfill complete: {self.stats.perplexity_queries_run} queries, "
                f"{successful} successful"
            )

        except Exception as e:
            logger.error(f"Historical backfill failed: {e}")
            self.stats.perplexity_errors += 1
            self.stats.errors_detail.append(f"Historical backfill: {e}")

        self.stats.total_duration_seconds += (
            datetime.now() - start_time
        ).total_seconds()
        return self.stats


# =============================================================================
# Convenience Functions for Common Scraping Scenarios
# =============================================================================


async def run_phase1_scraping() -> ScrapingStats:
    """
    Phase 1 scraping: RSS feeds + Press rooms.

    Estimated output: ~775 articles/month from 24 sources.

    Returns:
        ScrapingStats with combined results
    """
    logger.info("Starting Phase 1 scraping (RSS + Press Rooms)")

    orchestrator = ScrapingOrchestrator()

    # Run RSS feeds first (faster, lower API cost)
    await orchestrator.run_rss_scraping()

    # Then press rooms (slower, uses OpenAI API)
    await orchestrator.run_press_room_scraping()

    logger.info(
        f"Phase 1 complete: {orchestrator.stats.total_saved} articles saved, "
        f"{orchestrator.stats.total_duplicates} duplicates, "
        f"{orchestrator.stats.total_errors} errors"
    )

    return orchestrator.stats


async def run_phase2_scraping(days_back: int = 30) -> ScrapingStats:
    """
    Phase 2 scraping: NewsAPI collection.

    Args:
        days_back: Days of history to collect

    Returns:
        ScrapingStats with results
    """
    logger.info("Starting Phase 2 scraping (NewsAPI)")

    orchestrator = ScrapingOrchestrator()
    await orchestrator.run_newsapi_collection(days_back=days_back)

    return orchestrator.stats


async def run_full_scraping(
    days_back: int = 7,
    include_perplexity: bool = True,
) -> ScrapingStats:
    """
    Full scraping: all sources.

    Args:
        days_back: Days of NewsAPI history to collect
        include_perplexity: Include Perplexity research

    Returns:
        ScrapingStats with combined results
    """
    logger.info("Starting full scraping (all sources)")

    orchestrator = ScrapingOrchestrator()

    # Phase 1: RSS + Press rooms
    await orchestrator.run_rss_scraping()
    await orchestrator.run_press_room_scraping()

    # Phase 2: NewsAPI
    await orchestrator.run_newsapi_collection(days_back=days_back)

    # Phase 3: Perplexity (optional)
    if include_perplexity:
        await orchestrator.run_perplexity_research(
            templates=["DAILY_NEWS", "MARKET_INTEL"]
        )

    logger.info(
        f"Full scraping complete: {orchestrator.stats.total_saved} articles saved, "
        f"{orchestrator.stats.total_errors} errors"
    )

    return orchestrator.stats


async def run_historical_backfill(years_back: int = 3) -> ScrapingStats:
    """
    Historical backfill via Perplexity for 3-year coverage.

    Args:
        years_back: Number of years to backfill

    Returns:
        ScrapingStats with results
    """
    logger.info(f"Starting historical backfill ({years_back} years)")

    orchestrator = ScrapingOrchestrator()
    await orchestrator.run_historical_backfill(years_back=years_back)

    return orchestrator.stats


async def run_priority_scraping() -> ScrapingStats:
    """
    Priority scraping: critical and high priority sources only.

    Returns:
        ScrapingStats with results
    """
    logger.info("Starting priority scraping (critical + high)")

    # Get priority source IDs from registry
    priority_sources = get_priority_sources(["critical", "high"])
    rss_source_ids = [s.id for s in priority_sources if s.rss_url]

    orchestrator = ScrapingOrchestrator()

    # RSS for priority sources
    await orchestrator.run_rss_scraping(max_feeds=len(rss_source_ids))

    # Press rooms for regulatory and manufacturers (always priority)
    await orchestrator.run_press_room_scraping(
        source_types=["regulatory", "manufacturer"]
    )

    return orchestrator.stats


async def run_competitor_monitoring() -> ScrapingStats:
    """
    Competitor-focused scraping: engine manufacturers only.

    Returns:
        ScrapingStats with results
    """
    logger.info("Starting competitor monitoring")

    orchestrator = ScrapingOrchestrator()

    # Press rooms for manufacturers
    await orchestrator.run_press_room_scraping(source_types=["manufacturer"])

    # Perplexity for each competitor
    competitors = ["Wärtsilä", "MAN Energy Solutions", "Caterpillar", "Cummins"]
    await orchestrator.run_perplexity_research(
        templates=["COMPETITOR"],
        custom_topics=competitors,
    )

    return orchestrator.stats


def get_scraping_coverage_report() -> dict[str, Any]:
    """
    Get report of current scraping coverage.

    Returns:
        Dict with source statistics and coverage analysis
    """
    stats = get_source_stats()

    return {
        "total_sources": stats["total"],
        "enabled_sources": stats["enabled"],
        "sources_with_rss": stats["with_rss"],
        "by_category": stats["by_category"],
        "by_priority": stats["by_priority"],
        "by_tier": stats["by_tier"],
        "coverage_summary": {
            "automated_rss": f"{stats['with_rss']}/{stats['total']} sources have RSS",
            "priority_critical": f"{stats['by_priority'].get('critical', 0)} critical sources",
            "priority_high": f"{stats['by_priority'].get('high', 0)} high priority sources",
            "tier_1_official": f"{stats['by_tier'].get('tier_1', 0)} Tier 1 (official) sources",
        },
    }
