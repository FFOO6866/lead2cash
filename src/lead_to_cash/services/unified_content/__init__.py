"""
Unified Content Services

"Scrape Once, Use Many" architecture for maritime intelligence.

Components:
- models.py: Unified content data models
- database.py: PostgreSQL storage with pgvector
- embedding_cache.py: Shared embedding cache (eliminates 3x API calls)
- content_processor.py: Unified entity extraction and KB resolution
- ingestion.py: Unified content ingestion pipeline (connects all collectors)
"""

from lead_to_cash.services.unified_content.content_processor import (
    ContentProcessor,
    ProcessingResult,
    get_processor,
    process_content,
    process_content_batch,
)
from lead_to_cash.services.unified_content.database import (
    UnifiedContentDatabase,
    get_unified_content_db,
    initialize_unified_content_db,
)

# Re-export key components for convenience
from lead_to_cash.services.unified_content.embedding_cache import (
    SharedEmbeddingService,
    embed_text,
    embed_texts,
    get_embedding_stats,
    get_shared_embedding_service,
)
from lead_to_cash.services.unified_content.ingestion import (
    IngestionResult,
    UnifiedIngestionPipeline,
    get_pipeline,
    ingest_newsapi,
    ingest_press_rooms,
    ingest_rss,
    run_full_ingestion,
    run_priority_ingestion,
)
from lead_to_cash.services.unified_content.models import (
    ContentClassification,
    ContentPurpose,
    ContentSource,
    EntityType,
    ExtractedEntity,
    IngestionJob,
    SourceTier,
    UnifiedContent,
)

__all__ = [
    # Models
    "UnifiedContent",
    "ContentSource",
    "ContentPurpose",
    "EntityType",
    "SourceTier",
    "ExtractedEntity",
    "ContentClassification",
    "IngestionJob",
    # Embedding
    "SharedEmbeddingService",
    "get_shared_embedding_service",
    "embed_text",
    "embed_texts",
    "get_embedding_stats",
    # Database
    "UnifiedContentDatabase",
    "get_unified_content_db",
    "initialize_unified_content_db",
    # Processor
    "ContentProcessor",
    "ProcessingResult",
    "get_processor",
    "process_content",
    "process_content_batch",
    # Ingestion
    "IngestionResult",
    "UnifiedIngestionPipeline",
    "get_pipeline",
    "run_full_ingestion",
    "run_priority_ingestion",
    "ingest_newsapi",
    "ingest_rss",
    "ingest_press_rooms",
]
