-- Migration 008: OEM Duty Class Mapping (ISO 8528-1:2018 Harmonization)
-- Part of Harmonized Marine Engine Duty Classification System
--
-- This migration adds:
-- 1. Harmonized duty class ENUM type (CON, HVY, MED, LGT, INT, PLS)
-- 2. OEM duty mapping reference table
-- 3. Columns on kb_engine_ratings for harmonized classification
--
-- Reference: ISO 8528-1:2018(E) Third Edition
-- License: Integrum Pte Ltd / SS Foo - Order OP-1014241

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'kb_oem_duty_mappings') THEN
        RAISE NOTICE 'Migration 008 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Create Harmonized Duty Class ENUM Type
    -- ISO 8528-1:2018 aligned 6-tier classification system
    -- ========================================================================
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'harmonized_duty_class') THEN
        CREATE TYPE harmonized_duty_class AS ENUM (
            'CON',  -- Continuous (ISO COP equivalent)
            'HVY',  -- Heavy Duty (ISO PRP high utilization)
            'MED',  -- Medium Duty (ISO PRP standard utilization)
            'LGT',  -- Light Duty (ISO LTP/PRP low utilization)
            'INT',  -- Intermittent (ISO ESP equivalent)
            'PLS'   -- Pleasure (Below ISO ESP threshold)
        );
        RAISE NOTICE 'Created harmonized_duty_class ENUM type';
    END IF;

    -- ========================================================================
    -- Create Source Verification Status ENUM
    -- Track data quality and verification status
    -- ========================================================================
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_verification_status') THEN
        CREATE TYPE source_verification_status AS ENUM (
            'primary_oem',       -- Direct from OEM official documentation
            'secondary_dist',    -- From authorized distributor
            'aggregator',        -- From industry aggregator (needs verification)
            'inferred',          -- Inferred from related data
            'unverified'         -- Not yet verified
        );
        RAISE NOTICE 'Created source_verification_status ENUM type';
    END IF;

    -- ========================================================================
    -- OEM Duty Mapping Reference Table
    -- Maps OEM-specific rating codes to harmonized duty classes
    -- ========================================================================
    CREATE TABLE kb_oem_duty_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- OEM identification
        manufacturer TEXT NOT NULL,
        oem_rating_code TEXT NOT NULL,
        oem_rating_name TEXT,

        -- Harmonized classification
        harmonized_duty_class harmonized_duty_class NOT NULL,

        -- ISO 8528-1:2018 equivalent (for reference)
        iso_equivalent TEXT,

        -- Operating profile attributes
        load_factor_min_pct DECIMAL(5,2),
        load_factor_max_pct DECIMAL(5,2),
        annual_hours_min INTEGER,
        annual_hours_max INTEGER,
        full_power_hours_per_cycle DECIMAL(4,1),
        cycle_hours INTEGER,  -- Denominator (e.g., 12 for "10 of 12 hours")

        -- 10% overload capability per ISO 8528-1:2018 Clause 14.3.3
        overload_pct DECIMAL(4,1) DEFAULT 10.0,
        overload_duration_hours DECIMAL(4,2) DEFAULT 1.0,
        overload_cycle_hours INTEGER DEFAULT 12,

        -- Source verification
        source_verification source_verification_status NOT NULL DEFAULT 'unverified',
        source_document TEXT,
        source_url TEXT,
        source_date DATE,
        verified_by TEXT,
        verified_at TIMESTAMPTZ,

        -- Notes
        notes TEXT,

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        -- Unique constraint: one mapping per OEM rating code
        UNIQUE(manufacturer, oem_rating_code)
    );

    RAISE NOTICE 'Created kb_oem_duty_mappings table';

    -- ========================================================================
    -- Indexes for efficient lookups
    -- ========================================================================
    CREATE INDEX idx_oem_duty_mappings_manufacturer
        ON kb_oem_duty_mappings(manufacturer);

    CREATE INDEX idx_oem_duty_mappings_harmonized_class
        ON kb_oem_duty_mappings(harmonized_duty_class);

    CREATE INDEX idx_oem_duty_mappings_verification
        ON kb_oem_duty_mappings(source_verification)
        WHERE source_verification IN ('primary_oem', 'secondary_dist');

    RAISE NOTICE 'Created indexes for kb_oem_duty_mappings';

    -- ========================================================================
    -- Add columns to kb_engine_ratings
    -- ========================================================================
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'kb_engine_ratings' AND column_name = 'harmonized_duty_class'
    ) THEN
        ALTER TABLE kb_engine_ratings
            ADD COLUMN harmonized_duty_class harmonized_duty_class,
            ADD COLUMN oem_rating_code TEXT;

        RAISE NOTICE 'Added harmonized_duty_class and oem_rating_code columns to kb_engine_ratings';
    END IF;

    -- ========================================================================
    -- Index for harmonized duty class queries
    -- ========================================================================
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_engine_ratings_harmonized_duty'
    ) THEN
        CREATE INDEX idx_engine_ratings_harmonized_duty
            ON kb_engine_ratings(harmonized_duty_class);

        RAISE NOTICE 'Created index on kb_engine_ratings.harmonized_duty_class';
    END IF;

    -- ========================================================================
    -- Trigger for updated_at
    -- ========================================================================
    CREATE TRIGGER trg_oem_duty_mappings_updated_at
        BEFORE UPDATE ON kb_oem_duty_mappings
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    RAISE NOTICE 'Created update trigger for kb_oem_duty_mappings';

    RAISE NOTICE 'Migration 008_oem_duty_mapping.sql completed successfully';
END $$;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TYPE harmonized_duty_class IS
    'ISO 8528-1:2018 aligned 6-tier duty classification: CON (Continuous), HVY (Heavy), MED (Medium), LGT (Light), INT (Intermittent), PLS (Pleasure)';

COMMENT ON TABLE kb_oem_duty_mappings IS
    'Maps OEM-specific duty rating codes to harmonized ISO 8528-1:2018 aligned classifications';

COMMENT ON COLUMN kb_oem_duty_mappings.harmonized_duty_class IS
    'ISO 8528-1:2018 aligned duty class: CON=COP, HVY=PRP(high), MED=PRP(mid), LGT=LTP, INT=ESP, PLS=below ESP';

COMMENT ON COLUMN kb_oem_duty_mappings.iso_equivalent IS
    'ISO 8528-1:2018 equivalent code (COP, PRP, LTP, ESP, DCP, MAX)';

COMMENT ON COLUMN kb_oem_duty_mappings.load_factor_min_pct IS
    'Minimum average load factor percentage for this rating';

COMMENT ON COLUMN kb_oem_duty_mappings.load_factor_max_pct IS
    'Maximum average load factor percentage for this rating';

COMMENT ON COLUMN kb_oem_duty_mappings.overload_pct IS
    'Overload capability per ISO 8528-1:2018 Clause 14.3.3 (typically 10%)';

COMMENT ON COLUMN kb_oem_duty_mappings.source_verification IS
    'Data quality indicator: primary_oem (best), secondary_dist, aggregator, inferred, unverified';

COMMENT ON COLUMN kb_engine_ratings.harmonized_duty_class IS
    'ISO 8528-1:2018 aligned harmonized duty class (derived from OEM rating via kb_oem_duty_mappings)';

COMMENT ON COLUMN kb_engine_ratings.oem_rating_code IS
    'Original OEM rating code (e.g., M93, HD, B) - FK reference to kb_oem_duty_mappings';
