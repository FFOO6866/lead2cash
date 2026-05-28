# Industry News Intelligence Guide

> ⚠️ **SUPERSEDED** - For MarketIntelAgent, see `market_intel_guide.md`
> This guide contains additional detail for reference.
> **Date:** 2026-01-21
> **Content Source:** Unified Content Pipeline ([ADR-005](../../adr/005-unified-content-architecture.md))

---

> **Version:** 2.8
> **Last Updated:** 2026-01-22
> **Purpose:** Detailed reference for industry news analysis (supplementary to market_intel_guide.md)
> **Primary Guide:** `market_intel_guide.md`

---

## IMPORTANT: Unified Content Architecture

As of ADR-005, all news intelligence flows through the **Unified Content Pipeline**.

### Key Changes

1. **Single Ingestion Point**: All sources (NewsAPI, RSS, Perplexity, press rooms) feed into `UnifiedIngestionPipeline`
2. **Shared Embedding**: Single embedding per URL via `SharedEmbeddingService` (eliminates 3x API costs)
3. **Mandatory KB Linking**: All content MUST be linked to Knowledge Base entities
4. **Multi-Purpose Classification**: Same content scored for competitor intel, marine intel, and KB relevance

### Usage

```python
from lead_to_cash.services.unified_content import (
    run_full_ingestion,
    run_priority_ingestion,
    get_unified_content_db,
    ContentPurpose,
)

# Full ingestion from all 20+ sources
results = await run_full_ingestion()

# Query market intel content
db = get_unified_content_db()
market_content = await db.list_content(
    purposes=[ContentPurpose.MARKET_INTEL.value],
)
```

See [Unified Content Guide](unified_content_guide.md) for full details.

---

## CRITICAL: Data Integrity Rules

### MANDATORY: Agent Guide Reference

**⚠️ All agents performing industry news analysis MUST load and follow this guide.**

```python
# Agent MUST load guide at initialization
GUIDE_PATH = "src/lead_to_cash/docs/guides/industry_news_guide.md"

class MarineIntelAgent:
    def __init__(self):
        self.guide = self._load_guide(GUIDE_PATH)
        # Guide rules are MANDATORY for all news analysis
```

### MANDATORY: Anti-Hallucination Policy

**AI agents MUST follow these rules without exception:**

1. **ONLY report facts explicitly stated in source documents**
   - NEVER infer, assume, or generate information not in the source
   - If a contract value is not stated, report as "Not disclosed" - NEVER estimate
   - If an engine type is not specified, report as "Not specified" - NEVER guess

2. **ALWAYS include source attribution**
   - Every fact MUST have a verifiable source URL
   - Every date MUST come from the source, not be assumed
   - If source is unavailable, mark data as "UNVERIFIED"

3. **NEVER generate fictional examples or data**
   - All company names must be real, verified entities
   - All contract values must come from actual announcements
   - All vessel specifications must be from official sources

4. **When uncertain, flag for human review**
   - Confidence < 0.7 = requires human verification
   - Conflicting sources = flag both, do not resolve
   - Missing critical data = mark as "INCOMPLETE"

### MANDATORY: Reference Link Requirement

**⚠️ CRITICAL: Every news item MUST include a verifiable source URL.**

```json
{
  "headline": "News headline",
  "source": {
    "url": "https://example.com/article",  // REQUIRED - Must be real URL
    "name": "Publication Name",
    "published_date": "YYYY-MM-DD"
  },
  "confidence": 0.0-1.0
}
```

**Rules:**
1. **MUST be real, accessible URLs** - No fabricated links
2. **If no URL available** - Mark as `"requires_verification": true`
3. **Multiple sources = higher confidence** - 2+ sources boost score
4. **Primary sources preferred** - Official announcements > news coverage

### MANDATORY: Evidence-Based Terminology

**⚠️ CRITICAL: Use factual language. Never assert unverified attributes.**

| ❌ INCORRECT | ✅ CORRECT |
|-------------|-----------|
| "Major contract win" | "Contract announced for [value] per source" |
| "Significant growth" | "[X]% increase reported in [source]" |
| "Industry-leading" | "Ranked #[X] per [source publication]" |
| "Strong demand" | "[X] orders announced in [timeframe] per [source]" |

**Status Terminology:**
- `CONFIRMED` - Verified in official press release with URL
- `REPORTED` - Covered by trade media with URL
- `UNVERIFIED` - Single source or no URL available
- `REQUIRES_VERIFICATION` - Conflicting information

### Source Verification Checklist

Before including ANY news item, verify:
- [ ] Source URL is accessible and loads correctly
- [ ] Publication date is within acceptable range (< 7 days for daily briefing)
- [ ] Company names match official registered names
- [ ] Numbers and values are explicitly stated in source (not inferred)
- [ ] No paywalled content cited without access
- [ ] **Reference URL is included and verifiable**
- [ ] **Evidence-based terminology used (no unverified assertions)**

---

## 1. Overview

This guide defines how AI agents should collect, analyze, and present industry news insights for Rolls-Royce Power Systems (RRPS) sales operations.

### 1.1 Target Vertical

| Attribute | Specification | Source |
|-----------|---------------|--------|
| **Industry** | Marine & Offshore Power Systems | RRPS Business Unit |
| **Product Focus** | Medium-speed diesel/gas engines | Product Catalog |
| **RPM Range** | 300-1000 RPM (TARGET) | Engineering Specs |
| **Power Range** | 700 kW - 40,000 kW | Product Portfolio |
| **Key Brands** | MTU, Bergen Engines | RRPS Corporate |

### 1.2 Target Markets

| Market Segment | Priority | Description |
|----------------|----------|-------------|
| **Marine Transportation** | HIGH | Ferries, tugs, OSVs, cargo vessels |
| **Offshore Oil & Gas** | HIGH | Platform supply, FPSOs, drilling |
| **FPSO/FSO** | HIGH | Floating production and storage |
| **Power Generation** | MEDIUM | Land-based and offshore gensets |
| **Yachts & Special Vessels** | MEDIUM | Superyachts, research vessels |

---

## 2. News Categories

AI agents MUST classify each news item into one of the following categories:

### 2.1 Primary Categories

#### Sales Opportunities

