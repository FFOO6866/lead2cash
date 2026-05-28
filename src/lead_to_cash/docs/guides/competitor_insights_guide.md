# Competitor Insights Intelligence Guide

> ⚠️ **SUPERSEDED** - For CompetitorIntelAgent, see `competitor_intel_guide.md`
> This guide contains additional detail for reference.
> **Date:** 2026-01-21

---

> **Version:** 2.5
> **Last Updated:** 2026-01-21
> **Purpose:** Detailed reference for competitor analysis (supplementary to competitor_intel_guide.md)
> **Primary Guide:** `competitor_intel_guide.md`

---

## CRITICAL: Data Integrity Rules

### MANDATORY: Agent Guide Reference

**⚠️ All agents performing competitor analysis MUST load and follow this guide.**

```python
# Agent MUST load guide at initialization
GUIDE_PATH = "src/lead_to_cash/docs/guides/competitor_insights_guide.md"

class CompetitorIntelAgent:
    def __init__(self):
        self.guide = self._load_guide(GUIDE_PATH)
        # Guide rules are MANDATORY for all competitor analysis
```

### MANDATORY: Anti-Hallucination Policy

**AI agents MUST follow these rules without exception:**

1. **ONLY report facts explicitly stated in source documents**
   - NEVER infer, assume, or generate information not in the source
   - If a contract value is not disclosed, report as "Not disclosed" - NEVER estimate
   - If an engine model is not specified, report as "Not specified" - NEVER guess

2. **ALWAYS include source attribution**
   - Every fact MUST have a verifiable source URL
   - Every date MUST come from the source, not be assumed
   - If source is unavailable, mark data as "UNVERIFIED"

3. **NEVER generate fictional competitive intelligence**
   - All competitor names must be from the approved list (Section 1.1)
   - All contract wins must come from actual press releases
   - All financial data must be from verified SEC/regulatory filings

4. **When uncertain, flag for human review**
   - Confidence < 0.7 = requires human verification
   - Conflicting sources = flag both, do not resolve
   - Missing critical data = mark as "INCOMPLETE"

### MANDATORY: Reference Link Requirement

**⚠️ CRITICAL: Every competitive insight MUST include a verifiable source URL.**

