"""
Unit Tests for Reasoning Executor (Phase P4)

Tests:
1. Response formatting from evaluation results
2. Rollout bucket determinism
3. Feature flag behavior
4. Fallback on invalid plan
5. Fallback on missing evaluator
6. Response structure
"""

import pytest

from lead_to_cash.core.reasoning_evaluator import (
    EvaluationResult,
    GroundedFinding,
    StepData,
    risk_scoring,
)
from lead_to_cash.core.reasoning_executor import (
    ReasoningExecutor,
    ReasoningResponse,
)
from lead_to_cash.core.reasoning_planner import ReasoningPlan, ReasoningPlanner


# =============================================================================
# Response formatting
# =============================================================================


class TestResponseFormatting:
    """Test that evaluation results are formatted into readable responses."""

    def _make_eval_result(self) -> EvaluationResult:
        return risk_scoring(
            {
                "s1_billing": StepData(
                    step_id="s1_billing",
                    data={
                        "max_overdue_days": 52,
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

    def test_format_risk_assessment(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk of Neptune Energy",
            reasoning_type="evaluate",
            entity="Neptune Energy",
        )
        result = self._make_eval_result()
        answer = ReasoningExecutor._format_answer(plan, result)

        assert "Risk Assessment" in answer
        assert "Neptune Energy" in answer
        assert "HIGH" in answer
        assert "Payment Timeliness" in answer
        assert "Credit Utilization" in answer
        assert "Sanctions" in answer
        assert "SAP CPI" in answer

    def test_format_includes_criteria(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test",
        )
        result = self._make_eval_result()
        answer = ReasoningExecutor._format_answer(plan, result)
        assert "Criteria Applied" in answer

    def test_format_includes_recommendation(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test",
        )
        result = self._make_eval_result()
        answer = ReasoningExecutor._format_answer(plan, result)
        assert "Recommendation" in answer

    def test_format_includes_grounding_note(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test",
        )
        result = self._make_eval_result()
        answer = ReasoningExecutor._format_answer(plan, result)
        assert "grounded" in answer.lower()


# =============================================================================
# Rollout bucket
# =============================================================================


class TestRolloutBucket:
    """Test deterministic traffic routing."""

    def test_bucket_is_deterministic(self):
        q = "Assess risk of Neptune Energy"
        r1 = ReasoningExecutor.in_rollout_bucket(q)
        r2 = ReasoningExecutor.in_rollout_bucket(q)
        assert r1 == r2

    def test_100_percent_always_in(self):
        # Default ROLLOUT_PERCENTAGE is 100
        assert ReasoningExecutor.in_rollout_bucket("any query")

    def test_different_queries_may_differ(self):
        # Not all queries should hash to same bucket
        results = set()
        for i in range(100):
            results.add(ReasoningExecutor.in_rollout_bucket(f"query_{i}"))
        # With 100% rollout, all should be True
        # This test validates the function runs without error
        assert True in results


# =============================================================================
# Response structure
# =============================================================================


class TestReasoningResponse:
    """Test ReasoningResponse data structure."""

    def test_to_response_dict(self):
        resp = ReasoningResponse(
            success=True,
            template="risk_assessment",
            score="HIGH",
            recommendation="Monitor closely",
            findings=[{"dimension": "Payment", "result": "ADVERSE"}],
            criteria_table=["overdue > 45 → HIGH"],
            sources=["SAP CPI"],
            answer_text="## Risk Assessment\n\nHIGH risk.",
            confidence_score=0.85,
        )
        d = resp.to_response_dict("session-123")
        assert d["type"] == "reasoning_report"
        assert d["session_id"] == "session-123"
        assert d["score"] == "HIGH"
        assert d["answer"] == "## Risk Assessment\n\nHIGH risk."
        assert "SAP CPI" in d["sources"]
        assert d["confidence"] == "HIGH"
        assert d["confidence_score"] == 0.85

    def test_insufficient_data_response(self):
        resp = ReasoningResponse(
            success=False,
            template="risk_assessment",
            score="INSUFFICIENT_DATA",
            confidence_score=0.0,
            insufficient_data=True,
        )
        d = resp.to_response_dict()
        assert d["confidence"] == "LOW"
        assert d["insufficient_data"] is True

    def test_conflict_detected_response(self):
        resp = ReasoningResponse(
            success=True,
            template="risk_assessment",
            score="HIGH",
            confidence_score=0.7,
            conflict_detected=True,
            conflict_explanation="Mixed signals: Payment adverse, Sanctions clear.",
        )
        d = resp.to_response_dict()
        assert d["conflict_detected"] is True
        assert "Mixed signals" in d["conflict_explanation"]

    def test_failed_response(self):
        resp = ReasoningResponse(
            success=False,
            template="risk_assessment",
            fallback_reason="evaluator_failed",
        )
        d = resp.to_response_dict()
        assert d["confidence"] == "LOW"


# =============================================================================
# Safety: invalid plan fallback
# =============================================================================


class TestSafetyFallback:
    """Test that invalid plans don't execute."""

    @pytest.mark.asyncio
    async def test_invalid_plan_returns_none(self):
        plan = ReasoningPlan(
            template="unknown",
            reasoning_type="evaluate",
            valid=False,
            validation_errors=["No template"],
        )
        result = await ReasoningExecutor.execute(plan, None, None, None)
        assert result is None

    def test_feature_flag_default_off(self):
        import os

        # Remove env var if set
        old = os.environ.pop("REASONING_EXECUTION_ENABLED", None)
        try:
            assert ReasoningExecutor.is_enabled() is False
        finally:
            if old is not None:
                os.environ["REASONING_EXECUTION_ENABLED"] = old


# =============================================================================
# Evaluator integration
# =============================================================================


class TestEvaluatorIntegration:
    """Test evaluator execution within executor."""

    def test_execute_evaluator_with_valid_data(self):
        from lead_to_cash.core.reasoning_planner import ReasoningStep

        step = ReasoningStep(
            step_id="s3",
            action="evaluate",
            evaluator="risk_scoring",
        )
        inputs = {
            "s1_billing": StepData(
                step_id="s1_billing",
                data={
                    "max_overdue_days": 30,
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
        result = ReasoningExecutor._execute_evaluator(step, inputs)
        assert result is not None
        assert result.score == "LOW"

    def test_execute_unknown_evaluator_returns_none(self):
        from lead_to_cash.core.reasoning_planner import ReasoningStep

        step = ReasoningStep(
            step_id="s3",
            action="evaluate",
            evaluator="nonexistent_evaluator",
        )
        result = ReasoningExecutor._execute_evaluator(step, {})
        assert result is None
