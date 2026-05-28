"""
Reasoning System — Production Operations Validation

Simulates production operation at Phase A (10% rollout):
1. Run reasoning detection + planning + evaluation on representative queries
2. Compute all operational metrics
3. Validate QA criteria
4. Produce scaling decision

This test suite serves as the Phase A → Phase B gate.
"""

import pytest
from collections import Counter
from dataclasses import dataclass
from typing import List

from lead_to_cash.core.reasoning_detector import detect_reasoning
from lead_to_cash.core.reasoning_evaluator import (
    EvaluationResult,
    StepData,
    risk_scoring,
    product_comparison,
    credit_feasibility,
)
from lead_to_cash.core.reasoning_executor import ReasoningExecutor, ReasoningResponse
from lead_to_cash.core.reasoning_planner import ReasoningPlanner


# =============================================================================
# Simulated production workload
# =============================================================================


@dataclass
class SimQuery:
    query: str
    expected_reasoning: bool
    expected_type: str = ""
    template: str = ""
    # Simulated retrieval data for evaluator testing
    billing_data: dict = None
    kyp_data: dict = None
    product_data: dict = None
    competitor_data: dict = None
    credit_data: dict = None

    def __post_init__(self):
        self.billing_data = self.billing_data or {}
        self.kyp_data = self.kyp_data or {}
        self.product_data = self.product_data or {}
        self.competitor_data = self.competitor_data or {}
        self.credit_data = self.credit_data or {}


PRODUCTION_WORKLOAD = [
    # Non-reasoning queries (should pass through unchanged)
    SimQuery("Show billing items for Maersk", False),
    SimQuery("What are the MTU 4000 specs?", False),
    SimQuery("Caterpillar latest updates", False),
    SimQuery("Show aging buckets", False),
    SimQuery("Run KYP on Neptune Energy", False),
    SimQuery("Latest ferry market news", False),
    SimQuery("Credit status for ST Engineering", False),
    SimQuery("What is an OSV?", False),
    SimQuery("Show opportunities for Batam Fast Ferry", False),
    SimQuery("Collections items", False),
    # Reasoning: risk assessment
    SimQuery(
        "Assess risk of Neptune Energy",
        True,
        "evaluate",
        "risk_assessment",
        billing_data={"max_overdue_days": 52, "credit_utilization": 0.85},
        kyp_data={"sanctions_found": False},
    ),
    SimQuery(
        "Evaluate payment reliability of Maersk",
        True,
        "evaluate",
        "risk_assessment",
        billing_data={"max_overdue_days": 10, "credit_utilization": 0.30},
        kyp_data={"sanctions_found": False},
    ),
    SimQuery(
        "Check risk profile of this prospect",
        True,
        "evaluate",
        "risk_assessment",
        billing_data={"max_overdue_days": 0, "credit_utilization": 0},
        kyp_data={"sanctions_found": True},
    ),
    # Reasoning: product comparison
    SimQuery(
        "Recommend the best engine for ferry",
        True,
        "compare_recommend",
        "product_comparison",
        product_data={
            "power_kw": 1340,
            "fuel_efficiency": 92,
            "service_coverage": 130,
            "emissions_tier": 3,
            "lifecycle_cost": 80,
        },
        competitor_data={
            "power_kw": 1081,
            "fuel_efficiency": 88,
            "service_coverage": 90,
            "emissions_tier": 3,
            "lifecycle_cost": 85,
        },
    ),
    # Reasoning: credit feasibility (uses "then" for conditional detection)
    SimQuery(
        "If credit is sufficient for EUR 5M then propose an engine",
        True,
        "multi_hop",
        "credit_feasibility",
        credit_data={"available_credit": 6_000_000, "order_value": 5_000_000},
    ),
    SimQuery(
        "Assuming budget allows for EUR 10M order",
        True,
        "multi_hop",
        "credit_feasibility",
        credit_data={"available_credit": 3_000_000, "order_value": 10_000_000},
    ),
    # Reasoning: insufficient data scenarios
    SimQuery("Assess risk of Unknown Corp", True, "evaluate", "risk_assessment"),
    # No billing or KYP data → should return INSUFFICIENT_DATA
    # More non-reasoning to maintain ratio
    SimQuery("Payment history for ST Engineering", False),
    SimQuery("What power range for tugs?", False),
    SimQuery("Competitor wins in APAC", False),
]


# =============================================================================
# Simulation engine
# =============================================================================


