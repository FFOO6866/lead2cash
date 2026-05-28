"""
Daily Scheduler for Competitor Intelligence

Runs scheduled jobs to refresh competitor intelligence data:
- Daily refresh at 2 AM SGT (18:00 UTC previous day)
- Weekly full crawl on Sundays at 2 AM SGT

Uses APScheduler for production-ready async scheduling.
NO MOCKS - real scheduled jobs with real scraping.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from lead_to_cash.services.competitor_intel.models import (
    Competitor,
    ScrapingJob,
)

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


async def daily_refresh_job() -> dict:
    """
    Daily competitor intelligence refresh job.

    Runs at 2 AM SGT (18:00 UTC) every day:
    1. Scrapes competitor websites (BeautifulSoup)
    2. Fetches latest news (Perplexity API)
    3. Generates embeddings (OpenAI)
    4. Stores in PostgreSQL pgvector

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.embedding_service import (
        get_embedding_service,
    )
    from lead_to_cash.services.competitor_intel.scraper_service import (
        get_scraper_service,
    )
    from lead_to_cash.services.competitor_intel.web_scraper import get_web_scraper

    logger.info("Starting daily competitor intelligence refresh")

    # Create job record
    job = ScrapingJob(
        id=str(uuid.uuid4()),
        job_type="daily_refresh",
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    db = get_competitor_db()
    await db.save_job(job)

    total_docs = 0
    total_chunks = 0
    errors = 0

    try:
        # Step 1: Web scraping (BeautifulSoup)
        logger.info("Step 1: Web scraping competitor websites")
        web_scraper = get_web_scraper()
        web_docs = await web_scraper.scrape_all_competitors()

        for doc in web_docs:
            try:
                await db.save_document(doc)
                total_docs += 1
            except Exception as e:
                logger.error(f"Error saving web doc: {e}")
                errors += 1

        await web_scraper.close()
        logger.info(f"Web scraping complete: {len(web_docs)} documents")

        # Step 2: Perplexity API (news and intelligence)
        logger.info("Step 2: Fetching news via Perplexity API")
        scraper_service = get_scraper_service()

        for competitor in Competitor:
            try:
                result = await scraper_service.refresh_competitor(competitor.value)
                total_docs += result.get("documents_created", 0)
            except Exception as e:
                logger.error(f"Error refreshing {competitor.value}: {e}")
                errors += 1

        await scraper_service.close()
        logger.info("Perplexity scraping complete")

        # Step 3: Generate embeddings
        logger.info("Step 3: Generating embeddings")
        embedding_service = get_embedding_service()
        embed_result = await embedding_service.process_all_documents()
        total_chunks = embed_result.get("chunks_created", 0)
        errors += embed_result.get("errors", 0)

        await embedding_service.close()
        logger.info(f"Embedding complete: {total_chunks} chunks created")

        # Update job status
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.documents_processed = total_docs
        job.chunks_created = total_chunks
        job.documents_failed = errors

    except Exception as e:
        logger.error(f"Daily refresh job failed: {e}")
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)

    await db.save_job(job)

    result = {
        "job_id": job.id,
        "status": job.status,
        "documents_processed": total_docs,
        "chunks_created": total_chunks,
        "errors": errors,
        "duration_seconds": (
            (job.completed_at - job.started_at).total_seconds()
            if job.completed_at
            else 0
        ),
    }

    logger.info(f"Daily refresh complete: {result}")
    return result


