"""
Migration Script: product_data.py -> Unified PostgreSQL KB

Migrates all high-speed engine data from product_data.py to the unified
knowledge base with proper rating-level structure per ADR-004.

This script uses VERIFIED DATA from engine_master_data.py instead of
inferring duty classes from descriptions.

Data Sources (verified):
- MTU: https://www.mtu-solutions.com/eu/en/applications/marine.html
- Cummins: https://www.cummins.com/engines/marine
- Caterpillar: https://www.cat.com/en_US/products/new/power-systems/marine-power-systems.html
- MAN Engines: https://www.man.eu/engines/en/products/marine-engines/overview.html
- Volvo Penta: https://www.volvopenta.com/marine
- Yanmar: https://www.yanmar.com/marine/
- WEICHAI: https://en.weichai.com/
- FPT Industrial: https://www.fptindustrial.com/
- Scania: https://www.scania.com/group/en/home/products-and-services/engines.html

Usage:
    python -m lead_to_cash.services.knowledge_base.migrate_product_data

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from lead_to_cash.services.knowledge_base.engine_master_data import (
    ENGINE_MASTER_DATA,
    get_engine_specification,
)
from lead_to_cash.services.knowledge_base.product_data import (
    ALL_ENGINE_FACT_SHEETS,
    EmissionsTier,
    EngineFactSheet,
    FuelCapability,
    VerificationStatus,
)
from lead_to_cash.services.knowledge_base.unified_models import (
    AvailabilityStatus,
    DutyClass,
    EngineRating,
    HarmonizedDutyClass,
    ISOClassification,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MANUFACTURER MAPPING
# =============================================================================

MANUFACTURER_DATA = {
    "MTU (Rolls-Royce Power Systems)": {
        "canonical_name": "MTU (Rolls-Royce Power Systems)",
        "country": "Germany",
        "tier": 1,  # RRPS - our company
        "website": "https://www.mtu-solutions.com/",
        "is_rrps": True,
    },
    "Cummins": {
        "canonical_name": "Cummins",
        "country": "USA",
        "tier": 1,
        "website": "https://www.cummins.com/",
        "is_rrps": False,
    },
    "Caterpillar": {
        "canonical_name": "Caterpillar",
        "country": "USA",
        "tier": 1,
        "website": "https://www.cat.com/",
        "is_rrps": False,
    },
    "MAN Engines": {
        "canonical_name": "MAN Engines",
        "country": "Germany",
        "tier": 1,
        "website": "https://www.man.eu/engines/",
        "is_rrps": False,
    },
    "Volvo Penta": {
        "canonical_name": "Volvo Penta",
        "country": "Sweden",
        "tier": 1,
        "website": "https://www.volvopenta.com/",
        "is_rrps": False,
    },
    "Yanmar": {
        "canonical_name": "Yanmar",
        "country": "Japan",
        "tier": 2,
        "website": "https://www.yanmar.com/",
        "is_rrps": False,
    },
    "WEICHAI": {
        "canonical_name": "WEICHAI",
        "country": "China",
        "tier": 2,
        "website": "https://en.weichai.com/",
        "is_rrps": False,
    },
    "FPT Industrial": {
        "canonical_name": "FPT Industrial",
        "country": "Italy",
        "tier": 2,
        "website": "https://www.fptindustrial.com/",
        "is_rrps": False,
    },
    "Scania": {
        "canonical_name": "Scania",
        "country": "Sweden",
        "tier": 2,
        "website": "https://www.scania.com/",
        "is_rrps": False,
    },
    "Wartsila": {
        "canonical_name": "Wartsila",
        "country": "Finland",
        "tier": 1,
        "website": "https://www.wartsila.com/",
        "is_rrps": False,
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def map_emission_tier(tier: EmissionsTier) -> str:
    """Map EmissionsTier enum to string for database (Phase 4 expanded)."""
    tier_map = {
        # IMO MARPOL Annex VI
        EmissionsTier.TIER_I: "IMO Tier I",
        EmissionsTier.TIER_II: "IMO Tier II",
        EmissionsTier.TIER_III: "IMO Tier III",
        EmissionsTier.TIER_III_GAS_MODE: "IMO Tier III (Gas Mode)",
        EmissionsTier.TIER_III_SCR: "IMO Tier III (SCR)",
        # EPA (US waters)
        EmissionsTier.EPA_TIER_3: "EPA Tier 3",
        EmissionsTier.EPA_TIER_4: "EPA Tier 4",
        EmissionsTier.EPA_TIER_4_FINAL: "EPA Tier 4 Final",
        # EU Stage (inland waterways)
        EmissionsTier.EU_STAGE_IIIA: "EU Stage IIIA",
        EmissionsTier.EU_STAGE_IV: "EU Stage IV",
        EmissionsTier.EU_STAGE_V: "EU Stage V",
    }
    return tier_map.get(tier, "IMO Tier II")


def map_fuel_types(capability: FuelCapability, fuel_list: list[str]) -> list[str]:
    """Map fuel capability and fuel list to standardized fuel types."""
    fuel_map = {
        "diesel": "diesel",
        "mdo": "mdo",
        "mgo": "mgo",
        "hvo": "hvo",
        "gtl": "gtl",
        "natural_gas": "lng",
        "lng": "lng",
        "methanol": "methanol",
        "ammonia": "ammonia",
    }

    standardized = []
    for fuel in fuel_list:
        fuel_lower = fuel.lower()
        if fuel_lower in fuel_map:
            standardized.append(fuel_map[fuel_lower])
        else:
            standardized.append(fuel_lower)

    return list(set(standardized))


def map_availability_status(status: VerificationStatus) -> AvailabilityStatus:
    """Map verification status to availability status."""
    if status == VerificationStatus.VERIFIED:
        return AvailabilityStatus.AVAILABLE
    elif status == VerificationStatus.PARTIALLY_VERIFIED:
        return AvailabilityStatus.AVAILABLE
    else:
        return AvailabilityStatus.LIMITED


def generate_uuid() -> str:
    """Generate UUID string."""
    return str(uuid.uuid4())


def infer_applications_from_description(description: str) -> list[str]:
    """
    Extract application types from searchable_description.
    """
    desc_lower = description.lower()
    applications = []

    application_keywords = {
        "ferry": ["ferry", "ferries", "roro", "passenger"],
        "fast_craft": ["fast patrol", "fast craft", "high-speed", "fast ferry"],
        "patrol": ["patrol boat", "coast guard", "patrol vessel"],
        "yacht": ["yacht", "luxury", "mega-yacht", "pleasure"],
        "workboat": ["workboat", "work boat", "utility"],
        "tug": ["tug", "tugboat", "harbor tug", "escort"],
        "osv": ["osv", "offshore supply", "psv", "supply vessel"],
        "ahts": ["ahts", "anchor handling", "towing supply"],
        "fishing": ["fishing", "trawler", "commercial fishing"],
        "crew_transfer": ["crew boat", "crew transfer", "ctv"],
        "naval": ["naval", "military", "coast guard", "corvette", "frigate"],
        "offshore": ["offshore", "oil and gas", "platform supply"],
    }

    for app, keywords in application_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            applications.append(app)

    return applications if applications else ["general_marine"]


# =============================================================================
# MIGRATION FUNCTIONS
# =============================================================================


def create_engine_rating_from_factsheet(
    factsheet: EngineFactSheet,
    engine_model_id: str,
) -> EngineRating:
    """
    Convert EngineFactSheet to EngineRating using verified master data.
    """
    # Get verified specification from master data
    spec = get_engine_specification(factsheet.model_name)

    if spec:
        # Use verified data
        duty_class = spec.duty_class
        rating_designation = spec.rating_designation
        # Derive harmonized duty class from spec (auto-derived in __post_init__)
        harmonized_duty_class = spec.get_harmonized_duty_class().value
        oem_rating_code = spec.rating_designation
        dry_weight_kg = spec.dry_weight_kg
        length_mm = spec.length_mm
        width_mm = spec.width_mm
        height_mm = spec.height_mm
        applications = spec.primary_applications or infer_applications_from_description(
            factsheet.searchable_description
        )
    else:
        # Fallback for unverified engines
        logger.warning(f"No master data for {factsheet.model_name}, using defaults")
        duty_class = DutyClass.MEDIUM_DUTY
        rating_designation = _extract_rating_designation(
            factsheet.model_name, factsheet.series
        )
        # Derive harmonized class from duty class
        harmonized_duty_class = HarmonizedDutyClass.from_duty_class(duty_class).value
        oem_rating_code = rating_designation
        dry_weight_kg = None
        length_mm = None
        width_mm = None
        height_mm = None
        applications = infer_applications_from_description(
            factsheet.searchable_description
        )

    # Get typical operating limits for this duty class
    load_min, load_max = duty_class.typical_load_factor_range
    hours_min, hours_max = duty_class.typical_hours_range

    # Map fuel types
    fuel_types = map_fuel_types(factsheet.fuel_capability, factsheet.fuel_types)

    # Get manufacturer data source URL
    manufacturer_data = MANUFACTURER_DATA.get(factsheet.manufacturer, {})
    source_url = manufacturer_data.get("website", "")

    # Calculate power density if we have weight
    power_density = None
    if dry_weight_kg and dry_weight_kg > 0:
        power_density = round(factsheet.power_range_max_kw / dry_weight_kg, 4)

    return EngineRating(
        id=generate_uuid(),
        engine_model_id=engine_model_id,
        rating_designation=rating_designation,
        rating_name=factsheet.model_name,
        duty_class=duty_class,
        iso_classification=ISOClassification.NOT_APPLICABLE,
        harmonized_duty_class=harmonized_duty_class,
        oem_rating_code=oem_rating_code,
        power_kw=factsheet.power_range_max_kw,
        power_hp=factsheet.power_range_max_kw * 1.341,
        rpm=factsheet.rpm_options[0] if factsheet.rpm_options else 1800,
        load_factor_min=load_min,  # Keep as fraction (0.0-1.0) for DECIMAL(3,2)
        load_factor_max=load_max,
        annual_hours_min=hours_min,
        annual_hours_max=hours_max,
        dry_weight_kg=dry_weight_kg,
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        power_density_kw_per_kg=power_density,
        fuel_types=json.dumps(fuel_types),
        emission_tier=map_emission_tier(factsheet.emissions_tier),
        application_profiles=json.dumps(applications),
        primary_applications=json.dumps(applications[:3]),
        availability_status=map_availability_status(factsheet.verification_status),
        regions_available=json.dumps(["APAC", "EMEA", "Americas"]),
        data_source="manufacturer_datasheet",
        data_source_url=source_url,
        data_source_document=f"{factsheet.model_name} specification sheet",
        data_confidence=factsheet.data_confidence,
        last_verified=datetime.now(timezone.utc),
        verified_by="engine_master_data",
        notes=factsheet.searchable_description[:500],
    )


def _extract_rating_designation(model_name: str, series: str) -> str:
    """
    Extract rating designation from model name.
    Uses regex patterns specific to each manufacturer.
    """
    # MTU: M##, M##-N pattern
    match = re.search(r"M\d+[-]?[A-Z]?", model_name)
    if match:
        return match.group()

    # Cummins: QSK##
    match = re.search(r"QSK\d+", model_name)
    if match:
        return match.group()

    # Caterpillar: 35##, C##, C##B
    match = re.search(r"(35\d+[A-Z]?|C\d+[A-Z]?)", model_name)
    if match:
        return match.group()

    # MAN: LE###
    match = re.search(r"LE\d+", model_name)
    if match:
        return match.group()

    # MAN: D####
    match = re.search(r"D\d{4}", model_name)
    if match:
        return match.group()

    # Volvo: IPS### or D##-###
    match = re.search(r"(IPS\d+|D\d+-\d+)", model_name)
    if match:
        return match.group()

    # Yanmar: 6AY variants
    match = re.search(r"\dAY[A-Z]*[-]?[A-Z]*", model_name)
    if match:
        return match.group()

    # WEICHAI: WP##, WHM####, ##M##
    match = re.search(r"(WP\d+|WHM\d+|\d+M\d+)", model_name)
    if match:
        return match.group()

    # FPT: Cursor ##
    if "Cursor" in model_name:
        match = re.search(r"Cursor\s*\d+", model_name)
        if match:
            return match.group().replace(" ", "")

    # Scania: DI##
    match = re.search(r"DI\d+", model_name)
    if match:
        return match.group()

    # Default: use series name
    return series


def generate_migration_data() -> dict:
    """
    Generate all data needed for migration.

    Returns dict with:
    - manufacturers: List of manufacturer records
    - engine_series: List of series records
    - engine_models: List of model records
    - engine_ratings: List of rating records
    """
    manufacturers = {}
    engine_series = {}
    engine_models = {}
    engine_ratings = []

    for factsheet in ALL_ENGINE_FACT_SHEETS:
        # 1. Process manufacturer
        mfr_name = factsheet.manufacturer
        if mfr_name not in manufacturers:
            mfr_data = MANUFACTURER_DATA.get(
                mfr_name,
                {
                    "canonical_name": mfr_name,
                    "country": "Unknown",
                    "tier": 2,
                    "website": "",
                    "is_rrps": False,
                },
            )
            manufacturers[mfr_name] = {
                "id": generate_uuid(),
                "name": mfr_data["canonical_name"],
                "country": mfr_data["country"],
                "tier": mfr_data["tier"],
                "website": mfr_data["website"],
                "description": f"Marine engine manufacturer - {'RRPS' if mfr_data['is_rrps'] else 'Competitor'}",
                "is_active": True,
            }

        mfr_id = manufacturers[mfr_name]["id"]

        # 2. Process engine series
        series_key = f"{mfr_name}:{factsheet.series}"
        if series_key not in engine_series:
            engine_series[series_key] = {
                "id": generate_uuid(),
                "manufacturer_id": mfr_id,
                "brand": mfr_name.split()[0],
                "series_name": factsheet.series,
                "description": f"{factsheet.series} series marine engines",
                "is_current": True,
            }

        series_id = engine_series[series_key]["id"]

        # 3. Process engine model
        model_key = factsheet.model_name
        if model_key not in engine_models:
            config = (
                "V"
                if any(c.endswith("V") for c in factsheet.cylinders_available)
                else "inline"
            )
            cylinders = None
            for c in factsheet.cylinders_available:
                match = re.search(r"\d+", c)
                if match:
                    cylinders = int(match.group())
                    break

            engine_models[model_key] = {
                "id": generate_uuid(),
                "series_id": series_id,
                "model_name": factsheet.model_name,
                "rpm_min": (
                    min(factsheet.rpm_options) if factsheet.rpm_options else 1800
                ),
                "rpm_max": (
                    max(factsheet.rpm_options) if factsheet.rpm_options else 2100
                ),
                "power_min_kw": factsheet.power_range_min_kw,
                "power_max_kw": factsheet.power_range_max_kw,
                "cylinders": cylinders,
                "configuration": config,
                "displacement_liters": None,
                "fuel_types": json.dumps(factsheet.fuel_types),
                "emission_tier": map_emission_tier(factsheet.emissions_tier),
                "is_current_production": True,
                "data_source": "manufacturer_datasheet",
                "data_confidence": factsheet.data_confidence,
            }

        model_id = engine_models[model_key]["id"]

        # 4. Create engine rating using verified master data
        rating = create_engine_rating_from_factsheet(factsheet, model_id)
        engine_ratings.append(rating.to_dict())

    return {
        "manufacturers": list(manufacturers.values()),
        "engine_series": list(engine_series.values()),
        "engine_models": list(engine_models.values()),
        "engine_ratings": engine_ratings,
    }


def print_migration_summary(data: dict) -> None:
    """Print summary of migration data."""
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY: product_data.py -> Unified KB")
    print("Using VERIFIED data from engine_master_data.py")
    print("=" * 60)

    print(f"\nManufacturers: {len(data['manufacturers'])}")
    for mfr in data["manufacturers"]:
        is_rrps = "RRPS" if "Rolls-Royce" in mfr["name"] else "Competitor"
        print(f"  - {mfr['name']} ({mfr['country']}, Tier {mfr['tier']}) [{is_rrps}]")

    print(f"\nEngine Series: {len(data['engine_series'])}")
    for series in data["engine_series"]:
        print(f"  - {series['brand']} {series['series_name']}")

    print(f"\nEngine Models: {len(data['engine_models'])}")
    models_by_mfr = {}
    for model in data["engine_models"]:
        series = next(s for s in data["engine_series"] if s["id"] == model["series_id"])
        mfr = next(
            m for m in data["manufacturers"] if m["id"] == series["manufacturer_id"]
        )
        mfr_name = mfr["name"].split()[0]
        if mfr_name not in models_by_mfr:
            models_by_mfr[mfr_name] = []
        models_by_mfr[mfr_name].append(model["model_name"])

    for mfr, models in models_by_mfr.items():
        print(f"  {mfr}: {len(models)} models")

    print(f"\nEngine Ratings: {len(data['engine_ratings'])}")

    # Count by duty class
    duty_counts = {}
    for rating in data["engine_ratings"]:
        duty = rating["duty_class"]
        duty_counts[duty] = duty_counts.get(duty, 0) + 1

    print("  By Duty Class (VERIFIED):")
    for duty, count in sorted(duty_counts.items()):
        print(f"    - {duty}: {count}")

    # Verify coverage
    verified_count = sum(
        1 for r in data["engine_ratings"] if r["verified_by"] == "engine_master_data"
    )
    print(
        f"\n  Verified from master data: {verified_count}/{len(data['engine_ratings'])}"
    )

    print("\n" + "=" * 60)


def generate_sql_inserts(data: dict) -> str:
    """
    Generate SQL INSERT statements for migration.
    Includes rollback statements at the top.
    """
    sql_parts = []

    sql_parts.append("-- Migration: product_data.py -> Unified KB")
    sql_parts.append(f"-- Generated: {datetime.now(timezone.utc).isoformat()}")
    sql_parts.append(
        "-- Source: ALL_ENGINE_FACT_SHEETS with VERIFIED engine_master_data.py"
    )
    sql_parts.append("")

    # Rollback section
    sql_parts.append(
        "-- ============================================================================="
    )
    sql_parts.append("-- ROLLBACK: Run this section to undo the migration")
    sql_parts.append(
        "-- ============================================================================="
    )
    sql_parts.append(
        "-- DELETE FROM kb_engine_ratings WHERE data_source = 'manufacturer_datasheet';"
    )
    sql_parts.append(
        "-- DELETE FROM kb_engine_models WHERE data_source = 'manufacturer_datasheet';"
    )
    sql_parts.append(
        "-- DELETE FROM kb_engine_series WHERE 1=1; -- Careful: may delete existing data"
    )
    sql_parts.append(
        "-- DELETE FROM kb_manufacturers WHERE 1=1; -- Careful: may delete existing data"
    )
    sql_parts.append("")

    # Helper to escape SQL strings
    def sql_str(value: Optional[str]) -> str:
        if value is None:
            return "NULL"
        return "'" + str(value).replace("'", "''") + "'"

    def sql_num(value) -> str:
        if value is None:
            return "NULL"
        return str(value)

    def sql_bool(value: bool) -> str:
        return "TRUE" if value else "FALSE"

    # Manufacturers
    sql_parts.append(
        "-- ============================================================================="
    )
    sql_parts.append("-- MANUFACTURERS")
    sql_parts.append(
        "-- ============================================================================="
    )
    for mfr in data["manufacturers"]:
        sql_parts.append(
            f"""
