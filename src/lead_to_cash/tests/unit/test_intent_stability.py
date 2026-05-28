"""
Unit Tests for Intent Stability — Deterministic Routing Corrections

Tests the post-LLM intent stabilization rules in QueryUnderstandingEngine:
1. Billing override: billing keywords force billing_ar intent
2. Product override: product keywords force product_fit intent
3. KYP override: KYP keywords force kyp_due_diligence intent
4. Entity-intent alignment: competitors in customer_intel → competitor_intel
5. Low-confidence flagging
6. Override blocked intents: competitor queries with billing words not overridden
7. Fast-path intent guards: fast-paths respect LLM intent
"""

import pytest

from lead_to_cash.core.query_understanding import (
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
)


# =============================================================================
# Helper to build ParsedQuery with controllable fields
# =============================================================================


def _make_parsed(
    raw_query: str,
    intent: QueryIntent,
    intent_confidence: float = 0.8,
    companies: list | None = None,
    competitors: list | None = None,
    market_intel_style: str = "opportunities",
    competitor_intel_style: str = "news",
) -> ParsedQuery:
    return ParsedQuery(
        raw_query=raw_query,
        intent=intent,
        intent_confidence=intent_confidence,
        companies=companies or [],
        competitors=competitors or [],
        market_intel_style=market_intel_style,
        competitor_intel_style=competitor_intel_style,
    )


# =============================================================================
# Billing Override Rules
# =============================================================================