```json
{
  "headline": "Competitor news headline",
  "competitor": "Caterpillar|Cummins|MAN Energy",
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
2. **SEC/EODHD data requires filing reference** - Include 10-K, 10-Q identifiers
3. **If no URL available** - Mark as `"requires_verification": true`
4. **Multiple sources = higher confidence** - 2+ sources boost score
5. **Primary sources preferred** - SEC filings, press releases > news coverage

### MANDATORY: Evidence-Based Terminology

**⚠️ CRITICAL: Use factual language. Never assert competitive advantages without evidence.**

| ❌ INCORRECT | ✅ CORRECT |
|-------------|-----------|
| "Market leader" | "Reported [X]% market share per [source]" |
| "Superior technology" | "[Specific feature] announced per [source]" |
| "Outperforming RRPS" | "[X] contracts won in [segment] per [source]" |
| "Aggressive pricing" | "Price point of $[X] reported in [source]" |
| "Strong quarter" | "Revenue of $[X] reported in [10-K/10-Q filing]" |

**Status Terminology:**
- `CONFIRMED` - Verified in SEC filing or official press release
- `REPORTED` - Covered by trade media with URL
- `ESTIMATED` - Analyst estimate (cite source)
- `UNVERIFIED` - Single source or no URL available

### Source Verification Checklist

Before including ANY competitor intel, verify:
- [ ] Source URL is accessible and loads correctly
- [ ] Publication date is within acceptable range
- [ ] Company names match official registered names
- [ ] Financial figures match SEC/regulatory filings
- [ ] No competitor capabilities invented or assumed
- [ ] **Reference URL is included and verifiable**
- [ ] **Evidence-based terminology used (no unverified assertions)**

---

## 1. Overview

This guide defines how AI agents should collect, analyze, and present competitive intelligence for Rolls-Royce Power Systems (RRPS) sales operations.

### 1.1 Target Competitors (MANDATORY)

AI agents MUST only track the following approved competitors:

| Tier | Competitor | Legal Name | Ticker | Marine Focus |
|------|------------|------------|--------|--------------|
| **Primary** | Caterpillar | Caterpillar Inc. | CAT.US | MaK marine engines |
| **Primary** | Cummins | Cummins Inc. | CMI.US | Marine propulsion |
| **Primary** | MAN Energy | MAN Energy Solutions SE | Part of VW Group | Large-bore marine engines |

### 1.2 Competitor Scope Definition

| Competitor | Key Brands | Power Range | Marine Products |
|------------|------------|-------------|-----------------|
| **Caterpillar** | CAT, MaK | 500 kW - 18,000 kW | M32C, M43C, M46DF, M34DF marine engines |
| **Cummins** | Cummins Marine | 100 kW - 4,500 kW | QSK series, K19/38/50/60 marine |
| **MAN Energy** | MAN, Pielstick | 1,500 kW - 80,000 kW | 32/44CR, 48/60CR, 51/60 |

**DO NOT track competitors outside this approved list without explicit approval.**

---

## 2. Signal Types Classification

### 2.1 Signal Type Definitions

AI agents MUST classify each competitive signal into one of these categories:

| Signal Type | Code | Description | Score Boost |
|-------------|------|-------------|-------------|
| **Contract Win** | `CONTRACT_WIN` | Competitor wins vessel/project order | +30 if engines specified |
| **Customer Announcement** | `CUSTOMER_ANNOUNCEMENT` | New customer relationship or vessel delivery | +15 |
| **Product Launch** | `PRODUCT_LAUNCH` | New engine platform or fuel capability | +20 for new platform/fuel |
| **Technology POV** | `TECHNOLOGY_POV` | Fuel transition content, tech roadmap | +15 for fuel transition |
| **Thought Leadership** | `THOUGHT_LEADERSHIP` | Strategy, vision, market positioning | +10 |
| **Event Marketing** | `EVENT_MARKETING` | Trade shows, exhibitions, conferences | +10 if APAC/Singapore |
| **Partnership** | `PARTNERSHIP` | Strategic alliances, JVs, collaborations | +20 for technology partnerships |
| **Regulatory Positioning** | `REGULATORY_POSITIONING` | IMO compliance, emissions leadership | +10 |

### 2.2 Signal Detection Keywords

```yaml
contract_win:
  - "contract awarded"
  - "engine order"
  - "propulsion contract"
  - "selected to supply"
  - "wins order"
  - "supply agreement"

customer_announcement:
  - "delivery to"
  - "enters service"
  - "customer announcement"
  - "sea trials"
  - "commissioning"

product_launch:
  - "introduces"
  - "launches"
  - "announces new"
  - "next generation"
  - "upgraded"

technology_pov:
  - "fuel strategy"
  - "decarbonization"
  - "net zero"
  - "carbon neutral"
  - "alternative fuel"

partnership:
  - "partnership"
  - "collaboration"
  - "joint venture"
  - "strategic alliance"
  - "MoU signed"

regulatory_positioning:
  - "IMO Tier"
  - "emission reduction"
  - "EPA certified"
  - "compliance"
  - "ECA compliant"
