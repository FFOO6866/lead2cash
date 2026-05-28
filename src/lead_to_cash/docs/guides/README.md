# AI Agent Guides

This directory contains standardized guides for AI agents to produce consistent, comprehensive, and actionable intelligence outputs.

## Available Guides

| Guide | Version | Purpose | Primary Agent/Service |
|-------|---------|---------|----------------------|
| [unified_content_guide.md](./unified_content_guide.md) | 1.0 | "Scrape Once, Use Many" content pipeline (ADR-005) | unified_content/ |
| [orchestration_guide.md](./orchestration_guide.md) | 1.0 | Agent routing, data awareness, tool selection, conversation | AgentRegistry |
| [industry_news_guide.md](./industry_news_guide.md) | 2.7 | Industry news analysis and daily briefings | MarineIntelAgent |
| [competitor_intel_guide.md](./competitor_intel_guide.md) | 1.2 | Competitive intelligence analysis | CompetitorIntelAgent |
| [competitor_insights_guide.md](./competitor_insights_guide.md) | 2.4 | Competitive intelligence output formats | CompetitorIntelAgent |
| [KYP_guide.md](./KYP_guide.md) | 2.5 | Know Your Partner due diligence | DueDiligenceAgent |

## Guide Hierarchy

```
unified_content_guide.md        ← FOUNDATION: Single content pipeline (ADR-005)
    │
    ├── All news sources → UnifiedContent → KB linking → Multi-purpose
    │
orchestration_guide.md          ← System-wide: How agents are selected and coordinated
    │
    ├── industry_news_guide.md     ← Output format for marine/industry news
    ├── competitor_intel_guide.md  ← Competitor intelligence analysis
    ├── competitor_insights_guide.md ← Output format for competitor intelligence
    └── KYP_guide.md               ← Output format for customer due diligence
```

### Content Flow (ADR-005)

```
NewsAPI ─┐
RSS ─────┼─→ UnifiedIngestionPipeline ─→ ContentProcessor ─→ KB Linking
Perplexity┤                                    │
PressRooms┘                         SharedEmbeddingService
                                              │
                                              ↓
                              ┌───────────────┴───────────────┐
                              ↓               ↓               ↓
                     Competitor Intel   Marine Intel   Product Fit
```

## Guide Structure

### Orchestration Guide (System-Level)
1. **Query Understanding** - Intent classification, entity extraction, temporal parsing
2. **Data Inventory** - What data exists, coverage tracking, gap identification
3. **Tool Selection** - Dynamic tool chains, fallback strategies
4. **Conversation** - Multi-turn, clarifications, follow-ups
5. **Integration** - How to extend existing registry.py and gateway.py

### Output Guides (Agent-Level)
1. **Overview** - Purpose and scope
2. **Anti-Hallucination Rules** - Data integrity requirements
3. **Categories** - Classification taxonomy
4. **Output Format** - JSON/Markdown specifications
5. **Scoring** - Priority and confidence calculation
6. **Source Hierarchy** - Source credibility tiers
7. **Actionable Intelligence** - BU-level analysis requirements
8. **Quality Standards** - Data quality requirements

## MANDATORY: Agent Guide Loading

All agents MUST load and follow their respective guides:

```python
# At agent initialization
class MarineIntelAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config=config, signature=MarineIntelSignature())

        # MANDATORY: Reference guide
        self.GUIDE_PATH = "src/lead_to_cash/docs/guides/industry_news_guide.md"

        # Key requirements enforced from guide:
        # 1. Every finding MUST include source URL
        # 2. Use evidence-based terminology
        # 3. Provide actionable intelligence (Section 8)
        # 4. BU-level analysis (Section 8.3)
```

## Integration Points

| Component | File | Guides Used |
|-----------|------|-------------|
| **AgentRegistry** | `agents/registry.py` | `orchestration_guide.md` |
| **Gateway** | `core/gateway.py` | `orchestration_guide.md` |
| **MarineIntelAgent** | `agents/marine_intel_agent.py` | `industry_news_guide.md` |
| **CompetitorIntelAgent** | `agents/competitor_intel_agent.py` | `competitor_insights_guide.md` |
| **DueDiligenceAgent** | `agents/due_diligence_agent.py` | `KYP_guide.md` |
| **WebSearchAgent** | `agents/web_search_agent.py` | All guides (capability mapping) |

## Key Principles

### 1. Semantic Understanding (Not Keywords)
```python
# WRONG: Keyword matching
if "caterpillar" in query:
    use_competitor_agent()

# RIGHT: Intent classification
parsed = await query_engine.parse(query)
if parsed.intent == QueryIntent.COMPETITOR_INTEL:
    use_competitor_agent()
```

### 2. Data Awareness
```python
# WRONG: Always search everything
results = await perplexity.search(query)

# RIGHT: Check inventory first
inventory = await data_inventory.check_coverage(parsed_query)
if inventory.has_local_data:
    results = await vector_search(query)  # Use 3 years of scraped data
else:
    results = await perplexity.search(query)  # Real-time fallback
```

### 3. Tool Selection (Not Hardcoded)
```python
# WRONG: Fixed tool per agent
class CompetitorAgent:
    def query(self):
        return self.perplexity.search()

# RIGHT: Dynamic tool chain
tools = TOOL_CHAINS[parsed_query.intent]  # ["vector_search", "perplexity", "eodhd"]
for tool in tools:
    result = await execute_tool(tool)
    if is_sufficient(result):
        break
```

### 4. Conversational (Like Claude)
```python
# WRONG: Single-turn only
response = agent.query("What about Caterpillar?")

# RIGHT: Multi-turn with clarification
response = await conversation.process(
    session_id="user-session",
    message="What about Caterpillar?",
)
if response["type"] == "clarification_needed":
    # Ask: "What time period?" with options
```

### 5. Actionable Intelligence (Not Raw Data)
```python
# WRONG: Raw data dump
"Revenue: $16.2B, EPS: $4.25"

# RIGHT: Actionable insight
"Revenue declined 8% YoY - potential market share opportunity.
 RRPS Action: Target their marine customers showing dissatisfaction."
```

## Maintenance

- Guides are version-controlled with revision history
- Changes require review before deployment
- Version history maintained in each guide
- All agents must reference the latest guide version

## Files

```
docs/guides/
├── README.md                      ← This file
├── unified_content_guide.md       ← Content pipeline (v1.0) - FOUNDATION
├── orchestration_guide.md         ← System orchestration (v1.0)
├── industry_news_guide.md         ← Marine news output (v2.7)
├── competitor_intel_guide.md      ← Competitor intel analysis (v1.2)
├── competitor_insights_guide.md   ← Competitor intel output (v2.4)
├── KYP_guide.md                   ← Due diligence output (v2.5)
├── market_intel_guide.md          ← Market intelligence
├── customer_intel_guide.md        ← Customer intelligence
├── product_fit_guide.md           ← Product fit scoring
└── sales_intelligence_agent_guide.md ← Unified agent guide
```
