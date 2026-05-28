"""
Compound Query Executor

Executes multi-intent queries by running ToolExecutor independently
per sub-intent with full source isolation.

Supports:
- Parallel execution (asyncio.gather for independent sub-intents)
- Sequential execution (dependency chain with context passing)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from lead_to_cash.core.data_inventory import InventoryCheckResult
from lead_to_cash.core.multi_intent_detector import CompoundQuery, SubIntent
from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.response_quality import QualityMetrics
from lead_to_cash.core.source_authority import SourceAuthority

logger = logging.getLogger(__name__)

# Maximum total execution time for compound queries
COMPOUND_TIMEOUT_PARALLEL = 35.0  # seconds
COMPOUND_TIMEOUT_SEQUENTIAL = 45.0  # Hardened: reduced from 50s to 45s

# Confidence penalty per additional sub-intent
CONFIDENCE_PENALTY_PER_SUB = 0.05

# Minimum successful sub-intents to avoid full fallback
MIN_SUCCESSFUL_SUBS = 1


@dataclass
class SubIntentResult:
    """Result from executing one sub-intent."""

    intent: str
    answer: str
    sources: List[str]
    confidence: str
    tools_used: List[str]
    execution_time_ms: float
    status: str = "success"  # success, failed, timeout
    error: Optional[str] = None


@dataclass
class CompoundResult:
    """Combined result from all sub-intents."""

    sub_results: List[SubIntentResult]
    execution_order: str
    merge_strategy: str
    total_time_ms: float
    partial_success: bool = False

    @property
    def all_sources(self) -> List[str]:
        seen = set()
        sources = []
        for sr in self.sub_results:
            for s in sr.sources:
                if s not in seen:
                    seen.add(s)
                    sources.append(s)
        return sources

    @property
    def all_tools(self) -> List[str]:
        seen = set()
        tools = []
        for sr in self.sub_results:
            for t in sr.tools_used:
                if t not in seen:
                    seen.add(t)
                    tools.append(t)
        return tools


class CompoundExecutor:
    """
    Executes compound queries with per-sub-intent isolation.

    Each sub-intent gets:
    - Its own SourceAuthority decision
    - Its own ToolExecutor call
    - Its own timeout
    """

    @classmethod
    async def execute(
        cls,
        compound: CompoundQuery,
        base_parsed: ParsedQuery,
        inventory: InventoryCheckResult,
        tool_executor: Any,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> CompoundResult:
        """
        Execute a compound query.

        Args:
            compound: The detected CompoundQuery
            base_parsed: The original ParsedQuery (used as template)
            inventory: Data inventory check result
            tool_executor: The ToolExecutor instance
            conversation_history: Session history for context

        Returns:
            CompoundResult with all sub-intent results
        """
        start = datetime.now(UTC)

        # Hardening: confidence adjustment for compound complexity
        n_subs = len(compound.sub_intents)
        adjusted_confidence = compound.compound_confidence - (
            CONFIDENCE_PENALTY_PER_SUB * (n_subs - 1)
        )

        if compound.execution_order == "sequential":
            sub_results = await cls._execute_sequential(
                compound, base_parsed, inventory, tool_executor, conversation_history
            )
        else:
            sub_results = await cls._execute_parallel(
                compound, base_parsed, inventory, tool_executor, conversation_history
            )

        total_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        successful = [sr for sr in sub_results if sr.status == "success"]
        failed = [sr for sr in sub_results if sr.status != "success"]
        partial = len(failed) > 0

        # Hardening: classify failure type for incident tracking
        failure_type = None
        if failed:
            error_msgs = [sr.error or "" for sr in failed]
            if any("timeout" in (e or "").lower() for e in error_msgs):
                failure_type = "execution_timeout"
            elif any("SourceAuthority" in (e or "") for e in error_msgs):
                failure_type = "source_blocked"
            else:
                failure_type = "execution_error"

        # Hardening: fallback trigger — if too many sub-intents fail,
        # return None to signal caller to fall through to single-intent
        if len(successful) < MIN_SUCCESSFUL_SUBS:
            logger.warning(
                f"[Compound Fallback] {len(failed)}/{n_subs} sub-intents failed. "
                f"Triggering single-intent fallback."
            )
            QualityMetrics.record(
                event_type="compound_fallback",
                severity="WARNING",
                intent=compound.sub_intents[0].intent
                if compound.sub_intents
                else "unknown",
                details={
                    "reason": "insufficient_successful_subs",
                    "successful": len(successful),
                    "failed": len(failed),
                    "failure_type": failure_type,
                },
            )
            return None  # Signals caller to use single-intent path

        result = CompoundResult(
            sub_results=sub_results,
            execution_order=compound.execution_order,
            merge_strategy=compound.merge_strategy,
            total_time_ms=total_ms,
            partial_success=partial,
        )

        # Log compound execution with hardened metrics
        QualityMetrics.record(
            event_type="compound_query_execution",
            severity="INFO" if not partial else "WARNING",
            intent=compound.sub_intents[0].intent
            if compound.sub_intents
            else "unknown",
            details={
                "compound_confidence": round(adjusted_confidence, 3),
                "original_confidence": compound.compound_confidence,
                "detection_method": compound.detection_method,
                "sub_intent_count": n_subs,
                "execution_order": compound.execution_order,
                "merge_strategy": compound.merge_strategy,
                "successful_subs": len(successful),
                "failed_subs": len(failed),
                "failure_type": failure_type,
                "sub_intents": [
                    {
                        "intent": sr.intent,
                        "status": sr.status,
                        "time_ms": sr.execution_time_ms,
                        "sources": len(sr.sources),
                    }
                    for sr in sub_results
                ],
                "total_time_ms": total_ms,
                "partial_success": partial,
            },
        )

        return result

    @classmethod
    async def _execute_parallel(
        cls,
        compound: CompoundQuery,
        base_parsed: ParsedQuery,
        inventory: InventoryCheckResult,
        tool_executor: Any,
        history: Optional[List[Dict[str, str]]],
    ) -> List[SubIntentResult]:
        """Execute all sub-intents in parallel."""
        tasks = []
        for sub in compound.sub_intents:
            tasks.append(
                cls._execute_single_sub_intent(
                    sub, base_parsed, inventory, tool_executor, history
                )
            )

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=COMPOUND_TIMEOUT_PARALLEL,
            )
        except asyncio.TimeoutError:
            logger.warning("Compound parallel execution timed out")
            return [
                SubIntentResult(
                    intent=sub.intent,
                    answer="Execution timed out for this section.",
                    sources=[],
                    confidence="LOW",
                    tools_used=[],
                    execution_time_ms=COMPOUND_TIMEOUT_PARALLEL * 1000,
                    status="timeout",
                )
                for sub in compound.sub_intents
            ]

        sub_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sub_results.append(
                    SubIntentResult(
                        intent=compound.sub_intents[i].intent,
                        answer="This section could not be completed.",
                        sources=[],
                        confidence="LOW",
                        tools_used=[],
                        execution_time_ms=0,
                        status="failed",
                        error=str(result),
                    )
                )
            else:
                sub_results.append(result)

        return sub_results

    @classmethod
    async def _execute_sequential(
        cls,
        compound: CompoundQuery,
        base_parsed: ParsedQuery,
        inventory: InventoryCheckResult,
        tool_executor: Any,
        history: Optional[List[Dict[str, str]]],
    ) -> List[SubIntentResult]:
        """Execute sub-intents sequentially, passing context from each to the next."""
        sub_results = []
        context_history = list(history) if history else []

        for sub in compound.sub_intents:
            try:
                result = await asyncio.wait_for(
                    cls._execute_single_sub_intent(
                        sub, base_parsed, inventory, tool_executor, context_history
                    ),
                    timeout=COMPOUND_TIMEOUT_SEQUENTIAL / len(compound.sub_intents),
                )
                sub_results.append(result)
                # Pass result as context to next sub-intent
                if result.status == "success" and result.answer:
                    context_history.append(
                        {
                            "role": "assistant",
                            "content": f"[{result.intent} analysis]: {result.answer[:1000]}",
                        }
                    )
            except asyncio.TimeoutError:
                sub_results.append(
                    SubIntentResult(
                        intent=sub.intent,
                        answer="This section timed out.",
                        sources=[],
                        confidence="LOW",
                        tools_used=[],
                        execution_time_ms=0,
                        status="timeout",
                    )
                )
            except Exception as e:
                sub_results.append(
                    SubIntentResult(
                        intent=sub.intent,
                        answer="This section could not be completed.",
                        sources=[],
                        confidence="LOW",
                        tools_used=[],
                        execution_time_ms=0,
                        status="failed",
                        error=str(e),
                    )
                )

        return sub_results

    @classmethod
    async def _execute_single_sub_intent(
        cls,
        sub: SubIntent,
        base_parsed: ParsedQuery,
        inventory: InventoryCheckResult,
        tool_executor: Any,
        history: Optional[List[Dict[str, str]]],
    ) -> SubIntentResult:
        """Execute a single sub-intent with isolated source authority."""
        start = datetime.now(UTC)

        # Create a modified ParsedQuery for this sub-intent
        sub_parsed = ParsedQuery(
            raw_query=sub.query_fragment,
            intent=QueryIntent(sub.intent),
            intent_confidence=sub.confidence,
            companies=base_parsed.companies,
            competitors=base_parsed.competitors,
            products=base_parsed.products,
            regions=base_parsed.regions,
            market_intel_style=base_parsed.market_intel_style,
            competitor_intel_style=base_parsed.competitor_intel_style,
        )

        # Independent source authority decision
        source_decision = SourceAuthority.decide(sub_parsed, inventory)

        # Execute via standard ToolExecutor
        tool_result = await tool_executor.execute(
            sub_parsed,
            inventory,
            conversation_history=history,
            source_decision=source_decision,
        )

        elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000

        return SubIntentResult(
            intent=sub.intent,
            answer=tool_result.synthesized_content or "No data available.",
            sources=tool_result.sources or [],
            confidence=tool_result.confidence or "LOW",
            tools_used=[t.value for t in tool_result.tools_used],
            execution_time_ms=elapsed_ms,
        )
