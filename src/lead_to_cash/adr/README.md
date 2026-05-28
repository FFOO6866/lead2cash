# Architecture Decision Records (ADR)

This folder contains architecture decisions for the RRPS Lead-to-Cash platform.

## Active ADRs

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-002](002-cpi-gateway-architecture.md) | CPI Gateway Architecture | Accepted | 2026-01-15 |
| [ADR-003](003-a2a-agent-architecture.md) | A2A Agent Architecture Using Kaizen | Accepted | 2026-01-19 |
| [ADR-004](004-unified-knowledge-base-architecture.md) | Unified KB Architecture with Rating-Level Product Fit | Accepted | 2026-01-21 |
| [ADR-005](005-unified-content-architecture.md) | Unified Content Architecture - Scrape Once, Use Many | Accepted | 2026-01-21 |

## ADR Summaries

### ADR-002: CPI Gateway Architecture
Establishes the architecture for SAP Cloud Platform Integration (CPI) gateway, including the CPI Simulator for development and testing without production SAP access.

### ADR-003: A2A Agent Architecture Using Kaizen
Defines the Agent-to-Agent (A2A) architecture using Kaizen framework's Pipeline patterns. Key decisions:

- Use `Pipeline.router()` with `routing_strategy="semantic"` for intelligent task routing
- All agents implement `to_a2a_card()` for A2A capability discovery
- No hardcoded if/else routing - pure semantic matching
- SharedMemoryPool for inter-agent coordination
- Agents include: WebSearchAgent, DatabaseAgent, DueDiligenceAgent, CompetitorIntelAgent, MarineIntelAgent

### ADR-004: Unified KB Architecture with Rating-Level Product Fit
Establishes unified knowledge base architecture with critical enhancements:

- **Single Source of Truth**: Merge `product_data.py` (in-memory) into PostgreSQL KB
- **Rating-Level Data Model**: New `kb_engine_ratings` table for ISO 8528 duty class ratings
- **Customer Requirements**: New `kb_customer_requirements` table for structured fit matching
- **Product Fit Scoring**: Deterministic algorithm for engine-to-requirement matching
- **Competitor Engagements**: New `kb_competitor_engagements` table to track competitor activity at our customers
- **Apple-to-Apple Comparison**: `kb_rating_competitor_map` for rating-level (not model-level) competitive mapping

Key data models: DutyClass enum (Continuous, Heavy, Medium, Light, Pleasure per ISO 8528), EngineRating, CustomerRequirement, RatingCompetitorMap, CompetitorEngagement.

### ADR-005: Unified Content Architecture - Scrape Once, Use Many
Establishes unified content ingestion pipeline to eliminate duplicate processing:

- **"Scrape Once, Use Many"**: Single ingestion point for all content sources (NewsAPI, RSS, Perplexity, Press Rooms)
- **SharedEmbeddingService**: Single embedding service with content-hash caching (eliminates 3x API costs)
- **Unified Entity Extraction**: Single extraction pass with regex + LLM refinement
- **Mandatory KB Integration**: All content MUST be linked to Knowledge Base entities (no longer optional)
- **Multi-Purpose Classification**: Same content scored for competitor intel, marine intel, and KB relevance
- **URL Deduplication**: SHA-256 hash prevents duplicate content processing

Key components: UnifiedContent model, SharedEmbeddingService, ContentProcessor, UnifiedIngestionPipeline.

Free source coverage: 12 RSS feeds, 12 press rooms, 6 NewsAPI query categories, 5 Perplexity research templates.

## Creating New ADRs

### 1. Copy the Template
```bash
cp adr/001-template.md adr/004-your-decision.md
```

### 2. Fill in the Details
- **Title**: Short, descriptive name
- **Status**: Proposed | Accepted | Deprecated | Superseded
- **Context**: What forces you to make this decision?
- **Decision**: What you decided to do
- **Consequences**: What are the positive and negative outcomes?

### 3. ADR Lifecycle
1. **Proposed**: Draft ADR for team discussion
2. **Accepted**: Team agrees and implements
3. **Deprecated**: Decision no longer recommended
4. **Superseded**: Replaced by a newer ADR

## Best Practices

- **Keep it Short**: 1-2 pages maximum
- **Be Specific**: Focus on this app's architecture
- **Include Context**: Explain why you needed to decide
- **Date Decisions**: When was this decided?
- **Link Related ADRs**: Reference other decisions

## Related Documentation

- [Lead-to-Cash README](../README.md) - Platform overview
- [Kaizen Pipeline Patterns](../../../../sdk-users/apps/kaizen/docs/guides/pipeline-patterns.md)
- [Multi-Agent Coordination Guide](../../../../sdk-users/apps/kaizen/docs/guides/multi-agent-coordination.md)

---

*These ADRs define the architectural foundations of the RRPS Lead-to-Cash platform.*
