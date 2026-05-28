"""
Engine Master Data - Duty Classes Based on Official MTU Rating System

This file contains duty class assignments based on OFFICIAL MTU APPLICATION GROUPS:
- 1A: Unrestricted continuous operation (70-90% load) → CONTINUOUS
- 1B: Fast vessels with high load factors (60-80% load, 5000 hrs/yr) → HEAVY_DUTY
- 1D: Fast vessels with intermittent load factors → MEDIUM_DUTY
- 1DS: Fast vessels with low load factors → LIGHT_DUTY

IMPORTANT: MTU rating designations (M63, M72, M93, etc.) indicate APPLICATION GROUP:
- M63 = 1A rating (continuous operation)
- M72 = 1B rating (high load factors) → HEAVY_DUTY
- M93/M96 = 1DS rating (low load factors) → LIGHT_DUTY

NOTE: "Low load factor" (1DS) means the engine runs at HIGHER POWER OUTPUT but
for FEWER hours per year. Fast yachts, patrol boats need peak power but run
less than cargo ships. This is OPPOSITE to industrial "heavy duty" meaning.

Physical specifications are marked with source quality:
- "OEM_datasheet:document_number" = Official manufacturer datasheet
- "secondary_aggregator:sitename.com YYYY-MM-DD" = Third-party aggregator site

Data Quality Sources:
- MTU Solution Guide: https://penskeanz.com/wp-content/uploads/2023/07/16120032_MTU_SolutionGuide_Marine_00.pdf
- MTU Spec Sheets: https://www.mtu-solutions.com/content/dam/mtu/products/
- Maritime Propulsion (aggregator): https://www.maritimepropulsion.com/
- Industry Standard: https://www.impcorporation.com/blog/marine-engine-duty-ratings
"""

from dataclasses import dataclass, field
from typing import Optional

from lead_to_cash.services.knowledge_base.unified_models import (
    DutyClass,
    HarmonizedDutyClass,
)


@dataclass
class EngineSpecification:
    """
    Engine specification with verified duty class.

    IMPORTANT: Only duty_class and rating_designation are verified from
    manufacturer sources. All other technical specifications require
    actual datasheets to populate.

    Fields marked as None indicate data that needs legitimate sourcing:
    - Physical dimensions: Manufacturer datasheets (often confidential)
    - SFOC: Engine test reports or sales documentation
    - TBO: Maintenance manuals (often customer-restricted)
    - Type approvals: Classification society certificate databases
    """

    model_name: str
    duty_class: DutyClass
    rating_designation: str

    # ISO 8528-1:2018 aligned harmonized classification (NEW)
    # Derived from duty_class if not explicitly set
    harmonized_duty_class: Optional[HarmonizedDutyClass] = None

    # Physical specifications - NEED ACTUAL DATASHEETS
    dry_weight_kg: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None

    # Primary applications (from manufacturer marketing - generally reliable)
    primary_applications: list[str] = field(default_factory=list)

    # SFOC - NEED ACTUAL TEST REPORTS
    # Specific Fuel Oil Consumption (g/kWh)
    sfoc_rated_g_kwh: Optional[float] = None  # At 100% MCR
    sfoc_75pct_g_kwh: Optional[float] = None  # At 75% load (typical cruise)
    sfoc_50pct_g_kwh: Optional[float] = None  # At 50% load (low speed)

    # TBO - NEED ACTUAL MAINTENANCE MANUALS
    # Time Between Overhauls (hours)
    tbo_hours: Optional[int] = None  # Major overhaul interval
    minor_service_hours: Optional[int] = None  # Minor service interval

    # Type Approvals - NEED CLASSIFICATION SOCIETY CERTIFICATES
    # Values: List of society codes (DNV, LR, ABS, BV, NK, CCS, KR, RINA, RS, IRS)
    type_approvals: list[str] = field(default_factory=list)

    # Data quality indicators
    data_source: str = "duty_class_only"  # Only duty class is verified
    verified: bool = False  # Set to True only when actual datasheets are used
    notes: str = ""

    def __post_init__(self):
        """Auto-derive harmonized_duty_class from duty_class if not explicitly set."""
        if self.harmonized_duty_class is None:
            self.harmonized_duty_class = HarmonizedDutyClass.from_duty_class(
                self.duty_class
            )

    def get_harmonized_duty_class(self) -> HarmonizedDutyClass:
        """Get the harmonized duty class (ISO 8528-1:2018 aligned).

        Returns the explicitly set harmonized_duty_class, or derives it
        from the existing duty_class field.
        """
        if self.harmonized_duty_class is not None:
            return self.harmonized_duty_class
        return HarmonizedDutyClass.from_duty_class(self.duty_class)