```

---

## 3. Source Channels

### 3.1 Approved Source Channels

| Channel Code | Description | Refresh Frequency | Priority |
|--------------|-------------|-------------------|----------|
| `WEBSITE_NEWSROOM` | Official company news/press releases | Daily | Tier 1 |
| `WEBSITE_PRODUCT` | Product pages, specifications | Weekly | Tier 2 |
| `WEBSITE_INSIGHTS` | White papers, case studies, blogs | Weekly | Tier 2 |
| `LINKEDIN` | Official company LinkedIn page | Daily | Tier 3 |
| `TWITTER_X` | Official company X/Twitter | Daily | Tier 3 |
| `YOUTUBE` | Official company videos | Weekly | Tier 3 |
| `EODHD_FINANCIALS` | SEC filings, financial data | Quarterly | Tier 1 |
| `RSS_FEED` | Automated news feeds | Continuous | Varies |
| `PERPLEXITY` | AI-assisted research | On-demand | Tier 3 |

### 3.2 Official Competitor URLs (MANDATORY)

**Caterpillar:**
- Newsroom: https://www.caterpillar.com/en/news.html
- Marine: https://www.cat.com/marine
- MaK: https://www.mak-global.com
- Investor Relations: https://www.caterpillar.com/en/investors.html

**Cummins:**
- Newsroom: https://www.cummins.com/news
- Marine: https://marine.cummins.com
- Investor Relations: https://investor.cummins.com

**MAN Energy Solutions:**
- Newsroom: https://www.man-es.com/news
- Marine: https://www.man-es.com/marine
- Products: https://www.man-es.com/marine/products

### 3.3 Source Rejection Criteria

**DO NOT use sources that:**
- Are unofficial/fan pages or third-party aggregators
- Have no publication date
- Are older than 90 days (for news), 1 year (for product specs)
- Cannot be verified against official sources
- Are competitor marketing claims without substantiation

---

## 4. Output Format Specification

### 4.1 Competitor Signal Structure

```json
{
  "id": "SIG-{competitor}-YYYY-MM-DD-NNN",
  "competitor": "caterpillar|cummins|man_energy",
  "signal_type": "SIGNAL_TYPE from Section 2.1",
  "source_channel": "CHANNEL_CODE from Section 3.1",

  "headline": "Max 120 characters - exact from source",
  "description": "Max 500 characters - factual summary",

  "score": 0-100,
  "score_breakdown": {
    "base_signal_score": 0-40,
    "regional_boost": 0-20,
    "entity_boost": 0-20,
    "timing_boost": 0-20
  },

  "entities": {
    "customer_mentioned": "Exact name from source or null",
    "project_name": "From source or null",
    "vessel_type": "From source or null",
    "engine_model": "Exact model from source or null",
    "fuel_type": "diesel|lng|dual_fuel|methanol|ammonia|hydrogen|null",
    "contract_value_usd": "Exact value or 'Not disclosed'"
  },

  "geographic": {
    "region": "From source or null",
    "country": "From source or null",
    "is_apac": true|false,
    "is_singapore": true|false
  },

  "source": {
    "url": "MUST be accessible",
    "published_date": "YYYY-MM-DD from source",
    "accessed_date": "YYYY-MM-DD",
    "channel": "Source channel code"
  },

  "data_quality": {
    "confidence_score": 0.0-1.0,
    "all_facts_sourced": true|false,
    "requires_verification": ["List fields needing review"],
    "missing_data": ["List unavailable fields"]
  },

  "competitive_impact": {
    "threat_level": "HIGH|MEDIUM|LOW",
    "rrps_response_required": true|false,
    "affected_segments": ["marine_propulsion", "offshore_genset", etc.],
    "suggested_counter_action": "Specific action if justified"
  },

  "keywords_matched": ["keyword1", "keyword2"],

  "metadata": {
    "created_at": "ISO 8601",
    "agent": "CompetitorIntelAgent",
    "agent_version": "1.0"
  }
}
```

### 4.2 Competitor Intelligence Briefing Format

```markdown
# Competitor Intelligence Briefing
**Date:** YYYY-MM-DD | **Period:** [Daily/Weekly] | **Prepared by:** CompetitorIntelAgent

---

## Data Quality Statement

- **Total signals analyzed:** [N]
- **Tier 1 sources:** [N]%
- **High-confidence signals (>0.8):** [N]%
- **Items requiring verification:** [N]

---

## Executive Summary

**Key Competitive Moves (from verified sources):**

| Competitor | Signal Type | Impact | Source |
|------------|-------------|--------|--------|
| [Name] | [Type] | HIGH/MED/LOW | [Source] |

**Immediate Threats:**
1. [Competitor] - [Activity] - Source: [URL]
2. [Competitor] - [Activity] - Source: [URL]

---

## Section 1: Caterpillar/MaK Intelligence

### 1.1 Contract Wins & Orders

| Date | Customer | Project | Engine | Value | Source |
|------|----------|---------|--------|-------|--------|
| [Date] | [Name or "Not disclosed"] | [Name] | [Model or "N/A"] | [Value or "N/A"] | [URL] |

### 1.2 Product & Technology Updates
[Only if verified from official sources]

### 1.3 Strategic Moves
[Partnerships, acquisitions, leadership changes]

---

## Section 2: Cummins Intelligence

[Same structure as Section 1]

---

## Section 3: MAN Energy Solutions Intelligence

