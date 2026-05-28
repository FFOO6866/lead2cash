# ADR-004: Unified Knowledge Base Architecture with Rating-Level Product Fit

**Status:** Accepted
**Date:** 2026-01-21
**Deciders:** Product Team, Engineering Team
**Consulted:** Sales Operations, RRPS APAC Team
**Informed:** All AI Agents, Integration Teams

## Context

The current Knowledge Base (KB) implementation has critical architectural issues that prevent it from delivering on its stated business outcomes:

1. **Two Separate KBs**: Medium-speed engines (PostgreSQL via `models.py`) and high-speed engines (in-memory via `product_data.py`) exist as separate sources of truth.

2. **Model-Level Data Instead of Rating-Level**: Engine comparisons are made at the model level (e.g., "MAN D3872" vs "MTU Series 2000") rather than at the rating level (e.g., "MAN D3872 LE432 @ 1,213 kW" vs "MTU 12V 2000 M96 @ 1,432 kW").

3. **No Customer Requirements Model**: Customer requirements are reconstructed from free text each time rather than stored as structured data.

4. **No Product Fit Scoring Algorithm**: Despite having scoring for articles, there's no deterministic algorithm for scoring engine-to-requirement fit.

5. **No Competitor-at-Customer Tracking**: When competitor intel detects activity at a customer, there's no structured way to link this to our CRM customers or track the competitive threat.

### Business Outcomes Blocked

| Outcome | Current State | Impact |
|---------|---------------|--------|
| Analyze customer requirements | No structured model | Agents reconstruct from free text every time |
| Determine product fit | No fit algorithm | Cannot rank engines for a customer |
| Infer competitor @ our customers | No CRM link | Cannot alert sales to threats |

## Decision Drivers

* **Single Source of Truth**: All engines (high-speed and medium-speed) must be in one database
* **Apple-to-Apple Comparison**: Comparisons must be at rating level, not model level (per ISO 8528/ISO 3046)
* **Industry Standards**: Duty classifications must follow marine engine industry standards (Continuous, Heavy, Medium, Light, Pleasure)
* **Production Ready**: No mocks, no hardcoded data, all data from manufacturer sources
* **Agent Integration**: All AI agents must query the same KB with consistent results

## Considered Options

### Option 1: Patch Existing Schema (Add columns to kb_engine_models)

Add power_rating_1_kw, power_rating_2_kw, etc. columns to existing table.

* Bad, because schema becomes denormalized
* Bad, because different engines have different numbers of ratings
* Bad, because doesn't solve the two-KB problem

### Option 2: New EngineRating Table (Chosen)

Add a new `kb_engine_ratings` table that stores individual duty ratings, plus new tables for CustomerRequirement and CompetitorEngagement.

* Good, because properly normalized (one row per rating)
* Good, because supports unlimited ratings per model
* Good, because allows rating-level competitor mapping
* Good, because migrates product_data.py into same DB

### Option 3: GraphDB for Flexible Relationships

Use Neo4j or similar for flexible engine-rating-competitor relationships.

* Good, because very flexible schema
* Bad, because adds operational complexity
* Bad, because team not experienced with graph DBs
* Bad, because existing infrastructure is PostgreSQL

## Decision Outcome

Chosen option: **Option 2 - New EngineRating Table**, because it provides proper normalization while staying within our PostgreSQL infrastructure.

### New Schema Components

#### 1. DutyClass Enum (ISO Standard)

