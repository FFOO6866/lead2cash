-- Supplementary Migration: Add Check Constraints
-- Migration: 002b_add_constraints.sql
-- Run AFTER 002_unified_kb_rating_level.sql
--
-- Adds validation constraints to ensure data quality:
-- - Power values must be positive
-- - Load factors must be in valid range (0-100%)
-- - Annual hours must be positive
-- - Confidence values must be 0-1
-- - Physical dimensions must be positive when specified

-- =============================================================================
-- ROLLBACK: To remove all constraints added by this migration
-- =============================================================================
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_power_kw_positive;
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_rpm_positive;
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_load_factor_range;
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_annual_hours_range;
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_data_confidence_range;
-- ALTER TABLE kb_engine_ratings DROP CONSTRAINT IF EXISTS chk_physical_positive;
-- ALTER TABLE kb_customer_requirements DROP CONSTRAINT IF EXISTS chk_customer_power_positive;
-- ALTER TABLE kb_customer_requirements DROP CONSTRAINT IF EXISTS chk_tolerance_range;
-- ALTER TABLE kb_customer_requirements DROP CONSTRAINT IF EXISTS chk_load_factor_valid;
-- ALTER TABLE kb_product_fit_results DROP CONSTRAINT IF EXISTS chk_scores_valid;

-- =============================================================================
-- ENGINE RATINGS CONSTRAINTS
-- =============================================================================

-- Power must be positive
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_power_kw_positive
CHECK (power_kw > 0);

-- RPM must be positive
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_rpm_positive
CHECK (rpm > 0);

-- Load factor must be in valid range (stored as 0-100 percentage)
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_load_factor_range
CHECK (
    (load_factor_min IS NULL OR load_factor_min >= 0)
    AND (load_factor_max IS NULL OR load_factor_max <= 100)
    AND (load_factor_min IS NULL OR load_factor_max IS NULL OR load_factor_min <= load_factor_max)
);

-- Annual hours must be valid range
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_annual_hours_range
CHECK (
    (annual_hours_min IS NULL OR annual_hours_min >= 0)
    AND (annual_hours_max IS NULL OR annual_hours_max <= 10000)
    AND (annual_hours_min IS NULL OR annual_hours_max IS NULL OR annual_hours_min <= annual_hours_max)
);

-- Data confidence must be 0-1
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_data_confidence_range
CHECK (data_confidence >= 0 AND data_confidence <= 1);

-- Physical dimensions must be positive when specified
ALTER TABLE kb_engine_ratings
ADD CONSTRAINT chk_physical_positive
CHECK (
    (dry_weight_kg IS NULL OR dry_weight_kg > 0)
    AND (length_mm IS NULL OR length_mm > 0)
    AND (width_mm IS NULL OR width_mm > 0)
    AND (height_mm IS NULL OR height_mm > 0)
);


-- =============================================================================
-- CUSTOMER REQUIREMENTS CONSTRAINTS
-- =============================================================================

-- Required power must be positive
ALTER TABLE kb_customer_requirements
ADD CONSTRAINT chk_customer_power_positive
CHECK (power_required_kw > 0);

-- Tolerance must be reasonable (0-100%)
ALTER TABLE kb_customer_requirements
ADD CONSTRAINT chk_tolerance_range
CHECK (power_tolerance_pct IS NULL OR (power_tolerance_pct >= 0 AND power_tolerance_pct <= 100));

-- Load factor must be 0-1
ALTER TABLE kb_customer_requirements
ADD CONSTRAINT chk_load_factor_valid
CHECK (typical_load_factor IS NULL OR (typical_load_factor >= 0 AND typical_load_factor <= 1));


-- =============================================================================
-- PRODUCT FIT RESULTS CONSTRAINTS
-- =============================================================================

-- All scores must be 0-100
ALTER TABLE kb_product_fit_results
ADD CONSTRAINT chk_scores_valid
CHECK (
    overall_fit_score >= 0 AND overall_fit_score <= 100
    AND (power_fit_score IS NULL OR (power_fit_score >= 0 AND power_fit_score <= 100))
    AND (duty_fit_score IS NULL OR (duty_fit_score >= 0 AND duty_fit_score <= 100))
    AND (emission_fit_score IS NULL OR (emission_fit_score >= 0 AND emission_fit_score <= 100))
    AND (application_fit_score IS NULL OR (application_fit_score >= 0 AND application_fit_score <= 100))
    AND (physical_fit_score IS NULL OR (physical_fit_score >= 0 AND physical_fit_score <= 100))
    AND (fuel_fit_score IS NULL OR (fuel_fit_score >= 0 AND fuel_fit_score <= 100))
);


-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON CONSTRAINT chk_power_kw_positive ON kb_engine_ratings IS
'Engine power output must be a positive value';

COMMENT ON CONSTRAINT chk_load_factor_range ON kb_engine_ratings IS
'Load factor percentage must be between 0 and 100, with min <= max';

COMMENT ON CONSTRAINT chk_annual_hours_range ON kb_engine_ratings IS
'Annual operating hours must be non-negative and reasonable (max 10000), with min <= max';

COMMENT ON CONSTRAINT chk_data_confidence_range ON kb_engine_ratings IS
'Data confidence must be a value between 0.0 (no confidence) and 1.0 (fully verified)';

COMMENT ON CONSTRAINT chk_physical_positive ON kb_engine_ratings IS
'Physical dimensions (weight, length, width, height) must be positive when specified';

COMMENT ON CONSTRAINT chk_customer_power_positive ON kb_customer_requirements IS
'Customer required power must be a positive value';

COMMENT ON CONSTRAINT chk_tolerance_range ON kb_customer_requirements IS
'Power tolerance percentage must be between 0% and 100%';

COMMENT ON CONSTRAINT chk_scores_valid ON kb_product_fit_results IS
'All fit scores must be between 0 and 100 percent';