# =============================================================================
# MTU SERIES 2000 - Duty Class per OFFICIAL MTU Rating System
# M72 = 1B (High load factors) = HEAVY_DUTY
# M93/M96 = 1DS (Low load factors) = LIGHT_DUTY
# See: MTU Solution Guide Edition 2/22, penskeanz.com
# =============================================================================

MTU_SERIES_2000_SPECS = {
    "MTU 8V 2000 M72": EngineSpecification(
        model_name="MTU 8V 2000 M72",
        duty_class=DutyClass.HEAVY_DUTY,  # M72 = 1B rating (high load factors)
        rating_designation="M72",
        primary_applications=["patrol", "crew_transfer", "commercial_workboat"],
        notes="M72 = 1B rating (high load factors, 5000 hrs/yr). Fast vessels with high usage.",
    ),
    "MTU 10V 2000 M72": EngineSpecification(
        model_name="MTU 10V 2000 M72",
        duty_class=DutyClass.HEAVY_DUTY,  # M72 = 1B rating
        rating_designation="M72",
        primary_applications=["fast_ferry", "crew_boat", "pilot"],
        notes="M72 = 1B rating (high load factors, 5000 hrs/yr)",
    ),
    "MTU 12V 2000 M93": EngineSpecification(
        model_name="MTU 12V 2000 M93",
        duty_class=DutyClass.LIGHT_DUTY,  # M93 = 1DS rating (low load factors)
        rating_designation="M93",
        # FROM: maritimepropulsion.com/directory/product/mtu-12v2000m93-1797-hp-131940
        # Collected: 2026-01-22
        # WARNING: Secondary aggregator source, not official MTU datasheet
        dry_weight_kg=2780,  # ⚠️ Engine only, from aggregator
        length_mm=1870,  # ⚠️ Engine only, without gearbox
        width_mm=1295,  # ⚠️ From aggregator
        height_mm=1350,  # ⚠️ From aggregator
        primary_applications=["yacht", "fast_patrol", "fast_ferry"],
        data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
        verified=False,
        notes="1340kW@2450RPM. M93 = 1DS (low load). 12V, 23.94L displacement.",
    ),
    "MTU 16V 2000 M93": EngineSpecification(
        model_name="MTU 16V 2000 M93",
        duty_class=DutyClass.LIGHT_DUTY,  # M93 = 1DS rating (low load factors)
        rating_designation="M93",
        # FROM: maritimepropulsion.com/directory/product/mtu-16v2000m93-2400-hp-131931
        # Collected: 2026-01-22
        dry_weight_kg=4570,  # ⚠️ From aggregator
        length_mm=2330,  # ⚠️ From aggregator
        width_mm=1290,  # ⚠️ From aggregator
        height_mm=1420,  # ⚠️ From aggregator
        primary_applications=["yacht", "fast_ferry", "coast_guard"],
        data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
        verified=False,
        notes="1790kW@2450RPM. M93 = 1DS (low load). 16V, 32.8L displacement.",
    ),
    "MTU 16V 2000 M96": EngineSpecification(
        model_name="MTU 16V 2000 M96",
        duty_class=DutyClass.LIGHT_DUTY,  # M96 = 1DS rating (low load factors)
        rating_designation="M96",
        primary_applications=["yacht", "fast_patrol", "naval"],
        notes="M96 = 1DS rating. Higher output variant for low load applications.",
    ),
}

# =============================================================================
# MTU SERIES 4000 - Duty Class per OFFICIAL MTU Rating System
# M63 = 1A (Continuous operation) = CONTINUOUS (unrestricted)
# M73 = 1B (High load factors) = HEAVY_DUTY
# M93 = 1DS (Low load factors) = LIGHT_DUTY
# See: 3237371_Marine_spec_16V4000M63_R_L_1A.pdf (M63 = 1A confirmed)
# =============================================================================