Based on [ISO 8528](https://www.iso.org/standard/81529.html) and [marine industry standards](https://www.impcorporation.com/blog/marine-engine-duty-ratings):

```python
class DutyClass(str, Enum):
    CONTINUOUS = "continuous"      # 80-100% load, 5000-8000 hrs/year
    HEAVY_DUTY = "heavy_duty"      # 40-80% load, 3000-5000 hrs/year
    MEDIUM_DUTY = "medium_duty"    # 20-80% load, 2000-4000 hrs/year
    LIGHT_DUTY = "light_duty"      # Up to 50% load, 1000-3000 hrs/year
    PLEASURE = "pleasure"          # Up to 30% load, 250-1000 hrs/year
    INTERMITTENT = "intermittent"  # Variable duty cycles
```

#### 2. EngineRating Table

The atomic unit for product comparison:

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key |
| engine_model_id | VARCHAR(36) | FK to kb_engine_models |
| rating_designation | VARCHAR(50) | e.g., "LE432", "M96", "M93" |
| duty_class | VARCHAR(50) | DutyClass enum value |
| power_kw | DECIMAL | Power at this rating (single value) |
| rpm | INTEGER | RPM at this rating (single value) |
| load_factor_min | DECIMAL | Minimum sustained load |
| load_factor_max | DECIMAL | Maximum sustained load |
| annual_hours_min | INTEGER | Typical minimum hours/year |
| annual_hours_max | INTEGER | Typical maximum hours/year |
| application_profiles | JSONB | Suitable applications |
| availability_status | VARCHAR(50) | available, field_trial, planned |
| data_source_url | VARCHAR(500) | Manufacturer source URL |
| last_verified | TIMESTAMP | When data was verified |

#### 3. CustomerRequirement Table

Structured customer requirements for fit matching:

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key |
| customer_id | VARCHAR(50) | SAP customer number (optional) |
| customer_name | VARCHAR(255) | Customer name for matching |
| opportunity_id | VARCHAR(50) | CEC opportunity ID (optional) |
| power_required_kw | DECIMAL | Required power output |
| power_tolerance_pct | DECIMAL | Acceptable tolerance (default 15%) |
| duty_class_required | VARCHAR(50) | Required duty class |
| annual_operating_hours | INTEGER | Expected annual hours |
| vessel_type | VARCHAR(100) | Ferry, tug, OSV, etc. |
| application | VARCHAR(50) | Propulsion, genset, auxiliary |
| emission_tier_required | VARCHAR(50) | IMO Tier II/III, EPA Tier 4 |
| fuel_type_preference | JSONB | Preferred fuel types |
| max_weight_kg | DECIMAL | Weight constraint (optional) |
| max_length_mm | DECIMAL | Length constraint (optional) |
| region | VARCHAR(100) | Geographic region |
| created_by | VARCHAR(100) | Agent or user who created |

#### 4. RatingCompetitorMap Table

Apple-to-apple competitor mapping:

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key |
| our_rating_id | VARCHAR(36) | FK to our EngineRating |
| competitor_rating_id | VARCHAR(36) | FK to competitor EngineRating |
| power_delta_kw | DECIMAL | Competitor - Ours |
| power_delta_pct | DECIMAL | Percentage difference |
| competitive_position | VARCHAR(50) | advantage, parity, disadvantage |
| overlapping_applications | JSONB | Where they compete |
| threat_level | VARCHAR(50) | high, medium, low |
| notes | TEXT | Competitive notes |

#### 5. CompetitorEngagement Table

Track competitor activity at our customers:

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR(36) | Primary key |
| customer_id | VARCHAR(50) | SAP customer number |
| customer_name | VARCHAR(255) | Customer name |
| competitor | VARCHAR(100) | Competitor name |
| competitor_rating_id | VARCHAR(36) | FK to EngineRating (optional) |
| engagement_type | VARCHAR(50) | contract_win, proposal, demo |
| engagement_date | DATE | When it happened |
| source_signal_id | VARCHAR(36) | FK to competitor_signals |
| our_competing_rating_id | VARCHAR(36) | Which of our engines lost |
| estimated_value_usd | DECIMAL | Deal value if known |
| threat_level | VARCHAR(50) | critical, high, medium, low |
| requires_sales_action | BOOLEAN | Needs immediate attention |
| sales_rep_notified | BOOLEAN | Has sales been alerted |

### Positive Consequences

* Single source of truth for all engines
* Proper rating-level comparisons (apple-to-apple)
* Structured customer requirements enable automated fit scoring
* Competitor engagements linked to CRM customers
* All data verifiable against manufacturer sources

### Negative Consequences

* Migration required from product_data.py
* Existing code using product_data.py needs refactoring
* More complex schema to maintain

## Implementation Plan

### Phase 1: Foundation (Migration 002)

1. Create DutyClass enum
2. Create kb_engine_ratings table
3. Create kb_customer_requirements table
4. Create kb_rating_competitor_map table
5. Create kb_competitor_engagements table

### Phase 2: Data Migration

1. Migrate all product_data.py engines to kb_engine_models + kb_engine_ratings
2. Verify all data against manufacturer sources
3. Populate rating-level competitor mappings

### Phase 3: Services

1. Implement ProductFitScoring service
2. Implement RatingCompetitorService
3. Implement CompetitorEngagementService

### Phase 4: Agent Integration

1. Update KnowledgeBaseAgent (ProductFitAgent) to use new schema
2. Create product fit scoring endpoints
3. Create competitor threat alerting

## Links

* [ADR-003: A2A Agent Architecture](003-a2a-agent-architecture.md)
* [ISO 8528 Standard](https://www.iso.org/standard/81529.html)
* [Marine Engine Duty Ratings](https://www.impcorporation.com/blog/marine-engine-duty-ratings)
* [Product Fit Guide](../docs/guides/product_fit_guide.md)

---

*This ADR establishes the unified knowledge base architecture for the RRPS Lead-to-Cash platform.*
