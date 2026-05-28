# RRPS Sales Intelligence Agent Architecture

> **Version:** 2.0
> **Last Updated:** 2026-01-21
> **Status:** Production
> **ADR Reference:** ADR-003 (A2A Semantic Routing)

---

## Agent Naming Convention

| Original Name (File) | Alias Name | Domain |
|---------------------|------------|--------|
| `MarineIntelAgent` | `MarketIntelAgent` | Industry news, opportunities |
| `CustomerMatcherAgent` | `CustomerIntelAgent` | Customer profiling, SAP lookup |
| `CompetitorIntelAgent` | (same) | CAT, Cummins, MAN tracking |
| `DueDiligenceAgent` | `KYPAgent` | Risk assessment, compliance |
| `KnowledgeBaseAgent` | `ProductFitAgent` | Engine matching, KB queries |

**Usage:** Both names work interchangeably. Aliases provide clearer domain naming.

---

## 1. Overview

This document defines the authoritative agent architecture for the RRPS Sales Intelligence system. Each agent has a **strictly defined domain** with **no overlaps**.

### 1.1 Design Principles

1. **Single Responsibility:** Each agent owns ONE domain completely
2. **No Overlaps:** Clear boundaries - if in doubt, check this document
3. **A2A Coordination:** Agents communicate via semantic routing, not direct calls
4. **Guide-Agent Alignment:** Each domain agent has exactly ONE guide
5. **Smart Reasoning:** Agents don't just fetch data - they analyze, connect, and recommend

### 1.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR                                       │
│                         (SalesOpsAgent)                                      │
│                                                                              │
│  Responsibilities:                                                           │
│  • Intent classification (via QueryUnderstandingEngine)                      │
│  • Multi-agent coordination (always check multiple angles)                   │
│  • Result synthesis (connect dots across agents)                             │
│  • Proactive suggestions (follow-ups, monitoring)                            │
│  • Session context (connect to previous queries)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
         ┌───────────────┬───────────┼───────────┬───────────────┐
         ▼               ▼           ▼           ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   MARKET    │  │  CUSTOMER   │  │ COMPETITOR  │  │     KYP     │  │  PRODUCT    │
│   INTEL     │  │   INTEL     │  │   INTEL     │  │    AGENT    │  │  FIT AGENT  │
│   AGENT     │  │   AGENT     │  │   AGENT     │  │             │  │             │
├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤  ├─────────────┤
│ Industry    │  │ Customer    │  │ CAT/Cummins │  │ Due         │  │ MTU/Bergen  │
│ news &      │  │ profiles &  │  │ /MAN        │  │ diligence & │  │ product     │
│ opportunities│  │ relationships│  │ tracking    │  │ risk        │  │ matching    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
         │               │               │               │               │
         ▼               ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INFRASTRUCTURE LAYER                                  │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ WebSearch   │  │  Database   │  │    MCP      │  │  Knowledge  │        │
│  │   Agent     │  │   Agent     │  │  (SAP/CPI)  │  │    Base     │        │
│  │ (Perplexity)│  │ (PostgreSQL)│  │             │  │  (pgvector) │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Domain Agent Specifications

### 2.1 MarineIntelAgent (alias: MarketIntelAgent)

**File:** `agents/marine_intel_agent.py`
**Guide:** `docs/guides/market_intel_guide.md`
**Domain:** Industry news, opportunities, events, regulations, trends

#### Owns (Exclusively)

| Capability | Description |
|------------|-------------|
| `industry_news` | Marine/offshore industry news and announcements |
| `opportunities` | Newbuild, retrofit, repower opportunities |
| `events` | Trade shows, conferences, maritime weeks |
| `regulations` | IMO, MPA, EPA policy changes |
| `market_reports` | DNV, Clarksons, BIMCO forecasts |
| `technology_trends` | New propulsion tech, digitalization |
| `industry_ma` | Mergers, acquisitions, partnerships (non-competitor) |

#### Does NOT Own

| Capability | Owned By |
|------------|----------|
| Customer profiling | CustomerIntelAgent |
| Competitor tracking | CompetitorIntelAgent |
| Risk assessment | KYPAgent |
| Product recommendations | ProductFitAgent |

#### Data Sources

- Marine Intel DB (PostgreSQL + pgvector)
- NewsAPI (historical news)
- WebSearchAgent (Perplexity for real-time)

#### Output Standards

