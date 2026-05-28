"""
News Collector Service

Collects historical and current news for Marine Intel and Competitor Intel
using NewsAPI (detailed recent news) and Perplexity (intelligent historical search).

Production-ready with:
- Optimized NewsAPI queries for maritime industry
- Comprehensive competitor coverage
- Singapore & Southeast Asia focus
- Regulatory and environmental news
- Offshore oil & gas intelligence

Usage:
    from lead_to_cash.services.news_collector import NewsCollector

    collector = NewsCollector()
    results = await collector.collect_all()
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    """Result of a news collection run."""

    source: str
    articles_found: int
    articles_saved: int
    duplicates_skipped: int
    errors: int
    queries_executed: int
    duration_seconds: float
    queries_by_category: dict = field(default_factory=dict)


class NewsCollector:
    """
    Multi-source news collector for marine and competitor intelligence.

    Combines NewsAPI (recent, detailed) with Perplexity (historical, intelligent).

    Optimized for:
    - Singapore & Southeast Asia maritime news
    - Regulatory and environmental updates
    - Offshore oil & gas intelligence
    - Competitor activity tracking
    """

    # ==========================================================================
    # OPTIMIZED MARINE INDUSTRY QUERIES (Organized by Category)
    # ==========================================================================

    # Singapore & Southeast Asia Focus (Priority Region)
    SINGAPORE_SEA_QUERIES = [
        "Singapore Maritime MPA ferry vessel",
        "Singapore shipyard Keppel Sembcorp contract",
        "Southeast Asia shipping vessel order",
        "Indonesia ferry shipbuilding Batam",
        "Malaysia marine offshore Johor",
        "Vietnam shipyard vessel newbuild",
        "Thailand shipbuilding marine contract",
        "Philippines ferry vessel order",
    ]

    # Regulatory & Environmental (Critical for KB)
    REGULATORY_QUERIES = [
        "IMO MEPC emissions shipping regulation",
        "maritime decarbonization LNG methanol ammonia",
        "CII EEXI ship carbon intensity",
        "ECA emission control area marine",
        "green shipping corridor fuel transition",
        "Tier III emission marine engine",
        "MPA Singapore environmental vessel",
        "maritime sustainability regulation Asia",
    ]

    # Offshore Oil & Gas (High Value Segment)
    OFFSHORE_QUERIES = [
        "FPSO contract offshore production",
        "FID final investment decision offshore",
        "offshore support vessel OSV PSV charter",
        "subsea SURF installation vessel",
        "offshore drilling rig contract Asia",
        "platform supply vessel order",
        "AHTS anchor handling vessel contract",
    ]

    # Marine Engines & Propulsion (Direct KB Relevance)
    ENGINE_QUERIES = [
        "marine engine order Wartsila MAN",
        "dual fuel LNG engine vessel",
        "ship propulsion system contract",
        "marine diesel genset power",
        "vessel repower engine retrofit",
        "methanol ammonia marine engine",
        "medium speed marine engine order",
        "Bergen MTU marine engine contract",
    ]

    # Vessel Orders & Fleet (Sales Signals)
    VESSEL_ORDER_QUERIES = [
        "ferry newbuild order contract",
        "OSV PSV AHTS vessel order",
        "tanker newbuild shipyard",
        "container vessel order Asia",
        "cruise ship newbuild contract",
        "tug harbour craft order Singapore",
        "cargo vessel order shipyard Asia",
    ]

    # Shipyard & Construction
    SHIPYARD_QUERIES = [
        "shipyard contract awarded vessel Asia",
        "newbuild vessel shipyard Singapore",
        "ship construction order Southeast Asia",
        "Seatrium PaxOcean ASL Marine contract",
        "Korean shipyard Hyundai Samsung order",
        "Chinese shipyard vessel contract",
    ]

    # Combined marine queries (for backwards compatibility)
    MARINE_QUERIES = (
        SINGAPORE_SEA_QUERIES[:5]
        + REGULATORY_QUERIES[:4]
        + OFFSHORE_QUERIES[:4]
        + ENGINE_QUERIES[:4]
        + VESSEL_ORDER_QUERIES[:4]
        + SHIPYARD_QUERIES[:3]
    )

    # Organized queries by category for selective collection
    MARINE_QUERY_CATEGORIES = {
        "singapore_sea": SINGAPORE_SEA_QUERIES,
        "regulatory": REGULATORY_QUERIES,
        "offshore": OFFSHORE_QUERIES,
        "engines": ENGINE_QUERIES,
        "vessel_orders": VESSEL_ORDER_QUERIES,
        "shipyards": SHIPYARD_QUERIES,
    }

    # ==========================================================================
    # COMPETITOR QUERIES (Expanded Coverage)
    # ==========================================================================

    COMPETITOR_QUERIES = {
        "caterpillar": [
            "Caterpillar Marine engine order",
            "Caterpillar MaK marine vessel",
            "Cat marine power systems contract",
            "MaK engine ship propulsion",
            "Caterpillar 3500 3600 marine",
        ],
        "cummins": [
            "Cummins marine engine order",
            "Cummins vessel power contract",
            "Cummins QSK marine ship",
            "Cummins KTA marine propulsion",
        ],
        "man_energy": [
            "MAN Energy Solutions marine order",
            "MAN engine ship contract",
            "MAN dual fuel marine vessel",
            "MAN B&W marine engine order",
            "MAN 32/44CR 48/60CR marine",
        ],
        "wartsila": [
            "Wartsila marine engine order",
            "Wartsila dual fuel vessel",
            "Wartsila W31 W32 W46 marine",
            "Wartsila ship propulsion contract",
        ],
        "himsen": [
            "HiMSEN marine engine order",
            "Hyundai HiMSEN vessel",
            "HD Hyundai marine engine",
            "HiMSEN ship propulsion contract",
        ],
        "bergen": [
            "Bergen Engines marine order",
            "Bergen marine engine vessel",
            "Rolls-Royce Bergen marine",
            "Bergen B32 B33 B36 engine",
        ],
    }

    def __init__(self):
        self.newsapi_key = os.getenv("NEWSAPI_API_KEY")
        self.perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # =========================================================================
    # NewsAPI Collection (Last ~30 days)
    # =========================================================================

    async def collect_from_newsapi(
        self,
        queries: list[str],
        days_back: int = 30,
        max_per_query: int = 100,
    ) -> CollectionResult:
        """
        Collect news articles from NewsAPI.

        Args:
            queries: Search queries to execute
            days_back: How many days back to search (max ~30 for free plan)
            max_per_query: Maximum articles per query

        Returns:
            CollectionResult with statistics
        """
        if not self.newsapi_key:
            logger.warning("NEWSAPI_API_KEY not set, skipping NewsAPI collection")
            return CollectionResult(
                source="newsapi",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                queries_executed=0,
                duration_seconds=0,
            )

        start_time = datetime.now()
        client = await self._get_client()

        from_date = (datetime.now() - timedelta(days=min(days_back, 30))).strftime(
            "%Y-%m-%d"
        )

        articles_found = 0
        articles_saved = 0
        duplicates_skipped = 0
        errors = 0
        seen_urls = set()

        for query in queries:
            try:
                params = {
                    "q": query,
                    "from": from_date,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(max_per_query, 100),
                    "apiKey": self.newsapi_key,
                }

                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params=params,
                )
                data = resp.json()

                if data.get("status") != "ok":
                    logger.warning(
                        f"NewsAPI error for '{query}': {data.get('message')}"
                    )
                    errors += 1
                    continue

                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if not url or url in seen_urls:
                        duplicates_skipped += 1
                        continue

                    seen_urls.add(url)
                    articles_found += 1

                    # Save to marine intel database
                    try:
                        saved = await self._save_marine_article(article, query)
                        if saved:
                            articles_saved += 1
                        else:
                            duplicates_skipped += 1
                    except Exception as e:
                        logger.error(f"Error saving article: {e}")
                        errors += 1

                # Rate limiting - NewsAPI allows 100 requests/day on free plan
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error querying NewsAPI for '{query}': {e}")
                errors += 1

        duration = (datetime.now() - start_time).total_seconds()

        result = CollectionResult(
            source="newsapi",
            articles_found=articles_found,
            articles_saved=articles_saved,
            duplicates_skipped=duplicates_skipped,
            errors=errors,
            queries_executed=len(queries),
            duration_seconds=duration,
        )

        logger.info(
            f"NewsAPI collection complete: {articles_saved} saved, "
            f"{duplicates_skipped} duplicates, {errors} errors"
        )

        return result

    async def _save_marine_article(self, article: dict, query: str) -> bool:
        """Save a NewsAPI article to the marine intel database."""
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db
        from lead_to_cash.services.marine_intel.models import Article

        url = article.get("url", "")
        if not url:
            return False

        db = get_marine_intel_db()
        await db.initialize()

        # Check for duplicate by URL
        existing = await db.get_article_by_url(url)
        if existing:
            return False

        # Parse published date
        published_str = article.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            published_at = datetime.now(timezone.utc)

        # Determine source category
        source_name = article.get("source", {}).get("name", "Unknown")
        source_category = self._categorize_source(source_name)

        # Create article
        new_article = Article.create(
            url=url,
            title=article.get("title", "Untitled"),
            source=source_name,
            content=article.get("content") or article.get("description") or "",
            summary=article.get("description", ""),
            source_category=source_category,
            published_date=published_at,
        )

        # Add metadata (serialize to JSON string for JSONB column)
        new_article.metadata = json.dumps(
            {
                "newsapi_query": query,
                "author": article.get("author"),
                "image_url": article.get("urlToImage"),
            }
        )

        await db.save_article(new_article)
        return True

    def _categorize_source(self, source_name: str) -> str:
        """Categorize a news source."""
        source_lower = source_name.lower()

        trade_media = [
            "maritime",
            "shipping",
            "offshore",
            "marine",
            "seatrade",
            "tradewinds",
            "lloyds",
        ]
        if any(t in source_lower for t in trade_media):
            return "trade_media"

        business = ["reuters", "bloomberg", "financial", "business", "wsj", "economist"]
        if any(b in source_lower for b in business):
            return "business_news"

        return "general_news"

    # =========================================================================
    # Competitor Intel Collection
    # =========================================================================

    async def collect_competitor_news(
        self,
        competitor: Optional[str] = None,
        days_back: int = 30,
    ) -> CollectionResult:
        """
        Collect competitor-specific news from NewsAPI.

        Args:
            competitor: Specific competitor or None for all
            days_back: How many days back to search

        Returns:
            CollectionResult with statistics
        """
        if not self.newsapi_key:
            logger.warning("NEWSAPI_API_KEY not set, skipping competitor collection")
            return CollectionResult(
                source="newsapi_competitor",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                queries_executed=0,
                duration_seconds=0,
            )

        start_time = datetime.now()
        client = await self._get_client()

        from_date = (datetime.now() - timedelta(days=min(days_back, 30))).strftime(
            "%Y-%m-%d"
        )

        articles_found = 0
        articles_saved = 0
        duplicates_skipped = 0
        errors = 0
        seen_urls = set()
        queries_executed = 0

        # Select competitors to query
        competitors = (
            [competitor] if competitor else list(self.COMPETITOR_QUERIES.keys())
        )

        for comp in competitors:
            queries = self.COMPETITOR_QUERIES.get(comp, [])

            for query in queries:
                try:
                    params = {
                        "q": query,
                        "from": from_date,
                        "language": "en",
                        "sortBy": "relevancy",
                        "pageSize": 50,
                        "apiKey": self.newsapi_key,
                    }

                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params=params,
                    )
                    data = resp.json()
                    queries_executed += 1

                    if data.get("status") != "ok":
                        logger.warning(
                            f"NewsAPI error for '{query}': {data.get('message')}"
                        )
                        errors += 1
                        continue

                    for article in data.get("articles", []):
                        url = article.get("url", "")
                        if not url or url in seen_urls:
                            duplicates_skipped += 1
                            continue

                        seen_urls.add(url)
                        articles_found += 1

                        try:
                            saved = await self._save_competitor_article(article, comp)
                            if saved:
                                articles_saved += 1
                            else:
                                duplicates_skipped += 1
                        except Exception as e:
                            logger.error(f"Error saving competitor article: {e}")
                            errors += 1

                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(
                        f"Error querying NewsAPI for competitor '{query}': {e}"
                    )
                    errors += 1

        duration = (datetime.now() - start_time).total_seconds()

        result = CollectionResult(
            source="newsapi_competitor",
            articles_found=articles_found,
            articles_saved=articles_saved,
            duplicates_skipped=duplicates_skipped,
            errors=errors,
            queries_executed=queries_executed,
            duration_seconds=duration,
        )

        logger.info(
            f"Competitor news collection complete: {articles_saved} saved, "
            f"{duplicates_skipped} duplicates, {errors} errors"
        )

        return result

    async def _save_competitor_article(self, article: dict, competitor: str) -> bool:
        """Save a NewsAPI article to the competitor intel database."""
        from lead_to_cash.services.competitor_intel.database import get_competitor_db
        from lead_to_cash.services.competitor_intel.models import CompetitorDocument

        url = article.get("url", "")
        if not url:
            return False

        db = get_competitor_db()
        await db.initialize()

        # Check for duplicate by URL
        existing = await db.get_document_by_url(url)
        if existing:
            return False

        # Parse published date
        published_str = article.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            published_at = datetime.now(timezone.utc)

        # Create document (serialize metadata to JSON string for JSONB column)
        doc = CompetitorDocument(
            id=str(uuid.uuid4()),
            competitor=competitor,
            content_type="news",
            source_type="api",  # NewsAPI is an API source
            title=article.get("title", "Untitled"),
            content=article.get("content") or article.get("description") or "",
            source_url=url,
            published_date=published_at,
            metadata=json.dumps(
                {
                    "source": article.get("source", {}).get("name"),
                    "author": article.get("author"),
                    "image_url": article.get("urlToImage"),
                }
            ),
        )

        await db.save_document(doc)
        return True

    # =========================================================================
    # Full Collection
    # =========================================================================

    async def collect_all(
        self,
        days_back: int = 30,
        include_marine: bool = True,
        include_competitors: bool = True,
    ) -> dict:
        """
        Run full news collection for all sources.

        Args:
            days_back: Days of history to collect
            include_marine: Collect marine industry news
            include_competitors: Collect competitor news

        Returns:
            Dictionary with collection results
        """
        logger.info(f"Starting full news collection (days_back={days_back})")

        results = {}

        if include_marine:
            logger.info("Collecting marine industry news...")
            results["marine"] = await self.collect_from_newsapi(
                queries=self.MARINE_QUERIES,
                days_back=days_back,
            )

        if include_competitors:
            logger.info("Collecting competitor news...")
            results["competitors"] = await self.collect_competitor_news(
                days_back=days_back,
            )

        # Summary
        total_saved = sum(r.articles_saved for r in results.values())
        total_errors = sum(r.errors for r in results.values())

        logger.info(
            f"Full collection complete: {total_saved} articles saved, "
            f"{total_errors} errors"
        )

        return results

    async def collect_by_category(
        self,
        categories: Optional[list[str]] = None,
        days_back: int = 30,
        max_queries_per_category: int = 5,
    ) -> CollectionResult:
        """
        Collect news by specific categories for targeted research.

        Args:
            categories: List of category names (from MARINE_QUERY_CATEGORIES).
                       If None, collects from all categories.
                       Valid: singapore_sea, regulatory, offshore, engines, vessel_orders, shipyards
            days_back: How many days back to search
            max_queries_per_category: Maximum queries to run per category

        Returns:
            CollectionResult with statistics including queries_by_category
        """
        if not self.newsapi_key:
            logger.warning("NEWSAPI_API_KEY not set, skipping category collection")
            return CollectionResult(
                source="newsapi_category",
                articles_found=0,
                articles_saved=0,
                duplicates_skipped=0,
                errors=1,
                queries_executed=0,
                duration_seconds=0,
            )

        start_time = datetime.now()
        client = await self._get_client()

        from_date = (datetime.now() - timedelta(days=min(days_back, 30))).strftime(
            "%Y-%m-%d"
        )

        articles_found = 0
        articles_saved = 0
        duplicates_skipped = 0
        errors = 0
        seen_urls: set[str] = set()
        queries_executed = 0
        queries_by_category: dict[str, int] = {}

        # Determine categories to collect
        if categories is None:
            categories = list(self.MARINE_QUERY_CATEGORIES.keys())

        for category in categories:
            if category not in self.MARINE_QUERY_CATEGORIES:
                logger.warning(f"Unknown category: {category}, skipping")
                continue

            queries = self.MARINE_QUERY_CATEGORIES[category][:max_queries_per_category]
            category_count = 0

            logger.info(f"Collecting category '{category}' ({len(queries)} queries)")

            for query in queries:
                try:
                    params = {
                        "q": query,
                        "from": from_date,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 100,
                        "apiKey": self.newsapi_key,
                    }

                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params=params,
                    )
                    data = resp.json()
                    queries_executed += 1

                    if data.get("status") != "ok":
                        logger.warning(
                            f"NewsAPI error for '{query}': {data.get('message')}"
                        )
                        errors += 1
                        continue

                    for article in data.get("articles", []):
                        url = article.get("url", "")
                        if not url or url in seen_urls:
                            duplicates_skipped += 1
                            continue

                        seen_urls.add(url)
                        articles_found += 1

                        try:
                            saved = await self._save_marine_article(article, query)
                            if saved:
                                articles_saved += 1
                                category_count += 1
                            else:
                                duplicates_skipped += 1
                        except Exception as e:
                            logger.error(f"Error saving article: {e}")
                            errors += 1

                    # Rate limiting
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error querying NewsAPI for '{query}': {e}")
                    errors += 1

            queries_by_category[category] = category_count
            logger.info(f"Category '{category}': {category_count} articles saved")

        duration = (datetime.now() - start_time).total_seconds()

        result = CollectionResult(
            source="newsapi_category",
            articles_found=articles_found,
            articles_saved=articles_saved,
            duplicates_skipped=duplicates_skipped,
            errors=errors,
            queries_executed=queries_executed,
            duration_seconds=duration,
            queries_by_category=queries_by_category,
        )

        logger.info(
            f"Category collection complete: {articles_saved} saved, "
            f"{duplicates_skipped} duplicates, {errors} errors"
        )

        return result


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_category_collection(
    categories: Optional[list[str]] = None,
    days_back: int = 30,
) -> CollectionResult:
    """
    Run category-based news collection.

    Args:
        categories: List of categories (singapore_sea, regulatory, offshore, etc.)
        days_back: Days of history to collect

    Returns:
        CollectionResult with category breakdown
    """
    collector = NewsCollector()
    try:
        return await collector.collect_by_category(
            categories=categories,
            days_back=days_back,
        )
    finally:
        await collector.close()


async def run_full_collection(days_back: int = 30) -> dict:
    """Run a full news collection."""
    collector = NewsCollector()
    try:
        return await collector.collect_all(days_back=days_back)
    finally:
        await collector.close()


async def run_marine_collection(days_back: int = 30) -> CollectionResult:
    """Run marine industry news collection only."""
    collector = NewsCollector()
    try:
        return await collector.collect_from_newsapi(
            queries=NewsCollector.MARINE_QUERIES,
            days_back=days_back,
        )
    finally:
        await collector.close()


async def run_competitor_collection(
    competitor: Optional[str] = None,
    days_back: int = 30,
) -> CollectionResult:
    """Run competitor news collection."""
    collector = NewsCollector()
    try:
        return await collector.collect_competitor_news(
            competitor=competitor,
            days_back=days_back,
        )
    finally:
        await collector.close()
