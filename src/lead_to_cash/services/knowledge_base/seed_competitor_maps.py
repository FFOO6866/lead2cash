"""
Rating Competitor Map Seed Data
Phase 2 Knowledge Base Population

This module populates kb_rating_competitor_map with apple-to-apple competitive
mappings between MTU (our) ratings and competitor ratings at similar power levels.

Purpose:
    - Enable true rating-level competitive comparison
    - Pre-compute competitive position for each rating pair
    - Feed threat assessment in competitor intelligence

Usage:
    from lead_to_cash.services.knowledge_base.seed_competitor_maps import (
        seed_competitor_maps,
    )

    # Seed all competitor mappings
    map_ids = await seed_competitor_maps()
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# COMPETITIVE MAPPING DATA
# MTU vs Key Competitors at similar power/duty levels
# =============================================================================

# Competitive mappings define rating-to-rating comparisons
# Format: (our_rating_name, competitor_rating_name, analysis_data)
COMPETITIVE_MAPPINGS: list[dict[str, Any]] = [
    # =========================================================================
    # MTU Series 2000 vs Competitors (1000-2000 kW range)
    # =========================================================================
    {
        "our_rating_name": "MTU 12V 2000 M93",
        "competitor_rating_name": "Cat C32",
        "power_delta_kw": -259,  # MTU 1340 vs Cat 1081 = -259 (MTU higher)
        "power_delta_pct": -24.0,
        "competitive_position": "advantage",
        "price_positioning": "premium",
        "overlapping_applications": ["fast_ferry", "yacht", "patrol"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["light_duty", "medium_duty"],
        "threat_level": "medium",
        "our_advantages": [
            "Higher power output",
            "Better power density",
            "MTU global service network",
            "Proven in high-speed applications",
        ],
        "their_advantages": [
            "Lower acquisition cost",
            "Wider dealer network in Americas",
            "Simpler maintenance",
        ],
        "recommended_positioning": "Position on total cost of ownership and performance advantage",
    },
    {
        "our_rating_name": "MTU 16V 2000 M93",
        "competitor_rating_name": "Cummins QSK50",
        "power_delta_kw": 299,  # MTU 1790 vs Cummins 1491 = 299
        "power_delta_pct": 20.0,
        "competitive_position": "advantage",
        "price_positioning": "premium",
        "overlapping_applications": ["fast_ferry", "osv", "workboat"],
        "overlapping_regions": ["APAC", "Americas"],
        "overlapping_duty_classes": ["light_duty", "medium_duty"],
        "threat_level": "medium",
        "our_advantages": [
            "Higher power output",
            "More compact package",
            "Better fuel efficiency at part load",
        ],
        "their_advantages": [
            "Lower price point",
            "Extensive Americas service network",
            "Robust heavy-duty design",
        ],
        "recommended_positioning": "Emphasize compact design and performance for fast vessels",
    },
    {
        "our_rating_name": "MTU 12V 2000 M93",
        "competitor_rating_name": "MAN D2862 LE463",
        "power_delta_kw": 311,  # MTU 1340 vs MAN 1029 = 311
        "power_delta_pct": 30.2,
        "competitive_position": "strong_advantage",
        "price_positioning": "parity",
        "overlapping_applications": ["fast_ferry", "patrol", "yacht"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["light_duty"],
        "threat_level": "low",
        "our_advantages": [
            "Significantly higher power",
            "Better power-to-weight ratio",
            "More advanced fuel systems",
        ],
        "their_advantages": [
            "MAN service network in Europe",
            "German engineering reputation",
        ],
        "recommended_positioning": "Clear performance leader at this power level",
    },
    # =========================================================================
    # MTU Series 4000 vs Competitors (2000-4000 kW range)
    # =========================================================================
    {
        "our_rating_name": "MTU 12V 4000 M93",
        "competitor_rating_name": "Cat 3516C",
        "power_delta_kw": -185,  # MTU 2340 vs Cat 2525 = -185 (Cat higher)
        "power_delta_pct": -7.3,
        "competitive_position": "parity",
        "price_positioning": "premium",
        "overlapping_applications": ["tug", "osv", "ferry"],
        "overlapping_regions": ["APAC", "Americas", "EMEA"],
        "overlapping_duty_classes": ["light_duty", "medium_duty"],
        "threat_level": "high",
        "our_advantages": [
            "Better fuel efficiency",
            "More advanced engine management",
            "Dual-fuel option available",
        ],
        "their_advantages": [
            "Higher raw power output",
            "Caterpillar global dealer network",
            "Lower maintenance costs",
        ],
        "recommended_positioning": "Focus on lifecycle cost and fuel efficiency",
    },
    {
        "our_rating_name": "MTU 16V 4000 M73",
        "competitor_rating_name": "Cummins QSK60",
        "power_delta_kw": 856,  # MTU 2720 vs Cummins 1864 = 856
        "power_delta_pct": 45.9,
        "competitive_position": "strong_advantage",
        "price_positioning": "premium",
        "overlapping_applications": ["fast_ferry", "osv", "tug"],
        "overlapping_regions": ["APAC", "Americas"],
        "overlapping_duty_classes": ["heavy_duty"],
        "threat_level": "low",
        "our_advantages": [
            "Significantly higher power",
            "More suitable for high-speed applications",
            "Better power density",
        ],
        "their_advantages": [
            "Lower cost",
            "Simpler design",
            "Americas service network",
        ],
        "recommended_positioning": "Performance leader for demanding applications",
    },
    {
        "our_rating_name": "MTU 20V 4000 M93",
        "competitor_rating_name": "Wartsila 9L20",
        "power_delta_kw": 2100,  # MTU 3900 vs Wartsila 1800 = 2100
        "power_delta_pct": 116.7,
        "competitive_position": "strong_advantage",
        "price_positioning": "premium",
        "overlapping_applications": ["fast_ferry", "yacht", "naval"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["light_duty"],
        "threat_level": "low",
        "our_advantages": [
            "Much higher power output",
            "High-speed design",
            "Lower weight per kW",
        ],
        "their_advantages": [
            "Lower RPM (longer overhaul intervals)",
            "Wartsila service network",
            "Medium-speed reliability",
        ],
        "recommended_positioning": "High-speed propulsion vs medium-speed genset application",
    },
    # =========================================================================
    # MTU Series 4000 Gas vs Competitors (Dual-Fuel)
    # =========================================================================
    {
        "our_rating_name": "MTU 16V 4000 M05-N",
        "competitor_rating_name": "Cat 3516C",  # Diesel comparison
        "power_delta_kw": -535,  # MTU 1990 (gas) vs Cat 2525 = -535
        "power_delta_pct": -21.2,
        "competitive_position": "parity",
        "price_positioning": "premium",
        "overlapping_applications": ["ferry", "osv"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["medium_duty"],
        "threat_level": "medium",
        "our_advantages": [
            "LNG/dual-fuel capability",
            "IMO Tier III without SCR in gas mode",
            "Lower emissions",
            "Future fuel readiness",
        ],
        "their_advantages": [
            "Higher diesel power output",
            "Simpler fuel infrastructure",
            "Lower acquisition cost",
        ],
        "recommended_positioning": "Environmental compliance leader for ECA operations",
    },
    # =========================================================================
    # MTU Series 8000 vs Competitors (Large Power - 7000+ kW)
    # =========================================================================
    {
        "our_rating_name": "MTU 20V 8000 M91",
        "competitor_rating_name": "Wartsila 8L20",
        "power_delta_kw": 8400,  # MTU 10000 vs Wartsila 1600 (apples to oranges)
        "power_delta_pct": 525.0,
        "competitive_position": "strong_advantage",
        "price_positioning": "premium",
        "overlapping_applications": ["yacht", "fast_ferry", "naval"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["light_duty"],
        "threat_level": "low",
        "our_advantages": [
            "Flagship high-speed performance",
            "Compact for power output",
            "Naval pedigree",
        ],
        "their_advantages": [
            "Lower RPM medium-speed option",
            "Different application profile",
        ],
        "recommended_positioning": "Unmatched high-speed propulsion at this power level",
    },
    # =========================================================================
    # Cross-competitive in Medium Duty Segment
    # =========================================================================
    {
        "our_rating_name": "MTU 12V 4000 M73",
        "competitor_rating_name": "MAN V12-2000CR",
        "power_delta_kw": 716,  # MTU 2040 vs MAN 1324 = 716
        "power_delta_pct": 54.1,
        "competitive_position": "advantage",
        "price_positioning": "parity",
        "overlapping_applications": ["ferry", "patrol", "osv"],
        "overlapping_regions": ["APAC", "EMEA"],
        "overlapping_duty_classes": ["heavy_duty"],
        "threat_level": "medium",
        "our_advantages": [
            "Higher power output",
            "Better suited for demanding duty",
            "MTU service excellence",
        ],
        "their_advantages": [
            "MAN brand strength in Europe",
            "Common rail technology",
        ],
        "recommended_positioning": "Performance and reliability leader",
    },
    {
        "our_rating_name": "MTU 16V 4000 M63",
        "competitor_rating_name": "Cummins QSK78",
        "power_delta_kw": 163,  # MTU 2400 vs Cummins 2237 = 163
        "power_delta_pct": 7.3,
        "competitive_position": "parity",
        "price_positioning": "premium",
        "overlapping_applications": ["tug", "osv", "ferry"],
        "overlapping_regions": ["APAC", "Americas"],
        "overlapping_duty_classes": ["continuous", "heavy_duty"],
        "threat_level": "high",
        "our_advantages": [
            "More compact design",
            "Better fuel efficiency",
            "European quality standards",
        ],
        "their_advantages": [
            "Robust heavy-duty design",
            "Americas market dominance",
            "Lower price",
        ],
        "recommended_positioning": "Premium quality for demanding continuous duty",
    },
]


async def seed_competitor_maps(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> dict[str, str]:
    """
    Seed competitor rating maps into database.

    This function creates rating-to-rating competitive mappings.
    It requires engine ratings to already exist in kb_engine_ratings.

    Returns:
        Dictionary mapping key -> map_id
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.info("Starting competitor maps seed...")

    # Get rating IDs by name
    rating_ids = await _get_rating_ids_by_name(db)

    map_ids: dict[str, str] = {}
    inserted_count = 0
    skipped_count = 0

    now = datetime.now(timezone.utc)
    today = date.today()

    for mapping in COMPETITIVE_MAPPINGS:
        our_rating_name = mapping["our_rating_name"]
        competitor_rating_name = mapping["competitor_rating_name"]

        # Find rating IDs
        our_rating_id = rating_ids.get(our_rating_name)
        competitor_rating_id = rating_ids.get(competitor_rating_name)

        if not our_rating_id:
            logger.debug(f"Skipping: our rating '{our_rating_name}' not found in KB")
            skipped_count += 1
            continue

        if not competitor_rating_id:
            logger.debug(
                f"Skipping: competitor rating '{competitor_rating_name}' not found in KB"
            )
            skipped_count += 1
            continue

        map_id = str(uuid.uuid4())
        key = f"{our_rating_name}:{competitor_rating_name}"

        try:
            async with db._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kb_rating_competitor_map (
                        id, our_rating_id, competitor_rating_id,
                        power_delta_kw, power_delta_pct,
                        competitive_position, price_positioning,
                        overlapping_applications, overlapping_regions,
                        overlapping_duty_classes,
                        threat_level,
                        our_advantages, their_advantages,
                        recommended_positioning,
                        last_competitive_review, reviewed_by,
                        notes, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3,
                        $4, $5,
                        $6, $7,
                        $8, $9, $10,
                        $11,
                        $12, $13,
                        $14,
                        $15, $16,
                        $17, $18, $19
                    )
                    ON CONFLICT (our_rating_id, competitor_rating_id)
                    DO UPDATE SET
                        power_delta_kw = EXCLUDED.power_delta_kw,
                        power_delta_pct = EXCLUDED.power_delta_pct,
                        competitive_position = EXCLUDED.competitive_position,
                        threat_level = EXCLUDED.threat_level,
                        updated_at = EXCLUDED.updated_at
                    """,
                    map_id,
                    our_rating_id,
                    competitor_rating_id,
                    mapping.get("power_delta_kw"),
                    mapping.get("power_delta_pct"),
                    mapping.get("competitive_position"),
                    mapping.get("price_positioning"),
                    mapping.get("overlapping_applications"),  # JSONB
                    mapping.get("overlapping_regions"),  # JSONB
                    mapping.get("overlapping_duty_classes"),  # JSONB
                    mapping.get("threat_level", "medium"),
                    mapping.get("our_advantages"),  # JSONB
                    mapping.get("their_advantages"),  # JSONB
                    mapping.get("recommended_positioning"),
                    today,
                    "seed_data",
                    f"Seeded mapping: {our_rating_name} vs {competitor_rating_name}",
                    now,
                    now,
                )

            map_ids[key] = map_id
            inserted_count += 1
            logger.debug(f"Inserted mapping: {key}")

        except Exception as e:
            logger.error(f"Failed to insert mapping {key}: {e}")
            skipped_count += 1

    logger.info(
        f"Competitor maps seed complete: {inserted_count} inserted, "
        f"{skipped_count} skipped"
    )
    return map_ids


async def _get_rating_ids_by_name(db: KnowledgeBaseDatabase) -> dict[str, str]:
    """Get mapping of rating_name -> rating_id from kb_engine_ratings."""
    rating_ids = {}

    async with db._pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, rating_name FROM kb_engine_ratings")
        for row in rows:
            rating_ids[row["rating_name"]] = row["id"]

    logger.debug(f"Loaded {len(rating_ids)} engine ratings from KB")
    return rating_ids


async def clear_competitor_maps(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> int:
    """
    Clear all competitor maps from database.

    WARNING: This is destructive and cannot be undone.

    Returns:
        Number of records deleted
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    async with db._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM kb_rating_competitor_map")
        await conn.execute("DELETE FROM kb_rating_competitor_map")

    logger.info(f"Cleared {count} competitor maps")
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

        print("Seeding competitor maps...")
        map_ids = await seed_competitor_maps(db)
        print(f"Seeded {len(map_ids)} competitor maps")

        # Print summary
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT competitive_position, COUNT(*) as count
                FROM kb_rating_competitor_map
                GROUP BY competitive_position
                ORDER BY count DESC
                """
            )
            print("\nMappings by competitive position:")
            for row in rows:
                print(f"  {row['competitive_position']}: {row['count']}")

    asyncio.run(main())
