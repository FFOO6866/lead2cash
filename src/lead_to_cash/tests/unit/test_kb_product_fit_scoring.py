"""
Unit Tests for Knowledge Base Product Fit Scoring

Tests the deterministic algorithm for scoring engine-to-customer-requirement fit.
NO MOCKING - uses real dataclasses from unified_models.py.

Scoring Components (default weights):
- Power Match (30%): How well engine power matches requirement
- Application Fit (25%): Suitability for vessel type/application
- Duty Class Match (20%): Operating profile alignment
- Fuel Compatibility (10%): Supports required fuel types
- Emission Compliance (10%): Meets emission tier requirements
- Physical Constraints (5%): Weight/size within limits

Recommendation Thresholds:
- STRONG_FIT: 90-100%
- GOOD_FIT: 75-89%
- ACCEPTABLE: 60-74%
- MARGINAL: 40-59%
- NOT_SUITABLE: <40%
"""

import uuid

import pytest

from lead_to_cash.services.knowledge_base.product_fit_scoring import (
    APPLICATION_SUITABILITY,
    ENGINE_SERIES_APPLICATIONS,
    _smooth_score,
    score_duty_class_match,
    score_emission_compliance,
    score_power_match,
)
from lead_to_cash.services.knowledge_base.unified_models import (
    CustomerRequirement,
    DutyClass,
    EngineRating,
    FitRecommendation,
    HarmonizedDutyClass,
)

# =============================================================================
# FIXTURES
# =============================================================================


def make_engine_rating(
    power_kw: float = 4000.0,
    rpm: int = 1800,
    duty_class: DutyClass = DutyClass.MEDIUM_DUTY,
    emission_tier: str = None,
    dry_weight_kg: float = None,
) -> EngineRating:
    """Factory for creating engine ratings with defaults."""
    return EngineRating(
        id=str(uuid.uuid4()),
        engine_model_id=str(uuid.uuid4()),
        rating_designation="M96",
        duty_class=duty_class,
        power_kw=power_kw,
        rpm=rpm,
        emission_tier=emission_tier,
        dry_weight_kg=dry_weight_kg,
    )


def make_customer_requirement(
    power_required_kw: float = 4000.0,
    power_tolerance_pct: float = 15.0,
    duty_class_required: DutyClass = None,
    annual_operating_hours: int = None,
    emission_tier_required: str = None,
    vessel_type: str = None,
    max_engine_weight_kg: float = None,
) -> CustomerRequirement:
    """Factory for creating customer requirements with defaults."""
    return CustomerRequirement(
        id=str(uuid.uuid4()),
        customer_name="Test Customer",
        power_required_kw=power_required_kw,
        power_tolerance_pct=power_tolerance_pct,
        duty_class_required=duty_class_required,
        annual_operating_hours=annual_operating_hours,
        emission_tier_required=emission_tier_required,
        vessel_type=vessel_type,
        max_engine_weight_kg=max_engine_weight_kg,
    )


# =============================================================================
# SMOOTH SCORE TESTS
# =============================================================================


class TestSmoothScore:
    """Tests for _smooth_score interpolation function."""

    def test_exact_breakpoint_values(self):
        """Test score at exact breakpoint values."""
        breakpoints = [
            (0, 100),
            (10, 80),
            (20, 60),
            (50, 0),
        ]

        assert _smooth_score(0, breakpoints) == 100
        assert _smooth_score(10, breakpoints) == 80
        assert _smooth_score(20, breakpoints) == 60
        assert _smooth_score(50, breakpoints) == 0

    def test_linear_interpolation_midpoints(self):
        """Test linear interpolation between breakpoints."""
        breakpoints = [
            (0, 100),
            (10, 80),
            (20, 60),
        ]

        # Midpoint between (0, 100) and (10, 80) is (5, 90)
        assert _smooth_score(5, breakpoints) == 90.0

        # Midpoint between (10, 80) and (20, 60) is (15, 70)
        assert _smooth_score(15, breakpoints) == 70.0

    def test_below_first_breakpoint(self):
        """Test score below first breakpoint returns first score."""
        breakpoints = [
            (5, 95),
            (10, 80),
            (20, 60),
        ]

        # Below first threshold should return first score
        assert _smooth_score(0, breakpoints) == 95
        assert _smooth_score(3, breakpoints) == 95

    def test_above_last_breakpoint(self):
        """Test score above last breakpoint returns last score."""
        breakpoints = [
            (0, 100),
            (10, 80),
            (20, 60),
        ]

        # Above last threshold should return last score
        assert _smooth_score(25, breakpoints) == 60
        assert _smooth_score(100, breakpoints) == 60

    def test_single_breakpoint(self):
        """Test with single breakpoint."""
        breakpoints = [(10, 50)]

        assert _smooth_score(0, breakpoints) == 50
        assert _smooth_score(10, breakpoints) == 50
        assert _smooth_score(100, breakpoints) == 50


