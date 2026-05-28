# ADR-005: Unified Content Architecture - Scrape Once, Use Many

**Status:** Accepted
**Date:** 2026-01-21
**Deciders:** Engineering Team, AI Team
**Consulted:** Sales Operations, Intelligence Analysts
**Informed:** All AI Agents, Integration Teams

## Context

The current content ingestion and intelligence pipeline has critical architectural inefficiencies that cause:

1. **3x Duplicate Embeddings**: The same content is embedded independently by:
   - `competitor_intel/embedding_service.py`
   - `marine_intel/embedding_service.py`
   - `knowledge_base/embedding_service.py`

2. **3x Duplicate Entity Extraction**: Same entities are extracted 3 times:
   - CompetitorIntelAgent extracts competitor mentions
   - MarineIntelAgent extracts vessel/operator mentions
   - KnowledgeBaseAgent extracts product mentions

3. **Optional KB Integration**: In `competitor_intel_agent.py` lines 79-84, KB integration is wrapped in `try/except ImportError` making it OPTIONAL. This leads to unlinked competitor intel.

4. **No URL Deduplication**: The same news article can be stored 3 times in different tables with different processing.

5. **Inconsistent Source Coverage**: NewsAPI, RSS, Perplexity, and press room scraping were not unified.

### Business Impact

| Issue | Impact |
|-------|--------|
| 3x embedding API calls | 3x OpenAI costs (~$300/month wasted) |
| 3x entity extraction | Inconsistent entity resolution across services |
| Optional KB linking | No cross-service correlation (competitor intel not linked to products) |
| No deduplication | Same content processed multiple times |
| Separate pipelines | Maintenance burden, hard to add new sources |

## Decision Drivers

* **Single Source of Truth**: All content must flow through one ingestion pipeline
* **Cost Efficiency**: Eliminate duplicate API calls
* **Mandatory KB Integration**: All content MUST be linked to Knowledge Base entities
* **Consistent Entity Resolution**: Same entity should resolve identically across all services
* **Extensible Sources**: Easy to add new sources (RSS, Perplexity, press rooms)
* **Production Ready**: No mocks, real data, observable metrics

## Considered Options

### Option 1: Patch Existing Services (Add caching)

Add a shared cache to existing embedding services.

* Bad, because doesn't solve duplicate entity extraction
* Bad, because KB integration remains optional
* Bad, because increases complexity without solving root cause

### Option 2: Unified Content Layer (Chosen)

Create `services/unified_content/` module that:
- Provides single ingestion point for all sources
- Caches embeddings by content hash
- Performs single entity extraction with mandatory KB resolution
- Stores all content in unified PostgreSQL table with pgvector

* Good, because eliminates all duplication
* Good, because enforces mandatory KB linking
* Good, because centralizes source management
* Good, because provides single metrics/monitoring point

### Option 3: Event-Driven Architecture (Kafka/RabbitMQ)

Use message queues for content processing pipeline.

* Good, because highly scalable
* Bad, because adds operational complexity
* Bad, because team not experienced with message queues
* Bad, because overkill for current volume

## Decision Outcome

Chosen option: **Option 2 - Unified Content Layer**, because it solves all problems with minimal complexity increase.

### New Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCRAPE ONCE (Unified Ingestion)             │
├─────────────────────────────────────────────────────────────────┤
│  NewsAPI → RSS → Perplexity → Press Rooms                       │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              UnifiedContent Store                          │  │
│  │  • URL hash deduplication (SHA-256)                        │  │
│  │  • Single embedding (via SharedEmbeddingService)           │  │
│  │  • Single entity extraction (regex + LLM)                  │  │
│  │  • Mandatory KB resolution                                  │  │
│  │  • Multi-purpose classification                             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           ↓                                      │
├─────────────────────────────────────────────────────────────────┤
│                     USE MANY (Multi-Purpose Consumption)        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Competitor  │  │  Marine     │  │ Product Fit │              │
│  │   Intel     │  │   Intel     │  │  (KB match) │              │
│  │  (threats)  │  │   (opps)    │  │             │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └────────────────┼────────────────┘                      │
│                          ↓                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Knowledge Base (Central Hub)                  │  │
│  │  kb_manufacturers → kb_engine_models → kb_engine_ratings   │  │
│  │  kb_article_entities (MANDATORY linking)                   │  │
│  │  kb_rating_competitor_map → kb_competitor_engagements      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### New Components

#### 1. UnifiedContent Model

The atomic unit for all ingested content:

| Field | Type | Description |
|-------|------|-------------|
| id | VARCHAR(36) | Primary key (UUID) |
| url | TEXT | Source URL |
| url_hash | VARCHAR(64) | SHA-256 hash for deduplication |
| title | TEXT | Content title |
| content | TEXT | Full content |
| summary | TEXT | AI-generated summary |
| source_name | VARCHAR(255) | e.g., "Maritime Executive" |
| source_type | VARCHAR(50) | newsapi, rss_feed, perplexity, press_room |
| source_tier | INTEGER | 1-4 credibility tier |
| published_date | TIMESTAMPTZ | When published |
| embedding | vector(1536) | text-embedding-3-small |
| purposes | JSONB | ["competitor_intel", "marine_intel", ...] |
| classification | JSONB | Multi-purpose scoring |
| kb_linked | BOOLEAN | Mandatory KB linking flag |
| is_processed | BOOLEAN | Processing completion flag |

#### 2. ContentSource Enum

```python
class ContentSource(str, Enum):
    GENERAL = "general"
    NEWSAPI = "newsapi"
    RSS_FEED = "rss_feed"
    PERPLEXITY = "perplexity"
    PRESS_ROOM = "press_room"
    COMPETITOR_WEBSITE = "competitor_website"
    REGULATORY_ANNOUNCEMENT = "regulatory_announcement"
```

