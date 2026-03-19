"""
Two-Tier Customer Validation Service.

Combines:
- Tier 1: KYP Compliance Assessment (Aravo — external due diligence)
- Tier 2: SAP/ECC Validation (transactional due diligence via CPI)

Matches the production API pattern at rr.kailash.ai:
- GET  /api/v1/validation/kyp/{customer_name}  → Tier 1 only
- POST /api/v1/validation/validate             → Both tiers
- GET  /api/v1/validation/customers            → List available customers
"""

import logging
from typing import Any, Dict, List, Optional

from ..core.models import (
    KYPAssessment,
    TwoTierValidationResponse,
    TwoTierValidationStatus,
)
from .aravo_kyp_client import AravoKYPClient, AravoError

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Two-tier customer validation orchestrator.

    Tier 1 (KYP): Queries Aravo for third-party compliance status.
    Tier 2 (SAP): Queries SAP/ECC via CPI for master data and credit validation.
    """

    def __init__(self) -> None:
        self._aravo_client = AravoKYPClient()

    # ------------------------------------------------------------------
    # Tier 1: KYP Assessment (Aravo)
    # ------------------------------------------------------------------

    def get_kyp_assessment(self, customer_name: str) -> KYPAssessment:
        """
        Get KYP compliance assessment for a customer (Tier 1 only).

        Args:
            customer_name: Customer/partner name to look up in Aravo.

        Returns:
            KYPAssessment with risk rating, approval status, and issues.

        Raises:
            AravoError: If the Aravo API call fails.
        """
        return self._aravo_client.assess_customer(customer_name)

    # ------------------------------------------------------------------
    # Two-Tier Validation
    # ------------------------------------------------------------------

    def validate_customer(
        self,
        customer: str,
        order_value: float = 0.0,
    ) -> TwoTierValidationResponse:
        """
        Perform comprehensive two-tier customer validation.

        Tier 1: KYP compliance from Aravo (blocking if DENIED/REJECTED/VERY_HIGH risk).
        Tier 2: SAP master data and credit validation via CPI (TE-12).

        Args:
            customer: Customer name or SAP ID.
            order_value: Order value for credit check (Tier 2).

        Returns:
            TwoTierValidationResponse with combined results.
        """
        all_issues: List[str] = []
        all_conditions: List[str] = []
        tier1_result: Optional[KYPAssessment] = None
        tier2_result: Optional[Dict[str, Any]] = None

        # -- Tier 1: KYP (Aravo) --
        try:
            tier1_result = self._aravo_client.assess_customer(customer)
            all_issues.extend(tier1_result.issues)

            # Separate conditions from blocking issues
            if tier1_result.kyp_status == "CONDITIONAL":
                for issue in tier1_result.issues:
                    if "review" in issue.lower() or "additional" in issue.lower():
                        all_conditions.append(issue)
        except AravoError as exc:
            logger.error("Tier 1 KYP check failed: %s", exc)
            all_issues.append(f"KYP check unavailable: {exc}")

        # -- Tier 2: SAP/ECC (via CPI — TE-12 implementation) --
        # Tier 2 is wired when TE-12 (SAP Customer Master Client) is implemented.
        # The CPI integration validates: master data completeness, credit limit,
        # payment terms, sales area assignment. This is None until the CPI client
        # is connected — NOT simulated data.
        tier2_result = None
        if tier2_result is None:
            all_conditions.append("SAP master data validation pending (TE-12 not yet implemented)")

        # -- Determine combined status --
        status = self._determine_combined_status(tier1_result, tier2_result)

        return TwoTierValidationResponse(
            status=status,
            customer=customer,
            tier1_kyp=tier1_result,
            tier2_sap=tier2_result,
            issues=all_issues,
            conditions=all_conditions,
        )

    # ------------------------------------------------------------------
    # Customer listing
    # ------------------------------------------------------------------

    def list_customers(self) -> List[dict]:
        """
        List customers available for validation from Aravo KYP report.

        Returns:
            List of customer records from Aravo.
        """
        return self._aravo_client.list_customers()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _determine_combined_status(
        self,
        tier1: Optional[KYPAssessment],
        tier2: Optional[Dict[str, Any]],
    ) -> TwoTierValidationStatus:
        """
        Determine the combined validation status from both tiers.

        Rules:
        - If Tier 1 is BLOCKED → BLOCKED (regardless of Tier 2)
        - If Tier 1 is NOT_FOUND → PENDING (cannot proceed without KYP)
        - If Tier 1 is PENDING → PENDING
        - If Tier 1 is CONDITIONAL → CONDITIONAL
        - If Tier 1 is APPROVED but Tier 2 not yet available → CONDITIONAL
        - If both tiers pass → APPROVED
        """
        if tier1 is None:
            return TwoTierValidationStatus.PENDING

        if tier1.kyp_status == "BLOCKED":
            return TwoTierValidationStatus.BLOCKED

        if tier1.kyp_status == "NOT_FOUND":
            return TwoTierValidationStatus.PENDING

        if tier1.kyp_status == "PENDING":
            return TwoTierValidationStatus.PENDING

        if tier1.kyp_status == "CONDITIONAL":
            return TwoTierValidationStatus.CONDITIONAL

        # Tier 1 is APPROVED — check Tier 2
        if tier2 is None:
            # Cannot be fully APPROVED without SAP validation
            return TwoTierValidationStatus.CONDITIONAL

        return TwoTierValidationStatus.APPROVED
