"""
Marine Engine Knowledge Base - Seed Data

Tier-1 Global Players and Engine Families from requirements specification.

Manufacturers:
- Wärtsilä (Finland)
- MAN Energy Solutions (Germany)
- SEMT Pielstick / MAN France
- Caterpillar / MaK (Germany)
- HD Hyundai / HiMSEN (South Korea)
- Bergen Engines (Norway)
- Daihatsu (Japan)
- Niigata Power Systems (Japan)
- ABC - Anglo Belgian Corporation (Belgium)

Usage:
    from lead_to_cash.services.knowledge_base.seed_data import seed_knowledge_base

    # Seed all data
    await seed_knowledge_base()

    # Or seed individually
    await seed_manufacturers()
    await seed_engine_series()
    await seed_engine_models()
    await seed_aliases()
"""

import json
import logging
import uuid
from typing import Any, Optional

from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.models import (
    Application,
    EngineApplicationMap,
    EngineModel,
    EngineSeries,
    EntityAlias,
    Manufacturer,
    ManufacturerTier,
    MarketSegment,
    MarketSegmentType,
)
from lead_to_cash.services.knowledge_base.seed_competitor_engagements import (
    seed_competitor_engagements,
)
from lead_to_cash.services.knowledge_base.seed_competitor_maps import (
    seed_competitor_maps,
)
from lead_to_cash.services.knowledge_base.seed_customer_requirements import (
    seed_customer_requirements,
)

# Phase 2 seed modules (rating-level data)
from lead_to_cash.services.knowledge_base.seed_engine_ratings import (
    seed_engine_ratings,
)
from lead_to_cash.utils.logging import get_logger

# Use structured logger with correlation ID support
logger = get_logger(__name__)


# =============================================================================
# TIER-1 MANUFACTURERS
# =============================================================================

MANUFACTURERS: list[dict[str, Any]] = [
    {
        "name": "Wärtsilä",
        "country": "Finland",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.wartsila.com",
        "description": "Global leader in marine and energy markets with comprehensive portfolio of engines, propulsion systems, and lifecycle services.",
    },
    {
        "name": "MAN Energy Solutions",
        "country": "Germany",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.man-es.com",
        "description": "Leading provider of large-bore diesel and gas engines, turbochargers, and propulsion systems for marine and power applications.",
    },
    {
        "name": "SEMT Pielstick",
        "country": "France",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.man-es.com/company/locations/france",
        "description": "Part of MAN Energy Solutions, specializing in medium-speed diesel engines for marine and power generation (PC series).",
    },
    {
        "name": "Caterpillar MaK",
        "country": "Germany",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.cat.com",
        "description": "Caterpillar's marine and offshore engine division, producing medium-speed engines under the MaK brand for propulsion and power generation.",
    },
    {
        "name": "HD Hyundai HiMSEN",
        "country": "South Korea",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.hyundai-engine.com",
        "description": "HD Hyundai's engine division producing medium-speed engines for marine and power generation applications.",
    },
    {
        "name": "Bergen Engines",
        "country": "Norway",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.bergenengines.com",
        "description": "Former Rolls-Royce Power Systems brand (sold to Langley Holdings in December 2021). Bergen Engines specializes in medium-speed gas and diesel engines for marine, offshore, and land-based power generation. RRPS continues to sell and service Bergen engines under existing agreements.",
    },
    {
        "name": "Daihatsu Diesel",
        "country": "Japan",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.dhtd.co.jp/en",
        "description": "Japanese manufacturer of medium-speed marine diesel engines for auxiliary and propulsion applications.",
    },
    {
        "name": "Niigata Power Systems",
        "country": "Japan",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.niigata-power.com",
        "description": "Japanese manufacturer of medium-speed diesel and dual-fuel engines for marine and industrial applications.",
    },
    {
        "name": "ABC Engines",
        "country": "Belgium",
        "tier": ManufacturerTier.TIER_1.value,
        "website": "https://www.abc-engines.com",
        "description": "Anglo Belgian Corporation, regional manufacturer of medium-speed diesel engines for marine propulsion and power generation.",
    },
    # =========================================================================
    # TIER-2 REGIONAL PLAYERS
    # =========================================================================
    {
        "name": "Yanmar",
        "country": "Japan",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.yanmar.com",
        "description": "Japanese manufacturer specializing in compact marine diesel engines and propulsion systems for smaller vessels.",
    },
    {
        "name": "Cummins Marine",
        "country": "USA",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.cummins.com",
        "description": "American manufacturer of marine diesel engines for commercial, recreational, and military vessels.",
    },
    {
        "name": "Rolls-Royce Power Systems",
        "country": "Germany",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.mtu-solutions.com",
        "description": "MTU brand engines for marine propulsion, offshore, and land-based power applications.",
    },
    {
        "name": "Mitsubishi Heavy Industries",
        "country": "Japan",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.mhi.com",
        "description": "Japanese conglomerate producing marine diesel engines and turbochargers for large vessels.",
    },
    {
        "name": "Weichai Power",
        "country": "China",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.weichai.com",
        "description": "Chinese manufacturer of diesel engines for marine, automotive, and power generation applications.",
    },
    {
        "name": "WinGD",
        "country": "Switzerland",
        "tier": ManufacturerTier.TIER_2.value,
        "website": "https://www.wingd.com",
        "description": "Designer and licensor of two-stroke marine diesel engines for large container ships and tankers.",
    },
    # =========================================================================
    # TIER-3 EMERGING/SPECIALIZED PLAYERS
    # =========================================================================
    {
        "name": "CSSC Marine Power",
        "country": "China",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.cssc.net.cn",
        "description": "Chinese state-owned manufacturer of marine diesel engines and propulsion systems.",
    },
    {
        "name": "Doosan Infracore",
        "country": "South Korea",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.doosaninfracore.com",
        "description": "Korean manufacturer of diesel engines for marine, construction, and industrial applications.",
    },
    {
        "name": "Baudouin",
        "country": "France",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.baudouin.com",
        "description": "French manufacturer of marine propulsion engines now part of Weichai Power.",
    },
    {
        "name": "Volvo Penta",
        "country": "Sweden",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.volvopenta.com",
        "description": "Swedish manufacturer of marine engines for commercial and leisure craft.",
    },
    {
        "name": "Scania Marine",
        "country": "Sweden",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.scania.com",
        "description": "Swedish manufacturer of marine diesel engines for patrol boats, ferries, and workboats.",
    },
    {
        "name": "John Deere Marine",
        "country": "USA",
        "tier": ManufacturerTier.TIER_3.value,
        "website": "https://www.deere.com",
        "description": "American manufacturer of marine diesel engines for commercial and recreational vessels.",
    },
]


# =============================================================================
# ENGINE SERIES
# =============================================================================

