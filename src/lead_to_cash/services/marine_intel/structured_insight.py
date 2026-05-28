"""
Structured Insight Models for Marine Sales Intelligence

Pydantic models for structuring raw search results into actionable
sales intelligence for the RRPS marine engine sales team.

Each insight follows a strict schema designed for sales team consumption:
- Clear headline with specific company/deal information
- Tagged sales signals (NEWBUILD, RETROFIT, etc.)
- Engine requirements and power specifications
- Actionable sales recommendations
- Data quality scoring
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SalesSignalType(str, Enum):
    """Sales signal types indicating opportunity category."""

    NEWBUILD = "NEWBUILD"
    RETROFIT_REPOWER = "RETROFIT_REPOWER"
    OFFSHORE_PROJECT = "OFFSHORE_PROJECT"
    REGULATION = "REGULATION"
    FUEL_TRANSITION = "FUEL_TRANSITION"
    FLEET_EXPANSION = "FLEET_EXPANSION"
    INCIDENT_RELIABILITY = "INCIDENT_RELIABILITY"
    FINANCING_CAPEX = "FINANCING_CAPEX"


class Priority(str, Enum):
    """Insight priority levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNVERIFIED = "UNVERIFIED"


class SourceReliability(str, Enum):
    """Source reliability classification."""

    PRIMARY = "primary"  # Direct from company, regulatory body
    SECONDARY = "secondary"  # Trade media, industry publications
    RUMOR = "rumor"  # Unverified, industry gossip


# =============================================================================
# Sub-models for Structured Insight
# =============================================================================


class CompanyInfo(BaseModel):
    """Companies involved in the opportunity."""

    operator: str = Field(..., description="Vessel operator/owner company name")
    operator_country: Optional[str] = Field(None, description="Operator's country")
    shipyard: Optional[str] = Field(
        None, description="Shipyard building/repairing vessel"
    )
    shipyard_country: Optional[str] = Field(None, description="Shipyard's country")
    engine_supplier: Optional[str] = Field(
        "Unknown - OPPORTUNITY",
        description="Current or selected engine supplier, or 'Unknown - OPPORTUNITY'",
    )


class DealDetails(BaseModel):
    """Deal/contract specific information."""

    vessel_type: str = Field(..., description="Type of vessel (ferry, OSV, tug, etc.)")
    vessel_subtype: Optional[str] = Field(
        None, description="Specific subtype (e.g., DP2 OSV)"
    )
    vessel_count: Optional[int] = Field(None, ge=1, description="Number of vessels")
    vessel_specs: Optional[str] = Field(
        None, description="Vessel specifications (capacity, size)"
    )
    contract_value_usd: Optional[float] = Field(
        None, ge=0, description="Contract value in USD"
    )
    contract_value_local: Optional[str] = Field(
        None, description="Contract value in local currency"
    )
    delivery_timeline: Optional[str] = Field(
        None, description="Expected delivery timeframe"
    )
    project_duration: Optional[str] = Field(
        None, description="Project duration if applicable"
    )


class EngineRequirement(BaseModel):
    """Engine specifications and requirements."""

    power_range_kw: Optional[str] = Field(
        None, description="Power range in kW (e.g., '2000-4000')"
    )
    power_per_engine_kw: Optional[int] = Field(
        None, description="Power per engine in kW"
    )
    engine_count: Optional[int] = Field(
        None, ge=1, description="Number of engines required"
    )
    propulsion_type: Optional[str] = Field(
        None, description="Propulsion type (diesel-mechanical, diesel-electric)"
    )
    fuel_type: Optional[str] = Field(
        None, description="Fuel type (MDO, LNG, methanol, etc.)"
    )
    configuration: Optional[str] = Field(
        None, description="Engine configuration (twin, quad, etc.)"
    )
    estimated_value_usd: Optional[float] = Field(
        None, description="Estimated engine package value"
    )
    notes: Optional[str] = Field(
        None, description="Additional engine requirement notes"
    )


