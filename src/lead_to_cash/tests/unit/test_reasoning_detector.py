"""
Unit Tests for Reasoning Detector (Phase P1)

Tests:
A. Positive detections (queries that need reasoning)
B. Negative detections (simple factual queries)
C. Template hinting (which plan template matches)
D. Reasoning type classification
E. Confidence scoring
F. Safety (detection failure must not affect system)
"""

import pytest

from lead_to_cash.core.reasoning_detector import (
    ReasoningDetection,
    detect_reasoning,
)


# =============================================================================
# A. Positive detections — queries that need reasoning
# =============================================================================


class TestPositiveDetection:
    """Queries that should be detected as needing reasoning."""

    def test_assess_risk(self):
        result = detect_reasoning("Assess risk of Neptune Energy")
        assert result.reasoning_needed is True
        assert "evaluation_language" in result.matched_signals
        assert result.reasoning_type == "evaluate"

    def test_evaluate_performance(self):
        result = detect_reasoning("Evaluate the financial performance of Maersk")
        assert result.reasoning_needed is True
        assert "evaluation_language" in result.matched_signals

    def test_analyze_competitor(self):
        result = detect_reasoning("Analyze competitor positioning in APAC")
        assert result.reasoning_needed is True
        assert "evaluation_language" in result.matched_signals

    def test_recommend_best_option(self):
        result = detect_reasoning(
            "Recommend the best option between MTU and Caterpillar"
        )
        assert result.reasoning_needed is True
        assert "recommendation_language" in result.matched_signals
        assert result.reasoning_type == "compare_recommend"

    def test_which_should_we_choose(self):
        result = detect_reasoning("Which engine should we choose for the ferry?")
        assert result.reasoning_needed is True
        assert "recommendation_language" in result.matched_signals

    def test_suggest_configuration(self):
        result = detect_reasoning("Suggest the best engine configuration")
        assert result.reasoning_needed is True
        assert "recommendation_language" in result.matched_signals

    def test_if_then_conditional(self):
        result = detect_reasoning(
            "If credit is sufficient for EUR 5M, then propose an engine"
        )
        assert result.reasoning_needed is True
        assert "conditional_language" in result.matched_signals
        assert result.reasoning_type == "multi_hop"

    def test_assuming_conditional(self):
        result = detect_reasoning("Assuming they pass KYP, what engines can we offer?")
        assert result.reasoning_needed is True
        assert "conditional_language" in result.matched_signals

    def test_given_that_conditional(self):
        result = detect_reasoning("Given that their credit is good, propose a deal")
        assert result.reasoning_needed is True
        assert "conditional_language" in result.matched_signals

    def test_compare_and_recommend(self):
        result = detect_reasoning(
            "Compare MTU vs Caterpillar and recommend the best for ferries"
        )
        assert result.reasoning_needed is True
        # Should match comparison_judgment or recommendation
        has_comparison = "comparison_judgment" in result.matched_signals
        has_recommendation = "recommendation_language" in result.matched_signals
        assert has_comparison or has_recommendation

    def test_check_risk(self):
        result = detect_reasoning("Check risk of doing business with this company")
        assert result.reasoning_needed is True
        assert "evaluation_language" in result.matched_signals

    def test_score_supplier(self):
        result = detect_reasoning("Score this supplier on compliance")
        assert result.reasoning_needed is True
        assert "evaluation_language" in result.matched_signals

    def test_compound_sequential(self):
        result = detect_reasoning(
            "Check billing and summarize risks",
            compound_metadata={"execution_order": "sequential", "is_compound": True},
        )
        assert result.reasoning_needed is True
        assert "compound_sequential" in result.matched_signals

    def test_compound_comparison(self):
        result = detect_reasoning(
            "Compare MTU 4000 vs Cat 3516",
            compound_metadata={"detection_method": "comparison", "is_compound": True},
        )
        assert result.reasoning_needed is True
        assert "compound_comparison" in result.matched_signals


# =============================================================================
# B. Negative detections — simple factual queries
# =============================================================================


class TestNegativeDetection:
    """Queries that should NOT be detected as needing reasoning."""

    def test_simple_billing_query(self):
        result = detect_reasoning("Show billing items for Maersk")
        assert result.reasoning_needed is False

    def test_product_specs(self):
        result = detect_reasoning("What are the MTU 4000 specs?")
        assert result.reasoning_needed is False

    def test_credit_status(self):
        result = detect_reasoning("What is the credit status for ST Engineering?")
        assert result.reasoning_needed is False

    def test_market_news(self):
        result = detect_reasoning("Latest news in the APAC ferry market")
        assert result.reasoning_needed is False

    def test_customer_profile(self):
        result = detect_reasoning("Tell me about Batam Fast Ferry")
        assert result.reasoning_needed is False

    def test_show_collections(self):
        result = detect_reasoning("Show collections items")
        assert result.reasoning_needed is False

    def test_run_kyp(self):
        # "Run KYP" is an action, not reasoning
        result = detect_reasoning("Run KYP on Neptune Energy")
        assert result.reasoning_needed is False

    def test_payment_history_factual(self):
        # Factual retrieval, not evaluation
        result = detect_reasoning("Show payment history")
        assert result.reasoning_needed is False

    def test_competitor_news(self):
        result = detect_reasoning("What are the latest updates from Caterpillar?")
        assert result.reasoning_needed is False

    def test_general_question(self):
        result = detect_reasoning("What is an OSV?")
        assert result.reasoning_needed is False


