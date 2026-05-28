-- ============================================================================
-- Entity Registry Database Schema
-- Migration 001: Create core tables
-- ============================================================================
-- A dedicated database for unified company identity resolution.
-- Replaces hardcoded lookup tables (KYP_NAME_LOOKUP, CUSTOMER_NAME_LOOKUP).
--
-- Tables:
--   entity_registry          - Core entity table
--   entity_aliases           - Multiple aliases per entity
--   entity_external_mappings - Links to SAP, EODHD, Aravo
--   entity_resolution_history - Audit trail
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For trigram similarity search
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- For Levenshtein distance (typo correction)

-- Note: pgvector extension should be enabled if semantic search is needed
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

DO $$
BEGIN
    -- Verification status enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_status') THEN
        CREATE TYPE verification_status AS ENUM (
            'unverified',
            'user_confirmed',
            'externally_verified',
            'duplicate',
            'invalid',
            'archived'
        );
    END IF;

    -- Entity source type enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_source_type') THEN
        CREATE TYPE entity_source_type AS ENUM (
            'sap_cpi',
            'eodhd',
            'acra',
            'gleif',
            'opencorporates',
            'user_input',
            'migration'
        );
    END IF;
END $$;

-- ============================================================================
-- CORE ENTITY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_registry (
    -- Primary key (UUID for global uniqueness)
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Canonical name (user-confirmed or externally verified)
    canonical_name TEXT NOT NULL,

    -- Legal registration details
    legal_name TEXT,
    country_code CHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2

    -- Unique identifiers (nullable - not all entities have all IDs)
    uen TEXT,              -- Singapore Unique Entity Number
    lei TEXT,              -- Legal Entity Identifier (GLEIF, 20 chars)
    cvr TEXT,              -- Danish CVR number
    vat_number TEXT,       -- VAT registration number
    duns TEXT,             -- D&B DUNS number

    -- Registry information (JSON for flexibility)
    acra_data JSONB,           -- ACRA business profile (Singapore)
    opencorporates_data JSONB, -- OpenCorporates data (global)
    gleif_data JSONB,          -- GLEIF LEI data

    -- Entity classification
    entity_type TEXT DEFAULT 'company',  -- company, subsidiary, division
    industry_sector TEXT,

    -- Verification status
    verification_status verification_status NOT NULL DEFAULT 'unverified',
    verified_at TIMESTAMPTZ,
    verified_by TEXT,          -- user_id or 'system'
    verification_source TEXT,  -- 'user', 'acra', 'gleif', 'opencorporates'

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT entity_registry_lei_format CHECK (lei IS NULL OR length(lei) = 20),
    CONSTRAINT entity_registry_country_format CHECK (length(country_code) = 2)
);

-- Indexes for entity_registry
CREATE INDEX IF NOT EXISTS idx_entity_registry_canonical_name
    ON entity_registry USING gin (canonical_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_entity_registry_canonical_name_lower
    ON entity_registry (lower(canonical_name));

CREATE INDEX IF NOT EXISTS idx_entity_registry_country
    ON entity_registry (country_code);

CREATE INDEX IF NOT EXISTS idx_entity_registry_uen
    ON entity_registry (uen) WHERE uen IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entity_registry_lei
    ON entity_registry (lei) WHERE lei IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entity_registry_status
    ON entity_registry (verification_status);

CREATE INDEX IF NOT EXISTS idx_entity_registry_confirmed
    ON entity_registry (entity_type)
    WHERE verification_status IN ('user_confirmed', 'externally_verified');

CREATE INDEX IF NOT EXISTS idx_entity_registry_created_at
    ON entity_registry (created_at DESC);

-- Unique constraint on canonical name + country for confirmed entities
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_registry_unique_confirmed
    ON entity_registry (lower(canonical_name), country_code)
    WHERE verification_status IN ('user_confirmed', 'externally_verified');

-- ============================================================================
-- ALIASES TABLE (many aliases per entity)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES entity_registry(id) ON DELETE CASCADE,

    alias_text TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'common_name',
    -- common_name, abbreviation, trading_name, former_name, misspelling

    normalized_text TEXT NOT NULL,  -- lowercase, trimmed for exact match

    source entity_source_type NOT NULL DEFAULT 'user_input',
    confidence DECIMAL(3,2) DEFAULT 1.00,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT entity_aliases_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT entity_aliases_unique UNIQUE (entity_id, normalized_text)
);

