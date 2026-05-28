"""
Unit Tests for Reasoning Planner (Phase P2)

Tests:
1. Template selection and plan generation
2. Plan structure validation (DAG, no cycles, step limits)
3. Each template produces correct steps
4. Edge cases (unknown type, missing entity)
5. Determinism
"""

import pytest

from lead_to_cash.core.reasoning_planner import (
    ReasoningPlan,
    ReasoningPlanner,
    ReasoningStep,
)


# =============================================================================
# Template selection and generation
# =============================================================================


class TestTemplateSelection:
    """Test correct template is selected from reasoning type + hint."""

    def test_evaluate_defaults_to_risk_assessment(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk of Neptune Energy",
            reasoning_type="evaluate",
            entity="Neptune Energy",
        )
        assert plan.template == "risk_assessment"
        assert plan.valid

    def test_compare_recommend_defaults_to_product_comparison(self):
        plan = ReasoningPlanner.generate(
            query="Recommend the best engine",
            reasoning_type="compare_recommend",
            entity="",
        )
        assert plan.template == "product_comparison"
        assert plan.valid

    def test_multi_hop_defaults_to_credit_feasibility(self):
        plan = ReasoningPlanner.generate(
            query="If credit sufficient, propose engine",
            reasoning_type="multi_hop",
            entity="ST Engineering",
        )
        assert plan.template == "credit_feasibility"
        assert plan.valid

    def test_summarize_defaults_to_customer_deep_dive(self):
        plan = ReasoningPlanner.generate(
            query="Give me a full customer overview",
            reasoning_type="summarize",
            entity="Maersk",
        )
        assert plan.template == "customer_deep_dive"
        assert plan.valid

    def test_matched_template_overrides_default(self):
        plan = ReasoningPlanner.generate(
            query="Evaluate positioning",
            reasoning_type="evaluate",
            matched_template="competitive_positioning",
            entity="",
        )
        assert plan.template == "competitive_positioning"

    def test_unknown_type_produces_invalid_plan(self):
        plan = ReasoningPlanner.generate(
            query="Do something unknown",
            reasoning_type="unknown_type",
            entity="",
        )
        assert not plan.valid
        assert plan.template == "unknown"


# =============================================================================
# Plan structure validation
# =============================================================================


class TestPlanValidation:
    """Test plan DAG structure validation."""

    def test_risk_assessment_no_cycles(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test Corp",
        )
        assert plan.valid
        assert not ReasoningPlanner._has_cycle(plan.steps)

    def test_product_comparison_no_cycles(self):
        plan = ReasoningPlanner.generate(
            query="Compare engines",
            reasoning_type="compare_recommend",
            entity="",
        )
        assert plan.valid
        assert not ReasoningPlanner._has_cycle(plan.steps)

    def test_all_templates_within_step_limit(self):
        templates = [
            ("evaluate", "risk_assessment"),
            ("compare_recommend", "product_comparison"),
            ("multi_hop", "credit_feasibility"),
            ("summarize", "customer_deep_dive"),
            ("evaluate", "competitive_positioning"),
        ]
        for rtype, template in templates:
            plan = ReasoningPlanner.generate(
                query="Test",
                reasoning_type=rtype,
                matched_template=template,
                entity="Test",
            )
            assert len(plan.steps) <= 5, f"{template} has {len(plan.steps)} steps"

    def test_step_ids_unique(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test",
        )
        ids = [s.step_id for s in plan.steps]
        assert len(ids) == len(set(ids))

    def test_dependencies_reference_existing_steps(self):
        plan = ReasoningPlanner.generate(
            query="Compare products",
            reasoning_type="compare_recommend",
            entity="",
        )
        id_set = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for dep in step.input_from:
                assert dep in id_set, f"Step {step.step_id} depends on missing {dep}"


# =============================================================================
# Template step verification
# =============================================================================