ENGINE_SERIES: list[dict[str, Any]] = [
    # Wärtsilä
    {
        "manufacturer": "Wärtsilä",
        "brand": "Wärtsilä",
        "series_name": "31",
        "is_current": True,
    },
    {
        "manufacturer": "Wärtsilä",
        "brand": "Wärtsilä",
        "series_name": "46F",
        "is_current": True,
    },
    # MAN Energy Solutions
    {
        "manufacturer": "MAN Energy Solutions",
        "brand": "MAN",
        "series_name": "32/44CR",
        "is_current": True,
    },
    {
        "manufacturer": "MAN Energy Solutions",
        "brand": "MAN",
        "series_name": "48/60CR",
        "is_current": True,
    },
    {
        "manufacturer": "MAN Energy Solutions",
        "brand": "MAN",
        "series_name": "51/60",
        "is_current": True,
    },
    # SEMT Pielstick
    {
        "manufacturer": "SEMT Pielstick",
        "brand": "Pielstick",
        "series_name": "PC2.6B",
        "is_current": True,
    },
    {
        "manufacturer": "SEMT Pielstick",
        "brand": "Pielstick",
        "series_name": "PC4.2B",
        "is_current": True,
    },
    {
        "manufacturer": "SEMT Pielstick",
        "brand": "Pielstick",
        "series_name": "PC40",
        "is_current": True,
    },
    # Caterpillar MaK
    {
        "manufacturer": "Caterpillar MaK",
        "brand": "MaK",
        "series_name": "M32C",
        "is_current": True,
    },
    {
        "manufacturer": "Caterpillar MaK",
        "brand": "MaK",
        "series_name": "M43C",
        "is_current": True,
    },
    {
        "manufacturer": "Caterpillar MaK",
        "brand": "MaK",
        "series_name": "M46DF",
        "is_current": True,
    },
    {
        "manufacturer": "Caterpillar MaK",
        "brand": "MaK",
        "series_name": "M34DF",
        "is_current": True,
    },
    # HD Hyundai HiMSEN
    {
        "manufacturer": "HD Hyundai HiMSEN",
        "brand": "HiMSEN",
        "series_name": "H21/32",
        "is_current": True,
    },
    {
        "manufacturer": "HD Hyundai HiMSEN",
        "brand": "HiMSEN",
        "series_name": "H32/40",
        "is_current": True,
    },
    {
        "manufacturer": "HD Hyundai HiMSEN",
        "brand": "HiMSEN",
        "series_name": "H54DF",
        "is_current": True,
    },
    # Bergen Engines
    {
        "manufacturer": "Bergen Engines",
        "brand": "Bergen",
        "series_name": "C25:33",
        "is_current": True,
    },
    {
        "manufacturer": "Bergen Engines",
        "brand": "Bergen",
        "series_name": "B32:40",
        "is_current": True,
    },
    {
        "manufacturer": "Bergen Engines",
        "brand": "Bergen",
        "series_name": "B33:45",
        "is_current": True,
    },
    {
        "manufacturer": "Bergen Engines",
        "brand": "Bergen",
        "series_name": "B36:45",
        "is_current": True,
    },
    # Daihatsu
    {
        "manufacturer": "Daihatsu Diesel",
        "brand": "Daihatsu",
        "series_name": "DE",
        "is_current": True,
    },
    {
        "manufacturer": "Daihatsu Diesel",
        "brand": "Daihatsu",
        "series_name": "DK",
        "is_current": True,
    },
    # Niigata
    {
        "manufacturer": "Niigata Power Systems",
        "brand": "Niigata",
        "series_name": "28AHX-DF",
        "is_current": True,
    },
    # ABC
    {
        "manufacturer": "ABC Engines",
        "brand": "ABC",
        "series_name": "DV36",
        "is_current": True,
    },
    {
        "manufacturer": "ABC Engines",
        "brand": "ABC",
        "series_name": "DZC",
        "is_current": True,
    },
]


# =============================================================================
# ENGINE MODELS (with specifications from requirements)
# =============================================================================

