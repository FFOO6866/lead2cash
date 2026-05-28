"""
Marine Engine Knowledge Base - DataFlow Models

Knowledge base for marine engine manufacturers, series, models, and applications
with pgvector support for semantic search and fuzzy matching.

Domain Focus:
- Medium speed: 300-1000 rpm (target range)
- Power range: 700 kW - 40,000 kW
- Markets: Marine transportation, offshore oil & gas, FPSO, offshore power generation

Tables (10 models = 110 auto-generated DataFlow nodes):
- manufacturers: Engine manufacturers (Wärtsilä, MAN, Caterpillar, etc.)
- engine_series: Engine series/brands under manufacturers
- engine_models: Specific engine models with specifications
- applications: Marine application types (Ferry, OSV, FPSO, etc.)
- market_segments: Market segments with priority scoring
- engine_application_map: Many-to-many for engine-application relationships
- engine_competitor_map: Many-to-many for competitive engine relationships
- entity_aliases: Unified alias table with embeddings for fuzzy matching
- article_entities: Links articles to knowledge base entities
- article_scores: Article classification scores
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

# =============================================================================
# ENUMS FOR CLASSIFICATION
# =============================================================================


class RPMClass(str, Enum):
    """RPM classification per requirements."""

    HIGH_SPEED = "high_speed"  # >1000 rpm (IGNORE)
    MEDIUM_SPEED = "medium_speed"  # 300-1000 rpm (TARGET)
    LOW_SPEED = "low_speed"  # <300 rpm (IGNORE)

    @classmethod
    def from_rpm(cls, rpm: int) -> "RPMClass":
        """Classify RPM value."""
        if rpm > 1000:
            return cls.HIGH_SPEED
        elif rpm >= 300:
            return cls.MEDIUM_SPEED
        else:
            return cls.LOW_SPEED

    @property
    def is_target(self) -> bool:
        """Check if this RPM class is in target range."""
        return self == RPMClass.MEDIUM_SPEED


class PowerClass(str, Enum):
    """Power classification per requirements."""

    SMALL = "small"  # 700-2000 kW
    MID = "mid"  # 2000-10000 kW
    HIGH = "high"  # 10000-25000 kW
    ULTRA_HIGH = "ultra_high"  # 25000-40000 kW
    OUT_OF_RANGE = "out_of_range"  # Outside target range

    @classmethod
    def from_kw(cls, power_kw: float) -> "PowerClass":
        """Classify power value in kW."""
        if power_kw < 700:
            return cls.OUT_OF_RANGE
        elif power_kw <= 2000:
            return cls.SMALL
        elif power_kw <= 10000:
            return cls.MID
        elif power_kw <= 25000:
            return cls.HIGH
        elif power_kw <= 40000:
            return cls.ULTRA_HIGH
        else:
            return cls.OUT_OF_RANGE

    @property
    def is_target(self) -> bool:
        """Check if this power class is in target range."""
        return self != PowerClass.OUT_OF_RANGE


class FuelType(str, Enum):
    """Engine fuel types."""

    DIESEL = "diesel"
    HFO = "hfo"  # Heavy Fuel Oil
    GAS = "gas"
    LNG = "lng"
    DUAL_FUEL = "dual_fuel"
    METHANOL = "methanol"
    AMMONIA = "ammonia"


class MarketSegmentType(str, Enum):
    """Market segments per requirements."""

    MARINE_TRANSPORTATION = "marine_transportation"
    OFFSHORE_OIL_GAS = "offshore_oil_gas"
    FPSO_OFFSHORE_PRODUCTION = "fpso_offshore_production"
    MARINE_POWER_GENERATION = "marine_power_generation"
    LAND_POWER_PLANT = "land_power_plant"  # Low priority


class ApplicationType(str, Enum):
    """Application types for marine engines."""

    PROPULSION = "propulsion"
    GENSET = "genset"
    AUXILIARY = "auxiliary"
    OFFSHORE_POWER = "offshore_power"
    FPSO = "fpso"
    DRILLING = "drilling"


class RelevanceClassification(str, Enum):
    """Article relevance classification per requirements."""

    HIGH_PRIORITY = "high_priority"  # Score >= 70
    MONITOR = "monitor"  # Score 40-69
    IGNORE = "ignore"  # Score < 40

    @classmethod
    def from_score(cls, score: float) -> "RelevanceClassification":
        """Classify based on total score."""
        if score >= 70:
            return cls.HIGH_PRIORITY
        elif score >= 40:
            return cls.MONITOR
        else:
            return cls.IGNORE


class ManufacturerTier(int, Enum):
    """Manufacturer tier classification."""

    TIER_1 = 1  # Global players (Wärtsilä, MAN, Caterpillar, etc.)
    TIER_2 = 2  # Regional players
    TIER_3 = 3  # Niche players


# =============================================================================
# DATAFLOW MODELS
# =============================================================================


@dataclass
class Manufacturer:
    """
    Marine engine manufacturer.

    Examples: Wärtsilä, MAN Energy Solutions, Caterpillar/MaK, HD Hyundai

    Auto-generates 11 DataFlow nodes:
    - ManufacturerCreateNode, ManufacturerReadNode, ManufacturerUpdateNode
    - ManufacturerDeleteNode, ManufacturerListNode, ManufacturerCountNode
    - ManufacturerUpsertNode, ManufacturerBulkCreateNode, ManufacturerBulkUpdateNode
    - ManufacturerBulkDeleteNode, ManufacturerBulkUpsertNode
    """

    id: str  # UUID string
    name: str  # Official company name
    country: str  # Country of origin
    tier: int = ManufacturerTier.TIER_1.value  # 1=Global, 2=Regional, 3=Niche
    website: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "tier": self.tier,
            "website": self.website,
            "description": self.description,
            "is_active": self.is_active,
        }


@dataclass
class EngineSeries:
    """
    Engine series/brand under a manufacturer.

    Examples: Wärtsilä 31, MAN 32/44CR, MaK M43C, Bergen B32:40

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    manufacturer_id: str  # FK to Manufacturer
    brand: str  # Brand name (e.g., "Wärtsilä", "MaK", "Bergen")
    series_name: str  # Series identifier (e.g., "31", "32/44CR", "M43C")
    description: Optional[str] = None
    generation: Optional[int] = None  # Engine generation (1, 2, 3...)
    year_introduced: Optional[int] = None
    year_discontinued: Optional[int] = None
    is_current: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "manufacturer_id": self.manufacturer_id,
            "brand": self.brand,
            "series_name": self.series_name,
            "description": self.description,
            "generation": self.generation,
            "year_introduced": self.year_introduced,
            "year_discontinued": self.year_discontinued,
            "is_current": self.is_current,
        }


