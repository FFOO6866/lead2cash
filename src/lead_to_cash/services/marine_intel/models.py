"""
Marine Sales Intelligence Data Models

Models for tracking marine industry sales opportunities identified through
daily research of trade publications, regulatory bodies, and shipyard announcements.

Tables:
- Article: Source documents with URL hash deduplication
- Opportunity: Sales signals extracted from articles
- Account: Company tracking with mention counts across articles
- ResearchJob: Processing job tracking

Target Market: Singapore and Asia-Pacific
Priority Sectors: Marine transportation, Offshore oil & gas, Marine engineering
"""

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SalesSignal(str, Enum):
    """Sales signal tags indicating opportunity type."""

    NEWBUILD = "newbuild"
    RETROFIT_REPOWER = "retrofit_repower"
    OFFSHORE_PROJECT = "offshore_project"
    REGULATION = "regulation"
    FUEL_TRANSITION = "fuel_transition"
    FLEET_EXPANSION = "fleet_expansion"
    INCIDENT_RELIABILITY = "incident_reliability"
    FINANCING_CAPEX = "financing_capex"


class Region(str, Enum):
    """Priority regions for monitoring."""

    SINGAPORE = "singapore"
    INDONESIA = "indonesia"
    MALAYSIA = "malaysia"
    THAILAND = "thailand"
    VIETNAM = "vietnam"
    PHILIPPINES = "philippines"
    AUSTRALIA = "australia"
    CHINA = "china"
    KOREA = "korea"
    JAPAN = "japan"
    INDIA = "india"
    APAC_OTHER = "apac_other"


class VesselType(str, Enum):
    """Vessel types relevant for RRPS engines."""

    FERRY = "ferry"
    TUG = "tug"
    OSV = "osv"  # Offshore Support Vessel
    PSV = "psv"  # Platform Supply Vessel
    AHTS = "ahts"  # Anchor Handling Tug Supply
    FPSO = "fpso"  # Floating Production Storage Offloading
    HARBOUR_CRAFT = "harbour_craft"
    CARGO = "cargo"
    TANKER = "tanker"
    CONTAINER = "container"
    CRUISE = "cruise"
    YACHT = "yacht"
    NAVAL = "naval"
    FISHING = "fishing"
    DREDGER = "dredger"
    CONSTRUCTION = "construction"  # Offshore construction vessels
    OTHER = "other"


class Sector(str, Enum):
    """Industry sectors to monitor."""

    MARINE_TRANSPORTATION = "marine_transportation"
    OFFSHORE_OIL_GAS = "offshore_oil_gas"
    MARINE_ENGINEERING = "marine_engineering"
    PORT_TERMINAL = "port_terminal"
    SHIPPING = "shipping"
    NAVAL_DEFENSE = "naval_defense"


class SourceCategory(str, Enum):
    """Categories of news sources."""

    REGULATORY = "regulatory"  # MPA, IMO
    INDUSTRY_ASSOCIATION = "industry_association"  # SMF, ASMI, SSA
    TRADE_MEDIA = "trade_media"  # Maritime Executive, Seatrade
    SHIPYARD = "shipyard"  # Seatrium, PaxOcean
    SGX_ANNOUNCEMENT = "sgx_announcement"  # Stock exchange filings
    COMPANY_NEWS = "company_news"
    PERPLEXITY = "perplexity"


