"""
Signal Extractor

Extracts routing signals from ParsedQuery + session context.
All signals are derived from EXISTING data — no new API calls.

Signal categories:
- Entity signals: from ParsedQuery entities + session context
- Question-type signals: from query structure (heuristic patterns)
- Context signals: from ConversationSession state
- LLM signals: from ParsedQuery LLM outputs (already computed)
"""

import logging
import re
from typing import Any, Dict, FrozenSet, Optional

from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.routing_signals import SignalSnapshot

logger = logging.getLogger(__name__)


# =============================================================================
# Known entity registries (static — used for entity type classification)
# =============================================================================

# Known competitors (normalized to lowercase for matching)
_KNOWN_COMPETITORS: FrozenSet[str] = frozenset(
    s.lower()
    for s in [
        "Caterpillar",
        "CAT",
        "MaK",
        "Cummins",
        "MAN Energy Solutions",
        "MAN",
        "Wartsila",
        "Wärtsilä",
        "HiMSEN",
        "HD Hyundai",
        "Hyundai",
        "Daihatsu",
        "Yanmar",
        "ABC",
        "Anglo Belgian Corporation",
        "Volvo Penta",
        "Niigata",
    ]
)

# Product name patterns (MTU/Bergen model references)
_PRODUCT_PATTERN = re.compile(
    r"\b(?:mtu|bergen)\s+\d|"
    r"\b(?:series\s+\d{3,4}|[0-9]{1,2}v\s*\d{3,4})\b|"
    r"\bb3[25][:.]?[34][03]\b",
    re.IGNORECASE,
)

# =============================================================================
# Question-type heuristic patterns
# =============================================================================
# These match question STRUCTURE, not domain vocabulary.
# "What is the payment status?" and "What is the engine status?"
# both match seeks_data — domain is determined by entity+context, not question form.

_SEEKS_DATA_PATTERNS = re.compile(
    r"(?i)(?:"
    r"^(?:what|how\s+much|how\s+many|show|list|get|display|view)\s|"
    r"\b(?:status|history|record|amount|balance|total|count|details?|overview)\b|"
    r"\b(?:do\s+they|is\s+there|are\s+there|has\s+(?:it|the|this))\b|"
    r"\b(?:how\s+(?:is|are|was|were|does))\b"
    r")"
)

_SEEKS_SPECS_PATTERNS = re.compile(
    r"(?i)(?:"
    r"\b(?:specs?|specifications?|power\s+(?:rating|output|range))\b|"
    r"\b(?:fuel\s+consumption|bore|stroke|displacement|RPM|dimensions?)\b|"
    r"\b(?:compare\s+(?:engine|mtu|bergen)|engine\s+comparison)\b|"
    r"\b(?:ISO\s+8528|duty\s+(?:class|rating))\b|"
    r"\b(?:technical\s+(?:data|details?|parameters?))\b"
    r")"
)

_SEEKS_NEWS_PATTERNS = re.compile(
    r"(?i)(?:"
    r"\b(?:latest|recent|new|current|update|development|announcement)\b|"
    r"\b(?:what's\s+(?:new|happening)|news|trend)\b|"
    r"\b(?:what\s+(?:is|are)\s+(?:the\s+)?(?:latest|recent|new))\b"
    r")"
)

_SEEKS_ACTION_PATTERNS = re.compile(
    r"(?i)(?:"
    r"^(?:run|check|conduct|perform|do\s+a|execute|start)\s|"
    r"\b(?:run\s+(?:kyp|due\s+diligence|sanctions?))\b|"
    r"\b(?:(?:sanctions?|background|risk)\s+(?:check|screen|assessment))\b"
    r")"
)


# =============================================================================
# Domain concept patterns — WHAT the query is about (not HOW it asks)
# =============================================================================
# These detect domain-level concepts that indicate which data domain
# the query belongs to. Unlike question-type patterns (which match
# question structure), these match SUBJECT MATTER.

_CONCEPT_BILLING = re.compile(
    r"(?i)(?:"
    r"\b(?:payments?|invoices?|billing|collections?|aging|overdue|outstanding)\b|"
    r"\b(?:accounts?\s+receivable|AR\b|pay\s+on\s+time|paid|unpaid|receivables?)\b|"
    r"\b(?:downpayment|down\s+payment|payment\s+(?:status|history|track|discipline|progress))\b"
    r")"
)

_CONCEPT_PRODUCT = re.compile(
    r"(?i)(?:"
    r"\b(?:engines?|specs?|specifications?|power|kW|RPM|fuel|bore|stroke)\b|"
    r"\b(?:configuration|model|series|lineup|range|dimensions?|displacement)\b|"
    r"\b(?:dual\s+fuel|options?\s+available|technical|emissions?|IMO\s+Tier)\b"
    r")"
)

