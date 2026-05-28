"""
Product Fit Scoring Service

Deterministic algorithm for scoring engine-to-customer-requirement fit.
NO ML/LLM - pure rule-based scoring for auditability and consistency.

ADR Reference: ADR-004 Unified Knowledge Base Architecture

Scoring Components (weights configurable, default weights sum to 100%):
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

import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from lead_to_cash.services.knowledge_base.unified_models import (
    DEFAULT_FIT_WEIGHTS,
    CustomerRequirement,
    DutyClass,
    EngineRating,
    FitRecommendation,
    ProductFitResult,
    ProductFitWeights,
)

logger = logging.getLogger(__name__)


# Thread lock for singleton initialization
_service_lock = threading.Lock()


# =============================================================================
# SCORING CONSTANTS
# =============================================================================


# Application suitability matrix: vessel_type -> [suitable_applications]
# Based on product_fit_guide.md and industry knowledge
APPLICATION_SUITABILITY = {
    # High-speed applications (MTU specialty)
    "fast_ferry": ["ferry", "fast_craft", "high_speed"],
    "ferry": ["ferry", "passenger", "roro"],
    "patrol_boat": ["patrol", "naval", "fast_craft", "workboat"],
    "yacht": ["yacht", "pleasure", "luxury"],
    "crew_boat": ["crew_transfer", "workboat", "offshore"],
    "pilot_boat": ["pilot", "workboat", "patrol"],
    "workboat": ["workboat", "utility", "service"],
    # Medium-duty applications
    "tug": ["tug", "harbor", "escort", "workboat"],
    "osv": ["osv", "offshore", "psv", "ahts"],
    "psv": ["psv", "osv", "offshore", "supply"],
    "ahts": ["ahts", "osv", "offshore", "anchor_handling"],
    "fishing": ["fishing", "trawler", "workboat"],
    # Heavy-duty/continuous applications
    "cargo": ["cargo", "freighter", "container"],
    "tanker": ["tanker", "cargo", "bulk"],
    "dredger": ["dredger", "workboat", "heavy_duty"],
    "fpso": ["fpso", "offshore", "power_generation"],
    # Naval
    "corvette": ["naval", "corvette", "patrol"],
    "frigate": ["naval", "frigate", "corvette"],
}

# Engine series to typical applications mapping
# Based on product_fit_guide.md and MTU/Bergen portfolio
ENGINE_SERIES_APPLICATIONS = {
    # MTU Series (RRPS)
    "Series 2000": ["ferry", "yacht", "workboat", "patrol", "crew_transfer"],
    "Series 4000": ["osv", "ferry", "naval", "yacht", "ahts", "tug"],
    "Series 8000": ["fast_ferry", "naval", "large_ferry"],
    # Bergen (RRPS)
    "B32:40": ["ferry", "offshore", "power_generation"],
    "B35:40": ["fpso", "offshore", "large_ferry"],
    # Competitors (for reference)
    "QSK": ["tug", "osv", "workboat", "offshore"],
    "3500": ["tug", "osv", "workboat", "ferry"],
    "C32": ["workboat", "tug", "osv", "patrol", "yacht"],
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================


def _smooth_score(delta_pct: float, breakpoints: list[tuple[float, float]]) -> float:
    """
    Calculate smooth score using linear interpolation between breakpoints.

    This replaces cliff effects with smooth transitions.

    Args:
        delta_pct: Percentage difference (positive or negative)
        breakpoints: List of (pct_threshold, score) tuples, sorted by pct ascending

    Returns:
        Interpolated score (0-100)
    """
    # Handle exact match
    if delta_pct <= breakpoints[0][0]:
        return breakpoints[0][1]

    # Handle beyond last breakpoint
    if delta_pct >= breakpoints[-1][0]:
        return breakpoints[-1][1]

    # Find the two breakpoints to interpolate between
    for i in range(len(breakpoints) - 1):
        pct_low, score_low = breakpoints[i]
        pct_high, score_high = breakpoints[i + 1]

        if pct_low <= delta_pct <= pct_high:
            # Linear interpolation
            if pct_high == pct_low:
                return score_low
            ratio = (delta_pct - pct_low) / (pct_high - pct_low)
            return score_low + ratio * (score_high - score_low)

    return breakpoints[-1][1]


def score_power_match(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score how well the engine power matches the requirement.

    Uses smooth curves instead of cliff effects:
    - Exact match or within tolerance: 100 points
    - Gradually decreases based on how far from ideal
    - Overpowered: penalty, but still usable
    - Underpowered: steeper penalty (more problematic)

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    required_kw = requirement.power_required_kw
    engine_kw = rating.power_kw
    tolerance_pct = requirement.power_tolerance_pct or 15.0

    if required_kw <= 0:
        return (50.0, "No power requirement specified")

    # Calculate percentage difference
    delta_kw = engine_kw - required_kw
    delta_pct = (delta_kw / required_kw) * 100

    # Smooth scoring using breakpoints
    if delta_pct >= 0:
        # Overpowered case: less severe penalty
        # (tolerance, 100) -> (25, 90) -> (35, 75) -> (50, 55) -> (100, 40)
        breakpoints = [
            (0, 100),
            (tolerance_pct, 100),  # Within tolerance = perfect
            (25, 90),
            (35, 75),
            (50, 55),
            (75, 45),
            (100, 40),
        ]
        score = _smooth_score(delta_pct, breakpoints)
        if delta_pct <= tolerance_pct:
            detail = f"{engine_kw:.0f} kW matches {required_kw:.0f} kW requirement ({delta_pct:+.1f}%)"
        elif delta_pct <= 25:
            detail = f"{engine_kw:.0f} kW is slightly over {required_kw:.0f} kW ({delta_pct:+.1f}%)"
        else:
            detail = f"{engine_kw:.0f} kW is overpowered ({delta_pct:+.1f}% vs {required_kw:.0f} kW)"
    else:
        # Underpowered case: steeper penalty (more problematic)
        # (0, 100) -> (-15, 100) -> (-25, 70) -> (-35, 45) -> (-50, 20) -> (-75, 0)
        abs_delta = abs(delta_pct)
        breakpoints = [
            (0, 100),
            (tolerance_pct, 100),  # Within tolerance = perfect
            (25, 70),
            (35, 45),
            (50, 20),
            (75, 0),
        ]
        score = _smooth_score(abs_delta, breakpoints)
        detail = f"{engine_kw:.0f} kW is underpowered ({delta_pct:.1f}% vs {required_kw:.0f} kW)"

    return (round(score, 1), detail)


def score_duty_class_match(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score how well the engine duty class matches the customer's operating profile.

    Scoring Rules:
    - Exact match: 100 points
    - One class heavier (engine can do more): 80 points
    - One class lighter (engine may be overworked): 50 points
    - Two classes different: 30 points
    - Three+ classes different: 10 points

    If no duty class requirement, infer from annual hours.

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    # Determine required duty class
    required_duty = requirement.duty_class_required
    if not required_duty and requirement.annual_operating_hours:
        required_duty = DutyClass.from_annual_hours(requirement.annual_operating_hours)

    if not required_duty:
        return (70.0, "No duty class requirement specified, assuming medium duty")

    engine_duty = rating.duty_class

    # Define duty class ordering (heaviest to lightest)
    duty_order = [
        DutyClass.CONTINUOUS,
        DutyClass.HEAVY_DUTY,
        DutyClass.MEDIUM_DUTY,
        DutyClass.LIGHT_DUTY,
        DutyClass.PLEASURE,
        DutyClass.INTERMITTENT,
    ]

    try:
        required_idx = duty_order.index(required_duty)
        engine_idx = duty_order.index(engine_duty)
    except ValueError:
        return (
            50.0,
            f"Unknown duty class comparison: {engine_duty} vs {required_duty}",
        )

    diff = engine_idx - required_idx  # Positive = engine is lighter duty

    if diff == 0:
        score = 100.0
        detail = f"{engine_duty.value} matches {required_duty.value} requirement"
    elif diff == -1:
        # Engine is one class heavier (better than needed)
        score = 80.0
        detail = (
            f"{engine_duty.value} (heavier duty than {required_duty.value} required)"
        )
    elif diff == 1:
        # Engine is one class lighter (may be overworked)
        score = 50.0
        detail = f"{engine_duty.value} (lighter duty than {required_duty.value} required - may be overworked)"
    elif diff == -2:
        score = 70.0
        detail = f"{engine_duty.value} (much heavier duty than {required_duty.value} required)"
    elif diff == 2:
        score = 30.0
        detail = f"{engine_duty.value} (much lighter duty than {required_duty.value} required - risk of overwork)"
    else:
        score = 10.0
        detail = f"{engine_duty.value} does not match {required_duty.value} requirement (significant mismatch)"

    return (score, detail)


def score_emission_compliance(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score emission tier compliance.

    Scoring Rules:
    - Meets or exceeds requirement: 100 points
    - One tier below but can be upgraded with SCR: 80 points
    - One tier below, upgrade possible: 60 points
    - Does not meet and cannot be upgraded: 20 points
    - No requirement specified: 80 points (neutral)
    - ECA zone operation requires IMO Tier III or EPA Tier 4: penalized if not met

    Tier hierarchy (Phase 4 expanded):
    - Level 4: EPA Tier 4 Final, EU Stage V (strictest)
    - Level 3: IMO Tier III, IMO Tier III SCR, EPA Tier 4, EU Stage IV
    - Level 2: IMO Tier II, EPA Tier 3, EU Stage IIIA
    - Level 1: IMO Tier I (legacy)

    ECA Zone Compliance:
    - Emission Control Areas (Baltic, North Sea, US/Canada coasts, Caribbean US)
    - Require IMO Tier III for new ships (2016+)
    - Tier II engines can operate with SCR retrofit

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    required_tier = requirement.emission_tier_required
    engine_tier = rating.emission_tier
    eca_operation = getattr(requirement, "eca_operation", False)

    if not required_tier:
        # If ECA operation is specified, assume IMO Tier III required
        if eca_operation:
            required_tier = "IMO Tier III"
        else:
            return (80.0, "No emission tier requirement specified")

    if not engine_tier:
        return (50.0, "Engine emission tier not specified in data")

    # Normalize tier names for comparison
    required_lower = required_tier.lower().strip()
    engine_lower = engine_tier.lower().strip()

    # Define tier hierarchy (higher number = stricter/better) - Phase 4 expanded
    tier_levels = {
        # Level 1: Legacy
        "imo tier i": 1,
        # Level 2: Current standard
        "imo tier ii": 2,
        "epa tier 3": 2,
        "eu stage iiia": 2,
        "tier ii": 2,
        # Level 3: ECA compliant
        "imo tier iii": 3,
        "imo tier iii (gas mode)": 3,
        "imo tier iii (scr)": 3,
        "epa tier 4": 3,
        "eu stage iv": 3,
        "tier iii": 3,
        # Level 4: Strictest (ultra-low emissions)
        "epa tier 4 final": 4,
        "eu stage v": 4,
    }

    required_level = tier_levels.get(required_lower, 0)
    engine_level = tier_levels.get(engine_lower, 0)

    # Handle unknown tiers gracefully
    if required_level == 0:
        # Try partial match
        for tier_name, level in tier_levels.items():
            if tier_name in required_lower or required_lower in tier_name:
                required_level = level
                break

    if engine_level == 0:
        for tier_name, level in tier_levels.items():
            if tier_name in engine_lower or engine_lower in tier_name:
                engine_level = level
                break

    # ECA zone special handling
    if eca_operation and engine_level < 3:
        # Operating in ECA but engine is Tier II or lower
        if (
            rating.aftertreatment_required
            and "scr" in str(rating.aftertreatment_required).lower()
        ):
            score = 70.0
            detail = f"{engine_tier} requires SCR for ECA zone operation"
        else:
            score = 40.0
            detail = f"{engine_tier} does not meet ECA zone requirements (IMO Tier III needed)"
        return (score, detail)

    if engine_level >= required_level:
        score = 100.0
        detail = f"{engine_tier} meets {required_tier} requirement"
        if engine_level > required_level:
            detail = (
                f"{engine_tier} exceeds {required_tier} requirement (emission margin)"
            )
    elif engine_level == required_level - 1:
        # Check if aftertreatment can upgrade
        if (
            rating.aftertreatment_required
            and "scr" in str(rating.aftertreatment_required).lower()
        ):
            score = 80.0
            detail = f"{engine_tier} can meet {required_tier} with SCR aftertreatment"
        else:
            score = 60.0
            detail = (
                f"{engine_tier} is one tier below {required_tier}, SCR upgrade possible"
            )
    else:
        score = 20.0
        detail = (
            f"{engine_tier} does not meet {required_tier} requirement (gap too large)"
        )

    return (score, detail)


def score_application_fit(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score how well the engine suits the vessel type and application.

    Uses application_profiles from the rating and matches against
    vessel_type and application from the requirement.

    Scoring Rules:
    - Primary application match: 100 points
    - Secondary application match: 80 points
    - Related application: 60 points
    - No match but compatible: 40 points
    - Incompatible: 20 points

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    vessel_type = requirement.vessel_type
    application = requirement.application

    if not vessel_type and not application:
        return (70.0, "No vessel type or application specified")

    # Get engine's application profiles
    engine_apps = rating.get_application_profiles_list()
    if not engine_apps:
        # Try to infer from model name/series
        return (60.0, "Engine application profiles not specified in data")

    # Normalize for comparison
    vessel_lower = (vessel_type or "").lower().replace(" ", "_").replace("-", "_")
    app_lower = (application or "").lower().replace(" ", "_").replace("-", "_")
    engine_apps_lower = [
        a.lower().replace(" ", "_").replace("-", "_") for a in engine_apps
    ]

    # Check for direct match
    if vessel_lower in engine_apps_lower or app_lower in engine_apps_lower:
        score = 100.0
        detail = f"Engine proven in {vessel_type or application} applications"
        return (score, detail)

    # Check for related applications
    related_apps = APPLICATION_SUITABILITY.get(vessel_lower, [])
    matches = set(engine_apps_lower) & set(a.lower() for a in related_apps)
    if matches:
        score = 80.0
        detail = f"Engine suitable for related applications: {', '.join(matches)}"
        return (score, detail)

    # Check if any overlap at all
    all_suitable = set()
    for v, apps in APPLICATION_SUITABILITY.items():
        if v in engine_apps_lower:
            all_suitable.update(apps)

    if vessel_lower in all_suitable or app_lower in all_suitable:
        score = 60.0
        detail = f"Engine compatible with {vessel_type or application}"
        return (score, detail)

    # No clear match
    score = 40.0
    detail = f"No proven match for {vessel_type or application}, but may be suitable"
    return (score, detail)


def score_physical_constraints(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score whether engine meets physical constraints (weight, size).

    Scoring Rules:
    - All constraints met: 100 points
    - Weight within limit but close (>90%): 80 points
    - One constraint exceeded by <10%: 60 points
    - One constraint exceeded by >10%: 30 points
    - Multiple constraints exceeded: 10 points
    - No constraints specified: 80 points (neutral)

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    constraints_checked = 0
    constraints_met = 0
    details = []

    # Check weight
    if requirement.max_engine_weight_kg and rating.dry_weight_kg:
        constraints_checked += 1
        if rating.dry_weight_kg <= requirement.max_engine_weight_kg:
            constraints_met += 1
            pct = (rating.dry_weight_kg / requirement.max_engine_weight_kg) * 100
            details.append(
                f"Weight {rating.dry_weight_kg:.0f} kg within {requirement.max_engine_weight_kg:.0f} kg limit ({pct:.0f}%)"
            )
        else:
            excess = (
                (rating.dry_weight_kg - requirement.max_engine_weight_kg)
                / requirement.max_engine_weight_kg
            ) * 100
            details.append(
                f"Weight {rating.dry_weight_kg:.0f} kg exceeds {requirement.max_engine_weight_kg:.0f} kg limit by {excess:.1f}%"
            )

    # Check length
    if requirement.max_engine_length_mm and rating.length_mm:
        constraints_checked += 1
        if rating.length_mm <= requirement.max_engine_length_mm:
            constraints_met += 1
            details.append(f"Length {rating.length_mm:.0f} mm within limit")
        else:
            excess = (
                (rating.length_mm - requirement.max_engine_length_mm)
                / requirement.max_engine_length_mm
            ) * 100
            details.append(f"Length exceeds limit by {excess:.1f}%")

    # Check width
    if requirement.max_engine_width_mm and rating.width_mm:
        constraints_checked += 1
        if rating.width_mm <= requirement.max_engine_width_mm:
            constraints_met += 1
            details.append(f"Width {rating.width_mm:.0f} mm within limit")
        else:
            details.append("Width exceeds limit")

    # Check height
    if requirement.max_engine_height_mm and rating.height_mm:
        constraints_checked += 1
        if rating.height_mm <= requirement.max_engine_height_mm:
            constraints_met += 1
            details.append(f"Height {rating.height_mm:.0f} mm within limit")
        else:
            details.append("Height exceeds limit")

    if constraints_checked == 0:
        return (80.0, "No physical constraints specified")

    # Calculate score based on constraints met
    if constraints_met == constraints_checked:
        score = 100.0
    elif constraints_met >= constraints_checked - 1:
        score = 60.0
    else:
        score = 30.0

    detail = "; ".join(details) if details else "Physical constraints evaluated"
    return (score, detail)


def score_fuel_compatibility(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score fuel type compatibility.

    Scoring Rules:
    - All required fuels supported: 100 points
    - Primary fuel supported, secondary not: 80 points
    - Can use alternative (e.g., HVO instead of diesel): 70 points
    - Required fuel not supported: 30 points
    - No requirement specified: 80 points (neutral)

    Returns:
        tuple: (score 0-100, detail explanation)
    """
    # Get required fuels
    fuel_preference = requirement.get_fuel_preference_list()
    fuel_mandatory = []
    if requirement.fuel_type_mandatory:
        try:
            fuel_mandatory = json.loads(requirement.fuel_type_mandatory)
        except json.JSONDecodeError:
            pass

    if not fuel_preference and not fuel_mandatory:
        # Check if alternative fuel is required
        if requirement.alternative_fuel_required:
            engine_fuels = rating.get_fuel_types_list()
            alt_fuels = ["lng", "methanol", "ammonia", "hydrogen", "hvo", "gtl"]
            if any(f.lower() in [ef.lower() for ef in engine_fuels] for f in alt_fuels):
                return (100.0, "Alternative fuel capability available")
            else:
                return (40.0, "Alternative fuel required but not available")
        return (80.0, "No fuel type requirement specified")

    # Get engine fuels
    engine_fuels = rating.get_fuel_types_list()
    if not engine_fuels:
        return (50.0, "Engine fuel types not specified in data")

    engine_fuels_lower = [f.lower() for f in engine_fuels]

    # Check mandatory fuels first
    if fuel_mandatory:
        mandatory_lower = [f.lower() for f in fuel_mandatory]
        missing = [f for f in mandatory_lower if f not in engine_fuels_lower]
        if missing:
            return (30.0, f"Required fuel(s) not supported: {', '.join(missing)}")

    # Check preference fuels
    if fuel_preference:
        preference_lower = [f.lower() for f in fuel_preference]
        supported = [f for f in preference_lower if f in engine_fuels_lower]
        if len(supported) == len(preference_lower):
            return (100.0, f"All preferred fuels supported: {', '.join(engine_fuels)}")
        elif supported:
            return (80.0, f"Primary fuel supported: {', '.join(supported)}")

    # Check for equivalent fuels (e.g., HVO = diesel compatible)
    equivalents = {
        "diesel": ["mdo", "mgo", "hvo", "gtl"],
        "mdo": ["diesel", "mgo"],
        "hfo": ["diesel", "mdo"],
    }

    for pref in fuel_preference:
        pref_lower = pref.lower()
        if pref_lower in equivalents:
            for eq in equivalents[pref_lower]:
                if eq in engine_fuels_lower:
                    return (70.0, f"{pref} compatible via {eq}")

    return (
        50.0,
        f"Fuel compatibility uncertain. Engine supports: {', '.join(engine_fuels)}",
    )


