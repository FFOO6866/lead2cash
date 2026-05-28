-- Entity Registry Database Initialization Script
-- Creates the entity_registry database for company identity resolution
-- This runs on first PostgreSQL startup

-- Create the entity_registry database if it doesn't exist
-- Note: This uses a DO block with dynamic SQL since CREATE DATABASE can't be in a transaction
SELECT 'CREATE DATABASE entity_registry'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'entity_registry')\gexec

-- Connect to entity_registry and set up extensions
\c entity_registry

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching

-- Grant permissions to the default user
GRANT ALL ON DATABASE entity_registry TO lead_to_cash;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Entity Registry database initialized successfully';
END $$;
