"""
Signal Routing Evaluation & Calibration

Comprehensive evaluation of signal-based routing against a golden query set.
Computes all metrics required for Phase 3 go/no-go decision.

Metrics computed:
- Overall agreement rate (signal vs expected intent)
- Per-domain agreement rate
- Confidence distribution (HIGH/MODERATE/LOW)
- Hard rule usage frequency
- Disagreement classification
- Failure mode categorization
"""

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

import pytest

from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.routing_signals import SignalSnapshot
from lead_to_cash.core.signal_extractor import extract_signals
from lead_to_cash.core.signal_router import RoutingResult, route
from lead_to_cash.core.signal_scorer import score_domains

logger = logging.getLogger(__name__)


# =============================================================================
# Golden Query Definition
# =============================================================================


@dataclass
class GoldenQuery:
    """A query with its expected correct intent and routing context."""

    query: str
    expected_intent: str
    llm_intent: str  # What the LLM would classify as (simulated)
    llm_confidence: float
    entity_type: str = "none"
    companies: list = None
    competitors: list = None
    products: list = None
    has_sap_id: bool = False
    has_billing_history: bool = False
    in_competitor_list: bool = False
    in_product_registry: bool = False
    previous_intent: str = None
    previous_entity: str = None
    category: str = ""  # For grouping: billing, product, competitor, etc.
    notes: str = ""

    def __post_init__(self):
        if self.companies is None:
            self.companies = []
        if self.competitors is None:
            self.competitors = []
        if self.products is None:
            self.products = []


# =============================================================================
# 100+ Golden Query Set — covering all domains + edge cases
# =============================================================================

