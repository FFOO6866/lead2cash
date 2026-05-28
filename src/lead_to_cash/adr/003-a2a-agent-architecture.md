# ADR-003: Agent-to-Agent (A2A) Architecture Using Kaizen Framework

**Status:** Accepted
**Date:** 2026-01-19
**Deciders:** Development Team
**Consulted:** Kailash SDK Documentation
**Informed:** All stakeholders

## Context

The RRPS Lead-to-Cash platform requires multi-agent coordination where:
1. A user-facing agent interprets requests and routes to specialists
2. Specialized agents handle specific domains (due diligence, web search, database retrieval, analysis)
3. Agents share context and coordinate on complex tasks
4. The architecture must be consistent across all modules

Currently, we have a partial implementation with:
- 5 Kaizen BaseAgent implementations (SalesOps, DueDiligence, MarineIntel, CompetitorIntel, CustomerMatcher)
- Custom AgentRegistry with capability-based routing
- SharedMemoryPool for inter-agent data sharing
- Direct service calls for web search and database operations (not agent-based)

## Decision Drivers

* **Consistency**: Same A2A pattern must apply across all modules
* **No Duplication**: Use Kailash framework features, not custom implementations
* **Production Ready**: Must work in production environment at rr.kailash.ai
* **Maintainability**: Leverage framework-provided patterns for long-term support
* **No Mock/Hardcode**: All agents must use real data sources (except SAP CPI simulator)

## Considered Options

### Option 1: Custom A2A Implementation
Build custom A2A protocol, agent discovery, and routing logic.

### Option 2: Kaizen Pipeline Patterns (Router + Supervisor-Worker)
Use Kaizen's built-in Pipeline patterns with A2A semantic matching.

### Option 3: Core SDK A2ACoordinatorNode
Use lower-level A2ACoordinatorNode and SharedMemoryPoolNode from Core SDK.

## Decision Outcome

**Chosen option: "Option 2 - Kaizen Pipeline Patterns"**, because:
1. Kaizen provides 9 production-ready pipeline patterns with A2A integration
2. 4 patterns (Router, Supervisor-Worker, Ensemble, Blackboard) have built-in semantic matching
3. Pipelines can be converted to BaseAgent via `.to_agent()` for consistency
4. Framework is tested and maintained by Kailash team
5. Reduces custom code and maintenance burden

### Positive Consequences

* Semantic task routing without hardcoded if/else logic
* Consistent architecture across all modules
* Production-tested patterns with error handling
* Automatic capability discovery via A2A cards
* Reduced maintenance - framework handles complexity

### Negative Consequences

* Learning curve for Pipeline patterns
* Migration effort for existing custom registry
* Dependency on Kaizen framework updates

## Architecture Design

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ConversationAgent (Router)                        │
│            Pipeline.router(routing_strategy="semantic")              │
│   • Interprets user intent via LLM                                  │
│   • Routes to best specialist via A2A capability matching           │
│   • Synthesizes responses for user                                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ A2A Semantic Routing
        ┌─────────────┼─────────────┬─────────────┬──────────────┐
        ▼             ▼             ▼             ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ WebSearch    │ │ Database     │ │ DueDiligence │ │ MarineIntel  │
│ Agent        │ │ Agent        │ │ Agent        │ │ Agent        │
├──────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ Capabilities:│ │ Capabilities:│ │ Capabilities:│ │ Capabilities:│
│ • web_search │ │ • db_query   │ │ • customer   │ │ • research   │
│ • competitor │ │ • db_store   │ │   validation │ │ • vessel     │
│ • news_feed  │ │ • db_retrieve│ │ • credit_chk │ │   intel      │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┴──────────────┘
                            SharedMemoryPool
                      (Context & Results Sharing)
```

### New Agents to Implement

1. **WebSearchAgent** (BaseAgent)
   - Wraps InsightsService.search_insights() and Perplexity API
   - Capabilities: `web_search`, `competitor_intel`, `news_feed`, `customer_research`
   - Used by other agents when they need real-time web data

2. **DatabaseAgent** (BaseAgent)
   - Wraps PostgreSQL operations via marine_intel/database.py
   - Capabilities: `db_query`, `db_store`, `db_retrieve`, `opportunity_lookup`
   - Used by other agents when they need database access

3. **AnalysisAgent** (BaseAgent)
   - Wraps LLM-based reasoning and synthesis
   - Capabilities: `analyze`, `summarize`, `synthesize`, `compare`
   - Used for complex analysis tasks

### Router Configuration

```python
from kaizen.orchestration.pipeline import Pipeline

# Create router with semantic A2A matching
router = Pipeline.router(
    agents=[
        web_search_agent,
        database_agent,
        due_diligence_agent,
        marine_intel_agent,
        competitor_intel_agent,
        analysis_agent,
    ],
    routing_strategy="semantic",  # A2A-based routing
    error_handling="graceful"
)

# Route requests - no hardcoded logic!
result = router.run(
    task="Search for recent vessel orders in Singapore",
    context={"region": "singapore"}
)
# Automatically routes to marine_intel_agent or web_search_agent
```

### Migration Path

1. **Phase 1**: Create WebSearchAgent and DatabaseAgent as BaseAgents
2. **Phase 2**: Refactor AgentRegistry to use Pipeline.router()
3. **Phase 3**: Update SalesOpsAgent to be the ConversationAgent (user-facing router)
4. **Phase 4**: Ensure all agents have proper A2A capability cards

## Implementation Guidelines

### Agent Capability Cards

Every agent must define capabilities for A2A discovery:

```python
class WebSearchAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config=config, signature=WebSearchSignature())

    def to_a2a_card(self):
        return {
            "name": "WebSearchAgent",
            "description": "Real-time web search and competitor intelligence",
            "capabilities": [
                "web_search",
                "competitor_intel",
                "news_feed",
                "customer_research"
            ],
            "specialties": ["perplexity", "industry_news", "market_intel"]
        }
```

### No Hardcoded Routing

```python
# ❌ WRONG: Hardcoded if/else routing
if "credit" in request:
    return due_diligence_agent.run()
elif "search" in request:
    return web_search_agent.run()

# ✅ CORRECT: Semantic A2A routing
result = router.run(task=request, context=context)
# Router automatically selects best agent based on capabilities
```

### Shared Memory for Context

```python
from kaizen.memory import SharedMemoryPool

shared_pool = SharedMemoryPool()

# Agent writes findings
agent.write_to_memory(
    content={"finding": "Vessel order found", "value": "$50M"},
    tags=["marine_intel", "vessel_order"],
    importance=0.9
)

# Another agent reads context
context = agent2.read_from_memory(
    tags=["marine_intel"],
    min_importance=0.7
)
```

## Links

* [Kaizen Pipeline Patterns Guide](../../../sdk-users/apps/kaizen/docs/guides/pipeline-patterns.md)
* [Kaizen A2A Coordination](../../../sdk-users/2-core-concepts/cheatsheet/023-a2a-agent-coordination.md)
* [Multi-Agent Coordination Guide](../../../sdk-users/apps/kaizen/docs/guides/multi-agent-coordination.md)
* [ADR-002: CPI Gateway Architecture](002-cpi-gateway-architecture.md)

---

*This ADR establishes the A2A architecture using Kailash Kaizen framework for consistent multi-agent coordination.*
