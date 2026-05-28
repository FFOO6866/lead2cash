"""
Entity Registry Data Models

Core dataclasses for entity resolution and storage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class VerificationStatus(str, Enum):
    """Entity verification status."""

    UNVERIFIED = "unverified"
    USER_CONFIRMED = "user_confirmed"
    EXTERNALLY_VERIFIED = "externally_verified"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    ARCHIVED = "archived"


class EntitySourceType(str, Enum):
    """Source of entity data."""

    SAP_CPI = "sap_cpi"
    EODHD = "eodhd"
    ACRA = "acra"
    GLEIF = "gleif"
    OPENCORPORATES = "opencorporates"
    USER_INPUT = "user_input"
    MIGRATION = "migration"


class ResolutionStatus(str, Enum):
    """Status of entity resolution attempt."""

    EXACT_MATCH = "exact_match"
    HIGH_CONFIDENCE_MATCH = "high_confidence_match"
    CANDIDATES_FOUND = "candidates_found"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NO_MATCH = "no_match"
    NEW_ENTITY = "new_entity"


@dataclass
class Entity:
    """
    Core entity from the registry.

    Represents a confirmed company identity with all associated identifiers
    and verification metadata.
    """

    id: str
    canonical_name: str
    country_code: str

    # Legal details
    legal_name: Optional[str] = None

    # Unique identifiers
    uen: Optional[str] = None  # Singapore Unique Entity Number
    lei: Optional[str] = None  # Legal Entity Identifier (GLEIF)
    cvr: Optional[str] = None  # Danish CVR number
    vat_number: Optional[str] = None
    duns: Optional[str] = None  # D&B DUNS number

    # Classification
    entity_type: str = "company"
    industry_sector: Optional[str] = None

    # Verification
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    verification_source: Optional[str] = None

    # External data cache
    acra_data: Optional[dict] = None
    gleif_data: Optional[dict] = None
    opencorporates_data: Optional[dict] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "country_code": self.country_code,
            "legal_name": self.legal_name,
            "uen": self.uen,
            "lei": self.lei,
            "cvr": self.cvr,
            "vat_number": self.vat_number,
            "duns": self.duns,
            "entity_type": self.entity_type,
            "industry_sector": self.industry_sector,
            "verification_status": self.verification_status.value,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verified_by": self.verified_by,
            "verification_source": self.verification_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        """Create Entity from dictionary."""
        status = data.get("verification_status", "unverified")
        if isinstance(status, str):
            status = VerificationStatus(status)

        verified_at = data.get("verified_at")
        if isinstance(verified_at, str):
            verified_at = datetime.fromisoformat(verified_at)

        return cls(
            id=data["id"],
            canonical_name=data["canonical_name"],
            country_code=data["country_code"],
            legal_name=data.get("legal_name"),
            uen=data.get("uen"),
            lei=data.get("lei"),
            cvr=data.get("cvr"),
            vat_number=data.get("vat_number"),
            duns=data.get("duns"),
            entity_type=data.get("entity_type", "company"),
            industry_sector=data.get("industry_sector"),
            verification_status=status,
            verified_at=verified_at,
            verified_by=data.get("verified_by"),
            verification_source=data.get("verification_source"),
            acra_data=data.get("acra_data"),
            gleif_data=data.get("gleif_data"),
            opencorporates_data=data.get("opencorporates_data"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class EntityAlias:
    """
    Entity alias for fuzzy matching.

    Multiple aliases can map to a single entity.
    """

    id: str
    entity_id: str
    alias_text: str
    normalized_text: str
    alias_type: str = (
        "common_name"  # common_name, abbreviation, trading_name, former_name
    )
    source: EntitySourceType = EntitySourceType.USER_INPUT
    confidence: float = 1.0
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "alias_text": self.alias_text,
            "normalized_text": self.normalized_text,
            "alias_type": self.alias_type,
            "source": (
                self.source.value
                if isinstance(self.source, EntitySourceType)
                else self.source
            ),
            "confidence": self.confidence,
        }


@dataclass
class EntityExternalMapping:
    """
    Mapping between entity and external system ID.

    Links entities to SAP customer IDs, EODHD symbols, etc.
    """

    id: str
    entity_id: str
    external_system: str  # "sap", "eodhd", "aravo"
    external_id: str
    external_data: Optional[dict] = None
    verified: bool = False
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "external_system": self.external_system,
            "external_id": self.external_id,
            "external_data": self.external_data,
            "verified": self.verified,
        }


@dataclass
class EntityCandidate:
    """
    A candidate entity match with confidence scoring.

    Used in resolution results to present options to users.
    """

    # Identity
    entity_id: Optional[str]  # None if from external source (not yet in registry)
    canonical_name: str
    legal_name: Optional[str]
    country_code: str

    # Identifiers
    uen: Optional[str] = None
    lei: Optional[str] = None

    # Match metadata
    match_type: str = "exact"  # exact, fuzzy, semantic, external
    confidence_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)

    # Source data
    source: str = "registry"  # registry, acra, opencorporates, gleif
    external_data: Optional[dict] = None

    # For display
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "legal_name": self.legal_name,
            "country_code": self.country_code,
            "uen": self.uen,
            "lei": self.lei,
            "match_type": self.match_type,
            "confidence_score": self.confidence_score,
            "match_reasons": self.match_reasons,
            "source": self.source,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityCandidate":
        """Create EntityCandidate from dictionary."""
        return cls(
            entity_id=data.get("entity_id"),
            canonical_name=data["canonical_name"],
            legal_name=data.get("legal_name"),
            country_code=data["country_code"],
            uen=data.get("uen"),
            lei=data.get("lei"),
            match_type=data.get("match_type", "exact"),
            confidence_score=data.get("confidence_score", 0.0),
            match_reasons=data.get("match_reasons", []),
            source=data.get("source", "registry"),
            external_data=data.get("external_data"),
            rank=data.get("rank", 0),
        )

    @classmethod
    def from_entity(
        cls, entity: Entity, match_type: str = "exact", confidence: float = 100.0
    ) -> "EntityCandidate":
        """Create candidate from existing Entity."""
        return cls(
            entity_id=entity.id,
            canonical_name=entity.canonical_name,
            legal_name=entity.legal_name,
            country_code=entity.country_code,
            uen=entity.uen,
            lei=entity.lei,
            match_type=match_type,
            confidence_score=confidence,
            match_reasons=[f"{match_type.title()} match on canonical name"],
            source="registry",
        )


@dataclass
class ResolutionResult:
    """
    Result of entity resolution attempt.

    Contains match status, candidates, and confirmation instructions.
    """

    status: ResolutionStatus
    query: str

    # Match results
    exact_match: Optional[EntityCandidate] = None
    candidates: list[EntityCandidate] = field(default_factory=list)

    # For conversation flow
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None

    # External search results (not yet in registry)
    external_results: list[EntityCandidate] = field(default_factory=list)

    # Timing
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolution_time_ms: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "query": self.query,
            "exact_match": self.exact_match.to_dict() if self.exact_match else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "requires_confirmation": self.requires_confirmation,
            "confirmation_message": self.confirmation_message,
            "external_results": [c.to_dict() for c in self.external_results],
            "resolved_at": self.resolved_at.isoformat(),
            "resolution_time_ms": self.resolution_time_ms,
        }


@dataclass
class EntityConfirmationState:
    """
    State for pending entity confirmation in conversation.

    Stored in session context when waiting for user confirmation.
    """

    query: str
    candidates: list[dict]  # EntityCandidate.to_dict()
    context: str  # "kyp", "credit_check", etc.
    resolution_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for session storage."""
        return {
            "query": self.query,
            "candidates": self.candidates,
            "context": self.context,
            "resolution_id": self.resolution_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityConfirmationState":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            query=data["query"],
            candidates=data["candidates"],
            context=data["context"],
            resolution_id=data["resolution_id"],
            created_at=created_at,
        )
