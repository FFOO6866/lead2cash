"""
Reasoning Evaluator — Phase P3

Deterministic evaluation functions that produce grounded conclusions
from structured retrieval data. NO LLM involvement.

Each evaluator:
1. Receives structured input data (from retrieval steps)
2. Applies explicit threshold rules
3. Produces findings with full grounding chain
4. Is a pure function (no randomness, no side effects)

Phase P3: Validation only. Evaluators run against sample data
to verify correctness. No production impact.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class GroundedFinding:
    """A single finding with full traceability."""

    dimension: str
    result: str  # CLEAR | CAUTION | ADVERSE | CRITICAL
    detail: str
    data_value: Any = None
    threshold: str = ""
    source_step: str = ""
    source_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "result": self.result,
            "detail": self.detail,
            "data_value": self.data_value,
            "threshold": self.threshold,
            "source_step": self.source_step,
            "source_name": self.source_name,
        }


@dataclass
class EvaluationResult:
    """Output of a deterministic evaluator function."""

    evaluator: str
    score: str  # Overall conclusion (e.g., LOW/MEDIUM/HIGH/CRITICAL)
    findings: List[GroundedFinding] = field(default_factory=list)
    recommendation: str = ""
    grounding_complete: bool = True
    rules_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "score": self.score,
            "finding_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "recommendation": self.recommendation,
            "grounding_complete": self.grounding_complete,
            "rules_applied": self.rules_applied,
        }


# =============================================================================
# Step data (simulated retrieval output for validation)
# =============================================================================


@dataclass
class StepData:
    """Structured data from a retrieval step (or simulated for validation)."""

    step_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    source_tier: str = ""


# =============================================================================
# Evaluator functions — all deterministic, no LLM
# =============================================================================


def risk_scoring(inputs: Dict[str, StepData]) -> EvaluationResult:
    """
    Evaluate risk based on billing + KYP data.

    Rules (explicit, auditable):
    - sanctions_found = True → CRITICAL
    - max_overdue_days > 45 → HIGH
    - credit_utilization > 0.80 → MEDIUM
    - default → LOW
    """
    findings = []
    risk_level = "LOW"
    rules = [
        "sanctions_found → CRITICAL",
        "max_overdue_days > 45 → HIGH",
        "credit_utilization > 80% → MEDIUM",
        "default → LOW",
    ]

    billing = inputs.get("s1_billing")
    kyp = inputs.get("s2_kyp")

    # Insufficient data guard: if both inputs are missing, cannot assess
    if not billing and not kyp:
        return EvaluationResult(
            evaluator="risk_scoring",
            score="INSUFFICIENT_DATA",
            recommendation="Unable to assess risk — no billing or compliance data available.",
            grounding_complete=False,
            rules_applied=rules,
        )

    # Rule 1: Sanctions
    if kyp:
        sanctions = kyp.data.get("sanctions_found", False)
        if sanctions:
            risk_level = "CRITICAL"
            findings.append(
                GroundedFinding(
                    dimension="Sanctions",
                    result="CRITICAL",
                    detail="Active sanctions match found",
                    data_value=True,
                    threshold="sanctions_found → CRITICAL",
                    source_step="s2_kyp",
                    source_name=kyp.source,
                )
            )
        else:
            findings.append(
                GroundedFinding(
                    dimension="Sanctions",
                    result="CLEAR",
                    detail="No sanctions matches",
                    data_value=False,
                    threshold="sanctions_found → CRITICAL",
                    source_step="s2_kyp",
                    source_name=kyp.source,
                )
            )

    # Rule 2: Payment timeliness
    if billing:
        overdue = billing.data.get("max_overdue_days", 0)
        if overdue > 45:
            risk_level = _max_risk(risk_level, "HIGH")
            findings.append(
                GroundedFinding(
                    dimension="Payment Timeliness",
                    result="ADVERSE",
                    detail=f"{overdue} days overdue",
                    data_value=overdue,
                    threshold="max_overdue_days > 45 → HIGH",
                    source_step="s1_billing",
                    source_name=billing.source,
                )
            )
        else:
            findings.append(
                GroundedFinding(
                    dimension="Payment Timeliness",
                    result="CLEAR",
                    detail=f"{overdue} days (within tolerance)",
                    data_value=overdue,
                    threshold="max_overdue_days > 45 → HIGH",
                    source_step="s1_billing",
                    source_name=billing.source,
                )
            )

    # Rule 3: Credit utilization
    if billing:
        util = billing.data.get("credit_utilization", 0)
        if util > 0.80:
            risk_level = _max_risk(risk_level, "MEDIUM")
            findings.append(
                GroundedFinding(
                    dimension="Credit Utilization",
                    result="CAUTION",
                    detail=f"{util:.0%} utilized",
                    data_value=util,
                    threshold="credit_utilization > 80% → MEDIUM",
                    source_step="s1_billing",
                    source_name=billing.source,
                )
            )
        else:
            findings.append(
                GroundedFinding(
                    dimension="Credit Utilization",
                    result="CLEAR",
                    detail=f"{util:.0%} utilized",
                    data_value=util,
                    threshold="credit_utilization > 80% → MEDIUM",
                    source_step="s1_billing",
                    source_name=billing.source,
                )
            )

    grounded = all(f.source_step for f in findings)

    return EvaluationResult(
        evaluator="risk_scoring",
        score=risk_level,
        findings=findings,
        recommendation=_risk_recommendation(risk_level),
        grounding_complete=grounded,
        rules_applied=rules,
    )


def product_comparison(inputs: Dict[str, StepData]) -> EvaluationResult:
    """
    Compare two products across dimensions.

    Dimensions: power, fuel_efficiency, service_network, emissions, cost
    """
    product = inputs.get("s1_product")
    competitor = inputs.get("s2_competitor")
    findings = []
    our_wins = 0
    their_wins = 0

    dimensions = [
        "power_kw",
        "fuel_efficiency",
        "service_coverage",
        "emissions_tier",
        "lifecycle_cost",
    ]
    labels = [
        "Power (kW)",
        "Fuel Efficiency",
        "Service Network",
        "Emissions",
        "Lifecycle Cost",
    ]

    for dim, label in zip(dimensions, labels):
        our_val = product.data.get(dim) if product else None
        their_val = competitor.data.get(dim) if competitor else None

        if our_val is not None and their_val is not None:
            if isinstance(our_val, (int, float)) and isinstance(
                their_val, (int, float)
            ):
                if our_val > their_val:
                    result = "ADVANTAGE"
                    our_wins += 1
                elif our_val < their_val:
                    result = "GAP"
                    their_wins += 1
                else:
                    result = "PARITY"
            else:
                result = "PARITY"
        else:
            result = "INSUFFICIENT_DATA"

        findings.append(
            GroundedFinding(
                dimension=label,
                result=result,
                detail=f"Ours: {our_val}, Theirs: {their_val}",
                data_value={"ours": our_val, "theirs": their_val},
                threshold="higher value = ADVANTAGE",
                source_step="s1_product" if product else "",
                source_name=product.source if product else "",
            )
        )

    score = (
        "ADVANTAGE"
        if our_wins > their_wins
        else ("GAP" if their_wins > our_wins else "PARITY")
    )

    return EvaluationResult(
        evaluator="product_comparison",
        score=score,
        findings=findings,
        recommendation=f"Overall: {score} ({our_wins} wins vs {their_wins} losses)",
        grounding_complete=bool(product and competitor),
        rules_applied=["dimension_by_dimension", "majority_wins"],
    )


def credit_feasibility(inputs: Dict[str, StepData]) -> EvaluationResult:
    """
    Evaluate credit feasibility for a specific order value.
    """
    billing = inputs.get("s1_credit")
    findings = []

    available = billing.data.get("available_credit", 0) if billing else 0
    order_value = billing.data.get("order_value", 0) if billing else 0
    sufficient = available >= order_value

    findings.append(
        GroundedFinding(
            dimension="Credit Availability",
            result="SUFFICIENT" if sufficient else "INSUFFICIENT",
            detail=f"Available: {available:,.0f}, Required: {order_value:,.0f}",
            data_value={"available": available, "required": order_value},
            threshold="available_credit >= order_value",
            source_step="s1_credit",
            source_name=billing.source if billing else "",
        )
    )

    if not sufficient:
        shortfall = order_value - available
        findings.append(
            GroundedFinding(
                dimension="Shortfall",
                result="ADVERSE",
                detail=f"Shortfall: {shortfall:,.0f}",
                data_value=shortfall,
                threshold="order_value - available_credit",
                source_step="s1_credit",
                source_name=billing.source if billing else "",
            )
        )

    return EvaluationResult(
        evaluator="credit_feasibility",
        score="SUFFICIENT" if sufficient else "INSUFFICIENT",
        findings=findings,
        recommendation="Order can proceed"
        if sufficient
        else f"Shortfall of {order_value - available:,.0f}",
        grounding_complete=bool(billing),
        rules_applied=["available_credit >= order_value"],
    )


def recommendation_with_rationale(inputs: Dict[str, StepData]) -> EvaluationResult:
    """
    Produce a recommendation from comparison results.
    """
    comparison = inputs.get("s3_compare")
    if not comparison:
        return EvaluationResult(
            evaluator="recommendation_with_rationale",
            score="INSUFFICIENT_DATA",
            recommendation="Cannot recommend without comparison data",
            grounding_complete=False,
            rules_applied=["requires_comparison_input"],
        )

    score = comparison.data.get("score", "PARITY")
    wins = comparison.data.get("our_wins", 0)
    losses = comparison.data.get("their_wins", 0)

    if score == "ADVANTAGE":
        reco = f"Recommend our product: wins on {wins} of {wins + losses} dimensions"
    elif score == "GAP":
        reco = (
            f"Competitor leads on {losses} dimensions — consider positioning carefully"
        )
    else:
        reco = "Products are comparable — differentiate on service and relationship"

    return EvaluationResult(
        evaluator="recommendation_with_rationale",
        score=score,
        recommendation=reco,
        grounding_complete=True,
        rules_applied=["majority_advantage_wins", "include_rationale"],
    )


def conditional_recommendation(inputs: Dict[str, StepData]) -> EvaluationResult:
    """
    Conditional recommendation based on feasibility evaluation.
    """
    feasibility = inputs.get("s2_evaluate")
    if not feasibility:
        return EvaluationResult(
            evaluator="conditional_recommendation",
            score="INSUFFICIENT_DATA",
            recommendation="Cannot evaluate condition without feasibility data",
            grounding_complete=False,
            rules_applied=["requires_feasibility_input"],
        )

    is_feasible = feasibility.data.get("score") == "SUFFICIENT"
    if is_feasible:
        reco = "Condition met: proceed with proposed action"
        score = "PROCEED"
    else:
        reco = "Condition NOT met: alternative approach needed"
        score = "HOLD"

    return EvaluationResult(
        evaluator="conditional_recommendation",
        score=score,
        recommendation=reco,
        grounding_complete=True,
        rules_applied=["if_feasible_then_proceed", "else_hold"],
    )


# =============================================================================
# Evaluator registry
# =============================================================================

EVALUATOR_REGISTRY: Dict[str, Callable] = {
    "risk_scoring": risk_scoring,
    "product_comparison": product_comparison,
    "credit_feasibility": credit_feasibility,
    "recommendation_with_rationale": recommendation_with_rationale,
    "conditional_recommendation": conditional_recommendation,
}


def get_evaluator(name: str) -> Optional[Callable]:
    """Get an evaluator function by name."""
    return EVALUATOR_REGISTRY.get(name)


# =============================================================================
# Helpers
# =============================================================================

_RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _max_risk(current: str, new: str) -> str:
    """Return the higher risk level."""
    if _RISK_ORDER.get(new, 0) > _RISK_ORDER.get(current, 0):
        return new
    return current


def _risk_recommendation(level: str) -> str:
    """Generate recommendation text from risk level."""
    recs = {
        "LOW": "Risk is low. Proceed with standard terms.",
        "MEDIUM": "Moderate risk. Monitor payment behavior and credit utilization.",
        "HIGH": "Elevated risk. Require advance payment or credit insurance.",
        "CRITICAL": "Critical risk. Do not proceed without compliance clearance.",
    }
    return recs.get(level, "Unable to determine risk level.")
