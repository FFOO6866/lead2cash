#!/usr/bin/env python3
"""
Entity Registry Database Setup Script

Creates the entity_registry database and applies migrations.
Run this script before using the entity resolution service.

Usage:
    # From project root with venv activated:
    python -m lead_to_cash.services.entity_registry.setup_database

    # Or with explicit database URL:
    ENTITY_REGISTRY_DATABASE_URL=postgresql://user:pass@localhost:5432/entity_registry \
        python -m lead_to_cash.services.entity_registry.setup_database

    # To also seed initial data:
    python -m lead_to_cash.services.entity_registry.setup_database --seed
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Migration files in order
# Schema migrations run always, seed runs only with --seed
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
SCHEMA_MIGRATIONS = [
    "001_create_entity_registry.sql",
    "003_add_unique_constraints.sql",  # Unique constraints for UEN/LEI
    "004_fix_index_case_sensitivity.sql",  # Fix indexes to use upper() for queries
]
SEED_MIGRATIONS = [
    "005_seed_known_entities.sql",  # Seed known companies for fast local matching
]


def load_env():
    """Load environment variables from .env file."""
    env_paths = [
        Path(__file__).parent.parent.parent / ".env",  # src/lead_to_cash/.env
        Path(__file__).parent.parent.parent.parent.parent / ".env",  # project root .env
    ]

    for env_path in env_paths:
        if env_path.exists():
            logger.info(f"Loading environment from {env_path}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip())
            break


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("ENTITY_REGISTRY_DATABASE_URL")
    if not url:
        # Try to construct from main database URL
        main_url = os.getenv("DATABASE_URL", "")
        if main_url:
            # Replace database name with entity_registry
            if "/lead_to_cash" in main_url:
                url = main_url.replace("/lead_to_cash_dev", "/entity_registry")
                url = url.replace("/lead_to_cash", "/entity_registry")
            else:
                # Append entity_registry to base URL
                base = main_url.rsplit("/", 1)[0]
                url = f"{base}/entity_registry"
    return url or ""


def get_admin_url(db_url: str) -> str:
    """Get admin URL (postgres database) for creating new database."""
    # Replace database name with 'postgres' for admin operations
    if "/" in db_url:
        base = db_url.rsplit("/", 1)[0]
        return f"{base}/postgres"
    return db_url


async def database_exists(admin_url: str, db_name: str) -> bool:
    """Check if database exists."""
    try:
        conn = await asyncpg.connect(admin_url)
        try:
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            return result is not None
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to check database existence: {e}")
        return False


async def create_database(admin_url: str, db_name: str) -> bool:
    """Create the database if it doesn't exist."""
    try:
        conn = await asyncpg.connect(admin_url)
        try:
            # Check if exists
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            if exists:
                logger.info(f"Database '{db_name}' already exists")
                return True

            # Create database
            logger.info(f"Creating database '{db_name}'...")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database '{db_name}' created successfully")
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        return False


async def run_migration(db_url: str, migration_file: Path) -> bool:
    """Run a single migration file."""
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    logger.info(f"Running migration: {migration_file.name}")

    try:
        conn = await asyncpg.connect(db_url)
        try:
            sql = migration_file.read_text()
            await conn.execute(sql)
            logger.info(f"Migration {migration_file.name} completed")
            return True
        finally:
            await conn.close()
    except asyncpg.exceptions.DuplicateObjectError as e:
        logger.warning(
            f"Migration {migration_file.name}: Object already exists (skipping): {e}"
        )
        return True
    except Exception as e:
        logger.error(f"Migration {migration_file.name} failed: {e}")
        return False


async def verify_setup(db_url: str) -> bool:
    """Verify the database is set up correctly."""
    try:
        conn = await asyncpg.connect(db_url)
        try:
            # Check tables exist
            tables = await conn.fetch(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('entity_registry', 'entity_aliases',
                                   'entity_external_mappings', 'entity_resolution_history')
            """
            )
            table_names = [t["table_name"] for t in tables]

            expected = [
                "entity_registry",
                "entity_aliases",
                "entity_external_mappings",
                "entity_resolution_history",
            ]
            missing = set(expected) - set(table_names)

            if missing:
                logger.error(f"Missing tables: {missing}")
                return False

            # Check pg_trgm extension
            ext = await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
            )
            if not ext:
                logger.error("pg_trgm extension not installed")
                return False

            # Check unique constraints exist
            unique_indexes = await conn.fetch(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'entity_registry'
                AND indexname IN (
                    'idx_entity_registry_unique_uen',
                    'idx_entity_registry_unique_lei'
                )
            """
            )
            idx_names = [i["indexname"] for i in unique_indexes]
            if "idx_entity_registry_unique_uen" not in idx_names:
                logger.warning("Unique UEN constraint not found - run migration 003")
            if "idx_entity_registry_unique_lei" not in idx_names:
                logger.warning("Unique LEI constraint not found - run migration 003")

            # Count entities
            count = await conn.fetchval("SELECT COUNT(*) FROM entity_registry")
            logger.info(f"Entity registry has {count} entities")

            alias_count = await conn.fetchval("SELECT COUNT(*) FROM entity_aliases")
            logger.info(f"Entity aliases has {alias_count} aliases")

            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


async def main(seed: bool = False, schema_only: bool = False):
    """Main setup function."""
    load_env()

    db_url = get_database_url()
    if not db_url:
        logger.error(
            "ENTITY_REGISTRY_DATABASE_URL not set. "
            "Set it in .env or as environment variable."
        )
        sys.exit(1)

    logger.info(
        f"Database URL: {db_url.replace(db_url.split('@')[0].split('://')[-1], '***:***')}"
    )

    # Extract database name
    db_name = db_url.rsplit("/", 1)[-1]
    if "?" in db_name:
        db_name = db_name.split("?")[0]

    admin_url = get_admin_url(db_url)

    # Step 1: Create database
    if not await create_database(admin_url, db_name):
        logger.error("Failed to create database")
        sys.exit(1)

    # Step 2: Run schema migrations
    for migration_file in SCHEMA_MIGRATIONS:
        migration_path = MIGRATIONS_DIR / migration_file
        if not await run_migration(db_url, migration_path):
            logger.error(f"Schema migration {migration_file} failed")
            sys.exit(1)

    # Step 3: Run seed migrations if requested
    if seed and not schema_only:
        for migration_file in SEED_MIGRATIONS:
            migration_path = MIGRATIONS_DIR / migration_file
            if not await run_migration(db_url, migration_path):
                logger.warning(
                    f"Seed migration {migration_file} had issues (may be already seeded)"
                )

    # Step 4: Verify setup
    if await verify_setup(db_url):
        logger.info("=" * 50)
        logger.info("Entity registry database setup complete!")
        logger.info("=" * 50)
    else:
        logger.error("Setup verification failed")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up entity registry database")
    parser.add_argument(
        "--seed", action="store_true", help="Also run seed migration with initial data"
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Only run schema migration, skip seed",
    )
    args = parser.parse_args()

    asyncio.run(main(seed=args.seed, schema_only=args.schema_only))
