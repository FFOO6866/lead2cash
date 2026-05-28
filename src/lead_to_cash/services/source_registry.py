"""
Comprehensive Source Registry for Maritime Intelligence

54 legitimate sources organized by category:
- Regulatory & Environmental (8 sources)
- Singapore & Southeast Asia (10 sources)
- General Maritime News (8 sources)
- Offshore Oil & Gas (5 sources)
- Shipyards & Shipbuilding (6 sources)
- Engine Manufacturers (7 sources)
- Industry Associations (6 sources)
- Financial & Market Data (4 sources)

Usage:
    from lead_to_cash.services.source_registry import (
        get_all_sources,
        get_sources_by_category,
        get_priority_sources,
        REGULATORY_SOURCES,
        SINGAPORE_SEA_SOURCES,
    )

    # Get all sources
    all_sources = get_all_sources()

    # Get by category
    regulatory = get_sources_by_category("regulatory")

    # Get critical/high priority only
    priority = get_priority_sources(priority_levels=["critical", "high"])
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceCategory(Enum):
    """Source category classification."""

    REGULATORY = "regulatory"
    SINGAPORE_SEA = "singapore_sea"
    GENERAL_MARITIME = "general_maritime"
    OFFSHORE_OG = "offshore_og"
    SHIPYARDS = "shipyards"
    ENGINE_MANUFACTURERS = "engine_manufacturers"
    ASSOCIATIONS = "associations"
    FINANCIAL = "financial"


class SourcePriority(Enum):
    """Source priority levels."""

    CRITICAL = "critical"  # Must monitor daily
    HIGH = "high"  # Monitor 2-3x per week
    MEDIUM = "medium"  # Weekly monitoring
    LOW = "low"  # Monthly or ad-hoc


class SourceType(Enum):
    """Type of source for scraping strategy."""

    RSS = "rss"
    WEB_SCRAPE = "web_scrape"
    API = "api"
    PERPLEXITY = "perplexity"


class SourceTier(Enum):
    """Credibility tier."""

    TIER_1 = 1  # Official/regulatory - 100% trust
    TIER_2 = 2  # Premium trade media - 90% trust
    TIER_3 = 3  # Industry news - 80% trust
    TIER_4 = 4  # General news - 60% trust


@dataclass
class SourceDefinition:
    """Definition of a news/data source."""

    id: str
    name: str
    url: str
    category: SourceCategory
    priority: SourcePriority
    source_type: SourceType
    tier: SourceTier
    description: str
    rss_url: Optional[str] = None
    api_endpoint: Optional[str] = None
    scrape_selectors: Optional[dict] = None
    enabled: bool = True
    requires_auth: bool = False
    rate_limit_per_day: int = 100
    coverage: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "category": self.category.value,
            "priority": self.priority.value,
            "source_type": self.source_type.value,
            "tier": self.tier.value,
            "description": self.description,
            "rss_url": self.rss_url,
            "enabled": self.enabled,
            "coverage": self.coverage,
            "tags": self.tags,
        }


# =============================================================================
# REGULATORY & ENVIRONMENTAL SOURCES (8)
# =============================================================================

REGULATORY_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="imo",
        name="International Maritime Organization",
        url="https://www.imo.org/en/MediaCentre",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Global maritime regulations, MEPC, MARPOL, emissions standards",
        coverage=["global", "regulations", "MEPC", "MARPOL", "emissions"],
        tags=["regulatory", "imo", "mepc", "emissions"],
    ),
    SourceDefinition(
        id="mpa_singapore",
        name="MPA Singapore",
        url="https://www.mpa.gov.sg/media-centre",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore maritime authority, Green Ship Programme, port regulations",
        coverage=["singapore", "regulations", "green_ship", "bunkering"],
        tags=["regulatory", "singapore", "mpa"],
    ),
    SourceDefinition(
        id="dnv",
        name="DNV",
        url="https://www.dnv.com/news",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_1,
        description="Classification society, class rules, decarbonization standards",
        rss_url="https://www.dnv.com/news/rss.xml",
        coverage=["global", "classification", "decarbonization", "standards"],
        tags=["classification", "dnv", "standards"],
    ),
    SourceDefinition(
        id="lloyds_register",
        name="Lloyd's Register",
        url="https://www.lr.org/en/news",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Classification society, technical standards, fuel transition",
        coverage=["global", "classification", "technical", "fuel_transition"],
        tags=["classification", "lr", "standards"],
    ),
    SourceDefinition(
        id="bureau_veritas",
        name="Bureau Veritas Marine",
        url="https://marine-offshore.bureauveritas.com/newsroom",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Classification society, maritime regulations",
        coverage=["global", "classification", "regulations"],
        tags=["classification", "bv", "standards"],
    ),
    SourceDefinition(
        id="classnk",
        name="ClassNK",
        url="https://www.classnk.com/hp/en/info_service",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Japanese classification society, Asian maritime standards",
        coverage=["asia", "japan", "classification", "standards"],
        tags=["classification", "classnk", "japan"],
    ),
    SourceDefinition(
        id="eu_maritime",
        name="EU Maritime Transport",
        url="https://transport.ec.europa.eu/transport-modes/maritime_en",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="EU ETS, FuelEU Maritime, European regulations",
        coverage=["europe", "eu_ets", "fueleu", "regulations"],
        tags=["regulatory", "eu", "ets", "fueleu"],
    ),
    SourceDefinition(
        id="emsa",
        name="European Maritime Safety Agency",
        url="https://www.emsa.europa.eu/newsroom",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="EU maritime safety regulations",
        coverage=["europe", "safety", "regulations"],
        tags=["regulatory", "emsa", "safety"],
    ),
    SourceDefinition(
        id="abs_maritime",
        name="ABS Maritime",
        url="https://ww2.eagle.org/en/news.html",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="American Bureau of Shipping, classification society",
        coverage=["global", "classification", "standards", "offshore"],
        tags=["classification", "abs", "standards"],
    ),
    SourceDefinition(
        id="rina_class",
        name="RINA Classification",
        url="https://www.rina.org/en/news",
        category=SourceCategory.REGULATORY,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Italian classification society, China market presence",
        coverage=["global", "italy", "china", "classification"],
        tags=["classification", "rina", "china"],
    ),
]

# =============================================================================
# SINGAPORE & SOUTHEAST ASIA SOURCES (10)
# =============================================================================

SINGAPORE_SEA_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="smf",
        name="Singapore Maritime Foundation",
        url="https://www.smf.com.sg",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore maritime industry foundation, events, insights",
        coverage=["singapore", "industry", "events"],
        tags=["singapore", "smf", "industry"],
    ),
    SourceDefinition(
        id="asmi",
        name="Association of Singapore Marine Industries",
        url="https://www.asmi.com",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Singapore marine industries association",
        coverage=["singapore", "shipbuilding", "marine_services"],
        tags=["singapore", "asmi", "shipbuilding"],
    ),
    SourceDefinition(
        id="ssa",
        name="Singapore Shipping Association",
        url="https://www.ssa.org.sg",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Singapore ship owners and operators association",
        coverage=["singapore", "shipping", "operators"],
        tags=["singapore", "ssa", "shipping"],
    ),
    SourceDefinition(
        id="splash247",
        name="Splash247",
        url="https://splash247.com",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Asia-Pacific maritime news, Singapore focus",
        rss_url="https://splash247.com/feed/",
        coverage=["apac", "singapore", "shipping", "markets"],
        tags=["news", "apac", "splash247"],
    ),
    SourceDefinition(
        id="seatrade_maritime",
        name="Seatrade Maritime",
        url="https://www.seatrade-maritime.com",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Global and APAC maritime news coverage",
        rss_url="https://www.seatrade-maritime.com/rss.xml",
        coverage=["global", "apac", "shipping", "cruise"],
        tags=["news", "seatrade", "global"],
    ),
    SourceDefinition(
        id="marine_malaysia",
        name="Marine Department Malaysia",
        url="https://www.marine.gov.my",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Malaysia maritime authority",
        coverage=["malaysia", "regulations", "ports"],
        tags=["malaysia", "regulatory"],
    ),
    SourceDefinition(
        id="dgst_indonesia",
        name="Indonesia Directorate General of Sea Transportation",
        url="https://hubla.dephub.go.id",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Indonesia maritime authority",
        coverage=["indonesia", "regulations", "shipping"],
        tags=["indonesia", "regulatory"],
    ),
    SourceDefinition(
        id="vinamarine",
        name="Vietnam Maritime Administration",
        url="https://vinamarine.gov.vn",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Vietnam maritime authority",
        coverage=["vietnam", "regulations", "shipping"],
        tags=["vietnam", "regulatory"],
    ),
    SourceDefinition(
        id="psa_international",
        name="PSA International",
        url="https://www.globalpsa.com",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Port of Singapore operator, port news",
        coverage=["singapore", "ports", "logistics"],
        tags=["singapore", "psa", "ports"],
    ),
    SourceDefinition(
        id="jurong_port",
        name="Jurong Port",
        url="https://www.jp.com.sg",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Singapore bulk and general cargo port",
        coverage=["singapore", "ports", "bulk"],
        tags=["singapore", "jurong_port"],
    ),
    # Additional Singapore/SEA legitimate news sources
    SourceDefinition(
        id="straits_times_business",
        name="The Straits Times - Business",
        url="https://www.straitstimes.com/business",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_1,
        rss_url="https://www.straitstimes.com/news/business/rss.xml",
        description="Singapore's leading newspaper - business section",
        coverage=["singapore", "business", "trade", "shipping"],
        tags=["singapore", "straits_times", "news"],
    ),
    SourceDefinition(
        id="cna_business",
        name="Channel News Asia - Business",
        url="https://www.channelnewsasia.com/business",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_1,
        rss_url="https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
        description="Singapore news channel - business section",
        coverage=["singapore", "asia", "business", "trade"],
        tags=["singapore", "cna", "news"],
    ),
    SourceDefinition(
        id="business_times_sg",
        name="The Business Times Singapore",
        url="https://www.businesstimes.com.sg",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore financial and business news",
        coverage=["singapore", "business", "finance", "shipping"],
        tags=["singapore", "business_times", "finance"],
    ),
    SourceDefinition(
        id="gcmd_singapore",
        name="Global Centre for Maritime Decarbonisation",
        url="https://www.gcformd.org/news",
        category=SourceCategory.SINGAPORE_SEA,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore-based maritime decarbonisation centre",
        coverage=["singapore", "decarbonisation", "green_shipping"],
        tags=["singapore", "gcmd", "decarbonisation"],
    ),
    # Note: Seatrium is defined in SHIPYARD_SOURCES to avoid duplicate IDs
]

# =============================================================================
# GENERAL MARITIME NEWS (8)
# =============================================================================

GENERAL_MARITIME_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="maritime_executive",
        name="Maritime Executive",
        url="https://www.maritime-executive.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Comprehensive maritime news coverage",
        rss_url="https://www.maritime-executive.com/rss",
        coverage=["global", "shipping", "offshore", "ports"],
        tags=["news", "maritime_executive", "comprehensive"],
    ),
    SourceDefinition(
        id="gcaptain",
        name="gCaptain",
        url="https://gcaptain.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Maritime and offshore industry news",
        rss_url="https://gcaptain.com/feed/",
        coverage=["global", "shipping", "offshore", "accidents"],
        tags=["news", "gcaptain"],
    ),
    SourceDefinition(
        id="tradewinds",
        name="TradeWinds",
        url="https://www.tradewindsnews.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Shipping industry news and markets",
        coverage=["global", "shipping", "markets", "finance"],
        tags=["news", "tradewinds", "markets"],
        requires_auth=True,
    ),
    SourceDefinition(
        id="lloyds_list",
        name="Lloyd's List",
        url="https://lloydslist.maritimeintelligence.informa.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Premium shipping intelligence",
        coverage=["global", "shipping", "intelligence", "data"],
        tags=["news", "lloyds_list", "premium"],
        requires_auth=True,
    ),
    SourceDefinition(
        id="hellenic_shipping",
        name="Hellenic Shipping News",
        url="https://www.hellenicshippingnews.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_3,
        description="Free comprehensive shipping news",
        rss_url="https://www.hellenicshippingnews.com/feed/",
        coverage=["global", "shipping", "tankers", "bulk"],
        tags=["news", "hellenic", "free"],
    ),
    SourceDefinition(
        id="ship_bunker",
        name="Ship & Bunker",
        url="https://shipandbunker.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Bunker fuel and shipping news",
        rss_url="https://shipandbunker.com/rss",
        coverage=["global", "bunkering", "fuel", "prices"],
        tags=["news", "bunker", "fuel"],
    ),
    SourceDefinition(
        id="seanews_turkey",
        name="SeaNews Turkey",
        url="https://www.seanews.com.tr",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_3,
        description="Turkish and Mediterranean maritime news",
        coverage=["turkey", "mediterranean", "shipping"],
        tags=["news", "turkey", "mediterranean"],
    ),
    SourceDefinition(
        id="marine_link",
        name="Marine Link",
        url="https://www.marinelink.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_3,
        description="Maritime industry news and technology",
        rss_url="https://www.marinelink.com/rss/news.xml",
        coverage=["global", "technology", "shipbuilding"],
        tags=["news", "marine_link", "technology"],
    ),
    SourceDefinition(
        id="riviera_maritime",
        name="Riviera Maritime Media",
        url="https://www.rivieramm.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Maritime technology and operations news",
        coverage=["global", "technology", "operations", "offshore"],
        tags=["news", "riviera", "technology"],
    ),
    SourceDefinition(
        id="marine_insight",
        name="Marine Insight",
        url="https://www.marineinsight.com",
        category=SourceCategory.GENERAL_MARITIME,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_3,
        description="Maritime technical articles and guides",
        coverage=["global", "technical", "education", "guides"],
        tags=["news", "marine_insight", "technical"],
    ),
]

# =============================================================================
# OFFSHORE OIL & GAS (5)
# =============================================================================

OFFSHORE_OG_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="offshore_engineer",
        name="Offshore Engineer",
        url="https://www.oedigital.com",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Offshore oil & gas industry news",
        rss_url="https://www.oedigital.com/rss",
        coverage=["global", "offshore", "oil_gas", "subsea"],
        tags=["offshore", "oil_gas", "subsea"],
    ),
    SourceDefinition(
        id="upstream_online",
        name="Upstream Online",
        url="https://www.upstreamonline.com",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Oil & gas exploration and production news",
        coverage=["global", "exploration", "production", "fid"],
        tags=["upstream", "oil_gas", "exploration"],
        requires_auth=True,
    ),
    SourceDefinition(
        id="rigzone",
        name="Rigzone",
        url="https://www.rigzone.com",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Rig counts, drilling news, offshore jobs",
        rss_url="https://www.rigzone.com/news/rss/rigzone_latest.aspx",
        coverage=["global", "drilling", "rigs", "jobs"],
        tags=["rigzone", "drilling", "rigs"],
    ),
    SourceDefinition(
        id="offshore_magazine",
        name="Offshore Magazine",
        url="https://www.offshore-mag.com",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Offshore technology and projects",
        rss_url="https://www.offshore-mag.com/rss",
        coverage=["global", "technology", "projects", "fpso"],
        tags=["offshore", "technology", "fpso"],
    ),
    SourceDefinition(
        id="asian_oil_gas",
        name="Asian Oil & Gas",
        url="https://www.aaborneointernational.com",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Asia-Pacific oil & gas news",
        coverage=["apac", "oil_gas", "lng", "offshore"],
        tags=["asian", "oil_gas", "apac"],
    ),
    SourceDefinition(
        id="offshore_energy",
        name="Offshore Energy",
        url="https://www.offshore-energy.biz",
        category=SourceCategory.OFFSHORE_OG,
        priority=SourcePriority.HIGH,
        source_type=SourceType.RSS,
        tier=SourceTier.TIER_2,
        description="Offshore energy industry news",
        rss_url="https://www.offshore-energy.biz/feed/",
        coverage=["global", "offshore", "renewables", "oil_gas"],
        tags=["offshore", "energy", "renewables"],
    ),
]

# =============================================================================
# SHIPYARDS & SHIPBUILDING (6)
# =============================================================================

SHIPYARD_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="seatrium",
        name="Seatrium",
        url="https://www.seatrium.com/news",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore's largest shipyard (ex-Keppel O&M + Sembcorp Marine)",
        coverage=["singapore", "shipbuilding", "offshore", "repairs"],
        tags=["seatrium", "singapore", "shipyard"],
    ),
    SourceDefinition(
        id="keppel_corp",
        name="Keppel Corporation",
        url="https://www.kepcorp.com/en/news-centre",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Singapore conglomerate, offshore & marine",
        coverage=["singapore", "infrastructure", "offshore"],
        tags=["keppel", "singapore", "conglomerate"],
    ),
    SourceDefinition(
        id="hhi",
        name="Hyundai Heavy Industries",
        url="https://english.hhi.co.kr/news",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="World's largest shipyard, Korean orders",
        coverage=["korea", "shipbuilding", "lng_carriers", "tankers"],
        tags=["hhi", "korea", "shipyard"],
    ),
    SourceDefinition(
        id="samsung_heavy",
        name="Samsung Heavy Industries",
        url="https://www.samsungshi.com/eng/pr/news",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Korean shipyard, LNG carriers, drillships",
        coverage=["korea", "shipbuilding", "lng_carriers", "drillships"],
        tags=["shi", "korea", "shipyard"],
    ),
    SourceDefinition(
        id="cssc",
        name="China State Shipbuilding Corporation",
        url="https://www.cssc.net.cn/n3/n61/index.html",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="China's largest shipbuilding group",
        coverage=["china", "shipbuilding", "naval", "commercial"],
        tags=["cssc", "china", "shipyard"],
    ),
    SourceDefinition(
        id="fincantieri",
        name="Fincantieri",
        url="https://www.fincantieri.com/en/media/press-releases",
        category=SourceCategory.SHIPYARDS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Italian shipyard, cruise ships, naval",
        coverage=["italy", "cruise", "naval", "luxury"],
        tags=["fincantieri", "italy", "cruise"],
    ),
]

# =============================================================================
# ENGINE MANUFACTURERS - COMPETITORS (7)
# =============================================================================

ENGINE_MANUFACTURER_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="wartsila",
        name="Wärtsilä",
        url="https://www.wartsila.com/media/news",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Major competitor - marine engines, propulsion",
        coverage=["global", "engines", "propulsion", "contracts"],
        tags=["wartsila", "competitor", "engines"],
    ),
    SourceDefinition(
        id="man_es",
        name="MAN Energy Solutions",
        url="https://www.man-es.com/company/press",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Major competitor - two-stroke, four-stroke engines",
        coverage=["global", "engines", "two_stroke", "contracts"],
        tags=["man", "competitor", "engines"],
    ),
    SourceDefinition(
        id="caterpillar_marine",
        name="Caterpillar Marine",
        url="https://www.cat.com/en_US/news.html",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.CRITICAL,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Major competitor - marine diesel engines",
        coverage=["global", "engines", "diesel", "workboats"],
        tags=["caterpillar", "competitor", "engines"],
    ),
    SourceDefinition(
        id="rolls_royce_power",
        name="Rolls-Royce Power Systems",
        url="https://www.mtu-solutions.com/eu/en/news.html",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="MTU engines, power systems (own company)",
        coverage=["global", "mtu", "engines", "power_systems"],
        tags=["mtu", "rrps", "engines"],
    ),
    SourceDefinition(
        id="cummins_marine",
        name="Cummins Marine",
        url="https://www.cummins.com/news",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Competitor - marine diesel engines",
        coverage=["global", "engines", "diesel", "commercial"],
        tags=["cummins", "competitor", "engines"],
    ),
    SourceDefinition(
        id="volvo_penta",
        name="Volvo Penta",
        url="https://www.volvopenta.com/news",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Competitor - marine propulsion",
        coverage=["global", "engines", "propulsion", "leisure"],
        tags=["volvo_penta", "competitor", "engines"],
    ),
    SourceDefinition(
        id="yanmar_marine",
        name="Yanmar Marine",
        url="https://www.yanmar.com/global/news",
        category=SourceCategory.ENGINE_MANUFACTURERS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Competitor - marine diesel engines",
        coverage=["global", "japan", "engines", "fishing"],
        tags=["yanmar", "competitor", "engines"],
    ),
]

# =============================================================================
# INDUSTRY ASSOCIATIONS (6)
# =============================================================================

ASSOCIATION_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="smba_singapore",
        name="Singapore Maritime Business Association",
        url="https://www.smba.org.sg",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Singapore maritime business association",
        coverage=["singapore", "business", "maritime"],
        tags=["singapore", "smba", "association"],
    ),
    SourceDefinition(
        id="asa_asian_shipowners",
        name="Asian Shipowners' Association",
        url="https://www.asianshipowners.org",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Asian shipowners regional association",
        coverage=["asia", "shipowners", "regional"],
        tags=["asia", "asa", "shipowners"],
    ),
    SourceDefinition(
        id="bimco",
        name="BIMCO",
        url="https://www.bimco.org/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="International shipping association, contracts, standards",
        coverage=["global", "shipping", "contracts", "standards"],
        tags=["bimco", "association", "contracts"],
    ),
    SourceDefinition(
        id="ics",
        name="International Chamber of Shipping",
        url="https://www.ics-shipping.org/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="International shipping trade association",
        coverage=["global", "shipping", "policy", "regulations"],
        tags=["ics", "association", "policy"],
    ),
    SourceDefinition(
        id="clia",
        name="Cruise Lines International Association",
        url="https://cruising.org/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Cruise industry association",
        coverage=["global", "cruise", "tourism", "regulations"],
        tags=["clia", "cruise", "association"],
    ),
    SourceDefinition(
        id="iacs",
        name="International Association of Classification Societies",
        url="https://iacs.org.uk/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.HIGH,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_1,
        description="Umbrella for classification societies",
        coverage=["global", "classification", "standards", "safety"],
        tags=["iacs", "classification", "standards"],
    ),
    SourceDefinition(
        id="sea_europe",
        name="SEA Europe",
        url="https://www.seaeurope.eu/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="European shipbuilding association",
        coverage=["europe", "shipbuilding", "policy"],
        tags=["sea_europe", "shipbuilding", "europe"],
    ),
    SourceDefinition(
        id="interferry",
        name="Interferry",
        url="https://interferry.com/news",
        category=SourceCategory.ASSOCIATIONS,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="International ferry industry association",
        coverage=["global", "ferry", "passenger", "roro"],
        tags=["interferry", "ferry", "association"],
    ),
]

# =============================================================================
# FINANCIAL & MARKET DATA (4)
# =============================================================================

FINANCIAL_SOURCES: list[SourceDefinition] = [
    SourceDefinition(
        id="sgx",
        name="Singapore Exchange",
        url="https://www.sgx.com/securities/company-announcements",
        category=SourceCategory.FINANCIAL,
        priority=SourcePriority.HIGH,
        source_type=SourceType.API,
        tier=SourceTier.TIER_1,
        description="Singapore maritime company filings",
        coverage=["singapore", "financials", "filings", "announcements"],
        tags=["sgx", "financials", "filings"],
    ),
    SourceDefinition(
        id="clarksons",
        name="Clarksons Research",
        url="https://www.clarksons.com/research",
        category=SourceCategory.FINANCIAL,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.WEB_SCRAPE,
        tier=SourceTier.TIER_2,
        description="Shipping market research and indices",
        coverage=["global", "research", "indices", "valuations"],
        tags=["clarksons", "research", "data"],
        requires_auth=True,
    ),
    SourceDefinition(
        id="vesselsvalue",
        name="VesselsValue",
        url="https://www.vesselsvalue.com",
        category=SourceCategory.FINANCIAL,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.API,
        tier=SourceTier.TIER_2,
        description="Vessel valuations and market data",
        coverage=["global", "valuations", "fleet_data", "sales"],
        tags=["vesselsvalue", "valuations", "data"],
        requires_auth=True,
    ),
    SourceDefinition(
        id="eodhd",
        name="EODHD Financial API",
        url="https://eodhd.com",
        category=SourceCategory.FINANCIAL,
        priority=SourcePriority.MEDIUM,
        source_type=SourceType.API,
        tier=SourceTier.TIER_3,
        description="Financial data API for maritime stocks",
        api_endpoint="https://eodhd.com/api",
        coverage=["global", "stocks", "financials"],
        tags=["eodhd", "api", "financials"],
        requires_auth=True,
    ),
]


# =============================================================================
# ALL SOURCES COMBINED
# =============================================================================

ALL_SOURCES: list[SourceDefinition] = (
    REGULATORY_SOURCES
    + SINGAPORE_SEA_SOURCES
    + GENERAL_MARITIME_SOURCES
    + OFFSHORE_OG_SOURCES
    + SHIPYARD_SOURCES
    + ENGINE_MANUFACTURER_SOURCES
    + ASSOCIATION_SOURCES
    + FINANCIAL_SOURCES
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_all_sources() -> list[SourceDefinition]:
    """Get all registered sources."""
    return ALL_SOURCES


def get_sources_by_category(category: str) -> list[SourceDefinition]:
    """Get sources by category."""
    try:
        cat = SourceCategory(category)
    except ValueError:
        return []

    return [s for s in ALL_SOURCES if s.category == cat]


def get_sources_by_type(source_type: str) -> list[SourceDefinition]:
    """Get sources by type (rss, web_scrape, api, perplexity)."""
    try:
        st = SourceType(source_type)
    except ValueError:
        return []

    return [s for s in ALL_SOURCES if s.source_type == st]


def get_priority_sources(
    priority_levels: Optional[list[str]] = None,
) -> list[SourceDefinition]:
    """Get sources by priority level(s)."""
    if priority_levels is None:
        priority_levels = ["critical", "high"]

    priorities = []
    for level in priority_levels:
        try:
            priorities.append(SourcePriority(level))
        except ValueError:
            pass

    return [s for s in ALL_SOURCES if s.priority in priorities]


def get_enabled_sources() -> list[SourceDefinition]:
    """Get only enabled sources."""
    return [s for s in ALL_SOURCES if s.enabled]


def get_rss_sources() -> list[SourceDefinition]:
    """Get sources with RSS feeds."""
    return [s for s in ALL_SOURCES if s.rss_url is not None]


def get_source_by_id(source_id: str) -> Optional[SourceDefinition]:
    """Get a source by its ID."""
    for source in ALL_SOURCES:
        if source.id == source_id:
            return source
    return None


def get_source_stats() -> dict:
    """Get statistics about registered sources."""
    by_category: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}

    for source in ALL_SOURCES:
        # By category
        cat = source.category.value
        by_category[cat] = by_category.get(cat, 0) + 1

        # By priority
        pri = source.priority.value
        by_priority[pri] = by_priority.get(pri, 0) + 1

        # By type
        st = source.source_type.value
        by_type[st] = by_type.get(st, 0) + 1

        # By tier
        tier = f"tier_{source.tier.value}"
        by_tier[tier] = by_tier.get(tier, 0) + 1

    return {
        "total": len(ALL_SOURCES),
        "enabled": len(get_enabled_sources()),
        "with_rss": len(get_rss_sources()),
        "by_category": by_category,
        "by_priority": by_priority,
        "by_type": by_type,
        "by_tier": by_tier,
    }
