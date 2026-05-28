"""
Unified Knowledge Base Models - Rating-Level Product Fit

Extends the base KB models (models.py) with rating-level data structures
for apple-to-apple competitive comparison and product fit scoring.

ADR Reference: ADR-004 Unified Knowledge Base Architecture

Data Sources:
- ISO 8528 (Generator set performance classifications)
- ISO 3046 (Reciprocating internal combustion engines)
- IMP Corporation Marine Engine Duty Ratings
- Manufacturer datasheets (MTU, Cummins, Caterpillar, MAN, etc.)

Tables Added (Migration 002):
- kb_engine_ratings: Individual duty ratings per engine model
- kb_customer_requirements: Structured customer requirements
- kb_rating_competitor_map: Rating-level competitive mapping
- kb_competitor_engagements: Competitor activity at our customers
- kb_product_fit_results: Cached fit scoring results
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional

# =============================================================================
# ENUMS (Match SQL ENUM types from migration 002)
# =============================================================================


class DutyClass(str, Enum):
    """
    Marine engine duty class per ISO 8528 and industry standards.

    Reference: https://www.impcorporation.com/blog/marine-engine-duty-ratings

    These classifications determine appropriate engine-to-application matching
    based on expected operating profile.
    """

    CONTINUOUS = "continuous"
    """80-100% load, 5000-8000 hrs/year, unlimited full power.
    Applications: Freighters, tugboats, dredges with displacement hulls."""

    HEAVY_DUTY = "heavy_duty"
    """40-80% load, 3000-5000 hrs/year, 8 of 10 hours full power.
    Applications: Fishing trawlers, ferries, thrusters, auxiliary systems."""

    MEDIUM_DUTY = "medium_duty"
    """20-80% load, 2000-4000 hrs/year, 6 of 12 hours full power.
    Applications: Ferries, harbor tugs, offshore service vessels."""

    LIGHT_DUTY = "light_duty"
    """Up to 50% load, 1000-3000 hrs/year, 2 of 8 hours full power.
    Applications: Patrol boats, emergency fire pumps."""

    PLEASURE = "pleasure"
    """Up to 30% load, 250-1000 hrs/year, 1 of 8 hours full power.
    Applications: Pleasure craft, sportfishing vessels."""

    INTERMITTENT = "intermittent"
    """Variable duty cycles. Applications: Generator standby, peak shaving."""

    @classmethod
    def from_annual_hours(cls, hours: int) -> "DutyClass":
        """Infer duty class from annual operating hours."""
        if hours >= 5000:
            return cls.CONTINUOUS
        elif hours >= 3000:
            return cls.HEAVY_DUTY
        elif hours >= 2000:
            return cls.MEDIUM_DUTY
        elif hours >= 1000:
            return cls.LIGHT_DUTY
        else:
            return cls.PLEASURE

    @property
    def typical_hours_range(self) -> tuple[int, int]:
        """Return typical annual hours range for this duty class."""
        ranges = {
            self.CONTINUOUS: (5000, 8000),
            self.HEAVY_DUTY: (3000, 5000),
            self.MEDIUM_DUTY: (2000, 4000),
            self.LIGHT_DUTY: (1000, 3000),
            self.PLEASURE: (250, 1000),
            self.INTERMITTENT: (100, 2000),
        }
        return ranges.get(self, (0, 8000))

    @property
    def typical_load_factor_range(self) -> tuple[float, float]:
        """Return typical load factor range for this duty class."""
        ranges = {
            self.CONTINUOUS: (0.80, 1.00),
            self.HEAVY_DUTY: (0.40, 0.80),
            self.MEDIUM_DUTY: (0.20, 0.80),
            self.LIGHT_DUTY: (0.00, 0.50),
            self.PLEASURE: (0.00, 0.30),
            self.INTERMITTENT: (0.00, 1.00),
        }
        return ranges.get(self, (0.00, 1.00))


class ISOClassification(str, Enum):
    """ISO 8528 generator set performance classifications."""

    ISO_8528_COP = "iso_8528_cop"
    """Continuous Power: 100% average load, 10% overload capability."""

    ISO_8528_PRP = "iso_8528_prp"
    """Prime Power: ≤80% average load, unlimited operating time."""

    ISO_8528_LTP = "iso_8528_ltp"
    """Limited Time Power: Standby/emergency applications only."""

    NOT_APPLICABLE = "not_applicable"
    """For propulsion applications (not generator sets)."""


class HarmonizedDutyClass(str, Enum):
    """
    ISO 8528-1:2018 aligned harmonized duty classification.

    This enum provides a standardized 6-tier duty classification system
    based on ISO 8528-1:2018 power rating categories, enabling apple-to-apple
    comparison across different OEM rating systems.

    Reference: ISO 8528-1:2018(E) Third Edition
    License: Integrum Pte Ltd / SS Foo - Order OP-1014241

    OEM Mapping (see kb_oem_duty_mappings table):
    - MTU: 1A→CON, 1B→HVY, 1D→MED, 1DS→LGT
    - Cummins: CON→CON, HD→HVY, MCD→MED, LD→LGT, INT→INT, PLS→PLS
    - Caterpillar: A→CON, B→HVY, C→MED, D→LGT, E→PLS
    - MAN: Heavy→CON/HVY, Medium→MED, Light→LGT
    - Volvo: Rating 1→CON, 2→HVY, 3→MED, 4→LGT, 5→PLS
    """

    CON = "CON"
    """Continuous (ISO COP equivalent).
    - Load Factor: 80-100% (constant)
    - Annual Hours: Unlimited
    - ISO Reference: Clause 14.3.2
    - Applications: Cargo ships, tankers, tugboats, dredgers
    """

    HVY = "HVY"
    """Heavy Duty (ISO PRP high utilization).
    - Load Factor: 60-80%
    - Annual Hours: 3,000-5,000
    - Peak Power: 10 of 12 hours
    - Overload: 10% for 1hr/12hrs
    - ISO Reference: Clause 14.3.3 (high utilization)
    - Applications: Ferries, fishing trawlers, OSVs
    """

    MED = "MED"
    """Medium Duty (ISO PRP standard utilization).
    - Load Factor: 40-60%
    - Annual Hours: 2,000-4,000
    - Peak Power: 6 of 12 hours
    - Overload: 10% for 1hr/12hrs
    - ISO Reference: Clause 14.3.3 (standard utilization)
    - Applications: Harbor tugs, fast supply boats, research vessels
    """

    LGT = "LGT"
    """Light Duty (ISO LTP/PRP low utilization).
    - Load Factor: 20-50%
    - Annual Hours: 500-3,000
    - Peak Power: 2 of 8 hours
    - Overload: 10% for 1hr/12hrs
    - ISO Reference: Clause 14.3.4 / 14.3.3 (low utilization)
    - Applications: Patrol boats, pilot boats, crew transfer vessels
    """

    INT = "INT"
    """Intermittent (ISO ESP equivalent).
    - Load Factor: 10-40%
    - Annual Hours: 200-500
    - ISO Reference: Clause 14.3.5
    - Applications: Standby gensets, thrusters, peak shaving
    """

    PLS = "PLS"
    """Pleasure (Below ISO ESP threshold).
    - Load Factor: 0-30%
    - Annual Hours: 100-500
    - Peak Power: 1 of 8 hours
    - Applications: Yachts, pleasure cruisers, sport fishing
    """

    @classmethod
    def from_duty_class(cls, duty_class: DutyClass) -> "HarmonizedDutyClass":
        """Convert existing DutyClass enum to HarmonizedDutyClass."""
        mapping = {
            DutyClass.CONTINUOUS: cls.CON,
            DutyClass.HEAVY_DUTY: cls.HVY,
            DutyClass.MEDIUM_DUTY: cls.MED,
            DutyClass.LIGHT_DUTY: cls.LGT,
            DutyClass.INTERMITTENT: cls.INT,
            DutyClass.PLEASURE: cls.PLS,
        }
        return mapping.get(duty_class, cls.MED)

    @classmethod
    def from_iso_rating(cls, iso_rating: str) -> "HarmonizedDutyClass":
        """Map ISO 8528-1:2018 power rating to harmonized duty class.

        Args:
            iso_rating: ISO rating code (COP, PRP, LTP, ESP, DCP, MAX)

        Returns:
            Corresponding HarmonizedDutyClass
        """
        iso_mapping = {
            "COP": cls.CON,  # Continuous Power → Continuous
            "PRP": cls.HVY,  # Prime Power → Heavy Duty (default, can be MED/LGT)
            "LTP": cls.LGT,  # Limited-Time Power → Light Duty
            "ESP": cls.INT,  # Emergency Standby → Intermittent
            "DCP": cls.CON,  # Data Centre Power → Continuous (unlimited hours)
            "MAX": cls.LGT,  # Maximum Power (low-power mode) → Light Duty
        }
        return iso_mapping.get(iso_rating.upper(), cls.MED)

    @property
    def iso_equivalent(self) -> str:
        """Return ISO 8528-1:2018 equivalent rating code."""
        equivalents = {
            self.CON: "COP",
            self.HVY: "PRP (high)",
            self.MED: "PRP (mid)",
            self.LGT: "LTP/PRP (low)",
            self.INT: "ESP",
            self.PLS: "Below ESP",
        }
        return equivalents.get(self, "N/A")

    @property
    def load_factor_range(self) -> tuple[float, float]:
        """Return typical load factor range (min, max) as decimals."""
        ranges = {
            self.CON: (0.80, 1.00),
            self.HVY: (0.60, 0.80),
            self.MED: (0.40, 0.60),
            self.LGT: (0.20, 0.50),
            self.INT: (0.10, 0.40),
            self.PLS: (0.00, 0.30),
        }
        return ranges.get(self, (0.00, 1.00))

    @property
    def annual_hours_range(self) -> tuple[int, int]:
        """Return typical annual operating hours range."""
        ranges = {
            self.CON: (5000, 8760),  # Unlimited (up to 24/7)
            self.HVY: (3000, 5000),
            self.MED: (2000, 4000),
            self.LGT: (500, 3000),
            self.INT: (200, 500),
            self.PLS: (100, 500),
        }
        return ranges.get(self, (0, 8760))


class AvailabilityStatus(str, Enum):
    """Engine rating availability status."""

    AVAILABLE = "available"
    """Currently in production and available for order."""

    FIELD_TRIAL = "field_trial"
    """In field trials, not generally available."""

    PLANNED = "planned"
    """Announced but not yet available."""

    DISCONTINUED = "discontinued"
    """No longer in production."""

    LIMITED = "limited"
    """Limited availability (regional, special order only)."""


class CompetitivePosition(str, Enum):
    """Our competitive position relative to a competitor rating."""

    STRONG_ADVANTAGE = "strong_advantage"
    """We are clearly better (>10% power density advantage, better specs)."""

    ADVANTAGE = "advantage"
    """We have a noticeable edge."""

    PARITY = "parity"
    """Roughly equivalent specifications."""

    DISADVANTAGE = "disadvantage"
    """Competitor has an edge."""

    STRONG_DISADVANTAGE = "strong_disadvantage"
    """Competitor is clearly better in this comparison."""


class ThreatLevel(str, Enum):
    """Threat level for competitor engagements."""

    CRITICAL = "critical"
    """Competitor won at our ACTIVE customer. Immediate action required."""

    HIGH = "high"
    """Competitor won at our PROSPECT. Review our proposal."""

    MEDIUM = "medium"
    """Competitor activity in our market. Monitor and assess."""

    LOW = "low"
    """Competitor activity outside our focus. Log and monitor."""

    INFORMATIONAL = "informational"
    """General market intelligence. No action required."""


class EngagementType(str, Enum):
    """Type of competitor engagement at a customer."""

    CONTRACT_WIN = "contract_win"
    """Competitor won a contract."""

    PROPOSAL = "proposal"
    """Competitor submitted a proposal."""

    DEMO = "demo"
    """Competitor conducting demonstration or trials."""

    PARTNERSHIP = "partnership"
    """Competitor formed partnership with customer."""

    RUMORED = "rumored"
    """Unconfirmed activity (needs verification)."""

    LOST_TO_US = "lost_to_us"
    """We won against this competitor (positive outcome)."""


class FitRecommendation(str, Enum):
    """Product fit recommendation level based on fit score."""

    STRONG_FIT = "strong_fit"
    """90-100% fit score. Perfect match, proceed with confidence."""

    GOOD_FIT = "good_fit"
    """75-89% fit score. Strong fit, recommended."""

    ACCEPTABLE = "acceptable"
    """60-74% fit score. Acceptable, review alternatives."""

    MARGINAL = "marginal"
    """40-59% fit score. May work with caveats, needs evaluation."""

    NOT_SUITABLE = "not_suitable"
    """<40% fit score. Does not meet requirements."""

    @classmethod
    def from_score(cls, score: float) -> "FitRecommendation":
        """Determine recommendation from fit score (0-100)."""
        if score >= 90:
            return cls.STRONG_FIT
        elif score >= 75:
            return cls.GOOD_FIT
        elif score >= 60:
            return cls.ACCEPTABLE
        elif score >= 40:
            return cls.MARGINAL
        else:
            return cls.NOT_SUITABLE


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class EngineRating:
    """
    Individual duty rating for an engine model.

    This is the ATOMIC UNIT for product comparison - not the engine model!

    Example: MAN D3872 has multiple ratings:
    - LE427: 920 kW @ 1,800 RPM (Heavy-Duty, Continuous Commercial)
    - LE432: 1,213 kW @ 2,100 RPM (Medium-Duty, Workboats/Ferries)
    - LE433: 1,471 kW @ 2,300 RPM (Light-Duty, Fast Vessels)
    - LE433 Max: 1,618 kW @ 2,300 RPM (Light-Duty Max, High Performance)

    Comparisons should be: MAN D3872 LE432 vs MTU 12V 2000 M96
    NOT: MAN D3872 vs MTU Series 2000
    """

    id: str
    engine_model_id: str  # FK to kb_engine_models

    # Rating Identity
    rating_designation: str  # e.g., "LE432", "M96", "M93"
    rating_name: Optional[str] = None  # Full name if different

    # ISO/Industry Classification
    duty_class: DutyClass = DutyClass.MEDIUM_DUTY
    iso_classification: ISOClassification = ISOClassification.NOT_APPLICABLE

    # ISO 8528-1:2018 Harmonized Classification (NEW)
    # Enables cross-OEM comparison using standardized codes
    harmonized_duty_class: Optional[str] = None  # CON, HVY, MED, LGT, INT, PLS
    oem_rating_code: Optional[str] = None  # Original OEM code (e.g., "M93", "HD", "B")

    # Performance at THIS Rating (single values, NOT ranges!)
    power_kw: float = 0.0
    power_hp: Optional[float] = None
    rpm: int = 0

    # Operating Limits
    load_factor_min: float = 0.0
    load_factor_max: float = 1.0
    full_power_hours_per_cycle: Optional[int] = None
    cycle_hours: Optional[int] = None
    annual_hours_min: Optional[int] = None
    annual_hours_max: Optional[int] = None

    # Physical Characteristics
    dry_weight_kg: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    power_density_kw_per_kg: Optional[float] = None

    # Fuel and Emissions
    fuel_types: Optional[str] = None  # JSON array
    emission_tier: Optional[str] = None
    aftertreatment_required: Optional[str] = None
    nox_g_kwh: Optional[float] = None
    pm_g_kwh: Optional[float] = None

    # Application Suitability
    application_profiles: Optional[str] = None  # JSON array
    primary_applications: Optional[str] = None  # JSON array

    # Availability
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    availability_date: Optional[date] = None
    regions_available: Optional[str] = None  # JSON array

    # Data Provenance (CRITICAL: all data must be verifiable)
    data_source: str = "manufacturer_datasheet"
    data_source_url: Optional[str] = None
    data_source_document: Optional[str] = None
    data_confidence: float = 0.90
    last_verified: Optional[datetime] = None
    verified_by: Optional[str] = None

    # Metadata
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "engine_model_id": self.engine_model_id,
            "rating_designation": self.rating_designation,
            "rating_name": self.rating_name,
            "duty_class": (
                self.duty_class.value
                if isinstance(self.duty_class, DutyClass)
                else self.duty_class
            ),
            "iso_classification": (
                self.iso_classification.value
                if isinstance(self.iso_classification, ISOClassification)
                else self.iso_classification
            ),
            "harmonized_duty_class": self.harmonized_duty_class,
            "oem_rating_code": self.oem_rating_code,
            "power_kw": self.power_kw,
            "power_hp": self.power_hp,
            "rpm": self.rpm,
            "load_factor_min": self.load_factor_min,
            "load_factor_max": self.load_factor_max,
            "full_power_hours_per_cycle": self.full_power_hours_per_cycle,
            "cycle_hours": self.cycle_hours,
            "annual_hours_min": self.annual_hours_min,
            "annual_hours_max": self.annual_hours_max,
            "dry_weight_kg": self.dry_weight_kg,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "power_density_kw_per_kg": self.power_density_kw_per_kg,
            "fuel_types": self.fuel_types,
            "emission_tier": self.emission_tier,
            "aftertreatment_required": self.aftertreatment_required,
            "application_profiles": self.application_profiles,
            "primary_applications": self.primary_applications,
            "availability_status": (
                self.availability_status.value
                if isinstance(self.availability_status, AvailabilityStatus)
                else self.availability_status
            ),
            "availability_date": (
                self.availability_date.isoformat() if self.availability_date else None
            ),
            "regions_available": self.regions_available,
            "data_source": self.data_source,
            "data_source_url": self.data_source_url,
            "data_source_document": self.data_source_document,
            "data_confidence": self.data_confidence,
            "last_verified": (
                self.last_verified.isoformat() if self.last_verified else None
            ),
            "verified_by": self.verified_by,
            "notes": self.notes,
        }

    def get_fuel_types_list(self) -> list[str]:
        """Parse fuel_types JSON to list."""
        if not self.fuel_types:
            return []
        try:
            return json.loads(self.fuel_types)
        except json.JSONDecodeError:
            return []

    def get_application_profiles_list(self) -> list[str]:
        """Parse application_profiles JSON to list."""
        if not self.application_profiles:
            return []
        try:
            return json.loads(self.application_profiles)
        except json.JSONDecodeError:
            return []

    def calculate_power_density(self) -> Optional[float]:
        """Calculate and return power density (kW/kg)."""
        if self.power_kw and self.dry_weight_kg and self.dry_weight_kg > 0:
            return round(self.power_kw / self.dry_weight_kg, 4)
        return None


@dataclass
class CustomerRequirement:
    """
    Structured customer requirement for product fit matching.

    This model captures all the information needed to match engines
    to customer needs using deterministic scoring rules.
    """

    id: str
    customer_name: str

    # Customer Identity (links to SAP/CRM)
    customer_id: Optional[str] = None  # SAP KUNNR
    opportunity_id: Optional[str] = None  # CEC opportunity
    project_name: Optional[str] = None

    # Power Requirements
    power_required_kw: float = 0.0
    power_tolerance_pct: float = 15.0
    power_configuration: Optional[str] = None  # "single", "twin", "triple"
    total_installed_power_kw: Optional[float] = None

    # Operating Profile
    duty_class_required: Optional[DutyClass] = None
    annual_operating_hours: Optional[int] = None
    typical_load_factor: Optional[float] = None
    peak_load_duration_hours: Optional[int] = None

    # Vessel/Application Context
    vessel_type: Optional[str] = None
    vessel_name: Optional[str] = None
    vessel_length_m: Optional[float] = None
    vessel_beam_m: Optional[float] = None
    application: Optional[str] = None  # "propulsion", "genset", "auxiliary"
    new_build_or_repower: Optional[str] = None  # "new_build", "repower"

    # Environmental Requirements
    emission_tier_required: Optional[str] = None
    eca_operation: bool = False
    alternative_fuel_required: bool = False

    # Fuel Preferences
    fuel_type_preference: Optional[str] = None  # JSON array
    fuel_type_mandatory: Optional[str] = None  # JSON array

    # Physical Constraints
    max_engine_weight_kg: Optional[float] = None
    max_engine_length_mm: Optional[float] = None
    max_engine_width_mm: Optional[float] = None
    max_engine_height_mm: Optional[float] = None
    engine_room_constraints: Optional[str] = None

    # Commercial Context
    budget_level: Optional[str] = None  # "premium", "mid_range", "value"
    decision_timeline: Optional[str] = None
    competitor_under_consideration: Optional[str] = None  # JSON array

    # Geographic Context
    region: Optional[str] = None
    country: Optional[str] = None
    port_of_registry: Optional[str] = None
    flag_state: Optional[str] = None
    classification_society: Optional[str] = None

    # Status
    status: str = "active"
    fit_analysis_completed: bool = False

    # Metadata
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "opportunity_id": self.opportunity_id,
            "project_name": self.project_name,
            "power_required_kw": self.power_required_kw,
            "power_tolerance_pct": self.power_tolerance_pct,
            "power_configuration": self.power_configuration,
            "total_installed_power_kw": self.total_installed_power_kw,
            "duty_class_required": (
                self.duty_class_required.value
                if isinstance(self.duty_class_required, DutyClass)
                else self.duty_class_required
            ),
            "annual_operating_hours": self.annual_operating_hours,
            "typical_load_factor": self.typical_load_factor,
            "peak_load_duration_hours": self.peak_load_duration_hours,
            "vessel_type": self.vessel_type,
            "vessel_name": self.vessel_name,
            "vessel_length_m": self.vessel_length_m,
            "vessel_beam_m": self.vessel_beam_m,
            "application": self.application,
            "new_build_or_repower": self.new_build_or_repower,
            "emission_tier_required": self.emission_tier_required,
            "eca_operation": self.eca_operation,
            "alternative_fuel_required": self.alternative_fuel_required,
            "fuel_type_preference": self.fuel_type_preference,
            "fuel_type_mandatory": self.fuel_type_mandatory,
            "max_engine_weight_kg": self.max_engine_weight_kg,
            "max_engine_length_mm": self.max_engine_length_mm,
            "max_engine_width_mm": self.max_engine_width_mm,
            "max_engine_height_mm": self.max_engine_height_mm,
            "engine_room_constraints": self.engine_room_constraints,
            "budget_level": self.budget_level,
            "decision_timeline": self.decision_timeline,
            "competitor_under_consideration": self.competitor_under_consideration,
            "region": self.region,
            "country": self.country,
            "port_of_registry": self.port_of_registry,
            "flag_state": self.flag_state,
            "classification_society": self.classification_society,
            "status": self.status,
            "fit_analysis_completed": self.fit_analysis_completed,
            "created_by": self.created_by,
            "notes": self.notes,
        }

    def get_fuel_preference_list(self) -> list[str]:
        """Parse fuel_type_preference JSON to list."""
        if not self.fuel_type_preference:
            return []
        try:
            return json.loads(self.fuel_type_preference)
        except json.JSONDecodeError:
            return []

    def get_power_range(self) -> tuple[float, float]:
        """Get acceptable power range based on tolerance."""
        tolerance = self.power_tolerance_pct / 100.0
        min_power = self.power_required_kw * (1 - tolerance)
        max_power = self.power_required_kw * (1 + tolerance)
        return (min_power, max_power)


@dataclass
class RatingCompetitorMap:
    """
    Apple-to-apple competitive mapping at the RATING level.

    Maps our engine rating to competitor engine rating for proper comparison.
    Example: MTU 12V 2000 M96 vs MAN D3872 LE432 (both ~1200-1400 kW, Medium-Duty)
    """

    id: str
    our_rating_id: str  # FK to our EngineRating
    competitor_rating_id: str  # FK to competitor EngineRating

    # Comparison Metrics
    power_delta_kw: Optional[float] = None  # Competitor - Ours
    power_delta_pct: Optional[float] = None
    power_density_delta: Optional[float] = None
    rpm_delta: Optional[int] = None
    weight_delta_kg: Optional[float] = None

    # Competitive Assessment
    competitive_position: Optional[CompetitivePosition] = None
    price_positioning: Optional[str] = None  # "premium", "parity", "value"

    # Where They Compete
    overlapping_applications: Optional[str] = None  # JSON array
    overlapping_regions: Optional[str] = None  # JSON array
    overlapping_duty_classes: Optional[str] = None  # JSON array

    # Threat Assessment
    threat_level: ThreatLevel = ThreatLevel.MEDIUM
    win_rate_against_pct: Optional[float] = None

    # Analysis
    our_advantages: Optional[str] = None  # JSON array
    their_advantages: Optional[str] = None  # JSON array
    key_differentiators: Optional[str] = None
    recommended_positioning: Optional[str] = None

    # Data Quality
    last_competitive_review: Optional[date] = None
    reviewed_by: Optional[str] = None

    # Metadata
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "our_rating_id": self.our_rating_id,
            "competitor_rating_id": self.competitor_rating_id,
            "power_delta_kw": self.power_delta_kw,
            "power_delta_pct": self.power_delta_pct,
            "power_density_delta": self.power_density_delta,
            "rpm_delta": self.rpm_delta,
            "weight_delta_kg": self.weight_delta_kg,
            "competitive_position": (
                self.competitive_position.value
                if isinstance(self.competitive_position, CompetitivePosition)
                else self.competitive_position
            ),
            "price_positioning": self.price_positioning,
            "overlapping_applications": self.overlapping_applications,
            "overlapping_regions": self.overlapping_regions,
            "overlapping_duty_classes": self.overlapping_duty_classes,
            "threat_level": (
                self.threat_level.value
                if isinstance(self.threat_level, ThreatLevel)
                else self.threat_level
            ),
            "win_rate_against_pct": self.win_rate_against_pct,
            "our_advantages": self.our_advantages,
            "their_advantages": self.their_advantages,
            "key_differentiators": self.key_differentiators,
            "recommended_positioning": self.recommended_positioning,
            "last_competitive_review": (
                self.last_competitive_review.isoformat()
                if self.last_competitive_review
                else None
            ),
            "reviewed_by": self.reviewed_by,
            "notes": self.notes,
        }


@dataclass
class CompetitorEngagement:
    """
    Track competitor activity at our customers.

    Links competitor intelligence signals to SAP customer data
    for threat assessment and sales action.
    """

    id: str
    customer_name: str
    competitor: str
    engagement_type: EngagementType
    threat_level: ThreatLevel

    # Customer Identity
    customer_id: Optional[str] = None  # SAP KUNNR
    is_our_customer: bool = False
    customer_relationship: Optional[str] = None  # "active", "prospect", "former"

    # Competitor Details
    competitor_rating_id: Optional[str] = None  # FK to EngineRating
    competitor_engine_name: Optional[str] = None

    # Engagement Details
    engagement_date: Optional[date] = None
    engagement_value_usd: Optional[float] = None
    vessel_name: Optional[str] = None
    vessel_type: Optional[str] = None
    quantity: int = 1

    # Source Intelligence
    source_signal_id: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_confidence: Optional[float] = None

    # Impact Analysis
    our_competing_rating_id: Optional[str] = None  # FK to our EngineRating
    our_engine_name: Optional[str] = None
    loss_reason: Optional[str] = None

    # Threat Details
    threat_reason: Optional[str] = None

    # Actions
    requires_sales_action: bool = False
    action_recommendation: Optional[str] = None
    action_due_date: Optional[date] = None

    # Notifications
    sales_rep_notified: bool = False
    notified_at: Optional[datetime] = None
    notified_to: Optional[str] = None

    # Resolution
    resolution_status: str = "open"
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None

    # Geographic
    region: Optional[str] = None
    country: Optional[str] = None

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "is_our_customer": self.is_our_customer,
            "customer_relationship": self.customer_relationship,
            "competitor": self.competitor,
            "competitor_rating_id": self.competitor_rating_id,
            "competitor_engine_name": self.competitor_engine_name,
            "engagement_type": (
                self.engagement_type.value
                if isinstance(self.engagement_type, EngagementType)
                else self.engagement_type
            ),
            "engagement_date": (
                self.engagement_date.isoformat() if self.engagement_date else None
            ),
            "engagement_value_usd": self.engagement_value_usd,
            "vessel_name": self.vessel_name,
            "vessel_type": self.vessel_type,
            "quantity": self.quantity,
            "source_signal_id": self.source_signal_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_confidence": self.source_confidence,
            "our_competing_rating_id": self.our_competing_rating_id,
            "our_engine_name": self.our_engine_name,
            "loss_reason": self.loss_reason,
            "threat_level": (
                self.threat_level.value
                if isinstance(self.threat_level, ThreatLevel)
                else self.threat_level
            ),
            "threat_reason": self.threat_reason,
            "requires_sales_action": self.requires_sales_action,
            "action_recommendation": self.action_recommendation,
            "action_due_date": (
                self.action_due_date.isoformat() if self.action_due_date else None
            ),
            "sales_rep_notified": self.sales_rep_notified,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "notified_to": self.notified_to,
            "resolution_status": self.resolution_status,
            "resolution_notes": self.resolution_notes,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "region": self.region,
            "country": self.country,
            "created_by": self.created_by,
        }


@dataclass
class ProductFitResult:
    """
    Result of product fit analysis for a customer requirement.

    Contains overall fit score and component scores with explanations.
    """

    id: str
    requirement_id: str  # FK to CustomerRequirement
    engine_rating_id: str  # FK to EngineRating

    # Overall Score
    overall_fit_score: float  # 0-100
    fit_recommendation: FitRecommendation

    # Component Scores (0-100 each, weighted)
    power_fit_score: Optional[float] = None
    power_fit_detail: Optional[str] = None

    duty_fit_score: Optional[float] = None
    duty_fit_detail: Optional[str] = None

    emission_fit_score: Optional[float] = None
    emission_fit_detail: Optional[str] = None

    application_fit_score: Optional[float] = None
    application_fit_detail: Optional[str] = None

    physical_fit_score: Optional[float] = None
    physical_fit_detail: Optional[str] = None

    fuel_fit_score: Optional[float] = None
    fuel_fit_detail: Optional[str] = None

    # Explanation
    positive_factors: Optional[str] = None  # JSON array
    negative_factors: Optional[str] = None  # JSON array
    gap_factors: Optional[str] = None  # JSON array

    # Ranking
    rank_for_requirement: Optional[int] = None

    # Alternatives
    alternative_ratings: Optional[str] = None  # JSON array

    # Metadata
    scoring_algorithm_version: str = "v1"
    scored_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "requirement_id": self.requirement_id,
            "engine_rating_id": self.engine_rating_id,
            "overall_fit_score": self.overall_fit_score,
            "fit_recommendation": (
                self.fit_recommendation.value
                if isinstance(self.fit_recommendation, FitRecommendation)
                else self.fit_recommendation
            ),
            "power_fit_score": self.power_fit_score,
            "power_fit_detail": self.power_fit_detail,
            "duty_fit_score": self.duty_fit_score,
            "duty_fit_detail": self.duty_fit_detail,
            "emission_fit_score": self.emission_fit_score,
            "emission_fit_detail": self.emission_fit_detail,
            "application_fit_score": self.application_fit_score,
            "application_fit_detail": self.application_fit_detail,
            "physical_fit_score": self.physical_fit_score,
            "physical_fit_detail": self.physical_fit_detail,
            "fuel_fit_score": self.fuel_fit_score,
            "fuel_fit_detail": self.fuel_fit_detail,
            "positive_factors": self.positive_factors,
            "negative_factors": self.negative_factors,
            "gap_factors": self.gap_factors,
            "rank_for_requirement": self.rank_for_requirement,
            "alternative_ratings": self.alternative_ratings,
            "scoring_algorithm_version": self.scoring_algorithm_version,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
        }

    def get_positive_factors_list(self) -> list[str]:
        """Parse positive_factors JSON to list."""
        if not self.positive_factors:
            return []
        try:
            return json.loads(self.positive_factors)
        except json.JSONDecodeError:
            return []

    def get_negative_factors_list(self) -> list[str]:
        """Parse negative_factors JSON to list."""
        if not self.negative_factors:
            return []
        try:
            return json.loads(self.negative_factors)
        except json.JSONDecodeError:
            return []


# =============================================================================
# SCORING WEIGHTS (Configurable, but with sensible defaults)
# =============================================================================


@dataclass
class ProductFitWeights:
    """
    Weights for product fit scoring components.

    These weights determine how much each factor contributes to the overall fit score.
    Must sum to 1.0 (100%).

    Updated in Phase 3 to include propeller matching and classification society scoring.
    """

    power_weight: float = 0.25  # Power match is most important
    application_weight: float = 0.20  # Application suitability
    duty_weight: float = 0.15  # Duty class match
    propeller_weight: float = 0.15  # Propeller/gearbox matching (NEW in Phase 3)
    emission_weight: float = 0.10  # Emission tier compliance
    physical_weight: float = 0.05  # Weight/size constraints
    fuel_weight: float = 0.05  # Fuel compatibility
    classification_weight: float = (
        0.05  # Classification society type approval (NEW in Phase 3)
    )

    def validate(self) -> bool:
        """Validate weights sum to 1.0."""
        total = (
            self.power_weight
            + self.application_weight
            + self.duty_weight
            + self.propeller_weight
            + self.emission_weight
            + self.physical_weight
            + self.fuel_weight
            + self.classification_weight
        )
        return abs(total - 1.0) < 0.001


# Default weights instance
DEFAULT_FIT_WEIGHTS = ProductFitWeights()
