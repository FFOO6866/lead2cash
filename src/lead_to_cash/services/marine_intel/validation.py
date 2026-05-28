"""
Pydantic Validation Models for Marine Sales Intelligence

Provides input validation for all API endpoints and database operations.
Validates regions, sectors, signal types, and prevents injection attacks.

Production Features:
- Type-safe input validation with clear error messages
- Enum validation for constrained fields
- Length and range validation
- Sanitization of string inputs
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Enum Validators (matching models.py enums)
# =============================================================================


class ValidRegion(str, Enum):
    """Valid regions for marine intel queries."""

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


class ValidSector(str, Enum):
    """Valid sectors for marine intel queries."""

    MARINE_TRANSPORTATION = "marine_transportation"
    OFFSHORE_OIL_GAS = "offshore_oil_gas"
    MARINE_ENGINEERING = "marine_engineering"
    PORT_TERMINAL = "port_terminal"
    SHIPPING = "shipping"
    NAVAL_DEFENSE = "naval_defense"


class ValidSalesSignal(str, Enum):
    """Valid sales signal types."""

    NEWBUILD = "newbuild"
    RETROFIT_REPOWER = "retrofit_repower"
    OFFSHORE_PROJECT = "offshore_project"
    REGULATION = "regulation"
    FUEL_TRANSITION = "fuel_transition"
    FLEET_EXPANSION = "fleet_expansion"
    INCIDENT_RELIABILITY = "incident_reliability"
    FINANCING_CAPEX = "financing_capex"


class ValidVesselType(str, Enum):
    """Valid vessel types."""

    FERRY = "ferry"
    TUG = "tug"
    OSV = "osv"
    PSV = "psv"
    AHTS = "ahts"
    FPSO = "fpso"
    HARBOUR_CRAFT = "harbour_craft"
    CARGO = "cargo"
    TANKER = "tanker"
    CONTAINER = "container"
    CRUISE = "cruise"
    YACHT = "yacht"
    NAVAL = "naval"
    FISHING = "fishing"
    DREDGER = "dredger"
    CONSTRUCTION = "construction"
    OTHER = "other"


class ValidStatus(str, Enum):
    """Valid opportunity statuses."""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    WON = "won"
    LOST = "lost"
    INVALID = "invalid"


class ValidJobType(str, Enum):
    """Valid research job types."""

    DAILY_RESEARCH = "daily_research"
    TARGETED_RESEARCH = "targeted_research"
    MANUAL = "manual"
    WEEKLY_DEEP = "weekly_deep"


class ValidJobStatus(str, Enum):
    """Valid job statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# String Sanitization
