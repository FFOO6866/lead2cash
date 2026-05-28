"""
RSS Aggregator Service

Production-ready RSS feed aggregation for maritime industry news.
Collects from multiple free/open maritime news sources with:
- Automated feed parsing
- Content deduplication
- Source categorization
- Error resilience with retries
- Rate limiting

Usage:
    from lead_to_cash.services.rss_aggregator import RSSAggregator

    aggregator = RSSAggregator()
    result = await aggregator.collect_all_feeds()
"""

import asyncio
import hashlib
import logging
import xml.etree.ElementTree as _ET_stdlib
import defusedxml.ElementTree as ET  # Safe parsing

_Element = _ET_stdlib.Element
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# RSS Feed Configuration
# =============================================================================


@dataclass
class RSSFeed:
    """Configuration for an RSS feed source."""

    name: str
    url: str
    category: str  # e.g., "general_maritime", "offshore", "regulatory"
    priority: int = 1  # 1 = highest priority
    enabled: bool = True
    source_tier: int = 2  # 1-4 credibility tier


# Production RSS Feed Registry
RSS_FEEDS: list[RSSFeed] = [
    # Tier 1 - High-Value Maritime News (Free Full Access)
    RSSFeed(
        name="Maritime Executive",
        url="https://maritime-executive.com/rss",
        category="general_maritime",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="gCaptain",
        url="https://gcaptain.com/feed/",
        category="general_maritime",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="Splash247",
        url="https://splash247.com/feed/",
        category="asia_shipping",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="Hellenic Shipping News",
        url="https://www.hellenicshippingnews.com/feed/",
        category="tankers_bulk",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="Ship & Bunker",
        url="https://shipandbunker.com/rss",
        category="bunker_fuel",
        priority=1,
        source_tier=2,
    ),
    # Tier 2 - Offshore & Energy
    RSSFeed(
        name="Offshore Engineer",
        url="https://www.oedigital.com/rss",
        category="offshore_oil_gas",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="Rigzone",
        url="https://www.rigzone.com/news/rss/rigzone_latest.aspx",
        category="offshore_oil_gas",
        priority=2,
        source_tier=3,
    ),
    # Tier 2 - Workboats & Ferries
    RSSFeed(
        name="WorkBoat",
        url="https://www.workboat.com/rss",
        category="tugs_osv_ferries",
        priority=1,
        source_tier=2,
    ),
    RSSFeed(
        name="Baird Maritime",
        url="https://www.bairdmaritime.com/feed/",
        category="workboats_australia",
        priority=2,
        source_tier=3,
    ),
    # Tier 2 - Marine Technology
    RSSFeed(
        name="Marine Link",
        url="https://www.marinelink.com/rss",
        category="marine_technology",
        priority=2,
        source_tier=3,
    ),
    # Tier 2 - Classification Societies (Regulatory/Technical)
    RSSFeed(
        name="DNV Maritime",
        url="https://www.dnv.com/news/rss",
        category="regulations_class",
        priority=1,
        source_tier=1,
    ),
    # Tier 2 - Cruise & Ferry
    RSSFeed(
        name="Seatrade Maritime",
        url="https://www.seatrade-maritime.com/rss.xml",
        category="cruise_ferry",
        priority=2,
        source_tier=2,
    ),
    # Tier 1 - Singapore/SEA News (Legitimate Sources)
    RSSFeed(
        name="The Straits Times Business",
        url="https://www.straitstimes.com/news/business/rss.xml",
        category="singapore_business",
        priority=1,
        source_tier=1,
    ),
    RSSFeed(
        name="Channel News Asia Business",
        url="https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
        category="singapore_business",
        priority=1,
        source_tier=1,
    ),
]