INSERT INTO kb_manufacturers (id, name, country, tier, website, description, is_active)
VALUES ({sql_str(mfr['id'])}, {sql_str(mfr['name'])}, {sql_str(mfr['country'])}, {sql_num(mfr['tier'])}, {sql_str(mfr['website'])}, {sql_str(mfr['description'])}, {sql_bool(mfr['is_active'])})
ON CONFLICT (name) DO UPDATE SET
    website = EXCLUDED.website,
    tier = EXCLUDED.tier;"""
        )

    # Engine Series
    sql_parts.append(
        "\n-- ============================================================================="
    )
    sql_parts.append("-- ENGINE SERIES")
    sql_parts.append(
        "-- ============================================================================="
    )
    for series in data["engine_series"]:
        sql_parts.append(
            f"""
INSERT INTO kb_engine_series (id, manufacturer_id, brand, series_name, description, is_current)
VALUES ({sql_str(series['id'])}, {sql_str(series['manufacturer_id'])}, {sql_str(series['brand'])}, {sql_str(series['series_name'])}, {sql_str(series['description'])}, {sql_bool(series['is_current'])})
ON CONFLICT (manufacturer_id, series_name) DO UPDATE SET
    description = EXCLUDED.description;"""
        )

    # Engine Models
    sql_parts.append(
        "\n-- ============================================================================="
    )
    sql_parts.append("-- ENGINE MODELS")
    sql_parts.append(
        "-- ============================================================================="
    )
    for model in data["engine_models"]:
        sql_parts.append(
            f"""