ENGINE_MODELS: list[dict[str, Any]] = [
    # Wärtsilä 31
    {
        "series": "31",
        "manufacturer": "Wärtsilä",
        "model_name": "Wärtsilä 31DF",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 4600,
        "power_max_kw": 10400,
        "fuel_types": ["diesel", "gas", "dual_fuel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "World's most efficient 4-stroke engine, available in diesel, gas, and dual-fuel variants.",
    },
    # Wärtsilä 46F
    {
        "series": "46F",
        "manufacturer": "Wärtsilä",
        "model_name": "Wärtsilä 46F",
        "rpm_min": 500,
        "rpm_max": 600,
        "power_min_kw": 7500,
        "power_max_kw": 20000,
        "fuel_types": ["diesel", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "High-power medium-speed engine for FPSO, offshore platforms, and large marine vessels.",
    },
    # MAN 32/44CR
    {
        "series": "32/44CR",
        "manufacturer": "MAN Energy Solutions",
        "model_name": "MAN 32/44CR",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 3600,
        "power_max_kw": 12000,
        "fuel_types": ["diesel", "hfo", "dual_fuel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Common rail medium-speed engine for propulsion, gensets, and offshore power.",
    },
    # MAN 48/60CR
    {
        "series": "48/60CR",
        "manufacturer": "MAN Energy Solutions",
        "model_name": "MAN 48/60CR",
        "rpm_min": 500,
        "rpm_max": 600,
        "power_min_kw": 12000,
        "power_max_kw": 30000,
        "fuel_types": ["diesel", "hfo", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "High-power engine for FPSO, offshore platforms, and large vessels.",
    },
    # Pielstick PC2.6B
    {
        "series": "PC2.6B",
        "manufacturer": "SEMT Pielstick",
        "model_name": "PC2.6B",
        "rpm_min": 600,
        "rpm_max": 600,
        "power_min_kw": 9000,
        "power_max_kw": 13500,
        "fuel_types": ["diesel", "hfo"],
        "configuration": "V",
        "emission_tier": "IMO Tier II",
        "description": "Proven medium-speed engine for offshore gensets and marine power applications.",
    },
    # MaK M32C
    {
        "series": "M32C",
        "manufacturer": "Caterpillar MaK",
        "model_name": "MaK M32C",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 6000,
        "power_max_kw": 8000,
        "fuel_types": ["diesel", "hfo"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Robust medium-speed engine for propulsion and genset applications.",
    },
    # MaK M43C
    {
        "series": "M43C",
        "manufacturer": "Caterpillar MaK",
        "model_name": "MaK M43C",
        "rpm_min": 500,
        "rpm_max": 514,
        "power_min_kw": 5400,
        "power_max_kw": 9450,
        "fuel_types": ["diesel", "hfo"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Medium-speed engine for propulsion and offshore power applications.",
    },
    # MaK M46DF
    {
        "series": "M46DF",
        "manufacturer": "Caterpillar MaK",
        "model_name": "MaK M46DF",
        "rpm_min": 500,
        "rpm_max": 514,
        "power_min_kw": 5400,
        "power_max_kw": 18000,
        "fuel_types": ["dual_fuel", "lng", "diesel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Dual-fuel medium-speed engine for offshore power and large vessels (LNG capable).",
    },
    # HiMSEN H21/32
    {
        "series": "H21/32",
        "manufacturer": "HD Hyundai HiMSEN",
        "model_name": "HiMSEN H21/32",
        "rpm_min": 720,
        "rpm_max": 900,
        "power_min_kw": 800,
        "power_max_kw": 2000,
        "fuel_types": ["diesel"],
        "configuration": "inline",
        "emission_tier": "IMO Tier III",
        "description": "Compact medium-speed engine for marine auxiliary gensets.",
    },
    # HiMSEN H32/40
    {
        "series": "H32/40",
        "manufacturer": "HD Hyundai HiMSEN",
        "model_name": "HiMSEN H32/40",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 3000,
        "power_max_kw": 9600,
        "fuel_types": ["diesel", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Medium-speed engine for propulsion and offshore gensets.",
    },
    # HiMSEN H54DF
    {
        "series": "H54DF",
        "manufacturer": "HD Hyundai HiMSEN",
        "model_name": "HiMSEN H54DF",
        "rpm_min": 600,
        "rpm_max": 600,
        "power_min_kw": 8900,
        "power_max_kw": 26460,
        "fuel_types": ["dual_fuel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "High-power dual-fuel engine for FPSO and offshore power generation.",
    },
    # Bergen C25:33
    {
        "series": "C25:33",
        "manufacturer": "Bergen Engines",
        "model_name": "Bergen C25:33",
        "rpm_min": 900,
        "rpm_max": 1000,
        "power_min_kw": 1200,
        "power_max_kw": 1920,
        "fuel_types": ["diesel", "gas"],
        "configuration": "inline",
        "emission_tier": "IMO Tier III",
        "description": "Compact gas/diesel engine for auxiliaries and drilling rigs.",
    },
    # Bergen B32:40
    {
        "series": "B32:40",
        "manufacturer": "Bergen Engines",
        "model_name": "Bergen B32:40",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 3000,
        "power_max_kw": 9000,
        "fuel_types": ["diesel", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Medium-speed engine for OSVs, PSVs, and drillships.",
    },
    # Bergen B36:45
    {
        "series": "B36:45",
        "manufacturer": "Bergen Engines",
        "model_name": "Bergen B36:45",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 6000,
        "power_max_kw": 12000,
        "fuel_types": ["gas", "diesel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "High-power engine for FPSO, offshore platforms, and power plants.",
    },
    # Daihatsu DE-33
    {
        "series": "DE",
        "manufacturer": "Daihatsu Diesel",
        "model_name": "Daihatsu 8DE-33",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 3600,
        "power_max_kw": 4800,
        "fuel_types": ["diesel"],
        "configuration": "inline",
        "emission_tier": "IMO Tier II",
        "description": "Medium-speed auxiliary engine for cargo vessels.",
    },
    # Niigata 28AHX-DF
    {
        "series": "28AHX-DF",
        "manufacturer": "Niigata Power Systems",
        "model_name": "Niigata 28AHX-DF",
        "rpm_min": 750,
        "rpm_max": 750,
        "power_min_kw": 4000,
        "power_max_kw": 6000,
        "fuel_types": ["dual_fuel", "lng", "diesel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Dual-fuel engine for tugboats and offshore support vessels.",
    },
    # ABC DV36
    {
        "series": "DV36",
        "manufacturer": "ABC Engines",
        "model_name": "ABC 16DV36",
        "rpm_min": 600,
        "rpm_max": 750,
        "power_min_kw": 7800,
        "power_max_kw": 10400,
        "fuel_types": ["diesel", "hfo"],
        "configuration": "V",
        "emission_tier": "IMO Tier II",
        "description": "Medium-speed engine for marine propulsion and gensets.",
    },
    # ABC DZC
    {
        "series": "DZC",
        "manufacturer": "ABC Engines",
        "model_name": "ABC DZC",
        "rpm_min": 720,
        "rpm_max": 1000,
        "power_min_kw": 1000,
        "power_max_kw": 6000,
        "fuel_types": ["diesel"],
        "configuration": "inline",
        "emission_tier": "IMO Tier II",
        "description": "Compact medium-speed engine for marine propulsion and gensets.",
    },
    # MAN 51/60
    {
        "series": "51/60",
        "manufacturer": "MAN Energy Solutions",
        "model_name": "MAN 51/60",
        "rpm_min": 500,
        "rpm_max": 514,
        "power_min_kw": 15000,
        "power_max_kw": 34320,
        "fuel_types": ["diesel", "hfo", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Ultra high-power engine for FPSO, large vessels, and power plants.",
    },
    # Pielstick PC4.2B
    {
        "series": "PC4.2B",
        "manufacturer": "SEMT Pielstick",
        "model_name": "PC4.2B",
        "rpm_min": 500,
        "rpm_max": 600,
        "power_min_kw": 10000,
        "power_max_kw": 14000,
        "fuel_types": ["diesel", "hfo"],
        "configuration": "V",
        "emission_tier": "IMO Tier II",
        "description": "High-power medium-speed engine for offshore power and naval applications.",
    },
    # MaK M34DF
    {
        "series": "M34DF",
        "manufacturer": "Caterpillar MaK",
        "model_name": "MaK M34DF",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 3000,
        "power_max_kw": 6000,
        "fuel_types": ["dual_fuel", "lng", "diesel"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Compact dual-fuel engine for gensets and propulsion applications.",
    },
    # Bergen B33:45
    {
        "series": "B33:45",
        "manufacturer": "Bergen Engines",
        "model_name": "Bergen B33:45",
        "rpm_min": 450,
        "rpm_max": 750,
        "power_min_kw": 3600,
        "power_max_kw": 5400,
        "fuel_types": ["diesel", "gas"],
        "configuration": "V",
        "emission_tier": "IMO Tier III",
        "description": "Medium-speed engine for propulsion and offshore power applications.",
    },
    # Daihatsu DK
    {
        "series": "DK",
        "manufacturer": "Daihatsu Diesel",
        "model_name": "Daihatsu DK-28",
        "rpm_min": 720,
        "rpm_max": 750,
        "power_min_kw": 1200,
        "power_max_kw": 3000,
        "fuel_types": ["diesel"],
        "configuration": "inline",
        "emission_tier": "IMO Tier II",
        "description": "Compact medium-speed auxiliary engine for ferries and cargo ships.",
    },
]


# =============================================================================
# ALIASES (for fuzzy matching)
# =============================================================================

ALIASES: list[dict[str, Any]] = [
    # Wärtsilä aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Wärtsilä",
        "alias_text": "Wartsila",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Wärtsilä",
        "alias_text": "Wärtsilä",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Wärtsilä",
        "alias_text": "Waertsilae",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "31",
        "alias_text": "W31",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "31",
        "alias_text": "Wärtsilä31",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "31",
        "alias_text": "31DF",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "46F",
        "alias_text": "W46F",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "46F",
        "alias_text": "46F",
        "alias_type": "common_name",
    },
    # MAN aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "MAN Energy Solutions",
        "alias_text": "MAN",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "MAN Energy Solutions",
        "alias_text": "MAN ES",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "MAN Energy Solutions",
        "alias_text": "MAN Diesel",
        "alias_type": "former_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "32/44CR",
        "alias_text": "32/44CR",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "32/44CR",
        "alias_text": "V32/44CR",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "32/44CR",
        "alias_text": "L32/44CR",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "48/60CR",
        "alias_text": "48/60",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "48/60CR",
        "alias_text": "48/60CR",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "51/60",
        "alias_text": "51/60",
        "alias_type": "common_name",
    },
    # Pielstick aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "SEMT Pielstick",
        "alias_text": "Pielstick",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "SEMT Pielstick",
        "alias_text": "SEMT",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "SEMT Pielstick",
        "alias_text": "MAN France",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "PC2.6B",
        "alias_text": "PC2.6",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "PC4.2B",
        "alias_text": "PC4.2",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "PC40",
        "alias_text": "PC40",
        "alias_type": "common_name",
    },
    # Caterpillar/MaK aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Caterpillar MaK",
        "alias_text": "Caterpillar",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Caterpillar MaK",
        "alias_text": "Cat",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Caterpillar MaK",
        "alias_text": "CAT",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Caterpillar MaK",
        "alias_text": "MaK",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "M32C",
        "alias_text": "M32C",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "M43C",
        "alias_text": "M43C",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "M46DF",
        "alias_text": "M46DF",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "M34DF",
        "alias_text": "M34DF",
        "alias_type": "common_name",
    },
    # Hyundai/HiMSEN aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "HD Hyundai HiMSEN",
        "alias_text": "Hyundai",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "HD Hyundai HiMSEN",
        "alias_text": "HD Hyundai",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "HD Hyundai HiMSEN",
        "alias_text": "HiMSEN",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "HD Hyundai HiMSEN",
        "alias_text": "Hyundai Engine",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H21/32",
        "alias_text": "H21",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H21/32",
        "alias_text": "H21-32",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H32/40",
        "alias_text": "H32",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H32/40",
        "alias_text": "H32-40",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H54DF",
        "alias_text": "H54DF",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "H54DF",
        "alias_text": "H54DFV",
        "alias_type": "common_name",
    },
    # Bergen aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Bergen Engines",
        "alias_text": "Bergen",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Bergen Engines",
        "alias_text": "Rolls-Royce Bergen",
        "alias_type": "former_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Bergen Engines",
        "alias_text": "Langley Bergen",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "C25:33",
        "alias_text": "C25",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "C25:33",
        "alias_text": "C25:33",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "C25:33",
        "alias_text": "C25-33",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B32:40",
        "alias_text": "B32",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B32:40",
        "alias_text": "B32:40",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B32:40",
        "alias_text": "B32-40",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B33:45",
        "alias_text": "B33",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B33:45",
        "alias_text": "B33:45",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B33:45",
        "alias_text": "B33-45",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B36:45",
        "alias_text": "B36",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B36:45",
        "alias_text": "B36:45",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "B36:45",
        "alias_text": "B36-45",
        "alias_type": "common_name",
    },
    # Daihatsu aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Daihatsu Diesel",
        "alias_text": "Daihatsu",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DE",
        "alias_text": "8DE-33",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DE",
        "alias_text": "DE33",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DK",
        "alias_text": "DK series",
        "alias_type": "common_name",
    },
    # Niigata aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Niigata Power Systems",
        "alias_text": "Niigata",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "28AHX-DF",
        "alias_text": "28AHXDF",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "engine_series",
        "series_name": "28AHX-DF",
        "alias_text": "AHX-DF",
        "alias_type": "abbreviation",
    },
    # ABC aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "ABC Engines",
        "alias_text": "ABC",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "ABC Engines",
        "alias_text": "Anglo Belgian Corporation",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DV36",
        "alias_text": "DV36",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DV36",
        "alias_text": "12DV36",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DV36",
        "alias_text": "16DV36",
        "alias_type": "common_name",
    },
    {
        "entity_type": "engine_series",
        "series_name": "DZC",
        "alias_text": "DZC",
        "alias_type": "common_name",
    },
    # =========================================================================
    # TIER-2 MANUFACTURER ALIASES
    # =========================================================================
    # Yanmar aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Yanmar",
        "alias_text": "Yanmar",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Yanmar",
        "alias_text": "Yanmar Marine",
        "alias_type": "common_name",
    },
    # Cummins aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Cummins Marine",
        "alias_text": "Cummins",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Cummins Marine",
        "alias_text": "Cummins Inc",
        "alias_type": "common_name",
    },
    # Rolls-Royce/MTU aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Rolls-Royce Power Systems",
        "alias_text": "MTU",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Rolls-Royce Power Systems",
        "alias_text": "MTU Engines",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Rolls-Royce Power Systems",
        "alias_text": "Rolls-Royce MTU",
        "alias_type": "common_name",
    },
    # Mitsubishi aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Mitsubishi Heavy Industries",
        "alias_text": "Mitsubishi",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Mitsubishi Heavy Industries",
        "alias_text": "MHI",
        "alias_type": "abbreviation",
    },
    # Weichai aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Weichai Power",
        "alias_text": "Weichai",
        "alias_type": "common_name",
    },
    # WinGD aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "WinGD",
        "alias_text": "WinGD",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "WinGD",
        "alias_text": "Winterthur Gas & Diesel",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "WinGD",
        "alias_text": "Sulzer",
        "alias_type": "former_name",
    },
    # =========================================================================
    # TIER-3 MANUFACTURER ALIASES
    # =========================================================================
    # CSSC aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "CSSC Marine Power",
        "alias_text": "CSSC",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "CSSC Marine Power",
        "alias_text": "CSSC Marine",
        "alias_type": "common_name",
    },
    # Doosan aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Doosan Infracore",
        "alias_text": "Doosan",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Doosan Infracore",
        "alias_text": "Doosan Engine",
        "alias_type": "common_name",
    },
    # Baudouin aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Baudouin",
        "alias_text": "Baudouin",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Baudouin",
        "alias_text": "Moteurs Baudouin",
        "alias_type": "common_name",
    },
    # Volvo Penta aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Volvo Penta",
        "alias_text": "Volvo Penta",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Volvo Penta",
        "alias_text": "Volvo Marine",
        "alias_type": "common_name",
    },
    # Scania aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "Scania Marine",
        "alias_text": "Scania",
        "alias_type": "abbreviation",
    },
    # John Deere aliases
    {
        "entity_type": "manufacturer",
        "entity_name": "John Deere Marine",
        "alias_text": "John Deere",
        "alias_type": "common_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "John Deere Marine",
        "alias_text": "Deere",
        "alias_type": "abbreviation",
    },
]


