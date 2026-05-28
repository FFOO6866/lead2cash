"""
Database Migration: Add Embeddings and Retention Tier to Marine Intel

This migration adds:
1. pgvector extension (if not exists)
2. embedding column (vector(1536)) to marine_articles
3. retention_tier column to marine_articles
4. HNSW index for vector similarity search
5. Index on retention_tier

Run this migration for existing deployments before deploying the new code.

Usage:
    python -m lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention

Or import and call:
    from lead_to_cash.services.marine_intel.migrations.v001_add_embeddings_and_retention import run_migration
    await run_migration()
"""

import asyncio
import logging
import os
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "001_add_embeddings_and_retention"
MIGRATION_DESCRIPTION = (
    "Add embedding vector column and retention tier to marine_articles"
)


async def run_migration(database_url: Optional[str] = None) -> dict[str, Any]:
    """
    Run the migration to add embeddings and retention tier support.

    Args:
        database_url: PostgreSQL connection string. Uses DATABASE_URL env var if not provided.

    Returns:
        Migration result with status and details
    """
    db_url = database_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL must be set or provided")

    logger.info(f"Starting migration: {MIGRATION_ID}")
    logger.info(f"Description: {MIGRATION_DESCRIPTION}")

    result: dict[str, Any] = {
        "migration_id": MIGRATION_ID,
        "status": "pending",
        "steps_completed": [],
        "errors": [],
    }

    conn = await asyncpg.connect(db_url)

    try:
        # Step 1: Enable pgvector extension
        logger.info("Step 1: Enabling pgvector extension...")
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            result["steps_completed"].append("pgvector_extension")
            logger.info("pgvector extension enabled")
        except Exception as e:
            error_msg = f"Failed to enable pgvector: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
            # This is critical - cannot continue without pgvector
            result["status"] = "failed"
            return result

        # Step 2: Check if marine_articles table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'marine_articles'
            )
        """
        )

        if not table_exists:
            logger.info("marine_articles table does not exist - migration not needed")
            result["status"] = "skipped"
            result["message"] = (
                "Table does not exist yet. Migration will be applied on first initialization."
            )
            return result

        # Step 3: Add embedding column if not exists
        logger.info("Step 2: Adding embedding column...")
        embedding_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'marine_articles' AND column_name = 'embedding'
            )
        """
        )

        if not embedding_exists:
            await conn.execute(
                "ALTER TABLE marine_articles ADD COLUMN embedding vector(1536)"
            )
            result["steps_completed"].append("embedding_column")
            logger.info("embedding column added")
        else:
            logger.info("embedding column already exists - skipping")
            result["steps_completed"].append("embedding_column_existed")

        # Step 4: Add retention_tier column if not exists
        logger.info("Step 3: Adding retention_tier column...")
        retention_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'marine_articles' AND column_name = 'retention_tier'
            )
        """
        )

        if not retention_exists:
            await conn.execute(
                "ALTER TABLE marine_articles ADD COLUMN retention_tier TEXT DEFAULT 'hot'"
            )
            result["steps_completed"].append("retention_tier_column")
            logger.info("retention_tier column added")
        else:
            logger.info("retention_tier column already exists - skipping")
            result["steps_completed"].append("retention_tier_column_existed")

        # Step 5: Create retention_tier index if not exists
        logger.info("Step 4: Creating retention_tier index...")
        retention_idx_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = 'idx_marine_articles_retention_tier'
            )
        """
        )

        if not retention_idx_exists:
            await conn.execute(
                """
                CREATE INDEX idx_marine_articles_retention_tier
                ON marine_articles(retention_tier)
            """
            )
            result["steps_completed"].append("retention_tier_index")
            logger.info("retention_tier index created")
        else:
            logger.info("retention_tier index already exists - skipping")
            result["steps_completed"].append("retention_tier_index_existed")

        # Step 6: Create HNSW vector index if not exists
        logger.info("Step 5: Creating HNSW vector index...")
        hnsw_idx_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = 'idx_marine_articles_embedding'
            )
        """
        )

        if not hnsw_idx_exists:
            # HNSW index creation can take time on large tables
            await conn.execute(
                """
                CREATE INDEX idx_marine_articles_embedding
                ON marine_articles USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
            )
            result["steps_completed"].append("hnsw_index")
            logger.info("HNSW vector index created")
        else:
            logger.info("HNSW vector index already exists - skipping")
            result["steps_completed"].append("hnsw_index_existed")

        # Step 7: Set default retention_tier for existing rows
        logger.info("Step 6: Setting default retention_tier for existing rows...")
        update_result = await conn.execute(
            """
            UPDATE marine_articles
            SET retention_tier = 'hot'
            WHERE retention_tier IS NULL
        """
        )
        rows_updated = (
            int(update_result.split()[-1]) if "UPDATE" in update_result else 0
        )
        result["steps_completed"].append(f"default_retention_set_{rows_updated}_rows")
        logger.info(f"Set default retention_tier for {rows_updated} rows")

        # Get stats
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_articles,
                COUNT(embedding) as with_embedding,
                COUNT(*) - COUNT(embedding) as without_embedding
            FROM marine_articles
        """
        )

        result["stats"] = {
            "total_articles": stats["total_articles"],
            "with_embedding": stats["with_embedding"],
            "without_embedding": stats["without_embedding"],
        }

        result["status"] = "completed"
        logger.info(f"Migration {MIGRATION_ID} completed successfully")
        logger.info(f"Stats: {result['stats']}")

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg, exc_info=True)
        result["errors"].append(error_msg)
        result["status"] = "failed"

    finally:
        await conn.close()

    return result


async def rollback_migration(database_url: Optional[str] = None) -> dict[str, Any]:
    """
    Rollback the migration (remove added columns and indexes).

    WARNING: This will drop the embedding column and lose all embeddings!

    Args:
        database_url: PostgreSQL connection string.

    Returns:
        Rollback result
    """
    db_url = database_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL must be set or provided")

    logger.warning(f"Rolling back migration: {MIGRATION_ID}")
    logger.warning("WARNING: This will drop embedding data!")

    result: dict[str, Any] = {
        "migration_id": MIGRATION_ID,
        "status": "pending",
        "steps_completed": [],
    }

    conn = await asyncpg.connect(db_url)

    try:
        # Drop HNSW index
        await conn.execute("DROP INDEX IF EXISTS idx_marine_articles_embedding")
        result["steps_completed"].append("dropped_hnsw_index")

        # Drop retention_tier index
        await conn.execute("DROP INDEX IF EXISTS idx_marine_articles_retention_tier")
        result["steps_completed"].append("dropped_retention_index")

        # Drop columns
        await conn.execute(
            "ALTER TABLE marine_articles DROP COLUMN IF EXISTS embedding"
        )
        result["steps_completed"].append("dropped_embedding_column")

        await conn.execute(
            "ALTER TABLE marine_articles DROP COLUMN IF EXISTS retention_tier"
        )
        result["steps_completed"].append("dropped_retention_tier_column")

        result["status"] = "completed"
        logger.info("Rollback completed")

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        logger.error(f"Rollback failed: {e}")

    finally:
        await conn.close()

    return result


def main():
    """CLI entry point for running migration."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        print("Running rollback...")
        result = asyncio.run(rollback_migration())
    else:
        print("Running migration...")
        result = asyncio.run(run_migration())

    print(f"\nResult: {result}")

    if result["status"] == "completed":
        sys.exit(0)
    elif result["status"] == "skipped":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
