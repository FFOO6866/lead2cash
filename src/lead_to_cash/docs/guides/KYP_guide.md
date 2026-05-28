# KYP (Know Your Partner) Agent Guide

> **Version:** 3.4
> **Last Updated:** 2026-01-26
> **Agent:** DueDiligenceAgent (alias: KYPAgent)
> **File:** `agents/due_diligence_agent.py`
> **Purpose:** Due diligence, risk assessment, sanctions screening, compliance

---

## Domain Boundaries

**This agent OWNS (exclusively):**
- Sanctions screening (OFAC, EU, UN, MAS)
- Litigation and legal history
- Financial health assessment
- Safety record evaluation
- Reputation analysis
- Risk categorization
- Compliance recommendations
- Customer validation (SAP MS5)
- Third-Party Risk Management (Aravo TPRM)

**This agent does NOT own:**
- Industry news/opportunities -> MarketIntelAgent
- Customer relationship data -> CustomerIntelAgent
- Competitor tracking -> CompetitorIntelAgent
- Product specifications -> ProductFitAgent

---

## CRITICAL: Data Integrity Rules

### MANDATORY: Anti-Hallucination Policy

**AI agents MUST follow these rules without exception:**

1. **ONLY reference products that exist in the Knowledge Base**
   - NEVER invent engine models, specifications, or manufacturers
   - If an engine model is not in KB, mark as "NOT IN KB - VERIFY MANUALLY"
   - NEVER guess at power ratings, RPM ranges, or fuel capabilities

2. **ALWAYS use KB for entity resolution**
   - Match entities against KB before using in reports
   - Use entity_aliases table for fuzzy matching
   - Confidence threshold: 0.8 minimum for automatic matching

3. **NEVER fabricate product specifications**
   - All specs MUST come from KB or official manufacturer sources
   - If spec is missing from KB, mark as "NOT AVAILABLE"
   - NEVER extrapolate specs from similar models

4. **When uncertain, flag for human review**
   - Entity match confidence < 0.8 = requires verification
   - Unknown manufacturer = flag for KB team
   - Conflicting specs = flag both sources

### MANDATORY: Reference Link Requirement

**⚠️ CRITICAL: Every finding MUST include a verifiable source URL.**

```json
{
  "finding": "Description of the finding",
  "source": {
    "url": "https://example.com/article",  // REQUIRED - Must be a real, accessible URL
    "name": "Publication Name",
    "date": "YYYY-MM-DD",
    "accessed_date": "YYYY-MM-DD"
  },
  "confidence": 0.0-1.0
}
```

**Rules for Source URLs:**
1. **MUST be real, verifiable URLs** - No fabricated or placeholder links
2. **MUST be accessible** - Links should be publicly accessible or from known databases
3. **If no source URL available** - Mark as `"source": "MANUAL_VERIFICATION_REQUIRED"`
4. **Multiple sources increase confidence** - 2+ sources = higher confidence score
5. **Primary sources preferred** - Official websites, regulatory filings, court records
6. **News archives acceptable** - Reuters, Bloomberg, Straits Times, industry publications

**Example - Correct:**
```json
{
  "finding": "CCS fined entity S$172,906 for anti-competitive conduct",
  "source": {
    "url": "https://www.ccs.gov.sg/media-and-events/newsroom/...",
    "name": "Competition Commission of Singapore",
    "date": "2012-07-18"
  },
  "confidence": 1.0
}
```

**Example - Incorrect (will be rejected):**
```json
{
  "finding": "Company has good reputation",
  "source": null,  // ❌ NO SOURCE - REJECTED
  "confidence": 0.5
}
```

### KB Verification Checklist

Before using ANY KB data, verify:
- [ ] Entity exists in appropriate KB table
- [ ] Data has been validated (data_confidence > 0.9)
- [ ] Source is documented (data_source field)
- [ ] No circular references or alias loops
- [ ] **Source URL is provided and verifiable**

---

## 1. Overview

This guide defines how the Knowledge Base (KB) should be structured and how AI agents should use it for entity resolution, classification, and intelligence enrichment.

### 1.1 Knowledge Domains

| Domain | Primary Table | Purpose | Record Count |
|--------|---------------|---------|--------------|
| **Manufacturers** | `kb_manufacturers` | Engine makers registry | 9 |
| **Engine Series** | `kb_engine_series` | Product line families | 25 |
| **Engine Models** | `kb_engine_models` | Specific models with specs | 25+ |
| **Applications** | `kb_applications` | Use cases (ferry, OSV, etc.) | 10 |
| **Market Segments** | `kb_market_segments` | Market classifications | 5 |
| **Entity Aliases** | `kb_entity_aliases` | Alternative names/spellings | 80+ |

### 1.2 RRPS Product Focus

| Attribute | Value | Source |
|-----------|-------|--------|
| **Primary Brand** | MTU | RRPS Product Portfolio |
| **Secondary Brand** | Bergen Engines | RRPS Corporate |
| **Engine Type** | Medium-speed diesel/gas | Engineering |
| **RPM Range** | 300-1000 RPM (primary target) | Product Specs |
| **Power Range** | 700 kW - 40,000 kW | Product Portfolio |

---

## 2. Manufacturer Registry

### 2.1 Tier-1 Global Manufacturers

| Manufacturer | Country | Tier | Key Brands | KB ID Pattern |
|--------------|---------|------|------------|---------------|
| **Wärtsilä** | Finland | Tier 1 | Wärtsilä | `mfr-wartsila-*` |
| **MAN Energy Solutions** | Germany | Tier 1 | MAN, Pielstick | `mfr-man-*` |
| **SEMT Pielstick** | France | Tier 1 | Pielstick | `mfr-pielstick-*` |
| **Caterpillar MaK** | Germany | Tier 1 | CAT, MaK | `mfr-cat-*` |
| **HD Hyundai HiMSEN** | South Korea | Tier 1 | HiMSEN | `mfr-hyundai-*` |
| **Bergen Engines** | Norway | Tier 1 | Bergen | `mfr-bergen-*` |
| **Daihatsu Diesel** | Japan | Tier 1 | Daihatsu | `mfr-daihatsu-*` |
| **Niigata Power Systems** | Japan | Tier 1 | Niigata | `mfr-niigata-*` |
| **ABC Engines** | Belgium | Tier 1 | ABC | `mfr-abc-*` |

### 2.2 Manufacturer Data Structure