# =============================================================================
# APPLICATIONS
# =============================================================================

APPLICATIONS: list[dict[str, Any]] = [
    {
        "name": "Marine Propulsion",
        "code": "PROP",
        "category": "commercial",
        "power_min": 1000,
        "power_max": 40000,
    },
    {
        "name": "Marine Genset",
        "code": "GENSET",
        "category": "commercial",
        "power_min": 500,
        "power_max": 20000,
    },
    {
        "name": "Auxiliary Power",
        "code": "AUX",
        "category": "commercial",
        "power_min": 500,
        "power_max": 5000,
    },
    {
        "name": "FPSO Power",
        "code": "FPSO",
        "category": "offshore",
        "power_min": 5000,
        "power_max": 40000,
    },
    {
        "name": "Offshore Platform",
        "code": "PLATFORM",
        "category": "offshore",
        "power_min": 3000,
        "power_max": 30000,
    },
    {
        "name": "Drilling Rig",
        "code": "DRILL",
        "category": "offshore",
        "power_min": 2000,
        "power_max": 20000,
    },
    {
        "name": "OSV/PSV",
        "code": "OSV",
        "category": "offshore",
        "power_min": 2000,
        "power_max": 10000,
    },
    {
        "name": "Ferry",
        "code": "FERRY",
        "category": "commercial",
        "power_min": 2000,
        "power_max": 15000,
    },
    {
        "name": "Cargo Vessel",
        "code": "CARGO",
        "category": "commercial",
        "power_min": 3000,
        "power_max": 25000,
    },
    {
        "name": "Tanker",
        "code": "TANKER",
        "category": "commercial",
        "power_min": 5000,
        "power_max": 30000,
    },
]