| Category ID | Category Name | Description | Signal Keywords |
|-------------|---------------|-------------|-----------------|
| `NEWBUILD` | New Vessel Orders | Shipyard contracts, vessel orders, construction starts | "contract awarded", "vessel order", "shipbuilding agreement" |
| `RETROFIT_REPOWER` | Retrofit & Repowering | Engine replacement, upgrades, conversions | "repower", "retrofit", "engine replacement", "upgrade" |
| `OFFSHORE_PROJECT` | Offshore Projects | FID announcements, EPCIC contracts, field development | "FID", "final investment decision", "EPCIC", "sanctioned" |
| `FLEET_EXPANSION` | Fleet Expansion | Operator fleet growth, acquisitions | "fleet expansion", "fleet renewal", "acquisition" |
| `FINANCING_CAPEX` | Financing & CAPEX | Investment decisions, funding announcements | "financing", "investment", "funding", "ECA" |

#### Market Intelligence

| Category ID | Category Name | Description | Signal Keywords |
|-------------|---------------|-------------|-----------------|
| `REGULATION` | Regulatory & Policy | IMO rules, MPA requirements, emissions standards, government policy | "IMO", "regulation", "emission", "compliance", "Tier III", "policy", "mandate" |
| `FUEL_TRANSITION` | Fuel Transition | LNG, methanol, ammonia, hydrogen adoption trends | "LNG", "methanol", "ammonia", "dual-fuel", "alternative fuel", "decarbonization" |
| `MARKET_REPORT` | Market Reports & Outlooks | Industry forecasts, analyst reports, market data | "outlook", "forecast", "market report", "analysis", "DNV", "Clarksons" |
| `TECHNOLOGY` | Technology Announcements | New propulsion tech, digital solutions, innovation | "technology", "innovation", "digital", "autonomous", "hybrid", "electric" |
| `INCIDENT_RELIABILITY` | Incidents & Reliability | Engine failures, breakdowns, recalls, safety issues | "failure", "breakdown", "recall", "investigation", "incident" |

#### Industry Activity

| Category ID | Category Name | Description | Signal Keywords |
|-------------|---------------|-------------|-----------------|
| `INDUSTRY_EVENT` | Events & Conferences | Trade shows, maritime weeks, conferences, exhibitions | "trade show", "conference", "exhibition", "maritime week", "summit", "forum" |
| `PARTNERSHIP` | Partnerships & Alliances | Industry collaborations, JVs, strategic alliances (non-competitor) | "partnership", "collaboration", "alliance", "MoU", "joint venture", "agreement" |
| `LEADERSHIP_CHANGE` | Leadership & Organization | Executive appointments, organizational restructuring | "appointed", "CEO", "managing director", "restructuring", "leadership", "board" |
| `M_AND_A` | Mergers & Acquisitions | Industry consolidation, company acquisitions, spin-offs | "acquisition", "merger", "acquired", "takeover", "divest", "spin-off" |

### 2.2 Secondary Tags (Multi-select)

```yaml
vessel_types:
  - ferry
  - tug
  - osv          # Offshore Supply Vessel
  - psv          # Platform Supply Vessel
  - ahts         # Anchor Handling Tug Supply
  - tanker
  - container
  - cargo
  - fpso         # Floating Production Storage Offloading
  - drilling
  - yacht
  - cruise
  - naval
  - fishing
  - dredger
  - construction # Offshore construction vessels
  - harbour_craft
  - cable_layer
  - other

fuel_types:
  - diesel
  - hfo          # Heavy Fuel Oil
  - lng          # Liquefied Natural Gas
  - methanol
  - ammonia
  - dual_fuel
  - hydrogen
  - battery_hybrid

components:
  - main_engine
  - genset       # Generator Set
  - auxiliary
  - propulsion
  - thruster

lifecycle_stage:
  - newbuild
  - retrofit
  - maintenance
  - decommission
```

---

## 3. Output Format Specification

### 3.1 Standard News Item Structure

```json
{
  "id": "NEWS-YYYY-MM-DD-NNN",
  "headline": "Max 120 characters - exact headline from source or accurate summary",
  "summary": "Max 500 characters - factual summary using ONLY source information",
  "category": "CATEGORY_ID from Section 2.1",
  "secondary_tags": ["tag1", "tag2"],
  "priority": 1-10,
  "priority_rationale": "Explain calculation using Section 4 formula",

  "source": {
    "name": "Exact source publication name",
    "url": "Full URL - MUST be accessible",
    "published_date": "YYYY-MM-DD from source",
    "accessed_date": "YYYY-MM-DD when scraped",
    "credibility_tier": "TIER_1|TIER_2|TIER_3|TIER_4"
  },

  "entities": {
    "companies": ["Only companies explicitly named in source"],
    "shipyards": ["Only if explicitly stated"],
    "operators": ["Only if explicitly stated"],
    "locations": ["Country/city from source"],
    "engines": ["Only if engine model explicitly stated"],
    "vessel_count": "Number or null if not stated",
    "vessel_types": ["From source"],
    "contract_value": "Exact value from source or 'Not disclosed'"
  },

  "data_quality": {
    "all_facts_sourced": true,
    "confidence_score": 0.0-1.0,
    "requires_verification": ["List any fields needing human review"],
    "missing_data": ["List fields not available in source"]
  },

  "regional_context": {
    "region": "singapore|indonesia|malaysia|...",
    "market_relevance": "Why relevant - based on RRPS market presence",
    "competitive_landscape": "Only include if competitor mentioned in source"
  },

  "sales_signals": ["From defined list in Section 7"],

  "suggested_actions": [
    {
      "action": "Specific action description",
      "owner": "Team/role",
      "urgency": "HIGH|MEDIUM|LOW",
      "deadline": "YYYY-MM-DD",
      "rationale": "Why this action based on source data"
    }
  ],

  "key_insights": [
    "Insight 1 - must be derived from source facts",
    "Insight 2 - no speculation"
  ],

  "metadata": {
    "created_at": "ISO 8601 timestamp",
    "agent": "MarineIntelAgent|CompetitorIntelAgent",
    "agent_version": "1.0",
    "processing_notes": "Any issues encountered"
  }
}
```

### 3.2 Daily Briefing Format