```json
{
  "id": "UUID",
  "name": "Official registered name",
  "country": "Country of headquarters",
  "tier": "tier_1|tier_2|tier_3",
  "website": "Official website URL",
  "description": "Brief description of company and products",
  "is_active": true,
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### 2.3 Manufacturer Matching Rules

**When matching manufacturer names in text:**

1. Check exact match in `kb_manufacturers.name`
2. If no match, check `kb_entity_aliases` where `entity_type='manufacturer'`
3. Normalize text (lowercase, remove special chars) before matching
4. Confidence scoring:
   - Exact match = 1.0
   - Alias match = 0.9
   - Fuzzy match (>90% similarity) = 0.7-0.9
   - Below 0.7 = flag for verification

---

## 3. Engine Series & Models

### 3.1 Engine Series Structure

```json
{
  "id": "UUID",
  "manufacturer_id": "FK to manufacturers",
  "brand": "Marketing brand name",
  "series_name": "Series identifier (e.g., '31', 'M32C')",
  "is_current": true,
  "created_at": "ISO 8601"
}
```

### 3.2 Engine Model Structure

```json
{
  "id": "UUID",
  "series_id": "FK to engine_series",
  "model_name": "Full model name",
  "rpm_min": 500,
  "rpm_max": 750,
  "power_min_kw": 3000,
  "power_max_kw": 12000,
  "fuel_types": ["diesel", "gas", "dual_fuel"],
  "configuration": "V|inline",
  "emission_tier": "IMO Tier III|IMO Tier II|EPA Tier 4",
  "is_current_production": true,
  "data_source": "manufacturer_website|spec_sheet|verified",
  "data_confidence": 0.95,
  "created_at": "ISO 8601"
}
```

### 3.3 Reference Engine Models in KB

| Manufacturer | Series | Model | Power Range (kW) | RPM | Fuel Types |
|--------------|--------|-------|------------------|-----|------------|
| **Wärtsilä** | 31 | Wärtsilä 31DF | 4,600-10,400 | 720-750 | diesel, gas, dual_fuel |
| **Wärtsilä** | 46F | Wärtsilä 46F | 7,500-20,000 | 500-600 | diesel, gas |
| **MAN** | 32/44CR | MAN 32/44CR | 3,600-12,000 | 720-750 | diesel, hfo, dual_fuel |
| **MAN** | 48/60CR | MAN 48/60CR | 12,000-30,000 | 500-600 | diesel, hfo, gas |
| **MAN** | 51/60 | MAN 51/60 | 18,000-40,000 | 500-514 | diesel, hfo, gas |
| **Pielstick** | PC2.6B | PC2.6B | 9,000-13,500 | 600 | diesel, hfo |
| **Pielstick** | PC4.2B | PC4.2B | 4,200-8,400 | 600 | diesel, hfo |
| **Pielstick** | PC40 | PC40 | 6,000-12,000 | 600 | diesel, hfo |
| **Caterpillar MaK** | M32C | MaK M32C | 6,000-8,000 | 720-750 | diesel, hfo |
| **Caterpillar MaK** | M34DF | MaK M34DF | 3,600-7,200 | 720-750 | dual_fuel, lng, diesel |
| **Caterpillar MaK** | M43C | MaK M43C | 5,400-9,450 | 500-514 | diesel, hfo |
| **Caterpillar MaK** | M46DF | MaK M46DF | 5,400-18,000 | 500-514 | dual_fuel, lng, diesel |
| **HiMSEN** | H21/32 | HiMSEN H21/32 | 800-2,000 | 720-900 | diesel |
| **HiMSEN** | H32/40 | HiMSEN H32/40 | 3,000-9,600 | 720-750 | diesel, gas |
| **HiMSEN** | H54DF | HiMSEN H54DF | 8,900-26,460 | 600 | dual_fuel |
| **Bergen** | C25:33 | Bergen C25:33 | 1,200-1,920 | 900-1000 | diesel, gas |
| **Bergen** | B32:40 | Bergen B32:40 | 3,000-9,000 | 720-750 | diesel, gas |
| **Bergen** | B33:45 | Bergen B33:45 | 4,500-10,800 | 720-750 | diesel, gas |
| **Bergen** | B36:45 | Bergen B36:45 | 6,000-12,000 | 720-750 | gas, diesel |
| **Daihatsu** | DE | Daihatsu 8DE-33 | 3,600-4,800 | 720-750 | diesel |
| **Daihatsu** | DK | Daihatsu DK-series | 1,500-3,500 | 720-900 | diesel |
| **Niigata** | 28AHX-DF | Niigata 28AHX-DF | 4,000-6,000 | 750 | dual_fuel, lng, diesel |
| **ABC** | DV36 | ABC 16DV36 | 7,800-10,400 | 600-750 | diesel, hfo |
| **ABC** | DZC | ABC DZC | 2,000-5,000 | 720-900 | diesel |

### 3.4 Engine Matching Rules

**When matching engine names in text:**

1. Check series aliases first (`kb_entity_aliases` where `entity_type='engine_series'`)
2. Normalize: remove spaces, handle variations (e.g., "W31" → "31")
3. Match partial strings (e.g., "Wärtsilä 31" matches series "31" under Wärtsilä)
4. Power validation: if power mentioned in source, verify against KB range
5. Confidence thresholds:
   - Model name match = 1.0
   - Series + manufacturer match = 0.9
   - Alias match = 0.85
   - Power-based inference = 0.7 (flag for verification)

---

## 4. Entity Aliases

### 4.1 Alias Structure

```json
{
  "id": "UUID",
  "entity_type": "manufacturer|engine_series|engine_model",
  "entity_id": "FK to referenced entity",
  "alias_text": "Alternative name or spelling",
  "alias_type": "common_name|abbreviation|former_name|typo",
  "normalized_text": "lowercase, stripped version",
  "source": "seed_data|user_added|auto_detected",
  "confidence": 1.0,
  "is_active": true
}
```

### 4.2 Alias Types

| Alias Type | Description | Example |
|------------|-------------|---------|
| `common_name` | Commonly used alternative | "Wartsila" for "Wärtsilä" |
| `abbreviation` | Short form | "MAN" for "MAN Energy Solutions" |
| `former_name` | Historical name | "Rolls-Royce Bergen" for "Bergen Engines" |
| `typo` | Common misspellings | "Waertsilae" for "Wärtsilä" |

### 4.3 Key Aliases in KB

| Entity | Canonical Name | Aliases |
|--------|----------------|---------|
| Manufacturer | Wärtsilä | Wartsila, Waertsilae |
| Manufacturer | MAN Energy Solutions | MAN, MAN ES, MAN Diesel |
| Manufacturer | SEMT Pielstick | Pielstick, SEMT, MAN France |
| Manufacturer | Caterpillar MaK | Caterpillar, Cat, CAT, MaK |
| Manufacturer | HD Hyundai HiMSEN | Hyundai, HD Hyundai, HiMSEN |
| Manufacturer | Bergen Engines | Bergen, Rolls-Royce Bergen |
| Engine Series | 31 (Wärtsilä) | W31, Wärtsilä31, 31DF |
| Engine Series | M32C (MaK) | M32C |
| Engine Series | H32/40 (HiMSEN) | H32, H32-40 |

---

## 5. Applications

### 5.1 Application Structure

```json
{
  "id": "UUID",
  "name": "Marine Propulsion",
  "code": "PROP",
  "category": "commercial|offshore|military|pleasure",
  "typical_power_range_min_kw": 1000,
  "typical_power_range_max_kw": 40000,
  "description": "Main propulsion for commercial vessels",
  "is_active": true
}
```

### 5.2 Application Registry

| Application | Code | Category | Power Range (kW) | Typical Vessels |
|-------------|------|----------|------------------|-----------------|
| **Marine Propulsion** | PROP | commercial | 1,000-40,000 | Cargo, tanker, container |
| **Marine Genset** | GENSET | commercial | 500-20,000 | All vessel types |
| **Auxiliary Power** | AUX | commercial | 500-5,000 | Cargo, passenger |
| **FPSO Power** | FPSO | offshore | 5,000-40,000 | Floating production |
| **Offshore Platform** | PLATFORM | offshore | 3,000-30,000 | Fixed platforms |
| **Drilling Rig** | DRILL | offshore | 2,000-20,000 | Drillships, semisubs |
| **OSV/PSV** | OSV | offshore | 2,000-10,000 | Supply vessels |
| **Ferry** | FERRY | commercial | 2,000-15,000 | Passenger ferries |
| **Cargo Vessel** | CARGO | commercial | 3,000-25,000 | Bulk, general cargo |
| **Tanker** | TANKER | commercial | 5,000-30,000 | Oil, chemical, LNG |

### 5.3 Application Matching Rules

**When classifying applications from text:**

1. Keyword detection from application names and descriptions
2. Power validation: if power mentioned, check against typical range
3. Multiple applications can apply (e.g., OSV with genset)
4. Primary application = highest power requirement mentioned

---

## 6. Market Segments

### 6.1 Market Segment Structure

```json
{
  "id": "UUID",
  "name": "Offshore Oil & Gas",
  "segment_type": "offshore_oil_gas",
  "priority_score": 90,
  "growth_potential": "high|medium|low",
  "description": "Oil and gas exploration and production platforms",
  "is_active": true
}
```

### 6.2 Market Segment Registry

| Segment | Type Code | Priority | Growth | RRPS Focus |
|---------|-----------|----------|--------|------------|
| **Marine Transportation** | `marine_transportation` | 70 | Medium | Ferries, OSVs, cargo |
| **Offshore Oil & Gas** | `offshore_oil_gas` | 90 | High | Platforms, rigs |
| **FPSO/Offshore Production** | `fpso_offshore_production` | 95 | High | Floating production |
| **Marine Power Generation** | `marine_power_generation` | 80 | Medium | Shipboard gensets |
| **Land Power Plant** | `land_power_plant` | 30 | Low | Stationary power |

### 6.3 Segment Classification Rules

**Priority weighting for intelligence scoring:**

- FPSO/Offshore Production = highest priority (95)
- Offshore Oil & Gas = high priority (90)
- Marine Power Generation = medium-high (80)
- Marine Transportation = medium (70)
- Land Power Plant = lowest for marine focus (30)

---

## 7. Risk Intelligence & Partner Due Diligence

### 7.1 Risk Signal Categories

AI agents MUST monitor and flag the following risk categories for partners, customers, and manufacturers:

| Risk Category | Code | Description | Severity |
|---------------|------|-------------|----------|
| **Legal Disputes** | `LEGAL_DISPUTE` | Lawsuits, arbitration, litigation involving the entity | HIGH |
| **Regulatory Violations** | `REGULATORY_VIOLATION` | Fines, sanctions, compliance failures | HIGH |
| **Financial Distress** | `FINANCIAL_DISTRESS` | Bankruptcy, debt defaults, credit downgrades | CRITICAL |
| **Safety Incidents** | `SAFETY_INCIDENT` | Accidents, injuries, fatalities, vessel incidents | HIGH |
| **Environmental Issues** | `ENVIRONMENTAL` | Oil spills, emissions violations, pollution | HIGH |
| **Corruption/Fraud** | `CORRUPTION_FRAUD` | Bribery, fraud investigations, ethics violations | CRITICAL |
| **Sanctions/Blacklist** | `SANCTIONS` | OFAC, EU sanctions, trade restrictions | CRITICAL |
| **Management Changes** | `MGMT_CHANGE` | CEO departure, board disputes, leadership instability | MEDIUM |
| **Negative Press** | `NEGATIVE_PRESS` | Reputational damage, public criticism | MEDIUM |
| **Supply Chain Issues** | `SUPPLY_CHAIN` | Delivery failures, quality problems, recalls | MEDIUM |
| **TPRM Assessment** | `TPRM_ASSESSMENT` | Third-party risk assessment from Aravo platform | VARIES |

### 7.2 Risk Signal Structure

```json
{
  "id": "RISK-{entity_type}-{entity_id}-YYYY-MM-DD-NNN",
  "entity_type": "manufacturer|customer|partner|shipyard",
  "entity_id": "KB entity ID or name",
  "entity_name": "Entity display name",

  "risk_category": "RISK_CATEGORY from 7.1",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "headline": "Concise description (max 120 chars)",
  "description": "Detailed summary of the risk (max 500 chars)",

  "source": {
    "url": "Source URL (MUST be verifiable)",
    "name": "Source publication name",
    "published_date": "YYYY-MM-DD",
    "accessed_date": "YYYY-MM-DD"
  },

  "financial_impact": {
    "estimated_value_usd": "If quantified in source, or null",
    "fine_amount_usd": "If regulatory fine, or null",
    "settlement_amount_usd": "If legal settlement, or null"
  },

  "regulatory_details": {
    "regulatory_body": "MPA|IMO|EPA|SEC|DOJ|etc.",
    "violation_type": "Type of violation",
    "jurisdiction": "Country/region"
  },

  "status": "ACTIVE|RESOLVED|UNDER_INVESTIGATION|MONITORING",
  "first_reported": "YYYY-MM-DD",
  "last_updated": "YYYY-MM-DD",

  "data_quality": {
    "confidence_score": 0.0-1.0,
    "verified_sources": 1,
    "requires_verification": true|false
  },

  "recommended_action": "Specific action for sales team"
}
```

### 7.3 Risk Detection Keywords

```yaml
legal_disputes:
  - "lawsuit"
  - "litigation"
  - "arbitration"
  - "legal action"
  - "court case"
  - "sued"
  - "plaintiff"
  - "defendant"
  - "settlement"
  - "damages awarded"

