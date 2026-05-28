"""
Signal-Based Router

Takes scored domains and applies hard business rules to produce
a final RoutingResult. This is the decision layer.

Architecture:
    SignalSnapshot → signal_scorer.score_domains() → DomainScores
    DomainScores → signal_router.route() → RoutingResult

Hard rules are applied AFTER scoring. They enforce enterprise
safety constraints that must hold regardless of signal scores.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lead_to_cash.core.query_understanding import QueryIntent
from lead_to_cash.core.routing_signals import SignalSnapshot
from lead_to_cash.core.signal_scorer import DOMAINS, score_domains

logger = logging.getLogger(__name__)


# =============================================================================
# Routing Result
# =============================================================================


@dataclass
class RoutingResult:
    """
    Final routing decision from the signal-based router.

    Consumed by conversation.py to set parsed_query.intent.
    """

    intent: str
    """Selected intent (QueryIntent value string)."""

    confidence: float
    """Routing confidence (0.0 to 1.0)."""

    confidence_band: str
    """'HIGH' (≥0.7), 'MODERATE' (0.5-0.7), 'LOW' (<0.5)."""

    intent_source: str
    """How intent was determined: 'signal', 'hard_rule_H1', etc."""

    routing_risk: Optional[str]
    """Risk flag: 'MULTI_DOMAIN', 'LOW_CONFIDENCE', 'NO_ENTITY', 'GENERIC', or None."""

    domain_scores: Dict[str, float]
    """Top domain scores for logging/debugging."""

    signals_snapshot: Dict[str, Any]
    """Full signal values for audit."""

    hard_rule_fired: Optional[str] = None
    """Which hard rule fired, if any."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "confidence_band": self.confidence_band,
            "intent_source": self.intent_source,
            "routing_risk": self.routing_risk,
            "domain_scores": self.domain_scores,
            "hard_rule_fired": self.hard_rule_fired,
        }


# =============================================================================
# Confidence bands
# =============================================================================

# Calibrated v3: raised HIGH from 0.70 to 0.75 to reduce false HIGH confidence
_HIGH_THRESHOLD = 0.75
_MODERATE_THRESHOLD = 0.50
_TIE_GAP = 0.10  # Scores within this gap are considered tied
_CONFIDENCE_DAMPEN = 0.10  # Dampening applied when scores are close or multi-concept


def _confidence_band(score: float) -> str:
    if score >= _HIGH_THRESHOLD:
        return "HIGH"
    if score >= _MODERATE_THRESHOLD:
        return "MODERATE"
    return "LOW"


# =============================================================================
# Domain to QueryIntent mapping
# =============================================================================

_DOMAIN_TO_INTENT: Dict[str, str] = {
    "billing_ar": "billing_ar",
    "product_fit": "product_fit",
    "competitor_intel": "competitor_intel",
    "customer_intel": "customer_intel",
    "kyp_due_diligence": "kyp_due_diligence",
    "market_intel": "market_intel",
}

# Explicit KYP procedure patterns (hard rule H1)
_KYP_EXPLICIT_PATTERN = re.compile(
    r"(?i)\b(?:run\s+kyp|kyp\s+(?:on|for|check|report)|"
    r"due\s+diligence|sanctions?\s+(?:check|screen)|"
    r"background\s+(?:check|verification)|"
    r"risk\s+assessment\s+(?:on|for))\b"
)


# =============================================================================
# Main routing function
# =============================================================================