```python
class MarketIntelOutput:
    opportunities: List[Opportunity]  # Prioritized 1-10
    regulations: List[Regulation]     # With RRPS impact
    events: List[Event]               # With relevance assessment
    trends: List[Trend]               # With implications
    sources: List[Source]             # Verified URLs
    confidence: str                   # HIGH/MEDIUM/LOW
```

---

### 2.2 CustomerMatcherAgent (alias: CustomerIntelAgent)

**File:** `agents/customer_matcher_agent.py`
**Guide:** `docs/guides/customer_intel_guide.md`
**Domain:** Customer profiling, relationships, needs, SAP data

#### Owns (Exclusively)

| Capability | Description |
|------------|-------------|
| `customer_profile` | Who they are, what they do, fleet size |
| `customer_lookup` | SAP account lookup via MCP |
| `installed_base` | What MTU/Bergen products they have |
| `purchase_history` | Past purchases, service contracts |
| `open_opportunities` | CRM pipeline status |
| `key_contacts` | Decision makers, procurement |
| `customer_matching` | Fuzzy name resolution to SAP accounts |
| `customer_needs` | Strategy, fleet plans, requirements |
| `relationship_status` | Active customer, prospect, dormant |

#### Does NOT Own

| Capability | Owned By |
|------------|----------|
| Industry news about customer | MarketIntelAgent |
| Competitor activity at customer | CompetitorIntelAgent |
| Customer sanctions/risk | KYPAgent |
| Product recommendations | ProductFitAgent |

#### Data Sources

- SAP via MCP (customer_lookup, account_history, contact_lookup, opportunity_check)
- Accounts DB (PostgreSQL)
- Customer embeddings (pgvector)

#### Output Standards

```python
class CustomerIntelOutput:
    profile: CustomerProfile          # Company overview
    relationship: RelationshipStatus  # ACTIVE_CUSTOMER/PROSPECT/DORMANT
    installed_base: List[Product]     # Our products at customer
    opportunities: List[Opportunity]  # Open CRM opportunities
    contacts: List[Contact]           # Key decision makers
    needs: CustomerNeeds              # Requirements, strategy
    sources: List[Source]
    confidence: str
```

---

### 2.3 CompetitorIntelAgent

**File:** `agents/competitor_intel_agent.py`
**Guide:** `docs/guides/competitor_intel_guide.md`
**Domain:** CAT, Cummins, MAN tracking - their moves, wins, products

#### Owns (Exclusively)

| Capability | Description |
|------------|-------------|
| `competitor_wins` | Contract wins by CAT/Cummins/MAN |
| `competitor_products` | Product launches, specs |
| `competitor_partnerships` | Alliances, distributor deals |
| `competitor_financials` | SEC filings, quarterly results |
| `threat_assessment` | HIGH/MEDIUM/LOW threat level |
| `competitor_at_customer` | Competitor activity at our accounts |
| `market_share` | Segment share analysis |
| `competitor_pricing` | Pricing intelligence (when available) |

#### Does NOT Own

| Capability | Owned By |
|------------|----------|
| General industry news | MarketIntelAgent |
| Customer relationship data | CustomerIntelAgent |
| Competitor company risk | KYPAgent |
| Our product positioning | ProductFitAgent |

#### Tracked Competitors

| Competitor | Aliases | Key Products |
|------------|---------|--------------|
| Caterpillar | CAT, MaK | M32C, M43C, M46DF |
| Cummins | - | QSK60, QSK78, QSK95 |
| MAN Energy Solutions | MAN ES, MAN | 32/44CR, 48/60CR |

#### Data Sources

- Competitor Signals DB (PostgreSQL + pgvector)
- EODHD API (SEC filings)
- WebSearchAgent (Perplexity for real-time)

#### Output Standards

```python
class CompetitorIntelOutput:
    competitor: str                   # CAT/Cummins/MAN
    activity_type: str                # WIN/LAUNCH/PARTNERSHIP/FINANCIAL
    threat_level: str                 # HIGH/MEDIUM/LOW
    customer_impact: CustomerImpact   # Are they taking our customers?
    response: RecommendedResponse     # What we should do
    sources: List[Source]
    confidence: str
```

---

### 2.4 DueDiligenceAgent (alias: KYPAgent)

**File:** `agents/due_diligence_agent.py`
**Guide:** `docs/guides/KYP_guide.md`
**Domain:** Due diligence, risk assessment, compliance

#### Owns (Exclusively)

