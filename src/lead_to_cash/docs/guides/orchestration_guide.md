# Agent Orchestration Guide

> **Version:** 1.4
> **Last Updated:** 2026-02-04
> **Purpose:** Define intelligent agent routing, data awareness, tool selection, and conversational patterns
> **Related Guides:** `sales_intelligence_agent_guide.md` (unified guide for all intents)
> **Architecture:** 3-Domain Intelligence Architecture (see ADR-002)

---

## CRITICAL: Integration with Existing Components

### MANDATORY: This Guide Extends Existing Architecture

This guide extends (not replaces) the existing components:

| Component | File | This Guide Adds |
|-----------|------|-----------------|
| **AgentRegistry** | `agents/registry.py` | Query understanding, data inventory check |
| **Gateway** | `core/gateway.py` | Conversation session management |
| **Agents** | `agents/*.py` | Tool selection awareness, clarification support |

```python
# Existing registry.py - This guide enhances _select_best_agent()
class AgentRegistry:
    async def process(self, request: str, ...):
        # EXISTING: Semantic A2A routing
        selected_agent = self._select_best_agent(request)

        # ENHANCED (this guide): Add query understanding + data inventory
        parsed_query = await self._understand_query(request, conversation_history)
        inventory = await self._check_data_inventory(parsed_query)
        tool_plan = await self._plan_tool_execution(parsed_query, inventory)
```

---

## 1. Overview

This guide defines how the agent orchestration system:
1. **Understands queries** - Beyond keyword matching, semantic intent classification
2. **Knows available data** - 3 years of scraped intelligence with coverage tracking
3. **Selects tools** - Dynamic tool chains based on query and data availability
4. **Maintains conversation** - Multi-turn with clarifications and follow-ups

---

## 2. Query Understanding

### 2.1 Intent Classification

The system classifies queries into intents using LLM-based understanding (not keyword matching).

**See `sales_intelligence_agent_guide.md` Section 3 for complete intent definitions.**

#### 3-Domain Intelligence Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 KNOWLEDGE BASE (Shared Tool)                     │
│   Entity Registry | Product Specs | Historical Data              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ INDUSTRY INTEL  │ │ COMPETITOR INTEL│ │ PRODUCT INTEL   │
│   (Domain 1)    │ │   (Domain 2)    │ │   (Domain 3)    │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ Market trends   │ │ Win/loss track  │ │ Specifications  │
│ Fleet data      │ │ Pricing intel   │ │ Fit scoring     │
│ Opportunities   │ │ Market position │ │ Recommendations │
│ Industry news   │ │ Threat assess   │ │ Comparisons     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
              ┌───────────────────────┐
              │   KYP / DUE DILIGENCE │
              │ (Orchestrating Agent) │
              └───────────────────────┘
```

| Intent | Description | Primary Agent | Example Queries |
|--------|-------------|---------------|-----------------|
| `INDUSTRY_INTEL` | Market trends, opportunities, fleet data, news | IndustryIntelAgent | "What's happening in Singapore ferry market?" |
| `COMPETITOR_INTEL` | Competitor wins, moves, pricing, threats | CompetitorIntelAgent | "What is Cummins doing in APAC?" |
| `PRODUCT_INTEL` | Product specs, fit analysis, recommendations | ProductIntelAgent | "Which MTU engine fits 2,400kW ferry?" |
| `KYP_DUE_DILIGENCE` | Sanctions, risk, financial health, background | KYPAgent | "Run due diligence on PT Pelni" |

**Multi-Intent Queries:** Many queries combine intents. The agent should address all relevant angles per `sales_intelligence_agent_guide.md` Section 4 (Multi-Angle Analysis Framework). The KYP agent orchestrates all 3 intelligence domains for comprehensive due diligence.

**Backward Compatibility:**
- `MarineIntelAgent` → `IndustryIntelAgent` (alias)
- `KnowledgeBaseAgent` → `ProductIntelAgent` (alias)
- `CustomerIntelAgent` queries → routed to `IndustryIntelAgent` (customer fleet/profile) or `KYPAgent` (due diligence)
- `SalesOpsAgent` queries → routed to `KYPAgent` (relationship check via SAP)

### 2.2 Entity Extraction

Extract structured entities from natural language:

```json
{
  "query": "What contracts has Caterpillar won in APAC last quarter?",
  "extracted": {
    "competitors": ["Caterpillar"],
    "regions": ["APAC"],
    "time_reference": "last quarter",
    "parsed_time": {
      "start": "2025-10-01",
      "end": "2025-12-31"
    }
  }
}
```

### 2.3 Temporal Parsing

| Pattern | Interpretation | Real-Time Needed |
|---------|----------------|------------------|
| "latest", "recent", "today" | Last 7 days | YES |
| "last week" | 7 days back | Maybe |
| "last month" | 30 days back | No |
| "last quarter" | 90 days back | No |
| "last year", "2025" | 365 days back | No |
| "last 3 years" | Full archive | No |
| No time specified | Default: last 30 days | Ask clarification |

### 2.4 Query Understanding Implementation

**File:** `src/lead_to_cash/core/query_understanding.py`

```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import json
from openai import AsyncOpenAI