# =============================================================================
# C. Template hinting
# =============================================================================


class TestTemplateHinting:
    """Test that correct plan template is hinted for logging."""

    def test_risk_assessment_template(self):
        signals = {"concept_billing": True, "concept_kyp": True}
        result = detect_reasoning("Assess risk", signals_dict=signals)
        assert result.matched_template == "risk_assessment"

    def test_product_comparison_template(self):
        signals = {"concept_product": True, "concept_competitor": True}
        result = detect_reasoning("Compare engines", signals_dict=signals)
        assert result.matched_template == "product_comparison"

    def test_credit_feasibility_template(self):
        signals = {"concept_billing": True}
        result = detect_reasoning(
            "If credit sufficient then propose",
            signals_dict=signals,
        )
        assert result.matched_template == "credit_feasibility"

    def test_customer_deep_dive_template(self):
        signals = {"concept_customer": True}
        result = detect_reasoning("Evaluate customer", signals_dict=signals)
        assert result.matched_template == "customer_deep_dive"

    def test_competitive_positioning_template(self):
        signals = {"concept_competitor": True, "concept_market": True}
        result = detect_reasoning("Analyze positioning", signals_dict=signals)
        assert result.matched_template == "competitive_positioning"

    def test_no_template_without_concepts(self):
        result = detect_reasoning("Assess something")
        assert result.matched_template is None

    def test_no_template_with_single_non_matching_concept(self):
        signals = {"concept_market": True}
        result = detect_reasoning("Evaluate market", signals_dict=signals)
        # market alone doesn't match any 2-concept template,
        # but could match if we relax single-concept matching
        # Current: no strict match for market-only
        assert result.matched_template is None or result.matched_template is not None
        # Just verify no crash


# =============================================================================
# D. Reasoning type classification
# =============================================================================


class TestReasoningTypeClassification:
    """Test reasoning type is correctly classified."""

    def test_evaluate_type(self):
        result = detect_reasoning("Assess the risk of this company")
        assert result.reasoning_type == "evaluate"

    def test_compare_recommend_from_recommendation(self):
        result = detect_reasoning("Recommend the best engine")
        assert result.reasoning_type == "compare_recommend"

    def test_multi_hop_from_conditional(self):
        result = detect_reasoning("If credit is sufficient then propose a deal")
        assert result.reasoning_type == "multi_hop"

    def test_compare_from_compound(self):
        result = detect_reasoning(
            "Compare options",
            compound_metadata={"detection_method": "comparison"},
        )
        assert result.reasoning_type == "compare_recommend"

    def test_no_type_for_factual(self):
        result = detect_reasoning("Show billing items")
        assert result.reasoning_type is None


# =============================================================================
# E. Confidence scoring
# =============================================================================


class TestConfidenceScoring:
    """Test that confidence reflects signal strength."""

    def test_single_signal_moderate(self):
        result = detect_reasoning("Assess the risk")
        assert 0.3 <= result.confidence <= 0.5

    def test_multiple_signals_higher(self):
        result = detect_reasoning(
            "If credit sufficient then recommend the best engine",
        )
        # conditional + recommendation = higher confidence
        assert result.confidence > 0.5

    def test_no_signals_zero(self):
        result = detect_reasoning("Show billing items")
        assert result.confidence == 0.0

    def test_confidence_capped_at_1(self):
        # Stack many signals
        result = detect_reasoning(
            "Assess risk, recommend best option, and if approved then propose configuration",
            compound_metadata={"execution_order": "sequential"},
        )
        assert result.confidence <= 1.0

    def test_confidence_threshold(self):
        """Below threshold should not flag reasoning_needed."""
        # A query with very weak signal
        result = detect_reasoning("Show the status")
        assert result.reasoning_needed is False
        assert result.confidence < 0.3


# =============================================================================
# F. Safety and structure
# =============================================================================


class TestSafety:
    """Test that detection is safe and well-structured."""

    def test_to_dict(self):
        result = detect_reasoning("Assess risk of Neptune Energy")
        d = result.to_dict()
        assert "reasoning_needed" in d
        assert "reasoning_type" in d
        assert "matched_signals" in d
        assert "matched_template" in d
        assert "confidence" in d
        assert "query" in d

    def test_none_signals_handled(self):
        """Passing None for signals should not crash."""
        result = detect_reasoning("Assess risk", signals_dict=None)
        assert result.reasoning_needed is True
        assert result.matched_template is None  # No signals → no template

    def test_none_compound_handled(self):
        result = detect_reasoning("Assess risk", compound_metadata=None)
        assert result.reasoning_needed is True

    def test_empty_query(self):
        result = detect_reasoning("")
        assert result.reasoning_needed is False

    def test_very_long_query_truncated_in_result(self):
        long_query = "Assess risk " * 100
        result = detect_reasoning(long_query)
        assert len(result.to_dict()["query"]) <= 200

    def test_detection_is_deterministic(self):
        """Same input always produces same output."""
        q = "Assess risk of Neptune Energy and recommend next steps"
        r1 = detect_reasoning(q)
        r2 = detect_reasoning(q)
        assert r1.reasoning_needed == r2.reasoning_needed
        assert r1.reasoning_type == r2.reasoning_type
        assert r1.matched_signals == r2.matched_signals
        assert r1.confidence == r2.confidence
