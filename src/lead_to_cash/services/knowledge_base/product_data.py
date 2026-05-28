"""
Marine Engine Knowledge Base - High-Speed Engine Product Fact Sheets

DEPRECATED (2026-03-02): This module has been fully migrated to the unified PostgreSQL KB.
All data now lives in database tables seeded by migrations/003_seed_product_data.sql.
This file is retained ONLY for backward compatibility with migrate_product_data.py.
Do NOT import from this module for new code.

For new code, use:
    from lead_to_cash.services.knowledge_base.engine_master_data import (
        ENGINE_MASTER_DATA,
        get_engine_specification,
        get_duty_class,
    )

Migration Status: COMPLETE
- Data migrated to migrations/003_seed_product_data.sql
- Verified duty classes and physical specs in engine_master_data.py
- Only import is from migrate_product_data.py (one-time migration script)

Comprehensive product data for HIGH-SPEED marine engines (>1000 RPM, 700-10,000 kW focus).
This KB is designed for LLM-based semantic search to infer product matches from
customer requirements in news/media.

Target Scope:
- RPM: >1000 RPM (high-speed 4-stroke)
- Power: 700-4,000 kW primary focus, extending to 10,000 kW
- Applications: Fast ferries, patrol boats, yachts, workboats, tugs, offshore supply vessels

Sources:
- MTU (Rolls-Royce Power Systems): mtu-solutions.com, product brochures
- Cummins: cummins.com, marine specification sheets
- Caterpillar: cat.com, marine engine guides
- MAN Engines: man-es.com (MAN Truck & Bus division)
- Volvo Penta: volvopenta.com, IPS documentation
- Yanmar: yanmar.com, marine engine specifications
"""

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional

warnings.warn(
    "product_data.py is deprecated. Use engine_master_data.py and the unified "
    "PostgreSQL KB (migrations/003_seed_product_data.sql) instead.",
    DeprecationWarning,
    stacklevel=2,
)


class FuelCapability(Enum):
    """Fuel capability levels."""

    DIESEL_ONLY = "diesel_only"
    DUAL_FUEL = "dual_fuel"  # Gas + Diesel
    TRI_FUEL = "tri_fuel"  # Gas + Diesel + HFO
    MULTI_FUEL = "multi_fuel"  # Including methanol, ammonia
    GAS_ONLY = "gas_only"


class EmissionsTier(Enum):
    """
    Marine engine emissions compliance tier.

    IMO MARPOL Annex VI (global):
    - Tier I (2000): Basic NOx limits
    - Tier II (2011): 20% stricter than Tier I
    - Tier III (2016+ in ECAs): 80% stricter, requires SCR/EGR

    EPA (US waters):
    - Tier 4 (2017+): Equivalent to EU Stage V, requires DPF+SCR

    EU Stage V (inland waterways):
    - Stage V (2019+): Inland vessels, non-road mobile machinery

    Updated in Phase 4 to include all major compliance regimes.
    """

    # IMO MARPOL Annex VI (global marine)
    TIER_I = "imo_tier_i"
    TIER_II = "imo_tier_ii"
    TIER_III = "imo_tier_iii"
    TIER_III_GAS_MODE = "imo_tier_iii_gas_mode"  # Tier III only in gas mode
    TIER_III_SCR = "imo_tier_iii_scr"  # Tier III with SCR system (Phase 4 addition)

    # EPA Tier (US waters)
    EPA_TIER_3 = "epa_tier_3"  # Phase 4 addition
    EPA_TIER_4 = "epa_tier_4"
    EPA_TIER_4_FINAL = "epa_tier_4_final"  # Phase 4 addition

    # EU Stage (inland waterways, non-road)
    EU_STAGE_IIIA = "eu_stage_iiia"  # Phase 4 addition
    EU_STAGE_IV = "eu_stage_iv"  # Phase 4 addition
    EU_STAGE_V = "eu_stage_v"  # Phase 4 addition


class VerificationStatus(Enum):
    """Data verification status for fact sheets."""

    VERIFIED = "verified"  # Confirmed from official sources
    PARTIALLY_VERIFIED = "partially_verified"  # Some specs need confirmation
    UNVERIFIED = "unverified"  # Needs verification


@dataclass
class EngineFactSheet:
    """Comprehensive engine product fact sheet for high-speed marine engines."""

    # Identity
    manufacturer: str
    model_name: str
    series: str

    # Technical Specifications
    bore_mm: int
    stroke_mm: int
    cylinders_available: list[str]  # e.g., ["12V", "16V", "20V"]
    power_range_min_kw: float
    power_range_max_kw: float
    rpm_options: list[int]  # e.g., [1800, 2100]

    # Fuel & Efficiency
    fuel_capability: FuelCapability
    fuel_types: list[str]  # e.g., ["diesel", "mdo", "mgo"]

    # Emissions
    emissions_tier: EmissionsTier = EmissionsTier.TIER_II

    # Data Quality
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    data_confidence: float = 0.9

    # For LLM-based semantic search (embedding generation)
    searchable_description: str = ""


# =============================================================================
# MTU SERIES 2000 (High-Speed Marine Diesel)
# =============================================================================

MTU_8V2000_M72 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 8V 2000 M72",
    series="Series 2000",
    bore_mm=130,
    stroke_mm=150,
    cylinders_available=["8V"],
    power_range_min_kw=720,
    power_range_max_kw=720,
    rpm_options=[2250],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 8V 2000 M72 high-speed marine diesel engine manufactured by MTU, a Rolls-Royce Power Systems brand (RRPS). 8-cylinder V-configuration delivering 720 kW (965 bhp) at 2250 RPM. Series 2000 platform for fast patrol boats, crew transfer vessels, and luxury yachts. Common rail fuel injection, turbocharging with charge air cooling. IMO Tier II certified. Compact footprint ideal for twin or triple installations. MTU ValueCare service packages available. Also known as MTU 8V2000M72 or 8V-2000-M72.""",
)

MTU_10V2000_M72 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 10V 2000 M72",
    series="Series 2000",
    bore_mm=130,
    stroke_mm=150,
    cylinders_available=["10V"],
    power_range_min_kw=900,
    power_range_max_kw=900,
    rpm_options=[2250],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 10V 2000 M72 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 10-cylinder V-configuration producing 900 kW (1205 bhp) at 2250 RPM. Series 2000 platform for fast ferries, offshore crew boats, and pilot vessels. Features electronic engine management, common rail injection. IMO Tier II compliant. Popular choice for twin-engine fast craft applications. Also referred to as MTU 10V2000M72, 10V-2000-M72, or RRPS 10V2000.""",
)

MTU_12V2000_M93 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 12V 2000 M93",
    series="Series 2000",
    bore_mm=130,
    stroke_mm=150,
    cylinders_available=["12V"],
    power_range_min_kw=1340,
    power_range_max_kw=1340,
    rpm_options=[2450],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 12V 2000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 12-cylinder V-configuration delivering 1340 kW (1800 bhp) at 2450 RPM. M93 rating for heavy-duty continuous operation. Series 2000 platform optimized for fast ferries, patrol boats, and offshore supply vessels. Advanced common rail injection with MDEC electronic controls. IMO Tier II certified. Excellent power-to-weight ratio. Known as MTU 12V2000M93 or 12V-2000-M93.""",
)

MTU_16V2000_M93 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 2000 M93",
    series="Series 2000",
    bore_mm=130,
    stroke_mm=150,
    cylinders_available=["16V"],
    power_range_min_kw=1790,
    power_range_max_kw=1790,
    rpm_options=[2450],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 2000 M93 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1790 kW (2400 bhp) at 2450 RPM. Flagship of the Series 2000 M93 heavy-duty range. Ideal for fast ferries, coast guard vessels, and luxury mega-yachts requiring high power density. Common rail fuel system, turbocharging with dual-stage charge air cooling. IMO Tier II compliant. Also known as MTU 16V2000M93 or 16V-2000-M93.""",
)