regulatory_violations:
  - "fined"
  - "penalty"
  - "violation"
  - "non-compliance"
  - "regulatory action"
  - "enforcement"
  - "cease and desist"
  - "license revoked"
  - "suspended"

financial_distress:
  - "bankruptcy"
  - "insolvency"
  - "debt default"
  - "credit downgrade"
  - "restructuring"
  - "liquidation"
  - "chapter 11"
  - "administration"
  - "financial difficulties"

safety_incidents:
  - "accident"
  - "collision"
  - "grounding"
  - "fire"
  - "explosion"
  - "fatality"
  - "injury"
  - "safety violation"
  - "vessel detained"
  - "port state control"

environmental_issues:
  - "oil spill"
  - "pollution"
  - "emissions violation"
  - "environmental damage"
  - "contamination"
  - "discharge"
  - "MARPOL violation"

corruption_fraud:
  - "bribery"
  - "corruption"
  - "fraud"
  - "investigation"
  - "indictment"
  - "FCPA"
  - "money laundering"
  - "embezzlement"

sanctions:
  - "sanctioned"
  - "sanctions list"
  - "blacklisted"
  - "OFAC"
  - "SDN list"
  - "trade restriction"
  - "export control"
  - "embargo"
  - "designated entity"
```

### 7.4 Risk Severity Scoring

```python
# Base severity by category
RISK_SEVERITY = {
    "SANCTIONS": "CRITICAL",        # Immediate deal-breaker
    "FINANCIAL_DISTRESS": "CRITICAL",
    "CORRUPTION_FRAUD": "CRITICAL",
    "LEGAL_DISPUTE": "HIGH",
    "REGULATORY_VIOLATION": "HIGH",
    "SAFETY_INCIDENT": "HIGH",
    "ENVIRONMENTAL": "HIGH",
    "MGMT_CHANGE": "MEDIUM",
    "NEGATIVE_PRESS": "MEDIUM",
    "SUPPLY_CHAIN": "MEDIUM",
}

# Escalation factors
def calculate_risk_score(risk: RiskSignal) -> int:
    base_score = {
        "CRITICAL": 90,
        "HIGH": 70,
        "MEDIUM": 50,
        "LOW": 30,
    }[risk.severity]

    # Escalate for recent events
    if risk.days_since_reported < 30:
        base_score += 10

    # Escalate for financial impact
    if risk.financial_impact and risk.financial_impact > 10_000_000:
        base_score += 10

    # Escalate for multiple sources
    if risk.verified_sources >= 3:
        base_score += 5

    return min(base_score, 100)