# =============================================================================
# POWER MATCH SCORING TESTS
# =============================================================================


class TestPowerMatchScoring:
    """Tests for score_power_match function."""

    def test_exact_power_match(self):
        """Exact power match should score 100."""
        requirement = make_customer_requirement(power_required_kw=4000)
        rating = make_engine_rating(power_kw=4000)

        score, detail = score_power_match(requirement, rating)

        assert score == 100.0
        assert "matches" in detail.lower()

    def test_within_tolerance(self):
        """Power within tolerance should score 100."""
        requirement = make_customer_requirement(
            power_required_kw=4000, power_tolerance_pct=15.0
        )
        rating = make_engine_rating(power_kw=4500)  # +12.5%

        score, detail = score_power_match(requirement, rating)

        assert score == 100.0
        assert "matches" in detail.lower()

    def test_slightly_overpowered(self):
        """Slightly overpowered (20%) should have mild penalty."""
        requirement = make_customer_requirement(
            power_required_kw=4000, power_tolerance_pct=15.0
        )
        rating = make_engine_rating(power_kw=4800)  # +20%

        score, detail = score_power_match(requirement, rating)

        # Should be between 90-100 (slight penalty)
        assert 85 <= score <= 100
        assert "over" in detail.lower() or "matches" in detail.lower()

    def test_significantly_overpowered(self):
        """Significantly overpowered (50%) should have noticeable penalty."""
        requirement = make_customer_requirement(power_required_kw=4000)
        rating = make_engine_rating(power_kw=6000)  # +50%

        score, detail = score_power_match(requirement, rating)

        # Should be around 55 based on breakpoints
        assert 50 <= score <= 60
        assert "overpowered" in detail.lower()

    def test_underpowered_steep_penalty(self):
        """Underpowered should have steeper penalty than overpowered."""
        requirement = make_customer_requirement(
            power_required_kw=4000, power_tolerance_pct=15.0
        )
        rating = make_engine_rating(power_kw=3000)  # -25%

        score, detail = score_power_match(requirement, rating)

        # Underpowered has steeper penalty - should be around 70
        assert 65 <= score <= 75
        assert "underpowered" in detail.lower()

    def test_severely_underpowered(self):
        """Severely underpowered (-50%) should score very low."""
        requirement = make_customer_requirement(power_required_kw=4000)
        rating = make_engine_rating(power_kw=2000)  # -50%

        score, detail = score_power_match(requirement, rating)

        # Should be around 20 based on breakpoints
        assert score <= 25
        assert "underpowered" in detail.lower()

    def test_no_power_requirement(self):
        """No power requirement should return neutral score."""
        requirement = make_customer_requirement(power_required_kw=0)
        rating = make_engine_rating(power_kw=4000)

        score, detail = score_power_match(requirement, rating)

        assert score == 50.0
        assert "no power requirement" in detail.lower()

    def test_custom_tolerance(self):
        """Custom tolerance percentage should be respected."""
        requirement = make_customer_requirement(
            power_required_kw=4000, power_tolerance_pct=5.0
        )
        rating = make_engine_rating(power_kw=4200)  # +5% (within tolerance)

        score, detail = score_power_match(requirement, rating)

        assert score == 100.0

    def test_overpowered_less_severe_than_underpowered(self):
        """Same percentage overpowered should be better than underpowered."""
        requirement = make_customer_requirement(power_required_kw=4000)

        # +30% overpowered
        rating_over = make_engine_rating(power_kw=5200)
        score_over, _ = score_power_match(requirement, rating_over)

        # -30% underpowered
        rating_under = make_engine_rating(power_kw=2800)
        score_under, _ = score_power_match(requirement, rating_under)

        # Overpowered should be scored higher (less severe penalty)
        assert score_over > score_under


# =============================================================================
# DUTY CLASS MATCH SCORING TESTS
# =============================================================================