MTU_16V2000_M96 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 2000 M96",
    series="Series 2000",
    bore_mm=130,
    stroke_mm=150,
    cylinders_available=["16V"],
    power_range_min_kw=1790,
    power_range_max_kw=1939,
    rpm_options=[2450],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 2000 M96 high-speed marine diesel engine, latest Series 2000 variant from Rolls-Royce Power Systems MTU. 16-cylinder V-configuration with 1939 kW (2600 bhp) peak output at 2450 RPM. M96 rating indicates enhanced power for demanding applications. Used in high-speed ferries, naval patrol craft, and offshore vessels. Features latest common rail technology and optimized turbocharging. IMO Tier II certified. Also referred to as MTU 16V2000M96 or RRPS Series 2000.""",
)

# =============================================================================
# MTU SERIES 4000 (High-Speed Marine Diesel)
# =============================================================================

MTU_12V4000_M63 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 12V 4000 M63",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=210,
    cylinders_available=["12V"],
    power_range_min_kw=1500,
    power_range_max_kw=1500,
    rpm_options=[1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MTU 12V 4000 M63 high-speed marine diesel engine from Rolls-Royce Power Systems. 12-cylinder V-configuration delivering 1500 kW (2012 bhp) at 1600-1800 RPM. Series 4000 platform for medium-duty applications including tugs, offshore vessels, and large yachts. M63 rating for light-duty operation with extended maintenance intervals. Features MTU ADEC electronic controls, common rail injection. IMO Tier II compliant. Also known as MTU 12V4000M63 or 12V-4000-M63.""",
)

MTU_16V4000_M63 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 4000 M63",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=210,
    cylinders_available=["16V"],
    power_range_min_kw=1920,
    power_range_max_kw=2240,
    rpm_options=[1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 4000 M63 high-speed marine diesel engine by MTU Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1920-2240 kW (2575-3004 bhp) at 1600-1800 RPM. Series 4000 workhorse for commercial vessels, offshore support, and large motor yachts. M63 light-duty rating suitable for yachts and vessels with lower operating hours. Advanced common rail injection. IMO Tier II certified. Known as MTU 16V4000M63 or RRPS 16V4000.""",
)

MTU_12V4000_M73 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 12V 4000 M73",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["12V"],
    power_range_min_kw=1920,
    power_range_max_kw=2160,
    rpm_options=[1970, 2050],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MTU 12V 4000 M73 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 12-cylinder V-configuration delivering 1920-2160 kW (2575-2895 bhp) at 1970-2050 RPM. M73 medium-duty rating for ferries, patrol boats, and offshore vessels. Series 4000 with optimized turbocharging for marine applications. IMO Tier II certified. Suitable for vessels requiring balance of power and economy. Also referred to as MTU 12V4000M73 or 12V-4000-M73.""",
)

MTU_16V4000_M73 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 4000 M73",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=2560,
    power_range_max_kw=2880,
    rpm_options=[1970, 2050],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 4000 M73 high-speed marine diesel engine by Rolls-Royce Power Systems MTU. 16-cylinder V-configuration producing 2560-2880 kW (3435-3860 bhp) at 1970-2050 RPM. Popular choice for fast ferries, coast guard cutters, and naval patrol vessels. M73 medium-duty rating balances performance and durability. Series 4000 common rail technology with ADEC controls. IMO Tier II compliant. Known as MTU 16V4000M73 or RRPS Series 4000.""",
)

MTU_12V4000_M93 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 12V 4000 M93",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["12V"],
    power_range_min_kw=2340,
    power_range_max_kw=2580,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 12V 4000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems. 12-cylinder V-configuration delivering 2340-2580 kW (3140-3460 bhp) at 2100 RPM. M93 heavy-duty rating for demanding commercial operations. Suited for offshore supply vessels, large ferries, and military applications. Features advanced common rail injection and two-stage turbocharging. IMO Tier II certified. Also known as MTU 12V4000M93 or 12V-4000-M93.""",
)

MTU_16V4000_M93 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 4000 M93",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=3120,
    power_range_max_kw=3440,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 4000 M93 high-speed marine diesel engine by Rolls-Royce Power Systems MTU. 16-cylinder V-configuration producing 3120-3440 kW (4185-4615 bhp) at 2100 RPM. Heavy-duty M93 rating for high-utilization commercial vessels. Excellent choice for large fast ferries, offshore vessels, and naval craft. Two-stage turbocharging with charge air cooling. IMO Tier II compliant. Also referred to as MTU 16V4000M93 or RRPS 16V4000.""",
)

MTU_20V4000_M93 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 20V 4000 M93",
    series="Series 4000",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["20V"],
    power_range_min_kw=3900,
    power_range_max_kw=4300,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 20V 4000 M93 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 20-cylinder V-configuration delivering 3900-4300 kW (5230-5766 bhp) at 2100 RPM. Flagship of the Series 4000 M93 heavy-duty range. Maximum power density for large fast ferries, mega-yachts, and naval vessels. Features advanced common rail injection, dual-stage turbocharging. IMO Tier II certified. Known as MTU 20V4000M93 or 20V-4000-M93.""",
)

# =============================================================================
# MTU SERIES 4000 GAS (Natural Gas / LNG)
# =============================================================================

MTU_12V4000_M05N = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 12V 4000 M05-N",
    series="Series 4000 Gas",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["12V"],
    power_range_min_kw=1164,
    power_range_max_kw=1380,
    rpm_options=[1500],
    fuel_capability=FuelCapability.GAS_ONLY,
    fuel_types=["natural_gas", "lng"],
    emissions_tier=EmissionsTier.TIER_III_GAS_MODE,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MTU 12V 4000 M05-N natural gas marine engine from Rolls-Royce Power Systems. 12-cylinder V-configuration producing 1164-1380 kW at 1500 RPM. Series 4000 Gas platform for LNG-powered vessels. Achieves IMO Tier III emissions without aftertreatment in gas mode. Designed for ferries, offshore support vessels, and workboats transitioning to cleaner fuels. Spark-ignited, lean-burn combustion technology. Also known as MTU 12V4000M05N or RRPS Series 4000 Gas.""",
)

MTU_16V4000_M05N = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 4000 M05-N",
    series="Series 4000 Gas",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=1552,
    power_range_max_kw=1840,
    rpm_options=[1500],
    fuel_capability=FuelCapability.GAS_ONLY,
    fuel_types=["natural_gas", "lng"],
    emissions_tier=EmissionsTier.TIER_III_GAS_MODE,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MTU 16V 4000 M05-N natural gas marine engine from Rolls-Royce Power Systems. 16-cylinder V-configuration producing 1552-1840 kW at 1500 RPM. Series 4000 Gas for LNG-fueled marine applications. IMO Tier III compliant in gas mode without SCR or aftertreatment. Ideal for environmentally regulated areas (ECAs). Applications include LNG-powered ferries and offshore vessels. Known as MTU 16V4000M05N or RRPS 16V 4000 Gas.""",
)