@dataclass
class MarineOpportunity:
    """
    A marine sales opportunity identified through research.

    Represents a potential sales lead discovered from trade media,
    regulatory announcements, or shipyard news.
    """

    id: str
    headline: str
    source_name: str
    source_url: str
    url_hash: str  # SHA256 hash for deduplication

    # Classification
    sales_signals: list[str]  # List of SalesSignal values
    region: str
    vessel_types: list[str]  # List of VesselType values
    sector: str

    # Companies and context
    companies_involved: list[str]
    country: str

    # Analysis
    sales_explanation: str  # Why this matters for engine sales
    suggested_action: str  # Recommended sales action

    # Metadata
    source_category: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_date: Optional[datetime] = None
    raw_content: str = ""

    # Optional enrichment
    estimated_value: Optional[float] = None
    currency: str = "USD"
    engine_power_range: Optional[str] = None  # e.g., "2000-4000 kW"
    contact_info: Optional[str] = None

    # Processing status
    reviewed: bool = False
    exported_to_crm: bool = False
    priority: int = 5  # 1-10, 10 being highest

    # KB enrichment (populated by KBIntegrationService)
    kb_entities: Optional[list[dict]] = None  # Resolved KB entities
    kb_classification: Optional[dict] = None  # Technical/market classification
    kb_score: Optional[dict] = None  # KB relevance score breakdown

    # A2A enrichment (populated by CompetitorIntelAgent via request_enrichment)
    competitor_intel: Optional[dict] = (
        None  # Competitor analysis for companies involved
    )

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """Generate SHA256 hash of URL for deduplication."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "headline": self.headline,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "url_hash": self.url_hash,
            "sales_signals": self.sales_signals,
            "region": self.region,
            "vessel_types": self.vessel_types,
            "sector": self.sector,
            "companies_involved": self.companies_involved,
            "country": self.country,
            "sales_explanation": self.sales_explanation,
            "suggested_action": self.suggested_action,
            "source_category": self.source_category,
            "discovered_at": self.discovered_at.isoformat(),
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
            "raw_content": self.raw_content,
            "estimated_value": self.estimated_value,
            "currency": self.currency,
            "engine_power_range": self.engine_power_range,
            "contact_info": self.contact_info,
            "reviewed": self.reviewed,
            "exported_to_crm": self.exported_to_crm,
            "priority": self.priority,
            "kb_entities": self.kb_entities,
            "kb_classification": self.kb_classification,
            "kb_score": self.kb_score,
            "competitor_intel": self.competitor_intel,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MarineOpportunity":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            headline=data["headline"],
            source_name=data["source_name"],
            source_url=data["source_url"],
            url_hash=data.get("url_hash", cls.generate_url_hash(data["source_url"])),
            sales_signals=data.get("sales_signals", []),
            region=data.get("region", Region.APAC_OTHER.value),
            vessel_types=data.get("vessel_types", []),
            sector=data.get("sector", Sector.MARINE_TRANSPORTATION.value),
            companies_involved=data.get("companies_involved", []),
            country=data.get("country", ""),
            sales_explanation=data.get("sales_explanation", ""),
            suggested_action=data.get("suggested_action", ""),
            source_category=data.get(
                "source_category", SourceCategory.PERPLEXITY.value
            ),
            discovered_at=(
                datetime.fromisoformat(data["discovered_at"])
                if data.get("discovered_at")
                else datetime.now(timezone.utc)
            ),
            published_date=(
                datetime.fromisoformat(data["published_date"])
                if data.get("published_date")
                else None
            ),
            raw_content=data.get("raw_content", ""),
            estimated_value=data.get("estimated_value"),
            currency=data.get("currency", "USD"),
            engine_power_range=data.get("engine_power_range"),
            contact_info=data.get("contact_info"),
            reviewed=data.get("reviewed", False),
            exported_to_crm=data.get("exported_to_crm", False),
            priority=data.get("priority", 5),
            kb_entities=data.get("kb_entities"),
            kb_classification=data.get("kb_classification"),
            kb_score=data.get("kb_score"),
        )


@dataclass
class ResearchJob:
    """Track daily research job status."""

    id: str
    job_type: str  # "daily_research", "manual", "weekly_deep"
    status: str  # "pending", "running", "completed", "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    queries_executed: int = 0
    articles_processed: int = 0  # Number of articles/sources processed
    opportunities_found: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "queries_executed": self.queries_executed,
            "articles_processed": self.articles_processed,
            "opportunities_found": self.opportunities_found,
            "duplicates_skipped": self.duplicates_skipped,
            "errors": self.errors,
            "error_message": self.error_message,
        }


# =============================================================================
# NEW MODELS: Article and Account (per user requirements)
# =============================================================================


@dataclass
class Article:
    """
    A news article or source document from marine industry sources.

    Used for deduplication (by URL hash) and tracking which sources
    generated which opportunities. One article can generate multiple
    opportunities and mention multiple companies.

    Includes:
    - Embedding vector (1536-dim) for semantic search via pgvector
    - Retention tier for tiered data lifecycle management
    """

    id: str
    url: str
    url_hash: str  # SHA-256 hash of URL for deduplication
    title: str
    source: str  # Publication name (TradeWinds, Lloyd's List, etc.)

    # Content
    content: Optional[str] = None
    summary: Optional[str] = None

    # Dates
    published_date: Optional[datetime] = None
    processed_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Processing status
    is_processed: bool = False
    opportunities_generated: int = 0

    # Metadata
    source_category: str = "trade_media"  # SourceCategory value
    metadata: dict = field(default_factory=dict)

    # Embedding for semantic search (1536-dim vector from text-embedding-3-small)
    embedding: Optional[list[float]] = None

    # Data retention tier: hot (0-12 months), warm (12-24 months), cold (24-36 months)
    retention_tier: str = "hot"

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """Generate SHA-256 hash of URL for deduplication."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        url: str,
        title: str,
        source: str,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        published_date: Optional[datetime] = None,
        source_category: str = "trade_media",
        metadata: Optional[dict] = None,
    ) -> "Article":
        """Factory method to create an Article with auto-generated ID and hash."""
        return cls(
            id=str(uuid.uuid4()),
            url=url,
            url_hash=cls.generate_url_hash(url),
            title=title,
            source=source,
            content=content,
            summary=summary,
            published_date=published_date,
            source_category=source_category,
            metadata=metadata or {},
        )

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """
        Convert Article to dictionary.

        Args:
            include_embedding: If True, include the embedding vector (large).
                             Defaults to False to reduce response size.
        """
        result: dict[str, Any] = {
            "id": self.id,
            "url": self.url,
            "url_hash": self.url_hash,
            "title": self.title,
            "source": self.source,
            "content": self.content,
            "summary": self.summary,
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
            "processed_date": self.processed_date.isoformat(),
            "is_processed": self.is_processed,
            "opportunities_generated": self.opportunities_generated,
            "source_category": self.source_category,
            "metadata": self.metadata,
            "has_embedding": self.embedding is not None,
            "retention_tier": self.retention_tier,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_embedding and self.embedding:
            result["embedding"] = self.embedding
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            url=data["url"],
            url_hash=data.get("url_hash") or cls.generate_url_hash(data["url"]),
            title=data["title"],
            source=data["source"],
            content=data.get("content"),
            summary=data.get("summary"),
            published_date=(
                datetime.fromisoformat(data["published_date"])
                if data.get("published_date")
                else None
            ),
            processed_date=(
                datetime.fromisoformat(data["processed_date"])
                if data.get("processed_date")
                else datetime.now(timezone.utc)
            ),
            is_processed=data.get("is_processed", False),
            opportunities_generated=data.get("opportunities_generated", 0),
            source_category=data.get("source_category", "trade_media"),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            retention_tier=data.get("retention_tier", "hot"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.now(timezone.utc)
            ),
        )


