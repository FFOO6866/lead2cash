-- ============================================================================
-- Migration 005: Seed Known Entities
-- ============================================================================
-- Seeds the entity registry with known companies from SAP simulation and
-- frequently queried entities. This provides fast local matching before
-- falling back to external API searches.
--
-- Usage: Applied automatically during deployment via setup_database.py
--
-- NOTE: Uses WHERE NOT EXISTS instead of ON CONFLICT because the unique
-- indexes are expression-based (upper(uen), upper(lei)) which don't support
-- ON CONFLICT directly.
-- ============================================================================

-- ============================================================================
-- Singapore Companies
-- ============================================================================

-- ST Engineering (Singapore Technologies Engineering Ltd)
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    uen,
    lei,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'Singapore Technologies Engineering Ltd',
    'Singapore Technologies Engineering Ltd',
    'SG',
    '199706231H',
    '254900DC221DPLG97956',
    'corporation',
    'aerospace_defense',
    'externally_verified'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE upper(uen) = upper('199706231H')
);

-- Add aliases for ST Engineering
INSERT INTO entity_aliases (entity_id, alias_text, alias_type, normalized_text, confidence, source)
SELECT
    e.id,
    a.alias_text,
    'trade_name',
    UPPER(a.alias_text),
    0.95,
    'migration'::entity_source_type
FROM entity_registry e
CROSS JOIN (VALUES
    ('ST Engineering'),
    ('STE'),
    ('STEngg'),
    ('ST Engg'),
    ('Singapore Tech Engineering'),
    ('Singapore Technologies'),
    ('ST Engineering Limited'),
    ('ST Engineering Ltd')
) AS a(alias_text)
WHERE e.uen = '199706231H'
  AND NOT EXISTS (
      SELECT 1 FROM entity_aliases
      WHERE entity_id = e.id AND normalized_text = UPPER(a.alias_text)
  );

-- Batam Fast Ferry Pte Ltd
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    uen,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'Batam Fast Ferry Pte Ltd',
    'Batam Fast Ferry Pte Ltd',
    'SG',
    '199901234A',
    'private_company',
    'maritime_transport',
    'externally_verified'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE upper(uen) = upper('199901234A')
);

-- Add aliases for Batam Fast
INSERT INTO entity_aliases (entity_id, alias_text, alias_type, normalized_text, confidence, source)
SELECT
    e.id,
    a.alias_text,
    'trade_name',
    UPPER(a.alias_text),
    0.95,
    'migration'::entity_source_type
FROM entity_registry e
CROSS JOIN (VALUES
    ('Batam Fast'),
    ('BatamFast'),
    ('Batam Fast Ferry'),
    ('Batam Ferry'),
    ('Batam'),
    ('BATAM'),
    ('BFF')
) AS a(alias_text)
WHERE e.uen = '199901234A'
  AND NOT EXISTS (
      SELECT 1 FROM entity_aliases
      WHERE entity_id = e.id AND normalized_text = UPPER(a.alias_text)
  );

-- Pacific Maritime Pte Ltd (no UEN in simulation)
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'Pacific Maritime Pte Ltd',
    'Pacific Maritime Pte Ltd',
    'SG',
    'private_company',
    'maritime_services',
    'user_confirmed'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE canonical_name = 'Pacific Maritime Pte Ltd'
);

-- ============================================================================
-- European Companies
-- ============================================================================

-- Maersk A/S (Denmark)
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    uen,
    lei,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'A.P. Møller - Mærsk A/S',
    'A.P. Møller - Mærsk A/S',
    'DK',
    '25505933',
    '549300D1VQRWPG79RH48',
    'corporation',
    'shipping',
    'externally_verified'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE upper(lei) = upper('549300D1VQRWPG79RH48')
);

-- Add aliases for Maersk
INSERT INTO entity_aliases (entity_id, alias_text, alias_type, normalized_text, confidence, source)
SELECT
    e.id,
    a.alias_text,
    'trade_name',
    UPPER(a.alias_text),
    0.95,
    'migration'::entity_source_type
FROM entity_registry e
CROSS JOIN (VALUES
    ('Maersk'),
    ('Maersk Line'),
    ('Maersk A/S'),
    ('A.P. Moller Maersk'),
    ('A.P. Moller'),
    ('A.P. Møller'),
    ('Moller Maersk'),
    ('APMM'),
    ('AP Moller'),
    ('APM'),
    ('AP Moller Maersk')
) AS a(alias_text)
WHERE e.lei = '549300D1VQRWPG79RH48'
  AND NOT EXISTS (
      SELECT 1 FROM entity_aliases
      WHERE entity_id = e.id AND normalized_text = UPPER(a.alias_text)
  );

