"""
Post-Generation Output Enforcer — Deterministic Correctness Layer

Enforces correctness AFTER the LLM generates output. No reliance on
LLM compliance. Every output passes through this pipeline before
reaching the user.

Pipeline (sequential, mandatory):
    1. DeclarativeClaimValidator — extract and verify factual claims
    2. FactInferenceDetector — separate facts from inferences
    3. SynthesisBreaker — split compound claims into atomic facts
    4. OutputRewriter — reconstruct as Key Developments + Internal Analysis
    5. ZeroToleranceGate — discard if validation fails heavily
    6. EnforcementTelemetry — track all post-generation actions

Architecture:
    LLM output → [1] → [2] → [3] → [4] → [5] → user
                                              ↘ [6] telemetry

NO MOCKS, NO FALLBACKS — production implementation.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Verified Reference Data (from KB battlecard — static, deterministic)
# =============================================================================

# Competitor entities that trigger claim extraction
COMPETITOR_ENTITIES: FrozenSet[str] = frozenset(
    s.lower()
    for s in [
        "Caterpillar",
        "CAT",
        "MaK",
        "Cummins",
        "MAN Energy Solutions",
        "MAN",
        "Wartsila",
        "Wärtsilä",
        "HiMSEN",
        "HD Hyundai",
        "Hyundai",
        "Daihatsu",
        "Yanmar",
        "ABC",
        "Anglo Belgian Corporation",
        "Volvo Penta",
        "Niigata",
        "Bergen Engines",
        "Bergen",
        "Siemens",
        "Rolls-Royce",
    ]
)

# Verified competitor specs from KB battlecard (model → kW at rated duty)
# These are the ONLY competitor specs we can confirm.
_VERIFIED_COMPETITOR_SPECS: Dict[str, Dict[str, Any]] = {
    "cat c32": {"kw": 1081, "manufacturer": "caterpillar"},
    "cat c32b": {"kw": 1193, "manufacturer": "caterpillar"},
    "caterpillar c32": {"kw": 1081, "manufacturer": "caterpillar"},
    "caterpillar c32b": {"kw": 1193, "manufacturer": "caterpillar"},
    "cat 3512b": {"kw": 1491, "manufacturer": "caterpillar"},
    "caterpillar 3512b": {"kw": 1491, "manufacturer": "caterpillar"},
    "cat 3516c": {"kw": 2525, "manufacturer": "caterpillar"},
    "caterpillar 3516c": {"kw": 2525, "manufacturer": "caterpillar"},
    "cummins qsk38": {"kw": 1119, "manufacturer": "cummins"},
    "cummins qsk50": {"kw": 1491, "manufacturer": "cummins"},
    "cummins qsk60": {"kw": 1864, "manufacturer": "cummins"},
    "cummins qsk78": {"kw": 2237, "manufacturer": "cummins"},
    "wärtsilä 8l20": {"kw": 1600, "manufacturer": "wärtsilä"},
    "wartsila 8l20": {"kw": 1600, "manufacturer": "wärtsilä"},
    "wärtsilä 9l20": {"kw": 1800, "manufacturer": "wärtsilä"},
    "wartsila 9l20": {"kw": 1800, "manufacturer": "wärtsilä"},
    "man d2862 le463": {"kw": 1029, "manufacturer": "man"},
    "man v12-2000cr": {"kw": 1324, "manufacturer": "man"},
    "cat mak m32c": {"kw": 6000, "manufacturer": "caterpillar"},
    "caterpillar mak m32c": {"kw": 6000, "manufacturer": "caterpillar"},
    "mak m32c": {"kw": 6000, "manufacturer": "caterpillar"},
    # MaK M20 C / M25 E — OEM: h-cpc.cat.com (Caterpillar Marine)
    "mak m20": {"kw": 1800, "manufacturer": "caterpillar"},
    "mak m 20 c": {"kw": 1800, "manufacturer": "caterpillar"},
    "mak m25": {"kw": 3150, "manufacturer": "caterpillar"},
    "mak m 25 e": {"kw": 3150, "manufacturer": "caterpillar"},
    # Bergen B33:45 — OEM: bergenengines.com (Langley Holdings)
    "bergen b33:45l6": {"kw": 3600, "manufacturer": "bergen"},
    "bergen b33:45l8": {"kw": 4800, "manufacturer": "bergen"},
    "bergen b33:45l9": {"kw": 5400, "manufacturer": "bergen"},
    "bergen b33:45v12": {"kw": 7200, "manufacturer": "bergen"},
    "bergen b33:45": {"kw": 5400, "manufacturer": "bergen"},
    # HiMSEN H17/28, H21/32 — OEM: hyundai-engine.com (HD Hyundai)
    "himsen h17/28": {"kw": 960, "manufacturer": "hyundai"},
    "himsen h21/32": {"kw": 1800, "manufacturer": "hyundai"},
    # Volvo Penta D8/D13/D16 marine — OEM: volvopenta.com
    "volvo penta d8": {"kw": 441, "manufacturer": "volvo penta"},
    "volvo penta d13": {"kw": 735, "manufacturer": "volvo penta"},
    "volvo penta d16": {"kw": 625, "manufacturer": "volvo penta"},
    # Yanmar 6EY/8N330/12AYM — OEM: yanmar.com, yanmarmarine.eu
    "yanmar 6ey22aw": {"kw": 1370, "manufacturer": "yanmar"},
    "yanmar 6ey26w": {"kw": 1920, "manufacturer": "yanmar"},
    "yanmar 8n330": {"kw": 3310, "manufacturer": "yanmar"},
    "yanmar 12aym-wgt": {"kw": 1340, "manufacturer": "yanmar"},
    "yanmar 12aym": {"kw": 1340, "manufacturer": "yanmar"},
    # Daihatsu DK-28/DK-36 — OEM: d-infi.com (Daihatsu INFINEARTH)
    "daihatsu 8dk-28e": {"kw": 2800, "manufacturer": "daihatsu"},
    "daihatsu dk-28": {"kw": 2800, "manufacturer": "daihatsu"},
    "daihatsu 6dkm-36e": {"kw": 3500, "manufacturer": "daihatsu"},
    "daihatsu 8dkm-36e": {"kw": 4650, "manufacturer": "daihatsu"},
    "daihatsu dk-36": {"kw": 4650, "manufacturer": "daihatsu"},
    # Niigata 28AHX/34HX — OEM: ihi.co.jp/ips (IHI Power Systems)
    "niigata 6mg28ahx": {"kw": 2220, "manufacturer": "niigata"},
    "niigata 8mg28ahx": {"kw": 2960, "manufacturer": "niigata"},
    "niigata 16mg28ahx": {"kw": 5920, "manufacturer": "niigata"},
    "niigata 28ahx": {"kw": 5920, "manufacturer": "niigata"},
    "niigata 6mg34hx": {"kw": 3033, "manufacturer": "niigata"},
    "niigata 8mg34hx": {"kw": 3640, "manufacturer": "niigata"},
    "niigata 34hx": {"kw": 3640, "manufacturer": "niigata"},
}

# Verified MTU specs from KB battlecard
_VERIFIED_MTU_SPECS: Dict[str, int] = {
    "8v 2000 m72": 720,
    "10v 2000 m72": 900,
    "12v 2000 m93": 1340,
    "16v 2000 m93": 1790,
    "12v 4000 m63": 1800,
    "16v 4000 m63": 2400,
    "12v 4000 m73": 2040,
    "16v 4000 m73": 2720,
    "20v 4000 m93": 3900,
    "12v 4000 m05-n": 1492,
    "16v 8000 m71": 7200,
    "20v 8000 m91": 10000,
}

# Corporate ownership facts we can verify
_VERIFIED_CORPORATE_FACTS: Dict[str, str] = {
    "man energy solutions": "subsidiary of Volkswagen Group (VW)",
    "bergen engines": "owned by Langley Holdings (sold by Rolls-Royce in 2021)",
    "himsen": "brand of HD Hyundai (HD Korea Shipbuilding & Offshore Engineering)",
    "mak": "brand of Caterpillar (acquired from Krupp in 1997)",
    "mtu": "brand of Rolls-Royce Power Systems (RRPS)",
    "volvo penta": "subsidiary of Volvo Group (AB Volvo)",
    "daihatsu diesel": "subsidiary of Daihatsu Industries (Daihatsu Diesel Mfg)",
    "daihatsu": "subsidiary of Daihatsu Industries (marine diesel division)",
    "yanmar": "independent Japanese company (Yanmar Holdings)",
    "niigata power systems": "subsidiary of IHI Corporation (acquired 2003)",
    "niigata": "subsidiary of IHI Corporation (Niigata Power Systems)",
    "wärtsilä": "independent Finnish company (Wärtsilä Corporation, Helsinki-listed)",
    "wartsila": "independent Finnish company (Wärtsilä Corporation, Helsinki-listed)",
    "anglo belgian corporation": "independent Belgian company (ABC, Ghent-based)",
    "abc": "independent Belgian company (Anglo Belgian Corporation, Ghent-based)",
    "siemens energy": "independent German company (publicly listed, Frankfurt-listed since 2020)",
}


# =============================================================================
# Data Structures
# =============================================================================


class ClaimCategory(Enum):
    """Categories of extractable claims."""

    COMPETITOR_SPEC = "competitor_spec"
    OWNERSHIP = "ownership"
    ACQUISITION = "acquisition"
    PRODUCT_ATTRIBUTE = "product_attribute"
    CORPORATE_FACT = "corporate_fact"


class ClaimVerdict(Enum):
    """Verification verdict for an extracted claim."""

    VERIFIED = "verified"  # Matches KB exactly
    CONTRADICTED = "contradicted"  # Conflicts with KB data
    UNVERIFIABLE = "unverifiable"  # Not in KB, cannot confirm
    REMOVED = "removed"  # Stripped from output


@dataclass
class ExtractedClaim:
    """A factual claim extracted from LLM output."""

    text: str  # The original sentence
    category: ClaimCategory
    entity: str  # The entity the claim is about
    value: Optional[str] = None  # Specific value claimed (e.g., "1500 kW")
    verdict: ClaimVerdict = ClaimVerdict.UNVERIFIABLE
    replacement: Optional[str] = None  # What to replace with (if removed)
    source_line: int = 0  # Line number in original output


@dataclass
class FactInferenceSplit:
    """Result of separating facts from inferences."""

    facts: List[str]
    inferences: List[str]
    violations_moved: int = 0  # Inference sentences found in fact sections


@dataclass
class AtomicFact:
    """A single, atomic factual statement."""

    text: str
    entity: str
    source_hint: Optional[str] = None  # Which source this came from


@dataclass
class EnforcementReport:
    """Complete report of all post-generation enforcement actions."""

    original_text: str
    enforced_text: str
    was_modified: bool
    claims_extracted: int = 0
    claims_removed: int = 0
    claims_contradicted: int = 0
    fact_inference_violations: int = 0
    sentences_atomized: int = 0
    output_rewritten: bool = False
    fallback_triggered: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def summary(self) -> str:
        parts = []
        if self.claims_removed:
            parts.append(f"{self.claims_removed} claims removed")
        if self.claims_contradicted:
            parts.append(f"{self.claims_contradicted} contradicted")
        if self.fact_inference_violations:
            parts.append(f"{self.fact_inference_violations} inferences relocated")
        if self.sentences_atomized:
            parts.append(f"{self.sentences_atomized} compound facts split")
        if self.output_rewritten:
            parts.append("output restructured")
        if self.fallback_triggered:
            parts.append("FALLBACK: insufficient evidence")
        return "; ".join(parts) if parts else "no enforcement needed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "was_modified": self.was_modified,
            "claims_extracted": self.claims_extracted,
            "claims_removed": self.claims_removed,
            "claims_contradicted": self.claims_contradicted,
            "fact_inference_violations": self.fact_inference_violations,
            "sentences_atomized": self.sentences_atomized,
            "output_rewritten": self.output_rewritten,
            "fallback_triggered": self.fallback_triggered,
            "timestamp": self.timestamp,
        }


# =============================================================================
# TASK 1 — Declarative Claim Validator
# =============================================================================


class DeclarativeClaimValidator:
    """
    Extracts and validates all factual claims about competitors, ownership,
    acquisitions, and product attributes. Claims not in verified KB are removed.

    Operates sentence-by-sentence. No LLM involvement.
    """

    # Patterns to extract competitor spec claims: "X produces/delivers/rated at N kW"
    _SPEC_CLAIM_PATTERN = re.compile(
        r"(?:produces?|delivers?|generates?|rated\s+at|output\s+(?:of|is)|"
        r"offers?\s+(?:up\s+to)?|power(?:ed)?\s+(?:at|of|to)|"
        r"capacity\s+of|maximum\s+(?:of|power)|provides?)\s+"
        r"(?:up\s+to\s+)?(\d[\d,]*)\s*(?:kW|kw|MW|mw|hp|HP)",
        re.IGNORECASE,
    )

    # Patterns for standalone spec values: "the 1500 kW engine" or "1500-kW"
    _INLINE_SPEC_PATTERN = re.compile(
        r"(\d[\d,]*)\s*[-–]?\s*(?:kW|kw|MW|mw|hp|HP)\b",
    )

    # Ownership / acquisition patterns
    _OWNERSHIP_PATTERN = re.compile(
        r"\b(?:subsidiary\s+of|owned\s+by|part\s+of|division\s+of|"
        r"belongs?\s+to|unit\s+of|arm\s+of|brand\s+of)\b",
        re.IGNORECASE,
    )

    _ACQUISITION_PATTERN = re.compile(
        r"\b(?:acquired|bought|purchased|merged\s+with|"
        r"taken\s+over|acquisition\s+(?:of|by))\b",
        re.IGNORECASE,
    )

    @classmethod
    def extract_claims(cls, text: str) -> List[ExtractedClaim]:
        """Extract all verifiable factual claims from output text."""
        claims = []
        sentences = _split_sentences(text)

        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()

            # Check if sentence mentions a competitor entity
            mentioned_entity = _find_competitor_entity(sentence_lower)
            if not mentioned_entity:
                # Also check for MTU spec claims (our own products)
                mtu_entity = _find_mtu_entity(sentence_lower)
                if mtu_entity:
                    spec_match = cls._SPEC_CLAIM_PATTERN.search(sentence)
                    if not spec_match:
                        spec_match = cls._INLINE_SPEC_PATTERN.search(sentence)
                    if spec_match:
                        claimed_value = spec_match.group(1).replace(",", "")
                        claims.append(
                            ExtractedClaim(
                                text=sentence.strip(),
                                category=ClaimCategory.PRODUCT_ATTRIBUTE,
                                entity=mtu_entity,
                                value=f"{claimed_value} kW",
                                source_line=i,
                            )
                        )
                continue

            # Competitor spec claim
            spec_match = cls._SPEC_CLAIM_PATTERN.search(sentence)
            if not spec_match:
                spec_match = cls._INLINE_SPEC_PATTERN.search(sentence)
            if spec_match:
                claimed_value = spec_match.group(1).replace(",", "")
                claims.append(
                    ExtractedClaim(
                        text=sentence.strip(),
                        category=ClaimCategory.COMPETITOR_SPEC,
                        entity=mentioned_entity,
                        value=f"{claimed_value} kW",
                        source_line=i,
                    )
                )

            # Ownership claim
            if cls._OWNERSHIP_PATTERN.search(sentence):
                claims.append(
                    ExtractedClaim(
                        text=sentence.strip(),
                        category=ClaimCategory.OWNERSHIP,
                        entity=mentioned_entity,
                        source_line=i,
                    )
                )

            # Acquisition claim
            if cls._ACQUISITION_PATTERN.search(sentence):
                claims.append(
                    ExtractedClaim(
                        text=sentence.strip(),
                        category=ClaimCategory.ACQUISITION,
                        entity=mentioned_entity,
                        source_line=i,
                    )
                )

        return claims

    @classmethod
    def validate_claims(cls, claims: List[ExtractedClaim]) -> List[ExtractedClaim]:
        """Validate each claim against verified KB data."""
        for claim in claims:
            if claim.category == ClaimCategory.COMPETITOR_SPEC:
                claim.verdict, claim.replacement = cls._validate_competitor_spec(claim)
            elif claim.category == ClaimCategory.PRODUCT_ATTRIBUTE:
                claim.verdict, claim.replacement = cls._validate_mtu_spec(claim)
            elif claim.category in (
                ClaimCategory.OWNERSHIP,
                ClaimCategory.ACQUISITION,
            ):
                claim.verdict, claim.replacement = cls._validate_corporate_fact(claim)
            else:
                claim.verdict = ClaimVerdict.UNVERIFIABLE
                claim.replacement = "Cannot confirm this claim from verified sources."
        return claims

    @classmethod
    def apply_verdicts(cls, text: str, claims: List[ExtractedClaim]) -> str:
        """Replace or remove invalidated claims in the output text."""
        result = text
        # Process in reverse order to preserve string positions
        for claim in sorted(claims, key=lambda c: c.source_line, reverse=True):
            if claim.verdict in (ClaimVerdict.UNVERIFIABLE, ClaimVerdict.CONTRADICTED):
                if claim.replacement:
                    result = result.replace(claim.text, claim.replacement, 1)
        return result

    @classmethod
    def _validate_competitor_spec(
        cls, claim: ExtractedClaim
    ) -> Tuple[ClaimVerdict, Optional[str]]:
        """Validate a competitor specification claim against KB."""
        if not claim.value:
            return ClaimVerdict.UNVERIFIABLE, (
                "Cannot confirm this specification from verified sources."
            )

        entity_lower = claim.entity.lower()
        claimed_kw = _parse_kw(claim.value)
        if claimed_kw is None:
            return ClaimVerdict.UNVERIFIABLE, (
                "Cannot confirm this specification from verified sources."
            )

        # Try to find matching verified spec
        for model_key, spec_data in _VERIFIED_COMPETITOR_SPECS.items():
            if entity_lower in model_key or model_key.startswith(entity_lower):
                # Found a matching model — check if claimed value matches
                verified_kw = spec_data["kw"]
                tolerance = max(50, verified_kw * 0.05)  # 5% or 50 kW
                if abs(claimed_kw - verified_kw) <= tolerance:
                    return ClaimVerdict.VERIFIED, None
                else:
                    return ClaimVerdict.CONTRADICTED, (
                        "Cannot confirm this specification from verified sources."
                    )

        # Check if the claim sentence mentions a specific model we know
        sentence_lower = claim.text.lower()
        for model_key, spec_data in _VERIFIED_COMPETITOR_SPECS.items():
            # Extract model designation (e.g., "c32", "qsk60", "3516c")
            model_parts = model_key.split()
            model_designation = model_parts[-1] if len(model_parts) > 1 else model_key
            if model_designation in sentence_lower:
                verified_kw = spec_data["kw"]
                tolerance = max(50, verified_kw * 0.05)
                if abs(claimed_kw - verified_kw) <= tolerance:
                    return ClaimVerdict.VERIFIED, None
                else:
                    return ClaimVerdict.CONTRADICTED, (
                        "Cannot confirm this specification from verified sources."
                    )

        # No matching model in KB — unverifiable
        return ClaimVerdict.UNVERIFIABLE, (
            "Cannot confirm this competitor specification from verified sources."
        )

    @classmethod
    def _validate_mtu_spec(
        cls, claim: ExtractedClaim
    ) -> Tuple[ClaimVerdict, Optional[str]]:
        """Validate an MTU specification claim against KB."""
        if not claim.value:
            return ClaimVerdict.VERIFIED, None  # Non-spec MTU claims pass

        claimed_kw = _parse_kw(claim.value)
        if claimed_kw is None:
            return ClaimVerdict.VERIFIED, None

        sentence_lower = claim.text.lower()
        for model_key, verified_kw in _VERIFIED_MTU_SPECS.items():
            # Normalize model key for matching (e.g., "12v 2000 m93")
            normalized = model_key.replace(" ", r"\s*")
            if re.search(normalized, sentence_lower):
                tolerance = max(50, verified_kw * 0.05)
                if abs(claimed_kw - verified_kw) <= tolerance:
                    return ClaimVerdict.VERIFIED, None
                else:
                    return ClaimVerdict.CONTRADICTED, (
                        f"The verified rating for MTU {model_key.upper()} is "
                        f"{verified_kw:,} kW. The stated value could not be confirmed."
                    )

        # MTU model not in our spec table — let it pass (we may not cover all)
        return ClaimVerdict.VERIFIED, None

    @classmethod
    def _validate_corporate_fact(
        cls, claim: ExtractedClaim
    ) -> Tuple[ClaimVerdict, Optional[str]]:
        """Validate ownership / acquisition claims against known facts."""
        entity_lower = claim.entity.lower()
        sentence_lower = claim.text.lower()

        for company, fact in _VERIFIED_CORPORATE_FACTS.items():
            if company in entity_lower or company in sentence_lower:
                # We have a known fact — check if the claim contradicts it
                fact_lower = fact.lower()
                # Extract the claimed parent/owner from the sentence
                # If sentence says "subsidiary of X" and our fact says "subsidiary of Y",
                # check if X matches Y
                for parent_keyword in [
                    "subsidiary of",
                    "owned by",
                    "part of",
                    "acquired by",
                    "merged with",
                    "bought by",
                ]:
                    if parent_keyword in sentence_lower:
                        # Extract what follows the keyword
                        idx = sentence_lower.index(parent_keyword) + len(parent_keyword)
                        remainder = sentence_lower[idx:].strip()
                        # Check if the claimed parent matches the verified fact
                        fact_entities = _extract_key_terms(fact_lower)
                        remainder_terms = set(remainder.split()[:5])
                        if fact_entities & remainder_terms:
                            return ClaimVerdict.VERIFIED, None
                        else:
                            return ClaimVerdict.CONTRADICTED, (
                                f"Cannot confirm this corporate claim from verified "
                                f"sources. Verified information: {fact}."
                            )

        # No verified fact available for this entity
        return ClaimVerdict.UNVERIFIABLE, (
            "Cannot confirm this corporate fact from verified sources."
        )


# =============================================================================
# TASK 2 — Fact / Inference Detector
# =============================================================================


class FactInferenceDetector:
    """
    Parses output into sections and ensures inference language never
    appears in factual sections. Moves violations to Internal Analysis.

    Deterministic: regex-based detection, no LLM.
    """

    # Inference indicators that MUST NOT appear in fact sections
    _INFERENCE_PATTERNS: List[re.Pattern] = [
        re.compile(r"\bthis\s+suggests?\b", re.IGNORECASE),
        re.compile(r"\bthis\s+highlights?\b", re.IGNORECASE),
        re.compile(r"\bthis\s+indicates?\b", re.IGNORECASE),
        re.compile(r"\bthis\s+means?\b", re.IGNORECASE),
        re.compile(r"\bthis\s+implies?\b", re.IGNORECASE),
        re.compile(r"\btherefore\b", re.IGNORECASE),
        re.compile(r"\bopens?\s+(?:an?\s+)?opportunit", re.IGNORECASE),
        re.compile(r"\bpresents?\s+(?:an?\s+)?opportunit", re.IGNORECASE),
        re.compile(r"\bcreates?\s+(?:an?\s+)?opportunit", re.IGNORECASE),
        re.compile(r"\bsuggesting\s+that\b", re.IGNORECASE),
        re.compile(r"\bindicating\s+that\b", re.IGNORECASE),
        re.compile(r"\bwe\s+should\b", re.IGNORECASE),
        re.compile(r"\bRRPS\s+should\b", re.IGNORECASE),
        re.compile(r"\bwe\s+recommend\b", re.IGNORECASE),
        re.compile(
            r"\bthis\s+(?:could|would|might)\s+(?:mean|signal|indicate)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bpositions?\s+(?:us|RRPS|MTU)\s+(?:to|for)\b", re.IGNORECASE),
    ]

    # Section header patterns for identifying fact vs analysis sections
    _FACT_SECTION_HEADERS = re.compile(
        r"(?m)^#{1,4}\s*(?:Key\s+(?:Developments?|Findings?|Facts?|Updates?)|"
        r"Latest\s+(?:News|Developments?|Updates?)|"
        r"Recent\s+(?:Developments?|News|Updates?)|"
        r"Market\s+(?:News|Developments?|Updates?)|"
        r"Summary|Overview|Background|Facts?)\s*$",
        re.IGNORECASE,
    )

    _ANALYSIS_SECTION_HEADERS = re.compile(
        r"(?m)^#{1,4}\s*(?:(?:Internal\s+)?Analysis|Implications?|"
        r"Strategic\s+(?:Analysis|Implications?|Assessment)|"
        r"RRPS\s+(?:Implications?|Perspective|Position)|"
        r"Assessment|What\s+This\s+Means|Opportunities?|"
        r"Recommended?\s+Actions?|Action\s+Items?|Next\s+Steps?)\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def detect_and_separate(cls, text: str) -> FactInferenceSplit:
        """
        Parse output, find inference language in fact sections,
        and move those sentences to the analysis bucket.
        """
        sections = cls._parse_sections(text)
        facts = []
        inferences = []
        violations = 0

        for section_type, section_header, section_body in sections:
            sentences = _split_sentences(section_body)

            for sentence in sentences:
                if not sentence.strip():
                    continue

                is_inference = cls._is_inference(sentence)

                if section_type == "fact" and is_inference:
                    # Violation: inference in fact section → move it
                    inferences.append(sentence.strip())
                    violations += 1
                elif section_type == "analysis" or is_inference:
                    inferences.append(sentence.strip())
                else:
                    facts.append(sentence.strip())

        return FactInferenceSplit(
            facts=facts, inferences=inferences, violations_moved=violations
        )

    @classmethod
    def _is_inference(cls, sentence: str) -> bool:
        """Check if a sentence contains inference language."""
        return any(p.search(sentence) for p in cls._INFERENCE_PATTERNS)

    @classmethod
    def _parse_sections(cls, text: str) -> List[Tuple[str, str, str]]:
        """
        Parse text into (type, header, body) tuples.

        type: "fact", "analysis", or "unknown"
        """
        # Split by markdown headings
        heading_pattern = re.compile(r"(?m)^(#{1,4}\s+.+)$")
        parts = heading_pattern.split(text)

        sections = []
        current_type = "unknown"
        current_header = ""

        for part in parts:
            if heading_pattern.match(part):
                # This is a heading — classify it
                if cls._FACT_SECTION_HEADERS.match(part.strip()):
                    current_type = "fact"
                elif cls._ANALYSIS_SECTION_HEADERS.match(part.strip()):
                    current_type = "analysis"
                else:
                    current_type = "unknown"
                current_header = part.strip()
            elif part.strip():
                sections.append((current_type, current_header, part))

        # If no sections found (no headings), treat entire text as fact section
        if not sections and text.strip():
            sections.append(("fact", "", text))

        return sections


# =============================================================================
# TASK 3 — Synthesis Breaker
# =============================================================================


class SynthesisBreaker:
    """
    Breaks compound fact statements into atomic facts.

    A compound fact mentions multiple entities or events joined by
    conjunctions, where the entities/events come from different sources.
    Each atomic fact stands alone with a single entity and event.
    """

    # Conjunction patterns that join distinct facts
    _CONJUNCTION_PATTERN = re.compile(
        r"\b(?:while|whereas|meanwhile|additionally|furthermore|"
        r"in\s+addition|at\s+the\s+same\s+time|conversely|"
        r"on\s+the\s+other\s+hand|similarly|likewise)\b",
        re.IGNORECASE,
    )

    # Simpler conjunctions only split when entities differ
    _SIMPLE_CONJUNCTION = re.compile(
        r",\s*and\s+|\.\s+And\s+|\bwhile\b|\bwhereas\b",
        re.IGNORECASE,
    )

    @classmethod
    def atomize(cls, facts: List[str]) -> List[AtomicFact]:
        """Split compound fact sentences into atomic facts."""
        atomic_facts = []

        for fact in facts:
            entities_in_fact = _find_all_entities(fact)

            if len(entities_in_fact) <= 1:
                # Single entity — already atomic
                entity = entities_in_fact[0] if entities_in_fact else ""
                atomic_facts.append(AtomicFact(text=fact, entity=entity))
                continue

            # Multiple entities — try to split
            if cls._CONJUNCTION_PATTERN.search(fact):
                sub_facts = cls._split_by_conjunction(fact)
                for sf in sub_facts:
                    entity = _find_all_entities(sf)
                    atomic_facts.append(
                        AtomicFact(
                            text=sf.strip(),
                            entity=entity[0] if entity else "",
                        )
                    )
            else:
                # Multiple entities but no splittable conjunction — keep as is
                atomic_facts.append(AtomicFact(text=fact, entity=entities_in_fact[0]))

        return atomic_facts

    @classmethod
    def _split_by_conjunction(cls, sentence: str) -> List[str]:
        """Split a compound sentence at conjunction boundaries."""
        # First try the strong conjunction patterns
        parts = cls._CONJUNCTION_PATTERN.split(sentence)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        # Fall back to simple split at ", and" or ". And"
        parts = cls._SIMPLE_CONJUNCTION.split(sentence)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        return [sentence]


# =============================================================================
# TASK 4 — Output Rewriter
# =============================================================================


class SpeculationStripper:
    """
    Deterministic removal of speculation language and uncited facts from LLM output.

    Runs on the ENTIRE output (not just analysis). Three operations:
    1. Strip speculation phrases from all sections
    2. Remove uncited bullets from Key Developments
    3. Remove Sources/References sections (UI renders separately)
    """

    # Speculation patterns — matched case-insensitively, applied everywhere
    _SPECULATION_PATTERNS = re.compile(
        r"(?i)"
        # "could/may/might + verb" speculation
        r"(?:(?:could|may|might)\s+(?:influence|drive|lead\s+to|affect|impact|"
        r"be\s+positioned|present|result\s+in|open|signal|create|enable|benefit))"
        # "presents/presenting/creates/represents" + opportunity/opportunities
        r"|(?:(?:presents?|presenting|creates?|creating|represents?|representing)"
        r"\s+(?:an?\s+|direct\s+|potential\s+|significant\s+|new\s+)*"
        r"(?:opportunit(?:y|ies)|challenge|threat|opening))"
        r"|(?:(?:potential|significant|new)\s+opportunit(?:y|ies)\s+(?:for|to|in))"
        r"|(?:(?:highlight|present|offer)s?\s+(?:potential\s+)?opportunit(?:y|ies))"
        r"|(?:opens?\s+(?:the\s+door|opportunities|a\s+(?:path|window)))"
        r"|(?:(?:this\s+)?suggests?\s+(?:a\s+)?(?:growing|potential|shift|trend|need))"
        r"|(?:(?:this\s+)?indicates?\s+(?:a\s+)?(?:growing|potential|shift|trend))"
        # "potentially/likely" hedging
        r"|(?:potentially\s+(?:impact|affect|influence|drive|disrupt))"
        r"|(?:is\s+(?:likely|well[- ]positioned|poised)\s+to)"
        r"|(?:stands?\s+to\s+(?:gain|benefit|lose))"
        r"|(?:would\s+benefit\s+from)"
        # "aligns/aligning" + any object
        r"|(?:align(?:s|ing)\s+with\s+(?:global|the\s+|China's|industry|regulatory|our\s+|RRPS))"
        # "highlights/underscores" fake-authority
        r"|(?:(?:this\s+)?highlights?\s+(?:the\s+)?(?:growing|need|importance|trend))"
        r"|(?:underscores?\s+(?:the\s+)?(?:importance|need|growing|trend))"
        # "strengthens/supports/reinforces our" self-congratulation
        r"|(?:(?:strengthens?|supports?|reinforces?|complements?)\s+(?:our|RRPS's?))"
        # "This development/move..." pattern
        r"|(?:This\s+(?:development|move|initiative|transition|trend)\s+"
        r"(?:could|may|might|is\s+(?:likely|expected)))"
        # "consistent with / in line with" hidden inference
        r"|(?:(?:consistent|in\s+line)\s+with\s+(?:our|the\s+|RRPS))"
        r"|(?:complementary\s+to\s+(?:our|RRPS))"
        # Filler conclusion patterns
        r"|(?:ensuring\s+compliance\s+and\s+competitiveness)"
        r"|(?:capitalize\s+on\s+(?:emerging\s+)?opportunities)"
        r"|(?:maintain\s+(?:market\s+)?(?:relevance|competitiveness))"
        # "represent a potential market" / "direct sales opportunity"
        r"|(?:represent\s+a\s+(?:potential|direct|significant)\s+(?:market|opportunity|sales))"
        r"|(?:a\s+direct\s+(?:sales\s+)?opportunity)"
        # "potential market for" / "positions us" / "could benefit"
        r"|(?:(?:a\s+)?potential\s+market\s+for)"
        r"|(?:positions?\s+(?:us|RRPS|our\s+))"
        r"|(?:could\s+benefit\s+(?:from|our|RRPS))"
        r"|(?:represents?\s+(?:an?\s+)?opportunity)"
        # "strategic need" / "need to develop" / "remain competitive"
        r"|(?:(?:a\s+)?strategic\s+need\s+to)"
        r"|(?:remain\s+competitive)"
    )

    # Citation reference pattern: [N] where N is a number
    _CITATION_REF = re.compile(r"\[\d+\]")

    # Key Developments heading
    _KEY_DEV_HEADING = re.compile(r"^#{1,4}\s*(?:Key\s+Developments?)", re.IGNORECASE)

    # Any heading (to detect section boundaries)
    _ANY_HEADING = re.compile(r"^#{1,4}\s+\S")

    # Sources/References section
    _SOURCES_SECTION = re.compile(
        r"(?m)^(?:#{1,4}\s*)?(?:Sources|References|Bibliography|Source\s*List)\s*:?\s*$"
    )

    @classmethod
    def strip(cls, text: str) -> str:
        """Full post-processing: strip speculation, uncited facts, sources section."""
        text = cls._strip_speculation(text)
        text = cls._strip_uncited_developments(text)
        text = cls._strip_sources_section(text)
        return text

    # Patterns that should cause entire bullet to be dropped
    _DROP_PATTERNS = re.compile(r"(?i)(?:\(unverified\)|\bunverified\b)")

    @classmethod
    def _strip_speculation(cls, text: str) -> str:
        """Drop entire lines containing speculation or unverified markers."""
        lines = text.split("\n")
        cleaned: list = []
        dropped = 0

        for line in lines:
            # Headings and blank lines always pass through
            if cls._ANY_HEADING.match(line) or not line.strip():
                cleaned.append(line)
                continue
            # Drop lines with speculation or unverified markers
            if cls._SPECULATION_PATTERNS.search(line) or cls._DROP_PATTERNS.search(
                line
            ):
                dropped += 1
                continue
            cleaned.append(line)

        if dropped:
            logger.info(f"SPECULATION_STRIPPER: dropped {dropped} lines")
        return "\n".join(cleaned)

    @classmethod
    def _strip_uncited_developments(cls, text: str) -> str:
        """Remove bullets without [N] citations from Key Developments section."""
        lines = text.split("\n")
        cleaned: list = []
        in_key_dev = False
        removed = 0

        for line in lines:
            if cls._KEY_DEV_HEADING.match(line):
                in_key_dev = True
                cleaned.append(line)
                continue
            if cls._ANY_HEADING.match(line) and in_key_dev:
                in_key_dev = False

            if in_key_dev and line.strip().startswith(("-", "*", "•")):
                if not cls._CITATION_REF.search(line):
                    removed += 1
                    continue  # Drop uncited bullet
            cleaned.append(line)

        if removed:
            logger.info(
                f"CITATION_ENFORCER: removed {removed} uncited bullets from Key Developments"
            )
        return "\n".join(cleaned)

    @classmethod
    def _strip_sources_section(cls, text: str) -> str:
        """Remove Sources/References section (UI renders sources separately)."""
        match = cls._SOURCES_SECTION.search(text)
        if match:
            text = text[: match.start()].rstrip()
            logger.info("SOURCES_STRIPPER: removed Sources/References section")
        return text


class OutputRewriter:
    """
    Reconstructs the LLM output into a structured format:

    Key Developments:
    - only verified atomic facts

    Internal Analysis:
    - all inferred content (moved from fact sections + original analysis)

    Deterministic restructuring. No LLM.
    """

    @classmethod
    def rewrite(
        cls,
        atomic_facts: List[AtomicFact],
        inferences: List[str],
        original_text: str,
    ) -> str:
        """Reconstruct output in the standard fact/analysis structure."""
        # If there are very few facts and inferences, don't force restructure
        if len(atomic_facts) <= 1 and len(inferences) <= 1:
            return original_text

        lines = []

        # Key Developments section
        if atomic_facts:
            pass  # Header removed: let original output structure speak for itself
            seen = set()
            for fact in atomic_facts:
                # Deduplicate
                norm = fact.text.strip().lower()
                if norm not in seen:
                    seen.add(norm)
                    # Format as bullet point if not already
                    text = fact.text.strip()
                    if not text.startswith(("-", "•", "*")):
                        text = f"- {text}"
                    lines.append(text)
            lines.append("")

        # Internal Analysis section (only if there are inferences)
        if inferences:
            lines.append("### Internal Analysis\n")
            seen = set()
            for inference in inferences:
                norm = inference.strip().lower()
                if norm not in seen:
                    seen.add(norm)
                    text = inference.strip()
                    if not text.startswith(("-", "•", "*")):
                        text = f"- {text}"
                    lines.append(text)
            lines.append("")

        result = "\n".join(lines)
        return result if result.strip() else original_text


# =============================================================================
# TASK 5 — Zero Tolerance Gate
# =============================================================================


class ZeroToleranceGate:
    """
    Final quality gate. If validation failures exceed thresholds,
    discard the entire output and return a safe fallback.

    Thresholds:
    - >50% of extracted claims removed → DISCARD
    - >3 contradicted claims → DISCARD
    - Output too short after enforcement (<30 chars of facts) → DISCARD
    """

    REMOVAL_THRESHOLD = 0.50  # 50% of claims removed
    MIN_CLAIMS_FOR_RATIO = 3  # Need at least 3 claims before ratio threshold applies
    CONTRADICTION_LIMIT = 3
    MIN_FACT_LENGTH = 30  # Characters of factual content minimum

    @classmethod
    def should_discard(
        cls,
        claims: List[ExtractedClaim],
        enforced_text: str,
        atomic_facts: List[AtomicFact],
    ) -> bool:
        """Determine if the output should be discarded entirely."""
        if not claims:
            return False  # No claims to validate — pass through

        removed = sum(
            1
            for c in claims
            if c.verdict in (ClaimVerdict.UNVERIFIABLE, ClaimVerdict.CONTRADICTED)
        )
        total = len(claims)

        # Threshold 1: Too many claims removed (only when enough claims to judge)
        # For 1-2 claims, individual removal is sufficient — don't discard the whole output
        if (
            total >= cls.MIN_CLAIMS_FOR_RATIO
            and (removed / total) > cls.REMOVAL_THRESHOLD
        ):
            logger.warning(
                f"ZERO_TOLERANCE: {removed}/{total} claims removed "
                f"({removed / total:.0%}) — exceeds {cls.REMOVAL_THRESHOLD:.0%} threshold"
            )
            return True

        # Threshold 2: Too many contradictions
        contradicted = sum(1 for c in claims if c.verdict == ClaimVerdict.CONTRADICTED)
        if contradicted > cls.CONTRADICTION_LIMIT:
            logger.warning(
                f"ZERO_TOLERANCE: {contradicted} contradicted claims — "
                f"exceeds limit of {cls.CONTRADICTION_LIMIT}"
            )
            return True

        # Threshold 3: Insufficient factual content remaining
        fact_text = " ".join(f.text for f in atomic_facts)
        if len(fact_text.strip()) < cls.MIN_FACT_LENGTH and total > 2:
            logger.warning(
                f"ZERO_TOLERANCE: Only {len(fact_text.strip())} chars of "
                f"factual content remain — below {cls.MIN_FACT_LENGTH} minimum"
            )
            return True

        return False

    FALLBACK_RESPONSE = (
        "Insufficient verified evidence to provide a reliable answer. "
        "The available information could not be confirmed against our "
        "verified sources. Please refine your query or ask about a specific "
        "topic where we have verified intelligence."
    )


# =============================================================================
# TASK 6 — Enforcement Telemetry
# =============================================================================


class EnforcementTelemetry:
    """
    Tracks all post-generation enforcement actions for observability.

    Uses QualityMetrics (bounded in-memory collection + structured logging).
    """

    @staticmethod
    def record(report: EnforcementReport, intent: str) -> None:
        """Record enforcement actions to QualityMetrics and structured logging."""
        try:
            from lead_to_cash.core.response_quality import QualityMetrics

            if report.was_modified:
                QualityMetrics.record(
                    event_type="post_generation_enforcement",
                    severity="WARNING" if report.claims_removed > 0 else "INFO",
                    intent=intent,
                    details=report.to_dict(),
                )

            if report.fallback_triggered:
                QualityMetrics.record(
                    event_type="post_generation_fallback",
                    severity="ERROR",
                    intent=intent,
                    details={
                        "claims_extracted": report.claims_extracted,
                        "claims_removed": report.claims_removed,
                        "claims_contradicted": report.claims_contradicted,
                    },
                )
        except ImportError:
            pass  # QualityMetrics unavailable — telemetry skipped

        # Always log the summary for audit trail
        logger.info(
            "post_generation_enforcement",
            extra={
                "enforcement_summary": report.summary,
                "enforcement_modified": report.was_modified,
                "enforcement_claims_removed": report.claims_removed,
                "enforcement_inferences_moved": report.fact_inference_violations,
                "enforcement_fallback": report.fallback_triggered,
                "intent": intent,
            },
        )


# =============================================================================
# Main Pipeline — OutputEnforcer
# =============================================================================


class OutputEnforcer:
    """
    Post-generation enforcement pipeline.

    Runs deterministic validation on every LLM output:
    1. Extract and validate factual claims
    2. Separate facts from inferences
    3. Break compound claims into atomics
    4. Rewrite in structured format (if modifications needed)
    5. Apply zero-tolerance gate
    6. Record telemetry

    Usage:
        result = OutputEnforcer.enforce(llm_output, intent)
        final_text = result.enforced_text
    """

    @classmethod
    def enforce(
        cls,
        text: str,
        intent: str,
        retrieved_evidence: Optional[str] = None,
    ) -> EnforcementReport:
        """
        Run the full post-generation enforcement pipeline.

        Args:
            text: Raw LLM output text
            intent: Query intent (for telemetry)
            retrieved_evidence: Optional raw evidence from tools (for context)

        Returns:
            EnforcementReport with enforced text and action details
        """
        if not text or len(text.strip()) < 10:
            return EnforcementReport(
                original_text=text,
                enforced_text=text,
                was_modified=False,
            )

        # ── Step 1: Extract and validate claims ──────────────────
        claims = DeclarativeClaimValidator.extract_claims(text)
        claims = DeclarativeClaimValidator.validate_claims(claims)
        enforced_text = DeclarativeClaimValidator.apply_verdicts(text, claims)

        claims_removed = sum(
            1
            for c in claims
            if c.verdict in (ClaimVerdict.UNVERIFIABLE, ClaimVerdict.CONTRADICTED)
        )
        claims_contradicted = sum(
            1 for c in claims if c.verdict == ClaimVerdict.CONTRADICTED
        )

        # ── Step 2: Separate facts from inferences ───────────────
        split = FactInferenceDetector.detect_and_separate(enforced_text)

        # ── Step 3: Break compound facts into atomics ────────────
        atomic_facts = SynthesisBreaker.atomize(split.facts)
        sentences_atomized = (
            len(atomic_facts) - len(split.facts)
            if len(atomic_facts) > len(split.facts)
            else 0
        )

        # ── Step 3.5: Strip speculation, uncited facts, sources ─────
        enforced_text = SpeculationStripper.strip(enforced_text)

        # Check if stripping left essentially-empty output (just headings)
        _content_only = re.sub(r"(?m)^#{1,4}\s.*$", "", enforced_text).strip()
        if len(_content_only) < 30:
            enforced_text = (
                "No strongly verified recent developments found. "
                "The available information could not meet citation "
                "and verification standards."
            )
            report = EnforcementReport(
                original_text=text,
                enforced_text=enforced_text,
                was_modified=True,
                claims_extracted=len(claims),
                claims_removed=claims_removed,
                claims_contradicted=claims_contradicted,
                fact_inference_violations=split.violations_moved,
                sentences_atomized=sentences_atomized,
                output_rewritten=False,
                fallback_triggered=True,
            )
            EnforcementTelemetry.record(report, intent)
            return report

        # ── Step 4: Check zero-tolerance gate ────────────────────
        if ZeroToleranceGate.should_discard(claims, enforced_text, atomic_facts):
            report = EnforcementReport(
                original_text=text,
                enforced_text=ZeroToleranceGate.FALLBACK_RESPONSE,
                was_modified=True,
                claims_extracted=len(claims),
                claims_removed=claims_removed,
                claims_contradicted=claims_contradicted,
                fact_inference_violations=split.violations_moved,
                sentences_atomized=sentences_atomized,
                output_rewritten=False,
                fallback_triggered=True,
            )
            EnforcementTelemetry.record(report, intent)
            return report

        # ── Step 5: Rewrite output if modifications were needed ──
        needs_rewrite = (
            claims_removed > 0 or split.violations_moved > 0 or sentences_atomized > 0
        )

        if needs_rewrite:
            enforced_text = OutputRewriter.rewrite(
                atomic_facts, split.inferences, enforced_text
            )
            output_rewritten = True
        else:
            output_rewritten = False

        was_modified = enforced_text != text

        # ── Step 6: Build report and record telemetry ────────────
        report = EnforcementReport(
            original_text=text,
            enforced_text=enforced_text,
            was_modified=was_modified,
            claims_extracted=len(claims),
            claims_removed=claims_removed,
            claims_contradicted=claims_contradicted,
            fact_inference_violations=split.violations_moved,
            sentences_atomized=sentences_atomized,
            output_rewritten=output_rewritten,
            fallback_triggered=False,
        )

        EnforcementTelemetry.record(report, intent)
        return report


# =============================================================================
# Utility Functions
# =============================================================================


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences, preserving bullet points as units."""
    # First split by bullet points (each bullet is a sentence)
    lines = text.split("\n")
    sentences = []
    current = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("-", "•", "*", "1.", "2.", "3.", "4.", "5.")):
            # Flush current buffer
            if current:
                sentences.extend(_sentence_split_text(" ".join(current)))
                current = []
            sentences.append(stripped)
        elif stripped:
            current.append(stripped)

    if current:
        sentences.extend(_sentence_split_text(" ".join(current)))

    return [s for s in sentences if s.strip()]