MTU_20V4000_M05N = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 20V 4000 M05-N",
    series="Series 4000 Gas",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["20V"],
    power_range_min_kw=1940,
    power_range_max_kw=2300,
    rpm_options=[1500],
    fuel_capability=FuelCapability.GAS_ONLY,
    fuel_types=["natural_gas", "lng"],
    emissions_tier=EmissionsTier.TIER_III_GAS_MODE,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MTU 20V 4000 M05-N natural gas marine engine, flagship of the Series 4000 Gas range. 20-cylinder V-configuration producing 1940-2300 kW at 1500 RPM. Highest power output in MTU gas marine lineup. IMO Tier III emissions compliance without aftertreatment systems. Designed for large LNG-powered ferries and offshore vessels. Lean-burn spark-ignited technology with low methane slip. Also referred to as MTU 20V4000M05N or Rolls-Royce Series 4000 Gas.""",
)

# =============================================================================
# MTU SERIES 8000 (High-Power Marine Diesel)
# =============================================================================

MTU_16V8000_M71 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 16V 8000 M71",
    series="Series 8000",
    bore_mm=265,
    stroke_mm=315,
    cylinders_available=["16V"],
    power_range_min_kw=7280,
    power_range_max_kw=7280,
    rpm_options=[1150],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 16V 8000 M71 high-speed marine diesel engine from Rolls-Royce Power Systems MTU. 16-cylinder V-configuration delivering 7280 kW (9765 bhp) at 1150 RPM. Series 8000 platform bridges high-speed and medium-speed segments. Designed for large fast ferries, cruise ships, and naval frigates. Features common rail injection with ADEC engine management. IMO Tier II certified. Known for exceptional power density. Also referred to as MTU 16V8000M71 or RRPS Series 8000.""",
)

MTU_20V8000_M91 = EngineFactSheet(
    manufacturer="MTU (Rolls-Royce Power Systems)",
    model_name="MTU 20V 8000 M91",
    series="Series 8000",
    bore_mm=265,
    stroke_mm=315,
    cylinders_available=["20V"],
    power_range_min_kw=9100,
    power_range_max_kw=10000,
    rpm_options=[1150],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MTU 20V 8000 M91 high-speed marine diesel engine, flagship from Rolls-Royce Power Systems MTU. 20-cylinder V-configuration producing 9100-10000 kW (12200-13400 bhp) at 1150 RPM. Highest power output in MTU marine portfolio. Applications include large fast ferries, RoPax vessels, naval corvettes and frigates. M91 heavy-duty rating for demanding operations. Features advanced common rail injection and sophisticated turbocharging. IMO Tier II compliant. Known as MTU 20V8000M91 or RRPS 20V8000.""",
)

# =============================================================================
# CUMMINS QSK SERIES (High-Speed Marine Diesel)
# =============================================================================

CUMMINS_QSK38 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK38",
    series="QSK",
    bore_mm=159,
    stroke_mm=159,
    cylinders_available=["12V"],
    power_range_min_kw=1063,
    power_range_max_kw=1417,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Cummins QSK38 high-speed marine diesel engine. 12-cylinder V-configuration delivering 1063-1417 kW (1425-1900 bhp) at 1800 RPM. 38 liter displacement with Modular Common Rail Fuel System (MCRS). Popular for offshore crew boats, tugs, and workboats. Features Quantum electronic controls, heavy-duty design. IMO Tier II compliant. Excellent service network globally. Also known as Cummins QSK38-M, QSK 38, or Cummins 38-liter marine.""",
)

CUMMINS_QSK50 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK50",
    series="QSK",
    bore_mm=159,
    stroke_mm=159,
    cylinders_available=["16V"],
    power_range_min_kw=1268,
    power_range_max_kw=1700,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Cummins QSK50 high-speed marine diesel engine. 16-cylinder V-configuration producing 1268-1700 kW (1700-2280 bhp) at 1800 RPM. 50 liter displacement with Modular Common Rail Fuel System (MCRS). Popular mid-range option between QSK38 and QSK60. Direct competitor to MTU 12V2000 M93. Applications include tugs, offshore crew boats, fast supply vessels. Features Quantum electronic controls, proven reliability. IMO Tier II compliant. Excellent parts availability through global Cummins network. Also known as Cummins QSK50-M, QSK 50, or Cummins 50-liter marine.""",
)

CUMMINS_QSK60 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK60",
    series="QSK",
    bore_mm=159,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=1641,
    power_range_max_kw=2680,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Cummins QSK60 high-speed marine diesel engine. 16-cylinder V-configuration producing 1641-2680 kW (2200-3595 bhp) at 1800 RPM. 60.2 liter displacement, flagship of QSK marine range. Features Modular Common Rail Fuel System, Quantum electronic controls. Applications include large tugs, offshore supply vessels, fast ferries. IMO Tier II certified. Robust design proven in harsh marine environments. Known as Cummins QSK60-M, QSK 60, or Cummins 60-liter.""",
)

CUMMINS_QSK78 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK78",
    series="QSK",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["18V"],
    power_range_min_kw=2610,
    power_range_max_kw=3028,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.PARTIALLY_VERIFIED,
    data_confidence=0.85,
    searchable_description="""Cummins QSK78 high-speed marine diesel engine. 18-cylinder V-configuration delivering 2610-3028 kW (3500-4060 bhp) at 1800 RPM. 78 liter displacement for high-power marine applications. Features advanced common rail injection, electronic controls. Applications include large offshore vessels, harbor tugs, and ferries. IMO Tier II compliant. Less common than QSK60 but offers higher power. Also referred to as Cummins QSK78-M or QSK 78.""",
)

CUMMINS_QSK95 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK95",
    series="QSK",
    bore_mm=190,
    stroke_mm=210,
    cylinders_available=["16V"],
    power_range_min_kw=2834,
    power_range_max_kw=3730,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Cummins QSK95 high-speed marine diesel engine, the largest Cummins engine ever built. 16-cylinder V-configuration producing 2834-3730 kW (3800-5000 bhp) at 1800 RPM. 95 liter displacement with Modular Common Rail Fuel System. Designed for demanding marine applications including large tugs, offshore vessels, and dredgers. Features advanced Quantum electronic controls. IMO Tier II certified. Known as Cummins QSK95-M, QSK 95, or Cummins 95-liter marine.""",
)

# New Cummins engines for Phase 1
CUMMINS_QST30 = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QST30",
    series="QST",
    bore_mm=140,
    stroke_mm=165,
    cylinders_available=["12V"],
    power_range_min_kw=746,
    power_range_max_kw=1007,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Cummins QST30 high-speed marine diesel engine. 12-cylinder V-configuration delivering 746-1007 kW (1000-1350 bhp) at 1800-2100 RPM. 30 liter displacement with electronic fuel injection. Compact design for workboats, ferries, and crew boats. Features Quantum electronic controls, proven reliability. IMO Tier II certified. Known as Cummins QST30-M, QST 30, or Cummins 30-liter marine.""",
)

CUMMINS_X15_MARINE = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins X15 Marine",
    series="X15",
    bore_mm=137,
    stroke_mm=169,
    cylinders_available=["6L"],
    power_range_min_kw=450,
    power_range_max_kw=600,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Cummins X15 Marine high-speed diesel engine. 6-cylinder inline configuration delivering 450-600 kW (600-800 bhp) at 1800-2100 RPM. 15 liter displacement, compact design for smaller commercial vessels. Features advanced electronic controls, fuel efficiency. IMO Tier II certified. Ideal for workboats, fishing vessels, and crew boats. Known as Cummins X15-M or X15 Marine.""",
)

CUMMINS_QSK38_M = EngineFactSheet(
    manufacturer="Cummins",
    model_name="Cummins QSK38-M",
    series="QSK",
    bore_mm=159,
    stroke_mm=159,
    cylinders_available=["12V"],
    power_range_min_kw=895,
    power_range_max_kw=1193,
    rpm_options=[1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Cummins QSK38-M medium duty marine diesel engine. 12-cylinder V-configuration delivering 895-1193 kW (1200-1600 bhp) at 1800 RPM. 38 liter displacement, medium duty rating for varied applications. Features Quantum electronic controls, versatile power options. IMO Tier II certified. Applications include ferries, workboats, and patrol vessels. Known as Cummins QSK38 Medium or QSK38-M.""",
)

