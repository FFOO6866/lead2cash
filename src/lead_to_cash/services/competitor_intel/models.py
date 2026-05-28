"""
Competitor Intelligence Data Models

DataFlow models for storing and searching competitor intelligence
with pgvector embeddings for semantic search.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from lead_to_cash.services.competitor_intel.signal_models import (
    CompetitorFinancials,
    CompetitorSignal,
    CompetitorSignalType,
    ExtractedSignalData,
    FinancialSignalData,
    FuelType,
    SourceChannel,
)

logger = logging.getLogger(__name__)


class Competitor(str, Enum):
    """Target competitors for intelligence gathering."""

    CATERPILLAR = "caterpillar"
    CUMMINS = "cummins"
    MAN_ENERGY = "man_energy"
    WARTSILA = "wartsila"
    VOLVO_PENTA = "volvo_penta"
    YANMAR = "yanmar"


class ContentType(str, Enum):
    """Types of competitor content to track."""

    # Company Information
    NEWS = "news"
    PRESS_RELEASE = "press_release"
    ANNUAL_REPORT = "annual_report"
    QUARTERLY_REPORT = "quarterly_report"

    # Products & Services
    PRODUCT_PAGE = "product_page"
    PRODUCT_LAUNCH = "product_launch"
    SERVICE_OFFERING = "service_offering"
    TECHNICAL_SPEC = "technical_spec"

    # Sales Intelligence
    CONTRACT_WIN = "contract_win"
    CUSTOMER_SUCCESS = "customer_success"
    CASE_STUDY = "case_study"
    TESTIMONIAL = "testimonial"

    # Strategic
    PARTNERSHIP = "partnership"
    ACQUISITION = "acquisition"
    EXPANSION = "expansion"
    EXECUTIVE_CHANGE = "executive_change"

    # Market
    MARKET_ANALYSIS = "market_analysis"
    PRICING_INFO = "pricing_info"
    COMPETITOR_COMPARISON = "competitor_comparison"

    # Social & Events
    SOCIAL_MEDIA = "social_media"
    EVENT = "event"
    WEBINAR = "webinar"


class SourceType(str, Enum):
    """Source of the content."""

    PERPLEXITY = "perplexity"
    WEB_SCRAPE = "web_scrape"
    PDF = "pdf"
    RSS = "rss"
    API = "api"


@dataclass
class CompetitorDocument:
    """
    A competitor intelligence document.

    Stores full content from various sources about competitors.
    """

    id: str
    competitor: str
    content_type: str
    source_type: str
    title: str
    content: str
    summary: Optional[str] = None
    source_url: str = ""
    published_date: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    # Sales-relevant fields
    customer_mentioned: Optional[str] = None  # Customer name if mentioned
    deal_value: Optional[float] = None  # Contract value if disclosed
    region: Optional[str] = None  # Geographic region
    industry_segment: Optional[str] = None  # Marine, Oil & Gas, etc.

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "competitor": self.competitor,
            "content_type": self.content_type,
            "source_type": self.source_type,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "source_url": self.source_url,
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
            "scraped_at": self.scraped_at.isoformat(),
            "metadata": self.metadata,
            "customer_mentioned": self.customer_mentioned,
            "deal_value": self.deal_value,
            "region": self.region,
            "industry_segment": self.industry_segment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CompetitorDocument":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            competitor=data["competitor"],
            content_type=data["content_type"],
            source_type=data["source_type"],
            title=data["title"],
            content=data["content"],
            summary=data.get("summary"),
            source_url=data.get("source_url", ""),
            published_date=(
                datetime.fromisoformat(data["published_date"])
                if data.get("published_date")
                else None
            ),
            scraped_at=(
                datetime.fromisoformat(data["scraped_at"])
                if data.get("scraped_at")
                else datetime.now(timezone.utc)
            ),
            metadata=data.get("metadata", {}),
            customer_mentioned=data.get("customer_mentioned"),
            deal_value=data.get("deal_value"),
            region=data.get("region"),
            industry_segment=data.get("industry_segment"),
        )


@dataclass
class DocumentChunk:
    """
    A chunk of a competitor document for RAG retrieval.

    Documents are chunked for optimal embedding and retrieval.
    """

    id: str
    document_id: str
    chunk_index: int
    content: str
    embedding: list[float]  # 1536-dim for text-embedding-3-small
    token_count: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "embedding": self.embedding,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


@dataclass
class ScrapingJob:
    """Track scraping job status."""

    id: str
    job_type: str  # "daily_refresh", "manual", "initial", "weekly_full"
    status: str  # "pending", "running", "completed", "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    documents_processed: int = 0
    documents_failed: int = 0
    chunks_created: int = 0
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
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "chunks_created": self.chunks_created,
            "error_message": self.error_message,
        }


# =============================================================================
# Database Access
# =============================================================================
# The in-memory store has been replaced with PostgreSQL + pgvector.
# Use lead_to_cash.services.competitor_intel.database for database access.
#
# Import from database.py:
#   from lead_to_cash.services.competitor_intel.database import (
#       get_competitor_db,
#       initialize_competitor_db,
#   )
# =============================================================================


# =============================================================================
# Signal Models (Enhanced Competitor Intelligence)
# =============================================================================
# Re-export signal models for convenience.
# These support the enhanced competitor intelligence pipeline with:
# - Signal type classification (CONTRACT_WIN, PRODUCT_LAUNCH, etc.)
# - Source channel tracking (website, social media, EODHD)
# - Scoring system (0-100)
# - Financial data from EODHD
#
# Import from signal_models.py for full functionality:
#   from lead_to_cash.services.competitor_intel.signal_models import (
#       CompetitorSignal,
#       CompetitorFinancials,
#       CompetitorSignalType,
#       SourceChannel,
#       FuelType,
#   )
# =============================================================================

__all__ = [
    # Original models
    "Competitor",
    "ContentType",
    "SourceType",
    "CompetitorDocument",
    "DocumentChunk",
    "ScrapingJob",
    # Signal models (enhanced competitor intelligence)
    "CompetitorSignal",
    "CompetitorSignalType",
    "SourceChannel",
    "FuelType",
    "CompetitorFinancials",
    "ExtractedSignalData",
    "FinancialSignalData",
]
