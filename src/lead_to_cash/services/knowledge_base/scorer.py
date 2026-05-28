"""
Marine Engine Knowledge Base - Relevance Scorer

Rule-based relevance scoring per requirements specification.
NO ML/LLM - deterministic scoring based on exact rules.

Scoring Rules:
- Technical: Engine model (+40), Tier-1 (+20), Power>10kW (+15), RPM<=750 (+10)
- Market: Offshore O&G (+30), Marine power gen (+25), Marine transport (+20), Land (+5)
- Commercial: New order (+30), Retrofit (+25), Launch (+20), Regulatory (+15), Financial (+10)

Classification Thresholds:
- HIGH_PRIORITY: >= 70
- MONITOR: 40-69
- IGNORE: < 40
"""

from dataclasses import dataclass, field
from typing import Optional

from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics
from lead_to_cash.services.knowledge_base.models import (
    ArticleScore,
    ManufacturerTier,
    MarketSegmentType,
    PowerClass,
    RelevanceClassification,
    ResolvedEntity,
    RPMClass,
)
from lead_to_cash.services.knowledge_base.tracing import trace_operation
from lead_to_cash.utils.logging import get_logger

# Use structured logger with correlation ID support
logger = get_logger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of scoring components."""

    # Technical scores
    engine_model_identified: int = 0
    tier_1_manufacturer: int = 0
    power_over_10000kw: int = 0
    rpm_lte_750: int = 0

    # Market scores
    offshore_oil_gas: int = 0
    marine_power_generation: int = 0
    marine_transportation: int = 0
    land_power_plant: int = 0

    # Commercial scores
    new_vessel_order: int = 0
    fleet_retrofit: int = 0
    product_launch: int = 0
    regulatory_change: int = 0
    financial_results: int = 0

    @property
    def technical_total(self) -> int:
        """Sum of technical scores."""
        return (
            self.engine_model_identified
            + self.tier_1_manufacturer
            + self.power_over_10000kw
            + self.rpm_lte_750
        )

    @property
    def market_total(self) -> int:
        """Sum of market scores."""
        return (
            self.offshore_oil_gas
            + self.marine_power_generation
            + self.marine_transportation
            + self.land_power_plant
        )

    @property
    def commercial_total(self) -> int:
        """Sum of commercial scores."""
        return (
            self.new_vessel_order
            + self.fleet_retrofit
            + self.product_launch
            + self.regulatory_change
            + self.financial_results
        )

    @property
    def total(self) -> int:
        """Total score."""
        return self.technical_total + self.market_total + self.commercial_total

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "technical": {
                "engine_model_identified": self.engine_model_identified,
                "tier_1_manufacturer": self.tier_1_manufacturer,
                "power_over_10000kw": self.power_over_10000kw,
                "rpm_lte_750": self.rpm_lte_750,
                "subtotal": self.technical_total,
            },
            "market": {
                "offshore_oil_gas": self.offshore_oil_gas,
                "marine_power_generation": self.marine_power_generation,
                "marine_transportation": self.marine_transportation,
                "land_power_plant": self.land_power_plant,
                "subtotal": self.market_total,
            },
            "commercial": {
                "new_vessel_order": self.new_vessel_order,
                "fleet_retrofit": self.fleet_retrofit,
                "product_launch": self.product_launch,
                "regulatory_change": self.regulatory_change,
                "financial_results": self.financial_results,
                "subtotal": self.commercial_total,
            },
            "total": self.total,
        }


@dataclass
class ScoringInput:
    """Input for scoring an article."""

    article_id: str
    article_content: str

    # Resolved entities from KB
    entities: list[ResolvedEntity] = field(default_factory=list)

    # Detected market segments
    market_segments: list[MarketSegmentType] = field(default_factory=list)

    # Detected commercial signals (keywords)
    commercial_signals: list[str] = field(default_factory=list)


class RelevanceScorer:
    """
    Rule-based relevance scorer for marine engine articles.

    Implements exact scoring rules from requirements:

    Technical Relevance:
    - Engine model identified: +40
    - Manufacturer is Tier-1: +20
    - Power > 10,000 kW: +15
    - RPM ≤ 750: +10

    Market Relevance:
    - Offshore oil & gas: +30
    - Marine power generation: +25
    - Marine transportation: +20
    - Land power plant: +5

    Commercial Signals:
    - New vessel order or contract: +30
    - Fleet retrofit / repowering: +25
    - Product launch: +20
    - Regulatory change: +15
    - Financial results: +10

    Classification:
    - Score ≥ 70 → HIGH PRIORITY
    - Score 40–69 → MONITOR
    - Score < 40 → IGNORE

    Usage:
        scorer = RelevanceScorer()

        # Score from input
        input = ScoringInput(
            article_id="123",
            article_content="...",
            entities=[...],
            market_segments=[MarketSegmentType.OFFSHORE_OIL_GAS],
            commercial_signals=["new order", "contract"]
        )
        score = scorer.score(input)

        # Get classification
        classification = score.get_classification()
    """

    # Technical scoring rules
    SCORE_ENGINE_MODEL_IDENTIFIED = 40
    SCORE_TIER_1_MANUFACTURER = 20
    SCORE_POWER_OVER_10000KW = 15
    SCORE_RPM_LTE_750 = 10

    # Market scoring rules
    SCORE_OFFSHORE_OIL_GAS = 30
    SCORE_MARINE_POWER_GENERATION = 25
    SCORE_MARINE_TRANSPORTATION = 20
    SCORE_LAND_POWER_PLANT = 5

    # Commercial scoring rules
    SCORE_NEW_VESSEL_ORDER = 30
    SCORE_FLEET_RETROFIT = 25
    SCORE_PRODUCT_LAUNCH = 20
    SCORE_REGULATORY_CHANGE = 15
    SCORE_FINANCIAL_RESULTS = 10

    # Classification thresholds
    THRESHOLD_HIGH_PRIORITY = 70
    THRESHOLD_MONITOR = 40

    # Commercial signal keywords - MUST be specific phrases to avoid false positives
    # Keywords are checked as exact substrings in lowercased content
    SIGNAL_KEYWORDS = {
        "new_vessel_order": [
            # Specific contract/order phrases
            "vessel order",
            "newbuild contract",
            "newbuilding contract",
            "shipbuilding contract",
            "awarded contract",
            "contract awarded",
            "wins contract",
            "won contract",
            "contract win",
            "secures contract",
            "secured contract",
            "orders new",
            "ordered new",
            "placed order",
            "new vessel order",
            "ferry order",
            "tanker order",
            "cargo ship order",
        ],
        "fleet_retrofit": [
            # Specific retrofit/repower phrases
            "retrofit project",
            "repowering project",
            "engine replacement",
            "engine retrofit",
            "fleet modernization",
            "fleet upgrade",
            "vessel conversion",
            "lng conversion",
            "dual-fuel conversion",
            "engine overhaul",
            "life extension program",
            "mid-life upgrade",
        ],
        "product_launch": [
            # Specific product announcement phrases
            "launches new engine",
            "introduces new engine",
            "unveils new engine",
            "announces new engine",
            "new engine model",
            "new engine series",
            "product launch",
            "engine launch",
            "debuts new",
            "releases new engine",
            "new propulsion system",
        ],
        "regulatory_change": [
            # Specific regulatory phrases
            "imo regulation",
            "imo tier",
            "tier iii",
            "emission regulation",
            "emission standard",
            "eexi compliance",
            "cii rating",
            "sulphur cap",
            "sox emission",
            "nox emission",
            "decarbonization requirement",
            "environmental regulation",
            "maritime regulation",
        ],
        "financial_results": [
            # Specific financial phrases
            "quarterly results",
            "annual results",
            "financial results",
            "revenue growth",
            "profit growth",
            "earnings report",
            "annual report",
            "fiscal year",
            "order backlog",
            "order intake",
        ],
    }

    @trace_operation(
        "score_article",
        lambda input, **_: {"article_id": input.article_id if input else ""},
    )
    def score(self, input: ScoringInput) -> ArticleScore:
        """
        Score an article based on resolved entities and detected signals.

        Args:
            input: ScoringInput with entities, market segments, and signals

        Returns:
            ArticleScore with breakdown and classification
        """
        breakdown = ScoreBreakdown()

        # Score technical relevance
        self._score_technical(input.entities, breakdown)

        # Score market relevance
        self._score_market(input.market_segments, breakdown)

        # Score commercial signals
        self._score_commercial(
            input.commercial_signals, input.article_content, breakdown
        )

        # Build explanation
        explanation = self._build_explanation(breakdown)

        # Create ArticleScore
        import json
        import uuid
        from datetime import datetime, timezone

        classification = RelevanceClassification.from_score(breakdown.total)
        score = ArticleScore(
            id=str(uuid.uuid4()),
            article_id=input.article_id,
            technical_score=float(breakdown.technical_total),
            market_score=float(breakdown.market_total),
            commercial_score=float(breakdown.commercial_total),
            total_score=float(breakdown.total),
            classification=classification.value,
            score_breakdown=json.dumps(breakdown.to_dict()),
            scoring_model_version="v1",
            scored_at=datetime.now(timezone.utc),
            score_explanation=explanation,
        )

        # Record metrics
        get_kb_metrics().record_article_scored(classification.value)

        return score

    def _score_technical(
        self, entities: list[ResolvedEntity], breakdown: ScoreBreakdown
    ) -> None:
        """Score technical relevance from resolved entities."""
        has_engine_model = False
        has_tier_1 = False
        has_high_power = False
        has_low_rpm = False

        for entity in entities:
            # Check for engine model
            if entity.entity_type == "engine_model":
                has_engine_model = True

                # Check power class
                if entity.power_class in (PowerClass.HIGH, PowerClass.ULTRA_HIGH):
                    has_high_power = True

                # Check RPM class (medium speed <= 750 is target)
                if entity.rpm_class == RPMClass.MEDIUM_SPEED:
                    has_low_rpm = True

            # Check for Tier-1 manufacturer
            if entity.manufacturer_tier == ManufacturerTier.TIER_1:
                has_tier_1 = True

        if has_engine_model:
            breakdown.engine_model_identified = self.SCORE_ENGINE_MODEL_IDENTIFIED

        if has_tier_1:
            breakdown.tier_1_manufacturer = self.SCORE_TIER_1_MANUFACTURER

        if has_high_power:
            breakdown.power_over_10000kw = self.SCORE_POWER_OVER_10000KW

        if has_low_rpm:
            breakdown.rpm_lte_750 = self.SCORE_RPM_LTE_750

    def _score_market(
        self, market_segments: list[MarketSegmentType], breakdown: ScoreBreakdown
    ) -> None:
        """
        Score market relevance from detected segments.

        Uses DIMINISHING RETURNS formula to balance:
        - Rewarding multiple legitimate market segments
        - Preventing score inflation from overlapping segments

        Formula:
        - First (highest) segment: 100% of score
        - Second segment: 50% of score (capped at 15)
        - Third+ segments: Ignored to prevent inflation

        This ensures:
        - Single segment articles score fairly (e.g., offshore = 30)
        - Multi-segment articles get a boost (e.g., offshore + power gen = 30 + 12.5 = 42.5)
        - But inflation is capped (max ~45 for market vs theoretical 80 if all summed)

        Priority order:
        1. Offshore O&G (+30) - highest priority
        2. Marine Power Generation (+25)
        3. Marine Transportation (+20)
        4. Land Power Plant (+5) - lowest priority
        """
        # Collect unique applicable scores (deduplicate FPSO -> offshore)
        segment_scores = {}

        if MarketSegmentType.OFFSHORE_OIL_GAS in market_segments:
            segment_scores["offshore_oil_gas"] = self.SCORE_OFFSHORE_OIL_GAS

        if MarketSegmentType.FPSO_OFFSHORE_PRODUCTION in market_segments:
            # FPSO is offshore oil & gas - use same score bucket (won't duplicate)
            segment_scores["offshore_oil_gas"] = self.SCORE_OFFSHORE_OIL_GAS

        if MarketSegmentType.MARINE_POWER_GENERATION in market_segments:
            segment_scores["marine_power_generation"] = (
                self.SCORE_MARINE_POWER_GENERATION
            )

        if MarketSegmentType.MARINE_TRANSPORTATION in market_segments:
            segment_scores["marine_transportation"] = self.SCORE_MARINE_TRANSPORTATION

        if MarketSegmentType.LAND_POWER_PLANT in market_segments:
            segment_scores["land_power_plant"] = self.SCORE_LAND_POWER_PLANT

        if not segment_scores:
            return

        # Sort by score descending
        sorted_segments = sorted(
            segment_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Apply diminishing returns:
        # - First segment: 100%
        # - Second segment: 50% (capped at 15)
        for i, (segment, score) in enumerate(sorted_segments):
            if i == 0:
                # First segment: full score
                applied_score = score
            elif i == 1:
                # Second segment: 50% with cap of 15
                applied_score = min(int(score * 0.5), 15)
            else:
                # Third+ segments: ignored to prevent inflation
                break

            if segment == "offshore_oil_gas":
                breakdown.offshore_oil_gas = applied_score
            elif segment == "marine_power_generation":
                breakdown.marine_power_generation = applied_score
            elif segment == "marine_transportation":
                breakdown.marine_transportation = applied_score
            elif segment == "land_power_plant":
                breakdown.land_power_plant = applied_score

    def _score_commercial(
        self,
        signals: list[str],
        content: str,
        breakdown: ScoreBreakdown,
    ) -> None:
        """Score commercial signals from detected keywords and content."""
        # Check for explicit signals passed in
        signal_set = set(s.lower() for s in signals)

        # Also detect signals from content
        detected_signals = self.detect_commercial_signals(content)
        signal_set.update(detected_signals)

        # Apply scores for each signal type
        if any(s in signal_set for s in ["new_vessel_order", "new order", "contract"]):
            breakdown.new_vessel_order = self.SCORE_NEW_VESSEL_ORDER

        if any(s in signal_set for s in ["fleet_retrofit", "retrofit", "repowering"]):
            breakdown.fleet_retrofit = self.SCORE_FLEET_RETROFIT

        if any(s in signal_set for s in ["product_launch", "launch", "new product"]):
            breakdown.product_launch = self.SCORE_PRODUCT_LAUNCH

        if any(s in signal_set for s in ["regulatory_change", "regulatory", "imo"]):
            breakdown.regulatory_change = self.SCORE_REGULATORY_CHANGE

        if any(s in signal_set for s in ["financial_results", "revenue", "earnings"]):
            breakdown.financial_results = self.SCORE_FINANCIAL_RESULTS

    def detect_commercial_signals(self, content: str) -> list[str]:
        """
        Detect commercial signals from article content.

        Args:
            content: Article text

        Returns:
            List of detected signal types
        """
        content_lower = content.lower()
        detected = []

        for signal_type, keywords in self.SIGNAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    detected.append(signal_type)
                    break  # Only add each signal type once

        return detected

    def detect_market_segments(self, content: str) -> list[MarketSegmentType]:
        """
        Detect market segments from article content.

        Args:
            content: Article text

        Returns:
            List of detected market segments
        """
        content_lower = content.lower()
        segments = []

        # Offshore oil & gas keywords
        offshore_keywords = [
            "offshore",
            "oil and gas",
            "oil & gas",
            "drilling",
            "platform",
            "subsea",
            "fpso",
            "flng",
            "fso",
        ]
        if any(kw in content_lower for kw in offshore_keywords):
            segments.append(MarketSegmentType.OFFSHORE_OIL_GAS)

        # FPSO specific
        fpso_keywords = ["fpso", "floating production", "offshore production"]
        if any(kw in content_lower for kw in fpso_keywords):
            segments.append(MarketSegmentType.FPSO_OFFSHORE_PRODUCTION)

        # Marine power generation
        power_gen_keywords = [
            "power generation",
            "power plant",
            "genset",
            "generator set",
            "auxiliary power",
        ]
        if any(kw in content_lower for kw in power_gen_keywords):
            segments.append(MarketSegmentType.MARINE_POWER_GENERATION)

        # Marine transportation
        transport_keywords = [
            "ferry",
            "cargo",
            "container",
            "tanker",
            "bulk carrier",
            "roro",
            "cruise",
            "passenger",
            "vessel",
            "ship",
            "propulsion",
        ]
        if any(kw in content_lower for kw in transport_keywords):
            segments.append(MarketSegmentType.MARINE_TRANSPORTATION)

        # Land power (lower priority)
        land_keywords = ["land-based", "stationary", "onshore power"]
        if any(kw in content_lower for kw in land_keywords):
            segments.append(MarketSegmentType.LAND_POWER_PLANT)

        return segments

    def _build_explanation(self, breakdown: ScoreBreakdown) -> str:
        """Build human-readable explanation of the score."""
        parts = []

        # Technical
        if breakdown.technical_total > 0:
            tech_parts = []
            if breakdown.engine_model_identified:
                tech_parts.append(
                    f"engine model identified (+{self.SCORE_ENGINE_MODEL_IDENTIFIED})"
                )
            if breakdown.tier_1_manufacturer:
                tech_parts.append(
                    f"Tier-1 manufacturer (+{self.SCORE_TIER_1_MANUFACTURER})"
                )
            if breakdown.power_over_10000kw:
                tech_parts.append(
                    f"high power >10MW (+{self.SCORE_POWER_OVER_10000KW})"
                )
            if breakdown.rpm_lte_750:
                tech_parts.append(f"medium-speed RPM (+{self.SCORE_RPM_LTE_750})")
            parts.append(
                f"Technical ({breakdown.technical_total}): {', '.join(tech_parts)}"
            )

        # Market
        if breakdown.market_total > 0:
            market_parts = []
            if breakdown.offshore_oil_gas:
                market_parts.append(f"offshore O&G (+{self.SCORE_OFFSHORE_OIL_GAS})")
            if breakdown.marine_power_generation:
                market_parts.append(
                    f"marine power gen (+{self.SCORE_MARINE_POWER_GENERATION})"
                )
            if breakdown.marine_transportation:
                market_parts.append(
                    f"marine transport (+{self.SCORE_MARINE_TRANSPORTATION})"
                )
            if breakdown.land_power_plant:
                market_parts.append(f"land power (+{self.SCORE_LAND_POWER_PLANT})")
            parts.append(
                f"Market ({breakdown.market_total}): {', '.join(market_parts)}"
            )

        # Commercial
        if breakdown.commercial_total > 0:
            comm_parts = []
            if breakdown.new_vessel_order:
                comm_parts.append(f"new order (+{self.SCORE_NEW_VESSEL_ORDER})")
            if breakdown.fleet_retrofit:
                comm_parts.append(f"retrofit (+{self.SCORE_FLEET_RETROFIT})")
            if breakdown.product_launch:
                comm_parts.append(f"product launch (+{self.SCORE_PRODUCT_LAUNCH})")
            if breakdown.regulatory_change:
                comm_parts.append(f"regulatory (+{self.SCORE_REGULATORY_CHANGE})")
            if breakdown.financial_results:
                comm_parts.append(f"financial (+{self.SCORE_FINANCIAL_RESULTS})")
            parts.append(
                f"Commercial ({breakdown.commercial_total}): {', '.join(comm_parts)}"
            )

        # Classification
        classification = RelevanceClassification.from_score(breakdown.total)
        parts.append(f"Total: {breakdown.total} -> {classification.value.upper()}")

        return "; ".join(parts)

    def classify(self, score: float) -> RelevanceClassification:
        """
        Classify score into priority level.

        Args:
            score: Total relevance score

        Returns:
            RelevanceClassification enum
        """
        return RelevanceClassification.from_score(score)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_scorer: Optional[RelevanceScorer] = None


def get_relevance_scorer() -> RelevanceScorer:
    """Get singleton relevance scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = RelevanceScorer()
    return _scorer