# =============================================================================
# CATERPILLAR 3500 SERIES (High-Speed Marine Diesel)
# =============================================================================

CAT_3512 = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3512",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["12V"],
    power_range_min_kw=761,
    power_range_max_kw=1119,
    rpm_options=[1200, 1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Caterpillar 3512 high-speed marine diesel engine. 12-cylinder V-configuration delivering 761-1119 kW (1020-1500 bhp) at 1200-1800 RPM. 51.8 liter displacement. Versatile 3500 series platform for commercial marine applications. Features ADEM A4 electronic controls, unit injection fuel system. IMO Tier II compliant. Applications include tugs, workboats, ferries, fishing vessels. Extensive Cat dealer network. Also known as Cat 3512, CAT 3512, or Caterpillar 3512 marine.""",
)

CAT_3512B = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3512B",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["12V"],
    power_range_min_kw=1044,
    power_range_max_kw=1400,
    rpm_options=[1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Caterpillar 3512B high-speed marine diesel engine, enhanced B-series variant. 12-cylinder V-configuration producing 1044-1400 kW (1400-1875 bhp) at 1600-1800 RPM. Improved fuel efficiency and reliability over base 3512. Features ADEM electronic controls with enhanced diagnostics. IMO Tier II certified. Popular for commercial fishing, offshore support, and tug applications. Also referred to as Cat 3512B, CAT 3512B, or Caterpillar 3512B marine.""",
)

CAT_3516 = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3516",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=1011,
    power_range_max_kw=1492,
    rpm_options=[1200, 1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Caterpillar 3516 high-speed marine diesel engine. 16-cylinder V-configuration delivering 1011-1492 kW (1355-2000 bhp) at 1200-1800 RPM. 69 liter displacement. Workhorse of the Cat marine fleet for medium-power applications. Features ADEM A4 controls, proven reliability. IMO Tier II compliant. Applications include tugs, OSVs, ferries, and dredgers. Global Cat dealer support. Known as Cat 3516, CAT 3516, or Caterpillar 3516 marine.""",
)

CAT_3516B = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3516B",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=1340,
    power_range_max_kw=1680,
    rpm_options=[1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Caterpillar 3516B high-speed marine diesel engine, enhanced B-series V16. 16-cylinder V-configuration producing 1340-1680 kW (1795-2250 bhp) at 1600-1800 RPM. Improved power output and efficiency over base 3516. Features advanced ADEM electronic controls. IMO Tier II certified. Popular for large tugs, offshore supply vessels, and ferries. Also referred to as Cat 3516B, CAT 3516B, or Caterpillar 3516B marine.""",
)

CAT_3516C = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3516C",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["16V"],
    power_range_min_kw=2000,
    power_range_max_kw=2525,
    rpm_options=[1600, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Caterpillar 3516C high-speed marine diesel engine, flagship C-series variant. 16-cylinder V-configuration delivering 2000-2525 kW (2680-3385 bhp) at 1600-1800 RPM. Highest output in 3500 series. Features common rail fuel injection, ADEM A4 electronic management. IMO Tier II compliant. Designed for large tugs, offshore vessels, ferries requiring maximum power. Also known as Cat 3516C, CAT 3516C, or Caterpillar 3516C HD marine.""",
)

# =============================================================================
# CATERPILLAR C-SERIES (High-Speed Marine Diesel)
# =============================================================================

CAT_C18 = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat C18",
    series="C18",
    bore_mm=145,
    stroke_mm=183,
    cylinders_available=["6L"],
    power_range_min_kw=447,
    power_range_max_kw=597,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Caterpillar C18 high-speed marine diesel engine. 6-cylinder inline configuration delivering 447-597 kW (600-800 bhp) at 1800-2100 RPM. 18.1 liter displacement. Extremely popular workhorse for commercial marine applications. Features ACERT technology, common rail fuel injection, Cat Electronic Control Module. IMO Tier II and Tier III variants available. Applications include workboats, fishing vessels, small tugs, crew boats. Extensive global Cat dealer network. Also known as Cat C18, CAT C18 ACERT, Caterpillar C18 marine, C18 commercial propulsion.""",
)

CAT_C32 = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat C32",
    series="C32",
    bore_mm=145,
    stroke_mm=162,
    cylinders_available=["12V"],
    power_range_min_kw=746,
    power_range_max_kw=1417,
    rpm_options=[1800, 2100, 2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Caterpillar C32 high-speed marine diesel engine. 12-cylinder V-configuration producing 746-1417 kW (1000-1900 bhp) at 1800-2300 RPM. 32.1 liter displacement. One of the most popular high-speed marine engines globally - direct competitor to MTU Series 2000. Features ACERT technology, common rail fuel injection, advanced electronic controls. IMO Tier II standard, Tier III with SCR available. Applications include tugs, OSVs, fast ferries, patrol boats, luxury yachts. Industry-leading Cat dealer support network. Also known as Cat C32, CAT C32 ACERT, Caterpillar C32 marine, C32 high performance.""",
)

CAT_C32B = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat C32B",
    series="C32",
    bore_mm=145,
    stroke_mm=162,
    cylinders_available=["12V"],
    power_range_min_kw=1193,
    power_range_max_kw=1491,
    rpm_options=[2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Caterpillar C32B high-speed marine diesel engine, enhanced B-series variant with higher power density. 12-cylinder V-configuration delivering 1193-1491 kW (1600-2000 bhp) at 2300 RPM. 32.1 liter displacement. Premium variant for demanding applications requiring maximum power from C32 platform. Features enhanced ACERT technology, optimized turbocharging. IMO Tier II certified. Popular for fast ferries, large yachts, patrol vessels. Also referred to as Cat C32B, CAT C32B ACERT, Caterpillar C32B marine.""",
)

# New Caterpillar engines for Phase 1
CAT_C12_9 = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat C12.9",
    series="C12",
    bore_mm=130,
    stroke_mm=162,
    cylinders_available=["6L"],
    power_range_min_kw=373,
    power_range_max_kw=537,
    rpm_options=[1800, 2100, 2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Caterpillar C12.9 high-speed marine diesel engine. 6-cylinder inline configuration delivering 373-537 kW (500-720 bhp) at 1800-2300 RPM. 12.9 liter displacement. Compact design ideal for smaller commercial vessels. Features ACERT technology, electronic fuel injection. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as Cat C12.9, CAT C12, or Caterpillar C12.9 marine.""",
)

CAT_3508C = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat 3508C",
    series="3500",
    bore_mm=170,
    stroke_mm=190,
    cylinders_available=["8V"],
    power_range_min_kw=746,
    power_range_max_kw=895,
    rpm_options=[1200, 1600],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Caterpillar 3508C high-speed marine diesel engine. 8-cylinder V-configuration delivering 746-895 kW (1000-1200 bhp) at 1200-1600 RPM. 34.5 liter displacement. Smaller 3500 series platform for mid-range applications. Features ADEM electronic controls, unit injection. IMO Tier II certified. Applications include workboats, ferries, fishing vessels. Known as Cat 3508C, CAT 3508C, or Caterpillar 3508C marine.""",
)

