"""
Response Quality Infrastructure

Provides enums, contracts, validators, and enforcers for consistent,
grounded, scope-disciplined responses across the platform.

Architecture:
    1. SourceTier — priority ordering for data sources
    2. IntentScope — defines what each intent is ALLOWED to include
    3. ResponseContract — schema contract for each response type
    4. GroundingValidator — checks that claims are backed by evidence
    5. ScopeEnforcer — blocks out-of-scope content sections
    6. OutputSchemaValidator — validates response structure before sending
    7. FollowUpResolver — resolves follow-up queries against previous context
    8. QualityMetrics — observability hooks for quality monitoring

Usage:
    from lead_to_cash.core.response_quality import (
        SourceTier, IntentScope, ScopeEnforcer, GroundingValidator,
        OutputSchemaValidator, FollowUpResolver, QualityMetrics,
    )
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Source Tier Hierarchy
# =============================================================================


class SourceTier(int, Enum):
    """
    Source priority hierarchy. Lower number = higher trust.

    Enforcement: When sources from multiple tiers provide conflicting data,
    the HIGHER tier (lower number) wins. Tier 4 sources MUST be labeled
    as external/unverified in the response.
    """

    TIER_1_INTERNAL_STRUCTURED = 1
    """SAP CPI, internal KB product specs, curated data. Highest trust."""

    TIER_2_INTERNAL_SEMANTIC = 2
    """pgvector retrieval, curated documents, knowledge base embeddings."""

    TIER_3_EXTERNAL_TRUSTED = 3
    """EODHD financial data, Aravo TPRM, sanctioned databases."""

    TIER_4_EXTERNAL_BROAD = 4
    """Perplexity web search, NewsAPI. Must be labeled as external."""


# Map data sources to their tiers
SOURCE_TIER_MAP: Dict[str, SourceTier] = {
    # Tier 1: Internal structured
    "SAP CPI (MS5)": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "SAP CPI": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "SAP System": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "SAP CEC": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "IPAS": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "Product Database": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    "Knowledge Base": SourceTier.TIER_1_INTERNAL_STRUCTURED,
    # Tier 2: Internal semantic
    "Intelligence Database": SourceTier.TIER_2_INTERNAL_SEMANTIC,
    "Local Vector Database": SourceTier.TIER_2_INTERNAL_SEMANTIC,
    "Marine Intel DB": SourceTier.TIER_2_INTERNAL_SEMANTIC,
    # Tier 3: External trusted
    "EODHD": SourceTier.TIER_3_EXTERNAL_TRUSTED,
    "EODHD Fundamentals API": SourceTier.TIER_3_EXTERNAL_TRUSTED,
    "Financial Data": SourceTier.TIER_3_EXTERNAL_TRUSTED,
    "Aravo TPRM": SourceTier.TIER_3_EXTERNAL_TRUSTED,
    "Sanctions Database": SourceTier.TIER_3_EXTERNAL_TRUSTED,
    # Tier 4: External broad
    "Perplexity Search": SourceTier.TIER_4_EXTERNAL_BROAD,
    "Web Search": SourceTier.TIER_4_EXTERNAL_BROAD,
    "NewsAPI": SourceTier.TIER_4_EXTERNAL_BROAD,
}


def get_source_tier(source_name: str) -> SourceTier:
    """Get the tier for a source. Unknown sources default to Tier 4.

    HTTP URLs from the Marine Intel KB are classified as Tier 2 (internal semantic)
    because they are article URLs stored and verified in our database — not raw
    Perplexity search results.
    """
    tier = SOURCE_TIER_MAP.get(source_name)
    if tier is not None:
        return tier
    # KB article URLs are HTTP links stored in marine_opportunities.source_url.
    # They were verified at ingestion time. Treat as Tier 2 (internal semantic).
    if source_name.startswith(("https://", "http://")):
        return SourceTier.TIER_2_INTERNAL_SEMANTIC
    return SourceTier.TIER_4_EXTERNAL_BROAD


def get_highest_tier_sources(
    sources: List[str],
) -> Tuple[SourceTier, List[str]]:
    """Return the highest-tier sources from a list. Returns (tier, [sources])."""
    if not sources:
        return SourceTier.TIER_4_EXTERNAL_BROAD, []

    tiered = [(get_source_tier(s), s) for s in sources]
    best_tier = min(t for t, _ in tiered)
    best_sources = [s for t, s in tiered if t == best_tier]
    return best_tier, best_sources


def filter_sources_tier1_first(
    sources: List[str],
    max_tier: SourceTier,
) -> Tuple[List[str], List[str]]:
    """
    Filter sources using tier-1-first policy.

    If Tier 1 sources exist, return ONLY Tier 1 sources.
    Otherwise, return sources up to max_tier.

    Args:
        sources: List of source names to filter
        max_tier: Maximum tier allowed (from SourceDecision)

    Returns:
        Tuple of (kept_sources, removed_sources)
    """
    if not sources:
        return [], []

    tiered = [(get_source_tier(s), s) for s in sources]
    tier1 = [s for t, s in tiered if t == SourceTier.TIER_1_INTERNAL_STRUCTURED]

    # If Tier 1 sources present and sufficient, show only those
    if tier1:
        removed = [s for t, s in tiered if t != SourceTier.TIER_1_INTERNAL_STRUCTURED]
        return tier1, removed

    # Otherwise, keep sources up to max_tier
    kept = [s for t, s in tiered if t.value <= max_tier.value]
    removed = [s for t, s in tiered if t.value > max_tier.value]
    return kept, removed


def strip_ungrounded_citations(
    answer: str,
    allowed_sources: List[str],
    all_sources: List[str],
) -> Tuple[str, int]:
    """
    Remove [N] citation references from answer text if the cited source
    is not in the allowed list.

    Args:
        answer: Response text with [N] citations
        allowed_sources: Sources permitted after filtering
        all_sources: Original full source list (for index mapping)

    Returns:
        Tuple of (cleaned_answer, citations_removed_count)
    """
    if not answer or not all_sources:
        return answer, 0

    removed = 0
    allowed_set = set(allowed_sources)

    def _replace_citation(match: re.Match) -> str:
        nonlocal removed
        idx = int(match.group(1))
        if 1 <= idx <= len(all_sources):
            source = all_sources[idx - 1]
            if source not in allowed_set:
                removed += 1
                return ""  # Remove the citation marker
        return match.group(0)  # Keep valid citations

    cleaned = re.sub(r"\[(\d+)\]", _replace_citation, answer)
    return cleaned, removed


# =============================================================================
# Intent Scope Definitions
# =============================================================================


class ResponseSection(str, Enum):
    """Enumeration of all possible response sections."""

    # Product/Technical
    PRODUCT_SPECS = "product_specs"
    ENGINE_COMPARISON = "engine_comparison"
    TECHNICAL_DETAILS = "technical_details"
    PRODUCT_RECOMMENDATIONS = "product_recommendations"

    # Financial/Business
    FINANCIAL_PERFORMANCE = "financial_performance"
    CREDIT_STATUS = "credit_status"
    BILLING_STATUS = "billing_status"
    AGING_ANALYSIS = "aging_analysis"
    COLLECTIONS_STATUS = "collections_status"
    PAYMENT_TERMS = "payment_terms"
    DOWNPAYMENT_STATUS = "downpayment_status"

    # Intelligence
    MARKET_TRENDS = "market_trends"
    COMPETITOR_ACTIVITY = "competitor_activity"
    CUSTOMER_PROFILE = "customer_profile"
    INDUSTRY_NEWS = "industry_news"

    # Risk/Compliance
    SANCTIONS_CHECK = "sanctions_check"
    RISK_ASSESSMENT = "risk_assessment"
    OWNERSHIP_STRUCTURE = "ownership_structure"
    LITIGATION_HISTORY = "litigation_history"

    # Strategy (only when explicitly requested)
    SALES_STRATEGY = "sales_strategy"
    ACTION_ITEMS = "action_items"
    RECOMMENDATIONS = "recommendations"
    RRPS_IMPLICATIONS = "rrps_implications"


# What each intent is ALLOWED to include
# Anything not in this set for a given intent is OUT OF SCOPE
INTENT_ALLOWED_SECTIONS: Dict[str, FrozenSet[ResponseSection]] = {
    "product_fit": frozenset(
        {
            ResponseSection.PRODUCT_SPECS,
            ResponseSection.ENGINE_COMPARISON,
            ResponseSection.TECHNICAL_DETAILS,
            ResponseSection.PRODUCT_RECOMMENDATIONS,
        }
    ),
    "product_info": frozenset(
        {
            ResponseSection.PRODUCT_SPECS,
            ResponseSection.ENGINE_COMPARISON,
            ResponseSection.TECHNICAL_DETAILS,
        }
    ),
    "competitor_intel": frozenset(
        {
            ResponseSection.COMPETITOR_ACTIVITY,
            ResponseSection.ENGINE_COMPARISON,
            ResponseSection.PRODUCT_SPECS,
            ResponseSection.MARKET_TRENDS,
            ResponseSection.FINANCIAL_PERFORMANCE,
        }
    ),
    "customer_intel": frozenset(
        {
            ResponseSection.CUSTOMER_PROFILE,
            ResponseSection.CREDIT_STATUS,
            ResponseSection.INDUSTRY_NEWS,
        }
    ),
    "market_intel": frozenset(
        {
            ResponseSection.MARKET_TRENDS,
            ResponseSection.INDUSTRY_NEWS,
            ResponseSection.COMPETITOR_ACTIVITY,
        }
    ),
    "market_news": frozenset(
        {
            ResponseSection.MARKET_TRENDS,
            ResponseSection.INDUSTRY_NEWS,
        }
    ),
    "kyp_due_diligence": frozenset(
        {
            ResponseSection.SANCTIONS_CHECK,
            ResponseSection.RISK_ASSESSMENT,
            ResponseSection.OWNERSHIP_STRUCTURE,
            ResponseSection.LITIGATION_HISTORY,
            ResponseSection.CREDIT_STATUS,
            ResponseSection.FINANCIAL_PERFORMANCE,
            ResponseSection.CUSTOMER_PROFILE,
        }
    ),
    "billing_ar": frozenset(
        {
            ResponseSection.BILLING_STATUS,
            ResponseSection.AGING_ANALYSIS,
            ResponseSection.COLLECTIONS_STATUS,
            ResponseSection.PAYMENT_TERMS,
            ResponseSection.DOWNPAYMENT_STATUS,
            ResponseSection.CREDIT_STATUS,
        }
    ),
    "financial_analysis": frozenset(
        {
            ResponseSection.FINANCIAL_PERFORMANCE,
            ResponseSection.CREDIT_STATUS,
            ResponseSection.MARKET_TRENDS,
        }
    ),
    "relationship_check": frozenset(
        {
            ResponseSection.CUSTOMER_PROFILE,
            ResponseSection.CREDIT_STATUS,
            ResponseSection.COMPETITOR_ACTIVITY,
        }
    ),
    "general_question": frozenset(
        {
            # General questions can include most sections
            ResponseSection.PRODUCT_SPECS,
            ResponseSection.ENGINE_COMPARISON,
            ResponseSection.MARKET_TRENDS,
            ResponseSection.COMPETITOR_ACTIVITY,
            ResponseSection.CUSTOMER_PROFILE,
            ResponseSection.INDUSTRY_NEWS,
        }
    ),
}

# Sections that require EXPLICIT user request (never auto-included)
EXPLICIT_REQUEST_ONLY: FrozenSet[ResponseSection] = frozenset(
    {
        ResponseSection.SALES_STRATEGY,
        ResponseSection.ACTION_ITEMS,
        ResponseSection.RECOMMENDATIONS,
        ResponseSection.RRPS_IMPLICATIONS,
    }
)


# =============================================================================
# Scope Enforcer
# =============================================================================


class ScopeEnforcer:
    """
    Enforces that responses stay within the allowed scope for a given intent.

    Used in two places:
    1. PRE-SYNTHESIS: Generates scope boundary instructions for the LLM prompt
    2. POST-SYNTHESIS: Validates that the response doesn't contain out-of-scope sections
    """

    # Patterns that indicate out-of-scope content sections
    _SECTION_INDICATORS: Dict[ResponseSection, List[str]] = {
        ResponseSection.FINANCIAL_PERFORMANCE: [
            r"(?i)\b(revenue|market\s+cap|stock\s+price|share\s+price|P/E\s+ratio|earnings|EBITDA|profit\s+margin)\b",
        ],
        ResponseSection.SALES_STRATEGY: [
            r"(?i)\b(sales\s+strategy|go-to-market|penetration\s+strategy|sales\s+approach|selling\s+points)\b",
        ],
        ResponseSection.ACTION_ITEMS: [
            r"(?i)\b(action\s+items?|next\s+steps?|recommended\s+actions?|to-do|follow[- ]?up\s+actions?)\b",
        ],
        ResponseSection.RECOMMENDATIONS: [
            r"(?i)\b(we\s+recommend|I\s+recommend|recommendation[s]?:|suggested\s+approach|RRPS\s+should)\b",
        ],
        ResponseSection.RRPS_IMPLICATIONS: [
            r"(?i)\b(RRPS\s+implications?|implications?\s+for\s+(RRPS|Rolls.Royce|MTU|us)|what\s+this\s+means\s+for)\b",
        ],
        ResponseSection.BILLING_STATUS: [
            r"(?i)\b(billing\s+items?|invoice\s+status|AR\s+aging|accounts\s+receivable|outstanding\s+invoices?)\b",
        ],
        ResponseSection.AGING_ANALYSIS: [
            r"(?i)\b(aging\s+bucket|aging\s+analysis|days\s+overdue|overdue\s+invoices?|past\s+due)\b",
        ],
        ResponseSection.PRODUCT_SPECS: [
            r"(?i)\b(\d+\s*k[Ww]|\d+\s*hp|bore\s*×?\s*stroke|displacement|RPM\s+range|fuel\s+consumption)\b",
        ],
    }

    @classmethod
    def get_allowed_sections(
        cls,
        intent: str,
        explicit_request: bool = False,
    ) -> FrozenSet[ResponseSection]:
        """
        Get the set of allowed response sections for an intent.

        Args:
            intent: Query intent value (e.g., "competitor_intel")
            explicit_request: If True, also allows EXPLICIT_REQUEST_ONLY sections

        Returns:
            Set of allowed ResponseSection values
        """
        base = INTENT_ALLOWED_SECTIONS.get(
            intent,
            INTENT_ALLOWED_SECTIONS["general_question"],
        )
        if explicit_request:
            return base | EXPLICIT_REQUEST_ONLY
        return base

    @classmethod
    def build_scope_instruction(
        cls,
        intent: str,
        explicit_sections_requested: Optional[Set[str]] = None,
    ) -> str:
        """
        Build a scope boundary instruction for the synthesis prompt.

        Returns a text block that tells the LLM exactly what sections
        are allowed and which are forbidden.
        """
        allowed = cls.get_allowed_sections(
            intent,
            explicit_request=bool(explicit_sections_requested),
        )
        allowed_names = sorted(s.value for s in allowed)
        forbidden = set(ResponseSection) - allowed
        forbidden_names = sorted(s.value for s in forbidden)

        lines = [
            "## SCOPE DISCIPLINE (MANDATORY)",
            "",
            "You MUST stay within the following scope for this query.",
            "",
            f"**Intent:** {intent}",
            "",
            "**ALLOWED sections** (include ONLY these if relevant to the query):",
        ]
        for name in allowed_names:
            lines.append(f"  - {name}")

        lines.append("")
        lines.append(
            "**FORBIDDEN sections** (do NOT include these unless user explicitly asks):"
        )
        for name in forbidden_names:
            lines.append(f"  - {name}")

        lines.extend(
            [
                "",
                "**Rules:**",
                "1. Do NOT add recommendations, action items, or strategy unless the user explicitly asks for them.",
                '2. Do NOT add "RRPS Implications" or "What This Means For Us" sections unless asked.',
                "3. Do NOT mix financial/billing data into product or competitor responses.",
                "4. Do NOT mix product specs into financial or billing responses.",
                "5. If the user asks for ONE thing, answer ONLY that thing.",
                "6. Keep the response focused and single-purpose.",
                "",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def detect_scope_violations(
        cls,
        response_text: str,
        intent: str,
        explicit_request: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Post-synthesis check: detect sections that violate scope boundaries.

        Returns list of violations with section name and matched text.
        """
        allowed = cls.get_allowed_sections(intent, explicit_request)
        violations = []

        for section, patterns in cls._SECTION_INDICATORS.items():
            if section in allowed:
                continue

            for pattern in patterns:
                matches = re.findall(pattern, response_text)
                if matches:
                    violations.append(
                        {
                            "section": section.value,
                            "matched": matches[0]
                            if isinstance(matches[0], str)
                            else matches[0][0],
                            "intent": intent,
                        }
                    )
                    break  # One match per section is enough

        return violations


