-- Migration 004: Performance Curves and Enhanced Engine Data
-- Part of KB Enhancement Phase 2: Schema Improvements
--
-- This migration adds:
-- 1. Performance curve data (power/torque at multiple RPM points)
-- 2. Derating factors for altitude, temperature, humidity
-- 3. RPM range columns to kb_engine_ratings

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'kb_engine_performance_curves') THEN
        RAISE NOTICE 'Migration 004 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Performance Curves Table
    -- Stores power/torque data at multiple RPM points for each engine rating
    -- ========================================================================
    CREATE TABLE kb_engine_performance_curves (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        engine_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,

        -- RPM point for this data
        rpm_point INTEGER NOT NULL CHECK (rpm_point > 0 AND rpm_point <= 3000),

        -- Power at this RPM
        power_kw_at_rpm DECIMAL(10,2) NOT NULL CHECK (power_kw_at_rpm > 0),

        -- Torque at this RPM (optional)
        torque_nm_at_rpm DECIMAL(12,2) CHECK (torque_nm_at_rpm > 0),

        -- Brake Specific Fuel Consumption at this RPM (g/kWh)
        bsfc_g_kwh DECIMAL(8,2) CHECK (bsfc_g_kwh > 0),

        -- Data source for verification
        data_source TEXT DEFAULT 'manufacturer_datasheet',

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        -- Each rating can only have one curve point per RPM
        UNIQUE(engine_rating_id, rpm_point)
    );

    -- Index for fast lookups by engine rating
    CREATE INDEX idx_performance_curves_rating_id
        ON kb_engine_performance_curves(engine_rating_id);

    CREATE INDEX idx_performance_curves_rpm
        ON kb_engine_performance_curves(rpm_point);

    RAISE NOTICE 'Created kb_engine_performance_curves table';

    -- ========================================================================
    -- Derating Factors Table
    -- Stores power derating for various environmental conditions
    -- ========================================================================
    CREATE TABLE kb_engine_derating_factors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        engine_rating_id VARCHAR(36) NOT NULL REFERENCES kb_engine_ratings(id) ON DELETE CASCADE,

        -- Type of condition causing derating
        condition_type TEXT NOT NULL CHECK (condition_type IN (
            'altitude',           -- Meters above sea level
            'ambient_temp',       -- Degrees Celsius above reference
            'humidity',           -- Relative humidity percentage
            'coolant_temp',       -- Coolant temperature above reference
            'fuel_quality',       -- Lower heating value reduction
            'aging'              -- Operating hours
        )),

        -- Value of the condition (e.g., 1000m altitude, 40C ambient)
        condition_value DECIMAL(10,2) NOT NULL,

        -- Power derate percentage (e.g., -5.0 means 5% power reduction)
        power_derate_pct DECIMAL(5,2) NOT NULL,

        -- Data source
        data_source TEXT DEFAULT 'manufacturer_datasheet',

        -- Timestamps
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- Index for fast lookups
    CREATE INDEX idx_derating_factors_rating_id
        ON kb_engine_derating_factors(engine_rating_id);

    CREATE INDEX idx_derating_factors_condition
        ON kb_engine_derating_factors(condition_type);

    RAISE NOTICE 'Created kb_engine_derating_factors table';

    -- ========================================================================
    -- Add RPM Range and BSFC columns to kb_engine_ratings
    -- ========================================================================
    ALTER TABLE kb_engine_ratings
        ADD COLUMN IF NOT EXISTS rpm_min INTEGER CHECK (rpm_min > 0 AND rpm_min <= 3000),
        ADD COLUMN IF NOT EXISTS rpm_max INTEGER CHECK (rpm_max > 0 AND rpm_max <= 3000),
        ADD COLUMN IF NOT EXISTS bsfc_g_kwh DECIMAL(8,2) CHECK (bsfc_g_kwh > 0);

    -- Add constraint to ensure rpm_min <= rpm_max
    ALTER TABLE kb_engine_ratings
        ADD CONSTRAINT chk_rpm_range CHECK (rpm_min IS NULL OR rpm_max IS NULL OR rpm_min <= rpm_max);

    RAISE NOTICE 'Added rpm_min, rpm_max, bsfc_g_kwh columns to kb_engine_ratings';

    -- ========================================================================
    -- Trigger for updated_at
    -- ========================================================================
    CREATE OR REPLACE FUNCTION update_kb_timestamp()
    RETURNS TRIGGER AS $func$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $func$ LANGUAGE plpgsql;

    CREATE TRIGGER trg_performance_curves_updated_at
        BEFORE UPDATE ON kb_engine_performance_curves
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    CREATE TRIGGER trg_derating_factors_updated_at
        BEFORE UPDATE ON kb_engine_derating_factors
        FOR EACH ROW EXECUTE FUNCTION update_kb_timestamp();

    RAISE NOTICE 'Created update triggers';

    RAISE NOTICE 'Migration 004_performance_curves.sql completed successfully';
END $$;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE kb_engine_performance_curves IS
    'Performance curve data: power/torque at multiple RPM points for accurate propeller matching';

COMMENT ON TABLE kb_engine_derating_factors IS
    'Derating factors for environmental conditions (altitude, temperature, humidity, aging)';

COMMENT ON COLUMN kb_engine_ratings.rpm_min IS 'Minimum operating RPM for this rating';
COMMENT ON COLUMN kb_engine_ratings.rpm_max IS 'Maximum operating RPM for this rating';
COMMENT ON COLUMN kb_engine_ratings.bsfc_g_kwh IS 'Brake Specific Fuel Consumption at rated power (g/kWh)';
