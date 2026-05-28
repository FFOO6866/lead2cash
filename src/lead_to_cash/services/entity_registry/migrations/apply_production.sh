#!/bin/bash
# =============================================================================
# Entity Registry Database Setup for Production
# =============================================================================
# Run this script on the production server to set up the entity registry database.
#
# Usage:
#   # From the production server (rr.kailash.ai):
#   cd /opt/lead-to-cash/current
#   ./src/lead_to_cash/services/entity_registry/migrations/apply_production.sh
#
#   # Or with explicit database URL:
#   ENTITY_REGISTRY_DATABASE_URL=postgresql://user:pass@host:5432/entity_registry \
#       ./src/lead_to_cash/services/entity_registry/migrations/apply_production.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "Entity Registry Database Setup"
echo "=============================================="

# Check if running inside Docker or on host
if [ -f /.dockerenv ]; then
    echo -e "${YELLOW}Running inside Docker container${NC}"
    # Inside container, postgres is accessible via 'postgres' hostname
    DB_HOST="${DB_HOST:-postgres}"
else
    echo -e "${YELLOW}Running on host${NC}"
    # On host, use localhost or specified host
    DB_HOST="${DB_HOST:-localhost}"
fi

# Get database URL from environment or construct it
if [ -n "$ENTITY_REGISTRY_DATABASE_URL" ]; then
    echo "Using ENTITY_REGISTRY_DATABASE_URL from environment"
    DB_URL="$ENTITY_REGISTRY_DATABASE_URL"
else
    # Try to get from docker-compose environment
    DB_USER="${POSTGRES_USER:-lead_to_cash}"
    DB_PASS="${POSTGRES_PASSWORD:-}"
    DB_NAME="entity_registry"

    if [ -z "$DB_PASS" ]; then
        echo -e "${RED}ERROR: POSTGRES_PASSWORD or ENTITY_REGISTRY_DATABASE_URL must be set${NC}"
        exit 1
    fi

    DB_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}"
fi

echo "Database: entity_registry"

# Step 1: Create the database if it doesn't exist
echo ""
echo "Step 1: Creating database (if not exists)..."
echo "---------------------------------------------"

# Extract connection details for admin operations
ADMIN_URL=$(echo "$DB_URL" | sed 's|/entity_registry|/postgres|')

# Check if database exists, create if not
psql "$ADMIN_URL" -tc "SELECT 1 FROM pg_database WHERE datname = 'entity_registry'" | grep -q 1 || \
    psql "$ADMIN_URL" -c "CREATE DATABASE entity_registry"

echo -e "${GREEN}Database ready${NC}"

# Step 2: Apply schema migrations
echo ""
echo "Step 2: Applying schema migrations..."
echo "---------------------------------------------"

for migration in "001_create_entity_registry.sql" "003_add_unique_constraints.sql" "004_fix_index_case_sensitivity.sql"; do
    if [ -f "$MIGRATIONS_DIR/$migration" ]; then
        echo "Applying: $migration"
        psql "$DB_URL" -f "$MIGRATIONS_DIR/$migration" 2>&1 | grep -v "^NOTICE:" || true
        echo -e "${GREEN}  Done${NC}"
    else
        echo -e "${YELLOW}  Skipped (file not found): $migration${NC}"
    fi
done

# Step 3: Verify setup
echo ""
echo "Step 3: Verifying setup..."
echo "---------------------------------------------"

ENTITY_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM entity_registry" 2>/dev/null | tr -d ' ')
ALIAS_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM entity_aliases" 2>/dev/null | tr -d ' ')
MAPPING_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM entity_external_mappings" 2>/dev/null | tr -d ' ')

echo "  Entities: $ENTITY_COUNT"
echo "  Aliases: $ALIAS_COUNT"
echo "  External Mappings: $MAPPING_COUNT"

# Verify extensions
EXTENSIONS=$(psql "$DB_URL" -t -c "SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pg_trgm')" | tr -d ' ' | tr '\n' ', ')
echo "  Extensions: $EXTENSIONS"

echo ""
echo "=============================================="
echo -e "${GREEN}Entity Registry setup complete!${NC}"
echo "=============================================="
echo ""
echo "Test with:"
echo "  psql $DB_URL -c \"SELECT canonical_name, uen FROM entity_registry LIMIT 5\""