CAT_C18_ACERT = EngineFactSheet(
    manufacturer="Caterpillar",
    model_name="Cat C18 ACERT",
    series="C18",
    bore_mm=145,
    stroke_mm=183,
    cylinders_available=["6L"],
    power_range_min_kw=533,
    power_range_max_kw=803,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Caterpillar C18 ACERT heavy duty marine diesel engine. 6-cylinder inline configuration delivering 533-803 kW (715-1075 bhp) at 1800-2100 RPM. 18.1 liter displacement with ACERT technology for emissions reduction. Heavy duty rating for demanding commercial applications. IMO Tier II certified. Applications include tugs, workboats, OSVs. Known as Cat C18 ACERT HD, CAT C18 ACERT, or Caterpillar C18 heavy duty.""",
)

# =============================================================================
# MAN ENGINES (High-Speed Marine Diesel)
# =============================================================================

# New MAN engines for Phase 1
MAN_D2676_LE = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN D2676 LE",
    series="D2676",
    bore_mm=126,
    stroke_mm=166,
    cylinders_available=["6L"],
    power_range_min_kw=331,
    power_range_max_kw=537,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""MAN D2676 LE high-speed marine diesel engine. 6-cylinder inline configuration delivering 331-537 kW (450-720 hp) at 1800-2100 RPM. 12.4 liter displacement. Compact high-speed design for smaller commercial vessels. Features common rail injection, electronic management. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as MAN D2676, D26 inline, or MAN 6-cyl marine.""",
)

MAN_D2862_LE463 = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN D2862 LE463",
    series="D2862",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["12V"],
    power_range_min_kw=735,
    power_range_max_kw=1044,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""MAN D2862 LE463 high-speed marine diesel engine from MAN Engines (MAN Truck & Bus). 12-cylinder V-configuration producing 735-1044 kW (1000-1400 mhp) at 2100 RPM. 24.2 liter displacement. Compact design for fast craft, patrol boats, and luxury yachts. Features common rail injection, EDC electronic controls. IMO Tier II certified. Note: This is MAN Engines (truck-derived), not MAN Energy Solutions (large engines). Known as MAN D2862, D28 marine, or MAN V12 marine.""",
)

MAN_D2868_LE433 = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN D2868 LE433",
    series="D2868",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["8V"],
    power_range_min_kw=441,
    power_range_max_kw=882,
    rpm_options=[2100, 2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""MAN D2868 LE433 high-speed marine diesel engine from MAN Engines. 8-cylinder V-configuration producing 441-882 kW (600-1200 hp) at 2100-2300 RPM. 16.1 liter displacement. Compact and lightweight for fast boats, pilot vessels, and small ferries. Common rail injection with electronic management. IMO Tier II compliant. Part of MAN Engines marine portfolio (MAN Truck & Bus division). Also referred to as MAN D2868, D26 marine, or MAN V8 marine.""",
)

# New MAN engine variants for Phase 1
MAN_D2862_LE443 = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN D2862 LE443",
    series="D2862",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["12V"],
    power_range_min_kw=882,
    power_range_max_kw=1176,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""MAN D2862 LE443 heavy duty marine diesel engine. 12-cylinder V-configuration producing 882-1176 kW (1200-1575 hp) at 2100 RPM. 24.2 liter displacement. Heavy duty rating for commercial applications requiring durability. Features common rail injection, EDC electronic controls. IMO Tier II certified. Applications include tugs, OSVs, patrol vessels. Known as MAN D2862 HD, D28 heavy duty, or MAN V12 commercial.""",
)

MAN_D2868_LE423 = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN D2868 LE423",
    series="D2868",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["8V"],
    power_range_min_kw=735,
    power_range_max_kw=993,
    rpm_options=[2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""MAN D2868 LE423 heavy duty marine diesel engine. 8-cylinder V-configuration producing 735-993 kW (1000-1330 hp) at 2100 RPM. 16.1 liter displacement. Heavy duty rating for demanding commercial operations. Features common rail injection, electronic management. IMO Tier II certified. Applications include tugs, workboats, patrol vessels. Known as MAN D2868 HD, D26 heavy duty, or MAN V8 commercial.""",
)

MAN_V12_2000 = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN V12-2000",
    series="V12-2000",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["12V"],
    power_range_min_kw=1044,
    power_range_max_kw=1324,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""MAN V12-2000 high-speed marine diesel engine. 12-cylinder V-configuration producing 1044-1324 kW (1400-1775 hp) at 1800-2100 RPM. 24.2 liter displacement. Direct competitor to MTU Series 2000. Features common rail injection, advanced electronic management. IMO Tier II certified. Applications include OSVs, ferries, patrol vessels. Known as MAN V12-2000, MAN 2000 marine, or V12 high-speed.""",
)

MAN_V12_2000CR = EngineFactSheet(
    manufacturer="MAN Engines",
    model_name="MAN V12-2000CR",
    series="V12-2000",
    bore_mm=128,
    stroke_mm=157,
    cylinders_available=["12V"],
    power_range_min_kw=1193,
    power_range_max_kw=1471,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""MAN V12-2000CR common rail heavy duty marine diesel engine. 12-cylinder V-configuration producing 1193-1471 kW (1600-1970 hp) at 1800-2100 RPM. 24.2 liter displacement. Flagship MAN marine engine with common rail fuel system. Features advanced electronic controls, high power density. IMO Tier II certified. Applications include tugs, OSVs, naval vessels. Known as MAN V12-2000CR, MAN CR marine, or V12 flagship.""",
)

# =============================================================================
# VOLVO PENTA (High-Speed Marine Diesel)
# =============================================================================