```

### 7.5 KYP Data Sources by Category

**⚠️ MANDATORY: Each finding MUST include a source URL from these databases.**

The KYP data sources are organized into three phases following the **"Inside-Out, Risk-First"** approach:

| Phase | Purpose | Data Sources | Sales Question |
|-------|---------|--------------|----------------|
| **Phase 1** | Business Context | SAP ERP/CRM | "What's at stake?" |
| **Phase 2** | Internal Risk Data | SAP Credit, Aravo TPRM | "What do our systems say?" |
| **Phase 3** | External Risk Data | Sanctions, Financial, Legal | "What's the due diligence?" |

---

## Phase 1: Business Context

> **Purpose:** Understand our existing relationship and what's at stake before conducting due diligence.

#### 7.5.1 Existing Relationship (SAP ERP)

| Source | SAP Module | Data Available | Priority |
|--------|------------|----------------|----------|
| **Customer Master** | SD (KNA1) | Customer ID, creation date, status | Tier 1 |
| **Business Partner** | BP | Partner type, relationship category | Tier 1 |
| **Account History** | FI (BSID/BSAD) | Transaction history, payment behavior | Tier 1 |

**Relationship Data Points:**

| Data Point | SAP Table/Field | KYP Usage |
|------------|-----------------|-----------|
| Customer ID | `KNA1-KUNNR` | Entity identification |
| Customer Since | `KNA1-ERDAT` | Relationship duration |
| Customer Status | `KNA1-AUFSD` | Active/Blocked status |
| Account Group | `KNA1-KTOKD` | Customer classification |
| Sales Organization | `KNVV-VKORG` | Regional assignment |
| Last Transaction | `BSID-BUDAT` | Recency indicator |

**Relationship Status Interpretation:**

| Status | Criteria | KYP Implication |
|--------|----------|-----------------|
| `STRATEGIC_CUSTOMER` | >5 years, >€1M/year | High priority, expedited KYP |
| `ACTIVE_CUSTOMER` | Transactions in last 12 months | Normal KYP process |
| `DORMANT_CUSTOMER` | No transactions 12-36 months | Review for win-back |
| `INACTIVE_CUSTOMER` | No transactions >36 months | Full KYP required |
| `NEW_PROSPECT` | Not in SAP | Full KYP required |

**Integration Pattern (Python):**
```python
from lead_to_cash.integrations import CPISimulator, MS5Client

async def get_relationship_status(company_name: str) -> dict:
    simulator = CPISimulator()
    await simulator.connect()
    ms5 = MS5Client(cpi_client=simulator)
    await ms5.connect()

    # Search for customer
    customers = await ms5.search_customers(name=company_name)

    if not customers:
        return {"status": "NEW_PROSPECT", "customer_since": None}

    customer = customers[0]
    return {
        "status": "ACTIVE_CUSTOMER",
        "customer_id": customer.get("customer_id"),
        "customer_since": customer.get("created_date"),
        "last_transaction": customer.get("last_transaction_date"),
    }
```

#### 7.5.2 Active Contracts (SAP SD)

| Source | SAP Module | Data Available | Priority |
|--------|------------|----------------|----------|
| **Sales Contracts** | SD (VBAK/VBAP) | Contract value, validity, items | Tier 1 |
| **Service Contracts** | CS (SM contracts) | Service agreements, SLAs | Tier 1 |
| **Pricing Conditions** | SD (KONV) | Agreed pricing, discounts | Tier 1 |

**Contract Data Points:**

| Data Point | SAP Table/Field | KYP Usage |
|------------|-----------------|-----------|
| Contract Number | `VBAK-VBELN` | Contract identification |
| Contract Type | `VBAK-AUART` | Sales/Service/Framework |
| Valid From | `VBAK-GUEBG` | Contract start date |
| Valid To | `VBAK-GUEEN` | Contract end date |
| Net Value | `VBAK-NETWR` | Contract value |
| Currency | `VBAK-WAERK` | Contract currency |
| Status | `VBAK-GBSTK` | Active/Completed/Cancelled |

**Contract Value Interpretation:**

| Annual Contract Value | Business Impact | KYP Priority |
|----------------------|-----------------|--------------|
| >€5M | CRITICAL | Expedite - Executive review |
| €1M - €5M | HIGH | Priority processing |
| €100K - €1M | MEDIUM | Standard processing |
| <€100K | LOW | Standard processing |

#### 7.5.3 Pipeline & Opportunities (SAP CRM)

| Source | SAP Module | Data Available | Priority |
|--------|------------|----------------|----------|
| **Opportunities** | CRM (CRMD_ORDERADM_H) | Deal value, stage, probability | Tier 1 |
| **Quotations** | SD (VBAK type AG) | Quoted value, validity | Tier 1 |
| **Leads** | CRM | Lead source, qualification | Tier 2 |

**Pipeline Data Points:**

| Data Point | Source | KYP Usage |
|------------|--------|-----------|
| Opportunity ID | SAP CRM | Pipeline identification |
| Opportunity Value | SAP CRM | Revenue potential |
| Win Probability | SAP CRM | Deal likelihood |
| Expected Close | SAP CRM | Timeline urgency |
| Sales Stage | SAP CRM | Progress indicator |
| Competitor | SAP CRM | Competitive context |

**Pipeline Impact Assessment:**

| Pipeline Value | Urgency | KYP Action |
|---------------|---------|------------|
| >€10M | CRITICAL | Same-day KYP completion |
| €1M - €10M | HIGH | 48-hour KYP completion |
| €100K - €1M | MEDIUM | Standard 5-day KYP |
| <€100K | LOW | Standard processing |

#### 7.5.4 Revenue & Installed Base (SAP)

| Source | SAP Module | Data Available | Priority |
|--------|------------|----------------|----------|
| **Billing History** | FI (BSID/BSAD) | Revenue by period | Tier 1 |
| **Equipment Master** | PM (EQUI) | Installed engines, serial numbers | Tier 1 |
| **Service History** | CS (IW orders) | Maintenance, repairs | Tier 1 |

**Revenue Data Points:**

| Data Point | SAP Source | KYP Usage |
|------------|------------|-----------|
| Revenue (LTM) | FI - Last 12 months billing | Current business value |
| Revenue (Prior Year) | FI - Prior 12 months | Trend indicator |
| Revenue by Type | FI - Document type | Product vs Service mix |
| Payment Terms | KNB1-ZTERM | Payment behavior |
| DSO | Calculated | Collection efficiency |

**Installed Base Data Points:**

| Data Point | SAP Table/Field | KYP Usage |
|------------|-----------------|-----------|
| Equipment ID | `EQUI-EQUNR` | Asset identification |
| Engine Model | `EQUI-EQART` | Product installed |
| Serial Number | `EQUI-SERNR` | Unit identification |
| Install Date | `EQUI-INBDT` | Age of installation |
| Warranty End | `EQUI-GWLEN` | Service opportunity |
| Location | `EQUI-TPLNR` | Vessel/Site |

**Business Context Summary Format:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  BUSINESS CONTEXT: {Company Name}                                        │
├─────────────────────────────┬───────────────────────────────────────────┤
│ Relationship Status         │ {STRATEGIC/ACTIVE/DORMANT/NEW_PROSPECT}   │
│ Customer Since              │ {Date or "New Prospect"}                  │
│ Active Contracts            │ {Count} contracts, {Currency} {Value}/yr  │
│ Open Pipeline               │ {Count} opportunities, {Currency} {Value} │
│ Installed Base              │ {Count} engines across {Count} assets     │
│ Revenue (Last 12mo)         │ {Currency} {Value}                        │
├─────────────────────────────┴───────────────────────────────────────────┤
│ BUSINESS IMPACT: {CRITICAL/HIGH/MEDIUM/LOW}                              │
│ Total Value at Stake: {Currency} {Current + Pipeline Value}              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 2: Internal Risk Data

> **Purpose:** Check our internal systems before external due diligence.

#### 7.5.5 SAP Credit Status (SAP CPI/MS5)

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **SAP CPI (MS5)** | Via CPI iFlow | Customer master, credit limits, exposure | Tier 1 |
| **BAPI_CR_ACC_GETDETAIL** | SAP RFC | Credit control area, limits, utilization | Tier 1 |
| **Customer Search** | SAP RFC | Customer ID, name, UEN, address | Tier 1 |

**SAP Credit Data Points:**

| Data Point | SAP Field | KYP Usage |
|------------|-----------|-----------|
| Customer ID | `KUNNR` | Entity identification |
| Customer Name | `NAME1` | Entity profile |
| UEN/Tax Number | `STCD1` | Singapore company verification |
| Credit Control Area | `KKBER` | Regional credit policy |
| Credit Limit | `KLIMK` | Maximum approved credit |
| Credit Exposure | `SKFOR` | Current outstanding |
| Available Credit | Calculated | `KLIMK - SKFOR` |
| Utilization % | Calculated | `SKFOR / KLIMK * 100` |
| Credit Status | `CTLPC` | Blocked/Approved indicator |

**Integration Pattern (Python):**
```python
from lead_to_cash.integrations import CPISimulator, MS5Client

