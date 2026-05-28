"""
Competitor Intelligence Module

Production-ready competitor intelligence pipeline for RRPS Sales Ops.
Monitors Caterpillar, Cummins, and MAN Energy Solutions for:
- Contract wins and customer announcements
- Product launches and new engine platforms
- Technology POVs (fuel transition, dual fuel, methanol, ammonia, hydrogen)
- Financial signals from EODHD
- Social media activity via Perplexity

Components:
- PostgreSQL + pgvector for persistent vector storage
- BeautifulSoup web scraping for competitor websites
- pypdf parsing for annual reports
- Perplexity API for news and social media intelligence
- EODHD API for financial data (CAT, CMI)
- APScheduler for scheduled data collection
- Signal extraction with 0-100 scoring system
- JSONL and Markdown output generation
"""

from lead_to_cash.services.competitor_intel.chunking_service import (
    ChunkingService,
    chunk_document,
    get_chunking_service,
)

# Database
from lead_to_cash.services.competitor_intel.database import (
    CompetitorIntelDatabase,
    get_competitor_db,
    initialize_competitor_db,
)
from lead_to_cash.services.competitor_intel.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)
from lead_to_cash.services.competitor_intel.eodhd_service import (
    EODHDService,
    get_eodhd_service,
)

# Signal processing
from lead_to_cash.services.competitor_intel.keyword_detector import (
    DetectionResult,
    KeywordDetector,
    get_keyword_detector,
)

# Original models
from lead_to_cash.services.competitor_intel.models import (
    Competitor,
    CompetitorDocument,
    ContentType,
    DocumentChunk,
    ScrapingJob,
    SourceType,
)

# Output generation
from lead_to_cash.services.competitor_intel.output_generator import (
    OutputGenerator,
    get_output_generator,
)
from lead_to_cash.services.competitor_intel.pdf_scraper import (
    PDFScraper,
    get_pdf_scraper,
)

# Scheduler (original + enhanced)
from lead_to_cash.services.competitor_intel.scheduler import (  # Original jobs; Enhanced jobs; Health check
    check_database_health,
    daily_newsroom_job,
    daily_refresh_job,
    daily_social_media_job,
    get_full_health,
    get_scheduler_health,
    run_full_pipeline,
    run_manual_digest,
    run_manual_financials,
    run_manual_full_crawl,
    run_manual_newsroom,
    run_manual_refresh,
    run_manual_social_media,
    start_enhanced_scheduler,
    start_scheduler,
    stop_scheduler,
    weekly_digest_job,
    weekly_financials_job,
    weekly_full_crawl_job,
    weekly_full_scrape_job,
)

# Original scraper services
from lead_to_cash.services.competitor_intel.scraper_service import (
    CompetitorScraperService,
    get_scraper_service,
)
from lead_to_cash.services.competitor_intel.signal_extractor import (
    SignalExtractor,
    get_signal_extractor,
)

# Enhanced signal models
from lead_to_cash.services.competitor_intel.signal_models import (
    CompetitorFinancials,
    CompetitorSignal,
    CompetitorSignalType,
    ExtractedSignalData,
    FinancialSignalData,
    FuelType,
    SourceChannel,
)
from lead_to_cash.services.competitor_intel.signal_scorer import (
    ScoreBreakdown,
    SignalScorer,
    get_signal_scorer,
)
from lead_to_cash.services.competitor_intel.social_media_scraper import (
    SocialMediaContent,
    SocialMediaScraper,
    get_social_media_scraper,
)

# Enhanced scraper services
from lead_to_cash.services.competitor_intel.targeted_web_scraper import (
    ScrapedContent,
    TargetedWebScraper,
    get_targeted_web_scraper,
)
from lead_to_cash.services.competitor_intel.web_scraper import (
    WebScraper,
    get_web_scraper,
)

__all__ = [
    # Original Models
    "Competitor",
    "CompetitorDocument",
    "ContentType",
    "DocumentChunk",
    "ScrapingJob",
    "SourceType",
    # Enhanced Signal Models
    "CompetitorSignal",
    "CompetitorSignalType",
    "SourceChannel",
    "FuelType",
    "CompetitorFinancials",
    "ExtractedSignalData",
    "FinancialSignalData",
    # Database (PostgreSQL + pgvector)
    "CompetitorIntelDatabase",
    "get_competitor_db",
    "initialize_competitor_db",
    # Original Scraper Services
    "CompetitorScraperService",
    "get_scraper_service",
    "WebScraper",
    "get_web_scraper",
    "PDFScraper",
    "get_pdf_scraper",
    # Embedding & Chunking
    "EmbeddingService",
    "get_embedding_service",
    "ChunkingService",
    "get_chunking_service",
    "chunk_document",
    # Enhanced Scraper Services
    "TargetedWebScraper",
    "get_targeted_web_scraper",
    "ScrapedContent",
    "SocialMediaScraper",
    "get_social_media_scraper",
    "SocialMediaContent",
    "EODHDService",
    "get_eodhd_service",
    # Signal Processing
    "KeywordDetector",
    "get_keyword_detector",
    "DetectionResult",
    "SignalScorer",
    "get_signal_scorer",
    "ScoreBreakdown",
    "SignalExtractor",
    "get_signal_extractor",
    # Output Generation
    "OutputGenerator",
    "get_output_generator",
    # Original Scheduler
    "start_scheduler",
    "stop_scheduler",
    "run_manual_refresh",
    "run_manual_full_crawl",
    "daily_refresh_job",
    "weekly_full_crawl_job",
    # Enhanced Scheduler
    "start_enhanced_scheduler",
    "daily_newsroom_job",
    "daily_social_media_job",
    "weekly_full_scrape_job",
    "weekly_financials_job",
    "weekly_digest_job",
    "run_manual_newsroom",
    "run_manual_social_media",
    "run_manual_financials",
    "run_manual_digest",
    "run_full_pipeline",
    # Health Check
    "get_scheduler_health",
    "check_database_health",
    "get_full_health",
]