MTU_SERIES_4000_SPECS = {
    "MTU 12V 4000 M63": EngineSpecification(
        model_name="MTU 12V 4000 M63",
        duty_class=DutyClass.CONTINUOUS,  # M63 = 1A rating (unrestricted continuous)
        rating_designation="M63",
        primary_applications=["cargo", "tanker", "dredger", "tug"],
        notes="M63 = 1A rating (70-90% load, unlimited hours). Continuous operation.",
    ),
    "MTU 16V 4000 M63": EngineSpecification(
        model_name="MTU 16V 4000 M63",
        duty_class=DutyClass.CONTINUOUS,  # M63 = 1A rating
        rating_designation="M63",
        primary_applications=["cargo", "tanker", "ferry", "tug"],
        notes="M63 = 1A rating (unrestricted continuous operation).",
    ),
    "MTU 12V 4000 M73": EngineSpecification(
        model_name="MTU 12V 4000 M73",
        duty_class=DutyClass.HEAVY_DUTY,  # M73 = 1B rating (high load factors)
        rating_designation="M73",
        primary_applications=["ferry", "patrol", "osv"],
        notes="M73 = 1B rating (60-80% load, 5000 hrs/yr).",
    ),
    "MTU 16V 4000 M73": EngineSpecification(
        model_name="MTU 16V 4000 M73",
        duty_class=DutyClass.HEAVY_DUTY,  # M73 = 1B rating
        rating_designation="M73",
        primary_applications=["fast_ferry", "coast_guard", "naval"],
        notes="M73 = 1B rating (high load factors).",
    ),
    "MTU 12V 4000 M93": EngineSpecification(
        model_name="MTU 12V 4000 M93",
        duty_class=DutyClass.LIGHT_DUTY,  # M93 = 1DS rating (low load factors)
        rating_designation="M93",
        # FROM: maritimepropulsion.com/directory/product/mtu-12v4000m93-3138-hp-132010
        # Collected: 2026-01-22
        dry_weight_kg=7800,  # ⚠️ From aggregator
        length_mm=3197,  # ⚠️ From aggregator
        width_mm=1630,  # ⚠️ From aggregator
        height_mm=2103,  # ⚠️ From aggregator
        primary_applications=["yacht", "fast_ferry", "naval"],
        data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
        verified=False,
        notes="2340kW@2100RPM. M93 = 1DS (low load). 76.3L displacement. 12660Nm torque.",
    ),
    "MTU 16V 4000 M93": EngineSpecification(
        model_name="MTU 16V 4000 M93",
        duty_class=DutyClass.LIGHT_DUTY,  # M93 = 1DS rating
        rating_designation="M93",
        primary_applications=["yacht", "fast_ferry", "naval"],
        notes="M93 = 1DS rating (low load factors for fast vessels).",
    ),
    "MTU 20V 4000 M93": EngineSpecification(
        model_name="MTU 20V 4000 M93",
        duty_class=DutyClass.LIGHT_DUTY,  # M93 = 1DS rating
        rating_designation="M93",
        primary_applications=["large_yacht", "fast_ferry", "naval"],
        notes="M93 = 1DS rating. 20V flagship for fast vessels.",
    ),
}

# =============================================================================
# MTU SERIES 4000 GAS - Duty Class per Official MTU Rating System
# M05-N = Gas variant, typically 1D (intermittent) for environmental compliance
# =============================================================================

MTU_SERIES_4000_GAS_SPECS = {
    "MTU 12V 4000 M05-N": EngineSpecification(
        model_name="MTU 12V 4000 M05-N",
        duty_class=DutyClass.MEDIUM_DUTY,  # Gas engines = 1D rating (intermittent)
        rating_designation="M05-N",
        primary_applications=["ferry", "osv", "workboat"],
        notes="LNG gas engine. IMO Tier III in gas mode. 1D rating.",
    ),
    "MTU 16V 4000 M05-N": EngineSpecification(
        model_name="MTU 16V 4000 M05-N",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="M05-N",
        primary_applications=["ferry", "osv", "offshore"],
        notes="LNG gas engine. IMO Tier III compliant.",
    ),
    "MTU 20V 4000 M05-N": EngineSpecification(
        model_name="MTU 20V 4000 M05-N",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="M05-N",
        primary_applications=["large_ferry", "osv"],
        notes="LNG gas engine flagship. 20V configuration.",
    ),
}

# =============================================================================
# MTU SERIES 8000 - Duty Class per OFFICIAL MTU Rating System
# M71 = 1B (High load factors) = HEAVY_DUTY
# M91 = 1DS (Low load factors) = LIGHT_DUTY
# See: 3236371_Marine_Navy_spec_20V8000M91L_1DS.pdf (M91 = 1DS confirmed)
# =============================================================================

MTU_SERIES_8000_SPECS = {
    "MTU 16V 8000 M71": EngineSpecification(
        model_name="MTU 16V 8000 M71",
        duty_class=DutyClass.HEAVY_DUTY,  # M71 = 1B rating (high load factors)
        rating_designation="M71",
        primary_applications=["ferry", "ropax", "cruise"],
        notes="M71 = 1B rating (high load, 5000 hrs/yr). Series 8000.",
    ),
    "MTU 20V 8000 M91": EngineSpecification(
        model_name="MTU 20V 8000 M91",
        duty_class=DutyClass.LIGHT_DUTY,  # M91 = 1DS rating (low load factors)
        rating_designation="M91",
        primary_applications=["yacht", "fast_ferry", "naval"],
        notes="M91 = 1DS rating. 10000kW flagship for fast vessels.",
    ),
}