class SalesAction(BaseModel):
    """Recommended sales actions."""

    priority: Priority = Field(Priority.MEDIUM, description="Action priority")
    action: str = Field(..., description="Primary recommended action")
    contact_target: Optional[str] = Field(
        None, description="Who to contact (role/name)"
    )
    timeline: Optional[str] = Field(
        None, description="When to take action / decision timeline"
    )
    competition: Optional[str] = Field(
        None, description="Known competitors for this opportunity"
    )
    next_steps: Optional[list[str]] = Field(None, description="List of next steps")


class DataQuality(BaseModel):
    """Data quality and completeness indicators."""

    has_company_names: bool = False
    has_contract_value: bool = False
    has_vessel_specs: bool = False
    has_engine_requirements: bool = False
    has_timeline: bool = False
    has_contact_info: bool = False
    source_reliability: SourceReliability = SourceReliability.SECONDARY


class SourceInfo(BaseModel):
    """Source attribution."""

    name: str = Field(..., description="Source publication name")
    url: Optional[str] = Field(None, description="Article URL")
    published_date: Optional[str] = Field(None, description="Publication date")
    author: Optional[str] = Field(None, description="Article author if known")


# =============================================================================
# Main Structured Insight Model
# =============================================================================


class StructuredInsight(BaseModel):
    """
    A fully structured sales insight for the RRPS sales team.

    This model represents a single actionable opportunity extracted
    from raw search results, formatted for sales consumption.
    """

    # Identification
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique insight ID"
    )

    # Core information
    headline: str = Field(
        ...,
        description="Specific headline: '[Company] [action] [details]'",
        min_length=10,
        max_length=200,
    )
    signal_type: SalesSignalType = Field(..., description="Primary sales signal type")
    secondary_signals: list[SalesSignalType] = Field(
        default_factory=list, description="Secondary signal types"
    )
    priority: Priority = Field(Priority.MEDIUM, description="Overall priority")

    # Detailed information
    companies: CompanyInfo = Field(..., description="Companies involved")
    deal_details: DealDetails = Field(..., description="Deal/contract details")
    engine_requirement: Optional[EngineRequirement] = Field(
        None, description="Engine requirements"
    )

    # Sales context
    why_it_matters: str = Field(
        ...,
        description="Why this matters for RRPS - sales relevance explanation",
        min_length=20,
    )
    sales_action: SalesAction = Field(..., description="Recommended sales actions")

    # Region
    country: str = Field(..., description="Primary country")
    region: str = Field(..., description="Region code (singapore, indonesia, etc.)")

    # Source
    source: SourceInfo = Field(..., description="Source information")

    # Quality
    score: int = Field(..., ge=0, le=100, description="Data quality score (0-100)")
    data_quality: DataQuality = Field(
        default_factory=DataQuality, description="Data quality indicators"
    )

    # Timestamps
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When insight was discovered",
    )

    # Raw content for reference
    raw_excerpt: Optional[str] = Field(None, description="Raw text excerpt from source")

    def calculate_score(self) -> int:
        """Calculate data quality score based on completeness."""
        score = 0

        # Company names (25 points)
        if self.companies.operator and self.companies.shipyard:
            score += 25
        elif self.companies.operator or self.companies.shipyard:
            score += 15

        # Contract value (20 points)
        if self.deal_details.contract_value_usd:
            score += 20
        elif self.deal_details.contract_value_local:
            score += 10

        # Vessel specifications (20 points)
        specs_score = 0
        if self.deal_details.vessel_type:
            specs_score += 7
        if self.deal_details.vessel_count:
            specs_score += 7
        if self.deal_details.vessel_specs:
            specs_score += 6
        score += specs_score

        # Engine requirements (15 points)
        if self.engine_requirement:
            eng_score = 0
            if self.engine_requirement.power_range_kw:
                eng_score += 5
            if self.engine_requirement.engine_count:
                eng_score += 5
            if self.engine_requirement.fuel_type:
                eng_score += 5
            score += eng_score

        # Timeline (10 points)
        if self.deal_details.delivery_timeline:
            score += 10
        elif self.sales_action.timeline:
            score += 5

        # Source reliability (10 points)
        reliability_scores = {
            SourceReliability.PRIMARY: 10,
            SourceReliability.SECONDARY: 5,
            SourceReliability.RUMOR: 0,
        }
        score += reliability_scores.get(self.data_quality.source_reliability, 0)

        return min(100, score)

    def determine_priority(self) -> Priority:
        """Determine priority based on score and signal type."""
        score = self.score if self.score > 0 else self.calculate_score()

        # High priority signals
        high_priority_signals = {
            SalesSignalType.NEWBUILD,
            SalesSignalType.RETROFIT_REPOWER,
            SalesSignalType.FUEL_TRANSITION,
        }

        if score >= 85:
            return Priority.HIGH
        elif score >= 60:
            if self.signal_type in high_priority_signals:
                return Priority.HIGH
            return Priority.MEDIUM
        elif score >= 40:
            return Priority.LOW
        else:
            return Priority.UNVERIFIED

    def to_sales_report(self) -> str:
        """Format insight as a clean, scannable news brief."""
        # Build a concise 1-2 sentence description
        description_parts = []

        # Add contract value if available
        if self.deal_details.contract_value_usd:
            description_parts.append(
                f"${self.deal_details.contract_value_usd/1_000_000:.0f}M"
            )
        elif self.deal_details.contract_value_local:
            description_parts.append(self.deal_details.contract_value_local)

        # Add vessel details
        if self.deal_details.vessel_count and self.deal_details.vessel_type:
            description_parts.append(
                f"{self.deal_details.vessel_count} {self.deal_details.vessel_type}(s)"
            )
        elif self.deal_details.vessel_type:
            description_parts.append(self.deal_details.vessel_type)

        # Add key context from why_it_matters (first sentence only)
        if self.why_it_matters:
            first_sentence = self.why_it_matters.split(".")[0] + "."
            if len(first_sentence) < 150:
                description_parts.append(first_sentence)

        # Build description
        if description_parts:
            description = " | ".join(description_parts[:2])
            if len(description_parts) > 2:
                description += f" {description_parts[2]}"
        else:
            description = self.why_it_matters[:150] if self.why_it_matters else ""

        # Format source link
        source_link = (
            f"[Read more → {self.source.name}]({self.source.url})"
            if self.source.url
            else f"Source: {self.source.name}"
        )

        return f"**{self.headline}**\n{description}\n{source_link}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "headline": self.headline,
            "signal_type": self.signal_type.value,
            "secondary_signals": [s.value for s in self.secondary_signals],
            "priority": self.priority.value,
            "score": self.score,
            "companies": {
                "operator": self.companies.operator,
                "operator_country": self.companies.operator_country,
                "shipyard": self.companies.shipyard,
                "shipyard_country": self.companies.shipyard_country,
                "engine_supplier": self.companies.engine_supplier,
            },
            "deal_details": {
                "vessel_type": self.deal_details.vessel_type,
                "vessel_subtype": self.deal_details.vessel_subtype,
                "vessel_count": self.deal_details.vessel_count,
                "vessel_specs": self.deal_details.vessel_specs,
                "contract_value_usd": self.deal_details.contract_value_usd,
                "contract_value_local": self.deal_details.contract_value_local,
                "delivery_timeline": self.deal_details.delivery_timeline,
            },
            "engine_requirement": (
                {
                    "power_range_kw": (
                        self.engine_requirement.power_range_kw
                        if self.engine_requirement
                        else None
                    ),
                    "engine_count": (
                        self.engine_requirement.engine_count
                        if self.engine_requirement
                        else None
                    ),
                    "fuel_type": (
                        self.engine_requirement.fuel_type
                        if self.engine_requirement
                        else None
                    ),
                    "estimated_value_usd": (
                        self.engine_requirement.estimated_value_usd
                        if self.engine_requirement
                        else None
                    ),
                    "notes": (
                        self.engine_requirement.notes
                        if self.engine_requirement
                        else None
                    ),
                }
                if self.engine_requirement
                else None
            ),
            "why_it_matters": self.why_it_matters,
            "sales_action": {
                "priority": self.sales_action.priority.value,
                "action": self.sales_action.action,
                "contact_target": self.sales_action.contact_target,
                "timeline": self.sales_action.timeline,
                "competition": self.sales_action.competition,
                "next_steps": self.sales_action.next_steps,
            },
            "country": self.country,
            "region": self.region,
            "source": {
                "name": self.source.name,
                "url": self.source.url,
                "published_date": self.source.published_date,
            },
            "data_quality": {
                "has_company_names": self.data_quality.has_company_names,
                "has_contract_value": self.data_quality.has_contract_value,
                "has_vessel_specs": self.data_quality.has_vessel_specs,
                "has_engine_requirements": self.data_quality.has_engine_requirements,
                "has_timeline": self.data_quality.has_timeline,
                "source_reliability": self.data_quality.source_reliability.value,
            },
            "discovered_at": self.discovered_at.isoformat(),
        }


