-- Migration 011: Embedding Model Versioning
-- Adds version tracking to embedding columns for model upgrade support
--
-- This migration adds:
-- 1. embedding_model VARCHAR(50) - Tracks which model generated the embedding
-- 2. embedding_updated_at TIMESTAMPTZ - Tracks when embedding was last updated
--
-- Purpose:
-- - Enables detection of stale embeddings when upgrading models
-- - Provides migration path from text-embedding-3-small to future models
-- - Supports incremental re-embedding of outdated vectors
--
-- Affected tables:
-- - kb_manufacturers (name_embedding)
-- - kb_engine_models (model_embedding)
-- - kb_entity_aliases (embedding)
--
-- Reference: OpenAI Embeddings API versioning
-- License: Integrum Pte Ltd / SS Foo

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'kb_manufacturers'
        AND column_name = 'embedding_model'
    ) THEN
        RAISE NOTICE 'Migration 011 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Add versioning columns to kb_manufacturers
    -- ========================================================================
    ALTER TABLE kb_manufacturers
        ADD COLUMN embedding_model VARCHAR(50),
        ADD COLUMN embedding_updated_at TIMESTAMPTZ;

    -- Backfill existing embeddings with current model version
    UPDATE kb_manufacturers
    SET embedding_model = 'text-embedding-3-small',
        embedding_updated_at = updated_at
    WHERE name_embedding IS NOT NULL;

    RAISE NOTICE 'Added versioning columns to kb_manufacturers';

    -- ========================================================================
    -- Add versioning columns to kb_engine_models
    -- ========================================================================
    ALTER TABLE kb_engine_models
        ADD COLUMN embedding_model VARCHAR(50),
        ADD COLUMN embedding_updated_at TIMESTAMPTZ;

    -- Backfill existing embeddings
    UPDATE kb_engine_models
    SET embedding_model = 'text-embedding-3-small',
        embedding_updated_at = updated_at
    WHERE model_embedding IS NOT NULL;

    RAISE NOTICE 'Added versioning columns to kb_engine_models';

    -- ========================================================================
    -- Add versioning columns to kb_entity_aliases
    -- ========================================================================
    ALTER TABLE kb_entity_aliases
        ADD COLUMN embedding_model VARCHAR(50),
        ADD COLUMN embedding_updated_at TIMESTAMPTZ;

    -- Backfill existing embeddings
    UPDATE kb_entity_aliases
    SET embedding_model = 'text-embedding-3-small',
        embedding_updated_at = updated_at
    WHERE embedding IS NOT NULL;

    RAISE NOTICE 'Added versioning columns to kb_entity_aliases';

    -- ========================================================================
    -- Create indexes for stale embedding detection
    -- These enable efficient queries to find embeddings using outdated models
    -- ========================================================================
    CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_embedding_model
        ON kb_manufacturers(embedding_model)
        WHERE name_embedding IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_kb_engine_models_embedding_model
        ON kb_engine_models(embedding_model)
        WHERE model_embedding IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_embedding_model
        ON kb_entity_aliases(embedding_model)
        WHERE embedding IS NOT NULL;

    RAISE NOTICE 'Created indexes for stale embedding detection';

    -- ========================================================================
    -- Add column comments for documentation
    -- ========================================================================
    COMMENT ON COLUMN kb_manufacturers.embedding_model IS
        'OpenAI embedding model used (e.g., text-embedding-3-small). NULL means pre-versioning embedding.';
    COMMENT ON COLUMN kb_manufacturers.embedding_updated_at IS
        'Timestamp when embedding was last regenerated. Used for staleness detection.';

    COMMENT ON COLUMN kb_engine_models.embedding_model IS
        'OpenAI embedding model used (e.g., text-embedding-3-small). NULL means pre-versioning embedding.';
    COMMENT ON COLUMN kb_engine_models.embedding_updated_at IS
        'Timestamp when embedding was last regenerated. Used for staleness detection.';

    COMMENT ON COLUMN kb_entity_aliases.embedding_model IS
        'OpenAI embedding model used (e.g., text-embedding-3-small). Enables model upgrade detection.';
    COMMENT ON COLUMN kb_entity_aliases.embedding_updated_at IS
        'Timestamp when embedding was last regenerated. Used for staleness detection.';

    RAISE NOTICE 'Migration 011_embedding_versioning.sql completed';
END $$;

-- ============================================================================
-- ROLLBACK (manual if needed)
-- ============================================================================
-- ALTER TABLE kb_manufacturers DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE kb_manufacturers DROP COLUMN IF EXISTS embedding_updated_at;
-- ALTER TABLE kb_engine_models DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE kb_engine_models DROP COLUMN IF EXISTS embedding_updated_at;
-- ALTER TABLE kb_entity_aliases DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE kb_entity_aliases DROP COLUMN IF EXISTS embedding_updated_at;
-- DROP INDEX IF EXISTS idx_kb_manufacturers_embedding_model;
-- DROP INDEX IF EXISTS idx_kb_engine_models_embedding_model;
-- DROP INDEX IF EXISTS idx_kb_entity_aliases_embedding_model;