class QueryIntent(Enum):
    """Aligned with 3-Domain Intelligence Architecture (ADR-002)."""
    # Primary Intelligence Domains
    INDUSTRY_INTEL = "industry_intel"       # Domain 1: Market, fleet, opportunities
    COMPETITOR_INTEL = "competitor_intel"   # Domain 2: Win/loss, pricing, threats
    PRODUCT_INTEL = "product_intel"         # Domain 3: Specs, fit, recommendations
    # Orchestrating Agent
    KYP_DUE_DILIGENCE = "kyp_due_diligence" # Orchestrates all 3 domains

    # Backward compatibility aliases
    MARKET_INTEL = "industry_intel"         # Alias → INDUSTRY_INTEL
    CUSTOMER_INTEL = "industry_intel"       # Folded into INDUSTRY_INTEL
    PRODUCT_FIT = "product_intel"           # Alias → PRODUCT_INTEL
    RELATIONSHIP_CHECK = "kyp_due_diligence"  # Folded into KYP


@dataclass
class ParsedQuery:
    raw_query: str
    intent: QueryIntent
    confidence: float
    competitors: List[str]
    companies: List[str]
    regions: List[str]
    products: List[str]
    time_start: Optional[str]
    time_end: Optional[str]
    is_realtime_needed: bool
    requires_clarification: bool
    clarification_questions: List[str]


