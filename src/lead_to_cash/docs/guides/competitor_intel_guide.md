# Competitor Intelligence Agent Guide

> **Version:** 1.2
> **Last Updated:** 2026-01-21
> **Agent:** CompetitorIntelAgent
> **File:** `agents/competitor_intel_agent.py`
> **Purpose:** Track CAT, Cummins, MAN - their wins, products, and threats
> **Content Source:** Unified Content Pipeline ([ADR-005](../../adr/005-unified-content-architecture.md))

---

## IMPORTANT: Unified Content Architecture

As of ADR-005, CompetitorIntelAgent should consume content from the **Unified Content Store** rather than maintaining separate data pipelines.

### Migration Path

**OLD (Deprecated):**
```python
# Separate embedding and scraping
from lead_to_cash.services.competitor_intel import ScraperService, EmbeddingService
```

**NEW (Recommended):**
```python
from lead_to_cash.services.unified_content import (
    get_unified_content_db,
    ContentPurpose,
)

# Query pre-processed competitor content
db = get_unified_content_db()
competitor_content = await db.list_content(
    purposes=[ContentPurpose.COMPETITOR_INTEL.value],
    kb_linked=True,  # Mandatory KB linking
)
```

See [Unified Content Guide](unified_content_guide.md) for full details.

---

## 1. Domain Boundaries

**This agent OWNS (exclusively):**
- Competitor wins (contract wins by CAT/Cummins/MAN)
- Competitor products (launches, specifications)
- Competitor partnerships (alliances, distributor deals)
- Competitor financials (SEC filings, quarterly results)
- Threat assessment (HIGH/MEDIUM/LOW)
- Competitor at customer (activity at our accounts)
- Market share analysis
- Competitor pricing (when available)

**This agent does NOT own:**
- General industry news -> MarketIntelAgent
- Customer relationship data -> CustomerIntelAgent
- Competitor company risk/due diligence -> KYPAgent
- Our product positioning -> ProductFitAgent

---

## 2. Tracked Competitors

### 2.1 Caterpillar (CAT/MaK)

| Brand | Products | Segments |
|-------|----------|----------|
| Caterpillar Marine | C32, C175, 3500 series | Offshore, workboat |
| MaK | M32C, M43C, M46DF | Ferry, offshore, cruise |

**Key Markets:** Global, strong in Americas and Europe
**Threat Level:** HIGH - major competitor in offshore and ferry

### 2.2 Cummins

| Products | Power Range | Segments |
|----------|-------------|----------|
| QSK38 | 746-1007 kW | Workboat, patrol |
| QSK60 | 1417-2340 kW | OSV, ferry |
| QSK78 | 2013-2760 kW | Large offshore |
| QSK95 | 2850-3132 kW | Large offshore |

**Key Markets:** Global, strong service network
**Threat Level:** HIGH - price competitive, good service

### 2.3 MAN Energy Solutions

| Products | Power Range | Segments |
|----------|-------------|----------|
| 32/44CR | 3,600-7,200 kW | Ferry, offshore |
| 48/60CR | 6,000-12,000 kW | Large vessels, FPSO |
| 51/60DF | Dual-fuel | LNG carriers |

**Key Markets:** Europe, Asia for large vessels
**Threat Level:** MEDIUM - different market segment (larger vessels)

---

## 3. Data Sources

### 3.1 Internal Database
| Database | Contents | When to Use |
|----------|----------|-------------|
| **Competitor Signals** | Wins, moves, announcements | First stop for competitor queries |
| **Vector Store** | Embedded competitor intel | Semantic search |

### 3.2 External APIs
| API | Purpose | When to Use |
|-----|---------|-------------|
| **Perplexity** | Real-time web search | Fresh competitive intel |
| **EODHD** | SEC filings, financials | Quarterly analysis |

---

## 4. Signal Types

### 4.1 WIN - Contract Award
```
Competitor won a contract. HIGH priority if at our customer.
Required: Customer, value (if known), engine type, source
```

### 4.2 LAUNCH - Product Launch
```
New product or capability announcement.
Required: Product, specs, target segment, launch date
```

### 4.3 PARTNERSHIP - Strategic Alliance
```
Distribution deal, JV, technology partnership.
Required: Partners, scope, market impact
```

### 4.4 FINANCIAL - Quarterly/Annual Results
```
Earnings, revenue, segment performance.
Required: Figures, comparison, marine segment details
```

### 4.5 LEADERSHIP - Executive Changes
```
CEO, CMO, regional leadership changes.
Required: Person, role, previous position
```

### 4.6 PRICING - Price Intelligence
```
Contract pricing, list price changes, discounting trends.
Required: Source, reliability assessment
```

---

## 5. Threat Assessment

### 5.1 Threat Levels

| Level | Definition | Indicators |
|-------|------------|------------|
| **HIGH** | Competitor winning at our customer OR in our stronghold segment | Lost deal, incumbent displacement |
| **MEDIUM** | Competitor active in our market, general competitive pressure | New market entry, aggressive pricing |
| **LOW** | Competitor activity outside our focus areas | Different segment, different region |

### 5.2 Threat Assessment Matrix

| Scenario | Threat Level | Required Action |
|----------|--------------|-----------------|
| Competitor wins at ACTIVE customer | HIGH | Immediate sales alert |
| Competitor wins at PROSPECT | HIGH | Review our proposal |
| Competitor wins at unknown company | MEDIUM | Monitor, assess opportunity |
| Competitor launches competing product | MEDIUM | Product team briefing |
| Competitor partnership in our region | MEDIUM | Assess distribution impact |
| Competitor activity in non-focus segment | LOW | Log and monitor |