-- Neptune Energy (Netherlands)
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'Neptune Energy Group Midco Limited',
    'Neptune Energy Group Midco Limited',
    'NL',
    'private_company',
    'oil_gas',
    'user_confirmed'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE canonical_name = 'Neptune Energy Group Midco Limited'
);

-- Add aliases for Neptune Energy
INSERT INTO entity_aliases (entity_id, alias_text, alias_type, normalized_text, confidence, source)
SELECT
    e.id,
    a.alias_text,
    'trade_name',
    UPPER(a.alias_text),
    0.95,
    'migration'::entity_source_type
FROM entity_registry e
CROSS JOIN (VALUES
    ('Neptune Energy'),
    ('Neptune'),
    ('Neptune Oil'),
    ('Neptune Gas')
) AS a(alias_text)
WHERE e.canonical_name = 'Neptune Energy Group Midco Limited'
  AND NOT EXISTS (
      SELECT 1 FROM entity_aliases
      WHERE entity_id = e.id AND normalized_text = UPPER(a.alias_text)
  );

-- CLLS Power System (Germany)
INSERT INTO entity_registry (
    canonical_name,
    legal_name,
    country_code,
    entity_type,
    industry_sector,
    verification_status,
    verification_source
)
SELECT
    'CLLS Power System GmbH',
    'CLLS Power System GmbH',
    'DE',
    'private_company',
    'power_systems',
    'user_confirmed'::verification_status,
    'migration'
WHERE NOT EXISTS (
    SELECT 1 FROM entity_registry WHERE canonical_name = 'CLLS Power System GmbH'
);

-- Add aliases for CLLS Power
INSERT INTO entity_aliases (entity_id, alias_text, alias_type, normalized_text, confidence, source)
SELECT
    e.id,
    a.alias_text,
    'trade_name',
    UPPER(a.alias_text),
    0.95,
    'migration'::entity_source_type
FROM entity_registry e
CROSS JOIN (VALUES
    ('CLLS Power'),
    ('CLLS'),
    ('CLLS Power System'),
    ('CLLS GmbH')
) AS a(alias_text)
WHERE e.canonical_name = 'CLLS Power System GmbH'
  AND NOT EXISTS (
      SELECT 1 FROM entity_aliases
      WHERE entity_id = e.id AND normalized_text = UPPER(a.alias_text)
  );

-- ============================================================================
-- Add external mappings for SAP customer IDs
-- ============================================================================

-- ST Engineering → SAP 0022005992
INSERT INTO entity_external_mappings (entity_id, external_system, external_id, external_data, verified)
SELECT e.id, 'sap', '0022005992', '{"name": "ST Engineering"}'::jsonb, true
FROM entity_registry e
WHERE e.uen = '199706231H'
  AND NOT EXISTS (
      SELECT 1 FROM entity_external_mappings
      WHERE entity_id = e.id AND external_system = 'sap'
  );

-- Batam Fast → SAP 0000100001
INSERT INTO entity_external_mappings (entity_id, external_system, external_id, external_data, verified)
SELECT e.id, 'sap', '0000100001', '{"name": "Batam Fast Ferry Pte Ltd"}'::jsonb, true
FROM entity_registry e
WHERE e.uen = '199901234A'
  AND NOT EXISTS (
      SELECT 1 FROM entity_external_mappings
      WHERE entity_id = e.id AND external_system = 'sap'
  );

-- Maersk → SAP 0000100002
INSERT INTO entity_external_mappings (entity_id, external_system, external_id, external_data, verified)
SELECT e.id, 'sap', '0000100002', '{"name": "Maersk A/S"}'::jsonb, true
FROM entity_registry e
WHERE e.lei = '549300D1VQRWPG79RH48'
  AND NOT EXISTS (
      SELECT 1 FROM entity_external_mappings
      WHERE entity_id = e.id AND external_system = 'sap'
  );

-- CLLS Power System → SAP 0021000090
INSERT INTO entity_external_mappings (entity_id, external_system, external_id, external_data, verified)
SELECT e.id, 'sap', '0021000090', '{"name": "CLLS POWER SYSTEM LTD", "credit_control_area": "0111"}'::jsonb, true
FROM entity_registry e
WHERE e.canonical_name = 'CLLS Power System GmbH'
  AND NOT EXISTS (
      SELECT 1 FROM entity_external_mappings
      WHERE entity_id = e.id AND external_system = 'sap'
  );

-- ============================================================================
-- Log completion
-- ============================================================================
DO $$
DECLARE
    entity_count INTEGER;
    alias_count INTEGER;
    mapping_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO entity_count FROM entity_registry;
    SELECT COUNT(*) INTO alias_count FROM entity_aliases;
    SELECT COUNT(*) INTO mapping_count FROM entity_external_mappings;

    RAISE NOTICE 'Seed migration complete: % entities, % aliases, % mappings',
        entity_count, alias_count, mapping_count;
END $$;