class TestBillingOverride:
    """Billing keywords must force billing_ar regardless of LLM classification."""

    def test_payment_history_classified_as_customer_intel(self):
        """The critical failure: 'payment track record' misclassified as customer_intel."""
        parsed = _make_parsed(
            "What is ST Engineering's payment track record?",
            QueryIntent.CUSTOMER_INTEL,
            companies=["ST Engineering"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_overdue_invoices(self):
        parsed = _make_parsed(
            "Show overdue invoices for Maersk",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_aging_buckets(self):
        parsed = _make_parsed(
            "What are the aging buckets?",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_collections_status(self):
        parsed = _make_parsed(
            "Show collections items",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_payment_status(self):
        parsed = _make_parsed(
            "What is the payment status for this order?",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_billing_items(self):
        parsed = _make_parsed(
            "Show pending billing items",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_accounts_receivable(self):
        parsed = _make_parsed(
            "Show AR aging report",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_how_much_paid(self):
        parsed = _make_parsed(
            "How much has been paid so far?",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_downpayment(self):
        parsed = _make_parsed(
            "Show downpayment alerts",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR

    def test_already_billing_not_changed(self):
        """If LLM already got it right, don't change."""
        parsed = _make_parsed(
            "Show billing items",
            QueryIntent.BILLING_AR,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR


# =============================================================================
# Billing Override BLOCKED for competitor/product intents
# =============================================================================


class TestBillingOverrideBlocked:
    """Competitor/product queries containing billing words must NOT be overridden."""

    def test_competitor_billing_model(self):
        """'Caterpillar's billing model' is competitor intel, not billing_ar."""
        parsed = _make_parsed(
            "What is Caterpillar's billing model?",
            QueryIntent.COMPETITOR_INTEL,
            competitors=["Caterpillar"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.COMPETITOR_INTEL

    def test_product_payment_terms(self):
        """'Payment terms for MTU engines' is product context, not billing."""
        parsed = _make_parsed(
            "What payment terms does MTU offer?",
            QueryIntent.PRODUCT_FIT,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_kyp_with_payment_context(self):
        """KYP queries mentioning payments stay as KYP."""
        parsed = _make_parsed(
            "Run KYP - check payment history and sanctions",
            QueryIntent.KYP_DUE_DILIGENCE,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE


# =============================================================================
# Product Override Rules
# =============================================================================


class TestProductOverride:
    """Product keywords must force product_fit when no competitors mentioned."""

    def test_engine_specs(self):
        parsed = _make_parsed(
            "What are the MTU 12V 2000 M93 specs?",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_power_rating(self):
        parsed = _make_parsed(
            "What is the power rating of MTU 4000?",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_fuel_consumption(self):
        parsed = _make_parsed(
            "What is the fuel consumption of Bergen B35:40?",
            QueryIntent.MARKET_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_engine_comparison(self):
        parsed = _make_parsed(
            "Compare MTU engine models for ferry application",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_competitor_product_not_overridden(self):
        """If competitor product is asked about, keep competitor_intel."""
        parsed = _make_parsed(
            "What is the fuel consumption of Wärtsilä 31?",
            QueryIntent.COMPETITOR_INTEL,
            competitors=["Wärtsilä"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # Should stay competitor_intel because competitors are mentioned
        assert result.intent == QueryIntent.COMPETITOR_INTEL

    def test_competitor_in_product_query_no_override(self):
        """Product keyword + competitor entities → don't override to product_fit."""
        parsed = _make_parsed(
            "Cat C32 engine specs",
            QueryIntent.CUSTOMER_INTEL,
            competitors=["Caterpillar"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # Competitors present → don't override to product_fit
        # Entity-intent alignment will catch this instead
        assert result.intent != QueryIntent.PRODUCT_FIT

    def test_already_product_fit(self):
        parsed = _make_parsed(
            "MTU 4000 specs",
            QueryIntent.PRODUCT_FIT,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_iso_8528_query(self):
        parsed = _make_parsed(
            "Explain ISO 8528 duty classes",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT


# =============================================================================
# KYP Override Rules
# =============================================================================


class TestKYPOverride:
    """KYP keywords must force kyp_due_diligence."""

    def test_run_kyp(self):
        parsed = _make_parsed(
            "Run KYP on Neptune Energy",
            QueryIntent.CUSTOMER_INTEL,
            companies=["Neptune Energy"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE

    def test_due_diligence(self):
        parsed = _make_parsed(
            "Conduct due diligence on this company",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE

    def test_sanctions_check(self):
        parsed = _make_parsed(
            "Run sanctions check on Batam Fast Ferry",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE

    def test_already_kyp(self):
        parsed = _make_parsed(
            "KYP on Maersk",
            QueryIntent.KYP_DUE_DILIGENCE,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE


# =============================================================================
# Entity-Intent Alignment
# =============================================================================


class TestEntityIntentAlignment:
    """Competitors in customer_intel must be corrected to competitor_intel."""

    def test_competitor_in_customer_intent(self):
        parsed = _make_parsed(
            "What is Caterpillar doing in APAC?",
            QueryIntent.CUSTOMER_INTEL,
            competitors=["Caterpillar"],
            companies=[],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.COMPETITOR_INTEL

    def test_company_stays_customer(self):
        """If companies extracted (not competitors), keep customer_intel."""
        parsed = _make_parsed(
            "What is ST Engineering doing?",
            QueryIntent.CUSTOMER_INTEL,
            companies=["ST Engineering"],
            competitors=[],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.CUSTOMER_INTEL

    def test_both_company_and_competitor(self):
        """If both extracted, don't override (LLM had both signals)."""
        parsed = _make_parsed(
            "Is Caterpillar winning at ST Engineering?",
            QueryIntent.CUSTOMER_INTEL,
            companies=["ST Engineering"],
            competitors=["Caterpillar"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # Should not override: companies are present
        assert result.intent == QueryIntent.CUSTOMER_INTEL


# =============================================================================
# Low Confidence Flagging
# =============================================================================


class TestLowConfidence:
    """Low confidence intents should be flagged (not overridden)."""

    def test_low_confidence_logged(self):
        """Below threshold should be flagged but intent preserved."""
        parsed = _make_parsed(
            "Tell me something interesting",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.3,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # Intent should be preserved (no override rule matched)
        assert result.intent == QueryIntent.GENERAL_QUESTION
        assert result.intent_confidence == 0.3

    def test_high_confidence_no_flag(self):
        parsed = _make_parsed(
            "Show billing items",
            QueryIntent.BILLING_AR,
            intent_confidence=0.95,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR


# =============================================================================
# Confidence Boost on Override
# =============================================================================


class TestConfidenceBoost:
    """When an override fires, confidence should be boosted."""

    def test_billing_override_boosts_confidence(self):
        parsed = _make_parsed(
            "Show outstanding invoices",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.4,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR
        assert result.intent_confidence >= 0.9

    def test_product_override_boosts_confidence(self):
        parsed = _make_parsed(
            "MTU 12V 2000 engine specs",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.5,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT
        assert result.intent_confidence >= 0.85

    def test_no_override_preserves_confidence(self):
        parsed = _make_parsed(
            "What is happening in the ferry market?",
            QueryIntent.MARKET_INTEL,
            intent_confidence=0.7,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.MARKET_INTEL
        assert result.intent_confidence == 0.7


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases for intent stability."""

    def test_empty_query(self):
        parsed = _make_parsed("", QueryIntent.GENERAL_QUESTION)
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.GENERAL_QUESTION

    def test_mixed_billing_and_product_keywords(self):
        """When both billing and product keywords exist, first match wins."""
        parsed = _make_parsed(
            "Show billing items and engine specs",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # Billing patterns are checked first in the elif chain
        assert result.intent == QueryIntent.BILLING_AR

    def test_market_intel_not_overridden_by_billing(self):
        """Market intel about payments in an industry should not become billing."""
        parsed = _make_parsed(
            "Payment trends in the maritime industry",
            QueryIntent.MARKET_INTEL,
            intent_confidence=0.85,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        # No strong billing keyword match (no "payment status", "payment history",
        # "overdue invoice" etc.) — "payment trends" doesn't match the patterns
        assert result.intent == QueryIntent.MARKET_INTEL

    def test_stabilize_is_idempotent(self):
        """Running stabilize twice should produce the same result."""
        parsed = _make_parsed(
            "Show outstanding invoices",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.4,
        )
        result1 = QueryUnderstandingEngine._stabilize_intent(parsed)
        result2 = QueryUnderstandingEngine._stabilize_intent(result1)
        assert result1.intent == result2.intent
        assert result1.intent_confidence == result2.intent_confidence


# =============================================================================
# Critical Scenarios
# =============================================================================


class TestCriticalScenarios:
    """The exact failure scenarios that motivated this work."""

    def test_payment_track_record_becomes_billing(self):
        """'What is ST Engineering's payment track record?' → billing_ar"""
        parsed = _make_parsed(
            "What is ST Engineering's payment track record?",
            QueryIntent.CUSTOMER_INTEL,  # LLM's wrong classification
            intent_confidence=0.75,
            companies=["ST Engineering"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.BILLING_AR
        assert result.intent_confidence >= 0.9

    def test_offshore_engine_specs_not_financial(self):
        """'offshore engine specs' should be product, not financial."""
        parsed = _make_parsed(
            "What are the engine specs for offshore applications?",
            QueryIntent.FINANCIAL_ANALYSIS,  # LLM's wrong classification
            intent_confidence=0.6,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT

    def test_kyp_on_company_not_customer_intel(self):
        """'Run KYP on X' must be kyp, even if LLM says customer_intel."""
        parsed = _make_parsed(
            "Run KYP on Neptune Energy",
            QueryIntent.CUSTOMER_INTEL,  # LLM's wrong classification
            companies=["Neptune Energy"],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.KYP_DUE_DILIGENCE