[Same structure as Section 1]

---

## Section 4: Competitive Position Analysis

### 4.1 Win/Loss Summary (Verified Deals Only)

| Period | RRPS Wins | Competitor Wins | Unknown |
|--------|-----------|-----------------|---------|
| This Month | [N] | [N] | [N] |
| This Quarter | [N] | [N] | [N] |

### 4.2 Competitive Threats by Segment

| Segment | Primary Threat | Recent Activity | RRPS Position |
|---------|----------------|-----------------|---------------|
| Ferry/Passenger | [Competitor] | [Verified activity] | [Assessment] |
| Offshore | [Competitor] | [Verified activity] | [Assessment] |

---

## Section 5: Items Requiring Human Verification

| Signal ID | Issue | Action Required |
|-----------|-------|-----------------|
| [ID] | [Why flagged] | [What to verify] |

---

## Appendix: Source Log

| # | Source | Channel | Tier | URL | Status |
|---|--------|---------|------|-----|--------|
| 1 | [Name] | [Code] | [1-3] | [URL] | Verified/Failed |
```

---

## 5. Scoring System

### 5.1 Signal Score Calculation (0-100)

```python
# Base score by signal type
SIGNAL_BASE_SCORES = {
    "CONTRACT_WIN": 40,
    "CUSTOMER_ANNOUNCEMENT": 25,
    "PRODUCT_LAUNCH": 35,
    "TECHNOLOGY_POV": 30,
    "THOUGHT_LEADERSHIP": 15,
    "EVENT_MARKETING": 10,
    "PARTNERSHIP": 35,
    "REGULATORY_POSITIONING": 20,
}

# Calculate final score
base_score = SIGNAL_BASE_SCORES[signal_type]

# Engine involvement boost (ONLY if engine explicitly mentioned)
if engine_model_specified_in_source:
    base_score += 30

# Regional boost (ONLY if region in source)
REGION_BOOSTS = {
    "singapore": 20,
    "indonesia": 15,
    "malaysia": 15,
    "australia": 15,
    "thailand": 10,
    "vietnam": 10,
    "philippines": 10,
    "china": 10,
    "korea": 10,
    "japan": 10,
}
if region in REGION_BOOSTS:
    base_score += REGION_BOOSTS[region]

# APAC/Singapore specific boost
if is_apac:
    base_score += 10
if is_singapore:
    base_score += 5

# Fuel transition boost
FUEL_BOOSTS = {
    "methanol": 15,
    "ammonia": 15,
    "hydrogen": 15,
    "lng": 10,
    "dual_fuel": 10,
}
if fuel_type in FUEL_BOOSTS:
    base_score += FUEL_BOOSTS[fuel_type]