```markdown
# RRPS Industry Intelligence Briefing
**Date:** YYYY-MM-DD | **Region:** APAC | **Prepared by:** AI Intelligence System

---

## Data Quality Statement

- **Total sources analyzed:** [N]
- **Tier 1-2 sources:** [N]%
- **Items requiring verification:** [N]
- **Data freshness:** All items < 7 days old

---

## Executive Summary

**Key Metrics (from verified sources only):**
- Total news items analyzed: [N]
- High-priority opportunities (8-10): [N]
- New vessel orders tracked: [N]
- Retrofit opportunities: [N]

**Top 3 Actionable Items:**
1. [Category] Brief description (Priority: X/10) - Source: [Name]
2. [Category] Brief description (Priority: X/10) - Source: [Name]
3. [Category] Brief description (Priority: X/10) - Source: [Name]

---

## Section 1: Immediate Sales Opportunities (Priority 8-10)

### 1.1 [Headline]
**Category:** [CAT] | **Priority:** X/10 | **Source:** [URL]

**Facts from Source:**
- [Bullet points of verified facts only]

**Recommended Actions:**
- [ ] Action 1 (Due: YYYY-MM-DD)
- [ ] Action 2 (Due: YYYY-MM-DD)

**Data Quality:** [Any caveats or missing information]

---

## Section 2: Market Intelligence (Priority 5-7)

[Similar structure with source attribution]

---

## Section 3: Competitive Intelligence

| Competitor | Activity | Source | Threat Level |
|------------|----------|--------|--------------|
| [Name] | [Verified activity] | [Source] | HIGH/MED/LOW |

**Note:** Only include competitive moves verified from credible sources.

---

## Section 4: Items Requiring Human Verification

| Item | Issue | Action Required |
|------|-------|-----------------|
| [ID] | [Why flagged] | [What to verify] |

---

## Appendix: Source List

| # | Source | Tier | URL | Accessed |
|---|--------|------|-----|----------|
| 1 | [Name] | [1-4] | [URL] | [Date] |
```

---

## 4. Priority Scoring Criteria

### 4.1 Priority Scale (1-10)

| Score | Level | Description | Response Time |
|-------|-------|-------------|---------------|
| 9-10 | CRITICAL | Confirmed order with RRPS/MTU/Bergen specification | Same day |
| 7-8 | HIGH | Strong lead, RFQ released, or competitive threat | Within 48 hours |
| 5-6 | MEDIUM | Market intelligence, early-stage opportunity | Within 1 week |
| 3-4 | LOW | General industry trend, no immediate action | Monthly review |
| 1-2 | MONITOR | Background information only | Quarterly review |

### 4.2 Priority Calculation Formula

```python
# Base score from category (max 3)
CATEGORY_WEIGHTS = {
    "NEWBUILD": 3,
    "RETROFIT_REPOWER": 3,
    "OFFSHORE_PROJECT": 2,
    "FUEL_TRANSITION": 2,
    "REGULATION": 1,
    "FLEET_EXPANSION": 2,
    "INCIDENT": 2,
    "FINANCING": 1,
}

# Regional weight (max 3)
REGION_WEIGHTS = {
    "singapore": 3,
    "indonesia": 2,
    "malaysia": 2,
    "australia": 2,
    "thailand": 1,
    "vietnam": 1,
    "philippines": 1,
    "china": 2,
    "korea": 2,
    "japan": 2,
    "india": 1,
}

# Stage weight (max 3)
STAGE_WEIGHTS = {
    "confirmed_order": 3,
    "rfq_released": 2,
    "planning_stage": 1,
    "early_concept": 0,
}

# Calculate base (max 9)
base_priority = category_weight + region_weight + stage_weight

# Boosters (apply only if condition verified in source)
if "MTU" in source_text or "Bergen" in source_text:
    base_priority += 2  # Direct opportunity
if customer_is_existing_rrps_account:  # Verify against CRM
    base_priority += 2
if "RFQ" in source_text or "tender" in source_text:
    base_priority += 1
if contract_value and contract_value > 100_000_000:
    base_priority += 1

# Cap at 10
final_priority = min(base_priority, 10)
```

### 4.3 Priority Boosters (Only Apply If Verified)

| Condition | Boost | Verification Required |
|-----------|-------|----------------------|
| MTU/Bergen engine specified | +2 | Engine name in source text |
| Existing RRPS customer | +2 | Match against CRM account list |
| RFQ/tender released | +1 | "RFQ", "tender", "invitation to bid" in source |
| Competitor named as winner | +1 | Competitor explicitly named |
| Contract value > $100M | +1 | Value explicitly stated |
| Vessel count > 5 | +1 | Number explicitly stated |

---

## 5. Source Hierarchy

### 5.1 Source Credibility Tiers

| Tier | Credibility | Examples | Trust Level |
|------|-------------|----------|-------------|
| **Tier 1** | VERIFIED | Company press releases, SGX/NYSE filings, MPA announcements | 100% - Use directly |
| **Tier 2** | HIGH | Lloyd's List, TradeWinds, Seatrade Maritime | 90% - Minor verification |
| **Tier 3** | MEDIUM | Maritime Executive, Splash247, Offshore Engineer | 80% - Cross-reference recommended |
| **Tier 4** | LOW | General news, blogs, unverified aggregators | 60% - Must verify before use |

### 5.2 Comprehensive Source Registry (54 Sources)

> **Source Registry:** `services/source_registry.py` contains the full programmatic definition.

#### 5.2.1 Regulatory & Environmental (8 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **IMO** | imo.org/en/MediaCentre | 1 | CRITICAL | Web |
| **MPA Singapore** | mpa.gov.sg/media-centre | 1 | CRITICAL | Web |
| **DNV** | dnv.com/news | 1 | CRITICAL | RSS |
| **Lloyd's Register** | lr.org/en/news | 1 | HIGH | Web |
| **Bureau Veritas** | marine-offshore.bureauveritas.com/newsroom | 1 | HIGH | Web |
| **ClassNK** | classnk.com/hp/en/info_service | 1 | HIGH | Web |
| **EU Maritime** | transport.ec.europa.eu | 1 | HIGH | Web |
| **EMSA** | emsa.europa.eu/newsroom | 1 | MEDIUM | Web |

