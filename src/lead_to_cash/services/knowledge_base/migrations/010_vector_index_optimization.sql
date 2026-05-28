-- Migration 010: Vector Index Optimization for Hybrid Search
-- Adds filtered composite indexes for hybrid search (vector + metadata filtering)
-- Documents ef_search runtime parameter for HNSW indexes
--
-- This migration improves vector search performance by:
-- 1. Creating filtered indexes that combine metadata columns with vector eligibility
-- 2. Documenting runtime parameters for HNSW index tuning
--
-- Reference: pgvector documentation for HNSW parameters
-- License: Integrum Pte Ltd / SS Foo

-- ============================================================================
-- IDEMPOTENT: Check if migration has already been applied
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_kb_entity_aliases_filter_combo') THEN
        RAISE NOTICE 'Migration 010 already applied - skipping';
        RETURN;
    END IF;

    -- ========================================================================
    -- Filtered Composite Indexes for Hybrid Search
    -- These indexes optimize queries that filter by metadata before vector search
    -- ========================================================================

    -- Entity Aliases: Combined filter on entity_type and alias_type
    -- Optimizes: "Find similar aliases of type 'manufacturer' with alias_type 'abbreviation'"
    CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_filter_combo
        ON kb_entity_aliases(entity_type, alias_type)
        WHERE is_active = TRUE AND embedding IS NOT NULL;

    RAISE NOTICE 'Created idx_kb_entity_aliases_filter_combo';

    -- Engine Models: Combined filter on specs for power/RPM range queries
    -- Optimizes: "Find similar engines in power range 1000-5000 kW"
    CREATE INDEX IF NOT EXISTS idx_kb_engine_models_specs_filter
        ON kb_engine_models(rpm_min, rpm_max, power_min_kw, power_max_kw)
        WHERE is_current_production = TRUE AND model_embedding IS NOT NULL;

    RAISE NOTICE 'Created idx_kb_engine_models_specs_filter';

    -- Manufacturers: Tier-based filtering for vector search
    -- Optimizes: "Find similar Tier-1 manufacturers"
    CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_tier_filter
        ON kb_manufacturers(tier)
        WHERE is_active = TRUE AND name_embedding IS NOT NULL;

    RAISE NOTICE 'Created idx_kb_manufacturers_tier_filter';

    -- ========================================================================
    -- Document ef_search Runtime Parameter
    -- HNSW ef_search controls search accuracy vs speed at query time
    -- Default: 40 (matches ef_construction)
    -- Recommended: 100-200 for higher recall on larger datasets
    --
    -- Usage: SET LOCAL hnsw.ef_search = 100;
    --        SELECT * FROM kb_entity_aliases ORDER BY embedding <=> $1 LIMIT 10;
    -- ========================================================================

    COMMENT ON INDEX idx_kb_manufacturers_embedding IS
        'HNSW index (m=16, ef_construction=64). For higher recall: SET LOCAL hnsw.ef_search = 100 before query. Default ef_search=40.';

    COMMENT ON INDEX idx_kb_engine_models_embedding IS
        'HNSW index (m=16, ef_construction=64). For higher recall: SET LOCAL hnsw.ef_search = 100 before query. Default ef_search=40.';

    COMMENT ON INDEX idx_kb_entity_aliases_embedding IS
        'HNSW index (m=16, ef_construction=64). For higher recall: SET LOCAL hnsw.ef_search = 100 before query. Default ef_search=40.';

    RAISE NOTICE 'Added documentation comments to HNSW indexes';

    -- ========================================================================
    -- Statistics Update
    -- Run ANALYZE to ensure query planner has up-to-date statistics
    -- ========================================================================
    ANALYZE kb_entity_aliases;
    ANALYZE kb_engine_models;
    ANALYZE kb_manufacturers;

    RAISE NOTICE 'Migration 010_vector_index_optimization.sql completed';
END $$;

-- ============================================================================
-- ROLLBACK (manual if needed)
-- ============================================================================
-- DROP INDEX IF EXISTS idx_kb_entity_aliases_filter_combo;
-- DROP INDEX IF EXISTS idx_kb_engine_models_specs_filter;
-- DROP INDEX IF EXISTS idx_kb_manufacturers_tier_filter;