# Cap at 100
final_score = min(base_score, 100)
```

### 5.2 High-Impact Signal Threshold

| Score Range | Impact Level | Required Action |
|-------------|--------------|-----------------|
| 80-100 | CRITICAL | Same-day response required |
| 60-79 | HIGH | Within 48 hours |
| 40-59 | MEDIUM | Weekly review |
| 20-39 | LOW | Monthly review |
| 0-19 | MONITOR | Background tracking |

---

## 6. Financial Intelligence

### 6.1 Financial Data Sources

| Competitor | Ticker | Data Source | Available Metrics |
|------------|--------|-------------|-------------------|
| Caterpillar | CAT.US | EODHD, SEC | Full financials, segment data |
| Cummins | CMI.US | EODHD, SEC | Full financials, segment data |
| MAN Energy | Part of VW | Limited | Parent company only |

### 6.2 Financial Metrics to Track

```json
{
  "id": "FIN-{competitor}-{period}",
  "competitor": "caterpillar|cummins|man_energy",
  "ticker": "CAT.US|CMI.US|N/A",

  "period": {
    "type": "quarterly|annual",
    "fiscal_period": "Q1 2026|FY 2025",
    "report_date": "YYYY-MM-DD"
  },

  "metrics_usd": {
    "revenue": "From SEC filing or null",
    "operating_income": "From filing or null",
    "net_income": "From filing or null",
    "rd_spending": "From filing or null",
    "capex": "From filing or null",
    "order_backlog": "From filing or null"
  },

  "segment_data": {
    "marine_segment_revenue": "If disclosed or null",
    "energy_segment_revenue": "If disclosed or null",
    "power_systems_revenue": "If disclosed or null"
  },

  "ratios": {
    "gross_margin_pct": "Calculated from filing",
    "operating_margin_pct": "Calculated from filing",
    "revenue_growth_yoy_pct": "Calculated from filing",
    "revenue_growth_qoq_pct": "Calculated from filing"
  },

  "guidance_notes": "Management commentary from filing",

  "source": {
    "url": "SEC/regulatory filing URL",
    "fetched_at": "ISO 8601"
  }
}
```

### 6.3 Financial Analysis Rules

- **ONLY use verified SEC/regulatory filings**
- **NEVER extrapolate or forecast** - report historical data only
- **Flag segment data** if not explicitly disclosed (many companies don't break out marine)
- **Compare YoY and QoQ** only when both periods are available

### 6.4 MANDATORY: Financial Insights Requirements

**⚠️ CRITICAL: Raw financial data alone is NOT sufficient. Every financial report MUST include actionable business insights.**

#### What We Need vs What We DON'T Need

| ❌ RAW DATA (Insufficient) | ✅ ACTIONABLE INSIGHT (Required) |
|---------------------------|----------------------------------|
| "Revenue: $16.2B" | "Revenue declined 8% YoY from $17.6B - potential market share opportunity in marine segment" |
| "Operating margin: 12.5%" | "Operating margin compressed 200bps due to supply chain costs - may signal pricing pressure on new contracts" |
| "R&D spending: $1.2B" | "R&D spending up 15% focused on alternative fuels per 10-K - accelerating methanol/ammonia engine development" |
| "Backlog: $24B" | "Order backlog down 12% QoQ - potential capacity availability for competitive displacement" |
| "EPS: $4.25" | "EPS missed analyst estimates by 8% - management may be under pressure to win large contracts" |

#### Required Insight Categories

For each financial metric reported, provide insights in these categories:

1. **Sales Opportunity Signals**
   - Revenue/backlog declines = potential customer dissatisfaction
   - Margin pressure = may lead to pricing concessions
   - Geographic segment weakness = territory opportunity

2. **Competitive Threat Signals**
   - Strong cash position = M&A or pricing war capability
   - R&D acceleration = new product threat timeline
   - Backlog growth = strong market position

3. **BU-Specific Relevance**
   - How does this affect RRPS marine engine business?
   - Which RRPS segments are most impacted?
   - What is the recommended response?

#### Financial Insight Format

```json
{
  "metric": "revenue",
  "raw_value": "$16.2B",
  "change": "-8% YoY",
  "insight": {
    "observation": "Revenue declined from $17.6B, marine segment down 12%",
    "implication": "Competitor may be losing market share in marine propulsion",
    "opportunity": "Target their existing customers in ferry/offshore segments",
    "threat_level": "LOW",
    "recommended_action": "Sales team to identify CAT marine customers for outreach"
  },
  "source": {
    "filing": "10-K FY2025",
    "url": "https://sec.gov/..."
  }
}
```

### 6.5 BU-Relevant News Monitoring

**⚠️ CRITICAL: Track organizational changes that may affect procurement decisions and sales opportunities.**

#### News Categories to Monitor

| Category | Description | Why It Matters | Signal Type |
|----------|-------------|----------------|-------------|
| **Restructuring** | Division mergers, spin-offs, cost-cutting | Budget freezes, procurement delays, new decision-makers | HIGH |
| **Leadership Changes** | C-suite, VP, Division heads | New relationships needed, strategy shifts | HIGH |
| **Layoffs/Hiring** | Workforce changes | Financial stress or growth signals | MEDIUM |
| **Geographic Changes** | Office closures, new markets | Territory impact, customer access | MEDIUM |
| **Strategic Pivots** | New market focus, exits | Segment vulnerability or strength | HIGH |
| **M&A Activity** | Acquisitions, divestitures | Integration disruption, new competitors | HIGH |

#### BU-Relevant News Signal Structure

```json
{
  "id": "BU-NEWS-{competitor}-YYYY-MM-DD-NNN",
  "competitor": "caterpillar|cummins|man_energy",
  "news_type": "RESTRUCTURING|LEADERSHIP|LAYOFFS|GEOGRAPHIC|STRATEGIC_PIVOT|M_AND_A",

  "headline": "Exact headline from source",
  "summary": "Max 200 characters - factual summary",

  "business_impact": {
    "affected_division": "Marine|Power Systems|Energy|All",
    "procurement_impact": "FREEZE|DELAY|ACCELERATION|NEUTRAL",
    "decision_maker_change": true|false,
    "budget_impact": "INCREASE|DECREASE|NEUTRAL|UNKNOWN"
  },

  "sales_implications": {
    "opportunity_type": "DISPLACEMENT|RELATIONSHIP|TIMING|NONE",
    "affected_segments": ["ferry", "offshore", "workboat"],
    "urgency": "IMMEDIATE|NEAR_TERM|LONG_TERM",
    "recommended_action": "Specific action for sales team"
  },

  "source": {
    "url": "MUST be accessible",
    "published_date": "YYYY-MM-DD",
    "source_type": "SEC_FILING|PRESS_RELEASE|NEWS_MEDIA"
  }
}
```

#### Example BU-Relevant Insights

**Restructuring Example:**
```markdown
**NEWS:** Caterpillar announces consolidation of marine and industrial engine divisions
**Source:** CAT Press Release, 2026-01-15
**Impact:**
- New combined leadership = existing relationships may be invalidated
- 6-month integration period = potential procurement delays
- Cost synergy targets = may lead to price cuts or service reductions
**RRPS Action:** Identify CAT marine customers who may experience service disruption during transition
```

**Leadership Change Example:**
```markdown
**NEWS:** Cummins appoints new VP of Marine Business
**Source:** Cummins Press Release, 2026-01-10
**Impact:**
- New decision-maker = competitor relationship reset
- 90-day learning period = window for competitive positioning
- Previous VP relationships = may no longer be valid
**RRPS Action:** Research new VP background, identify connection opportunities
```

**Strategic Pivot Example:**
```markdown
**NEWS:** MAN Energy Solutions exits small-bore marine engine market
**Source:** Trade publication, 2026-01-08
**Impact:**
- Segment exit = immediate displacement opportunity
- Existing MAN customers need alternative = target list development
- Service gap = aftermarket opportunity
**RRPS Action:** Generate list of MAN small-bore customers, prioritize outreach
```

---

## 7. Content Type Classification

### 7.1 Content Types (for document storage)

| Content Type | Code | Description | Typical Sources |
|--------------|------|-------------|-----------------|
| News | `NEWS` | General news coverage | Trade media, Perplexity |
| Press Release | `PRESS_RELEASE` | Official announcements | Newsroom |
| Annual Report | `ANNUAL_REPORT` | Yearly financial report | Investor relations |
| Quarterly Report | `QUARTERLY_REPORT` | Quarterly financials | SEC filings |
| Product Page | `PRODUCT_PAGE` | Product specifications | Website |
| Product Launch | `PRODUCT_LAUNCH` | New product announcement | Newsroom |
| Service Offering | `SERVICE_OFFERING` | Service capabilities | Website |
| Technical Spec | `TECHNICAL_SPEC` | Engine specifications | Product pages |
| Contract Win | `CONTRACT_WIN` | Order announcement | Press release |
| Customer Success | `CUSTOMER_SUCCESS` | Case studies, testimonials | Website |
| Case Study | `CASE_STUDY` | Detailed customer implementations | Website |
| Testimonial | `TESTIMONIAL` | Customer quotes and endorsements | Website |
| Partnership | `PARTNERSHIP` | Alliance announcements | Press release |
| Executive Change | `EXECUTIVE_CHANGE` | Leadership changes | Press release |
| Market Analysis | `MARKET_ANALYSIS` | Industry reports | Research |
| Event | `EVENT` | Trade show, exhibition | Events page |

---

## 8. Competitive Response Framework

### 8.1 Threat Assessment Matrix

| Signal Type | RRPS Market Share Impact | Response Urgency |
|-------------|-------------------------|------------------|
| CONTRACT_WIN in APAC | Direct - lost opportunity | IMMEDIATE |
| PRODUCT_LAUNCH (new fuel) | Capability gap risk | HIGH |
| PARTNERSHIP (tech) | Innovation threat | MEDIUM |
| PRICING change | Margin pressure | HIGH |
| EVENT_MARKETING (APAC) | Visibility competition | LOW |

### 8.2 Suggested Actions (Template)

**ONLY suggest actions that are:**
- Justified by verified intelligence
- Within RRPS sales team capability
- Specific and actionable

```markdown
**Suggested Action:**
- **Type:** Customer Contact | Proposal | Counter-Marketing
- **Trigger:** [Specific signal that triggered this]
- **Action:** [Specific step to take]
- **Owner:** [Sales/Marketing/Product]
- **Urgency:** HIGH/MEDIUM/LOW
- **Evidence:** [Source URL supporting the action]
```

---

## 9. What AI Agents Must NEVER Do

1. **NEVER invent competitor contract wins or customer names**
2. **NEVER estimate financial data not in SEC filings**
3. **NEVER track competitors outside the approved list**
4. **NEVER assume engine specifications not in source**
5. **NEVER generate "example" outputs with fictional data**
6. **NEVER report rumors or unverified social media as facts**
7. **NEVER assign threat levels without supporting evidence**
8. **NEVER omit source attribution**
9. **NEVER extrapolate market share or forecast future performance**
10. **NEVER create competitive responses without verified triggers**

---

## 10. Integration Points

### 10.1 System Dependencies

| System | Integration | Purpose |
|--------|-------------|---------|
| CompetitorIntelAgent | Primary agent | Signal extraction and scoring |
| CompetitorEmbeddingService | Vector storage | Semantic search of intel |
| Knowledge Base | KB enrichment | Entity resolution |
| Scheduler | 2 AM SGT daily | Automated refresh |
| PostgreSQL + pgvector | Storage | Document and embedding storage |

### 10.2 Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `competitor_documents` | Full content storage | id, competitor, content_type, content |
| `document_chunks` | RAG retrieval | id, document_id, embedding |
| `competitor_signals` | Extracted signals | id, signal_type, score |
| `competitor_financials` | Financial tracking | id, ticker, period, metrics |

---

## 11. API Data Sources

### 11.1 EODHD API Integration (Financial Data)

**Purpose:** Fetch verified financial data from SEC filings for competitor tracking.

| Parameter | Value |
|-----------|-------|
| **API Endpoint** | `https://eodhd.com/api/fundamentals/{TICKER}` |
| **Environment Variable** | `EODHD_API_KEY` |
| **Rate Limit** | 100 requests/minute (depends on plan) |
| **Data Freshness** | Quarterly/Annual reports |

