"""
KB Gap Detection → Ingestion Pipeline

Automated 4-stage pipeline that detects missing KB coverage from production
behavior, classifies gaps, generates safe ingestion tasks, and validates
post-ingest correctness.

Stages:
    1. GapDetector     — detect candidates from enforcement telemetry
    2. GapClassifier   — classify type and priority
    3. IngestionQueue  — generate ordered ingestion tasks
    4. PostIngestValidator — verify gap is resolved after KB addition

This module is DATA OPS ONLY. It does NOT modify:
    - OutputEnforcer logic
    - Verification rules
    - Routing or reasoning
    - Thresholds

Usage:
    pipeline = KBGapPipeline()
    gaps = pipeline.detect()
    classified = pipeline.classify(gaps)
    queue = pipeline.build_queue(classified)
    # ... human adds data ...
    results = pipeline.validate(queue)
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class GapType(Enum):
    """Classification of KB coverage gaps."""

    CORPORATE_FACT_GAP = "corporate_fact_gap"
    PRODUCT_SPEC_GAP = "product_spec_gap"
    MARKET_ENTITY_GAP = "market_entity_gap"
    PARTIAL_COVERAGE = "partial_coverage"


class GapPriority(Enum):
    """Priority for gap resolution."""

    HIGH = "high"  # Causes claim rejection on common queries
    MEDIUM = "medium"  # Partial coverage, safe fallback available
    LOW = "low"  # Rare entity or low-frequency query


class DetectionSource(Enum):
    """How the gap was detected."""

    ENFORCER_REMOVAL = "enforcer_removal"
    ENFORCER_CONTRADICTION = "enforcer_contradiction"
    FALLBACK_TRIGGERED = "fallback_triggered"
    AUDIT_FINDING = "audit_finding"
    QUERY_PATTERN = "query_pattern"


class FailureMode(Enum):
    """How the gap manifests in production."""

    CLAIM_REJECTED = "claim_rejected"
    CLAIM_CONTRADICTED = "claim_contradicted"
    FALLBACK_RESPONSE = "fallback_response"
    UNVERIFIABLE_ENTITY = "unverifiable_entity"
    MISSING_SPEC = "missing_spec"
    MISSING_CORPORATE_FACT = "missing_corporate_fact"
    PARTIAL_ENTITY = "partial_entity"


class GapStatus(Enum):
    """Resolution status of a gap."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    UNRESOLVED = "unresolved"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class GapCandidate:
    """A detected KB coverage gap candidate."""

    entity: str
    attribute_or_fact_type: str  # e.g., "kw_rating", "ownership", "subsidiary"
    domain: str  # product / corporate / market
    source_of_detection: DetectionSource
    sample_query: str
    failure_mode: FailureMode
    frequency: int = 1
    severity: GapPriority = GapPriority.MEDIUM
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "attribute_or_fact_type": self.attribute_or_fact_type,
            "domain": self.domain,
            "source_of_detection": self.source_of_detection.value,
            "sample_query": self.sample_query,
            "failure_mode": self.failure_mode.value,
            "frequency": self.frequency,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ClassifiedGap:
    """A gap with type classification and priority assignment."""

    candidate: GapCandidate
    gap_type: GapType
    priority: GapPriority
    classification_reason: str
    required_fields: List[str]
    preferred_sources: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.candidate.entity,
            "gap_type": self.gap_type.value,
            "priority": self.priority.value,
            "classification_reason": self.classification_reason,
            "required_fields": self.required_fields,
            "preferred_sources": self.preferred_sources,
            "failure_mode": self.candidate.failure_mode.value,
            "sample_query": self.candidate.sample_query,
            "frequency": self.candidate.frequency,
        }


@dataclass
class IngestionTask:
    """A concrete task for KB data ingestion."""

    entity: str
    gap_type: GapType
    required_fields: List[str]
    preferred_source_types: List[str]
    verification_requirements: List[str]
    priority: GapPriority
    sample_query: str
    status: GapStatus = GapStatus.OPEN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "gap_type": self.gap_type.value,
            "required_fields": self.required_fields,
            "preferred_source_types": self.preferred_source_types,
            "verification_requirements": self.verification_requirements,
            "priority": self.priority.value,
            "sample_query": self.sample_query,
            "status": self.status.value,
        }


