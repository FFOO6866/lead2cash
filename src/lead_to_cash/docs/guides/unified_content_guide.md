# Unified Content Services Guide

> **Version:** 1.1
> **Last Updated:** 2026-01-22
> **ADR:** [ADR-005](../../adr/005-unified-content-architecture.md)
> **Purpose:** "Scrape Once, Use Many" architecture for maritime intelligence

---

## 1. Overview

The Unified Content Services module (`services/unified_content/`) implements a centralized content pipeline that:

1. **Ingests** content from multiple sources (NewsAPI, RSS, Perplexity, press rooms)
2. **Deduplicates** by URL hash (SHA-256)
3. **Embeds** once via SharedEmbeddingService (eliminates 3x API costs)
4. **Extracts** entities via regex + LLM
5. **Links** to Knowledge Base (mandatory, not optional)
6. **Classifies** for multiple purposes (competitor intel, marine intel, KB relevance)

This eliminates the previous architecture where:
- `competitor_intel/` had its own embedding service
- `marine_intel/` had its own embedding service
- `knowledge_base/` had its own embedding service
- KB integration was OPTIONAL in CompetitorIntelAgent

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCRAPE ONCE                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │  NewsAPI    │ │ RSS Feeds   │ │ Perplexity  │ │ Press Room ││
│  │ (6 queries) │ │ (12 feeds)  │ │(5 templates)│ │(12 sources)││
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬─────┘│
│         └────────────────┴──────────────┴────────────────┘      │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │            UnifiedIngestionPipeline                        │  │
│  │  • URL hash deduplication                                  │  │
│  │  • Source tier assignment                                  │  │
│  │  • Purpose determination                                   │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                             ↓                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              ContentProcessor                              │  │
│  │  • Entity extraction (regex + LLM)                        │  │
│  │  • KB entity resolution (mandatory)                       │  │
│  │  • Multi-purpose classification                           │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                             ↓                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │            SharedEmbeddingService                          │  │
│  │  • Content-hash caching                                   │  │
│  │  • text-embedding-3-small (1536 dim)                      │  │
│  │  • Batch processing                                       │  │
│  └─────────────────────────┬─────────────────────────────────┘  │
│                             ↓                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │            UnifiedContentDatabase                          │  │
│  │  • PostgreSQL with pgvector                               │  │
│  │  • unified_content table                                  │  │
│  │  • unified_content_entities table                         │  │
│  │  • unified_content_kb_links table                         │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      USE MANY                                   │
├─────────────────────────────────────────────────────────────────┤
│  CompetitorIntelAgent → Query by purposes=["competitor_intel"]  │
│  MarineIntelAgent     → Query by purposes=["marine_intel"]      │
│  ProductFitAgent      → Query by kb_linked=True                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Quick Start

### 3.1 Full Ingestion

```python
from lead_to_cash.services.unified_content import run_full_ingestion

# Ingest from all sources
results = await run_full_ingestion()

# Results is dict[str, IngestionResult]
for source, result in results.items():
    print(f"{source}: {result.content_saved} saved, {result.duplicates_skipped} skipped")
```

### 3.2 Priority Ingestion

```python
from lead_to_cash.services.unified_content import run_priority_ingestion

# Ingest from priority sources only
results = await run_priority_ingestion(sources=["newsapi", "rss"])
```

### 3.3 Single Source Ingestion

```python
from lead_to_cash.services.unified_content import (
    ingest_newsapi,
    ingest_rss,
    ingest_press_rooms,
)

# NewsAPI only
result = await ingest_newsapi(categories=["singapore_sea", "regulatory"])

# RSS only
result = await ingest_rss(feed_keys=["maritime_executive", "gcaptain"])

# Press rooms only
result = await ingest_press_rooms(source_keys=["mpa_singapore", "imo"])
```

### 3.4 Manual Content Processing

```python
from lead_to_cash.services.unified_content import (
    UnifiedContent,
    ContentSource,
    ContentPurpose,
    process_content,
)

# Create content manually
content = UnifiedContent.create(
    url="https://example.com/article",
    title="Wärtsilä Wins Ferry Contract",
    source_name="Maritime Executive",
    source_type=ContentSource.RSS_FEED.value,
    content="Full article text...",
    purposes=[ContentPurpose.COMPETITOR_INTEL.value],
)

# Process (extracts entities, generates embedding, links to KB)
result = await process_content(content)

print(f"Entities: {result.entities_extracted}")
print(f"KB links: {result.kb_entities_resolved}")
print(f"Priority: {result.classification_score}")
```

