-- =============================================================================
-- Migration 001b: Add Unique Constraints for ON CONFLICT Support
-- =============================================================================
-- This migration adds UNIQUE constraints required by the seed SQL (003)
-- Run AFTER 001_create_kb_tables.sql
--
-- ROLLBACK:
-- ALTER TABLE kb_manufacturers DROP CONSTRAINT IF EXISTS kb_manufacturers_name_key;
-- ALTER TABLE kb_engine_series DROP CONSTRAINT IF EXISTS kb_engine_series_mfr_name_key;
-- ALTER TABLE kb_engine_models DROP CONSTRAINT IF EXISTS kb_engine_models_name_key;
-- =============================================================================

-- Add unique constraint on manufacturer name
ALTER TABLE kb_manufacturers
ADD CONSTRAINT kb_manufacturers_name_key UNIQUE (name);

-- Add unique constraint on engine series (per manufacturer)
ALTER TABLE kb_engine_series
ADD CONSTRAINT kb_engine_series_mfr_name_key UNIQUE (manufacturer_id, series_name);

-- Add unique constraint on engine model name
ALTER TABLE kb_engine_models
ADD CONSTRAINT kb_engine_models_name_key UNIQUE (model_name);

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Migration 001b completed: Added unique constraints for ON CONFLICT support';
END $$;