GOLDEN_QUERIES = [
    # ── BILLING / FINANCE (20 queries) ─────────────────────────────
    GoldenQuery(
        "What is ST Engineering's payment track record?",
        "billing_ar",
        "customer_intel",
        0.7,
        entity_type="customer",
        companies=["ST Engineering"],
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
        notes="Critical failure scenario — LLM misclassifies as customer_intel",
    ),
    GoldenQuery(
        "Do they pay on time?",
        "billing_ar",
        "customer_intel",
        0.6,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        previous_intent="customer_intel",
        previous_entity="ST Engineering",
        category="billing",
        notes="Follow-up without billing keywords",
    ),
    GoldenQuery(
        "Show billing items for Maersk",
        "billing_ar",
        "billing_ar",
        0.9,
        entity_type="customer",
        companies=["Maersk"],
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Show overdue invoices",
        "billing_ar",
        "billing_ar",
        0.85,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "What are the aging buckets?",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Show collections items",
        "billing_ar",
        "billing_ar",
        0.85,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "What is the payment status for this order?",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "How much has been paid so far?",
        "billing_ar",
        "customer_intel",
        0.65,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
        notes="No billing keyword — seeks_data + has_billing_history",
    ),
    GoldenQuery(
        "Show downpayment alerts",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "What is their payment discipline?",
        "billing_ar",
        "customer_intel",
        0.6,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        previous_intent="customer_intel",
        category="billing",
        notes="Indirect reference — no billing keywords",
    ),
    GoldenQuery(
        "Show AR aging report", "billing_ar", "billing_ar", 0.85, category="billing"
    ),
    GoldenQuery(
        "Outstanding invoices for this customer",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Show payment history",
        "billing_ar",
        "customer_intel",
        0.65,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Collections history for this customer",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        previous_intent="customer_intel",
        category="billing",
    ),
    GoldenQuery(
        "Are there any overdue payments?",
        "billing_ar",
        "billing_ar",
        0.75,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Payment progress overview",
        "billing_ar",
        "customer_intel",
        0.6,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "What invoices are pending?",
        "billing_ar",
        "billing_ar",
        0.8,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    GoldenQuery(
        "Show billing summary", "billing_ar", "billing_ar", 0.85, category="billing"
    ),
    GoldenQuery(
        "Accounts receivable status",
        "billing_ar",
        "billing_ar",
        0.8,
        category="billing",
    ),
    GoldenQuery(
        "What is the total outstanding amount?",
        "billing_ar",
        "customer_intel",
        0.6,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="billing",
    ),
    # ── PRODUCT / TECHNICAL (15 queries) ───────────────────────────
    GoldenQuery(
        "What are the MTU 12V 2000 M93 specs?",
        "product_fit",
        "product_fit",
        0.9,
        entity_type="product",
        products=["MTU 12V 2000"],
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "Engine specifications for OSV applications",
        "product_fit",
        "product_fit",
        0.85,
        category="product",
    ),
    GoldenQuery(
        "Compare MTU 4000 models",
        "product_fit",
        "product_fit",
        0.85,
        entity_type="product",
        products=["MTU 4000"],
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "Power output of Bergen B35:40",
        "product_fit",
        "product_fit",
        0.9,
        entity_type="product",
        products=["Bergen B35:40"],
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "What engine fits a 2000 kW ferry requirement?",
        "product_fit",
        "product_fit",
        0.8,
        category="product",
    ),
    GoldenQuery(
        "Fuel consumption data for Series 4000",
        "product_fit",
        "product_fit",
        0.85,
        entity_type="product",
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "Explain ISO 8528 duty classes",
        "product_fit",
        "general_question",
        0.6,
        category="product",
        notes="LLM might miss product context",
    ),
    GoldenQuery(
        "MTU engine lineup for marine applications",
        "product_fit",
        "product_fit",
        0.85,
        entity_type="product",
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "What are the dimensions of the 16V 4000?",
        "product_fit",
        "product_fit",
        0.8,
        entity_type="product",
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "RPM range for continuous duty engines",
        "product_fit",
        "product_fit",
        0.75,
        category="product",
    ),
    GoldenQuery(
        "Technical specifications for power generation",
        "product_fit",
        "product_fit",
        0.7,
        category="product",
    ),
    GoldenQuery(
        "What is our engine range for tugs?",
        "product_fit",
        "product_fit",
        0.8,
        category="product",
    ),
    GoldenQuery(
        "Bore x stroke for MTU 2000 series",
        "product_fit",
        "product_fit",
        0.9,
        entity_type="product",
        in_product_registry=True,
        category="product",
    ),
    GoldenQuery(
        "Dual fuel options available?",
        "product_fit",
        "product_fit",
        0.7,
        category="product",
    ),
    GoldenQuery(
        "What engine for 3500 kW OSV?",
        "product_fit",
        "product_fit",
        0.75,
        category="product",
    ),
    # ── COMPETITOR INTELLIGENCE (15 queries) ───────────────────────
    GoldenQuery(
        "What are the latest updates from Caterpillar?",
        "competitor_intel",
        "competitor_intel",
        0.85,
        entity_type="competitor",
        competitors=["Caterpillar"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "Cummins latest product launches",
        "competitor_intel",
        "competitor_intel",
        0.85,
        entity_type="competitor",
        competitors=["Cummins"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "How does Wärtsilä compare to us in offshore?",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["Wärtsilä"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "MAN Energy Solutions financial performance",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["MAN Energy Solutions"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "What is Caterpillar's billing model?",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["Caterpillar"],
        in_competitor_list=True,
        category="competitor",
        notes="Has 'billing' word — must NOT go to billing_ar",
    ),
    GoldenQuery(
        "Competitor wins in APAC region",
        "competitor_intel",
        "competitor_intel",
        0.8,
        category="competitor",
    ),
    GoldenQuery(
        "Cat C32 fuel consumption specs",
        "competitor_intel",
        "competitor_intel",
        0.75,
        entity_type="competitor",
        competitors=["Caterpillar"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "What is Cummins QSK60 power rating?",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["Cummins"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "HiMSEN engine threat assessment",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["HiMSEN"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "Competitor activity in ferry segment",
        "competitor_intel",
        "competitor_intel",
        0.8,
        category="competitor",
    ),
    GoldenQuery(
        "What is Caterpillar doing in the market?",
        "competitor_intel",
        "customer_intel",
        0.6,
        entity_type="competitor",
        competitors=["Caterpillar"],
        in_competitor_list=True,
        category="competitor",
        notes="LLM might see 'Caterpillar' as a company, not competitor",
    ),
    GoldenQuery(
        "Wartsila 31 specifications",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["Wartsila"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "Compare our position against MAN",
        "competitor_intel",
        "competitor_intel",
        0.85,
        entity_type="competitor",
        competitors=["MAN"],
        in_competitor_list=True,
        category="competitor",
    ),
    GoldenQuery(
        "MAN billing model and payment terms",
        "competitor_intel",
        "competitor_intel",
        0.7,
        entity_type="competitor",
        companies=["MAN"],
        in_competitor_list=True,
        category="competitor",
        notes="MAN in companies list, but IS a competitor",
    ),
    GoldenQuery(
        "Tell me about their latest products",
        "competitor_intel",
        "competitor_intel",
        0.7,
        entity_type="competitor",
        in_competitor_list=True,
        previous_intent="competitor_intel",
        previous_entity="Caterpillar",
        category="competitor",
        notes="Follow-up about competitor",
    ),
    # ── CUSTOMER INTELLIGENCE (10 queries) ─────────────────────────
    GoldenQuery(
        "Tell me about Batam Fast Ferry",
        "customer_intel",
        "customer_intel",
        0.8,
        entity_type="customer",
        companies=["Batam Fast Ferry"],
        has_sap_id=True,
        category="customer",
    ),
    GoldenQuery(
        "What is Maersk's fleet composition?",
        "customer_intel",
        "customer_intel",
        0.8,
        entity_type="customer",
        companies=["Maersk"],
        has_sap_id=True,
        category="customer",
    ),
    GoldenQuery(
        "Show opportunities for ST Engineering",
        "customer_intel",
        "customer_intel",
        0.85,
        entity_type="customer",
        companies=["ST Engineering"],
        has_sap_id=True,
        category="customer",
    ),
    GoldenQuery(
        "Customer profile for Neptune Energy",
        "customer_intel",
        "customer_intel",
        0.85,
        entity_type="prospect",
        companies=["Neptune Energy"],
        category="customer",
    ),
    GoldenQuery(
        "What is their installed base?",
        "customer_intel",
        "customer_intel",
        0.7,
        entity_type="customer",
        has_sap_id=True,
        previous_intent="customer_intel",
        category="customer",
        notes="Follow-up",
    ),
    GoldenQuery(
        "Latest news about Maersk",
        "customer_intel",
        "customer_intel",
        0.8,
        entity_type="customer",
        companies=["Maersk"],
        has_sap_id=True,
        category="customer",
    ),
    GoldenQuery(
        "Pacific Maritime company overview",
        "customer_intel",
        "customer_intel",
        0.75,
        entity_type="prospect",
        companies=["Pacific Maritime"],
        category="customer",
    ),
    GoldenQuery(
        "What deals has Batam Fast Ferry won?",
        "customer_intel",
        "customer_intel",
        0.8,
        entity_type="customer",
        companies=["Batam Fast Ferry"],
        has_sap_id=True,
        category="customer",
    ),
    GoldenQuery(
        "Show CEC opportunities for this customer",
        "customer_intel",
        "customer_intel",
        0.85,
        entity_type="customer",
        has_sap_id=True,
        previous_intent="customer_intel",
        category="customer",
    ),
    GoldenQuery(
        "What engines do they currently use?",
        "customer_intel",
        "customer_intel",
        0.7,
        entity_type="customer",
        has_sap_id=True,
        previous_intent="customer_intel",
        category="customer",
        notes="Follow-up",
    ),
    # ── KYP / DUE DILIGENCE (10 queries) ──────────────────────────
    GoldenQuery(
        "Run KYP on Neptune Energy",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.95,
        entity_type="prospect",
        companies=["Neptune Energy"],
        category="kyp",
    ),
    GoldenQuery(
        "Conduct due diligence on this company",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.9,
        entity_type="prospect",
        category="kyp",
    ),
    GoldenQuery(
        "Sanctions check on Batam Fast Ferry",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.9,
        entity_type="customer",
        companies=["Batam Fast Ferry"],
        has_sap_id=True,
        category="kyp",
    ),
    GoldenQuery(
        "Background check on XYZ Corp",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.85,
        entity_type="prospect",
        companies=["XYZ Corp"],
        category="kyp",
    ),
    GoldenQuery(
        "KYP report for Maersk",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.9,
        entity_type="customer",
        companies=["Maersk"],
        has_sap_id=True,
        category="kyp",
    ),
    GoldenQuery(
        "Risk assessment on this entity",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.85,
        entity_type="prospect",
        category="kyp",
    ),
    GoldenQuery(
        "Check for sanctions on this supplier",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.85,
        category="kyp",
    ),
    GoldenQuery(
        "Is this company sanctioned?",
        "kyp_due_diligence",
        "customer_intel",
        0.6,
        entity_type="prospect",
        category="kyp",
        notes="LLM might miss KYP intent",
    ),
    GoldenQuery(
        "Run compliance check",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.8,
        category="kyp",
    ),
    GoldenQuery(
        "Due diligence report please",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.85,
        previous_intent="customer_intel",
        category="kyp",
    ),
    # ── MARKET INTELLIGENCE (10 queries) ──────────────────────────
    GoldenQuery(
        "What is happening in the APAC ferry market?",
        "market_intel",
        "market_intel",
        0.85,
        category="market",
    ),
    GoldenQuery(
        "Latest developments in offshore energy",
        "market_intel",
        "market_intel",
        0.8,
        category="market",
    ),
    GoldenQuery(
        "Market opportunities in Singapore",
        "market_intel",
        "market_intel",
        0.8,
        category="market",
    ),
    GoldenQuery(
        "Maritime industry trends",
        "market_intel",
        "market_intel",
        0.85,
        category="market",
    ),
    GoldenQuery(
        "What are the growth areas for power generation?",
        "market_intel",
        "market_intel",
        0.75,
        category="market",
    ),
    GoldenQuery(
        "Vessel orders in Southeast Asia",
        "market_intel",
        "market_intel",
        0.8,
        category="market",
    ),
    GoldenQuery(
        "Industry news for marine engines",
        "market_intel",
        "market_intel",
        0.85,
        category="market",
    ),
    GoldenQuery(
        "What shipyards are active in APAC?",
        "market_intel",
        "market_intel",
        0.75,
        category="market",
    ),
    GoldenQuery(
        "LNG adoption trends in shipping",
        "market_intel",
        "market_intel",
        0.8,
        category="market",
    ),
    GoldenQuery(
        "New build programs in Indonesia",
        "market_intel",
        "market_intel",
        0.8,
        category="market",
    ),
    # ── GENERAL / AMBIGUOUS (10 queries) ──────────────────────────
    GoldenQuery(
        "Tell me something interesting",
        "general_question",
        "general_question",
        0.3,
        category="general",
        notes="Very generic",
    ),
    GoldenQuery(
        "What is an OSV?",
        "general_question",
        "general_question",
        0.5,
        category="general",
    ),
    GoldenQuery(
        "Help me with something",
        "general_question",
        "general_question",
        0.3,
        category="general",
    ),
    GoldenQuery(
        "What can you do?",
        "general_question",
        "general_question",
        0.4,
        category="general",
    ),
    GoldenQuery(
        "Hello", "general_question", "general_question", 0.2, category="general"
    ),
    GoldenQuery(
        "Compare options",
        "general_question",
        "general_question",
        0.4,
        category="general",
        notes="Too vague",
    ),
    GoldenQuery(
        "What are the trends?",
        "market_intel",
        "market_intel",
        0.5,
        category="general",
        notes="Borderline market_intel",
    ),
    GoldenQuery(
        "Show me data", "general_question", "general_question", 0.3, category="general"
    ),
    GoldenQuery(
        "Payment trends in the maritime industry",
        "market_intel",
        "market_intel",
        0.6,
        category="general",
        notes="Has 'payment' but is market context",
    ),
    GoldenQuery(
        "Summary please",
        "general_question",
        "general_question",
        0.3,
        previous_intent="customer_intel",
        category="general",
        notes="Generic follow-up",
    ),
    # ── CROSS-DOMAIN EDGE CASES (10 queries) ──────────────────────
    GoldenQuery(
        "Caterpillar's credit financing model",
        "competitor_intel",
        "competitor_intel",
        0.7,
        entity_type="competitor",
        competitors=["Caterpillar"],
        in_competitor_list=True,
        category="edge",
        notes="Has 'credit' but is competitor intel",
    ),
    GoldenQuery(
        "What payment terms does MTU offer?",
        "product_fit",
        "product_fit",
        0.7,
        entity_type="product",
        in_product_registry=True,
        category="edge",
        notes="Has 'payment' but is product context",
    ),
    GoldenQuery(
        "Is Caterpillar winning at ST Engineering?",
        "competitor_intel",
        "customer_intel",
        0.6,
        entity_type="competitor",
        competitors=["Caterpillar"],
        companies=["ST Engineering"],
        in_competitor_list=True,
        has_sap_id=True,
        category="edge",
        notes="Both competitor and customer entity",
    ),
    GoldenQuery(
        "Run KYP - check payment history and sanctions",
        "kyp_due_diligence",
        "kyp_due_diligence",
        0.85,
        entity_type="prospect",
        category="edge",
        notes="Has billing keywords but is KYP",
    ),
    GoldenQuery(
        "Competitor billing and collections comparison",
        "competitor_intel",
        "competitor_intel",
        0.7,
        entity_type="competitor",
        in_competitor_list=True,
        category="edge",
        notes="Billing words in competitor context",
    ),
    GoldenQuery(
        "What is the credit status AND latest news for ST Engineering?",
        "customer_intel",
        "customer_intel",
        0.7,
        entity_type="customer",
        companies=["ST Engineering"],
        has_sap_id=True,
        category="edge",
        notes="Cross-domain query — could be billing or customer",
    ),
    GoldenQuery(
        "Engine specs for Wärtsilä 31",
        "competitor_intel",
        "competitor_intel",
        0.75,
        entity_type="competitor",
        competitors=["Wärtsilä"],
        in_competitor_list=True,
        category="edge",
        notes="Product specs but for a competitor engine",
    ),
    GoldenQuery(
        "What are our advantages over Cummins?",
        "competitor_intel",
        "competitor_intel",
        0.8,
        entity_type="competitor",
        competitors=["Cummins"],
        in_competitor_list=True,
        category="edge",
    ),
    GoldenQuery(
        "Order details for 1000024001",
        "customer_intel",
        "customer_intel",
        0.7,
        entity_type="customer",
        has_sap_id=True,
        category="edge",
        notes="Order query — currently fast-path",
    ),
    GoldenQuery(
        "Show deals and payment status",
        "billing_ar",
        "customer_intel",
        0.6,
        entity_type="customer",
        has_sap_id=True,
        has_billing_history=True,
        category="edge",
        notes="Mixed billing + opportunity query",
    ),
]


# =============================================================================
# Evaluation Engine
# =============================================================================


def _build_signals(gq: GoldenQuery) -> SignalSnapshot:
    """Build a SignalSnapshot from a GoldenQuery definition."""
    # Build ParsedQuery for signal extraction
    intent_map = {v.value: v for v in QueryIntent}
    llm_intent = intent_map.get(gq.llm_intent, QueryIntent.GENERAL_QUESTION)

    parsed = ParsedQuery(
        raw_query=gq.query,
        intent=llm_intent,
        intent_confidence=gq.llm_confidence,
        companies=gq.companies or [],
        competitors=gq.competitors or [],
        products=gq.products or [],
    )

    ctx = {}
    if gq.has_sap_id:
        ctx["confirmed_entity"] = {
            "entity_id": "0001",
            "canonical_name": gq.companies[0] if gq.companies else "Entity",
        }
    if gq.previous_intent:
        ctx["last_intent"] = gq.previous_intent
    if gq.previous_entity:
        ctx["last_kyp_entity"] = gq.previous_entity
    elif gq.companies:
        ctx["companies"] = gq.companies

    signals = extract_signals(parsed, ctx)

    # Override entity signals that require real DB lookups
    if gq.has_billing_history:
        signals.entity_has_billing_history = True
    if gq.in_product_registry:
        signals.entity_in_product_registry = True

    return signals


def run_evaluation() -> dict:
    """Run full evaluation and return metrics."""
    results = []
    for gq in GOLDEN_QUERIES:
        signals = _build_signals(gq)
        scores = score_domains(signals)
        result = route(signals, scores)

        correct = result.intent == gq.expected_intent
        agrees_with_current = result.intent == gq.llm_intent
        current_correct = gq.llm_intent == gq.expected_intent

        results.append(
            {
                "query": gq.query,
                "expected": gq.expected_intent,
                "signal_intent": result.intent,
                "current_intent": gq.llm_intent,
                "signal_correct": correct,
                "current_correct": current_correct,
                "agreement": agrees_with_current,
                "confidence": result.confidence,
                "confidence_band": result.confidence_band,
                "hard_rule": result.hard_rule_fired,
                "intent_source": result.intent_source,
                "routing_risk": result.routing_risk,
                "category": gq.category,
                "domain_scores": result.domain_scores,
            }
        )

    # Compute metrics
    total = len(results)
    signal_correct = sum(1 for r in results if r["signal_correct"])
    current_correct_count = sum(1 for r in results if r["current_correct"])
    agreement = sum(1 for r in results if r["agreement"])

    # Per-domain accuracy
    domain_metrics = defaultdict(
        lambda: {"total": 0, "signal_correct": 0, "current_correct": 0}
    )
    for r in results:
        domain = r["expected"]
        domain_metrics[domain]["total"] += 1
        if r["signal_correct"]:
            domain_metrics[domain]["signal_correct"] += 1
        if r["current_correct"]:
            domain_metrics[domain]["current_correct"] += 1

    # Confidence distribution
    conf_dist = Counter(r["confidence_band"] for r in results)

    # Hard rule usage
    hard_rules = Counter(r["hard_rule"] for r in results if r["hard_rule"])
    hard_rule_rate = sum(1 for r in results if r["hard_rule"]) / total

    # Disagreement classification
    disagreements = {
        "signal_correct_current_wrong": [],
        "current_correct_signal_wrong": [],
        "both_wrong": [],
        "both_correct_different": [],
    }
    for r in results:
        if r["signal_correct"] and not r["current_correct"]:
            disagreements["signal_correct_current_wrong"].append(r)
        elif not r["signal_correct"] and r["current_correct"]:
            disagreements["current_correct_signal_wrong"].append(r)
        elif not r["signal_correct"] and not r["current_correct"]:
            disagreements["both_wrong"].append(r)
        elif r["signal_correct"] and r["current_correct"] and not r["agreement"]:
            disagreements["both_correct_different"].append(r)

    # HIGH confidence error rate
    high_conf = [r for r in results if r["confidence_band"] == "HIGH"]
    high_conf_errors = sum(1 for r in high_conf if not r["signal_correct"])
    high_conf_error_rate = high_conf_errors / len(high_conf) if high_conf else 0

    return {
        "total_queries": total,
        "signal_accuracy": signal_correct / total,
        "current_accuracy": current_correct_count / total,
        "agreement_rate": agreement / total,
        "signal_correct": signal_correct,
        "current_correct": current_correct_count,
        "domain_metrics": dict(domain_metrics),
        "confidence_distribution": dict(conf_dist),
        "hard_rule_usage": dict(hard_rules),
        "hard_rule_rate": hard_rule_rate,
        "disagreements": {k: len(v) for k, v in disagreements.items()},
        "disagreement_details": disagreements,
        "high_confidence_error_rate": high_conf_error_rate,
        "high_confidence_total": len(high_conf),
        "high_confidence_errors": high_conf_errors,
        "results": results,
    }


# =============================================================================
# Tests — Run evaluation and assert go/no-go thresholds
# =============================================================================


class TestEvaluationMetrics:
    """Run full evaluation and verify go/no-go thresholds."""

    @pytest.fixture(scope="class")
    def eval_results(self):
        return run_evaluation()

    def test_signal_accuracy_above_threshold(self, eval_results):
        """Signal routing must be ≥93% accurate."""
        accuracy = eval_results["signal_accuracy"]
        assert accuracy >= 0.93, (
            f"Signal accuracy {accuracy:.1%} below 93% threshold. "
            f"{eval_results['signal_correct']}/{eval_results['total_queries']} correct."
        )

    def test_signal_better_than_current(self, eval_results):
        """Signal routing must be at least as accurate as current keyword routing."""
        assert eval_results["signal_accuracy"] >= eval_results["current_accuracy"], (
            f"Signal accuracy {eval_results['signal_accuracy']:.1%} worse than "
            f"current {eval_results['current_accuracy']:.1%}"
        )

    def test_current_correct_signal_wrong_below_threshold(self, eval_results):
        """Cases where current is right but signal is wrong must be ≤2%."""
        rate = (
            eval_results["disagreements"]["current_correct_signal_wrong"]
            / eval_results["total_queries"]
        )
        assert rate <= 0.02, (
            f"Regression rate {rate:.1%} exceeds 2% threshold. "
            f"Signal made {eval_results['disagreements']['current_correct_signal_wrong']} errors "
            f"that current routing got right."
        )

    def test_high_confidence_error_rate_below_threshold(self, eval_results):
        """HIGH confidence errors must be ≤1%."""
        rate = eval_results["high_confidence_error_rate"]
        assert rate <= 0.01, (
            f"HIGH confidence error rate {rate:.1%} exceeds 1% threshold. "
            f"{eval_results['high_confidence_errors']}/{eval_results['high_confidence_total']} "
            f"HIGH-confidence decisions were wrong."
        )

    def test_signal_improvement_rate(self, eval_results):
        """Signal should improve on current routing by ≥3%."""
        improvement = eval_results["disagreements"]["signal_correct_current_wrong"]
        rate = improvement / eval_results["total_queries"]
        assert rate >= 0.03, (
            f"Signal improvement rate {rate:.1%} below 3% threshold. "
            f"Signal corrected only {improvement} queries that current got wrong."
        )


class TestPerDomainAccuracy:
    """Per-domain accuracy must be reasonable."""

    @pytest.fixture(scope="class")
    def eval_results(self):
        return run_evaluation()

    def test_billing_accuracy(self, eval_results):
        metrics = eval_results["domain_metrics"].get("billing_ar", {})
        if metrics["total"] > 0:
            accuracy = metrics["signal_correct"] / metrics["total"]
            assert accuracy >= 0.85, f"Billing accuracy {accuracy:.1%} too low"

    def test_product_accuracy(self, eval_results):
        metrics = eval_results["domain_metrics"].get("product_fit", {})
        if metrics["total"] > 0:
            accuracy = metrics["signal_correct"] / metrics["total"]
            assert accuracy >= 0.90, f"Product accuracy {accuracy:.1%} too low"

    def test_competitor_accuracy(self, eval_results):
        metrics = eval_results["domain_metrics"].get("competitor_intel", {})
        if metrics["total"] > 0:
            accuracy = metrics["signal_correct"] / metrics["total"]
            assert accuracy >= 0.85, f"Competitor accuracy {accuracy:.1%} too low"

    def test_kyp_accuracy(self, eval_results):
        metrics = eval_results["domain_metrics"].get("kyp_due_diligence", {})
        if metrics["total"] > 0:
            accuracy = metrics["signal_correct"] / metrics["total"]
            assert accuracy >= 0.90, f"KYP accuracy {accuracy:.1%} too low"


class TestHardRuleEffectiveness:
    """Hard rules should fire appropriately."""

    @pytest.fixture(scope="class")
    def eval_results(self):
        return run_evaluation()

    def test_hard_rule_rate_reasonable(self, eval_results):
        """Hard rules should fire for ≤30% of queries."""
        assert eval_results["hard_rule_rate"] <= 0.30, (
            f"Hard rules fire too often: {eval_results['hard_rule_rate']:.1%}"
        )

    def test_hard_rule_accuracy(self, eval_results):
        """When hard rules fire, they should be correct."""
        hard_rule_results = [r for r in eval_results["results"] if r["hard_rule"]]
        if hard_rule_results:
            correct = sum(1 for r in hard_rule_results if r["signal_correct"])
            accuracy = correct / len(hard_rule_results)
            assert accuracy >= 0.95, (
                f"Hard rule accuracy {accuracy:.1%} below 95% threshold"
            )


class TestConfidenceCalibration:
    """Confidence bands should correlate with actual accuracy."""

    @pytest.fixture(scope="class")
    def eval_results(self):
        return run_evaluation()

    def test_high_confidence_is_reliable(self, eval_results):
        """HIGH confidence decisions should be ≥99% correct."""
        high = [r for r in eval_results["results"] if r["confidence_band"] == "HIGH"]
        if high:
            accuracy = sum(1 for r in high if r["signal_correct"]) / len(high)
            assert accuracy >= 0.99, f"HIGH confidence accuracy {accuracy:.1%} too low"

    def test_low_confidence_is_cautious(self, eval_results):
        """LOW confidence should be ≤20% of total queries."""
        low_rate = (
            eval_results["confidence_distribution"].get("LOW", 0)
            / eval_results["total_queries"]
        )
        assert low_rate <= 0.20, f"Too many LOW confidence: {low_rate:.1%}"


class TestEvaluationReport:
    """Generate human-readable evaluation report."""

    def test_print_report(self):
        """Print full evaluation report — always passes, for visibility."""
        results = run_evaluation()

        print("\n" + "=" * 70)
        print("SIGNAL ROUTING EVALUATION REPORT")
        print("=" * 70)

        print(f"\nTotal queries: {results['total_queries']}")
        print(
            f"Signal accuracy: {results['signal_accuracy']:.1%} ({results['signal_correct']}/{results['total_queries']})"
        )
        print(
            f"Current accuracy: {results['current_accuracy']:.1%} ({results['current_correct']}/{results['total_queries']})"
        )
        print(f"Agreement rate: {results['agreement_rate']:.1%}")

        print(f"\n{'Domain':<20} {'Total':>6} {'Signal':>8} {'Current':>8}")
        print("-" * 45)
        for domain, m in sorted(results["domain_metrics"].items()):
            sig_acc = m["signal_correct"] / m["total"] if m["total"] else 0
            cur_acc = m["current_correct"] / m["total"] if m["total"] else 0
            print(f"{domain:<20} {m['total']:>6} {sig_acc:>7.0%} {cur_acc:>7.0%}")

        print(
            f"\nConfidence: HIGH={results['confidence_distribution'].get('HIGH', 0)} "
            f"MOD={results['confidence_distribution'].get('MODERATE', 0)} "
            f"LOW={results['confidence_distribution'].get('LOW', 0)}"
        )
        print(
            f"HIGH confidence error rate: {results['high_confidence_error_rate']:.1%}"
        )
        print(f"Hard rule rate: {results['hard_rule_rate']:.1%}")
        if results["hard_rule_usage"]:
            for rule, count in sorted(results["hard_rule_usage"].items()):
                print(f"  {rule}: {count}")

        print(f"\nDisagreements:")
        for cat, count in results["disagreements"].items():
            print(f"  {cat}: {count}")

        # Show signal improvements
        improvements = results["disagreement_details"]["signal_correct_current_wrong"]
        if improvements:
            print(f"\nSignal IMPROVEMENTS ({len(improvements)} queries):")
            for r in improvements[:10]:
                print(
                    f"  '{r['query'][:50]}...' current={r['current_intent']} signal={r['signal_intent']} expected={r['expected']}"
                )

        # Show signal regressions
        regressions = results["disagreement_details"]["current_correct_signal_wrong"]
        if regressions:
            print(f"\nSignal REGRESSIONS ({len(regressions)} queries):")
            for r in regressions:
                print(
                    f"  '{r['query'][:50]}...' current={r['current_intent']} signal={r['signal_intent']} expected={r['expected']}"
                )
                print(f"    scores: {r['domain_scores']}")

        print("\n" + "=" * 70)
        print("GO/NO-GO ASSESSMENT")
        print("=" * 70)
        checks = [
            ("Signal accuracy ≥ 93%", results["signal_accuracy"] >= 0.93),
            (
                "Signal ≥ current accuracy",
                results["signal_accuracy"] >= results["current_accuracy"],
            ),
            (
                "Regression rate ≤ 2%",
                results["disagreements"]["current_correct_signal_wrong"]
                / results["total_queries"]
                <= 0.02,
            ),
            (
                "HIGH confidence error ≤ 1%",
                results["high_confidence_error_rate"] <= 0.01,
            ),
            (
                "Improvement rate ≥ 3%",
                results["disagreements"]["signal_correct_current_wrong"]
                / results["total_queries"]
                >= 0.03,
            ),
        ]
        all_pass = True
        for name, passed in checks:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {name}")
            if not passed:
                all_pass = False

        print(
            f"\nDecision: {'GO — Ready for Phase 3' if all_pass else 'NO-GO — Calibration needed'}"
        )
        print("=" * 70)