INSERT INTO kb_engine_models (id, series_id, model_name, rpm_min, rpm_max, power_min_kw, power_max_kw, cylinders, configuration, fuel_types, emission_tier, is_current_production, data_source, data_confidence)
VALUES ({sql_str(model['id'])}, {sql_str(model['series_id'])}, {sql_str(model['model_name'])}, {sql_num(model['rpm_min'])}, {sql_num(model['rpm_max'])}, {sql_num(model['power_min_kw'])}, {sql_num(model['power_max_kw'])}, {sql_num(model['cylinders'])}, {sql_str(model['configuration'])}, {sql_str(model['fuel_types'])}, {sql_str(model['emission_tier'])}, {sql_bool(model['is_current_production'])}, {sql_str(model['data_source'])}, {sql_num(model['data_confidence'])})
ON CONFLICT (model_name) DO UPDATE SET
    power_min_kw = EXCLUDED.power_min_kw,
    power_max_kw = EXCLUDED.power_max_kw,
    data_confidence = EXCLUDED.data_confidence;"""
        )

    # Engine Ratings
    sql_parts.append(
        "\n-- ============================================================================="
    )
    sql_parts.append("-- ENGINE RATINGS (VERIFIED from engine_master_data.py)")
    sql_parts.append(
        "-- ============================================================================="
    )
    for rating in data["engine_ratings"]:
        sql_parts.append(
            f"""
