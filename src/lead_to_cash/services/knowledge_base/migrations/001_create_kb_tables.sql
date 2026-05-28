-- Marine Engine Knowledge Base - PostgreSQL Schema
-- Migration: 001_create_kb_tables.sql
--
-- Creates all tables for the knowledge base with pgvector support
-- for semantic search and fuzzy matching.

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- CORE ENTITY TABLES
-- =============================================================================

-- Manufacturers table
CREATE TABLE IF NOT EXISTS kb_manufacturers (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    tier INTEGER DEFAULT 1 CHECK (tier IN (1, 2, 3)),
    website VARCHAR(500),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- pgvector column for name embeddings
    name_embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_name ON kb_manufacturers(name);
CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_tier ON kb_manufacturers(tier);
CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_active ON kb_manufacturers(is_active) WHERE is_active = TRUE;

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_kb_manufacturers_embedding
ON kb_manufacturers USING hnsw (name_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);


-- Engine Series table
CREATE TABLE IF NOT EXISTS kb_engine_series (
    id VARCHAR(36) PRIMARY KEY,
    manufacturer_id VARCHAR(36) NOT NULL REFERENCES kb_manufacturers(id) ON DELETE CASCADE,
    brand VARCHAR(255) NOT NULL,
    series_name VARCHAR(255) NOT NULL,
    description TEXT,
    generation INTEGER,
    year_introduced INTEGER,
    year_discontinued INTEGER,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_engine_series_manufacturer ON kb_engine_series(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_kb_engine_series_brand ON kb_engine_series(brand);
CREATE INDEX IF NOT EXISTS idx_kb_engine_series_name ON kb_engine_series(series_name);


-- Engine Models table
CREATE TABLE IF NOT EXISTS kb_engine_models (
    id VARCHAR(36) PRIMARY KEY,
    series_id VARCHAR(36) NOT NULL REFERENCES kb_engine_series(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,

    -- RPM specifications (target: 300-1000 rpm)
    rpm_min INTEGER,
    rpm_max INTEGER,

    -- Power specifications (target: 700-40,000 kW)
    power_min_kw DECIMAL(10,2),
    power_max_kw DECIMAL(10,2),

    -- Configuration
    cylinders INTEGER,
    configuration VARCHAR(50),  -- "V", "inline", "L"
    displacement_liters DECIMAL(10,2),

    -- Fuel types (JSON array)
    fuel_types JSONB,

    -- Weight and dimensions
    dry_weight_kg DECIMAL(10,2),
    length_mm DECIMAL(10,2),
    width_mm DECIMAL(10,2),
    height_mm DECIMAL(10,2),

    -- Classification
    emission_tier VARCHAR(50),  -- "IMO Tier II", "IMO Tier III"
    is_current_production BOOLEAN DEFAULT TRUE,

    -- Metadata
    data_source VARCHAR(255),
    data_confidence DECIMAL(3,2) DEFAULT 0.80,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- pgvector column for model name embeddings
    model_embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_kb_engine_models_series ON kb_engine_models(series_id);
CREATE INDEX IF NOT EXISTS idx_kb_engine_models_name ON kb_engine_models(model_name);
CREATE INDEX IF NOT EXISTS idx_kb_engine_models_rpm ON kb_engine_models(rpm_min, rpm_max);
CREATE INDEX IF NOT EXISTS idx_kb_engine_models_power ON kb_engine_models(power_min_kw, power_max_kw);
CREATE INDEX IF NOT EXISTS idx_kb_engine_models_production ON kb_engine_models(is_current_production) WHERE is_current_production = TRUE;

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_kb_engine_models_embedding
ON kb_engine_models USING hnsw (model_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);


-- Applications table
CREATE TABLE IF NOT EXISTS kb_applications (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50),  -- Short code like "FPSO", "OSV"
    description TEXT,
    category VARCHAR(100),  -- "commercial", "offshore", "naval"
    typical_power_range_min_kw DECIMAL(10,2),
    typical_power_range_max_kw DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_applications_name ON kb_applications(name);
CREATE INDEX IF NOT EXISTS idx_kb_applications_code ON kb_applications(code);
CREATE INDEX IF NOT EXISTS idx_kb_applications_category ON kb_applications(category);


-- Market Segments table
CREATE TABLE IF NOT EXISTS kb_market_segments (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    segment_type VARCHAR(100) NOT NULL,  -- MarketSegmentType value
    description TEXT,
    priority_score INTEGER DEFAULT 50 CHECK (priority_score >= 1 AND priority_score <= 100),
    growth_potential VARCHAR(50),  -- "high", "medium", "low"
    focus_regions JSONB,  -- JSON array of regions
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_market_segments_type ON kb_market_segments(segment_type);
CREATE INDEX IF NOT EXISTS idx_kb_market_segments_priority ON kb_market_segments(priority_score DESC);


-- =============================================================================
-- RELATIONSHIP/JUNCTION TABLES
-- =============================================================================

-- Engine-Application mapping
CREATE TABLE IF NOT EXISTS kb_engine_application_map (
    id VARCHAR(36) PRIMARY KEY,
    engine_model_id VARCHAR(36) NOT NULL REFERENCES kb_engine_models(id) ON DELETE CASCADE,
    application_id VARCHAR(36) NOT NULL REFERENCES kb_applications(id) ON DELETE CASCADE,
    suitability_score DECIMAL(3,2) DEFAULT 0.50 CHECK (suitability_score >= 0 AND suitability_score <= 1),
    is_primary_application BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(engine_model_id, application_id)
);

CREATE INDEX IF NOT EXISTS idx_kb_engine_app_map_engine ON kb_engine_application_map(engine_model_id);
CREATE INDEX IF NOT EXISTS idx_kb_engine_app_map_app ON kb_engine_application_map(application_id);


-- Engine-Competitor mapping
CREATE TABLE IF NOT EXISTS kb_engine_competitor_map (
    id VARCHAR(36) PRIMARY KEY,
    engine_model_id VARCHAR(36) NOT NULL REFERENCES kb_engine_models(id) ON DELETE CASCADE,
    competitor_engine_id VARCHAR(36) NOT NULL REFERENCES kb_engine_models(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) DEFAULT 'direct',  -- "direct", "indirect", "potential"
    overlap_score DECIMAL(3,2) DEFAULT 0.50 CHECK (overlap_score >= 0 AND overlap_score <= 1),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(engine_model_id, competitor_engine_id),
    CHECK(engine_model_id != competitor_engine_id)
);

CREATE INDEX IF NOT EXISTS idx_kb_engine_comp_map_engine ON kb_engine_competitor_map(engine_model_id);
CREATE INDEX IF NOT EXISTS idx_kb_engine_comp_map_competitor ON kb_engine_competitor_map(competitor_engine_id);


-- =============================================================================
-- ALIAS TABLE WITH EMBEDDINGS
-- =============================================================================

-- Entity Aliases for fuzzy matching
CREATE TABLE IF NOT EXISTS kb_entity_aliases (
    id VARCHAR(36) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,  -- "manufacturer", "engine_series", "engine_model", "application"
    entity_id VARCHAR(36) NOT NULL,  -- FK to referenced entity
    alias_text VARCHAR(500) NOT NULL,
    alias_type VARCHAR(50) DEFAULT 'common_name',  -- "common_name", "abbreviation", "misspelling", "former_name"
    normalized_text VARCHAR(500),  -- Lowercase, stripped for exact matching
    source VARCHAR(50) DEFAULT 'manual',  -- "manual", "extracted", "learned"
    confidence DECIMAL(3,2) DEFAULT 1.00 CHECK (confidence >= 0 AND confidence <= 1),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- pgvector column for semantic search
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_type ON kb_entity_aliases(entity_type);
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_entity ON kb_entity_aliases(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_text ON kb_entity_aliases(alias_text);
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_normalized ON kb_entity_aliases(normalized_text);
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_active ON kb_entity_aliases(is_active) WHERE is_active = TRUE;

-- HNSW index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_embedding
ON kb_entity_aliases USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Composite index for filtered vector searches
CREATE INDEX IF NOT EXISTS idx_kb_entity_aliases_type_embedding
ON kb_entity_aliases (entity_type) WHERE embedding IS NOT NULL;


-- =============================================================================
-- ARTICLE LINKING TABLES
-- =============================================================================

-- Article-Entity links
CREATE TABLE IF NOT EXISTS kb_article_entities (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL,  -- FK to external article table
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 0.50 CHECK (confidence >= 0 AND confidence <= 1),
    mention_count INTEGER DEFAULT 1,
    context_snippet TEXT,
    extraction_method VARCHAR(50) DEFAULT 'llm',  -- "llm", "regex", "manual"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(article_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_kb_article_entities_article ON kb_article_entities(article_id);
CREATE INDEX IF NOT EXISTS idx_kb_article_entities_entity ON kb_article_entities(entity_type, entity_id);


-- Article Scores
CREATE TABLE IF NOT EXISTS kb_article_scores (
    id VARCHAR(36) PRIMARY KEY,
    article_id VARCHAR(36) NOT NULL UNIQUE,  -- FK to external article table

    -- Component scores (0-100)
    technical_score DECIMAL(5,2) DEFAULT 0.00,
    market_score DECIMAL(5,2) DEFAULT 0.00,
    commercial_score DECIMAL(5,2) DEFAULT 0.00,

    -- Computed total
    total_score DECIMAL(5,2) DEFAULT 0.00,

    -- Classification: "high_priority", "monitor", "ignore"
    classification VARCHAR(50) DEFAULT 'ignore',

    -- Detailed breakdown (JSON)
    score_breakdown JSONB,

    -- Metadata
    scoring_model_version VARCHAR(20) DEFAULT 'v1',
    scored_at TIMESTAMP WITH TIME ZONE,
    score_explanation TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_article_scores_article ON kb_article_scores(article_id);
CREATE INDEX IF NOT EXISTS idx_kb_article_scores_total ON kb_article_scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_kb_article_scores_classification ON kb_article_scores(classification);


-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_kb_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN
        SELECT table_name FROM information_schema.columns
        WHERE column_name = 'updated_at'
        AND table_name LIKE 'kb_%'
        AND table_schema = 'public'
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

COMMENT ON TABLE kb_manufacturers IS 'Marine engine manufacturers (Tier 1-3)';
COMMENT ON TABLE kb_engine_series IS 'Engine series/brands under manufacturers';
COMMENT ON TABLE kb_engine_models IS 'Specific engine models with specifications';
COMMENT ON TABLE kb_applications IS 'Marine application types (FPSO, OSV, etc.)';
COMMENT ON TABLE kb_market_segments IS 'Market segments for opportunity prioritization';
COMMENT ON TABLE kb_engine_application_map IS 'Engine-to-application suitability mapping';
COMMENT ON TABLE kb_engine_competitor_map IS 'Competitive engine relationships';
COMMENT ON TABLE kb_entity_aliases IS 'Aliases for fuzzy entity matching with embeddings';
COMMENT ON TABLE kb_article_entities IS 'Article-to-entity extraction links';
COMMENT ON TABLE kb_article_scores IS 'Article relevance scoring and classification';