# New Volvo engines for Phase 1
VOLVO_D11 = EngineFactSheet(
    manufacturer="Volvo Penta",
    model_name="Volvo Penta D11",
    series="D11",
    bore_mm=123,
    stroke_mm=152,
    cylinders_available=["6L"],
    power_range_min_kw=298,
    power_range_max_kw=406,
    rpm_options=[1800, 2100, 2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Volvo Penta D11 high-speed marine diesel engine. 6-cylinder inline configuration producing 298-406 kW (400-545 hp) at 1800-2300 RPM. 10.8 liter displacement. Compact commercial marine design. Features common rail injection, EMS electronic management. IMO Tier II certified. Applications include workboats, fishing vessels, crew boats. Known as Volvo D11 marine, Volvo Penta D11, or D11 commercial.""",
)

VOLVO_D13_IPS1200 = EngineFactSheet(
    manufacturer="Volvo Penta",
    model_name="Volvo Penta D13-IPS1200",
    series="D13",
    bore_mm=131,
    stroke_mm=158,
    cylinders_available=["6L"],
    power_range_min_kw=588,
    power_range_max_kw=662,
    rpm_options=[2300, 2400],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Volvo Penta D13-IPS1200 high-speed marine diesel engine with IPS pod drive. 6-cylinder inline producing 588-662 kW (800-900 hp) at 2300-2400 RPM. 12.8 liter displacement. IPS system with forward-facing counter-rotating propellers. Features common rail injection, EVC electronic controls. IMO Tier II certified. Applications include yachts, patrol vessels, pilot boats. Known as Volvo Penta IPS1200, D13 IPS, or Volvo IPS pod.""",
)

VOLVO_D13_IPS1350 = EngineFactSheet(
    manufacturer="Volvo Penta",
    model_name="Volvo Penta D13-IPS1350",
    series="D13",
    bore_mm=131,
    stroke_mm=158,
    cylinders_available=["6L"],
    power_range_min_kw=662,
    power_range_max_kw=735,
    rpm_options=[2300, 2400],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Volvo Penta D13-IPS1350 high-speed marine diesel engine with IPS pod drive system. 6-cylinder inline configuration producing 662-735 kW (900-1000 hp) at 2300-2400 RPM. 12.8 liter displacement. Revolutionary IPS (Inboard Performance System) with forward-facing counter-rotating propellers. Features common rail injection, EVC electronic controls. IMO Tier II compliant. Ideal for luxury motor yachts and fast cruisers. Also known as Volvo Penta IPS1350, D13 IPS, or Volvo IPS pod system.""",
)

VOLVO_D13_800 = EngineFactSheet(
    manufacturer="Volvo Penta",
    model_name="Volvo Penta D13-800",
    series="D13",
    bore_mm=131,
    stroke_mm=158,
    cylinders_available=["6L"],
    power_range_min_kw=515,
    power_range_max_kw=588,
    rpm_options=[2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Volvo Penta D13-800 high-speed marine diesel engine for commercial applications. 6-cylinder inline configuration producing 515-588 kW (700-800 hp) at 2300 RPM. 12.8 liter displacement. Shaft-line installation for workboats, small ferries, and fishing vessels. Features common rail fuel injection, EMS electronic management. IMO Tier II certified. Excellent fuel efficiency and reliability. Also referred to as Volvo D13 marine, Volvo Penta D13-800, or D13 commercial.""",
)

# =============================================================================
# YANMAR (High-Speed Marine Diesel)
# =============================================================================

YANMAR_6AYM_ETE = EngineFactSheet(
    manufacturer="Yanmar",
    model_name="Yanmar 6AYM-ETE",
    series="6AY",
    bore_mm=155,
    stroke_mm=180,
    cylinders_available=["6L"],
    power_range_min_kw=485,
    power_range_max_kw=563,
    rpm_options=[1900],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Yanmar 6AYM-ETE high-speed marine diesel engine. 6-cylinder inline configuration producing 485-563 kW (650-755 hp) at 1900 RPM. 20.4 liter displacement. Japanese-built reliability for workboats, fishing vessels, and small ferries. Features electronic fuel injection with ETE turbocharging. IMO Tier II compliant. Known for durability and fuel economy. Popular in Asian markets. Also referred to as Yanmar 6AYM, 6AY marine, or Yanmar AYM series.""",
)

YANMAR_6AYEM_GT = EngineFactSheet(
    manufacturer="Yanmar",
    model_name="Yanmar 6AYEM-GT",
    series="6AY",
    bore_mm=155,
    stroke_mm=180,
    cylinders_available=["6L"],
    power_range_min_kw=485,
    power_range_max_kw=749,
    rpm_options=[1840, 2000],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.95,
    searchable_description="""Yanmar 6AYEM-GT high-speed marine diesel engine with enhanced GT turbocharging. 6-cylinder inline configuration producing 485-749 kW (650-1005 hp) at 1840-2000 RPM. 20.4 liter displacement. Higher output variant of the AY series for fast workboats and patrol craft. Features advanced turbocharging for improved response. IMO Tier II certified. Excellent power-to-weight ratio. Known as Yanmar 6AYEM, 6AY-GT marine, or Yanmar GT series.""",
)

# New Yanmar engines for Phase 1
YANMAR_8AYM_WET = EngineFactSheet(
    manufacturer="Yanmar",
    model_name="Yanmar 8AYM-WET",
    series="8AY",
    bore_mm=155,
    stroke_mm=180,
    cylinders_available=["8V"],
    power_range_min_kw=637,
    power_range_max_kw=716,
    rpm_options=[1900],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Yanmar 8AYM-WET high-speed marine diesel engine. 8-cylinder V-configuration producing 637-716 kW (855-960 hp) at 1900 RPM. 27.2 liter displacement. Wet exhaust design for commercial applications. Features electronic fuel injection, advanced turbocharging. IMO Tier II certified. Applications include ferries, OSVs, patrol vessels. Known as Yanmar 8AYM, 8AY marine, or Yanmar V8 commercial.""",
)

YANMAR_12AYM_WGT = EngineFactSheet(
    manufacturer="Yanmar",
    model_name="Yanmar 12AYM-WGT",
    series="12AY",
    bore_mm=155,
    stroke_mm=180,
    cylinders_available=["12V"],
    power_range_min_kw=955,
    power_range_max_kw=1074,
    rpm_options=[1900],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Yanmar 12AYM-WGT high-speed marine diesel engine. 12-cylinder V-configuration producing 955-1074 kW (1280-1440 hp) at 1900 RPM. 40.8 liter displacement. Flagship Yanmar marine engine with wet exhaust and GT turbo. Features electronic fuel injection, advanced controls. IMO Tier II certified. Applications include ferries, OSVs, naval vessels. Known as Yanmar 12AYM, 12AY marine, or Yanmar V12 flagship.""",
)

# New Volvo heavy duty for Phase 1
VOLVO_D13_MH = EngineFactSheet(
    manufacturer="Volvo Penta",
    model_name="Volvo Penta D13 MH",
    series="D13",
    bore_mm=131,
    stroke_mm=158,
    cylinders_available=["6L"],
    power_range_min_kw=625,
    power_range_max_kw=735,
    rpm_options=[2100, 2300],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.90,
    searchable_description="""Volvo Penta D13 MH heavy duty marine diesel engine. 6-cylinder inline producing 625-735 kW (840-985 hp) at 2100-2300 RPM. 12.8 liter displacement. Heavy duty commercial rating for demanding operations. Features common rail injection, EMS electronic management. IMO Tier II certified. Applications include tugs, OSVs, workboats. Known as Volvo D13 MH, Volvo Penta D13 HD, or D13 heavy duty.""",
)

# =============================================================================
# WEICHAI (Chinese High-Speed Marine Diesel)
# =============================================================================

WEICHAI_WP13 = EngineFactSheet(
    manufacturer="WEICHAI",
    model_name="WEICHAI WP13",
    series="WP13",
    bore_mm=127,
    stroke_mm=165,
    cylinders_available=["6L"],
    power_range_min_kw=368,
    power_range_max_kw=537,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""WEICHAI WP13 high-speed marine diesel engine from Weichai Power, China's largest diesel engine manufacturer. 6-cylinder inline configuration producing 368-537 kW (500-730 hp) at 1800-2100 RPM. 12.9 liter displacement. Highly competitive pricing - typically 40-50% below Western brands. Popular in Asian tug, workboat, and fishing vessel markets. Features electronic fuel injection, turbocharging. IMO Tier II certified. Also known as Weichai WP13, Weichai 13-liter, or WP13C marine. Baudouin technology base.""",
)

WEICHAI_WHM6160 = EngineFactSheet(
    manufacturer="WEICHAI",
    model_name="WEICHAI WHM6160",
    series="WHM6160",
    bore_mm=160,
    stroke_mm=180,
    cylinders_available=["6L", "8V", "12V"],
    power_range_min_kw=550,
    power_range_max_kw=1200,
    rpm_options=[1500, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""WEICHAI WHM6160 high-speed marine diesel engine series. Available in 6L, 8V, and 12V configurations producing 550-1200 kW (750-1600 hp) at 1500-1800 RPM. Designed for commercial marine applications including tugs, OSVs, and cargo vessels. Aggressive pricing strategy makes it strong competitor in Asian markets. Features common rail injection, electronic controls. IMO Tier II compliant. Known as Weichai WHM6160, 6160 series, or Weichai medium-power marine. Growing presence in Southeast Asia, Middle East, Africa.""",
)

WEICHAI_12M33 = EngineFactSheet(
    manufacturer="WEICHAI",
    model_name="WEICHAI 12M33",
    series="M33",
    bore_mm=170,
    stroke_mm=195,
    cylinders_available=["12V", "16V"],
    power_range_min_kw=1100,
    power_range_max_kw=2200,
    rpm_options=[1500, 1800],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.PARTIALLY_VERIFIED,
    data_confidence=0.8,
    searchable_description="""WEICHAI 12M33 high-speed marine diesel engine, high-power offering from China's leading engine manufacturer. 12 and 16-cylinder V-configurations producing 1100-2200 kW (1475-2950 hp) at 1500-1800 RPM. Competes directly with MTU Series 4000 and Cummins QSK series at significantly lower price point. Features modern common rail injection, electronic management. IMO Tier II certified. Growing adoption in Chinese-built vessels, Asian fleet operators. Also known as Weichai M33 series, 12M33C, 16M33C marine.""",
)

# =============================================================================
# FPT INDUSTRIAL / IVECO (European High-Speed Marine Diesel)
# =============================================================================

FPT_C13_500 = EngineFactSheet(
    manufacturer="FPT Industrial",
    model_name="FPT Cursor 13",
    series="Cursor",
    bore_mm=135,
    stroke_mm=150,
    cylinders_available=["6L"],
    power_range_min_kw=368,
    power_range_max_kw=509,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""FPT Cursor 13 high-speed marine diesel engine from FPT Industrial (Iveco/CNH group). 6-cylinder inline configuration producing 368-509 kW (500-690 hp) at 1800-2100 RPM. 12.9 liter displacement. Popular in European fishing and workboat markets. Features common rail injection, HI-eSCR technology for Tier III compliance. Competitive pricing versus Caterpillar and Cummins. Known as FPT Cursor 13, Iveco Cursor 13, NEF 13, C13 marine. Strong presence in Mediterranean and Northern European markets.""",
)

FPT_C16_600 = EngineFactSheet(
    manufacturer="FPT Industrial",
    model_name="FPT Cursor 16",
    series="Cursor",
    bore_mm=135,
    stroke_mm=150,
    cylinders_available=["6L"],
    power_range_min_kw=485,
    power_range_max_kw=662,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""FPT Cursor 16 high-speed marine diesel engine from FPT Industrial (Iveco/CNH group). 6-cylinder inline configuration producing 485-662 kW (660-900 hp) at 1800-2100 RPM. 15.9 liter displacement. Largest Cursor series marine engine. Applications include fishing vessels, tugs, ferries, workboats. Features advanced common rail injection, available with HI-eSCR for IMO Tier III. Known as FPT Cursor 16, Iveco Cursor 16, C16 marine. Competitive alternative to MAN Engines and Volvo Penta in European markets.""",
)

# =============================================================================
# SCANIA (Swedish High-Speed Marine Diesel)
# =============================================================================

SCANIA_DI13 = EngineFactSheet(
    manufacturer="Scania",
    model_name="Scania DI13",
    series="DI13",
    bore_mm=130,
    stroke_mm=160,
    cylinders_available=["6L"],
    power_range_min_kw=405,
    power_range_max_kw=588,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Scania DI13 high-speed marine diesel engine from Scania (Traton Group). 6-cylinder inline configuration producing 405-588 kW (550-800 hp) at 1800-2100 RPM. 12.7 liter displacement. Swedish engineering with excellent reliability reputation. Direct competitor to Volvo Penta D13. Features XPI common rail fuel injection, EMS electronic management. IMO Tier II standard, Tier III with SCR available. Popular in Scandinavian markets for ferries, workboats, fishing vessels. Known as Scania DI13, DI13M, or Scania 13-liter marine.""",
)

SCANIA_DI16 = EngineFactSheet(
    manufacturer="Scania",
    model_name="Scania DI16",
    series="DI16",
    bore_mm=130,
    stroke_mm=160,
    cylinders_available=["8V"],
    power_range_min_kw=588,
    power_range_max_kw=809,
    rpm_options=[1800, 2100],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.9,
    searchable_description="""Scania DI16 high-speed marine diesel engine from Scania (Traton Group). 8-cylinder V-configuration producing 588-809 kW (800-1100 hp) at 1800-2100 RPM. 16.4 liter displacement. Largest Scania marine engine, competing with Cat C18 and Volvo D13 IPS. Swedish quality engineering, excellent fuel efficiency. Features XPI common rail injection, advanced EMS controls. IMO Tier II certified, Tier III with SCR. Growing market share in Northern Europe for ferries, pilot boats, patrol vessels. Known as Scania DI16, DI16M, V8 marine, or Scania 16-liter.""",
)

# =============================================================================
# WARTSILA HIGH-SPEED ENGINES (14 and 20 Series)
# Source: https://www.wartsila.com/marine/products/engines
# Note: Only HIGH-SPEED engines (>1000 RPM) for apple-to-apple comparison
# =============================================================================

WARTSILA_6L14 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 6L14",
    series="Wartsila 14",
    bore_mm=140,
    stroke_mm=165,
    cylinders_available=["6L"],
    power_range_min_kw=735,
    power_range_max_kw=882,
    rpm_options=[1500],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 6L14 high-speed marine diesel engine from Wartsila Corporation. 6-cylinder inline configuration producing 735-882 kW (1000-1200 hp) at 1500 RPM. 14cm bore, compact high-speed design for workboats, ferries, and tugs. Features common rail fuel injection, electronic controls. IMO Tier II certified. Compact footprint ideal for space-constrained engine rooms. Known as Wartsila 6L14, W14, or Wartsila 14-series inline.""",
)

WARTSILA_8L14 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 8L14",
    series="Wartsila 14",
    bore_mm=140,
    stroke_mm=165,
    cylinders_available=["8L"],
    power_range_min_kw=980,
    power_range_max_kw=1176,
    rpm_options=[1500],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 8L14 high-speed marine diesel engine from Wartsila Corporation. 8-cylinder inline configuration producing 980-1176 kW (1315-1580 hp) at 1500 RPM. 14cm bore, extended inline design for workboats, ferries, and offshore support vessels. Features common rail fuel injection, electronic management. IMO Tier II certified. Known as Wartsila 8L14, W14, or Wartsila 14-series 8-cylinder.""",
)

WARTSILA_12V14 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 12V14",
    series="Wartsila 14",
    bore_mm=140,
    stroke_mm=165,
    cylinders_available=["12V"],
    power_range_min_kw=1470,
    power_range_max_kw=1764,
    rpm_options=[1200],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 12V14 high-speed marine diesel engine from Wartsila Corporation. 12-cylinder V-configuration producing 1470-1764 kW (1970-2370 hp) at 1200 RPM. 14cm bore, V-configuration for heavy-duty commercial applications. Features common rail fuel injection, advanced electronic controls. IMO Tier II certified. Applications include ferries, offshore supply vessels, and tugs. Known as Wartsila 12V14, W14V, or Wartsila 14-series V12.""",
)

WARTSILA_6L20 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 6L20",
    series="Wartsila 20",
    bore_mm=200,
    stroke_mm=280,
    cylinders_available=["6L"],
    power_range_min_kw=1000,
    power_range_max_kw=1200,
    rpm_options=[1200],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 6L20 high-speed marine diesel engine from Wartsila Corporation. 6-cylinder inline configuration producing 1000-1200 kW (1340-1610 hp) at 1200 RPM. 20cm bore, borderline high-speed for commercial marine applications. Features common rail injection, electronic engine management. IMO Tier II certified. Applications include ferries, offshore support vessels, and tugs. Known as Wartsila 6L20, W20, or Wartsila 20-series inline.""",
)

WARTSILA_8L20 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 8L20",
    series="Wartsila 20",
    bore_mm=200,
    stroke_mm=280,
    cylinders_available=["8L"],
    power_range_min_kw=1333,
    power_range_max_kw=1600,
    rpm_options=[1200],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 8L20 high-speed marine diesel engine from Wartsila Corporation. 8-cylinder inline configuration producing 1333-1600 kW (1790-2145 hp) at 1200 RPM. 20cm bore, heavy-duty commercial marine applications. Features common rail fuel injection, advanced electronic controls. IMO Tier II certified. Applications include ferries, offshore supply vessels, tugs, and workboats. Known as Wartsila 8L20, W20, or Wartsila 20-series 8-cylinder.""",
)

