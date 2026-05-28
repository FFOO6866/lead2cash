"""
Customer Requirements Seed Data
Phase 2 Knowledge Base Population

This module populates kb_customer_requirements with sample customer specifications
for product fit matching. Requirements link to SAP customers via customer_id (KUNNR).

Data Sources:
    - SAP CPI Simulator customer data
    - Realistic marine industry scenarios

Usage:
    from lead_to_cash.services.knowledge_base.seed_customer_requirements import (
        seed_customer_requirements,
    )

    # Seed all customer requirements
    req_ids = await seed_customer_requirements()
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# CUSTOMER REQUIREMENTS DATA
# Realistic scenarios based on SAP CPI Simulator customers
# =============================================================================

CUSTOMER_REQUIREMENTS: list[dict[str, Any]] = [
    # =========================================================================
    # Batam Fast Ferry - High-Speed Ferry Operator
    # SAP Customer ID: 0000100001
    # =========================================================================
    {
        "customer_id": "0000100001",
        "customer_name": "Batam Fast Ferry",
        "project_name": "Fast Ferry Fleet Renewal - 2 New Vessels",
        "power_required_kw": 1200.0,
        "power_tolerance_pct": 10.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 2400.0,
        "duty_class_required": "medium_duty",
        "annual_operating_hours": 3500,
        "typical_load_factor": 0.70,
        "peak_load_duration_hours": 2,
        "vessel_type": "fast_ferry",
        "vessel_name": "Batam Express III",
        "vessel_length_m": 45.0,
        "vessel_beam_m": 12.0,
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": True,
        "alternative_fuel_required": False,
        "fuel_type_preference": ["diesel", "hvo"],
        "fuel_type_mandatory": None,
        "max_engine_weight_kg": 4000.0,
        "max_engine_length_mm": 3000.0,
        "max_engine_width_mm": 1500.0,
        "max_engine_height_mm": 1800.0,
        "engine_room_constraints": "Compact engine room, twin shaft line configuration",
        "budget_level": "mid_range",
        "decision_timeline": "6_months",
        "competitor_under_consideration": ["caterpillar", "mtu"],
        "region": "APAC",
        "country": "Singapore",
        "port_of_registry": "Singapore",
        "flag_state": "Singapore",
        "classification_society": "DNV",
        "status": "active",
        "notes": "Replace aging Caterpillar engines with more fuel-efficient solution",
    },
    {
        "customer_id": "0000100001",
        "customer_name": "Batam Fast Ferry",
        "project_name": "Batam Express IV Repower",
        "power_required_kw": 1000.0,
        "power_tolerance_pct": 15.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 2000.0,
        "duty_class_required": "medium_duty",
        "annual_operating_hours": 4000,
        "typical_load_factor": 0.65,
        "vessel_type": "fast_ferry",
        "vessel_name": "Batam Express IV",
        "vessel_length_m": 38.0,
        "application": "propulsion",
        "new_build_or_repower": "repower",
        "emission_tier_required": "IMO Tier II",
        "eca_operation": False,
        "budget_level": "value",
        "decision_timeline": "3_months",
        "competitor_under_consideration": ["cummins"],
        "region": "APAC",
        "country": "Singapore",
        "classification_society": "Lloyd's Register",
        "status": "active",
        "notes": "Urgent repower due to main engine failure",
    },
    # =========================================================================
    # Seatrium (ST Engineering Marine) - Offshore Platform FPSO
    # SAP Customer ID: 0022005992
    # =========================================================================
    {
        "customer_id": "0022005992",
        "customer_name": "ST Engineering Marine",
        "project_name": "FPSO Prosperity Power Generation",
        "power_required_kw": 8000.0,
        "power_tolerance_pct": 5.0,
        "power_configuration": "quad",
        "total_installed_power_kw": 32000.0,
        "duty_class_required": "continuous",
        "annual_operating_hours": 8000,
        "typical_load_factor": 0.85,
        "vessel_type": "fpso",
        "vessel_name": "FPSO Prosperity",
        "application": "genset",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": False,
        "alternative_fuel_required": True,
        "fuel_type_preference": ["lng", "dual_fuel"],
        "fuel_type_mandatory": ["dual_fuel"],
        "max_engine_weight_kg": 15000.0,
        "budget_level": "premium",
        "decision_timeline": "12_months",
        "competitor_under_consideration": ["wartsila", "man"],
        "region": "APAC",
        "country": "Singapore",
        "classification_society": "ABS",
        "status": "active",
        "notes": "Critical power generation for offshore platform - requires high reliability",
    },
    # =========================================================================
    # Maersk A/S - Container Feeder Vessel
    # SAP Customer ID: 0000100002
    # =========================================================================
    {
        "customer_id": "0000100002",
        "customer_name": "Maersk A/S",
        "project_name": "Feeder Vessel Retrofit - ECO Efficiency",
        "power_required_kw": 6000.0,
        "power_tolerance_pct": 10.0,
        "power_configuration": "single",
        "total_installed_power_kw": 6000.0,
        "duty_class_required": "heavy_duty",
        "annual_operating_hours": 6000,
        "typical_load_factor": 0.75,
        "vessel_type": "container",
        "vessel_name": "Maersk Defender",
        "vessel_length_m": 180.0,
        "application": "propulsion",
        "new_build_or_repower": "retrofit",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": True,
        "alternative_fuel_required": True,
        "fuel_type_preference": ["methanol", "diesel"],
        "budget_level": "premium",
        "decision_timeline": "12_months",
        "competitor_under_consideration": ["man", "wartsila"],
        "region": "EMEA",
        "country": "Denmark",
        "classification_society": "DNV",
        "status": "active",
        "notes": "Part of Maersk decarbonization program - methanol-ready preferred",
    },
    # =========================================================================
    # Neptune Energy - Offshore Support Vessel
    # SAP Customer ID: 0000100003
    # =========================================================================
    {
        "customer_id": "0000100003",
        "customer_name": "Neptune Energy",
        "project_name": "OSV Fleet Expansion - 2 New PSVs",
        "power_required_kw": 3000.0,
        "power_tolerance_pct": 10.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 6000.0,
        "duty_class_required": "heavy_duty",
        "annual_operating_hours": 4500,
        "typical_load_factor": 0.60,
        "peak_load_duration_hours": 4,
        "vessel_type": "osv",
        "vessel_name": "Neptune Pioneer",
        "vessel_length_m": 85.0,
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": True,
        "alternative_fuel_required": True,
        "fuel_type_preference": ["lng", "diesel"],
        "max_engine_weight_kg": 10000.0,
        "budget_level": "premium",
        "decision_timeline": "6_months",
        "competitor_under_consideration": ["caterpillar", "rolls_royce"],
        "region": "EMEA",
        "country": "Netherlands",
        "classification_society": "DNV",
        "status": "active",
        "notes": "DP2 capable, requires high redundancy for offshore operations",
    },
    # =========================================================================
    # Pacific Maritime - Small Workboat
    # SAP Customer ID: 0000100005
    # =========================================================================
    {
        "customer_id": "0000100005",
        "customer_name": "Pacific Maritime",
        "project_name": "Harbor Tug Newbuild",
        "power_required_kw": 2000.0,
        "power_tolerance_pct": 15.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 4000.0,
        "duty_class_required": "heavy_duty",
        "annual_operating_hours": 3000,
        "typical_load_factor": 0.50,
        "peak_load_duration_hours": 1,
        "vessel_type": "tug",
        "vessel_name": None,
        "vessel_length_m": 32.0,
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier II",
        "eca_operation": False,
        "budget_level": "value",
        "decision_timeline": "3_months",
        "competitor_under_consideration": ["cummins", "caterpillar"],
        "region": "APAC",
        "country": "Australia",
        "classification_society": "Lloyd's Register",
        "status": "active",
        "notes": "Budget-conscious operator, reliability is key",
    },
    # =========================================================================
    # Additional scenarios for comprehensive testing
    # =========================================================================
    {
        "customer_id": None,  # Unknown customer
        "customer_name": "Penguin Shipyard Customer",
        "project_name": "Fast Crew Boat - CTV for Wind Farm",
        "power_required_kw": 800.0,
        "power_tolerance_pct": 10.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 1600.0,
        "duty_class_required": "medium_duty",
        "annual_operating_hours": 2500,
        "typical_load_factor": 0.55,
        "vessel_type": "crew_boat",
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": True,
        "budget_level": "mid_range",
        "decision_timeline": "6_months",
        "competitor_under_consideration": ["mtu", "volvo_penta"],
        "region": "APAC",
        "country": "Singapore",
        "classification_society": "BV",
        "status": "active",
        "notes": "Crew transfer vessel for offshore wind farm service",
    },
    {
        "customer_id": None,
        "customer_name": "Indonesian Navy (Potential)",
        "project_name": "Patrol Vessel Modernization",
        "power_required_kw": 2500.0,
        "power_tolerance_pct": 5.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 5000.0,
        "duty_class_required": "light_duty",
        "annual_operating_hours": 1500,
        "typical_load_factor": 0.40,
        "peak_load_duration_hours": 2,
        "vessel_type": "patrol",
        "application": "propulsion",
        "new_build_or_repower": "repower",
        "emission_tier_required": "IMO Tier II",
        "eca_operation": False,
        "max_engine_weight_kg": 5000.0,
        "budget_level": "premium",
        "decision_timeline": "12_months",
        "competitor_under_consideration": ["mtu", "man"],
        "region": "APAC",
        "country": "Indonesia",
        "classification_society": "BKI",
        "status": "active",
        "notes": "High-speed requirement, military-grade reliability",
    },
    {
        "customer_id": None,
        "customer_name": "Bangkok Port Authority",
        "project_name": "Harbor Pilot Boat Fleet",
        "power_required_kw": 600.0,
        "power_tolerance_pct": 15.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 1200.0,
        "duty_class_required": "medium_duty",
        "annual_operating_hours": 2000,
        "typical_load_factor": 0.50,
        "vessel_type": "pilot",
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier II",
        "budget_level": "value",
        "decision_timeline": "3_months",
        "competitor_under_consideration": ["yanmar", "volvo_penta"],
        "region": "APAC",
        "country": "Thailand",
        "classification_society": "ClassNK",
        "status": "active",
        "notes": "Government tender, price competitive",
    },
    {
        "customer_id": None,
        "customer_name": "Luxury Yacht Builders Pte Ltd",
        "project_name": "65m Superyacht Project",
        "power_required_kw": 3500.0,
        "power_tolerance_pct": 5.0,
        "power_configuration": "twin",
        "total_installed_power_kw": 7000.0,
        "duty_class_required": "pleasure",
        "annual_operating_hours": 500,
        "typical_load_factor": 0.25,
        "peak_load_duration_hours": 1,
        "vessel_type": "yacht",
        "vessel_length_m": 65.0,
        "application": "propulsion",
        "new_build_or_repower": "new_build",
        "emission_tier_required": "IMO Tier III",
        "eca_operation": True,
        "max_engine_weight_kg": 8000.0,
        "max_engine_height_mm": 1600.0,
        "engine_room_constraints": "Height restricted engine room, noise requirements",
        "budget_level": "premium",
        "decision_timeline": "12_months",
        "competitor_under_consideration": ["mtu", "caterpillar"],
        "region": "APAC",
        "country": "Singapore",
        "classification_society": "RINA",
        "status": "active",
        "notes": "Premium yacht - noise and vibration critical, NVH package required",
    },
]


async def seed_customer_requirements(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> dict[str, str]:
    """
    Seed customer requirements into database.

    Returns:
        Dictionary mapping project_name -> requirement_id
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.info("Starting customer requirements seed...")

    req_ids: dict[str, str] = {}
    inserted_count = 0

    now = datetime.now(timezone.utc)

    for req_data in CUSTOMER_REQUIREMENTS:
        req_id = str(uuid.uuid4())
        project_name = req_data.get("project_name", "Unknown Project")

        try:
            async with db._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kb_customer_requirements (
                        id, customer_id, customer_name, project_name,
                        power_required_kw, power_tolerance_pct,
                        power_configuration, total_installed_power_kw,
                        duty_class_required, annual_operating_hours,
                        typical_load_factor, peak_load_duration_hours,
                        vessel_type, vessel_name, vessel_length_m, vessel_beam_m,
                        application, new_build_or_repower,
                        emission_tier_required, eca_operation,
                        alternative_fuel_required,
                        fuel_type_preference, fuel_type_mandatory,
                        max_engine_weight_kg, max_engine_length_mm,
                        max_engine_width_mm, max_engine_height_mm,
                        engine_room_constraints,
                        budget_level, decision_timeline,
                        competitor_under_consideration,
                        region, country, port_of_registry, flag_state,
                        classification_society,
                        status, notes,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14, $15, $16,
                        $17, $18,
                        $19, $20, $21,
                        $22, $23,
                        $24, $25, $26, $27,
                        $28,
                        $29, $30, $31,
                        $32, $33, $34, $35,
                        $36,
                        $37, $38,
                        $39, $40
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    req_id,
                    req_data.get("customer_id"),
                    req_data.get("customer_name"),
                    project_name,
                    req_data.get("power_required_kw"),
                    req_data.get("power_tolerance_pct", 10.0),
                    req_data.get("power_configuration"),
                    req_data.get("total_installed_power_kw"),
                    req_data.get("duty_class_required"),
                    req_data.get("annual_operating_hours"),
                    req_data.get("typical_load_factor"),
                    req_data.get("peak_load_duration_hours"),
                    req_data.get("vessel_type"),
                    req_data.get("vessel_name"),
                    req_data.get("vessel_length_m"),
                    req_data.get("vessel_beam_m"),
                    req_data.get("application"),
                    req_data.get("new_build_or_repower"),
                    req_data.get("emission_tier_required"),
                    req_data.get("eca_operation", False),
                    req_data.get("alternative_fuel_required", False),
                    req_data.get("fuel_type_preference"),  # JSONB
                    req_data.get("fuel_type_mandatory"),  # JSONB
                    req_data.get("max_engine_weight_kg"),
                    req_data.get("max_engine_length_mm"),
                    req_data.get("max_engine_width_mm"),
                    req_data.get("max_engine_height_mm"),
                    req_data.get("engine_room_constraints"),
                    req_data.get("budget_level"),
                    req_data.get("decision_timeline"),
                    req_data.get("competitor_under_consideration"),  # JSONB
                    req_data.get("region"),
                    req_data.get("country"),
                    req_data.get("port_of_registry"),
                    req_data.get("flag_state"),
                    req_data.get("classification_society"),
                    req_data.get("status", "active"),
                    req_data.get("notes"),
                    now,
                    now,
                )

            req_ids[project_name] = req_id
            inserted_count += 1
            logger.debug(f"Inserted requirement: {project_name}")

        except Exception as e:
            logger.error(f"Failed to insert requirement {project_name}: {e}")

    logger.info(f"Customer requirements seed complete: {inserted_count} inserted")
    return req_ids


async def clear_customer_requirements(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> int:
    """
    Clear all customer requirements from database.

    WARNING: This is destructive and cannot be undone.

    Returns:
        Number of records deleted
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    async with db._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM kb_customer_requirements")
        await conn.execute("DELETE FROM kb_customer_requirements")

    logger.info(f"Cleared {count} customer requirements")
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

        print("Seeding customer requirements...")
        req_ids = await seed_customer_requirements(db)
        print(f"Seeded {len(req_ids)} customer requirements")

        # Print summary
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT duty_class_required, COUNT(*) as count
                FROM kb_customer_requirements
                GROUP BY duty_class_required
                ORDER BY count DESC
                """
            )
            print("\nRequirements by duty class:")
            for row in rows:
                print(f"  {row['duty_class_required']}: {row['count']}")

    asyncio.run(main())
