"""
Unified Content Models

Single source of truth for all scraped/collected content across:
- Competitor Intelligence
- Marine Intelligence
- News Intelligence
- Knowledge Base enrichment

Key Principle: Scrape Once, Use Many
- One content record per URL (deduped by hash)
- One embedding per content
- One entity extraction per content
- Mandatory KB entity linking

Usage:
    from lead_to_cash.services.unified_content.models import (
        UnifiedContent,
        ContentSource,
        ContentPurpose,
    )
"""

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ContentSource(str, Enum):
    """Source of content ingestion."""

    # General
    GENERAL = "general"

    # News Sources
    NEWSAPI = "newsapi"
    RSS_FEED = "rss_feed"
    PERPLEXITY = "perplexity"

    # Web Scraping
    PRESS_ROOM = "press_room"
    COMPETITOR_WEBSITE = "competitor_website"
    PRODUCT_PAGE = "product_page"

    # Documents
    PDF_DOCUMENT = "pdf_document"
    ANNUAL_REPORT = "annual_report"

    # Regulatory
    REGULATORY_ANNOUNCEMENT = "regulatory_announcement"
    SGX_FILING = "sgx_filing"

    # Other
    SOCIAL_MEDIA = "social_media"
    MANUAL_ENTRY = "manual_entry"


class ContentPurpose(str, Enum):
    """Intended purpose/use case for content."""

    COMPETITOR_INTEL = "competitor_intel"
    MARINE_INTEL = "marine_intel"
    REGULATORY_INTEL = "regulatory_intel"
    PRODUCT_INTEL = "product_intel"
    MARKET_INTEL = "market_intel"
    GENERAL = "general"


class EntityType(str, Enum):
    """Types of entities that can be extracted."""

    MANUFACTURER = "manufacturer"
    ENGINE_MODEL = "engine_model"
    ENGINE_RATING = "engine_rating"
    VESSEL = "vessel"
    VESSEL_TYPE = "vessel_type"
    SHIPYARD = "shipyard"
    OPERATOR = "operator"
    CUSTOMER = "customer"
    REGULATORY_BODY = "regulatory_body"
    REGION = "region"
    CONTRACT_VALUE = "contract_value"


class SourceTier(int, Enum):
    """Source credibility tiers."""

    TIER_1 = 1  # Verified: Press releases, SGX filings, IMO, MPA
    TIER_2 = 2  # High: Lloyd's List, TradeWinds, DNV
    TIER_3 = 3  # Medium: Maritime Executive, Splash247
    TIER_4 = 4  # Low: General news, blogs, unverified