@dataclass
class Account:
    """
    A company/account tracked across multiple articles and opportunities.

    Aggregates mentions and opportunities by company for account-based
    selling. Uses normalized company name for matching.
    """

    id: str
    company_name: str
    normalized_name: str  # Lowercase, cleaned company name for matching

    # Company info
    country: Optional[str] = None
    sector: Optional[str] = None  # Primary sector
    website: Optional[str] = None

    # Tracking counts
    mention_count: int = 0
    opportunity_count: int = 0

    # Date tracking
    first_seen_date: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_seen_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Scoring
    total_score: float = 0.0  # Sum of opportunity scores
    priority_rank: Optional[int] = None  # Calculated ranking

    # CRM integration
    crm_account_id: Optional[str] = None  # SAP CRM / MS5 ID
    is_existing_customer: bool = False

    # Aliases and metadata
    aliases: list[str] = field(default_factory=list)  # Alternative company names
    metadata: dict = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def normalize_company_name(name: str) -> str:
        """
        Normalize company name for matching.

        Removes common suffixes (Pte Ltd, Inc, Corp, etc.) and cleans whitespace.
        """
        normalized = name.lower().strip()
        # Remove common corporate suffixes
        suffixes = [
            r"\s+(pte\.?\s*ltd\.?|ltd\.?|inc\.?|corp\.?|co\.?|llc|plc|gmbh|bv|sa|srl|ag)\.?$",
            r"\s+(private|limited|corporation|company|incorporated)\.?$",
            r"\s+\(.*?\)$",  # Remove parenthetical content
        ]
        for suffix in suffixes:
            normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)
        # Clean multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @classmethod
    def create(
        cls,
        company_name: str,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        **kwargs,
    ) -> "Account":
        """Factory method to create an Account with auto-generated ID and normalized name."""
        return cls(
            id=str(uuid.uuid4()),
            company_name=company_name,
            normalized_name=cls.normalize_company_name(company_name),
            country=country,
            sector=sector,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "company_name": self.company_name,
            "normalized_name": self.normalized_name,
            "country": self.country,
            "sector": self.sector,
            "website": self.website,
            "mention_count": self.mention_count,
            "opportunity_count": self.opportunity_count,
            "first_seen_date": self.first_seen_date.isoformat(),
            "last_seen_date": self.last_seen_date.isoformat(),
            "total_score": self.total_score,
            "priority_rank": self.priority_rank,
            "crm_account_id": self.crm_account_id,
            "is_existing_customer": self.is_existing_customer,
            "aliases": self.aliases,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            company_name=data["company_name"],
            normalized_name=data.get("normalized_name")
            or cls.normalize_company_name(data["company_name"]),
            country=data.get("country"),
            sector=data.get("sector"),
            website=data.get("website"),
            mention_count=data.get("mention_count", 0),
            opportunity_count=data.get("opportunity_count", 0),
            first_seen_date=(
                datetime.fromisoformat(data["first_seen_date"])
                if data.get("first_seen_date")
                else datetime.now(timezone.utc)
            ),
            last_seen_date=(
                datetime.fromisoformat(data["last_seen_date"])
                if data.get("last_seen_date")
                else datetime.now(timezone.utc)
            ),
            total_score=data.get("total_score", 0.0),
            priority_rank=data.get("priority_rank"),
            crm_account_id=data.get("crm_account_id"),
            is_existing_customer=data.get("is_existing_customer", False),
            aliases=data.get("aliases", []),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.now(timezone.utc)
            ),
        )


