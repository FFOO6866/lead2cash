"""
Unit Tests for Reasoning Evaluator (Phase P3)

Tests all 5 evaluator functions with sample data:
1. risk_scoring — threshold rules, grounding chains
2. product_comparison — dimension-by-dimension comparison
3. credit_feasibility — sufficient/insufficient assessment
4. recommendation_with_rationale — recommendation from comparison
5. conditional_recommendation — conditional logic
"""

import pytest

from lead_to_cash.core.reasoning_evaluator import (
    EVALUATOR_REGISTRY,
    EvaluationResult,
    GroundedFinding,
    StepData,
    credit_feasibility,
    conditional_recommendation,
    get_evaluator,
    product_comparison,
    recommendation_with_rationale,
    risk_scoring,
)


# =============================================================================
# Risk Scoring Tests
# =============================================================================


class TestRiskScoring:
    """Test risk_scoring evaluator with various data combinations."""

    def test_low_risk_clean_record(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 10,
                        "credit_utilization": 0.45,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert result.score == "LOW"
        assert result.grounding_complete
        assert len(result.findings) == 3
        assert all(f.result in ("CLEAR",) for f in result.findings)

    def test_medium_risk_high_utilization(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 10,
                        "credit_utilization": 0.85,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert result.score == "MEDIUM"
        util_finding = next(
            f for f in result.findings if f.dimension == "Credit Utilization"
        )
        assert util_finding.result == "CAUTION"

    def test_high_risk_overdue(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 52,
                        "credit_utilization": 0.60,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert result.score == "HIGH"
        payment = next(
            f for f in result.findings if f.dimension == "Payment Timeliness"
        )
        assert payment.result == "ADVERSE"
        assert payment.data_value == 52

    def test_critical_risk_sanctions(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 5,
                        "credit_utilization": 0.30,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": True,
                    },
                    source="OFAC",
                ),
            }
        )
        assert result.score == "CRITICAL"
        sanctions = next(f for f in result.findings if f.dimension == "Sanctions")
        assert sanctions.result == "CRITICAL"

    def test_combined_high_and_medium(self):
        """Overdue (HIGH) + high utilization (MEDIUM) → overall HIGH."""
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 50,
                        "credit_utilization": 0.90,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert result.score == "HIGH"  # HIGH trumps MEDIUM

    def test_grounding_chain_complete(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 10,
                        "credit_utilization": 0.50,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert result.grounding_complete
        for f in result.findings:
            assert f.source_step, f"Finding {f.dimension} missing source_step"
            assert f.source_name, f"Finding {f.dimension} missing source_name"
            assert f.threshold, f"Finding {f.dimension} missing threshold"

    def test_rules_applied_listed(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(step_id="s1_billing", data={}, source="SAP"),
                "s2_kyp": StepData(step_id="s2_kyp", data={}, source="DB"),
            }
        )
        assert len(result.rules_applied) >= 3

    def test_recommendation_matches_score(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 50,
                        "credit_utilization": 0.50,
                    },
                    source="SAP CPI",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="Sanctions DB",
                ),
            }
        )
        assert (
            "risk" in result.recommendation.lower()
            or "proceed" in result.recommendation.lower()
        )

    def test_deterministic(self):
        inputs = {
            "s1_billing": StepData(
                step_id="s1_billing",
                data={
                    "max_overdue_days": 30,
                    "credit_utilization": 0.70,
                },
                source="SAP",
            ),
            "s2_kyp": StepData(
                step_id="s2_kyp",
                data={
                    "sanctions_found": False,
                },
                source="DB",
            ),
        }
        r1 = risk_scoring(inputs)
        r2 = risk_scoring(inputs)
        assert r1.score == r2.score
        assert len(r1.findings) == len(r2.findings)


# =============================================================================
# Product Comparison Tests
# =============================================================================


class TestProductComparison:
    """Test product_comparison evaluator."""

    def test_advantage_when_we_win_majority(self):
        result = product_comparison(
            {
                "s1_product": StepData(
                    step_id="s1_product",
                    data={
                        "power_kw": 1340,
                        "fuel_efficiency": 92,
                        "service_coverage": 130,
                        "emissions_tier": 3,
                        "lifecycle_cost": 80,
                    },
                    source="KB",
                ),
                "s2_competitor": StepData(
                    step_id="s2_competitor",
                    data={
                        "power_kw": 1081,
                        "fuel_efficiency": 88,
                        "service_coverage": 90,
                        "emissions_tier": 3,
                        "lifecycle_cost": 85,
                    },
                    source="Competitor DB",
                ),
            }
        )
        assert result.score == "ADVANTAGE"
        assert result.grounding_complete

    def test_gap_when_they_win_majority(self):
        result = product_comparison(
            {
                "s1_product": StepData(
                    step_id="s1_product",
                    data={
                        "power_kw": 1000,
                        "fuel_efficiency": 85,
                        "service_coverage": 90,
                        "emissions_tier": 2,
                        "lifecycle_cost": 90,
                    },
                    source="KB",
                ),
                "s2_competitor": StepData(
                    step_id="s2_competitor",
                    data={
                        "power_kw": 1200,
                        "fuel_efficiency": 92,
                        "service_coverage": 120,
                        "emissions_tier": 3,
                        "lifecycle_cost": 80,
                    },
                    source="Competitor DB",
                ),
            }
        )
        assert result.score == "GAP"

    def test_parity_when_equal(self):
        same = {
            "power_kw": 1000,
            "fuel_efficiency": 90,
            "service_coverage": 100,
            "emissions_tier": 3,
            "lifecycle_cost": 85,
        }
        result = product_comparison(
            {
                "s1_product": StepData(step_id="s1_product", data=same, source="KB"),
                "s2_competitor": StepData(
                    step_id="s2_competitor", data=same, source="DB"
                ),
            }
        )
        assert result.score == "PARITY"

    def test_five_dimensions_compared(self):
        result = product_comparison(
            {
                "s1_product": StepData(
                    step_id="s1_product",
                    data={
                        "power_kw": 1340,
                        "fuel_efficiency": 92,
                        "service_coverage": 130,
                        "emissions_tier": 3,
                        "lifecycle_cost": 80,
                    },
                    source="KB",
                ),
                "s2_competitor": StepData(
                    step_id="s2_competitor",
                    data={
                        "power_kw": 1081,
                        "fuel_efficiency": 88,
                        "service_coverage": 90,
                        "emissions_tier": 3,
                        "lifecycle_cost": 85,
                    },
                    source="DB",
                ),
            }
        )
        assert len(result.findings) == 5