_CONCEPT_COMPETITOR = re.compile(
    r"(?i)(?:"
    r"\b(?:competitors?|competitive|wins?|losses?|market\s+share|position)\b|"
    r"\b(?:threat|advantage|gap|parity|versus|vs\.?|against)\b|"
    r"\b(?:competitor\s+(?:activity|wins?|news|updates?))\b"
    r")"
)

_CONCEPT_KYP = re.compile(
    r"(?i)(?:"
    r"\b(?:KYP|due\s+diligence|sanctions?|compliance|risk\s+(?:assessment|check))\b|"
    r"\b(?:background\s+check|litigation|regulatory|blacklist|screening)\b|"
    r"\b(?:verification|verify|sanctioned|OFAC|EU\s+sanctions?)\b"
    r")"
)

# Calibrated v3: added "shipyard" as standalone, "active in" pattern
_CONCEPT_MARKET = re.compile(
    r"(?i)(?:"
    r"\b(?:market|industry|trends?|opportunities?|growth|sector|segment)\b|"
    r"\b(?:newbuild|vessel\s+orders?|shipyards?|fleet\s+expansion)\b|"
    r"\b(?:maritime|offshore|marine\s+(?:market|industry|sector))\b|"
    r"\b(?:active\s+in\s+\w+|LNG\s+adoption|new\s+build\s+programs?)\b"
    r")"
)

# Calibrated v3: expanded to catch "company overview", "what engines do they use",
# "order details", "credit status and news" — customer relationship queries
# that don't use the word "customer" explicitly.
_CONCEPT_CUSTOMER = re.compile(
    r"(?i)(?:"
    r"\b(?:customer|fleet|installed\s+base|relationship|pipeline|deals?)\b|"
    r"\b(?:opportunities?\s+for|CEC\s+opp|account|profile)\b|"
    r"\b(?:customer\s+(?:profile|data|info)|won\s+deals?)\b|"
    r"\b(?:company\s+overview|company\s+profile|about\s+(?:this|the)\s+company)\b|"
    r"\b(?:what\s+(?:engines?|products?)\s+(?:do|does)\s+they)\b|"
    r"\b(?:currently\s+use|installed|order\s+details?|order\s+for)\b|"
    r"\b(?:credit\s+status|credit\s+limit)\b"
    r")"
)


# =============================================================================
# Follow-up detection (structural, not domain-specific)
# =============================================================================

_FOLLOWUP_INDICATORS = re.compile(
    r"(?i)(?:"
    r"^(?:and|also|what\s+about|how\s+about|tell\s+me\s+more)\b|"
    r"^(?:their|its|the\s+company|this\s+company)\b|"
    r"^(?:yes|ok|sure)\s|"
    r"^\w{1,4}\?$"  # Very short queries like "and?" or "more?"
    r")"
)


# =============================================================================
# Main extraction function
# =============================================================================


