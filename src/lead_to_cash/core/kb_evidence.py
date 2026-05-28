"""
Knowledge Base Evidence Layer

Transforms KB retrieval from raw text to verified, typed evidence.
Every retrieved fact must be traceable to source text with explicit
verification status.

Architecture:
1. Source typing: every KB entry has a declared source type
2. Verification: claims must appear in source text
3. Domain separation: market / product / corporate
4. Retrieval filtering: only VERIFIED entries return to callers

This module wraps KB retrieval — it does NOT modify stored data.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from lead_to_cash.core.response_quality import QualityMetrics

logger = logging.getLogger(__name__)


# =============================================================================
# Source typing
# =============================================================================


class SourceType(str, Enum):
    """Type of source that backs a KB entry."""

    NEWS_ARTICLE = "news_article"
    PRODUCT_PAGE = "product_page"
    BROCHURE = "brochure"
    INVESTOR_REPORT = "investor_report"
    PRESS_RELEASE = "press_release"
    INTERNAL_DATA = "internal_data"  # SAP, curated seed data
    UNKNOWN = "unknown"


class ClaimType(str, Enum):
    """What kind of claim this is."""

    MARKET = "market"  # Market trends, orders, industry news
    PRODUCT = "product"  # Engine specs, features, configurations
    FINANCIAL = "financial"  # Revenue, market cap, earnings
    CORPORATE = "corporate"  # Ownership, leadership, partnerships
    COMPETITIVE = "competitive"  # Win/loss, market share, positioning


class VerificationStatus(str, Enum):
    """Verification state of a KB entry."""

    VERIFIED_STRONG = "verified_strong"  # Entity + claim + context all match
    VERIFIED = "verified"  # Entity + claim match, context partial
    VERIFIED_WEAK = "verified_weak"  # Partial support only
    UNVERIFIED = "unverified"  # Source exists but claim not confirmed
    REJECTED = "rejected"  # Claim contradicted or fabricated
    INTERNAL = "internal"  # Internal data (SAP, seed) — trusted by definition


class KBDomain(str, Enum):
    """Domain partition for retrieval filtering."""

    MARKET = "market"
    PRODUCT = "product"
    CORPORATE = "corporate"


# =============================================================================
# Verified claim structure
# =============================================================================


@dataclass
class VerifiedKBEntry:
    """A KB entry with full verification metadata."""

    entity: str
    claim: str
    claim_type: ClaimType
    value: Optional[str] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    source_type: SourceType = SourceType.UNKNOWN
    source_url: str = ""
    supporting_excerpt: str = ""
    page_ref: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    domain: KBDomain = KBDomain.PRODUCT
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "claim": self.claim,
            "claim_type": self.claim_type.value,
            "value": self.value,
            "unit": self.unit,
            "period": self.period,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "supporting_excerpt": self.supporting_excerpt[:200],
            "verification_status": self.verification_status.value,
            "domain": self.domain.value,
            "confidence": self.confidence,
        }


# =============================================================================
# KB Evidence Filter
# =============================================================================


class KBEvidenceFilter:
    """
    Filters KB retrieval results to return only verified, typed evidence.

    Applied as a post-retrieval step — wraps existing KB queries without
    modifying the underlying database or retrieval logic.
    """

    @classmethod
    def filter_results(
        cls,
        raw_results: List[Dict[str, Any]],
        domain: Optional[KBDomain] = None,
        require_verified: bool = True,
        strict: bool = False,
    ) -> List[VerifiedKBEntry]:
        """
        Filter raw KB results into verified entries.

        Args:
            raw_results: Raw results from KB query
            domain: Optional domain filter (market/product/corporate)
            require_verified: If True, exclude unverified entries
            strict: If True, exclude VERIFIED_WEAK entries too

        Returns:
            List of VerifiedKBEntry objects that pass all checks
        """
        entries = []
        rejected = 0

        # Accepted statuses based on mode
        if strict:
            accepted = {
                VerificationStatus.INTERNAL,
                VerificationStatus.VERIFIED_STRONG,
                VerificationStatus.VERIFIED,
            }
        elif require_verified:
            accepted = {
                VerificationStatus.INTERNAL,
                VerificationStatus.VERIFIED_STRONG,
                VerificationStatus.VERIFIED,
                VerificationStatus.VERIFIED_WEAK,
            }
        else:
            accepted = set(VerificationStatus)

        # Split multi-claim entries into atomic claims
        atomic_results = []
        split_count = 0
        for raw in raw_results:
            atoms = cls.split_atomic_claims(raw)
            if len(atoms) > 1:
                split_count += len(atoms) - 1
            atomic_results.extend(atoms)

        rejection_reasons = {"domain_mismatch": 0, "verification_failed": 0}

        for raw in atomic_results:
            entry = cls._classify_entry(raw)

            # Domain filter
            if domain and entry.domain != domain:
                rejection_reasons["domain_mismatch"] += 1
                continue

            # Verification filter
            if entry.verification_status not in accepted:
                rejected += 1
                rejection_reasons["verification_failed"] += 1
                continue

            entries.append(entry)

        # Enhanced telemetry with rejection reasons
        QualityMetrics.record(
            event_type="kb_evidence_filter",
            severity="INFO",
            intent="kb_retrieval",
            details={
                "raw_count": len(raw_results),
                "atomic_count": len(atomic_results),
                "split_count": split_count,
                "verified_count": len(entries),
                "rejected_count": rejected,
                "rejection_reasons": rejection_reasons,
                "domain_filter": domain.value if domain else None,
                "require_verified": require_verified,
                "strict": strict,
                "evidence_strength": {
                    s.value: sum(1 for e in entries if e.verification_status == s)
                    for s in VerificationStatus
                },
            },
        )

        return entries

    @classmethod
    def _classify_entry(cls, raw: Dict[str, Any]) -> VerifiedKBEntry:
        """Classify a raw KB result into a typed, verified entry."""
        # Determine source type
        source_type = cls._detect_source_type(raw)

        # Determine claim type
        claim_type = cls._detect_claim_type(raw)

        # Determine domain
        domain = cls._detect_domain(claim_type)

        # Determine verification status
        verification = cls._verify_entry(raw, source_type)

        # Confidence: scaled by verification strength
        confidence = {
            VerificationStatus.INTERNAL: 1.0,
            VerificationStatus.VERIFIED_STRONG: 0.9,
            VerificationStatus.VERIFIED: 0.8,
            VerificationStatus.VERIFIED_WEAK: 0.6,
            VerificationStatus.UNVERIFIED: 0.3,
            VerificationStatus.REJECTED: 0.0,
        }.get(verification, 0.0)

        return VerifiedKBEntry(
            entity=raw.get("entity", raw.get("name", raw.get("manufacturer", ""))),
            claim=raw.get("claim", raw.get("description", raw.get("content", ""))),
            claim_type=claim_type,
            value=raw.get("value", raw.get("power_kw")),
            unit=raw.get("unit", "kW" if raw.get("power_kw") else None),
            period=raw.get("period"),
            source_type=source_type,
            source_url=raw.get("source_url", raw.get("url", "")),
            supporting_excerpt=raw.get("supporting_excerpt", raw.get("excerpt", "")),
            page_ref=raw.get("page_ref", ""),
            verification_status=verification,
            domain=domain,
            confidence=confidence,
        )

    @classmethod
    def _detect_source_type(cls, raw: Dict[str, Any]) -> SourceType:
        """Detect source type from raw entry metadata."""
        # Explicit source_type field
        st = raw.get("source_type", "")
        if st:
            try:
                return SourceType(st)
            except ValueError:
                pass

        # Heuristic detection from URL or content
        url = raw.get("source_url", raw.get("url", "")).lower()
        if not url:
            # No URL = likely internal/seed data
            if raw.get("power_kw") or raw.get("rpm") or raw.get("cylinders"):
                return SourceType.INTERNAL_DATA
            return SourceType.UNKNOWN

        if "investor" in url or "annual-report" in url or "ir." in url:
            return SourceType.INVESTOR_REPORT
        if "press" in url or "newsroom" in url or "media" in url:
            return SourceType.PRESS_RELEASE
        if "product" in url or "engine" in url or "specification" in url:
            return SourceType.PRODUCT_PAGE
        if any(
            d in url
            for d in [
                "maritimeexecutive",
                "seatrade",
                "tradewinds",
                "reuters",
                "bloomberg",
                "splash247",
                "gcaptain",
            ]
        ):
            return SourceType.NEWS_ARTICLE

        return SourceType.UNKNOWN

    @classmethod
    def _detect_claim_type(cls, raw: Dict[str, Any]) -> ClaimType:
        """Detect claim type from raw entry content."""
        content = (
            raw.get("claim", "")
            + " "
            + raw.get("description", "")
            + " "
            + raw.get("content", "")
        ).lower()

        # Product specs
        if any(k in raw for k in ["power_kw", "rpm", "cylinders", "bore", "stroke"]):
            return ClaimType.PRODUCT
        if any(
            w in content for w in ["kw", "rpm", "engine", "fuel consumption", "bore"]
        ):
            return ClaimType.PRODUCT

        # Financial
        if any(
            w in content
            for w in ["revenue", "earnings", "market cap", "profit", "ebitda"]
        ):
            return ClaimType.FINANCIAL

        # Competitive
        if any(
            w in content for w in ["win", "loss", "contract", "awarded", "market share"]
        ):
            return ClaimType.COMPETITIVE

        # Corporate
        if any(
            w in content
            for w in ["ownership", "board", "ceo", "partnership", "acquisition"]
        ):
            return ClaimType.CORPORATE

        # Default to market
        return ClaimType.MARKET

    @classmethod
    def _detect_domain(cls, claim_type: ClaimType) -> KBDomain:
        """Map claim type to KB domain."""
        return {
            ClaimType.MARKET: KBDomain.MARKET,
            ClaimType.PRODUCT: KBDomain.PRODUCT,
            ClaimType.FINANCIAL: KBDomain.CORPORATE,
            ClaimType.CORPORATE: KBDomain.CORPORATE,
            ClaimType.COMPETITIVE: KBDomain.MARKET,
        }.get(claim_type, KBDomain.MARKET)

    @classmethod
    def _verify_entry(
        cls, raw: Dict[str, Any], source_type: SourceType
    ) -> VerificationStatus:
        """
        Structured 3-check verification.

        Check 1 (entity_match): entity must appear in supporting excerpt
        Check 2 (claim_match): key claim terms must appear in excerpt
        Check 3 (context_match): entity and claim terms in same span

        Scoring:
        - All 3 pass → VERIFIED_STRONG (0.9)
        - Checks 1+2 pass → VERIFIED (0.8)
        - Only 1 check passes → VERIFIED_WEAK (0.6)
        - No checks pass → UNVERIFIED (0.3)
        """
        # Internal data is trusted by definition
        if source_type == SourceType.INTERNAL_DATA:
            return VerificationStatus.INTERNAL

        # Must have source URL
        if not raw.get("source_url") and not raw.get("url"):
            return VerificationStatus.UNVERIFIED

        # Must have supporting excerpt
        excerpt = raw.get("supporting_excerpt", raw.get("excerpt", ""))
        if not excerpt:
            return VerificationStatus.UNVERIFIED

        entity = raw.get("entity", raw.get("name", raw.get("manufacturer", ""))).lower()
        claim = raw.get("claim", raw.get("description", "")).lower()
        excerpt_lower = excerpt.lower()

        # ── Check 1: Entity match ───────────────────────────────────
        # Entity name (or significant portion) must appear in excerpt
        entity_match = False
        if entity and len(entity) >= 3:
            entity_words = entity.split()
            # Match if any entity word (≥3 chars) appears in excerpt
            entity_match = any(w in excerpt_lower for w in entity_words if len(w) >= 3)

        # ── Check 2: Claim match ────────────────────────────────────
        # Key claim terms (4+ char words) must have ≥40% overlap with excerpt
        claim_match = False
        if claim:
            claim_terms = set(re.findall(r"\b\w{4,}\b", claim))
            excerpt_terms = set(re.findall(r"\b\w{4,}\b", excerpt_lower))
            if claim_terms:
                overlap = len(claim_terms & excerpt_terms)
                claim_match = (overlap / len(claim_terms)) >= 0.4

        # ── Check 3: Context match ──────────────────────────────────
        # Entity and at least one claim term must appear in same sentence
        context_match = False
        if entity_match and claim_match:
            sentences = re.split(r"[.!?]\s+", excerpt_lower)
            for sent in sentences:
                has_entity = any(w in sent for w in entity.split() if len(w) >= 3)
                has_claim = any(w in sent for w in claim_terms if len(w) >= 4)
                if has_entity and has_claim:
                    context_match = True
                    break

        # ── Score verification ──────────────────────────────────────
        checks_passed = sum([entity_match, claim_match, context_match])

        if checks_passed == 3:
            return VerificationStatus.VERIFIED_STRONG
        if checks_passed == 2:
            return VerificationStatus.VERIFIED
        if checks_passed == 1:
            return VerificationStatus.VERIFIED_WEAK
        return VerificationStatus.UNVERIFIED

    # =================================================================
    # Atomic claim splitting
    # =================================================================

    @classmethod
    def split_atomic_claims(cls, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a raw KB entry with multiple claims into atomic entries.

        Detects multiple claims via sentence splitting + conjunction patterns.
        Each atomic entry inherits the parent's source metadata.
        """
        claim = raw.get("claim", raw.get("description", ""))
        if not claim or len(claim) < 20:
            return [raw]

        # Split on sentence boundaries that indicate separate claims
        # "Company X did A. They also did B." → two claims
        sentences = re.split(r"(?<=[.!])\s+(?=[A-Z])", claim)
        if len(sentences) <= 1:
            # Try conjunction split: "X did A and also did B"
            parts = re.split(
                r"\.\s*(?:Also|Additionally|Furthermore|Moreover)\s+",
                claim,
                flags=re.IGNORECASE,
            )
            if len(parts) <= 1:
                return [raw]
            sentences = parts

        if len(sentences) <= 1:
            return [raw]

        # Split into atomic entries
        result = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 15:
                continue
            atomic = dict(raw)
            atomic["claim"] = sent
            result.append(atomic)

        return result if result else [raw]

    # =================================================================
    # Response building with usage policy enforcement
    # =================================================================

    @classmethod
    def build_evidence_response(
        cls,
        entries: List[VerifiedKBEntry],
        for_reasoning: bool = False,
    ) -> Optional[str]:
        """
        Build a response from verified entries with controlled fallback.

        Tier 1 (strict): INTERNAL + VERIFIED_STRONG
        Tier 2 (fallback): + VERIFIED (with disclaimer, reduced confidence)
        NEVER: VERIFIED_WEAK, UNVERIFIED

        for_reasoning=True starts at Tier 1 and falls back to Tier 2.
        for_reasoning=False uses Tier 2 directly.

        Returns None only if no qualifying entries at any tier.
        """
        if not entries:
            return None

        tier1 = {VerificationStatus.INTERNAL, VerificationStatus.VERIFIED_STRONG}
        tier2 = tier1 | {VerificationStatus.VERIFIED}

        used_fallback = False

        if for_reasoning:
            qualified = [e for e in entries if e.verification_status in tier1]
            if not qualified:
                # Controlled fallback: include VERIFIED with disclaimer
                qualified = [e for e in entries if e.verification_status in tier2]
                used_fallback = bool(qualified)
                # Reduce confidence for fallback entries
                for e in qualified:
                    if e.verification_status == VerificationStatus.VERIFIED:
                        e.confidence = min(e.confidence, 0.7)
        else:
            qualified = [e for e in entries if e.verification_status in tier2]

        # Track VERIFIED_WEAK exclusions
        weak_excluded = sum(
            1
            for e in entries
            if e.verification_status == VerificationStatus.VERIFIED_WEAK
        )
        if weak_excluded > 0:
            QualityMetrics.record(
                event_type="kb_weak_evidence_excluded",
                severity="INFO",
                intent="kb_response",
                details={
                    "weak_excluded": weak_excluded,
                    "qualified": len(qualified),
                    "for_reasoning": for_reasoning,
                },
            )

        if not qualified:
            return None

        # Log fallback usage
        if used_fallback:
            QualityMetrics.record(
                event_type="kb_reasoning_fallback",
                severity="INFO",
                intent="kb_response",
                details={
                    "reason": "no_strong_evidence_available",
                    "fallback_entries": len(qualified),
                },
            )

        lines = []
        if used_fallback:
            lines.append("*Based on moderately verified sources.*\n")
        for e in qualified:
            source_label = (
                f" [{e.source_type.value}]"
                if e.source_type != SourceType.INTERNAL_DATA
                else ""
            )
            lines.append(f"- {e.claim}{source_label}")

        return "\n".join(lines)

    @classmethod
    def get_audit_summary(
        cls,
        entries: List[VerifiedKBEntry],
    ) -> Dict[str, Any]:
        """Produce an audit summary of KB entries."""
        total = len(entries)
        by_status = {}
        by_type = {}
        by_domain = {}

        for e in entries:
            by_status[e.verification_status.value] = (
                by_status.get(e.verification_status.value, 0) + 1
            )
            by_type[e.source_type.value] = by_type.get(e.source_type.value, 0) + 1
            by_domain[e.domain.value] = by_domain.get(e.domain.value, 0) + 1

        verified = by_status.get("verified", 0) + by_status.get("internal", 0)
        verification_rate = verified / total if total > 0 else 0

        return {
            "total_entries": total,
            "verification_rate": round(verification_rate, 3),
            "by_status": by_status,
            "by_source_type": by_type,
            "by_domain": by_domain,
        }