@dataclass
class ValidationResult:
    """Result of post-ingest validation for a gap."""

    entity: str
    gap_type: GapType
    status: GapStatus
    query_tested: str
    answer_falls_back: bool
    claim_grounded: bool
    enforcer_accepts: bool
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "gap_type": self.gap_type.value,
            "status": self.status.value,
            "query_tested": self.query_tested,
            "answer_falls_back": self.answer_falls_back,
            "claim_grounded": self.claim_grounded,
            "enforcer_accepts": self.enforcer_accepts,
            "details": self.details,
        }


# =============================================================================
# Stage 1 — Gap Detector
# =============================================================================


class GapDetector:
    """
    Detects KB coverage gaps from production signals.

    Sources:
    A. OutputEnforcer telemetry (claim removals, contradictions, fallbacks)
    B. Fallback response patterns
    C. Repeated query patterns for missing entities
    D. Audit findings (manual or automated)
    """

    # Fallback phrases that indicate a KB gap
    _FALLBACK_PHRASES = [
        "cannot confirm from verified sources",
        "no verified information found",
        "insufficient verified evidence",
        "cannot confirm this specification",
        "cannot confirm this claim",
        "cannot confirm this corporate",
    ]

    @classmethod
    def detect_from_enforcer_reports(
        cls, reports: List[Dict[str, Any]]
    ) -> List[GapCandidate]:
        """
        Extract gap candidates from OutputEnforcer enforcement reports.

        Each report is an EnforcementReport.to_dict() with claim details.
        """
        candidates = []
        entity_counter: Counter = Counter()

        for report in reports:
            if not report.get("was_modified"):
                continue

            # Extract claims from the report's original text
            # We look at what was removed/contradicted
            claims_removed = report.get("claims_removed", 0)
            claims_contradicted = report.get("claims_contradicted", 0)

            if claims_removed > 0 or claims_contradicted > 0:
                # Extract entity from the report if available
                entity = report.get("entity", "unknown")
                entity_counter[entity] += 1

                if claims_contradicted > 0:
                    candidates.append(
                        GapCandidate(
                            entity=entity,
                            attribute_or_fact_type="specification_or_fact",
                            domain="product",
                            source_of_detection=DetectionSource.ENFORCER_CONTRADICTION,
                            sample_query=report.get("sample_query", ""),
                            failure_mode=FailureMode.CLAIM_CONTRADICTED,
                            frequency=entity_counter[entity],
                        )
                    )
                elif claims_removed > 0:
                    candidates.append(
                        GapCandidate(
                            entity=entity,
                            attribute_or_fact_type="specification_or_fact",
                            domain="product",
                            source_of_detection=DetectionSource.ENFORCER_REMOVAL,
                            sample_query=report.get("sample_query", ""),
                            failure_mode=FailureMode.CLAIM_REJECTED,
                            frequency=entity_counter[entity],
                        )
                    )

            if report.get("fallback_triggered"):
                candidates.append(
                    GapCandidate(
                        entity=report.get("entity", "unknown"),
                        attribute_or_fact_type="insufficient_coverage",
                        domain="product",
                        source_of_detection=DetectionSource.FALLBACK_TRIGGERED,
                        sample_query=report.get("sample_query", ""),
                        failure_mode=FailureMode.FALLBACK_RESPONSE,
                    )
                )

        return candidates

    @classmethod
    def detect_from_responses(
        cls, responses: List[Dict[str, str]]
    ) -> List[GapCandidate]:
        """
        Detect gaps from actual response texts.

        Each response is {"query": "...", "answer": "...", "intent": "..."}.
        """
        candidates = []

        for resp in responses:
            answer = resp.get("answer", "").lower()
            query = resp.get("query", "")

            # Check for fallback phrases
            for phrase in cls._FALLBACK_PHRASES:
                if phrase in answer:
                    # Extract entity from query
                    entity = cls._extract_entity_from_query(query)
                    candidates.append(
                        GapCandidate(
                            entity=entity,
                            attribute_or_fact_type="unverifiable",
                            domain=cls._infer_domain(query),
                            source_of_detection=DetectionSource.FALLBACK_TRIGGERED,
                            sample_query=query,
                            failure_mode=FailureMode.FALLBACK_RESPONSE,
                        )
                    )
                    break

        return candidates

    @classmethod
    def detect_from_audit(
        cls, audit_findings: List[Dict[str, Any]]
    ) -> List[GapCandidate]:
        """
        Create gap candidates from structured audit findings.

        Each finding: {"entity": "...", "gap_type": "FULL_GAP|SPEC_GAP|PARTIAL",
                       "has_specs": bool, "has_corporate": bool}
        """
        candidates = []

        for finding in audit_findings:
            entity = finding["entity"]
            gap_level = finding.get("gap_type", "PARTIAL")
            has_specs = finding.get("has_specs", False)
            has_corporate = finding.get("has_corporate", False)

            if gap_level == "FULL_GAP":
                # No specs AND no corporate facts
                candidates.append(
                    GapCandidate(
                        entity=entity,
                        attribute_or_fact_type="corporate_ownership",
                        domain="corporate",
                        source_of_detection=DetectionSource.AUDIT_FINDING,
                        sample_query=f"What is {entity}'s corporate structure?",
                        failure_mode=FailureMode.MISSING_CORPORATE_FACT,
                        severity=GapPriority.HIGH,
                    )
                )
                candidates.append(
                    GapCandidate(
                        entity=entity,
                        attribute_or_fact_type="engine_specs",
                        domain="product",
                        source_of_detection=DetectionSource.AUDIT_FINDING,
                        sample_query=f"What are {entity}'s engine specifications?",
                        failure_mode=FailureMode.MISSING_SPEC,
                        severity=GapPriority.HIGH,
                    )
                )
            elif gap_level == "SPEC_GAP":
                candidates.append(
                    GapCandidate(
                        entity=entity,
                        attribute_or_fact_type="engine_specs",
                        domain="product",
                        source_of_detection=DetectionSource.AUDIT_FINDING,
                        sample_query=f"What is the power rating of {entity}?",
                        failure_mode=FailureMode.MISSING_SPEC,
                        severity=GapPriority.MEDIUM,
                    )
                )
            elif gap_level == "PARTIAL":
                if not has_specs:
                    candidates.append(
                        GapCandidate(
                            entity=entity,
                            attribute_or_fact_type="engine_specs",
                            domain="product",
                            source_of_detection=DetectionSource.AUDIT_FINDING,
                            sample_query=f"What are {entity}'s engine specifications?",
                            failure_mode=FailureMode.PARTIAL_ENTITY,
                            severity=GapPriority.MEDIUM,
                        )
                    )
                if not has_corporate:
                    candidates.append(
                        GapCandidate(
                            entity=entity,
                            attribute_or_fact_type="corporate_ownership",
                            domain="corporate",
                            source_of_detection=DetectionSource.AUDIT_FINDING,
                            sample_query=f"Who owns {entity}?",
                            failure_mode=FailureMode.MISSING_CORPORATE_FACT,
                            severity=GapPriority.MEDIUM,
                        )
                    )

        return candidates

    @staticmethod
    def _extract_entity_from_query(query: str) -> str:
        """Best-effort entity extraction from a query string."""
        try:
            from lead_to_cash.core.output_enforcer import _find_competitor_entity

            entity = _find_competitor_entity(query.lower())
            return entity or "unknown"
        except ImportError:
            # Fallback: simple keyword scan for known competitor names
            q = query.lower()
            for name in [
                "caterpillar",
                "cummins",
                "wartsila",
                "wärtsilä",
                "man",
                "himsen",
                "hyundai",
                "daihatsu",
                "yanmar",
                "niigata",
                "bergen",
                "volvo penta",
                "siemens",
                "mak",
                "abc",
            ]:
                if name in q:
                    return name
            return "unknown"

    @staticmethod
    def _infer_domain(query: str) -> str:
        """Infer gap domain from query content."""
        q = query.lower()
        if any(kw in q for kw in ["kw", "power", "engine", "spec", "model"]):
            return "product"
        if any(kw in q for kw in ["subsidiary", "owned", "acquired", "merged"]):
            return "corporate"
        return "market"