WARTSILA_9L20 = EngineFactSheet(
    manufacturer="Wartsila",
    model_name="Wartsila 9L20",
    series="Wartsila 20",
    bore_mm=200,
    stroke_mm=280,
    cylinders_available=["9L"],
    power_range_min_kw=1500,
    power_range_max_kw=1800,
    rpm_options=[1200],
    fuel_capability=FuelCapability.DIESEL_ONLY,
    fuel_types=["diesel", "mdo", "mgo"],
    emissions_tier=EmissionsTier.TIER_II,
    verification_status=VerificationStatus.VERIFIED,
    data_confidence=0.85,
    searchable_description="""Wartsila 9L20 high-speed marine diesel engine from Wartsila Corporation. 9-cylinder inline configuration producing 1500-1800 kW (2010-2415 hp) at 1200 RPM. 20cm bore, largest inline variant of the 20-series. Features common rail fuel injection, sophisticated electronic controls. IMO Tier II certified. Applications include ferries, offshore support vessels, and naval applications. Known as Wartsila 9L20, W20, or Wartsila 20-series 9-cylinder.""",
)

# =============================================================================
# ALL ENGINE FACT SHEETS (for iteration)
# =============================================================================

ALL_ENGINE_FACT_SHEETS = [
    # MTU Series 2000 (5 engines)
    MTU_8V2000_M72,
    MTU_10V2000_M72,
    MTU_12V2000_M93,
    MTU_16V2000_M93,
    MTU_16V2000_M96,
    # MTU Series 4000 Diesel (7 engines)
    MTU_12V4000_M63,
    MTU_16V4000_M63,
    MTU_12V4000_M73,
    MTU_16V4000_M73,
    MTU_12V4000_M93,
    MTU_16V4000_M93,
    MTU_20V4000_M93,
    # MTU Series 4000 Gas (3 engines)
    MTU_12V4000_M05N,
    MTU_16V4000_M05N,
    MTU_20V4000_M05N,
    # MTU Series 8000 (2 engines)
    MTU_16V8000_M71,
    MTU_20V8000_M91,
    # Cummins QSK/QST/X15 (8 engines)
    CUMMINS_QSK38,
    CUMMINS_QSK50,
    CUMMINS_QSK60,
    CUMMINS_QSK78,
    CUMMINS_QSK95,
    CUMMINS_QST30,
    CUMMINS_X15_MARINE,
    CUMMINS_QSK38_M,
    # Caterpillar 3500 (6 engines)
    CAT_3508C,
    CAT_3512,
    CAT_3512B,
    CAT_3516,
    CAT_3516B,
    CAT_3516C,
    # Caterpillar C-Series (6 engines)
    CAT_C12_9,
    CAT_C18,
    CAT_C18_ACERT,
    CAT_C32,
    CAT_C32B,
    # MAN Engines (8 engines)
    MAN_D2676_LE,
    MAN_D2862_LE463,
    MAN_D2862_LE443,
    MAN_D2868_LE433,
    MAN_D2868_LE423,
    MAN_V12_2000,
    MAN_V12_2000CR,
    # Volvo Penta (5 engines)
    VOLVO_D11,
    VOLVO_D13_IPS1200,
    VOLVO_D13_IPS1350,
    VOLVO_D13_800,
    VOLVO_D13_MH,
    # Yanmar (4 engines)
    YANMAR_6AYM_ETE,
    YANMAR_6AYEM_GT,
    YANMAR_8AYM_WET,
    YANMAR_12AYM_WGT,
    # WEICHAI (3 engines)
    WEICHAI_WP13,
    WEICHAI_WHM6160,
    WEICHAI_12M33,
    # FPT Industrial (2 engines)
    FPT_C13_500,
    FPT_C16_600,
    # Scania (2 engines)
    SCANIA_DI13,
    SCANIA_DI16,
    # Wartsila High-Speed (6 engines)
    WARTSILA_6L14,
    WARTSILA_8L14,
    WARTSILA_12V14,
    WARTSILA_6L20,
    WARTSILA_8L20,
    WARTSILA_9L20,
]


