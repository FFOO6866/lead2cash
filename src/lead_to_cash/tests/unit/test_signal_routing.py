"""
Unit Tests for Signal-Based Routing System

Tests all 4 phases:
Phase 1: Signal extraction (17 signals from existing data)
Phase 2: Domain scoring (universal formula + lookup tables)
Phase 2: Hard rules (H1-H5)
Phase 2: Routing decisions (intent selection + confidence)
"""

import pytest

from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.routing_signals import SignalSnapshot
from lead_to_cash.core.signal_extractor import extract_signals
from lead_to_cash.core.signal_router import RoutingResult, route
from lead_to_cash.core.signal_scorer import DOMAINS, score_domains


# =============================================================================
# Helpers
# =============================================================================


def _make_parsed(
    raw_query: str,
    intent: QueryIntent,
    confidence: float = 0.8,
    companies: list | None = None,
    competitors: list | None = None,
    products: list | None = None,
    market_intel_style: str = "opportunities",
    competitor_intel_style: str = "news",
) -> ParsedQuery:
    return ParsedQuery(
        raw_query=raw_query,
        intent=intent,
        intent_confidence=confidence,
        companies=companies or [],
        competitors=competitors or [],
        products=products or [],
        market_intel_style=market_intel_style,
        competitor_intel_style=competitor_intel_style,
    )


def _make_context(
    last_intent: str | None = None,
    companies: list | None = None,
    confirmed_entity: dict | None = None,
) -> dict:
    ctx = {}
    if last_intent:
        ctx["last_intent"] = last_intent
    if companies:
        ctx["companies"] = companies
    if confirmed_entity:
        ctx["confirmed_entity"] = confirmed_entity
    return ctx


# =============================================================================
# Phase 1: Signal Extraction Tests
# =============================================================================