---

## 4. Components

### 4.1 UnifiedContent Model

The atomic unit for all ingested content.

```python
from lead_to_cash.services.unified_content import (
    UnifiedContent,
    ContentSource,
    ContentPurpose,
    SourceTier,
)

content = UnifiedContent.create(
    url="https://maritime-executive.com/article/wartsila-ferry",
    title="Wärtsilä Wins Singapore Ferry Contract",
    source_name="Maritime Executive",
    source_type=ContentSource.RSS_FEED.value,
    source_tier=SourceTier.TIER_3.value,
    content="Full article content...",
    summary="AI-generated summary...",
    purposes=[
        ContentPurpose.COMPETITOR_INTEL.value,
        ContentPurpose.MARINE_INTEL.value,
    ],
)

# Auto-generated fields
print(content.id)       # UUID
print(content.url_hash) # SHA-256
print(content.ingested_at)  # Timestamp
```

**Content Source Types:**

| Source | Value | Description |
|--------|-------|-------------|
| GENERAL | `general` | Default source |
| NEWSAPI | `newsapi` | NewsAPI articles |
| RSS_FEED | `rss_feed` | RSS feed articles |
| PERPLEXITY | `perplexity` | Perplexity research |
| PRESS_ROOM | `press_room` | Company press rooms |
| COMPETITOR_WEBSITE | `competitor_website` | Competitor websites |
| REGULATORY_ANNOUNCEMENT | `regulatory_announcement` | MPA, IMO, etc. |

**Content Purpose Types:**

| Purpose | Value | Description |
|---------|-------|-------------|
| COMPETITOR_INTEL | `competitor_intel` | Competitor tracking |
| MARINE_INTEL | `marine_intel` | Sales opportunities |
| REGULATORY_INTEL | `regulatory_intel` | Regulatory updates |
| PRODUCT_INTEL | `product_intel` | Product information |
| MARKET_INTEL | `market_intel` | Market trends |
| GENERAL | `general` | General news |

### 4.2 SharedEmbeddingService

Single embedding service for the entire application.

```python
from lead_to_cash.services.unified_content import (
    get_shared_embedding_service,
    embed_text,
    embed_texts,
    get_embedding_stats,
)

# Get singleton service
service = get_shared_embedding_service()

# Embed single text
embedding = await service.embed_text("Maritime news content")

# Convenience function
embedding = await embed_text("Maritime news content")

# Batch embedding (auto-deduplicates)
embeddings = await embed_texts([
    "First article content",
    "Second article content",
    "First article content",  # Cached, no API call
])

# View cache stats
stats = get_embedding_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']}")
print(f"API calls saved: {stats['api_calls_saved']}")
```

**Cache Stats Example:**
```json
{
  "total_requests": 1000,
  "cache_hits": 850,
  "cache_misses": 150,
  "cache_hit_rate": "85.0%",
  "api_calls": 150,
  "api_calls_saved": 850,
  "total_tokens": 45000,
  "cache_size": 850,
  "max_cache_size": 10000,
  "model": "text-embedding-3-small"
}
```

### 4.3 ContentProcessor

Extracts entities and links to Knowledge Base.

```python
from lead_to_cash.services.unified_content import (
    ContentProcessor,
    get_processor,
)

# Get singleton processor
processor = await get_processor()

# Process content
result = await processor.process(content)

# Result contains:
# - content: Updated UnifiedContent with entities, embedding, classification
# - entities_extracted: Count of entities found
# - kb_entities_resolved: Count of entities linked to KB
# - embedding_generated: Whether embedding was created
# - classification_score: Priority score (1-10)
# - processing_time_ms: Processing duration
# - errors: Any errors encountered
```

**Entity Types Extracted:**

| Type | Examples | KB Table |
|------|----------|----------|
| MANUFACTURER | Wärtsilä, MAN, Caterpillar | kb_manufacturers |
| ENGINE_MODEL | W31, C32, D3872 | kb_engine_models |
| VESSEL_TYPE | Ferry, OSV, FPSO | - |
| SHIPYARD | Seatrium, Keppel | - |
| REGION | Singapore, Indonesia | - |
| REGULATORY_BODY | IMO, MPA, DNV | - |

### 4.4 ContentClassification