---

## 6. Output Standards

### 6.1 Universal Requirements

| Field | Required | Rule |
|-------|----------|------|
| Competitor | Always | CAT, Cummins, or MAN |
| Activity Type | Always | WIN, LAUNCH, PARTNERSHIP, FINANCIAL |
| Threat Level | Always | HIGH / MEDIUM / LOW |
| Source URL | Always | Verifiable link |
| Customer Impact | If at our customer | Are they taking our share? |
| Our Response | For HIGH threats | What should we do? |

### 6.2 Anti-Hallucination Rules

- Contract value not stated -> "Not disclosed"
- Engine type not specified -> "Not specified"
- No source -> "UNVERIFIED - requires confirmation"
- Never assert "market leader" without evidence
- Financial data MUST come from SEC/official filings

---

## 7. Output Format

### 7.1 Competitor Alert Output

| Field | Required | Notes |
|-------|----------|-------|
| Competitor | Yes | CAT, Cummins, or MAN |
| Activity Type | Yes | WIN, LAUNCH, etc. |
| Threat Level | Yes | HIGH/MEDIUM/LOW |
| What Happened | Yes | Concise description |
| Customer Impact | If relevant | Are they at our customer? |
| Competitor Product | If relevant | Engine model, specs |
| Our Response | For HIGH | Recommended action |

### 7.2 Competitor Profile Output

| Field | Required | Notes |
|-------|----------|-------|
| Competitor | Yes | Full company name |
| Recent Activity | Yes | Last 90 days summary |
| Market Position | Yes | Segment strength |
| Products Competing with Us | Yes | Direct competitors to MTU |
| Known Wins in Region | If known | Recent contracts |
| Threat Assessment | Yes | Overall threat level |

---

## 8. Example Responses

### 8.1 Competitor Alert

**User:** "Cummins just won at Pacific Radiance"

```
## Competitor Alert: Cummins Win at Pacific Radiance

**Source:** [Splash247, 2026-01-18](https://splash247.com/...)
**Confidence:** HIGH (press release confirmed)

### What Happened
Cummins delivered QSK95 engines for 4 new Pacific Radiance PSVs.
Contract value: ~$8M (estimated based on typical QSK95 pricing)

### Threat Assessment

| Factor | Assessment |
|--------|------------|
| Threat Level | **HIGH** |
| Reason | Pacific Radiance is OUR CUSTOMER |
| Our Installed Base | 6 vessels with MTU 4000 |
| This is their | FIRST Cummins purchase |

### Customer Impact
- We're losing share at this account
- Cummins now has foothold for future deals
- Risk: Maintenance contracts may shift

### Competitor Product (from KB)
- Cummins QSK95: 2,850-3,132 kW, 1800 RPM
- Competes directly with our MTU 4000 series
- Price advantage: Typically 10-15% lower

### Recommended Response (HIGH threat)
1. **Immediate:** Sales to call Pacific Radiance procurement
2. **Objective:** Understand why Cummins won (price? delivery?)
3. **Protect:** Secure maintenance for our 6 vessels
4. **Position:** Get on shortlist for next order

Should I create a competitor threat record in CRM?
```

### 8.2 Competitor Tracking Query

**User:** "What's CAT doing in Singapore?"

```
## Caterpillar Activity in Singapore (Last 90 Days)

### Recent Wins

**1. Keppel Offshore - 2 AHTSs**
- **Date:** 2025-12-15
- **Source:** [TradeWinds](https://tradewindsnews.com/...)
- **Engine:** MaK M32C (4,500 kW)
- **Threat Level:** MEDIUM (not our customer)

**2. Nam Cheong - 4 PSVs**
- **Date:** 2025-11-20
- **Source:** [Offshore Energy](https://offshore-energy.biz/...)
- **Engine:** CAT 3516E
- **Threat Level:** LOW (different segment)

### Partnership Activity
- No new partnerships announced in Singapore

### Market Position
- CAT/MaK strong in offshore construction segment
- Less presence in ferry market (our stronghold)
- Pricing typically 5-10% below MTU

### Threat Summary

| Segment | CAT Activity | Our Position | Threat |
|---------|--------------|--------------|--------|
| Offshore (OSV/PSV) | Active, winning | Moderate | MEDIUM |
| Ferry | Limited | Strong | LOW |
| Workboat | Active | Competitive | MEDIUM |

### Recommended Actions
1. Monitor Keppel for future opportunities
2. Engage Nam Cheong proactively for next cycle
3. Protect ferry segment - our competitive advantage
```

---

## 9. Integration Points

**Coordinate with other agents:**
- MarketIntelAgent identifies news -> CompetitorIntelAgent assesses if competitor involved
- CustomerIntelAgent provides customer relationship -> helps assess threat level
- ProductFitAgent provides competitive product specs for comparison

---

## 10. What We Never Do

1. **Never fabricate competitor data** - Only verified sources
2. **Never estimate contract values** - Say "Not disclosed"
3. **Never understate threats** - If at our customer, it's HIGH
4. **Never ignore competitor wins** - Always log and assess
5. **Never share competitive pricing externally** - Internal use only
6. **Never assert competitive claims without evidence** - Verify first
