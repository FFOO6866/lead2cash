"""
ACRA (Accounting and Corporate Regulatory Authority) Client

Web scraping client for Singapore company lookups.
Uses public sources like sgpbusiness.com for company profiles.
Rate limit: 5 requests/minute to be respectful.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ACRAEntity:
    """Entity data from ACRA/Singapore business registry."""

    uen: str
    entity_name: str
    entity_type: Optional[str] = None  # Private Limited, LLP, etc.
    status: Optional[str] = None  # Live, Struck Off, etc.
    registration_date: Optional[datetime] = None
    address: Optional[str] = None
    primary_activity: Optional[str] = None
    secondary_activity: Optional[str] = None

    # Capital information
    paid_up_capital: Optional[str] = None

    # Raw data for storage
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "uen": self.uen,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "status": self.status,
            "registration_date": (
                self.registration_date.isoformat() if self.registration_date else None
            ),
            "address": self.address,
            "primary_activity": self.primary_activity,
            "secondary_activity": self.secondary_activity,
            "paid_up_capital": self.paid_up_capital,
        }


class ACRAClient:
    """
    ACRA client for Singapore company lookups.

    Uses web scraping from public business profile websites.
    Rate limited to 5 requests/minute.
    """

    # Primary source for Singapore business info
    SEARCH_URL = "https://www.sgpbusiness.com/search"
    PROFILE_URL = "https://www.sgpbusiness.com/company"

    RATE_LIMIT = 5  # requests per minute
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
                logger.debug(f"ACRA rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def get_by_uen(self, uen: str) -> Optional[ACRAEntity]:
        """
        Get entity by UEN (Unique Entity Number).

        Args:
            uen: Singapore UEN (e.g., 200504525N)

        Returns:
            ACRAEntity or None if not found
        """
        uen = uen.strip().upper()
        if not self._is_valid_uen(uen):
            logger.warning(f"Invalid UEN format: {uen}")
            return None

        await self._rate_limit()
        client = await self._get_client()

        try:
            # Try to get company profile directly
            url = f"{self.PROFILE_URL}/{uen}"
            response = await client.get(url)

            if response.status_code == 404:
                logger.debug(f"UEN not found: {uen}")
                return None

            response.raise_for_status()
            return self._parse_profile_page(response.text, uen)

        except httpx.HTTPStatusError as e:
            logger.error(f"ACRA request error for UEN {uen}: {e}")
            return None
        except Exception as e:
            logger.error(f"ACRA request failed for UEN {uen}: {e}")
            return None

    async def search_by_name(self, name: str, limit: int = 10) -> list[ACRAEntity]:
        """
        Search for companies by name.

        Args:
            name: Company name to search
            limit: Maximum results (default 10)

        Returns:
            List of matching ACRAEntity objects
        """
        await self._rate_limit()
        client = await self._get_client()

        try:
            # Search page with query
            params = {"q": name}
            response = await client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()

            return self._parse_search_results(response.text, limit)

        except httpx.HTTPStatusError as e:
            logger.error(f"ACRA search error: {e}")
            return []
        except Exception as e:
            logger.error(f"ACRA search failed: {e}")
            return []

    def _is_valid_uen(self, uen: str) -> bool:
        """Validate Singapore UEN format."""
        # UEN formats:
        # - Old format: 8 digits + letter (e.g., 12345678A)
        # - New format: 9 digits + letter (e.g., 200504525N)
        # - Other: T prefix for certain entities (e.g., T12AB1234C)
        pattern = r"^([0-9]{8,9}[A-Za-z]|[A-Za-z][0-9]{2}[A-Za-z]{2}[0-9]{4}[A-Za-z])$"
        return bool(re.match(pattern, uen))

    def _parse_profile_page(self, html: str, uen: str) -> Optional[ACRAEntity]:
        """Parse company profile page."""
        soup = BeautifulSoup(html, "html.parser")

        # Try to find company name
        name_elem = soup.find("h1", class_="company-name") or soup.find("h1")
        if not name_elem:
            logger.warning(f"Could not parse company name for UEN {uen}")
            return None

        entity_name = name_elem.get_text(strip=True)

        # Extract other fields from profile
        entity = ACRAEntity(
            uen=uen,
            entity_name=entity_name,
            raw_data={"html_source": "sgpbusiness.com"},
        )

        # Try to extract additional fields
        for row in soup.find_all("tr"):
            cells: Any = row.find_all("td")  # type: ignore[union-attr]
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)

                if "status" in label:
                    entity.status = value
                elif "entity type" in label or "company type" in label:
                    entity.entity_type = value
                elif "registration" in label and "date" in label:
                    entity.registration_date = self._parse_date(value)
                elif "address" in label:
                    entity.address = value
                elif "primary" in label and "activity" in label:
                    entity.primary_activity = value
                elif "capital" in label:
                    entity.paid_up_capital = value

        return entity

    def _parse_search_results(self, html: str, limit: int) -> list[ACRAEntity]:
        """Parse search results page."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[ACRAEntity] = []

        # Look for search result items
        for item in soup.find_all("div", class_="search-result")[:limit]:
            try:
                # Extract UEN and name from result item
                uen_elem: Any = item.find(class_="uen") or item.find(  # type: ignore[union-attr, call-arg]
                    "span", string=re.compile(r"[0-9]{8,9}[A-Z]")
                )
                name_elem: Any = item.find(class_="company-name") or item.find("a")  # type: ignore[union-attr, call-arg]

                if not uen_elem or not name_elem:
                    continue

                uen: str = uen_elem.get_text(strip=True)
                name: str = name_elem.get_text(strip=True)

                if not self._is_valid_uen(uen):
                    continue

                entity = ACRAEntity(
                    uen=uen,
                    entity_name=name,
                    raw_data={"source": "search_results"},
                )

                # Try to get status if available
                status_elem: Any = item.find(class_="status")  # type: ignore[union-attr, call-arg]
                if status_elem:
                    entity.status = status_elem.get_text(strip=True)

                results.append(entity)

            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
                continue

        # If no structured results, try alternative parsing
        if not results:
            results = self._parse_search_results_alternative(soup, limit)

        logger.info(f"ACRA search found {len(results)} results")
        return results

    def _parse_search_results_alternative(
        self, soup: BeautifulSoup, limit: int
    ) -> list[ACRAEntity]:
        """Alternative parsing for different HTML structures."""
        results: list[ACRAEntity] = []

        # Try finding links that contain UEN patterns
        for link in soup.find_all("a", href=re.compile(r"/company/[0-9]+")):  # type: ignore[union-attr]
            if len(results) >= limit:
                break

            href: str = str(link.get("href", ""))  # type: ignore[union-attr]
            uen_match = re.search(r"/company/([0-9]{8,9}[A-Za-z])", href)
            if uen_match:
                uen = uen_match.group(1).upper()
                name = link.get_text(strip=True)
                if name and len(name) > 3:
                    results.append(
                        ACRAEntity(
                            uen=uen,
                            entity_name=name,
                            raw_data={"source": "alternative_parse"},
                        )
                    )

        return results

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime."""
        formats = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None


# Singleton instance
_acra_client: Optional[ACRAClient] = None


def get_acra_client() -> ACRAClient:
    """Get singleton ACRA client instance."""
    global _acra_client
    if _acra_client is None:
        _acra_client = ACRAClient()
    return _acra_client