@dataclass
class EngineModel:
    """
    Specific engine model with full specifications.

    Examples: Wärtsilä 31DF (720/750 rpm, 4,600-10,400 kW)

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    series_id: str  # FK to EngineSeries
    model_name: str  # Full model designation

    # RPM specifications (target: 300-1000 rpm)
    rpm_min: Optional[int] = None
    rpm_max: Optional[int] = None

    # Power specifications (target: 700-40,000 kW)
    power_min_kw: Optional[float] = None
    power_max_kw: Optional[float] = None

    # Configuration
    cylinders: Optional[int] = None
    configuration: Optional[str] = None  # "V", "inline", "L"
    displacement_liters: Optional[float] = None

    # Fuel types (JSON array as string)
    fuel_types: Optional[str] = None  # JSON: ["diesel", "gas", "dual_fuel"]

    # Weight and dimensions
    dry_weight_kg: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None

    # Classification
    emission_tier: Optional[str] = None  # "IMO Tier II", "IMO Tier III"
    is_current_production: bool = True

    # Metadata
    data_source: Optional[str] = None
    data_confidence: float = 0.8
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "series_id": self.series_id,
            "model_name": self.model_name,
            "rpm_min": self.rpm_min,
            "rpm_max": self.rpm_max,
            "power_min_kw": self.power_min_kw,
            "power_max_kw": self.power_max_kw,
            "cylinders": self.cylinders,
            "configuration": self.configuration,
            "displacement_liters": self.displacement_liters,
            "fuel_types": self.fuel_types,
            "dry_weight_kg": self.dry_weight_kg,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "emission_tier": self.emission_tier,
            "is_current_production": self.is_current_production,
            "data_source": self.data_source,
            "data_confidence": self.data_confidence,
        }

    def get_fuel_types_list(self) -> list[str]:
        """Parse fuel_types JSON to list."""
        if not self.fuel_types:
            return []
        try:
            return json.loads(self.fuel_types)
        except json.JSONDecodeError:
            return []

    def get_rpm_class(self) -> RPMClass:
        """Get RPM classification based on rpm_max."""
        if self.rpm_max:
            return RPMClass.from_rpm(self.rpm_max)
        return RPMClass.MEDIUM_SPEED  # Default

    def get_power_class(self) -> PowerClass:
        """Get power classification based on power_max_kw."""
        if self.power_max_kw:
            return PowerClass.from_kw(self.power_max_kw)
        return PowerClass.MID  # Default


@dataclass
class Application:
    """
    Marine application types.

    Examples: Propulsion, Genset, FPSO, Offshore Power

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    name: str  # Application name
    code: Optional[str] = None  # Short code (e.g., "FPSO", "OSV")
    description: Optional[str] = None
    category: Optional[str] = None  # "commercial", "offshore", "naval"
    typical_power_range_min_kw: Optional[float] = None
    typical_power_range_max_kw: Optional[float] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "category": self.category,
            "typical_power_range_min_kw": self.typical_power_range_min_kw,
            "typical_power_range_max_kw": self.typical_power_range_max_kw,
            "is_active": self.is_active,
        }