# =============================================================================
# Grounding Validator
# =============================================================================


@dataclass
class GroundingCheck:
    """Result of a grounding validation check."""

    is_grounded: bool
    claim: str
    source_tier: Optional[SourceTier] = None
    source_name: Optional[str] = None
    confidence: str = "UNKNOWN"  # HIGH, MEDIUM, LOW, UNKNOWN
    issue: Optional[str] = None


class GroundingValidator:
    """
    Validates that factual claims in responses are backed by retrieved evidence.

    Checks:
    1. Numeric claims (power ratings, financial figures) must cite a source
    2. Technical specs must come from Tier 1-2 sources
    3. Claims from Tier 4 sources must be labeled as external/unverified
    4. Missing sources trigger "insufficient evidence" responses
    """

    # Patterns for numeric/factual claims that MUST be grounded
    _NUMERIC_CLAIM_PATTERNS = [
        # Power ratings
        r"(\d{2,5}\s*k[Ww])\b",
        # Financial figures
        r"(?:USD|EUR|SGD|AUD)\s*[\d,.]+\s*(?:million|billion|M|B|k)?",
        r"\$[\d,.]+\s*(?:million|billion|M|B|k)?",
        # Percentages with context
        r"(\d+(?:\.\d+)?%)\s+(?:market\s+share|growth|decline|increase|decrease|margin)",
        # Specific dates/years with claims
        r"(?:in|since|by|from)\s+(\d{4})\s+(?:the\s+company|they|it|revenue|market)",
    ]

    # Patterns for technical claims that need Tier 1-2 sources
    _TECHNICAL_CLAIM_PATTERNS = [
        r"(?i)\b(bore|stroke|displacement|cylinder|turbocharger|injection|RPM)\b.*\d+",
        r"(?i)\b(ISO\s+8528|IMO\s+Tier|EPA\s+Tier|EU\s+Stage)\b",
        r"(?i)\b(fuel\s+consumption|specific\s+fuel|SFOC)\b.*\d+",
    ]

    @classmethod
    def check_grounding(
        cls,
        response_text: str,
        sources: List[str],
        retrieved_evidence: Optional[str] = None,
    ) -> List[GroundingCheck]:
        """
        Check if factual claims in the response are grounded in evidence.

        Args:
            response_text: The synthesized response text
            sources: List of source names used
            retrieved_evidence: Raw retrieved text from tools (optional)

        Returns:
            List of GroundingCheck results for each claim found
        """
        checks = []

        # Check numeric claims
        for pattern in cls._NUMERIC_CLAIM_PATTERNS:
            matches = re.finditer(pattern, response_text)
            for match in matches:
                claim_text = match.group(0)
                # Check if this claim appears in retrieved evidence
                is_grounded = False
                grounding_source = None
                grounding_tier = None

                if retrieved_evidence:
                    # Extract the core number from the claim
                    numbers = re.findall(r"\d+(?:[.,]\d+)*", claim_text)
                    for num in numbers:
                        if num in retrieved_evidence:
                            is_grounded = True
                            # Find which source this evidence came from
                            if sources:
                                grounding_tier, tier_sources = get_highest_tier_sources(
                                    sources
                                )
                                grounding_source = (
                                    tier_sources[0] if tier_sources else None
                                )
                            break

                checks.append(
                    GroundingCheck(
                        is_grounded=is_grounded,
                        claim=claim_text,
                        source_tier=grounding_tier,
                        source_name=grounding_source,
                        confidence="HIGH" if is_grounded else "LOW",
                        issue=None
                        if is_grounded
                        else "Numeric claim not found in retrieved evidence",
                    )
                )

        # Check technical claims need Tier 1-2
        for pattern in cls._TECHNICAL_CLAIM_PATTERNS:
            matches = re.finditer(pattern, response_text)
            for match in matches:
                claim_text = match.group(0)
                best_tier, best_sources = get_highest_tier_sources(sources)

                is_adequate = (
                    best_tier.value <= SourceTier.TIER_2_INTERNAL_SEMANTIC.value
                )
                checks.append(
                    GroundingCheck(
                        is_grounded=is_adequate,
                        claim=claim_text,
                        source_tier=best_tier,
                        source_name=best_sources[0] if best_sources else None,
                        confidence="HIGH" if is_adequate else "LOW",
                        issue=(
                            None
                            if is_adequate
                            else f"Technical claim sourced from {best_tier.name} — needs Tier 1 or 2"
                        ),
                    )
                )

        return checks

    @classmethod
    def build_grounding_instruction(cls, sources: List[str]) -> str:
        """
        Build grounding rules for the synthesis prompt based on available sources.
        """
        tier_groups: Dict[SourceTier, List[str]] = {}
        for s in sources:
            tier = get_source_tier(s)
            tier_groups.setdefault(tier, []).append(s)

        lines = [
            "## SOURCE GROUNDING RULES (MANDATORY)",
            "",
            "You have data from the following sources, ranked by trust level:",
            "",
        ]

        for tier in sorted(tier_groups.keys(), key=lambda t: t.value):
            tier_label = tier.name.replace("_", " ").title()
            source_list = ", ".join(tier_groups[tier])
            lines.append(f"**{tier_label}**: {source_list}")

        lines.extend(
            [
                "",
                "**Rules:**",
                "1. If Tier 1 and Tier 4 sources CONFLICT, use Tier 1 data and note the discrepancy.",
                "2. Technical specifications (kW, dimensions, fuel consumption) MUST come from Tier 1 or 2 sources.",
                "3. If you have NO source for a factual claim, say 'Data not available from our sources' instead of inferring.",
                "4. Tier 4 (web search) claims MUST be attributed: 'According to [source]...'",
                "5. NEVER present Tier 4 data as if it were verified internal data.",
                "6. If evidence is insufficient, say so. Do NOT fill gaps with training data.",
                "",
            ]
        )
        return "\n".join(lines)


