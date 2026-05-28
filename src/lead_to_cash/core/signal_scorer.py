"""
Signal-Based Domain Scorer

Scores each routing domain using a UNIVERSAL formula applied
identically to all domains. Domain-specific behavior comes from
signal VALUES (via lookup tables), not custom formulas.

Formula:
    domain_score(D) =
        W_entity   × entity_match(D)     # 0.30
      + W_question × question_match(D)   # 0.25
      + W_context  × context_match(D)    # 0.15
      + W_llm      × llm_match(D)       # 0.15
      + W_affinity × affinity_bonus(D)   # 0.15

All weights sum to 1.0. Same for every domain.
"""

import logging
from typing import Dict, Optional

from lead_to_cash.core.routing_signals import SignalSnapshot

logger = logging.getLogger(__name__)

# =============================================================================
# Universal weights — same for ALL domains
# =============================================================================

# Calibrated weights (v2) — reduced entity dependence, added concept signal
# Change log:
#   v1: entity=0.30, question=0.25, context=0.15, llm=0.15, affinity=0.15
#   v2: entity=0.20, question=0.25, concept=0.20, context=0.10, llm=0.10, affinity=0.15
#   Rationale: entity-less queries (market/competitor without named entity) were
#   failing because entity_match (30%) dominated. Domain concepts now carry 20%,
#   reducing entity dependence. LLM reduced from 15% to 10% to further limit
#   nondeterminism. Context reduced from 15% to 10% to prevent follow-up bias.
W_ENTITY = 0.20
W_QUESTION = 0.25
W_CONCEPT = 0.20
W_CONTEXT = 0.10
W_LLM = 0.10
W_AFFINITY = 0.15

# =============================================================================
# Domain identifiers
# =============================================================================

DOMAINS = [
    "billing_ar",
    "product_fit",
    "competitor_intel",
    "customer_intel",
    "kyp_due_diligence",
    "market_intel",
]

# Intent-to-domain mapping (for LLM match and context match)
_INTENT_TO_DOMAIN: Dict[str, str] = {
    "billing_ar": "billing_ar",
    "product_fit": "product_fit",
    "product_info": "product_fit",
    "competitor_intel": "competitor_intel",
    "financial_analysis": "competitor_intel",
    "customer_intel": "customer_intel",
    "customer_research": "customer_intel",
    "kyp_due_diligence": "kyp_due_diligence",
    "market_intel": "market_intel",
    "market_news": "market_intel",
    "sales_opportunity": "market_intel",
    "relationship_check": "customer_intel",
    "general_question": "market_intel",  # default broad domain
}


# =============================================================================
# Lookup tables — static, auditable
# =============================================================================

# entity_match(D): entity_type → domain → score
_ENTITY_MATCH: Dict[str, Dict[str, float]] = {
    "customer": {
        "billing_ar": 1.0,
        "product_fit": 0.3,
        "competitor_intel": 0.0,
        "customer_intel": 1.0,
        "kyp_due_diligence": 0.7,
        "market_intel": 0.3,
    },
    "competitor": {
        "billing_ar": 0.0,
        "product_fit": 0.3,
        "competitor_intel": 1.0,
        "customer_intel": 0.0,
        "kyp_due_diligence": 0.3,
        "market_intel": 0.3,
    },
    "product": {
        "billing_ar": 0.0,
        "product_fit": 1.0,
        "competitor_intel": 0.3,
        "customer_intel": 0.0,
        "kyp_due_diligence": 0.0,
        "market_intel": 0.3,
    },
    "prospect": {
        "billing_ar": 0.0,
        "product_fit": 0.3,
        "competitor_intel": 0.0,
        "customer_intel": 0.5,
        "kyp_due_diligence": 0.8,
        "market_intel": 0.3,
    },
    "none": {
        "billing_ar": 0.2,
        "product_fit": 0.5,
        "competitor_intel": 0.4,  # Calibrated: competitor queries often lack named entity
        "customer_intel": 0.2,
        "kyp_due_diligence": 0.2,
        "market_intel": 0.6,  # Calibrated: market queries commonly have no specific entity
    },
}
# fmt: off

