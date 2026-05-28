"""
OpenCorporates Client

Web scraping client for global company lookups.
OpenCorporates provides company data for 140+ jurisdictions.
Rate limit: 10 requests/minute for free tier.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class OpenCorporatesEntity:
    """Entity data from OpenCorporates."""

    company_number: str
    jurisdiction_code: str
    name: str

    # Status and dates
    status: Optional[str] = None  # active, dissolved, etc.
    incorporation_date: Optional[datetime] = None
    dissolution_date: Optional[datetime] = None

    # Company details
    company_type: Optional[str] = None
    registered_address: Optional[str] = None

    # OpenCorporates specific
    opencorporates_url: Optional[str] = None
    registry_url: Optional[str] = None

    # Raw data for storage
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "company_number": self.company_number,
            "jurisdiction_code": self.jurisdiction_code,
            "name": self.name,
            "status": self.status,
            "incorporation_date": (
                self.incorporation_date.isoformat() if self.incorporation_date else None
            ),
            "dissolution_date": (
                self.dissolution_date.isoformat() if self.dissolution_date else None
            ),
            "company_type": self.company_type,
            "registered_address": self.registered_address,
            "opencorporates_url": self.opencorporates_url,
            "registry_url": self.registry_url,
        }


class OpenCorporatesClient:
    """
    OpenCorporates client for global company lookups.

    Uses web scraping from opencorporates.com.
    Rate limited to 10 requests/minute.
    """

    BASE_URL = "https://opencorporates.com"
    SEARCH_URL = "https://opencorporates.com/companies"

    # Jurisdiction code mappings
    JURISDICTION_MAP = {
        "SG": "sg",
        "US": "us",  # Will need state, e.g., us_de
        "GB": "gb",
        "DE": "de",
        "DK": "dk",
        "NL": "nl",
        "NO": "no",
        "AU": "au",
        "HK": "hk",
        "JP": "jp",
        "CN": "cn",
    }

    RATE_LIMIT = 10  # requests per minute
    RATE_WINDOW = 60  # seconds

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._request_times: list[float] = []

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = asyncio.get_event_loop().time()

        # Remove old timestamps outside the window
        self._request_times = [
            t for t in self._request_times if now - t < self.RATE_WINDOW
        ]

        # If at limit, wait
        if len(self._request_times) >= self.RATE_LIMIT:
            oldest = min(self._request_times)
            wait_time = self.RATE_WINDOW - (now - oldest) + 0.1
            if wait_time > 0:
                logger.debug(f"OpenCorporates rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def get_company(
        self,
        jurisdiction: str,
        company_number: str,
    ) -> Optional[OpenCorporatesEntity]:
        """
        Get company by jurisdiction and company number.

        Args:
            jurisdiction: Jurisdiction code (e.g., "sg", "gb")
            company_number: Company registration number

        Returns:
            OpenCorporatesEntity or None if not found
        """
        jurisdiction = jurisdiction.lower()
        await self._rate_limit()
        client = await self._get_client()

        try:
            url = f"{self.BASE_URL}/companies/{jurisdiction}/{company_number}"
            response = await client.get(url)

            if response.status_code == 404:
                logger.debug(f"Company not found: {jurisdiction}/{company_number}")
                return None

            response.raise_for_status()
            return self._parse_company_page(response.text, jurisdiction)

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenCorporates request error: {e}")
            return None
        except Exception as e:
            logger.error(f"OpenCorporates request failed: {e}")
            return None

    async def search(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        limit: int = 10,
    ) -> list[OpenCorporatesEntity]:
        """
        Search for companies by name.

        Args:
            query: Company name to search
            jurisdiction: Optional jurisdiction code (ISO country code)
            limit: Maximum results (default 10)

        Returns:
            List of matching OpenCorporatesEntity objects
        """
        await self._rate_limit()
        client = await self._get_client()

        # Build search URL
        encoded_query = quote_plus(query)
        url = f"{self.SEARCH_URL}?q={encoded_query}"

        if jurisdiction:
            jur_code = self.JURISDICTION_MAP.get(
                jurisdiction.upper(), jurisdiction.lower()
            )
            url += f"&jurisdiction_code={jur_code}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            return self._parse_search_results(response.text, limit)

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenCorporates search error: {e}")
            return []
        except Exception as e:
            logger.error(f"OpenCorporates search failed: {e}")
            return []

    def _parse_company_page(
        self,
        html: str,
        jurisdiction: str,
    ) -> Optional[OpenCorporatesEntity]:
        """Parse company detail page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try to find company name
        name_elem = soup.find("h1", class_="company_name") or soup.find("h1")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        # Remove jurisdiction prefix if present
        name = re.sub(r"^\s*\([^)]+\)\s*", "", name)

        # Find company number
        company_number = None
        for dt in soup.find_all("dt"):
            if "company number" in dt.get_text(strip=True).lower():
                dd_elem: Any = dt.find_next_sibling("dd")
                if dd_elem:
                    company_number = dd_elem.get_text(strip=True)
                    break

        if not company_number:
            # Try to extract from URL or page content
            match = re.search(r"/companies/[^/]+/([^/]+)", html)
            if match:
                company_number = match.group(1)

        if not company_number:
            return None

        entity = OpenCorporatesEntity(
            company_number=company_number,
            jurisdiction_code=jurisdiction,
            name=name,
            raw_data={"source": "opencorporates"},
        )

        # Extract additional fields
        for dt in soup.find_all("dt"):
            label = dt.get_text(strip=True).lower()
            dd: Any = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(strip=True)

            if "status" in label:
                entity.status = value
            elif "incorporation" in label and "date" in label:
                entity.incorporation_date = self._parse_date(value)
            elif "dissolution" in label and "date" in label:
                entity.dissolution_date = self._parse_date(value)
            elif "company type" in label or "type" in label:
                entity.company_type = value
            elif "registered address" in label or "address" in label:
                entity.registered_address = value
            elif "registry" in label and "url" in label:
                link: Any = dd.find("a")  # type: ignore[attr-defined]
                if link:
                    entity.registry_url = link.get("href")

        return entity

    def _parse_search_results(
        self,
        html: str,
        limit: int,
    ) -> list[OpenCorporatesEntity]:
        """Parse search results page."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[OpenCorporatesEntity] = []

        # Find search result items
        for item in soup.find_all("li", class_="company")[:limit]:  # type: ignore[union-attr]
            try:
                # Find company link
                link: Any = item.find("a", class_="company_name") or item.find("a")  # type: ignore[union-attr, call-arg]
                if not link:
                    continue

                name: str = link.get_text(strip=True)
                href: str = link.get("href", "")

                # Extract jurisdiction and company number from URL
                # Format: /companies/jurisdiction/company_number
                match = re.search(r"/companies/([^/]+)/([^/]+)", href)
                if not match:
                    continue

                jurisdiction = match.group(1)
                company_number = match.group(2)

                entity = OpenCorporatesEntity(
                    company_number=company_number,
                    jurisdiction_code=jurisdiction,
                    name=name,
                    opencorporates_url=(
                        f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    ),
                    raw_data={"source": "search_results"},
                )

                # Try to get status
                status_elem: Any = item.find(class_="status") or item.find(  # type: ignore[union-attr, call-arg]
                    class_="company_status"
                )
                if status_elem:
                    entity.status = status_elem.get_text(strip=True)

                # Try to get jurisdiction display
                jur_elem: Any = item.find(class_="jurisdiction")  # type: ignore[union-attr, call-arg]
                if jur_elem:
                    entity.raw_data["jurisdiction_name"] = jur_elem.get_text(strip=True)

                results.append(entity)

            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
                continue

        # Try alternative parsing if no results
        if not results:
            results = self._parse_search_results_alternative(soup, limit)

        logger.info(f"OpenCorporates search found {len(results)} results")
        return results

    def _parse_search_results_alternative(
        self,
        soup: BeautifulSoup,
        limit: int,
    ) -> list[OpenCorporatesEntity]:
        """Alternative parsing for different HTML structures."""
        results: list[OpenCorporatesEntity] = []

        # Find all links to company pages
        for link in soup.find_all("a", href=re.compile(r"/companies/[^/]+/[^/]+")):  # type: ignore[union-attr]
            if len(results) >= limit:
                break

            href: str = str(link.get("href", ""))  # type: ignore[union-attr]
            match = re.search(r"/companies/([^/]+)/([^/]+)", href)
            if not match:
                continue

            name: str = link.get_text(strip=True)
            if not name or len(name) < 3:
                continue

            # Skip navigation links
            if name.lower() in ["view", "details", "more", "search"]:
                continue

            jurisdiction = match.group(1)
            company_number = match.group(2)

            # Avoid duplicates
            if any(
                r.jurisdiction_code == jurisdiction
                and r.company_number == company_number
                for r in results
            ):
                continue

            oc_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            results.append(
                OpenCorporatesEntity(
                    company_number=company_number,
                    jurisdiction_code=jurisdiction,
                    name=name,
                    opencorporates_url=oc_url,
                    raw_data={"source": "alternative_parse"},
                )
            )

        return results

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        formats = [
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%B %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None


# Singleton instance
_oc_client: Optional[OpenCorporatesClient] = None


def get_opencorporates_client() -> OpenCorporatesClient:
    """Get singleton OpenCorporates client instance."""
    global _oc_client
    if _oc_client is None:
        _oc_client = OpenCorporatesClient()
    return _oc_client