async def weekly_full_crawl_job() -> dict:
    """
    Weekly full crawl job including PDFs.

    Runs on Sundays at 2 AM UTC:
    - All daily refresh tasks
    - Plus: Download and parse annual reports (pypdf)

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.embedding_service import (
        get_embedding_service,
    )
    from lead_to_cash.services.competitor_intel.pdf_scraper import get_pdf_scraper

    logger.info("Starting weekly full crawl")

    # Run daily refresh first
    daily_result = await daily_refresh_job()

    # Then add PDF parsing
    job = ScrapingJob(
        id=str(uuid.uuid4()),
        job_type="weekly_full",
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    db = get_competitor_db()
    await db.save_job(job)

    pdf_docs = 0
    errors = daily_result.get("errors", 0)

    try:
        # Scrape annual reports
        logger.info("Scraping annual reports (PDF)")
        pdf_scraper = get_pdf_scraper()
        reports = await pdf_scraper.scrape_all_annual_reports()

        for doc in reports:
            try:
                await db.save_document(doc)
                pdf_docs += 1
            except Exception as e:
                logger.error(f"Error saving PDF doc: {e}")
                errors += 1

        await pdf_scraper.close()
        logger.info(f"PDF scraping complete: {pdf_docs} documents")

        # Generate embeddings for new PDFs
        logger.info("Generating embeddings for PDFs")
        embedding_service = get_embedding_service()
        embed_result = await embedding_service.process_all_documents()
        await embedding_service.close()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.documents_processed = daily_result.get("documents_processed", 0) + pdf_docs
        job.chunks_created = daily_result.get("chunks_created", 0) + embed_result.get(
            "chunks_created", 0
        )
        job.documents_failed = errors

    except Exception as e:
        logger.error(f"Weekly crawl failed: {e}")
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)

    await db.save_job(job)

    result = {
        "job_id": job.id,
        "status": job.status,
        "documents_processed": job.documents_processed,
        "chunks_created": job.chunks_created,
        "pdf_documents": pdf_docs,
        "errors": errors,
    }

    logger.info(f"Weekly crawl complete: {result}")
    return result


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    """
    Start the competitor intelligence scheduler.

    Adds scheduled jobs:
    - Daily refresh at 2 AM SGT (18:00 UTC)
    - Weekly full crawl on Sundays at 2 AM SGT (18:00 UTC)

    Returns:
        Started scheduler instance
    """
    scheduler = get_scheduler()

    # Daily refresh at 2 AM SGT = 18:00 UTC
    scheduler.add_job(
        daily_refresh_job,
        CronTrigger(hour=18, minute=0, timezone="UTC"),
        id="daily_competitor_refresh",
        replace_existing=True,
        name="Daily Competitor Intelligence Refresh",
    )
    logger.info("Scheduled daily refresh job at 2:00 AM SGT (18:00 UTC)")

    # Weekly full crawl on Sundays at 2 AM SGT = 18:00 UTC Saturday
    scheduler.add_job(
        weekly_full_crawl_job,
        CronTrigger(day_of_week="sat", hour=18, minute=0, timezone="UTC"),
        id="weekly_competitor_crawl",
        replace_existing=True,
        name="Weekly Full Competitor Crawl",
    )
    logger.info("Scheduled weekly crawl job for Sundays at 2:00 AM SGT (Sat 18:00 UTC)")

    scheduler.start()
    logger.info("Competitor intelligence scheduler started")

    return scheduler


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Competitor intelligence scheduler stopped")
    _scheduler = None


async def run_manual_refresh() -> dict:
    """
    Run a manual refresh (triggered by API call).

    Returns:
        Refresh job result
    """
    return await daily_refresh_job()


async def run_manual_full_crawl() -> dict:
    """
    Run a manual full crawl including PDFs.

    Returns:
        Crawl job result
    """
    return await weekly_full_crawl_job()


# =============================================================================
# Enhanced Competitor Intelligence Jobs
# =============================================================================


async def daily_newsroom_job() -> dict:
    """
    Daily newsroom scraping job using targeted web scraper.

    Runs at 6:00 AM UTC:
    1. Scrapes newsroom pages for all competitors
    2. Extracts signals using signal extractor
    3. Scores and stores signals in database

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.signal_extractor import (
        get_signal_extractor,
    )
    from lead_to_cash.services.competitor_intel.targeted_web_scraper import (
        get_targeted_web_scraper,
    )

    logger.info("Starting daily newsroom scraping job")

    db = get_competitor_db()

    # Initialize database - required for standalone scheduler process
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or db._initialized:
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            return {"status": "failed", "error": f"Database initialization failed: {e}"}

    scraper = get_targeted_web_scraper()
    extractor = get_signal_extractor()

    signals_created = 0
    errors = 0

    try:
        # Scrape all newsrooms
        scraper.reset_seen_urls()
        scraped_items = await scraper.scrape_all_newsrooms()
        logger.info(f"Scraped {len(scraped_items)} newsroom items")

        # Extract signals
        for item in scraped_items:
            try:
                signal = await extractor.extract_from_scraped_content(
                    item, use_llm=True
                )
                await db.save_signal(signal)
                signals_created += 1
            except Exception as e:
                logger.error(f"Error extracting signal: {e}")
                errors += 1

        await scraper.close()
        await extractor.close()

    except Exception as e:
        logger.error(f"Daily newsroom job failed: {e}")
        return {"status": "failed", "error": str(e)}

    result = {
        "status": "completed",
        "scraped_items": len(scraped_items),
        "signals_created": signals_created,
        "errors": errors,
    }
    logger.info(f"Daily newsroom job complete: {result}")
    return result


