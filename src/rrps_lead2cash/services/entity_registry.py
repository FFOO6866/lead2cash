"""
Entity Registry — Customer name-to-ID resolution.

Maps customer names to SAP customer IDs for the chat agent
and API endpoints. Uses a combination of:
1. Known customers from IPAS XML files (Sold_To_Party + Partner_Information)
2. Known customers from FinOps simulator data
3. Aravo KYP report (if available)
4. Fuzzy matching for partial/misspelled names

This replaces the production entity registry database for local development.
"""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Known customers with SAP IDs, names, and aliases
_KNOWN_CUSTOMERS: List[Dict[str, Any]] = [
    {
        "customer_id": "0022005992",
        "name": "ST Engineering Marine Ltd",
        "aliases": ["ST Engineering", "STE", "ST Eng", "ST Engineering Marine", "ST Engineering Land Systems Ltd"],
        "country": "SG",
        "currency": "SGD",
    },
    {
        "customer_id": "0021000090",
        "name": "CLLS POWER SYSTEM LTD",
        "aliases": ["CLLS", "CLLS Power", "CLLS Power System"],
        "country": "SG",
        "currency": "EUR",
    },
    {
        "customer_id": "0022005601",
        "name": "TIANJIN DINGSHENG CONSTRUCTION MACHINERY CO. LTD",
        "aliases": ["Tianjin", "Tianjin Dingsheng", "Dingsheng", "Dingsheng Construction",
                     "TIANJIN DINGSHENG CONSTRUCTION"],
        "country": "CN",
        "currency": "EUR",
    },
    {
        "customer_id": "0022049826",
        "name": "SSZ Customer (Suzhou)",
        "aliases": ["SSZ", "Suzhou"],
        "country": "CN",
        "currency": "CNY",
    },
    # Simulator customers (from production entity registry)
    {
        "customer_id": "0000100001",
        "name": "Batam Fast Ferry",
        "aliases": ["BatamFast", "Batam Fast", "Batam"],
        "country": "SG",
        "currency": "SGD",
    },
    {
        "customer_id": "0000100002",
        "name": "Maersk A/S",
        "aliases": ["Maersk"],
        "country": "DK",
        "currency": "EUR",
    },
    {
        "customer_id": "0000100003",
        "name": "Neptune Energy",
        "aliases": ["Neptune"],
        "country": "NL",
        "currency": "EUR",
    },
    {
        "customer_id": "0000100004",
        "name": "Blocked Marine",
        "aliases": ["Blocked"],
        "country": "US",
        "currency": "USD",
    },
    {
        "customer_id": "0000100005",
        "name": "Pacific Maritime",
        "aliases": ["Pacific"],
        "country": "AU",
        "currency": "AUD",
    },
]


class EntityRegistry:
    """
    Customer name-to-ID resolution service.

    Resolves customer names (including partial matches, aliases, and
    fuzzy matching) to SAP customer IDs.
    """

    def __init__(self) -> None:
        self._customers = list(_KNOWN_CUSTOMERS)
        self._build_index()

    def _build_index(self) -> None:
        """Build lookup indexes."""
        self._by_id: Dict[str, Dict] = {}
        self._by_name_lower: Dict[str, Dict] = {}

        for cust in self._customers:
            self._by_id[cust["customer_id"]] = cust
            self._by_name_lower[cust["name"].lower()] = cust
            for alias in cust.get("aliases", []):
                self._by_name_lower[alias.lower()] = cust

    def add_customer(self, customer_id: str, name: str, aliases: Optional[List[str]] = None, **kwargs) -> None:
        """Add a customer to the registry (e.g., from IPAS XML or Aravo)."""
        # Check if already exists
        if customer_id in self._by_id:
            return
        entry = {"customer_id": customer_id, "name": name, "aliases": aliases or [], **kwargs}
        self._customers.append(entry)
        self._build_index()

    def resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a customer name/ID to a full customer record.

        Tries: exact ID -> exact name -> alias -> fuzzy match.

        Returns:
            Customer dict with customer_id, name, etc. or None.
        """
        q = query.strip()

        # Try exact ID match (with/without leading zeros)
        if q in self._by_id:
            return self._by_id[q]
        padded = q.zfill(10)
        if padded in self._by_id:
            return self._by_id[padded]

        # Try exact name/alias match (case-insensitive)
        q_lower = q.lower()
        if q_lower in self._by_name_lower:
            return self._by_name_lower[q_lower]

        # Try substring match
        for cust in self._customers:
            name_lower = cust["name"].lower()
            if q_lower in name_lower or name_lower in q_lower:
                return cust
            for alias in cust.get("aliases", []):
                if q_lower in alias.lower() or alias.lower() in q_lower:
                    return cust

        # Fuzzy match
        best_score = 0.0
        best_match = None
        for cust in self._customers:
            candidates = [cust["name"]] + cust.get("aliases", [])
            for candidate in candidates:
                score = SequenceMatcher(None, q_lower, candidate.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = cust

        if best_score >= 0.6:
            return best_match

        return None

    def resolve_to_id(self, query: str) -> Optional[str]:
        """Resolve a query to just the SAP customer ID."""
        result = self.resolve(query)
        return result["customer_id"] if result else None

    def list_customers(self) -> List[Dict[str, Any]]:
        """List all known customers."""
        return [
            {
                "customer_id": c["customer_id"],
                "name": c["name"],
                "country": c.get("country", ""),
                "currency": c.get("currency", ""),
            }
            for c in self._customers
        ]

    def search(self, query: str, top_n: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        """Search customers by name, returning top matches with scores."""
        q_lower = query.strip().lower()
        scored = []
        for cust in self._customers:
            candidates = [cust["name"]] + cust.get("aliases", [])
            best = max(
                SequenceMatcher(None, q_lower, c.lower()).ratio()
                for c in candidates
            )
            scored.append((best, cust))
        scored.sort(key=lambda x: -x[0])
        return scored[:top_n]