#### 3. ContentPurpose Enum

```python
class ContentPurpose(str, Enum):
    COMPETITOR_INTEL = "competitor_intel"
    MARINE_INTEL = "marine_intel"
    REGULATORY_INTEL = "regulatory_intel"
    PRODUCT_INTEL = "product_intel"
    MARKET_INTEL = "market_intel"
    GENERAL = "general"
```

#### 4. ContentClassification Model

Multi-purpose scoring for each content item:

| Field | Type | Description |
|-------|------|-------------|
| competitor_threat_score | INTEGER | 0-100, threat level |
| competitor_name | VARCHAR | Which competitor |
| sales_opportunity_score | INTEGER | 0-100, opportunity level |
| sales_signals | JSONB | ["newbuild", "retrofit", ...] |
| technical_score | INTEGER | 0-40, KB technical relevance |
| market_score | INTEGER | 0-30, market relevance |
| commercial_score | INTEGER | 0-30, commercial relevance |
| kb_relevance_total | INTEGER | 0-100, sum of above |
| priority | INTEGER | 1-10, processing priority |
| requires_review | BOOLEAN | Needs human attention |

#### 5. SharedEmbeddingService

Single embedding service for entire application:

```python
from lead_to_cash.services.unified_content import (
    SharedEmbeddingService,
    get_shared_embedding_service,
)

service = get_shared_embedding_service()
embedding = await service.embed_text("Content to embed")

# Cache stats
stats = service.get_stats()
# {
#   "total_requests": 1000,
#   "cache_hits": 850,
#   "cache_hit_rate": "85.0%",
#   "api_calls_saved": 850,
#   ...
# }
```

#### 6. UnifiedIngestionPipeline

Single entry point for all content sources:

```python
from lead_to_cash.services.unified_content import (
    UnifiedIngestionPipeline,
    run_full_ingestion,
)

# Full ingestion from all sources
results = await run_full_ingestion()

# Priority ingestion (subset)
results = await run_priority_ingestion(sources=["newsapi", "rss"])
```

### Free Source Coverage (Implemented)

| Source Type | Sources | Method |
|-------------|---------|--------|
| RSS Feeds | 12 feeds (Maritime Executive, gCaptain, Splash247, Ship & Bunker, Offshore Engineer, etc.) | RSSAggregator |
| Press Rooms | 12 sources (MPA, IMO, DNV, Wärtsilä, MAN, Caterpillar, etc.) | PressRoomScraper |
| NewsAPI | 6 query categories, 6 competitor profiles | NewsCollector |
| Perplexity | 5 research templates (daily, historical, competitor) | PerplexityResearch |

### Positive Consequences

* **Cost Reduction**: 3x reduction in embedding API costs
* **Consistency**: Same entity resolves identically everywhere
* **KB Integration**: All content linked to Knowledge Base (mandatory)
* **Deduplication**: Same URL processed only once
* **Extensibility**: Easy to add new sources
* **Observability**: Single metrics point for content pipeline

### Negative Consequences

* **Migration Required**: Existing services need to consume from unified layer
* **Initial Complexity**: New module to understand
* **Storage Increase**: Unified table grows faster than separate tables

## Implementation

### New Files Created

| File | Purpose |
|------|---------|
| `services/unified_content/__init__.py` | Package exports |
| `services/unified_content/models.py` | UnifiedContent, ExtractedEntity, ContentClassification |
| `services/unified_content/database.py` | PostgreSQL storage with pgvector |
| `services/unified_content/embedding_cache.py` | SharedEmbeddingService with content-hash caching |
| `services/unified_content/content_processor.py` | Entity extraction + KB resolution |
| `services/unified_content/ingestion.py` | UnifiedIngestionPipeline |
| `tests/services/test_unified_content.py` | 35 unit tests |

### Migration Path

1. **Phase 1** (Complete): Create unified_content module
2. **Phase 2**: Update CompetitorIntelAgent to consume from unified layer
3. **Phase 3**: Update MarineIntelAgent to consume from unified layer
4. **Phase 4**: Deprecate separate embedding services

## Usage

### Basic Usage

```python
from lead_to_cash.services.unified_content import (
    UnifiedContent,
    ContentSource,
    ContentPurpose,
    process_content,
    run_full_ingestion,
)

# Create content manually
content = UnifiedContent.create(
    url="https://maritime-executive.com/article",
    title="Wärtsilä Wins Ferry Contract",
    source_name="Maritime Executive",
    source_type=ContentSource.RSS_FEED.value,
    purposes=[ContentPurpose.COMPETITOR_INTEL.value],
)

# Process through pipeline (extracts entities, generates embedding, links to KB)
result = await process_content(content)

# Or run full ingestion from all sources
results = await run_full_ingestion()
```

### Querying Content

```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    embed_text,
)

db = get_unified_content_db()
await db.initialize()

# Get content by purpose
competitor_content = await db.list_content(
    purposes=["competitor_intel"],
    kb_linked=True,
    limit=100,
)

# Semantic search
query_embedding = await embed_text("Wärtsilä ferry contract Singapore")
results = await db.vector_search(
    query_embedding=query_embedding,
    top_k=10,
    min_similarity=0.7,
)
```

## Links

* [ADR-004: Unified KB Architecture](004-unified-knowledge-base-architecture.md)
* [ADR-003: A2A Agent Architecture](003-a2a-agent-architecture.md)
* [Competitor Intel Guide](../docs/guides/competitor_intel_guide.md)
* [Industry News Guide](../docs/guides/industry_news_guide.md)
* [Unified Content Services Guide](../docs/guides/unified_content_guide.md)

---

*This ADR establishes the unified content architecture for eliminating duplicate processing and enforcing mandatory KB integration.*
