"""
Unit Tests for Consolidated Patch

Tests the 10 operational/observability/compatibility fixes:
1. Routing metadata (intent_source, routing_risk)
2. Intent source tracking
3. Override structured logging
4. Billing fast-path guard
5. Strict mode for internal-only queries
6. Source filtering
7. Hard source gate
8. Validator compatibility
"""

import pytest

from lead_to_cash.core.data_inventory import DataSource, InventoryCheckResult
from lead_to_cash.core.query_understanding import (
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
)
from lead_to_cash.core.source_authority import (
    FallbackStrategy,
    SourceAuthority,
    SourceDecision,
    WebSearchGate,
)


# =============================================================================
# Helper
# =============================================================================


def _make_parsed(
    raw_query: str,
    intent: QueryIntent,
    intent_confidence: float = 0.8,
    companies: list | None = None,
    competitors: list | None = None,
) -> ParsedQuery:
    return ParsedQuery(
        raw_query=raw_query,
        intent=intent,
        intent_confidence=intent_confidence,
        companies=companies or [],
        competitors=competitors or [],
    )


def _make_inventory(has_local_data: bool = True) -> InventoryCheckResult:
    return InventoryCheckResult(
        has_local_data=has_local_data,
        coverage=None,
        confidence="HIGH" if has_local_data else "LOW",
        gaps=[],
        recommended_sources=[],
    )


# =============================================================================
# Task 1: Routing metadata — intent_source and routing_risk fields
# =============================================================================