# =============================================================================
# Credit Feasibility Tests
# =============================================================================


class TestCreditFeasibility:
    """Test credit_feasibility evaluator."""

    def test_sufficient_credit(self):
        result = credit_feasibility(
            {
                "s1_credit": StepData(
                    step_id="s1_credit",
                    data={
                        "available_credit": 6_000_000,
                        "order_value": 5_000_000,
                    },
                    source="SAP CPI",
                ),
            }
        )
        assert result.score == "SUFFICIENT"
        assert "proceed" in result.recommendation.lower()

    def test_insufficient_credit(self):
        result = credit_feasibility(
            {
                "s1_credit": StepData(
                    step_id="s1_credit",
                    data={
                        "available_credit": 3_000_000,
                        "order_value": 5_000_000,
                    },
                    source="SAP CPI",
                ),
            }
        )
        assert result.score == "INSUFFICIENT"
        assert len(result.findings) == 2  # availability + shortfall

    def test_exact_match_is_sufficient(self):
        result = credit_feasibility(
            {
                "s1_credit": StepData(
                    step_id="s1_credit",
                    data={
                        "available_credit": 5_000_000,
                        "order_value": 5_000_000,
                    },
                    source="SAP CPI",
                ),
            }
        )
        assert result.score == "SUFFICIENT"


# =============================================================================
# Recommendation Tests
# =============================================================================


class TestRecommendation:
    """Test recommendation_with_rationale evaluator."""

    def test_recommend_on_advantage(self):
        result = recommendation_with_rationale(
            {
                "s3_compare": StepData(
                    step_id="s3_compare",
                    data={
                        "score": "ADVANTAGE",
                        "our_wins": 4,
                        "their_wins": 1,
                    },
                    source="evaluation",
                ),
            }
        )
        assert result.score == "ADVANTAGE"
        assert "recommend" in result.recommendation.lower()

    def test_caution_on_gap(self):
        result = recommendation_with_rationale(
            {
                "s3_compare": StepData(
                    step_id="s3_compare",
                    data={
                        "score": "GAP",
                        "our_wins": 1,
                        "their_wins": 4,
                    },
                    source="evaluation",
                ),
            }
        )
        assert result.score == "GAP"

    def test_insufficient_without_input(self):
        result = recommendation_with_rationale({})
        assert result.score == "INSUFFICIENT_DATA"
        assert not result.grounding_complete


# =============================================================================
# Conditional Recommendation Tests
# =============================================================================


class TestConditionalRecommendation:
    """Test conditional_recommendation evaluator."""

    def test_proceed_when_feasible(self):
        result = conditional_recommendation(
            {
                "s2_evaluate": StepData(
                    step_id="s2_evaluate",
                    data={
                        "score": "SUFFICIENT",
                    },
                    source="evaluation",
                ),
            }
        )
        assert result.score == "PROCEED"

    def test_hold_when_not_feasible(self):
        result = conditional_recommendation(
            {
                "s2_evaluate": StepData(
                    step_id="s2_evaluate",
                    data={
                        "score": "INSUFFICIENT",
                    },
                    source="evaluation",
                ),
            }
        )
        assert result.score == "HOLD"

    def test_insufficient_without_input(self):
        result = conditional_recommendation({})
        assert result.score == "INSUFFICIENT_DATA"


# =============================================================================
# Registry and Serialization
# =============================================================================


class TestRegistry:
    """Test evaluator registry."""

    def test_all_evaluators_registered(self):
        expected = [
            "risk_scoring",
            "product_comparison",
            "credit_feasibility",
            "recommendation_with_rationale",
            "conditional_recommendation",
        ]
        for name in expected:
            assert name in EVALUATOR_REGISTRY
            assert get_evaluator(name) is not None

    def test_unknown_evaluator_returns_none(self):
        assert get_evaluator("nonexistent") is None

    def test_evaluation_result_to_dict(self):
        result = risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 10,
                        "credit_utilization": 0.50,
                    },
                    source="SAP",
                ),
                "s2_kyp": StepData(
                    step_id="s2_kyp",
                    data={
                        "sanctions_found": False,
                    },
                    source="DB",
                ),
            }
        )
        d = result.to_dict()
        assert "evaluator" in d
        assert "score" in d
        assert "findings" in d
        assert "grounding_complete" in d
        assert "rules_applied" in d