def run_production_simulation():
    """Simulate Phase A production operation."""
    total = len(PRODUCTION_WORKLOAD)
    results = {
        "total_queries": total,
        "reasoning_detected": 0,
        "reasoning_executed": 0,
        "reasoning_successful": 0,
        "reasoning_fallback": 0,
        "insufficient_data": 0,
        "conflicts_detected": 0,
        "qa_samples": [],
        "scores": [],
        "templates_used": Counter(),
        "confidence_scores": [],
    }

    for sim in PRODUCTION_WORKLOAD:
        # Step 1: Detection
        detection = detect_reasoning(sim.query)

        if detection.reasoning_needed:
            results["reasoning_detected"] += 1

            # Step 2: Plan generation
            plan = ReasoningPlanner.generate(
                query=sim.query,
                reasoning_type=detection.reasoning_type or "evaluate",
                matched_template=detection.matched_template,
                entity="TestEntity",
            )

            if not plan.valid:
                results["reasoning_fallback"] += 1
                continue

            # Step 3: Simulate evaluation (using provided data)
            eval_result = _simulate_evaluation(sim, plan)
            if not eval_result:
                results["reasoning_fallback"] += 1
                continue

            results["reasoning_executed"] += 1
            results["templates_used"][plan.template] += 1

            # Step 4: Build response
            is_insufficient = eval_result.score == "INSUFFICIENT_DATA"
            if is_insufficient:
                results["insufficient_data"] += 1
            else:
                results["reasoning_successful"] += 1

            # Conflict detection
            if eval_result.findings:
                result_set = {f.result for f in eval_result.findings}
                has_clear = bool(result_set & {"CLEAR", "SUFFICIENT"})
                has_adverse = bool(result_set & {"ADVERSE", "CRITICAL"})
                if has_clear and has_adverse:
                    results["conflicts_detected"] += 1

            # Confidence scoring
            data_completeness = 1.0 if not is_insufficient else 0.0
            grounding = 1.0 if eval_result.grounding_complete else 0.5
            conf = round(data_completeness * grounding, 2)
            results["confidence_scores"].append(conf)

            results["scores"].append(eval_result.score)
            answer = ReasoningExecutor._format_answer(plan, eval_result)

            # QA sample
            results["qa_samples"].append(
                {
                    "query": sim.query,
                    "expected_type": sim.expected_type,
                    "template": plan.template,
                    "score": eval_result.score,
                    "findings": len(eval_result.findings),
                    "grounded": eval_result.grounding_complete,
                    "has_criteria": bool(eval_result.rules_applied),
                    "has_sources": any(f.source_name for f in eval_result.findings),
                    "answer_length": len(answer),
                    "insufficient": is_insufficient,
                }
            )

    # Compute metrics
    det = results["reasoning_detected"]
    exe = results["reasoning_executed"]
    results["detection_rate"] = round(det / total, 3) if total else 0
    results["execution_rate"] = round(exe / total, 3) if total else 0
    results["fallback_rate"] = round(results["reasoning_fallback"] / max(det, 1), 3)
    results["insufficient_rate"] = round(results["insufficient_data"] / max(exe, 1), 3)
    results["avg_confidence"] = (
        round(sum(results["confidence_scores"]) / len(results["confidence_scores"]), 3)
        if results["confidence_scores"]
        else 0
    )

    return results


def _simulate_evaluation(sim: SimQuery, plan):
    """Simulate evaluator execution with provided test data."""
    if plan.template == "risk_assessment":
        inputs = {}
        if sim.billing_data:
            inputs["s1_billing"] = StepData(
                step_id="s1_billing", data=sim.billing_data, source="SAP CPI"
            )
        if sim.kyp_data:
            inputs["s2_kyp"] = StepData(
                step_id="s2_kyp", data=sim.kyp_data, source="Sanctions DB"
            )
        return risk_scoring(inputs)

    elif plan.template == "product_comparison":
        inputs = {}
        if sim.product_data:
            inputs["s1_product"] = StepData(
                step_id="s1_product", data=sim.product_data, source="Knowledge Base"
            )
        if sim.competitor_data:
            inputs["s2_competitor"] = StepData(
                step_id="s2_competitor",
                data=sim.competitor_data,
                source="Competitor DB",
            )
        return product_comparison(inputs)

    elif plan.template == "credit_feasibility":
        inputs = {}
        if sim.credit_data:
            inputs["s1_credit"] = StepData(
                step_id="s1_credit", data=sim.credit_data, source="SAP CPI"
            )
        return credit_feasibility(inputs)

    return None


# =============================================================================
# Operational metrics tests
# =============================================================================


class TestPhaseAMetrics:
    """Validate Phase A operational metrics."""

    @pytest.fixture(scope="class")
    def sim(self):
        return run_production_simulation()

    def test_detection_rate_reasonable(self, sim):
        assert 0.20 <= sim["detection_rate"] <= 0.50, (
            f"Detection rate {sim['detection_rate']:.0%} outside expected range"
        )

    def test_fallback_rate_below_threshold(self, sim):
        assert sim["fallback_rate"] < 0.10, (
            f"Fallback rate {sim['fallback_rate']:.0%} exceeds 10%"
        )

    def test_insufficient_data_rate_reasonable(self, sim):
        assert sim["insufficient_rate"] <= 0.20, (
            f"Insufficient data rate {sim['insufficient_rate']:.0%} exceeds 20%"
        )

    def test_all_qa_samples_have_criteria(self, sim):
        for s in sim["qa_samples"]:
            if not s["insufficient"]:
                assert s["has_criteria"], f"Missing criteria: {s['query']}"

    def test_all_qa_samples_grounded(self, sim):
        for s in sim["qa_samples"]:
            if not s["insufficient"]:
                assert s["grounded"], f"Ungrounded: {s['query']}"

    def test_all_qa_samples_have_sources(self, sim):
        for s in sim["qa_samples"]:
            if not s["insufficient"]:
                assert s["has_sources"], f"Missing sources: {s['query']}"