async def daily_social_media_job() -> dict:
    """
    Daily social media monitoring job using Perplexity.

    Runs at 6:30 AM UTC:
    1. Searches for competitor social media mentions
    2. Extracts signals from social content
    3. Scores and stores signals

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.signal_extractor import (
        get_signal_extractor,
    )
    from lead_to_cash.services.competitor_intel.social_media_scraper import (
        get_social_media_scraper,
    )

    logger.info("Starting daily social media monitoring job")

    db = get_competitor_db()

    # Initialize database - required for standalone scheduler process
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or db._initialized:
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            return {"status": "failed", "error": f"Database initialization failed: {e}"}

    scraper = get_social_media_scraper()
    extractor = get_signal_extractor()

    signals_created = 0
    errors = 0

    try:
        # Search all competitors on all platforms
        social_items = await scraper.search_all_competitors()
        logger.info(f"Found {len(social_items)} social media items")

        # Extract signals
        for item in social_items:
            try:
                signal = await extractor.extract_from_social_content(item, use_llm=True)
                await db.save_signal(signal)
                signals_created += 1
            except Exception as e:
                logger.error(f"Error extracting social signal: {e}")
                errors += 1

        await scraper.close()
        await extractor.close()

    except Exception as e:
        logger.error(f"Daily social media job failed: {e}")
        return {"status": "failed", "error": str(e)}

    result = {
        "status": "completed",
        "social_items": len(social_items),
        "signals_created": signals_created,
        "errors": errors,
    }
    logger.info(f"Daily social media job complete: {result}")
    return result


async def weekly_full_scrape_job() -> dict:
    """
    Weekly full scrape of product and insights pages.

    Runs on Sundays at 2:00 AM UTC:
    1. Scrapes product pages for all competitors
    2. Scrapes insights/technology pages
    3. Extracts and stores signals

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.signal_extractor import (
        get_signal_extractor,
    )
    from lead_to_cash.services.competitor_intel.targeted_web_scraper import (
        get_targeted_web_scraper,
    )

    logger.info("Starting weekly full scrape job")

    db = get_competitor_db()

    # Initialize database - required for standalone scheduler process
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or db._initialized:
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            return {"status": "failed", "error": f"Database initialization failed: {e}"}

    scraper = get_targeted_web_scraper()
    extractor = get_signal_extractor()

    signals_created = 0
    errors = 0
    total_scraped = 0

    try:
        scraper.reset_seen_urls()

        # Scrape product pages
        product_items = await scraper.scrape_all_product_pages()
        logger.info(f"Scraped {len(product_items)} product page items")
        total_scraped += len(product_items)

        # Scrape insights pages
        insights_items = await scraper.scrape_all_insights()
        logger.info(f"Scraped {len(insights_items)} insights items")
        total_scraped += len(insights_items)

        # Extract signals from all items
        all_items = product_items + insights_items
        for item in all_items:
            try:
                signal = await extractor.extract_from_scraped_content(
                    item, use_llm=True
                )
                await db.save_signal(signal)
                signals_created += 1
            except Exception as e:
                logger.error(f"Error extracting signal: {e}")
                errors += 1

        await scraper.close()
        await extractor.close()

    except Exception as e:
        logger.error(f"Weekly full scrape job failed: {e}")
        return {"status": "failed", "error": str(e)}

    result = {
        "status": "completed",
        "total_scraped": total_scraped,
        "signals_created": signals_created,
        "errors": errors,
    }
    logger.info(f"Weekly full scrape job complete: {result}")
    return result