@dataclass
class ExtractedEntity:
    """An entity extracted from content and resolved against KB."""

    entity_type: str
    raw_text: str  # Original text as found in content
    normalized_text: str  # Cleaned/normalized version
    kb_entity_id: Optional[str] = None  # FK to KB entity (if resolved)
    kb_entity_type: Optional[str] = (
        None  # Which KB table (manufacturer, engine_model, etc.)
    )
    confidence: float = 0.0  # 0.0-1.0 resolution confidence
    context: Optional[str] = None  # Surrounding text for context
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "kb_entity_id": self.kb_entity_id,
            "kb_entity_type": self.kb_entity_type,
            "confidence": self.confidence,
            "context": self.context,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractedEntity":
        return cls(
            entity_type=data["entity_type"],
            raw_text=data["raw_text"],
            normalized_text=data["normalized_text"],
            kb_entity_id=data.get("kb_entity_id"),
            kb_entity_type=data.get("kb_entity_type"),
            confidence=data.get("confidence", 0.0),
            context=data.get("context"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ContentClassification:
    """Multi-purpose classification for content."""

    # Competitor Intel Scoring (0-100)
    competitor_threat_score: Optional[int] = None
    competitor_name: Optional[str] = None  # Which competitor this is about
    competitor_signal_type: Optional[str] = None  # contract_win, product_launch, etc.

    # Marine Intel Scoring
    sales_opportunity_score: Optional[int] = None
    sales_signals: list[str] = field(default_factory=list)  # newbuild, retrofit, etc.
    vessel_types: list[str] = field(default_factory=list)
    region: Optional[str] = None

    # KB Relevance Scoring
    technical_score: Optional[int] = None  # 0-40
    market_score: Optional[int] = None  # 0-30
    commercial_score: Optional[int] = None  # 0-30
    kb_relevance_total: Optional[int] = None  # 0-100

    # Priority
    priority: int = 5  # 1-10, 10 being highest
    requires_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "competitor_threat_score": self.competitor_threat_score,
            "competitor_name": self.competitor_name,
            "competitor_signal_type": self.competitor_signal_type,
            "sales_opportunity_score": self.sales_opportunity_score,
            "sales_signals": self.sales_signals,
            "vessel_types": self.vessel_types,
            "region": self.region,
            "technical_score": self.technical_score,
            "market_score": self.market_score,
            "commercial_score": self.commercial_score,
            "kb_relevance_total": self.kb_relevance_total,
            "priority": self.priority,
            "requires_review": self.requires_review,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContentClassification":
        return cls(
            competitor_threat_score=data.get("competitor_threat_score"),
            competitor_name=data.get("competitor_name"),
            competitor_signal_type=data.get("competitor_signal_type"),
            sales_opportunity_score=data.get("sales_opportunity_score"),
            sales_signals=data.get("sales_signals", []),
            vessel_types=data.get("vessel_types", []),
            region=data.get("region"),
            technical_score=data.get("technical_score"),
            market_score=data.get("market_score"),
            commercial_score=data.get("commercial_score"),
            kb_relevance_total=data.get("kb_relevance_total"),
            priority=data.get("priority", 5),
            requires_review=data.get("requires_review", False),
        )


@dataclass
class UnifiedContent:
    """
    Single content record for all intelligence services.

    This is the core model for the "Scrape Once, Use Many" architecture.
    Every piece of content (news, documents, web scrapes) goes through
    this unified model with:
    - URL-based deduplication
    - Single embedding generation
    - Mandatory KB entity resolution
    - Multi-purpose classification
    """

    id: str
    url: str
    url_hash: str  # SHA-256 for deduplication

    # Content
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None

    # Source Information
    source_name: str = ""  # e.g., "Maritime Executive", "MPA Singapore"
    source_type: str = ContentSource.GENERAL.value
    source_tier: int = SourceTier.TIER_3.value
    source_url: Optional[str] = None  # Original source URL (may differ from url)

    # Dates
    published_date: Optional[datetime] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    # Purposes (which services can use this content)
    purposes: list[str] = field(default_factory=list)

    # Embedding (1536-dim vector from text-embedding-3-small)
    embedding: Optional[list[float]] = None
    embedding_model: str = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")

    # Extracted Entities (resolved against KB)
    entities: list[ExtractedEntity] = field(default_factory=list)
    entities_extracted_at: Optional[datetime] = None

    # Multi-Purpose Classification
    classification: Optional[ContentClassification] = None

    # KB Linking (mandatory after processing)
    kb_linked: bool = False
    kb_article_entity_ids: list[str] = field(
        default_factory=list
    )  # FKs to kb_article_entities

    # Processing Status
    is_processed: bool = False
    processing_errors: list[str] = field(default_factory=list)

    # Metadata
    author: Optional[str] = None
    language: str = "en"
    metadata: dict = field(default_factory=dict)

    # Retention
    retention_tier: str = "hot"  # hot, warm, cold

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
        source_name: str,
        source_type: str = ContentSource.GENERAL.value,
        purposes: Optional[list[str]] = None,
        **kwargs,
    ) -> "UnifiedContent":
        """Factory method to create UnifiedContent with auto-generated ID and hash."""
        return cls(
            id=str(uuid.uuid4()),
            url=url,
            url_hash=cls.generate_url_hash(url),
            title=title,
            source_name=source_name,
            source_type=source_type,
            purposes=purposes or [ContentPurpose.GENERAL.value],
            **kwargs,
        )

    def add_entity(self, entity: ExtractedEntity) -> None:
        """Add an extracted entity."""
        self.entities.append(entity)

    def set_classification(self, classification: ContentClassification) -> None:
        """Set multi-purpose classification."""
        self.classification = classification
        self.updated_at = datetime.now(timezone.utc)

    def mark_kb_linked(self, kb_entity_ids: list[str]) -> None:
        """Mark content as linked to KB entities."""
        self.kb_linked = True
        self.kb_article_entity_ids = kb_entity_ids
        self.updated_at = datetime.now(timezone.utc)

    def mark_processed(self) -> None:
        """Mark content as fully processed."""
        self.is_processed = True
        self.processed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "url": self.url,
            "url_hash": self.url_hash,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_tier": self.source_tier,
            "source_url": self.source_url,
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
            "ingested_at": self.ingested_at.isoformat(),
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
            "purposes": self.purposes,
            "has_embedding": self.embedding is not None,
            "embedding_model": self.embedding_model,
            "entities": [e.to_dict() for e in self.entities],
            "entities_extracted_at": (
                self.entities_extracted_at.isoformat()
                if self.entities_extracted_at
                else None
            ),
            "classification": (
                self.classification.to_dict() if self.classification else None
            ),
            "kb_linked": self.kb_linked,
            "kb_article_entity_ids": self.kb_article_entity_ids,
            "is_processed": self.is_processed,
            "processing_errors": self.processing_errors,
            "author": self.author,
            "language": self.language,
            "metadata": self.metadata,
            "retention_tier": self.retention_tier,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_embedding and self.embedding:
            result["embedding"] = self.embedding
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedContent":
        """Create from dictionary."""
        entities = [ExtractedEntity.from_dict(e) for e in data.get("entities", [])]
        classification = (
            ContentClassification.from_dict(data["classification"])
            if data.get("classification")
            else None
        )

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            url=data["url"],
            url_hash=data.get("url_hash") or cls.generate_url_hash(data["url"]),
            title=data["title"],
            content=data.get("content"),
            summary=data.get("summary"),
            source_name=data.get("source_name", ""),
            source_type=data.get("source_type", ContentSource.GENERAL.value),
            source_tier=data.get("source_tier", SourceTier.TIER_3.value),
            source_url=data.get("source_url"),
            published_date=(
                datetime.fromisoformat(data["published_date"])
                if data.get("published_date")
                else None
            ),
            ingested_at=(
                datetime.fromisoformat(data["ingested_at"])
                if data.get("ingested_at")
                else datetime.now(timezone.utc)
            ),
            processed_at=(
                datetime.fromisoformat(data["processed_at"])
                if data.get("processed_at")
                else None
            ),
            purposes=data.get("purposes", [ContentPurpose.GENERAL.value]),
            embedding=data.get("embedding"),
            embedding_model=data.get("embedding_model", os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")),
            entities=entities,
            entities_extracted_at=(
                datetime.fromisoformat(data["entities_extracted_at"])
                if data.get("entities_extracted_at")
                else None
            ),
            classification=classification,
            kb_linked=data.get("kb_linked", False),
            kb_article_entity_ids=data.get("kb_article_entity_ids", []),
            is_processed=data.get("is_processed", False),
            processing_errors=data.get("processing_errors", []),
            author=data.get("author"),
            language=data.get("language", "en"),
            metadata=data.get("metadata", {}),
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
class IngestionJob:
    """Track content ingestion jobs."""

    id: str
    job_type: str  # "daily_news", "competitor_scrape", "rss_aggregation", etc.
    status: str  # "pending", "running", "completed", "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None

    # Counters
    content_found: int = 0
    content_saved: int = 0
    duplicates_skipped: int = 0
    entities_extracted: int = 0
    kb_links_created: int = 0
    errors: int = 0

    # Details
    sources_processed: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "content_found": self.content_found,
            "content_saved": self.content_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "entities_extracted": self.entities_extracted,
            "kb_links_created": self.kb_links_created,
            "errors": self.errors,
            "sources_processed": self.sources_processed,
            "error_messages": self.error_messages,
        }
