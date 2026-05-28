-- ============================================================================
-- Entity Registry Database Schema
-- Migration 003: Add unique constraints to prevent race condition duplicates
-- ============================================================================
-- Prevents concurrent requests from creating duplicate entities by adding
-- unique constraints on business identifiers (UEN, LEI).
-- ============================================================================

-- Add unique constraint on UEN (Singapore Unique Entity Number)
-- UEN is globally unique within Singapore, so no duplicates allowed
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_registry_unique_uen
    ON entity_registry (upper(uen))
    WHERE uen IS NOT NULL;

-- Add unique constraint on LEI (Legal Entity Identifier)
-- LEI is globally unique (managed by GLEIF), so no duplicates allowed
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_registry_unique_lei
    ON entity_registry (upper(lei))
    WHERE lei IS NOT NULL;

-- Add unique constraint on CVR (Danish business number)
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_registry_unique_cvr
    ON entity_registry (upper(cvr))
    WHERE cvr IS NOT NULL;

-- Add unique constraint on DUNS number (D&B)
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_registry_unique_duns
    ON entity_registry (duns)
    WHERE duns IS NOT NULL;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON INDEX idx_entity_registry_unique_uen IS
    'Ensures UEN uniqueness to prevent race condition duplicates. '
    'UEN format is case-insensitive (e.g., 199901234A = 199901234a).';

COMMENT ON INDEX idx_entity_registry_unique_lei IS
    'Ensures LEI uniqueness to prevent race condition duplicates. '
    'LEI is a 20-character global identifier from GLEIF.';