class TestRiskAssessmentTemplate:
    """Test risk_assessment template structure."""

    def test_has_billing_retrieval(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            matched_template="risk_assessment",
            entity="Neptune Energy",
        )
        retrieve_intents = [s.intent for s in plan.steps if s.action == "retrieve"]
        assert "billing_ar" in retrieve_intents

    def test_has_kyp_retrieval(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            matched_template="risk_assessment",
            entity="Neptune Energy",
        )
        retrieve_intents = [s.intent for s in plan.steps if s.action == "retrieve"]
        assert "kyp_due_diligence" in retrieve_intents

    def test_has_risk_evaluator(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            matched_template="risk_assessment",
            entity="Neptune Energy",
        )
        evaluators = [s.evaluator for s in plan.steps if s.action == "evaluate"]
        assert "risk_scoring" in evaluators

    def test_has_synthesize_step(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            matched_template="risk_assessment",
            entity="Neptune Energy",
        )
        synth_steps = [s for s in plan.steps if s.action == "synthesize"]
        assert len(synth_steps) == 1

    def test_evaluate_depends_on_retrievals(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            matched_template="risk_assessment",
            entity="Neptune Energy",
        )
        eval_step = next(s for s in plan.steps if s.action == "evaluate")
        assert "s1_billing" in eval_step.input_from
        assert "s2_kyp" in eval_step.input_from


class TestProductComparisonTemplate:
    """Test product_comparison template."""

    def test_has_product_and_competitor_retrieval(self):
        plan = ReasoningPlanner.generate(
            query="Compare engines",
            reasoning_type="compare_recommend",
            matched_template="product_comparison",
            entity="ferry",
        )
        intents = [s.intent for s in plan.steps if s.action == "retrieve"]
        assert "product_fit" in intents
        assert "competitor_intel" in intents

    def test_has_comparison_step(self):
        plan = ReasoningPlanner.generate(
            query="Compare engines",
            reasoning_type="compare_recommend",
            matched_template="product_comparison",
            entity="ferry",
        )
        compare_steps = [s for s in plan.steps if s.action == "compare"]
        assert len(compare_steps) == 1

    def test_has_decide_step(self):
        plan = ReasoningPlanner.generate(
            query="Compare engines",
            reasoning_type="compare_recommend",
            matched_template="product_comparison",
            entity="ferry",
        )
        decide_steps = [s for s in plan.steps if s.action == "decide"]
        assert len(decide_steps) == 1


class TestCreditFeasibilityTemplate:
    """Test credit_feasibility template."""

    def test_has_billing_retrieval(self):
        plan = ReasoningPlanner.generate(
            query="If credit sufficient, propose",
            reasoning_type="multi_hop",
            matched_template="credit_feasibility",
            entity="ST Engineering",
        )
        intents = [s.intent for s in plan.steps if s.action == "retrieve"]
        assert "billing_ar" in intents

    def test_has_conditional_evaluator(self):
        plan = ReasoningPlanner.generate(
            query="If credit sufficient, propose",
            reasoning_type="multi_hop",
            matched_template="credit_feasibility",
            entity="ST Engineering",
        )
        evaluators = [s.evaluator for s in plan.steps if s.evaluator]
        assert "credit_feasibility" in evaluators
        assert "conditional_recommendation" in evaluators


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and safety."""

    def test_empty_entity(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="",
        )
        assert plan.valid  # Should still work with empty entity

    def test_none_template(self):
        plan = ReasoningPlanner.generate(
            query="Evaluate something",
            reasoning_type="evaluate",
            matched_template=None,
            entity="Test",
        )
        assert plan.template == "risk_assessment"  # Default for evaluate

    def test_plan_to_dict(self):
        plan = ReasoningPlanner.generate(
            query="Assess risk",
            reasoning_type="evaluate",
            entity="Test Corp",
        )
        d = plan.to_dict()
        assert "template" in d
        assert "reasoning_type" in d
        assert "steps" in d
        assert "valid" in d
        assert "step_count" in d

    def test_deterministic_output(self):
        """Same input always produces same plan."""
        p1 = ReasoningPlanner.generate(
            query="Assess risk of Neptune",
            reasoning_type="evaluate",
            entity="Neptune",
        )
        p2 = ReasoningPlanner.generate(
            query="Assess risk of Neptune",
            reasoning_type="evaluate",
            entity="Neptune",
        )
        assert p1.template == p2.template
        assert len(p1.steps) == len(p2.steps)
        for s1, s2 in zip(p1.steps, p2.steps):
            assert s1.step_id == s2.step_id
            assert s1.action == s2.action
