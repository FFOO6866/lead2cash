"""
Competitor Intelligence Signal Models

Pydantic models and dataclasses for competitor intelligence signals,
financial data, and structured extraction results.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CompetitorSignalType(str, Enum):
    """Signal types for competitor intelligence classification."""

    CONTRACT_WIN = "contract_win"  # +30 if involving engines
    CUSTOMER_ANNOUNCEMENT = "customer_announcement"  # Customer/vessel announcements
    PRODUCT_LAUNCH = "product_launch"  # +20 for new platform/fuel
    TECHNOLOGY_POV = "technology_pov"  # +15 for fuel transition content
    THOUGHT_LEADERSHIP = "thought_leadership"  # Strategy and vision content
    EVENT_MARKETING = "event_marketing"  # +10 if APAC/Singapore
    PARTNERSHIP = "partnership"  # Strategic partnerships
    REGULATORY_POSITIONING = "regulatory_positioning"  # Emissions, IMO compliance


class SourceChannel(str, Enum):
    """Content source channels for competitor intelligence."""

    WEBSITE_NEWSROOM = "website_newsroom"
    WEBSITE_PRODUCT = "website_product"
    WEBSITE_INSIGHTS = "website_insights"
    LINKEDIN = "linkedin"
    TWITTER_X = "twitter_x"
    YOUTUBE = "youtube"
    EODHD_FINANCIALS = "eodhd_financials"
    RSS_FEED = "rss_feed"
    PERPLEXITY = "perplexity"


class FuelType(str, Enum):
    """Fuel types for marine engines."""

    DIESEL = "diesel"
    LNG = "lng"
    DUAL_FUEL = "dual_fuel"
    METHANOL = "methanol"
    AMMONIA = "ammonia"
    HYDROGEN = "hydrogen"
    HYBRID = "hybrid"
    ELECTRIC = "electric"
    UNKNOWN = "unknown"


@dataclass
class CompetitorSignal:
    """
    A competitor intelligence signal extracted from content.

    Represents a single piece of competitor intelligence with
    scoring, entity extraction, and geographic relevance.
    """

    id: str
    competitor: str  # caterpillar, cummins, man_energy
    signal_type: str  # CompetitorSignalType value
    source_channel: str  # SourceChannel value

    # Content
    headline: str
    description: str
    raw_content: str = ""

    # Scoring
    score: int = 0  # 0-100
    score_breakdown: dict = field(default_factory=dict)

    # Extracted entities
    customer_mentioned: Optional[str] = None
    project_name: Optional[str] = None
    vessel_type: Optional[str] = None
    engine_model: Optional[str] = None
    fuel_type: Optional[str] = None  # dual fuel, methanol, ammonia, etc.
    contract_value_usd: Optional[float] = None

    # Geographic relevance
    region: Optional[str] = None
    country: Optional[str] = None
    is_apac: bool = False
    is_singapore: bool = False

    # Keywords detected
    keywords_matched: list[str] = field(default_factory=list)

    # Source tracking
    source_url: str = ""
    published_date: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        competitor: str,
        signal_type: str,
        source_channel: str,
        headline: str,
        description: str,
        **kwargs,
    ) -> "CompetitorSignal":
        """Factory method to create a new CompetitorSignal with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            competitor=competitor,
            signal_type=signal_type,
            source_channel=source_channel,
            headline=headline,
            description=description,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "competitor": self.competitor,
            "signal_type": self.signal_type,
            "source_channel": self.source_channel,
            "headline": self.headline,
            "description": self.description,
            "raw_content": self.raw_content,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "customer_mentioned": self.customer_mentioned,
            "project_name": self.project_name,
            "vessel_type": self.vessel_type,
            "engine_model": self.engine_model,
            "fuel_type": self.fuel_type,
            "contract_value_usd": self.contract_value_usd,
            "region": self.region,
            "country": self.country,
            "is_apac": self.is_apac,
            "is_singapore": self.is_singapore,
            "keywords_matched": self.keywords_matched,
            "source_url": self.source_url,
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
            "discovered_at": self.discovered_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompetitorSignal":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            competitor=data["competitor"],
            signal_type=data["signal_type"],
            source_channel=data["source_channel"],
            headline=data["headline"],
            description=data.get("description", ""),
            raw_content=data.get("raw_content", ""),
            score=data.get("score", 0),
            score_breakdown=data.get("score_breakdown", {}),
            customer_mentioned=data.get("customer_mentioned"),
            project_name=data.get("project_name"),
            vessel_type=data.get("vessel_type"),
            engine_model=data.get("engine_model"),
            fuel_type=data.get("fuel_type"),
            contract_value_usd=data.get("contract_value_usd"),
            region=data.get("region"),
            country=data.get("country"),
            is_apac=data.get("is_apac", False),
            is_singapore=data.get("is_singapore", False),
            keywords_matched=data.get("keywords_matched", []),
            source_url=data.get("source_url", ""),
            published_date=(
                datetime.fromisoformat(data["published_date"])
                if data.get("published_date")
                else None
            ),
            discovered_at=(
                datetime.fromisoformat(data["discovered_at"])
                if data.get("discovered_at")
                else datetime.now(timezone.utc)
            ),
            metadata=data.get("metadata", {}),
        )

    def is_high_impact(self) -> bool:
        """Check if this signal is high-impact (score >= 60)."""
        return self.score >= 60

    def to_jsonl_line(self) -> str:
        """Convert to JSONL line for file output."""
        import json

        return json.dumps(self.to_dict(), default=str)


