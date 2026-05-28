"""
Press Room Scraper Service

Production-ready LLM-powered web scraper for monitoring official press rooms
of regulatory bodies, industry associations, and engine manufacturers.

Features:
- OpenAI-powered content extraction
- Structured news item parsing
- Entity recognition (companies, vessels, engines)
- Source deduplication
- Rate limiting and error resilience

Usage:
    from lead_to_cash.services.press_room_scraper import PressRoomScraper

    scraper = PressRoomScraper()
    result = await scraper.scrape_all_sources()
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx

from lead_to_cash.utils import AsyncHTTPClientMixin

logger = logging.getLogger(__name__)


# =============================================================================
# Press Room Source Configuration
# =============================================================================


class SourceType(str, Enum):
    """Types of press room sources."""

    REGULATORY = "regulatory"
    ASSOCIATION = "association"
    MANUFACTURER = "manufacturer"
    SHIPYARD = "shipyard"
    CLASSIFICATION = "classification"


@dataclass
class PressRoomSource:
    """Configuration for a press room source."""

    name: str
    url: str
    source_type: SourceType
    region: str
    priority: int = 1  # 1 = highest priority
    enabled: bool = True
    source_tier: int = 1  # 1-4 credibility tier
    selectors: Optional[dict] = None  # CSS selectors for parsing (optional)


# Production Press Room Registry
PRESS_ROOM_SOURCES: list[PressRoomSource] = [
    # Singapore Regulatory (Tier 1 - Highest Authority)
    PressRoomSource(
        name="MPA Singapore",
        url="https://www.mpa.gov.sg/media-centre/news",
        source_type=SourceType.REGULATORY,
        region="singapore",
        priority=1,
        source_tier=1,
    ),
    PressRoomSource(
        name="MPA Singapore Circulars",
        url="https://www.mpa.gov.sg/media-centre/circulars",
        source_type=SourceType.REGULATORY,
        region="singapore",
        priority=1,
        source_tier=1,
    ),
    # International Regulatory (Tier 1)
    PressRoomSource(
        name="IMO Press Briefings",
        url="https://www.imo.org/en/MediaCentre/PressBriefings",
        source_type=SourceType.REGULATORY,
        region="global",
        priority=1,
        source_tier=1,
    ),
    # Singapore Industry Associations (Tier 1-2)
    PressRoomSource(
        name="SMF News",
        url="https://www.smf.com.sg/news",
        source_type=SourceType.ASSOCIATION,
        region="singapore",
        priority=1,
        source_tier=2,
    ),
    PressRoomSource(
        name="SSA News",
        url="https://www.ssa.org.sg/news",
        source_type=SourceType.ASSOCIATION,
        region="singapore",
        priority=2,
        source_tier=2,
    ),
    # Classification Societies (Tier 1 - Technical Authority)
    PressRoomSource(
        name="DNV Maritime",
        url="https://www.dnv.com/news",
        source_type=SourceType.CLASSIFICATION,
        region="global",
        priority=1,
        source_tier=1,
    ),
    PressRoomSource(
        name="Lloyd's Register",
        url="https://www.lr.org/en/latest-news",
        source_type=SourceType.CLASSIFICATION,
        region="global",
        priority=2,
        source_tier=1,
    ),
    # Engine Manufacturers (Tier 1 - Primary Source)
    PressRoomSource(
        name="Wartsila Press",
        url="https://www.wartsila.com/media/news-releases",
        source_type=SourceType.MANUFACTURER,
        region="global",
        priority=1,
        source_tier=1,
    ),
    PressRoomSource(
        name="MAN Energy Solutions",
        url="https://www.man-es.com/company/press",
        source_type=SourceType.MANUFACTURER,
        region="global",
        priority=1,
        source_tier=1,
    ),
    PressRoomSource(
        name="Caterpillar Marine",
        url="https://www.cat.com/en_US/news.html",
        source_type=SourceType.MANUFACTURER,
        region="global",
        priority=2,
        source_tier=1,
    ),
    # Singapore Shipyards (Tier 1 - Primary Source)
    PressRoomSource(
        name="Seatrium",
        url="https://www.seatrium.com/media",
        source_type=SourceType.SHIPYARD,
        region="singapore",
        priority=1,
        source_tier=1,
    ),
    PressRoomSource(
        name="Keppel O&M",
        url="https://www.kepcorp.com/en/media",
        source_type=SourceType.SHIPYARD,
        region="singapore",
        priority=1,
        source_tier=1,
    ),
]


@dataclass
class ExtractedNewsItem:
    """News item extracted from press room."""

    title: str
    url: str
    url_hash: str
    source_name: str
    source_type: str
    region: str
    summary: Optional[str] = None
    published_date: Optional[datetime] = None
    category: str = "general"
    entities: list[str] = field(default_factory=list)
    source_tier: int = 1
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """Generate SHA-256 hash of URL for deduplication."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()


