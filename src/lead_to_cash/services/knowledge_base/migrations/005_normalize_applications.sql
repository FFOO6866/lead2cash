-- Migration 005: Normalized Applications Schema
-- Part of KB Enhancement Phase 2: Schema Improvements
--
-- This migration adds:
-- 1. Application types reference table with typical RPM/power ranges
-- 2. Rating-to-application mapping with suitability scores
-- 3. Replaces JSONB applications with proper relational model

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'kb_application_types') THEN
        RAISE NOTICE 'Migration 005 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Application Types Reference Table
    -- Defines all valid HIGH-SPEED marine engine applications
    -- ========================================================================
    CREATE TABLE kb_application_types (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- Application identifier (e.g., 'osv', 'ferry', 'tug')
        code TEXT NOT NULL UNIQUE,

        -- Display name
        name TEXT NOT NULL,

        -- Category for grouping
        category TEXT NOT NULL CHECK (category IN (
            'commercial',   -- OSV, ferry, tug, workboat
            'naval',        -- Patrol, naval, coast guard
            'pleasure',     -- Yacht, fast cruiser
            'fishing',      -- Commercial fishing
            'special'       -- Dredger, research, other
        )),

        -- Typical operating parameters for this application
        typical_rpm_min INTEGER CHECK (typical_rpm_min > 0),
        typical_rpm_max INTEGER CHECK (typical_rpm_max > 0),
        typical_power_min_kw INTEGER CHECK (typical_power_min_kw > 0),
        typical_power_max_kw INTEGER CHECK (typical_power_max_kw > 0),

        -- Typical load factor range
        typical_load_factor_min DECIMAL(3,2) CHECK (typical_load_factor_min >= 0 AND typical_load_factor_min <= 1),
        typical_load_factor_max DECIMAL(3,2) CHECK (typical_load_factor_max >= 0 AND typical_load_factor_max <= 1),

        -- Description for matching
        description TEXT,

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    RAISE NOTICE 'Created kb_application_types table';

    -- ========================================================================
    -- Insert HIGH-SPEED application types
    -- ========================================================================
    INSERT INTO kb_application_types (code, name, category, typical_rpm_min, typical_rpm_max, typical_power_min_kw, typical_power_max_kw, typical_load_factor_min, typical_load_factor_max, description)
    VALUES
        -- Commercial applications
        ('osv', 'Offshore Support Vessel', 'commercial', 1200, 1800, 1000, 6000, 0.40, 0.80,
         'Platform supply, anchor handling, and offshore logistics support'),
        ('ferry', 'Ferry', 'commercial', 1200, 2000, 500, 8000, 0.50, 0.85,
         'Passenger and vehicle ferries, regular scheduled routes'),
        ('fast_ferry', 'Fast Ferry', 'commercial', 1800, 2500, 2000, 10000, 0.60, 0.90,
         'High-speed passenger ferries, catamaran, HSC'),
        ('tug', 'Tug', 'commercial', 1200, 1800, 1000, 5000, 0.40, 0.70,
         'Harbor, escort, and ocean towing operations'),
        ('workboat', 'Workboat', 'commercial', 1500, 2100, 300, 2000, 0.30, 0.60,
         'General utility, survey, and service vessels'),
        ('crew_boat', 'Crew Transfer Vessel', 'commercial', 1800, 2300, 500, 2000, 0.50, 0.80,
         'Offshore crew transfer and fast supply'),

        -- Naval/Government applications
        ('patrol', 'Patrol Vessel', 'naval', 1800, 2500, 500, 4000, 0.40, 0.70,
         'Coast guard, customs, and law enforcement'),
        ('naval', 'Naval Vessel', 'naval', 1500, 2500, 2000, 10000, 0.40, 0.80,
         'Military fast attack, corvettes, and support vessels'),

        -- Pleasure applications
        ('yacht', 'Yacht', 'pleasure', 1800, 2500, 300, 3000, 0.20, 0.50,
         'Motor yachts, superyachts, and pleasure craft'),

        -- Fishing applications
        ('fishing', 'Fishing Vessel', 'fishing', 1500, 2100, 300, 2000, 0.40, 0.70,
         'Commercial fishing, trawlers, and purse seiners'),

        -- Special applications
        ('dredger', 'Dredger', 'special', 1200, 1600, 2000, 8000, 0.60, 0.90,
         'Dredging and land reclamation vessels'),
        ('pilot', 'Pilot Boat', 'special', 1800, 2300, 300, 1000, 0.40, 0.60,
         'Harbor pilot transfer vessels');

    RAISE NOTICE 'Inserted 12 application types';

    -- ========================================================================
    -- Rating-to-Application Mapping Table
    -- Links engine ratings to suitable applications with suitability scores
    -- ========================================================================
    CREATE TABLE kb_rating_applications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- Foreign keys
        engine_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,
        application_type_id UUID NOT NULL REFERENCES kb_application_types(id) ON DELETE CASCADE,

        -- Suitability score (0.0-1.0, where 1.0 = ideal match)
        suitability_score DECIMAL(3,2) NOT NULL DEFAULT 0.80
            CHECK (suitability_score >= 0 AND suitability_score <= 1),

        -- Is this the primary intended application?
        is_primary BOOLEAN DEFAULT FALSE,

        -- Notes about specific suitability
        notes TEXT,

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        -- Each rating can only map to each application once
        UNIQUE(engine_rating_id, application_type_id)
    );

    -- Indexes for fast lookups
    CREATE INDEX idx_rating_applications_rating_id
        ON kb_rating_applications(engine_rating_id);

    CREATE INDEX idx_rating_applications_app_id
        ON kb_rating_applications(application_type_id);

    CREATE INDEX idx_rating_applications_primary
        ON kb_rating_applications(is_primary) WHERE is_primary = TRUE;

    RAISE NOTICE 'Created kb_rating_applications table';

    -- ========================================================================
    -- Triggers for updated_at
    -- ========================================================================
    CREATE TRIGGER trg_application_types_updated_at
        BEFORE UPDATE ON kb_application_types
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    CREATE TRIGGER trg_rating_applications_updated_at
        BEFORE UPDATE ON kb_rating_applications
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    RAISE NOTICE 'Created update triggers';

    RAISE NOTICE 'Migration 005_normalize_applications.sql completed successfully';
END $$;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE kb_application_types IS
    'Reference table of HIGH-SPEED marine engine applications with typical operating parameters';

COMMENT ON TABLE kb_rating_applications IS
    'Maps engine ratings to suitable applications with suitability scores (0.0-1.0)';

COMMENT ON COLUMN kb_rating_applications.suitability_score IS
    'How well-suited this engine is for this application (0.0 = poor, 1.0 = ideal)';

COMMENT ON COLUMN kb_rating_applications.is_primary IS
    'TRUE if this is the primary intended application for this engine rating';
