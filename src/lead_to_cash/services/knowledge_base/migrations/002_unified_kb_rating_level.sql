-- Unified Knowledge Base - Rating-Level Product Fit Schema
-- Migration: 002_unified_kb_rating_level.sql
-- ADR: ADR-004 Unified Knowledge Base Architecture
--
-- This migration adds:
-- 1. kb_engine_ratings - Individual duty ratings per engine model (ISO 8528)
-- 2. kb_customer_requirements - Structured customer requirements for fit matching
-- 3. kb_rating_competitor_map - Apple-to-apple rating-level competitor mapping
-- 4. kb_competitor_engagements - Track competitor activity at our customers
-- 5. kb_product_fit_results - Cached product fit scoring results
--
-- Data sources:
-- - ISO 8528 (Generator set performance classifications)
-- - ISO 3046 (Reciprocating internal combustion engines)
-- - IMP Corporation Marine Engine Duty Ratings guide
-- - Manufacturer datasheets (MTU, Cummins, Caterpillar, MAN, etc.)

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

-- Duty class per ISO 8528 and marine industry standards
-- Reference: https://www.impcorporation.com/blog/marine-engine-duty-ratings
DO $$ BEGIN
    CREATE TYPE duty_class_enum AS ENUM (
        'continuous',      -- 80-100% load, 5000-8000 hrs/year, unlimited full power
        'heavy_duty',      -- 40-80% load, 3000-5000 hrs/year, 8 of 10 hrs full power
        'medium_duty',     -- 20-80% load, 2000-4000 hrs/year, 6 of 12 hrs full power
        'light_duty',      -- Up to 50% load, 1000-3000 hrs/year, 2 of 8 hrs full power
        'pleasure',        -- Up to 30% load, 250-1000 hrs/year, 1 of 8 hrs full power
        'intermittent'     -- Variable duty cycles (generator standby, etc.)
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ISO 8528 generator performance classifications
DO $$ BEGIN
    CREATE TYPE iso_classification_enum AS ENUM (
        'iso_8528_cop',    -- Continuous Power: 100% average, 10% overload capability
        'iso_8528_prp',    -- Prime Power: ≤80% average, unlimited time
        'iso_8528_ltp',    -- Limited Time Power: Standby/emergency applications
        'not_applicable'   -- For propulsion (not generator) applications
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Availability status for engine ratings
DO $$ BEGIN
    CREATE TYPE availability_status_enum AS ENUM (
        'available',       -- Currently in production and available
        'field_trial',     -- In field trials, not generally available
        'planned',         -- Announced but not yet available
        'discontinued',    -- No longer in production
        'limited'          -- Limited availability (regional, special order)
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Competitive position assessment
DO $$ BEGIN
    CREATE TYPE competitive_position_enum AS ENUM (
        'strong_advantage',   -- We are clearly better (>10% power density, better specs)
        'advantage',          -- We have an edge
        'parity',            -- Roughly equivalent
        'disadvantage',      -- Competitor has an edge
        'strong_disadvantage' -- Competitor is clearly better
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Threat level for competitor engagements
DO $$ BEGIN
    CREATE TYPE threat_level_enum AS ENUM (
        'critical',    -- Competitor won at our active customer
        'high',        -- Competitor won at our prospect
        'medium',      -- Competitor activity in our market
        'low',         -- Competitor activity outside our focus
        'informational' -- General market intelligence
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Engagement type for competitor activities
DO $$ BEGIN
    CREATE TYPE engagement_type_enum AS ENUM (
        'contract_win',    -- Competitor won a contract
        'proposal',        -- Competitor submitted a proposal
        'demo',            -- Competitor conducting demo/trials
        'partnership',     -- Competitor formed partnership with customer
        'rumored',         -- Unconfirmed activity
        'lost_to_us'       -- We won against this competitor
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Product fit recommendation level
DO $$ BEGIN
    CREATE TYPE fit_recommendation_enum AS ENUM (
        'strong_fit',      -- 90-100% fit score, proceed with confidence
        'good_fit',        -- 75-89% fit score, recommended
        'acceptable',      -- 60-74% fit score, review alternatives
        'marginal',        -- 40-59% fit score, may work with caveats
        'not_suitable'     -- <40% fit score, does not meet requirements
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- =============================================================================
-- ENGINE RATINGS TABLE (The atomic unit for comparison)
-- =============================================================================

-- Individual duty ratings per engine model
-- Example: MAN D3872 has ratings LE427 (920kW), LE432 (1213kW), LE433 (1618kW)
CREATE TABLE IF NOT EXISTS kb_engine_ratings (
    id VARCHAR(36) PRIMARY KEY,
    engine_model_id VARCHAR(36) NOT NULL REFERENCES kb_engine_models(id) ON DELETE CASCADE,

    -- Rating Identity
    rating_designation VARCHAR(100) NOT NULL,  -- e.g., "LE432", "M96", "M93"
    rating_name VARCHAR(255),                   -- Full name if different from designation

    -- ISO/Industry Classification
    duty_class duty_class_enum NOT NULL,
    iso_classification iso_classification_enum DEFAULT 'not_applicable',

    -- Performance at THIS Rating (single values, NOT ranges!)
    power_kw DECIMAL(10,2) NOT NULL,           -- Power output at this rating
    power_hp DECIMAL(10,2),                    -- Horsepower equivalent
    rpm INTEGER NOT NULL,                       -- Operating RPM at this rating

    -- Operating Limits per duty class
    load_factor_min DECIMAL(3,2) DEFAULT 0.00, -- Minimum sustained load (0.0-1.0)
    load_factor_max DECIMAL(3,2) DEFAULT 1.00, -- Maximum sustained load (0.0-1.0)
    full_power_hours_per_cycle INTEGER,         -- e.g., 8 of 10 hours for heavy duty
    cycle_hours INTEGER,                        -- Total cycle hours (e.g., 10 for heavy duty)
    annual_hours_min INTEGER,                   -- Typical minimum hours/year
    annual_hours_max INTEGER,                   -- Typical maximum hours/year

    -- Physical Characteristics at this rating
    dry_weight_kg DECIMAL(10,2),
    length_mm DECIMAL(10,2),
    width_mm DECIMAL(10,2),
    height_mm DECIMAL(10,2),
    power_density_kw_per_kg DECIMAL(6,4),      -- Calculated: power_kw / dry_weight_kg

    -- Fuel and Emissions at this rating
    fuel_types JSONB,                          -- ["diesel", "hvo", "gtl"]
    emission_tier VARCHAR(50),                 -- "IMO Tier II", "IMO Tier III", "EPA Tier 4"
    aftertreatment_required VARCHAR(100),      -- "None", "SCR", "DPF+SCR"
    nox_g_kwh DECIMAL(6,3),                    -- NOx emissions if available
    pm_g_kwh DECIMAL(6,4),                     -- Particulate matter if available

    -- Application Suitability
    application_profiles JSONB,                -- ["ferry", "workboat", "offshore"]
    primary_applications JSONB,                -- Most common applications

    -- Availability
    availability_status availability_status_enum DEFAULT 'available',
    availability_date DATE,                    -- When available (for planned/field_trial)
    regions_available JSONB,                   -- ["APAC", "EMEA", "Americas"]

    -- Data Provenance (CRITICAL: all data must be verifiable)
    data_source VARCHAR(100) NOT NULL,         -- "manufacturer_datasheet", "press_release"
    data_source_url VARCHAR(500),              -- URL to manufacturer source
    data_source_document VARCHAR(255),         -- Document name/reference
    data_confidence DECIMAL(3,2) DEFAULT 0.90, -- 0.0-1.0
    last_verified TIMESTAMP WITH TIME ZONE,    -- When data was last verified
    verified_by VARCHAR(100),                  -- Who verified the data

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique rating per model
    UNIQUE(engine_model_id, rating_designation)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_model ON kb_engine_ratings(engine_model_id);
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_duty ON kb_engine_ratings(duty_class);
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_power ON kb_engine_ratings(power_kw);
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_rpm ON kb_engine_ratings(rpm);
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_available ON kb_engine_ratings(availability_status)
    WHERE availability_status = 'available';
-- Composite index for power+duty queries (most common fit matching pattern)
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_power_duty ON kb_engine_ratings(power_kw, duty_class);
-- Index for emission tier filtering
CREATE INDEX IF NOT EXISTS idx_kb_engine_ratings_emission ON kb_engine_ratings(emission_tier);


-- =============================================================================
-- CUSTOMER REQUIREMENTS TABLE
-- =============================================================================

-- Structured customer requirements for product fit matching
CREATE TABLE IF NOT EXISTS kb_customer_requirements (
    id VARCHAR(36) PRIMARY KEY,

    -- Customer Identity (links to SAP/CRM)
    customer_id VARCHAR(50),                   -- SAP customer number (KUNNR)
    customer_name VARCHAR(255) NOT NULL,       -- Customer name for matching
    opportunity_id VARCHAR(50),                -- CEC opportunity ID
    project_name VARCHAR(255),                 -- Project/vessel name

    -- Power Requirements
    power_required_kw DECIMAL(10,2) NOT NULL,  -- Required power output
    power_tolerance_pct DECIMAL(5,2) DEFAULT 15.00, -- Acceptable tolerance %
    power_configuration VARCHAR(50),           -- "single", "twin", "triple", "quad"
    total_installed_power_kw DECIMAL(10,2),    -- If multiple engines

    -- Operating Profile (maps to duty class)
    duty_class_required duty_class_enum,       -- Required duty class
    annual_operating_hours INTEGER,            -- Expected hours/year
    typical_load_factor DECIMAL(3,2),          -- Expected average load
    peak_load_duration_hours INTEGER,          -- How long at peak load

    -- Vessel/Application Context
    vessel_type VARCHAR(100),                  -- Ferry, tug, OSV, yacht, etc.
    vessel_name VARCHAR(255),                  -- Specific vessel name if known
    vessel_length_m DECIMAL(8,2),              -- Vessel length
    vessel_beam_m DECIMAL(8,2),                -- Vessel beam
    application VARCHAR(50),                   -- Propulsion, genset, auxiliary
    new_build_or_repower VARCHAR(20),          -- "new_build", "repower", "retrofit"

    -- Environmental Requirements
    emission_tier_required VARCHAR(50),        -- "IMO Tier II", "IMO Tier III"
    eca_operation BOOLEAN DEFAULT FALSE,       -- Will operate in Emission Control Area
    alternative_fuel_required BOOLEAN DEFAULT FALSE,

    -- Fuel Preferences
    fuel_type_preference JSONB,                -- ["diesel", "lng", "methanol"]
    fuel_type_mandatory JSONB,                 -- Must-have fuel types

    -- Physical Constraints
    max_engine_weight_kg DECIMAL(10,2),        -- Weight limit per engine
    max_engine_length_mm DECIMAL(10,2),        -- Length limit
    max_engine_width_mm DECIMAL(10,2),         -- Width limit
    max_engine_height_mm DECIMAL(10,2),        -- Height limit
    engine_room_constraints TEXT,              -- Free text constraints

    -- Commercial Context
    budget_level VARCHAR(50),                  -- "premium", "mid_range", "value"
    decision_timeline VARCHAR(50),             -- "immediate", "3_months", "6_months", "12_months"
    competitor_under_consideration JSONB,      -- ["caterpillar", "cummins"]

    -- Geographic Context
    region VARCHAR(100),                       -- APAC, EMEA, Americas
    country VARCHAR(100),
    port_of_registry VARCHAR(100),
    flag_state VARCHAR(100),
    classification_society VARCHAR(100),       -- DNV, Lloyd's, ABS, etc.

    -- Status
    status VARCHAR(50) DEFAULT 'active',       -- active, won, lost, dormant
    fit_analysis_completed BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_by VARCHAR(100),                   -- Agent or user who created
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_customer ON kb_customer_requirements(customer_id);
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_opportunity ON kb_customer_requirements(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_power ON kb_customer_requirements(power_required_kw);
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_duty ON kb_customer_requirements(duty_class_required);
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_vessel ON kb_customer_requirements(vessel_type);
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_status ON kb_customer_requirements(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_kb_customer_req_region ON kb_customer_requirements(region);


-- =============================================================================
-- RATING COMPETITOR MAP TABLE (Apple-to-Apple Comparison)
-- =============================================================================

-- Maps OUR engine ratings to competitor engine ratings at the same duty class
CREATE TABLE IF NOT EXISTS kb_rating_competitor_map (
    id VARCHAR(36) PRIMARY KEY,

    -- Our rating (must be RRPS: MTU or Bergen)
    our_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,

    -- Competitor rating
    competitor_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,

    -- Comparison Metrics
    power_delta_kw DECIMAL(10,2),              -- Competitor - Ours (positive = they have more)
    power_delta_pct DECIMAL(6,2),              -- Percentage difference
    power_density_delta DECIMAL(6,4),          -- Their kW/kg - Our kW/kg
    rpm_delta INTEGER,                         -- Their RPM - Our RPM
    weight_delta_kg DECIMAL(10,2),             -- Their weight - Our weight

    -- Competitive Assessment
    competitive_position competitive_position_enum,
    price_positioning VARCHAR(50),             -- "premium", "parity", "value"

    -- Where They Compete
    overlapping_applications JSONB,            -- ["ferry", "osv"]
    overlapping_regions JSONB,                 -- ["APAC", "EMEA"]
    overlapping_duty_classes JSONB,            -- ["medium_duty", "heavy_duty"]

    -- Threat Assessment
    threat_level threat_level_enum DEFAULT 'medium',
    win_rate_against_pct DECIMAL(5,2),         -- Our win rate against this competitor rating

    -- Analysis
    our_advantages JSONB,                      -- ["power_density", "fuel_options"]
    their_advantages JSONB,                    -- ["price", "service_network"]
    key_differentiators TEXT,
    recommended_positioning TEXT,              -- How to position against them

    -- Data Quality
    last_competitive_review DATE,
    reviewed_by VARCHAR(100),

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one mapping per pair
    UNIQUE(our_rating_id, competitor_rating_id),
    -- Prevent self-comparison
    CHECK(our_rating_id != competitor_rating_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_rating_comp_our ON kb_rating_competitor_map(our_rating_id);
CREATE INDEX IF NOT EXISTS idx_kb_rating_comp_competitor ON kb_rating_competitor_map(competitor_rating_id);
CREATE INDEX IF NOT EXISTS idx_kb_rating_comp_threat ON kb_rating_competitor_map(threat_level);
CREATE INDEX IF NOT EXISTS idx_kb_rating_comp_position ON kb_rating_competitor_map(competitive_position);


-- =============================================================================
-- COMPETITOR ENGAGEMENTS TABLE
-- =============================================================================

-- Track competitor activity at our customers (links intel to CRM)
CREATE TABLE IF NOT EXISTS kb_competitor_engagements (
    id VARCHAR(36) PRIMARY KEY,

    -- Customer Identity (links to SAP)
    customer_id VARCHAR(50),                   -- SAP customer number (if known)
    customer_name VARCHAR(255) NOT NULL,       -- Customer name (always required)
    is_our_customer BOOLEAN DEFAULT FALSE,     -- TRUE if in our SAP
    customer_relationship VARCHAR(50),         -- "active", "prospect", "former", "unknown"

    -- Competitor Info
    competitor VARCHAR(100) NOT NULL,          -- "caterpillar", "cummins", "man"
    competitor_rating_id VARCHAR(36) REFERENCES kb_engine_ratings(id), -- FK if we know the engine
    competitor_engine_name VARCHAR(255),       -- Engine name if rating not in KB

    -- Engagement Details
    engagement_type engagement_type_enum NOT NULL,
    engagement_date DATE,
    engagement_value_usd DECIMAL(15,2),        -- Deal value if disclosed
    vessel_name VARCHAR(255),
    vessel_type VARCHAR(100),
    quantity INTEGER DEFAULT 1,                -- Number of engines

    -- Source Intelligence
    source_signal_id VARCHAR(36),              -- FK to competitor_signals table
    source_type VARCHAR(50),                   -- "press_release", "trade_news", "field_intel"
    source_url VARCHAR(500),
    source_confidence DECIMAL(3,2),            -- 0.0-1.0

    -- Impact Analysis
    our_competing_rating_id VARCHAR(36) REFERENCES kb_engine_ratings(id), -- Which of ours competed
    our_engine_name VARCHAR(255),              -- If rating not in KB
    loss_reason TEXT,                          -- Why we lost (if known)

    -- Threat Assessment
    threat_level threat_level_enum NOT NULL,
    threat_reason TEXT,

    -- Required Actions
    requires_sales_action BOOLEAN DEFAULT FALSE,
    action_recommendation TEXT,
    action_due_date DATE,

    -- Notifications
    sales_rep_notified BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMP WITH TIME ZONE,
    notified_to VARCHAR(255),                  -- Email or name

    -- Resolution
    resolution_status VARCHAR(50) DEFAULT 'open', -- "open", "acknowledged", "actioned", "closed"
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,

    -- Geographic Context
    region VARCHAR(100),
    country VARCHAR(100),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_customer ON kb_competitor_engagements(customer_id);
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_customer_name ON kb_competitor_engagements(customer_name);
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_competitor ON kb_competitor_engagements(competitor);
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_threat ON kb_competitor_engagements(threat_level);
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_date ON kb_competitor_engagements(engagement_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_action ON kb_competitor_engagements(requires_sales_action)
    WHERE requires_sales_action = TRUE;
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_resolution ON kb_competitor_engagements(resolution_status)
    WHERE resolution_status = 'open';
CREATE INDEX IF NOT EXISTS idx_kb_comp_engage_our_customer ON kb_competitor_engagements(is_our_customer)
    WHERE is_our_customer = TRUE;


-- =============================================================================
-- PRODUCT FIT RESULTS TABLE (Cached scoring results)
-- =============================================================================

-- Cache product fit scoring results for performance
CREATE TABLE IF NOT EXISTS kb_product_fit_results (
    id VARCHAR(36) PRIMARY KEY,

    -- Links
    requirement_id VARCHAR(36) NOT NULL REFERENCES kb_customer_requirements(id) ON DELETE CASCADE,
    engine_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,

    -- Overall Fit Score (0-100)
    overall_fit_score DECIMAL(5,2) NOT NULL,
    fit_recommendation fit_recommendation_enum NOT NULL,

    -- Component Scores (0-100 each)
    power_fit_score DECIMAL(5,2),              -- How well power matches
    power_fit_detail TEXT,                     -- "1213 kW vs 1200 kW required (+1%)"

    duty_fit_score DECIMAL(5,2),               -- Does duty class match
    duty_fit_detail TEXT,                      -- "Medium duty matches medium duty requirement"

    emission_fit_score DECIMAL(5,2),           -- Emission tier compliance
    emission_fit_detail TEXT,                  -- "IMO Tier III meets requirement"

    application_fit_score DECIMAL(5,2),        -- Application suitability
    application_fit_detail TEXT,               -- "Proven in ferry applications"

    physical_fit_score DECIMAL(5,2),           -- Weight/size constraints
    physical_fit_detail TEXT,                  -- "2720 kg under 3000 kg limit"

    fuel_fit_score DECIMAL(5,2),               -- Fuel compatibility
    fuel_fit_detail TEXT,                      -- "Diesel, HVO supported"

    -- Fit Factors (for explanation)
    positive_factors JSONB,                    -- Reasons it's a good fit
    negative_factors JSONB,                    -- Reasons it's not ideal
    gap_factors JSONB,                         -- What's missing

    -- Ranking
    rank_for_requirement INTEGER,              -- 1 = best fit, 2 = second best, etc.

    -- Alternatives
    alternative_ratings JSONB,                 -- Other ratings to consider

    -- Scoring Metadata
    scoring_algorithm_version VARCHAR(20) DEFAULT 'v1',
    scored_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one result per requirement-rating pair
    UNIQUE(requirement_id, engine_rating_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kb_fit_results_requirement ON kb_product_fit_results(requirement_id);
CREATE INDEX IF NOT EXISTS idx_kb_fit_results_rating ON kb_product_fit_results(engine_rating_id);
CREATE INDEX IF NOT EXISTS idx_kb_fit_results_score ON kb_product_fit_results(overall_fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_kb_fit_results_recommendation ON kb_product_fit_results(fit_recommendation);
CREATE INDEX IF NOT EXISTS idx_kb_fit_results_rank ON kb_product_fit_results(requirement_id, rank_for_requirement);


-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Apply updated_at trigger to new tables
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN VALUES
        ('kb_engine_ratings'),
        ('kb_customer_requirements'),
        ('kb_rating_competitor_map'),
        ('kb_competitor_engagements'),
        ('kb_product_fit_results')
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_updated_at ON %I;
            CREATE TRIGGER update_%I_updated_at
            BEFORE UPDATE ON %I
            FOR EACH ROW EXECUTE FUNCTION update_kb_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;


-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE kb_engine_ratings IS 'Individual duty ratings per engine model (ISO 8528). The atomic unit for product comparison.';
COMMENT ON TABLE kb_customer_requirements IS 'Structured customer requirements for deterministic product fit matching.';
COMMENT ON TABLE kb_rating_competitor_map IS 'Apple-to-apple rating-level competitive mapping between our engines and competitors.';
COMMENT ON TABLE kb_competitor_engagements IS 'Track competitor activity at our customers, linked to SAP customer data.';
COMMENT ON TABLE kb_product_fit_results IS 'Cached product fit scoring results for performance and audit trail.';

COMMENT ON COLUMN kb_engine_ratings.duty_class IS 'ISO 8528/marine industry duty classification: continuous, heavy_duty, medium_duty, light_duty, pleasure, intermittent';
COMMENT ON COLUMN kb_engine_ratings.data_source_url IS 'CRITICAL: URL to manufacturer source. All data must be verifiable.';
COMMENT ON COLUMN kb_customer_requirements.duty_class_required IS 'Maps to engine duty_class for matching';
COMMENT ON COLUMN kb_rating_competitor_map.competitive_position IS 'Our position relative to this competitor rating';
COMMENT ON COLUMN kb_competitor_engagements.is_our_customer IS 'TRUE if customer exists in SAP (matched via customer_id)';


-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 002_unified_kb_rating_level.sql completed successfully';
    RAISE NOTICE 'Created tables: kb_engine_ratings, kb_customer_requirements, kb_rating_competitor_map, kb_competitor_engagements, kb_product_fit_results';
    RAISE NOTICE 'Created enums: duty_class_enum, iso_classification_enum, availability_status_enum, competitive_position_enum, threat_level_enum, engagement_type_enum, fit_recommendation_enum';
END $$;