@dataclass
class ScrapeResult:
    """Result of press room scraping."""

    sources_scraped: int
    sources_failed: int
    items_found: int
    items_saved: int
    duplicates_skipped: int
    errors: int
    duration_seconds: float
    by_source: dict = field(default_factory=dict)
    by_type: dict = field(default_factory=dict)


# LLM Extraction Prompt
EXTRACTION_PROMPT = """
Extract all news items from this webpage content. For each news item found, provide:

1. **title**: The headline or title (exact text)
2. **url**: The link/URL to the full article (if available)
3. **date**: Publication date (YYYY-MM-DD format if possible, otherwise as shown)
4. **summary**: First 2-3 sentences of the article content
5. **category**: One of: NEWBUILD, RETROFIT, REGULATION, OFFSHORE, CONTRACT, PRODUCT, GENERAL
6. **entities**: List of companies, vessel names, engine models, or organizations mentioned

Return as a JSON array of objects. Only include items from the last 90 days if dates are visible.
If a field is not available, use null.

Example format:
```json
[
  {
    "title": "Company X Wins Contract for New Ferry",
    "url": "https://example.com/news/article1",
    "date": "2026-01-15",
    "summary": "Company X has been awarded a contract to build...",
    "category": "NEWBUILD",
    "entities": ["Company X", "Ferry Operator Y", "W31 engines"]
  }
]
```

Focus on maritime industry news: vessel orders, engine contracts, regulatory updates,
offshore projects, product launches, and company announcements.
"""