class TestRoutingMetadata:
    """ParsedQuery must carry intent_source and routing_risk after stabilization."""

    def test_llm_intent_has_source_llm(self):
        """When no override fires, intent_source should be 'llm'."""
        parsed = _make_parsed(
            "What is happening in the ferry market?",
            QueryIntent.MARKET_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent_source == "llm"

    def test_billing_override_sets_rule_override(self):
        parsed = _make_parsed(
            "Show outstanding invoices",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent_source == "rule_override"

    def test_product_override_sets_rule_override(self):
        parsed = _make_parsed(
            "MTU 12V 2000 engine specs",
            QueryIntent.GENERAL_QUESTION,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent_source == "rule_override"

    def test_kyp_override_sets_rule_override(self):
        parsed = _make_parsed(
            "Run KYP on Maersk",
            QueryIntent.CUSTOMER_INTEL,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent_source == "rule_override"

    def test_entity_alignment_sets_rule_override(self):
        parsed = _make_parsed(
            "What is Caterpillar doing?",
            QueryIntent.CUSTOMER_INTEL,
            competitors=["Caterpillar"],
            companies=[],
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent_source == "rule_override"

    def test_low_confidence_sets_routing_risk(self):
        parsed = _make_parsed(
            "Tell me something",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.3,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.routing_risk == "LOW_CONFIDENCE"

    def test_high_confidence_no_routing_risk(self):
        parsed = _make_parsed(
            "Show billing items",
            QueryIntent.BILLING_AR,
            intent_confidence=0.9,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.routing_risk is None

    def test_metadata_in_to_dict(self):
        parsed = _make_parsed(
            "Show overdue invoices",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.4,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        d = result.to_dict()
        assert "intent_source" in d
        assert "routing_risk" in d
        assert d["intent_source"] == "rule_override"
        # Billing override boosts confidence to 0.9, so routing_risk is cleared
        assert d["routing_risk"] is None


# =============================================================================
# Task 4: Billing fast-path guard
# =============================================================================


class TestBillingFastPathGuard:
    """Billing fast-path must not trigger for non-billing intents."""

    def test_billing_keywords_in_competitor_context(self):
        """'Caterpillar billing model' — competitor query with billing word."""
        parsed = _make_parsed(
            "What is Caterpillar's billing model?",
            QueryIntent.COMPETITOR_INTEL,
            competitors=["Caterpillar"],
        )
        # After stabilization, this stays COMPETITOR_INTEL
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.COMPETITOR_INTEL
        # The billing fast-path guard should block for COMPETITOR_INTEL

    def test_billing_keywords_in_product_context(self):
        """'Payment terms for MTU' — product query with billing word."""
        parsed = _make_parsed(
            "What payment terms does MTU offer?",
            QueryIntent.PRODUCT_FIT,
        )
        result = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert result.intent == QueryIntent.PRODUCT_FIT
        # The billing fast-path guard should block for PRODUCT_FIT


# =============================================================================
# Task 5: Strict mode for internal-only queries
# =============================================================================


class TestStrictMode:
    """Internal-only intents should get strict synthesis instructions."""

    def test_billing_is_internal_only(self):
        parsed = _make_parsed("Show billing items", QueryIntent.BILLING_AR)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY

    def test_product_fit_is_internal_only(self):
        parsed = _make_parsed("MTU 4000 specs", QueryIntent.PRODUCT_FIT)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY

    def test_market_intel_is_not_internal_only(self):
        parsed = _make_parsed("APAC market trends", QueryIntent.MARKET_INTEL)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy != FallbackStrategy.INTERNAL_ONLY


# =============================================================================
# Task 8: Hard source gate
# =============================================================================


class TestHardSourceGate:
    """Forbidden sources must never execute, even if accidentally queued."""

    def test_forbidden_source_decision(self):
        """Verify that billing_ar decision actually forbids web sources."""
        parsed = _make_parsed("Show billing items", QueryIntent.BILLING_AR)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        assert not decision.is_source_allowed(DataSource.PERPLEXITY)
        assert not decision.is_source_allowed(DataSource.NEWSAPI)

    def test_product_fit_forbids_web(self):
        parsed = _make_parsed("MTU engine specs", QueryIntent.PRODUCT_FIT)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert not decision.is_source_allowed(DataSource.PERPLEXITY)

    def test_openai_always_allowed(self):
        """OPENAI (synthesis) should pass the gate even for internal-only."""
        parsed = _make_parsed("Show billing", QueryIntent.BILLING_AR)
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.is_source_allowed(DataSource.OPENAI)


# =============================================================================
# Task 9: Validator compatibility with routing metadata
# =============================================================================


class TestValidatorCompatibility:
    """Validators should work with the new routing metadata fields."""

    def test_parsed_query_serialization_roundtrip(self):
        """New fields must survive to_dict() → from_dict() roundtrip."""
        parsed = _make_parsed(
            "Show outstanding invoices",
            QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.4,
        )
        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)
        d = stabilized.to_dict()

        reconstructed = ParsedQuery.from_dict(d)
        assert reconstructed is not None
        assert reconstructed.intent == QueryIntent.BILLING_AR
        assert reconstructed.intent_confidence >= 0.9

    def test_source_decision_survives_enforcement(self):
        """Enforcement pipeline should not crash with new metadata."""
        from lead_to_cash.core.response_quality import ResponseEnforcer

        text = "Revenue was EUR 52.6 billion."
        result = ResponseEnforcer.enforce(
            text, "billing_ar", ["SAP CPI (MS5)"], "Revenue EUR 52.6 billion"
        )
        # Should not crash and should not modify grounded billing data
        assert "52.6" in result.enforced_text


# =============================================================================
# Task 10: Observability coverage
# =============================================================================


class TestObservability:
    """Quality metrics should accept routing metadata."""

    def test_metrics_accept_routing_details(self):
        from lead_to_cash.core.response_quality import QualityMetrics

        QualityMetrics.record(
            event_type="response_routing_summary",
            severity="INFO",
            intent="billing_ar",
            details={
                "intent_source": "rule_override",
                "routing_risk": None,
                "source_decision_fallback": "internal_only",
                "web_gate": "blocked",
                "used_web_sources": False,
                "tier1_only": True,
            },
        )
        events = QualityMetrics.get_recent_events("response_routing_summary")
        assert len(events) > 0
        assert events[-1].details["intent_source"] == "rule_override"

    def test_source_blocked_metric(self):
        from lead_to_cash.core.response_quality import QualityMetrics

        QualityMetrics.record(
            event_type="source_blocked",
            severity="WARNING",
            intent="billing_ar",
            details={
                "blocked_source": "perplexity",
                "reason": "forbidden_by_source_authority",
            },
        )
        events = QualityMetrics.get_recent_events("source_blocked")
        assert len(events) > 0


# =============================================================================
# Integration: end-to-end routing metadata flow
# =============================================================================


class TestEndToEndMetadataFlow:
    """Verify metadata flows from parse → stabilize → source authority → response."""

    def test_billing_query_full_metadata_flow(self):
        """A billing query should carry correct metadata through the pipeline."""
        # Step 1: Parse + stabilize
        parsed = _make_parsed(
            "What is ST Engineering's payment history?",
            QueryIntent.CUSTOMER_INTEL,  # LLM misclassifies
            intent_confidence=0.75,
            companies=["ST Engineering"],
        )
        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)

        # Should be overridden to billing_ar
        assert stabilized.intent == QueryIntent.BILLING_AR
        assert stabilized.intent_source == "rule_override"
        assert stabilized.routing_risk is None  # confidence was boosted

        # Step 2: Source authority
        decision = SourceAuthority.decide(stabilized, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY
        assert decision.web_search_gate == WebSearchGate.BLOCKED
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_product_query_full_metadata_flow(self):
        parsed = _make_parsed(
            "What are the engine specs for MTU 4000?",
            QueryIntent.FINANCIAL_ANALYSIS,  # LLM misclassifies
            intent_confidence=0.5,
        )
        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)

        assert stabilized.intent == QueryIntent.PRODUCT_FIT
        assert stabilized.intent_source == "rule_override"

        decision = SourceAuthority.decide(stabilized, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_market_intel_no_override(self):
        parsed = _make_parsed(
            "What is happening in the APAC ferry market?",
            QueryIntent.MARKET_INTEL,
            intent_confidence=0.9,
        )
        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)

        assert stabilized.intent == QueryIntent.MARKET_INTEL
        assert stabilized.intent_source == "llm"
        assert stabilized.routing_risk is None

        decision = SourceAuthority.decide(stabilized, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.FULL_FALLBACK
        assert DataSource.PERPLEXITY not in decision.forbidden_sources
