#!/usr/bin/env python
"""
Knowledge Base CLI

Command-line tools for managing the Marine Engine Knowledge Base.

Commands:
    migrate   - Run database migrations
    seed      - Seed the knowledge base with data
    backfill  - Backfill embeddings for aliases
    health    - Check KB service health
    stats     - Show KB statistics
    quality   - Run data quality checks

Usage:
    python -m lead_to_cash.services.knowledge_base.cli migrate
    python -m lead_to_cash.services.knowledge_base.cli seed
    python -m lead_to_cash.services.knowledge_base.cli backfill
    python -m lead_to_cash.services.knowledge_base.cli health
    python -m lead_to_cash.services.knowledge_base.cli stats
    python -m lead_to_cash.services.knowledge_base.cli quality
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL environment variable not set")
        logger.info("Set DATABASE_URL to your PostgreSQL connection string")
        logger.info("Example: postgresql://user:password@localhost:5432/dbname")
        sys.exit(1)
    return url


async def cmd_migrate(args: argparse.Namespace) -> int:
    """Run database migrations."""
    import asyncpg

    database_url = get_database_url()
    logger.info("Running Knowledge Base migrations...")

    # Get migration files directory
    migrations_dir = Path(__file__).parent.parent / "migrations"
    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return 1

    # Find all SQL migration files (exclude macOS resource forks)
    migration_files = sorted(
        f for f in migrations_dir.glob("*.sql") if not f.name.startswith("._")
    )
    if not migration_files:
        logger.warning("No migration files found")
        return 0

    logger.info(f"Found {len(migration_files)} migration file(s)")

    # Connect to database
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return 1

    try:
        # Create migrations tracking table if not exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Get already applied migrations
        applied = await conn.fetch("SELECT filename FROM kb_migrations")
        applied_set = {row["filename"] for row in applied}

        # Apply pending migrations
        applied_count = 0
        for migration_file in migration_files:
            filename = migration_file.name

            if filename in applied_set:
                logger.debug(f"Skipping already applied: {filename}")
                continue

            logger.info(f"Applying migration: {filename}")

            # Read and execute migration
            sql = migration_file.read_text()

            try:
                # Execute migration in transaction
                async with conn.transaction():
                    await conn.execute(sql)

                    # Record migration
                    await conn.execute(
                        "INSERT INTO kb_migrations (filename) VALUES ($1)", filename
                    )

                logger.info(f"Applied: {filename}")
                applied_count += 1

            except Exception as e:
                logger.error(f"Failed to apply {filename}: {e}")
                return 1

        if applied_count > 0:
            logger.info(f"Successfully applied {applied_count} migration(s)")
        else:
            logger.info("No new migrations to apply")

        return 0

    finally:
        await conn.close()


async def cmd_seed(args: argparse.Namespace) -> int:
    """Seed the knowledge base with data."""
    from lead_to_cash.services.knowledge_base.database import get_knowledge_base_db
    from lead_to_cash.services.knowledge_base.seed_data import seed_knowledge_base

    logger.info("Seeding Knowledge Base...")

    try:
        # Initialize database
        db = get_knowledge_base_db()
        await db.initialize()

        # Run seed
        counts = await seed_knowledge_base(db)

        logger.info("Seed complete:")
        logger.info(f"  Manufacturers: {counts.get('manufacturers', 0)}")
        logger.info(f"  Engine Series: {counts.get('series', 0)}")
        logger.info(f"  Engine Models: {counts.get('models', 0)}")
        logger.info(f"  Aliases: {counts.get('aliases', 0)}")

        return 0

    except Exception as e:
        logger.error(f"Seed failed: {e}")
        return 1


async def cmd_backfill(args: argparse.Namespace) -> int:
    """Backfill embeddings for aliases."""
    from lead_to_cash.services.knowledge_base.embedding_service import (
        get_kb_embedding_service,
    )

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        return 1

    logger.info("Backfilling embeddings for KB aliases...")

    try:
        # Initialize embedding service
        service = get_kb_embedding_service()
        await service.initialize()

        # Get initial stats
        stats = await service.get_embedding_stats()
        logger.info(f"Before: {stats['without_embedding']} aliases need embeddings")

        # Run backfill
        batch_size = args.batch_size or 100
        total = await service.backfill_all_embeddings(batch_size=batch_size)

        logger.info(f"Backfilled {total} embeddings")

        # Get final stats
        stats = await service.get_embedding_stats()
        logger.info(f"After: {stats['coverage_percent']}% coverage")

        return 0

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        return 1


async def cmd_health(args: argparse.Namespace) -> int:
    """Check KB service health."""
    from lead_to_cash.services.knowledge_base.database import get_knowledge_base_db
    from lead_to_cash.services.knowledge_base.embedding_service import (
        get_kb_embedding_service,
    )

    logger.info("Checking Knowledge Base health...")

    results = {}

    # Check database
    try:
        db = get_knowledge_base_db()
        await db.initialize()
        health = await db.health_check()
        results["database"] = health
        status = "OK" if health.get("healthy") else "FAIL"
        logger.info(f"Database: {status}")
    except Exception as e:
        results["database"] = {"healthy": False, "error": str(e)}
        logger.error(f"Database: FAIL - {e}")

    # Check embedding service (only if API key is set)
    if os.getenv("OPENAI_API_KEY"):
        try:
            embedding = get_kb_embedding_service()
            await embedding.initialize()
            stats = await embedding.get_embedding_stats()
            results["embeddings"] = stats
            logger.info(f"Embeddings: OK - {stats['coverage_percent']}% coverage")
        except Exception as e:
            results["embeddings"] = {"error": str(e)}
            logger.error(f"Embeddings: FAIL - {e}")
    else:
        results["embeddings"] = {
            "status": "skipped",
            "reason": "OPENAI_API_KEY not set",
        }
        logger.info("Embeddings: SKIPPED (no API key)")

    # Overall status
    all_healthy = all(
        r.get("healthy", True) or r.get("status") == "skipped" for r in results.values()
    )

    if args.json:
        import json

        print(json.dumps(results, indent=2, default=str))

    return 0 if all_healthy else 1


async def cmd_stats(args: argparse.Namespace) -> int:
    """Show KB statistics."""
    from lead_to_cash.services.knowledge_base.database import get_knowledge_base_db

    logger.info("Knowledge Base Statistics")
    logger.info("=" * 40)

    try:
        db = get_knowledge_base_db()
        await db.initialize()

        health = await db.health_check()
        counts = health.get("counts", {})

        print(f"\nManufacturers: {counts.get('manufacturers', 'N/A')}")
        print(f"Engine Series: {counts.get('engine_series', 'N/A')}")
        print(f"Engine Models: {counts.get('engine_models', 'N/A')}")
        print(f"Aliases: {counts.get('aliases', 'N/A')}")
        print(f"Article Scores: {counts.get('article_scores', 'N/A')}")

        # Check embedding coverage if available
        if os.getenv("OPENAI_API_KEY"):
            from lead_to_cash.services.knowledge_base.embedding_service import (
                get_kb_embedding_service,
            )

            embedding = get_kb_embedding_service()
            await embedding.initialize()
            stats = await embedding.get_embedding_stats()
            print(f"\nEmbedding Coverage: {stats['coverage_percent']}%")
            print(f"  With embedding: {stats['with_embedding']}")
            print(f"  Without embedding: {stats['without_embedding']}")

        return 0

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return 1


async def cmd_quality(args: argparse.Namespace) -> int:
    """Run data quality checks."""
    from lead_to_cash.services.knowledge_base.data_quality import (
        get_data_quality_validator,
    )

    logger.info("Running Knowledge Base data quality checks...")

    try:
        validator = get_data_quality_validator()
        await validator.initialize()

        report = await validator.generate_quality_report()

        print(f"\n{'='*60}")
        print("KB DATA QUALITY REPORT")
        print(f"{'='*60}")
        print(f"Generated: {report.generated_at}")
        print(f"\nHealth Score: {report.summary['health_score']}/100")
        print(f"\nTotal Issues: {report.total_issues}")
        print(f"  Critical: {report.critical_count}")
        print(f"  Warning:  {report.warning_count}")
        print(f"  Info:     {report.info_count}")

        print("\nIssues by Category:")
        for category, count in report.summary["issues_by_category"].items():
            print(f"  {category}: {count}")

        print("\nEntity Counts:")
        for entity_type, count in report.summary["entity_counts"].items():
            print(f"  {entity_type}: {count}")

        if args.verbose and report.issues:
            print(f"\n{'='*60}")
            print("ISSUE DETAILS (first 20)")
            print(f"{'='*60}")
            for issue in report.issues[:20]:
                print(f"\n[{issue.severity.upper()}] {issue.category}")
                print(f"  Entity: {issue.entity_type} ({issue.entity_id})")
                print(f"  {issue.description}")
                print(f"  Action: {issue.suggested_action}")
                if issue.details:
                    print(f"  Details: {issue.details}")

        if args.json:
            import json

            print(f"\n{'='*60}")
            print("JSON OUTPUT")
            print(f"{'='*60}")
            print(json.dumps(report.to_dict(), indent=2))

        # Return non-zero if critical issues found
        return 1 if report.critical_count > 0 else 0

    except Exception as e:
        logger.error(f"Quality check failed: {e}")
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Knowledge Base CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # migrate command
    subparsers.add_parser("migrate", help="Run database migrations")

    # seed command
    subparsers.add_parser("seed", help="Seed the knowledge base with data")

    # backfill command
    backfill_parser = subparsers.add_parser(
        "backfill", help="Backfill embeddings for aliases"
    )
    backfill_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for embedding generation (default: 100)",
    )

    # health command
    health_parser = subparsers.add_parser("health", help="Check KB service health")
    health_parser.add_argument(
        "--json", action="store_true", help="Output health status as JSON"
    )

    # stats command
    subparsers.add_parser("stats", help="Show KB statistics")

    # quality command
    quality_parser = subparsers.add_parser("quality", help="Run data quality checks")
    quality_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed issue information"
    )
    quality_parser.add_argument(
        "--json", action="store_true", help="Output full report as JSON"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    commands = {
        "migrate": cmd_migrate,
        "seed": cmd_seed,
        "backfill": cmd_backfill,
        "health": cmd_health,
        "stats": cmd_stats,
        "quality": cmd_quality,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        return asyncio.run(cmd_func(args))

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