# =============================================================================
# Stage 2 — Gap Classifier
# =============================================================================


class GapClassifier:
    """
    Classifies gap candidates into typed, prioritized gaps.

    Classification rules (deterministic, no LLM):
    - CORPORATE_FACT_GAP: ownership, subsidiary, acquisition claims
    - PRODUCT_SPEC_GAP: kW, model, fuel type claims
    - MARKET_ENTITY_GAP: missing entity in market KB entirely
    - PARTIAL_COVERAGE: entity exists but missing attribute
    """

    # Required fields by gap type
    _REQUIRED_FIELDS = {
        GapType.CORPORATE_FACT_GAP: [
            "entity_name",
            "ownership_type",  # independent / subsidiary / brand
            "parent_company",  # or "none" if independent
            "source_reference",
        ],
        GapType.PRODUCT_SPEC_GAP: [
            "model_designation",
            "power_kw",
            "manufacturer",
            "source_reference",
        ],
        GapType.MARKET_ENTITY_GAP: [
            "entity_name",
            "entity_type",  # manufacturer / operator / shipyard
            "market_segment",
            "source_reference",
        ],
        GapType.PARTIAL_COVERAGE: [
            "entity_name",
            "missing_attribute",
            "source_reference",
        ],
    }

    # Preferred sources by gap type
    _PREFERRED_SOURCES = {
        GapType.CORPORATE_FACT_GAP: [
            "OEM official website",
            "company investor relations page",
            "annual report",
            "stock exchange filing",
        ],
        GapType.PRODUCT_SPEC_GAP: [
            "OEM spec sheet",
            "official product page",
            "technical brochure",
            "type approval certificate",
        ],
        GapType.MARKET_ENTITY_GAP: [
            "trusted trade publication",
            "OEM newsroom",
            "operator announcement",
            "shipyard press release",
        ],
        GapType.PARTIAL_COVERAGE: [
            "OEM spec sheet",
            "official company page",
            "annual report",
        ],
    }

    @classmethod
    def classify(cls, candidates: List[GapCandidate]) -> List[ClassifiedGap]:
        """Classify and prioritize a list of gap candidates."""
        classified = []

        for candidate in candidates:
            gap_type = cls._determine_type(candidate)
            priority = cls._determine_priority(candidate, gap_type)
            reason = cls._build_reason(candidate, gap_type)

            classified.append(
                ClassifiedGap(
                    candidate=candidate,
                    gap_type=gap_type,
                    priority=priority,
                    classification_reason=reason,
                    required_fields=cls._REQUIRED_FIELDS.get(gap_type, []),
                    preferred_sources=cls._PREFERRED_SOURCES.get(gap_type, []),
                )
            )

        return classified

    @classmethod
    def _determine_type(cls, candidate: GapCandidate) -> GapType:
        """Classify gap type from candidate attributes."""
        if candidate.failure_mode == FailureMode.MISSING_CORPORATE_FACT:
            return GapType.CORPORATE_FACT_GAP
        if candidate.failure_mode == FailureMode.MISSING_SPEC:
            return GapType.PRODUCT_SPEC_GAP
        if candidate.failure_mode == FailureMode.PARTIAL_ENTITY:
            return GapType.PARTIAL_COVERAGE
        if candidate.failure_mode == FailureMode.UNVERIFIABLE_ENTITY:
            return GapType.MARKET_ENTITY_GAP

        # Classify by domain
        if candidate.domain == "corporate":
            return GapType.CORPORATE_FACT_GAP
        if candidate.domain == "product":
            return GapType.PRODUCT_SPEC_GAP

        return GapType.MARKET_ENTITY_GAP

    @classmethod
    def _determine_priority(
        cls, candidate: GapCandidate, gap_type: GapType
    ) -> GapPriority:
        """Assign priority based on impact and frequency."""
        # Already assigned by audit
        if candidate.severity != GapPriority.MEDIUM:
            return candidate.severity

        # High: frequent failures or contradictions
        if candidate.frequency >= 3:
            return GapPriority.HIGH
        if candidate.failure_mode == FailureMode.CLAIM_CONTRADICTED:
            return GapPriority.HIGH

        # Medium: removals, partial coverage
        if candidate.failure_mode in (
            FailureMode.CLAIM_REJECTED,
            FailureMode.PARTIAL_ENTITY,
        ):
            return GapPriority.MEDIUM

        # Low: fallback on rare entities
        if candidate.failure_mode == FailureMode.FALLBACK_RESPONSE:
            return GapPriority.LOW

        return GapPriority.MEDIUM

    @classmethod
    def _build_reason(cls, candidate: GapCandidate, gap_type: GapType) -> str:
        """Build a human-readable classification reason."""
        reasons = {
            GapType.CORPORATE_FACT_GAP: (
                f"Entity '{candidate.entity}' has no verified corporate ownership "
                f"fact in KB. Detected via {candidate.source_of_detection.value}."
            ),
            GapType.PRODUCT_SPEC_GAP: (
                f"Entity '{candidate.entity}' has no verified engine specifications "
                f"in KB. Detected via {candidate.source_of_detection.value}."
            ),
            GapType.MARKET_ENTITY_GAP: (
                f"Entity '{candidate.entity}' is not covered in the market KB. "
                f"Detected via {candidate.source_of_detection.value}."
            ),
            GapType.PARTIAL_COVERAGE: (
                f"Entity '{candidate.entity}' has partial KB coverage — missing "
                f"{candidate.attribute_or_fact_type}. "
                f"Detected via {candidate.source_of_detection.value}."
            ),
        }
        return reasons.get(gap_type, f"Gap for {candidate.entity}")