def _sentence_split_text(text: str) -> List[str]:
    """Split a block of text into sentences at period boundaries."""
    # Split on sentence-ending punctuation followed by space + capital
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def _find_competitor_entity(text_lower: str) -> Optional[str]:
    """Find the first competitor entity mentioned in lowercased text."""
    # Check multi-word entities first (longer matches first)
    multi_word = [
        "man energy solutions",
        "anglo belgian corporation",
        "siemens energy",
        "bergen engines",
        "volvo penta",
        "hd hyundai",
    ]
    for entity in multi_word:
        if entity in text_lower:
            return entity

    # Then single-word entities
    single_word = [
        "caterpillar",
        "cummins",
        "wartsila",
        "wärtsilä",
        "himsen",
        "hyundai",
        "daihatsu",
        "yanmar",
        "niigata",
        "bergen",
        "siemens",
    ]
    for entity in single_word:
        if entity in text_lower:
            return entity

    # Check abbreviated forms with word boundaries
    # "mak" before "cat" so "Cat MaK M32C" resolves to "mak" (specific brand)
    if re.search(r"\bmak\b", text_lower):
        return "mak"
    if re.search(r"\bcat\b", text_lower) and "caterpillar" not in text_lower:
        return "caterpillar"
    if re.search(r"\bman\b", text_lower) and "man energy" not in text_lower:
        # Only match "MAN" when it's clearly the company
        if any(
            kw in text_lower for kw in ["engine", "energy", "marine", "diesel", "power"]
        ):
            return "man"
    if re.search(r"\babc\b", text_lower):
        if any(kw in text_lower for kw in ["engine", "marine", "diesel", "belgian"]):
            return "anglo belgian corporation"

    return None