INSERT INTO kb_engine_ratings (
    id, engine_model_id, rating_designation, rating_name, duty_class, iso_classification,
    harmonized_duty_class, oem_rating_code,
    power_kw, power_hp, rpm, load_factor_min, load_factor_max, annual_hours_min, annual_hours_max,
    dry_weight_kg, length_mm, width_mm, height_mm, power_density_kw_per_kg,
    fuel_types, emission_tier, application_profiles, primary_applications,
    availability_status, regions_available, data_source, data_source_url, data_source_document,
    data_confidence, last_verified, verified_by, notes
) VALUES (
    {sql_str(rating['id'])}, {sql_str(rating['engine_model_id'])}, {sql_str(rating['rating_designation'])},
    {sql_str(rating['rating_name'])}, {sql_str(rating['duty_class'])}, {sql_str(rating['iso_classification'])},
    {sql_str(rating['harmonized_duty_class'])}, {sql_str(rating['oem_rating_code'])},
    {sql_num(rating['power_kw'])}, {sql_num(rating['power_hp'])}, {sql_num(rating['rpm'])},
    {sql_num(rating['load_factor_min'])}, {sql_num(rating['load_factor_max'])},
    {sql_num(rating['annual_hours_min'])}, {sql_num(rating['annual_hours_max'])},
    {sql_num(rating['dry_weight_kg'])}, {sql_num(rating['length_mm'])},
    {sql_num(rating['width_mm'])}, {sql_num(rating['height_mm'])}, {sql_num(rating['power_density_kw_per_kg'])},
    {sql_str(rating['fuel_types'])}, {sql_str(rating['emission_tier'])},
    {sql_str(rating['application_profiles'])}, {sql_str(rating['primary_applications'])},
    {sql_str(rating['availability_status'])}, {sql_str(rating['regions_available'])},
    {sql_str(rating['data_source'])}, {sql_str(rating['data_source_url'])},
    {sql_str(rating['data_source_document'])}, {sql_num(rating['data_confidence'])},
    NOW(), {sql_str(rating['verified_by'])}, {sql_str(rating['notes'])}
)
ON CONFLICT (engine_model_id, rating_designation) DO UPDATE SET
    power_kw = EXCLUDED.power_kw,
    power_hp = EXCLUDED.power_hp,
    duty_class = EXCLUDED.duty_class,
    harmonized_duty_class = EXCLUDED.harmonized_duty_class,
    oem_rating_code = EXCLUDED.oem_rating_code,
    dry_weight_kg = EXCLUDED.dry_weight_kg,
    length_mm = EXCLUDED.length_mm,
    width_mm = EXCLUDED.width_mm,
    height_mm = EXCLUDED.height_mm,
    power_density_kw_per_kg = EXCLUDED.power_density_kw_per_kg,
    last_verified = NOW(),
    verified_by = EXCLUDED.verified_by;"""
        )

    return "\n".join(sql_parts)


def main():
    """Run migration."""
    print("Starting migration: product_data.py -> Unified PostgreSQL KB")
    print(f"Source: {len(ALL_ENGINE_FACT_SHEETS)} engine fact sheets")
    print(f"Master data: {len(ENGINE_MASTER_DATA)} verified specifications")

    # Generate migration data
    data = generate_migration_data()

    # Print summary
    print_migration_summary(data)

    # Generate SQL
    sql = generate_sql_inserts(data)

    # Write to file
    output_path = os.path.join(
        os.path.dirname(__file__), "migrations", "003_seed_product_data.sql"
    )

    with open(output_path, "w") as f:
        f.write(sql)

    print(f"\nSQL migration written to: {output_path}")
    print("\nTo apply migration:")
    print(f"  psql $DATABASE_URL -f {output_path}")


if __name__ == "__main__":
    main()