@dataclass
class MarketSegment:
    """
    Market segments for opportunity prioritization.

    Per requirements:
    - Marine transportation
    - Offshore oil and gas
    - FPSO / offshore production
    - Marine power generation
    - Land power plants (low priority)

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    name: str
    segment_type: str  # MarketSegmentType value
    description: Optional[str] = None
    priority_score: int = 50  # 1-100, higher = more important
    growth_potential: Optional[str] = None  # "high", "medium", "low"
    focus_regions: Optional[str] = None  # JSON array of regions
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "name": self.name,
            "segment_type": self.segment_type,
            "description": self.description,
            "priority_score": self.priority_score,
            "growth_potential": self.growth_potential,
            "focus_regions": self.focus_regions,
            "is_active": self.is_active,
        }


@dataclass
class EngineApplicationMap:
    """
    Many-to-many mapping between engines and applications.

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    engine_model_id: str  # FK to EngineModel
    application_id: str  # FK to Application
    suitability_score: float = 0.5  # 0-1, how suitable
    is_primary_application: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "engine_model_id": self.engine_model_id,
            "application_id": self.application_id,
            "suitability_score": self.suitability_score,
            "is_primary_application": self.is_primary_application,
            "notes": self.notes,
        }


@dataclass
class EngineCompetitorMap:
    """
    Many-to-many mapping for competitive engine relationships.

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    engine_model_id: str  # FK to EngineModel (primary)
    competitor_engine_id: str  # FK to EngineModel (competitor)
    relationship_type: str = "direct"  # "direct", "indirect", "potential"
    overlap_score: float = 0.5  # 0-1, market overlap
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "engine_model_id": self.engine_model_id,
            "competitor_engine_id": self.competitor_engine_id,
            "relationship_type": self.relationship_type,
            "overlap_score": self.overlap_score,
            "notes": self.notes,
        }


@dataclass
class EntityAlias:
    """
    Unified alias table for fuzzy matching across all entity types.

    Stores alternative names, abbreviations, and common misspellings
    with embedding vectors for semantic search.

    Examples:
    - "W31" -> Wärtsilä 31 (engine_series)
    - "Cat" -> Caterpillar (manufacturer)
    - "MaK" -> Caterpillar MaK (manufacturer)
    - "HiMSEN" -> HD Hyundai HiMSEN (manufacturer)

    Auto-generates 11 DataFlow nodes.
    Note: Embedding vector stored via SQL migration (pgvector).
    """

    id: str
    entity_type: str  # "manufacturer", "engine_series", "engine_model", "application"
    entity_id: str  # FK to the referenced entity
    alias_text: str  # The alias/alternative name
    alias_type: str = (
        "common_name"  # "common_name", "abbreviation", "misspelling", "former_name"
    )
    normalized_text: Optional[str] = None  # Lowercase, stripped for exact matching
    source: str = "manual"  # "manual", "extracted", "learned"
    confidence: float = 1.0  # 0-1
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "alias_text": self.alias_text,
            "alias_type": self.alias_type,
            "normalized_text": self.normalized_text or self.alias_text.lower().strip(),
            "source": self.source,
            "confidence": self.confidence,
            "is_active": self.is_active,
        }


@dataclass
class ArticleEntity:
    """
    Links articles to knowledge base entities.

    When an article mentions a manufacturer, engine, or application,
    this table captures that relationship with confidence scores.

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    article_id: str  # FK to marine_articles or external article ID
    entity_type: str  # "manufacturer", "engine_series", "engine_model", "application"
    entity_id: str  # FK to the referenced entity
    confidence: float = 0.5  # 0-1, extraction confidence
    mention_count: int = 1  # Times mentioned in article
    context_snippet: Optional[str] = None  # Text excerpt where found
    extraction_method: str = "llm"  # "llm", "regex", "manual"
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "article_id": self.article_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "confidence": self.confidence,
            "mention_count": self.mention_count,
            "context_snippet": self.context_snippet,
            "extraction_method": self.extraction_method,
        }