# =============================================================================
# MARKET SEGMENTS
# =============================================================================

MARKET_SEGMENTS: list[dict[str, Any]] = [
    {
        "name": "Marine Transportation",
        "segment_type": MarketSegmentType.MARINE_TRANSPORTATION.value,
        "priority_score": 70,
        "growth_potential": "medium",
    },
    {
        "name": "Offshore Oil & Gas",
        "segment_type": MarketSegmentType.OFFSHORE_OIL_GAS.value,
        "priority_score": 90,
        "growth_potential": "high",
    },
    {
        "name": "FPSO / Offshore Production",
        "segment_type": MarketSegmentType.FPSO_OFFSHORE_PRODUCTION.value,
        "priority_score": 95,
        "growth_potential": "high",
    },
    {
        "name": "Marine Power Generation",
        "segment_type": MarketSegmentType.MARINE_POWER_GENERATION.value,
        "priority_score": 80,
        "growth_potential": "medium",
    },
    {
        "name": "Land Power Plant",
        "segment_type": MarketSegmentType.LAND_POWER_PLANT.value,
        "priority_score": 30,
        "growth_potential": "low",
    },
]


# =============================================================================
# ENGINE-APPLICATION MAPPINGS
# Maps engine models to suitable applications with suitability scores
# =============================================================================