def route(
    signals: SignalSnapshot,
    scores: Optional[Dict[str, float]] = None,
    user_permissions: Optional[Dict[str, list]] = None,
) -> RoutingResult:
    """
    Apply hard rules and select final intent from domain scores.

    Args:
        signals: Extracted signal snapshot
        scores: Pre-computed domain scores (if None, computed internally)
        user_permissions: User RBAC permissions (for hard rule H4)

    Returns:
        RoutingResult with final intent, confidence, and audit trail
    """
    if scores is None:
        scores = score_domains(signals)

    signals_dict = signals.to_dict()

    # ── Hard Rule H1: KYP/Due Diligence detection ───────────────────
    # Triggers on ANY of these conditions:
    # A) Question seeks action AND LLM classified as KYP
    # B) KYP concept detected AND LLM classified as KYP
    # C) KYP concept detected AND question seeks action
    # This catches "KYP report for Maersk" (concept+LLM) and
    # "Due diligence report please" (concept+action) and
    # "Is this company sanctioned?" (concept without action verb).
    _h1_action = signals.question_seeks_action
    _h1_concept = getattr(signals, "concept_kyp", False)
    _h1_llm = signals.llm_classified_intent == "kyp_due_diligence"
    _h1_conditions_met = sum([_h1_action, _h1_concept, _h1_llm])
    if _h1_conditions_met >= 2:
        return RoutingResult(
            intent="kyp_due_diligence",
            confidence=0.95,
            confidence_band="HIGH",
            intent_source="hard_rule_H1",
            routing_risk=None,
            domain_scores=_top_scores(scores, 3),
            signals_snapshot=signals_dict,
            hard_rule_fired="H1_explicit_procedure",
        )

    # ── Hard Rule H2: Internal operational data protection ──────────
    # Protects billing queries from being misrouted to customer_intel
    # when entity has billing data. Uses two independent trigger paths:
    #
    # Path A: LLM agrees (billing_ar intent) + entity has billing data
    #         → strong signal, override regardless of score gap
    # Path B: LLM disagrees but billing_ar tops scoring
    #         → scoring alone determines it's billing
    #
    # GUARD: Never fire for news/specs/action queries — those are
    # legitimately customer_intel or product_fit even for billing entities.
    _ranked_for_h2 = _rank_domains(scores)
    _h2_top_domain, _h2_top_score = _ranked_for_h2[0] if _ranked_for_h2 else ("", 0)
    _h2_billing_score = scores.get("billing_ar", 0)
    # Calibrated v3: H2 now requires concept_billing to be present.
    # This prevents customer queries like "Show opportunities" and
    # "Order details" from being caught by H2 just because the entity
    # has billing history. The billing CONCEPT must appear in the query.
    _h2_has_billing_concept = getattr(signals, "concept_billing", False)
    _h2_entity_is_billing_customer = (
        signals.entity_has_sap_id
        and signals.entity_has_billing_history
        and signals.question_seeks_data
        and _h2_has_billing_concept  # MUST have billing concept in query
        and not signals.question_seeks_news
        and not signals.question_seeks_specs
        and not signals.entity_in_competitor_list
        and not getattr(signals, "concept_product", False)
        and not getattr(signals, "concept_customer", False)
    )
    _h2_llm_agrees = signals.llm_classified_intent == "billing_ar"

    if _h2_entity_is_billing_customer and _h2_llm_agrees:
        return RoutingResult(
            intent="billing_ar",
            confidence=max(_h2_billing_score, 0.85),
            confidence_band="HIGH",
            intent_source="hard_rule_H2",
            routing_risk=None,
            domain_scores=_top_scores(scores, 3),
            signals_snapshot=signals_dict,
            hard_rule_fired="H2_internal_data_protection",
        )

    # ── Hard Rule H3: Competitor entity exclusion ───────────────────
    # Competitors must never route to billing_ar or relationship_check
    ranked = _rank_domains(scores)
    top_domain, top_score = ranked[0]
    if signals.entity_in_competitor_list and top_domain in (
        "billing_ar",
        "relationship_check",
    ):
        competitor_score = scores.get("competitor_intel", 0)
        return RoutingResult(
            intent="competitor_intel",
            confidence=max(competitor_score, 0.80),
            confidence_band="HIGH",
            intent_source="hard_rule_H3",
            routing_risk=None,
            domain_scores=_top_scores(scores, 3),
            signals_snapshot=signals_dict,
            hard_rule_fired="H3_competitor_exclusion",
        )

    # ── Hard Rule H4: RBAC enforcement ──────────────────────────────
    if top_domain == "billing_ar" and user_permissions:
        has_billing = "read" in user_permissions.get("billing", [])
        has_wildcard = "*" in user_permissions.get("*", [])
        if not has_billing and not has_wildcard:
            return RoutingResult(
                intent="billing_ar",  # Keep intent for denial message
                confidence=top_score,
                confidence_band=_confidence_band(top_score),
                intent_source="hard_rule_H4",
                routing_risk="RBAC_DENIED",
                domain_scores=_top_scores(scores, 3),
                signals_snapshot=signals_dict,
                hard_rule_fired="H4_rbac_denied",
            )

    # ── Score-based selection ───────────────────────────────────────
    second_domain, second_score = ranked[1] if len(ranked) > 1 else ("", 0.0)

    # Detect routing risk
    routing_risk = _detect_routing_risk(signals, top_score, second_score, top_domain)

    # ── Hard Rule H5: Low-confidence fallback ───────────────────────
    if top_score < _MODERATE_THRESHOLD:
        return RoutingResult(
            intent="general_question",
            confidence=top_score,
            confidence_band="LOW",
            intent_source="hard_rule_H5",
            routing_risk=routing_risk or "LOW_CONFIDENCE",
            domain_scores=_top_scores(scores, 3),
            signals_snapshot=signals_dict,
            hard_rule_fired="H5_low_confidence_fallback",
        )

    # ── Hard Rule H6: Preserve general_question from LLM ─────────────
    # When LLM classified as general_question, do not override to a
    # domain-specific intent. Prevents greetings, vague questions, and
    # general queries from being routed to market_intel/customer_intel.
    if signals.llm_classified_intent == "general_question":
        return RoutingResult(
            intent="general_question",
            confidence=top_score,
            confidence_band=_confidence_band(top_score),
            intent_source="hard_rule_H6",
            routing_risk=routing_risk,
            domain_scores=_top_scores(scores, 3),
            signals_snapshot=signals_dict,
            hard_rule_fired="H6_general_question_preserved",
        )

    # ── Normal selection: highest-scoring domain ────────────────────
    selected_intent = _DOMAIN_TO_INTENT.get(top_domain, "general_question")

    # Calibrated v3: confidence dampening for ambiguous cases
    # When top two scores are close OR multiple concept signals are active,
    # reduce confidence to avoid false HIGH-confidence decisions.
    final_confidence = top_score
    _score_gap = top_score - second_score
    _multi_concept = (
        sum(
            1
            for k in [
                "concept_billing",
                "concept_product",
                "concept_competitor",
                "concept_kyp",
                "concept_market",
                "concept_customer",
            ]
            if signals_dict.get(k, False)
        )
        > 1
    )

    if _score_gap < _TIE_GAP or _multi_concept:
        final_confidence = max(top_score - _CONFIDENCE_DAMPEN, 0.0)

    return RoutingResult(
        intent=selected_intent,
        confidence=round(final_confidence, 4),
        confidence_band=_confidence_band(final_confidence),
        intent_source="signal",
        routing_risk=routing_risk,
        domain_scores=_top_scores(scores, 3),
        signals_snapshot=signals_dict,
    )