# =============================================================================


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize a string input to prevent injection attacks.

    - Strips whitespace
    - Removes null bytes
    - Limits length
    - Preserves unicode for international names
    """
    if not value:
        return value
    # Remove null bytes
    value = value.replace("\x00", "")
    # Strip whitespace
    value = value.strip()
    # Limit length
    if len(value) > max_length:
        value = value[:max_length]
    return value


def sanitize_identifier(value: str) -> str:
    """
    Sanitize an identifier (ID, name for matching).

    Only allows alphanumeric, hyphens, underscores.
    """
    if not value:
        return value
    # Remove any characters that aren't alphanumeric, hyphen, or underscore
    return re.sub(r"[^a-zA-Z0-9_-]", "", value)


# =============================================================================
# Query Parameter Validators
# =============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum items to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class DateRangeParams(BaseModel):
    """Date range parameters for queries."""

    days: int = Field(
        default=7, ge=1, le=365, description="Number of days to look back"
    )


class OpportunityQueryParams(BaseModel):
    """Query parameters for listing opportunities."""

    region: Optional[ValidRegion] = Field(default=None, description="Filter by region")
    sector: Optional[ValidSector] = Field(default=None, description="Filter by sector")
    sales_signal: Optional[ValidSalesSignal] = Field(
        default=None, description="Filter by sales signal"
    )
    vessel_type: Optional[ValidVesselType] = Field(
        default=None, description="Filter by vessel type"
    )
    reviewed: Optional[bool] = Field(
        default=None, description="Filter by review status"
    )
    min_priority: int = Field(
        default=1, ge=1, le=10, description="Minimum priority (1-10)"
    )
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum items to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class ArticleQueryParams(BaseModel):
    """Query parameters for listing articles."""

    source: Optional[str] = Field(
        default=None, max_length=200, description="Filter by source"
    )
    is_processed: Optional[bool] = Field(
        default=None, description="Filter by processed status"
    )
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum items to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of items to skip")

    @field_validator("source", mode="before")
    @classmethod
    def sanitize_source(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_string(v, max_length=200)


class AccountQueryParams(BaseModel):
    """Query parameters for listing accounts."""

    country: Optional[str] = Field(
        default=None, max_length=100, description="Filter by country"
    )
    sector: Optional[ValidSector] = Field(default=None, description="Filter by sector")
    is_existing_customer: Optional[bool] = Field(
        default=None, description="Filter by customer status"
    )
    min_mentions: int = Field(default=0, ge=0, description="Minimum mention count")
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum items to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of items to skip")

    @field_validator("country", mode="before")
    @classmethod
    def sanitize_country(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_string(v, max_length=100)


# =============================================================================
# Research Job Validators
# =============================================================================


class TargetedResearchRequest(BaseModel):
    """Request parameters for targeted research."""

    region: Optional[ValidRegion] = Field(default=None, description="Target region")
    sector: Optional[ValidSector] = Field(default=None, description="Target sector")
    category: Optional[str] = Field(
        default=None, max_length=50, description="Research category"
    )

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = sanitize_string(v, max_length=50)
        # Valid categories from scheduler
        valid_categories = {
            "newbuild",
            "retrofit_repower",
            "offshore",
            "fuel_transition",
            "fleet_expansion",
            "incidents",
        }
        if v and v.lower() not in valid_categories:
            raise ValueError(
                f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        return v.lower() if v else v


class JobQueryParams(BaseModel):
    """Query parameters for listing jobs."""

    job_type: Optional[ValidJobType] = Field(
        default=None, description="Filter by job type"
    )
    status: Optional[ValidJobStatus] = Field(
        default=None, description="Filter by status"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum items to return")


# =============================================================================
# Create/Update Validators
# =============================================================================


class ArticleCreate(BaseModel):
    """Validated article creation request."""

    url: str = Field(..., min_length=10, max_length=2000, description="Article URL")
    title: str = Field(..., min_length=1, max_length=500, description="Article title")
    source: str = Field(
        ..., min_length=1, max_length=200, description="Source publication"
    )
    content: Optional[str] = Field(
        default=None, max_length=100000, description="Article content"
    )
    summary: Optional[str] = Field(
        default=None, max_length=5000, description="Article summary"
    )
    published_date: Optional[datetime] = Field(
        default=None, description="Publication date"
    )
    source_category: str = Field(
        default="trade_media", max_length=50, description="Source category"
    )

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = sanitize_string(v, max_length=2000)
        # Basic URL validation
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("title", "source", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: str) -> str:
        return sanitize_string(v)

    @field_validator("content", "summary", mode="before")
    @classmethod
    def sanitize_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_string(v, max_length=100000)


class OpportunityCreate(BaseModel):
    """Validated opportunity creation request."""

    article_id: str = Field(
        ..., min_length=1, max_length=100, description="Source article ID"
    )
    company_name: str = Field(
        ..., min_length=1, max_length=200, description="Company name"
    )
    country: str = Field(..., min_length=1, max_length=100, description="Country")
    signal_type: ValidSalesSignal = Field(..., description="Sales signal type")
    vessel_type: Optional[ValidVesselType] = Field(
        default=None, description="Vessel type"
    )
    sector: Optional[ValidSector] = Field(default=None, description="Sector")
    score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Opportunity score (0-100)"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="AI confidence (0-1)"
    )
    description: Optional[str] = Field(
        default=None, max_length=5000, description="Opportunity description"
    )
    vessel_count: Optional[int] = Field(
        default=None, ge=0, le=10000, description="Number of vessels"
    )
    estimated_value: Optional[float] = Field(
        default=None, ge=0, description="Estimated value in USD"
    )
    engine_requirement: Optional[str] = Field(
        default=None, max_length=500, description="Engine requirement"
    )
    source_url: str = Field(default="", max_length=2000, description="Source URL")
    source_excerpt: Optional[str] = Field(
        default=None, max_length=2000, description="Relevant excerpt"
    )

    @field_validator("article_id", mode="before")
    @classmethod
    def validate_article_id(cls, v: str) -> str:
        return sanitize_string(v, max_length=100)

    @field_validator("company_name", "country", mode="before")
    @classmethod
    def sanitize_name_fields(cls, v: str) -> str:
        return sanitize_string(v, max_length=200)


class OpportunityStatusUpdate(BaseModel):
    """Validated opportunity status update."""

    status: ValidStatus = Field(..., description="New status")
    notes: Optional[str] = Field(
        default=None, max_length=5000, description="Optional notes"
    )

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_string(v, max_length=5000)


class AccountCreate(BaseModel):
    """Validated account creation request."""

    company_name: str = Field(
        ..., min_length=1, max_length=200, description="Company name"
    )
    country: Optional[str] = Field(default=None, max_length=100, description="Country")
    sector: Optional[ValidSector] = Field(default=None, description="Primary sector")
    website: Optional[str] = Field(
        default=None, max_length=500, description="Company website"
    )

    @field_validator("company_name", "country", mode="before")
    @classmethod
    def sanitize_name_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_string(v, max_length=200)

    @field_validator("website", mode="before")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = sanitize_string(v, max_length=500)
        if v and not v.startswith(("http://", "https://")):
            # Add https:// if missing
            v = f"https://{v}"
        return v


class AccountCRMUpdate(BaseModel):
    """Validated account CRM integration update."""

    crm_account_id: str = Field(
        ..., min_length=1, max_length=100, description="CRM account ID"
    )
    is_existing_customer: bool = Field(default=True, description="Is existing customer")

    @field_validator("crm_account_id", mode="before")
    @classmethod
    def sanitize_crm_id(cls, v: str) -> str:
        return sanitize_identifier(v)


class PriorityUpdate(BaseModel):
    """Validated priority update."""

    priority: int = Field(..., ge=1, le=10, description="Priority (1-10, 10 = highest)")


# =============================================================================
# Helper Functions
# =============================================================================


def validate_id(id_value: str, name: str = "ID") -> str:
    """
    Validate an ID parameter.

    Args:
        id_value: The ID to validate
        name: Name of the field for error messages

    Returns:
        Sanitized ID

    Raises:
        ValueError: If ID is invalid
    """
    if not id_value:
        raise ValueError(f"{name} is required")

    sanitized = sanitize_string(id_value, max_length=100)

    if len(sanitized) < 1:
        raise ValueError(f"{name} cannot be empty")

    return sanitized


def validate_days_param(days: Any) -> int:
    """
    Validate a days parameter for date range queries.

    Args:
        days: The days value to validate

    Returns:
        Validated days as integer (1-365)
    """
    try:
        days_int = int(days)
    except (TypeError, ValueError):
        return 7  # Default

    return max(1, min(365, days_int))


def validate_limit_param(limit: Any, default: int = 100, maximum: int = 1000) -> int:
    """
    Validate a limit parameter for pagination.

    Args:
        limit: The limit value to validate
        default: Default value if invalid
        maximum: Maximum allowed value

    Returns:
        Validated limit as integer
    """
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        return default

    return max(1, min(maximum, limit_int))


def validate_offset_param(offset: Any) -> int:
    """
    Validate an offset parameter for pagination.

    Args:
        offset: The offset value to validate

    Returns:
        Validated offset as integer (>= 0)
    """
    try:
        offset_int = int(offset)
    except (TypeError, ValueError):
        return 0

    return max(0, offset_int)