Multi-purpose scoring for each content item.

```python
from lead_to_cash.services.unified_content import ContentClassification

classification = ContentClassification(
    # Competitor Intel Scoring
    competitor_threat_score=75,  # 0-100
    competitor_name="Wärtsilä",
    competitor_signal_type="contract_win",

    # Marine Intel Scoring
    sales_opportunity_score=60,  # 0-100
    sales_signals=["newbuild", "ferry"],
    vessel_types=["Ferry"],
    region="Singapore",

    # KB Relevance Scoring
    technical_score=35,  # 0-40
    market_score=25,     # 0-30
    commercial_score=20, # 0-30
    kb_relevance_total=80,  # Sum of above

    # Priority
    priority=8,  # 1-10
    requires_review=True,
)
```

### 4.5 UnifiedContentDatabase

PostgreSQL storage with pgvector support.

```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    initialize_unified_content_db,
)

# Initialize database
db = await initialize_unified_content_db()

# Save content
content_id, is_new = await db.save_content(content)
# is_new=False means duplicate was skipped

# Get content
content = await db.get_content(content_id)
content = await db.get_content_by_url("https://example.com/article")

# Check if URL exists
exists = await db.check_url_exists("https://example.com/article")

# List content with filters
competitor_content = await db.list_content(
    source_type="newsapi",
    purposes=["competitor_intel"],
    is_processed=True,
    kb_linked=True,
    limit=100,
)

# Get unprocessed content for backfill
unprocessed = await db.get_unprocessed_content(limit=50)

# Vector search
results = await db.vector_search(
    query_embedding=embedding,
    top_k=10,
    min_similarity=0.7,
    source_types=["newsapi", "rss_feed"],
    purposes=["competitor_intel"],
)
# Returns list of (UnifiedContent, similarity_score)

# Get stats
stats = await db.get_stats()
```

---

## 5. News Sources (54 Total)

> **Full Registry:** See `services/source_registry.py` for programmatic access to all 54 sources.

### 5.1 Source Registry Overview

```python
from lead_to_cash.services.source_registry import (
    get_all_sources,
    get_sources_by_category,
    get_priority_sources,
    get_rss_sources,
    get_source_stats,
)

# Get statistics
stats = get_source_stats()
# {
#   'total': 54,
#   'enabled': 54,
#   'with_rss': 12,
#   'by_category': {'regulatory': 8, 'singapore_sea': 10, ...},
#   'by_priority': {'critical': 13, 'high': 25, 'medium': 16},
#   'by_tier': {'tier_1': 29, 'tier_2': 21, 'tier_3': 4}
# }
```

| Category | Sources | Critical | High | Medium |
|----------|---------|----------|------|--------|
| Regulatory & Environmental | 8 | 3 | 4 | 1 |
| Singapore & Southeast Asia | 10 | 2 | 5 | 3 |
| General Maritime | 8 | 2 | 4 | 2 |
| Offshore Oil & Gas | 5 | 1 | 3 | 1 |
| Shipyards | 6 | 2 | 3 | 1 |
| Engine Manufacturers | 7 | 3 | 2 | 2 |
| Associations | 6 | 0 | 3 | 3 |
| Financial | 4 | 0 | 1 | 3 |
| **TOTAL** | **54** | **13** | **25** | **16** |

### 5.2 NewsAPI (6 Query Categories)

```python
from lead_to_cash.services.news_collector import NewsCollector

collector = NewsCollector()

# Available categories
categories = list(collector.MARINE_QUERY_CATEGORIES.keys())
# ['singapore_sea', 'regulatory', 'offshore', 'engines', 'vessel_orders', 'shipyards']

# Collect by category
result = await collector.collect_by_category(["singapore_sea", "regulatory"])
```

| Category | Queries | Focus |
|----------|---------|-------|
| `singapore_sea` | 8 queries | MPA, Keppel, Sembcorp, Indonesia, Malaysia, Vietnam |
| `regulatory` | 8 queries | IMO, MEPC, CII, EEXI, ECA, Tier III |
| `offshore` | 7 queries | FPSO, FID, OSV, PSV, AHTS, subsea |
| `engines` | 8 queries | Wärtsilä, MAN, dual fuel, retrofit |
| `vessel_orders` | 7 queries | Ferry, OSV, tanker, cruise, tug |
| `shipyards` | 6 queries | Asia shipyards, Korean, Chinese |

