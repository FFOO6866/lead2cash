"""
Response Composer for Compound Queries

Merges sub-intent results into a coherent compound response.
Three merge strategies:
1. Comparison — side-by-side with summary
2. Summary — domain sections with combined view
3. Sequential narrative — ordered with context flow
"""

import logging
import re
from typing import Any, Dict, List

from lead_to_cash.core.compound_executor import CompoundResult, SubIntentResult

logger = logging.getLogger(__name__)

# Domain display names for headers
_DOMAIN_LABELS: Dict[str, str] = {
    "billing_ar": "Billing & Payment Analysis",
    "product_fit": "Product & Technical Analysis",
    "competitor_intel": "Competitive Intelligence",
    "customer_intel": "Customer Intelligence",
    "kyp_due_diligence": "Due Diligence Assessment",
    "market_intel": "Market Intelligence",
}


class ResponseComposer:
    """Merge sub-intent results into a unified compound response."""

    @classmethod
    def compose(cls, compound_result: CompoundResult) -> Dict[str, Any]:
        """
        Compose sub-results into a final response.

        Args:
            compound_result: Results from CompoundExecutor

        Returns:
            Response dict compatible with existing frontend
        """
        strategy = compound_result.merge_strategy
        subs = compound_result.sub_results

        if not subs:
            return cls._empty_response()

        # Route to strategy
        if strategy == "comparison":
            merged = cls._merge_comparison(subs)
        elif strategy == "sequential_narrative":
            merged = cls._merge_sequential(subs)
        else:
            merged = cls._merge_summary(subs)

        # Validate and clean
        merged = cls._validate_merged(merged)

        # Build response
        successful = [s for s in subs if s.status == "success"]
        confidence = (
            "HIGH" if all(s.confidence == "HIGH" for s in successful) else "MEDIUM"
        )

        return {
            "type": "compound_report",
            "answer": merged,
            "sub_responses": [
                {
                    "intent": s.intent,
                    "domain_label": _DOMAIN_LABELS.get(s.intent, s.intent),
                    "answer": s.answer,
                    "sources": s.sources,
                    "status": s.status,
                }
                for s in subs
            ],
            "sources": compound_result.all_sources,
            "confidence": confidence,
            "tools_used": compound_result.all_tools,
            "execution_time_ms": compound_result.total_time_ms,
            "merge_strategy": strategy,
            "partial_success": compound_result.partial_success,
        }

    @classmethod
    def _merge_comparison(cls, subs: List[SubIntentResult]) -> str:
        """Merge for comparison queries: side-by-side with summary."""
        parts = []
        for sub in subs:
            label = _DOMAIN_LABELS.get(sub.intent, sub.intent)
            if sub.status == "success":
                parts.append(f"## {label}\n\n{sub.answer}")
            else:
                parts.append(f"## {label}\n\n*Data not available for this section.*")

        # Add comparison summary
        if len(subs) >= 2 and all(s.status == "success" for s in subs):
            parts.append(
                "## Comparison Summary\n\n"
                "The above analyses cover different aspects of the query. "
                "Review each section for the specific domain perspective."
            )

        return "\n\n---\n\n".join(parts)

    @classmethod
    def _merge_summary(cls, subs: List[SubIntentResult]) -> str:
        """Merge for summary queries: domain sections."""
        parts = []
        for sub in subs:
            label = _DOMAIN_LABELS.get(sub.intent, sub.intent)
            if sub.status == "success":
                parts.append(f"## {label}\n\n{sub.answer}")
            else:
                parts.append(f"## {label}\n\n*This section could not be completed.*")

        return "\n\n---\n\n".join(parts)

    @classmethod
    def _merge_sequential(cls, subs: List[SubIntentResult]) -> str:
        """Merge for sequential queries: ordered narrative with context flow."""
        parts = []
        for i, sub in enumerate(subs):
            label = _DOMAIN_LABELS.get(sub.intent, sub.intent)
            if sub.status == "success":
                if i == 0:
                    parts.append(f"## {label}\n\n{sub.answer}")
                else:
                    parts.append(
                        f"## {label}\n\nBased on the above analysis:\n\n{sub.answer}"
                    )
            else:
                parts.append(f"## {label}\n\n*This section could not be completed.*")

        return "\n\n---\n\n".join(parts)

    @classmethod
    def _validate_merged(cls, text: str) -> str:
        """Validate and clean merged response text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Remove duplicate section headers
        lines = text.split("\n")
        seen_headers = set()
        cleaned = []
        for line in lines:
            if line.startswith("## "):
                if line in seen_headers:
                    continue
                seen_headers.add(line)
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    @classmethod
    def _empty_response(cls) -> Dict[str, Any]:
        return {
            "type": "answer",
            "answer": "Unable to process this compound query.",
            "sources": [],
            "confidence": "LOW",
        }