# =============================================================================
# Helper functions
# =============================================================================


def _is_kyp_explicit(signals: SignalSnapshot) -> bool:
    """Check if LLM classified as KYP or KYP-like intent."""
    return (
        signals.llm_classified_intent in ("kyp_due_diligence",)
        or signals.question_seeks_action
    )


def _rank_domains(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    """Rank domains by score, descending."""
    return sorted(scores.items(), key=lambda x: -x[1])


def _top_scores(scores: Dict[str, float], n: int) -> Dict[str, float]:
    """Return top N domain scores for logging."""
    ranked = _rank_domains(scores)
    return dict(ranked[:n])


def _detect_routing_risk(
    signals: SignalSnapshot,
    top_score: float,
    second_score: float,
    top_domain: str,
) -> Optional[str]:
    """Detect routing risk flags."""
    # Multi-domain: top two scores are very close
    if abs(top_score - second_score) < _TIE_GAP and top_score >= _MODERATE_THRESHOLD:
        return "MULTI_DOMAIN"

    # No entity: no entity in query or context
    if signals.entity_type == "none" and signals.context_previous_entity is None:
        return "NO_ENTITY"

    # Low confidence
    if top_score < _MODERATE_THRESHOLD:
        return "LOW_CONFIDENCE"

    return None