async def weekly_financials_job() -> dict:
    """
    Weekly financial data refresh from EODHD.

    Runs on Mondays at 8:00 AM UTC:
    1. Fetches quarterly financials for CAT, CMI
    2. Stores in database

    Returns:
        Job result statistics
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.eodhd_service import get_eodhd_service

    logger.info("Starting weekly financials job")

    db = get_competitor_db()

    # Initialize database - required for standalone scheduler process
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or db._initialized:
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            return {"status": "failed", "error": f"Database initialization failed: {e}"}

    eodhd = get_eodhd_service()

    financials_saved = 0
    errors = 0

    try:
        if not eodhd.is_configured():
            logger.warning("EODHD API not configured, skipping financials job")
            return {
                "status": "skipped",
                "reason": "EODHD_API_KEY not configured",
            }

        # Fetch all financials
        financials = await eodhd.refresh_all_financials()
        logger.info(f"Fetched {len(financials)} financial records")

        # Save to database
        for fin in financials:
            try:
                await db.save_financials(fin)
                financials_saved += 1
            except Exception as e:
                logger.error(f"Error saving financials: {e}")
                errors += 1

        await eodhd.close()

    except Exception as e:
        logger.error(f"Weekly financials job failed: {e}")
        return {"status": "failed", "error": str(e)}

    result = {
        "status": "completed",
        "financials_saved": financials_saved,
        "errors": errors,
    }
    logger.info(f"Weekly financials job complete: {result}")
    return result


async def weekly_digest_job() -> dict:
    """
    Weekly digest generation job.

    Runs on Mondays at 9:00 AM UTC:
    1. Retrieves signals from past week
    2. Retrieves latest financials
    3. Generates markdown digest and JSONL files

    Returns:
        Job result statistics
    """
    from datetime import timedelta

    from lead_to_cash.services.competitor_intel.database import get_competitor_db
    from lead_to_cash.services.competitor_intel.output_generator import (
        get_output_generator,
    )

    logger.info("Starting weekly digest job")

    db = get_competitor_db()

    # Initialize database - required for standalone scheduler process
    try:
        await db.initialize()
        logger.info("Database initialized successfully")
    except Exception as e:
        # Check if it's just "already initialized" vs actual error
        if "already exists" in str(e).lower() or db._initialized:
            logger.debug(f"Database tables already exist: {e}")
        else:
            logger.error(f"Database initialization failed: {e}")
            return {"status": "failed", "error": f"Database initialization failed: {e}"}

    generator = get_output_generator()

    try:
        # Get signals from past week
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        signals = await db.get_signals_by_date_range(start_date, end_date)
        logger.info(f"Retrieved {len(signals)} signals from past week")

        # Get latest financials
        financials = await db.get_all_latest_financials()

        # Generate output files
        items_path = generator.write_all_items(signals)
        opportunities_path = generator.write_opportunities(signals)
        digest_path = generator.generate_weekly_digest(signals, financials)

    except Exception as e:
        logger.error(f"Weekly digest job failed: {e}")
        return {"status": "failed", "error": str(e)}

    result = {
        "status": "completed",
        "signals_processed": len(signals),
        "high_impact_signals": len([s for s in signals if s.score >= 60]),
        "output_files": {
            "items": items_path,
            "opportunities": opportunities_path,
            "digest": digest_path,
        },
    }
    logger.info(f"Weekly digest job complete: {result}")
    return result


def start_enhanced_scheduler() -> AsyncIOScheduler:
    """
    Start the enhanced competitor intelligence scheduler.

    Adds all scheduled jobs (all times in SGT, converted to UTC):
    CORE JOBS (from basic scheduler):
    - Daily refresh at 2:00 AM SGT (18:00 UTC) - web scraping, Perplexity, embeddings
    - Weekly full crawl on Sundays at 2:00 AM SGT (Sat 18:00 UTC) - includes PDFs

    ENHANCED JOBS:
    - Daily newsroom at 2:00 AM SGT (18:00 UTC)
    - Daily social media at 2:30 AM SGT (18:30 UTC)
    - Weekly full scrape on Sundays at 2:00 AM SGT (Sat 18:00 UTC)
    - Weekly financials on Mondays at 8:00 AM SGT (Mon 00:00 UTC)
    - Weekly digest on Mondays at 9:00 AM SGT (Mon 01:00 UTC)

    Returns:
        Started scheduler instance
    """
    scheduler = get_scheduler()

    # ==========================================================================
    # CORE JOBS (from basic scheduler)
    # ==========================================================================

    # Daily refresh at 2:00 AM SGT = 18:00 UTC previous day
    scheduler.add_job(
        daily_refresh_job,
        CronTrigger(hour=18, minute=0, timezone="UTC"),
        id="daily_competitor_refresh",
        replace_existing=True,
        name="Daily Competitor Intelligence Refresh",
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Scheduled daily competitor refresh at 2:00 AM SGT (18:00 UTC)")

    # Weekly full crawl on Sundays at 2:00 AM SGT = Sat 18:00 UTC
    scheduler.add_job(
        weekly_full_crawl_job,
        CronTrigger(day_of_week="sat", hour=18, minute=0, timezone="UTC"),
        id="weekly_competitor_crawl",
        replace_existing=True,
        name="Weekly Full Competitor Crawl",
        misfire_grace_time=7200,
        coalesce=True,
    )
    logger.info("Scheduled weekly crawl job for Sundays at 2:00 AM SGT (Sat 18:00 UTC)")

    # ==========================================================================
    # ENHANCED JOBS
    # ==========================================================================

    # Daily newsroom scraping at 2:00 AM SGT = 18:00 UTC
    scheduler.add_job(
        daily_newsroom_job,
        CronTrigger(hour=18, minute=0, timezone="UTC"),
        id="daily_newsroom_scrape",
        replace_existing=True,
        name="Daily Newsroom Scrape",
    )
    logger.info("Scheduled daily newsroom job at 2:00 AM SGT (18:00 UTC)")

    # Daily social media at 2:30 AM SGT = 18:30 UTC
    scheduler.add_job(
        daily_social_media_job,
        CronTrigger(hour=18, minute=30, timezone="UTC"),
        id="daily_social_media",
        replace_existing=True,
        name="Daily Social Media Monitoring",
    )
    logger.info("Scheduled daily social media job at 2:30 AM SGT (18:30 UTC)")

    # Weekly full scrape on Sundays at 2:00 AM SGT = Sat 18:00 UTC
    scheduler.add_job(
        weekly_full_scrape_job,
        CronTrigger(day_of_week="sat", hour=18, minute=0, timezone="UTC"),
        id="weekly_full_scrape",
        replace_existing=True,
        name="Weekly Full Scrape (Products + Insights)",
    )
    logger.info(
        "Scheduled weekly full scrape for Sundays at 2:00 AM SGT (Sat 18:00 UTC)"
    )

    # Weekly financials on Mondays at 8:00 AM SGT = Mon 00:00 UTC
    scheduler.add_job(
        weekly_financials_job,
        CronTrigger(day_of_week="mon", hour=0, minute=0, timezone="UTC"),
        id="weekly_financials",
        replace_existing=True,
        name="Weekly Financial Data Refresh",
    )
    logger.info(
        "Scheduled weekly financials job for Mondays at 8:00 AM SGT (00:00 UTC)"
    )

    # Weekly digest on Mondays at 9:00 AM SGT = Mon 01:00 UTC
    scheduler.add_job(
        weekly_digest_job,
        CronTrigger(day_of_week="mon", hour=1, minute=0, timezone="UTC"),
        id="weekly_digest",
        replace_existing=True,
        name="Weekly Digest Generation",
    )
    logger.info("Scheduled weekly digest job for Mondays at 9:00 AM SGT (01:00 UTC)")

    scheduler.start()
    logger.info("Enhanced competitor intelligence scheduler started")

    return scheduler


# Manual trigger functions for enhanced jobs


async def run_manual_newsroom() -> dict:
    """Manually trigger newsroom scraping."""
    return await daily_newsroom_job()


async def run_manual_social_media() -> dict:
    """Manually trigger social media monitoring."""
    return await daily_social_media_job()


async def run_manual_financials() -> dict:
    """Manually trigger financial data refresh."""
    return await weekly_financials_job()


async def run_manual_digest() -> dict:
    """Manually trigger weekly digest generation."""
    return await weekly_digest_job()


async def run_full_pipeline() -> dict:
    """
    Run the full competitor intelligence pipeline manually.

    Executes all jobs in sequence:
    1. Newsroom scraping
    2. Social media monitoring
    3. Product/insights scraping
    4. Financial data
    5. Digest generation

    Returns:
        Combined results from all jobs
    """
    logger.info("Running full competitor intelligence pipeline")

    results = {}

    # Newsroom
    results["newsroom"] = await daily_newsroom_job()

    # Social media
    results["social_media"] = await daily_social_media_job()

    # Full scrape (products + insights)
    results["full_scrape"] = await weekly_full_scrape_job()

    # Financials
    results["financials"] = await weekly_financials_job()

    # Digest
    results["digest"] = await weekly_digest_job()

    logger.info(f"Full pipeline complete: {results}")
    return results


# =============================================================================
# Health Check
# =============================================================================


def get_scheduler_health() -> dict:
    """
    Get health status of the competitor intelligence scheduler.

    Returns:
        Dictionary with scheduler health information including:
        - is_running: Whether scheduler is active
        - job_count: Number of scheduled jobs
        - jobs: Details of each job (id, name, next_run_time)
        - last_error: Last error if any (from job results)
    """
    scheduler = get_scheduler()

    if scheduler is None:
        return {
            "is_running": False,
            "job_count": 0,
            "jobs": [],
            "status": "not_initialized",
        }

    is_running = scheduler.running if hasattr(scheduler, "running") else False

    jobs_info = []
    for job in scheduler.get_jobs():
        job_info = {
            "id": job.id,
            "name": job.name,
            "next_run_time": (
                job.next_run_time.isoformat() if job.next_run_time else None
            ),
            "trigger": str(job.trigger),
        }
        jobs_info.append(job_info)

    return {
        "is_running": is_running,
        "job_count": len(jobs_info),
        "jobs": jobs_info,
        "status": "running" if is_running else "stopped",
    }


async def check_database_health() -> dict:
    """
    Check health of the competitor intelligence database.

    Returns:
        Dictionary with database health information.
    """
    from lead_to_cash.services.competitor_intel.database import get_competitor_db

    db = get_competitor_db()

    try:
        # Try to initialize if not already done
        if not db._initialized:
            await db.initialize()

        # Check if we can get a connection
        async with db.pool.acquire() as conn:
            # Simple health check query
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                return {
                    "status": "healthy",
                    "connected": True,
                    "initialized": db._initialized,
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "initialized": db._initialized if hasattr(db, "_initialized") else False,
            "error": str(e),
        }

    return {
        "status": "unknown",
        "connected": False,
        "initialized": False,
    }


async def get_full_health() -> dict:
    """
    Get comprehensive health status of the competitor intelligence system.

    Returns:
        Dictionary with scheduler and database health.
    """
    scheduler_health = get_scheduler_health()
    db_health = await check_database_health()

    overall_status = "healthy"
    if scheduler_health["status"] != "running":
        overall_status = "degraded"
    if db_health["status"] != "healthy":
        overall_status = "unhealthy"

    return {
        "overall_status": overall_status,
        "scheduler": scheduler_health,
        "database": db_health,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