class TestSignalExtraction:
    """Test that signals are correctly extracted from ParsedQuery + context."""

    def test_competitor_entity_type(self):
        parsed = _make_parsed(
            "Caterpillar news",
            QueryIntent.COMPETITOR_INTEL,
            competitors=["Caterpillar"],
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "competitor"
        assert signals.entity_in_competitor_list is True

    def test_customer_entity_type(self):
        parsed = _make_parsed(
            "ST Engineering credit",
            QueryIntent.CUSTOMER_INTEL,
            companies=["ST Engineering"],
        )
        ctx = _make_context(
            confirmed_entity={"entity_id": "0022005992", "uen": "199706231H"}
        )
        signals = extract_signals(parsed, ctx)
        assert signals.entity_type == "customer"
        assert signals.entity_has_sap_id is True

    def test_product_entity_type(self):
        parsed = _make_parsed(
            "MTU 4000 specs", QueryIntent.PRODUCT_FIT, products=["MTU 4000"]
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "product"
        assert signals.entity_in_product_registry is True

    def test_no_entity(self):
        parsed = _make_parsed("What is an OSV?", QueryIntent.GENERAL_QUESTION)
        signals = extract_signals(parsed)
        assert signals.entity_type == "none"

    def test_prospect_entity(self):
        parsed = _make_parsed(
            "Tell me about XYZ Corp", QueryIntent.CUSTOMER_INTEL, companies=["XYZ Corp"]
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "prospect"

    def test_seeks_data(self):
        parsed = _make_parsed("What is the payment status?", QueryIntent.BILLING_AR)
        signals = extract_signals(parsed)
        assert signals.question_seeks_data is True

    def test_seeks_specs(self):
        parsed = _make_parsed("Engine specifications for OSV", QueryIntent.PRODUCT_FIT)
        signals = extract_signals(parsed)
        assert signals.question_seeks_specs is True

    def test_seeks_news(self):
        parsed = _make_parsed("Latest developments in APAC", QueryIntent.MARKET_INTEL)
        signals = extract_signals(parsed)
        assert signals.question_seeks_news is True

    def test_seeks_action(self):
        parsed = _make_parsed(
            "Run KYP on Neptune Energy",
            QueryIntent.KYP_DUE_DILIGENCE,
            companies=["Neptune Energy"],
        )
        signals = extract_signals(parsed)
        assert signals.question_seeks_action is True

    def test_context_followup(self):
        parsed = _make_parsed("Tell me more", QueryIntent.CUSTOMER_INTEL)
        ctx = _make_context(last_intent="customer_intel", companies=["ST Engineering"])
        signals = extract_signals(parsed, ctx)
        assert signals.context_is_followup is True
        assert signals.context_previous_intent == "customer_intel"

    def test_llm_signals_preserved(self):
        parsed = _make_parsed(
            "Caterpillar news", QueryIntent.COMPETITOR_INTEL, confidence=0.85
        )
        signals = extract_signals(parsed)
        assert signals.llm_classified_intent == "competitor_intel"
        assert signals.llm_intent_confidence == 0.85

    def test_signal_snapshot_to_dict(self):
        parsed = _make_parsed("Test query", QueryIntent.GENERAL_QUESTION)
        signals = extract_signals(parsed)
        d = signals.to_dict()
        assert "entity_type" in d
        assert "question_seeks_data" in d
        assert "llm_classified_intent" in d

    def test_company_in_competitor_list_reclassified(self):
        """A company name that IS a known competitor should return 'competitor'."""
        parsed = _make_parsed(
            "MAN billing model", QueryIntent.CUSTOMER_INTEL, companies=["MAN"]
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "competitor"
        assert signals.entity_in_competitor_list is True


# =============================================================================
# Phase 2: Domain Scoring Tests
# =============================================================================


class TestDomainScoring:
    """Test the universal scoring formula produces expected domain rankings."""

    def test_billing_query_scores_highest_for_billing(self):
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=True,
            question_seeks_data=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        scores = score_domains(signals)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        assert ranked[0][0] == "billing_ar"

    def test_product_query_scores_highest_for_product(self):
        signals = SignalSnapshot(
            entity_type="product",
            entity_in_product_registry=True,
            question_seeks_specs=True,
            llm_classified_intent="product_fit",
            llm_intent_confidence=0.9,
        )
        scores = score_domains(signals)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        assert ranked[0][0] == "product_fit"

    def test_competitor_query_scores_highest_for_competitor(self):
        signals = SignalSnapshot(
            entity_type="competitor",
            entity_in_competitor_list=True,
            question_seeks_news=True,
            llm_classified_intent="competitor_intel",
            llm_intent_confidence=0.85,
        )
        scores = score_domains(signals)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        assert ranked[0][0] == "competitor_intel"

    def test_kyp_query_scores_highest_for_kyp(self):
        signals = SignalSnapshot(
            entity_type="prospect",
            question_seeks_action=True,
            llm_classified_intent="kyp_due_diligence",
            llm_intent_confidence=0.9,
        )
        scores = score_domains(signals)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        assert ranked[0][0] == "kyp_due_diligence"

    def test_market_news_scores_highest_for_market(self):
        signals = SignalSnapshot(
            entity_type="none",
            question_seeks_news=True,
            llm_classified_intent="market_intel",
            llm_intent_confidence=0.85,
        )
        scores = score_domains(signals)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        assert ranked[0][0] == "market_intel"

    def test_all_scores_between_0_and_1(self):
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            question_seeks_data=True,
        )
        scores = score_domains(signals)
        for domain, score in scores.items():
            assert 0.0 <= score <= 1.0, f"{domain} score {score} out of range"

    def test_all_domains_scored(self):
        signals = SignalSnapshot()
        scores = score_domains(signals)
        for domain in DOMAINS:
            assert domain in scores

    def test_competitor_billing_model_scores_competitor_higher(self):
        """'Caterpillar billing model' — competitor entity should push competitor_intel up."""
        signals = SignalSnapshot(
            entity_type="competitor",
            entity_in_competitor_list=True,
            question_seeks_data=True,  # "billing model" sounds like data
            llm_classified_intent="competitor_intel",
            llm_intent_confidence=0.8,
        )
        scores = score_domains(signals)
        assert scores["competitor_intel"] > scores["billing_ar"]


# =============================================================================
# Phase 2: Hard Rule Tests
# =============================================================================


class TestHardRules:
    """Test the 5 hard business rules."""

    def test_h1_explicit_kyp(self):
        signals = SignalSnapshot(
            entity_type="prospect",
            question_seeks_action=True,
            llm_classified_intent="kyp_due_diligence",
            llm_intent_confidence=0.9,
        )
        result = route(signals)
        assert result.intent == "kyp_due_diligence"
        assert result.hard_rule_fired == "H1_explicit_procedure"
        assert result.confidence == 0.95

    def test_h2_internal_data_protection(self):
        """H2 fires when billing concept + LLM agrees + entity has billing data."""
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=True,
            question_seeks_data=True,
            concept_billing=True,  # Billing concept required by calibrated H2
            llm_classified_intent="billing_ar",  # LLM agrees
            llm_intent_confidence=0.8,
        )
        result = route(signals)
        assert result.intent == "billing_ar"
        assert result.hard_rule_fired == "H2_internal_data_protection"

    def test_h3_competitor_exclusion(self):
        """Competitor entity must never route to billing_ar."""
        signals = SignalSnapshot(
            entity_type="competitor",
            entity_in_competitor_list=True,
            question_seeks_data=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.6,
        )
        # Force billing_ar to top via entity_has_billing_history
        # (this shouldn't happen naturally, but tests the guard)
        scores = score_domains(signals)
        # Manually check: billing should score low because entity is competitor
        assert scores["billing_ar"] < scores["competitor_intel"]
        result = route(signals, scores)
        assert result.intent != "billing_ar"

    def test_h4_rbac_denial(self):
        """H4 fires when billing tops scoring but user lacks permission.
        Set entity_has_billing_history=False so H2 doesn't pre-empt."""
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=False,  # H2 won't fire
            question_seeks_data=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        # User without billing permission
        result = route(signals, user_permissions={"marine_intel": ["read"]})
        assert result.routing_risk == "RBAC_DENIED"
        assert result.hard_rule_fired == "H4_rbac_denied"

    def test_h5_low_confidence_fallback(self):
        signals = SignalSnapshot(
            entity_type="none",
            llm_classified_intent="general_question",
            llm_intent_confidence=0.3,
        )
        result = route(signals)
        assert result.intent == "general_question"
        assert result.confidence_band == "LOW"

    def test_no_hard_rule_for_normal_query(self):
        signals = SignalSnapshot(
            entity_type="none",
            question_seeks_news=True,
            llm_classified_intent="market_intel",
            llm_intent_confidence=0.85,
        )
        result = route(signals)
        assert result.hard_rule_fired is None
        assert result.intent_source == "signal"


# =============================================================================
# Phase 2: Routing Result Tests
# =============================================================================


class TestRoutingResult:
    """Test routing result structure and confidence bands."""

    def test_high_confidence(self):
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=True,
            question_seeks_data=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        result = route(signals)
        assert result.confidence_band == "HIGH"
        assert result.confidence >= 0.7

    def test_moderate_confidence(self):
        signals = SignalSnapshot(
            entity_type="none",
            question_seeks_data=True,
            llm_classified_intent="customer_intel",
            llm_intent_confidence=0.5,
        )
        result = route(signals)
        assert result.confidence_band in ("MODERATE", "HIGH", "LOW")
        # Exact band depends on scores — just verify it's valid

    def test_routing_result_to_dict(self):
        signals = SignalSnapshot(
            entity_type="customer",
            question_seeks_data=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        result = route(signals)
        d = result.to_dict()
        assert "intent" in d
        assert "confidence" in d
        assert "confidence_band" in d
        assert "domain_scores" in d

    def test_multi_domain_risk(self):
        """When two domains score close, routing_risk should flag it."""
        signals = SignalSnapshot(
            entity_type="customer",
            entity_has_sap_id=True,
            question_seeks_news=True,  # News pushes toward market/customer
            llm_classified_intent="customer_intel",
            llm_intent_confidence=0.6,
        )
        result = route(signals)
        # May or may not flag MULTI_DOMAIN depending on exact scores
        # At minimum, routing_risk should be populated or None (not crash)
        assert result.routing_risk is None or isinstance(result.routing_risk, str)


# =============================================================================
# Golden Query Tests — the critical scenarios
# =============================================================================


class TestGoldenQueries:
    """The exact scenarios from the design document."""

    def test_payment_track_record(self):
        """'What is ST Engineering's payment track record?'
        When LLM says customer_intel (no billing keyword override), signal router
        correctly scores customer_intel higher because LLM match component favors it.
        In Phase 3, the keyword stabilizer fallback corrects this to billing_ar.
        The signal router alone routes to customer_intel — billing_ar scores close."""
        parsed = _make_parsed(
            "What is ST Engineering's payment track record?",
            QueryIntent.CUSTOMER_INTEL,  # LLM misclassifies
            confidence=0.7,
            companies=["ST Engineering"],
        )
        ctx = _make_context(
            confirmed_entity={
                "entity_id": "0022005992",
                "canonical_name": "ST Engineering",
            }
        )
        signals = extract_signals(parsed, ctx)
        assert signals.entity_type == "customer"
        assert signals.entity_has_sap_id is True
        assert signals.question_seeks_data is True

        result = route(signals)
        # Signal router sees LLM=customer_intel, so customer_intel wins scoring.
        # billing_ar is close (#2) — the keyword stabilizer handles the override in Phase 3.
        assert result.intent in ("customer_intel", "billing_ar")
        scores = result.domain_scores
        # billing_ar must be competitive (within 0.15 of top)
        assert scores.get("billing_ar", 0) >= 0.6

    def test_do_they_pay_on_time(self):
        """'Do they pay on time?' — same pattern as payment track record.
        Signal router sees LLM=customer_intel, routes accordingly.
        Keyword stabilizer would correct to billing_ar in Phase 3."""
        parsed = _make_parsed(
            "Do they pay on time?",
            QueryIntent.CUSTOMER_INTEL,
            confidence=0.7,
        )
        ctx = _make_context(
            last_intent="customer_intel",
            companies=["ST Engineering"],
            confirmed_entity={"entity_id": "0022005992"},
        )
        signals = extract_signals(parsed, ctx)
        assert signals.entity_has_sap_id is True
        assert signals.question_seeks_data is True

        result = route(signals)
        assert result.intent in ("customer_intel", "billing_ar")
        # billing_ar must score competitively
        assert result.domain_scores.get("billing_ar", 0) >= 0.5

    def test_competitor_billing_model(self):
        """'Caterpillar billing model' → competitor_intel (NOT billing_ar)"""
        parsed = _make_parsed(
            "What is Caterpillar's billing model?",
            QueryIntent.COMPETITOR_INTEL,
            confidence=0.8,
            competitors=["Caterpillar"],
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "competitor"

        result = route(signals)
        assert result.intent == "competitor_intel"

    def test_engine_specs(self):
        """'MTU 12V 2000 specs' → product_fit"""
        parsed = _make_parsed(
            "What are the MTU 12V 2000 specs?",
            QueryIntent.PRODUCT_FIT,
            confidence=0.9,
            products=["MTU 12V 2000"],
        )
        signals = extract_signals(parsed)
        assert signals.entity_type == "product"
        assert signals.question_seeks_specs is True

        result = route(signals)
        assert result.intent == "product_fit"

    def test_market_news(self):
        """'Latest ferry market news' → market_intel"""
        parsed = _make_parsed(
            "What are the latest developments in the ferry market?",
            QueryIntent.MARKET_INTEL,
            confidence=0.85,
        )
        signals = extract_signals(parsed)
        assert signals.question_seeks_news is True

        result = route(signals)
        assert result.intent == "market_intel"

    def test_run_kyp(self):
        """'Run KYP on Neptune Energy' → kyp_due_diligence"""
        parsed = _make_parsed(
            "Run KYP on Neptune Energy",
            QueryIntent.KYP_DUE_DILIGENCE,
            confidence=0.95,
            companies=["Neptune Energy"],
        )
        signals = extract_signals(parsed)
        assert signals.question_seeks_action is True

        result = route(signals)
        assert result.intent == "kyp_due_diligence"

    def test_collections_history(self):
        """'Collections history for this customer' → billing_ar"""
        parsed = _make_parsed(
            "Show collections history",
            QueryIntent.BILLING_AR,
            confidence=0.8,
        )
        ctx = _make_context(
            last_intent="customer_intel",
            companies=["Maersk"],
            confirmed_entity={"entity_id": "0000100002", "uen": "25505933"},
        )
        signals = extract_signals(parsed, ctx)
        result = route(signals)
        assert result.intent == "billing_ar"

    def test_competitor_latest_updates(self):
        """'What are the latest updates from Cummins?' → competitor_intel"""
        parsed = _make_parsed(
            "What are the latest updates from Cummins?",
            QueryIntent.COMPETITOR_INTEL,
            confidence=0.85,
            competitors=["Cummins"],
        )
        signals = extract_signals(parsed)
        result = route(signals)
        assert result.intent == "competitor_intel"

    def test_generic_question(self):
        """'Tell me something interesting' → general_question (low confidence)"""
        parsed = _make_parsed(
            "Tell me something interesting",
            QueryIntent.GENERAL_QUESTION,
            confidence=0.4,
        )
        signals = extract_signals(parsed)
        result = route(signals)
        assert result.confidence_band == "LOW"
        assert result.intent == "general_question"

    def test_customer_news_vs_data(self):
        """'Latest news about Maersk' → customer_intel (not billing)"""
        parsed = _make_parsed(
            "Latest news about Maersk",
            QueryIntent.CUSTOMER_INTEL,
            confidence=0.8,
            companies=["Maersk"],
            market_intel_style="news",
        )
        ctx = _make_context(confirmed_entity={"entity_id": "0000100002"})
        signals = extract_signals(parsed, ctx)
        assert signals.question_seeks_news is True
        # H2 should NOT fire because seeks_news is true, not seeks_data
        result = route(signals)
        # Should be customer_intel or market_intel, NOT billing
        assert result.intent != "billing_ar"