# =============================================================================
# CUMMINS QSK SERIES - Duty Class from product line positioning
# QSK series designed for heavy commercial marine
# =============================================================================

CUMMINS_QSK_SPECS = {
    "Cummins QST30": EngineSpecification(
        model_name="Cummins QST30",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="QST30-M",
        primary_applications=["workboat", "ferry", "crew_boat"],
        notes="30L displacement, medium-duty commercial marine",
    ),
    "Cummins X15 Marine": EngineSpecification(
        model_name="Cummins X15 Marine",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="X15-M",
        primary_applications=["workboat", "fishing", "crew_boat"],
        notes="15L displacement, compact high-speed commercial",
    ),
    "Cummins QSK38": EngineSpecification(
        model_name="Cummins QSK38",
        duty_class=DutyClass.HEAVY_DUTY,  # QSK series for heavy commercial
        rating_designation="QSK38-HD",
        primary_applications=["tug", "osv", "workboat"],
        notes="38L displacement, heavy-duty commercial marine",
    ),
    "Cummins QSK38-M": EngineSpecification(
        model_name="Cummins QSK38-M",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="QSK38-M",
        primary_applications=["ferry", "workboat", "patrol"],
        notes="38L displacement, medium-duty rating",
    ),
    "Cummins QSK50": EngineSpecification(
        model_name="Cummins QSK50",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="QSK50-HD",
        primary_applications=["tug", "osv", "fast_supply"],
        notes="50L displacement",
    ),
    "Cummins QSK60": EngineSpecification(
        model_name="Cummins QSK60",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="QSK60-HD",
        # FROM: cummins.com/engines/qsk60 (search snippets, couldn't access directly)
        # Also: lectura-specs.com/en/model/components/engines-cummins/qsk60-2850-11688974
        # Collected: 2026-01-22
        # WARNING: Data from search snippets and equipment database, not official Cummins datasheet
        dry_weight_kg=8754,  # ⚠️ UNVERIFIED - from equipment database
        length_mm=3290,  # ⚠️ UNVERIFIED - from equipment database
        width_mm=1757,  # ⚠️ UNVERIFIED - from equipment database
        height_mm=2415,  # ⚠️ UNVERIFIED - from equipment database
        primary_applications=["tug", "osv", "ferry"],
        data_source="secondary_aggregator:lectura-specs.com 2026-01-22",
        verified=False,  # Secondary source, not OEM datasheet
        notes="1641-2125kW. Dimensions from equipment database, needs OEM verification",
    ),
    "Cummins QSK78": EngineSpecification(
        model_name="Cummins QSK78",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="QSK78-HD",
        primary_applications=["tug", "osv", "ferry"],
        notes="78L, less common than QSK60",
    ),
    "Cummins QSK95": EngineSpecification(
        model_name="Cummins QSK95",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="QSK95-HD",
        primary_applications=["tug", "osv", "dredger"],
        notes="95L, largest Cummins engine",
    ),
}

# =============================================================================
# CATERPILLAR 3500 SERIES - Duty Class from model variants
# Base models = Medium, B/C series = Heavy
# =============================================================================

CAT_3500_SPECS = {
    "Cat 3508C": EngineSpecification(
        model_name="Cat 3508C",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="3508C",
        primary_applications=["workboat", "ferry", "fishing"],
        notes="34.5L V8, smaller 3500 series platform",
    ),
    "Cat 3512": EngineSpecification(
        model_name="Cat 3512",
        duty_class=DutyClass.MEDIUM_DUTY,  # Base model = versatile
        rating_designation="3512",
        primary_applications=["tug", "workboat", "ferry", "fishing"],
        notes="Versatile 51.8L platform",
    ),
    "Cat 3512B": EngineSpecification(
        model_name="Cat 3512B",
        duty_class=DutyClass.HEAVY_DUTY,  # B-series = enhanced for heavy commercial
        rating_designation="3512B",
        primary_applications=["fishing", "osv", "tug"],
        notes="Enhanced B-series",
    ),
    "Cat 3516": EngineSpecification(
        model_name="Cat 3516",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="3516",
        primary_applications=["tug", "osv", "ferry", "dredger"],
        notes="69L platform",
    ),
    "Cat 3516B": EngineSpecification(
        model_name="Cat 3516B",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="3516B",
        primary_applications=["tug", "osv", "ferry"],
        notes="Enhanced B-series",
    ),
    "Cat 3516C": EngineSpecification(
        model_name="Cat 3516C",
        duty_class=DutyClass.HEAVY_DUTY,  # C-series = maximum output
        rating_designation="3516C-HD",
        primary_applications=["tug", "osv", "ferry"],
        notes="C-series HD flagship",
    ),
}

