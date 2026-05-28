"""
Signal Scorer for Competitor Intelligence

Calculates scores (0-100) for competitor intelligence signals based on:
- Signal type and content
- Geographic relevance (APAC, Singapore)
- Marine industry relevance
- Branding content penalties
"""

from dataclasses import dataclass
from typing import Optional

from lead_to_cash.services.competitor_intel.keyword_detector import (
    DetectionResult,
    get_keyword_detector,
)
from lead_to_cash.services.competitor_intel.signal_models import CompetitorSignal


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of score components."""

    # Positive factors
    contract_win_engines: int = 0  # +30
    new_vessel_project: int = 0  # +25
    offshore_project: int = 0  # +25
    product_launch_platform: int = 0  # +20
    product_launch_fuel: int = 0  # +20
    technology_fuel_transition: int = 0  # +15
    event_marketing: int = 0  # +10
    apac_relevance: int = 0  # +10
    singapore_relevance: int = 0  # +10

    # Negative factors (penalties)
    generic_branding_penalty: int = 0  # -10
    non_marine_penalty: int = 0  # -15

    # Calculated total
    total: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "contract_win_engines": self.contract_win_engines,
            "new_vessel_project": self.new_vessel_project,
            "offshore_project": self.offshore_project,
            "product_launch_platform": self.product_launch_platform,
            "product_launch_fuel": self.product_launch_fuel,
            "technology_fuel_transition": self.technology_fuel_transition,
            "event_marketing": self.event_marketing,
            "apac_relevance": self.apac_relevance,
            "singapore_relevance": self.singapore_relevance,
            "generic_branding_penalty": self.generic_branding_penalty,
            "non_marine_penalty": self.non_marine_penalty,
            "total": self.total,
        }


class SignalScorer:
    """
    Scoring algorithm for competitor intelligence signals.

    Scoring System (0-100):
    - +30: Contract win involving engines
    - +25: New vessel project
    - +25: Offshore project selection
    - +20: Product launch (new platform or fuel type)
    - +15: Technology POV related to fuel transition
    - +10: Event/marketing relevance
    - +10: APAC relevance
    - +10: Singapore relevance
    - -10: Generic branding content
    - -15: Non-marine content

    High-impact threshold: score >= 60
    """

    # Score constants
    SCORE_CONTRACT_WIN_ENGINES = 30
    SCORE_NEW_VESSEL_PROJECT = 25
    SCORE_OFFSHORE_PROJECT = 25
    SCORE_PRODUCT_LAUNCH_PLATFORM = 20
    SCORE_PRODUCT_LAUNCH_FUEL = 20
    SCORE_TECHNOLOGY_FUEL_TRANSITION = 15
    SCORE_EVENT_MARKETING = 10
    SCORE_APAC_RELEVANCE = 10
    SCORE_SINGAPORE_RELEVANCE = 10

    # Penalties
    PENALTY_GENERIC_BRANDING = -10
    PENALTY_NON_MARINE = -15

    # Thresholds
    HIGH_IMPACT_THRESHOLD = 60

    def __init__(self):
        """Initialize the scorer."""
        self._keyword_detector = get_keyword_detector()

    def calculate_score(
        self,
        signal: CompetitorSignal,
        detection_result: Optional[DetectionResult] = None,
    ) -> tuple[int, ScoreBreakdown]:
        """
        Calculate score for a competitor signal.

        Args:
            signal: The CompetitorSignal to score
            detection_result: Pre-computed keyword detection result (optional)

        Returns:
            Tuple of (final_score, score_breakdown)
        """
        breakdown = ScoreBreakdown()

        # Get keyword detection result if not provided
        if detection_result is None:
            content = f"{signal.headline} {signal.description} {signal.raw_content}"
            detection_result = self._keyword_detector.detect(content)

        # Score based on signal type and keywords
        self._score_contract_win(signal, detection_result, breakdown)
        self._score_vessel_project(signal, detection_result, breakdown)
        self._score_product_launch(signal, detection_result, breakdown)
        self._score_technology(signal, detection_result, breakdown)
        self._score_events(signal, detection_result, breakdown)
        self._score_geographic(signal, detection_result, breakdown)
        self._score_penalties(signal, detection_result, breakdown)

        # Calculate total (clamped to 0-100)
        total = (
            breakdown.contract_win_engines
            + breakdown.new_vessel_project
            + breakdown.offshore_project
            + breakdown.product_launch_platform
            + breakdown.product_launch_fuel
            + breakdown.technology_fuel_transition
            + breakdown.event_marketing
            + breakdown.apac_relevance
            + breakdown.singapore_relevance
            + breakdown.generic_branding_penalty
            + breakdown.non_marine_penalty
        )

        breakdown.total = max(0, min(100, total))

        return breakdown.total, breakdown

    def _score_contract_win(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score contract win signals."""
        if signal.signal_type == "CONTRACT_WIN" or detection.has_contract_signals():
            # Check if it involves engines (marine propulsion)
            content = f"{signal.headline} {signal.description}".lower()
            engine_keywords = [
                "engine",
                "propulsion",
                "genset",
                "generator",
                "power system",
                "mak",
                "cat marine",
                "cummins marine",
                "man engine",
            ]

            involves_engines = any(k in content for k in engine_keywords)

            if involves_engines or detection.is_marine_relevant():
                breakdown.contract_win_engines = self.SCORE_CONTRACT_WIN_ENGINES

    def _score_vessel_project(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score vessel and project signals."""
        content = f"{signal.headline} {signal.description}".lower()

        # Check for new vessel project
        if detection.vessel_keywords:
            newbuild_keywords = ["newbuild", "new build", "new vessel", "ordered"]
            is_newbuild = any(k in content for k in newbuild_keywords)

            if is_newbuild:
                breakdown.new_vessel_project = self.SCORE_NEW_VESSEL_PROJECT
            elif signal.vessel_type:
                # Has vessel type but not clearly a newbuild
                breakdown.new_vessel_project = self.SCORE_NEW_VESSEL_PROJECT // 2

        # Check for offshore project
        offshore_keywords = [
            "offshore",
            "fpso",
            "fso",
            "osv",
            "ahts",
            "psv",
            "drilling",
            "subsea",
            "oil & gas",
            "oil and gas",
        ]

        if any(k in content for k in offshore_keywords):
            # Don't double-count if already scored as contract win
            if breakdown.contract_win_engines == 0:
                breakdown.offshore_project = self.SCORE_OFFSHORE_PROJECT
            else:
                # Add partial offshore bonus
                breakdown.offshore_project = self.SCORE_OFFSHORE_PROJECT // 2

    def _score_product_launch(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score product launch signals."""
        if signal.signal_type == "PRODUCT_LAUNCH" or detection.product_keywords:
            content = f"{signal.headline} {signal.description}".lower()

            # Check for new platform
            platform_keywords = [
                "new platform",
                "new series",
                "next generation",
                "new model",
                "new engine",
            ]
            is_new_platform = any(k in content for k in platform_keywords)

            if is_new_platform:
                breakdown.product_launch_platform = self.SCORE_PRODUCT_LAUNCH_PLATFORM

            # Check for fuel-related launch
            if detection.has_fuel_transition():
                breakdown.product_launch_fuel = self.SCORE_PRODUCT_LAUNCH_FUEL

    def _score_technology(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score technology and fuel transition signals."""
        if signal.signal_type == "TECHNOLOGY_POV" or detection.technology_keywords:
            # Higher score for fuel transition content
            if detection.has_fuel_transition():
                breakdown.technology_fuel_transition = (
                    self.SCORE_TECHNOLOGY_FUEL_TRANSITION
                )
            else:
                # General technology content gets partial score
                breakdown.technology_fuel_transition = (
                    self.SCORE_TECHNOLOGY_FUEL_TRANSITION // 2
                )

    def _score_events(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score event and marketing signals."""
        if signal.signal_type == "EVENT_MARKETING" or detection.event_keywords:
            # Base event score
            breakdown.event_marketing = self.SCORE_EVENT_MARKETING

            # Bonus for marine-specific events
            marine_events = [
                "sea asia",
                "nor-shipping",
                "otc asia",
                "smo",
                "singapore maritime",
                "posidonia",
            ]
            content = f"{signal.headline} {signal.description}".lower()

            if any(event in content for event in marine_events):
                # Marine event bonus already captured in APAC/Singapore scoring
                pass

    def _score_geographic(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Score geographic relevance."""
        # APAC relevance
        if signal.is_apac or detection.is_apac_relevant():
            breakdown.apac_relevance = self.SCORE_APAC_RELEVANCE

        # Singapore relevance (cumulative with APAC)
        if signal.is_singapore or detection.is_singapore_relevant():
            breakdown.singapore_relevance = self.SCORE_SINGAPORE_RELEVANCE
            # Also ensure APAC is scored if Singapore is mentioned
            if breakdown.apac_relevance == 0:
                breakdown.apac_relevance = self.SCORE_APAC_RELEVANCE

    def _score_penalties(
        self,
        signal: CompetitorSignal,
        detection: DetectionResult,
        breakdown: ScoreBreakdown,
    ):
        """Apply penalty scores for low-value content."""
        # Generic branding penalty
        if detection.is_generic_branding():
            breakdown.generic_branding_penalty = self.PENALTY_GENERIC_BRANDING

        # Non-marine penalty
        if detection.non_marine_keywords and not detection.is_marine_relevant():
            # Only apply if clearly non-marine
            content = f"{signal.headline} {signal.description}".lower()
            marine_override = [
                "marine",
                "maritime",
                "vessel",
                "ship",
                "offshore",
                "propulsion",
            ]

            if not any(k in content for k in marine_override):
                breakdown.non_marine_penalty = self.PENALTY_NON_MARINE

    def is_high_impact(self, score: int) -> bool:
        """Check if a score qualifies as high-impact."""
        return score >= self.HIGH_IMPACT_THRESHOLD

    def score_and_update_signal(self, signal: CompetitorSignal) -> CompetitorSignal:
        """
        Calculate score and update signal in place.

        Args:
            signal: The signal to score

        Returns:
            The same signal with score and score_breakdown updated
        """
        content = f"{signal.headline} {signal.description} {signal.raw_content}"
        detection = self._keyword_detector.detect(content)

        # Calculate score
        score, breakdown = self.calculate_score(signal, detection)

        # Update signal
        signal.score = score
        signal.score_breakdown = breakdown.to_dict()

        # Update geographic flags if not set
        if not signal.is_apac and detection.is_apac_relevant():
            signal.is_apac = True
        if not signal.is_singapore and detection.is_singapore_relevant():
            signal.is_singapore = True

        # Update keywords matched
        signal.keywords_matched = detection.all_matches

        # Extract fuel type if not set
        if not signal.fuel_type:
            signal.fuel_type = self._keyword_detector.extract_fuel_type(content)

        # Extract vessel type if not set
        if not signal.vessel_type:
            signal.vessel_type = self._keyword_detector.extract_vessel_type(content)

        return signal


# Singleton instance
_scorer: Optional[SignalScorer] = None


def get_signal_scorer() -> SignalScorer:
    """Get or create the signal scorer singleton."""
    global _scorer
    if _scorer is None:
        _scorer = SignalScorer()
    return _scorer