| Capability | Description |
|------------|-------------|
| `sanctions_screening` | OFAC, EU, UN, MAS sanctions lists |
| `litigation_check` | Court cases, regulatory actions |
| `financial_health` | Bankruptcy, credit risk, payment history |
| `safety_record` | MPA, port state control, incidents |
| `reputation_check` | News, reviews, complaints |
| `risk_categorization` | CRITICAL/HIGH/MEDIUM/LOW |
| `compliance_recommendation` | PROCEED/CAUTION/DO_NOT_PROCEED |

#### Does NOT Own

| Capability | Owned By |
|------------|----------|
| Customer relationship | CustomerIntelAgent |
| Industry news | MarketIntelAgent |
| Competitor tracking | CompetitorIntelAgent |
| Product recommendations | ProductFitAgent |

#### Data Sources

- Sanctions databases (OFAC, EU, UN, MAS)
- Litigation databases
- Financial databases
- Maritime safety databases (MPA, Tokyo MoU)
- WebSearchAgent (reputation)

#### Output Standards

```python
class KYPOutput:
    entity: str
    sanctions: SanctionsResult        # NO_RECORDS_FOUND or findings
    litigation: LitigationResult      # NO_ADVERSE_FINDINGS or findings
    financial: FinancialResult        # Assessment with indicators
    safety: SafetyResult              # Clean or incidents
    reputation: ReputationResult      # No issues or concerns
    overall_risk: str                 # NO_ADVERSE_FINDINGS/FINDINGS_IDENTIFIED
    recommendation: str               # PROCEED/CAUTION/DO_NOT_PROCEED
    sources: List[Source]
    confidence: str
```

#### CRITICAL: Terminology Rules

| Never Say | Always Say |
|-----------|------------|
| "PASS" | "No matching records identified in [database] as of [date]" |
| "CLEAN" | "No adverse findings from sources reviewed" |
| "GOOD reputation" | "No significant negative coverage identified" |
| "SAFE" | "No port state control detentions in past 3 years" |

---

### 2.5 KnowledgeBaseAgent (alias: ProductFitAgent)

**File:** `agents/knowledge_base_agent.py`
**Guide:** `docs/guides/product_fit_guide.md`
**Domain:** MTU/Bergen product matching, specifications, recommendations

#### Owns (Exclusively)

| Capability | Description |
|------------|-------------|
| `product_catalog` | MTU/Bergen product specifications |
| `power_matching` | Match power requirements to products |
| `application_fit` | Ferry, OSV, tug, offshore application matching |
| `fuel_compatibility` | Diesel, dual-fuel, methanol compatibility |
| `product_comparison` | Our products vs competitor products |
| `product_recommendation` | Best product for requirement |
| `specification_lookup` | Detailed technical specs |

#### Does NOT Own

| Capability | Owned By |
|------------|----------|
| Customer needs | CustomerIntelAgent |
| Industry trends | MarketIntelAgent |
| Competitor wins | CompetitorIntelAgent |
| Customer risk | KYPAgent |

#### Product Portfolio

| Series | Type | Power Range | RPM | Applications |
|--------|------|-------------|-----|--------------|
| MTU 2000 | High-speed | 700-1,600 kW | 1800-2100 | Ferries, workboats |
| MTU 4000 | High-speed | 1,400-4,300 kW | 1600-2100 | Ferries, OSVs, yachts |
| MTU 8000 | High-speed | 7,200-10,000 kW | 1150 | Large ferries, cruise |
| Bergen B32:40 | Medium-speed | 4,500-9,000 kW | 750 | OSVs, cargo |
| Bergen B35:40 | Medium-speed | 6,200-12,000 kW | 750 | Offshore, power gen |

#### Data Sources

- Knowledge Base (kb_engine_series, kb_manufacturers, kb_applications)
- Product specifications database

#### Output Standards

```python
class ProductFitOutput:
    requirement: Requirement          # What customer needs
    recommended_products: List[Product]  # Ranked by fit
    fit_analysis: FitAnalysis         # Why each product fits/doesn't
    competitor_comparison: Comparison # Our product vs competitor
    sources: List[Source]
    confidence: str
```

---

## 3. Orchestrator Specification

### 3.1 SalesOpsAgent (Orchestrator)

**File:** `agents/sales_ops_agent.py`
**Role:** Central coordination, multi-agent routing, synthesis

#### Responsibilities

1. **Intent Classification**
   - Parse user query via QueryUnderstandingEngine
   - Map to primary agent(s)

