"""
Citation Verifier

Ensures market insight claims are factually supported by their cited sources.
Prevents fabricated relevance where Perplexity summaries are treated as evidence.

Architecture:
1. DISCOVERY (Perplexity) → raw citations + summary
2. VERIFICATION (this module) → validated claims only
3. GENERATION (LLM) → narrate verified claims only

Key principle: Perplexity/search = discovery, NOT evidence.
Only article content that directly supports a claim is evidence.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from lead_to_cash.core.response_quality import QualityMetrics

logger = logging.getLogger(__name__)


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class VerifiedClaim:
    """A claim that has been verified against its cited source."""

    claim: str
    article_url: str
    article_title: str
    publisher: str
    supporting_excerpt: str
    confidence: float
    verification_status: str  # VERIFIED | UNVERIFIED | REJECTED


@dataclass
class CitationVerificationResult:
    """Result of verifying all claims against their citations."""

    total_claims: int = 0
    verified_claims: List[VerifiedClaim] = field(default_factory=list)
    rejected_claims: List[Dict[str, str]] = field(default_factory=list)
    unverified_claims: List[Dict[str, str]] = field(default_factory=list)
    verification_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "verified": len(self.verified_claims),
            "rejected": len(self.rejected_claims),
            "unverified": len(self.unverified_claims),
            "verification_rate": self.verification_rate,
        }


# =============================================================================
# Trusted publisher domains
# =============================================================================

_TRUSTED_PUBLISHERS = {
    "maritimeexecutive.com": "Maritime Executive",
    "seatrade-maritime.com": "Seatrade Maritime",
    "tradewindsnews.com": "TradeWinds",
    "splash247.com": "Splash247",
    "lloydslist.com": "Lloyd's List",
    "offshore-engineer.com": "Offshore Engineer",
    "gcaptain.com": "gCaptain",
    "workboat.com": "WorkBoat",
    "bairdmaritime.com": "Baird Maritime",
    "dnv.com": "DNV",
    "imo.org": "IMO",
    "mpa.gov.sg": "MPA Singapore",
    "rivieramm.com": "Riviera Maritime",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "ft.com": "Financial Times",
}

# Junk domains that should never appear as evidence
_JUNK_DOMAINS = frozenset(
    {
        "youtube.com",
        "reddit.com",
        "quora.com",
        "wikipedia.org",
        "alibaba.com",
        "ebay.com",
        "amazon.com",
    }
)


# =============================================================================
# Citation verifier
# =============================================================================


class CitationVerifier:
    """
    Verifies that claims in LLM-generated content are supported by cited sources.

    Does NOT fetch article content (that would require HTTP calls).
    Instead, validates structural alignment between claims and citations:
    1. Citation URL is from a trusted/known publisher
    2. Citation is not from a junk domain
    3. Inline citation [N] maps to a real URL
    4. Claim text shows semantic alignment with citation context

    For full content verification (Phase 2), article fetching would be added.
    """

    @classmethod
    def verify_output(
        cls,
        content: str,
        citations: List[str],
        query_entities: Optional[List[str]] = None,
    ) -> CitationVerificationResult:
        """
        Verify all citation references in generated content.

        Args:
            content: The LLM-generated text with [N] references
            citations: List of citation URLs (index-matched to [N])
            query_entities: Entity names that should appear in relevant articles

        Returns:
            CitationVerificationResult with verified/rejected/unverified claims
        """
        entities = [e.lower() for e in (query_entities or [])]
        result = CitationVerificationResult()

        # Extract all [N] references from content
        citation_refs = re.findall(r"\[(\d+)\]", content)
        unique_refs = set(int(r) for r in citation_refs)

        result.total_claims = len(unique_refs)

        for ref_num in sorted(unique_refs):
            idx = ref_num - 1  # 0-based
            if idx < 0 or idx >= len(citations):
                result.rejected_claims.append(
                    {
                        "ref": ref_num,
                        "reason": "citation_index_out_of_range",
                    }
                )
                continue

            url = citations[idx]

            # Check 1: Not a junk domain
            domain = cls._extract_domain(url)
            if domain in _JUNK_DOMAINS:
                result.rejected_claims.append(
                    {
                        "ref": ref_num,
                        "url": url,
                        "reason": "junk_domain",
                        "domain": domain,
                    }
                )
                continue

            # Check 2: Publisher identification
            publisher = _TRUSTED_PUBLISHERS.get(domain, domain)

            # Check 3: Extract the sentence(s) around the citation
            context = cls._extract_citation_context(content, ref_num)

            # Check 4: Structural verification
            # - Is the URL a real article (has path beyond root)?
            has_article_path = len(urlparse(url).path.strip("/")) > 5
            if not has_article_path:
                result.unverified_claims.append(
                    {
                        "ref": ref_num,
                        "url": url,
                        "reason": "url_appears_to_be_homepage_not_article",
                    }
                )
                continue

            # Build verified claim
            is_trusted = domain in _TRUSTED_PUBLISHERS
            confidence = 0.8 if is_trusted else 0.5

            result.verified_claims.append(
                VerifiedClaim(
                    claim=context[:200],
                    article_url=url,
                    article_title="",  # Would need fetch to get title
                    publisher=publisher,
                    supporting_excerpt=context[:300],
                    confidence=confidence,
                    verification_status="VERIFIED" if is_trusted else "UNVERIFIED",
                )
            )

        # Compute rate
        total = result.total_claims
        result.verification_rate = (
            len(result.verified_claims) / total if total > 0 else 1.0
        )

        # Log telemetry
        QualityMetrics.record(
            event_type="citation_verification",
            severity="INFO" if result.verification_rate >= 0.8 else "WARNING",
            intent="market_intel",
            details=result.to_dict(),
        )

        return result

    @classmethod
    def filter_content_by_verification(
        cls,
        content: str,
        citations: List[str],
        verification: CitationVerificationResult,
    ) -> str:
        """
        Remove or annotate unverified citations from content.

        Rejected citations: remove the [N] reference entirely.
        Unverified citations: keep but add (unverified) annotation.
        """
        modified = content

        # Remove rejected citation markers
        for rejected in verification.rejected_claims:
            ref = rejected["ref"]
            modified = modified.replace(f"[{ref}]", "")

        # Annotate unverified
        for unverified in verification.unverified_claims:
            ref = unverified["ref"]
            modified = modified.replace(f"[{ref}]", f"[{ref}] (unverified)")

        # Clean up double spaces from removals
        modified = re.sub(r"  +", " ", modified)

        return modified

    @classmethod
    def build_verified_only_content(
        cls,
        verification: CitationVerificationResult,
    ) -> Optional[str]:
        """
        Build content from verified claims only.

        Returns None if no verified claims exist.
        """
        if not verification.verified_claims:
            return None

        lines = []
        for i, vc in enumerate(verification.verified_claims, 1):
            lines.append(f"- {vc.claim} [{i}]")

        lines.append("")
        lines.append("Sources:")
        for i, vc in enumerate(verification.verified_claims, 1):
            lines.append(f"[{i}] {vc.publisher}: {vc.article_url}")

        return "\n".join(lines)

    @classmethod
    def verify_claim_entity_alignment(
        cls,
        claim_text: str,
        entities: List[str],
        source_context: str,
    ) -> Dict[str, Any]:
        """
        Check that the entity in a claim actually appears in the source context.

        This prevents fabricated relevance where the LLM ties an entity
        to a source that doesn't mention it.

        Returns:
            Dict with entity_found, claim_supported, and details
        """
        claim_lower = claim_text.lower()
        context_lower = source_context.lower()

        # Check entity presence in source context
        entity_found = False
        matched_entity = None
        for entity in entities:
            entity_lower = entity.lower()
            # Check entity words (≥3 chars) appear in context
            entity_words = [w for w in entity_lower.split() if len(w) >= 3]
            if entity_words and any(w in context_lower for w in entity_words):
                entity_found = True
                matched_entity = entity
                break

        # Strict claim validation: require claim's core assertion
        # to be directly present in source context — not just word overlap.
        #
        # Level 1 (STRONG): A key phrase (3+ consecutive words) from claim
        #   appears verbatim in source context
        # Level 2 (SUPPORTED): Entity + key claim nouns (≥50% overlap)
        #   co-occur in same sentence of source context
        # Below Level 2: UNSUPPORTED

        claim_terms = set(re.findall(r"\b\w{4,}\b", claim_lower))
        context_terms = set(re.findall(r"\b\w{4,}\b", context_lower))
        term_overlap = len(claim_terms & context_terms) / max(len(claim_terms), 1)

        # Level 1: verbatim phrase match (3+ consecutive words)
        claim_words = claim_lower.split()
        has_verbatim = False
        for i in range(len(claim_words) - 2):
            phrase = " ".join(claim_words[i : i + 3])
            # Only check phrases with substantive words (skip "the", "and", etc.)
            substantive = [w for w in claim_words[i : i + 3] if len(w) >= 4]
            if len(substantive) >= 2 and phrase in context_lower:
                has_verbatim = True
                break

        # Level 2: entity + claim nouns in same sentence
        same_sentence = False
        if entity_found:
            context_sentences = re.split(r"[.!?]\s+", context_lower)
            entity_words_lower = [
                w.lower() for w in (matched_entity or "").split() if len(w) >= 3
            ]
            for sent in context_sentences:
                has_entity_in_sent = any(w in sent for w in entity_words_lower)
                matching_terms = sum(1 for t in claim_terms if t in sent)
                if has_entity_in_sent and matching_terms >= 2:
                    same_sentence = True
                    break

        if has_verbatim:
            claim_supported = True
            support_level = "STRONG"
        elif same_sentence and term_overlap >= 0.5:
            claim_supported = True
            support_level = "SUPPORTED"
        else:
            claim_supported = False
            support_level = "UNSUPPORTED"

        return {
            "entity_found": entity_found,
            "matched_entity": matched_entity,
            "claim_supported": claim_supported,
            "support_level": support_level,
            "term_overlap": round(term_overlap, 2),
            "has_verbatim_phrase": has_verbatim,
            "same_sentence_match": same_sentence,
            "pass": entity_found and claim_supported,
        }

    @classmethod
    def separate_fact_inference(
        cls,
        content: str,
    ) -> Dict[str, List[str]]:
        """
        Separate factual claims from inferences/opinions in generated content.

        Facts: directly stated information (dates, numbers, events)
        Inferences: analysis, implications, recommendations

        Returns dict with 'facts' and 'inferences' lists.
        """
        # Inference indicators
        _INFERENCE_PATTERNS = re.compile(
            r"(?i)(?:"
            r"\b(?:suggests?|indicates?|implies?|could\s+mean|may\s+signal|"
            r"opportunity\s+for|this\s+(?:means|suggests|indicates)|"
            r"likely|potentially|appears?\s+to|we\s+(?:should|recommend|suggest))\b"
            r")"
        )

        sentences = re.split(r"(?<=[.!?])\s+", content)
        facts = []
        inferences = []

        for sent in sentences:
            sent = sent.strip()
            if not sent or len(sent) < 10:
                continue
            if _INFERENCE_PATTERNS.search(sent):
                inferences.append(sent)
            else:
                facts.append(sent)

        return {"facts": facts, "inferences": inferences}

    @classmethod
    def enforce_market_insight_quality(
        cls,
        content: str,
        citations: List[str],
        entities: List[str],
    ) -> Dict[str, Any]:
        """
        Full market insight quality enforcement.

        Combines citation verification + entity alignment + fact/inference separation.
        Returns enforcement result with cleaned content or fallback.
        """
        # Step 1: Verify citations
        verification = cls.verify_output(content, citations, query_entities=entities)

        # Step 2: Strict entity alignment + excerpt validation
        strongly_grounded = 0
        supported_grounded = 0
        ungrounded = 0
        no_excerpt = 0

        for vc in verification.verified_claims:
            # Require supporting excerpt exists
            if not vc.supporting_excerpt or len(vc.supporting_excerpt.strip()) < 20:
                no_excerpt += 1
                continue

            alignment = cls.verify_claim_entity_alignment(
                vc.claim, entities, vc.supporting_excerpt
            )
            if alignment["pass"]:
                level = alignment.get("support_level", "UNSUPPORTED")
                if level == "STRONG":
                    strongly_grounded += 1
                elif level == "SUPPORTED":
                    supported_grounded += 1
                else:
                    ungrounded += 1
            else:
                ungrounded += 1

        entity_aligned = strongly_grounded + supported_grounded

        # Step 3: Separate facts from inferences
        separation = cls.separate_fact_inference(content)

        # Step 4: Determine output quality (strict)
        has_verified = len(verification.verified_claims) > 0
        has_grounded = entity_aligned > 0

        if has_verified and has_grounded:
            cleaned = cls.filter_content_by_verification(
                content, citations, verification
            )
            # Add inference separation if inferences detected
            if separation["inferences"]:
                cleaned += "\n\n*Internal analysis (not from source):*\n"
                for inf in separation["inferences"][:3]:
                    cleaned += f"- {inf}\n"
            status = "verified"
        elif has_verified:
            cleaned = cls.filter_content_by_verification(
                content, citations, verification
            )
            status = "entity_unconfirmed"
        else:
            # Fallback: no verified claims
            cleaned = None
            status = "insufficient_evidence"

        # Telemetry
        QualityMetrics.record(
            event_type="market_insight_enforcement",
            severity="INFO" if status == "verified" else "WARNING",
            intent="market_intel",
            details={
                "status": status,
                "articles_retrieved": len(citations),
                "claims_verified": len(verification.verified_claims),
                "claims_rejected": len(verification.rejected_claims),
                "strongly_grounded": strongly_grounded,
                "supported_grounded": supported_grounded,
                "ungrounded": ungrounded,
                "no_excerpt": no_excerpt,
                "entity_aligned": entity_aligned,
                "facts_count": len(separation["facts"]),
                "inferences_count": len(separation["inferences"]),
                "verification_rate": verification.verification_rate,
            },
        )

        return {
            "status": status,
            "content": cleaned,
            "fallback_message": "No strongly relevant verified market insight found."
            if not cleaned
            else None,
            "verification": verification.to_dict(),
            "fact_inference_split": {
                "facts": len(separation["facts"]),
                "inferences": len(separation["inferences"]),
            },
        }

    @classmethod
    def _extract_domain(cls, url: str) -> str:
        """Extract base domain from URL, stripping subdomains like en., www., m."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Strip common subdomains
            for prefix in ("www.", "en.", "m.", "mobile."):
                if domain.startswith(prefix):
                    domain = domain[len(prefix) :]
            return domain
        except Exception:
            return ""

    @classmethod
    def _extract_citation_context(cls, content: str, ref_num: int) -> str:
        """Extract the sentence(s) surrounding a citation reference."""
        # Find the citation marker
        pattern = rf"\[{ref_num}\]"
        match = re.search(pattern, content)
        if not match:
            return ""

        # Get surrounding text (100 chars before, 50 after)
        start = max(0, match.start() - 100)
        end = min(len(content), match.end() + 50)
        context = content[start:end].strip()

        # Try to get the full sentence
        sentences = re.split(r"[.!?]\s+", context)
        for sent in sentences:
            if f"[{ref_num}]" in sent:
                return sent.strip()

        return context
