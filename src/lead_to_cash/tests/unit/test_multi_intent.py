"""
Unit Tests for Multi-Intent Query System

Tests:
1. Multi-intent detection (comparison, concept co-occurrence, conjunction)
2. Response composition (comparison, summary, sequential)
3. Edge cases (single intent, ambiguous, partial failure)
"""

import pytest

from lead_to_cash.core.compound_executor import CompoundResult, SubIntentResult
from lead_to_cash.core.multi_intent_detector import (
    CompoundQuery,
    MultiIntentDetector,
    SubIntent,
)
from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.response_composer import ResponseComposer
from lead_to_cash.core.routing_signals import SignalSnapshot
from lead_to_cash.core.signal_scorer import score_domains


# =============================================================================
# Helpers
# =============================================================================


def _make_signals(**kwargs) -> SignalSnapshot:
    return SignalSnapshot(**kwargs)


def _detect(query: str, **signal_kwargs) -> CompoundQuery:
    signals = _make_signals(**signal_kwargs)
    scores = score_domains(signals)
    return MultiIntentDetector.detect(query, signals, scores)


# =============================================================================
# Detection Tests
# =============================================================================


class TestComparisonDetection:
    """Test comparison pattern detection."""

    def test_compare_mtu_vs_caterpillar(self):
        result = _detect(
            "Compare MTU 4000 vs Caterpillar 3516 for ferry applications",
            entity_type="product",
            entity_in_product_registry=True,
            question_seeks_specs=True,
            concept_product=True,
            concept_competitor=True,
            llm_classified_intent="product_fit",
            llm_intent_confidence=0.8,
        )
        assert result.is_compound
        assert (
            result.detection_method == "comparison"
            or result.detection_method == "concept_co_occurrence"
        )
        assert len(result.sub_intents) >= 2

    def test_simple_product_query_not_compound(self):
        result = _detect(
            "What are the MTU 4000 specs?",
            entity_type="product",
            entity_in_product_registry=True,
            question_seeks_specs=True,
            concept_product=True,
            llm_classified_intent="product_fit",
            llm_intent_confidence=0.9,
        )
        assert not result.is_compound


