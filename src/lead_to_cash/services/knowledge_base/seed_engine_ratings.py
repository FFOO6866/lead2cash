"""
Engine Ratings Seed Data - ISO 8528-1:2018 Aligned
Phase 2 Knowledge Base Population

This module populates kb_engine_ratings with individual duty ratings per engine model.
Engine ratings are the ATOMIC UNIT for product comparison (not engine models).

Example:
    MTU Series 2000 has multiple ratings:
    - MTU 12V 2000 M72 (Heavy Duty, 1080 kW @ 2250 RPM)
    - MTU 12V 2000 M93 (Light Duty, 1340 kW @ 2450 RPM)

Data Sources:
    - ISO 8528-1:2018 Third Edition (License: Integrum Pte Ltd / SS Foo - Order OP-1014241)
    - MTU Solution Guide Edition 2/22
    - OEM datasheets (public sources only)

Usage:
    from lead_to_cash.services.knowledge_base.seed_engine_ratings import (
        seed_engine_ratings,
    )

    # Seed all engine ratings
    rating_ids = await seed_engine_ratings()
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.engine_master_data import (
    ENGINE_MASTER_DATA,
    EngineSpecification,
)
from lead_to_cash.services.knowledge_base.unified_models import (
    DutyClass,
)
from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENGINE RATING DATA (Power, RPM, and Physical Specs)
# Data from manufacturer datasheets and industry sources
# =============================================================================

# Map duty class to ISO 8528 operating characteristics
DUTY_CLASS_OPERATING_PROFILE = {
    DutyClass.CONTINUOUS: {
        "load_factor_min": 0.70,
        "load_factor_max": 1.00,
        "annual_hours_min": 5000,
        "annual_hours_max": 8760,
        "full_power_hours_per_cycle": None,  # Unlimited
        "cycle_hours": None,
    },
    DutyClass.HEAVY_DUTY: {
        "load_factor_min": 0.40,
        "load_factor_max": 0.80,
        "annual_hours_min": 3000,
        "annual_hours_max": 5000,
        "full_power_hours_per_cycle": 8,
        "cycle_hours": 10,
    },
    DutyClass.MEDIUM_DUTY: {
        "load_factor_min": 0.20,
        "load_factor_max": 0.80,
        "annual_hours_min": 2000,
        "annual_hours_max": 4000,
        "full_power_hours_per_cycle": 6,
        "cycle_hours": 12,
    },
    DutyClass.LIGHT_DUTY: {
        "load_factor_min": 0.00,
        "load_factor_max": 0.50,
        "annual_hours_min": 1000,
        "annual_hours_max": 3000,
        "full_power_hours_per_cycle": 2,
        "cycle_hours": 8,
    },
    DutyClass.PLEASURE: {
        "load_factor_min": 0.00,
        "load_factor_max": 0.30,
        "annual_hours_min": 250,
        "annual_hours_max": 1000,
        "full_power_hours_per_cycle": 1,
        "cycle_hours": 8,
    },
    DutyClass.INTERMITTENT: {
        "load_factor_min": 0.20,
        "load_factor_max": 0.40,
        "annual_hours_min": 250,
        "annual_hours_max": 1000,
        "full_power_hours_per_cycle": 2,
        "cycle_hours": 8,
    },
}

# Power and RPM data for engines (from datasheets and aggregators)
# Format: (power_kw, rpm, emission_tier, fuel_types)
ENGINE_POWER_DATA: dict[str, tuple[float, int, str, list[str]]] = {
    # MTU Series 2000
    "MTU 8V 2000 M72": (720, 2250, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 10V 2000 M72": (900, 2250, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 12V 2000 M93": (1340, 2450, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 16V 2000 M93": (1790, 2450, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 16V 2000 M96": (1939, 2450, "IMO Tier II", ["diesel", "hvo"]),
    # MTU Series 4000
    "MTU 12V 4000 M63": (1800, 1800, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 16V 4000 M63": (2400, 1800, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 12V 4000 M73": (2040, 2050, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 16V 4000 M73": (2720, 2050, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 12V 4000 M93": (2340, 2100, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 16V 4000 M93": (3120, 2100, "IMO Tier II", ["diesel", "hvo"]),
    "MTU 20V 4000 M93": (3900, 2100, "IMO Tier II", ["diesel", "hvo"]),
    # MTU Series 4000 Gas
    "MTU 12V 4000 M05-N": (1492, 1800, "IMO Tier III", ["lng", "diesel"]),
    "MTU 16V 4000 M05-N": (1990, 1800, "IMO Tier III", ["lng", "diesel"]),
    "MTU 20V 4000 M05-N": (2486, 1800, "IMO Tier III", ["lng", "diesel"]),
    # MTU Series 8000
    "MTU 16V 8000 M71": (7200, 1150, "IMO Tier II", ["diesel", "mdo"]),
    "MTU 20V 8000 M91": (10000, 1150, "IMO Tier II", ["diesel", "mdo"]),
    # Cummins QSK Series
    "Cummins QST30": (895, 2100, "IMO Tier II", ["diesel"]),
    "Cummins X15 Marine": (503, 1800, "IMO Tier III", ["diesel"]),
    "Cummins QSK38": (1119, 1800, "IMO Tier II", ["diesel"]),
    "Cummins QSK38-M": (1007, 1800, "IMO Tier II", ["diesel"]),
    "Cummins QSK50": (1491, 1800, "IMO Tier II", ["diesel"]),
    "Cummins QSK60": (1864, 1800, "IMO Tier II", ["diesel"]),
    "Cummins QSK78": (2237, 1800, "IMO Tier II", ["diesel"]),
    "Cummins QSK95": (2983, 1800, "IMO Tier II", ["diesel"]),
    # Caterpillar 3500 Series
    "Cat 3508C": (1100, 1600, "IMO Tier II", ["diesel"]),
    "Cat 3512": (1380, 1800, "IMO Tier II", ["diesel"]),
    "Cat 3512B": (1491, 1800, "IMO Tier II", ["diesel"]),
    "Cat 3516": (2000, 1600, "IMO Tier II", ["diesel"]),
    "Cat 3516B": (2240, 1800, "IMO Tier II", ["diesel"]),
    "Cat 3516C": (2525, 1800, "IMO Tier II", ["diesel"]),
    # Caterpillar C-Series
    "Cat C12.9": (490, 2300, "IMO Tier III", ["diesel"]),
    "Cat C18": (597, 2100, "IMO Tier III", ["diesel"]),
    "Cat C18 ACERT": (600, 2100, "IMO Tier III", ["diesel"]),
    "Cat C32": (1081, 2100, "IMO Tier III", ["diesel"]),
    "Cat C32B": (1193, 2300, "IMO Tier II", ["diesel"]),
    # MAN Engines
    "MAN D2676 LE": (588, 2100, "IMO Tier II", ["diesel"]),
    "MAN D2862 LE463": (1029, 2100, "IMO Tier II", ["diesel"]),
    "MAN D2862 LE443": (882, 1800, "IMO Tier II", ["diesel"]),
    "MAN D2868 LE433": (809, 2100, "IMO Tier II", ["diesel"]),
    "MAN D2868 LE423": (735, 1800, "IMO Tier II", ["diesel"]),
    "MAN V12-2000": (1213, 2100, "IMO Tier II", ["diesel"]),
    "MAN V12-2000CR": (1324, 2100, "IMO Tier II", ["diesel"]),
    # Volvo Penta
    "Volvo Penta D11": (400, 2200, "IMO Tier III", ["diesel"]),
    "Volvo Penta D13-IPS1350": (736, 2300, "IMO Tier II", ["diesel"]),
    "Volvo Penta D13-IPS1200": (662, 2300, "IMO Tier II", ["diesel"]),
    "Volvo Penta D13-800": (588, 2200, "IMO Tier II", ["diesel"]),
    "Volvo Penta D13 MH": (478, 1800, "IMO Tier II", ["diesel"]),
    # Yanmar
    "Yanmar 6AYM-ETE": (670, 1900, "IMO Tier II", ["diesel"]),
    "Yanmar 6AYEM-GT": (749, 1950, "IMO Tier II", ["diesel"]),
    "Yanmar 8AYM-WET": (890, 1900, "IMO Tier II", ["diesel"]),
    "Yanmar 12AYM-WGT": (1340, 1900, "IMO Tier II", ["diesel"]),
    # Weichai
    "WEICHAI WP13": (441, 2100, "IMO Tier II", ["diesel"]),
    "WEICHAI WHM6160": (1324, 1500, "IMO Tier II", ["diesel"]),
    "WEICHAI 12M33": (2576, 1000, "IMO Tier II", ["diesel"]),
    # FPT Industrial
    "FPT Cursor 13": (500, 2100, "IMO Tier III", ["diesel"]),
    "FPT Cursor 16": (600, 1800, "IMO Tier II", ["diesel"]),
    # Scania
    "Scania DI13": (478, 2100, "IMO Tier III", ["diesel"]),
    "Scania DI16": (588, 2100, "IMO Tier III", ["diesel"]),
    # Wartsila High-Speed (14 series)
    "Wartsila 6L14": (570, 1500, "IMO Tier II", ["diesel"]),
    "Wartsila 8L14": (760, 1500, "IMO Tier II", ["diesel"]),
    "Wartsila 12V14": (1140, 1200, "IMO Tier II", ["diesel"]),
    # Wartsila High-Speed (20 series)
    "Wartsila 6L20": (1200, 1000, "IMO Tier II", ["diesel"]),
    "Wartsila 8L20": (1600, 1000, "IMO Tier II", ["diesel"]),
    "Wartsila 9L20": (1800, 1000, "IMO Tier II", ["diesel"]),
}


def _get_manufacturer_from_model_name(model_name: str) -> str:
    """Extract manufacturer name from model name for matching to kb_engine_models."""
    if model_name.startswith("MTU"):
        return "Rolls-Royce Power Systems"
    elif model_name.startswith("Cat ") or model_name.startswith("Cat C"):
        return "Caterpillar MaK"
    elif model_name.startswith("Cummins"):
        return "Cummins Marine"
    elif model_name.startswith("MAN"):
        return "MAN Energy Solutions"
    elif model_name.startswith("Volvo"):
        return "Volvo Penta"
    elif model_name.startswith("Yanmar"):
        return "Yanmar"
    elif model_name.startswith("WEICHAI"):
        return "Weichai Power"
    elif model_name.startswith("FPT"):
        # FPT is not in seed_data manufacturers, skip
        return None
    elif model_name.startswith("Scania"):
        # Scania is not in seed_data manufacturers, skip
        return None
    elif model_name.startswith("Wartsila"):
        return "Wärtsilä"
    else:
        return None


def _get_series_from_model_name(model_name: str) -> Optional[str]:
    """Extract series name from model name for matching to kb_engine_series."""
    # MTU Series mapping
    if "2000" in model_name:
        return "2000"
    elif "4000" in model_name:
        return "4000"
    elif "8000" in model_name:
        return "8000"
    # Cummins
    elif "QSK" in model_name or "QST" in model_name or "X15" in model_name:
        return "QSK"
    # Caterpillar
    elif "3508" in model_name or "3512" in model_name or "3516" in model_name:
        return "3500"
    elif "C12" in model_name or "C18" in model_name or "C32" in model_name:
        return "C-Series"
    # MAN
    elif "D26" in model_name or "D28" in model_name or "V12-2000" in model_name:
        return "D26/28"
    # Volvo Penta
    elif "D11" in model_name or "D13" in model_name:
        return "D13"
    # Yanmar
    elif "AYM" in model_name:
        return "AYM"
    # Weichai
    elif "WP13" in model_name or "WHM" in model_name or "M33" in model_name:
        return "WHM"
    # Wartsila
    elif "L14" in model_name or "V14" in model_name:
        return "14"
    elif "L20" in model_name:
        return "20"
    return None


def _build_rating_record(
    spec: EngineSpecification,
    engine_model_id: str,
) -> dict[str, Any]:
    """Build a rating record from engine specification."""
    model_name = spec.model_name

    # Get power and RPM data
    power_data = ENGINE_POWER_DATA.get(model_name)
    if power_data:
        power_kw, rpm, emission_tier, fuel_types = power_data
    else:
        # Default values if not in power data
        power_kw = 1000.0
        rpm = 1800
        emission_tier = "IMO Tier II"
        fuel_types = ["diesel"]

    # Get operating profile from duty class
    profile = DUTY_CLASS_OPERATING_PROFILE.get(spec.duty_class, {})

    # Get harmonized duty class
    harmonized = spec.get_harmonized_duty_class()

    # Build data source string
    data_source = spec.data_source if spec.data_source else "engine_master_data"
    if not spec.verified:
        data_source = f"unverified:{data_source}"

    now = datetime.now(timezone.utc)

    return {
        "id": str(uuid.uuid4()),
        "engine_model_id": engine_model_id,
        "rating_designation": spec.rating_designation,
        "rating_name": model_name,
        # ISO/Industry Classification
        "duty_class": spec.duty_class.value,
        "iso_classification": "not_applicable",  # Propulsion engines
        # Performance
        "power_kw": power_kw,
        "power_hp": round(power_kw * 1.341, 2),  # kW to HP
        "rpm": rpm,
        # Operating profile (from ISO 8528)
        "load_factor_min": profile.get("load_factor_min", 0.0),
        "load_factor_max": profile.get("load_factor_max", 1.0),
        "full_power_hours_per_cycle": profile.get("full_power_hours_per_cycle"),
        "cycle_hours": profile.get("cycle_hours"),
        "annual_hours_min": profile.get("annual_hours_min"),
        "annual_hours_max": profile.get("annual_hours_max"),
        # Physical (from spec if available)
        "dry_weight_kg": spec.dry_weight_kg,
        "length_mm": spec.length_mm,
        "width_mm": spec.width_mm,
        "height_mm": spec.height_mm,
        "power_density_kw_per_kg": (
            round(power_kw / spec.dry_weight_kg, 4) if spec.dry_weight_kg else None
        ),
        # Fuel and emissions
        "fuel_types": fuel_types,
        "emission_tier": emission_tier,
        "aftertreatment_required": ("SCR" if "III" in emission_tier else "None"),
        # Applications
        "application_profiles": spec.primary_applications,
        "primary_applications": (
            spec.primary_applications[:3] if spec.primary_applications else []
        ),
        # Availability
        "availability_status": "available",
        "regions_available": ["APAC", "EMEA", "Americas"],
        # Data provenance (CRITICAL)
        "data_source": data_source,
        "data_source_url": None,  # Requires legitimate sourcing
        "data_confidence": 0.90 if spec.verified else 0.70,
        "last_verified": now if spec.verified else None,
        "verified_by": "engine_master_data" if spec.verified else None,
        # Harmonized duty class (ISO 8528-1:2018 aligned)
        "harmonized_duty_class": harmonized.value,
        "oem_rating_code": spec.rating_designation,
        # Metadata
        "notes": spec.notes,
        "created_at": now,
        "updated_at": now,
    }


async def seed_engine_ratings(
    db: Optional[KnowledgeBaseDatabase] = None,
    model_ids: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Seed engine ratings into database.

    This function creates rating records from ENGINE_MASTER_DATA, linking
    each rating to its parent engine model in kb_engine_models.

    Args:
        db: Database connection (optional, will create if not provided)
        model_ids: Optional mapping of model_name -> model_id
                   If not provided, will query kb_engine_models

    Returns:
        Dictionary mapping rating_designation -> rating_id
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.info("Starting engine ratings seed...")

    # Get model IDs if not provided
    if model_ids is None:
        model_ids = await _get_model_ids(db)

    rating_ids: dict[str, str] = {}
    inserted_count = 0
    skipped_count = 0

    for model_name, spec in ENGINE_MASTER_DATA.items():
        # Find the engine model ID
        # First try exact match
        engine_model_id = model_ids.get(model_name)

        # If not found, try to match by series
        if not engine_model_id:
            series = _get_series_from_model_name(model_name)
            manufacturer = _get_manufacturer_from_model_name(model_name)
            if series and manufacturer:
                # Look for model with matching series in the model_ids
                for mid_name, mid_id in model_ids.items():
                    if series.lower() in mid_name.lower():
                        engine_model_id = mid_id
                        logger.debug(f"Matched {model_name} to model {mid_name}")
                        break

        if not engine_model_id:
            # Model not found in KB - this is expected for some engines
            # that aren't in the Phase 1 seed data
            logger.debug(f"Skipping {model_name}: no matching engine model in KB")
            skipped_count += 1
            continue

        # Build and insert rating record
        rating_record = _build_rating_record(spec, engine_model_id)

        try:
            # Use upsert pattern to handle duplicate rating designations
            async with db._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kb_engine_ratings (
                        id, engine_model_id, rating_designation, rating_name,
                        duty_class, iso_classification,
                        power_kw, power_hp, rpm,
                        load_factor_min, load_factor_max,
                        full_power_hours_per_cycle, cycle_hours,
                        annual_hours_min, annual_hours_max,
                        dry_weight_kg, length_mm, width_mm, height_mm,
                        power_density_kw_per_kg,
                        fuel_types, emission_tier, aftertreatment_required,
                        application_profiles, primary_applications,
                        availability_status, regions_available,
                        data_source, data_source_url, data_confidence,
                        last_verified, verified_by,
                        harmonized_duty_class, oem_rating_code,
                        notes, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6,
                        $7, $8, $9,
                        $10, $11,
                        $12, $13,
                        $14, $15,
                        $16, $17, $18, $19,
                        $20,
                        $21, $22, $23,
                        $24, $25,
                        $26, $27,
                        $28, $29, $30,
                        $31, $32,
                        $33, $34,
                        $35, $36, $37
                    )
                    ON CONFLICT (engine_model_id, rating_designation)
                    DO UPDATE SET
                        power_kw = EXCLUDED.power_kw,
                        power_hp = EXCLUDED.power_hp,
                        rpm = EXCLUDED.rpm,
                        duty_class = EXCLUDED.duty_class,
                        harmonized_duty_class = EXCLUDED.harmonized_duty_class,
                        updated_at = EXCLUDED.updated_at
                    """,
                    rating_record["id"],
                    rating_record["engine_model_id"],
                    rating_record["rating_designation"],
                    rating_record["rating_name"],
                    rating_record["duty_class"],
                    rating_record["iso_classification"],
                    rating_record["power_kw"],
                    rating_record["power_hp"],
                    rating_record["rpm"],
                    rating_record["load_factor_min"],
                    rating_record["load_factor_max"],
                    rating_record["full_power_hours_per_cycle"],
                    rating_record["cycle_hours"],
                    rating_record["annual_hours_min"],
                    rating_record["annual_hours_max"],
                    rating_record["dry_weight_kg"],
                    rating_record["length_mm"],
                    rating_record["width_mm"],
                    rating_record["height_mm"],
                    rating_record["power_density_kw_per_kg"],
                    rating_record["fuel_types"],  # JSONB
                    rating_record["emission_tier"],
                    rating_record["aftertreatment_required"],
                    rating_record["application_profiles"],  # JSONB
                    rating_record["primary_applications"],  # JSONB
                    rating_record["availability_status"],
                    rating_record["regions_available"],  # JSONB
                    rating_record["data_source"],
                    rating_record["data_source_url"],
                    rating_record["data_confidence"],
                    rating_record["last_verified"],
                    rating_record["verified_by"],
                    rating_record["harmonized_duty_class"],
                    rating_record["oem_rating_code"],
                    rating_record["notes"],
                    rating_record["created_at"],
                    rating_record["updated_at"],
                )

            rating_ids[spec.rating_designation] = rating_record["id"]
            inserted_count += 1
            logger.debug(f"Inserted rating: {model_name} ({spec.rating_designation})")

        except Exception as e:
            logger.error(f"Failed to insert rating {model_name}: {e}")
            skipped_count += 1

    logger.info(
        f"Engine ratings seed complete: {inserted_count} inserted, "
        f"{skipped_count} skipped"
    )
    return rating_ids


