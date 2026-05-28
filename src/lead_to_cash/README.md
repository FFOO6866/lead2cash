# RRPS Lead-to-Cash Platform

Production-ready Lead-to-Cash platform for RRPS Sales Operations, built on Kailash SDK with Kaizen AI agents and A2A (Agent-to-Agent) architecture.

## Overview

The Lead-to-Cash platform automates sales operations from initial lead through to cash collection, integrating with SAP ERP systems via Cloud Platform Integration (CPI).

### Key Features

- **AI Agent Orchestration**: Multi-agent system using Kaizen BaseAgent architecture
- **A2A Semantic Routing**: Intelligent task routing via Pipeline.router() (ADR-003)
- **SAP Integration**: Customer validation, credit checks, sales order processing
- **Marine Intelligence**: Industry research and opportunity tracking
- **Competitor Intelligence**: RAG-based competitor analysis
- **Unified Content Pipeline**: "Scrape Once, Use Many" architecture (ADR-005)
- **News Intelligence**: 20+ free sources (RSS, NewsAPI, Perplexity, press rooms)

## Architecture

### A2A Agent Architecture (ADR-003)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     AgentRegistry (Router)                          │
│             Pipeline.router(routing_strategy="semantic")            │
│   • Interprets user intent via LLM                                  │
│   • Routes to best specialist via A2A capability matching           │
│   • No hardcoded if/else routing - pure semantic matching           │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ A2A Semantic Routing
        ┌─────────────┼─────────────┬─────────────┬──────────────┐
        ▼             ▼             ▼             ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ WebSearch    │ │ Database     │ │ DueDiligence │ │ Competitor   │
│ Agent        │ │ Agent        │ │ Agent        │ │ Intel Agent  │
├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ Capabilities:│ │ Capabilities:│ │ Capabilities:│ │ Capabilities:│
│ • web_search │ │ • db_query   │ │ • customer   │ │ • competitor │
│ • competitor │ │ • db_store   │ │   validation │ │   analysis   │
│ • news_feed  │ │ • db_retrieve│ │ • credit_chk │ │ • RAG query  │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┴──────────────┘
                            SharedMemoryPool
                      (Context & Results Sharing)
```

### Agent Capabilities

| Agent | Capabilities | Description |
|-------|-------------|-------------|
| **DueDiligenceAgent** | customer_validation, credit_check, partner_function | SAP customer master data validation |
| **CompetitorIntelAgent** | competitor_analysis, rag_query | RAG-based competitor intelligence |
| **WebSearchAgent** | web_search, industry_news, customer_research | Real-time web search via Perplexity |
| **DatabaseAgent** | db_query, db_store, opportunity_lookup | PostgreSQL marine intel operations |
| **MarineIntelAgent** | research, vessel_intel | Marine industry research and tracking |
| **CustomerMatcherAgent** | customer_matching | LLM-based customer name matching |

### Unified Content Architecture (ADR-005)

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCRAPE ONCE                                 │
│  NewsAPI → RSS (12 feeds) → Perplexity → Press Rooms (12)       │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              UnifiedContent Store                          │  │
│  │  • URL hash deduplication (SHA-256)                        │  │
│  │  • Single embedding (SharedEmbeddingService)               │  │
│  │  • Single entity extraction                                │  │
│  │  • Mandatory KB resolution                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           ↓                                      │
│                     USE MANY                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │ Competitor  │ │   Marine    │ │ Product Fit │                │
│  │   Intel     │ │   Intel     │ │  (KB match) │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Knowledge Base (Central Hub)                  │  │
│  │  kb_manufacturers → kb_engine_models → kb_engine_ratings   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- **3x Cost Reduction**: Single embedding per URL (eliminates duplicate API calls)
- **Mandatory KB Integration**: All content linked to Knowledge Base entities
- **20+ Free Sources**: RSS feeds, press rooms, NewsAPI, Perplexity

## Project Structure

```
lead_to_cash/
├── agents/                    # Kaizen BaseAgent implementations
│   ├── registry.py           # A2A semantic router (Pipeline.router)
│   ├── due_diligence_agent.py
│   ├── competitor_intel_agent.py
│   ├── web_search_agent.py   # A2A infrastructure agent
│   ├── database_agent.py     # A2A infrastructure agent
│   ├── marine_intel_agent.py
│   └── customer_matcher_agent.py
│
├── services/                  # Service layer
│   ├── unified_content/      # Unified content pipeline (ADR-005)
│   │   ├── models.py         # UnifiedContent, ExtractedEntity
│   │   ├── database.py       # PostgreSQL with pgvector
│   │   ├── embedding_cache.py # SharedEmbeddingService
│   │   ├── content_processor.py # Entity extraction + KB linking
│   │   └── ingestion.py      # UnifiedIngestionPipeline
│   ├── news_collector.py     # NewsAPI integration (6 query categories)
│   ├── rss_aggregator.py     # RSS feeds (12 sources)
│   ├── perplexity_research.py # Perplexity API (5 templates)
│   ├── press_room_scraper.py # Press room scraping (12 sources)
│   ├── news_intelligence_orchestrator.py # Unified orchestration
│   ├── insights_service.py   # Perplexity API integration
│   ├── marine_intel/         # Marine intelligence module
│   ├── competitor_intel/     # Competitor intelligence module
│   ├── knowledge_base/       # Knowledge base module
│   └── customer_validation/  # SAP customer validation
│
├── integrations/              # External integrations
│   ├── cpi_simulator.py      # SAP CPI simulator
│   └── sap_adapter.py        # SAP adapter patterns
│
├── api/                       # FastAPI endpoints
│   └── routers/              # API routers by domain
│
├── adr/                       # Architecture Decision Records
│   ├── 001-template.md
│   ├── 002-cpi-gateway-architecture.md
│   └── 003-a2a-agent-architecture.md
│
└── deployment/               # Deployment configuration
    └── docker/              # Docker Compose for rr.kailash.ai