# Connect to SAP CPI
simulator = CPISimulator()
await simulator.connect()
ms5 = MS5Client(cpi_client=simulator)
await ms5.connect()

# Search for customer
customers = await ms5.search_customers(name="Batam Fast Ferry")
if customers:
    customer = customers[0]
    customer_id = customer.get("customer_id")

    # Get credit data
    credit = await ms5.check_credit_limit(
        customer_id=customer_id,
        credit_control_area="1000"  # Default for Singapore
    )

    print(f"Credit Limit: {credit['currency']} {credit['credit_limit']:,.2f}")
    print(f"Utilization: {credit['utilization']:.1f}%")
    print(f"Status: {'BLOCKED' if credit['blocked'] else 'APPROVED'}")
```

**SAP Credit Status Interpretation:**

| SAP Status | KYP Interpretation | Action |
|------------|-------------------|--------|
| No block, utilization < 80% | `NO_ADVERSE_FINDINGS` | Standard terms apply |
| Utilization 80-100% | `NO_ADVERSE_FINDINGS` (Note: High utilization) | Monitor closely |
| Utilization > 100% | `ADVERSE_FINDINGS` | Credit review required |
| Credit blocked | `ADVERSE_FINDINGS` | Do not proceed without approval |
| Customer not found | `UNABLE_TO_VERIFY` | New prospect - manual review |

**Search Query Template:**
```
"{entity_name}" SAP customer credit limit exposure
```

#### 7.5.6 Third-Party Risk Management (Aravo TPRM)

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **Aravo TPRM Platform** | https://[customer].aravo.com/ | Supplier due diligence, risk assessments | Tier 1 |
| **Aravo Supplier Portal** | Supplier self-service | Questionnaire responses, certifications | Tier 1 |
| **Business Process Workflows** | Aravo API | Onboarding status, approval workflows | Tier 1 |
| **Risk Assessment Reports** | Aravo Reports API | Historical assessments, trend analysis | Tier 1 |

**TPRM Data Points:**

| Data Point | Aravo Field | KYP Usage |
|------------|-------------|-----------|
| Supplier ID | `aravo_supplier_id` | Entity identification |
| Supplier Status | `supplier_status` | Approval state |
| Inherent Risk Score | `inherent_risk_score` | Risk rating (0-100) |
| TPRM Status | `tprm_status` | Overall assessment |
| Due Diligence Status | `due_diligence_workflows[].status` | Workflow progress |
| Questionnaire Scores | `questionnaire_scores[]` | Compliance scores |

**Integration Pattern (Python):**
```python
from lead_to_cash.integrations.aravo_client import AravoClient
from lead_to_cash.integrations.aravo_simulator import AravoSimulator

# Production
async with AravoClient() as aravo:
    assessment = await aravo.get_tprm_assessment(supplier_id="SUP-001")
    print(f"Risk Score: {assessment.overall_risk_score}")
    print(f"TPRM Status: {assessment.tprm_status.value}")

# Development/Testing
async with AravoSimulator() as aravo:
    suppliers = await aravo.search_suppliers(name="Batam Fast Ferry")
    for supplier in suppliers:
        print(f"Supplier: {supplier.name}, Status: {supplier.status}")