@dataclass
class CompetitorFinancials:
    """
    Financial data from EODHD API for competitor tracking.

    Stores quarterly and annual financial metrics for CAT, CMI tickers.
    MAN Energy Solutions is part of VW group - limited data availability.
    """

    id: str
    competitor: str  # caterpillar, cummins, man_energy
    ticker: str  # CAT.US, CMI.US

    # Period
    period_type: str  # "quarterly", "annual"
    fiscal_period: str  # "Q1 2026", "FY 2025"
    report_date: datetime

    # Key metrics (USD)
    revenue_usd: Optional[float] = None
    operating_income_usd: Optional[float] = None
    net_income_usd: Optional[float] = None
    rd_spending_usd: Optional[float] = None
    capex_usd: Optional[float] = None
    order_backlog_usd: Optional[float] = None

    # Segment data (if available)
    marine_segment_revenue: Optional[float] = None
    energy_segment_revenue: Optional[float] = None
    power_systems_revenue: Optional[float] = None

    # Ratios
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    revenue_growth_yoy_pct: Optional[float] = None
    revenue_growth_qoq_pct: Optional[float] = None

    # Guidance
    guidance_notes: Optional[str] = None

    # Metadata
    source_url: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        competitor: str,
        ticker: str,
        period_type: str,
        fiscal_period: str,
        report_date: datetime,
        **kwargs,
    ) -> "CompetitorFinancials":
        """Factory method to create a new CompetitorFinancials with auto-generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            competitor=competitor,
            ticker=ticker,
            period_type=period_type,
            fiscal_period=fiscal_period,
            report_date=report_date,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "competitor": self.competitor,
            "ticker": self.ticker,
            "period_type": self.period_type,
            "fiscal_period": self.fiscal_period,
            "report_date": self.report_date.isoformat(),
            "revenue_usd": self.revenue_usd,
            "operating_income_usd": self.operating_income_usd,
            "net_income_usd": self.net_income_usd,
            "rd_spending_usd": self.rd_spending_usd,
            "capex_usd": self.capex_usd,
            "order_backlog_usd": self.order_backlog_usd,
            "marine_segment_revenue": self.marine_segment_revenue,
            "energy_segment_revenue": self.energy_segment_revenue,
            "power_systems_revenue": self.power_systems_revenue,
            "gross_margin_pct": self.gross_margin_pct,
            "operating_margin_pct": self.operating_margin_pct,
            "revenue_growth_yoy_pct": self.revenue_growth_yoy_pct,
            "revenue_growth_qoq_pct": self.revenue_growth_qoq_pct,
            "guidance_notes": self.guidance_notes,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat(),
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompetitorFinancials":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            competitor=data["competitor"],
            ticker=data["ticker"],
            period_type=data["period_type"],
            fiscal_period=data["fiscal_period"],
            report_date=datetime.fromisoformat(data["report_date"]),
            revenue_usd=data.get("revenue_usd"),
            operating_income_usd=data.get("operating_income_usd"),
            net_income_usd=data.get("net_income_usd"),
            rd_spending_usd=data.get("rd_spending_usd"),
            capex_usd=data.get("capex_usd"),
            order_backlog_usd=data.get("order_backlog_usd"),
            marine_segment_revenue=data.get("marine_segment_revenue"),
            energy_segment_revenue=data.get("energy_segment_revenue"),
            power_systems_revenue=data.get("power_systems_revenue"),
            gross_margin_pct=data.get("gross_margin_pct"),
            operating_margin_pct=data.get("operating_margin_pct"),
            revenue_growth_yoy_pct=data.get("revenue_growth_yoy_pct"),
            revenue_growth_qoq_pct=data.get("revenue_growth_qoq_pct"),
            guidance_notes=data.get("guidance_notes"),
            source_url=data.get("source_url", ""),
            fetched_at=(
                datetime.fromisoformat(data["fetched_at"])
                if data.get("fetched_at")
                else datetime.now(timezone.utc)
            ),
            raw_data=data.get("raw_data", {}),
        )


# Pydantic models for API responses and Kaizen agent signatures


class CompetitorSignalResponse(BaseModel):
    """Pydantic model for API response of a competitor signal."""

    id: str
    competitor: str
    signal_type: str
    source_channel: str
    headline: str
    description: str
    score: int = 0
    customer_mentioned: Optional[str] = None
    vessel_type: Optional[str] = None
    fuel_type: Optional[str] = None
    region: Optional[str] = None
    is_apac: bool = False
    is_singapore: bool = False
    source_url: str = ""
    published_date: Optional[str] = None
    discovered_at: str


class ExtractedSignalData(BaseModel):
    """Pydantic model for LLM-extracted signal data."""

    signal_type: str = Field(
        description="One of: CONTRACT_WIN, CUSTOMER_ANNOUNCEMENT, PRODUCT_LAUNCH, "
        "TECHNOLOGY_POV, THOUGHT_LEADERSHIP, EVENT_MARKETING, PARTNERSHIP, "
        "REGULATORY_POSITIONING"
    )
    headline: str = Field(description="Concise headline summarizing the signal")
    description: str = Field(description="Detailed description of the intelligence")
    customer_mentioned: Optional[str] = Field(
        default=None, description="Customer or company name if mentioned"
    )
    project_name: Optional[str] = Field(
        default=None, description="Project or vessel name if mentioned"
    )
    vessel_type: Optional[str] = Field(
        default=None,
        description="Type of vessel: ferry, OSV, tug, FPSO, patrol vessel, etc.",
    )
    engine_model: Optional[str] = Field(
        default=None, description="Engine model or product line mentioned"
    )
    fuel_type: Optional[str] = Field(
        default=None,
        description="Fuel type: diesel, LNG, dual_fuel, methanol, ammonia, hydrogen",
    )
    contract_value_usd: Optional[float] = Field(
        default=None, description="Contract value in USD if disclosed"
    )
    region: Optional[str] = Field(default=None, description="Geographic region")
    country: Optional[str] = Field(default=None, description="Specific country")
    is_marine_relevant: bool = Field(
        default=True, description="Whether this is relevant to marine industry"
    )
    confidence_score: float = Field(
        default=0.5, description="Confidence in extraction (0.0-1.0)"
    )


class FinancialSignalData(BaseModel):
    """Pydantic model for financial signal extraction."""

    signal_type: str = Field(
        default="FINANCIAL_UPDATE", description="Type of financial signal"
    )
    headline: str = Field(description="Headline for the financial signal")
    description: str = Field(description="Description of financial implications")
    metric_name: str = Field(description="Name of the financial metric")
    metric_value: Optional[float] = Field(default=None, description="Value of metric")
    change_pct: Optional[float] = Field(
        default=None, description="Percentage change (YoY or QoQ)"
    )
    trend: str = Field(
        default="stable", description="Trend: increasing, decreasing, stable"
    )
    competitive_impact: str = Field(
        description="Impact on RRPS competitive position: positive, negative, neutral"
    )
