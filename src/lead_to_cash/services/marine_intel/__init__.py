"""
Marine Sales Intelligence Service

Daily research service for identifying RRPS marine engine sales opportunities
in Singapore and Asia-Pacific markets.

Tables:
- Article: Source documents with URL hash deduplication
- Opportunity: Sales signals extracted from articles
- Account: Company tracking with mention counts across articles
- ResearchJob: Processing job tracking

Target Market: Singapore and Asia-Pacific
Priority Sectors: Marine transportation, Offshore oil & gas, Marine engineering
"""

from lead_to_cash.services.marine_intel.database import (
    MarineIntelDatabase,
    get_marine_intel_db,
    initialize_marine_intel_db,
)
from lead_to_cash.services.marine_intel.embedding_service import (
    MarineEmbeddingService,
    close_marine_embedding_service,
    get_marine_embedding_service,
    initialize_marine_embedding_service,
)
from lead_to_cash.services.marine_intel.insight_parser import (
    InsightParser,
    get_insight_parser,
)
from lead_to_cash.services.marine_intel.models import (  # Enums; Models; Query patterns and sources
    MANDATORY_SOURCES,
    QUERY_PATTERNS,
    Account,
    Article,
    ArticleAccountMention,
    MarineOpportunity,
    Region,
    ResearchJob,
    SalesSignal,
    Sector,
    SourceCategory,
    VesselType,
)
from lead_to_cash.services.marine_intel.retention_service import (
    RetentionJobResult,
    RetentionPolicy,
    RetentionService,
    get_retention_service,
    run_retention_job,
)
from lead_to_cash.services.marine_intel.scheduler import (
    daily_marine_intel_job,
    embedding_backfill_job,
    retention_cleanup_job,
    run_historical_backfill,
    run_manual_embedding_backfill,
    run_manual_research,
    run_manual_retention_cleanup,
    run_manual_targeted_research,
    start_marine_scheduler,
    stop_marine_scheduler,
)
from lead_to_cash.services.marine_intel.structured_insight import (
    CompanyInfo,
    DataQuality,
    DealDetails,
    EngineRequirement,
    InsightCollectionResponse,
    Priority,
    SalesAction,
    SalesSignalType,
    SourceInfo,
    SourceReliability,
    StructuredInsight,
)
from lead_to_cash.services.marine_intel.validation import (  # Enums for validation; Query parameter validators; Create/Update validators; Helper functions
    AccountCreate,
    AccountCRMUpdate,
    AccountQueryParams,
    ArticleCreate,
    ArticleQueryParams,
    DateRangeParams,
    JobQueryParams,
    OpportunityCreate,
    OpportunityQueryParams,
    OpportunityStatusUpdate,
    PaginationParams,
    PriorityUpdate,
    TargetedResearchRequest,
    ValidJobStatus,
    ValidJobType,
    ValidRegion,
    ValidSalesSignal,
    ValidSector,
    ValidStatus,
    ValidVesselType,
    sanitize_string,
    validate_days_param,
    validate_id,
    validate_limit_param,
    validate_offset_param,
)

__all__ = [
    # Enums
    "SalesSignal",
    "Region",
    "VesselType",
    "Sector",
    "SourceCategory",
    # Data models
    "MarineOpportunity",
    "Article",
    "Account",
    "ArticleAccountMention",
    "ResearchJob",
    # Query patterns and sources
    "QUERY_PATTERNS",
    "MANDATORY_SOURCES",
    # Database
    "MarineIntelDatabase",
    "get_marine_intel_db",
    "initialize_marine_intel_db",
    # Embedding Service
    "MarineEmbeddingService",
    "get_marine_embedding_service",
    "close_marine_embedding_service",
    "initialize_marine_embedding_service",
    # Retention Service
    "RetentionService",
    "RetentionPolicy",
    "RetentionJobResult",
    "get_retention_service",
    "run_retention_job",
    # Scheduler
    "start_marine_scheduler",
    "stop_marine_scheduler",
    "run_manual_research",
    "run_manual_targeted_research",
    "run_historical_backfill",
    "daily_marine_intel_job",
    "embedding_backfill_job",
    "retention_cleanup_job",
    "run_manual_embedding_backfill",
    "run_manual_retention_cleanup",
    # Validation - Enums
    "ValidRegion",
    "ValidSector",
    "ValidSalesSignal",
    "ValidVesselType",
    "ValidStatus",
    "ValidJobType",
    "ValidJobStatus",
    # Validation - Query params
    "PaginationParams",
    "DateRangeParams",
    "OpportunityQueryParams",
    "ArticleQueryParams",
    "AccountQueryParams",
    "JobQueryParams",
    # Validation - Create/Update
    "ArticleCreate",
    "OpportunityCreate",
    "OpportunityStatusUpdate",
    "AccountCreate",
    "AccountCRMUpdate",
    "PriorityUpdate",
    "TargetedResearchRequest",
    # Validation - Helpers
    "validate_id",
    "validate_days_param",
    "validate_limit_param",
    "validate_offset_param",
    "sanitize_string",
    # Structured Insights
    "StructuredInsight",
    "InsightCollectionResponse",
    "SalesSignalType",
    "Priority",
    "SourceReliability",
    "CompanyInfo",
    "DealDetails",
    "EngineRequirement",
    "SalesAction",
    "DataQuality",
    "SourceInfo",
    # Insight Parser
    "InsightParser",
    "get_insight_parser",
]