class TestDutyClassMatchScoring:
    """Tests for score_duty_class_match function."""

    def test_exact_duty_match(self):
        """Exact duty class match should score 100."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.MEDIUM_DUTY
        )
        rating = make_engine_rating(duty_class=DutyClass.MEDIUM_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 100.0
        assert "matches" in detail.lower()

    def test_heavier_duty_engine(self):
        """Engine one class heavier should score 80."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.MEDIUM_DUTY
        )
        rating = make_engine_rating(duty_class=DutyClass.HEAVY_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 80.0
        assert "heavier duty" in detail.lower()

    def test_lighter_duty_engine(self):
        """Engine one class lighter should score 50."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.MEDIUM_DUTY
        )
        rating = make_engine_rating(duty_class=DutyClass.LIGHT_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 50.0
        assert "lighter duty" in detail.lower()
        assert "overworked" in detail.lower()

    def test_much_heavier_duty(self):
        """Engine two classes heavier should score 70."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.LIGHT_DUTY
        )
        rating = make_engine_rating(duty_class=DutyClass.HEAVY_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 70.0
        assert "much heavier" in detail.lower()

    def test_much_lighter_duty(self):
        """Engine two classes lighter should score 30."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.HEAVY_DUTY
        )
        rating = make_engine_rating(duty_class=DutyClass.LIGHT_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 30.0
        assert "much lighter" in detail.lower() or "risk" in detail.lower()

    def test_extreme_mismatch(self):
        """Extreme duty mismatch (3+ classes) should score 10."""
        requirement = make_customer_requirement(
            duty_class_required=DutyClass.CONTINUOUS
        )
        rating = make_engine_rating(duty_class=DutyClass.PLEASURE)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 10.0
        assert "does not match" in detail.lower() or "mismatch" in detail.lower()

    def test_no_duty_requirement(self):
        """No duty requirement should return neutral score."""
        requirement = make_customer_requirement(duty_class_required=None)
        rating = make_engine_rating(duty_class=DutyClass.MEDIUM_DUTY)

        score, detail = score_duty_class_match(requirement, rating)

        assert score == 70.0
        assert "no duty class requirement" in detail.lower()

    def test_infer_duty_from_hours(self):
        """Should infer duty class from annual operating hours."""
        # 5000+ hours = Continuous
        requirement = make_customer_requirement(
            duty_class_required=None, annual_operating_hours=6000
        )
        rating = make_engine_rating(duty_class=DutyClass.CONTINUOUS)

        score, detail = score_duty_class_match(requirement, rating)

        # Should match inferred continuous duty
        assert score == 100.0


# =============================================================================
# DUTY CLASS ENUM TESTS
# =============================================================================


class TestDutyClassEnum:
    """Tests for DutyClass enum methods."""

    def test_from_annual_hours_continuous(self):
        """5000+ hours should be continuous duty."""
        assert DutyClass.from_annual_hours(5000) == DutyClass.CONTINUOUS
        assert DutyClass.from_annual_hours(8000) == DutyClass.CONTINUOUS

    def test_from_annual_hours_heavy_duty(self):
        """3000-4999 hours should be heavy duty."""
        assert DutyClass.from_annual_hours(3000) == DutyClass.HEAVY_DUTY
        assert DutyClass.from_annual_hours(4500) == DutyClass.HEAVY_DUTY

    def test_from_annual_hours_medium_duty(self):
        """2000-2999 hours should be medium duty."""
        assert DutyClass.from_annual_hours(2000) == DutyClass.MEDIUM_DUTY
        assert DutyClass.from_annual_hours(2500) == DutyClass.MEDIUM_DUTY

    def test_from_annual_hours_light_duty(self):
        """1000-1999 hours should be light duty."""
        assert DutyClass.from_annual_hours(1000) == DutyClass.LIGHT_DUTY
        assert DutyClass.from_annual_hours(1500) == DutyClass.LIGHT_DUTY

    def test_from_annual_hours_pleasure(self):
        """<1000 hours should be pleasure."""
        assert DutyClass.from_annual_hours(500) == DutyClass.PLEASURE
        assert DutyClass.from_annual_hours(999) == DutyClass.PLEASURE

    def test_typical_hours_range(self):
        """Test typical hours range properties."""
        assert DutyClass.CONTINUOUS.typical_hours_range == (5000, 8000)
        assert DutyClass.HEAVY_DUTY.typical_hours_range == (3000, 5000)
        assert DutyClass.MEDIUM_DUTY.typical_hours_range == (2000, 4000)
        assert DutyClass.LIGHT_DUTY.typical_hours_range == (1000, 3000)
        assert DutyClass.PLEASURE.typical_hours_range == (250, 1000)

    def test_typical_load_factor_range(self):
        """Test typical load factor range properties."""
        assert DutyClass.CONTINUOUS.typical_load_factor_range == (0.80, 1.00)
        assert DutyClass.HEAVY_DUTY.typical_load_factor_range == (0.40, 0.80)
        assert DutyClass.MEDIUM_DUTY.typical_load_factor_range == (0.20, 0.80)


# =============================================================================
# FIT RECOMMENDATION TESTS
# =============================================================================


class TestFitRecommendation:
    """Tests for FitRecommendation enum."""

    def test_strong_fit_threshold(self):
        """Score >= 90 should be STRONG_FIT."""
        assert FitRecommendation.from_score(90) == FitRecommendation.STRONG_FIT
        assert FitRecommendation.from_score(95) == FitRecommendation.STRONG_FIT
        assert FitRecommendation.from_score(100) == FitRecommendation.STRONG_FIT

    def test_good_fit_threshold(self):
        """Score 75-89 should be GOOD_FIT."""
        assert FitRecommendation.from_score(75) == FitRecommendation.GOOD_FIT
        assert FitRecommendation.from_score(80) == FitRecommendation.GOOD_FIT
        assert FitRecommendation.from_score(89) == FitRecommendation.GOOD_FIT

    def test_acceptable_threshold(self):
        """Score 60-74 should be ACCEPTABLE."""
        assert FitRecommendation.from_score(60) == FitRecommendation.ACCEPTABLE
        assert FitRecommendation.from_score(70) == FitRecommendation.ACCEPTABLE
        assert FitRecommendation.from_score(74) == FitRecommendation.ACCEPTABLE

    def test_marginal_threshold(self):
        """Score 40-59 should be MARGINAL."""
        assert FitRecommendation.from_score(40) == FitRecommendation.MARGINAL
        assert FitRecommendation.from_score(50) == FitRecommendation.MARGINAL
        assert FitRecommendation.from_score(59) == FitRecommendation.MARGINAL

    def test_not_suitable_threshold(self):
        """Score <40 should be NOT_SUITABLE."""
        assert FitRecommendation.from_score(39) == FitRecommendation.NOT_SUITABLE
        assert FitRecommendation.from_score(20) == FitRecommendation.NOT_SUITABLE
        assert FitRecommendation.from_score(0) == FitRecommendation.NOT_SUITABLE

    def test_boundary_values(self):
        """Test exact boundary values."""
        # 89.9 should still be GOOD_FIT, 90 should be STRONG_FIT
        assert FitRecommendation.from_score(89.9) == FitRecommendation.GOOD_FIT
        assert FitRecommendation.from_score(90.0) == FitRecommendation.STRONG_FIT

        # 74.9 should still be ACCEPTABLE, 75 should be GOOD_FIT
        assert FitRecommendation.from_score(74.9) == FitRecommendation.ACCEPTABLE
        assert FitRecommendation.from_score(75.0) == FitRecommendation.GOOD_FIT


# =============================================================================
# HARMONIZED DUTY CLASS TESTS
# =============================================================================


class TestHarmonizedDutyClass:
    """Tests for HarmonizedDutyClass enum."""

    def test_from_duty_class_mapping(self):
        """Test conversion from DutyClass to HarmonizedDutyClass."""
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.CONTINUOUS)
            == HarmonizedDutyClass.CON
        )
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.HEAVY_DUTY)
            == HarmonizedDutyClass.HVY
        )
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.MEDIUM_DUTY)
            == HarmonizedDutyClass.MED
        )
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.LIGHT_DUTY)
            == HarmonizedDutyClass.LGT
        )
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.INTERMITTENT)
            == HarmonizedDutyClass.INT
        )
        assert (
            HarmonizedDutyClass.from_duty_class(DutyClass.PLEASURE)
            == HarmonizedDutyClass.PLS
        )

    def test_load_factor_range(self):
        """Test load factor range properties."""
        assert HarmonizedDutyClass.CON.load_factor_range == (0.80, 1.00)
        assert HarmonizedDutyClass.HVY.load_factor_range == (0.60, 0.80)
        assert HarmonizedDutyClass.MED.load_factor_range == (0.40, 0.60)
        assert HarmonizedDutyClass.LGT.load_factor_range == (0.20, 0.50)
        assert HarmonizedDutyClass.INT.load_factor_range == (0.10, 0.40)
        assert HarmonizedDutyClass.PLS.load_factor_range == (0.00, 0.30)

    def test_annual_hours_range(self):
        """Test annual hours range properties."""
        assert HarmonizedDutyClass.CON.annual_hours_range == (5000, 8760)
        assert HarmonizedDutyClass.HVY.annual_hours_range == (3000, 5000)
        assert HarmonizedDutyClass.MED.annual_hours_range == (2000, 4000)


# =============================================================================
# EMISSION COMPLIANCE TESTS
# =============================================================================


class TestEmissionComplianceScoring:
    """Tests for score_emission_compliance function."""

    def test_meets_emission_requirement(self):
        """Engine meeting emission tier should score 100."""
        requirement = make_customer_requirement(emission_tier_required="IMO Tier III")
        rating = make_engine_rating(emission_tier="IMO Tier III")

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 100.0
        assert "meets" in detail.lower()

    def test_exceeds_emission_requirement(self):
        """Engine exceeding emission tier should score 100."""
        requirement = make_customer_requirement(emission_tier_required="IMO Tier II")
        rating = make_engine_rating(emission_tier="IMO Tier III")

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 100.0
        assert "exceeds" in detail.lower()

    def test_one_tier_below_with_scr(self):
        """One tier below with SCR should score 80."""
        requirement = make_customer_requirement(emission_tier_required="IMO Tier III")
        rating = EngineRating(
            id=str(uuid.uuid4()),
            engine_model_id=str(uuid.uuid4()),
            rating_designation="M96",
            emission_tier="IMO Tier II",
            aftertreatment_required="SCR system",
            power_kw=4000,
            rpm=1800,
        )

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 80.0
        assert "scr" in detail.lower()

    def test_one_tier_below_without_scr(self):
        """One tier below without SCR should score 60."""
        requirement = make_customer_requirement(emission_tier_required="IMO Tier III")
        rating = make_engine_rating(emission_tier="IMO Tier II")

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 60.0
        assert "upgrade possible" in detail.lower() or "one tier" in detail.lower()

    def test_large_gap_in_tiers(self):
        """Large gap in emission tiers should score 20."""
        requirement = make_customer_requirement(
            emission_tier_required="EPA Tier 4 Final"
        )
        rating = make_engine_rating(emission_tier="IMO Tier I")

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 20.0
        assert "gap" in detail.lower() or "does not meet" in detail.lower()

    def test_no_emission_requirement(self):
        """No emission requirement should return neutral score."""
        requirement = make_customer_requirement(emission_tier_required=None)
        rating = make_engine_rating(emission_tier="IMO Tier III")

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 80.0
        assert "no emission tier requirement" in detail.lower()

    def test_engine_tier_not_specified(self):
        """Engine with no emission tier should return 50."""
        requirement = make_customer_requirement(emission_tier_required="IMO Tier III")
        rating = make_engine_rating(emission_tier=None)

        score, detail = score_emission_compliance(requirement, rating)

        assert score == 50.0
        assert "not specified" in detail.lower()


# =============================================================================
# APPLICATION SUITABILITY TESTS
# =============================================================================


class TestApplicationSuitability:
    """Tests for APPLICATION_SUITABILITY constant."""

    def test_fast_ferry_applications(self):
        """Fast ferry should map to fast craft applications."""
        assert "fast_craft" in APPLICATION_SUITABILITY["fast_ferry"]
        assert "high_speed" in APPLICATION_SUITABILITY["fast_ferry"]

    def test_fpso_applications(self):
        """FPSO should include offshore and power generation."""
        assert "fpso" in APPLICATION_SUITABILITY["fpso"]
        assert "offshore" in APPLICATION_SUITABILITY["fpso"]
        assert "power_generation" in APPLICATION_SUITABILITY["fpso"]

    def test_tug_applications(self):
        """Tug should include harbor and workboat."""
        assert "tug" in APPLICATION_SUITABILITY["tug"]
        assert "harbor" in APPLICATION_SUITABILITY["tug"]
        assert "workboat" in APPLICATION_SUITABILITY["tug"]

    def test_naval_applications(self):
        """Corvette and frigate should include naval."""
        assert "naval" in APPLICATION_SUITABILITY["corvette"]
        assert "naval" in APPLICATION_SUITABILITY["frigate"]


# =============================================================================
# ENGINE SERIES APPLICATIONS TESTS
# =============================================================================


class TestEngineSeriesApplications:
    """Tests for ENGINE_SERIES_APPLICATIONS constant."""

    def test_mtu_series_2000(self):
        """MTU Series 2000 should be suitable for ferries and yachts."""
        assert "ferry" in ENGINE_SERIES_APPLICATIONS["Series 2000"]
        assert "yacht" in ENGINE_SERIES_APPLICATIONS["Series 2000"]

    def test_mtu_series_4000(self):
        """MTU Series 4000 should be suitable for OSV and naval."""
        assert "osv" in ENGINE_SERIES_APPLICATIONS["Series 4000"]
        assert "naval" in ENGINE_SERIES_APPLICATIONS["Series 4000"]

    def test_bergen_b32_40(self):
        """Bergen B32:40 should be suitable for offshore and ferries."""
        assert "offshore" in ENGINE_SERIES_APPLICATIONS["B32:40"]
        assert "ferry" in ENGINE_SERIES_APPLICATIONS["B32:40"]


# =============================================================================
# ENGINE RATING DATACLASS TESTS
# =============================================================================


class TestEngineRatingDataclass:
    """Tests for EngineRating dataclass."""

    def test_engine_rating_creation(self):
        """Test creating an EngineRating."""
        rating = make_engine_rating(
            power_kw=4000,
            rpm=1800,
            duty_class=DutyClass.MEDIUM_DUTY,
        )

        assert rating.power_kw == 4000
        assert rating.rpm == 1800
        assert rating.duty_class == DutyClass.MEDIUM_DUTY

    def test_engine_rating_to_dict(self):
        """Test EngineRating to_dict method."""
        rating = make_engine_rating(
            power_kw=4000,
            rpm=1800,
            duty_class=DutyClass.MEDIUM_DUTY,
        )

        result = rating.to_dict()

        assert result["power_kw"] == 4000
        assert result["rpm"] == 1800
        assert result["duty_class"] == "medium_duty"

    def test_calculate_power_density(self):
        """Test power density calculation."""
        rating = make_engine_rating(power_kw=4000, dry_weight_kg=2000)

        density = rating.calculate_power_density()

        assert density == 2.0  # 4000 / 2000

    def test_calculate_power_density_no_weight(self):
        """Test power density with no weight returns None."""
        rating = make_engine_rating(power_kw=4000, dry_weight_kg=None)

        density = rating.calculate_power_density()

        assert density is None


# =============================================================================
# CUSTOMER REQUIREMENT DATACLASS TESTS
# =============================================================================


class TestCustomerRequirementDataclass:
    """Tests for CustomerRequirement dataclass."""

    def test_customer_requirement_creation(self):
        """Test creating a CustomerRequirement."""
        req = make_customer_requirement(
            power_required_kw=4000,
            duty_class_required=DutyClass.HEAVY_DUTY,
        )

        assert req.power_required_kw == 4000
        assert req.duty_class_required == DutyClass.HEAVY_DUTY

    def test_customer_requirement_defaults(self):
        """Test CustomerRequirement default values."""
        req = CustomerRequirement(
            id=str(uuid.uuid4()),
            customer_name="Test",
        )

        assert req.power_required_kw == 0.0
        assert req.power_tolerance_pct == 15.0
        assert req.duty_class_required is None
        assert req.eca_operation is False
        assert req.status == "active"

    def test_customer_requirement_to_dict(self):
        """Test CustomerRequirement to_dict method."""
        req = make_customer_requirement(
            power_required_kw=4000,
            duty_class_required=DutyClass.MEDIUM_DUTY,
        )

        result = req.to_dict()

        assert result["power_required_kw"] == 4000
        assert result["duty_class_required"] == "medium_duty"


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_power_engine(self):
        """Test with zero power engine."""
        requirement = make_customer_requirement(power_required_kw=4000)
        rating = make_engine_rating(power_kw=0)

        score, detail = score_power_match(requirement, rating)

        # Should handle gracefully (100% underpowered)
        assert score <= 25
        assert "underpowered" in detail.lower()

    def test_negative_tolerance_treated_as_zero(self):
        """Test that negative tolerance is handled."""
        requirement = make_customer_requirement(
            power_required_kw=4000, power_tolerance_pct=-10.0
        )
        rating = make_engine_rating(power_kw=4000)

        # Should not crash - exact match
        score, detail = score_power_match(requirement, rating)
        assert score >= 90  # Still high score for exact match

    def test_very_high_power_difference(self):
        """Test with extreme power difference."""
        requirement = make_customer_requirement(power_required_kw=1000)
        rating = make_engine_rating(power_kw=10000)  # 10x overpowered

        score, detail = score_power_match(requirement, rating)

        # Should not crash, should return low score
        assert score >= 0
        assert "overpowered" in detail.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