class PressRoomScraper(AsyncHTTPClientMixin):
    """
    LLM-powered press room scraper for maritime intelligence.

    Scrapes official press rooms and uses OpenAI to extract
    structured news items with entity recognition.

    Inherits from AsyncHTTPClientMixin for HTTP client lifecycle management.
    Use as async context manager for automatic cleanup:

        async with PressRoomScraper() as scraper:
            result = await scraper.scrape_all_sources()

    Features:
    - Multi-source scraping with priority ordering
    - LLM-powered content extraction
    - Entity recognition (companies, vessels, engines)
    - Source deduplication
    - Rate limiting
    """

    # Browser-like headers for web scraping
    SCRAPER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(
        self,
        sources: Optional[list[PressRoomSource]] = None,
        openai_api_key: Optional[str] = None,
        timeout: int = 60,
        delay_between_sources: float = 2.0,
    ) -> None:
        """
        Initialize press room scraper.

        Args:
            sources: Custom source list (defaults to PRESS_ROOM_SOURCES)
            openai_api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            timeout: HTTP request timeout in seconds
            delay_between_sources: Delay between source scrapes (rate limiting)
        """
        super().__init__(
            timeout=float(timeout),
            headers=self.SCRAPER_HEADERS,
            follow_redirects=True,
        )
        self.sources = sources or [s for s in PRESS_ROOM_SOURCES if s.enabled]
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.delay_between_sources = delay_between_sources

        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set - extraction will fail")

    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch webpage content.

        Args:
            url: URL to fetch

        Returns:
            Page HTML content or None if failed
        """
        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: status {response.status_code}")
                return None

            return response.text

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def _clean_html(self, html: str) -> str:
        """
        Clean HTML content for LLM processing.

        Removes scripts, styles, and normalizes whitespace.
        Limits content length for API efficiency.
        """
        # Remove script and style elements
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(
            r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Remove extra whitespace
        html = re.sub(r"\s+", " ", html)

        # Limit length (OpenAI has token limits)
        max_chars = 50000
        if len(html) > max_chars:
            html = html[:max_chars]

        return html.strip()

    async def extract_news_items(
        self,
        html: str,
        source: PressRoomSource,
    ) -> list[ExtractedNewsItem]:
        """
        Extract news items from HTML using OpenAI.

        Args:
            html: Page HTML content
            source: Source configuration

        Returns:
            List of extracted news items
        """
        if not self.openai_api_key:
            logger.error("OpenAI API key not configured")
            return []

        cleaned_html = self._clean_html(html)

        try:
            client = await self._get_client()

            # Call OpenAI API
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a maritime industry news extraction assistant. Extract news items from webpage content and return as JSON.",
                        },
                        {
                            "role": "user",
                            "content": f"{EXTRACTION_PROMPT}\n\nWebpage content from {source.name} ({source.url}):\n\n{cleaned_html}",
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )

            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code}")
                return []

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON response
            try:
                parsed = json.loads(content)
                # Handle both array and object with 'items' key
                items = parsed if isinstance(parsed, list) else parsed.get("items", [])
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                return []

            # Convert to ExtractedNewsItem objects
            extracted = []
            base_url = f"{urlparse(source.url).scheme}://{urlparse(source.url).netloc}"

            for item in items:
                if not item.get("title"):
                    continue

                # Resolve relative URLs
                item_url = item.get("url") or source.url
                if item_url and not item_url.startswith("http"):
                    item_url = urljoin(base_url, item_url)

                # Parse date
                published_date = None
                if item.get("date"):
                    try:
                        published_date = datetime.fromisoformat(item["date"])
                    except ValueError:
                        # Try common date formats
                        for fmt in [
                            "%Y-%m-%d",
                            "%d %b %Y",
                            "%B %d, %Y",
                            "%d/%m/%Y",
                        ]:
                            try:
                                published_date = datetime.strptime(item["date"], fmt)
                                break
                            except ValueError:
                                continue

                extracted.append(
                    ExtractedNewsItem(
                        title=item["title"][:500],
                        url=item_url,
                        url_hash=ExtractedNewsItem.generate_url_hash(item_url),
                        source_name=source.name,
                        source_type=source.source_type.value,
                        region=source.region,
                        summary=(
                            item.get("summary", "")[:2000]
                            if item.get("summary")
                            else None
                        ),
                        published_date=published_date,
                        category=item.get("category", "GENERAL"),
                        entities=item.get("entities", []),
                        source_tier=source.source_tier,
                        metadata={
                            "source_url": source.url,
                            "source_priority": source.priority,
                        },
                    )
                )

            logger.info(f"Extracted {len(extracted)} items from {source.name}")
            return extracted

        except Exception as e:
            logger.error(f"Error extracting from {source.name}: {e}")
            return []

    async def _save_item(self, item: ExtractedNewsItem) -> bool:
        """
        Save extracted news item to database.

        Returns True if new item saved, False if duplicate.
        """
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db
        from lead_to_cash.services.marine_intel.models import Article

        db = get_marine_intel_db()
        await db.initialize()

        # Check for duplicate by URL
        existing = await db.get_article_by_url(item.url)
        if existing:
            return False

        # Create Article model
        article = Article.create(
            url=item.url,
            title=item.title,
            source=item.source_name,
            content=None,  # Press room scraping gets summary only
            summary=item.summary,
            published_date=item.published_date,
            source_category=item.source_type,
            metadata={
                "region": item.region,
                "category": item.category,
                "entities": item.entities,
                "source_tier": item.source_tier,
                **item.metadata,
            },
        )

        _, is_new = await db.save_article(article)
        return is_new

    async def scrape_source(self, source: PressRoomSource) -> dict[str, int]:
        """
        Scrape a single press room source.

        Returns:
            Dict with items_found, items_saved, duplicates, errors
        """
        result = {
            "items_found": 0,
            "items_saved": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }

        logger.info(f"Scraping {source.name} ({source.url})")

        try:
            # Fetch page
            html = await self.fetch_page(source.url)
            if not html:
                result["errors"] += 1
                return result

            # Extract news items
            items = await self.extract_news_items(html, source)
            result["items_found"] = len(items)

            # Save items
            for item in items:
                try:
                    saved = await self._save_item(item)
                    if saved:
                        result["items_saved"] += 1
                    else:
                        result["duplicates_skipped"] += 1
                except Exception as e:
                    logger.error(f"Error saving item from {source.name}: {e}")
                    result["errors"] += 1

        except Exception as e:
            logger.error(f"Error scraping {source.name}: {e}")
            result["errors"] += 1

        return result

    async def scrape_all_sources(
        self,
        source_types: Optional[list[SourceType]] = None,
        max_sources: Optional[int] = None,
    ) -> ScrapeResult:
        """
        Scrape all configured press room sources.

        Args:
            source_types: Filter by source type (optional)
            max_sources: Maximum sources to scrape (optional)

        Returns:
            ScrapeResult with statistics
        """
        start_time = datetime.now()

        # Filter sources
        sources_to_scrape = self.sources
        if source_types:
            sources_to_scrape = [
                s for s in sources_to_scrape if s.source_type in source_types
            ]
        if max_sources:
            sources_to_scrape = sources_to_scrape[:max_sources]

        # Sort by priority
        sources_to_scrape = sorted(sources_to_scrape, key=lambda s: s.priority)

        logger.info(
            f"Starting press room scraping for {len(sources_to_scrape)} sources"
        )

        sources_scraped = 0
        sources_failed = 0
        total_found = 0
        total_saved = 0
        total_duplicates = 0
        total_errors = 0
        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for source in sources_to_scrape:
            result = await self.scrape_source(source)

            if result["errors"] > 0 and result["items_found"] == 0:
                sources_failed += 1
            else:
                sources_scraped += 1

            total_found += result["items_found"]
            total_saved += result["items_saved"]
            total_duplicates += result["duplicates_skipped"]
            total_errors += result["errors"]

            by_source[source.name] = result["items_saved"]

            source_type = source.source_type.value
            if source_type not in by_type:
                by_type[source_type] = 0
            by_type[source_type] += result["items_saved"]

            # Rate limiting
            await asyncio.sleep(self.delay_between_sources)

        duration = (datetime.now() - start_time).total_seconds()

        scrape_result = ScrapeResult(
            sources_scraped=sources_scraped,
            sources_failed=sources_failed,
            items_found=total_found,
            items_saved=total_saved,
            duplicates_skipped=total_duplicates,
            errors=total_errors,
            duration_seconds=duration,
            by_source=by_source,
            by_type=by_type,
        )

        logger.info(
            f"Press room scraping complete: {sources_scraped} sources, "
            f"{total_saved} items saved, {total_duplicates} duplicates, "
            f"{total_errors} errors in {duration:.1f}s"
        )

        return scrape_result

    async def scrape_regulatory(self) -> ScrapeResult:
        """Scrape regulatory sources only."""
        return await self.scrape_all_sources(source_types=[SourceType.REGULATORY])

    async def scrape_manufacturers(self) -> ScrapeResult:
        """Scrape manufacturer press rooms only."""
        return await self.scrape_all_sources(source_types=[SourceType.MANUFACTURER])

    async def scrape_shipyards(self) -> ScrapeResult:
        """Scrape shipyard press rooms only."""
        return await self.scrape_all_sources(source_types=[SourceType.SHIPYARD])

    def list_sources(self) -> list[dict[str, Any]]:
        """List all configured sources."""
        return [
            {
                "name": s.name,
                "url": s.url,
                "type": s.source_type.value,
                "region": s.region,
                "priority": s.priority,
                "enabled": s.enabled,
                "source_tier": s.source_tier,
            }
            for s in self.sources
        ]


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_press_room_scraping(
    source_types: Optional[list[str]] = None,
) -> ScrapeResult:
    """
    Run press room scraping.

    Args:
        source_types: Filter by types (regulatory, manufacturer, etc.)

    Returns:
        ScrapeResult with statistics
    """
    types = [SourceType(t) for t in source_types] if source_types else None
    scraper = PressRoomScraper()
    try:
        return await scraper.scrape_all_sources(source_types=types)
    finally:
        await scraper.close()


async def run_regulatory_scraping() -> ScrapeResult:
    """Scrape regulatory sources (MPA, IMO)."""
    scraper = PressRoomScraper()
    try:
        return await scraper.scrape_regulatory()
    finally:
        await scraper.close()


async def run_manufacturer_scraping() -> ScrapeResult:
    """Scrape manufacturer press rooms (Wartsila, MAN, etc.)."""
    scraper = PressRoomScraper()
    try:
        return await scraper.scrape_manufacturers()
    finally:
        await scraper.close()


def get_source_registry() -> list[dict[str, Any]]:
    """Get the configured press room source registry."""
    return [
        {
            "name": s.name,
            "url": s.url,
            "type": s.source_type.value,
            "region": s.region,
            "source_tier": s.source_tier,
        }
        for s in PRESS_ROOM_SOURCES
    ]
