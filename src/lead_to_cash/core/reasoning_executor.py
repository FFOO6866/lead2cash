"""
Reasoning Executor — Phase P4

Orchestrates full reasoning plan execution:
1. Retrieval steps → existing pipeline (SourceAuthority → ToolExecutor → Enforcer)
2. Evaluation steps → deterministic evaluator functions
3. Synthesis step → structured output formatting

Phase P4: Full execution with feature flag control.
REASONING_EXECUTION_ENABLED=true to activate.

Safety: any failure → fallback to existing pipeline.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.reasoning_evaluator import (
    EVALUATOR_REGISTRY,
    EvaluationResult,
    StepData,
)
from lead_to_cash.core.reasoning_planner import ReasoningPlan, ReasoningStep
from lead_to_cash.core.response_quality import QualityMetrics
from lead_to_cash.core.source_authority import SourceAuthority

logger = logging.getLogger(__name__)

# Traffic rollout: hash query to deterministic bucket
ROLLOUT_PERCENTAGE = int(os.environ.get("REASONING_ROLLOUT_PCT", "100"))


@dataclass
class ReasoningResponse:
    """Final response from reasoning execution."""

    success: bool
    template: str
    score: str = ""
    recommendation: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    criteria_table: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    answer_text: str = ""
    fallback_reason: Optional[str] = None
    execution_time_ms: float = 0
    confidence_score: float = 0.0
    insufficient_data: bool = False
    conflict_detected: bool = False
    conflict_explanation: str = ""

    def to_response_dict(self, session_id: str = "") -> Dict[str, Any]:
        """Convert to response dict compatible with existing frontend."""
        if self.confidence_score >= 0.8:
            confidence_label = "HIGH"
        elif self.confidence_score >= 0.5:
            confidence_label = "MEDIUM"
        else:
            confidence_label = "LOW"

        result = {
            "type": "reasoning_report",
            "session_id": session_id,
            "answer": self.answer_text,
            "score": self.score,
            "recommendation": self.recommendation,
            "findings": self.findings,
            "criteria_table": self.criteria_table,
            "sources": self.sources,
            "confidence": confidence_label,
            "confidence_score": self.confidence_score,
            "template": self.template,
            "insufficient_data": self.insufficient_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if self.conflict_detected:
            result["conflict_detected"] = True
            result["conflict_explanation"] = self.conflict_explanation
        return result


class ReasoningExecutor:
    """Orchestrates reasoning plan execution."""

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if reasoning execution is enabled."""
        return os.environ.get("REASONING_EXECUTION_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )

    @classmethod
    def in_rollout_bucket(cls, query: str) -> bool:
        """Deterministic traffic routing for gradual rollout."""
        if ROLLOUT_PERCENTAGE >= 100:
            return True
        if ROLLOUT_PERCENTAGE <= 0:
            return False
        bucket = int(hashlib.md5(query.encode()).hexdigest()[:8], 16) % 100
        return bucket < ROLLOUT_PERCENTAGE

    @classmethod
    async def execute(
        cls,
        plan: ReasoningPlan,
        parsed: ParsedQuery,
        tool_executor: Any,
        inventory: Any,
        session_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[ReasoningResponse]:
        """
        Execute a reasoning plan.

        Returns ReasoningResponse on success, None on failure (signals fallback).
        """
        if not plan.valid:
            logger.warning(f"[Reasoning] Invalid plan: {plan.validation_errors}")
            return None

        start = datetime.now(UTC)
        step_outputs: Dict[str, StepData] = {}
        eval_result: Optional[EvaluationResult] = None
        sources: List[str] = []

        try:
            for step in plan.steps:
                if step.action == "retrieve":
                    output = await cls._execute_retrieval(
                        step, parsed, tool_executor, inventory, session_history
                    )
                    if output:
                        step_outputs[step.step_id] = output
                        if output.source:
                            sources.append(output.source)
                    else:
                        logger.warning(f"[Reasoning] Retrieval failed: {step.step_id}")

                elif step.action in ("evaluate", "compare", "decide"):
                    inputs = {
                        dep: step_outputs[dep]
                        for dep in step.input_from
                        if dep in step_outputs
                    }
                    result = cls._execute_evaluator(step, inputs)
                    if result:
                        eval_result = result
                        # Store as StepData for downstream steps
                        step_outputs[step.step_id] = StepData(
                            step_id=step.step_id,
                            data=result.to_dict(),
                            source="evaluator",
                        )
                    else:
                        logger.warning(f"[Reasoning] Evaluator failed: {step.step_id}")
                        return None

                elif step.action == "synthesize":
                    # Synthesis uses the evaluation result to build response
                    pass  # Handled below

        except Exception as e:
            logger.error(f"[Reasoning] Execution error: {e}")
            QualityMetrics.record(
                event_type="reasoning_execution_error",
                severity="ERROR",
                intent=parsed.intent.value,
                details={"error": str(e), "template": plan.template},
            )
            return None

        if not eval_result:
            return None

        # ── Insufficient data check ─────────────────────────────────
        is_insufficient = eval_result.score == "INSUFFICIENT_DATA"

        # ── Confidence scoring ──────────────────────────────────────
        # confidence = data_completeness × grounding × rule_strength
        data_completeness = len(step_outputs) / max(
            sum(1 for s in plan.steps if s.action == "retrieve"), 1
        )
        grounding_factor = 1.0 if eval_result.grounding_complete else 0.5
        rule_strength = 1.0 if eval_result.rules_applied else 0.3
        confidence_score = round(
            data_completeness * grounding_factor * rule_strength, 2
        )
        if is_insufficient:
            confidence_score = 0.0

        # ── Conflict detection ──────────────────────────────────────
        # Check if findings contain both CLEAR and ADVERSE for related dimensions
        conflict_detected = False
        conflict_explanation = ""
        if eval_result.findings:
            results_set = {f.result for f in eval_result.findings}
            has_clear = bool(results_set & {"CLEAR", "SUFFICIENT"})
            has_adverse = bool(results_set & {"ADVERSE", "CRITICAL", "INSUFFICIENT"})
            if has_clear and has_adverse:
                conflict_detected = True
                adverse_dims = [
                    f.dimension
                    for f in eval_result.findings
                    if f.result in ("ADVERSE", "CRITICAL")
                ]
                clear_dims = [
                    f.dimension for f in eval_result.findings if f.result == "CLEAR"
                ]
                conflict_explanation = (
                    f"Mixed signals: {', '.join(adverse_dims)} show risk "
                    f"while {', '.join(clear_dims)} are clear. "
                    f"Overall score driven by highest severity finding."
                )

        # Build response
        elapsed = (datetime.now(UTC) - start).total_seconds() * 1000

        answer = cls._format_answer(plan, eval_result)
        if conflict_detected:
            answer += f"\n\n**Note:** {conflict_explanation}"

        criteria = eval_result.rules_applied

        response = ReasoningResponse(
            success=not is_insufficient,
            template=plan.template,
            score=eval_result.score,
            recommendation=eval_result.recommendation,
            findings=[f.to_dict() for f in eval_result.findings],
            criteria_table=criteria,
            sources=list(set(sources)),
            answer_text=answer,
            execution_time_ms=elapsed,
            confidence_score=confidence_score,
            insufficient_data=is_insufficient,
            conflict_detected=conflict_detected,
            conflict_explanation=conflict_explanation,
        )

        # Log execution with full telemetry
        QualityMetrics.record(
            event_type="reasoning_executed",
            severity="INFO" if not is_insufficient else "WARNING",
            intent=parsed.intent.value,
            details={
                "success": not is_insufficient,
                "template": plan.template,
                "reasoning_type": plan.reasoning_type,
                "score": eval_result.score,
                "confidence_score": confidence_score,
                "finding_count": len(eval_result.findings),
                "grounding_complete": eval_result.grounding_complete,
                "sources": sources,
                "execution_time_ms": elapsed,
                "step_count": len(plan.steps),
                "insufficient_data": is_insufficient,
                "conflict_detected": conflict_detected,
            },
        )

        return response

    @classmethod
    async def _execute_retrieval(
        cls,
        step: ReasoningStep,
        parsed: ParsedQuery,
        tool_executor: Any,
        inventory: Any,
        history: Optional[List[Dict[str, str]]],
    ) -> Optional[StepData]:
        """Execute a retrieval step via the existing pipeline."""
        try:
            sub_parsed = ParsedQuery(
                raw_query=step.query_fragment or parsed.raw_query,
                intent=QueryIntent(step.intent),
                intent_confidence=0.9,
                companies=parsed.companies,
                competitors=parsed.competitors,
            )
            source_decision = SourceAuthority.decide(sub_parsed, inventory)
            result = await tool_executor.execute(
                sub_parsed,
                inventory,
                conversation_history=history,
                source_decision=source_decision,
            )
            return StepData(
                step_id=step.step_id,
                data={
                    "content": result.synthesized_content or "",
                    "tools_used": [t.value for t in result.tools_used],
                },
                source=result.sources[0] if result.sources else "",
                source_tier="governed",
            )
        except Exception as e:
            logger.warning(f"[Reasoning] Retrieval error for {step.step_id}: {e}")
            return None

    @classmethod
    def _execute_evaluator(
        cls,
        step: ReasoningStep,
        inputs: Dict[str, StepData],
    ) -> Optional[EvaluationResult]:
        """Execute a deterministic evaluator function."""
        evaluator_fn = EVALUATOR_REGISTRY.get(step.evaluator or "")
        if not evaluator_fn:
            logger.warning(f"[Reasoning] Unknown evaluator: {step.evaluator}")
            return None
        try:
            return evaluator_fn(inputs)
        except Exception as e:
            logger.error(f"[Reasoning] Evaluator {step.evaluator} error: {e}")
            return None

    @classmethod
    def _format_answer(cls, plan: ReasoningPlan, result: EvaluationResult) -> str:
        """Format evaluation result into readable response text."""
        lines = []

        # Header
        template_labels = {
            "risk_assessment": "Risk Assessment",
            "product_comparison": "Product Comparison",
            "credit_feasibility": "Credit Feasibility Analysis",
            "customer_deep_dive": "Customer Profile Analysis",
            "competitive_positioning": "Competitive Position Analysis",
        }
        title = template_labels.get(plan.template, "Analysis")
        lines.append(f"## {title}: {plan.entity or 'Assessment'}")
        lines.append("")

        # Score
        lines.append(f"**Overall Assessment: {result.score}**")
        lines.append("")

        # Recommendation
        if result.recommendation:
            lines.append(f"**Recommendation:** {result.recommendation}")
            lines.append("")

        # Criteria table
        if result.rules_applied:
            lines.append("**Criteria Applied:**")
            for rule in result.rules_applied:
                lines.append(f"- {rule}")
            lines.append("")

        # Findings
        if result.findings:
            lines.append("**Findings:**")
            lines.append("")
            for i, f in enumerate(result.findings, 1):
                status_icon = {
                    "CLEAR": "✓",
                    "CAUTION": "⚠",
                    "ADVERSE": "✗",
                    "CRITICAL": "🚫",
                    "ADVANTAGE": "✓",
                    "GAP": "✗",
                    "PARITY": "≈",
                    "SUFFICIENT": "✓",
                    "INSUFFICIENT": "✗",
                }.get(f.result, "•")
                source_ref = f" [Source: {f.source_name}]" if f.source_name else ""
                lines.append(
                    f"{i}. {status_icon} **{f.dimension}**: {f.result} — {f.detail}{source_ref}"
                )
            lines.append("")

        # Grounding note
        if result.grounding_complete:
            lines.append(
                "*All findings are grounded in retrieved data with full traceability.*"
            )
        else:
            lines.append(
                "*Some findings could not be fully verified from available data.*"
            )

        return "\n".join(lines)