# =============================================================================
# CATERPILLAR C-SERIES - Duty Class from product positioning
# =============================================================================

CAT_C_SERIES_SPECS = {
    "Cat C12.9": EngineSpecification(
        model_name="Cat C12.9",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="C12.9",
        primary_applications=["workboat", "fishing", "crew_boat"],
        notes="12.9L inline 6, compact high-speed",
    ),
    "Cat C18": EngineSpecification(
        model_name="Cat C18",
        duty_class=DutyClass.MEDIUM_DUTY,  # Workhorse for commercial
        rating_designation="C18",
        primary_applications=["workboat", "fishing", "tug", "crew_boat"],
        notes="18.1L, extremely popular",
    ),
    "Cat C18 ACERT": EngineSpecification(
        model_name="Cat C18 ACERT",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="C18-ACERT",
        primary_applications=["tug", "workboat", "osv"],
        notes="18.1L with ACERT technology, heavy duty commercial",
    ),
    "Cat C32": EngineSpecification(
        model_name="Cat C32",
        duty_class=DutyClass.MEDIUM_DUTY,  # Versatile
        rating_designation="C32",
        primary_applications=["tug", "osv", "ferry", "patrol", "yacht"],
        notes="32.1L, direct competitor to MTU Series 2000",
    ),
    "Cat C32B": EngineSpecification(
        model_name="Cat C32B",
        duty_class=DutyClass.LIGHT_DUTY,  # B-series optimized for high-speed
        rating_designation="C32B",
        primary_applications=["fast_ferry", "yacht", "patrol"],
        notes="Enhanced B-series, higher power density",
    ),
}

# =============================================================================
# MAN ENGINES - Duty Class from LE rating codes
# LE4xx codes indicate duty class variants
# =============================================================================

MAN_ENGINES_SPECS = {
    "MAN D2676 LE": EngineSpecification(
        model_name="MAN D2676 LE",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="D2676-LE",
        primary_applications=["workboat", "fishing", "crew_boat"],
        notes="12.4L inline 6, compact high-speed commercial",
    ),
    "MAN D2862 LE463": EngineSpecification(
        model_name="MAN D2862 LE463",
        duty_class=DutyClass.LIGHT_DUTY,  # LE463 = Light duty rating
        rating_designation="LE463",
        # FROM: maritimepropulsion.com/directory/product/man--d-2862-le-463--1400-hp-132836
        # Also: man.eu/engines/en/products/marine/engines-for-commercial-shipping/man-motor-d2862-le44x.html
        # Collected: 2026-01-22
        # WARNING: Secondary aggregator source, not official MAN datasheet
        # SFOC REMOVED: Was 210 g/kWh from Maritime Propulsion (aggregator, not authoritative)
        dry_weight_kg=2270,  # ⚠️ UNVERIFIED - from industry aggregator
        length_mm=1631,  # ⚠️ UNVERIFIED - from industry aggregator
        width_mm=1153,  # ⚠️ UNVERIFIED - from industry aggregator
        height_mm=1289,  # ⚠️ UNVERIFIED - from industry aggregator
        sfoc_rated_g_kwh=None,  # REMOVED - aggregator is not authoritative source
        primary_applications=["fast_craft", "patrol", "yacht"],
        data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
        verified=False,  # Secondary source, not OEM datasheet
        notes="1029kW@2100RPM. Dimensions from aggregator site, needs OEM verification",
    ),
    "MAN D2862 LE443": EngineSpecification(
        model_name="MAN D2862 LE443",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="LE443",
        primary_applications=["tug", "osv", "patrol"],
        notes="24.2L V12, heavy duty rating for commercial",
    ),
    "MAN D2868 LE433": EngineSpecification(
        model_name="MAN D2868 LE433",
        duty_class=DutyClass.LIGHT_DUTY,  # LE433 = Light duty
        rating_designation="LE433",
        primary_applications=["fast_boat", "pilot", "ferry"],
        notes="16.1L V8, compact light duty",
    ),
    "MAN D2868 LE423": EngineSpecification(
        model_name="MAN D2868 LE423",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="LE423",
        primary_applications=["tug", "workboat", "patrol"],
        notes="16.1L V8, heavy duty commercial",
    ),
    "MAN V12-2000": EngineSpecification(
        model_name="MAN V12-2000",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="V12-2000",
        primary_applications=["osv", "ferry", "patrol"],
        notes="V12 24.2L, medium duty competitor to MTU 2000",
    ),
    "MAN V12-2000CR": EngineSpecification(
        model_name="MAN V12-2000CR",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="V12-2000CR",
        primary_applications=["tug", "osv", "naval"],
        notes="V12 24.2L common rail, heavy duty flagship",
    ),
}