# =============================================================================
# Output Schema Validator
# =============================================================================


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Required fields for each response type
RESPONSE_TYPE_SCHEMAS: Dict[str, Dict[str, type]] = {
    "answer": {
        "type": {"type": str, "required": True},
        "session_id": {"type": str, "required": True},
        "answer": {"type": str, "required": True},
        "sources": {"type": list, "required": True},
        "confidence": {"type": str, "required": True},
        "timestamp": {"type": str, "required": True},
    },
    "kyp_report": {
        "type": {"type": str, "required": True},
        "session_id": {"type": str, "required": True},
        "entity_name": {"type": str, "required": True},
        "sources": {"type": list, "required": True},
        "timestamp": {"type": str, "required": True},
    },
    "credit_report": {
        "type": {"type": str, "required": True},
        "session_id": {"type": str, "required": True},
        "credit": {"type": dict, "required": True},
        "sources": {"type": list, "required": True},
        "timestamp": {"type": str, "required": True},
    },
    "finops_report": {
        "type": {"type": str, "required": True},
        "session_id": {"type": str, "required": True},
        "timestamp": {"type": str, "required": True},
    },
    "order_detail": {
        "type": {"type": str, "required": True},
        "order": {"type": dict, "required": True},
        "sources": {"type": list, "required": True},
    },
    "opportunity_report": {
        "type": {"type": str, "required": True},
        "customer_name": {"type": str, "required": True},
        "opportunities": {"type": list, "required": True},
        "summary": {"type": dict, "required": True},
        "sources": {"type": list, "required": True},
    },
    "clarification_needed": {
        "type": {"type": str, "required": True},
        "questions": {"type": list, "required": True},
    },
    "entity_confirmation_needed": {
        "type": {"type": str, "required": True},
    },
    "error": {
        "type": {"type": str, "required": True},
    },
}