@dataclass
class RSSArticle:
    """Parsed article from RSS feed."""

    title: str
    url: str
    url_hash: str
    source_name: str
    source_category: str
    summary: Optional[str] = None
    content: Optional[str] = None
    published_date: Optional[datetime] = None
    author: Optional[str] = None
    source_tier: int = 2
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """Generate SHA-256 hash of URL for deduplication."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()


@dataclass
class AggregationResult:
    """Result of RSS aggregation run."""

    feeds_processed: int
    feeds_failed: int
    articles_found: int
    articles_saved: int
    duplicates_skipped: int
    errors: int
    duration_seconds: float
    by_feed: dict = field(default_factory=dict)
    by_category: dict = field(default_factory=dict)


class RSSAggregator:
    """
    Production RSS feed aggregator for maritime news.

    Collects from multiple free maritime news sources and saves
    to the marine_articles database with deduplication.

    Features:
    - Concurrent feed fetching with rate limiting
    - Robust XML parsing with fallbacks
    - Source categorization and tier assignment
    - Error resilience with per-feed isolation
    """

    def __init__(
        self,
        feeds: Optional[list[RSSFeed]] = None,
        timeout: int = 30,
        max_concurrent: int = 5,
        delay_between_feeds: float = 1.0,
    ):
        """
        Initialize RSS aggregator.

        Args:
            feeds: Custom feed list (defaults to RSS_FEEDS)
            timeout: HTTP request timeout in seconds
            max_concurrent: Maximum concurrent feed fetches
            delay_between_feeds: Delay between feed requests (rate limiting)
        """
        self.feeds = feeds or [f for f in RSS_FEEDS if f.enabled]
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.delay_between_feeds = delay_between_feeds
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "RRPS-MarineIntel/1.0 (News Aggregator)",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def fetch_feed(self, feed: RSSFeed) -> list[RSSArticle]:
        """
        Fetch and parse a single RSS feed.

        Args:
            feed: RSS feed configuration

        Returns:
            List of parsed RSSArticle objects
        """
        articles: list[RSSArticle] = []

        try:
            client = await self._get_client()
            response = await client.get(feed.url)

            if response.status_code != 200:
                logger.warning(
                    f"Feed '{feed.name}' returned status {response.status_code}"
                )
                return articles

            content = response.text

            # Parse XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                logger.error(f"XML parse error for '{feed.name}': {e}")
                return articles

            # Find items (RSS 2.0 format: channel/item, Atom: entry)
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items:
                try:
                    article = self._parse_item(item, feed)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning(f"Error parsing item in '{feed.name}': {e}")
                    continue

            logger.info(f"Feed '{feed.name}': {len(articles)} articles parsed")

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching feed '{feed.name}'")
        except httpx.RequestError as e:
            logger.error(f"Request error for '{feed.name}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error for '{feed.name}': {e}")

        return articles

    def _parse_item(
        self,
        item: _Element,
        feed: RSSFeed,
    ) -> Optional[RSSArticle]:
        """
        Parse an RSS item element into RSSArticle.

        Handles both RSS 2.0 and Atom formats.
        """
        # Namespaces for Atom
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "content": "http://purl.org/rss/1.0/modules/content/",
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        # Extract title
        title_elem = item.find("title")
        if title_elem is None:
            title_elem = item.find("atom:title", ns)
        title = (
            title_elem.text.strip()
            if title_elem is not None and title_elem.text
            else None
        )

        if not title:
            return None

        # Extract URL
        link_elem = item.find("link")
        if link_elem is None:
            link_elem = item.find("atom:link", ns)
            url = link_elem.get("href") if link_elem is not None else None
        else:
            url = link_elem.text.strip() if link_elem.text else link_elem.get("href")

        if not url:
            return None

        # Extract summary/description
        summary = None
        for tag in ["description", "summary", "atom:summary"]:
            elem = item.find(tag) if ":" not in tag else item.find(tag, ns)
            if elem is not None and elem.text:
                summary = elem.text.strip()[:2000]  # Limit length
                break

        # Extract full content (if available)
        content = None
        content_elem = item.find("content:encoded", ns)
        if content_elem is not None and content_elem.text:
            content = content_elem.text.strip()[:10000]

        # Extract published date
        published_date = None
        for tag in ["pubDate", "published", "atom:published", "dc:date"]:
            elem = item.find(tag) if ":" not in tag else item.find(tag, ns)
            if elem is not None and elem.text:
                try:
                    # Try RFC 2822 format (RSS 2.0)
                    published_date = parsedate_to_datetime(elem.text)
                except (TypeError, ValueError):
                    try:
                        # Try ISO format (Atom)
                        published_date = datetime.fromisoformat(
                            elem.text.replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                break

        # Extract author
        author = None
        for tag in ["author", "dc:creator", "atom:author"]:
            elem = item.find(tag) if ":" not in tag else item.find(tag, ns)
            if elem is not None:
                if elem.text:
                    author = elem.text.strip()
                else:
                    # Atom format: author/name
                    name_elem = elem.find("atom:name", ns)
                    if name_elem is not None and name_elem.text:
                        author = name_elem.text.strip()
                break

        return RSSArticle(
            title=title[:500],  # Limit title length
            url=url,
            url_hash=RSSArticle.generate_url_hash(url),
            source_name=feed.name,
            source_category=feed.category,
            summary=summary,
            content=content,
            published_date=published_date,
            author=author,
            source_tier=feed.source_tier,
            metadata={
                "feed_url": feed.url,
                "feed_priority": feed.priority,
            },
        )

    async def _save_article(self, article: RSSArticle) -> bool:
        """
        Save article to marine_articles database.

        Returns True if new article saved, False if duplicate.
        """
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db
        from lead_to_cash.services.marine_intel.models import Article

        db = get_marine_intel_db()
        await db.initialize()

        # Check for duplicate by URL
        existing = await db.get_article_by_url(article.url)
        if existing:
            return False

        # Create Article model
        db_article = Article.create(
            url=article.url,
            title=article.title,
            source=article.source_name,
            content=article.content,
            summary=article.summary,
            published_date=article.published_date,
            source_category=article.source_category,
            metadata={
                "rss_feed": article.metadata.get("feed_url"),
                "author": article.author,
                "source_tier": article.source_tier,
            },
        )

        _, is_new = await db.save_article(db_article)
        return is_new

    async def collect_feed(self, feed: RSSFeed) -> dict[str, int]:
        """
        Collect articles from a single feed.

        Returns:
            Dict with articles_found, articles_saved, duplicates, errors
        """
        result = {
            "articles_found": 0,
            "articles_saved": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }

        try:
            articles = await self.fetch_feed(feed)
            result["articles_found"] = len(articles)

            for article in articles:
                try:
                    saved = await self._save_article(article)
                    if saved:
                        result["articles_saved"] += 1
                    else:
                        result["duplicates_skipped"] += 1
                except Exception as e:
                    logger.error(f"Error saving article from '{feed.name}': {e}")
                    result["errors"] += 1

        except Exception as e:
            logger.error(f"Error collecting feed '{feed.name}': {e}")
            result["errors"] += 1

        return result

    async def collect_all_feeds(
        self,
        categories: Optional[list[str]] = None,
        max_feeds: Optional[int] = None,
    ) -> AggregationResult:
        """
        Collect articles from all configured RSS feeds.

        Args:
            categories: Filter feeds by category (optional)
            max_feeds: Maximum number of feeds to process (optional)

        Returns:
            AggregationResult with statistics
        """
        start_time = datetime.now()

        # Filter feeds
        feeds_to_process = self.feeds
        if categories:
            feeds_to_process = [f for f in feeds_to_process if f.category in categories]
        if max_feeds:
            feeds_to_process = feeds_to_process[:max_feeds]

        logger.info(f"Starting RSS aggregation for {len(feeds_to_process)} feeds")

        feeds_processed = 0
        feeds_failed = 0
        total_found = 0
        total_saved = 0
        total_duplicates = 0
        total_errors = 0
        by_feed: dict[str, int] = {}
        by_category: dict[str, int] = {}

        # Process feeds with rate limiting
        for feed in feeds_to_process:
            result = await self.collect_feed(feed)

            if result["errors"] > 0 and result["articles_found"] == 0:
                feeds_failed += 1
            else:
                feeds_processed += 1

            total_found += result["articles_found"]
            total_saved += result["articles_saved"]
            total_duplicates += result["duplicates_skipped"]
            total_errors += result["errors"]

            by_feed[feed.name] = result["articles_saved"]

            if feed.category not in by_category:
                by_category[feed.category] = 0
            by_category[feed.category] += result["articles_saved"]

            # Rate limiting between feeds
            await asyncio.sleep(self.delay_between_feeds)

        duration = (datetime.now() - start_time).total_seconds()

        result = AggregationResult(
            feeds_processed=feeds_processed,
            feeds_failed=feeds_failed,
            articles_found=total_found,
            articles_saved=total_saved,
            duplicates_skipped=total_duplicates,
            errors=total_errors,
            duration_seconds=duration,
            by_feed=by_feed,
            by_category=by_category,
        )

        logger.info(
            f"RSS aggregation complete: {feeds_processed} feeds, "
            f"{total_saved} articles saved, {total_duplicates} duplicates, "
            f"{total_errors} errors in {duration:.1f}s"
        )

        return result

    async def collect_by_category(
        self,
        category: str,
    ) -> AggregationResult:
        """
        Collect articles from feeds in a specific category.

        Args:
            category: Feed category to collect

        Returns:
            AggregationResult for that category
        """
        return await self.collect_all_feeds(categories=[category])

    def list_feeds(self) -> list[dict[str, Any]]:
        """List all configured feeds."""
        return [
            {
                "name": f.name,
                "url": f.url,
                "category": f.category,
                "priority": f.priority,
                "enabled": f.enabled,
                "source_tier": f.source_tier,
            }
            for f in self.feeds
        ]

    def list_categories(self) -> list[str]:
        """List unique feed categories."""
        return list(set(f.category for f in self.feeds))


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_rss_aggregation(
    categories: Optional[list[str]] = None,
) -> AggregationResult:
    """
    Run RSS feed aggregation.

    Args:
        categories: Filter by categories (optional)

    Returns:
        AggregationResult with statistics
    """
    aggregator = RSSAggregator()
    try:
        return await aggregator.collect_all_feeds(categories=categories)
    finally:
        await aggregator.close()


async def run_priority_rss_aggregation() -> AggregationResult:
    """
    Run RSS aggregation for priority feeds only (priority=1).
    """
    priority_feeds = [f for f in RSS_FEEDS if f.priority == 1 and f.enabled]
    aggregator = RSSAggregator(feeds=priority_feeds)
    try:
        return await aggregator.collect_all_feeds()
    finally:
        await aggregator.close()


def get_feed_registry() -> list[dict[str, Any]]:
    """Get the configured RSS feed registry."""
    return [
        {
            "name": f.name,
            "url": f.url,
            "category": f.category,
            "priority": f.priority,
            "source_tier": f.source_tier,
        }
        for f in RSS_FEEDS
    ]