class QueryUnderstandingEngine:
    """LLM-based query understanding - NOT keyword matching."""

    SYSTEM_PROMPT = """You are a query analyzer for Rolls-Royce Power Systems (RRPS) sales intelligence.

Analyze the user query and extract:
1. INTENT: One of [industry_intel, competitor_intel, product_intel, kyp_due_diligence]

   3-DOMAIN INTELLIGENCE ARCHITECTURE:
   - industry_intel: Market trends, fleet data, opportunities, industry news, customer profiles
     ("what's happening in...", "ferry market in...", "tell me about [company]'s fleet...")
   - competitor_intel: Competitor wins/losses, pricing intel, market positioning, threats
     ("what is CAT/Cummins/MAN doing...", "competitor wins in...")
   - product_intel: Product specifications, fit analysis, recommendations, comparisons
     ("which engine fits...", "recommend product for...", "MTU specs...")
   - kyp_due_diligence: Due diligence, sanctions, risk assessment, financial health, relationship status
     ("due diligence on...", "safe to work with...", "KYP on...", "winning/losing at...")

2. COMPETITORS: Caterpillar (CAT), Cummins, MAN Energy Solutions (if mentioned)
3. COMPANIES: Any company names (customers, shipyards, operators)
4. REGIONS: Geographic locations (Singapore, Indonesia, APAC, etc.)
5. PRODUCTS: Engine models, product lines (MTU, Bergen)
6. TIME_PERIOD: Parse dates or relative periods
7. REALTIME_NEEDED: true if "latest", "recent", "today", "current"
8. MULTI_INTENT: true if query spans multiple intents (requires Multi-Angle Analysis)
9. CLARIFICATION: If query is ambiguous, what to ask

Context: "we" always means RRPS. The agent is a sales ops assistant for RRPS APAC team.

Respond in JSON format only."""

    def __init__(self, model: str = "gpt-4o"):
        self.client = AsyncOpenAI()
        self.model = model

    async def parse(
        self,
        query: str,
        conversation_history: List[dict] = None,
    ) -> ParsedQuery:
        """Parse query into structured understanding."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # Add conversation context
        if conversation_history:
            messages.append({
                "role": "user",
                "content": f"Previous context: {json.dumps(conversation_history[-3:])}"
            })

        messages.append({"role": "user", "content": query})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = json.loads(response.choices[0].message.content)
        return self._build_parsed_query(query, result)

    def _build_parsed_query(self, query: str, result: dict) -> ParsedQuery:
        return ParsedQuery(
            raw_query=query,
            intent=QueryIntent(result.get("intent", "general_question")),
            confidence=result.get("confidence", 0.8),
            competitors=result.get("competitors", []),
            companies=result.get("companies", []),
            regions=result.get("regions", []),
            products=result.get("products", []),
            time_start=result.get("time_start"),
            time_end=result.get("time_end"),
            is_realtime_needed=result.get("realtime_needed", False),
            requires_clarification=result.get("requires_clarification", False),
            clarification_questions=result.get("clarification_questions", []),
        )
```

---

## 3. Data Inventory System

### 3.1 Purpose

The system maintains awareness of what data exists so agents can:
- Know what questions they can answer from local data
- Identify gaps that require real-time search
- Report data coverage confidence to users

### 3.2 Data Coverage Tracking

| Domain | Data Source | Time Coverage | Entities | Refresh |
|--------|-------------|---------------|----------|---------|
| `competitor_intel` | PostgreSQL + pgvector | 3 years | CAT, CMI, MAN | Daily |
| `marine_news` | PostgreSQL + pgvector | 3 years | APAC operators | Daily |
| `customer_research` | PostgreSQL + pgvector | 3 years | APAC companies | On-demand |
| `product_kb` | PostgreSQL + pgvector | Current | MTU, Bergen | Weekly |
| `financials` | EODHD API | Quarterly | CAT.US, CMI.US | Quarterly |

### 3.3 Data Inventory Implementation

**File:** `src/lead_to_cash/core/data_inventory.py`

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum

from lead_to_cash.services.competitor_intel.database import get_competitor_db
from lead_to_cash.services.marine_intel.database import get_marine_intel_db


class DataSource(Enum):
    LOCAL_VECTORDB = "local_vectordb"
    PERPLEXITY = "perplexity"
    NEWSAPI = "newsapi"
    EODHD = "eodhd"
    SAP_MCP = "sap_mcp"
    KNOWLEDGE_BASE = "knowledge_base"


@dataclass
class DataCoverage:
    domain: str
    entities_covered: List[str]
    time_range_start: datetime
    time_range_end: datetime
    document_count: int
    last_updated: datetime
    coverage_percentage: float


@dataclass
class InventoryCheckResult:
    has_local_data: bool
    coverage: Optional[DataCoverage]
    confidence: str  # HIGH, MEDIUM, LOW
    gaps: List[str]
    recommended_sources: List[DataSource]


class DataInventoryService:
    """
    Tracks what data is available across all sources.

    Answers: "Do we have data to answer this query?"
    """

    def __init__(self):
        self._coverage_cache: dict = {}
        self._cache_ttl = timedelta(hours=1)
        self._last_refresh: Optional[datetime] = None

    async def refresh_inventory(self):
        """Refresh coverage metadata from databases."""
        competitor_db = get_competitor_db()
        marine_db = get_marine_intel_db()

        # Get competitor intel coverage
        comp_stats = await competitor_db.get_coverage_stats()
        self._coverage_cache["competitor_intel"] = DataCoverage(
            domain="competitor_intel",
            entities_covered=comp_stats.get("competitors", []),
            time_range_start=comp_stats.get("earliest_date"),
            time_range_end=comp_stats.get("latest_date"),
            document_count=comp_stats.get("document_count", 0),
            last_updated=comp_stats.get("last_updated"),
            coverage_percentage=self._calculate_coverage(comp_stats),
        )

        # Get marine news coverage
        marine_stats = await marine_db.get_coverage_stats()
        self._coverage_cache["marine_news"] = DataCoverage(
            domain="marine_news",
            entities_covered=marine_stats.get("regions", []),
            time_range_start=marine_stats.get("earliest_date"),
            time_range_end=marine_stats.get("latest_date"),
            document_count=marine_stats.get("document_count", 0),
            last_updated=marine_stats.get("last_updated"),
            coverage_percentage=self._calculate_coverage(marine_stats),
        )

        self._last_refresh = datetime.now()

    async def check_coverage(self, parsed_query: ParsedQuery) -> InventoryCheckResult:
        """
        Check if we have data to answer this query.

        Returns coverage analysis with recommendations.
        """
        # Ensure cache is fresh
        if (not self._last_refresh or
            datetime.now() - self._last_refresh > self._cache_ttl):
            await self.refresh_inventory()

        # Map intent to domain
        domain = self._intent_to_domain(parsed_query.intent)
        coverage = self._coverage_cache.get(domain)

        if not coverage:
            return InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                gaps=[f"No local data for domain: {domain}"],
                recommended_sources=[DataSource.PERPLEXITY],
            )

        # Check entity coverage
        entity_match = self._check_entity_match(parsed_query, coverage)

        # Check temporal coverage
        temporal_match = self._check_temporal_match(parsed_query, coverage)

        # Determine gaps
        gaps = []
        recommended = [DataSource.LOCAL_VECTORDB]

        if entity_match < 0.5:
            gaps.append(f"Limited data on entities: {parsed_query.competitors or parsed_query.companies}")
            recommended.append(DataSource.PERPLEXITY)

        if temporal_match < 0.5 or parsed_query.is_realtime_needed:
            gaps.append("Need real-time data for recent period")
            recommended.insert(1, DataSource.PERPLEXITY)

        if parsed_query.intent == QueryIntent.FINANCIAL_ANALYSIS:
            recommended.append(DataSource.EODHD)

        # Calculate confidence
        overall = (entity_match + temporal_match) / 2
        confidence = "HIGH" if overall > 0.7 else "MEDIUM" if overall > 0.4 else "LOW"

        return InventoryCheckResult(
            has_local_data=overall > 0.3,
            coverage=coverage,
            confidence=confidence,
            gaps=gaps,
            recommended_sources=recommended,
        )

    def _intent_to_domain(self, intent: QueryIntent) -> str:
        """Map QueryIntent to data domain (3-Domain Architecture)."""
        mapping = {
            # 3 Intelligence Domains
            QueryIntent.INDUSTRY_INTEL: "industry_intel",      # Domain 1
            QueryIntent.COMPETITOR_INTEL: "competitor_intel",  # Domain 2
            QueryIntent.PRODUCT_INTEL: "product_kb",           # Domain 3
            # Orchestrating Agent (accesses all domains)
            QueryIntent.KYP_DUE_DILIGENCE: "kyp_combined",
            # Backward compatibility (alias handling)
            QueryIntent.MARKET_INTEL: "industry_intel",
            QueryIntent.CUSTOMER_INTEL: "industry_intel",
            QueryIntent.PRODUCT_FIT: "product_kb",
            QueryIntent.RELATIONSHIP_CHECK: "kyp_combined",
        }
        return mapping.get(intent, "general")

    def _check_entity_match(self, query: ParsedQuery, coverage: DataCoverage) -> float:
        """Check how many query entities are in our coverage."""
        query_entities = set(
            (query.competitors or []) +
            (query.companies or []) +
            (query.regions or [])
        )
        if not query_entities:
            return 1.0  # No specific entities = match all

        covered = set(coverage.entities_covered)
        matches = query_entities.intersection(covered)
        return len(matches) / len(query_entities) if query_entities else 1.0

    def _check_temporal_match(self, query: ParsedQuery, coverage: DataCoverage) -> float:
        """Check if query time range is within our coverage."""
        if not query.time_start:
            return 0.8  # No specific time = mostly covered

        query_start = datetime.fromisoformat(query.time_start)
        if query_start < coverage.time_range_start:
            return 0.3  # Before our coverage
        if query_start > coverage.time_range_end:
            return 0.1  # After our coverage (need real-time)
        return 1.0
```

---

## 4. Tool Selection

**See `sales_intelligence_agent_guide.md` Section 2 for complete tool reference.**

### 4.1 Available Tools

| Tool | Category | Purpose | Latency | Cost |
|------|----------|---------|---------|------|
| `marine_intel_db` | Internal DB | Opportunities, articles, embeddings | 50ms | Free |
| `accounts_db` | Internal DB | Customer records, mention history | 30ms | Free |
| `competitor_signals_db` | Internal DB | Competitor wins, moves, announcements | 50ms | Free |
| `knowledge_base` | Internal KB | Product specs, entity resolution | 30ms | Free |
| `sap_mcp` | MCP/CRM | Customer data, installed base, contacts | 200ms | Free |
| `perplexity_search` | External API | Real-time web research | 3s | $0.01 |
| `newsapi_search` | External API | Historical news (30 days) | 500ms | $0.001 |
| `eodhd_financials` | External API | Competitor financials, SEC data | 300ms | $0.001 |
| `due_diligence_sources` | External | Sanctions, litigation, safety | 2s | Varies |

### 4.2 Tool Selection by Intent (3-Domain Architecture)

**Principle:** Always check Knowledge Base first (shared tool), then domain-specific sources, then external APIs.

**Key Design:** Knowledge Base is a **shared tool** (not a separate agent) that all intelligence agents call for entity resolution, product specs, and historical data.

```python
TOOL_CHAINS = {
    # Domain 1: Industry Intelligence
    QueryIntent.INDUSTRY_INTEL: [
        "knowledge_base",       # 1. Entity resolution, historical context
        "local_vectordb",       # 2. Marine intel DB, opportunities
        "sap_mcp",              # 3. Customer data, installed base
        "perplexity_search",    # 4. Real-time if needed
    ],

    # Domain 2: Competitor Intelligence
    QueryIntent.COMPETITOR_INTEL: [
        "knowledge_base",       # 1. Entity resolution, competitor products
        "local_vectordb",       # 2. Competitor signals, activity
        "sap_mcp",              # 3. Are they at our customers?
        "perplexity_search",    # 4. Real-time updates
        "eodhd_financials",     # 5. Financial data if needed
    ],

    # Domain 3: Product Intelligence
    QueryIntent.PRODUCT_INTEL: [
        "knowledge_base",       # 1. Product specs, fit analysis (primary)
        "local_vectordb",       # 2. Similar installations, use cases
        "sap_mcp",              # 3. Product availability
    ],

    # Orchestrating Agent: KYP (calls all 3 domains)
    QueryIntent.KYP_DUE_DILIGENCE: [
        "knowledge_base",         # 1. Entity resolution, historical records
        "sap_mcp",                # 2. SAP credit, customer data
        "aravo_tprm",             # 3. Third-party risk management
        "perplexity_search",      # 4. News, reputation
        "eodhd_financials",       # 5. Financial health
        "due_diligence_sources",  # 6. Sanctions, litigation, safety
    ],
}
```

**Tool Reference (Updated):**

| Tool | Used By | Purpose |
|------|---------|---------|
| `knowledge_base` | All agents | Entity resolution, product specs, historical data |
| `local_vectordb` | Industry, Competitor | Marine intel DB, opportunities, competitor activity |
| `sap_mcp` | All agents | Customer data, credit, installed base |
| `perplexity_search` | All agents | Real-time web search |
| `eodhd_financials` | Competitor, KYP | Financial fundamentals |
| `aravo_tprm` | KYP | Third-party risk management |
| `due_diligence_sources` | KYP | Sanctions, litigation, safety records |

### 4.3 Tool Execution Pattern

**Pattern:** Execute tools in sequence, stop when sufficient data found.

```python
async def execute_tool_chain(
    parsed_query: ParsedQuery,
    inventory: InventoryCheckResult,
) -> dict:
    """Execute tools based on query analysis."""

    # Get tool chain for intent
    tools = TOOL_CHAINS.get(
        parsed_query.intent,
        ["vector_search", "perplexity_search"]
    )

    # Adjust based on inventory
    if not inventory.has_local_data:
        # Skip local tools, go to real-time
        tools = [t for t in tools if t != "vector_search"]
        tools.insert(0, "perplexity_search")

    if parsed_query.is_realtime_needed:
        # Prioritize real-time
        if "perplexity_search" in tools:
            tools.remove("perplexity_search")
            tools.insert(0, "perplexity_search")

    # Execute tools until sufficient data
    results = {}
    for tool_name in tools:
        result = await _execute_tool(tool_name, parsed_query)
        results[tool_name] = result

        if _is_sufficient(results):
            break

    return results
```

### 4.4 Tool Implementation

**File:** `src/lead_to_cash/core/tool_executor.py`

```python
from typing import Any, Dict, List
from lead_to_cash.services.competitor_intel.database import get_competitor_db
from lead_to_cash.services.competitor_intel.embedding_service import get_embedding_service
from lead_to_cash.services.insights_service import InsightsService
from lead_to_cash.services.competitor_intel.eodhd_service import get_eodhd_service


class ToolExecutor:
    """Execute tools for query answering."""

    def __init__(self):
        self.insights_service = InsightsService()
        self.embedding_service = None
        self.competitor_db = None

    async def initialize(self):
        self.embedding_service = get_embedding_service()
        self.competitor_db = get_competitor_db()

    async def execute(
        self,
        tool_name: str,
        parsed_query: ParsedQuery,
    ) -> Dict[str, Any]:
        """Execute a specific tool."""

        if tool_name == "vector_search":
            return await self._vector_search(parsed_query)
        elif tool_name == "perplexity_search":
            return await self._perplexity_search(parsed_query)
        elif tool_name == "newsapi_search":
            return await self._newsapi_search(parsed_query)
        elif tool_name == "eodhd_financials":
            return await self._eodhd_search(parsed_query)
        elif tool_name == "knowledge_base":
            return await self._kb_search(parsed_query)
        elif tool_name == "sap_mcp":
            return await self._sap_search(parsed_query)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _vector_search(self, query: ParsedQuery) -> Dict[str, Any]:
        """Search local vector database."""
        embedding = await self.embedding_service.generate_embedding(query.raw_query)

        results = await self.competitor_db.vector_search(
            embedding=embedding,
            top_k=10,
            filters={
                "competitors": query.competitors,
                "date_range": (query.time_start, query.time_end),
            }
        )

        return {
            "tool": "vector_search",
            "documents": results,
            "count": len(results),
            "source": "local_archive",
        }

    async def _perplexity_search(self, query: ParsedQuery) -> Dict[str, Any]:
        """Real-time web search via Perplexity."""
        result = await self.insights_service.search_insights(query.raw_query)

        return {
            "tool": "perplexity_search",
            "content": result.content,
            "sources": result.sources,
            "source": "perplexity_realtime",
        }

    async def _eodhd_search(self, query: ParsedQuery) -> Dict[str, Any]:
        """Fetch financial data from EODHD."""
        eodhd = get_eodhd_service()

        results = {}
        for competitor in query.competitors:
            ticker = {"caterpillar": "CAT.US", "cummins": "CMI.US"}.get(
                competitor.lower()
            )
            if ticker:
                data = await eodhd.fetch_quarterly_financials(ticker)
                results[competitor] = data

        return {
            "tool": "eodhd_financials",
            "financials": results,
            "source": "eodhd_api",
        }
```

---

## 5. Conversation Management

### 5.1 Session State

Each conversation maintains:
- **Session ID** - Unique identifier
- **Turn History** - Previous messages for context
- **Extracted Context** - Entities, topics mentioned
- **Pending Clarifications** - Questions awaiting response

### 5.2 Clarification Triggers

| Condition | Clarification Question |
|-----------|----------------------|
| No time period specified | "What time period are you interested in?" |
| Ambiguous competitor | "Which competitor: Caterpillar, Cummins, or MAN?" |
| No scope specified | "Do you want a quick summary or detailed analysis?" |
| Multiple possible intents | "Are you looking for news, financials, or opportunities?" |

### 5.3 Follow-Up Suggestions

Generate contextual follow-up suggestions based on response:

| Query Type | Follow-Up Suggestions |
|------------|----------------------|
| Competitor contracts | "Compare with [other competitor]?", "See financial impact?" |
| Market news | "Focus on specific region?", "Identify opportunities?" |
| Customer research | "Run full KYP check?", "Check financial health?" |
| Product info | "See competitor alternatives?", "Check availability?" |

### 5.4 Conversation Implementation

**File:** `src/lead_to_cash/core/conversation.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationSession:
    session_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    pending_clarification: Optional[Dict[str, Any]] = None

    def add_turn(self, role: str, content: str, **metadata):
        self.turns.append(ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
        ))

    def get_history(self, max_turns: int = 10) -> List[Dict[str, str]]:
        return [
            {"role": t.role, "content": t.content}
            for t in self.turns[-max_turns:]
        ]


class ConversationManager:
    """Manages multi-turn conversations with clarifications."""

    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}
        self.query_engine = QueryUnderstandingEngine()
        self.inventory = DataInventoryService()
        self.tool_executor = ToolExecutor()

    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(session_id=session_id)

        return self.sessions[session_id]

    async def process_message(
        self,
        session_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Process a user message in conversation."""
        session = self.get_or_create_session(session_id)

        # Check if responding to clarification
        if session.pending_clarification:
            return await self._handle_clarification(session, message)

        # Add user turn
        session.add_turn("user", message)

        # Parse query with conversation context
        parsed = await self.query_engine.parse(
            message,
            session.get_history()
        )

        # Check if clarification needed
        clarifications = self._check_clarifications(parsed, session)
        if clarifications:
            session.pending_clarification = {
                "parsed_query": parsed,
                "questions": clarifications,
            }
            return {
                "type": "clarification_needed",
                "questions": clarifications,
                "partial_understanding": {
                    "intent": parsed.intent.value,
                    "entities": {
                        "competitors": parsed.competitors,
                        "regions": parsed.regions,
                    }
                }
            }

        # Check data inventory
        inventory = await self.inventory.check_coverage(parsed)

        # Execute tool chain
        tool_results = await self.tool_executor.execute_chain(parsed, inventory)

        # Generate response (delegate to appropriate agent)
        response = await self._generate_response(parsed, tool_results, inventory)

        # Generate follow-ups
        follow_ups = self._generate_follow_ups(parsed, response)

        # Add assistant turn
        session.add_turn("assistant", response["answer"],
                        sources=response.get("sources"),
                        follow_ups=follow_ups)

        return {
            "type": "answer",
            "session_id": session_id,
            "answer": response["answer"],
            "sources": response.get("sources", []),
            "confidence": response.get("confidence", "medium"),
            "data_coverage": {
                "has_local_data": inventory.has_local_data,
                "coverage_confidence": inventory.confidence,
                "gaps": inventory.gaps,
            },
            "follow_up_suggestions": follow_ups,
        }

    def _check_clarifications(
        self,
        parsed: ParsedQuery,
        session: ConversationSession,
    ) -> List[Dict[str, Any]]:
        """Check if clarification questions are needed."""
        questions = []

        # Check if LLM flagged clarification
        if parsed.requires_clarification:
            for q in parsed.clarification_questions:
                questions.append({
                    "question": q,
                    "type": "text",
                })

        # Check temporal ambiguity for time-sensitive queries
        time_sensitive = [
            QueryIntent.COMPETITOR_INTEL,
            QueryIntent.MARKET_NEWS,
            QueryIntent.FINANCIAL_ANALYSIS,
        ]
        if (parsed.intent in time_sensitive and
            not parsed.time_start and
            not parsed.is_realtime_needed):
            questions.append({
                "question": "What time period are you interested in?",
                "type": "choice",
                "options": [
                    "Last 7 days (latest)",
                    "Last 30 days",
                    "Last 3 months",
                    "Last year",
                    "All available (3 years)",
                ],
            })

        # Check competitor ambiguity
        if (parsed.intent == QueryIntent.COMPETITOR_INTEL and
            not parsed.competitors):
            questions.append({
                "question": "Which competitor(s) are you interested in?",
                "type": "choice",
                "options": [
                    "Caterpillar (CAT/MaK)",
                    "Cummins",
                    "MAN Energy Solutions",
                    "All major competitors",
                ],
            })

        return questions

    def _generate_follow_ups(
        self,
        parsed: ParsedQuery,
        response: Dict[str, Any],
    ) -> List[str]:
        """Generate contextual follow-up suggestions."""
        follow_ups = []

        if parsed.intent == QueryIntent.COMPETITOR_INTEL:
            if parsed.competitors:
                other = {"caterpillar": "Cummins", "cummins": "Caterpillar", "man": "Caterpillar"}
                comp = parsed.competitors[0].lower()
                if comp in other:
                    follow_ups.append(f"Compare with {other[comp]}?")
            follow_ups.append("See financial performance details?")
            follow_ups.append("Identify RRPS competitive response?")

        elif parsed.intent == QueryIntent.MARKET_NEWS:
            follow_ups.append("Focus on a specific region?")
            follow_ups.append("Identify sales opportunities from this?")
            follow_ups.append("Track this topic for daily updates?")

        elif parsed.intent == QueryIntent.CUSTOMER_RESEARCH:
            follow_ups.append("Run full KYP due diligence?")
            follow_ups.append("Check financial health?")
            follow_ups.append("See fleet composition?")

        return follow_ups[:3]  # Max 3 suggestions