-- Indexes for entity_aliases
CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized
    ON entity_aliases (normalized_text);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity
    ON entity_aliases (entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_text
    ON entity_aliases USING gin (alias_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_source
    ON entity_aliases (source);

-- ============================================================================
-- EXTERNAL SYSTEM MAPPINGS
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_external_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES entity_registry(id) ON DELETE CASCADE,

    external_system TEXT NOT NULL,  -- 'sap', 'eodhd', 'aravo'
    external_id TEXT NOT NULL,      -- customer_id, stock_symbol, etc.
    external_data JSONB,            -- cached data from external system

    verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT entity_mappings_unique_entity_system UNIQUE (entity_id, external_system),
    CONSTRAINT entity_mappings_unique_system_id UNIQUE (external_system, external_id)
);

-- Indexes for entity_external_mappings
CREATE INDEX IF NOT EXISTS idx_entity_mappings_external
    ON entity_external_mappings (external_system, external_id);

CREATE INDEX IF NOT EXISTS idx_entity_mappings_entity
    ON entity_external_mappings (entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_mappings_verified
    ON entity_external_mappings (verified) WHERE verified = TRUE;

-- ============================================================================
-- RESOLUTION HISTORY (audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_resolution_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Resolution request
    session_id TEXT NOT NULL,
    user_query TEXT NOT NULL,

    -- Resolution result
    entity_id UUID REFERENCES entity_registry(id),  -- NULL if no match confirmed
    resolution_type TEXT NOT NULL,
    -- 'exact_match', 'user_confirmed', 'auto_confirmed', 'no_match', 'new_entity'

    -- Candidates presented (for audit)
    candidates_presented JSONB,
    selected_rank INTEGER,

    -- Timing
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    response_time_ms INTEGER
);

-- Indexes for entity_resolution_history
CREATE INDEX IF NOT EXISTS idx_resolution_history_session
    ON entity_resolution_history (session_id);

CREATE INDEX IF NOT EXISTS idx_resolution_history_entity
    ON entity_resolution_history (entity_id) WHERE entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_resolution_history_time
    ON entity_resolution_history (resolved_at DESC);

CREATE INDEX IF NOT EXISTS idx_resolution_history_type
    ON entity_resolution_history (resolution_type);

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_entity_registry_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic updated_at
DROP TRIGGER IF EXISTS trigger_entity_registry_updated_at ON entity_registry;
CREATE TRIGGER trigger_entity_registry_updated_at
    BEFORE UPDATE ON entity_registry
    FOR EACH ROW EXECUTE FUNCTION update_entity_registry_updated_at();

DROP TRIGGER IF EXISTS trigger_entity_mappings_updated_at ON entity_external_mappings;
CREATE TRIGGER trigger_entity_mappings_updated_at
    BEFORE UPDATE ON entity_external_mappings
    FOR EACH ROW EXECUTE FUNCTION update_entity_registry_updated_at();

-- Function to normalize text for matching
CREATE OR REPLACE FUNCTION normalize_entity_name(name TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Lowercase, remove common suffixes, collapse whitespace
    RETURN regexp_replace(
        regexp_replace(
            regexp_replace(
                lower(trim(name)),
                '\s+(pte\.?|pty\.?|ltd\.?|limited|inc\.?|corp\.?|llc\.?|gmbh|b\.?v\.?|a/s|s\.?a\.?)(\s|$)',
                ' ',
                'gi'
            ),
            '[^\w\s-]',
            '',
            'g'
        ),
        '\s+',
        ' ',
        'g'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- TABLE COMMENTS
-- ============================================================================

COMMENT ON TABLE entity_registry IS
    'Unified company identity registry. Single source of truth for confirmed '
    'company identities from SAP, EODHD, ACRA, GLEIF, and user input.';

COMMENT ON COLUMN entity_registry.canonical_name IS
    'Official company name (primary identifier for display and matching)';

COMMENT ON COLUMN entity_registry.uen IS
    'Singapore Unique Entity Number (e.g., 200504525N for Batam Fast Ferry)';

COMMENT ON COLUMN entity_registry.lei IS
    'Legal Entity Identifier - 20-character global standard from GLEIF';

COMMENT ON COLUMN entity_registry.verification_status IS
    'Status of entity verification: unverified, user_confirmed, externally_verified, etc.';

COMMENT ON TABLE entity_aliases IS
    'Multiple name variations that map to a single entity. '
    'Used for fuzzy matching and common abbreviations.';

COMMENT ON TABLE entity_external_mappings IS
    'Links entity registry entries to external system IDs '
    '(SAP customer number, EODHD stock symbol, Aravo supplier ID).';

COMMENT ON TABLE entity_resolution_history IS
    'Audit trail of entity resolution attempts. '
    'Records queries, candidates presented, and user selections.';
