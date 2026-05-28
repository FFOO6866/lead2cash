-- =============================================================================
-- Marine Sales Intelligence Database Schema
-- =============================================================================
--
-- Tables:
-- 1. marine_opportunities - Sales opportunities with URL hash deduplication
-- 2. marine_articles - Source documents with embeddings (for future RAG)
-- 3. marine_accounts - Company tracking with mention counts
-- 4. marine_article_accounts - Junction table for article-company mentions
-- 5. marine_research_jobs - Processing job tracking
--
-- Target Market: Singapore and Asia-Pacific
-- Priority Sectors: Marine transportation, Offshore oil & gas, Marine engineering
-- Signal Types: NEWBUILD, RETROFIT_REPOWER, OFFSHORE_PROJECT, REGULATION,
--               FUEL_TRANSITION, FLEET_EXPANSION, INCIDENT_RELIABILITY, FINANCING_CAPEX
-- =============================================================================

-- Enable required extensions (for PostgreSQL)
-- Note: pgvector may already be enabled in the database
-- CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- Table 1: marine_opportunities (Primary Sales Opportunities)
-- =============================================================================
-- Sales opportunities extracted from web research with URL hash deduplication.

CREATE TABLE IF NOT EXISTS marine_opportunities (
    id TEXT PRIMARY KEY,
    headline TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    url_hash TEXT UNIQUE NOT NULL,

    -- Classification
    sales_signals TEXT[] NOT NULL DEFAULT '{}',
    region TEXT NOT NULL,
    vessel_types TEXT[] NOT NULL DEFAULT '{}',
    sector TEXT NOT NULL,

    -- Companies and context
    companies_involved TEXT[] NOT NULL DEFAULT '{}',
    country TEXT NOT NULL,

    -- Analysis
    sales_explanation TEXT NOT NULL,
    suggested_action TEXT NOT NULL,

    -- Metadata
    source_category TEXT NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_date TIMESTAMPTZ,
    raw_content TEXT DEFAULT '',

    -- Optional enrichment
    estimated_value FLOAT,
    currency TEXT DEFAULT 'USD',
    engine_power_range TEXT,
    contact_info TEXT,

    -- Processing status
    reviewed BOOLEAN DEFAULT FALSE,
    exported_to_crm BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 5,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Opportunity indexes
CREATE INDEX IF NOT EXISTS idx_opportunities_region ON marine_opportunities(region);
CREATE INDEX IF NOT EXISTS idx_opportunities_sector ON marine_opportunities(sector);
CREATE INDEX IF NOT EXISTS idx_opportunities_discovered_at ON marine_opportunities(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_reviewed ON marine_opportunities(reviewed);
CREATE INDEX IF NOT EXISTS idx_opportunities_priority ON marine_opportunities(priority DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_sales_signals ON marine_opportunities USING GIN (sales_signals);
CREATE INDEX IF NOT EXISTS idx_opportunities_vessel_types ON marine_opportunities USING GIN (vessel_types);

COMMENT ON TABLE marine_opportunities IS 'Sales opportunities from web research with URL-based deduplication';
COMMENT ON COLUMN marine_opportunities.url_hash IS 'SHA-256 hash of source_url for duplicate detection';
COMMENT ON COLUMN marine_opportunities.sales_signals IS 'Array of signal types: newbuild, retrofit_repower, etc.';

-- =============================================================================
-- Table 2: marine_articles (Source Documents - for future RAG)
-- =============================================================================
-- Stores news articles and source documents with URL hash for deduplication.
-- Supports vector embeddings for semantic search.

CREATE TABLE IF NOT EXISTS marine_articles (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE,  -- SHA-256 hash for deduplication
    title TEXT NOT NULL,
    source TEXT NOT NULL,           -- Publication name (TradeWinds, Lloyd's List, etc.)
    content TEXT,                   -- Full article content
    summary TEXT,                   -- AI-generated or extracted summary
    published_date TIMESTAMPTZ,
    processed_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_processed BOOLEAN DEFAULT FALSE,
    opportunities_generated INTEGER DEFAULT 0,
    source_category TEXT DEFAULT 'trade_media',  -- regulatory, industry_association, trade_media, shipyard, etc.
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),         -- OpenAI text-embedding-3-small
    retention_tier TEXT DEFAULT 'hot',  -- hot, warm, cold
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for marine_articles
CREATE INDEX IF NOT EXISTS idx_marine_articles_url_hash ON marine_articles(url_hash);
CREATE INDEX IF NOT EXISTS idx_marine_articles_source ON marine_articles(source);
CREATE INDEX IF NOT EXISTS idx_marine_articles_published_date ON marine_articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_marine_articles_processed_date ON marine_articles(processed_date DESC);
CREATE INDEX IF NOT EXISTS idx_marine_articles_is_processed ON marine_articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_marine_articles_retention_tier ON marine_articles(retention_tier);
-- HNSW vector index for semantic similarity search
CREATE INDEX IF NOT EXISTS idx_marine_articles_embedding ON marine_articles USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE marine_articles IS 'Source documents for marine intelligence with URL-based deduplication';
COMMENT ON COLUMN marine_articles.url_hash IS 'SHA-256 hash of URL for duplicate detection';
COMMENT ON COLUMN marine_articles.source IS 'Publication name: TradeWinds, Lloyd''s List, Maritime Executive, etc.';
COMMENT ON COLUMN marine_articles.source_category IS 'Category: regulatory, industry_association, trade_media, shipyard, sgx_announcement, company_news, perplexity';
COMMENT ON COLUMN marine_articles.embedding IS '1536-dim vector from OpenAI text-embedding-3-small';
COMMENT ON COLUMN marine_articles.retention_tier IS 'Data lifecycle: hot (full), warm (summary only), cold (metadata only)';

-- =============================================================================
-- Table 3: marine_accounts (Company Tracking)
-- =============================================================================
-- Tracks companies mentioned across articles for account-based selling.
-- Uses normalized company name for matching.

CREATE TABLE IF NOT EXISTS marine_accounts (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,  -- Lowercase, cleaned for matching
    country TEXT,
    sector TEXT,                            -- Primary sector
    website TEXT,
    mention_count INTEGER DEFAULT 0,
    opportunity_count INTEGER DEFAULT 0,
    first_seen_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_score FLOAT DEFAULT 0.0,          -- Sum of opportunity scores
    priority_rank INTEGER,                   -- Calculated ranking
    crm_account_id TEXT,                     -- SAP CRM / MS5 ID
    is_existing_customer BOOLEAN DEFAULT FALSE,
    aliases TEXT[] DEFAULT '{}',             -- Alternative company names
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for marine_accounts
CREATE INDEX IF NOT EXISTS idx_marine_accounts_normalized_name ON marine_accounts(normalized_name);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_country ON marine_accounts(country);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_sector ON marine_accounts(sector);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_mention_count ON marine_accounts(mention_count DESC);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_total_score ON marine_accounts(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_last_seen ON marine_accounts(last_seen_date DESC);
CREATE INDEX IF NOT EXISTS idx_marine_accounts_crm_id ON marine_accounts(crm_account_id);

COMMENT ON TABLE marine_accounts IS 'Company tracking for account-based selling with mention aggregation';
COMMENT ON COLUMN marine_accounts.normalized_name IS 'Lowercase name with suffixes (Pte Ltd, Inc, etc.) removed for matching';
COMMENT ON COLUMN marine_accounts.sector IS 'Primary sector: marine_transportation, offshore_oil_gas, marine_engineering, etc.';
COMMENT ON COLUMN marine_accounts.crm_account_id IS 'External CRM reference ID (SAP, MS5)';

-- =============================================================================
-- Table 4: marine_article_accounts (Junction Table)
-- =============================================================================
-- Tracks which companies are mentioned in which articles.
-- Many-to-many relationship for article-company mentions.

CREATE TABLE IF NOT EXISTS marine_article_accounts (
    article_id TEXT NOT NULL REFERENCES marine_articles(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES marine_accounts(id) ON DELETE CASCADE,
    mention_context TEXT,                    -- Excerpt where company was mentioned
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (article_id, account_id)
);

-- Indexes for marine_article_accounts
CREATE INDEX IF NOT EXISTS idx_marine_article_accounts_article ON marine_article_accounts(article_id);
CREATE INDEX IF NOT EXISTS idx_marine_article_accounts_account ON marine_article_accounts(account_id);

COMMENT ON TABLE marine_article_accounts IS 'Junction table tracking company mentions in articles';
COMMENT ON COLUMN marine_article_accounts.mention_context IS 'Text excerpt where company was mentioned in the article';

-- =============================================================================
-- Table 5: marine_research_jobs (Processing Jobs)
-- =============================================================================
-- Tracks research/processing job status and metrics.

CREATE TABLE IF NOT EXISTS marine_research_jobs (
    id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,                  -- daily_research, manual, weekly_deep
    status TEXT NOT NULL,                    -- pending, running, completed, failed
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    queries_executed INTEGER DEFAULT 0,
    articles_processed INTEGER DEFAULT 0,
    opportunities_found INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_message TEXT
);

-- Indexes for marine_research_jobs
CREATE INDEX IF NOT EXISTS idx_marine_research_jobs_status ON marine_research_jobs(status);
CREATE INDEX IF NOT EXISTS idx_marine_research_jobs_started ON marine_research_jobs(started_at DESC);

COMMENT ON TABLE marine_research_jobs IS 'Research and processing job tracking';
COMMENT ON COLUMN marine_research_jobs.job_type IS 'Job type: daily_research, manual, weekly_deep, backfill, reprocess';
COMMENT ON COLUMN marine_research_jobs.status IS 'Job status: pending, running, completed, failed';

-- =============================================================================
-- Useful Views
-- =============================================================================

-- View: Top accounts by score
CREATE OR REPLACE VIEW v_top_accounts AS
SELECT
    id,
    company_name,
    country,
    sector,
    mention_count,
    opportunity_count,
    total_score,
    last_seen_date,
    crm_account_id,
    is_existing_customer
FROM marine_accounts
ORDER BY total_score DESC
LIMIT 100;

-- View: Recent high-priority opportunities
CREATE OR REPLACE VIEW v_recent_opportunities AS
SELECT
    id,
    headline,
    country,
    region,
    sector,
    sales_signals,
    priority,
    discovered_at,
    source_name,
    source_url,
    reviewed
FROM marine_opportunities
WHERE reviewed = FALSE
ORDER BY priority DESC, discovered_at DESC
LIMIT 100;

-- View: Article processing status
CREATE OR REPLACE VIEW v_article_processing AS
SELECT
    source,
    COUNT(*) as total_articles,
    COUNT(*) FILTER (WHERE is_processed = TRUE) as processed,
    COUNT(*) FILTER (WHERE is_processed = FALSE) as pending,
    SUM(opportunities_generated) as total_opportunities,
    MAX(processed_date) as last_processed
FROM marine_articles
GROUP BY source
ORDER BY total_articles DESC;

-- =============================================================================
-- Signal Type Reference
-- =============================================================================
--
-- NEWBUILD: New vessel construction contracts
-- RETROFIT_REPOWER: Engine replacement/upgrade projects
-- OFFSHORE_PROJECT: Offshore oil & gas projects (FPSO, OSV, etc.)
-- REGULATION: IMO/regulatory compliance needs (emissions, CII)
-- FUEL_TRANSITION: LNG, methanol, ammonia conversion projects
-- FLEET_EXPANSION: Fleet growth announcements
-- INCIDENT_RELIABILITY: Engine failures, reliability issues (repower opportunity)
-- FINANCING_CAPEX: Investment/financing announcements indicating procurement
-- =============================================================================

-- =============================================================================
-- Sector Reference
-- =============================================================================
--
-- MARINE_TRANSPORTATION: Ferries, cargo, cruise vessels
-- OFFSHORE_OIL_GAS: OSV, PSV, AHTS, FPSO, drilling
-- MARINE_ENGINEERING: Shipyards, repair facilities
-- PORT_TERMINAL: Tugs, dredgers, port vessels
-- SHIPPING: Container, tanker, bulk carriers
-- NAVAL_DEFENSE: Naval vessels, coast guard
-- =============================================================================