# question_match(D): question_type → domain → score
# Multiple question types can be True — we take the max
_QUESTION_MATCH: Dict[str, Dict[str, float]] = {
    "seeks_data":   {"billing_ar": 1.0, "product_fit": 0.5, "competitor_intel": 0.3, "customer_intel": 0.8, "kyp_due_diligence": 0.3, "market_intel": 0.3},
    "seeks_specs":  {"billing_ar": 0.0, "product_fit": 1.0, "competitor_intel": 0.5, "customer_intel": 0.0, "kyp_due_diligence": 0.0, "market_intel": 0.0},
    "seeks_news":   {"billing_ar": 0.0, "product_fit": 0.0, "competitor_intel": 0.8, "customer_intel": 0.5, "kyp_due_diligence": 0.0, "market_intel": 1.0},
    "seeks_action": {"billing_ar": 0.3, "product_fit": 0.2, "competitor_intel": 0.2, "customer_intel": 0.3, "kyp_due_diligence": 1.0, "market_intel": 0.2},
    "none":         {"billing_ar": 0.3, "product_fit": 0.3, "competitor_intel": 0.3, "customer_intel": 0.3, "kyp_due_diligence": 0.2, "market_intel": 0.4},
}
# fmt: on


# =============================================================================
# Scoring functions
# =============================================================================


def score_domains(signals: SignalSnapshot) -> Dict[str, float]:
    """
    Score all domains using the universal formula (v2 with concept signal).

    Formula:
        domain_score(D) =
            W_ENTITY   × entity_match(D)     # 0.20
          + W_QUESTION × question_match(D)   # 0.25
          + W_CONCEPT  × concept_match(D)    # 0.20 (NEW)
          + W_CONTEXT  × context_match(D)    # 0.10
          + W_LLM      × llm_match(D)       # 0.10
          + W_AFFINITY × affinity_bonus(D)   # 0.15
        Total: 1.00

    Args:
        signals: Extracted signal snapshot

    Returns:
        Dict mapping domain name to score (0.0 to 1.0)
    """
    scores = {}
    for domain in DOMAINS:
        entity_score = _compute_entity_match(signals, domain)
        question_score = _compute_question_match(signals, domain)
        concept_score = _compute_concept_match(signals, domain)
        context_score = _compute_context_match(signals, domain)
        llm_score = _compute_llm_match(signals, domain)
        affinity_score = _compute_affinity_bonus(signals, domain)

        total = (
            W_ENTITY * entity_score
            + W_QUESTION * question_score
            + W_CONCEPT * concept_score
            + W_CONTEXT * context_score
            + W_LLM * llm_score
            + W_AFFINITY * affinity_score
        )
        scores[domain] = round(total, 4)

    return scores


# =============================================================================
# Component scoring functions
# =============================================================================


def _compute_entity_match(signals: SignalSnapshot, domain: str) -> float:
    """Score based on entity type vs domain."""
    entity_type = signals.entity_type
    row = _ENTITY_MATCH.get(entity_type, _ENTITY_MATCH["none"])
    score = row.get(domain, 0.2)

    # Refinement: customer with SAP ID gets full score for billing
    if domain == "billing_ar" and entity_type == "customer":
        if signals.entity_has_sap_id:
            return 1.0
        return 0.5  # Customer without SAP ID — billing data uncertain

    return score


def _compute_question_match(signals: SignalSnapshot, domain: str) -> float:
    """Score based on question type vs domain. Takes max across active types."""
    active_types = []
    if signals.question_seeks_data:
        active_types.append("seeks_data")
    if signals.question_seeks_specs:
        active_types.append("seeks_specs")
    if signals.question_seeks_news:
        active_types.append("seeks_news")
    if signals.question_seeks_action:
        active_types.append("seeks_action")

    if not active_types:
        active_types = ["none"]

    return max(
        _QUESTION_MATCH.get(qt, _QUESTION_MATCH["none"]).get(domain, 0.3)
        for qt in active_types
    )