# =============================================================================
# PROPELLER/GEARBOX MATCHING (Phase 3 Enhancement)
# =============================================================================


def score_propeller_match(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score propeller/gearbox matching for HIGH-SPEED engines.

    HIGH-SPEED engines (>1000 RPM) typically require reduction gearboxes to match
    propeller RPM requirements. This function evaluates whether the engine's RPM
    range is suitable for the application's typical propeller requirements.

    Args:
        requirement: Customer requirement
        rating: Engine rating to evaluate

    Returns:
        Tuple of (score 0-100, explanation string)
    """
    # Get vessel type from requirement (ferry, tug, osv, etc.)
    vessel_type = requirement.vessel_type

    if not vessel_type:
        return (75.0, "No vessel type specified, assuming standard propeller matching")

    # Typical propeller RPM ranges by vessel type
    # These are typical propeller speeds for various applications
    propeller_rpm_ranges = {
        "tug": (150, 300),  # Tugs need high torque, low propeller RPM
        "osv": (180, 350),
        "ferry": (200, 400),
        "fast_ferry": (300, 600),
        "workboat": (250, 450),
        "crew_boat": (300, 550),
        "patrol": (350, 600),
        "naval": (250, 500),
        "yacht": (400, 700),
        "fishing": (200, 400),
        "dredger": (120, 250),  # Very low RPM for dredging
        "pilot": (350, 550),
    }

    # Get engine RPM from rating
    engine_rpm = rating.rpm
    if not engine_rpm:
        return (70.0, "Engine RPM not specified")

    primary_app = vessel_type.lower().replace("-", "_").replace(" ", "_")

    if primary_app not in propeller_rpm_ranges:
        return (
            75.0,
            f"Unknown application '{primary_app}', assuming standard gearbox available",
        )

    prop_rpm_min, prop_rpm_max = propeller_rpm_ranges[primary_app]

    # Calculate required gear ratio
    # Gear ratio = Engine RPM / Propeller RPM
    gear_ratio_min = engine_rpm / prop_rpm_max  # Minimum ratio (high prop RPM)
    gear_ratio_max = engine_rpm / prop_rpm_min  # Maximum ratio (low prop RPM)

    # Typical marine gearboxes available in ratios from 1.5:1 to 6:1
    # Specialized gearboxes can go higher (up to 8:1)
    min_available_ratio = 1.5
    max_available_ratio = 6.0

    # Check if required ratio falls within standard gearbox range
    if gear_ratio_min <= max_available_ratio and gear_ratio_max >= min_available_ratio:
        # Calculate optimal score based on how well it fits
        optimal_ratio = (gear_ratio_min + gear_ratio_max) / 2

        if 2.0 <= optimal_ratio <= 4.5:
            # Ideal range - common gearbox ratios
            score = 95.0
            detail = f"Excellent match: {engine_rpm} RPM with {optimal_ratio:.1f}:1 gearbox for {primary_app}"
        elif 1.5 <= optimal_ratio <= 6.0:
            # Good range - available ratios
            score = 80.0
            detail = f"Good match: {engine_rpm} RPM needs {optimal_ratio:.1f}:1 gearbox for {primary_app}"
        else:
            # Specialized gearbox needed
            score = 65.0
            detail = f"Specialized gearbox needed: {optimal_ratio:.1f}:1 ratio for {primary_app}"

        return (score, detail)

    # Check if it's close but needs extended ratio
    if gear_ratio_min > max_available_ratio:
        # Engine RPM too high for this application
        return (
            40.0,
            f"Engine RPM too high ({engine_rpm}) for {primary_app}, "
            f"requires {gear_ratio_min:.1f}:1 ratio (max available ~6:1)",
        )

    if gear_ratio_max < min_available_ratio:
        # Engine RPM too low - unusual for high-speed
        return (
            55.0,
            f"Engine RPM ({engine_rpm}) may be too low for optimal {primary_app} propeller matching",
        )

    return (70.0, f"Standard propeller matching possible for {primary_app}")


# =============================================================================
# CLASSIFICATION SOCIETY SCORING (Phase 3 Enhancement)
# =============================================================================


def score_classification_compliance(
    requirement: CustomerRequirement,
    rating: EngineRating,
) -> tuple[float, str]:
    """
    Score engine type approval/certification by classification society.

    Checks if the engine has type approval from the required classification
    society (Lloyd's, DNV, ABS, etc.). For now, this is a placeholder that
    returns a neutral score since type approval data isn't yet populated.

    Args:
        requirement: Customer requirement (may include required_class_society)
        rating: Engine rating to evaluate

    Returns:
        Tuple of (score 0-100, explanation string)
    """
    # Check if requirement specifies a classification society
    # This field would be in customer requirement metadata
    required_class = getattr(requirement, "required_class_society", None)

    if not required_class:
        # No specific class society required - assume all major engines
        # from reputable manufacturers have type approvals
        return (
            80.0,
            "No specific class society required; major manufacturer assumed approved",
        )

    # For now, return a placeholder score since type approvals data isn't populated
    # In production, this would query kb_engine_type_approvals table
    manufacturer = rating.rating_name.split()[0] if rating.rating_name else ""

    # Major manufacturers typically have type approvals from all IACS members
    major_manufacturers = [
        "MTU",
        "Cummins",
        "Cat",
        "Caterpillar",
        "MAN",
        "Volvo",
        "Wartsila",
    ]

    if manufacturer in major_manufacturers:
        return (
            85.0,
            f"{manufacturer} typically has type approvals from {required_class}; verify specific certificate",
        )

    # Other manufacturers may or may not have approvals
    return (
        65.0,
        f"Verify {manufacturer} has {required_class} type approval for this rating",
    )


# =============================================================================
# MAIN SCORING SERVICE
# =============================================================================


@dataclass
class ProductFitScoringService:
    """
    Service for calculating product fit scores.

    All scoring is deterministic (no ML/LLM) for auditability.
    Thread-safe singleton access via get_product_fit_scoring_service().
    """

    weights: ProductFitWeights = None

    def __post_init__(self):
        """Initialize with default weights if not provided, with validation."""
        if self.weights is None:
            self.weights = DEFAULT_FIT_WEIGHTS
        else:
            # Validate custom weights
            if not self.weights.validate():
                logger.warning(
                    f"Custom weights do not sum to 1.0 "
                    f"(actual: {self._weights_sum():.3f}), using defaults"
                )
                self.weights = DEFAULT_FIT_WEIGHTS

    def _weights_sum(self) -> float:
        """Calculate sum of all weights."""
        return (
            self.weights.power_weight
            + self.weights.application_weight
            + self.weights.duty_weight
            + self.weights.propeller_weight
            + self.weights.fuel_weight
            + self.weights.emission_weight
            + self.weights.physical_weight
            + self.weights.classification_weight
        )

    def calculate_fit(
        self,
        requirement: CustomerRequirement,
        rating: EngineRating,
    ) -> ProductFitResult:
        """
        Calculate overall product fit score and component scores.

        Updated in Phase 3 to include propeller matching and classification society scoring.

        Args:
            requirement: Customer requirement to match against
            rating: Engine rating to evaluate

        Returns:
            ProductFitResult with all scores and explanations
        """
        # Calculate component scores
        power_score, power_detail = score_power_match(requirement, rating)
        duty_score, duty_detail = score_duty_class_match(requirement, rating)
        emission_score, emission_detail = score_emission_compliance(requirement, rating)
        app_score, app_detail = score_application_fit(requirement, rating)
        physical_score, physical_detail = score_physical_constraints(
            requirement, rating
        )
        fuel_score, fuel_detail = score_fuel_compatibility(requirement, rating)
        # Phase 3 additions
        propeller_score, propeller_detail = score_propeller_match(requirement, rating)
        class_score, class_detail = score_classification_compliance(requirement, rating)

        # Calculate weighted overall score (Phase 3 updated weights)
        overall_score = (
            power_score * self.weights.power_weight
            + app_score * self.weights.application_weight
            + duty_score * self.weights.duty_weight
            + propeller_score * self.weights.propeller_weight
            + fuel_score * self.weights.fuel_weight
            + emission_score * self.weights.emission_weight
            + physical_score * self.weights.physical_weight
            + class_score * self.weights.classification_weight
        )

        # Determine recommendation
        recommendation = FitRecommendation.from_score(overall_score)

        # Collect positive and negative factors
        positive_factors = []
        negative_factors = []
        gap_factors = []

        score_threshold = 70.0  # Above this is positive, below is negative

        if power_score >= score_threshold:
            positive_factors.append(power_detail)
        elif power_score < 50:
            negative_factors.append(power_detail)
        else:
            gap_factors.append(power_detail)

        if duty_score >= score_threshold:
            positive_factors.append(duty_detail)
        elif duty_score < 50:
            negative_factors.append(duty_detail)
        else:
            gap_factors.append(duty_detail)

        if emission_score >= score_threshold:
            positive_factors.append(emission_detail)
        elif emission_score < 50:
            negative_factors.append(emission_detail)
        else:
            gap_factors.append(emission_detail)

        if app_score >= score_threshold:
            positive_factors.append(app_detail)
        elif app_score < 50:
            negative_factors.append(app_detail)
        else:
            gap_factors.append(app_detail)

        if physical_score >= score_threshold:
            positive_factors.append(physical_detail)
        elif physical_score < 50:
            negative_factors.append(physical_detail)
        else:
            gap_factors.append(physical_detail)

        if fuel_score >= score_threshold:
            positive_factors.append(fuel_detail)
        elif fuel_score < 50:
            negative_factors.append(fuel_detail)
        else:
            gap_factors.append(fuel_detail)

        # Phase 3: Propeller matching factors
        if propeller_score >= score_threshold:
            positive_factors.append(propeller_detail)
        elif propeller_score < 50:
            negative_factors.append(propeller_detail)
        else:
            gap_factors.append(propeller_detail)

        # Phase 3: Classification society factors
        if class_score >= score_threshold:
            positive_factors.append(class_detail)
        elif class_score < 50:
            negative_factors.append(class_detail)
        else:
            gap_factors.append(class_detail)

        # Create result
        result = ProductFitResult(
            id=str(uuid.uuid4()),
            requirement_id=requirement.id,
            engine_rating_id=rating.id,
            overall_fit_score=round(overall_score, 2),
            fit_recommendation=recommendation,
            power_fit_score=round(power_score, 2),
            power_fit_detail=power_detail,
            duty_fit_score=round(duty_score, 2),
            duty_fit_detail=duty_detail,
            emission_fit_score=round(emission_score, 2),
            emission_fit_detail=emission_detail,
            application_fit_score=round(app_score, 2),
            application_fit_detail=app_detail,
            physical_fit_score=round(physical_score, 2),
            physical_fit_detail=physical_detail,
            fuel_fit_score=round(fuel_score, 2),
            fuel_fit_detail=fuel_detail,
            positive_factors=json.dumps(positive_factors) if positive_factors else None,
            negative_factors=json.dumps(negative_factors) if negative_factors else None,
            gap_factors=json.dumps(gap_factors) if gap_factors else None,
            scoring_algorithm_version="v3",  # v3: Phase 3 - propeller + classification scoring
            scored_at=datetime.now(timezone.utc),
        )

        return result

    def rank_ratings_for_requirement(
        self,
        requirement: CustomerRequirement,
        ratings: list[EngineRating],
        top_n: Optional[int] = None,
    ) -> list[ProductFitResult]:
        """
        Score and rank multiple engine ratings for a requirement.

        Args:
            requirement: Customer requirement
            ratings: List of engine ratings to evaluate
            top_n: Limit results to top N (optional)

        Returns:
            List of ProductFitResult sorted by score descending
        """
        results = []
        for rating in ratings:
            result = self.calculate_fit(requirement, rating)
            results.append(result)

        # Sort by overall score descending
        results.sort(key=lambda r: r.overall_fit_score, reverse=True)

        # Assign ranks
        for i, result in enumerate(results):
            result.rank_for_requirement = i + 1

        # Limit to top N if specified
        if top_n:
            results = results[:top_n]

        return results

    def find_best_fit(
        self,
        requirement: CustomerRequirement,
        ratings: list[EngineRating],
        min_score: float = 60.0,
    ) -> Optional[ProductFitResult]:
        """
        Find the best fitting engine rating for a requirement.

        Args:
            requirement: Customer requirement
            ratings: List of engine ratings to evaluate
            min_score: Minimum acceptable score (default 60%)

        Returns:
            Best ProductFitResult if score >= min_score, else None
        """
        ranked = self.rank_ratings_for_requirement(requirement, ratings, top_n=1)
        if ranked and ranked[0].overall_fit_score >= min_score:
            return ranked[0]
        return None

    def compare_ratings(
        self,
        requirement: CustomerRequirement,
        rating_a: EngineRating,
        rating_b: EngineRating,
    ) -> dict:
        """
        Compare two engine ratings for the same requirement.

        Args:
            requirement: Customer requirement
            rating_a: First engine rating
            rating_b: Second engine rating

        Returns:
            Comparison dictionary with scores and recommendation
        """
        result_a = self.calculate_fit(requirement, rating_a)
        result_b = self.calculate_fit(requirement, rating_b)

        # Determine winner for each category
        comparison = {
            "rating_a": {
                "id": rating_a.id,
                "designation": rating_a.rating_designation,
                "overall_score": result_a.overall_fit_score,
                "recommendation": result_a.fit_recommendation.value,
            },
            "rating_b": {
                "id": rating_b.id,
                "designation": rating_b.rating_designation,
                "overall_score": result_b.overall_fit_score,
                "recommendation": result_b.fit_recommendation.value,
            },
            "category_winners": {
                "power": (
                    "A" if result_a.power_fit_score >= result_b.power_fit_score else "B"
                ),
                "duty": (
                    "A" if result_a.duty_fit_score >= result_b.duty_fit_score else "B"
                ),
                "emission": (
                    "A"
                    if result_a.emission_fit_score >= result_b.emission_fit_score
                    else "B"
                ),
                "application": (
                    "A"
                    if result_a.application_fit_score >= result_b.application_fit_score
                    else "B"
                ),
                "physical": (
                    "A"
                    if result_a.physical_fit_score >= result_b.physical_fit_score
                    else "B"
                ),
                "fuel": (
                    "A" if result_a.fuel_fit_score >= result_b.fuel_fit_score else "B"
                ),
            },
            "overall_winner": (
                "A"
                if result_a.overall_fit_score > result_b.overall_fit_score
                else (
                    "B"
                    if result_b.overall_fit_score > result_a.overall_fit_score
                    else "TIE"
                )
            ),
            "score_difference": abs(
                result_a.overall_fit_score - result_b.overall_fit_score
            ),
        }

        return comparison

    def compare_fit(
        self,
        requirement: CustomerRequirement,
        our_ratings: list[EngineRating],
        competitor_ratings: list[EngineRating],
    ) -> dict:
        """
        Compare our best-fit engine against competitor's best-fit engine
        for the same customer requirement.

        This enables bidirectional product fit analysis:
        "How does our best engine compare to their best engine for this customer?"

        Args:
            requirement: Customer requirement to match against
            our_ratings: List of our (MTU/RRPS) engine ratings
            competitor_ratings: List of competitor engine ratings

        Returns:
            Dict with our_fit, competitor_fit, advantage_areas, gap_areas,
            and narrative summary. Returns insufficient_data flag when
            either side has no ratings.
        """
        if not our_ratings or not competitor_ratings:
            return {
                "insufficient_data": True,
                "our_fit": None,
                "competitor_fit": None,
                "reason": (
                    "Missing our ratings" if not our_ratings
                    else "Missing competitor ratings"
                ),
            }

        # Find best fit on each side
        our_best = self.find_best_fit(requirement, our_ratings, min_score=0.0)
        competitor_best = self.find_best_fit(
            requirement, competitor_ratings, min_score=0.0
        )

        if not our_best or not competitor_best:
            return {
                "insufficient_data": True,
                "our_fit": None,
                "competitor_fit": None,
                "reason": "Could not calculate fit scores",
            }

        # Find the actual rating objects for designations
        our_rating = next(
            (r for r in our_ratings if r.id == our_best.engine_rating_id), None
        )
        competitor_rating = next(
            (r for r in competitor_ratings if r.id == competitor_best.engine_rating_id),
            None,
        )

        # Determine advantage and gap areas
        advantage_areas = []
        gap_areas = []
        parity_areas = []

        score_pairs = [
            ("power", our_best.power_fit_score, competitor_best.power_fit_score),
            ("duty_class", our_best.duty_fit_score, competitor_best.duty_fit_score),
            ("emission", our_best.emission_fit_score, competitor_best.emission_fit_score),
            ("application", our_best.application_fit_score, competitor_best.application_fit_score),
            ("physical", our_best.physical_fit_score, competitor_best.physical_fit_score),
            ("fuel", our_best.fuel_fit_score, competitor_best.fuel_fit_score),
        ]

        for category, our_score, their_score in score_pairs:
            delta = our_score - their_score
            if delta > 5:
                advantage_areas.append(category)
            elif delta < -5:
                gap_areas.append(category)
            else:
                parity_areas.append(category)

        # Overall position
        score_delta = our_best.overall_fit_score - competitor_best.overall_fit_score
        if score_delta > 5:
            position = "ADVANTAGE"
        elif score_delta < -5:
            position = "GAP"
        else:
            position = "PARITY"

        return {
            "insufficient_data": False,
            "our_fit": {
                "score": our_best.overall_fit_score,
                "recommendation": our_best.fit_recommendation.value,
                "engine": our_rating.rating_designation if our_rating else "Unknown",
            },
            "competitor_fit": {
                "score": competitor_best.overall_fit_score,
                "recommendation": competitor_best.fit_recommendation.value,
                "engine": (
                    competitor_rating.rating_designation
                    if competitor_rating
                    else "Unknown"
                ),
            },
            "position": position,
            "score_delta": round(score_delta, 2),
            "advantage_areas": advantage_areas,
            "gap_areas": gap_areas,
            "parity_areas": parity_areas,
        }


# =============================================================================
# THREAD-SAFE SINGLETON INSTANCE
# =============================================================================


_scoring_service_instance: Optional[ProductFitScoringService] = None


def get_product_fit_scoring_service(
    weights: Optional[ProductFitWeights] = None,
) -> ProductFitScoringService:
    """
    Get thread-safe singleton instance of ProductFitScoringService.

    Uses double-checked locking for thread safety without
    performance impact on subsequent calls.

    Args:
        weights: Optional custom weights (only used on first call)

    Returns:
        ProductFitScoringService instance
    """
    global _scoring_service_instance

    # Fast path: already initialized
    if _scoring_service_instance is not None:
        return _scoring_service_instance

    # Slow path: need to initialize with lock
    with _service_lock:
        # Double-check after acquiring lock
        if _scoring_service_instance is None:
            _scoring_service_instance = ProductFitScoringService(weights=weights)
        return _scoring_service_instance


def reset_scoring_service() -> None:
    """Reset singleton instance (for testing). Thread-safe."""
    global _scoring_service_instance
    with _service_lock:
        _scoring_service_instance = None