2. **Multi-Agent Coordination**
   - ALWAYS check multiple angles (not just primary intent)
   - Route to relevant domain agents in parallel

3. **Result Synthesis**
   - Combine results from multiple agents
   - Connect dots across domains
   - Resolve conflicts

4. **Proactive Intelligence**
   - Connect to previous session queries
   - Suggest follow-ups
   - Offer monitoring/alerts

5. **Session Management**
   - Maintain conversation context
   - Track mentioned entities
   - Handle clarifications

#### Multi-Angle Analysis Rule

**MANDATORY:** For every query, the orchestrator MUST check relevant angles:

```python
async def process(self, query: str, context: dict) -> Response:
    # 1. Classify primary intent
    intent = await self.classify_intent(query)

    # 2. Identify mentioned entities
    entities = await self.extract_entities(query)

    # 3. ALWAYS check multiple angles
    tasks = []

    # Primary agent based on intent
    tasks.append(self.invoke_primary_agent(intent, query))

    # If companies mentioned → check customer relationship
    if entities.companies:
        tasks.append(self.customer_intel_agent.lookup_batch(entities.companies))

    # If opportunity/company → check competitor activity
    if intent in [MARKET_INTEL, CUSTOMER_INTEL] or entities.companies:
        tasks.append(self.competitor_intel_agent.check_activity(entities))

    # If opportunity → check product fit
    if intent == MARKET_INTEL and entities.requirements:
        tasks.append(self.product_fit_agent.match(entities.requirements))

    # 4. Execute in parallel
    results = await asyncio.gather(*tasks)

    # 5. Synthesize with session context
    return await self.synthesize(results, context)
```

#### Intent-to-Agent Routing

| Primary Intent | Primary Agent | Always Also Check |
|----------------|---------------|-------------------|
| `MARKET_INTEL` | MarketIntelAgent | CustomerIntel (if company), CompetitorIntel, ProductFit |
| `CUSTOMER_INTEL` | CustomerIntelAgent | CompetitorIntel, MarketIntel (news about them) |
| `COMPETITOR_INTEL` | CompetitorIntelAgent | CustomerIntel (our relationship) |
| `KYP_DUE_DILIGENCE` | KYPAgent | CustomerIntel (relationship context) |
| `PRODUCT_FIT` | ProductFitAgent | CustomerIntel (their needs) |

---

## 4. Infrastructure Agents

### 4.1 WebSearchAgent

**Domain:** Real-time web search via Perplexity
**Used By:** All domain agents for real-time data

### 4.2 DatabaseAgent

**Domain:** PostgreSQL operations
**Used By:** All domain agents for database queries

### 4.3 MCP Tools (SAP/CPI)

**Domain:** SAP integration
**Used By:** CustomerIntelAgent primarily

---

## 5. Guide-Agent Mapping

| Agent | Guide | Status |
|-------|-------|--------|
| MarketIntelAgent | `market_intel_guide.md` | Create (consolidate from industry_news_guide.md) |
| CustomerIntelAgent | `customer_intel_guide.md` | Create (extract from sales_intelligence_agent_guide.md) |
| CompetitorIntelAgent | `competitor_intel_guide.md` | Existing (rename from competitor_insights_guide.md) |
| KYPAgent | `kyp_guide.md` | Existing (rename from KYP_guide.md) |
| ProductFitAgent | `product_fit_guide.md` | Create |
| SalesOpsAgent | `orchestration_guide.md` | Existing (update) |

---

## 6. A2A Communication

### 6.1 Capability Discovery

Each agent implements `_extract_primary_capabilities()`:

```python
def _extract_primary_capabilities(self) -> List[Capability]:
    return [
        Capability(
            name="industry_news",
            domain="market_intelligence",
            description="Marine/offshore industry news and announcements",
            keywords=["news", "market", "industry", "announcement"],
        ),
        # ... more capabilities
    ]
```

### 6.2 Semantic Routing

Agents are selected via `Pipeline.router(routing_strategy="semantic")`:

```python
router = Pipeline.router(
    agents=[market_intel, customer_intel, competitor_intel, kyp, product_fit],
    routing_strategy="semantic",
    error_handling="graceful",
)
```

### 6.3 Shared Memory

Agents share state via `SharedMemoryPool`:

```python
# Store validated customer data
shared_memory.store("validated_customers", {"penguin": customer_data})

# Retrieve in another agent
customer_data = shared_memory.retrieve("validated_customers")
```

---

## 7. Implementation Status

> **Last Verified:** 2026-02-04