# =============================================================================
# Stage 3 — Ingestion Queue Builder
# =============================================================================


# Standard verification requirements for all KB entries
_VERIFICATION_REQUIREMENTS = [
    "atomic_claim_only",
    "supporting_excerpt_required",
    "entity_match_required",
    "claim_match_required",
    "context_match_required",
    "VERIFIED_STRONG_preferred",
    "no_summaries",
    "no_inferred_facts",
    "no_perplexity_summaries_as_facts",
]


class IngestionQueueBuilder:
    """
    Generates an ordered queue of ingestion tasks from classified gaps.

    Output queue ordered by: priority → frequency → user impact.
    """

    @classmethod
    def build(cls, classified_gaps: List[ClassifiedGap]) -> List[IngestionTask]:
        """Build an ordered ingestion queue from classified gaps."""
        # Deduplicate by entity + gap_type
        seen: Set[Tuple[str, str]] = set()
        tasks = []

        for gap in classified_gaps:
            key = (gap.candidate.entity.lower(), gap.gap_type.value)
            if key in seen:
                continue
            seen.add(key)

            tasks.append(
                IngestionTask(
                    entity=gap.candidate.entity,
                    gap_type=gap.gap_type,
                    required_fields=gap.required_fields,
                    preferred_source_types=gap.preferred_sources,
                    verification_requirements=_VERIFICATION_REQUIREMENTS,
                    priority=gap.priority,
                    sample_query=gap.candidate.sample_query,
                )
            )

        # Sort by priority (HIGH first), then frequency
        priority_order = {
            GapPriority.HIGH: 0,
            GapPriority.MEDIUM: 1,
            GapPriority.LOW: 2,
        }
        tasks.sort(key=lambda t: priority_order.get(t.priority, 2))

        return tasks

    @classmethod
    def to_json(cls, queue: List[IngestionTask]) -> str:
        """Serialize queue to JSON for export/storage."""
        return json.dumps([t.to_dict() for t in queue], indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> List[IngestionTask]:
        """Deserialize queue from JSON."""
        items = json.loads(data)
        return [
            IngestionTask(
                entity=item["entity"],
                gap_type=GapType(item["gap_type"]),
                required_fields=item["required_fields"],
                preferred_source_types=item["preferred_source_types"],
                verification_requirements=item["verification_requirements"],
                priority=GapPriority(item["priority"]),
                sample_query=item["sample_query"],
                status=GapStatus(item.get("status", "open")),
            )
            for item in items
        ]


# =============================================================================
# Stage 4 — Post-Ingest Validator
# =============================================================================


class PostIngestValidator:
    """
    Validates that a KB addition actually resolves the detected gap.

    Checks:
    1. Answer no longer falls back
    2. Claim is grounded (not replaced by enforcer)
    3. OutputEnforcer accepts the new data
    """

    @classmethod
    def validate_entry(
        cls,
        entity: str,
        gap_type: GapType,
        sample_query: str,
        enforcer_result: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate a single KB entry after ingestion.

        Args:
            entity: The entity that was added
            gap_type: The type of gap that was filled
            sample_query: The query that originally triggered the gap
            enforcer_result: OutputEnforcer.enforce() result dict (if available)
        """
        if enforcer_result is None:
            return ValidationResult(
                entity=entity,
                gap_type=gap_type,
                status=GapStatus.OPEN,
                query_tested=sample_query,
                answer_falls_back=True,
                claim_grounded=False,
                enforcer_accepts=False,
                details="No enforcer result provided — needs re-test",
            )

        falls_back = enforcer_result.get("fallback_triggered", False)
        claims_removed = enforcer_result.get("claims_removed", 0)
        claims_contradicted = enforcer_result.get("claims_contradicted", 0)
        was_modified = enforcer_result.get("was_modified", False)

        # Determine status
        enforcer_accepts = claims_removed == 0 and claims_contradicted == 0
        claim_grounded = not falls_back and enforcer_accepts

        if claim_grounded and not was_modified:
            status = GapStatus.RESOLVED
            details = "KB entry verified — claim passes enforcement"
        elif not falls_back and was_modified:
            status = GapStatus.PARTIALLY_RESOLVED
            details = (
                f"No fallback but enforcer modified output: "
                f"{claims_removed} removed, {claims_contradicted} contradicted"
            )
        else:
            status = GapStatus.UNRESOLVED
            details = "Gap persists after KB addition"

        return ValidationResult(
            entity=entity,
            gap_type=gap_type,
            status=status,
            query_tested=sample_query,
            answer_falls_back=falls_back,
            claim_grounded=claim_grounded,
            enforcer_accepts=enforcer_accepts,
            details=details,
        )

    @classmethod
    def validate_batch(
        cls,
        tasks: List[IngestionTask],
        results: Dict[str, Dict[str, Any]],
    ) -> List[ValidationResult]:
        """
        Validate a batch of ingestion tasks.

        Args:
            tasks: Ingestion tasks to validate
            results: Map of entity → enforcer_result for each task
        """
        validations = []
        for task in tasks:
            enforcer_result = results.get(task.entity.lower())
            v = cls.validate_entry(
                entity=task.entity,
                gap_type=task.gap_type,
                sample_query=task.sample_query,
                enforcer_result=enforcer_result,
            )
            validations.append(v)
        return validations


# =============================================================================
# Telemetry
# =============================================================================


class GapTelemetry:
    """
    Tracks gap pipeline metrics for observability.

    All data stored as bounded in-memory counters + structured logging.
    """

    _gap_counts: Counter = Counter()
    _resolution_counts: Counter = Counter()
    _entity_gap_history: Dict[str, List[str]] = defaultdict(list)
    _max_history: int = 1000

    @classmethod
    def record_detection(cls, candidates: List[GapCandidate]) -> None:
        """Record detected gaps."""
        for c in candidates:
            cls._gap_counts[c.failure_mode.value] += 1
            key = c.entity.lower()
            if len(cls._entity_gap_history[key]) < cls._max_history:
                cls._entity_gap_history[key].append(c.timestamp)

        logger.info(
            "kb_gap_detection",
            extra={
                "gaps_detected": len(candidates),
                "by_failure_mode": dict(cls._gap_counts),
            },
        )

    @classmethod
    def record_resolution(cls, results: List[ValidationResult]) -> None:
        """Record gap resolution outcomes."""
        for r in results:
            cls._resolution_counts[r.status.value] += 1

        logger.info(
            "kb_gap_resolution",
            extra={
                "results_count": len(results),
                "by_status": dict(cls._resolution_counts),
            },
        )

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        """Get current telemetry summary."""
        return {
            "total_gaps_detected": sum(cls._gap_counts.values()),
            "gaps_by_type": dict(cls._gap_counts),
            "top_missing_entities": [
                (entity, len(timestamps))
                for entity, timestamps in sorted(
                    cls._entity_gap_history.items(),
                    key=lambda x: len(x[1]),
                    reverse=True,
                )[:10]
            ],
            "resolutions": dict(cls._resolution_counts),
            "resolution_rate": (
                cls._resolution_counts.get("resolved", 0)
                / max(sum(cls._resolution_counts.values()), 1)
            ),
        }

    @classmethod
    def reset(cls) -> None:
        """Reset telemetry counters (for testing)."""
        cls._gap_counts.clear()
        cls._resolution_counts.clear()
        cls._entity_gap_history.clear()


# =============================================================================
# Main Pipeline
# =============================================================================


class KBGapPipeline:
    """
    Complete KB gap detection → ingestion pipeline.

    Usage:
        pipeline = KBGapPipeline()

        # From audit findings
        gaps = pipeline.detect_from_audit(findings)
        classified = pipeline.classify(gaps)
        queue = pipeline.build_queue(classified)
        print(pipeline.export_queue(queue))

        # After data is added
        results = pipeline.validate(queue, enforcer_results)
        print(pipeline.summary())
    """

    def detect_from_audit(
        self, audit_findings: List[Dict[str, Any]]
    ) -> List[GapCandidate]:
        """Stage 1: Detect gaps from audit findings."""
        candidates = GapDetector.detect_from_audit(audit_findings)
        GapTelemetry.record_detection(candidates)
        return candidates

    def detect_from_enforcer(self, reports: List[Dict[str, Any]]) -> List[GapCandidate]:
        """Stage 1: Detect gaps from enforcer telemetry."""
        candidates = GapDetector.detect_from_enforcer_reports(reports)
        GapTelemetry.record_detection(candidates)
        return candidates

    def detect_from_responses(
        self, responses: List[Dict[str, str]]
    ) -> List[GapCandidate]:
        """Stage 1: Detect gaps from response texts."""
        candidates = GapDetector.detect_from_responses(responses)
        GapTelemetry.record_detection(candidates)
        return candidates

    def classify(self, candidates: List[GapCandidate]) -> List[ClassifiedGap]:
        """Stage 2: Classify and prioritize gaps."""
        return GapClassifier.classify(candidates)

    def build_queue(self, classified: List[ClassifiedGap]) -> List[IngestionTask]:
        """Stage 3: Build ordered ingestion queue."""
        return IngestionQueueBuilder.build(classified)

    def validate(
        self,
        queue: List[IngestionTask],
        enforcer_results: Dict[str, Dict[str, Any]],
    ) -> List[ValidationResult]:
        """Stage 4: Validate post-ingest correctness."""
        results = PostIngestValidator.validate_batch(queue, enforcer_results)
        GapTelemetry.record_resolution(results)
        return results

    def export_queue(self, queue: List[IngestionTask]) -> str:
        """Export queue as JSON."""
        return IngestionQueueBuilder.to_json(queue)

    def summary(self) -> Dict[str, Any]:
        """Get pipeline telemetry summary."""
        return GapTelemetry.get_summary()


# =============================================================================
# Seed Queue — Current Audit Findings
# =============================================================================


def build_seed_queue() -> List[IngestionTask]:
    """
    Build the initial ingestion queue from current audit findings.

    These are the gaps identified in the 2026-04-02 audit.
    """
    audit_findings = [
        # RESOLVED (already added to KB — included for tracking)
        {
            "entity": "ABC",
            "gap_type": "FULL_GAP",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Siemens Energy",
            "gap_type": "FULL_GAP",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Cat MaK M32C",
            "gap_type": "SPEC_GAP",
            "has_specs": True,
            "has_corporate": False,
        },
        # OPEN — need engine specs
        {
            "entity": "Bergen Engines",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "HiMSEN",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Volvo Penta",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Yanmar",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Daihatsu",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "Niigata",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
        {
            "entity": "MaK",
            "gap_type": "PARTIAL",
            "has_specs": False,
            "has_corporate": True,
        },
    ]

    pipeline = KBGapPipeline()
    gaps = pipeline.detect_from_audit(audit_findings)
    classified = pipeline.classify(gaps)
    queue = pipeline.build_queue(classified)
    return queue