ENGINE_APPLICATION_MAPPINGS: list[dict[str, Any]] = [
    # Wärtsilä 31DF - Versatile medium-speed engine
    {
        "engine_model": "Wärtsilä 31DF",
        "application_code": "GENSET",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Wärtsilä 31DF",
        "application_code": "PROP",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "Wärtsilä 31DF",
        "application_code": "FERRY",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Wärtsilä 31DF",
        "application_code": "CARGO",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Wärtsilä 46F - High-power offshore engine
    {
        "engine_model": "Wärtsilä 46F",
        "application_code": "FPSO",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Wärtsilä 46F",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "Wärtsilä 46F",
        "application_code": "DRILL",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Wärtsilä 46F",
        "application_code": "TANKER",
        "suitability": 0.80,
        "is_primary": False,
    },
    # MAN 32/44CR - Versatile medium-speed
    {
        "engine_model": "MAN 32/44CR",
        "application_code": "GENSET",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "MAN 32/44CR",
        "application_code": "PROP",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "MAN 32/44CR",
        "application_code": "OSV",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "MAN 32/44CR",
        "application_code": "CARGO",
        "suitability": 0.80,
        "is_primary": False,
    },
    # MAN 48/60CR - High-power offshore
    {
        "engine_model": "MAN 48/60CR",
        "application_code": "FPSO",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "MAN 48/60CR",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "MAN 48/60CR",
        "application_code": "DRILL",
        "suitability": 0.85,
        "is_primary": False,
    },
    # MAN 51/60 - Ultra high-power
    {
        "engine_model": "MAN 51/60",
        "application_code": "FPSO",
        "suitability": 0.98,
        "is_primary": True,
    },
    {
        "engine_model": "MAN 51/60",
        "application_code": "PLATFORM",
        "suitability": 0.95,
        "is_primary": False,
    },
    {
        "engine_model": "MAN 51/60",
        "application_code": "TANKER",
        "suitability": 0.85,
        "is_primary": False,
    },
    # Pielstick PC2.6B - Offshore genset
    {
        "engine_model": "PC2.6B",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "PC2.6B",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "PC2.6B",
        "application_code": "DRILL",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Pielstick PC4.2B - High-power offshore
    {
        "engine_model": "PC4.2B",
        "application_code": "PLATFORM",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "PC4.2B",
        "application_code": "FPSO",
        "suitability": 0.85,
        "is_primary": False,
    },
    # MaK M32C - Marine propulsion
    {
        "engine_model": "MaK M32C",
        "application_code": "PROP",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "MaK M32C",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "MaK M32C",
        "application_code": "FERRY",
        "suitability": 0.80,
        "is_primary": False,
    },
    # MaK M43C - Propulsion and offshore
    {
        "engine_model": "MaK M43C",
        "application_code": "PROP",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "MaK M43C",
        "application_code": "PLATFORM",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "MaK M43C",
        "application_code": "CARGO",
        "suitability": 0.80,
        "is_primary": False,
    },
    # MaK M46DF - Dual-fuel offshore
    {
        "engine_model": "MaK M46DF",
        "application_code": "FPSO",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "MaK M46DF",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "MaK M46DF",
        "application_code": "TANKER",
        "suitability": 0.85,
        "is_primary": False,
    },
    # MaK M34DF - Compact dual-fuel
    {
        "engine_model": "MaK M34DF",
        "application_code": "GENSET",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "MaK M34DF",
        "application_code": "PROP",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "MaK M34DF",
        "application_code": "FERRY",
        "suitability": 0.80,
        "is_primary": False,
    },
    # HiMSEN H21/32 - Compact auxiliary
    {
        "engine_model": "HiMSEN H21/32",
        "application_code": "AUX",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "HiMSEN H21/32",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    # HiMSEN H32/40 - Medium propulsion
    {
        "engine_model": "HiMSEN H32/40",
        "application_code": "GENSET",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "HiMSEN H32/40",
        "application_code": "PROP",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "HiMSEN H32/40",
        "application_code": "OSV",
        "suitability": 0.80,
        "is_primary": False,
    },
    # HiMSEN H54DF - High-power offshore
    {
        "engine_model": "HiMSEN H54DF",
        "application_code": "FPSO",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "HiMSEN H54DF",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "HiMSEN H54DF",
        "application_code": "DRILL",
        "suitability": 0.85,
        "is_primary": False,
    },
    # Bergen C25:33 - Compact gas/diesel
    {
        "engine_model": "Bergen C25:33",
        "application_code": "AUX",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "Bergen C25:33",
        "application_code": "DRILL",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Bergen C25:33",
        "application_code": "OSV",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Bergen B32:40 - OSV/PSV specialist
    {
        "engine_model": "Bergen B32:40",
        "application_code": "OSV",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Bergen B32:40",
        "application_code": "DRILL",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "Bergen B32:40",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    # Bergen B33:45 - Propulsion and offshore
    {
        "engine_model": "Bergen B33:45",
        "application_code": "PROP",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "Bergen B33:45",
        "application_code": "OSV",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Bergen B33:45",
        "application_code": "PLATFORM",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Bergen B36:45 - High-power offshore
    {
        "engine_model": "Bergen B36:45",
        "application_code": "FPSO",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Bergen B36:45",
        "application_code": "PLATFORM",
        "suitability": 0.90,
        "is_primary": False,
    },
    {
        "engine_model": "Bergen B36:45",
        "application_code": "DRILL",
        "suitability": 0.85,
        "is_primary": False,
    },
    # Daihatsu 8DE-33 - Cargo auxiliary
    {
        "engine_model": "Daihatsu 8DE-33",
        "application_code": "AUX",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "Daihatsu 8DE-33",
        "application_code": "CARGO",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Daihatsu 8DE-33",
        "application_code": "GENSET",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Daihatsu DK-28 - Compact auxiliary
    {
        "engine_model": "Daihatsu DK-28",
        "application_code": "AUX",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Daihatsu DK-28",
        "application_code": "FERRY",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Daihatsu DK-28",
        "application_code": "CARGO",
        "suitability": 0.80,
        "is_primary": False,
    },
    # Niigata 28AHX-DF - Dual-fuel OSV
    {
        "engine_model": "Niigata 28AHX-DF",
        "application_code": "OSV",
        "suitability": 0.95,
        "is_primary": True,
    },
    {
        "engine_model": "Niigata 28AHX-DF",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "Niigata 28AHX-DF",
        "application_code": "PROP",
        "suitability": 0.80,
        "is_primary": False,
    },
    # ABC 16DV36 - Medium propulsion
    {
        "engine_model": "ABC 16DV36",
        "application_code": "PROP",
        "suitability": 0.90,
        "is_primary": True,
    },
    {
        "engine_model": "ABC 16DV36",
        "application_code": "GENSET",
        "suitability": 0.85,
        "is_primary": False,
    },
    {
        "engine_model": "ABC 16DV36",
        "application_code": "CARGO",
        "suitability": 0.80,
        "is_primary": False,
    },
    # ABC DZC - Compact propulsion
    {
        "engine_model": "ABC DZC",
        "application_code": "PROP",
        "suitability": 0.85,
        "is_primary": True,
    },
    {
        "engine_model": "ABC DZC",
        "application_code": "GENSET",
        "suitability": 0.80,
        "is_primary": False,
    },
    {
        "engine_model": "ABC DZC",
        "application_code": "FERRY",
        "suitability": 0.75,
        "is_primary": False,
    },
]


# =============================================================================
# SEED FUNCTIONS
# =============================================================================


async def seed_manufacturers(
    db: Optional[KnowledgeBaseDatabase] = None,
) -> dict[str, str]:
    """
    Seed manufacturers into database.

    Returns:
        Dict mapping manufacturer name to ID
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    manufacturer_ids = {}

    manufacturers = [
        Manufacturer(
            id=str(uuid.uuid4()),
            name=m["name"],
            country=m["country"],
            tier=m["tier"],
            website=m.get("website"),
            description=m.get("description"),
            is_active=True,
        )
        for m in MANUFACTURERS
    ]

    count = await db.bulk_create_manufacturers(manufacturers)
    logger.info(f"Seeded {count} manufacturers")

    # Build ID mapping
    for m in manufacturers:
        manufacturer_ids[m.name] = m.id

    return manufacturer_ids


async def seed_engine_series(
    db: Optional[KnowledgeBaseDatabase] = None,
    manufacturer_ids: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Seed engine series into database.

    Returns:
        Dict mapping series name to ID
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    if manufacturer_ids is None:
        # Load manufacturers from DB
        manufacturers = await db.list_manufacturers()
        manufacturer_ids = {m.name: m.id for m in manufacturers}

    series_ids: dict[str, str] = {}
    series_list: list[EngineSeries] = []

    for s in ENGINE_SERIES:
        mfr_id = manufacturer_ids.get(s["manufacturer"])
        if not mfr_id:
            logger.warning(f"Manufacturer not found: {s['manufacturer']}")
            continue

        series = EngineSeries(
            id=str(uuid.uuid4()),
            manufacturer_id=mfr_id,
            brand=s["brand"],
            series_name=s["series_name"],
            is_current=s.get("is_current", True),
        )
        series_list.append(series)
        series_ids[s["series_name"]] = series.id

    count = await db.bulk_create_engine_series(series_list)
    logger.info(f"Seeded {count} engine series")

    return series_ids


async def seed_engine_models(
    db: Optional[KnowledgeBaseDatabase] = None,
    series_ids: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Seed engine models into database.

    Returns:
        Dict mapping model name to ID
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    if series_ids is None:
        # Load series from DB - need to build mapping from DB
        series_ids = {}
        manufacturers = await db.list_manufacturers()
        for mfr in manufacturers:
            series_list_db = await db.list_engine_series_by_manufacturer(mfr.id)
            for s in series_list_db:
                series_ids[s.series_name] = s.id

    model_ids: dict[str, str] = {}
    models: list[EngineModel] = []

    for m in ENGINE_MODELS:
        series_id = series_ids.get(m["series"])
        if not series_id:
            logger.warning(f"Series not found: {m['series']}")
            continue

        model = EngineModel(
            id=str(uuid.uuid4()),
            series_id=series_id,
            model_name=m["model_name"],
            rpm_min=m.get("rpm_min"),
            rpm_max=m.get("rpm_max"),
            power_min_kw=m.get("power_min_kw"),
            power_max_kw=m.get("power_max_kw"),
            fuel_types=json.dumps(m.get("fuel_types", [])),
            configuration=m.get("configuration"),
            emission_tier=m.get("emission_tier"),
            is_current_production=True,
            data_source="seed_data",
            data_confidence=0.95,
        )
        models.append(model)
        model_ids[m["model_name"]] = model.id

    count = await db.bulk_create_engine_models(models)
    logger.info(f"Seeded {count} engine models")

    return model_ids


async def seed_aliases(
    db: Optional[KnowledgeBaseDatabase] = None,
    manufacturer_ids: Optional[dict[str, str]] = None,
    series_ids: Optional[dict[str, str]] = None,
) -> int:
    """
    Seed aliases into database.

    Returns:
        Count of seeded aliases
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    if manufacturer_ids is None:
        manufacturers = await db.list_manufacturers()
        manufacturer_ids = {m.name: m.id for m in manufacturers}

    if series_ids is None:
        series_ids = {}
        for mfr in await db.list_manufacturers():
            for s in await db.list_engine_series_by_manufacturer(mfr.id):
                series_ids[s.series_name] = s.id

    aliases = []

    for a in ALIASES:
        entity_id = None

        if a["entity_type"] == "manufacturer":
            entity_name = a.get("entity_name")
            if entity_name:
                entity_id = manufacturer_ids.get(str(entity_name))
        elif a["entity_type"] == "engine_series":
            series_name = a.get("series_name")
            if series_name:
                entity_id = series_ids.get(str(series_name))

        if not entity_id:
            logger.warning(f"Entity not found for alias: {a['alias_text']}")
            continue

        alias = EntityAlias(
            id=str(uuid.uuid4()),
            entity_type=a["entity_type"],
            entity_id=entity_id,
            alias_text=a["alias_text"],
            alias_type=a.get("alias_type", "common_name"),
            normalized_text=a["alias_text"].lower().strip(),
            source="seed_data",
            confidence=1.0,
            is_active=True,
        )
        aliases.append(alias)

    count = await db.bulk_create_aliases(aliases)
    logger.info(f"Seeded {count} aliases")

    return count


async def seed_applications(db: Optional[KnowledgeBaseDatabase] = None) -> int:
    """Seed applications into database."""
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    count = 0
    for a in APPLICATIONS:
        app = Application(
            id=str(uuid.uuid4()),
            name=a["name"],
            code=a.get("code"),
            category=a.get("category"),
            typical_power_range_min_kw=a.get("power_min"),
            typical_power_range_max_kw=a.get("power_max"),
            is_active=True,
        )
        await db.create_application(app)
        count += 1

    logger.info(f"Seeded {count} applications")
    return count


async def seed_market_segments(db: Optional[KnowledgeBaseDatabase] = None) -> int:
    """Seed market segments into database."""
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    count = 0
    for s in MARKET_SEGMENTS:
        segment = MarketSegment(
            id=str(uuid.uuid4()),
            name=s["name"],
            segment_type=s["segment_type"],
            priority_score=s.get("priority_score", 50),
            growth_potential=s.get("growth_potential"),
            is_active=True,
        )
        await db.create_market_segment(segment)
        count += 1

    logger.info(f"Seeded {count} market segments")
    return count


async def seed_engine_application_mappings(
    db: Optional[KnowledgeBaseDatabase] = None,
    model_ids: Optional[dict[str, str]] = None,
) -> int:
    """
    Seed engine-application mappings into database.

    Args:
        db: Database instance
        model_ids: Dict mapping model_name to model_id

    Returns:
        Count of seeded mappings
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    # Build model_ids from DB if not provided
    if model_ids is None:
        models = await db.list_engine_models()
        model_ids = {m.model_name: m.id for m in models}

    # Build application code -> id mapping
    apps = await db.list_applications()
    app_ids = {a.code: a.id for a in apps}

    mappings = []

    for m in ENGINE_APPLICATION_MAPPINGS:
        model_id = model_ids.get(m["engine_model"])
        app_id = app_ids.get(m["application_code"])

        if not model_id:
            logger.warning(f"Engine model not found: {m['engine_model']}")
            continue

        if not app_id:
            logger.warning(f"Application not found: {m['application_code']}")
            continue

        mapping = EngineApplicationMap(
            id=str(uuid.uuid4()),
            engine_model_id=model_id,
            application_id=app_id,
            suitability_score=m.get("suitability", 0.5),
            is_primary_application=m.get("is_primary", False),
            notes=m.get("notes"),
        )
        mappings.append(mapping)

    count = await db.bulk_create_engine_application_map(mappings)
    logger.info(f"Seeded {count} engine-application mappings")

    return count


async def seed_knowledge_base(
    db: Optional[KnowledgeBaseDatabase] = None,
    include_phase2: bool = True,
) -> dict:
    """
    Seed all knowledge base data.

    Args:
        db: Database connection (optional, will create if not provided)
        include_phase2: If True, also seed Phase 2 rating-level data

    Returns:
        Summary of seeded data
    """
    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.info("Starting knowledge base seed...")

    # ==========================================================================
    # PHASE 1: Core reference data (manufacturers, series, models, aliases)
    # ==========================================================================
    manufacturer_ids = await seed_manufacturers(db)
    series_ids = await seed_engine_series(db, manufacturer_ids)
    model_ids = await seed_engine_models(db, series_ids)
    alias_count = await seed_aliases(db, manufacturer_ids, series_ids)
    app_count = await seed_applications(db)
    segment_count = await seed_market_segments(db)
    # Seed engine-application mappings (requires models and applications)
    mapping_count = await seed_engine_application_mappings(db, model_ids)

    summary = {
        "manufacturers": len(manufacturer_ids),
        "engine_series": len(series_ids),
        "engine_models": len(model_ids),
        "aliases": alias_count,
        "applications": app_count,
        "market_segments": segment_count,
        "engine_application_mappings": mapping_count,
    }

    # ==========================================================================
    # PHASE 2: Rating-level data (ratings, requirements, competitive maps)
    # ==========================================================================
    if include_phase2:
        logger.info("Starting Phase 2 seed (rating-level data)...")

        # Engine ratings (requires models)
        rating_ids = await seed_engine_ratings(db, model_ids)
        summary["engine_ratings"] = len(rating_ids)

        # Customer requirements
        req_ids = await seed_customer_requirements(db)
        summary["customer_requirements"] = len(req_ids)

        # Competitor maps (requires ratings)
        map_ids = await seed_competitor_maps(db)
        summary["competitor_maps"] = len(map_ids)

        # Competitor engagements
        engagement_ids = await seed_competitor_engagements(db)
        summary["competitor_engagements"] = len(engagement_ids)

    logger.info(f"Knowledge base seed complete: {summary}")
    return summary


# =============================================================================
# ROLLBACK / CLEAR FUNCTIONS
# =============================================================================


async def clear_knowledge_base(
    db: Optional[KnowledgeBaseDatabase] = None,
    include_phase2: bool = True,
) -> dict:
    """
    Clear all knowledge base data (for rollback or reset).

    WARNING: This is destructive and cannot be undone.

    Uses whitelist validation for table names to prevent SQL injection.

    Args:
        db: Database connection (optional, will create if not provided)
        include_phase2: If True, also clear Phase 2 rating-level data

    Returns:
        Summary of cleared data
    """
    from lead_to_cash.services.knowledge_base.database import ALLOWED_TABLES

    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    logger.warning("Clearing all knowledge base data...")

    # Clear in reverse order of foreign key dependencies
    # Note: Uses direct SQL as DataFlow doesn't have truncate
    # Table names are validated against ALLOWED_TABLES whitelist
    async with db._pool.acquire() as conn:
        # Get counts before clearing
        counts = {}

        # Phase 2 tables (must be cleared first due to FK dependencies)
        phase2_tables = [
            ("kb_product_fit_results", "product_fit_results"),  # FK to ratings & reqs
            ("kb_rating_competitor_map", "competitor_maps"),  # FK to ratings
            ("kb_competitor_engagements", "competitor_engagements"),
            ("kb_customer_requirements", "customer_requirements"),
            ("kb_engine_ratings", "engine_ratings"),  # FK to models
        ]

        # Phase 1 tables
        phase1_tables = [
            (
                "kb_engine_application_map",
                "engine_application_mappings",
            ),  # FK to models & apps
            ("kb_entity_aliases", "aliases"),
            ("kb_engine_models", "engine_models"),
            ("kb_engine_series", "engine_series"),
            ("kb_manufacturers", "manufacturers"),
            ("kb_applications", "applications"),
            ("kb_market_segments", "market_segments"),
        ]

        # Determine which tables to clear
        tables = phase1_tables
        if include_phase2:
            tables = phase2_tables + phase1_tables

        for table_name, key in tables:
            # Validate table name against whitelist
            if table_name not in ALLOWED_TABLES:
                raise ValueError(f"Invalid table name: {table_name}")
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {table_name}"
            )  # Safe: validated
            counts[key] = count

        # Clear tables (order matters for FK constraints)
        for table_name, _ in tables:
            # Validate table name against whitelist
            if table_name not in ALLOWED_TABLES:
                raise ValueError(f"Invalid table name: {table_name}")
            await conn.execute(f"DELETE FROM {table_name}")  # Safe: validated
            logger.info(f"Cleared table: {table_name}")

    logger.info(f"Knowledge base cleared: {counts}")
    return counts


async def get_seed_preview() -> dict:
    """
    Get a preview of what would be seeded (dry-run).

    Returns:
        Summary of data that would be seeded
    """
    return {
        "manufacturers": {
            "count": len(MANUFACTURERS),
            "items": [m["name"] for m in MANUFACTURERS],
        },
        "engine_series": {
            "count": len(ENGINE_SERIES),
            "items": [f"{s['brand']} {s['series_name']}" for s in ENGINE_SERIES],
        },
        "engine_models": {
            "count": len(ENGINE_MODELS),
            "items": [m["model_name"] for m in ENGINE_MODELS],
        },
        "aliases": {
            "count": len(ALIASES),
            "manufacturers": len(
                [a for a in ALIASES if a["entity_type"] == "manufacturer"]
            ),
            "engine_series": len(
                [a for a in ALIASES if a["entity_type"] == "engine_series"]
            ),
        },
        "applications": {
            "count": len(APPLICATIONS),
            "items": [a["name"] for a in APPLICATIONS],
        },
        "market_segments": {
            "count": len(MARKET_SEGMENTS),
            "items": [s["name"] for s in MARKET_SEGMENTS],
        },
        "engine_application_mappings": {
            "count": len(ENGINE_APPLICATION_MAPPINGS),
            "engines_covered": len(
                set(m["engine_model"] for m in ENGINE_APPLICATION_MAPPINGS)
            ),
        },
    }


async def seed_knowledge_base_with_rollback(
    db: Optional[KnowledgeBaseDatabase] = None,
    dry_run: bool = False,
    clear_first: bool = False,
) -> dict:
    """
    Seed knowledge base with rollback on failure.

    Args:
        db: Database instance
        dry_run: If True, only preview what would be seeded
        clear_first: If True, clear existing data before seeding

    Returns:
        Summary of seeded data (or preview in dry-run mode)

    Raises:
        Exception: Re-raises after rollback on failure
    """
    if dry_run:
        logger.info("DRY RUN: Previewing seed data...")
        return await get_seed_preview()

    if db is None:
        db = get_knowledge_base_db()
        await db.initialize()

    if clear_first:
        await clear_knowledge_base(db)

    try:
        summary = await seed_knowledge_base(db)
        return summary

    except Exception as e:
        logger.error(f"Seed failed: {e}. Rolling back...")
        try:
            await clear_knowledge_base(db)
            logger.info("Rollback complete - database cleared")
        except Exception as rollback_error:
            logger.error(f"Rollback also failed: {rollback_error}")
        raise


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    async def main():
        """Run seed as CLI command with options."""
        from dotenv import load_dotenv

        load_dotenv()

        parser = argparse.ArgumentParser(
            description="Seed Marine Engine Knowledge Base",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Preview what would be seeded (dry run)
  python -m lead_to_cash.services.knowledge_base.seed_data --dry-run

  # Seed the database
  python -m lead_to_cash.services.knowledge_base.seed_data

  # Clear and re-seed (fresh start)
  python -m lead_to_cash.services.knowledge_base.seed_data --clear-first

  # Clear database only (no seeding)
  python -m lead_to_cash.services.knowledge_base.seed_data --clear-only
            """,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be seeded without making changes",
        )
        parser.add_argument(
            "--clear-first",
            action="store_true",
            help="Clear existing data before seeding",
        )
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Only clear the database (no seeding)",
        )
        parser.add_argument(
            "--verbose", "-v", action="store_true", help="Enable verbose logging"
        )

        args = parser.parse_args()

        # Setup logging
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        try:
            if args.clear_only:
                print("\n" + "=" * 60)
                print("CLEARING KNOWLEDGE BASE")
                print("=" * 60)
                confirm = input("This will DELETE all KB data. Type 'yes' to confirm: ")
                if confirm.lower() != "yes":
                    print("Aborted.")
                    sys.exit(0)
                summary = await clear_knowledge_base()
                print(f"\nCleared knowledge base:\n{json.dumps(summary, indent=2)}")

            elif args.dry_run:
                print("\n" + "=" * 60)
                print("DRY RUN - SEED PREVIEW")
                print("=" * 60)
                preview = await get_seed_preview()
                print("\nManufacturers to seed:")
                for name in preview["manufacturers"]["items"]:
                    print(f"  - {name}")
                print(f"\nEngine Series: {preview['engine_series']['count']} items")
                print(f"Engine Models: {preview['engine_models']['count']} items")
                print(f"Aliases: {preview['aliases']['count']} items")
                print(f"Applications: {preview['applications']['count']} items")
                print(f"Market Segments: {preview['market_segments']['count']} items")
                print(
                    "\nTotal items that would be seeded:",
                    sum(
                        [
                            preview["manufacturers"]["count"],
                            preview["engine_series"]["count"],
                            preview["engine_models"]["count"],
                            preview["aliases"]["count"],
                            preview["applications"]["count"],
                            preview["market_segments"]["count"],
                        ]
                    ),
                )

            else:
                print("\n" + "=" * 60)
                print("SEEDING KNOWLEDGE BASE")
                print("=" * 60)
                if args.clear_first:
                    print("Note: Will clear existing data before seeding")
                summary = await seed_knowledge_base_with_rollback(
                    dry_run=False,
                    clear_first=args.clear_first,
                )
                print(f"\nSeeded knowledge base:\n{json.dumps(summary, indent=2)}")
                print("\nSeed complete!")

        except Exception as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(main())
