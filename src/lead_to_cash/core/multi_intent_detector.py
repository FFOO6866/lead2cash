"""
Multi-Intent Query Detector

Detects compound queries that require routing to multiple domains.
Uses three deterministic detection methods:
1. Conjunction splitting ("X and Y" across different domains)
2. Concept co-occurrence (billing + KYP concepts in same query)
3. Comparison markers ("compare X vs Y" across entity types)

Does NOT use LLM for splitting — all detection is structural/pattern-based.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from lead_to_cash.core.routing_signals import SignalSnapshot
from lead_to_cash.core.signal_scorer import DOMAINS, score_domains

logger = logging.getLogger(__name__)


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class SubIntent:
    """A single intent within a compound query."""

    intent: str
    query_fragment: str
    confidence: float
    priority: int = 0
    depends_on: Optional[str] = None


@dataclass
class CompoundQuery:
    """Result of multi-intent detection."""

    is_compound: bool
    compound_confidence: float = 0.0
    detection_method: str = "single"
    sub_intents: List[SubIntent] = field(default_factory=list)
    execution_order: str = "parallel"
    merge_strategy: str = "summary"

    def to_dict(self) -> dict:
        return {
            "is_compound": self.is_compound,
            "compound_confidence": self.compound_confidence,
            "detection_method": self.detection_method,
            "sub_intent_count": len(self.sub_intents),
            "execution_order": self.execution_order,
            "merge_strategy": self.merge_strategy,
            "sub_intents": [
                {"intent": s.intent, "confidence": s.confidence, "priority": s.priority}
                for s in self.sub_intents
            ],
        }


# =============================================================================
# Static dependency map
# =============================================================================

# When these domain pairs appear together, use this execution order
DOMAIN_DEPENDENCIES: Dict[FrozenSet[str], str] = {
    frozenset({"billing_ar", "kyp_due_diligence"}): "sequential",
    frozenset({"billing_ar", "customer_intel"}): "sequential",
    frozenset({"customer_intel", "kyp_due_diligence"}): "sequential",
    frozenset({"product_fit", "competitor_intel"}): "parallel",
    frozenset({"competitor_intel", "market_intel"}): "parallel",
    frozenset({"market_intel", "customer_intel"}): "parallel",
}

# For sequential pairs, which domain goes first
DOMAIN_PRIORITY: Dict[str, int] = {
    "billing_ar": 1,
    "customer_intel": 2,
    "product_fit": 2,
    "competitor_intel": 3,
    "kyp_due_diligence": 4,
    "market_intel": 3,
}

# =============================================================================
# Detection patterns
# =============================================================================

# Conjunction patterns that split a query into two parts
_CONJUNCTION_PATTERN = re.compile(
    r"(?i)(?:"
    r"(.{10,}?)\s+(?:and\s+also|and\s+then|and|,\s*also|;\s*also|\.?\s*then|\.?\s*also)\s+(.{10,})"
    r")",
)

# Sequential dependency markers
_SEQUENTIAL_MARKERS = re.compile(
    r"(?i)\b(?:based\s+on|using\s+the\s+above|then|after\s+that|from\s+that)\b"
)

# Comparison patterns
_COMPARISON_PATTERN = re.compile(
    r"(?i)(?:"
    r"compare\s+(.+?)\s+(?:vs\.?|versus|against|with|to)\s+(.+?)(?:\s+(?:for|in)\b|$)|"
    r"(.+?)\s+vs\.?\s+(.+?)(?:\s+(?:for|in)\b|$)|"
    r"how\s+does\s+(.+?)\s+compare\s+(?:to|with|against)\s+(.+)"
    r")"
)

# Confidence threshold — below this, treat as single-intent
COMPOUND_CONFIDENCE_THRESHOLD = 0.60

# Maximum sub-intents per compound query
MAX_SUB_INTENTS = 3


# =============================================================================
# Main detection function
# =============================================================================


class MultiIntentDetector:
    """Deterministic multi-intent detection for compound queries."""

    @classmethod
    def detect(
        cls,
        query: str,
        signals: SignalSnapshot,
        domain_scores: Dict[str, float],
    ) -> CompoundQuery:
        """
        Detect if a query contains multiple intents.

        Checks three methods in order, returns first confident match:
        1. Comparison pattern (highest specificity)
        2. Concept co-occurrence (medium specificity)
        3. Conjunction splitting (lowest specificity)

        Args:
            query: The raw user query
            signals: Extracted signal snapshot
            domain_scores: Pre-computed domain scores

        Returns:
            CompoundQuery with detection result
        """
        # Method 1: Comparison detection
        result = cls._detect_comparison(query, signals, domain_scores)
        if result and result.compound_confidence >= COMPOUND_CONFIDENCE_THRESHOLD:
            return result

        # Method 2: Concept co-occurrence
        result = cls._detect_concept_co_occurrence(query, signals, domain_scores)
        if result and result.compound_confidence >= COMPOUND_CONFIDENCE_THRESHOLD:
            return result

        # Method 3: Conjunction splitting
        result = cls._detect_conjunction(query, signals, domain_scores)
        if result and result.compound_confidence >= COMPOUND_CONFIDENCE_THRESHOLD:
            return result

        # Single intent
        top_domain = max(domain_scores, key=domain_scores.get)
        return CompoundQuery(
            is_compound=False,
            compound_confidence=0.0,
            detection_method="single",
            sub_intents=[
                SubIntent(
                    intent=top_domain,
                    query_fragment=query,
                    confidence=domain_scores.get(top_domain, 0),
                )
            ],
        )

    @classmethod
    def _detect_comparison(
        cls,
        query: str,
        signals: SignalSnapshot,
        scores: Dict[str, float],
    ) -> Optional[CompoundQuery]:
        """Detect comparison patterns: 'Compare MTU vs Caterpillar'."""
        match = _COMPARISON_PATTERN.search(query)
        if not match:
            return None

        # Extract the two entities from the match groups
        groups = match.groups()
        entity_a = next((g for g in groups[::2] if g), None)
        entity_b = next((g for g in groups[1::2] if g), None)
        if not entity_a or not entity_b:
            return None

        entity_a = entity_a.strip()
        entity_b = entity_b.strip()

        # Score both sides — for comparison, we need product_fit + competitor_intel
        # or two different domains
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        top_two = ranked[:2]
        if len(top_two) < 2:
            return None

        domain_a, score_a = top_two[0]
        domain_b, score_b = top_two[1]

        # Only compound if top two are different domains
        if domain_a == domain_b:
            return None

        return CompoundQuery(
            is_compound=True,
            compound_confidence=min(score_a, score_b)
            + 0.1,  # Boost for explicit comparison
            detection_method="comparison",
            sub_intents=[
                SubIntent(
                    intent=domain_a,
                    query_fragment=entity_a,
                    confidence=score_a,
                    priority=0,
                ),
                SubIntent(
                    intent=domain_b,
                    query_fragment=entity_b,
                    confidence=score_b,
                    priority=0,
                ),
            ],
            execution_order="parallel",
            merge_strategy="comparison",
        )

    @classmethod
    def _detect_concept_co_occurrence(
        cls,
        query: str,
        signals: SignalSnapshot,
        scores: Dict[str, float],
    ) -> Optional[CompoundQuery]:
        """Detect when multiple domain concepts co-occur in one query."""
        active_concepts = []
        concept_domain_map = {
            "concept_billing": "billing_ar",
            "concept_product": "product_fit",
            "concept_competitor": "competitor_intel",
            "concept_kyp": "kyp_due_diligence",
            "concept_market": "market_intel",
            "concept_customer": "customer_intel",
        }

        for attr, domain in concept_domain_map.items():
            if getattr(signals, attr, False):
                active_concepts.append(domain)

        if len(active_concepts) < 2:
            return None

        # Take top 2-3 concept domains by score
        concept_scores = [(d, scores.get(d, 0)) for d in active_concepts]
        concept_scores.sort(key=lambda x: -x[1])
        top = concept_scores[:MAX_SUB_INTENTS]

        # Determine execution order from dependency map
        domain_pair = frozenset(d for d, _ in top[:2])
        exec_order = DOMAIN_DEPENDENCIES.get(domain_pair, "parallel")

        # Check for sequential markers in query
        if _SEQUENTIAL_MARKERS.search(query):
            exec_order = "sequential"

        # Build sub-intents with priority for sequential
        sub_intents = []
        for i, (domain, score) in enumerate(top):
            priority = (
                DOMAIN_PRIORITY.get(domain, 5) if exec_order == "sequential" else 0
            )
            sub_intents.append(
                SubIntent(
                    intent=domain,
                    query_fragment=query,
                    confidence=score,
                    priority=priority,
                )
            )

        if exec_order == "sequential":
            sub_intents.sort(key=lambda s: s.priority)
            for i in range(1, len(sub_intents)):
                sub_intents[i].depends_on = sub_intents[i - 1].intent

        confidence = sum(s.confidence for s in sub_intents) / len(sub_intents)

        return CompoundQuery(
            is_compound=True,
            compound_confidence=confidence,
            detection_method="concept_co_occurrence",
            sub_intents=sub_intents,
            execution_order=exec_order,
            merge_strategy="sequential_narrative"
            if exec_order == "sequential"
            else "summary",
        )

    @classmethod
    def _detect_conjunction(
        cls,
        query: str,
        signals: SignalSnapshot,
        scores: Dict[str, float],
    ) -> Optional[CompoundQuery]:
        """Detect conjunction patterns: 'Show billing and run KYP'."""
        match = _CONJUNCTION_PATTERN.search(query)
        if not match:
            return None

        part_a = match.group(1).strip()
        part_b = match.group(2).strip()

        if len(part_a) < 10 or len(part_b) < 10:
            return None

        # Score each part independently using concept detection
        from lead_to_cash.core.signal_extractor import (
            _CONCEPT_BILLING,
            _CONCEPT_COMPETITOR,
            _CONCEPT_CUSTOMER,
            _CONCEPT_KYP,
            _CONCEPT_MARKET,
            _CONCEPT_PRODUCT,
        )

        concept_map = [
            (_CONCEPT_BILLING, "billing_ar"),
            (_CONCEPT_PRODUCT, "product_fit"),
            (_CONCEPT_COMPETITOR, "competitor_intel"),
            (_CONCEPT_KYP, "kyp_due_diligence"),
            (_CONCEPT_MARKET, "market_intel"),
            (_CONCEPT_CUSTOMER, "customer_intel"),
        ]

        domain_a = None
        domain_b = None
        for pattern, domain in concept_map:
            if pattern.search(part_a) and domain_a is None:
                domain_a = domain
            if pattern.search(part_b) and domain_b is None:
                domain_b = domain

        if not domain_a or not domain_b or domain_a == domain_b:
            return None

        score_a = scores.get(domain_a, 0.4)
        score_b = scores.get(domain_b, 0.4)

        domain_pair = frozenset({domain_a, domain_b})
        exec_order = DOMAIN_DEPENDENCIES.get(domain_pair, "parallel")

        if _SEQUENTIAL_MARKERS.search(query):
            exec_order = "sequential"

        sub_a = SubIntent(
            intent=domain_a,
            query_fragment=part_a,
            confidence=score_a,
            priority=DOMAIN_PRIORITY.get(domain_a, 5),
        )
        sub_b = SubIntent(
            intent=domain_b,
            query_fragment=part_b,
            confidence=score_b,
            priority=DOMAIN_PRIORITY.get(domain_b, 5),
        )

        subs = [sub_a, sub_b]
        if exec_order == "sequential":
            subs.sort(key=lambda s: s.priority)
            subs[1].depends_on = subs[0].intent

        # Conjunction confidence: average of domain scores + 0.15 boost for
        # explicit structural split (the user clearly separated two requests)
        _conj_confidence = min((score_a + score_b) / 2 + 0.15, 0.95)

        return CompoundQuery(
            is_compound=True,
            compound_confidence=_conj_confidence,
            detection_method="conjunction",
            sub_intents=subs,
            execution_order=exec_order,
            merge_strategy="sequential_narrative"
            if exec_order == "sequential"
            else "summary",
        )