def get_engine_by_model(model_name: str) -> Optional[EngineFactSheet]:
    """Get engine fact sheet by model name."""
    for engine in ALL_ENGINE_FACT_SHEETS:
        if engine.model_name.lower() == model_name.lower():
            return engine
        if model_name.lower() in engine.model_name.lower():
            return engine
    return None


def get_engines_by_manufacturer(manufacturer: str) -> list[EngineFactSheet]:
    """Get all engines for a manufacturer."""
    return [
        e
        for e in ALL_ENGINE_FACT_SHEETS
        if manufacturer.lower() in e.manufacturer.lower()
    ]


def get_engines_in_power_range(min_kw: float, max_kw: float) -> list[EngineFactSheet]:
    """Get engines that operate in the specified power range."""
    results = []
    for engine in ALL_ENGINE_FACT_SHEETS:
        # Check if ranges overlap
        if engine.power_range_min_kw <= max_kw and engine.power_range_max_kw >= min_kw:
            results.append(engine)
    return results


def get_engines_by_rpm_range(min_rpm: int, max_rpm: int) -> list[EngineFactSheet]:
    """Get engines that operate in the specified RPM range."""
    results = []
    for engine in ALL_ENGINE_FACT_SHEETS:
        for rpm in engine.rpm_options:
            if min_rpm <= rpm <= max_rpm:
                results.append(engine)
                break
    return results


def get_verified_engines() -> list[EngineFactSheet]:
    """Get engines with fully verified specifications."""
    return [
        e
        for e in ALL_ENGINE_FACT_SHEETS
        if e.verification_status == VerificationStatus.VERIFIED
    ]


def get_verification_summary() -> dict:
    """Get summary of data verification status."""
    verified = len(
        [
            e
            for e in ALL_ENGINE_FACT_SHEETS
            if e.verification_status == VerificationStatus.VERIFIED
        ]
    )
    partial = len(
        [
            e
            for e in ALL_ENGINE_FACT_SHEETS
            if e.verification_status == VerificationStatus.PARTIALLY_VERIFIED
        ]
    )
    unverified = len(
        [
            e
            for e in ALL_ENGINE_FACT_SHEETS
            if e.verification_status == VerificationStatus.UNVERIFIED
        ]
    )

    avg_confidence = sum(e.data_confidence for e in ALL_ENGINE_FACT_SHEETS) / len(
        ALL_ENGINE_FACT_SHEETS
    )

    return {
        "total_engines": len(ALL_ENGINE_FACT_SHEETS),
        "verified": verified,
        "partially_verified": partial,
        "unverified": unverified,
        "average_confidence": round(avg_confidence, 2),
        "manufacturers": len(set(e.manufacturer for e in ALL_ENGINE_FACT_SHEETS)),
    }
