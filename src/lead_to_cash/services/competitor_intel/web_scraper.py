"""
Web Scraper for Competitor Intelligence

Direct web scraping using BeautifulSoup for competitor product pages,
press releases, and other web content.

NO MOCKS, NO SIMULATIONS - real HTTP requests to competitor websites.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from lead_to_cash.services.competitor_intel.models import (
    CompetitorDocument,
    ContentType,
    SourceType,
)

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Production web scraper for competitor websites.

    Scrapes product pages, press releases, and news from:
    - Caterpillar Marine: cat.com, caterpillar.com
    - Cummins Marine: cummins.com
    - MAN Energy Solutions: man-es.com
    """

    # Real competitor URLs for scraping
    COMPETITOR_URLS = {
        "caterpillar": {
            "product_pages": [
                "https://www.cat.com/en_US/products/new/power-systems/marine-power-systems.html",
                "https://www.cat.com/en_US/products/new/power-systems/marine-power-systems/propulsion-engines.html",
                "https://www.cat.com/en_US/products/new/power-systems/marine-power-systems/auxiliary-engines.html",
                "https://www.cat.com/en_US/products/new/power-systems/marine-power-systems/generator-sets.html",
            ],
            "press_releases": "https://www.caterpillar.com/en/news/corporate-press-releases.html",
            "news_page": "https://www.caterpillar.com/en/news.html",
            "marine_solutions": "https://www.cat.com/en_US/by-industry/marine.html",
        },
        "cummins": {
            "product_pages": [
                "https://www.cummins.com/engines/marine",
                "https://www.cummins.com/engines/marine/commercial",
                "https://www.cummins.com/engines/marine/recreational",
                "https://www.cummins.com/engines/marine/high-horsepower",
            ],
            "press_releases": "https://www.cummins.com/news/releases",
            "news_page": "https://www.cummins.com/news",
            "marine_solutions": "https://www.cummins.com/marine",
        },
        "man_energy": {
            "product_pages": [
                "https://www.man-es.com/marine/products/propulsion-engines",
                "https://www.man-es.com/marine/products/auxiliary-systems",
                "https://www.man-es.com/marine/products/turbocharger",
                "https://www.man-es.com/marine/products/propeller",
            ],
            "press_releases": "https://www.man-es.com/company/press-releases",
            "news_page": "https://www.man-es.com/discover/news",
            "marine_solutions": "https://www.man-es.com/marine",
        },
        "wartsila": {
            "product_pages": [
                "https://www.wartsila.com/marine/products/engines-and-generating-sets",
                "https://www.wartsila.com/marine/products/propulsors-and-gears",
                "https://www.wartsila.com/marine/products/hybrid-solutions",
            ],
            "press_releases": "https://www.wartsila.com/media/news",
            "news_page": "https://www.wartsila.com/insights",
            "marine_solutions": "https://www.wartsila.com/marine",
        },
        "volvo_penta": {
            "product_pages": [
                "https://www.volvopenta.com/marine/products/engines/",
                "https://www.volvopenta.com/marine/products/gensets/",
                "https://www.volvopenta.com/marine/products/transmissions/",
            ],
            "press_releases": "https://www.volvopenta.com/about-us/news-and-media/news/",
            "news_page": "https://www.volvopenta.com/about-us/news-and-media/",
            "marine_solutions": "https://www.volvopenta.com/marine/",
        },
        "yanmar": {
            "product_pages": [
                "https://www.yanmar.com/global/marinecommercial/products/",
                "https://www.yanmar.com/global/marinecommercial/products/propulsion/",
                "https://www.yanmar.com/global/marinecommercial/products/auxiliary/",
            ],
            "press_releases": "https://www.yanmar.com/global/news/",
            "news_page": "https://www.yanmar.com/global/news/",
            "marine_solutions": "https://www.yanmar.com/global/marinecommercial/",
        },
    }

    # HTTP headers to mimic a real browser
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with browser-like headers."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.HEADERS,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Core Scraping Methods
    # =========================================================================

    async def scrape_page(self, url: str) -> dict[str, Any]:
        """
        Scrape a single web page and extract content.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with title, content, url, and metadata
        """
        logger.info(f"Scraping: {url}")

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Remove unwanted elements
            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "footer",
                    "header",
                    "aside",
                    "noscript",
                    "iframe",
                    "form",
                ]
            ):
                tag.decompose()

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string or ""
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)

            # Extract main content
            # Try to find main content area first
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find(class_=re.compile(r"content|main|body"))
            )

            if main_content:
                content = main_content.get_text(separator="\n", strip=True)
            else:
                content = soup.get_text(separator="\n", strip=True)

            # Clean up content - remove excessive whitespace
            content = re.sub(r"\n\s*\n", "\n\n", content)
            content = re.sub(r" +", " ", content)

            # Extract metadata
            meta_description = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_description = meta_tag.get("content", "")  # type: ignore[attr-defined]

            # Extract links for potential follow-up scraping
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]  # type: ignore[index]
                if href.startswith("/"):  # type: ignore[union-attr]
                    href = urljoin(url, href)
                if href.startswith("http"):  # type: ignore[union-attr]
                    links.append(href)

            return {
                "title": title.strip(),
                "content": content.strip(),
                "url": url,
                "meta_description": meta_description,
                "links": links[:50],  # Limit links
                "scraped_at": datetime.now(timezone.utc),
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping {url}: {e}")
            return {
                "title": "",
                "content": "",
                "url": url,
                "error": str(e),
                "scraped_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "title": "",
                "content": "",
                "url": url,
                "error": str(e),
                "scraped_at": datetime.now(timezone.utc),
            }

    async def scrape_press_releases(self, url: str, competitor: str) -> list[dict]:
        """
        Scrape press release listings and extract individual releases.

        Args:
            url: Press release listing page URL
            competitor: Competitor identifier

        Returns:
            List of scraped press release data
        """
        logger.info(f"Scraping press releases from: {url}")

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            releases = []

            # Find press release links - different patterns for each site
            article_links: list[str] = []

            if "caterpillar" in competitor:
                # Caterpillar uses specific class patterns
                for anchor in soup.find_all("a", href=True):
                    href = str(anchor.get("href", ""))  # type: ignore[union-attr]
                    if "press-release" in href.lower() or "news" in href.lower():
                        if href.startswith("/"):
                            href = urljoin(url, href)
                        article_links.append(href)

            elif "cummins" in competitor:
                # Cummins news page structure
                for anchor in soup.find_all("a", href=True):
                    href = str(anchor.get("href", ""))  # type: ignore[union-attr]
                    if "/news/" in href or "/releases/" in href:
                        if href.startswith("/"):
                            href = urljoin(url, href)
                        article_links.append(href)

            elif "man_energy" in competitor:
                # MAN ES press release structure
                for anchor in soup.find_all("a", href=True):
                    href = str(anchor.get("href", ""))  # type: ignore[union-attr]
                    if "press-release" in href.lower() or "news" in href.lower():
                        if href.startswith("/"):
                            href = urljoin(url, href)
                        article_links.append(href)

            # Deduplicate and limit
            article_links = list(dict.fromkeys(article_links))[:10]

            # Scrape each press release (with rate limiting)
            for article_link in article_links:
                await asyncio.sleep(1)  # Rate limiting
                data = await self.scrape_page(article_link)
                if data.get("content"):
                    releases.append(data)

            return releases

        except Exception as e:
            logger.error(f"Error scraping press releases from {url}: {e}")
            return []

    # =========================================================================
    # Competitor-Specific Scraping
    # =========================================================================

    async def scrape_competitor(self, competitor: str) -> list[CompetitorDocument]:
        """
        Scrape all configured pages for a competitor.

        Args:
            competitor: Competitor identifier (caterpillar, cummins, man_energy)

        Returns:
            List of CompetitorDocument objects
        """
        if competitor not in self.COMPETITOR_URLS:
            logger.error(f"Unknown competitor: {competitor}")
            return []

        urls = self.COMPETITOR_URLS[competitor]
        documents = []

        # Scrape product pages
        for product_url in urls.get("product_pages", []):
            await asyncio.sleep(1)  # Rate limiting
            data = await self.scrape_page(product_url)

            if data.get("content") and not data.get("error"):
                doc = CompetitorDocument(
                    id=self._generate_doc_id(product_url),
                    competitor=competitor,
                    content_type=ContentType.PRODUCT_PAGE.value,
                    source_type=SourceType.WEB_SCRAPE.value,
                    title=data["title"] or f"{competitor.title()} Product Page",
                    content=data["content"],
                    summary=data.get("meta_description"),
                    source_url=product_url,
                    scraped_at=data["scraped_at"],
                    metadata={
                        "links": data.get("links", [])[:10],
                        "scrape_method": "web_scraper",
                    },
                )
                documents.append(doc)

        # Scrape marine solutions page
        marine_url = urls.get("marine_solutions")
        if marine_url and isinstance(marine_url, str):
            await asyncio.sleep(1)
            data = await self.scrape_page(marine_url)

            if data.get("content") and not data.get("error"):
                doc = CompetitorDocument(
                    id=self._generate_doc_id(marine_url),
                    competitor=competitor,
                    content_type=ContentType.SERVICE_OFFERING.value,
                    source_type=SourceType.WEB_SCRAPE.value,
                    title=data["title"] or f"{competitor.title()} Marine Solutions",
                    content=data["content"],
                    summary=data.get("meta_description"),
                    source_url=marine_url,
                    scraped_at=data["scraped_at"],
                    metadata={"scrape_method": "web_scraper"},
                )
                documents.append(doc)

        # Scrape press releases
        press_url = urls.get("press_releases")
        if press_url and isinstance(press_url, str):
            releases = await self.scrape_press_releases(press_url, competitor)

            for release in releases:
                if release.get("content") and not release.get("error"):
                    doc = CompetitorDocument(
                        id=self._generate_doc_id(release["url"]),
                        competitor=competitor,
                        content_type=ContentType.PRESS_RELEASE.value,
                        source_type=SourceType.WEB_SCRAPE.value,
                        title=release["title"] or "Press Release",
                        content=release["content"],
                        summary=release.get("meta_description"),
                        source_url=release["url"],
                        scraped_at=release["scraped_at"],
                        metadata={"scrape_method": "web_scraper"},
                    )
                    documents.append(doc)

        # Scrape news page
        news_url = urls.get("news_page")
        if news_url and isinstance(news_url, str):
            await asyncio.sleep(1)
            data = await self.scrape_page(news_url)

            if data.get("content") and not data.get("error"):
                doc = CompetitorDocument(
                    id=self._generate_doc_id(news_url),
                    competitor=competitor,
                    content_type=ContentType.NEWS.value,
                    source_type=SourceType.WEB_SCRAPE.value,
                    title=data["title"] or f"{competitor.title()} News",
                    content=data["content"],
                    summary=data.get("meta_description"),
                    source_url=news_url,
                    scraped_at=data["scraped_at"],
                    metadata={
                        "links": data.get("links", [])[:10],
                        "scrape_method": "web_scraper",
                    },
                )
                documents.append(doc)

        logger.info(f"Scraped {len(documents)} documents for {competitor}")
        return documents

    async def scrape_all_competitors(self) -> list[CompetitorDocument]:
        """Scrape all configured competitors."""
        all_documents = []

        for competitor in self.COMPETITOR_URLS.keys():
            try:
                docs = await self.scrape_competitor(competitor)
                all_documents.extend(docs)
            except Exception as e:
                logger.error(f"Error scraping {competitor}: {e}")

        return all_documents

    # =========================================================================
    # Utilities
    # =========================================================================

    def _generate_doc_id(self, url: str) -> str:
        """Generate a deterministic document ID from URL."""
        # Use URL hash for deduplication
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"web_{url_hash}"


# Singleton instance
_web_scraper: Optional[WebScraper] = None


def get_web_scraper() -> WebScraper:
    """Get or create the web scraper singleton."""
    global _web_scraper
    if _web_scraper is None:
        _web_scraper = WebScraper()
    return _web_scraper