#### 5.2.2 Singapore & Southeast Asia (10 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **Singapore Maritime Foundation** | smf.com.sg | 1 | CRITICAL | Web |
| **ASMI** | asmi.com | 2 | HIGH | Web |
| **Singapore Shipping Association** | ssa.org.sg | 2 | HIGH | Web |
| **Splash247** | splash247.com | 2 | CRITICAL | RSS |
| **Seatrade Maritime** | seatrade-maritime.com | 2 | HIGH | RSS |
| **Marine Dept Malaysia** | marine.gov.my | 1 | MEDIUM | Web |
| **Indonesia DGST** | hubla.dephub.go.id | 1 | MEDIUM | Web |
| **Vietnam Maritime Admin** | vinamarine.gov.vn | 1 | MEDIUM | Web |
| **PSA International** | globalpsa.com | 2 | HIGH | Web |
| **Jurong Port** | jp.com.sg | 2 | MEDIUM | Web |

#### 5.2.3 General Maritime News (8 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **Maritime Executive** | maritime-executive.com | 2 | CRITICAL | RSS |
| **gCaptain** | gcaptain.com | 2 | CRITICAL | RSS |
| **TradeWinds** | tradewindsnews.com | 2 | HIGH | Web* |
| **Lloyd's List** | lloydslist.maritimeintelligence.informa.com | 2 | HIGH | Web* |
| **Hellenic Shipping News** | hellenicshippingnews.com | 3 | HIGH | RSS |
| **Ship & Bunker** | shipandbunker.com | 2 | HIGH | RSS |
| **SeaNews Turkey** | seanews.com.tr | 3 | MEDIUM | Web |
| **Marine Link** | marinelink.com | 3 | MEDIUM | RSS |

*Requires subscription

#### 5.2.4 Offshore Oil & Gas (5 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **Offshore Engineer** | oedigital.com | 2 | CRITICAL | RSS |
| **Upstream Online** | upstreamonline.com | 2 | HIGH | Web* |
| **Rigzone** | rigzone.com | 2 | HIGH | RSS |
| **Offshore Magazine** | offshore-mag.com | 2 | MEDIUM | RSS |
| **Asian Oil & Gas** | aaborneointernational.com | 2 | HIGH | Web |

#### 5.2.5 Shipyards & Shipbuilding (6 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **Seatrium** | seatrium.com/news | 1 | CRITICAL | Web |
| **Keppel Corporation** | kepcorp.com/en/news-centre | 1 | CRITICAL | Web |
| **Hyundai Heavy Industries** | english.hhi.co.kr/news | 1 | HIGH | Web |
| **Samsung Heavy Industries** | samsungshi.com/eng/pr/news | 1 | HIGH | Web |
| **CSSC China** | cssc.net.cn | 1 | HIGH | Web |
| **Fincantieri** | fincantieri.com/en/media/press-releases | 1 | MEDIUM | Web |

#### 5.2.6 Engine Manufacturers - Competitors (7 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **Wärtsilä** | wartsila.com/media/news | 1 | CRITICAL | Web |
| **MAN Energy Solutions** | man-es.com/company/press | 1 | CRITICAL | Web |
| **Caterpillar Marine** | cat.com/en_US/news.html | 1 | CRITICAL | Web |
| **MTU/Rolls-Royce Power** | mtu-solutions.com/news | 1 | HIGH | Web |
| **Cummins Marine** | cummins.com/news | 1 | HIGH | Web |
| **Volvo Penta** | volvopenta.com/news | 1 | MEDIUM | Web |
| **Yanmar Marine** | yanmar.com/global/news | 1 | MEDIUM | Web |

#### 5.2.7 Industry Associations (6 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **BIMCO** | bimco.org/news | 2 | HIGH | Web |
| **ICS** | ics-shipping.org/news | 2 | HIGH | Web |
| **CLIA** | cruising.org/news | 2 | MEDIUM | Web |
| **IACS** | iacs.org.uk/news | 1 | HIGH | Web |
| **SEA Europe** | seaeurope.eu/news | 2 | MEDIUM | Web |
| **Interferry** | interferry.com/news | 2 | MEDIUM | Web |

#### 5.2.8 Financial & Market Data (4 Sources)

| Source | URL | Tier | Priority | Type |
|--------|-----|------|----------|------|
| **SGX** | sgx.com/securities/company-announcements | 1 | HIGH | API |
| **Clarksons Research** | clarksons.com/research | 2 | MEDIUM | Web* |
| **VesselsValue** | vesselsvalue.com | 2 | MEDIUM | API* |
| **EODHD** | eodhd.com | 3 | MEDIUM | API |

*Requires subscription

#### 5.2.9 Source Summary

| Category | Sources | Critical | High | Medium |
|----------|---------|----------|------|--------|
| Regulatory | 8 | 3 | 4 | 1 |
| Singapore/SEA | 10 | 2 | 5 | 3 |
| General Maritime | 8 | 2 | 4 | 2 |
| Offshore O&G | 5 | 1 | 3 | 1 |
| Shipyards | 6 | 2 | 3 | 1 |
| Engine OEMs | 7 | 3 | 2 | 2 |
| Associations | 6 | 0 | 3 | 3 |
| Financial | 4 | 0 | 1 | 3 |
| **TOTAL** | **54** | **13** | **25** | **16** |

#### 5.2.10 Programmatic Access

```python
from lead_to_cash.services.source_registry import (
    get_all_sources,
    get_sources_by_category,
    get_priority_sources,
    get_rss_sources,
    get_source_stats,
)

# Get all 54 sources
all_sources = get_all_sources()

# Get by category
regulatory = get_sources_by_category("regulatory")
singapore = get_sources_by_category("singapore_sea")

# Get critical/high priority only
priority = get_priority_sources(["critical", "high"])

# Get RSS-enabled sources (for automated scraping)
rss_sources = get_rss_sources()

# Get statistics
stats = get_source_stats()
# {'total': 54, 'by_category': {...}, 'by_priority': {...}}
```

### 5.3 Source Rejection Criteria

**DO NOT use sources that:**
- Require subscription without verified access
- Have no publication date
- Are older than 30 days (for news items)
- Cannot be accessed via direct URL
- Are social media posts without official verification
- Aggregate content without original reporting

---

## 6. Regional Focus & Context

### 6.1 Priority Regions (RRPS APAC Focus)