class TestQACorrectness:
    """Validate reasoning output correctness."""

    @pytest.fixture(scope="class")
    def sim(self):
        return run_production_simulation()

    def test_risk_scores_valid(self, sim):
        valid_scores = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "INSUFFICIENT_DATA"}
        for s in sim["qa_samples"]:
            if s["template"] == "risk_assessment":
                assert s["score"] in valid_scores, f"Invalid score: {s['score']}"

    def test_overdue_entity_gets_high_risk(self, sim):
        sample = next(
            (
                s
                for s in sim["qa_samples"]
                if "Neptune" in s["query"] and s["template"] == "risk_assessment"
            ),
            None,
        )
        if sample:
            assert sample["score"] in ("HIGH", "CRITICAL")

    def test_clean_entity_gets_low_risk(self, sim):
        sample = next(
            (
                s
                for s in sim["qa_samples"]
                if "Maersk" in s["query"] and s["template"] == "risk_assessment"
            ),
            None,
        )
        if sample:
            assert sample["score"] == "LOW"

    def test_sanctioned_entity_gets_critical(self, sim):
        sample = next(
            (
                s
                for s in sim["qa_samples"]
                if "prospect" in s["query"] and s["template"] == "risk_assessment"
            ),
            None,
        )
        if sample:
            assert sample["score"] == "CRITICAL"

    def test_no_data_gets_insufficient(self, sim):
        sample = next((s for s in sim["qa_samples"] if "Unknown" in s["query"]), None)
        if sample:
            assert sample["score"] == "INSUFFICIENT_DATA"


class TestScalingDecision:
    """Phase A → Phase B gate decision."""

    def test_scaling_report(self):
        sim = run_production_simulation()

        print("\n" + "=" * 60)
        print("REASONING SYSTEM — PRODUCTION OPERATIONS REPORT")
        print("=" * 60)
        print(f"\nPhase: A (10% rollout)")
        print(f"Total queries simulated: {sim['total_queries']}")
        print(
            f"Reasoning detected: {sim['reasoning_detected']} ({sim['detection_rate']:.0%})"
        )
        print(
            f"Reasoning executed: {sim['reasoning_executed']} ({sim['execution_rate']:.0%})"
        )
        print(f"Successful: {sim['reasoning_successful']}")
        print(f"Fallbacks: {sim['reasoning_fallback']} ({sim['fallback_rate']:.0%})")
        print(
            f"Insufficient data: {sim['insufficient_data']} ({sim['insufficient_rate']:.0%})"
        )
        print(f"Conflicts detected: {sim['conflicts_detected']}")
        print(f"Avg confidence: {sim['avg_confidence']:.2f}")

        print(f"\nTemplate usage:")
        for t, c in sim["templates_used"].most_common():
            print(f"  {t}: {c}")

        print(f"\nScore distribution:")
        for s, c in Counter(sim["scores"]).most_common():
            print(f"  {s}: {c}")

        print(f"\nQA samples: {len(sim['qa_samples'])}")
        all_grounded = all(
            s["grounded"] for s in sim["qa_samples"] if not s["insufficient"]
        )
        all_criteria = all(
            s["has_criteria"] for s in sim["qa_samples"] if not s["insufficient"]
        )
        all_sources = all(
            s["has_sources"] for s in sim["qa_samples"] if not s["insufficient"]
        )
        print(f"  All grounded: {all_grounded}")
        print(f"  All have criteria: {all_criteria}")
        print(f"  All have sources: {all_sources}")

        print("\n" + "=" * 60)
        print("SCALING DECISION")
        print("=" * 60)
        checks = [
            ("Fallback rate < 10%", sim["fallback_rate"] < 0.10),
            ("Insufficient data ≤ 20%", sim["insufficient_rate"] <= 0.20),
            ("All QA grounded", all_grounded),
            ("All QA have criteria", all_criteria),
            ("All QA have sources", all_sources),
        ]
        all_pass = True
        for name, ok in checks:
            print(f"  {'✓' if ok else '✗'} {name}")
            if not ok:
                all_pass = False

        decision = "SCALE TO PHASE B (50%)" if all_pass else "HOLD AT PHASE A"
        print(f"\nDecision: {decision}")
        print("=" * 60)