@dataclass
class ArticleScore:
    """
    Article classification scores for opportunity assessment.

    Scoring per requirements:
    - Technical: Engine model (+40), Tier-1 (+20), Power>10kW (+15), RPM<=750 (+10)
    - Market: Offshore O&G (+30), Marine power gen (+25), Marine transport (+20)
    - Commercial: New order (+30), Retrofit (+25), Launch (+20), Regulatory (+15)

    Classification thresholds:
    - HIGH_PRIORITY: >= 70
    - MONITOR: 40-69
    - IGNORE: < 40

    Auto-generates 11 DataFlow nodes.
    """

    id: str
    article_id: str  # FK to marine_articles or external article ID

    # Component scores (0-100 each)
    technical_score: float = 0.0
    market_score: float = 0.0
    commercial_score: float = 0.0

    # Computed total
    total_score: float = 0.0

    # Classification
    classification: str = RelevanceClassification.IGNORE.value

    # Detailed breakdown (JSON)
    score_breakdown: Optional[str] = None  # JSON with individual signals

    # Metadata
    scoring_model_version: str = "v1"
    scored_at: Optional[datetime] = None
    score_explanation: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFlow operations."""
        return {
            "id": self.id,
            "article_id": self.article_id,
            "technical_score": self.technical_score,
            "market_score": self.market_score,
            "commercial_score": self.commercial_score,
            "total_score": self.total_score,
            "classification": self.classification,
            "score_breakdown": self.score_breakdown,
            "scoring_model_version": self.scoring_model_version,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
            "score_explanation": self.score_explanation,
        }

    def get_classification(self) -> RelevanceClassification:
        """Get classification enum from string."""
        return RelevanceClassification(self.classification)

    def update_classification(self) -> None:
        """Update classification based on total_score."""
        self.classification = RelevanceClassification.from_score(self.total_score).value


# =============================================================================
# HELPER DATA CLASSES FOR AGENT USE
# =============================================================================


@dataclass
class ExtractedEntity:
    """Entity extracted from article content (before KB resolution)."""

    text: str  # Raw text as found in article
    entity_type: str  # Guessed type: manufacturer, engine, etc.
    confidence: float  # Extraction confidence
    context: Optional[str] = None  # Surrounding text

    # Optional parsed values
    rpm: Optional[int] = None
    power_kw: Optional[float] = None
    fuel_type: Optional[str] = None


@dataclass
class ResolvedEntity:
    """Entity resolved against knowledge base."""

    extracted: ExtractedEntity  # Original extraction
    entity_type: str  # Confirmed type
    entity_id: str  # KB entity ID
    entity_name: str  # Canonical name from KB
    match_type: str  # "exact", "alias", "fuzzy", "semantic"
    match_confidence: float  # Resolution confidence

    # For engine models, include classifications
    rpm_class: Optional[RPMClass] = None
    power_class: Optional[PowerClass] = None
    manufacturer_tier: Optional[ManufacturerTier] = None


@dataclass
class ClassifiedArticle:
    """Final output from article processing pipeline."""

    article_id: str
    article_title: str
    article_summary: str

    # Extracted and resolved entities
    entities: list[ResolvedEntity] = field(default_factory=list)

    # Classifications
    rpm_classes: list[RPMClass] = field(default_factory=list)
    power_classes: list[PowerClass] = field(default_factory=list)
    fuel_types: list[FuelType] = field(default_factory=list)
    market_segments: list[MarketSegmentType] = field(default_factory=list)
    applications: list[ApplicationType] = field(default_factory=list)

    # Commercial signals detected
    commercial_signals: list[str] = field(default_factory=list)

    # Scores
    technical_score: float = 0.0
    market_score: float = 0.0
    commercial_score: float = 0.0
    total_score: float = 0.0

    # Final classification
    classification: RelevanceClassification = RelevanceClassification.IGNORE

    # Affected competitors (manufacturers)
    affected_competitors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for output."""
        return {
            "article_id": self.article_id,
            "article_title": self.article_title,
            "article_summary": self.article_summary,
            "entities": [
                {
                    "text": e.extracted.text,
                    "type": e.entity_type,
                    "name": e.entity_name,
                    "match_type": e.match_type,
                    "confidence": e.match_confidence,
                }
                for e in self.entities
            ],
            "classifications": {
                "rpm_classes": [r.value for r in self.rpm_classes],
                "power_classes": [p.value for p in self.power_classes],
                "fuel_types": [f.value for f in self.fuel_types],
                "market_segments": [m.value for m in self.market_segments],
                "applications": [a.value for a in self.applications],
            },
            "commercial_signals": self.commercial_signals,
            "scores": {
                "technical": self.technical_score,
                "market": self.market_score,
                "commercial": self.commercial_score,
                "total": self.total_score,
            },
            "classification": self.classification.value,
            "affected_competitors": self.affected_competitors,
        }
