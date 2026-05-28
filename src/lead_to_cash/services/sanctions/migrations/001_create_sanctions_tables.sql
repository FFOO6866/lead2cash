-- Sanctions screening persistent store
-- Replaces live downloads with database-backed screening.
-- Data refreshed daily via background task; KYP queries DB instantly.

CREATE TABLE IF NOT EXISTS sanctions_entries (
    id SERIAL PRIMARY KEY,
    source_key VARCHAR(50) NOT NULL,        -- OFAC_SDN, UN_CONSOLIDATED, EU_FSF, MAS_SG
    entity_name VARCHAR(1000) NOT NULL,
    entity_name_normalized VARCHAR(1000) NOT NULL,  -- lowercase, no punctuation
    entity_type VARCHAR(50),                -- INDIVIDUAL, ENTITY, null
    is_alias BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sanctions_source ON sanctions_entries(source_key);
CREATE INDEX IF NOT EXISTS idx_sanctions_normalized ON sanctions_entries(entity_name_normalized);
CREATE INDEX IF NOT EXISTS idx_sanctions_name ON sanctions_entries(entity_name);

CREATE TABLE IF NOT EXISTS sanctions_list_metadata (
    source_key VARCHAR(50) PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    source_url VARCHAR(500),
    record_count INTEGER DEFAULT 0,
    list_date DATE,
    last_refreshed TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'not_loaded'  -- not_loaded, loading, loaded, error
);

-- Seed metadata rows for the 4 authoritative lists
INSERT INTO sanctions_list_metadata (source_key, source_name, source_url)
VALUES
    ('OFAC_SDN', 'OFAC SDN List', 'https://sanctionssearch.ofac.treas.gov/'),
    ('UN_CONSOLIDATED', 'UN Security Council', 'https://scsanctions.un.org/'),
    ('EU_FSF', 'EU Consolidated Sanctions', 'https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions'),
    ('MAS_SG', 'MAS Singapore', 'https://www.mas.gov.sg/regulation/anti-money-laundering/targeted-financial-sanctions/lists-of-designated-individuals-and-entities')
ON CONFLICT (source_key) DO NOTHING;