def _find_mtu_entity(text_lower: str) -> Optional[str]:
    """Find MTU/RRPS entity mention in lowercased text."""
    if "mtu" in text_lower or "rrps" in text_lower or "rolls-royce" in text_lower:
        return "mtu"
    return None


def _find_all_entities(text: str) -> List[str]:
    """Find all entity names (competitor + MTU) in text."""
    text_lower = text.lower()
    found = []

    # Check competitors
    comp = _find_competitor_entity(text_lower)
    if comp:
        found.append(comp)

    # Check for additional competitors beyond the first
    # (for compound detection)
    remaining = text_lower
    if comp:
        remaining = remaining.replace(comp, "", 1)
        comp2 = _find_competitor_entity(remaining)
        if comp2 and comp2 != comp:
            found.append(comp2)

    # Check MTU
    if _find_mtu_entity(text_lower):
        found.append("mtu")

    return found if found else [""]


def _parse_kw(value_str: str) -> Optional[int]:
    """Parse a kW value string like '1500 kW' into an integer."""
    match = re.search(r"(\d[\d,]*)", value_str)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_key_terms(text: str) -> Set[str]:
    """Extract significant terms from text for matching."""
    stop_words = {
        "the",
        "a",
        "an",
        "of",
        "in",
        "by",
        "and",
        "or",
        "is",
        "was",
        "to",
        "for",
        "from",
        "with",
        "on",
        "at",
    }
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return set(words) - stop_words