class TestConceptCoOccurrence:
    """Test concept co-occurrence detection."""

    def test_billing_and_kyp(self):
        result = _detect(
            "Check ST Engineering payment history and summarize risks",
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=True,
            question_seeks_data=True,
            concept_billing=True,
            concept_kyp=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.7,
        )
        assert result.is_compound
        assert result.detection_method == "concept_co_occurrence"
        intents = {s.intent for s in result.sub_intents}
        assert "billing_ar" in intents
        assert "kyp_due_diligence" in intents
        # billing + kyp is sequential
        assert result.execution_order == "sequential"

    def test_competitor_and_market(self):
        result = _detect(
            "Give me competitor positioning and latest market developments",
            entity_type="none",
            question_seeks_news=True,
            concept_competitor=True,
            concept_market=True,
            llm_classified_intent="competitor_intel",
            llm_intent_confidence=0.7,
        )
        assert result.is_compound
        intents = {s.intent for s in result.sub_intents}
        assert "competitor_intel" in intents
        assert "market_intel" in intents
        assert result.execution_order == "parallel"

    def test_single_concept_not_compound(self):
        result = _detect(
            "Show billing items for Maersk",
            entity_type="customer",
            entity_has_sap_id=True,
            concept_billing=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        assert not result.is_compound


class TestConjunctionDetection:
    """Test conjunction splitting."""

    def test_billing_and_kyp_conjunction(self):
        result = _detect(
            "Show me the payment status and also run a sanctions check",
            entity_type="customer",
            entity_has_sap_id=True,
            concept_billing=True,
            concept_kyp=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.7,
        )
        assert result.is_compound
        assert len(result.sub_intents) >= 2


class TestSequentialDetection:
    """Test sequential dependency detection."""

    def test_sequential_markers_force_sequential(self):
        result = _detect(
            "Check credit status, then based on that assess the risk",
            entity_type="customer",
            entity_has_sap_id=True,
            entity_has_billing_history=True,
            concept_billing=True,
            concept_kyp=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.7,
        )
        if result.is_compound:
            assert result.execution_order == "sequential"


class TestEdgeCases:
    """Test edge cases in detection."""

    def test_very_short_query(self):
        result = _detect(
            "billing", llm_classified_intent="billing_ar", llm_intent_confidence=0.5
        )
        assert not result.is_compound

    def test_single_domain_not_compound(self):
        result = _detect(
            "Show all billing items and outstanding invoices",
            concept_billing=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.9,
        )
        # Same domain on both sides → not compound
        assert not result.is_compound

    def test_compound_query_to_dict(self):
        result = _detect(
            "Show billing and run KYP check",
            concept_billing=True,
            concept_kyp=True,
            llm_classified_intent="billing_ar",
            llm_intent_confidence=0.7,
        )
        d = result.to_dict()
        assert "is_compound" in d
        assert "compound_confidence" in d
        assert "sub_intents" in d


# =============================================================================
# Response Composition Tests
# =============================================================================


class TestResponseComposer:
    """Test response merging strategies."""

    def _make_compound_result(
        self, strategy="summary", order="parallel"
    ) -> CompoundResult:
        return CompoundResult(
            sub_results=[
                SubIntentResult(
                    intent="billing_ar",
                    answer="Outstanding amount: EUR 450K. Payment on time.",
                    sources=["SAP CPI (MS5)"],
                    confidence="HIGH",
                    tools_used=["billing_agent"],
                    execution_time_ms=1200,
                ),
                SubIntentResult(
                    intent="kyp_due_diligence",
                    answer="No sanctions found. Clean compliance record.",
                    sources=["Sanctions Database"],
                    confidence="HIGH",
                    tools_used=["sap_mcp", "perplexity"],
                    execution_time_ms=3500,
                ),
            ],
            execution_order=order,
            merge_strategy=strategy,
            total_time_ms=3800,
        )

    def test_summary_merge(self):
        result = self._make_compound_result("summary")
        response = ResponseComposer.compose(result)
        assert response["type"] == "compound_report"
        assert "Billing" in response["answer"]
        assert "Due Diligence" in response["answer"]
        assert len(response["sub_responses"]) == 2

    def test_comparison_merge(self):
        result = self._make_compound_result("comparison")
        response = ResponseComposer.compose(result)
        assert "Comparison Summary" in response["answer"]

    def test_sequential_merge(self):
        result = self._make_compound_result("sequential_narrative", "sequential")
        response = ResponseComposer.compose(result)
        assert "Based on the above" in response["answer"]

    def test_partial_failure(self):
        result = CompoundResult(
            sub_results=[
                SubIntentResult(
                    intent="billing_ar",
                    answer="Payment data retrieved.",
                    sources=["SAP CPI"],
                    confidence="HIGH",
                    tools_used=["billing_agent"],
                    execution_time_ms=1200,
                ),
                SubIntentResult(
                    intent="kyp_due_diligence",
                    answer="This section could not be completed.",
                    sources=[],
                    confidence="LOW",
                    tools_used=[],
                    execution_time_ms=0,
                    status="failed",
                    error="Perplexity timeout",
                ),
            ],
            execution_order="parallel",
            merge_strategy="summary",
            total_time_ms=5000,
            partial_success=True,
        )
        response = ResponseComposer.compose(result)
        assert response["partial_success"] is True
        assert "could not be completed" in response["answer"]

    def test_source_isolation(self):
        result = self._make_compound_result()
        response = ResponseComposer.compose(result)
        # Each sub-response should have its own sources
        assert response["sub_responses"][0]["sources"] == ["SAP CPI (MS5)"]
        assert response["sub_responses"][1]["sources"] == ["Sanctions Database"]

    def test_empty_result(self):
        result = CompoundResult(
            sub_results=[],
            execution_order="parallel",
            merge_strategy="summary",
            total_time_ms=0,
        )
        response = ResponseComposer.compose(result)
        assert response["type"] == "answer"
        assert "Unable" in response["answer"]

    def test_all_sources_combined(self):
        result = self._make_compound_result()
        response = ResponseComposer.compose(result)
        assert "SAP CPI (MS5)" in response["sources"]
        assert "Sanctions Database" in response["sources"]