```

## Quick Start

### 1. Setup

```bash
# Install in development mode
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Usage

```python
from lead_to_cash.agents import create_agent_registry

async def main():
    # Create registry with A2A semantic routing
    registry = await create_agent_registry()

    # Requests are automatically routed based on A2A capabilities
    result = await registry.process("Validate customer 1234567")
    # -> Routes to DueDiligenceAgent

    result = await registry.process("Search for vessel orders in Singapore")
    # -> Routes to WebSearchAgent or MarineIntelAgent

    result = await registry.process("What contracts has Caterpillar won?")
    # -> Routes to CompetitorIntelAgent
```

### 3. Direct Agent Access

```python
from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

async def validate():
    config = DueDiligenceConfig()
    async with DueDiligenceAgent(config) as agent:
        result = await agent.validate_customer("1234567")
```

## Key Principles

1. **100% Kailash SDK** - All agents use Kaizen BaseAgent, all routing via Pipeline
2. **A2A Semantic Routing** - No hardcoded if/else routing (ADR-003)
3. **Real Data Only** - No mocks except SAP CPI simulator
4. **Shared Memory** - Agents share context via SharedMemoryPool
5. **Production Ready** - Deployed at rr.kailash.ai

## Architecture Decision Records

| ADR | Title | Status |
|-----|-------|--------|
| ADR-002 | CPI Gateway Architecture | Accepted |
| ADR-003 | A2A Agent Architecture Using Kaizen | Accepted |
| ADR-004 | Unified KB Architecture with Rating-Level Product Fit | Accepted |
| ADR-005 | Unified Content Architecture - Scrape Once, Use Many | Accepted |

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=lead_to_cash

# Test specific module
pytest tests/test_agents/ -v
```

## Deployment

The platform is deployed at **rr.kailash.ai** using Docker Compose with Traefik reverse proxy.

```bash
# Deploy to production
cd deployment/docker
docker-compose -f docker-compose.prod.yml up -d
```

## App Metadata

- **App Name**: RRPS Lead-to-Cash Platform
- **Purpose**: Sales operations automation with SAP integration
- **Owner**: RRPS Development Team
- **Status**: Production
- **Production URL**: https://rr.kailash.ai

---

*Built on Kailash SDK with Kaizen AI framework for A2A agent coordination.*