**Competitor Ticker Mapping:**

| Competitor | Ticker | Data Availability |
|------------|--------|-------------------|
| Caterpillar | `CAT.US` | Full financials, segment data |
| Cummins | `CMI.US` | Full financials, segment data |
| MAN Energy Solutions | N/A (part of VW Group) | Limited - parent company only |

**Metrics Retrieved:**

```json
{
  "quarterly_financials": {
    "revenue_usd": "From SEC filing",
    "operating_income_usd": "From SEC filing",
    "net_income_usd": "From SEC filing",
    "rd_spending_usd": "From SEC filing",
    "gross_margin_pct": "Calculated from filing",
    "operating_margin_pct": "Calculated from filing",
    "revenue_growth_yoy_pct": "Calculated (needs 4 quarters history)",
    "revenue_growth_qoq_pct": "Calculated (needs 2 quarters history)"
  },
  "segment_data": {
    "market_cap": "From highlights",
    "pe_ratio": "From highlights",
    "52_week_high": "From highlights",
    "52_week_low": "From highlights"
  }
}
```

**Usage:**
```python
from lead_to_cash.services.competitor_intel.eodhd_service import get_eodhd_service

service = get_eodhd_service()

# Fetch quarterly financials for Caterpillar
quarterly = await service.fetch_quarterly_financials("caterpillar")
print(f"CAT Revenue: ${quarterly.revenue_usd:,.0f}")

# Fetch annual financials for Cummins
annual = await service.fetch_annual_financials("cummins")
print(f"CMI FY Revenue: ${annual.revenue_usd:,.0f}")

# Refresh all competitors
all_financials = await service.refresh_all_financials()
```