### 5.3 RSS Feeds (12 Sources)

```python
from lead_to_cash.services.rss_aggregator import RSSAggregator, RSS_FEEDS

aggregator = RSSAggregator()

# RSS_FEEDS is a list[RSSFeed] - iterate directly
for feed in RSS_FEEDS:
    if feed.enabled:
        articles = await aggregator.fetch_feed(feed)
```

| Feed | Source | Category | Tier |
|------|--------|----------|------|
| Maritime Executive | maritime-executive.com | general_maritime | 2 |
| gCaptain | gcaptain.com | general_maritime | 2 |
| Splash247 | splash247.com | apac | 2 |
| Ship & Bunker | shipandbunker.com | bunkering | 2 |
| Offshore Engineer | oedigital.com | offshore | 2 |
| Hellenic Shipping News | hellenicshippingnews.com | shipping | 3 |
| Rigzone | rigzone.com | offshore | 2 |
| Offshore Magazine | offshore-mag.com | offshore | 2 |
| Seatrade Maritime | seatrade-maritime.com | global | 2 |
| DNV News | dnv.com | classification | 1 |
| Marine Link | marinelink.com | technology | 3 |
| WorkBoat | workboat.com | workboats | 3 |

### 5.4 Press Room Sources (12 Sources)

```python
from lead_to_cash.services.press_room_scraper import (
    PressRoomScraper,
    PRESS_ROOM_SOURCES,
)

scraper = PressRoomScraper()

# PRESS_ROOM_SOURCES is a list[PressRoomSource] - iterate directly
for source in PRESS_ROOM_SOURCES:
    if source.enabled:
        result = await scraper.scrape_source(source)
```

| Source | Organization | Type | Tier |
|--------|--------------|------|------|
| MPA Singapore | Maritime Port Authority | Regulatory | 1 |
| IMO | International Maritime Organization | Regulatory | 1 |
| DNV | DNV GL | Classification | 1 |
| Lloyd's Register | Lloyd's Register | Classification | 1 |
| Wärtsilä | Wärtsilä Corporation | Competitor | 1 |
| MAN ES | MAN Energy Solutions | Competitor | 1 |
| Caterpillar | Caterpillar Marine | Competitor | 1 |
| Cummins | Cummins Inc. | Competitor | 1 |
| Seatrium | Seatrium Limited | Shipyard | 1 |
| Keppel | Keppel Corporation | Shipyard | 1 |
| SMF | Singapore Maritime Foundation | Association | 1 |
| BIMCO | BIMCO | Association | 2 |

### 5.5 Perplexity Research (5 Templates)

```python
from lead_to_cash.services.perplexity_research import (
    PerplexityResearch,
    RESEARCH_TEMPLATES,
)

researcher = PerplexityResearch()

# Available templates
templates = list(RESEARCH_TEMPLATES.keys())
# ['DAILY_NEWS', 'HISTORICAL', 'COMPETITOR', 'REGULATORY', 'MARKET_INTEL']

# Run research
result = await researcher.research(template="DAILY_NEWS")
result = await researcher.research(template="COMPETITOR", topic="Wärtsilä")

# Historical backfill (3 years)
results = await researcher.run_historical_backfill(years_back=3)
```

### 5.6 Historical Backfill Strategy

For 3-year coverage via Perplexity:

| Topic | Queries | Est. Articles |
|-------|---------|---------------|
| Singapore Maritime 2022-2024 | 36 | ~500 |
| IMO Regulations 2022-2024 | 24 | ~300 |
| Engine Orders 2022-2024 | 48 | ~600 |
| FPSO/OSV Projects | 24 | ~400 |
| **Total** | **132** | **~1,800** |

---

## 6. Integration with Existing Services

### 6.1 CompetitorIntelAgent

```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    ContentPurpose,
)

# Query competitor intel content
db = get_unified_content_db()
await db.initialize()

competitor_content = await db.list_content(
    purposes=[ContentPurpose.COMPETITOR_INTEL.value],
    kb_linked=True,  # Only KB-linked content
    limit=100,
)

# Filter by competitor
for content in competitor_content:
    if content.classification:
        if content.classification.competitor_name == "Wärtsilä":
            print(f"Threat: {content.classification.competitor_threat_score}")
```

### 6.2 MarineIntelAgent

