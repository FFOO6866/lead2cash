"""
Customer Validation Service - Two-Tier KYP Assessment with LLM Matching

Combines Tier 1 (KYP Compliance) and Tier 2 (SAP/ECC Validation) checks
for comprehensive customer due diligence.

This service integrates with existing components:
    - MS5Client: For SAP/ECC validation (Tier 2)
    - KYPProcessor: For KYP compliance assessment (Tier 1)
    - CustomerMatcherAgent: For intelligent LLM-based customer name matching
    - DueDiligenceAgent: Can be used as alternative for Tier 2

Architecture:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  CustomerValidationService                                               │
    │    ├── Step 0: LLM Customer Matching (CustomerMatcherAgent) [NEW]       │
    │    │    └── Fuzzy matching: abbreviations, typos, variations            │
    │    │                                                                     │
    │    ├── Tier 1: KYP Compliance Assessment (KYPProcessor)                 │
    │    │    └── Partner risk rating, sanctions, regulatory history          │
    │    │                                                                     │
    │    ├── Tier 2: SAP/ECC Validation (MS5Client)                           │
    │    │    ├── Customer master data (BAPI_CUSTOMER_GETDETAIL2)             │
    │    │    ├── Credit check (BAPI_CR_ACC_GETDETAIL)                        │
    │    │    └── Partner functions (AG, WE, RE, RG)                          │
    │    │                                                                     │
    │    └── Combined Decision                                                 │
    │         ├── Both tiers must pass for automatic approval                 │
    │         ├── Medium-High/High KYP risk → requires EDD                    │
    │         └── Failed credit check → order blocked                         │
    └─────────────────────────────────────────────────────────────────────────┘

New Flow (Human-in-the-Loop):
    1. Sales enters "batam fast ferry" (free text)
    2. Call find_customer() → returns ranked candidates
       [1] Batam Fast Ferry Pte. Ltd. (SAP: 0000100001) - 95% confidence
       [2] BatamFast (KYP Report) - 92% confidence
    3. User selects [1] to confirm match
    4. Call validate_customer(customer_id="0000100001") → full validation

Usage:
    from lead_to_cash.services.customer_validation_service import CustomerValidationService
    from lead_to_cash.integrations import MS5Client, CPISimulator

    # With CPISimulator and LLM matching
    cpi_sim = CPISimulator()
    await cpi_sim.connect()
    ms5 = MS5Client(cpi_client=cpi_sim)

    service = CustomerValidationService(
        ms5_client=ms5,
        kyp_reports_dir="data/",
        enable_llm_matching=True,  # Enable LLM-based matching
    )
    await service.connect()

    # Step 1: Find customer candidates (LLM matching)
    match_result = await service.find_customer("batam fast ferry")
    for c in match_result.candidates:
        print(f"{c.rank}. {c.name} - {c.confidence_score}%")

    # Step 2: User selects candidate
    selected = match_result.candidates[0]  # User chose first option

    # Step 3: Validate with confirmed customer ID
    result = await service.validate_customer(selected.customer_id)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from lead_to_cash.integrations import MS5Client
from lead_to_cash.services.kyp_processor import (
    KYPAssessmentResult,
    KYPProcessor,
    RiskLevel,
)

if TYPE_CHECKING:
    from lead_to_cash.agents.customer_matcher_agent import (
        CustomerMatcherAgent,
        CustomerMatchResult,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Fallback Match Data Classes (Module Level - No Kaizen Dependency)
# =============================================================================


class FallbackMatchSource(str, Enum):
    """Source system for fallback matching."""

    SAP_CPI = "SAP_CPI"
    KYP_REPORT = "KYP_REPORT"
    BOTH = "BOTH"


class FallbackConfidenceLevel(str, Enum):
    """Confidence level for fallback matching."""

    HIGH = "HIGH"  # >= 90%
    MEDIUM = "MEDIUM"  # 70-89%
    LOW = "LOW"  # 50-69%
    UNCERTAIN = "UNCERTAIN"  # < 50%


@dataclass
class FallbackMatchCandidate:
    """Match candidate for fallback mode (no Kaizen dependency)."""

    rank: int
    name: str
    customer_id: Optional[str]
    source: FallbackMatchSource
    confidence_score: float
    confidence_level: FallbackConfidenceLevel
    match_reasons: list[str]
    sap_data: Optional[dict[str, Any]] = None
    kyp_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rank": self.rank,
            "name": self.name,
            "customer_id": self.customer_id,
            "source": self.source.value,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level.value,
            "match_reasons": self.match_reasons,
            "sap_data": self.sap_data,
            "kyp_data": self.kyp_data,
        }


@dataclass
class FallbackMatchResult:
    """Match result for fallback mode (no Kaizen dependency)."""

    query: str
    candidates: list[FallbackMatchCandidate]
    best_match: Optional[FallbackMatchCandidate]
    has_high_confidence_match: bool
    requires_user_confirmation: bool
    search_stats: dict[str, Any]
    searched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "has_high_confidence_match": self.has_high_confidence_match,
            "requires_user_confirmation": self.requires_user_confirmation,
            "search_stats": self.search_stats,
            "searched_at": self.searched_at.isoformat(),
        }

    def get_candidate_by_rank(self, rank: int) -> Optional[FallbackMatchCandidate]:
        """Get candidate by rank (1-indexed)."""
        for c in self.candidates:
            if c.rank == rank:
                return c
        return None


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ValidationTier(str, Enum):
    """Validation tier identifier."""

    TIER1_KYP = "TIER1_KYP"
    TIER2_SAP = "TIER2_SAP"


class OverallStatus(str, Enum):
    """Overall validation status."""

    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class TierResult:
    """Result from a single validation tier."""

    tier: ValidationTier
    passed: bool
    status: str
    score: float
    issues: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CombinedValidationResult:
    """Combined result from both validation tiers."""

    customer_id: str
    customer_name: str
    overall_status: OverallStatus
    can_proceed: bool
    requires_human_review: bool
    requires_enhanced_dd: bool
    tier1_kyp: Optional[TierResult]
    tier2_sap: Optional[TierResult]
    combined_score: float
    issues: list[str]
    conditions: list[str]
    recommendations: list[str]
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "overall_status": self.overall_status.value,
            "can_proceed": self.can_proceed,
            "requires_human_review": self.requires_human_review,
            "requires_enhanced_dd": self.requires_enhanced_dd,
            "tier1_kyp": (
                {
                    "tier": self.tier1_kyp.tier.value,
                    "passed": self.tier1_kyp.passed,
                    "status": self.tier1_kyp.status,
                    "score": self.tier1_kyp.score,
                    "issues": self.tier1_kyp.issues,
                    "details": self.tier1_kyp.details,
                }
                if self.tier1_kyp
                else None
            ),
            "tier2_sap": (
                {
                    "tier": self.tier2_sap.tier.value,
                    "passed": self.tier2_sap.passed,
                    "status": self.tier2_sap.status,
                    "score": self.tier2_sap.score,
                    "issues": self.tier2_sap.issues,
                    "details": self.tier2_sap.details,
                }
                if self.tier2_sap
                else None
            ),
            "combined_score": self.combined_score,
            "issues": self.issues,
            "conditions": self.conditions,
            "recommendations": self.recommendations,
            "validated_at": self.validated_at.isoformat(),
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"## Customer Validation: {self.customer_name}",
            f"**Overall Status:** {self.overall_status.value}",
            f"**Can Proceed:** {'Yes' if self.can_proceed else 'No'}",
            "",
        ]

        if self.tier1_kyp:
            lines.extend(
                [
                    "### Tier 1: KYP Compliance Assessment",
                    f"- Status: {self.tier1_kyp.status}",
                    f"- Risk Rating: {self.tier1_kyp.details.get('risk_rating', 'N/A')}",
                ]
            )

        if self.tier2_sap:
            credit_limit = self.tier2_sap.details.get("credit_limit", 0)
            available = self.tier2_sap.details.get("available_credit", 0)
            lines.extend(
                [
                    "",
                    "### Tier 2: SAP/ECC Validation",
                    f"- Status: {self.tier2_sap.status}",
                    f"- Credit Limit: {credit_limit:,.2f}",
                    f"- Available Credit: {available:,.2f}",
                ]
            )

        if self.issues:
            lines.extend(["", "### Issues Found"])
            for issue in self.issues[:5]:
                lines.append(f"- {issue}")

        if self.conditions:
            lines.extend(["", "### Conditions/Required Actions"])
            for cond in self.conditions[:5]:
                lines.append(f"- {cond}")

        return "\n".join(lines)


# =============================================================================
# Customer Validation Service
# =============================================================================


class CustomerValidationService:
    """
    Two-Tier Customer Validation Service with LLM-Based Matching.

    Combines KYP compliance assessment with SAP/ECC transactional validation.
    Optionally uses LLM-based intelligent matching for customer names.

    Args:
        ms5_client: MS5Client instance for SAP/ECC validation
        kyp_processor: KYPProcessor instance for compliance assessment
        kyp_reports_dir: Directory containing KYP report files
        credit_control_area: SAP credit control area (default: "1000")
        sales_org: SAP sales organization (default: "1000")
        enable_llm_matching: Enable LLM-based customer matching (default: False)
        customer_matcher: Pre-configured CustomerMatcherAgent instance

    Example:
        # With CPISimulator and LLM matching for development
        from lead_to_cash.integrations import CPISimulator, MS5Client

        cpi_sim = CPISimulator()
        await cpi_sim.connect()
        ms5 = MS5Client(cpi_client=cpi_sim)

        service = CustomerValidationService(
            ms5_client=ms5,
            kyp_reports_dir="data/",
            enable_llm_matching=True,  # Enable LLM customer matching
        )
        await service.connect()

        # Find customer with LLM matching
        match_result = await service.find_customer("batam fast ferry")
        for c in match_result.candidates:
            print(f"{c.rank}. {c.name} - {c.confidence_score}%")

        # Validate with confirmed customer
        result = await service.validate_customer(match_result.best_match.customer_id)
    """

    def __init__(
        self,
        ms5_client: Optional[MS5Client] = None,
        kyp_processor: Optional[KYPProcessor] = None,
        kyp_reports_dir: Optional[str] = None,
        credit_control_area: str = "1000",
        sales_org: str = "1000",
        enable_llm_matching: bool = False,
        customer_matcher: Optional["CustomerMatcherAgent"] = None,
    ):
        """Initialize Customer Validation Service."""
        self._ms5 = ms5_client
        self._kyp = kyp_processor or KYPProcessor(reports_directory=kyp_reports_dir)
        self._connected = False
        self._credit_control_area = credit_control_area
        self._sales_org = sales_org
        self._enable_llm_matching = enable_llm_matching
        self._customer_matcher = customer_matcher
        # Cache for customer name-to-ID mapping (fallback when LLM not available)
        self._customer_cache: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        """Connect to SAP systems and initialize LLM matcher if enabled."""
        if self._ms5 and not self._connected:
            await self._ms5.connect()
            self._connected = True
            logger.info("Customer Validation Service connected")

        # Initialize LLM customer matcher if enabled but not provided
        if self._enable_llm_matching and self._customer_matcher is None:
            await self._initialize_customer_matcher()

    async def _initialize_customer_matcher(self) -> None:
        """Initialize the CustomerMatcherAgent for LLM-based matching."""
        try:
            from lead_to_cash.agents.customer_matcher_agent import (
                CustomerMatcherAgent,
                CustomerMatcherConfig,
            )

            config = CustomerMatcherConfig()
            # Pass CPI client if available (for SAP candidate data)
            cpi_client = self._ms5.cpi if self._ms5 else None
            self._customer_matcher = CustomerMatcherAgent(
                config=config,
                cpi_client=cpi_client,
                kyp_processor=self._kyp,
            )
            logger.info("CustomerMatcherAgent initialized for LLM-based matching")
        except ImportError as e:
            logger.warning(f"Could not initialize CustomerMatcherAgent: {e}")
            self._enable_llm_matching = False
        except Exception as e:
            logger.error(f"Error initializing CustomerMatcherAgent: {e}")
            self._enable_llm_matching = False

    async def disconnect(self) -> None:
        """Disconnect from SAP systems."""
        if self._ms5 and self._connected:
            await self._ms5.disconnect()
            self._connected = False

    def set_connected(self, connected: bool) -> None:
        """Set connection state (for shared client scenarios)."""
        self._connected = connected

    # -------------------------------------------------------------------------
    # LLM-Based Customer Matching
    # -------------------------------------------------------------------------

    async def find_customer(
        self,
        search_query: str,
        context: str = "",
    ) -> "CustomerMatchResult":
        """
        Find customer candidates using LLM-based intelligent matching.

        This method should be called BEFORE validate_customer() to allow
        the user to select the correct customer from ranked candidates.

        Args:
            search_query: Free-text customer name (e.g., "batam fast ferry")
            context: Optional context (e.g., "Singapore ferry operator")

        Returns:
            CustomerMatchResult with ranked candidates

        Raises:
            RuntimeError: If LLM matching is not enabled

        Example:
            # Step 1: Find candidates
            match_result = await service.find_customer("batam fast ferry")

            # Step 2: Present to user
            for c in match_result.candidates:
                print(f"{c.rank}. {c.name} ({c.customer_id}) - {c.confidence_score}%")
                print(f"   Reasons: {', '.join(c.match_reasons)}")

            # Step 3: User selects candidate
            selected = match_result.candidates[0]

            # Step 4: Validate with confirmed customer
            result = await service.validate_customer(selected.customer_id)
        """
        if not self._enable_llm_matching or self._customer_matcher is None:
            # Fall back to creating a basic match result from cache
            return await self._fallback_find_customer(search_query)

        logger.info(f"Finding customer with LLM matching: '{search_query}'")
        return await self._customer_matcher.match_customer(search_query, context)

    async def _fallback_find_customer(self, search_query: str) -> FallbackMatchResult:
        """
        Fallback customer search using fuzzy string matching.

        Searches BOTH SAP/CPI customers AND KYP reports.
        Uses difflib.SequenceMatcher for fuzzy matching (handles abbreviations).

        Args:
            search_query: Free-text customer name

        Returns:
            FallbackMatchResult with ranked candidates from both sources
        """
        logger.warning(
            f"Using fallback matching for '{search_query}' - "
            "LLM matching unavailable (Kaizen not installed). "
            "Results may be less accurate."
        )

        candidates: list[FallbackMatchCandidate] = []

        # Normalize search query
        search_normalized = self._normalize_name(search_query)

        # 1. Search SAP/CPI customers
        sap_candidates = await self._search_sap_customers(
            search_normalized, search_query
        )
        candidates.extend(sap_candidates)

        # 2. Search KYP reports
        kyp_candidates = await self._search_kyp_reports(search_normalized, search_query)
        candidates.extend(kyp_candidates)

        # 3. Deduplicate by name (prefer SAP if both have same name)
        candidates = self._deduplicate_candidates(candidates)

        # 4. Sort by confidence and assign ranks
        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        for i, c in enumerate(candidates[:10], start=1):
            c.rank = i

        best = candidates[0] if candidates else None
        has_high = (
            best is not None and best.confidence_level == FallbackConfidenceLevel.HIGH
        )

        return FallbackMatchResult(
            query=search_query,
            candidates=candidates[:10],
            best_match=best,
            has_high_confidence_match=has_high,
            requires_user_confirmation=not has_high,
            search_stats={
                "mode": "fallback",
                "llm_enabled": False,
                "kaizen_available": False,
                "sap_candidates": len(sap_candidates),
                "kyp_candidates": len(kyp_candidates),
                "total_candidates": len(candidates),
            },
        )

    def _normalize_name(self, name: str) -> str:
        """
        Normalize customer name for matching.

        - Lowercase
        - Remove common suffixes (Pte. Ltd., A/S, B.V., etc.)
        - Remove punctuation
        - Collapse whitespace
        """
        normalized = name.lower()

        # Remove common legal entity suffixes
        suffixes = [
            r"\bpte\.?\s*ltd\.?",
            r"\bpty\.?\s*ltd\.?",
            r"\bltd\.?",
            r"\binc\.?",
            r"\bcorp\.?",
            r"\ba/s\b",
            r"\bb\.?v\.?",
            r"\bgmbh\b",
            r"\bs\.?a\.?",
            r"\bllc\.?",
            r"\blimited\b",
            r"\bco\.?",
        ]
        for suffix in suffixes:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)

        # Remove punctuation except hyphens
        normalized = re.sub(r"[^\w\s-]", "", normalized)

        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _calculate_match_score(
        self, query_normalized: str, name_normalized: str, original_name: str
    ) -> tuple[float, list[str]]:
        """
        Calculate match score using multiple strategies.

        Returns (score, list of match reasons).
        """
        reasons = []
        scores = []

        # Strategy 1: Exact match (after normalization)
        if query_normalized == name_normalized:
            return 98.0, ["Exact match (normalized)"]

        # Strategy 2: Substring match
        if query_normalized in name_normalized:
            scores.append(85.0)
            reasons.append("Query is substring of name")
        elif name_normalized in query_normalized:
            scores.append(80.0)
            reasons.append("Name is substring of query")

        # Strategy 3: Fuzzy match using SequenceMatcher
        ratio = SequenceMatcher(None, query_normalized, name_normalized).ratio()
        fuzzy_score = ratio * 100
        if fuzzy_score >= 60:
            scores.append(fuzzy_score)
            reasons.append(f"Fuzzy match ({ratio:.0%} similar)")

        # Strategy 4: Word overlap
        query_words = set(query_normalized.split())
        name_words = set(name_normalized.split())
        if query_words and name_words:
            overlap = query_words & name_words
            if overlap:
                overlap_ratio = len(overlap) / max(len(query_words), len(name_words))
                word_score = 50 + (overlap_ratio * 40)
                scores.append(word_score)
                reasons.append(f"Word overlap: {', '.join(overlap)}")

        # Strategy 5: Abbreviation detection (e.g., "batamfast" vs "batam fast")
        query_no_space = query_normalized.replace(" ", "").replace("-", "")
        name_no_space = name_normalized.replace(" ", "").replace("-", "")
        if query_no_space == name_no_space:
            return 92.0, ["Abbreviation match (spaces removed)"]
        elif query_no_space in name_no_space or name_no_space in query_no_space:
            scores.append(85.0)
            reasons.append("Abbreviation substring match")

        # Strategy 6: Initial letters match (e.g., "BFFPL" for "Batam Fast Ferry Pte Ltd")
        name_initials = "".join(w[0] for w in original_name.split() if w)
        if query_normalized.upper() == name_initials.upper():
            scores.append(75.0)
            reasons.append(f"Initials match: {name_initials}")

        if not scores:
            return 0.0, []

        return max(scores), reasons

    def _score_to_confidence_level(self, score: float) -> FallbackConfidenceLevel:
        """Convert numeric score to confidence level."""
        if score >= 90:
            return FallbackConfidenceLevel.HIGH
        elif score >= 70:
            return FallbackConfidenceLevel.MEDIUM
        elif score >= 50:
            return FallbackConfidenceLevel.LOW
        else:
            return FallbackConfidenceLevel.UNCERTAIN

    async def _search_sap_customers(
        self, search_normalized: str, original_query: str
    ) -> list[FallbackMatchCandidate]:
        """Search SAP/CPI customers."""
        candidates = []

        # Build cache if empty
        if not self._customer_cache:
            customers = await self.list_customers()
            for c in customers:
                name_key = c.get("name", "").lower()
                self._customer_cache[name_key] = c

        for name_key, customer in self._customer_cache.items():
            original_name = customer.get("name", "")
            name_normalized = self._normalize_name(original_name)

            score, reasons = self._calculate_match_score(
                search_normalized, name_normalized, original_name
            )

            if score >= 40:  # Minimum threshold
                candidates.append(
                    FallbackMatchCandidate(
                        rank=0,
                        name=original_name,
                        customer_id=customer.get("customer_id"),
                        source=FallbackMatchSource.SAP_CPI,
                        confidence_score=round(score, 1),
                        confidence_level=self._score_to_confidence_level(score),
                        match_reasons=reasons or ["Partial match"],
                        sap_data=customer,
                    )
                )

        return candidates

    async def _search_kyp_reports(
        self, search_normalized: str, original_query: str
    ) -> list[FallbackMatchCandidate]:
        """Search KYP reports."""
        candidates = []

        kyp_reports = self._kyp.list_reports()

        for report in kyp_reports:
            partner_name = report.get("partner_name", "")
            name_normalized = self._normalize_name(partner_name)

            score, reasons = self._calculate_match_score(
                search_normalized, name_normalized, partner_name
            )

            if score >= 40:  # Minimum threshold
                candidates.append(
                    FallbackMatchCandidate(
                        rank=0,
                        name=partner_name,
                        customer_id=None,  # KYP reports don't have SAP ID
                        source=FallbackMatchSource.KYP_REPORT,
                        confidence_score=round(score, 1),
                        confidence_level=self._score_to_confidence_level(score),
                        match_reasons=reasons
                        + [f"KYP Risk: {report.get('risk_rating', 'N/A')}"],
                        kyp_data=report,
                    )
                )

        return candidates

    def _deduplicate_candidates(
        self, candidates: list[FallbackMatchCandidate]
    ) -> list[FallbackMatchCandidate]:
        """
        Deduplicate candidates by normalized name.

        If same name appears in both SAP and KYP, merge them.
        """
        seen: dict[str, FallbackMatchCandidate] = {}

        for candidate in candidates:
            key = self._normalize_name(candidate.name)

            if key in seen:
                existing = seen[key]
                # Merge: keep higher score, combine sources
                if candidate.confidence_score > existing.confidence_score:
                    # Use the higher-scoring candidate as base
                    merged = candidate
                    merged.match_reasons = list(
                        set(existing.match_reasons + candidate.match_reasons)
                    )
                else:
                    merged = existing
                    merged.match_reasons = list(
                        set(existing.match_reasons + candidate.match_reasons)
                    )

                # Mark as BOTH if different sources
                if existing.source != candidate.source:
                    merged.source = FallbackMatchSource.BOTH
                    # Prefer SAP customer_id
                    if not merged.customer_id and candidate.customer_id:
                        merged.customer_id = candidate.customer_id
                    elif not merged.customer_id and existing.customer_id:
                        merged.customer_id = existing.customer_id
                    # Merge data
                    if candidate.sap_data:
                        merged.sap_data = candidate.sap_data
                    if candidate.kyp_data:
                        merged.kyp_data = candidate.kyp_data

                seen[key] = merged
            else:
                seen[key] = candidate

        return list(seen.values())

    async def _resolve_customer_id(
        self,
        identifier: str,
        use_llm: bool = True,
        min_confidence: float = 80.0,
    ) -> tuple[str, str]:
        """
        Resolve customer identifier to SAP customer ID and name.

        Uses LLM-based matching if enabled, otherwise falls back to cache lookup.

        Args:
            identifier: Customer name or SAP customer ID
            use_llm: Whether to use LLM matching (if enabled globally)
            min_confidence: Minimum confidence for auto-selecting LLM match

        Returns:
            Tuple of (customer_id, customer_name)
        """
        # If it's already a 10-digit number, use it directly
        if identifier.isdigit():
            return identifier.zfill(10), identifier

        # Try LLM-based matching first if enabled
        if use_llm and self._enable_llm_matching and self._customer_matcher is not None:
            try:
                match_result = await self._customer_matcher.match_customer(identifier)
                if (
                    match_result.best_match
                    and match_result.best_match.confidence_score >= min_confidence
                ):
                    best = match_result.best_match
                    logger.info(
                        f"LLM matched '{identifier}' to '{best.name}' "
                        f"(ID: {best.customer_id}, confidence: {best.confidence_score}%)"
                    )
                    return best.customer_id or identifier, best.name
                else:
                    logger.info(
                        f"LLM matching for '{identifier}' - no high confidence match, "
                        f"best: {match_result.best_match.confidence_score if match_result.best_match else 0}%"
                    )
            except Exception as e:
                logger.warning(f"LLM matching failed, falling back to cache: {e}")

        # Fallback to cache-based lookup
        # Build cache if empty
        if not self._customer_cache:
            customers = await self.list_customers()
            for c in customers:
                # Index by name (case-insensitive) and by ID
                name_key = c.get("name", "").lower()
                self._customer_cache[name_key] = c
                self._customer_cache[c.get("customer_id", "")] = c

        # Try to find by name (case-insensitive)
        identifier_lower = identifier.lower()
        if identifier_lower in self._customer_cache:
            customer = self._customer_cache[identifier_lower]
            return customer.get("customer_id", identifier), customer.get(
                "name", identifier
            )

        # Try partial match
        for name_key, customer in self._customer_cache.items():
            if identifier_lower in name_key or name_key in identifier_lower:
                return customer.get("customer_id", identifier), customer.get(
                    "name", identifier
                )

        # Not found - return as-is
        logger.warning(f"Customer '{identifier}' not found in cache, using as-is")
        return identifier, identifier

    async def validate_customer(
        self,
        customer_identifier: str,
        order_value: float = 0.0,
        skip_tier1: bool = False,
        skip_tier2: bool = False,
    ) -> CombinedValidationResult:
        """
        Perform comprehensive two-tier customer validation.

        Args:
            customer_identifier: Customer name or SAP customer ID
            order_value: Optional order value for credit check
            skip_tier1: Skip KYP compliance check
            skip_tier2: Skip SAP/ECC validation

        Returns:
            CombinedValidationResult with both tier results
        """
        logger.info(f"Starting customer validation for: {customer_identifier}")

        if not self._connected and self._ms5:
            await self.connect()

        # Resolve customer name to ID (supports both name and ID input)
        customer_id, customer_name = await self._resolve_customer_id(
            customer_identifier
        )
        logger.info(f"Resolved customer: ID={customer_id}, Name={customer_name}")

        # Tier 1: KYP Compliance Assessment (uses customer name for report lookup)
        tier1_result = None
        if not skip_tier1:
            # Use resolved name for KYP lookup, fall back to original identifier
            kyp_name = (
                customer_name if customer_name != customer_id else customer_identifier
            )
            tier1_result = await self._validate_tier1_kyp(kyp_name)
            # Update name from KYP if found
            if tier1_result and tier1_result.details.get("partner_name"):
                partner_name = tier1_result.details["partner_name"]
                if partner_name != kyp_name:  # KYP found a better name
                    customer_name = partner_name

        # Tier 2: SAP/ECC Validation (uses customer ID)
        tier2_result = None
        if not skip_tier2 and self._ms5:
            tier2_result = await self._validate_tier2_sap(customer_id, order_value)
            # Update from SAP response
            if tier2_result and tier2_result.details.get("customer_id"):
                customer_id = tier2_result.details["customer_id"]
            if tier2_result and tier2_result.details.get("customer_name"):
                customer_name = tier2_result.details["customer_name"]

        return self._combine_results(
            customer_id=customer_id,
            customer_name=customer_name,
            tier1_result=tier1_result,
            tier2_result=tier2_result,
        )

    async def _validate_tier1_kyp(self, customer_name: str) -> TierResult:
        """Perform Tier 1 KYP Compliance Assessment."""
        logger.info(f"Tier 1 KYP assessment for: {customer_name}")

        kyp_result: KYPAssessmentResult = await self._kyp.get_risk_assessment(
            customer_name
        )

        passed = kyp_result.kyp_status in ["PASSED", "REQUIRES_EDD"]
        blocked = kyp_result.kyp_status == "FAILED"

        score_map = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.75,
            RiskLevel.MEDIUM_HIGH: 0.5,
            RiskLevel.HIGH: 0.25,
            RiskLevel.NOT_ASSESSED: 0.0,
        }
        score = score_map.get(kyp_result.risk_rating, 0.5)

        if blocked:
            status = "BLOCKED - Partner rejected"
        elif kyp_result.requires_enhanced_dd:
            status = "CONDITIONAL - EDD Required"
        elif passed:
            status = "PASSED"
        else:
            status = "PENDING - Assessment needed"

        return TierResult(
            tier=ValidationTier.TIER1_KYP,
            passed=passed and not blocked,
            status=status,
            score=score,
            issues=kyp_result.issues,
            details={
                "partner_name": kyp_result.partner_name,
                "risk_rating": kyp_result.risk_rating.value,
                "approval_status": kyp_result.approval_status.value,
                "requires_edd": kyp_result.requires_enhanced_dd,
                "conditions": kyp_result.conditions,
                "summary": kyp_result.summary,
            },
        )

    async def _validate_tier2_sap(
        self, customer_id: str, order_value: float = 0.0
    ) -> TierResult:
        """Perform Tier 2 SAP/ECC Validation using MS5Client.

        Args:
            customer_id: SAP customer ID (10-digit format)
            order_value: Order value for credit check
        """
        logger.info(f"Tier 2 SAP validation for: {customer_id}")

        issues: list[str] = []
        details: dict[str, Any] = {}
        checks_passed = 0
        total_checks = 3  # master_data, credit, partner_functions

        # Ensure customer ID is in SAP format (10 digits, zero-padded)
        if customer_id.isdigit():
            customer_id = customer_id.zfill(10)

        # MS5 client must be available for Tier 2 validation
        assert self._ms5 is not None, "MS5 client required for Tier 2 validation"

        try:
            # 1. Customer Master Data Check
            try:
                customer_data = await self._ms5.get_customer(customer_id)
                master_data_valid = bool(customer_data.name)

                if master_data_valid:
                    checks_passed += 1
                    details["customer_id"] = customer_id
                    details["customer_name"] = customer_data.name
                    details["address"] = customer_data.address
                else:
                    issues.append("Customer master data incomplete")
            except Exception as e:
                issues.append(f"Customer not found: {e}")
                master_data_valid = False

            # 2. Credit Check (using configured credit control area)
            try:
                credit_data = await self._ms5.check_credit_limit(
                    customer_id,
                    order_value=order_value,
                    credit_control_area=self._credit_control_area,
                )

                details["credit_limit"] = credit_data.credit_limit
                details["credit_exposure"] = credit_data.credit_exposure
                details["available_credit"] = credit_data.available_credit
                details["credit_utilization_pct"] = credit_data.utilization_percent
                details["credit_passed"] = credit_data.credit_check_passed

                if credit_data.credit_check_passed:
                    checks_passed += 1
                else:
                    if order_value > credit_data.available_credit:
                        issues.append(
                            f"Order value ({order_value:,.2f}) exceeds "
                            f"available credit ({credit_data.available_credit:,.2f})"
                        )
                    else:
                        issues.append("Credit check failed")

            except Exception as e:
                issues.append(f"Credit check failed: {e}")
                details["credit_passed"] = False

            # 3. Partner Functions Check (using configured sales org)
            try:
                partners = await self._ms5.get_partner_functions(
                    customer_id,
                    sales_org=self._sales_org,
                )
                assigned = [p.get("function", "") for p in partners]
                details["partner_functions"] = assigned

                required = ["AG", "WE", "RE", "RG"]
                missing = [f for f in required if f not in assigned]

                if not missing:
                    checks_passed += 1
                else:
                    func_names = {
                        "AG": "Sold-to",
                        "WE": "Ship-to",
                        "RE": "Bill-to",
                        "RG": "Payer",
                    }
                    missing_names = [func_names.get(f, f) for f in missing]
                    issues.append(
                        f"Missing partner functions: {', '.join(missing_names)}"
                    )

            except Exception as e:
                issues.append(f"Partner functions check failed: {e}")

        except Exception as e:
            logger.error(f"Tier 2 validation error: {e}")
            issues.append(f"SAP validation error: {e}")

        # Calculate score and status
        score = checks_passed / total_checks if total_checks > 0 else 0.0
        passed = score >= 0.67  # Need 2 of 3 checks

        credit_blocked = not details.get("credit_passed", True)

        if credit_blocked:
            status = "BLOCKED - Credit check failed"
        elif not master_data_valid:
            status = "FAILED - Customer not found"
        elif passed:
            status = "PASSED"
        else:
            status = f"PARTIAL - {checks_passed}/{total_checks} checks passed"

        return TierResult(
            tier=ValidationTier.TIER2_SAP,
            passed=passed,
            status=status,
            score=score,
            issues=issues,
            details=details,
        )

    def _combine_results(
        self,
        customer_id: str,
        customer_name: str,
        tier1_result: Optional[TierResult],
        tier2_result: Optional[TierResult],
    ) -> CombinedValidationResult:
        """Combine Tier 1 and Tier 2 results into final decision."""
        all_issues = []
        all_conditions = []
        recommendations = []
        requires_edd = False
        requires_human_review = False

        # Process Tier 1 results
        if tier1_result:
            all_issues.extend(tier1_result.issues)
            if tier1_result.details.get("requires_edd"):
                requires_edd = True
                all_conditions.extend(tier1_result.details.get("conditions", []))
            if not tier1_result.passed:
                if "BLOCKED" in tier1_result.status:
                    recommendations.append("Partner rejected - do not proceed")
                else:
                    recommendations.append("Complete KYP assessment")
        else:
            all_issues.append("Tier 1 KYP assessment not performed")
            recommendations.append("Complete KYP compliance assessment")
            requires_human_review = True

        # Process Tier 2 results
        if tier2_result:
            all_issues.extend(tier2_result.issues)
            if not tier2_result.details.get("credit_passed", True):
                all_conditions.append("Credit block must be released")
                requires_human_review = True
            if not tier2_result.passed:
                recommendations.append("Resolve SAP validation issues")
        else:
            all_issues.append("Tier 2 SAP validation not performed")
            recommendations.append("Complete SAP customer validation")
            requires_human_review = True

        # Calculate combined score
        scores = []
        if tier1_result:
            scores.append(tier1_result.score)
        if tier2_result:
            scores.append(tier2_result.score)
        combined_score = sum(scores) / len(scores) if scores else 0.0

        # Determine overall status
        if not tier1_result or not tier2_result:
            overall_status = OverallStatus.PENDING
            can_proceed = False
        elif tier1_result.passed and tier2_result.passed:
            if requires_edd:
                overall_status = OverallStatus.CONDITIONAL
                can_proceed = True
            else:
                overall_status = OverallStatus.APPROVED
                can_proceed = True
        elif "BLOCKED" in (
            tier1_result.status if tier1_result else ""
        ) or "BLOCKED" in (tier2_result.status if tier2_result else ""):
            overall_status = OverallStatus.BLOCKED
            can_proceed = False
        else:
            overall_status = OverallStatus.CONDITIONAL
            can_proceed = combined_score >= 0.6
            requires_human_review = True

        return CombinedValidationResult(
            customer_id=customer_id,
            customer_name=customer_name,
            overall_status=overall_status,
            can_proceed=can_proceed,
            requires_human_review=requires_human_review,
            requires_enhanced_dd=requires_edd,
            tier1_kyp=tier1_result,
            tier2_sap=tier2_result,
            combined_score=combined_score,
            issues=all_issues,
            conditions=all_conditions,
            recommendations=recommendations,
        )

    async def list_customers(self) -> list[dict[str, Any]]:
        """List available customers (from CPI simulator if used)."""
        if self._ms5 and hasattr(self._ms5.cpi, "list_customers"):
            return self._ms5.cpi.list_customers()
        return []

    async def __aenter__(self) -> "CustomerValidationService":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