# =============================================================================
# Insight Collection Response
# =============================================================================


class InsightCollectionResponse(BaseModel):
    """Response containing multiple structured insights."""

    status: str = Field("success", description="Response status")
    query_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When query was executed",
    )
    insights_count: int = Field(0, description="Total insights found")
    high_priority_count: int = Field(0, description="High priority insights")
    medium_priority_count: int = Field(0, description="Medium priority insights")
    low_priority_count: int = Field(0, description="Low priority insights")
    insights: list[StructuredInsight] = Field(
        default_factory=list, description="List of insights"
    )

    # Search metadata
    search_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Search execution metadata"
    )

    # When no results
    message: Optional[str] = Field(None, description="Status message")
    recommendations: Optional[list[str]] = Field(
        None, description="Recommendations when no results"
    )
    market_context: Optional[str] = Field(
        None, description="Market context explanation"
    )

    def to_sales_report(self) -> str:
        """Generate a clean news briefing grouped by source category."""
        if not self.insights:
            lines = [
                "## Singapore Marine Intelligence",
                "",
                "No news found matching your criteria.",
                "",
            ]
            if self.recommendations:
                lines.append("**Suggestions:**")
                for rec in self.recommendations:
                    lines.append(f"• {rec}")
            if self.market_context:
                lines.append("")
                lines.append(f"*{self.market_context}*")
            return "\n".join(lines)

        # Categorize sources
        regulatory_sources = {
            "MPA",
            "PSA",
            "SMF",
            "ASMI",
            "SSA",
            "SGX",
            "Petronas",
            "MPA Singapore",
        }
        company_sources = {
            "Seatrium",
            "PaxOcean",
            "ASL Marine",
            "Penguin",
            "MISC",
            "Keppel",
            "Sembcorp",
        }

        regulatory = []
        industry_news = []
        company_announcements = []

        for insight in self.insights:
            source_name = insight.source.name or ""
            # Check if source is regulatory
            if any(reg in source_name for reg in regulatory_sources):
                regulatory.append(insight)
            # Check if source is company announcement
            elif any(comp in source_name for comp in company_sources):
                company_announcements.append(insight)
            else:
                industry_news.append(insight)

        lines = ["## 🇸🇬 Singapore", ""]

        # Regulatory & Official
        if regulatory:
            lines.append("### Regulatory & Official")
            lines.append("")
            for insight in regulatory:
                lines.append(insight.to_sales_report())
                lines.append("")

        # Industry News
        if industry_news:
            lines.append("### Industry News")
            lines.append("")
            for insight in industry_news:
                lines.append(insight.to_sales_report())
                lines.append("")

        # Company Announcements
        if company_announcements:
            lines.append("### Company Announcements")
            lines.append("")
            for insight in company_announcements:
                lines.append(insight.to_sales_report())
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status,
            "query_timestamp": self.query_timestamp.isoformat(),
            "insights_count": self.insights_count,
            "high_priority_count": self.high_priority_count,
            "medium_priority_count": self.medium_priority_count,
            "low_priority_count": self.low_priority_count,
            "insights": [i.to_dict() for i in self.insights],
            "search_metadata": self.search_metadata,
            "message": self.message,
            "recommendations": self.recommendations,
            "market_context": self.market_context,
        }