**CRITICAL: Financial Data Rules**
- ONLY use verified SEC/regulatory filings
- NEVER extrapolate or forecast future performance
- Flag segment data if not explicitly disclosed
- Report MAN Energy as "N/A - Part of VW Group"

### 11.2 NewsAPI Integration (Competitor News)

**Purpose:** Collect competitor-specific news articles for signal extraction.

| Parameter | Value |
|-----------|-------|
| **API Endpoint** | `https://newsapi.org/v2/everything` |
| **Environment Variable** | `NEWSAPI_API_KEY` |
| **Coverage** | Last 30 days (free plan limit) |
| **Rate Limit** | 100 requests/day (free plan) |

**Competitor Search Queries:**

```yaml
caterpillar:
  - "Caterpillar Marine engine"
  - "Caterpillar MaK marine"
  - "Cat marine power systems"
  - "Caterpillar vessel propulsion"

cummins:
  - "Cummins marine engine"
  - "Cummins vessel power"
  - "Cummins ship propulsion"
  - "Cummins QSK marine"

man_energy:
  - "MAN Energy Solutions marine"
  - "MAN engine ship"
  - "MAN dual fuel marine"
  - "MAN B&W marine engine"
```

**Usage:**
```python
from lead_to_cash.services.news_collector import NewsCollector

collector = NewsCollector()

# Collect for all competitors
results = await collector.collect_competitor_news(days_back=30)

# Collect for specific competitor
cat_news = await collector.collect_competitor_news(
    competitor="caterpillar",
    days_back=30,
)
```