| Rank | Region | Key Ports | RRPS Presence | Market Notes |
|------|--------|-----------|---------------|--------------|
| 1 | Singapore | Singapore | Service Center, HQ | Maritime hub, regulatory leader |
| 2 | Indonesia | Jakarta, Batam | Sales Office | Ferry market, offshore |
| 3 | Malaysia | Port Klang, Johor | Distributor | Offshore hub |
| 4 | Australia | Perth, Darwin | Service Partner | OSV, ferries |
| 5 | Thailand | Laem Chabang | Distributor | Regional shipping |
| 6 | Vietnam | Hai Phong, HCMC | Agent | Growing market |
| 7 | Philippines | Manila, Cebu | Agent | Ferry market |
| 8 | China | Shanghai, Guangzhou | Office | Shipbuilding |
| 9 | Korea | Busan, Ulsan | Partner | Major shipyards |
| 10 | Japan | Tokyo, Kobe | Partner | High-spec vessels |
| 11 | APAC Other | Various | Varies | Other APAC markets |

### 6.2 Regional Context Requirements

For each news item, include (ONLY if data available in source):
1. **Country/Region** - Where the activity is occurring
2. **Market relevance** - Why relevant to RRPS (based on presence above)
3. **Local considerations** - Only if mentioned in source

**DO NOT fabricate regional context not in the source.**

---

## 7. Sales Signals Classification

### 7.1 Signal Definitions

| Signal ID | Definition | Detection Keywords |
|-----------|------------|-------------------|
| `newbuild` | New vessel construction | "newbuild", "new vessel", "order", "contract" |
| `retrofit_repower` | Engine replacement/upgrade | "repower", "retrofit", "upgrade", "replacement" |
| `offshore_project` | Oil/gas project activity | "FID", "EPCIC", "offshore", "field development" |
| `regulation` | Compliance requirement | "IMO", "regulation", "compliance", "Tier III" |
| `fuel_transition` | Alternative fuel adoption | "LNG", "methanol", "dual-fuel", "ammonia" |
| `fleet_expansion` | Operator growth | "fleet", "expansion", "additional vessels" |
| `incident_reliability` | Mechanical issues | "failure", "breakdown", "incident", "recall" |
| `financing_capex` | Investment secured | "financing", "investment", "approved", "funding" |

### 7.2 Signal Detection Rules

**Only assign a signal if:**
- The keyword appears in the source text
- The context confirms the signal meaning
- Multiple signals can apply to one item

**Example:**
- "Maersk orders 6 methanol-powered vessels" → `newbuild` + `fuel_transition`
- "PSA Marine to repower ferries for IMO compliance" → `retrofit_repower` + `regulation`

---

## 8. MANDATORY: Actionable Intelligence Requirements

**⚠️ CRITICAL: Raw news reporting alone is NOT sufficient. Every industry news item MUST include actionable business intelligence for RRPS sales operations.**

### 8.1 What We Need vs What We DON'T Need

| ❌ RAW NEWS (Insufficient) | ✅ ACTIONABLE INTELLIGENCE (Required) |
|---------------------------|--------------------------------------|
| "Maersk orders 6 vessels from Hyundai" | "Maersk orders 6 vessels - engine spec TBD, RRPS product fit: MTU 8000 series for ferry application, contact: procurement dept Hyundai" |
| "Singapore MPA announces new emission rules" | "New MPA emission rules (effective 2027) - affects 40+ vessels in Singapore registry needing Tier III compliance, RRPS opportunity: retrofit gensets, target: PSA Marine, Penguin Ferries" |
| "Offshore project FID announced" | "Project FID creates OSV demand - 8-12 vessels needed, timeline: 2026-2027, RRPS competitive position: strong in PSV segment, key shipyards: Keppel, Sembcorp" |
| "Ferry operator expands fleet" | "Ferry operator fleet expansion - 3 vessels ordered, current fleet uses CAT engines, RRPS displacement opportunity, contact window: Q2 2026 for next order cycle" |

### 8.2 Required Analysis Categories

For each news item, provide analysis in these categories:

#### 8.2.1 RRPS Product Fit Analysis
- **Engine/Genset Match**: Which RRPS products fit this application?
- **Power Range**: Does the project fall within RRPS power range (700kW-40MW)?
- **Application Type**: Main propulsion, genset, auxiliary - which RRPS solution applies?
- **Fuel Compatibility**: Diesel, dual-fuel, methanol - RRPS product availability?

```json
{
  "product_fit": {
    "applicable_products": ["MTU 8000", "MTU 4000", "Bergen B35:40"],
    "power_range_match": true,
    "application": "main_propulsion|genset|auxiliary",
    "fuel_type_available": true|false,
    "fit_confidence": "HIGH|MEDIUM|LOW",
    "notes": "Specific product recommendation rationale"
  }
}
```

#### 8.2.2 Competitive Position Assessment
- **Current Incumbent**: What engines does the operator currently use?
- **Competitor Threat**: Which competitors are likely bidding?
- **RRPS Win Probability**: Based on relationship, product fit, pricing position
- **Displacement Opportunity**: If competitor incumbent, what's the switch trigger?

```json
{
  "competitive_position": {
    "current_incumbent": "CAT|Cummins|MAN|RRPS|Unknown",
    "competitor_threat": ["CAT", "Cummins"],
    "rrps_win_probability": "HIGH|MEDIUM|LOW",
    "displacement_opportunity": true|false,
    "rationale": "Why RRPS can/cannot win this"
  }
}
```

#### 8.2.3 Timeline & Urgency Assessment
- **Project Stage**: Concept, planning, RFQ, awarded?
- **Decision Timeline**: When will engine selection happen?
- **RRPS Action Window**: When must RRPS engage to influence spec?
- **Key Milestones**: What events trigger next steps?

```json
{
  "timeline": {
    "project_stage": "concept|planning|rfq|awarded|construction",
    "decision_date": "YYYY-MM-DD or estimate",
    "rrps_action_window": "YYYY-MM-DD deadline",
    "key_milestones": [
      {"event": "RFQ release", "date": "YYYY-MM-DD"},
      {"event": "Technical evaluation", "date": "YYYY-MM-DD"}
    ]
  }
}
```

### 8.3 BU-Level Analysis Requirements

**⚠️ CRITICAL: Zoom into the actual business unit level, not just group/corporate news.**

#### 8.3.1 Operator-Level Intelligence (Not Group Level)

| ❌ GROUP LEVEL (Insufficient) | ✅ BU LEVEL (Required) |
|------------------------------|------------------------|
| "Maersk fleet expansion" | "Maersk Line (container) vs Svitzer (tugs) - different BUs, different engine needs" |
| "Sembcorp Marine contract" | "Sembcorp Marine Admiralty Yard (OSV focus) vs Tuas Yard (rig focus) - target the right yard" |
| "POSH Offshore news" | "POSH Semco (PSVs) vs POSH Terasea (AHTS) - different vessel types, different engine specs" |