| Feature | Status | Implementation Notes |
|---------|--------|---------------------|
| **A2A AI-Enhanced Routing** | ✅ Active | Hybrid routing: LLM intent (60%) + Kaizen capability matching (40%). Uses GPT-4o via QueryUnderstandingEngine for semantic understanding, combined with `matches_requirement()` for fine-grained matching. |
| **SharedMemoryPool** | ✅ Active | Read/write coordination via `_check_memory_for_context()` and `write_to_memory()`. 1-hour cache TTL. All key agents implement both. |
| **Agent Enrichment** | ✅ Active | Via `request_enrichment(capability, data)`. Standardized A2A response format (`success`, `result_data`, `error_message`). Implemented in DueDiligenceAgent (customer_matching) and MarineIntelAgent (competitor_intel). |
| **SAP CPI MCP Server** | ✅ Active | 13 tools for external AI integration: `sap_check_credit`, `sap_get_customer`, `sap_get_kyp_assessment`, `cec_get_opportunity`, `ipas_get_configuration`, etc. Internal agents use client libraries directly. |
| **CEC Integration** | ✅ Simulated | Uses `CPISimulator` when `simulation_mode=True`. Real CPI integration pending iFlow deployment. |
| **IPAS Integration** | ✅ Simulated | Uses `CPISimulator` for development. Parses `SSZ sample.XML` for BOM structure. |
| **Sanctions Screening** | ✅ Simulated | `AravoSimulator` checks against OFAC, EU, UN, MAS lists. Returns `NO_ADVERSE_FINDINGS` or `ADVERSE_FINDINGS`. |
| **Query Understanding** | ✅ Active | Uses OpenAI GPT-4o for intent classification with JSON response format. Powers the AI-enhanced routing. |
| **KYP Templates** | ✅ Active | Full KYP infrastructure at `services/kyp_processor.py`, `services/kyp_report.py`, and `docs/guides/KYP_guide.md` (1496 lines). |

### AI-Enhanced Routing Algorithm

The routing system uses a hybrid approach combining:

1. **LLM Intent Classification (60% weight):** GPT-4o extracts semantic intent from natural language queries
2. **Kaizen Capability Matching (40% weight):** Uses `Capability.matches_requirement()` for fine-grained matching

```python
# Combined score calculation
combined_score = (0.6 * llm_intent_score) + (0.4 * capability_score)

# Accept if combined score >= 0.3 (meaningful match)
if combined_score >= 0.3:
    return selected_agent
```

### A2A Response Format Standard

All agents return this standardized format for A2A compatibility:

```python
{
    "success": True,
    "agent_id": "agent_name",
    "result_data": {
        # Agent-specific results here
    },
    "error_message": None,
    "metadata": {"routing": "a2a_run"}
}
```

### Simulation Mode

Order Processing agents support `simulation_mode` for development without SAP credentials:

```python
from lead_to_cash.agents import OpportunityAgent, OpportunityConfig

# Development mode - uses simulators
config = OpportunityConfig(simulation_mode=True)
agent = OpportunityAgent(config)

# Production mode - uses real CPI
config = OpportunityConfig(simulation_mode=False)
agent = OpportunityAgent(config)
```

### A2A Communication Pattern

Agents can request enrichment from other agents by capability:

```python
# In any agent with _registry set
result = await self.request_enrichment(
    capability="customer_validation",
    data={"task": "Validate customer", "customer_id": "1234567"}
)
```

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.3 | 2026-02-04 | AI Architecture Team | AI-enhanced routing (LLM + Kaizen hybrid), fixed data contracts, standardized A2A response format |
| 2.2 | 2026-02-04 | AI Architecture Team | Fixed A2A routing (18% threshold, public API), added actual enrichment calls, verified KYP/MCP integration |
| 2.1 | 2026-02-04 | AI Architecture Team | Added Implementation Status section |
| 2.0 | 2026-01-21 | AI Architecture Team | A2A semantic routing architecture |
| 1.0 | 2026-01-21 | AI Architecture Team | Initial architecture definition |

---

## 9. Related Documents

- `orchestration_guide.md` - Detailed orchestration patterns
- `market_intel_guide.md` - MarketIntelAgent output standards
- `customer_intel_guide.md` - CustomerIntelAgent output standards
- `competitor_intel_guide.md` - CompetitorIntelAgent output standards
- `kyp_guide.md` - KYPAgent output standards
- `product_fit_guide.md` - ProductFitAgent output standards
