"""
Targeted Web Scraper for Competitor Intelligence

Monitors specific competitor website sections:
- Newsroom/press releases (daily)
- Marine product pages (weekly)
- Technology/insights pages (weekly)

Uses BeautifulSoup for HTML parsing with rate limiting and error handling.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ScrapedContent:
    """Content scraped from a competitor website."""

    competitor: str
    source_channel: str  # website_newsroom, website_product, website_insights
    url: str
    title: str
    content: str
    published_date: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Generate hash for deduplication."""
        return hashlib.sha256(f"{self.url}:{self.title}".encode()).hexdigest()[:16]


class TargetedWebScraper:
    """
    Targeted web scraper for specific competitor content types.

    Monitors:
    - Newsroom/press releases (daily)
    - Marine product pages (weekly)
    - Technology/insights pages (weekly)
    """

    # Competitor website configurations
    # NOTE: Caterpillar and Cummins websites block web scraping (403 Forbidden)
    # These competitors are better monitored via Perplexity API (social_media_scraper)
    # Only MAN-ES allows web scraping
    COMPETITOR_URLS = {
        "caterpillar": {
            # BLOCKED: caterpillar.com returns 403 for all pages (WAF/anti-bot)
            # Use Perplexity API instead for Caterpillar news
            "newsroom": [],  # Blocked - see social_media_scraper
            "product_pages": [],  # Blocked
            "insights": [],  # Blocked
        },
        "cummins": {
            # BLOCKED: cummins.com returns 403 for all pages (WAF/anti-bot)
            # Use Perplexity API instead for Cummins news
            "newsroom": [],  # Blocked - see social_media_scraper
            "product_pages": [],  # Blocked
            "insights": [],  # Blocked
        },
        "man_energy": {
            "newsroom": [
                "https://www.man-es.com/company/press-releases",
                # NOTE: /discover/news returns 404 as of 2026-01-21
            ],
            "product_pages": [
                "https://www.man-es.com/marine/products/propulsion-engines",
                "https://www.man-es.com/marine",
            ],
            "insights": [
                "https://www.man-es.com/discover/technology",
                "https://www.man-es.com/discover/decarbonization",
            ],
        },
    }

    # Rate limiting
    REQUEST_DELAY = 2.0  # seconds between requests
    MAX_RETRIES = 3
    TIMEOUT = 30.0

    def __init__(self):
        """Initialize the scraper."""
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
        self._seen_urls: set[str] = set()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            await asyncio.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a single page with retry logic.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None if failed
        """
        await self._rate_limit()
        client = await self._get_client()

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    logger.warning(f"Page not found: {url}")
                    return None
                else:
                    logger.warning(
                        f"HTTP {response.status_code} for {url}, attempt {attempt + 1}"
                    )
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url}, attempt {attempt + 1}")
            except httpx.RequestError as e:
                logger.error(f"Request error for {url}: {e}")
                return None

            # Exponential backoff
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)

        return None

    def _parse_newsroom(
        self, html: str, competitor: str, base_url: str
    ) -> list[ScrapedContent]:
        """
        Parse newsroom/press release page.

        Extracts:
        - Article titles
        - Article URLs
        - Published dates (if available)
        - Article summaries
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Common patterns for news/press release pages
        selectors = [
            # Generic article patterns
            "article",
            ".news-item",
            ".press-release",
            ".news-article",
            ".media-item",
            # List patterns
            ".news-list li",
            ".press-list li",
            ".article-list li",
            # Card patterns
            ".news-card",
            ".article-card",
            ".content-card",
        ]

        articles: list = []  # type: ignore[type-arg]
        for selector in selectors:
            found = soup.select(selector)
            if found:
                articles.extend(found)
                break  # Use first matching selector

        # Fallback: look for links with news-related patterns
        if not articles:
            articles = soup.find_all("a", href=True)
            articles = [
                a
                for a in articles
                if any(
                    x in str(a.get("href", "")).lower()  # type: ignore[union-attr]
                    for x in ["news", "press", "release", "article"]
                )
            ]

        for article in articles[:20]:  # Limit to 20 items
            try:
                # Find title
                title_elem = article.find(["h1", "h2", "h3", "h4", "a"])  # type: ignore[attr-defined]
                title = title_elem.get_text(strip=True) if title_elem else ""

                if not title or len(title) < 10:
                    continue

                # Find URL
                link = article.find("a", href=True)  # type: ignore[attr-defined]
                if link:
                    url = urljoin(base_url, link["href"])
                else:
                    continue

                # Skip if already seen
                if url in self._seen_urls:
                    continue
                self._seen_urls.add(url)

                # Find date
                date_elem = article.find(["time", ".date", ".published"])  # type: ignore[attr-defined]
                published_date = None
                if date_elem:
                    date_str = date_elem.get("datetime") or date_elem.get_text(
                        strip=True
                    )
                    published_date = self._parse_date(date_str)

                # Find summary/description
                summary_elem = article.find(  # type: ignore[attr-defined]
                    ["p", ".summary", ".description", ".excerpt"]
                )
                summary = summary_elem.get_text(strip=True) if summary_elem else ""

                content = f"{title}\n\n{summary}" if summary else title

                results.append(
                    ScrapedContent(
                        competitor=competitor,
                        source_channel="website_newsroom",
                        url=url,
                        title=title,
                        content=content,
                        published_date=published_date,
                        metadata={"base_url": base_url},
                    )
                )

            except Exception as e:
                logger.debug(f"Error parsing article: {e}")
                continue

        return results

    def _parse_product_page(
        self, html: str, competitor: str, base_url: str
    ) -> list[ScrapedContent]:
        """
        Parse product pages for marine engines and power systems.

        Extracts:
        - Product names
        - Product descriptions
        - Specifications
        - Product URLs
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Product patterns
        selectors = [
            ".product",
            ".product-item",
            ".product-card",
            ".engine-item",
            "[data-product]",
            ".model-item",
        ]

        products: list = []  # type: ignore[type-arg]
        for selector in selectors:
            found = soup.select(selector)
            if found:
                products.extend(found)
                break

        # Fallback: parse main content
        if not products:
            main_content = soup.find(["main", "#content", ".content", "article"])
            if main_content:
                # Get all sections with headings
                sections = main_content.find_all(["section", "div"], recursive=False)  # type: ignore[attr-defined]
                products = sections if sections else [main_content]

        for product in products[:15]:
            try:
                # Find title
                title_elem = product.find(["h1", "h2", "h3", "h4"])
                title = title_elem.get_text(strip=True) if title_elem else ""

                if not title or len(title) < 5:
                    continue

                # Find URL (if product has dedicated page)
                link = product.find("a", href=True)
                url = urljoin(base_url, link["href"]) if link else base_url

                # Skip if already seen
                if url in self._seen_urls and url != base_url:
                    continue
                if url != base_url:
                    self._seen_urls.add(url)

                # Get product description
                desc_elems = product.find_all(["p", ".description", ".specs"])
                description = " ".join(
                    elem.get_text(strip=True) for elem in desc_elems[:3]
                )

                content = f"{title}\n\n{description}" if description else title

                results.append(
                    ScrapedContent(
                        competitor=competitor,
                        source_channel="website_product",
                        url=url,
                        title=title,
                        content=content,
                        metadata={"base_url": base_url, "type": "product"},
                    )
                )

            except Exception as e:
                logger.debug(f"Error parsing product: {e}")
                continue

        return results

    def _parse_insights_page(
        self, html: str, competitor: str, base_url: str
    ) -> list[ScrapedContent]:
        """
        Parse technology/insights/sustainability pages.

        Extracts:
        - Technology announcements
        - Sustainability initiatives
        - Innovation content
        - Thought leadership articles
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Insights patterns
        selectors = [
            "article",
            ".insight",
            ".story",
            ".technology-item",
            ".initiative",
            ".content-block",
        ]

        items: list = []  # type: ignore[type-arg]
        for selector in selectors:
            found = soup.select(selector)
            if found:
                items.extend(found)
                break

        # Fallback: get main content sections
        if not items:
            main_content = soup.find(["main", "#content", ".content"])
            if main_content:
                items = main_content.find_all(  # type: ignore[attr-defined]
                    ["section", "article", "div"], class_=True
                )

        for item in items[:15]:
            try:
                # Find title
                title_elem = item.find(["h1", "h2", "h3", "h4"])
                title = title_elem.get_text(strip=True) if title_elem else ""

                if not title or len(title) < 10:
                    continue

                # Find URL
                link = item.find("a", href=True)
                url = urljoin(base_url, link["href"]) if link else base_url

                # Skip duplicates
                if url in self._seen_urls and url != base_url:
                    continue
                if url != base_url:
                    self._seen_urls.add(url)

                # Get content
                content_elems = item.find_all(["p"])
                content_text = " ".join(
                    elem.get_text(strip=True) for elem in content_elems[:5]
                )

                content = f"{title}\n\n{content_text}" if content_text else title

                results.append(
                    ScrapedContent(
                        competitor=competitor,
                        source_channel="website_insights",
                        url=url,
                        title=title,
                        content=content,
                        metadata={"base_url": base_url, "type": "insights"},
                    )
                )

            except Exception as e:
                logger.debug(f"Error parsing insight: {e}")
                continue

        return results

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue

        return None

    async def scrape_newsroom(self, competitor: str) -> list[ScrapedContent]:
        """
        Scrape newsroom pages for a competitor.

        Args:
            competitor: Competitor identifier (caterpillar, cummins, man_energy)

        Returns:
            List of scraped content items
        """
        if competitor not in self.COMPETITOR_URLS:
            logger.error(f"Unknown competitor: {competitor}")
            return []

        urls = self.COMPETITOR_URLS[competitor].get("newsroom", [])
        results = []

        for url in urls:
            logger.info(f"Scraping newsroom: {url}")
            html = await self._fetch_page(url)
            if html:
                parsed = self._parse_newsroom(html, competitor, url)
                results.extend(parsed)
                logger.info(f"Found {len(parsed)} items from {url}")

        return results

    async def scrape_product_pages(self, competitor: str) -> list[ScrapedContent]:
        """
        Scrape product pages for a competitor.

        Args:
            competitor: Competitor identifier

        Returns:
            List of scraped content items
        """
        if competitor not in self.COMPETITOR_URLS:
            logger.error(f"Unknown competitor: {competitor}")
            return []

        urls = self.COMPETITOR_URLS[competitor].get("product_pages", [])
        results = []

        for url in urls:
            logger.info(f"Scraping product page: {url}")
            html = await self._fetch_page(url)
            if html:
                parsed = self._parse_product_page(html, competitor, url)
                results.extend(parsed)
                logger.info(f"Found {len(parsed)} items from {url}")

        return results

    async def scrape_insights(self, competitor: str) -> list[ScrapedContent]:
        """
        Scrape technology/insights pages for a competitor.

        Args:
            competitor: Competitor identifier

        Returns:
            List of scraped content items
        """
        if competitor not in self.COMPETITOR_URLS:
            logger.error(f"Unknown competitor: {competitor}")
            return []

        urls = self.COMPETITOR_URLS[competitor].get("insights", [])
        results = []

        for url in urls:
            logger.info(f"Scraping insights page: {url}")
            html = await self._fetch_page(url)
            if html:
                parsed = self._parse_insights_page(html, competitor, url)
                results.extend(parsed)
                logger.info(f"Found {len(parsed)} items from {url}")

        return results

    async def scrape_all_newsrooms(self) -> list[ScrapedContent]:
        """Scrape newsrooms for all competitors."""
        results = []
        for competitor in self.COMPETITOR_URLS.keys():
            items = await self.scrape_newsroom(competitor)
            results.extend(items)
        return results

    async def scrape_all_product_pages(self) -> list[ScrapedContent]:
        """Scrape product pages for all competitors."""
        results = []
        for competitor in self.COMPETITOR_URLS.keys():
            items = await self.scrape_product_pages(competitor)
            results.extend(items)
        return results

    async def scrape_all_insights(self) -> list[ScrapedContent]:
        """Scrape insights pages for all competitors."""
        results = []
        for competitor in self.COMPETITOR_URLS.keys():
            items = await self.scrape_insights(competitor)
            results.extend(items)
        return results

    async def full_scrape(
        self, competitor: Optional[str] = None
    ) -> list[ScrapedContent]:
        """
        Perform full scrape of all page types.

        Args:
            competitor: Optional specific competitor to scrape

        Returns:
            All scraped content items
        """
        results = []
        competitors = [competitor] if competitor else list(self.COMPETITOR_URLS.keys())

        for comp in competitors:
            logger.info(f"Starting full scrape for {comp}")

            # Newsroom (highest priority)
            news = await self.scrape_newsroom(comp)
            results.extend(news)

            # Product pages
            products = await self.scrape_product_pages(comp)
            results.extend(products)

            # Insights
            insights = await self.scrape_insights(comp)
            results.extend(insights)

            logger.info(
                f"Completed scrape for {comp}: {len(news)} news, "
                f"{len(products)} products, {len(insights)} insights"
            )

        return results

    def reset_seen_urls(self):
        """Reset the seen URLs set for a fresh scrape."""
        self._seen_urls.clear()


# Singleton instance
_scraper: Optional[TargetedWebScraper] = None


def get_targeted_web_scraper() -> TargetedWebScraper:
    """Get or create the targeted web scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = TargetedWebScraper()
    return _scraper