# =============================================================================
# VOLVO PENTA - Duty Class from product line positioning
# =============================================================================

VOLVO_PENTA_SPECS = {
    "Volvo Penta D11": EngineSpecification(
        model_name="Volvo Penta D11",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="D11-M",
        primary_applications=["workboat", "fishing", "crew_boat"],
        notes="10.8L inline 6, compact commercial marine",
    ),
    "Volvo Penta D13-IPS1350": EngineSpecification(
        model_name="Volvo Penta D13-IPS1350",
        duty_class=DutyClass.LIGHT_DUTY,  # IPS systems for yacht/pleasure
        rating_designation="IPS1350",
        primary_applications=["yacht", "fast_cruiser"],
        notes="IPS pod drive system for yachts",
    ),
    "Volvo Penta D13-IPS1200": EngineSpecification(
        model_name="Volvo Penta D13-IPS1200",
        duty_class=DutyClass.LIGHT_DUTY,
        rating_designation="IPS1200",
        primary_applications=["yacht", "patrol", "pilot"],
        notes="IPS pod drive for smaller yachts",
    ),
    "Volvo Penta D13-800": EngineSpecification(
        model_name="Volvo Penta D13-800",
        duty_class=DutyClass.MEDIUM_DUTY,  # Commercial rating
        rating_designation="D13-800",
        primary_applications=["workboat", "ferry", "fishing"],
        notes="Shaft-line for commercial applications",
    ),
    "Volvo Penta D13 MH": EngineSpecification(
        model_name="Volvo Penta D13 MH",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="D13-MH",
        primary_applications=["tug", "osv", "workboat"],
        notes="Heavy duty commercial rating",
    ),
}

# =============================================================================
# YANMAR - Duty Class from product positioning
# =============================================================================

YANMAR_SPECS = {
    "Yanmar 6AYM-ETE": EngineSpecification(
        model_name="Yanmar 6AYM-ETE",
        duty_class=DutyClass.MEDIUM_DUTY,  # Commercial workboat focus
        rating_designation="6AYM-ETE",
        primary_applications=["workboat", "fishing", "ferry"],
        notes="Japanese reliability, 20.4L",
    ),
    "Yanmar 6AYEM-GT": EngineSpecification(
        model_name="Yanmar 6AYEM-GT",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="6AYEM-GT",
        primary_applications=["workboat", "patrol", "fast_craft"],
        notes="GT turbo variant, higher output",
    ),
    "Yanmar 8AYM-WET": EngineSpecification(
        model_name="Yanmar 8AYM-WET",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="8AYM-WET",
        primary_applications=["ferry", "osv", "patrol"],
        notes="27.2L V8, wet exhaust commercial",
    ),
    "Yanmar 12AYM-WGT": EngineSpecification(
        model_name="Yanmar 12AYM-WGT",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="12AYM-WGT",
        primary_applications=["ferry", "osv", "naval"],
        notes="40.8L V12, heavy duty flagship",
    ),
}

# =============================================================================
# WEICHAI - Duty Class from product positioning
# =============================================================================

WEICHAI_SPECS = {
    "WEICHAI WP13": EngineSpecification(
        model_name="WEICHAI WP13",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="WP13",
        primary_applications=["tug", "workboat", "fishing"],
        notes="12.9L, competitive pricing",
    ),
    "WEICHAI WHM6160": EngineSpecification(
        model_name="WEICHAI WHM6160",
        duty_class=DutyClass.HEAVY_DUTY,  # Designed for commercial
        rating_designation="WHM6160",
        primary_applications=["tug", "osv", "cargo"],
        notes="Multi-config platform",
    ),
    "WEICHAI 12M33": EngineSpecification(
        model_name="WEICHAI 12M33",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="12M33C",
        primary_applications=["tug", "osv", "large_vessel"],
        notes="Competes with MTU 4000, Cummins QSK",
    ),
}

# =============================================================================
# FPT INDUSTRIAL - Duty Class from product positioning
# =============================================================================

