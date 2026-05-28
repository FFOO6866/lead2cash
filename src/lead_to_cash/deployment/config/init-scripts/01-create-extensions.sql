-- Lead to Cash Database Initialization Script
-- Extensions and initial setup for PostgreSQL with pgvector
-- NOTE: User and database names must match docker-compose environment variables:
--       POSTGRES_USER=lead_to_cash, POSTGRES_DB=lead_to_cash

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema for application
CREATE SCHEMA IF NOT EXISTS lead_to_cash;

-- Grant permissions (user name matches POSTGRES_USER env var)
GRANT ALL ON SCHEMA lead_to_cash TO lead_to_cash;
GRANT ALL ON ALL TABLES IN SCHEMA lead_to_cash TO lead_to_cash;
GRANT ALL ON ALL SEQUENCES IN SCHEMA lead_to_cash TO lead_to_cash;

-- Set search path (database name matches POSTGRES_DB env var)
ALTER DATABASE lead_to_cash SET search_path TO lead_to_cash, public;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Lead to Cash database extensions initialized successfully';
END $$;