```

---

## 6. Integration with Existing Components

### 6.1 Registry Enhancement

Update `AgentRegistry.process()` to use new orchestration:

```python
# In agents/registry.py

class AgentRegistry:
    def __init__(self, ...):
        # ... existing init ...
        self.query_engine = QueryUnderstandingEngine()
        self.data_inventory = DataInventoryService()
        self.conversation_manager = ConversationManager()

    async def process(
        self,
        request: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
        trace_context: Optional["SpanContext"] = None,
    ) -> dict:
        """
        Enhanced processing with query understanding and data awareness.
        """
        # Use conversation manager for multi-turn support
        if session_id:
            return await self.conversation_manager.process_message(
                session_id=session_id,
                message=request,
            )

        # Single-turn processing (backward compatible)
        # 1. Understand query (not just keyword matching)
        parsed_query = await self.query_engine.parse(request)

        # 2. Check data inventory
        inventory = await self.data_inventory.check_coverage(parsed_query)

        # 3. Select agent based on intent (semantic, not keyword)
        selected_agent = self._select_agent_by_intent(parsed_query.intent)

        # 4. Execute with tool awareness
        result = await self._execute_with_tools(
            agent=selected_agent,
            parsed_query=parsed_query,
            inventory=inventory,
            trace_context=trace_context,
        )

        # 5. Add metadata
        result["data_coverage"] = {
            "has_local_data": inventory.has_local_data,
            "confidence": inventory.confidence,
            "gaps": inventory.gaps,
        }

        return result