@dataclass
class ArticleAccountMention:
    """
    Junction table for tracking company mentions in articles.

    Links articles to accounts with context about the mention.
    """

    article_id: str
    account_id: str
    mention_context: Optional[str] = None  # Excerpt where company was mentioned
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "account_id": self.account_id,
            "mention_context": self.mention_context,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Query Patterns for Research
# =============================================================================

QUERY_PATTERNS = {
    "newbuild": [
        "contract awarded + vessel + shipyard + Singapore",
        "newbuild + ferry OR OSV OR tug + Asia",
        "vessel order + shipyard + Indonesia OR Malaysia OR Thailand OR Vietnam",
        "new ship construction + Asia Pacific + 2024 OR 2025",
        "shipbuilding contract + marine engines + APAC",
    ],
    "repower_retrofit": [
        "repower OR repowering + vessel + Singapore",
        "retrofit + dual fuel OR LNG OR methanol + ship",
        "engine replacement + ferry OR tug + Asia",
        "main engine upgrade + vessel + Southeast Asia",
        "propulsion retrofit + marine + APAC",
    ],
    "offshore_project": [
        "FID OR final investment decision + offshore + Indonesia OR Malaysia",
        "EPCIC contract + FPSO + Asia",
        "offshore project sanction + oil gas + Asia Pacific",
        "offshore vessel demand + Southeast Asia",
        "OSV contract + offshore + Singapore OR Malaysia",
    ],
    "fuel_transition": [
        "dual fuel engine + vessel order + Asia",
        "methanol-ready engine + marine + order",
        "ammonia marine engine + newbuild",
        "LNG bunkering + vessel + Singapore OR Malaysia",
        "alternative fuel + ship + Asia Pacific",
    ],
    "incidents": [
        "engine failure + ferry + Singapore OR Indonesia",
        "vessel breakdown + marine engine + Asia",
        "grounding OR collision + investigation + ship + APAC",
        "mechanical failure + offshore vessel + Southeast Asia",
    ],
    "regulations": [
        "IMO emissions + regulation + Asia Pacific",
        "MPA Singapore + environmental + vessel requirement",
        "decarbonization + shipping + Southeast Asia mandate",
        "CII rating + vessel + compliance + Asia",
    ],
    "fleet_expansion": [
        "fleet expansion + ferry operator + Asia",
        "new vessel acquisition + shipping company + Singapore",
        "fleet renewal + offshore + Malaysia OR Indonesia",
        "port development + vessel requirement + Asia Pacific",
    ],
}

