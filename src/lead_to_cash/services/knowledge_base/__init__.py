"""
Marine Engine Knowledge Base Service

A structured knowledge base for AI agents to analyze the medium-speed
high-power marine engine market (300-1000 RPM, 700-40,000 kW).

Capabilities:
- Entity recognition (engine model, manufacturer, power class, rpm class)
- Technical classification
- Market segmentation
- Competitor vs customer differentiation
- Structured reasoning for relevance scoring

This module is a SEPARATE track from core development.
"""

# Audit
from lead_to_cash.services.knowledge_base.audit import (
    AuditAction,
    AuditEvent,
    KBAuditLogger,
    get_kb_audit_logger,
)
from lead_to_cash.services.knowledge_base.constants import (
    CLASSIFICATION_SYSTEM_PROMPT,
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_REASONING_MODEL,
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    FUZZY_MATCH_THRESHOLD,
    KB_QUERY_SYSTEM_PROMPT,
    SEMANTIC_MATCH_THRESHOLD,
    TARGET_POWER_MAX_KW,
    TARGET_POWER_MIN_KW,
    TARGET_RPM_MAX,
    TARGET_RPM_MIN,
    TIER_1_MANUFACTURERS,
)
from lead_to_cash.services.knowledge_base.data_enrichment import (
    DataEnrichmentService,
    get_data_enrichment_service,
    initialize_data_enrichment_service,
)
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
    initialize_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.embedding_service import (
    KBEmbeddingService,
    get_kb_embedding_service,
    initialize_kb_embedding_service,
)
from lead_to_cash.services.knowledge_base.entity_resolver import (
    EntityResolver,
    get_entity_resolver,
    initialize_entity_resolver,
)

# Exceptions
from lead_to_cash.services.knowledge_base.exceptions import (
    KBCircuitBreakerError,
    KBConfigurationError,
    KBConnectionError,
    KBException,
    KBNotFoundError,
    KBRateLimitError,
    KBTimeoutError,
    KBValidationError,
)

# Health
from lead_to_cash.services.knowledge_base.health import (
    ComponentHealth,
    HealthProbes,
    HealthResponse,
    HealthStatus,
)
from lead_to_cash.services.knowledge_base.integration import (
    EnrichedDocument,
    EnrichedOpportunity,
    KBIntegrationService,
    get_kb_integration_service,
    initialize_kb_integration_service,
)

# Metrics
from lead_to_cash.services.knowledge_base.metrics import (
    KBMetrics,
    get_kb_metrics,
)
from lead_to_cash.services.knowledge_base.models import (
    Application,
    ApplicationType,
    ArticleEntity,
    ArticleScore,
    ClassifiedArticle,
    EngineApplicationMap,
    EngineCompetitorMap,
    EngineModel,
    EngineSeries,
    EntityAlias,
    ExtractedEntity,
    FuelType,
    Manufacturer,
    ManufacturerTier,
    MarketSegment,
    MarketSegmentType,
    PowerClass,
    RelevanceClassification,
    ResolvedEntity,
    RPMClass,
)
from lead_to_cash.services.knowledge_base.scorer import (
    RelevanceScorer,
    ScoreBreakdown,
    ScoringInput,
    get_relevance_scorer,
)
from lead_to_cash.services.knowledge_base.seed_data import (
    seed_aliases,
    seed_engine_models,
    seed_engine_series,
    seed_knowledge_base,
    seed_manufacturers,
)

# Tracing
from lead_to_cash.services.knowledge_base.tracing import (
    KBTracer,
    configure_kb_tracing,
    get_kb_tracer,
    trace_operation,
)

# Validation
from lead_to_cash.services.knowledge_base.validation import (
    VALID_ENTITY_TYPES,
    validate_embedding,
    validate_entity_type,
    validate_float_range,
    validate_id,
    validate_list,
    validate_positive_int,
    validate_text,
)

__all__ = [
    # DataFlow Models
    "Manufacturer",
    "EngineSeries",
    "EngineModel",
    "Application",
    "MarketSegment",
    "EngineApplicationMap",
    "EngineCompetitorMap",
    "EntityAlias",
    "ArticleEntity",
    "ArticleScore",
    # Helper Models
    "ExtractedEntity",
    "ResolvedEntity",
    "ClassifiedArticle",
    # Enums
    "RPMClass",
    "PowerClass",
    "FuelType",
    "MarketSegmentType",
    "ApplicationType",
    "RelevanceClassification",
    "ManufacturerTier",
    # Database
    "KnowledgeBaseDatabase",
    "get_knowledge_base_db",
    "initialize_knowledge_base_db",
    # Embedding Service
    "KBEmbeddingService",
    "get_kb_embedding_service",
    "initialize_kb_embedding_service",
    # Entity Resolver
    "EntityResolver",
    "get_entity_resolver",
    "initialize_entity_resolver",
    # Scorer
    "RelevanceScorer",
    "get_relevance_scorer",
    "ScoreBreakdown",
    "ScoringInput",
    # Seed Data
    "seed_knowledge_base",
    "seed_manufacturers",
    "seed_engine_series",
    "seed_engine_models",
    "seed_aliases",
    # Data Enrichment
    "DataEnrichmentService",
    "get_data_enrichment_service",
    "initialize_data_enrichment_service",
    # Integration Service
    "KBIntegrationService",
    "get_kb_integration_service",
    "initialize_kb_integration_service",
    "EnrichedOpportunity",
    "EnrichedDocument",
    # Constants
    "ENTITY_EXTRACTION_SYSTEM_PROMPT",
    "CLASSIFICATION_SYSTEM_PROMPT",
    "KB_QUERY_SYSTEM_PROMPT",
    "DEFAULT_EXTRACTION_MODEL",
    "DEFAULT_REASONING_MODEL",
    "TARGET_RPM_MIN",
    "TARGET_RPM_MAX",
    "TARGET_POWER_MIN_KW",
    "TARGET_POWER_MAX_KW",
    "TIER_1_MANUFACTURERS",
    "FUZZY_MATCH_THRESHOLD",
    "SEMANTIC_MATCH_THRESHOLD",
    # Exceptions
    "KBException",
    "KBValidationError",
    "KBNotFoundError",
    "KBTimeoutError",
    "KBConnectionError",
    "KBRateLimitError",
    "KBCircuitBreakerError",
    "KBConfigurationError",
    # Validation
    "validate_text",
    "validate_entity_type",
    "validate_embedding",
    "validate_positive_int",
    "validate_float_range",
    "validate_list",
    "validate_id",
    "VALID_ENTITY_TYPES",
    # Audit
    "KBAuditLogger",
    "get_kb_audit_logger",
    "AuditEvent",
    "AuditAction",
    # Tracing
    "KBTracer",
    "get_kb_tracer",
    "configure_kb_tracing",
    "trace_operation",
    # Metrics
    "KBMetrics",
    "get_kb_metrics",
    # Health
    "HealthProbes",
    "HealthStatus",
    "ComponentHealth",
    "HealthResponse",
]