```

### 6.2 Gateway Enhancement

Update `/api/v1/agents/process` to support sessions:

```python
# In core/gateway.py

@app.post("/api/v1/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Conversational chat endpoint with multi-turn support.

    Headers:
        X-Session-ID: Optional session ID for conversation continuity

    Request body:
        {
            "message": "What contracts has Caterpillar won?",
            "clarification_response": {  // Optional, if responding to clarification
                "question_id": "time_period",
                "answer": "Last 3 months"
            }
        }

    Response:
        {
            "session_id": "uuid",
            "type": "answer" | "clarification_needed",
            "answer": "...",  // If type=answer
            "questions": [...],  // If type=clarification_needed
            "sources": [...],
            "confidence": "HIGH",
            "data_coverage": {...},
            "follow_up_suggestions": [...]
        }
    """
    if not agent_registry:
        raise HTTPException(status_code=503, detail="Agent registry not initialized")

    result = await agent_registry.process(
        request=body.message,
        session_id=session_id or str(uuid.uuid4()),
    )

    return {
        "session_id": result.get("session_id", session_id),
        **result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

## 7. Response Format

### 7.1 Standard Response Structure

```json
{
  "session_id": "uuid-string",
  "type": "answer",

  "answer": "Structured response following agent guides...",

  "sources": [
    {
      "url": "https://...",
      "title": "Source title",
      "type": "local_archive|perplexity|newsapi|eodhd",
      "date": "2026-01-15"
    }
  ],

  "confidence": "HIGH|MEDIUM|LOW",

  "data_coverage": {
    "has_local_data": true,
    "coverage_confidence": "HIGH",
    "document_count": 234,
    "time_range": "2023-01-01 to 2026-01-20",
    "gaps": ["Need real-time for last 24 hours"]
  },

  "tools_used": ["vector_search", "perplexity_search"],

  "follow_up_suggestions": [
    "Compare with Cummins?",
    "See financial details?",
    "Track for updates?"
  ],

  "metadata": {
    "selected_agent": "competitor_intel",
    "routing": "semantic_intent",
    "processing_time_ms": 1234
  }
}
```

### 7.2 Clarification Response

```json
{
  "session_id": "uuid-string",
  "type": "clarification_needed",

  "questions": [
    {
      "id": "time_period",
      "question": "What time period are you interested in?",
      "type": "choice",
      "options": [
        "Last 7 days (latest)",
        "Last 30 days",
        "Last 3 months",
        "All available (3 years)"
      ],
      "reason": "Time scope affects data sources used"
    }
  ],

  "partial_understanding": {
    "intent": "competitor_intel",
    "entities": {
      "competitors": ["Caterpillar"],
      "regions": ["APAC"]
    }
  }
}
```

---

## 8. Streaming Response (Real-Time UX)

### 8.1 Overview

The chat interface supports **Server-Sent Events (SSE)** for real-time response streaming, providing a ChatGPT/Claude-like experience.

**Benefits:**
- **Perceived latency reduction**: Users see activity immediately
- **Progress visibility**: Users understand what the AI is doing
- **Better engagement**: Token-by-token response feels interactive

### 8.2 Streaming Endpoint

```
POST /api/v1/chat/stream
Content-Type: application/json
X-Session-ID: <optional-session-id>

{"message": "What's happening in Singapore ferry market?"}
```

**Response:** `text/event-stream` with SSE events

### 8.3 Event Types

| Event Type | Description | Example |
|------------|-------------|---------|
| `session` | Session ID confirmation | `{"type": "session", "session_id": "uuid"}` |
| `status` | Progress updates | `{"type": "status", "step": "gathering", "message": "Searching 3 data sources..."}` |
| `tools_complete` | Sources gathered | `{"type": "tools_complete", "sources": [...], "tools_used": [...]}` |
| `token` | Response token | `{"type": "token", "content": "The "}` |
| `done` | Completion with metadata | `{"type": "done", "confidence": "HIGH", "follow_up_suggestions": [...]}` |
| `clarification_needed` | Clarification required | `{"type": "clarification_needed", "questions": [...]}` |
| `error` | Error occurred | `{"type": "error", "error": "..."}` |

### 8.4 Status Steps

The thinking indicator shows these steps:

```
1. understanding      → "Understanding your query..."
2. checking_inventory → "Checking data availability..."
3. planning           → "Planning tool execution..."
4. gathering          → "Searching 3 data sources..."
5. fallback           → "Searching additional sources..."
6. synthesizing       → "Generating response..."
```

### 8.5 Frontend Implementation

```javascript
// Use fetch with ReadableStream for SSE
const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Session-ID': sessionId},
    body: JSON.stringify({message: text})
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const event = JSON.parse(line.slice(6));
            switch (event.type) {
                case 'token': appendToMessage(event.content); break;
                case 'status': updateThinkingStep(event.step); break;
                case 'done': finalizeMessage(event); break;
            }
        }
    }
}
```

---

## 9. Session Storage (Production)

### 9.1 Overview

Session storage determines whether conversations persist across:
- Multiple workers (horizontal scaling)
- Server restarts
- Load balancer routing

### 9.2 Storage Options

| Storage | Use Case | Configuration |
|---------|----------|---------------|
| **In-Memory** | Development, single worker | Default (no config needed) |
| **Redis** | Production, multiple workers | Set `REDIS_URL` environment variable |

### 9.3 Redis Configuration

```bash
# .env
REDIS_URL=redis://localhost:6379/0

# Production with password
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
```

**Session key format:** `l2c:chat:session:{session_id}`
**TTL:** 2 hours (7200 seconds)

### 9.4 Automatic Detection

The `get_conversation_manager()` function automatically detects and uses Redis:

```python
# In core/conversation.py
def get_conversation_manager() -> ConversationManager:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # Production: Use Redis for distributed sessions
        session_store = RedisSessionStore(redis_url=redis_url)
        return ConversationManager(session_store=session_store)
    else:
        # Development: Use in-memory (warns in production)
        return ConversationManager()
```

### 9.5 Production Checklist

- [ ] Set `REDIS_URL` in environment
- [ ] Ensure Redis is running and accessible
- [ ] Test session persistence across requests
- [ ] Monitor Redis connection logs on startup

---

## 10. Content Relevance Filter (Programmatic)

### 10.1 Overview

Beyond prompt-based filtering, the system applies **programmatic post-filters** to ensure content relevance. This catches edge cases where LLM synthesis includes irrelevant content despite prompt instructions.

### 10.2 Filter Implementation

**File:** `src/lead_to_cash/core/tool_executor.py`

```python
# Irrelevant marine segments (leisure/recreational)
IRRELEVANT_MARINE_TERMS = frozenset([
    "sailing boat", "sailing yacht", "sailboat",
    "beneteau", "jeanneau", "bavaria yachts",
    "outboard motor", "jet ski", "fish finder",
    ...
])

# Relevance indicators that SHOULD be present
RELEVANCE_INDICATORS = frozenset([
    "mtu", "bergen", "rolls-royce", "diesel engine",
    "ferry", "osv", "psv", "ahts", "tug", "offshore",
    "caterpillar", "cummins", "man energy",
    ...
])

def check_content_relevance(content: str) -> tuple[bool, str]:
    """
    Programmatic relevance check applied after synthesis.

    Returns:
        (is_relevant, reason)
    """
    # Decision logic:
    # 1. Irrelevant terms + no relevant terms -> FAIL
    # 2. Many irrelevant terms (>3) + few relevant (<2) -> FAIL
    # 3. Relevant terms present -> PASS
    ...
```

### 10.3 Filter Behavior

| Scenario | Result | Action |
|----------|--------|--------|
| Only sailing/leisure content | FAIL | Replace with "no relevant content" message |
| Mixed relevant + some irrelevant | PASS | Content proceeds (prompt handles filtering) |
| Strong relevant indicators | PASS | Content proceeds |
| No indicators either way | PASS | Allow by default |

### 10.4 Filtered Response

When content fails relevance check:

```json
{
  "type": "answer",
  "answer": "No relevant commercial marine or offshore opportunities found...",
  "confidence": "LOW",
  "sources": [],  // Cleared
  "data_coverage": {...}
}
```

---

## 11. What Agents Must Do

**Reference:** `sales_intelligence_agent_guide.md` for complete response standards.

1. **Load unified guide at initialization** - Use output format from `sales_intelligence_agent_guide.md`
2. **Identify intent(s)** - Recognize single or multi-intent queries
3. **Check internal data first** - Marine Intel DB, Accounts DB, KB, MCP/SAP
4. **Apply multi-angle analysis** - Consider all relevant angles (Product Fit, Customer, Competitor, Risk, Relationship)
5. **Use tool chain** - Follow recommended tool sequence per intent
6. **Query KB for product fit** - Always match opportunities to our products
7. **Check MCP for relationship** - Always verify customer status in SAP
8. **Support clarifications** - Handle pending clarification state
9. **Generate follow-ups** - Provide contextual suggestions
10. **Track data coverage** - Report what data was used and gaps
11. **Never fabricate** - No fake URLs, no estimated values, no guessed products
12. **Filter irrelevant content** - Exclude sailing boats, leisure yachts, marine electronics

---

## 12. Production Hardening

### 12.1 Thread-Safe Initialization

The `get_conversation_manager()` function uses double-checked locking:

```python
_manager_lock = threading.Lock()

def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is not None:
        return _manager  # Fast path

    with _manager_lock:  # Slow path with lock
        if _manager is not None:
            return _manager  # Double-check
        # Initialize...
```

### 12.2 Redis Resilience

RedisSessionStore includes production-grade resilience:

- **Lazy connection**: No blocking ping on initialization
- **Automatic reconnection**: Rate-limited retry with exponential backoff
- **Fallback cache**: In-memory fallback during Redis outages
- **Session restoration**: Restores cached sessions when Redis recovers

### 12.3 Streaming Robustness

The streaming endpoint handles edge cases:

| Scenario | Handling |
|----------|----------|
| Client disconnects | `request.is_disconnected()` check, generator cleanup |
| OpenAI timeout | 60-second timeout with fallback to raw content |
| asyncio.CancelledError | Clean propagation for proper resource cleanup |
| Generator cleanup | `try/finally` with `await generator.aclose()` |

### 12.4 Content Filter Timing

| Path | When Filter Runs |
|------|------------------|
| Non-streaming | After synthesis, before return |
| Streaming | Before synthesis, on raw tool outputs |

---

## 13. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-20 | AI Architecture Team | Initial release |
| 1.1 | 2026-01-21 | AI Architecture Team | Aligned with unified sales_intelligence_agent_guide.md |
| 1.2 | 2026-01-21 | AI Architecture Team | Added streaming response (SSE), Redis session storage, stricter content relevance filtering |
| 1.3 | 2026-01-21 | AI Architecture Team | Production hardening: thread-safe singleton, Redis resilience with lazy connect/reconnection/fallback, streaming disconnect detection and timeout, programmatic content relevance post-filter |
| 1.4 | 2026-02-04 | AI Architecture Team | **3-Domain Intelligence Architecture**: Restructured to IndustryIntel/CompetitorIntel/ProductIntel domains with Knowledge Base as shared tool. KYP orchestrates all 3 domains. Added backward compatibility aliases. Updated QueryIntent enum and tool chains. (ADR-002) |

---

## 14. Related Documents

**Architecture Reference:**
- `docs/adr/ADR-002-autonomous-agent-redesign.md` - **3-Domain Intelligence Architecture specification**

**Primary Reference:**
- `sales_intelligence_agent_guide.md` - **Unified guide for all intents, output standards, multi-angle analysis**

**Agent Signatures:**
- `agents/signatures.py` - **IndustryIntelSignature, CompetitorIntelSignature, ProductIntelSignature, KYPSignature**
- `agents/autonomous_base.py` - **AutonomousAgent base class with convergence detection**
- `agents/contracts.py` - **AgentResponse typed contracts**

**Deprecated Guides (replaced by unified guide):**
- ~~`industry_news_guide.md`~~ - See `sales_intelligence_agent_guide.md` Section 5.2
- ~~`competitor_insights_guide.md`~~ - See `sales_intelligence_agent_guide.md` Section 5.3
- ~~`KYP_guide.md`~~ - See `sales_intelligence_agent_guide.md` Section 5.5

**Implementation:**
- `agents/registry.py` - Agent registration and routing
- `agents/autonomous/` - Autonomous agent implementations (IndustryIntelAgent, CompetitorIntelAgent, ProductIntelAgent, KYPAgent)
- `core/gateway.py` - HTTP API gateway, streaming endpoint
- `core/conversation.py` - Session management, streaming orchestration
- `core/tool_executor.py` - Tool execution, streaming synthesis
- `frontend/chat-enhanced.html` - Streaming UI with thinking indicator
