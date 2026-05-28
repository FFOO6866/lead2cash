"""
Routing Signal Type Definitions

Defines the signal types used by the signal-based routing framework.
All signals are typed, named, and classified by extraction method:
- D (Deterministic): from data lookups, 100% reproducible
- H (Heuristic): from query structure patterns, ~95% reproducible
- L (LLM-derived): from LLM output, ~90% reproducible

Usage:
    from lead_to_cash.core.routing_signals import SignalSnapshot
    from lead_to_cash.core.signal_extractor import extract_signals

    signals = extract_signals(parsed_query, session)
    # signals.entity_type → "customer"
    # signals.question_seeks_data → True
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SignalSnapshot:
    """
    Complete set of routing signals extracted from a query + context.

    Each field is annotated with its extraction method:
    D = Deterministic, H = Heuristic, L = LLM-derived
    """

    # ── Entity signals (D — Deterministic) ─────────────────────────
    entity_type: str = "none"
    """Type of primary entity: 'customer', 'competitor', 'product', 'prospect', 'none'"""

    entity_has_sap_id: bool = False
    """Entity was found in SAP (MS5) — we have internal records."""

    entity_has_billing_history: bool = False
    """Entity has billing/AR data in BillingBrain."""

    entity_in_competitor_list: bool = False
    """Entity matches the known competitor list."""

    entity_in_product_registry: bool = False
    """Entity matches a known MTU/Bergen product name or model number."""

    # ── Question-type signals (H — Heuristic) ──────────────────────
    question_seeks_data: bool = False
    """Query asks for records, status, amounts, history."""

    question_seeks_specs: bool = False
    """Query asks for technical specifications, ratings, dimensions."""

    question_seeks_news: bool = False
    """Query asks for recent events, updates, developments."""

    question_seeks_action: bool = False
    """Query requests a procedure: 'run KYP', 'check sanctions'."""

    # ── Domain concept signals (H — Heuristic) ──────────────────────
    # These detect WHAT the query is about at the concept level,
    # independent of entity type. "payment track record" → billing concept
    # even when entity is classified as "customer".
    concept_billing: bool = False
    """Query references billing/payment/AR/collections concepts."""

    concept_product: bool = False
    """Query references product/engine/technical concepts."""

    concept_competitor: bool = False
    """Query references competitive/market-share/wins concepts."""

    concept_kyp: bool = False
    """Query references due-diligence/risk/compliance concepts."""

    concept_market: bool = False
    """Query references market/industry/trend concepts."""

    concept_customer: bool = False
    """Query references customer-relationship/fleet/opportunity concepts."""

    # ── Context signals (D — Deterministic) ────────────────────────
    context_previous_intent: Optional[str] = None
    """Intent from the previous conversation turn."""

    context_previous_entity: Optional[str] = None
    """Primary entity from the previous turn."""

    context_is_followup: bool = False
    """Query is a follow-up to a previous turn."""

    context_turn_count: int = 0
    """Number of turns in the current session."""

    # ── LLM-derived signals (L — LLM-assisted) ────────────────────
    llm_classified_intent: Optional[str] = None
    """Intent classification from the LLM (QueryUnderstandingEngine)."""

    llm_intent_confidence: float = 0.0
    """LLM's confidence in its intent classification (0.0-1.0)."""

    llm_sub_classification: Optional[str] = None
    """Sub-classification: market_intel_style or competitor_intel_style."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            # Entity signals (D)
            "entity_type": self.entity_type,
            "entity_has_sap_id": self.entity_has_sap_id,
            "entity_has_billing_history": self.entity_has_billing_history,
            "entity_in_competitor_list": self.entity_in_competitor_list,
            "entity_in_product_registry": self.entity_in_product_registry,
            # Question-type signals (H)
            "question_seeks_data": self.question_seeks_data,
            "question_seeks_specs": self.question_seeks_specs,
            "question_seeks_news": self.question_seeks_news,
            "question_seeks_action": self.question_seeks_action,
            # Domain concept signals (H)
            "concept_billing": self.concept_billing,
            "concept_product": self.concept_product,
            "concept_competitor": self.concept_competitor,
            "concept_kyp": self.concept_kyp,
            "concept_market": self.concept_market,
            "concept_customer": self.concept_customer,
            # Context signals (D)
            "context_previous_intent": self.context_previous_intent,
            "context_previous_entity": self.context_previous_entity,
            "context_is_followup": self.context_is_followup,
            "context_turn_count": self.context_turn_count,
            # LLM signals (L)
            "llm_classified_intent": self.llm_classified_intent,
            "llm_intent_confidence": self.llm_intent_confidence,
            "llm_sub_classification": self.llm_sub_classification,
        }
