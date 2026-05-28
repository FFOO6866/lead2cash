"""
Reasoning Detector — Phase P1

Detects queries that would benefit from structured reasoning
(evaluation, comparison, recommendation, conditional logic)
beyond simple data retrieval.

Phase P1: Detection and logging ONLY. No plan generation,
no evaluator execution, no user-visible behavior change.

All detection is deterministic (pattern-based, no LLM).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Detection result
# =============================================================================


@dataclass
class ReasoningDetection:
    """Result of reasoning requirement detection."""

    reasoning_needed: bool
    reasoning_type: Optional[str] = None
    matched_signals: List[str] = field(default_factory=list)
    matched_template: Optional[str] = None
    confidence: float = 0.0
    query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reasoning_needed": self.reasoning_needed,
            "reasoning_type": self.reasoning_type,
            "matched_signals": self.matched_signals,
            "matched_template": self.matched_template,
            "confidence": self.confidence,
            "query": self.query[:200],
        }


# =============================================================================
# Reasoning signal patterns (deterministic)
# =============================================================================

_EVALUATION_PATTERN = re.compile(
    r"(?i)\b(?:assess|evaluate|analyze|determine|rate|score|"
    r"check\s+(?:the\s+)?risk|risk\s+assessment|risk\s+of)\b"
)

_RECOMMENDATION_PATTERN = re.compile(
    r"(?i)\b(?:recommend|suggest|best\s+option|advise|propose|"
    r"which\s+(?:\w+\s+)?should\s+(?:\w+\s+)?(?:choose|pick|select|use|be\s+better|be\s+best)|"
    r"which\s+(?:is|should|would)\s+(?:be\s+)?(?:better|best)|"
    r"what\s+should\s+(?:we|i)\s+(?:choose|pick|select|use))\b"
)

_CONDITIONAL_PATTERN = re.compile(
    r"(?i)(?:"
    r"\bif\s+.{5,}?\s+then\b|"
    r"\bassuming\s+.{3,}|"
    r"\bgiven\s+that\b|"
    r"\bprovided\s+that\b|"
    r"\bin\s+case\s+.{3,}"
    r")"
)

_COMPARISON_JUDGMENT_PATTERN = re.compile(
    r"(?i)(?:"
    r"\bcompare\b.{3,}\b(?:recommend|suggest|better|best|choose)\b|"
    r"\bvs\.?\b.{3,}\b(?:recommend|suggest|better|best|which)\b"
    r")"
)

# Confidence contribution per matched signal
_SIGNAL_WEIGHTS = {
    "evaluation_language": 0.35,
    "recommendation_language": 0.35,
    "conditional_language": 0.40,
    "comparison_judgment": 0.35,
    "compound_sequential": 0.35,  # Compound sequential implies reasoning need
    "compound_comparison": 0.30,  # Compound comparison implies judgment needed
}

# Template matching: concept combinations → template name
_TEMPLATE_HINTS = {
    frozenset({"concept_billing", "concept_kyp"}): "risk_assessment",
    frozenset({"concept_product", "concept_competitor"}): "product_comparison",
    frozenset({"concept_billing"}): "credit_feasibility",
    frozenset({"concept_customer"}): "customer_deep_dive",
    frozenset({"concept_competitor", "concept_market"}): "competitive_positioning",
}

# Minimum confidence to classify as reasoning-needed
_CONFIDENCE_THRESHOLD = 0.30


# =============================================================================
# Main detection function
# =============================================================================


def detect_reasoning(
    query: str,
    signals_dict: Optional[Dict[str, Any]] = None,
    compound_metadata: Optional[Dict[str, Any]] = None,
) -> ReasoningDetection:
    """
    Detect whether a query would benefit from structured reasoning.

    Phase P1: Detection and logging only. Does not generate plans.

    Args:
        query: The raw user query
        signals_dict: Signal snapshot dict (from SignalSnapshot.to_dict())
        compound_metadata: CompoundQuery.to_dict() if available

    Returns:
        ReasoningDetection with detection result
    """
    matched = []
    confidence = 0.0

    # ── Pattern matching ────────────────────────────────────────
    if _EVALUATION_PATTERN.search(query):
        matched.append("evaluation_language")
        confidence += _SIGNAL_WEIGHTS["evaluation_language"]

    if _RECOMMENDATION_PATTERN.search(query):
        matched.append("recommendation_language")
        confidence += _SIGNAL_WEIGHTS["recommendation_language"]

    if _CONDITIONAL_PATTERN.search(query):
        matched.append("conditional_language")
        confidence += _SIGNAL_WEIGHTS["conditional_language"]

    if _COMPARISON_JUDGMENT_PATTERN.search(query):
        matched.append("comparison_judgment")
        confidence += _SIGNAL_WEIGHTS["comparison_judgment"]

    # ── Compound query indicators ───────────────────────────────
    if compound_metadata:
        if compound_metadata.get("execution_order") == "sequential":
            matched.append("compound_sequential")
            confidence += _SIGNAL_WEIGHTS["compound_sequential"]
        if compound_metadata.get("detection_method") == "comparison":
            matched.append("compound_comparison")
            confidence += _SIGNAL_WEIGHTS["compound_comparison"]

    # ── Determine reasoning type ────────────────────────────────
    reasoning_type = _classify_reasoning_type(matched)

    # ── Template hint (for logging/analytics only) ──────────────
    template = _hint_template(signals_dict) if signals_dict else None

    # ── Cap confidence at 1.0 ───────────────────────────────────
    confidence = min(confidence, 1.0)
    reasoning_needed = confidence >= _CONFIDENCE_THRESHOLD and len(matched) > 0

    return ReasoningDetection(
        reasoning_needed=reasoning_needed,
        reasoning_type=reasoning_type,
        matched_signals=matched,
        matched_template=template,
        confidence=round(confidence, 3),
        query=query,
    )


def _classify_reasoning_type(matched: List[str]) -> Optional[str]:
    """Classify reasoning type from matched signals."""
    if "conditional_language" in matched:
        return "multi_hop"
    if "comparison_judgment" in matched or "compound_comparison" in matched:
        return "compare_recommend"
    if "recommendation_language" in matched:
        return "compare_recommend"
    if "evaluation_language" in matched:
        return "evaluate"
    if "compound_sequential" in matched:
        return "evaluate"
    return None


def _hint_template(signals_dict: Dict[str, Any]) -> Optional[str]:
    """Hint at the most likely plan template based on concept signals."""
    active_concepts = set()
    for key in [
        "concept_billing",
        "concept_product",
        "concept_competitor",
        "concept_kyp",
        "concept_market",
        "concept_customer",
    ]:
        if signals_dict.get(key, False):
            active_concepts.add(key)

    if not active_concepts:
        return None

    # Find best matching template
    best_template = None
    best_overlap = 0
    for required_concepts, template_name in _TEMPLATE_HINTS.items():
        overlap = len(active_concepts & required_concepts)
        if overlap > best_overlap and overlap >= min(len(required_concepts), 2):
            best_overlap = overlap
            best_template = template_name
        elif overlap > best_overlap and len(required_concepts) == 1 and overlap == 1:
            best_overlap = overlap
            best_template = template_name

    return best_template
