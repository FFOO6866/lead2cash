-- ============================================================================
-- Entity Registry Database Schema
-- Migration 004: Fix regular indexes to match query case sensitivity
-- ============================================================================
-- The queries use upper(uen) and upper(lei) for case-insensitive lookups,
-- but the original indexes were on raw uen/lei columns. This migration
-- drops the old indexes and creates new ones that match the query pattern.
-- ============================================================================

-- Drop old indexes that don't match query patterns
DROP INDEX IF EXISTS idx_entity_registry_uen;
DROP INDEX IF EXISTS idx_entity_registry_lei;

-- Create new indexes that match the upper() function used in queries
-- These support efficient lookups like: WHERE upper(uen) = 'ABC123'
CREATE INDEX IF NOT EXISTS idx_entity_registry_uen
    ON entity_registry (upper(uen))
    WHERE uen IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entity_registry_lei
    ON entity_registry (upper(lei))
    WHERE lei IS NOT NULL;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON INDEX idx_entity_registry_uen IS
    'Functional index on upper(uen) for case-insensitive UEN lookups. '
    'Matches query pattern: WHERE upper(uen) = $1';

COMMENT ON INDEX idx_entity_registry_lei IS
    'Functional index on upper(lei) for case-insensitive LEI lookups. '
    'Matches query pattern: WHERE upper(lei) = $1';