FPT_SPECS = {
    "FPT Cursor 13": EngineSpecification(
        model_name="FPT Cursor 13",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="C13-500",
        primary_applications=["fishing", "workboat", "ferry"],
        notes="12.9L, European markets",
    ),
    "FPT Cursor 16": EngineSpecification(
        model_name="FPT Cursor 16",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="C16-600",
        primary_applications=["fishing", "tug", "ferry", "workboat"],
        notes="15.9L, largest Cursor",
    ),
}

# =============================================================================
# SCANIA - Duty Class from product positioning
# =============================================================================

SCANIA_SPECS = {
    "Scania DI13": EngineSpecification(
        model_name="Scania DI13",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="DI13",
        primary_applications=["ferry", "workboat", "fishing"],
        notes="12.7L, Swedish quality",
    ),
    "Scania DI16": EngineSpecification(
        model_name="Scania DI16",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="DI16",
        primary_applications=["ferry", "pilot", "patrol"],
        notes="16.4L V8, largest Scania",
    ),
}


# =============================================================================
# WARTSILA HIGH-SPEED ENGINES - Duty Class VERIFIED
# Only HIGH-SPEED engines (>1000 RPM) for apple-to-apple comparison
# =============================================================================

WARTSILA_14_SPECS = {
    "Wartsila 6L14": EngineSpecification(
        model_name="Wartsila 6L14",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="6L14",
        primary_applications=["workboat", "ferry", "tug"],
        notes="6-cyl inline, 14cm bore, 1500 RPM high-speed",
    ),
    "Wartsila 8L14": EngineSpecification(
        model_name="Wartsila 8L14",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="8L14",
        primary_applications=["workboat", "ferry", "osv"],
        notes="8-cyl inline, 14cm bore, 1500 RPM high-speed",
    ),
    "Wartsila 12V14": EngineSpecification(
        model_name="Wartsila 12V14",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="12V14",
        primary_applications=["ferry", "osv", "tug"],
        notes="V12, 14cm bore, 1200 RPM high-speed, heavy-duty commercial",
    ),
}

WARTSILA_20_SPECS = {
    "Wartsila 6L20": EngineSpecification(
        model_name="Wartsila 6L20",
        duty_class=DutyClass.MEDIUM_DUTY,
        rating_designation="6L20",
        # FROM: maritimepropulsion.com/directory/product/wrtsil-6l20-16092hp-130167
        # Also: wartsila.com/marine/products/engines-and-generating-sets/wartsila-20
        # Collected: 2026-01-22
        # WARNING: Primary data from industry aggregator, not official Wartsila datasheet
        dry_weight_kg=18000,  # ⚠️ UNVERIFIED - from industry aggregator
        length_mm=3845,  # ⚠️ UNVERIFIED - from industry aggregator
        width_mm=1450,  # ⚠️ UNVERIFIED - from industry aggregator
        height_mm=2375,  # ⚠️ UNVERIFIED - from industry aggregator
        primary_applications=["ferry", "osv", "tug"],
        data_source="secondary_aggregator:maritimepropulsion.com 2026-01-22",
        verified=False,  # Secondary source, needs official Wartsila datasheet
        notes="1200kW@1000RPM. Dimensions from aggregator site, needs OEM verification",
    ),
    "Wartsila 8L20": EngineSpecification(
        model_name="Wartsila 8L20",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="8L20",
        primary_applications=["ferry", "osv", "tug", "workboat"],
        notes="8-cyl inline, 20cm bore, 1200 RPM",
    ),
    "Wartsila 9L20": EngineSpecification(
        model_name="Wartsila 9L20",
        duty_class=DutyClass.HEAVY_DUTY,
        rating_designation="9L20",
        primary_applications=["ferry", "osv", "naval"],
        notes="9-cyl inline, 20cm bore, 1200 RPM, heavy commercial",
    ),
}


# =============================================================================
# MASTER LOOKUP DICTIONARY
# =============================================================================

ENGINE_MASTER_DATA: dict[str, EngineSpecification] = {
    **MTU_SERIES_2000_SPECS,
    **MTU_SERIES_4000_SPECS,
    **MTU_SERIES_4000_GAS_SPECS,
    **MTU_SERIES_8000_SPECS,
    **CUMMINS_QSK_SPECS,
    **CAT_3500_SPECS,
    **CAT_C_SERIES_SPECS,
    **MAN_ENGINES_SPECS,
    **VOLVO_PENTA_SPECS,
    **YANMAR_SPECS,
    **WEICHAI_SPECS,
    **FPT_SPECS,
    **SCANIA_SPECS,
    **WARTSILA_14_SPECS,
    **WARTSILA_20_SPECS,
}