**Required Operator Details:**
```json
{
  "operator_analysis": {
    "parent_company": "Group name",
    "specific_bu": "Operating unit making the purchase",
    "bu_focus": "PSV|ferry|tug|AHTS|tanker",
    "fleet_size": "Number of vessels in this BU",
    "current_engine_mix": ["MTU", "CAT", "Cummins"],
    "procurement_cycle": "Annual|project-based|opportunistic",
    "key_contacts": ["Name/Title if public"],
    "rrps_relationship": "Existing customer|Prospect|Competitor-locked"
  }
}
```

#### 8.3.2 Shipyard-Level Intelligence

| ❌ GENERIC (Insufficient) | ✅ SPECIFIC (Required) |
|--------------------------|------------------------|
| "Keppel wins contract" | "Keppel Offshore - FELS yard (jackup rigs) vs Keppel Singmarine (OSVs) - different engine requirements" |
| "Chinese shipyard order" | "COSCO Dalian (large vessels) vs Fujian Mawei (ferries) - target yard with RRPS product fit" |

**Required Shipyard Details:**
```json
{
  "shipyard_analysis": {
    "parent_company": "Group name",
    "specific_yard": "Yard name and location",
    "yard_specialization": "OSV|ferry|tanker|container|rig",
    "typical_power_range": "Engine power range for their vessels",
    "preferred_engine_suppliers": ["Current supplier relationships"],
    "rrps_installed_base": "Number of RRPS engines delivered to this yard",
    "entry_strategy": "How RRPS can get specified at this yard"
  }
}
```

### 8.4 Project Pipeline Intelligence

**⚠️ CRITICAL: Track projects through their lifecycle with actionable updates.**

#### 8.4.1 Pipeline Stage Tracking

| Stage | Description | RRPS Action Required | Urgency |
|-------|-------------|---------------------|---------|
| **CONCEPT** | Early announcement, feasibility study | Monitor, prepare capability deck | LOW |
| **PLANNING** | Engineering started, specs being developed | Engage naval architect, influence spec | HIGH |
| **RFQ** | Tender released, bids requested | Submit competitive proposal | CRITICAL |
| **EVALUATION** | Bids under review, technical clarifications | Support evaluation, address concerns | CRITICAL |
| **AWARDED** | Contract signed, engine TBD or selected | If not selected, track for retrofit/next vessel | MEDIUM |
| **CONSTRUCTION** | Vessel building, engine on order | Service relationship, spare parts | LOW |

#### 8.4.2 Pipeline Intelligence Format

```json
{
  "pipeline_tracking": {
    "project_id": "PIPE-YYYY-MM-NNN",
    "project_name": "Project name",
    "current_stage": "concept|planning|rfq|evaluation|awarded|construction",
    "stage_entry_date": "YYYY-MM-DD",
    "expected_next_stage": "YYYY-MM-DD",

    "vessel_details": {
      "type": "ferry|osv|psv|ahts|tug",
      "quantity": 3,
      "power_requirement_kw": 5000,
      "fuel_type": "diesel|dual_fuel|methanol"
    },

    "stakeholders": {
      "owner": "End operator name",
      "shipyard": "Building yard",
      "naval_architect": "Design firm if known",
      "classification_society": "DNV|LR|BV|ABS"
    },

    "rrps_position": {
      "engaged": true|false,
      "spec_influence": "HIGH|MEDIUM|LOW|NONE",
      "proposal_submitted": true|false,
      "win_probability": "HIGH|MEDIUM|LOW",
      "competitor_status": ["CAT bidding", "Cummins preferred"]
    },

    "next_action": {
      "action": "Specific action required",
      "owner": "Sales rep or team",
      "deadline": "YYYY-MM-DD",
      "success_criteria": "What defines success"
    }
  }
}
```

### 8.5 Market Trend Implications

**⚠️ CRITICAL: Connect news to market trends with BU-specific implications.**

#### 8.5.1 Trend Analysis Format

| ❌ GENERIC TREND | ✅ BU-SPECIFIC IMPLICATION |
|-----------------|---------------------------|
| "LNG adoption increasing" | "LNG adoption in SE Asia ferries - affects 15+ operators, MTU gas engines competitive, target: Bintan Resort Ferries (current diesel, routes suitable for LNG)" |
| "OSV market recovering" | "OSV day rates up 25% in SE Asia - operators ordering 20+ vessels, PSV segment (RRPS strong) vs AHTS (competitor-dominated), focus on: POSH, Tidewater, Bourbon" |
| "Shipyard orderbooks full" | "Singapore/Korea yards booked through 2027 - Vietnamese yards (Ha Long, Song Thu) emerging alternative, RRPS needs type approval at new yards" |

```json
{
  "trend_implication": {
    "trend": "Description of industry trend",
    "affected_segments": ["ferry", "osv", "offshore"],
    "rrps_impact": "OPPORTUNITY|THREAT|NEUTRAL",

    "segment_breakdown": [
      {
        "segment": "ferry",
        "trend_impact": "Positive - fuel transition driving orders",
        "rrps_position": "Strong in dual-fuel",
        "target_operators": ["Operator A", "Operator B"],
        "competitive_threat": "CAT aggressive on pricing"
      }
    ],

    "recommended_response": {
      "strategic_action": "What RRPS should do",
      "tactical_actions": ["Action 1", "Action 2"],
      "timeline": "When to act",
      "resources_needed": "What's required"
    }
  }
}
```

---

## 9. Quality Assurance

### 9.1 Mandatory Fields Checklist

Every news item MUST have:
- [ ] Unique ID (format: NEWS-YYYY-MM-DD-NNN)
- [ ] Headline (max 120 chars, from source)
- [ ] Summary (max 500 chars, factual)
- [ ] Category (from defined list)
- [ ] Priority (1-10 with rationale)
- [ ] Source URL (accessible)
- [ ] Source name and date
- [ ] At least one company entity
- [ ] Region classification
- [ ] Confidence score

### 9.2 Data Quality Rules

| Rule | Implementation |
|------|----------------|
| **No duplicates** | SHA256 hash of URL for deduplication |
| **Fresh data** | News < 7 days for daily briefing |
| **Source verification** | URL must return HTTP 200 |
| **Complete entities** | Extract all entities mentioned |
| **Currency standardization** | USD for all values |
| **Missing data handling** | Use "Not disclosed" or null, NEVER estimate |