### 11.3 Perplexity API Integration (AI Research)

**Purpose:** AI-powered competitor research with real-time web search and analysis.

| Parameter | Value |
|-----------|-------|
| **API Endpoint** | `https://api.perplexity.ai/chat/completions` |
| **Environment Variable** | `PERPLEXITY_API_KEY` |
| **Model** | `sonar` (default) or `sonar-pro` |
| **Timeout** | 90 seconds |

**Features:**
- Returns citations with source URLs
- Structured analysis of competitor activities
- Real-time web research capabilities
- Circuit breaker protection for reliability

**Usage with CompetitorIntelAgent:**
```python
from lead_to_cash.agents import CompetitorIntelAgent, CompetitorIntelConfig

config = CompetitorIntelConfig()
agent = CompetitorIntelAgent(config)

# Query competitor intelligence
result = await agent.query("What are Caterpillar's recent marine engine wins?")
print(result["answer"])
print(f"Sources: {result['sources']}")
print(f"Confidence: {result['confidence']}")
```

### 11.4 API Configuration

**Required Environment Variables:**
```bash
# EODHD - for financial data (Caterpillar, Cummins)
EODHD_API_KEY=your_eodhd_key

# NewsAPI - for competitor news collection
NEWSAPI_API_KEY=your_newsapi_key

# Perplexity - for AI-powered competitor research
PERPLEXITY_API_KEY=your_perplexity_key
```

**Service Initialization:**
```python
# All services auto-initialize from environment variables
from lead_to_cash.services.competitor_intel.eodhd_service import get_eodhd_service
from lead_to_cash.services.news_collector import NewsCollector
from lead_to_cash.agents import CompetitorIntelAgent

# Check if configured
eodhd = get_eodhd_service()
if eodhd.is_configured():
    financials = await eodhd.refresh_all_financials()
```

---

## 12. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.4 | 2026-01-20 | AI Intelligence Team | Added Financial Insights Requirements (6.4) and BU-Relevant News Monitoring (6.5) |
| 2.3 | 2026-01-20 | AI Intelligence Team | Added mandatory agent guide reference and evidence-based terminology |
| 2.2 | 2026-01-20 | AI Intelligence Team | Added API Data Sources section (EODHD, NewsAPI, Perplexity) |
| 2.1 | 2026-01-20 | AI Intelligence Team | Audit fixes: added CASE_STUDY, TESTIMONIAL content types |
| 2.0 | 2026-01-20 | AI Intelligence Team | Full guide with anti-hallucination rules |
| 0.1 | 2026-01-20 | AI Intelligence Team | Initial placeholder |

---

## 13. Related Documents

- `industry_news_guide.md` - Industry news standards
- `KYP_guide.md` - Knowledge base and product guide
- `source_list.yaml` - Comprehensive source configuration