```

**TPRM Status Interpretation:**

| Aravo Supplier Status | TPRM Status | Action |
|----------------------|-------------|--------|
| `Approved`, `Active` | `NO_ADVERSE_FINDINGS` | Proceed with engagement |
| `Rejected`, `Blocked`, `Terminated` | `ADVERSE_FINDINGS` | Investigate before engagement |
| `Pending`, `Under Review`, `In Progress` | `UNDER_REVIEW` | Wait for due diligence completion |
| Other/Unknown | `UNABLE_TO_VERIFY` | Manual verification required |

---

## Phase 3: External Risk Data

> **Purpose:** Conduct external due diligence using public sources and databases.

#### 7.5.7 Sanctions & Blacklist Check

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **OFAC SDN List** | https://sanctionssearch.ofac.treas.gov/ | US sanctions, SDN designations | Tier 1 |
| **OFAC Recent Actions** | https://ofac.treasury.gov/recent-actions | Latest sanctions updates | Tier 1 |
| **EU Consolidated List** | https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions | EU sanctions | Tier 1 |
| **UN Security Council** | https://www.un.org/securitycouncil/sanctions/information | UN sanctions | Tier 1 |
| **Singapore MAS** | https://www.mas.gov.sg/regulation/anti-money-laundering | AML/sanctions | Tier 1 |
| **News Search** | Perplexity/NewsAPI | Sanctions-related news | Tier 2 |

**Search Query Template:**
```
"{entity_name}" AND (sanctions OR "OFAC" OR "SDN list" OR "blacklist" OR "trade restriction")
```

#### 7.5.8 Financial Health (External)

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **Company Website** | Investor Relations section | Annual reports, financials | Tier 1 |
| **Annual Reports** | Company filings | Revenue, profit, assets, debt | Tier 1 |
| **EODHD API** | https://eodhd.com/ | SEC filings (public companies) | Tier 1 |
| **SGX** | https://www.sgx.com/ | Singapore listed companies | Tier 1 |
| **IDX** | https://www.idx.co.id/ | Indonesia listed companies | Tier 1 |
| **Moody's** | https://www.moodys.com/ | Credit ratings | Tier 1 |
| **S&P Global** | https://www.spglobal.com/ | Credit ratings | Tier 1 |
| **Fitch Ratings** | https://www.fitchratings.com/ | Credit ratings | Tier 1 |
| **Parent Company Filings** | Listed parent annual reports | Subsidiary financials | Tier 2 |
| **Business News** | Reuters, Bloomberg, Straits Times | Financial performance news | Tier 2 |

**Search Query Template:**
```
"{entity_name}" AND (revenue OR profit OR financial OR "annual report" OR investment OR fleet OR vessel order)
```

#### 7.5.9 Ownership, UBO & Leadership

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **Company Website** | Entity's official website | About Us, Leadership, Board | Tier 1 |
| **Singapore ACRA** | https://www.acra.gov.sg/bizfile | Singapore company registry | Tier 1 |
| **Indonesia AHU** | https://ahu.go.id/ | Indonesia company registry | Tier 1 |
| **Annual Reports** | Company investor relations | Ownership, financials, leadership | Tier 1 |
| **ZoomInfo** | https://www.zoominfo.com/ | Executives, org structure | Tier 2 |
| **LinkedIn** | https://www.linkedin.com/ | Executive profiles | Tier 2 |
| **RecordOwl** | https://recordowl.com/ | Singapore company data | Tier 2 |
| **Datanyze** | https://www.datanyze.com/ | Company technographics | Tier 3 |

**Search Query Template:**
```
"{entity_name}" AND (CEO OR "chief executive" OR founder OR owner OR director OR board OR shareholder OR UBO)
```

#### 7.5.10 Litigation & Legal Disputes

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **CCS Singapore** | https://www.ccs.gov.sg/case-register | Competition law decisions | Tier 1 |
| **Singapore Courts** | https://www.judiciary.gov.sg/ | Court judgments | Tier 1 |
| **Indonesia Courts** | https://putusan3.mahkamahagung.go.id/ | Indonesian court decisions | Tier 1 |
| **SEC EDGAR** | https://www.sec.gov/edgar | US legal disclosures | Tier 1 |
| **News Archives** | Straits Times, Reuters, Bloomberg | Litigation coverage | Tier 2 |
| **Law Firm Publications** | Drew & Napier, Allen & Gledhill | Case analysis | Tier 2 |

**Search Query Template:**
```
"{entity_name}" AND (lawsuit OR litigation OR court OR sued OR fine OR penalty OR settlement OR arbitration)
```

#### 7.5.11 Safety Record & Incidents

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **MPA Singapore** | https://www.mpa.gov.sg/media-centre | Investigation reports, detentions | Tier 1 |
| **Indonesia KNKT** | http://knkt.dephub.go.id/ | Maritime accident investigations | Tier 1 |
| **IMO GISIS** | https://gisis.imo.org/ | Global maritime incidents | Tier 1 |
| **Classification Societies** | DNV, Lloyd's, BV, ABS | Vessel certifications, detentions | Tier 1 |
| **Safety4Sea** | https://safety4sea.com/ | Maritime safety news | Tier 2 |
| **Maritime Executive** | https://maritime-executive.com/ | Incident coverage | Tier 2 |
| **FleetMon** | https://www.fleetmon.com/ | Vessel tracking, incidents | Tier 2 |
| **MagicPort** | https://magicport.ai/ | Fleet data, vessel info | Tier 2 |
| **Port State Control** | Paris MoU, Tokyo MoU databases | Vessel detentions | Tier 1 |

**Search Query Template:**
```
"{entity_name}" AND (accident OR collision OR grounding OR fire OR detained OR investigation OR safety)
```

#### 7.5.12 Environmental Compliance

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **MPA Singapore** | https://www.mpa.gov.sg/ | Environmental enforcement | Tier 1 |
| **Indonesia KLHK** | https://www.menlhk.go.id/ | Environmental ministry | Tier 1 |
| **IMO** | https://www.imo.org/ | MARPOL violations | Tier 1 |
| **EPA** | https://www.epa.gov/ | US environmental violations | Tier 1 |
| **News Archives** | Search for spills, violations | Environmental incidents | Tier 2 |

**Search Query Template:**
```
"{entity_name}" AND ("oil spill" OR pollution OR emissions OR environmental OR MARPOL OR discharge)
```

#### 7.5.13 Reputation & Customer Feedback

| Source | URL | Data Available | Priority |
|--------|-----|----------------|----------|
| **TripAdvisor** | https://www.tripadvisor.com/ | Customer reviews, ratings | Tier 1 |
| **Google Reviews** | https://www.google.com/maps | Customer reviews, ratings | Tier 1 |
| **Facebook** | https://www.facebook.com/ | Company reviews, complaints | Tier 2 |
| **News Archives** | Straits Times, CNA, Jakarta Post | Media coverage | Tier 2 |
| **Industry Forums** | Marine industry forums | Industry reputation | Tier 3 |
| **Better Business Bureau** | https://www.bbb.org/ | Complaints (if applicable) | Tier 3 |

**Search Query Template:**
```
"{entity_name}" AND (review OR complaint OR customer service OR reputation OR experience)
```

#### 7.5.14 Source Priority Matrix

| Priority | Source Type | Confidence Boost | Examples |
|----------|-------------|------------------|----------|
| **Tier 1** | Official/Regulatory | +0.3 | OFAC, MPA, Courts, Company filings |
| **Tier 2** | Reliable Third-Party | +0.2 | Reuters, Bloomberg, ZoomInfo, TripAdvisor |
| **Tier 3** | Supplementary | +0.1 | Social media, forums, minor publications |

**Confidence Calculation:**
```python
base_confidence = 0.5
for source in findings:
    if source.tier == 1:
        base_confidence += 0.3
    elif source.tier == 2:
        base_confidence += 0.2
    elif source.tier == 3:
        base_confidence += 0.1
final_confidence = min(base_confidence, 1.0)
```

### 7.6 Due Diligence Terminology Standards

**⚠️ CRITICAL: Use factual, evidence-based language. Never assert positive attributes without evidence.**

#### 7.6.1 Correct vs Incorrect Terminology

| Category | ❌ INCORRECT (Assertive) | ✅ CORRECT (Evidence-Based) |
|----------|--------------------------|----------------------------|
| **Sanctions** | "PASS - Clear of sanctions" | "No records found in OFAC/EU/UN databases searched" |
| **Sanctions** | "Company is not sanctioned" | "No matching entries identified in sanctions databases as of [date]" |
| **Litigation** | "CLEAR - No legal issues" | "No litigation records identified in public court databases" |
| **Litigation** | "Clean legal history" | "No adverse legal findings from searched sources" |
| **Financial** | "HEALTHY - Good financial standing" | "No bankruptcy filings or credit downgrades identified" |
| **Financial** | "Financially stable" | "No indicators of financial distress found in public records" |
| **Safety** | "GOOD - Excellent safety record" | "No safety incidents identified in maritime databases searched" |
| **Safety** | "Safe operator" | "No port state control detentions found in [database] for past 3 years" |
| **Reputation** | "POSITIVE - Good reputation" | "No significant negative press coverage identified" |
| **Reputation** | "Well-regarded company" | "No adverse media reports found in news archives searched" |
| **Overall** | "Low risk partner" | "No adverse findings from public sources reviewed" |

#### 7.6.2 Standard Due Diligence Phrases

**Use these phrases in KYP reports:**

```yaml
no_findings:
  sanctions: "No matching records identified in [OFAC SDN/EU/UN] databases as of [date]"
  litigation: "No litigation records identified in [court/database] search"
  regulatory: "No regulatory enforcement actions found in [authority] public records"
  safety: "No safety incidents reported in [MPA/maritime database] for reviewed period"
  financial: "No bankruptcy filings, credit downgrades, or payment defaults identified"
  environmental: "No environmental violations found in [agency] enforcement records"
  reputation: "No significant negative press coverage identified in news search"

with_findings:
  sanctions: "Entity identified in [list name] - [details]"
  litigation: "[X] legal matter(s) identified: [brief description]"
  regulatory: "Regulatory action(s) found: [authority], [date], [penalty if any]"
  safety: "[X] incident(s) identified: [date], [type], [source]"

limitations:
  - "Search limited to publicly available sources"
  - "Private company - financial data not publicly disclosed"
  - "Records prior to [date] not reviewed"
  - "Non-English language sources not searched"