class OutputSchemaValidator:
    """
    Validates response dicts against their declared type schema.

    Used as the final gate before sending responses to the frontend.
    Ensures every response has the required fields and correct types.
    """

    @classmethod
    def validate(cls, response: Dict[str, Any]) -> ValidationResult:
        """
        Validate a response dict against its type schema.

        Args:
            response: The response dictionary to validate

        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []

        # Check type field exists
        resp_type = response.get("type")
        if not resp_type:
            errors.append("Response missing 'type' field")
            return ValidationResult(is_valid=False, errors=errors)

        # Check schema exists for this type
        schema = RESPONSE_TYPE_SCHEMAS.get(resp_type)
        if not schema:
            warnings.append(f"No schema defined for response type '{resp_type}'")
            return ValidationResult(is_valid=True, warnings=warnings)

        # Validate required fields
        for field_name, field_spec in schema.items():
            if field_spec.get("required", False):
                if field_name not in response:
                    errors.append(
                        f"Missing required field '{field_name}' for type '{resp_type}'"
                    )
                elif response[field_name] is None:
                    warnings.append(
                        f"Field '{field_name}' is None for type '{resp_type}'"
                    )

        # Validate sources are not empty for data responses
        if resp_type in ("answer", "kyp_report", "credit_report", "opportunity_report"):
            sources = response.get("sources", [])
            if not sources:
                warnings.append(f"Empty sources list for type '{resp_type}'")

        # Validate answer is not empty for answer type
        if resp_type == "answer":
            answer = response.get("answer", "")
            if not answer or not answer.strip():
                errors.append("Empty answer text for type 'answer'")

        # Validate confidence is valid
        if "confidence" in response:
            valid_confidence = {"HIGH", "MEDIUM", "LOW"}
            if response["confidence"] not in valid_confidence:
                warnings.append(
                    f"Invalid confidence '{response['confidence']}' — expected one of {valid_confidence}"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def ensure_type_field(
        cls, response: Dict[str, Any], expected_type: str
    ) -> Dict[str, Any]:
        """Ensure the response has the correct type field. Mutates and returns the dict."""
        if "type" not in response:
            response["type"] = expected_type
            logger.warning(f"Added missing 'type' field: {expected_type}")
        return response


# =============================================================================
# Follow-Up Context Resolver
# =============================================================================


@dataclass
class FollowUpResolution:
    """Result of resolving a follow-up query against previous context."""

    is_followup: bool
    resolved_intent: Optional[str] = None
    resolved_entity: Optional[str] = None
    resolved_context: Optional[Dict[str, Any]] = None
    carry_forward_sources: Optional[List[str]] = None
    original_query: Optional[str] = None
    confidence: float = 0.0


class FollowUpResolver:
    """
    Resolves follow-up queries against previous conversation context.

    Follow-up patterns:
    - "tell me more" → same intent, same entity, expand previous response
    - "what about offshore?" → same entity, modify scope/filter
    - "compare with MTU" → same intent, add comparison entity
    - "and their financials?" → same entity, change intent sub-scope
    """

    # Patterns that indicate a follow-up (not a new query)
    _FOLLOWUP_PATTERNS = [
        r"(?i)^(tell\s+me\s+more|more\s+details?|expand\s+on|elaborate|go\s+deeper)",
        r"(?i)^(what\s+about|how\s+about|and\s+what\s+about|what\s+of)",
        r"(?i)^(compare|versus|vs\.?|against)\s",
        r"(?i)^(and\s+)?(their|its|the)\s+(financials?|specs?|products?|fleet|performance|competitors?)",
        r"(?i)^(show|give|get)\s+me\s+(the\s+)?(full|detail|complete)\s+(report|analysis|breakdown)",
        r"(?i)^(what\s+about\s+)?(offshore|marine|power\s*gen|gas|onshore)",
        r"(?i)^(and|also|additionally|furthermore)\s",
        r"(?i)^(yes|ok|sure|right|exactly)[,.]?\s*(tell|show|give|what|how|and)?",
    ]

    # Patterns that indicate scope modification (same entity, different angle)
    _SCOPE_MODIFIERS = {
        r"(?i)\b(offshore|marine|naval|maritime)\b": "offshore_marine",
        r"(?i)\b(onshore|land.based|power\s*gen|stationary)\b": "onshore_powergen",
        r"(?i)\b(gas|dual.fuel|LNG)\b": "gas_applications",
        r"(?i)\b(financials?|revenue|earnings|market\s*cap)\b": "financial_analysis",
        r"(?i)\b(products?|engines?|specs?|technical)\b": "product_technical",
        r"(?i)\b(fleet|vessels?|ships?|boats?)\b": "fleet_analysis",
        r"(?i)\b(risks?|compliance|sanctions|litigation)\b": "risk_compliance",
    }

    @classmethod
    def is_followup_query(cls, query: str) -> bool:
        """Check if a query looks like a follow-up to a previous turn."""
        query_stripped = query.strip()
        # Very short queries are likely follow-ups
        if len(query_stripped.split()) <= 4:
            return True
        for pattern in cls._FOLLOWUP_PATTERNS:
            if re.search(pattern, query_stripped):
                return True
        return False

    @classmethod
    def resolve(
        cls,
        current_query: str,
        previous_intent: Optional[str],
        previous_entity: Optional[str],
        previous_response_type: Optional[str],
        session_context: Optional[Dict[str, Any]] = None,
    ) -> FollowUpResolution:
        """
        Resolve a follow-up query against the previous conversation turn.

        Args:
            current_query: The current user query
            previous_intent: Intent from the previous turn
            previous_entity: Primary entity from the previous turn
            previous_response_type: Response type from the previous turn
            session_context: Full session context dict

        Returns:
            FollowUpResolution with resolved intent, entity, and context
        """
        if not cls.is_followup_query(current_query):
            return FollowUpResolution(is_followup=False, original_query=current_query)

        if not previous_intent and not previous_entity:
            return FollowUpResolution(is_followup=False, original_query=current_query)

        # Detect scope modification
        scope_mod = None
        for pattern, scope in cls._SCOPE_MODIFIERS.items():
            if re.search(pattern, current_query):
                scope_mod = scope
                break

        # Determine if intent should change based on scope modifier
        resolved_intent = previous_intent
        if scope_mod == "financial_analysis" and previous_intent != "billing_ar":
            resolved_intent = "financial_analysis"
        elif scope_mod == "product_technical":
            resolved_intent = "product_fit"
        elif scope_mod == "risk_compliance":
            resolved_intent = "kyp_due_diligence"

        # Check for "full report" / "detail report" request
        wants_full = bool(
            re.search(
                r"(?i)(full|detail|complete|comprehensive)\s+(report|analysis|breakdown|assessment)",
                current_query,
            )
        )

        context = {}
        if session_context:
            context = {
                "companies": session_context.get("companies", []),
                "competitors": session_context.get("competitors", []),
                "regions": session_context.get("regions", []),
                "last_kyp_entity": session_context.get("last_kyp_entity"),
            }

        if wants_full and previous_response_type:
            context["wants_full_report"] = True
            context["expand_from"] = previous_response_type

        return FollowUpResolution(
            is_followup=True,
            resolved_intent=resolved_intent,
            resolved_entity=previous_entity,
            resolved_context=context,
            confidence=0.85 if previous_entity else 0.5,
            original_query=current_query,
        )


# =============================================================================
# Quality Metrics & Observability
# =============================================================================


@dataclass
class QualityEvent:
    """A quality-relevant event for observability."""

    event_type: str  # scope_violation, grounding_failure, schema_error, etc.
    severity: str  # INFO, WARNING, ERROR
    intent: str
    details: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class QualityMetrics:
    """
    Collects quality metrics for observability and continuous improvement.

    Emits structured log events that can be consumed by monitoring systems.
    """

    _events: List[QualityEvent] = []
    _max_events: int = 10000

    @classmethod
    def record(
        cls,
        event_type: str,
        severity: str,
        intent: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a quality event."""
        event = QualityEvent(
            event_type=event_type,
            severity=severity,
            intent=intent,
            details=details or {},
        )

        # Structured log for monitoring
        logger.log(
            logging.WARNING if severity == "ERROR" else logging.INFO,
            "quality_event",
            extra={
                "quality_event_type": event_type,
                "quality_severity": severity,
                "quality_intent": intent,
                "quality_details": details,
            },
        )

        # Bounded in-memory collection
        if len(cls._events) >= cls._max_events:
            cls._events = cls._events[-(cls._max_events // 2) :]
        cls._events.append(event)

    @classmethod
    def record_scope_violation(
        cls,
        intent: str,
        violations: List[Dict[str, str]],
    ) -> None:
        """Record scope discipline violations."""
        cls.record(
            event_type="scope_violation",
            severity="WARNING",
            intent=intent,
            details={"violations": violations, "count": len(violations)},
        )

    @classmethod
    def record_grounding_failure(
        cls,
        intent: str,
        checks: List[GroundingCheck],
    ) -> None:
        """Record grounding validation failures."""
        failed = [c for c in checks if not c.is_grounded]
        if failed:
            cls.record(
                event_type="grounding_failure",
                severity="WARNING",
                intent=intent,
                details={
                    "failed_claims": [
                        {"claim": c.claim, "issue": c.issue} for c in failed
                    ],
                    "total_claims": len(checks),
                    "failed_count": len(failed),
                },
            )

    @classmethod
    def record_schema_validation(
        cls,
        response_type: str,
        result: ValidationResult,
    ) -> None:
        """Record schema validation results."""
        if not result.is_valid:
            cls.record(
                event_type="schema_validation_error",
                severity="ERROR",
                intent=response_type,
                details={"errors": result.errors, "warnings": result.warnings},
            )
        elif result.warnings:
            cls.record(
                event_type="schema_validation_warning",
                severity="INFO",
                intent=response_type,
                details={"warnings": result.warnings},
            )

    @classmethod
    def record_source_tier_usage(
        cls,
        intent: str,
        sources: List[str],
    ) -> None:
        """Record which source tiers were used for a response."""
        tier_counts: Dict[str, int] = {}
        for s in sources:
            tier = get_source_tier(s)
            tier_name = tier.name
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1
        cls.record(
            event_type="source_tier_usage",
            severity="INFO",
            intent=intent,
            details={"tier_counts": tier_counts, "sources": sources},
        )

    @classmethod
    def get_recent_events(
        cls,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[QualityEvent]:
        """Get recent quality events, optionally filtered by type."""
        events = cls._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


# =============================================================================
# Production Routing Monitor
# =============================================================================


class RoutingMonitor:
    """
    Production monitoring for signal-based routing.

    Consumes signal_routing_live events from QualityMetrics and provides:
    1. Early warning metrics (low confidence, domain drift)
    2. Auto-QA sampling (1-5% of queries tagged for review)
    3. Regression detection (disagreement trends, accuracy proxies)
    4. Domain health dashboard (per-domain stats)
    5. Incident capture (last N failures for root cause analysis)

    All methods are classmethod — no instance state needed.
    Reads from QualityMetrics._events (shared bounded collection).
    """

    # Auto-QA sampling rate (1 in N queries gets full trace)
    QA_SAMPLE_RATE = 20  # 5% = 1 in 20

    # Alert thresholds
    LOW_CONFIDENCE_ALERT = 0.25  # Alert if >25% queries are LOW confidence
    FALLBACK_RATE_ALERT = 0.25  # Alert if >25% fallback
    DISAGREEMENT_ALERT = 0.03  # Alert if >3% signal vs keyword disagree
    HIGH_CONF_ERROR_ALERT = 0.01  # Alert if >1% HIGH confidence errors

    @classmethod
    def get_routing_stats(cls, window: int = 200) -> Dict[str, Any]:
        """
        Compute routing health metrics from recent events.

        Args:
            window: Number of recent events to analyze

        Returns:
            Dict with all monitoring metrics
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=window)
        if not events:
            return {"status": "no_data", "event_count": 0}

        total = len(events)
        details_list = [e.details for e in events]

        # ── Routing source distribution ────────────────────────────
        signal_count = sum(
            1 for d in details_list if d.get("routing_source") == "signal"
        )
        fallback_count = total - signal_count
        fallback_rate = fallback_count / total

        # ── Confidence distribution ────────────────────────────────
        bands = {"HIGH": 0, "MODERATE": 0, "LOW": 0}
        confidence_sum = 0.0
        for d in details_list:
            band = d.get("signal_confidence_band", "LOW")
            bands[band] = bands.get(band, 0) + 1
            confidence_sum += d.get("signal_confidence", 0.0)
        avg_confidence = confidence_sum / total

        low_rate = bands.get("LOW", 0) / total

        # ── Domain distribution ────────────────────────────────────
        domain_counts: Dict[str, int] = {}
        for d in details_list:
            intent = d.get("final_intent", "unknown")
            domain_counts[intent] = domain_counts.get(intent, 0) + 1

        # ── Disagreement rate ──────────────────────────────────────
        disagreements = sum(1 for d in details_list if not d.get("agreement", True))
        disagreement_rate = disagreements / total

        # ── Hard rule usage ────────────────────────────────────────
        hard_rules: Dict[str, int] = {}
        for d in details_list:
            rule = d.get("hard_rule_fired")
            if rule:
                hard_rules[rule] = hard_rules.get(rule, 0) + 1
        hard_rule_rate = sum(hard_rules.values()) / total if hard_rules else 0.0

        # ── Alerts ─────────────────────────────────────────────────
        alerts = []
        if low_rate > cls.LOW_CONFIDENCE_ALERT:
            alerts.append(
                f"LOW_CONFIDENCE_HIGH: {low_rate:.1%} > {cls.LOW_CONFIDENCE_ALERT:.0%}"
            )
        if fallback_rate > cls.FALLBACK_RATE_ALERT:
            alerts.append(
                f"FALLBACK_RATE_HIGH: {fallback_rate:.1%} > {cls.FALLBACK_RATE_ALERT:.0%}"
            )
        if disagreement_rate > cls.DISAGREEMENT_ALERT:
            alerts.append(
                f"DISAGREEMENT_HIGH: {disagreement_rate:.1%} > {cls.DISAGREEMENT_ALERT:.0%}"
            )

        return {
            "status": "healthy" if not alerts else "warning",
            "event_count": total,
            "routing_source": {
                "signal": signal_count,
                "fallback": fallback_count,
                "signal_rate": round(signal_count / total, 3),
                "fallback_rate": round(fallback_rate, 3),
            },
            "confidence": {
                "HIGH": bands.get("HIGH", 0),
                "MODERATE": bands.get("MODERATE", 0),
                "LOW": bands.get("LOW", 0),
                "average": round(avg_confidence, 3),
                "low_rate": round(low_rate, 3),
            },
            "domains": domain_counts,
            "disagreement_rate": round(disagreement_rate, 3),
            "hard_rules": hard_rules,
            "hard_rule_rate": round(hard_rule_rate, 3),
            "alerts": alerts,
        }

    @classmethod
    def get_domain_health(cls, window: int = 200) -> Dict[str, Dict[str, Any]]:
        """
        Per-domain routing health metrics.

        Returns:
            Dict mapping domain → health metrics
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=window)
        if not events:
            return {}

        domains: Dict[str, Dict[str, Any]] = {}
        for e in events:
            d = e.details
            intent = d.get("final_intent", "unknown")
            if intent not in domains:
                domains[intent] = {
                    "total": 0,
                    "signal_routed": 0,
                    "fallback_routed": 0,
                    "confidence_sum": 0.0,
                    "high_count": 0,
                    "moderate_count": 0,
                    "low_count": 0,
                    "disagreements": 0,
                }
            dm = domains[intent]
            dm["total"] += 1
            if d.get("routing_source") == "signal":
                dm["signal_routed"] += 1
            else:
                dm["fallback_routed"] += 1
            dm["confidence_sum"] += d.get("signal_confidence", 0)
            band = d.get("signal_confidence_band", "LOW")
            if band == "HIGH":
                dm["high_count"] += 1
            elif band == "MODERATE":
                dm["moderate_count"] += 1
            else:
                dm["low_count"] += 1
            if not d.get("agreement", True):
                dm["disagreements"] += 1

        # Compute rates
        for intent, dm in domains.items():
            t = dm["total"]
            dm["signal_rate"] = round(dm["signal_routed"] / t, 3) if t else 0
            dm["fallback_rate"] = round(dm["fallback_routed"] / t, 3) if t else 0
            dm["avg_confidence"] = round(dm["confidence_sum"] / t, 3) if t else 0
            dm["disagreement_rate"] = round(dm["disagreements"] / t, 3) if t else 0

        return domains

    @classmethod
    def should_sample_for_qa(cls, query_index: int) -> bool:
        """Deterministic QA sampling: returns True for ~5% of queries."""
        return (query_index % cls.QA_SAMPLE_RATE) == 0

    @classmethod
    def capture_qa_sample(
        cls,
        query: str,
        intent: str,
        routing_source: str,
        confidence: float,
        signals_snapshot: Dict[str, Any],
        response_type: str,
    ) -> None:
        """Log a full routing trace for QA review."""
        QualityMetrics.record(
            event_type="qa_sample",
            severity="INFO",
            intent=intent,
            details={
                "query": query[:200],
                "routing_source": routing_source,
                "confidence": confidence,
                "signals": signals_snapshot,
                "response_type": response_type,
                "tagged_for_review": True,
            },
        )

    @classmethod
    def check_regression(cls, window: int = 100) -> Dict[str, Any]:
        """
        Check for routing regressions by analyzing recent events.

        Returns dict with regression status and details.
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=window)
        if len(events) < 20:
            return {"status": "insufficient_data", "event_count": len(events)}

        total = len(events)
        details_list = [e.details for e in events]

        # Disagreement rate
        disagreements = sum(1 for d in details_list if not d.get("agreement", True))
        disagreement_rate = disagreements / total

        # HIGH-confidence cases that disagree with keyword (proxy for error)
        high_conf_disagree = sum(
            1
            for d in details_list
            if d.get("signal_confidence_band") == "HIGH"
            and not d.get("agreement", True)
        )
        high_conf_total = sum(
            1 for d in details_list if d.get("signal_confidence_band") == "HIGH"
        )
        high_conf_error_proxy = (
            high_conf_disagree / high_conf_total if high_conf_total > 0 else 0
        )

        alerts = []
        if disagreement_rate > cls.DISAGREEMENT_ALERT:
            alerts.append(
                f"REGRESSION: disagreement_rate={disagreement_rate:.1%} "
                f"> {cls.DISAGREEMENT_ALERT:.0%}"
            )
        if high_conf_error_proxy > cls.HIGH_CONF_ERROR_ALERT:
            alerts.append(
                f"HIGH_CONF_ERROR: {high_conf_error_proxy:.1%} "
                f"> {cls.HIGH_CONF_ERROR_ALERT:.0%}"
            )

        if alerts:
            for alert in alerts:
                logger.warning(f"[Routing Regression] {alert}")

        return {
            "status": "regression_detected" if alerts else "healthy",
            "event_count": total,
            "disagreement_rate": round(disagreement_rate, 3),
            "high_confidence_error_proxy": round(high_conf_error_proxy, 3),
            "alerts": alerts,
        }

    @classmethod
    def capture_incident(cls, reason: str) -> Dict[str, Any]:
        """
        Capture recent routing events for incident analysis.

        Called when rollback is triggered.
        Returns last 100 routing events with full details.
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=100)
        errors = QualityMetrics.get_recent_events("signal_routing_error", limit=20)

        incident = {
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
            "recent_routing_events": len(events),
            "recent_errors": len(errors),
            "failure_classification": {
                "signal_failures": len(errors),
                "high_conf_disagreements": sum(
                    1
                    for e in events
                    if e.details.get("signal_confidence_band") == "HIGH"
                    and not e.details.get("agreement", True)
                ),
                "fallback_spikes": sum(
                    1 for e in events if e.details.get("fallback_triggered", False)
                ),
            },
            "last_10_events": [
                {
                    "query": e.details.get("query", "")[:80],
                    "signal_intent": e.details.get("signal_intent"),
                    "keyword_intent": e.details.get("keyword_intent"),
                    "final_intent": e.details.get("final_intent"),
                    "confidence": e.details.get("signal_confidence"),
                    "routing_source": e.details.get("routing_source"),
                }
                for e in events[-10:]
            ],
        }

        # Log incident
        QualityMetrics.record(
            event_type="routing_incident",
            severity="ERROR",
            intent="system",
            details=incident,
        )

        return incident

    @classmethod
    def get_compound_stats(cls, window: int = 200) -> Dict[str, Any]:
        """
        Compound query monitoring dashboard.

        Tracks all metrics required for phased activation:
        - detection rate, execution rate, success rate
        - parallel vs sequential ratio
        - partial failure rate
        - average latency
        """
        detected = QualityMetrics.get_recent_events(
            "compound_query_detected", limit=window
        )
        executed = QualityMetrics.get_recent_events(
            "compound_query_execution", limit=window
        )
        fallbacks = QualityMetrics.get_recent_events("compound_fallback", limit=window)
        all_routing = QualityMetrics.get_recent_events(
            "signal_routing_live", limit=window
        )

        total_queries = len(all_routing) or 1
        total_detected = len(detected)
        total_executed = len(executed)
        total_fallbacks = len(fallbacks)

        # Success/failure from executed
        successful = sum(
            1 for e in executed if not e.details.get("partial_success", False)
        )
        partial = sum(1 for e in executed if e.details.get("partial_success", False))

        # Parallel vs sequential
        parallel = sum(
            1 for e in executed if e.details.get("execution_order") == "parallel"
        )
        sequential = total_executed - parallel

        # Latency
        latencies = [e.details.get("total_time_ms", 0) for e in executed]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Sub-intent counts
        sub_counts = [e.details.get("sub_intent_count", 0) for e in executed]
        avg_subs = sum(sub_counts) / len(sub_counts) if sub_counts else 0

        # Rollback condition checks
        success_rate = successful / total_executed if total_executed > 0 else 1.0
        partial_rate = partial / total_executed if total_executed > 0 else 0.0
        fallback_rate = total_fallbacks / max(total_detected, 1)

        alerts = []
        if total_executed >= 10 and success_rate < 0.90:
            alerts.append(f"COMPOUND_SUCCESS_LOW: {success_rate:.0%} < 90%")
        if total_executed >= 10 and partial_rate > 0.20:
            alerts.append(f"COMPOUND_PARTIAL_HIGH: {partial_rate:.0%} > 20%")
        if avg_latency > 30000:
            alerts.append(f"COMPOUND_LATENCY_HIGH: {avg_latency:.0f}ms > 30000ms")

        return {
            "status": "healthy" if not alerts else "warning",
            "compound_query_rate": round(total_detected / total_queries, 3),
            "detection_count": total_detected,
            "execution_count": total_executed,
            "success_rate": round(success_rate, 3),
            "partial_failure_rate": round(partial_rate, 3),
            "fallback_count": total_fallbacks,
            "parallel_count": parallel,
            "sequential_count": sequential,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_sub_intents": round(avg_subs, 2),
            "alerts": alerts,
        }


# =============================================================================
# Insufficient Evidence Response Builder
# =============================================================================


class InsufficientEvidenceBuilder:
    """
    Builds structured responses when evidence is insufficient for a claim.

    Instead of hallucinating, the system should clearly communicate
    what it knows, what it doesn't, and where to look.
    """

    @classmethod
    def build_partial_response(
        cls,
        intent: str,
        available_data: Dict[str, Any],
        missing_areas: List[str],
        sources_used: List[str],
    ) -> str:
        """
        Build a response that clearly separates known data from gaps.

        Args:
            intent: The query intent
            available_data: Dict of what data IS available
            missing_areas: List of areas where data is insufficient
            sources_used: Sources that were queried

        Returns:
            Formatted response text with clear evidence boundaries
        """
        lines = []

        # What we found
        if available_data:
            lines.append("**Based on available data:**\n")
            for key, value in available_data.items():
                if isinstance(value, str) and value.strip():
                    lines.append(f"- **{key}**: {value}")
                elif isinstance(value, (int, float)):
                    lines.append(f"- **{key}**: {value}")

        # What we couldn't find
        if missing_areas:
            lines.append("\n**Data not available from our sources:**\n")
            for area in missing_areas:
                lines.append(f"- {area}")

        # Sources checked
        if sources_used:
            tier_labels = {
                SourceTier.TIER_1_INTERNAL_STRUCTURED: "Internal Systems",
                SourceTier.TIER_2_INTERNAL_SEMANTIC: "Intelligence Database",
                SourceTier.TIER_3_EXTERNAL_TRUSTED: "External Trusted Sources",
                SourceTier.TIER_4_EXTERNAL_BROAD: "Web Search",
            }
            lines.append("\n**Sources checked:**\n")
            for source in sources_used:
                tier = get_source_tier(source)
                label = tier_labels.get(tier, "Other")
                lines.append(f"- {source} ({label})")

        return "\n".join(lines)


# =============================================================================
# Enforcement Severity
# =============================================================================


class EnforcementSeverity(str, Enum):
    """Severity levels that determine enforcement action."""

    LOW = "low"
    """Log only. No modification to response."""

    MEDIUM = "medium"
    """Annotate: add disclaimers to unverified claims."""

    HIGH = "high"
    """Modify: strip or replace problematic sections."""

    CRITICAL = "critical"
    """Block: replace entire section with 'data not available'."""


# =============================================================================
# Enforcement Result
# =============================================================================


@dataclass
class EnforcementResult:
    """Result of enforcing quality rules on a response."""

    original_text: str
    enforced_text: str
    was_modified: bool
    actions_taken: List[Dict[str, str]]
    scope_violations_removed: int = 0
    claims_annotated: int = 0
    claims_replaced: int = 0

    @property
    def summary(self) -> str:
        parts = []
        if self.scope_violations_removed:
            parts.append(f"{self.scope_violations_removed} scope violations removed")
        if self.claims_annotated:
            parts.append(f"{self.claims_annotated} claims annotated")
        if self.claims_replaced:
            parts.append(f"{self.claims_replaced} claims replaced")
        return "; ".join(parts) if parts else "no modifications"


# =============================================================================
# Response Enforcer
# =============================================================================


class ResponseEnforcer:
    """
    Active enforcement of response quality rules.

    Upgrades passive logging to controlled modification:
    - Strips out-of-scope sections (recommendations, action items, billing in product queries)
    - Annotates ungrounded numeric claims
    - Replaces unverified technical specs with disclaimers
    - Tracks all modifications for observability

    Enforcement is calibrated by severity thresholds — not all violations
    are treated equally. The goal is precision, not aggression.
    """

    # ── Section heading patterns for stripping ──────────────────────
    # These match markdown-style headings that introduce out-of-scope content.
    # We strip the heading AND its content until the next heading of equal/higher level.
    _SECTION_HEADING_PATTERNS: Dict[ResponseSection, re.Pattern] = {
        ResponseSection.RECOMMENDATIONS: re.compile(
            r"(?m)^#{1,4}\s*(?:Recommendation|Suggested\s+Approach|Our\s+Recommendation)s?\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.ACTION_ITEMS: re.compile(
            r"(?m)^#{1,4}\s*(?:(?:RRPS\s+)?Action\s+Items?|Next\s+Steps?|Recommended\s+Actions?|Follow[- ]?up\s+Actions?|Opportunities|Threats)\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.RRPS_IMPLICATIONS: re.compile(
            r"(?m)^#{1,4}\s*(?:RRPS\s+Implications?|Implications?\s+for\s+(?:RRPS|Rolls[- ]Royce|MTU|Us)|What\s+This\s+Means|Emerging\s+Trends?|Competitive\s+Landscape)\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.SALES_STRATEGY: re.compile(
            r"(?m)^#{1,4}\s*(?:Sales\s+Strategy|Go[- ]to[- ]Market|Strategic\s+Approach|Selling\s+Points?)\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.BILLING_STATUS: re.compile(
            r"(?m)^#{1,4}\s*(?:Billing\s+(?:Status|Items?|Overview)|Invoice\s+Status|AR\s+(?:Aging|Status)|Accounts?\s+Receivable)\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.AGING_ANALYSIS: re.compile(
            r"(?m)^#{1,4}\s*(?:Aging\s+(?:Analysis|Buckets?|Report)|Overdue\s+(?:Analysis|Summary))\s*\n",
            re.IGNORECASE,
        ),
        ResponseSection.PRODUCT_SPECS: re.compile(
            r"(?m)^#{1,4}\s*(?:Product\s+Specifications?|Engine\s+Specs?|Technical\s+Specifications?)\s*\n",
            re.IGNORECASE,
        ),
    }

    # Pattern to find the NEXT heading at same or higher level (to bound section removal)
    _NEXT_HEADING = re.compile(r"(?m)^#{1,4}\s+\S")

    @classmethod
    def enforce(
        cls,
        response_text: str,
        intent: str,
        sources: List[str],
        retrieved_evidence: Optional[str] = None,
    ) -> EnforcementResult:
        """
        Apply active enforcement to a synthesized response.

        Pipeline:
        1. Detect and strip out-of-scope SECTIONS (headings + content)
        2. Detect and annotate out-of-scope INLINE content
        3. Detect and handle ungrounded claims

        Args:
            response_text: The LLM-synthesized response text
            intent: The query intent value
            sources: List of source names used
            retrieved_evidence: Raw retrieved text from tools

        Returns:
            EnforcementResult with modified text and action log
        """
        text = response_text
        actions: List[Dict[str, str]] = []
        scope_removed = 0
        claims_annotated = 0
        claims_replaced = 0

        # ── Phase 1: Strip out-of-scope sections ────────────────────
        text, phase1_actions, phase1_count = cls._enforce_scope(text, intent)
        actions.extend(phase1_actions)
        scope_removed += phase1_count

        # ── Phase 2: Strip inline scope violations ──────────────────
        text, phase2_actions, phase2_count = cls._enforce_inline_scope(text, intent)
        actions.extend(phase2_actions)
        scope_removed += phase2_count

        # ── Phase 3: Enforce grounding ──────────────────────────────
        text, phase3_actions, annotated, replaced = cls._enforce_grounding(
            text, intent, sources, retrieved_evidence
        )
        actions.extend(phase3_actions)
        claims_annotated += annotated
        claims_replaced += replaced

        was_modified = text != response_text

        if was_modified:
            QualityMetrics.record(
                event_type="enforcement_applied",
                severity="INFO",
                intent=intent,
                details={
                    "scope_removed": scope_removed,
                    "claims_annotated": claims_annotated,
                    "claims_replaced": claims_replaced,
                    "actions": [a["action"] for a in actions],
                },
            )

        return EnforcementResult(
            original_text=response_text,
            enforced_text=text,
            was_modified=was_modified,
            actions_taken=actions,
            scope_violations_removed=scope_removed,
            claims_annotated=claims_annotated,
            claims_replaced=claims_replaced,
        )

    @classmethod
    def _enforce_scope(
        cls,
        text: str,
        intent: str,
    ) -> tuple[str, List[Dict[str, str]], int]:
        """
        Strip headed sections that are forbidden for this intent.

        Finds markdown headings (## Recommendations, ## Action Items, etc.)
        and removes the heading plus all content until the next heading.

        Returns: (modified_text, actions, violation_count)
        """
        allowed = ScopeEnforcer.get_allowed_sections(intent)
        forbidden_sections = set(ResponseSection) - allowed
        actions = []
        count = 0

        for section in forbidden_sections:
            pattern = cls._SECTION_HEADING_PATTERNS.get(section)
            if not pattern:
                continue

            match = pattern.search(text)
            if not match:
                continue

            # Find where this section ends (next heading or end of text)
            section_start = match.start()
            remaining = text[match.end() :]
            next_heading = cls._NEXT_HEADING.search(remaining)

            if next_heading:
                section_end = match.end() + next_heading.start()
            else:
                section_end = len(text)

            removed_content = text[section_start:section_end].strip()
            # Only strip if there's meaningful content (not just whitespace)
            if len(removed_content) > 10:
                text = text[:section_start] + text[section_end:]
                count += 1
                actions.append(
                    {
                        "action": "scope_section_removed",
                        "severity": EnforcementSeverity.HIGH.value,
                        "section": section.value,
                        "intent": intent,
                        "removed_chars": len(removed_content),
                    }
                )
                logger.info(
                    f"ENFORCEMENT: Removed '{section.value}' section "
                    f"({len(removed_content)} chars) from {intent} response"
                )

        return text, actions, count

    @classmethod
    def _enforce_inline_scope(
        cls,
        text: str,
        intent: str,
    ) -> tuple[str, List[Dict[str, str]], int]:
        """
        Remove inline out-of-scope sentences (not under a heading).

        Targets specific high-confidence patterns:
        - "We recommend..." / "I recommend..." / "RRPS should..."
        - "Action items:" followed by a list
        - "Implications for RRPS:" followed by content

        Only fires for EXPLICIT_REQUEST_ONLY sections when they appear inline.

        Returns: (modified_text, actions, violation_count)
        """
        allowed = ScopeEnforcer.get_allowed_sections(intent)
        actions = []
        count = 0

        # Only strip inline content for EXPLICIT_REQUEST_ONLY sections
        if ResponseSection.RECOMMENDATIONS not in allowed:
            # Remove sentences starting with recommendation verbs
            reco_pattern = re.compile(
                r"(?m)^[•\-*]?\s*(?:We|I|RRPS)\s+(?:recommend|suggest|advise|should)\b[^\n]*\n?",
                re.IGNORECASE,
            )
            matches = reco_pattern.findall(text)
            if matches:
                text = reco_pattern.sub("", text)
                count += len(matches)
                actions.append(
                    {
                        "action": "inline_recommendation_removed",
                        "severity": EnforcementSeverity.MEDIUM.value,
                        "count": str(len(matches)),
                        "intent": intent,
                    }
                )

        if ResponseSection.ACTION_ITEMS not in allowed:
            # Remove "Next steps:" or "Action items:" with following bullets
            action_pattern = re.compile(
                r"(?m)(?:^|\n)\**(?:Next\s+steps?|Action\s+items?)\s*:?\**\s*\n"
                r"(?:[•\-*]\s+[^\n]+\n?)*",
                re.IGNORECASE,
            )
            matches = action_pattern.findall(text)
            if matches:
                text = action_pattern.sub("\n", text)
                count += len(matches)
                actions.append(
                    {
                        "action": "inline_action_items_removed",
                        "severity": EnforcementSeverity.MEDIUM.value,
                        "count": str(len(matches)),
                        "intent": intent,
                    }
                )

        return text, actions, count

    @classmethod
    def _enforce_grounding(
        cls,
        text: str,
        intent: str,
        sources: List[str],
        retrieved_evidence: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, str]], int, int]:
        """
        Enforce grounding rules on factual claims.

        Severity model:
        - Technical specs (kW, RPM, bore×stroke) without Tier 1-2 source
          → CRITICAL: replace with "[specifications not verified from internal sources]"
        - Financial figures without evidence
          → MEDIUM: annotate with "(unverified)"
        - General numeric claims without evidence
          → LOW: log only (too many false positives if we modify)

        Returns: (modified_text, actions, annotated_count, replaced_count)
        """
        actions = []
        annotated = 0
        replaced = 0

        # Get grounding checks
        checks = GroundingValidator.check_grounding(text, sources, retrieved_evidence)
        ungrounded = [c for c in checks if not c.is_grounded]

        if not ungrounded:
            return text, actions, 0, 0

        for check in ungrounded:
            severity = cls._classify_grounding_severity(check, intent)

            if severity == EnforcementSeverity.CRITICAL:
                # Replace ungrounded technical specs with disclaimer
                replacement = "[data not verified from internal sources]"
                if check.claim in text:
                    text = text.replace(check.claim, replacement, 1)
                    replaced += 1
                    actions.append(
                        {
                            "action": "ungrounded_spec_replaced",
                            "severity": severity.value,
                            "original_claim": check.claim,
                            "replacement": replacement,
                            "reason": check.issue
                            or "Technical spec without Tier 1-2 source",
                        }
                    )
                    logger.info(
                        f"ENFORCEMENT: Replaced ungrounded spec '{check.claim}' "
                        f"in {intent} response"
                    )

            elif severity == EnforcementSeverity.MEDIUM:
                # Annotate financial claims with "(unverified)"
                if check.claim in text:
                    annotated_claim = f"{check.claim} (unverified)"
                    text = text.replace(check.claim, annotated_claim, 1)
                    annotated += 1
                    actions.append(
                        {
                            "action": "ungrounded_claim_annotated",
                            "severity": severity.value,
                            "claim": check.claim,
                            "reason": check.issue or "Claim not found in evidence",
                        }
                    )

            else:
                # LOW severity — log only
                QualityMetrics.record(
                    event_type="ungrounded_claim_low",
                    severity="INFO",
                    intent=intent,
                    details={"claim": check.claim, "issue": check.issue},
                )

        return text, actions, annotated, replaced

    @classmethod
    def _classify_grounding_severity(
        cls,
        check: GroundingCheck,
        intent: str,
    ) -> EnforcementSeverity:
        """
        Classify the enforcement severity for an ungrounded claim.

        Rules:
        - Technical specs (kW, RPM, bore, displacement) in product/competitor intents
          → CRITICAL (these are the specs users make business decisions on)
        - Financial figures (USD, EUR, revenue, market cap) without evidence
          → MEDIUM (annotate but don't remove — could be from context)
        - General percentages, dates, counts
          → LOW (too many legitimate uses to enforce aggressively)
        """
        claim = check.claim

        # CRITICAL: Technical specs without verified source
        # These are the claims that cause real business harm if wrong
        is_technical_spec = bool(
            re.search(
                r"\d+\s*k[wW]|\d+\s*(?:rpm|RPM|hp|HP)|bore|stroke|displacement|sfoc|SFOC|fuel\s+consumption",
                claim,
                re.IGNORECASE,
            )
        )
        is_spec_intent = intent in (
            "product_fit",
            "product_info",
            "competitor_intel",
        )
        if is_technical_spec and is_spec_intent:
            # Only CRITICAL if the source tier is inadequate
            if (
                check.source_tier is not None
                and check.source_tier.value > SourceTier.TIER_2_INTERNAL_SEMANTIC.value
            ):
                return EnforcementSeverity.CRITICAL
            if check.source_tier is None:
                return EnforcementSeverity.CRITICAL

        # MEDIUM: Financial figures without evidence
        is_financial = bool(
            re.search(
                r"(?:USD|EUR|SGD|AUD|\$)\s*[\d,.]+|revenue|market\s+cap|EBITDA",
                claim,
                re.IGNORECASE,
            )
        )
        if is_financial and not check.is_grounded:
            return EnforcementSeverity.MEDIUM

        # LOW: Everything else
        return EnforcementSeverity.LOW

    @classmethod
    def cleanup_whitespace(cls, text: str) -> str:
        """Clean up whitespace artifacts from section removal."""
        # Collapse 3+ consecutive newlines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing whitespace on lines
        text = re.sub(r" +$", "", text, flags=re.MULTILINE)
        return text.strip()