def _compute_concept_match(signals: SignalSnapshot, domain: str) -> float:
    """Score based on domain concept signals detected in the query text.

    This is the key differentiator for entity-less queries and for
    billing vs customer disambiguation. 'payment track record' triggers
    concept_billing, pushing billing_ar score up even when entity signals
    point to customer_intel.
    """
    # Map each domain to its primary concept signal
    concept_map = {
        "billing_ar": signals.concept_billing,
        "product_fit": signals.concept_product,
        "competitor_intel": signals.concept_competitor,
        "kyp_due_diligence": signals.concept_kyp,
        "market_intel": signals.concept_market,
        "customer_intel": signals.concept_customer,
    }

    primary_concept = concept_map.get(domain, False)

    # Count how many concepts are active (multi-concept dampens confidence)
    active_count = sum(1 for v in concept_map.values() if v)

    if primary_concept:
        # Calibrated v3: softened from 1.0 to 0.8
        # When multiple concepts active, dampen further to avoid false certainty
        if active_count > 1:
            return 0.65  # Multi-concept: reduced influence
        return 0.8  # Single concept: strong but not dominant

    # If NO concept detected for any domain, return neutral
    if active_count == 0:
        return 0.5  # Calibrated v3: softened from 0.4 to 0.5 (less penalty for no concepts)

    # Some other domain's concept was detected, not ours
    return 0.3  # Calibrated v3: softened from 0.1 to 0.3 (less harsh penalty)


def _compute_context_match(signals: SignalSnapshot, domain: str) -> float:
    """Score based on conversation context continuity."""
    if not signals.context_is_followup:
        return 0.5  # Neutral — no context signal

    prev_domain = _INTENT_TO_DOMAIN.get(signals.context_previous_intent or "", None)
    if prev_domain == domain:
        return 1.0  # Strong continuity
    if prev_domain is not None:
        return 0.2  # Different domain follow-up (possible domain switch)
    return 0.5  # No previous intent available


def _compute_llm_match(signals: SignalSnapshot, domain: str) -> float:
    """Score based on LLM classification agreement."""
    llm_domain = _INTENT_TO_DOMAIN.get(signals.llm_classified_intent or "", None)
    if llm_domain == domain:
        return signals.llm_intent_confidence  # 0.0 to 1.0
    return 0.0


def _compute_affinity_bonus(signals: SignalSnapshot, domain: str) -> float:
    """Domain-specific affinity signals."""
    if domain == "billing_ar":
        if signals.entity_has_billing_history:
            return 1.0
        if signals.entity_has_sap_id:
            return 0.5
        return 0.0

    if domain == "product_fit":
        if signals.entity_in_product_registry:
            return 1.0
        return 0.3  # Products are often queried without naming a specific model

    if domain == "competitor_intel":
        if signals.entity_in_competitor_list:
            return 1.0
        # Calibrated v3: competitor queries may reference competitors generically
        # ("competitor wins", "competitor activity") without naming one.
        # Boost when concept_competitor detected OR LLM agrees.
        if getattr(signals, "concept_competitor", False):
            return 0.7  # Strong concept signal
        if signals.llm_classified_intent in ("competitor_intel", "financial_analysis"):
            return 0.5
        return 0.0

    if domain == "kyp_due_diligence":
        if signals.question_seeks_action:
            return 1.0
        return 0.2

    if domain == "customer_intel":
        if signals.entity_has_sap_id and not signals.entity_in_competitor_list:
            return 0.8
        return 0.3

    if domain == "market_intel":
        # Calibrated: market intel queries are inherently entity-free.
        # Without a specific affinity bonus, they score too low and
        # fall to general_question via H5.
        if signals.question_seeks_news:
            return 0.8  # News-seeking + market domain = strong affinity
        return 0.5  # General market queries still get moderate affinity

    return 0.2
