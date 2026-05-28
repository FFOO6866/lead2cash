"""
Daily Scheduler for Marine Sales Intelligence

Runs scheduled jobs to research marine engine sales opportunities:
- Daily research at 2 AM SGT (18:00 UTC previous day)
- Targets Singapore and Asia-Pacific markets

Production Features:
- Job idempotency (prevents duplicate runs)
- Proper error handling (no silent failures)
- Job recovery and retry logic
- Comprehensive logging

Uses APScheduler for production-ready async scheduling.
Integrates with MarineIntelAgent for Perplexity-based research.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from lead_to_cash.services.marine_intel.models import ResearchJob

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None

# Job lock to prevent concurrent execution
_job_locks: dict[str, datetime] = {}
_LOCK_TTL_SECONDS = 3600  # 1 hour lock timeout


def _get_idempotency_key(job_type: str, date: Optional[datetime] = None) -> str:
    """Generate idempotency key for a job."""
    if date is None:
        date = datetime.now(timezone.utc)
    return f"{job_type}_{date.strftime('%Y-%m-%d')}"


def _acquire_lock(job_key: str) -> bool:
    """
    Acquire a lock for a job. Returns True if lock acquired.

    Uses in-memory locking. For multi-instance deployments,
    consider using Redis or database-based locking.
    """
    now = datetime.now(timezone.utc)

    # Check if lock exists and is still valid
    if job_key in _job_locks:
        lock_time = _job_locks[job_key]
        if (now - lock_time).total_seconds() < _LOCK_TTL_SECONDS:
            logger.warning(f"Job {job_key} is already running (locked at {lock_time})")
            return False
        else:
            logger.info(f"Job {job_key} lock expired, acquiring new lock")

    _job_locks[job_key] = now
    return True


def _release_lock(job_key: str) -> None:
    """Release a job lock."""
    if job_key in _job_locks:
        del _job_locks[job_key]


async def daily_marine_intel_job() -> dict:
    """
    Daily marine sales intelligence research job.

    Runs at 2 AM SGT (18:00 UTC previous day) every day:
    1. Queries Perplexity API for marine industry news
    2. Extracts structured opportunities using LLM
    3. Deduplicates by URL hash
    4. Stores in PostgreSQL

    Features:
    - Idempotency: Won't run twice on the same day
    - Recovery: Retries failed API calls
    - Logging: Comprehensive audit trail

    Returns:
        Job result statistics
    """
    from lead_to_cash.agents.marine_intel_agent import (
        MarineIntelAgent,
        MarineIntelConfig,
    )
    from lead_to_cash.services.marine_intel.database import get_marine_intel_db

    # Generate idempotency key for today
    job_key = _get_idempotency_key("daily_research")

    # Check for existing completed job today
    db = get_marine_intel_db()

    # Initialize database - fail loudly if this doesn't work
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            raise RuntimeError(
                f"Cannot start job - database initialization failed: {e}"
            )

    # Clean up any stale jobs from previous container restarts
    try:
        stale_count = await db.cleanup_stale_jobs(stale_minutes=10)
        if stale_count > 0:
            logger.info(
                f"Cleaned up {stale_count} stale jobs before starting new research"
            )
    except Exception as e:
        logger.warning(f"Could not cleanup stale jobs: {e}")

    # Check if job already completed today (idempotency)
    try:
        existing_jobs = await db.list_jobs(job_type="daily_research", limit=1)
        if existing_jobs:
            latest = existing_jobs[0]
            if (
                latest.status == "completed"
                and latest.started_at.date() == datetime.now(timezone.utc).date()
            ):
                logger.info(f"Daily job already completed today (job_id={latest.id})")
                return {
                    "job_id": latest.id,
                    "status": "skipped",
                    "reason": "already_completed_today",
                    "original_result": {
                        "articles_processed": latest.articles_processed,
                        "opportunities_found": latest.opportunities_found,
                    },
                }
    except Exception as e:
        logger.warning(f"Could not check for existing jobs: {e}")

    # Acquire lock to prevent concurrent execution
    if not _acquire_lock(job_key):
        return {
            "status": "skipped",
            "reason": "concurrent_execution",
            "message": "Another instance of this job is already running",
        }

    logger.info(f"Starting daily marine sales intelligence research (key={job_key})")

    # Create job record
    job = ResearchJob(
        id=job_key,  # Use idempotency key as job ID
        job_type="daily_research",
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    await db.save_job(job)

    # Initialize counters
    queries_executed = 0
    total_articles = 0
    total_opportunities = 0
    duplicates_skipped = 0
    errors = 0

    try:
        # Initialize marine intel agent
        config = MarineIntelConfig()

        async with MarineIntelAgent(config) as agent:
            # Run comprehensive daily research
            logger.info("Running daily research across all categories")
            result = await agent.run_daily_research()

            # Extract all statistics from agent result
            queries_executed = result.get("queries_executed", 0)
            total_articles = result.get("articles_processed", 0)
            total_opportunities = result.get("opportunities_found", 0)
            duplicates_skipped = result.get("duplicates_skipped", 0)
            errors = result.get("errors", 0)

            logger.info(
                f"Daily research complete: {queries_executed} queries, "
                f"{total_articles} articles, {total_opportunities} opportunities, "
                f"{duplicates_skipped} duplicates, {errors} errors"
            )

        # Update job status with all statistics
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.queries_executed = queries_executed
        job.articles_processed = total_articles
        job.opportunities_found = total_opportunities
        job.duplicates_skipped = duplicates_skipped
        job.errors = errors

    except Exception as e:
        logger.error(f"Daily marine intel job failed: {e}", exc_info=True)
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)
        errors += 1

    finally:
        # Always save job status and release lock
        try:
            await db.save_job(job)
        except Exception as save_error:
            logger.error(f"Failed to save job status: {save_error}")

        _release_lock(job_key)

    result = {
        "job_id": job.id,
        "status": job.status,
        "queries_executed": queries_executed,
        "articles_processed": total_articles,
        "opportunities_found": total_opportunities,
        "duplicates_skipped": duplicates_skipped,
        "errors": errors,
        "duration_seconds": (
            (job.completed_at - job.started_at).total_seconds()
            if job.completed_at
            else 0
        ),
    }

    logger.info(f"Daily marine intel job complete: {result}")
    return result


async def targeted_research_job(
    region: Optional[str] = None,
    sector: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Run targeted research for specific region, sector, or category.

    Args:
        region: Target region (e.g., "singapore", "indonesia")
        sector: Target sector (e.g., "marine_transportation", "offshore_oil_gas")
        category: Research category (e.g., "newbuild", "retrofit_repower")

    Returns:
        Job result statistics
    """
    from lead_to_cash.agents.marine_intel_agent import (
        MarineIntelAgent,
        MarineIntelConfig,
    )
    from lead_to_cash.services.marine_intel.database import get_marine_intel_db

    # Generate unique job ID for targeted research
    job_id = f"targeted_{region or 'all'}_{sector or 'all'}_{category or 'all'}_{uuid.uuid4().hex[:8]}"

    logger.info(
        f"Starting targeted research: region={region}, sector={sector}, category={category}"
    )

    job = ResearchJob(
        id=job_id,
        job_type="targeted_research",
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    db = get_marine_intel_db()

    # Initialize database - fail loudly if this doesn't work
    try:
        await db.initialize()
    except Exception as e:
        if "already exists" not in str(e).lower():
            logger.error(f"Database initialization failed: {e}")
            raise RuntimeError(
                f"Cannot start job - database initialization failed: {e}"
            )

    await db.save_job(job)

    # Initialize counters
    opportunities_found = 0
    errors_count = 0

    try:
        config = MarineIntelConfig()

        async with MarineIntelAgent(config) as agent:
            # Build custom queries from category if specified
            custom_queries = None
            if category:
                # Map category to specific research queries
                category_queries = {
                    "newbuild": [
                        f"shipyard contract awarded newbuild vessel {region or 'Singapore Asia'} 2026",
                        f"new vessel order ferry OSV tug {region or 'Southeast Asia'} 2026",
                        f"shipbuilding tender announcement {region or 'Asia Pacific'} marine",
                    ],
                    "retrofit_repower": [
                        f"engine repower retrofit vessel {region or 'Singapore'} 2026",
                        f"vessel modernization engine upgrade {region or 'Southeast Asia'}",
                        f"IMO Tier III retrofit SCR EGR {region or 'Asia'} ship",
                    ],
                    "offshore": [
                        f"FID final investment decision offshore {region or 'Indonesia Malaysia Australia'} 2026",
                        f"EPCIC contract FPSO OSV {region or 'Southeast Asia'} sanctioned",
                        f"offshore vessel charter contract {region or 'Asia Pacific'} awarded",
                    ],
                    "fuel_transition": [
                        f"LNG methanol ammonia dual fuel vessel order {region or 'Asia'} 2026",
                        f"dual fuel engine conversion retrofit {region or 'Singapore'} ship",
                        f"alternative fuel vessel newbuild {region or 'Southeast Asia'}",
                    ],
                    "fleet_expansion": [
                        f"fleet expansion ferry operator {region or 'Singapore Indonesia'} vessel order",
                        f"shipping company fleet growth new vessels {region or 'Asia Pacific'}",
                        f"harbour craft operator expansion {region or 'Singapore'} 2026",
                    ],
                    "incidents": [
                        f"engine failure vessel {region or 'Singapore'} ferry investigation",
                        f"ship machinery breakdown {region or 'Southeast Asia'} marine",
                        f"vessel grounding collision {region or 'Asia'} investigation report",
                    ],
                }
                custom_queries = category_queries.get(
                    category,
                    [f"{category} marine vessel {region or 'Asia Pacific'} 2026"],
                )

            opportunities = await agent.run_targeted_research(
                region=region,
                sector=sector,
                custom_queries=custom_queries,
            )
            opportunities_found = len(opportunities) if opportunities else 0

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.queries_executed = (
                len(custom_queries) if custom_queries else 4
            )  # Default 4 queries
            job.articles_processed = job.queries_executed  # 1 article per query
            job.opportunities_found = opportunities_found
            job.errors = 0

    except Exception as e:
        logger.error(f"Targeted research failed: {e}", exc_info=True)
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)
        errors_count = 1

    finally:
        try:
            await db.save_job(job)
        except Exception as save_error:
            logger.error(f"Failed to save job status: {save_error}")

    return {
        "job_id": job.id,
        "status": job.status,
        "queries_executed": getattr(job, "queries_executed", 0),
        "articles_processed": getattr(job, "articles_processed", 0),
        "opportunities_found": opportunities_found,
        "errors": errors_count,
        "filters": {
            "region": region,
            "sector": sector,
            "category": category,
        },
    }


