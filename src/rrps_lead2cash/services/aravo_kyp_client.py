"""
Aravo KYP (Know Your Partner) Client Service.

Direct REST API client for the Aravo third-party risk management platform.
This is a direct integration — does NOT route through SAP CPI.

Aravo API: GET /aems/restservices/v5.0/reports/{report_id}
Auth: HTTP Basic Authentication (pre-encoded token)
Response: JSON report with column definitions and row data

Used for Tier 1 due diligence validation during opportunity qualification (Epic 1).
"""

import logging
import time
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

import requests

from ..config import config
from ..core.models import (
    AravoEngagement,
    AravoReportMeta,
    KYPAssessment,
)

logger = logging.getLogger(__name__)

# Default cache TTL: 5 minutes (Aravo ETL runs infrequently)
DEFAULT_CACHE_TTL_SECONDS = 300


class AravoKYPClient:
    """
    Client for querying Aravo KYP third-party compliance data.

    Calls the Aravo Reports REST API to retrieve the KYP report,
    parses the columnar response into engagement records,
    and performs fuzzy matching by customer name.

    The report is cached in-memory with a configurable TTL to avoid
    redundant HTTP calls (Aravo data changes infrequently).
    """

    # Aravo report column mapping (c1-c12 → field names)
    COLUMN_MAP = {
        "c1": "active",
        "c2": "third_party_id",
        "c3": "third_party_name",
        "c4": "proposer",
        "c5": "onboarding_status",
        "c6": "third_party_status",
        "c7": "ec_review_status",
        "c8": "sec_review_status",
        "c9": "risk_rating",
        "c10": "engagement_id",
        "c11": "engagement_name",
        "c12": "partner_type",
    }

    def __init__(self, cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._report_url = config.get_aravo_report_url()
        self._auth_token = config.aravo_auth_token
        self._timeout = config.aravo_timeout
        self._verify_ssl = config.aravo_verify_ssl
        self._cache_ttl = cache_ttl

        # In-memory report cache
        self._cached_meta: Optional[AravoReportMeta] = None
        self._cached_engagements: Optional[List[AravoEngagement]] = None
        self._cache_timestamp: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_report(self, force_refresh: bool = False) -> Tuple[AravoReportMeta, List[AravoEngagement]]:
        """
        Fetch the full KYP report from Aravo (with TTL cache).

        Returns cached data if still fresh. Set force_refresh=True to
        bypass the cache and hit the Aravo API directly.

        Returns:
            Tuple of (report metadata, list of active engagement records).

        Raises:
            AravoConfigError: If auth token or report ID is missing.
            AravoConnectionError: If the API call fails.
            AravoAuthError: If authentication fails.
        """
        if not force_refresh and self._is_cache_valid():
            logger.debug("Returning cached Aravo report (%d engagements)", len(self._cached_engagements))
            return self._cached_meta, self._cached_engagements

        if not self._auth_token:
            raise AravoConfigError(
                "ARAVO_AUTH_TOKEN environment variable must be set"
            )

        if not config.aravo_report_id:
            raise AravoConfigError(
                "ARAVO_REPORT_ID environment variable must be set"
            )

        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {self._auth_token}",
        }

        logger.info("Fetching Aravo KYP report from %s", self._report_url)

        try:
            response = requests.get(
                self._report_url,
                headers=headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
            )
        except requests.exceptions.ConnectionError as exc:
            raise AravoConnectionError(
                f"Failed to connect to Aravo API at {self._report_url}: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise AravoConnectionError(
                f"Aravo API request timed out after {self._timeout}s: {exc}"
            ) from exc

        if response.status_code == 401:
            raise AravoAuthError("Aravo API authentication failed (401)")
        if response.status_code != 200:
            raise AravoConnectionError(
                f"Aravo API returned HTTP {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        meta, engagements = self._parse_report(data)
        logger.info(
            "Aravo KYP report fetched: %d active engagements (ETL: %s)",
            len(engagements),
            meta.etl_datetime,
        )

        # Update cache
        self._cached_meta = meta
        self._cached_engagements = engagements
        self._cache_timestamp = time.monotonic()

        return meta, engagements

    def assess_customer(self, customer_name: str) -> KYPAssessment:
        """
        Perform a KYP assessment for a customer by name.

        Fetches the Aravo report (from cache if fresh), fuzzy-matches
        the customer name, and returns the KYP compliance assessment.

        Args:
            customer_name: Customer or partner name to look up.

        Returns:
            KYPAssessment with matched engagement data and compliance outcome.
            If no match found, includes up to 3 nearest-name suggestions.
        """
        meta, engagements = self.fetch_report()
        match = self._find_best_match(customer_name, engagements)

        if match is None:
            logger.warning("No Aravo match found for customer: %s", customer_name)
            suggestions = self._get_nearest_names(customer_name, engagements, top_n=3)
            issues = [f"No matching third party found in Aravo for '{customer_name}'"]
            if suggestions:
                issues.append(f"Did you mean: {', '.join(suggestions)}?")
            return KYPAssessment(
                customer_name=customer_name,
                matched=False,
                kyp_status="NOT_FOUND",
                issues=issues,
                blocking=True,
                report_etl_datetime=meta.etl_datetime,
            )

        return self._build_assessment(customer_name, match, meta)

    def list_customers(self) -> List[dict]:
        """
        List all active customers/partners in the Aravo KYP report.

        Returns:
            List of dicts with third_party_id, third_party_name, partner_type, risk_rating.
        """
        _, engagements = self.fetch_report()
        return [
            {
                "third_party_id": e.third_party_id,
                "third_party_name": e.third_party_name,
                "partner_type": e.partner_type,
                "risk_rating": e.risk_rating,
                "onboarding_status": e.onboarding_status,
                "third_party_status": e.third_party_status,
            }
            for e in engagements
        ]

    def invalidate_cache(self) -> None:
        """Force-clear the report cache."""
        self._cached_meta = None
        self._cached_engagements = None
        self._cache_timestamp = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_cache_valid(self) -> bool:
        """Check if the cached report is still within TTL."""
        if self._cached_meta is None or self._cached_engagements is None:
            return False
        elapsed = time.monotonic() - self._cache_timestamp
        return elapsed < self._cache_ttl

    def _parse_report(
        self, data: dict
    ) -> Tuple[AravoReportMeta, List[AravoEngagement]]:
        """Parse the Aravo API JSON response into structured models.

        Only includes active engagements (c1=True).
        """
        if not isinstance(data, dict):
            raise AravoConnectionError("Aravo API returned non-JSON response")

        meta_raw = data.get("meta")
        data_list = data.get("data")

        if not meta_raw or not isinstance(data_list, list) or len(data_list) == 0:
            raise AravoConnectionError(
                f"Unexpected Aravo response structure: missing 'meta' or empty 'data' array"
            )

        report = data_list[0]

        meta = AravoReportMeta(
            api_version=meta_raw.get("apiVersion", "unknown"),
            data_size=meta_raw.get("dataSize", 0),
            report_id=str(report.get("id", "")),
            report_name=str(report.get("name", "")),
            etl_datetime=str(report.get("etlDateTime", "")),
        )

        engagements: List[AravoEngagement] = []
        for row in report.get("rows", []):
            active = row.get("c1", False)
            if not active:
                continue
            engagements.append(
                AravoEngagement(
                    active=active,
                    third_party_id=str(row.get("c2", "")),
                    third_party_name=str(row.get("c3", "")).strip(),
                    proposer=str(row.get("c4", "")),
                    onboarding_status=str(row.get("c5", "")),
                    third_party_status=str(row.get("c6", "")),
                    ec_review_status=str(row.get("c7", "")),
                    sec_review_status=str(row.get("c8", "")),
                    risk_rating=str(row.get("c9", "")),
                    engagement_id=int(row.get("c10", 0)),
                    engagement_name=str(row.get("c11", "")),
                    partner_type=str(row.get("c12", "")),
                )
            )

        return meta, engagements

    def _find_best_match(
        self,
        customer_name: str,
        engagements: List[AravoEngagement],
        threshold: float = 0.6,
    ) -> Optional[AravoEngagement]:
        """
        Find the best fuzzy match for a customer name in the engagements list.

        Uses a three-pass strategy:
        1. Exact match (case-insensitive)
        2. Substring containment
        3. SequenceMatcher fuzzy scoring (above threshold)

        Args:
            customer_name: Name to search for.
            engagements: List of Aravo engagement records.
            threshold: Minimum similarity ratio (0.0-1.0) for a match.

        Returns:
            Best matching AravoEngagement or None if no match above threshold.
        """
        query = customer_name.strip().lower()

        # Pass 1: exact match (case-insensitive)
        for eng in engagements:
            if eng.third_party_name.strip().lower() == query:
                return eng

        # Pass 2: substring containment
        for eng in engagements:
            name_lower = eng.third_party_name.strip().lower()
            if query in name_lower or name_lower in query:
                return eng

        # Pass 3: fuzzy match
        best_score = 0.0
        best_match: Optional[AravoEngagement] = None
        for eng in engagements:
            score = SequenceMatcher(
                None, query, eng.third_party_name.strip().lower()
            ).ratio()
            if score > best_score:
                best_score = score
                best_match = eng

        if best_score >= threshold:
            return best_match

        return None

    def _get_nearest_names(
        self,
        customer_name: str,
        engagements: List[AravoEngagement],
        top_n: int = 3,
    ) -> List[str]:
        """Return the top-N nearest third party names by similarity."""
        query = customer_name.strip().lower()
        scored = []
        for eng in engagements:
            name = eng.third_party_name.strip()
            score = SequenceMatcher(None, query, name.lower()).ratio()
            scored.append((score, name))
        scored.sort(key=lambda x: -x[0])
        return [name for _, name in scored[:top_n]]

    def _build_assessment(
        self,
        customer_name: str,
        engagement: AravoEngagement,
        meta: AravoReportMeta,
    ) -> KYPAssessment:
        """Build a KYPAssessment from a matched Aravo engagement."""
        issues: List[str] = []
        blocking = False

        # Evaluate onboarding status
        if engagement.onboarding_status == "Rejected":
            issues.append("Third party onboarding REJECTED in Aravo")
            blocking = True
        elif engagement.onboarding_status == "TP Completing DDQ":
            issues.append("Third party is still completing Due Diligence Questionnaire")
        elif engagement.onboarding_status == "KYP Hub Review":
            issues.append("Engagement is under KYP Hub Review")

        # Evaluate third party status
        if engagement.third_party_status == "Denied":
            issues.append("Third party status is DENIED")
            blocking = True
        elif engagement.third_party_status == "Pending Approval":
            issues.append("Third party approval is pending")

        # Evaluate risk rating
        if engagement.risk_rating == "Very High":
            issues.append("Engagement risk rating is VERY HIGH — requires enhanced due diligence")
            blocking = True
        elif engagement.risk_rating == "High":
            issues.append("Engagement risk rating is HIGH — additional review may be required")

        # Evaluate E&C review
        if engagement.ec_review_status == "Pending":
            issues.append("Ethics & Compliance review is pending")

        # Evaluate S&EC review
        if engagement.sec_review_status == "Pending":
            issues.append("Security & Export Control review is pending")

        # Determine overall KYP status
        if blocking:
            kyp_status = "BLOCKED"
        elif engagement.onboarding_status != "Approved" or engagement.third_party_status != "Approved":
            kyp_status = "PENDING"
        elif issues:
            kyp_status = "CONDITIONAL"
        else:
            kyp_status = "APPROVED"

        return KYPAssessment(
            customer_name=customer_name,
            matched=True,
            third_party_id=engagement.third_party_id,
            engagement_id=engagement.engagement_id,
            engagement_name=engagement.engagement_name,
            partner_type=engagement.partner_type,
            proposer=engagement.proposer,
            onboarding_status=engagement.onboarding_status,
            third_party_status=engagement.third_party_status,
            risk_rating=engagement.risk_rating,
            ec_review_status=engagement.ec_review_status,
            sec_review_status=engagement.sec_review_status,
            kyp_status=kyp_status,
            issues=issues,
            blocking=blocking,
            report_etl_datetime=meta.etl_datetime,
        )


# ============================================================================
# Custom Exceptions
# ============================================================================


class AravoError(Exception):
    """Base exception for Aravo KYP client errors."""
    pass


class AravoConfigError(AravoError):
    """Aravo configuration is missing or invalid."""
    pass


class AravoConnectionError(AravoError):
    """Failed to connect to or receive response from Aravo API."""
    pass


class AravoAuthError(AravoError):
    """Aravo API authentication failed."""
    pass