# =============================================================================
# Mandatory Sources to Monitor
# =============================================================================

MANDATORY_SOURCES = {
    "singapore_regulatory": [
        {
            "name": "MPA Singapore",
            "url": "https://www.mpa.gov.sg/",
            "category": "regulatory",
        },
        {
            "name": "SMF (Singapore Maritime Foundation)",
            "url": "https://www.smf.com.sg/",
            "category": "industry_association",
        },
        {
            "name": "ASMI",
            "url": "https://www.asmi.com/",
            "category": "industry_association",
        },
        {
            "name": "SSA (Singapore Shipping Association)",
            "url": "https://www.ssa.org.sg/",
            "category": "industry_association",
        },
        {
            "name": "SMI",
            "url": "https://www.smi.com.sg/",
            "category": "industry_association",
        },
        {
            "name": "SGX Announcements",
            "url": "https://www.sgx.com/securities/company-announcements",
            "category": "sgx_announcement",
        },
    ],
    "trade_media": [
        {
            "name": "Maritime Executive",
            "url": "https://maritime-executive.com/",
            "category": "trade_media",
        },
        {
            "name": "Seatrade Maritime",
            "url": "https://www.seatrade-maritime.com/",
            "category": "trade_media",
        },
        {
            "name": "Splash247",
            "url": "https://splash247.com/",
            "category": "trade_media",
        },
        {
            "name": "Offshore Engineer",
            "url": "https://www.oedigital.com/",
            "category": "trade_media",
        },
        {
            "name": "Asian Oil & Gas",
            "url": "https://www.asianoilandgas.com/",
            "category": "trade_media",
        },
        {
            "name": "Upstream Online",
            "url": "https://www.upstreamonline.com/",
            "category": "trade_media",
        },
        {
            "name": "TradeWinds",
            "url": "https://www.tradewindsnews.com/",
            "category": "trade_media",
        },
        {
            "name": "Lloyd's List",
            "url": "https://lloydslist.maritimeintelligence.informa.com/",
            "category": "trade_media",
        },
    ],
    "shipyards": [
        {
            "name": "Seatrium",
            "url": "https://www.seatrium.com/",
            "category": "shipyard",
        },
        {
            "name": "PaxOcean",
            "url": "https://www.paxocean.com/",
            "category": "shipyard",
        },
        {
            "name": "ASL Marine",
            "url": "https://www.asl.com.sg/",
            "category": "shipyard",
        },
        {
            "name": "Penguin Shipyard",
            "url": "https://www.penguinshipyard.com/",
            "category": "shipyard",
        },
    ],
}