```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    ContentPurpose,
)

# Query marine intel content
db = get_unified_content_db()
await db.initialize()

marine_content = await db.list_content(
    purposes=[ContentPurpose.MARINE_INTEL.value],
    limit=100,
)

# Filter by opportunity score
high_opportunity = [
    c for c in marine_content
    if c.classification and c.classification.sales_opportunity_score > 50
]
```

### 6.3 KnowledgeBaseAgent

```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    embed_text,
)

# Semantic search for KB-relevant content
db = get_unified_content_db()
await db.initialize()

query_embedding = await embed_text("Wärtsilä W31 dual fuel engine ferry")
results = await db.vector_search(
    query_embedding=query_embedding,
    top_k=10,
    min_similarity=0.7,
)

for content, similarity in results:
    print(f"[{similarity:.2f}] {content.title}")
```

---

## 7. Scheduling & Automation

### 7.1 Daily Ingestion

```python
import asyncio
from lead_to_cash.services.unified_content import run_priority_ingestion

async def daily_ingestion():
    """Run daily at 6 AM."""
    results = await run_priority_ingestion(
        sources=["newsapi", "rss", "press_room"]
    )

    total_saved = sum(r.content_saved for r in results.values())
    total_skipped = sum(r.duplicates_skipped for r in results.values())

    print(f"Daily ingestion: {total_saved} new, {total_skipped} skipped")
```

### 7.2 Weekly Full Ingestion

```python
async def weekly_full_ingestion():
    """Run weekly on Sunday."""
    from lead_to_cash.services.unified_content import run_full_ingestion

    results = await run_full_ingestion()

    # Include Perplexity research for deeper analysis
    from lead_to_cash.services.perplexity_research import PerplexityResearch

    researcher = PerplexityResearch()
    await researcher.research(template="MARKET_INTEL")
```

### 7.3 Backfill Processing

```python
async def backfill_missing():
    """Backfill embeddings and KB links for unprocessed content."""
    from lead_to_cash.services.unified_content import get_pipeline

    pipeline = await get_pipeline()

    # Backfill embeddings
    embeddings_added = await pipeline.backfill_embeddings(limit=100)

    # Backfill KB links
    kb_links_added = await pipeline.backfill_kb_links(limit=100)

    print(f"Backfill: {embeddings_added} embeddings, {kb_links_added} KB links")
```

---

## 8. Monitoring & Metrics

### 8.1 Embedding Stats

```python
from lead_to_cash.services.unified_content import get_embedding_stats

stats = get_embedding_stats()

# Key metrics to monitor
print(f"Cache hit rate: {stats['cache_hit_rate']}")
print(f"API calls saved: {stats['api_calls_saved']}")
print(f"Total tokens used: {stats['total_tokens']}")
```

### 8.2 Database Stats

```python
from lead_to_cash.services.unified_content import get_unified_content_db

db = get_unified_content_db()
await db.initialize()

stats = await db.get_stats()

# Key metrics
print(f"Total content: {stats['total_content']}")
print(f"Processed: {stats['processed']}")
print(f"KB linked: {stats['kb_linked']}")
print(f"With embedding: {stats['with_embedding']}")
print(f"By source type: {stats['by_source_type']}")
print(f"By purpose: {stats['by_purpose']}")
```

### 8.3 Ingestion Job Tracking

```python
# After ingestion, check results
result = await ingest_newsapi()

print(f"Job ID: {result.job_id}")
print(f"Status: {result.status}")
print(f"Content found: {result.content_found}")
print(f"Content saved: {result.content_saved}")
print(f"Duplicates skipped: {result.duplicates_skipped}")
print(f"Entities extracted: {result.entities_extracted}")
print(f"KB links created: {result.kb_links_created}")
print(f"Errors: {result.errors}")
```

---

## 9. Related Documentation

- [ADR-005: Unified Content Architecture](../../adr/005-unified-content-architecture.md)
- [ADR-004: Unified KB Architecture](../../adr/004-unified-knowledge-base-architecture.md)
- [Competitor Intel Guide](competitor_intel_guide.md)
- [Industry News Guide](industry_news_guide.md)
- [Marine Intel Structure](../../services/marine_intel/INSIGHT_STRUCTURE.md)

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.1 | 2026-01-22 | Engineering Team | Added comprehensive 54-source registry overview, expanded RSS/Press Room tables, added historical backfill strategy |
| 1.0 | 2026-01-21 | Engineering Team | Initial release |