def get_marine_scheduler() -> AsyncIOScheduler:
    """Get or create the marine intel scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_marine_scheduler() -> AsyncIOScheduler:
    """
    Start the marine sales intelligence scheduler.

    Adds scheduled jobs:
    - Daily research at 2 AM SGT (18:00 UTC previous day)
    - Daily embedding backfill at 3 AM SGT (19:00 UTC)
    - Weekly retention cleanup at 2 AM SGT on Sundays (Sat 18:00 UTC)

    Returns:
        Started scheduler instance
    """
    scheduler = get_marine_scheduler()

    # Daily research at 2 AM SGT = 18:00 UTC previous day
    scheduler.add_job(
        daily_marine_intel_job,
        CronTrigger(hour=18, minute=0, timezone="UTC"),
        id="daily_marine_intel_research",
        replace_existing=True,
        name="Daily Marine Sales Intelligence Research",
        misfire_grace_time=3600,  # Allow 1 hour grace period for misfires
        coalesce=True,  # Coalesce multiple misfired runs into one
    )
    logger.info("Scheduled daily marine intel job at 2:00 AM SGT (18:00 UTC)")

    # Daily RSS scraping at 4 AM SGT = 20:00 UTC
    scheduler.add_job(
        daily_rss_scraping_job,
        CronTrigger(hour=20, minute=0, timezone="UTC"),
        id="daily_rss_scraping",
        replace_existing=True,
        name="Daily RSS Feed Scraping",
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Scheduled daily RSS scraping job at 4:00 AM SGT (20:00 UTC)")

    # Daily embedding backfill at 5 AM SGT = 21:00 UTC (after RSS scraping)
    scheduler.add_job(
        embedding_backfill_job,
        CronTrigger(hour=21, minute=0, timezone="UTC"),
        id="daily_embedding_backfill",
        replace_existing=True,
        name="Daily Embedding Backfill",
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Scheduled daily embedding backfill job at 5:00 AM SGT (21:00 UTC)")

    # Weekly retention cleanup on Sundays at 2 AM SGT = Sat 18:00 UTC
    scheduler.add_job(
        retention_cleanup_job,
        CronTrigger(day_of_week="sat", hour=18, minute=0, timezone="UTC"),
        id="weekly_retention_cleanup",
        replace_existing=True,
        name="Weekly Retention Cleanup",
        misfire_grace_time=7200,  # 2 hour grace for weekly job
        coalesce=True,
    )
    logger.info(
        "Scheduled weekly retention cleanup job at 2:00 AM SGT on Sundays (Sat 18:00 UTC)"
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Marine sales intelligence scheduler started")

    return scheduler


def stop_marine_scheduler() -> None:
    """Stop the marine intel scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Marine sales intelligence scheduler stopped")
    _scheduler = None