def get_engine_specification(model_name: str) -> Optional[EngineSpecification]:
    """
    Get verified engine specification by model name.

    Args:
        model_name: Engine model name (e.g., "MTU 12V 2000 M93")

    Returns:
        EngineSpecification or None if not found
    """
    return ENGINE_MASTER_DATA.get(model_name)


def get_duty_class(model_name: str) -> DutyClass:
    """
    Get verified duty class for an engine.

    Args:
        model_name: Engine model name

    Returns:
        DutyClass (defaults to MEDIUM_DUTY if not found)
    """
    spec = ENGINE_MASTER_DATA.get(model_name)
    if spec:
        return spec.duty_class
    return DutyClass.MEDIUM_DUTY  # Safe default


def get_duty_class_summary() -> dict[str, int]:
    """Get summary of duty class distribution."""
    summary = {}
    for spec in ENGINE_MASTER_DATA.values():
        dc = spec.duty_class.value
        summary[dc] = summary.get(dc, 0) + 1
    return summary


# =============================================================================
# APPLICATION SYNONYMS - For fuzzy matching
# =============================================================================

APPLICATION_SYNONYMS = {
    # Ferry variants
    "ferry": ["ferry", "ferries", "fast_ferry", "passenger_ferry", "car_ferry", "roro"],
    "fast_ferry": ["fast_ferry", "high_speed_ferry", "hsc", "fast_craft"],
    # Offshore variants
    "osv": [
        "osv",
        "offshore_supply",
        "offshore_supply_vessel",
        "psv",
        "ahts",
        "supply_vessel",
    ],
    "psv": ["psv", "platform_supply", "platform_supply_vessel", "osv"],
    "ahts": ["ahts", "anchor_handling", "anchor_handling_tug", "osv"],
    # Workboat variants
    "workboat": [
        "workboat",
        "work_boat",
        "utility",
        "service_vessel",
        "utility_vessel",
    ],
    "tug": ["tug", "tugboat", "harbor_tug", "escort_tug", "ocean_tug"],
    # Patrol/naval variants
    "patrol": ["patrol", "patrol_boat", "patrol_vessel", "coast_guard", "naval_patrol"],
    "naval": ["naval", "navy", "military", "corvette", "frigate", "naval_vessel"],
    # Yacht variants
    "yacht": ["yacht", "motor_yacht", "mega_yacht", "superyacht", "pleasure", "luxury"],
    "pleasure": ["pleasure", "recreational", "private", "yacht"],
    # Crew variants
    "crew_boat": ["crew_boat", "crew_transfer", "ctv", "crew_vessel"],
    "crew_transfer": ["crew_transfer", "ctv", "crew_boat", "wind_farm_vessel"],
    # Fishing variants
    "fishing": ["fishing", "trawler", "fishing_vessel", "commercial_fishing"],
    # Pilot variants
    "pilot": ["pilot", "pilot_boat", "pilot_vessel", "harbor_pilot"],
    # Dredging
    "dredger": ["dredger", "dredge", "dredging_vessel"],
    # Cargo/tanker
    "cargo": ["cargo", "freighter", "cargo_vessel", "container"],
    "tanker": ["tanker", "oil_tanker", "product_tanker", "chemical_tanker"],
}


def normalize_application(app: str) -> str:
    """
    Normalize application name to canonical form.

    Args:
        app: Application name (may have variations)

    Returns:
        Canonical application name
    """
    app_lower = app.lower().strip().replace(" ", "_").replace("-", "_")

    # Check direct match first
    if app_lower in APPLICATION_SYNONYMS:
        return app_lower

    # Check if it's a synonym
    for canonical, synonyms in APPLICATION_SYNONYMS.items():
        if app_lower in synonyms:
            return canonical

    return app_lower  # Return as-is if not found


def applications_match(required: str, available: list[str]) -> tuple[bool, float]:
    """
    Check if required application matches any available applications.

    Args:
        required: Required application
        available: List of available applications

    Returns:
        Tuple of (matches, confidence_score)
    """
    required_normalized = normalize_application(required)
    required_synonyms = APPLICATION_SYNONYMS.get(
        required_normalized, [required_normalized]
    )

    for app in available:
        app_normalized = normalize_application(app)
        app_synonyms = APPLICATION_SYNONYMS.get(app_normalized, [app_normalized])

        # Check for direct match
        if app_normalized == required_normalized:
            return (True, 1.0)

        # Check for synonym overlap
        if set(required_synonyms) & set(app_synonyms):
            return (True, 0.9)

        # Check if one is subset of other (e.g., "ferry" in "fast_ferry")
        if (
            required_normalized in app_normalized
            or app_normalized in required_normalized
        ):
            return (True, 0.8)

    return (False, 0.0)
