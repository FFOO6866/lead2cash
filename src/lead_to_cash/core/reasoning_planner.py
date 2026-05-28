"""
Reasoning Planner — Phase P2

Generates structured ReasoningPlans from detected reasoning queries.
Uses a deterministic template library — NO LLM involvement.

Phase P2: Plan generation and logging ONLY. No execution.

Each plan is a DAG of steps: retrieve → evaluate → synthesize.
Steps map to existing Signal Router intents for retrieval
and to named evaluator functions for evaluation (future Phase P3).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Plan data structures
# =============================================================================


@dataclass
class ReasoningStep:
    """A single step in a reasoning plan."""

    step_id: str
    action: str  # retrieve | evaluate | compare | decide | synthesize
    intent: Optional[str] = None  # Signal Router intent (for retrieve steps)
    evaluator: Optional[str] = None  # Named evaluator function (for eval steps)
    input_from: List[str] = field(default_factory=list)
    output_to: List[str] = field(default_factory=list)
    query_fragment: str = ""
    grounding_rule: str = "must_cite_source"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "intent": self.intent,
            "evaluator": self.evaluator,
            "input_from": self.input_from,
            "output_to": self.output_to,
            "grounding_rule": self.grounding_rule,
        }


@dataclass
class ReasoningPlan:
    """A structured reasoning plan (DAG of steps)."""

    template: str
    reasoning_type: str
    entity: str = ""
    steps: List[ReasoningStep] = field(default_factory=list)
    valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "reasoning_type": self.reasoning_type,
            "entity": self.entity,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "valid": self.valid,
            "validation_errors": self.validation_errors,
        }


# =============================================================================
# Template library — deterministic plan structures
# =============================================================================


def _risk_assessment(entity: str, query: str) -> ReasoningPlan:
    """Risk assessment: billing + KYP → evaluate risk → synthesize."""
    return ReasoningPlan(
        template="risk_assessment",
        reasoning_type="evaluate",
        entity=entity,
        steps=[
            ReasoningStep(
                step_id="s1_billing",
                action="retrieve",
                intent="billing_ar",
                query_fragment=f"{entity} payment history and credit status",
                output_to=["s3_evaluate"],
            ),
            ReasoningStep(
                step_id="s2_kyp",
                action="retrieve",
                intent="kyp_due_diligence",
                query_fragment=f"{entity} sanctions and compliance status",
                output_to=["s3_evaluate"],
            ),
            ReasoningStep(
                step_id="s3_evaluate",
                action="evaluate",
                evaluator="risk_scoring",
                input_from=["s1_billing", "s2_kyp"],
                output_to=["s4_synthesize"],
                grounding_rule="must_show_criteria",
            ),
            ReasoningStep(
                step_id="s4_synthesize",
                action="synthesize",
                input_from=["s3_evaluate"],
                grounding_rule="must_show_criteria",
            ),
        ],
    )


def _product_comparison(entity: str, query: str) -> ReasoningPlan:
    """Product comparison: product + competitor → compare → recommend → synthesize."""
    return ReasoningPlan(
        template="product_comparison",
        reasoning_type="compare_recommend",
        entity=entity,
        steps=[
            ReasoningStep(
                step_id="s1_product",
                action="retrieve",
                intent="product_fit",
                query_fragment=f"MTU engine specifications for {entity or 'application'}",
                output_to=["s3_compare"],
            ),
            ReasoningStep(
                step_id="s2_competitor",
                action="retrieve",
                intent="competitor_intel",
                query_fragment=f"Competitor engine specifications for {entity or 'application'}",
                output_to=["s3_compare"],
            ),
            ReasoningStep(
                step_id="s3_compare",
                action="compare",
                evaluator="product_comparison",
                input_from=["s1_product", "s2_competitor"],
                output_to=["s4_recommend"],
                grounding_rule="must_cite_source",
            ),
            ReasoningStep(
                step_id="s4_recommend",
                action="decide",
                evaluator="recommendation_with_rationale",
                input_from=["s3_compare"],
                output_to=["s5_synthesize"],
                grounding_rule="must_show_criteria",
            ),
            ReasoningStep(
                step_id="s5_synthesize",
                action="synthesize",
                input_from=["s4_recommend"],
                grounding_rule="must_show_criteria",
            ),
        ],
    )


def _credit_feasibility(entity: str, query: str) -> ReasoningPlan:
    """Credit feasibility: billing → evaluate → conditional action → synthesize."""
    return ReasoningPlan(
        template="credit_feasibility",
        reasoning_type="multi_hop",
        entity=entity,
        steps=[
            ReasoningStep(
                step_id="s1_credit",
                action="retrieve",
                intent="billing_ar",
                query_fragment=f"{entity} credit status and available credit",
                output_to=["s2_evaluate"],
            ),
            ReasoningStep(
                step_id="s2_evaluate",
                action="evaluate",
                evaluator="credit_feasibility",
                input_from=["s1_credit"],
                output_to=["s3_decide"],
                grounding_rule="must_show_criteria",
            ),
            ReasoningStep(
                step_id="s3_decide",
                action="decide",
                evaluator="conditional_recommendation",
                input_from=["s2_evaluate"],
                output_to=["s4_synthesize"],
                grounding_rule="must_show_criteria",
            ),
            ReasoningStep(
                step_id="s4_synthesize",
                action="synthesize",
                input_from=["s3_decide"],
                grounding_rule="must_show_criteria",
            ),
        ],
    )


def _customer_deep_dive(entity: str, query: str) -> ReasoningPlan:
    """Customer deep dive: customer + billing + opportunities → synthesize."""
    return ReasoningPlan(
        template="customer_deep_dive",
        reasoning_type="summarize",
        entity=entity,
        steps=[
            ReasoningStep(
                step_id="s1_customer",
                action="retrieve",
                intent="customer_intel",
                query_fragment=f"{entity} customer profile and fleet",
                output_to=["s4_synthesize"],
            ),
            ReasoningStep(
                step_id="s2_billing",
                action="retrieve",
                intent="billing_ar",
                query_fragment=f"{entity} payment and billing status",
                output_to=["s4_synthesize"],
            ),
            ReasoningStep(
                step_id="s3_opportunities",
                action="retrieve",
                intent="customer_intel",
                query_fragment=f"{entity} CEC opportunities and pipeline",
                output_to=["s4_synthesize"],
            ),
            ReasoningStep(
                step_id="s4_synthesize",
                action="synthesize",
                input_from=["s1_customer", "s2_billing", "s3_opportunities"],
                grounding_rule="must_reference_step",
            ),
        ],
    )


def _competitive_positioning(entity: str, query: str) -> ReasoningPlan:
    """Competitive positioning: competitor + market → evaluate → synthesize."""
    return ReasoningPlan(
        template="competitive_positioning",
        reasoning_type="evaluate",
        entity=entity,
        steps=[
            ReasoningStep(
                step_id="s1_competitor",
                action="retrieve",
                intent="competitor_intel",
                query_fragment=f"Competitive landscape for {entity or 'APAC market'}",
                output_to=["s3_evaluate"],
            ),
            ReasoningStep(
                step_id="s2_market",
                action="retrieve",
                intent="market_intel",
                query_fragment=f"Market trends for {entity or 'APAC'}",
                output_to=["s3_evaluate"],
            ),
            ReasoningStep(
                step_id="s3_evaluate",
                action="evaluate",
                evaluator="competitive_positioning",
                input_from=["s1_competitor", "s2_market"],
                output_to=["s4_synthesize"],
                grounding_rule="must_show_criteria",
            ),
            ReasoningStep(
                step_id="s4_synthesize",
                action="synthesize",
                input_from=["s3_evaluate"],
                grounding_rule="must_show_criteria",
            ),
        ],
    )


# Template registry
_TEMPLATE_BUILDERS = {
    "risk_assessment": _risk_assessment,
    "product_comparison": _product_comparison,
    "credit_feasibility": _credit_feasibility,
    "customer_deep_dive": _customer_deep_dive,
    "competitive_positioning": _competitive_positioning,
}

# Template selection: reasoning_type → default template
_TYPE_TO_DEFAULT_TEMPLATE = {
    "evaluate": "risk_assessment",
    "compare_recommend": "product_comparison",
    "multi_hop": "credit_feasibility",
    "summarize": "customer_deep_dive",
}

MAX_STEPS = 5


# =============================================================================
# Plan generation
# =============================================================================


class ReasoningPlanner:
    """Deterministic template-based reasoning planner."""

    @classmethod
    def generate(
        cls,
        query: str,
        reasoning_type: str,
        matched_template: Optional[str] = None,
        entity: str = "",
        intent: Optional[str] = None,
    ) -> ReasoningPlan:
        """
        Generate a ReasoningPlan from a detected reasoning query.

        Args:
            query: The raw user query
            reasoning_type: Detected type (evaluate, compare_recommend, multi_hop, summarize)
            matched_template: Template hint from detector (may be None)
            entity: Primary entity name
            intent: Current parsed intent

        Returns:
            ReasoningPlan (may be invalid if no template matches)
        """
        # Select template
        template_name = matched_template or _TYPE_TO_DEFAULT_TEMPLATE.get(
            reasoning_type
        )
        if not template_name or template_name not in _TEMPLATE_BUILDERS:
            return ReasoningPlan(
                template="unknown",
                reasoning_type=reasoning_type,
                entity=entity,
                valid=False,
                validation_errors=[f"No template for type '{reasoning_type}'"],
            )

        # Build plan from template
        builder = _TEMPLATE_BUILDERS[template_name]
        plan = builder(entity or "entity", query)

        # Validate
        errors = cls._validate(plan)
        if errors:
            plan.valid = False
            plan.validation_errors = errors

        return plan

    @classmethod
    def _validate(cls, plan: ReasoningPlan) -> List[str]:
        """Validate plan structure."""
        errors = []

        # Check step count
        if len(plan.steps) > MAX_STEPS:
            errors.append(f"Too many steps: {len(plan.steps)} > {MAX_STEPS}")

        # Check for cycles
        if cls._has_cycle(plan.steps):
            errors.append("Plan contains dependency cycle")

        # Check all step IDs are unique
        ids = [s.step_id for s in plan.steps]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate step IDs")

        # Check dependencies reference existing steps
        id_set = set(ids)
        for step in plan.steps:
            for dep in step.input_from:
                if dep not in id_set:
                    errors.append(f"Step {step.step_id} depends on unknown step {dep}")

        # Check retrieve steps have intents
        for step in plan.steps:
            if step.action == "retrieve" and not step.intent:
                errors.append(f"Retrieve step {step.step_id} has no intent")

        # Check evaluate steps have evaluators
        for step in plan.steps:
            if step.action in ("evaluate", "compare", "decide") and not step.evaluator:
                errors.append(f"Evaluation step {step.step_id} has no evaluator")

        return errors

    @classmethod
    def _has_cycle(cls, steps: List[ReasoningStep]) -> bool:
        """Check for dependency cycles using DFS."""
        graph = {s.step_id: s.output_to for s in steps}
        visited = set()
        in_stack = set()

        def dfs(node: str) -> bool:
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for neighbor in graph.get(node, []):
                if dfs(neighbor):
                    return True
            in_stack.discard(node)
            return False

        for step in steps:
            if dfs(step.step_id):
                return True
        return False