async def _get_model_ids(db: KnowledgeBaseDatabase) -> dict[str, str]:
    """Get mapping of model_name -> model_id from kb_engine_models."""
    model_ids = {}

    async with db._pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, model_name FROM kb_engine_models")
        for row in rows:
            model_ids[row["model_name"]] = row["id"]

    logger.debug(f"Loaded {len(model_ids)} engine models from KB")
    return model_ids


async def clear_engine_ratings(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> int:
    """
    Clear all engine ratings from database.

    WARNING: This is destructive and cannot be undone.

    Returns:
        Number of records deleted
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    async with db._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM kb_engine_ratings")
        await conn.execute("DELETE FROM kb_engine_ratings")

    logger.info(f"Cleared {count} engine ratings")
    return count


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        """Run seed from command line."""
        db = get_knowledge_base_db()
        await db.initialize()

        print("Seeding engine ratings...")
        rating_ids = await seed_engine_ratings(db)
        print(f"Seeded {len(rating_ids)} engine ratings")

        # Print summary by duty class
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT duty_class, COUNT(*) as count
                FROM kb_engine_ratings
                GROUP BY duty_class
                ORDER BY duty_class
                """
            )
            print("\nRatings by duty class:")
            for row in rows:
                print(f"  {row['duty_class']}: {row['count']}")

    asyncio.run(main())