### 9.3 Confidence Scoring

| Confidence | Score | When to Apply |
|------------|-------|---------------|
| HIGH | 0.9+ | All facts explicitly stated, Tier 1-2 source |
| MEDIUM | 0.7-0.9 | Most facts stated, some inference needed |
| LOW | 0.5-0.7 | Key facts missing, Tier 3-4 source |
| UNVERIFIED | < 0.5 | Cannot verify, flag for human review |

---

## 10. What AI Agents Must NEVER Do

1. **NEVER invent company names, vessel names, or contract values**
2. **NEVER estimate or guess missing information**
3. **NEVER use sources without verifiable URLs**
4. **NEVER ignore source date/freshness**
5. **NEVER assign priority boosters without verification**
6. **NEVER generate "example" outputs using fictional data**
7. **NEVER assume engine specifications not stated in source**
8. **NEVER create actions without supporting evidence**
9. **NEVER omit source attribution**
10. **NEVER report rumors as facts**

---

## 11. Integration with Knowledge Base

### 11.1 KB Enrichment (Optional)

When KB is available, enrich with:
- Manufacturer matching (verify against KB)
- Engine series identification (if mentioned)
- Application classification
- Competitor mapping

### 11.2 KB Enrichment Rules

- Only apply KB enrichment if entity match confidence > 0.8
- If fuzzy match, flag for verification
- Never assume engine models not mentioned in source

---

## 12. API Data Sources

### 12.1 NewsAPI Integration

**Purpose:** Collect recent news articles (last 30 days) for marine industry intelligence.

| Parameter | Value |
|-----------|-------|
| **API Endpoint** | `https://newsapi.org/v2/everything` |
| **Environment Variable** | `NEWSAPI_API_KEY` |
| **Coverage** | Last 30 days (free plan limit) |
| **Rate Limit** | 100 requests/day (free plan) |
| **Request Delay** | 0.5 seconds between queries |

**Marine Industry Queries:**
```yaml
shipbuilding_queries:
  - "shipyard contract awarded vessel"
  - "newbuild ship ferry Singapore"
  - "newbuild OSV offshore vessel Asia"
  - "vessel order shipbuilding contract"
  - "marine ferry newbuild Southeast Asia"

engine_queries:
  - "marine engine order contract"
  - "ship propulsion system award"
  - "dual fuel engine vessel LNG"
  - "marine diesel engine megawatt"
  - "vessel repower engine retrofit"

offshore_queries:
  - "offshore vessel FPSO contract"
  - "FID final investment decision oil gas"
  - "offshore support vessel OSV charter"
  - "subsea vessel contract award"

regulation_queries:
  - "IMO emissions maritime regulation"
  - "ship decarbonization fuel transition"
  - "maritime green shipping methanol ammonia"
```

**Response Processing:**
- Deduplicate by URL hash (SHA256)
- Categorize source (trade_media, business_news, general_news)
- Extract: title, content, description, published date, author, image URL
- Store metadata as JSON for downstream processing

### 12.2 Perplexity API Integration

**Purpose:** AI-powered web research for real-time intelligence with structured analysis.

| Parameter | Value |
|-----------|-------|
| **API Endpoint** | `https://api.perplexity.ai/chat/completions` |
| **Environment Variable** | `PERPLEXITY_API_KEY` |
| **Model** | `sonar` (default) or `sonar-pro` |
| **Timeout** | 90 seconds |
| **Temperature** | 0.2 (for factual responses) |

**System Prompt Focus Areas:**
1. New vessel construction (newbuilds) requiring propulsion systems
2. Engine repowering and retrofit projects
3. Offshore oil & gas projects requiring vessel support
4. Fuel transition projects (LNG, methanol, ammonia, dual-fuel)
5. Fleet expansion by ferry operators, port authorities, offshore companies
6. Engine reliability issues creating replacement opportunities

**Priority Regions:**
- Singapore, Indonesia, Malaysia, Thailand, Vietnam
- Philippines, Australia, China, Korea, Japan, India

**Key Sources Prioritized:**
- MPA Singapore, Singapore Maritime Foundation, SSA, ASMI
- Maritime Executive, Seatrade Maritime, Splash247, TradeWinds, Lloyd's List
- Offshore Engineer, Asian Oil & Gas, Upstream Online
- SGX company announcements, shipyard press releases

**Features:**
- Returns citations with source URLs
- Circuit breaker protection (opens after 5 failures, recovers after 60s)
- Automatic retry with exponential backoff (max 3 retries)
- Rate limiting (configurable delay between queries)

**Response Structure:**
```json
{
  "content": "Research response text with analysis",
  "sources": ["https://source1.com", "https://source2.com"],
  "error": null
}
```

### 12.3 API Configuration

**Required Environment Variables:**
```bash
# NewsAPI - for historical news collection
NEWSAPI_API_KEY=your_newsapi_key

# Perplexity - for AI-powered research
PERPLEXITY_API_KEY=your_perplexity_key
```

**Usage in Code:**
```python
from lead_to_cash.services.news_collector import NewsCollector

# Collect marine industry news
collector = NewsCollector()
results = await collector.collect_from_newsapi(
    queries=NewsCollector.MARINE_QUERIES,
    days_back=30,
)

# Or use MarineIntelAgent for Perplexity-powered research
from lead_to_cash.agents import MarineIntelAgent, MarineIntelConfig

config = MarineIntelConfig()
agent = MarineIntelAgent(config)
result = await agent.run_daily_research()
```

---

## 13. Key Industry Events Calendar

### 13.1 Major Maritime Trade Shows & Conferences

**Track and report on upcoming events relevant to RRPS sales:**