async def run_manual_research() -> dict:
    """
    Run a manual daily research (triggered by API call).

    Returns:
        Research job result
    """
    return await daily_marine_intel_job()


async def run_manual_targeted_research(
    region: Optional[str] = None,
    sector: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Run a manual targeted research.

    Args:
        region: Target region
        sector: Target sector
        category: Research category

    Returns:
        Research job result
    """
    return await targeted_research_job(region, sector, category)


async def retry_failed_jobs(max_retries: int = 3) -> list[dict]:
    """
    Retry failed jobs from the last 24 hours.

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        List of retry results
    """
    from lead_to_cash.services.marine_intel.database import get_marine_intel_db

    db = get_marine_intel_db()
    results = []

    try:
        # Get failed jobs from last 24 hours
        failed_jobs = await db.list_jobs(status="failed", limit=10)

        for job in failed_jobs:
            # Skip if too old (> 24 hours)
            if (datetime.now(timezone.utc) - job.started_at) > timedelta(hours=24):
                continue

            logger.info(f"Retrying failed job: {job.id}")

            if job.job_type == "daily_research":
                result = await daily_marine_intel_job()
            else:
                # Parse job ID for targeted research parameters
                result = await targeted_research_job()

            results.append({"original_job_id": job.id, "retry_result": result})

    except Exception as e:
        logger.error(f"Error retrying failed jobs: {e}")

    return results


# =============================================================================
# Embedding and Retention Jobs
# =============================================================================


async def daily_rss_scraping_job() -> dict:
    """
    Daily RSS feed scraping job.

    Scheduled to run daily at 4 AM SGT (20:00 UTC):
    1. Scrapes all configured RSS feeds from source registry
    2. Saves new articles to marine_articles database
    3. Generates embeddings for new articles

    Returns:
        Job result statistics
    """
    job_key = _get_idempotency_key("daily_rss_scraping")

    # Acquire lock
    if not _acquire_lock(job_key):
        return {
            "status": "skipped",
            "reason": "concurrent_execution",
        }

    logger.info(f"Starting daily RSS scraping job (key={job_key})")

    try:
        from lead_to_cash.services.marine_intel.embedding_service import (
            initialize_marine_embedding_service,
        )
        from lead_to_cash.services.scraping_orchestrator import run_phase1_scraping

        # Run RSS scraping
        result = await run_phase1_scraping()

        # Generate embeddings for new articles
        embedding_service = await initialize_marine_embedding_service()
        embedding_result = await embedding_service.backfill_missing_embeddings(
            batch_size=50, max_articles=200
        )
        await embedding_service.close()

        logger.info(
            f"Daily RSS scraping complete: {result.rss_articles_saved} RSS articles, "
            f"{result.press_items_saved} press items, "
            f"{embedding_result.get('articles_processed', 0)} embeddings generated"
        )

        return {
            "job_id": job_key,
            "status": "completed",
            "rss_articles_saved": result.rss_articles_saved,
            "press_items_saved": result.press_items_saved,
            "embeddings_generated": embedding_result.get("articles_processed", 0),
            "duration_seconds": result.total_duration_seconds,
        }

    except Exception as e:
        logger.error(f"Daily RSS scraping job failed: {e}", exc_info=True)
        return {
            "job_id": job_key,
            "status": "failed",
            "error": str(e),
        }

    finally:
        _release_lock(job_key)


async def embedding_backfill_job() -> dict:
    """
    Backfill embeddings for articles that don't have them.

    Scheduled to run daily at 3 AM UTC. Processes articles in batches
    to avoid overwhelming the OpenAI API.

    Returns:
        Job result statistics
    """
    job_key = _get_idempotency_key("embedding_backfill")

    # Acquire lock
    if not _acquire_lock(job_key):
        return {
            "status": "skipped",
            "reason": "concurrent_execution",
        }

    logger.info(f"Starting embedding backfill job (key={job_key})")

    try:
        from lead_to_cash.services.marine_intel.embedding_service import (
            get_marine_embedding_service,
        )

        service = get_marine_embedding_service()
        result = await service.backfill_missing_embeddings(
            batch_size=50,
            max_articles=500,  # Process up to 500 per run
        )

        logger.info(
            f"Embedding backfill complete: {result['articles_processed']} processed, "
            f"{result['errors']} errors"
        )

        return {
            "job_id": job_key,
            "status": "completed",
            **result,
        }

    except Exception as e:
        logger.error(f"Embedding backfill job failed: {e}", exc_info=True)
        return {
            "job_id": job_key,
            "status": "failed",
            "error": str(e),
        }

    finally:
        _release_lock(job_key)


async def retention_cleanup_job() -> dict:
    """
    Run retention tier transitions and cleanup old data.

    Scheduled to run weekly on Sundays at 2 AM UTC:
    - Hot → Warm: Articles > 12 months old
    - Warm → Cold: Articles > 24 months old
    - Delete: Articles > 36 months old

    Returns:
        Job result statistics
    """
    job_key = _get_idempotency_key("retention_cleanup")

    # Acquire lock
    if not _acquire_lock(job_key):
        return {
            "status": "skipped",
            "reason": "concurrent_execution",
        }

    logger.info(f"Starting retention cleanup job (key={job_key})")

    try:
        from lead_to_cash.services.marine_intel.retention_service import (
            get_retention_service,
        )

        service = get_retention_service()
        result = await service.run_retention_job()

        logger.info(
            f"Retention cleanup complete: "
            f"hot→warm={result.hot_to_warm}, "
            f"warm→cold={result.warm_to_cold}, "
            f"deleted={result.deleted}"
        )

        return {
            "job_id": job_key,
            "status": "completed",
            **result.to_dict(),
        }

    except Exception as e:
        logger.error(f"Retention cleanup job failed: {e}", exc_info=True)
        return {
            "job_id": job_key,
            "status": "failed",
            "error": str(e),
        }

    finally:
        _release_lock(job_key)


async def run_manual_embedding_backfill(
    batch_size: int = 50,
    max_articles: int = 500,
) -> dict:
    """
    Run a manual embedding backfill (triggered by API call).

    Args:
        batch_size: Number of articles per batch
        max_articles: Maximum articles to process

    Returns:
        Backfill job result
    """
    from lead_to_cash.services.marine_intel.embedding_service import (
        get_marine_embedding_service,
    )

    logger.info(
        f"Running manual embedding backfill: batch_size={batch_size}, max={max_articles}"
    )

    service = get_marine_embedding_service()
    result = await service.backfill_missing_embeddings(
        batch_size=batch_size,
        max_articles=max_articles,
    )

    return {
        "status": "completed",
        **result,
    }


async def run_manual_retention_cleanup() -> dict:
    """
    Run a manual retention cleanup (triggered by API call).

    Returns:
        Retention job result
    """
    from lead_to_cash.services.marine_intel.retention_service import (
        get_retention_service,
    )

    logger.info("Running manual retention cleanup")

    service = get_retention_service()
    result = await service.run_retention_job()

    return {
        "status": "completed",
        **result.to_dict(),
    }


# =============================================================================
# Historical Backfill - KB-Aware
# =============================================================================

# KB-derived query patterns based on product_data.py
# Target: High-speed marine engines (>1000 RPM, 700-10,000 kW)
# Industries: Marine, Offshore Oil & Gas, Marine Transportation

KB_BACKFILL_QUERIES = {
    # RRPS Products (MTU)
    "mtu_series_2000": [
        "MTU 2000 marine engine ferry patrol boat",
        "MTU Series 2000 high-speed vessel yacht",
        "MTU 8V2000 10V2000 12V2000 16V2000 marine",
    ],
    "mtu_series_4000": [
        "MTU 4000 marine engine offshore vessel",
        "MTU Series 4000 fast ferry OSV workboat",
        "MTU 12V4000 16V4000 20V4000 marine propulsion",
    ],
    "mtu_series_4000_gas": [
        "MTU 4000 gas engine LNG marine vessel",
        "MTU dual fuel engine ferry hybrid",
        "MTU natural gas marine propulsion",
    ],
    "mtu_series_8000": [
        "MTU 8000 marine engine fast ferry",
        "MTU Series 8000 high-power vessel yacht",
        "MTU 16V8000 20V8000 marine flagship",
    ],
    # Competitors - Cummins
    "cummins_qsk": [
        "Cummins QSK marine engine vessel",
        "Cummins QSK38 QSK60 marine workboat tug",
        "Cummins QSK78 QSK95 marine offshore ferry",
    ],
    # Competitors - Caterpillar
    "caterpillar_3500": [
        "Caterpillar 3500 marine engine vessel",
        "Cat 3512 3516 marine workboat offshore",
        "Caterpillar marine engine tug ferry OSV",
    ],
    # Competitors - MAN Engines
    "man_engines": [
        "MAN D2862 D2868 marine engine vessel",
        "MAN high-speed marine engine yacht ferry",
        "MAN Engines marine propulsion workboat",
    ],
    # Competitors - Volvo Penta
    "volvo_penta": [
        "Volvo Penta D13 marine engine vessel",
        "Volvo Penta IPS marine yacht ferry",
        "Volvo Penta marine propulsion workboat",
    ],
    # Competitors - Yanmar
    "yanmar": [
        "Yanmar 6AY marine engine vessel",
        "Yanmar high-speed marine engine workboat",
        "Yanmar marine diesel engine ferry tug",
    ],
    # Industry-specific (power range context)
    "ferry_passenger": [
        "fast ferry engine order Asia contract",
        "passenger ferry vessel newbuild propulsion",
        "high-speed ferry engine replacement repower",
    ],
    "offshore_osv": [
        "OSV platform supply vessel engine order",
        "offshore support vessel engine contract Asia",
        "AHTS anchor handling tug engine newbuild",
    ],
    "workboat_tug": [
        "harbor tug engine order newbuild",
        "workboat engine contract Asia Pacific",
        "tugboat marine engine replacement repower",
    ],
    "patrol_defense": [
        "patrol boat engine order contract",
        "coast guard vessel engine newbuild",
        "naval fast attack craft engine propulsion",
    ],
    "yacht_luxury": [
        "superyacht engine order MTU Caterpillar",
        "luxury yacht marine engine newbuild",
        "mega yacht propulsion engine contract",
    ],
}


async def run_historical_backfill(
    years: Optional[List[int]] = None,
    categories: Optional[List[str]] = None,
    region: str = "Asia Pacific Singapore",
) -> dict:
    """
    Run historical backfill for past years using KB-aware queries.

    Searches news archives for marine engine opportunities based on:
    - RRPS products (MTU Series 2000, 4000, 4000 Gas, 8000)
    - Competitor products (Cummins, Cat, MAN, Volvo Penta, Yanmar)
    - Target industries (ferry, offshore, workboat, patrol, yacht)

    Args:
        years: List of years to backfill (default: [2023, 2024, 2025])
        categories: Specific KB categories to query (default: all)
        region: Geographic focus (default: "Asia Pacific Singapore")

    Returns:
        Backfill job result statistics
    """
    from lead_to_cash.agents.marine_intel_agent import (
        MarineIntelAgent,
        MarineIntelConfig,
    )
    from lead_to_cash.services.marine_intel.database import get_marine_intel_db

    if years is None:
        years = [2023, 2024, 2025]

    if categories is None:
        categories = list(KB_BACKFILL_QUERIES.keys())

    job_id = (
        f"historical_backfill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )

    logger.info(
        f"Starting historical backfill: years={years}, categories={len(categories)}, "
        f"region={region}"
    )

    job = ResearchJob(
        id=job_id,
        job_type="historical_backfill",
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    db = get_marine_intel_db()

    try:
        await db.initialize()
    except Exception as e:
        if "already exists" not in str(e).lower():
            logger.error(f"Database initialization failed: {e}")
            raise

    await db.save_job(job)

    total_queries = 0
    total_opportunities = 0
    total_duplicates = 0
    errors = 0

    try:
        config = MarineIntelConfig()

        async with MarineIntelAgent(config) as agent:
            # Process each year
            for year in years:
                logger.info(f"Processing year {year}...")

                # Process each category
                for category in categories:
                    if category not in KB_BACKFILL_QUERIES:
                        continue

                    queries = KB_BACKFILL_QUERIES[category]

                    for base_query in queries:
                        # Add year and region context
                        full_query = f"{base_query} {region} {year}"

                        try:
                            logger.info(f"Query: {full_query[:60]}...")

                            # Use the agent's research method
                            opportunities = await agent.run_targeted_research(
                                custom_queries=[full_query],
                            )

                            total_queries += 1

                            if opportunities:
                                new_opps = len(opportunities)
                                total_opportunities += new_opps
                                logger.info(f"  -> Found {new_opps} opportunities")

                        except Exception as query_error:
                            logger.warning(f"Query failed: {query_error}")
                            errors += 1
                            continue

                logger.info(
                    f"Year {year} complete: {total_queries} queries, "
                    f"{total_opportunities} opportunities"
                )

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.queries_executed = total_queries
        job.opportunities_found = total_opportunities
        job.duplicates_skipped = total_duplicates
        job.errors = errors

    except Exception as e:
        logger.error(f"Historical backfill failed: {e}", exc_info=True)
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)
        errors += 1

    finally:
        try:
            await db.save_job(job)
        except Exception as save_error:
            logger.error(f"Failed to save job status: {save_error}")

    result = {
        "job_id": job_id,
        "status": job.status,
        "years_processed": years,
        "categories_processed": len(categories),
        "queries_executed": total_queries,
        "opportunities_found": total_opportunities,
        "duplicates_skipped": total_duplicates,
        "errors": errors,
        "duration_seconds": (
            (job.completed_at - job.started_at).total_seconds()
            if job.completed_at
            else 0
        ),
    }

    logger.info(f"Historical backfill complete: {result}")
    return result