# =============================================================================
# Continuous Intelligence Loop
# =============================================================================


class ContinuousIntelligence:
    """
    Continuous improvement loop for signal-based routing.

    Provides:
    1. QA feedback collection and storage
    2. Confidence calibration metrics
    3. Weak pattern detection
    4. Calibration suggestion engine
    5. Periodic review report generation

    All analysis is read-only — suggestions require manual approval.
    No auto-application of changes. Human-in-the-loop required.
    """

    # ── QA feedback storage (bounded in-memory) ────────────────────
    _qa_feedback: List[Dict[str, Any]] = []
    _max_feedback: int = 5000

    @classmethod
    def record_qa_feedback(
        cls,
        query: str,
        signal_intent: str,
        keyword_intent: str,
        final_intent: str,
        verdict: str,
        confidence: float,
        notes: str = "",
    ) -> None:
        """
        Record QA reviewer feedback on a routing decision.

        Args:
            query: The original query text
            signal_intent: What signal router chose
            keyword_intent: What keyword stabilizer would choose
            final_intent: What was actually used
            verdict: 'correct', 'incorrect', or 'ambiguous'
            confidence: Signal confidence score
            notes: Optional reviewer notes
        """
        feedback = {
            "query": query[:300],
            "signal_intent": signal_intent,
            "keyword_intent": keyword_intent,
            "final_intent": final_intent,
            "verdict": verdict,
            "confidence": confidence,
            "confidence_band": (
                "HIGH"
                if confidence >= 0.75
                else "MODERATE"
                if confidence >= 0.50
                else "LOW"
            ),
            "timestamp": datetime.now(UTC).isoformat(),
            "notes": notes,
        }

        if len(cls._qa_feedback) >= cls._max_feedback:
            cls._qa_feedback = cls._qa_feedback[-(cls._max_feedback // 2) :]
        cls._qa_feedback.append(feedback)

        QualityMetrics.record(
            event_type="qa_feedback",
            severity="INFO",
            intent=final_intent,
            details=feedback,
        )

    @classmethod
    def get_confidence_calibration(cls, window: int = 500) -> Dict[str, Any]:
        """
        Compute accuracy per confidence band from QA feedback.

        Returns calibration data showing whether confidence scores
        are meaningful (HIGH should be more accurate than LOW).
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=window)
        feedback = cls._qa_feedback[-window:] if cls._qa_feedback else []

        # From feedback (ground truth when available)
        bands = {
            "HIGH": {"total": 0, "correct": 0},
            "MODERATE": {"total": 0, "correct": 0},
            "LOW": {"total": 0, "correct": 0},
        }
        for fb in feedback:
            band = fb.get("confidence_band", "LOW")
            if band in bands:
                bands[band]["total"] += 1
                if fb.get("verdict") == "correct":
                    bands[band]["correct"] += 1

        # Compute accuracy per band
        calibration = {}
        for band, counts in bands.items():
            total = counts["total"]
            correct = counts["correct"]
            calibration[band] = {
                "total": total,
                "correct": correct,
                "accuracy": round(correct / total, 3) if total > 0 else None,
            }

        # From routing events (proxy: agreement as accuracy)
        event_bands = {
            "HIGH": {"total": 0, "agree": 0},
            "MODERATE": {"total": 0, "agree": 0},
            "LOW": {"total": 0, "agree": 0},
        }
        for e in events:
            d = e.details
            band = d.get("signal_confidence_band", "LOW")
            if band in event_bands:
                event_bands[band]["total"] += 1
                if d.get("agreement", True):
                    event_bands[band]["agree"] += 1

        proxy_calibration = {}
        for band, counts in event_bands.items():
            total = counts["total"]
            proxy_calibration[band] = {
                "total": total,
                "agreement_rate": round(counts["agree"] / total, 3)
                if total > 0
                else None,
            }

        return {
            "from_qa_feedback": calibration,
            "from_agreement_proxy": proxy_calibration,
            "total_feedback": len(feedback),
            "total_events": len(events),
        }

    @classmethod
    def detect_weak_patterns(cls, window: int = 300) -> Dict[str, Any]:
        """
        Automatically detect weak routing patterns.

        Checks:
        1. Repeated fallback triggers (same query patterns)
        2. Domains with rising disagreement
        3. Low-confidence clusters (queries that consistently score poorly)
        """
        events = QualityMetrics.get_recent_events("signal_routing_live", limit=window)
        fallback_events = QualityMetrics.get_recent_events(
            "fallback_usage", limit=window
        )

        patterns = {
            "repeated_fallbacks": [],
            "weak_domains": [],
            "low_confidence_clusters": [],
        }

        if not events:
            return patterns

        # ── Repeated fallback triggers ─────────────────────────────
        # Group fallback queries by keyword_intent to find patterns
        fallback_intents: Dict[str, int] = {}
        for e in fallback_events:
            d = e.details
            intent = d.get("keyword_intent", "unknown")
            fallback_intents[intent] = fallback_intents.get(intent, 0) + 1
        # Flag intents that trigger fallback more than 10% of time
        total = len(events) or 1
        for intent, count in fallback_intents.items():
            rate = count / total
            if rate > 0.05 and count >= 3:
                patterns["repeated_fallbacks"].append(
                    {
                        "intent": intent,
                        "count": count,
                        "rate": round(rate, 3),
                    }
                )

        # ── Domains with rising disagreement ───────────────────────
        domain_stats: Dict[str, Dict[str, int]] = {}
        for e in events:
            d = e.details
            domain = d.get("final_intent", "unknown")
            if domain not in domain_stats:
                domain_stats[domain] = {"total": 0, "disagree": 0}
            domain_stats[domain]["total"] += 1
            if not d.get("agreement", True):
                domain_stats[domain]["disagree"] += 1

        for domain, stats in domain_stats.items():
            if stats["total"] >= 5:
                rate = stats["disagree"] / stats["total"]
                if rate > 0.10:
                    patterns["weak_domains"].append(
                        {
                            "domain": domain,
                            "disagreement_rate": round(rate, 3),
                            "total": stats["total"],
                            "disagree": stats["disagree"],
                        }
                    )

        # ── Low-confidence clusters ────────────────────────────────
        low_conf_queries = []
        for e in events:
            d = e.details
            if d.get("signal_confidence", 1.0) < 0.50:
                low_conf_queries.append(
                    {
                        "intent": d.get("final_intent"),
                        "confidence": d.get("signal_confidence"),
                    }
                )

        if len(low_conf_queries) >= 3:
            # Group by intent
            lc_by_intent: Dict[str, int] = {}
            for lc in low_conf_queries:
                i = lc.get("intent", "unknown")
                lc_by_intent[i] = lc_by_intent.get(i, 0) + 1
            for intent, count in lc_by_intent.items():
                if count >= 3:
                    patterns["low_confidence_clusters"].append(
                        {
                            "intent": intent,
                            "count": count,
                            "pct_of_total": round(count / total, 3),
                        }
                    )

        return patterns

    @classmethod
    def suggest_calibration(cls, window: int = 300) -> Dict[str, Any]:
        """
        Generate calibration suggestions from QA feedback and metrics.

        IMPORTANT: Suggestions are advisory only. They require manual
        review and approval before any changes are applied.
        """
        patterns = cls.detect_weak_patterns(window)
        calibration = cls.get_confidence_calibration(window)
        feedback = cls._qa_feedback[-window:] if cls._qa_feedback else []

        suggestions = []

        # ── From weak patterns ─────────────────────────────────────
        for fb in patterns.get("repeated_fallbacks", []):
            suggestions.append(
                {
                    "type": "fallback_reduction",
                    "priority": "MEDIUM",
                    "description": (
                        f"Domain '{fb['intent']}' triggers fallback {fb['rate']:.0%} of time. "
                        f"Consider adding concept signals or adjusting domain affinity."
                    ),
                    "data": fb,
                }
            )

        for wd in patterns.get("weak_domains", []):
            suggestions.append(
                {
                    "type": "domain_calibration",
                    "priority": "HIGH",
                    "description": (
                        f"Domain '{wd['domain']}' has {wd['disagreement_rate']:.0%} "
                        f"disagreement rate ({wd['disagree']}/{wd['total']} queries). "
                        f"Review scoring weights or concept patterns."
                    ),
                    "data": wd,
                }
            )

        for lc in patterns.get("low_confidence_clusters", []):
            suggestions.append(
                {
                    "type": "concept_gap",
                    "priority": "MEDIUM",
                    "description": (
                        f"Domain '{lc['intent']}' has {lc['count']} low-confidence queries. "
                        f"May need new concept patterns or entity signals."
                    ),
                    "data": lc,
                }
            )

        # ── From QA feedback ───────────────────────────────────────
        incorrect = [f for f in feedback if f.get("verdict") == "incorrect"]
        if len(incorrect) >= 3:
            # Group by signal_intent to find systematic errors
            error_intents: Dict[str, int] = {}
            for f in incorrect:
                i = f.get("signal_intent", "unknown")
                error_intents[i] = error_intents.get(i, 0) + 1
            for intent, count in error_intents.items():
                if count >= 2:
                    suggestions.append(
                        {
                            "type": "routing_error",
                            "priority": "HIGH",
                            "description": (
                                f"Signal routes to '{intent}' incorrectly in {count} QA samples. "
                                f"Review scoring for this domain."
                            ),
                            "data": {"intent": intent, "error_count": count},
                        }
                    )

        # ── From confidence calibration ────────────────────────────
        qa_cal = calibration.get("from_qa_feedback", {})
        high_cal = qa_cal.get("HIGH", {})
        if high_cal.get("total", 0) >= 5 and high_cal.get("accuracy", 1.0) is not None:
            if high_cal["accuracy"] < 0.95:
                suggestions.append(
                    {
                        "type": "confidence_threshold",
                        "priority": "HIGH",
                        "description": (
                            f"HIGH confidence accuracy is only {high_cal['accuracy']:.0%} "
                            f"({high_cal['correct']}/{high_cal['total']}). "
                            f"Consider raising HIGH threshold from 0.75 to 0.80."
                        ),
                        "data": high_cal,
                    }
                )

        return {
            "suggestions": suggestions,
            "suggestion_count": len(suggestions),
            "high_priority": sum(1 for s in suggestions if s["priority"] == "HIGH"),
            "requires_manual_approval": True,
            "auto_apply": False,
        }

    @classmethod
    def generate_review_report(cls, window: int = 500) -> Dict[str, Any]:
        """
        Generate a periodic review report for human assessment.

        Combines all metrics, patterns, and suggestions into a single
        report suitable for weekly review.
        """
        stats = RoutingMonitor.get_routing_stats(window)
        domain_health = RoutingMonitor.get_domain_health(window)
        regression = RoutingMonitor.check_regression(window)
        calibration = cls.get_confidence_calibration(window)
        patterns = cls.detect_weak_patterns(window)
        suggestions = cls.suggest_calibration(window)

        feedback = cls._qa_feedback[-window:]
        feedback_summary = {
            "total": len(feedback),
            "correct": sum(1 for f in feedback if f.get("verdict") == "correct"),
            "incorrect": sum(1 for f in feedback if f.get("verdict") == "incorrect"),
            "ambiguous": sum(1 for f in feedback if f.get("verdict") == "ambiguous"),
        }

        return {
            "report_type": "routing_review",
            "generated_at": datetime.now(UTC).isoformat(),
            "window_size": window,
            "summary": {
                "overall_status": stats.get("status", "unknown"),
                "signal_rate": stats.get("routing_source", {}).get("signal_rate"),
                "fallback_rate": stats.get("routing_source", {}).get("fallback_rate"),
                "avg_confidence": stats.get("confidence", {}).get("average"),
                "disagreement_rate": stats.get("disagreement_rate"),
                "regression_status": regression.get("status"),
            },
            "domain_health": domain_health,
            "confidence_calibration": calibration,
            "weak_patterns": patterns,
            "qa_feedback_summary": feedback_summary,
            "suggestions": suggestions,
            "alerts": stats.get("alerts", []),
        }

    @classmethod
    def validate_update_safety(
        cls,
        update_description: str,
        golden_results_before: Dict[str, Any],
        golden_results_after: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate a proposed calibration update against golden dataset.

        Called BEFORE deploying any scoring/rule change.
        Compares before vs after metrics to ensure no regression.

        Args:
            update_description: What is being changed
            golden_results_before: Evaluation results before change
            golden_results_after: Evaluation results after change

        Returns:
            Safety assessment with go/no-go recommendation
        """
        before_acc = golden_results_before.get("signal_accuracy", 0)
        after_acc = golden_results_after.get("signal_accuracy", 0)
        before_reg = golden_results_before.get("disagreements", {}).get(
            "current_correct_signal_wrong", 0
        )
        after_reg = golden_results_after.get("disagreements", {}).get(
            "current_correct_signal_wrong", 0
        )
        before_total = golden_results_before.get("total_queries", 1)
        after_total = golden_results_after.get("total_queries", 1)

        checks = {
            "accuracy_improved": after_acc >= before_acc,
            "no_new_regressions": after_reg <= before_reg,
            "accuracy_above_93": after_acc >= 0.93,
            "regression_below_2pct": (after_reg / after_total) <= 0.02
            if after_total > 0
            else True,
        }

        all_pass = all(checks.values())

        result = {
            "update_description": update_description,
            "recommendation": "GO" if all_pass else "NO-GO",
            "checks": checks,
            "before": {"accuracy": before_acc, "regressions": before_reg},
            "after": {"accuracy": after_acc, "regressions": after_reg},
            "requires_manual_approval": True,
        }

        QualityMetrics.record(
            event_type="update_validation",
            severity="INFO" if all_pass else "WARNING",
            intent="system",
            details=result,
        )

        return result