```

#### 7.6.3 Status Codes

| Status Code | Meaning | When to Use |
|-------------|---------|-------------|
| `NO_ADVERSE_FINDINGS` | No negative information found | Default when searches return no issues |
| `ADVERSE_FINDINGS` | Negative information identified | When issues are found with sources |
| `UNABLE_TO_VERIFY` | Could not access required data | Database unavailable or access restricted |
| `NOT_SEARCHED` | Category not yet reviewed | Incomplete due diligence |
| `REQUIRES_VERIFICATION` | Findings need manual confirmation | Low confidence or single source |

**NEVER use:** `PASS`, `FAIL`, `GOOD`, `BAD`, `CLEAR`, `CLEAN`, `SAFE`, `HEALTHY`, `POSITIVE`

### 7.7 Partner Due Diligence Checklist

Before engaging with any partner/customer, document findings for each category:

- [ ] **Sanctions Check**: Document databases searched, date, and result
- [ ] **Ownership Structure**: Document sources checked for UBO identification
- [ ] **Financial Health**: Document financial records/filings reviewed
- [ ] **Litigation History**: Document court databases and news archives searched
- [ ] **Regulatory Standing**: Document regulatory bodies' public records checked
- [ ] **Safety Record**: Document maritime safety databases reviewed
- [ ] **Environmental Compliance**: Document environmental agency records checked
- [ ] **Reputation**: Document news sources and review platforms searched
- [ ] **TPRM Status**: Document Aravo supplier status, risk score, and due diligence workflow

**Checklist Result Format:**
```markdown
| Category | Sources Searched | Result | Date |
|----------|------------------|--------|------|
| Sanctions | OFAC SDN, EU List | No matching records identified | 2026-01-20 |
| Litigation | CCS Singapore, news archives | 1 resolved regulatory matter (2012) | 2026-01-20 |
| Safety | MPA Singapore, Safety4Sea | 1 grounding incident (2015, resolved) | 2026-01-20 |
```

### 7.8 Risk Alert Format

```markdown
## RISK ALERT: [Entity Name]

**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Category:** [Risk Category]
**Date Detected:** YYYY-MM-DD

### Summary
[Brief description of the risk - use evidence-based language]

### Source
- **Publication:** [Name]
- **URL:** [Link]  ← REQUIRED
- **Date:** YYYY-MM-DD

### Financial Impact
- Estimated: $X (if known, or "Not quantified in source")

### Recommended Action
[Specific action for sales team]

### Verification Status
- [ ] Primary source verified
- [ ] Secondary source confirmed
- [ ] Legal/compliance review required

### Search Limitations
- [List any databases not searched or access limitations]
```

### 7.9 What AI Agents Must NEVER Do (Risk Intelligence)

1. **NEVER report unverified allegations as facts**
2. **NEVER assign CRITICAL severity without verified source**
3. **NEVER recommend deal termination without multiple sources**
4. **NEVER ignore risk signals for active customers**
5. **NEVER cache outdated sanctions data (refresh daily)**
6. **NEVER expose confidential investigation details**
7. **NEVER speculate on ongoing legal proceedings**
8. **NEVER conflate parent company issues with subsidiaries without verification**
9. **NEVER assert positive attributes without evidence** (e.g., "good reputation", "safe operator")
10. **NEVER use PASS/FAIL/GOOD/BAD terminology** - use evidence-based language only

---

## 8. Entity Resolution Rules

### 8.1 Resolution Algorithm

```python
def resolve_entity(text: str, entity_type: str) -> EntityMatch:
    """
    Resolve entity from text against KB.

    Returns:
        EntityMatch with entity_id, confidence, match_type
    """
    # Step 1: Exact match against canonical names
    exact = kb.find_exact(entity_type, text)
    if exact:
        return EntityMatch(exact.id, confidence=1.0, match_type="exact")

    # Step 2: Alias lookup
    normalized = normalize(text)  # lowercase, strip whitespace
    alias = kb.find_alias(entity_type, normalized)
    if alias:
        return EntityMatch(alias.entity_id, confidence=0.9, match_type="alias")

    # Step 3: Fuzzy matching (only if confidence threshold met)
    fuzzy_matches = kb.fuzzy_search(entity_type, text, threshold=0.8)
    if fuzzy_matches:
        best = max(fuzzy_matches, key=lambda m: m.similarity)
        if best.similarity >= 0.8:
            return EntityMatch(
                best.entity_id,
                confidence=best.similarity,
                match_type="fuzzy",
                requires_verification=best.similarity < 0.9
            )

    # Step 4: No match found
    return EntityMatch(
        entity_id=None,
        confidence=0.0,
        match_type="not_found",
        requires_verification=True
    )
```

### 8.2 Confidence Thresholds

| Confidence | Action | Match Type |
|------------|--------|------------|
| 1.0 | Use directly | Exact match |
| 0.9-0.99 | Use with note | Alias match |
| 0.8-0.89 | Use but flag | Fuzzy match |
| < 0.8 | Do not use | Requires manual resolution |

### 8.3 Entity Resolution in Intelligence Reports

**DO:**
- Include KB entity ID when match confidence >= 0.8
- Include match confidence in metadata
- Link to KB entity for enrichment

**DON'T:**
- Use unresolved entities without flagging
- Assume matches below threshold
- Create new entities without verification

---

## 9. Embedding Strategy

### 9.1 Embedding Fields

| Entity Type | Fields to Embed | Purpose |
|-------------|-----------------|---------|
| Manufacturer | name, description | Semantic search |
| Engine Series | brand + series_name + description | Product search |
| Engine Model | model_name + specs | Spec matching |
| Application | name + description | Use case matching |

### 9.2 Embedding Model

| Parameter | Value |
|-----------|-------|
| Model | text-embedding-3-small |
| Dimensions | 1536 |
| Chunking | N/A for KB (single documents) |

### 9.3 Vector Search Rules

```python
async def kb_semantic_search(
    query: str,
    entity_type: str,
    top_k: int = 5,
    threshold: float = 0.7
) -> list[KBMatch]:
    """
    Semantic search against KB embeddings.

    Args:
        query: User query text
        entity_type: manufacturer|engine_series|engine_model|application
        top_k: Number of results
        threshold: Minimum similarity score

    Returns:
        List of KBMatch objects with similarity scores
    """
    query_embedding = await embed(query)
    results = await kb.vector_search(
        entity_type=entity_type,
        embedding=query_embedding,
        top_k=top_k
    )
    return [r for r in results if r.similarity >= threshold]
```

---

## 10. Query Patterns

### 10.1 Common KB Queries

| Query Type | Pattern | Use Case |
|------------|---------|----------|
| Get manufacturer by name | `kb.get_manufacturer(name)` | Entity resolution |
| List engines by power | `kb.engines_by_power(min_kw, max_kw)` | Spec matching |
| Find competitors for engine | `kb.get_competitors(engine_id)` | Competitive mapping |
| Get aliases for entity | `kb.get_aliases(entity_type, entity_id)` | Fuzzy matching |
| Search by application | `kb.engines_for_application(app_code)` | Use case filtering |

### 10.2 Enrichment Patterns

**When enriching intelligence with KB:**

```python
async def enrich_news_item(item: NewsItem) -> EnrichedItem:
    """
    Enrich news item with KB data.
    """
    enriched = item.copy()

    # Resolve mentioned manufacturers
    for company in item.companies:
        match = await resolve_entity(company, "manufacturer")
        if match.confidence >= 0.8:
            enriched.kb_manufacturers.append({
                "name": company,
                "kb_id": match.entity_id,
                "confidence": match.confidence,
                "match_type": match.match_type
            })
        else:
            enriched.unresolved_entities.append(company)

    # Resolve engine mentions
    for engine in item.engines_mentioned:
        match = await resolve_entity(engine, "engine_model")
        if not match.entity_id:
            match = await resolve_entity(engine, "engine_series")

        if match.confidence >= 0.8:
            enriched.kb_engines.append({
                "mention": engine,
                "kb_id": match.entity_id,
                "confidence": match.confidence,
                "match_type": match.match_type
            })

    # Flag items needing verification
    if enriched.unresolved_entities:
        enriched.requires_verification = True

    return enriched
