"""
GLEIF (Global Legal Entity Identifier Foundation) API Client

Free public API for LEI lookups.
API docs: https://api.gleif.org/api/v1
Rate limit: 60 requests/minute
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GLEIFEntity:
    """Entity data from GLEIF API."""

    lei: str
    legal_name: str
    legal_address_country: Optional[str] = None
    headquarters_country: Optional[str] = None
    jurisdiction: Optional[str] = None
    entity_status: Optional[str] = None
    registration_status: Optional[str] = None
    registration_date: Optional[datetime] = None
    last_update: Optional[datetime] = None
    legal_form: Optional[str] = None
    entity_category: Optional[str] = None

    # Additional address details
    legal_address_city: Optional[str] = None
    legal_address_postal_code: Optional[str] = None
    headquarters_city: Optional[str] = None

    # Raw data for storage
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "lei": self.lei,
            "legal_name": self.legal_name,
            "legal_address_country": self.legal_address_country,
            "headquarters_country": self.headquarters_country,
            "jurisdiction": self.jurisdiction,
            "entity_status": self.entity_status,
            "registration_status": self.registration_status,
            "registration_date": (
                self.registration_date.isoformat() if self.registration_date else None
            ),
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "legal_form": self.legal_form,
            "entity_category": self.entity_category,
            "legal_address_city": self.legal_address_city,
            "legal_address_postal_code": self.legal_address_postal_code,
            "headquarters_city": self.headquarters_city,
        }


class GLEIFClient:
    """
    GLEIF API client for LEI lookups.

    Uses the free public GLEIF API (no authentication required).
    Rate limited to 60 requests/minute.
    """

    BASE_URL = "https://api.gleif.org/api/v1"
    RATE_LIMIT = 60  # requests per minute
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
                    "Accept": "application/vnd.api+json",
                    "User-Agent": "RRPS-LeadToCash/1.0",
                },
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
                logger.debug(f"GLEIF rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def get_by_lei(self, lei: str) -> Optional[GLEIFEntity]:
        """
        Get entity by LEI.

        Args:
            lei: Legal Entity Identifier (20 characters)

        Returns:
            GLEIFEntity or None if not found
        """
        if not lei or len(lei) != 20:
            logger.warning(f"Invalid LEI format: {lei}")
            return None

        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(f"{self.BASE_URL}/lei-records/{lei.upper()}")

            if response.status_code == 404:
                logger.debug(f"LEI not found: {lei}")
                return None

            response.raise_for_status()
            data = response.json()

            return self._parse_entity(data.get("data", {}))

        except httpx.HTTPStatusError as e:
            logger.error(f"GLEIF API error for LEI {lei}: {e}")
            return None
        except Exception as e:
            logger.error(f"GLEIF request failed for LEI {lei}: {e}")
            return None

    async def search(
        self,
        query: str,
        country: Optional[str] = None,
        limit: int = 10,
    ) -> list[GLEIFEntity]:
        """
        Search for entities by name.

        Args:
            query: Company name to search
            country: Optional ISO country code filter
            limit: Maximum results (default 10)

        Returns:
            List of matching GLEIFEntity objects
        """
        await self._rate_limit()
        client = await self._get_client()

        params = {
            "filter[entity.legalName]": query,
            "page[size]": str(min(limit, 100)),
        }

        if country:
            params["filter[entity.legalAddress.country]"] = country.upper()

        try:
            response = await client.get(
                f"{self.BASE_URL}/lei-records",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for record in data.get("data", []):
                entity = self._parse_entity(record)
                if entity:
                    results.append(entity)

            logger.info(f"GLEIF search '{query}' found {len(results)} results")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"GLEIF search error: {e}")
            return []
        except Exception as e:
            logger.error(f"GLEIF search failed: {e}")
            return []

    async def search_fuzzy(
        self,
        query: str,
        country: Optional[str] = None,
        limit: int = 10,
    ) -> list[GLEIFEntity]:
        """
        Fuzzy search for entities by name.

        Note: GLEIF API's filter[entity.legalName] already does partial/substring
        matching, so this delegates to the regular search method.

        Args:
            query: Company name to search
            country: Optional ISO country code filter
            limit: Maximum results (default 10)

        Returns:
            List of matching GLEIFEntity objects
        """
        # GLEIF's name filter already does partial matching
        # No separate fuzzy endpoint exists
        return await self.search(query, country, limit)

    def _parse_entity(self, record: dict) -> Optional[GLEIFEntity]:
        """Parse GLEIF API response into GLEIFEntity."""
        if not record:
            return None

        attributes = record.get("attributes", {})
        entity = attributes.get("entity", {})
        registration = attributes.get("registration", {})

        legal_name = entity.get("legalName", {}).get("name")
        if not legal_name:
            return None

        lei = attributes.get("lei")
        if not lei:
            return None

        # Parse addresses
        legal_address = entity.get("legalAddress", {})
        headquarters = entity.get("headquartersAddress", {})

        # Parse dates
        reg_date = None
        if registration.get("initialRegistrationDate"):
            try:
                reg_date = datetime.fromisoformat(
                    registration["initialRegistrationDate"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        last_update = None
        if registration.get("lastUpdateDate"):
            try:
                last_update = datetime.fromisoformat(
                    registration["lastUpdateDate"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return GLEIFEntity(
            lei=lei,
            legal_name=legal_name,
            legal_address_country=legal_address.get("country"),
            headquarters_country=headquarters.get("country"),
            jurisdiction=entity.get("jurisdiction"),
            entity_status=entity.get("status"),
            registration_status=registration.get("status"),
            registration_date=reg_date,
            last_update=last_update,
            legal_form=entity.get("legalForm", {}).get("id"),
            entity_category=entity.get("category"),
            legal_address_city=legal_address.get("city"),
            legal_address_postal_code=legal_address.get("postalCode"),
            headquarters_city=headquarters.get("city"),
            raw_data=record,
        )


# Singleton instance
_gleif_client: Optional[GLEIFClient] = None


def get_gleif_client() -> GLEIFClient:
    """Get singleton GLEIF client instance."""
    global _gleif_client
    if _gleif_client is None:
        _gleif_client = GLEIFClient()
    return _gleif_client
