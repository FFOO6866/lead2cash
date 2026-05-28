#!/bin/bash
# =============================================================================
# Apply Unified KB Migrations to Production
# =============================================================================
# Usage: SSH to production server and run this script
#
# Prerequisites:
# 1. Ensure DATABASE_URL is set or use the container network
# 2. Migrations in order: 001, 001b, 002, 002b, 003
#
# Example from rr.kailash.ai:
#   cd /opt/lead-to-cash
#   docker exec -i lead-to-cash-postgres-1 psql -U lead_to_cash -d lead_to_cash < src/lead_to_cash/services/knowledge_base/migrations/apply_production.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="${1:-lead-to-cash-postgres-1}"

echo "============================================================"
echo "Applying Unified KB Migrations to Production"
echo "============================================================"
echo ""

# Function to run migration
run_migration() {
    local file="$1"
    local name="$2"
    echo "Applying: $name"
    docker exec -i "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash < "$SCRIPT_DIR/$file"
    echo "  Done: $name"
    echo ""
}

# Check if base tables exist
echo "Checking existing tables..."
TABLE_EXISTS=$(docker exec "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'kb_manufacturers')")

if [ "$TABLE_EXISTS" = "f" ]; then
    echo "No KB tables found. Running base migration..."
    run_migration "001_create_kb_tables.sql" "001: Base KB Tables"
else
    echo "Base KB tables already exist."
fi

# Check if unique constraints exist
echo "Checking unique constraints..."
CONSTRAINT_EXISTS=$(docker exec "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash -tAc "SELECT EXISTS (SELECT FROM pg_constraint WHERE conname = 'kb_manufacturers_name_key')")

if [ "$CONSTRAINT_EXISTS" = "f" ]; then
    run_migration "001b_add_unique_constraints.sql" "001b: Unique Constraints"
else
    echo "Unique constraints already exist."
fi

# Check if rating tables exist
echo "Checking rating tables..."
RATING_TABLE_EXISTS=$(docker exec "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'kb_engine_ratings')")

if [ "$RATING_TABLE_EXISTS" = "f" ]; then
    run_migration "002_unified_kb_rating_level.sql" "002: Unified KB Rating Tables"
    run_migration "002b_add_constraints.sql" "002b: Check Constraints"
else
    echo "Rating tables already exist."
fi

# Seed data (idempotent with ON CONFLICT)
echo "Seeding engine data..."
run_migration "003_seed_product_data.sql" "003: Seed Engine Data"

# Verify
echo "============================================================"
echo "VERIFICATION"
echo "============================================================"
docker exec "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash -c "
SELECT 'Manufacturers' as entity, COUNT(*) as count FROM kb_manufacturers
UNION ALL
SELECT 'Engine Series', COUNT(*) FROM kb_engine_series
UNION ALL
SELECT 'Engine Models', COUNT(*) FROM kb_engine_models
UNION ALL
SELECT 'Engine Ratings', COUNT(*) FROM kb_engine_ratings;
"

docker exec "$CONTAINER_NAME" psql -U lead_to_cash -d lead_to_cash -c "
SELECT duty_class::text, COUNT(*) as count FROM kb_engine_ratings GROUP BY duty_class ORDER BY duty_class;
"

echo ""
echo "============================================================"
echo "Migration Complete!"
echo "============================================================"