| Event | Location | Typical Timing | Relevance | Priority |
|-------|----------|----------------|-----------|----------|
| **Singapore Maritime Week (SMW)** | Singapore | April | APAC hub, regulatory updates, customer meetings | HIGH |
| **Sea Asia** | Singapore | April (biennial) | Regional trade show, product showcase | HIGH |
| **Nor-Shipping** | Oslo, Norway | June (biennial) | Global maritime, Nordic customers | MEDIUM |
| **SMM Hamburg** | Hamburg, Germany | September (biennial) | World's largest maritime trade show | HIGH |
| **Posidonia** | Athens, Greece | June (biennial) | Greek shipping, tanker/bulk markets | MEDIUM |
| **Offshore Technology Conference (OTC)** | Houston, USA | May | Offshore oil & gas | MEDIUM |
| **OTC Asia** | Kuala Lumpur | March (biennial) | APAC offshore | HIGH |
| **Marintec China** | Shanghai | December (biennial) | Chinese shipbuilding | MEDIUM |
| **Indonesia Maritime Expo** | Jakarta | October | Indonesia ferry/offshore market | HIGH |
| **INMEX Vietnam** | Ho Chi Minh | October | Vietnam emerging market | MEDIUM |

### 13.2 Industry Webinars & Seminars

**Classification societies and industry bodies regularly host:**

| Organization | Event Types | Topics | How to Track |
|--------------|-------------|--------|--------------|
| **DNV** | Webinars, seminars | Decarbonization, regulations, class rules | dnv.com/events |
| **Lloyd's Register** | Technical seminars | Machinery, safety, fuel transition | lr.org/events |
| **Bureau Veritas** | Webinars | Classification, digital | marine-offshore.bureauveritas.com |
| **ABS** | Technical sessions | Offshore, LNG, safety | ww2.eagle.org |
| **Singapore Maritime Foundation** | SMW events | Industry networking | smf.com.sg |
| **MPA Singapore** | Regulatory briefings | Singapore regulations | mpa.gov.sg |

### 13.3 Event Intelligence Output Format

```json
{
  "category": "INDUSTRY_EVENT",
  "event_name": "Sea Asia 2026",
  "event_type": "trade_show|conference|webinar|seminar",
  "location": "Singapore",
  "dates": {
    "start": "2026-04-15",
    "end": "2026-04-17"
  },
  "relevance": {
    "rrps_participation": true|false,
    "competitor_presence": ["CAT", "Cummins"],
    "key_customers_attending": ["Penguin Ferries", "PSA Marine"],
    "business_opportunity": "Customer meetings, product showcase"
  },
  "action_items": [
    {"action": "Schedule customer meetings", "deadline": "2026-03-15"},
    {"action": "Prepare product materials", "deadline": "2026-04-01"}
  ],
  "source": {
    "url": "https://sea-asia.com/",
    "accessed_date": "2026-01-21"
  }
}
```

---

## 14. Market Reports & Outlooks

### 14.1 Key Industry Reports to Track

| Report | Publisher | Frequency | Content | RRPS Relevance |
|--------|-----------|-----------|---------|----------------|
| **Maritime Forecast to 2050** | DNV | Annual | Decarbonization pathways, fuel scenarios | Fuel transition strategy |
| **Shipping Market Review** | BIMCO | Quarterly | Freight rates, fleet growth | Market demand indicators |
| **World Fleet Monitor** | Clarksons | Monthly | Orderbook, deliveries, scrapping | Newbuild pipeline |
| **Offshore Market Report** | Westwood | Quarterly | OSV/rig utilization, dayrates | Offshore segment health |
| **LNG Shipping Report** | Poten & Partners | Monthly | LNG carrier orders, rates | LNG fuel adoption |
| **Ferry Shipping Report** | Shippax | Annual | Global ferry market | Ferry segment analysis |
| **Marine Engine Market** | Various analysts | Ad-hoc | Engine market share, trends | Competitive positioning |

### 14.2 Regulatory Updates to Monitor

| Body | Update Type | Impact | How to Track |
|------|-------------|--------|--------------|
| **IMO (MEPC)** | Emissions regulations | Tier III, CII, EEXI | imo.org/en/MediaCentre |
| **MPA Singapore** | Port regulations | Singapore operations | mpa.gov.sg/media-centre |
| **EU** | FuelEU Maritime, ETS | European trading routes | ec.europa.eu/transport |
| **US EPA** | Tier 4 standards | US market requirements | epa.gov/regulations-emissions-vehicles |
| **China MSA** | Domestic ECA | China coastal operations | msa.gov.cn |

### 14.3 Market Report Intelligence Format

```json
{
  "category": "MARKET_REPORT",
  "report_name": "DNV Maritime Forecast 2026",
  "publisher": "DNV",
  "published_date": "2026-01-15",
  "key_findings": [
    "Methanol uptake accelerating in container segment",
    "Dual-fuel orders reached 40% of newbuilds in 2025",
    "APAC ferry electrification lagging Europe"
  ],
  "rrps_implications": {
    "opportunity": "Dual-fuel engine demand increasing",
    "threat": "Battery-electric competition in short-sea ferry",
    "action": "Accelerate MTU dual-fuel marketing in APAC"
  },
  "affected_segments": ["ferry", "container", "tanker"],
  "source": {
    "url": "https://dnv.com/maritime-forecast",
    "access_type": "public|subscription"
  }
}
```

---

## 15. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.8 | 2026-01-22 | Engineering Team | Expanded Section 5.2 to comprehensive 54-source registry with 8 categories, added programmatic access via source_registry.py |
| 2.5 | 2026-01-21 | AI Intelligence Team | Added new categories (INDUSTRY_EVENT, MARKET_REPORT, PARTNERSHIP, LEADERSHIP_CHANGE, M_AND_A, TECHNOLOGY), Section 13 (Events Calendar), Section 14 (Market Reports) |
| 2.4 | 2026-01-20 | AI Intelligence Team | Added Actionable Intelligence Requirements (Section 8) - BU-level analysis, pipeline tracking, market trend implications |
| 2.3 | 2026-01-20 | AI Intelligence Team | Added mandatory agent guide reference and evidence-based terminology |
| 2.2 | 2026-01-20 | AI Intelligence Team | Added API Data Sources section (NewsAPI, Perplexity) |
| 2.1 | 2026-01-20 | AI Intelligence Team | Audit fixes: signal names, vessel types, industry associations |
| 2.0 | 2026-01-20 | AI Intelligence Team | Added anti-hallucination rules, source verification |
| 1.0 | 2026-01-20 | AI Intelligence Team | Initial release |

---

## 16. Related Documents

- `sales_intelligence_agent_guide.md` - Unified agent guide (primary reference)
- `competitor_insights_guide.md` - Competitive intelligence standards
- `KYP_guide.md` - Knowledge base and product guide
- `source_list.yaml` - Comprehensive source configuration
