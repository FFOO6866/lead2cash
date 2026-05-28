"""
Competitor Engagements Seed Data
Phase 2 Knowledge Base Population

This module populates kb_competitor_engagements with sample win/loss data
for competitor intelligence tracking.

Purpose:
    - Demo competitor threat alerting
    - Historical data for win rate analysis
    - Links to SAP customers via customer_id

Usage:
    from lead_to_cash.services.knowledge_base.seed_competitor_engagements import (
        seed_competitor_engagements,
    )

    # Seed all competitor engagements
    engagement_ids = await seed_competitor_engagements()
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
# COMPETITOR ENGAGEMENT DATA
# Sample win/loss scenarios for testing and demo
# =============================================================================

COMPETITOR_ENGAGEMENTS: list[dict[str, Any]] = [
    # =========================================================================
    # WINS (lost_to_us) - Competitor activity we beat
    # =========================================================================
    {
        "customer_id": "0000100001",
        "customer_name": "Batam Fast Ferry",
        "is_our_customer": True,
        "customer_relationship": "active",
        "competitor": "caterpillar",
        "competitor_engine_name": "Cat C32B",
        "engagement_type": "lost_to_us",
        "engagement_date": date(2024, 6, 15),
        "engagement_value_usd": 1200000.00,
        "vessel_name": "Batam Express II",
        "vessel_type": "fast_ferry",
        "quantity": 2,
        "source_type": "field_intel",
        "source_confidence": 0.95,
        "threat_level": "informational",
        "threat_reason": "We won this deal - Caterpillar was competing",
        "requires_sales_action": False,
        "region": "APAC",
        "country": "Singapore",
        "notes": "Customer chose MTU 12V 2000 M93 over Cat C32B due to better fuel efficiency",
    },
    {
        "customer_id": "0022005992",
        "customer_name": "ST Engineering Marine",
        "is_our_customer": True,
        "customer_relationship": "active",
        "competitor": "man",
        "competitor_engine_name": "MAN V12-2000CR",
        "engagement_type": "lost_to_us",
        "engagement_date": date(2024, 3, 20),
        "engagement_value_usd": 3500000.00,
        "vessel_type": "patrol",
        "quantity": 4,
        "source_type": "press_release",
        "source_url": "https://example.com/stengg-mtu-order",
        "source_confidence": 0.90,
        "threat_level": "informational",
        "threat_reason": "Strategic win at key account",
        "requires_sales_action": False,
        "region": "APAC",
        "country": "Singapore",
        "notes": "ST Engineering selected MTU for new patrol vessel program",
    },
    # =========================================================================
    # CRITICAL THREATS - Competitor wins at our active customers
    # =========================================================================
    {
        "customer_id": "0000100002",
        "customer_name": "Maersk A/S",
        "is_our_customer": True,
        "customer_relationship": "active",
        "competitor": "wartsila",
        "competitor_engine_name": "Wartsila 31DF",
        "engagement_type": "contract_win",
        "engagement_date": date(2025, 1, 10),
        "engagement_value_usd": 8500000.00,
        "vessel_name": "Maersk Emerald",
        "vessel_type": "container",
        "quantity": 4,
        "source_type": "press_release",
        "source_url": "https://example.com/maersk-wartsila",
        "source_confidence": 0.95,
        "threat_level": "critical",
        "threat_reason": "Competitor won at our active customer for genset application",
        "requires_sales_action": True,
        "action_recommendation": "Schedule meeting with Maersk procurement to understand decision factors",
        "action_due_date": date(2025, 2, 1),
        "region": "EMEA",
        "country": "Denmark",
        "notes": "Maersk selected Wartsila dual-fuel for new container vessel gensets",
    },
    {
        "customer_id": "0000100003",
        "customer_name": "Neptune Energy",
        "is_our_customer": True,
        "customer_relationship": "active",
        "competitor": "caterpillar",
        "competitor_engine_name": "Cat 3516C",
        "engagement_type": "contract_win",
        "engagement_date": date(2024, 11, 5),
        "engagement_value_usd": 4200000.00,
        "vessel_name": "Neptune Viking",
        "vessel_type": "osv",
        "quantity": 2,
        "source_type": "trade_news",
        "source_confidence": 0.85,
        "threat_level": "critical",
        "threat_reason": "Lost deal to Caterpillar at active customer",
        "loss_reason": "Price competitiveness - Cat was 15% cheaper",
        "requires_sales_action": True,
        "action_recommendation": "Review pricing strategy for OSV segment",
        "region": "EMEA",
        "country": "Netherlands",
        "notes": "Neptune chose Cat due to lower acquisition cost, despite higher fuel consumption",
    },
    # =========================================================================
    # HIGH THREATS - Competitor wins at our prospects
    # =========================================================================
    {
        "customer_id": None,
        "customer_name": "Penguin Shipyard (Customer)",
        "is_our_customer": False,
        "customer_relationship": "prospect",
        "competitor": "mtu",  # This is us winning, but from competitor POV
        "competitor_engine_name": "MTU 12V 2000 M93",
        "engagement_type": "contract_win",
        "engagement_date": date(2024, 9, 30),
        "engagement_value_usd": 800000.00,
        "vessel_type": "crew_boat",
        "quantity": 2,
        "source_type": "field_intel",
        "source_confidence": 0.90,
        "threat_level": "informational",
        "notes": "Converted prospect to customer",
    },
    {
        "customer_id": None,
        "customer_name": "Vietnam Coast Guard",
        "is_our_customer": False,
        "customer_relationship": "prospect",
        "competitor": "man",
        "competitor_engine_name": "MAN D2868 LE433",
        "engagement_type": "contract_win",
        "engagement_date": date(2024, 12, 1),
        "engagement_value_usd": 6000000.00,
        "vessel_type": "patrol",
        "quantity": 8,
        "source_type": "press_release",
        "source_confidence": 0.80,
        "threat_level": "high",
        "threat_reason": "Large patrol vessel order went to MAN",
        "requires_sales_action": True,
        "action_recommendation": "Engage with Vietnam shipyards for future opportunities",
        "region": "APAC",
        "country": "Vietnam",
        "notes": "MAN won large Vietnam Coast Guard patrol boat tender",
    },
    # =========================================================================
    # MEDIUM THREATS - Competitor activity in our market
    # =========================================================================
    {
        "customer_id": None,
        "customer_name": "Indonesian Navy",
        "is_our_customer": False,
        "customer_relationship": "unknown",
        "competitor": "caterpillar",
        "competitor_engine_name": "Cat 3516C",
        "engagement_type": "proposal",
        "engagement_date": date(2025, 1, 15),
        "vessel_type": "patrol",
        "quantity": 10,
        "source_type": "trade_news",
        "source_confidence": 0.70,
        "threat_level": "medium",
        "threat_reason": "Caterpillar submitting proposal for large naval program",
        "requires_sales_action": True,
        "action_recommendation": "Monitor and engage Indonesian naval procurement",
        "region": "APAC",
        "country": "Indonesia",
        "notes": "Caterpillar reportedly bidding on Indonesian Navy fast patrol boat program",
    },
    {
        "customer_id": None,
        "customer_name": "Singapore Ferry Operators Association",
        "is_our_customer": False,
        "customer_relationship": "unknown",
        "competitor": "yanmar",
        "competitor_engine_name": "Yanmar 6AYM-ETE",
        "engagement_type": "demo",
        "engagement_date": date(2025, 1, 20),
        "vessel_type": "ferry",
        "quantity": 1,
        "source_type": "field_intel",
        "source_confidence": 0.75,
        "threat_level": "medium",
        "threat_reason": "Yanmar conducting demos in Singapore ferry market",
        "requires_sales_action": True,
        "action_recommendation": "Schedule MTU demo with ferry operators",
        "region": "APAC",
        "country": "Singapore",
        "notes": "Yanmar aggressively marketing to Singapore ferry operators",
    },
    # =========================================================================
    # LOW THREATS - General market intelligence
    # =========================================================================
    {
        "customer_id": None,
        "customer_name": "Thai Shipbuilding Co",
        "is_our_customer": False,
        "customer_relationship": "unknown",
        "competitor": "weichai",
        "competitor_engine_name": "Weichai WP13",
        "engagement_type": "partnership",
        "engagement_date": date(2024, 10, 1),
        "source_type": "press_release",
        "source_confidence": 0.85,
        "threat_level": "low",
        "threat_reason": "Weichai partnership in budget segment we don't target",
        "requires_sales_action": False,
        "region": "APAC",
        "country": "Thailand",
        "notes": "Weichai appointed Thai Shipbuilding as authorized distributor",
    },
    {
        "customer_id": None,
        "customer_name": "Chinese Fishing Fleet Operator",
        "is_our_customer": False,
        "customer_relationship": "unknown",
        "competitor": "weichai",
        "competitor_engine_name": "Weichai WHM6160",
        "engagement_type": "contract_win",
        "engagement_date": date(2024, 8, 15),
        "engagement_value_usd": 2000000.00,
        "vessel_type": "fishing",
        "quantity": 20,
        "source_type": "trade_news",
        "source_confidence": 0.70,
        "threat_level": "low",
        "threat_reason": "Budget fishing fleet segment - not our target market",
        "requires_sales_action": False,
        "region": "APAC",
        "country": "China",
        "notes": "Large order but in segment we don't compete",
    },
    # =========================================================================
    # RUMORED - Unconfirmed activity
    # =========================================================================
    {
        "customer_id": None,
        "customer_name": "Malaysian Navy (Potential)",
        "is_our_customer": False,
        "customer_relationship": "unknown",
        "competitor": "man",
        "competitor_engine_name": "MAN V12-2000CR",
        "engagement_type": "rumored",
        "engagement_date": date(2025, 1, 1),
        "vessel_type": "patrol",
        "source_type": "field_intel",
        "source_confidence": 0.50,
        "threat_level": "medium",
        "threat_reason": "Rumored MAN activity in Malaysian naval program",
        "requires_sales_action": True,
        "action_recommendation": "Verify rumor through Malaysian contacts",
        "region": "APAC",
        "country": "Malaysia",
        "notes": "Unconfirmed reports of MAN engaging with Malaysian Navy",
    },
]


async def seed_competitor_engagements(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> dict[str, str]:
    """
    Seed competitor engagements into database.

    Returns:
        Dictionary mapping customer_name:competitor -> engagement_id
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.info("Starting competitor engagements seed...")

    engagement_ids: dict[str, str] = {}
    inserted_count = 0

    now = datetime.now(timezone.utc)

    for engagement in COMPETITOR_ENGAGEMENTS:
        engagement_id = str(uuid.uuid4())
        key = f"{engagement['customer_name']}:{engagement['competitor']}"

        try:
            async with db._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kb_competitor_engagements (
                        id, customer_id, customer_name, is_our_customer,
                        customer_relationship,
                        competitor, competitor_engine_name,
                        engagement_type, engagement_date, engagement_value_usd,
                        vessel_name, vessel_type, quantity,
                        source_type, source_url, source_confidence,
                        threat_level, threat_reason, loss_reason,
                        requires_sales_action, action_recommendation, action_due_date,
                        region, country,
                        notes, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5,
                        $6, $7,
                        $8, $9, $10,
                        $11, $12, $13,
                        $14, $15, $16,
                        $17, $18, $19,
                        $20, $21, $22,
                        $23, $24,
                        $25, $26, $27
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    engagement_id,
                    engagement.get("customer_id"),
                    engagement.get("customer_name"),
                    engagement.get("is_our_customer", False),
                    engagement.get("customer_relationship"),
                    engagement.get("competitor"),
                    engagement.get("competitor_engine_name"),
                    engagement.get("engagement_type"),
                    engagement.get("engagement_date"),
                    engagement.get("engagement_value_usd"),
                    engagement.get("vessel_name"),
                    engagement.get("vessel_type"),
                    engagement.get("quantity", 1),
                    engagement.get("source_type"),
                    engagement.get("source_url"),
                    engagement.get("source_confidence"),
                    engagement.get("threat_level", "medium"),
                    engagement.get("threat_reason"),
                    engagement.get("loss_reason"),
                    engagement.get("requires_sales_action", False),
                    engagement.get("action_recommendation"),
                    engagement.get("action_due_date"),
                    engagement.get("region"),
                    engagement.get("country"),
                    engagement.get("notes"),
                    now,
                    now,
                )

            engagement_ids[key] = engagement_id
            inserted_count += 1
            logger.debug(f"Inserted engagement: {key}")

        except Exception as e:
            logger.error(f"Failed to insert engagement {key}: {e}")

    logger.info(f"Competitor engagements seed complete: {inserted_count} inserted")
    return engagement_ids


async def clear_competitor_engagements(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> int:
    """
    Clear all competitor engagements from database.

    WARNING: This is destructive and cannot be undone.

    Returns:
        Number of records deleted
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    async with db._pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM kb_competitor_engagements")
        await conn.execute("DELETE FROM kb_competitor_engagements")

    logger.info(f"Cleared {count} competitor engagements")
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

        print("Seeding competitor engagements...")
        engagement_ids = await seed_competitor_engagements(db)
        print(f"Seeded {len(engagement_ids)} competitor engagements")

        # Print summary
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT threat_level, COUNT(*) as count
                FROM kb_competitor_engagements
                GROUP BY threat_level
                ORDER BY count DESC
                """
            )
            print("\nEngagements by threat level:")
            for row in rows:
                print(f"  {row['threat_level']}: {row['count']}")

            rows = await conn.fetch(
                """
                SELECT engagement_type, COUNT(*) as count
                FROM kb_competitor_engagements
                GROUP BY engagement_type
                ORDER BY count DESC
                """
            )
            print("\nEngagements by type:")
            for row in rows:
                print(f"  {row['engagement_type']}: {row['count']}")

    asyncio.run(main())