```

---

## 11. What AI Agents Must NEVER Do

1. **NEVER invent engine models not in the KB**
2. **NEVER fabricate specifications (power, RPM, fuel types)**
3. **NEVER assume manufacturer ownership without verification**
4. **NEVER create new KB entries without human approval**
5. **NEVER use entity matches below 0.8 confidence without flagging**
6. **NEVER omit KB match metadata from enriched items**
7. **NEVER ignore unresolved entities - always flag them**
8. **NEVER extrapolate specs from similar models**
9. **NEVER report outdated products as current production**
10. **NEVER mix competitor and RRPS product data without clear labels**

---

## 12. Integration Points

### 12.1 System Dependencies

| System | Integration | Purpose |
|--------|-------------|---------|
| MarineIntelAgent | KB enrichment | Entity resolution for news |
| CompetitorIntelAgent | KB enrichment | Competitor product matching |
| PostgreSQL | kb_* tables | Data storage |
| pgvector | Embeddings | Semantic search |
| Seed Data | seed_data.py | Initial data population |

### 12.2 Database Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `kb_manufacturers` | Manufacturer registry | id, name, tier, country |
| `kb_engine_series` | Product line families | id, manufacturer_id, series_name |
| `kb_engine_models` | Specific models | id, series_id, power, rpm, fuel_types |
| `kb_applications` | Use case definitions | id, name, code, power_range |
| `kb_market_segments` | Market classifications | id, name, priority_score |
| `kb_entity_aliases` | Alternative names | id, entity_type, entity_id, alias_text |

### 12.3 Seed Data Management

**To seed the KB:**

```bash
# Preview what would be seeded
python -m lead_to_cash.services.knowledge_base.seed_data --dry-run

# Seed the database
python -m lead_to_cash.services.knowledge_base.seed_data

# Clear and re-seed (fresh start)
python -m lead_to_cash.services.knowledge_base.seed_data --clear-first
```

---

## 13. Data Quality & Maintenance

### 13.1 Data Confidence Levels

| Confidence | Source | Action Required |
|------------|--------|-----------------|
| 0.95+ | Official spec sheets, verified | Production use |
| 0.85-0.94 | Trade publications, reliable sources | Use with note |
| 0.70-0.84 | Single source, unverified | Flag for review |
| < 0.70 | Uncertain | Do not use in production |

### 13.2 KB Update Rules

- New manufacturers require approval before adding
- Engine spec updates must cite official source
- Aliases can be auto-added if similarity >= 0.95
- Deprecated entities should be marked `is_active=false`, not deleted

### 13.3 Data Freshness

| Data Type | Refresh Frequency | Staleness Threshold |
|-----------|-------------------|---------------------|
| Manufacturer info | Monthly | 6 months |
| Engine specs | Quarterly | 1 year |
| Aliases | Continuous (auto-detect) | N/A |
| Applications | Annually | 2 years |

---

## 14. API Data Sources (Cross-Reference)

The Knowledge Base integrates with external APIs for data enrichment. See the respective guides for full documentation:

### 14.1 Industry News APIs (See `industry_news_guide.md`)

| API | Purpose | Environment Variable |
|-----|---------|---------------------|
| **NewsAPI** | Historical news collection (30 days) | `NEWSAPI_API_KEY` |
| **Perplexity** | AI-powered real-time research | `PERPLEXITY_API_KEY` |

### 14.2 Competitor Intelligence APIs (See `competitor_insights_guide.md`)

| API | Purpose | Environment Variable |
|-----|---------|---------------------|
| **EODHD** | SEC financial data for competitors | `EODHD_API_KEY` |
| **NewsAPI** | Competitor news collection | `NEWSAPI_API_KEY` |
| **Perplexity** | Competitor research | `PERPLEXITY_API_KEY` |

### 14.3 KB Enrichment from API Data

**How APIs Feed KB:**

1. **News Articles** → Entity extraction → KB alias matching
2. **Perplexity Research** → Entity mentions → KB entity resolution
3. **Financial Data** → Competitor metrics → KB competitor profiles

**Example: Entity Resolution from News**
```python
from lead_to_cash.services.knowledge_base.integration import get_kb_integration_service

kb = get_kb_integration_service()

# Resolve entity from news article text
match = await kb.resolve_entity("Wärtsilä 31DF engine", "engine_model")
if match.confidence >= 0.8:
    enriched_data = {
        "kb_entity_id": match.entity_id,
        "kb_entity_type": "engine_model",
        "match_confidence": match.confidence,
        "match_type": match.match_type,
    }
```

### 14.4 Required Environment Variables Summary

```bash
# All API keys for full KB enrichment capability
NEWSAPI_API_KEY=your_newsapi_key        # News collection
PERPLEXITY_API_KEY=your_perplexity_key  # AI research
EODHD_API_KEY=your_eodhd_key            # Financial data

# OpenAI for embeddings
OPENAI_API_KEY=your_openai_key          # text-embedding-3-small

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
```

---

## 15. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 3.4 | 2026-01-26 | AI Intelligence Team | Restructured Section 7.5 with "Inside-Out, Risk-First" approach: Phase 1 (Business Context: 7.5.1-7.5.4), Phase 2 (Internal Risk: 7.5.5-7.5.6), Phase 3 (External Risk: 7.5.7-7.5.14); removed duplicate TPRM section |
| 3.3 | 2026-01-26 | AI Intelligence Team | Added Section 7.5.4: SAP Credit Status (SAP CPI/MS5) with integration patterns; renumbered sections 7.5.5-7.5.10 for consistency |
| 3.2 | 2026-01-26 | AI Intelligence Team | Updated Section 7.5.10 TPRM: Fixed TPRMAssessment structure, TPRMStatus enum values, import paths, and example code to match actual implementation |
| 3.1 | 2026-01-26 | AI Intelligence Team | Added Section 7.5.10: Third-Party Risk Management (TPRM) - Aravo integration for supplier due diligence |
| 2.5 | 2026-01-20 | AI Intelligence Team | Added Section 7.6: Due Diligence Terminology Standards - evidence-based language, no positive assertions |
| 2.4 | 2026-01-20 | AI Intelligence Team | Added comprehensive KYP data sources (7.5.1-7.5.8), mandatory reference link requirement |
| 2.3 | 2026-01-20 | AI Intelligence Team | Added Section 7: Risk Intelligence & Partner Due Diligence |
| 2.2 | 2026-01-20 | AI Intelligence Team | Added API Data Sources cross-reference section |
| 2.1 | 2026-01-20 | AI Intelligence Team | Audit fixes: added engine series from seed_data |
| 2.0 | 2026-01-20 | AI Intelligence Team | Full guide with anti-hallucination rules |
| 0.1 | 2026-01-20 | AI Intelligence Team | Initial placeholder |

---

## 16. Related Documents

- `industry_news_guide.md` - Industry news standards (NewsAPI, Perplexity)
- `competitor_insights_guide.md` - Competitive intelligence guide (EODHD, NewsAPI)
- `seed_data.py` - KB seed data definitions
- `source_list.yaml` - Comprehensive source configuration