def extract_signals(
    parsed_query: ParsedQuery,
    session_context: Optional[Dict[str, Any]] = None,
) -> SignalSnapshot:
    """
    Extract all routing signals from a parsed query and session context.

    No new API calls — uses only data already available in ParsedQuery
    and session.context dict.

    Args:
        parsed_query: The LLM-parsed query (already computed)
        session_context: session.context dict (already available)

    Returns:
        SignalSnapshot with all signal values
    """
    ctx = session_context or {}
    query = parsed_query.raw_query

    # ── Entity signals (Deterministic) ──────────────────────────────
    entity_type = _classify_entity_type(parsed_query, ctx)
    entity_has_sap_id = bool(
        ctx.get("confirmed_entity", {}).get("entity_id")
        or ctx.get("confirmed_entity", {}).get("uen")
        or ctx.get("confirmed_entity", {}).get("canonical_name")
    )
    entity_in_competitor_list = bool(parsed_query.competitors) or _is_competitor_name(
        parsed_query.companies
    )
    entity_in_product_registry = bool(parsed_query.products) or bool(
        _PRODUCT_PATTERN.search(query)
    )
    # Billing history: inferred from entity having SAP ID + billing intent history
    entity_has_billing_history = entity_has_sap_id and _has_billing_context(ctx)

    # ── Question-type signals (Heuristic) ───────────────────────────
    question_seeks_data = bool(_SEEKS_DATA_PATTERNS.search(query))
    question_seeks_specs = bool(_SEEKS_SPECS_PATTERNS.search(query))
    question_seeks_news = bool(_SEEKS_NEWS_PATTERNS.search(query))
    question_seeks_action = bool(_SEEKS_ACTION_PATTERNS.search(query))

    # ── Domain concept signals (Heuristic) ─────────────────────────
    concept_billing = bool(_CONCEPT_BILLING.search(query))
    concept_product = bool(_CONCEPT_PRODUCT.search(query))
    concept_competitor = bool(_CONCEPT_COMPETITOR.search(query))
    concept_kyp = bool(_CONCEPT_KYP.search(query))
    concept_market = bool(_CONCEPT_MARKET.search(query))
    concept_customer = bool(_CONCEPT_CUSTOMER.search(query))

    # ── Context signals (Deterministic) ─────────────────────────────
    context_previous_intent = ctx.get("last_intent")
    context_previous_entity = ctx.get("last_kyp_entity") or (
        ctx.get("companies", [None])[-1] if ctx.get("companies") else None
    )
    context_is_followup = (
        bool(_FOLLOWUP_INDICATORS.search(query)) or len(query.split()) <= 4
    )
    context_turn_count = ctx.get("_turn_count", 0)

    # ── LLM signals (from existing ParsedQuery) ────────────────────
    llm_classified_intent = parsed_query.intent.value
    llm_intent_confidence = parsed_query.intent_confidence
    llm_sub_classification = _get_sub_classification(parsed_query)

    snapshot = SignalSnapshot(
        entity_type=entity_type,
        entity_has_sap_id=entity_has_sap_id,
        entity_has_billing_history=entity_has_billing_history,
        entity_in_competitor_list=entity_in_competitor_list,
        entity_in_product_registry=entity_in_product_registry,
        question_seeks_data=question_seeks_data,
        question_seeks_specs=question_seeks_specs,
        question_seeks_news=question_seeks_news,
        question_seeks_action=question_seeks_action,
        concept_billing=concept_billing,
        concept_product=concept_product,
        concept_competitor=concept_competitor,
        concept_kyp=concept_kyp,
        concept_market=concept_market,
        concept_customer=concept_customer,
        context_previous_intent=context_previous_intent,
        context_previous_entity=context_previous_entity,
        context_is_followup=context_is_followup,
        context_turn_count=context_turn_count,
        llm_classified_intent=llm_classified_intent,
        llm_intent_confidence=llm_intent_confidence,
        llm_sub_classification=llm_sub_classification,
    )

    logger.debug(
        f"Signals extracted: entity={entity_type}, "
        f"seeks_data={question_seeks_data}, seeks_specs={question_seeks_specs}, "
        f"seeks_news={question_seeks_news}, seeks_action={question_seeks_action}, "
        f"followup={context_is_followup}, llm_intent={llm_classified_intent}"
    )

    return snapshot


# =============================================================================
# Helper functions
# =============================================================================


def _classify_entity_type(
    parsed: ParsedQuery,
    ctx: Dict[str, Any],
) -> str:
    """Classify the primary entity type from parsed query + context."""
    # Competitor takes priority (explicit extraction)
    if parsed.competitors:
        return "competitor"

    # Product reference
    if parsed.products or _PRODUCT_PATTERN.search(parsed.raw_query):
        return "product"

    # Company mentioned
    if parsed.companies:
        # Check if the company is actually a known competitor
        if _is_competitor_name(parsed.companies):
            return "competitor"
        # Check if confirmed entity has SAP ID (existing customer)
        confirmed = ctx.get("confirmed_entity", {})
        if confirmed.get("entity_id") or confirmed.get("uen"):
            return "customer"
        return "prospect"

    # No entity in query — check context
    if ctx.get("last_kyp_entity") or ctx.get("companies"):
        # Inherit from context
        prev_companies = ctx.get("companies", [])
        if prev_companies and _is_competitor_name(prev_companies):
            return "competitor"
        if ctx.get("confirmed_entity"):
            return "customer"
        return "prospect"

    return "none"


def _is_competitor_name(names: list[str]) -> bool:
    """Check if any name matches the known competitor list."""
    if not names:
        return False
    return any(n.lower() in _KNOWN_COMPETITORS for n in names)


def _has_billing_context(ctx: Dict[str, Any]) -> bool:
    """Check if session context suggests billing data availability."""
    # If previous intent was billing-related, the entity likely has billing data
    prev = ctx.get("last_intent", "")
    if prev in ("billing_ar",):
        return True
    # If confirmed entity exists with SAP ID, assume billing data exists
    confirmed = ctx.get("confirmed_entity", {})
    if confirmed.get("entity_id") or confirmed.get("uen"):
        return True
    return False


def _get_sub_classification(parsed: ParsedQuery) -> Optional[str]:
    """Get the LLM sub-classification for the intent."""
    if parsed.intent == QueryIntent.MARKET_INTEL:
        return parsed.market_intel_style
    if parsed.intent == QueryIntent.COMPETITOR_INTEL:
        return parsed.competitor_intel_style
    return None
