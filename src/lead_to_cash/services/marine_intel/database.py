"""
PostgreSQL Database Layer for Marine Sales Intelligence

Production-ready database operations for storing and querying
marine sales opportunities with URL-based deduplication.

Tables:
- marine_opportunities: Sales opportunities with URL hash deduplication
- marine_articles: Source documents with embeddings (for future RAG)
- marine_accounts: Company tracking with mention counts
- marine_article_accounts: Junction table for article-company mentions
- marine_research_jobs: Processing job tracking

Production Features:
- Connection pool with retry logic
- Transient failure recovery with exponential backoff
- Input validation integration
"""

import json
import logging
import os
from typing import Any, Optional

import asyncpg

from lead_to_cash.services.marine_intel.models import (
    Account,
    Article,
    MarineOpportunity,
    ResearchJob,
)
from lead_to_cash.utils.resilience import with_retry

logger = logging.getLogger(__name__)


class MarineIntelDatabase:
    """
    PostgreSQL database for marine sales intelligence.

    Stores sales opportunities with URL hash-based deduplication
    to avoid duplicate entries from the same source article.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection string. If not provided,
                         uses DATABASE_URL environment variable.
        """
        # Store provided URL or defer to env var lookup
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    @property
    def database_url(self) -> str:
        """Get database URL, validating on first access."""
        url = self._database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError(
                "DATABASE_URL must be set. "
                "Example: postgresql://user:pass@localhost:5432/lead_to_cash"
            )
        return url

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool, raising if not initialized."""
        if self._pool is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._pool

    async def initialize(self) -> None:
        """
        Initialize database connection pool and create tables.

        Creates:
        - marine_opportunities: Sales opportunities with URL hash deduplication
        - marine_articles: Source documents with embeddings (for future RAG)
        - marine_accounts: Company tracking with mention counts
        - marine_article_accounts: Junction table for mentions
        - marine_research_jobs: Processing job tracking
        """
        if self._initialized:
            return

        logger.info("Initializing Marine Intel PostgreSQL database")

        # Create connection pool
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        async with self.pool.acquire() as conn:
            # =========================================================================
            # NEW TABLES: Articles, Opportunities (v2), Accounts
            # =========================================================================

            # Enable pgvector extension for semantic search
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Create marine_articles table (source documents with embeddings)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marine_articles (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    published_date TIMESTAMPTZ,
                    processed_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    is_processed BOOLEAN DEFAULT FALSE,
                    opportunities_generated INTEGER DEFAULT 0,
                    source_category TEXT DEFAULT 'trade_media',
                    metadata JSONB DEFAULT '{}',
                    embedding vector(1536),
                    retention_tier TEXT DEFAULT 'hot',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create marine_accounts table (company tracking)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marine_accounts (
                    id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    country TEXT,
                    sector TEXT,
                    website TEXT,
                    mention_count INTEGER DEFAULT 0,
                    opportunity_count INTEGER DEFAULT 0,
                    first_seen_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    total_score FLOAT DEFAULT 0.0,
                    priority_rank INTEGER,
                    crm_account_id TEXT,
                    is_existing_customer BOOLEAN DEFAULT FALSE,
                    aliases TEXT[] DEFAULT '{}',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create marine_article_accounts junction table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marine_article_accounts (
                    article_id TEXT NOT NULL REFERENCES marine_articles(id) ON DELETE CASCADE,
                    account_id TEXT NOT NULL REFERENCES marine_accounts(id) ON DELETE CASCADE,
                    mention_context TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (article_id, account_id)
                )
            """
            )

            # =========================================================================
            # INDEXES for new tables
            # =========================================================================

            # Articles indexes
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_url_hash
                ON marine_articles(url_hash)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_source
                ON marine_articles(source)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_published_date
                ON marine_articles(published_date DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_processed_date
                ON marine_articles(processed_date DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_is_processed
                ON marine_articles(is_processed)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_retention_tier
                ON marine_articles(retention_tier)
            """
            )
            # HNSW vector index for semantic similarity search
            # Uses cosine distance, optimized for recall
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_articles_embedding
                ON marine_articles USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
            )

            # Accounts indexes
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_normalized_name
                ON marine_accounts(normalized_name)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_country
                ON marine_accounts(country)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_sector
                ON marine_accounts(sector)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_mention_count
                ON marine_accounts(mention_count DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_total_score
                ON marine_accounts(total_score DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_last_seen
                ON marine_accounts(last_seen_date DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_accounts_crm_id
                ON marine_accounts(crm_account_id)
            """
            )

            # Article-accounts junction indexes
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_article_accounts_article
                ON marine_article_accounts(article_id)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_marine_article_accounts_account
                ON marine_article_accounts(account_id)
            """
            )

            # =========================================================================
            # OPPORTUNITY TABLE (Primary sales opportunities storage)
            # =========================================================================

            # Create marine_opportunities table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marine_opportunities (
                    id TEXT PRIMARY KEY,
                    headline TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    url_hash TEXT UNIQUE NOT NULL,

                    -- Classification
                    sales_signals TEXT[] NOT NULL DEFAULT '{}',
                    region TEXT NOT NULL,
                    vessel_types TEXT[] NOT NULL DEFAULT '{}',
                    sector TEXT NOT NULL,

                    -- Companies and context
                    companies_involved TEXT[] NOT NULL DEFAULT '{}',
                    country TEXT NOT NULL,

                    -- Analysis
                    sales_explanation TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,

                    -- Metadata
                    source_category TEXT NOT NULL,
                    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    published_date TIMESTAMPTZ,
                    raw_content TEXT DEFAULT '',

                    -- Optional enrichment
                    estimated_value FLOAT,
                    currency TEXT DEFAULT 'USD',
                    engine_power_range TEXT,
                    contact_info TEXT,

                    -- Processing status
                    reviewed BOOLEAN DEFAULT FALSE,
                    exported_to_crm BOOLEAN DEFAULT FALSE,
                    priority INTEGER DEFAULT 5,

                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create marine_research_jobs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marine_research_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    queries_executed INTEGER DEFAULT 0,
                    articles_processed INTEGER DEFAULT 0,
                    opportunities_found INTEGER DEFAULT 0,
                    duplicates_skipped INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """
            )

            # Add articles_processed column if it doesn't exist (migration for existing DBs)
            await conn.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'marine_research_jobs'
                        AND column_name = 'articles_processed'
                    ) THEN
                        ALTER TABLE marine_research_jobs
                        ADD COLUMN articles_processed INTEGER DEFAULT 0;
                    END IF;
                END $$;
            """
            )

            # Opportunity indexes
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_region
                ON marine_opportunities(region)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_sector
                ON marine_opportunities(sector)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_discovered_at
                ON marine_opportunities(discovered_at DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_reviewed
                ON marine_opportunities(reviewed)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_priority
                ON marine_opportunities(priority DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_sales_signals
                ON marine_opportunities USING GIN (sales_signals)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_opportunities_vessel_types
                ON marine_opportunities USING GIN (vessel_types)
            """
            )

        self._initialized = True
        logger.info("Marine Intel database initialization complete")

    async def close(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False

    # =========================================================================
    # Article Operations
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def save_article(self, article: Article) -> tuple[str, bool]:
        """
        Save an article with URL hash deduplication.

        Args:
            article: Article to save

        Returns:
            Tuple of (article_id, is_new). is_new=False means duplicate was skipped.
        """
        async with self.pool.acquire() as conn:
            # Check if URL hash already exists (deduplication)
            existing = await conn.fetchval(
                "SELECT id FROM marine_articles WHERE url_hash = $1", article.url_hash
            )

            if existing:
                logger.debug(f"Duplicate article skipped: {article.url}")
                return existing, False

            # Insert new article with embedding and retention_tier
            # Convert embedding to pgvector format if present
            embedding_str = None
            if article.embedding is not None:
                embedding_str = "[" + ",".join(str(x) for x in article.embedding) + "]"

            # Serialize metadata to JSON string for JSONB column
            metadata_json = json.dumps(article.metadata) if article.metadata else "{}"

            await conn.execute(
                """
                INSERT INTO marine_articles (
                    id, url, url_hash, title, source, content, summary,
                    published_date, processed_date, is_processed,
                    opportunities_generated, source_category, metadata,
                    embedding, retention_tier
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14::vector, $15)
            """,
                article.id,
                article.url,
                article.url_hash,
                article.title,
                article.source,
                article.content,
                article.summary,
                article.published_date,
                article.processed_date,
                article.is_processed,
                article.opportunities_generated,
                article.source_category,
                metadata_json,
                embedding_str,
                article.retention_tier,
            )

            logger.info(f"New article saved: {article.title[:50]}...")
            return article.id, True

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_article(self, article_id: str) -> Optional[Article]:
        """Get an article by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_articles WHERE id = $1", article_id
            )
            if row:
                return self._row_to_article(row)
        return None

    async def get_article_by_url(self, url: str) -> Optional[Article]:
        """Get an article by URL (using hash)."""
        url_hash = Article.generate_url_hash(url)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_articles WHERE url_hash = $1", url_hash
            )
            if row:
                return self._row_to_article(row)
        return None

    async def check_article_url_exists(self, url: str) -> bool:
        """Check if an article URL already exists."""
        url_hash = Article.generate_url_hash(url)
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM marine_articles WHERE url_hash = $1)",
                url_hash,
            )
            return exists

    async def list_articles(
        self,
        source: Optional[str] = None,
        is_processed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Article]:
        """List articles with optional filters."""
        query = "SELECT * FROM marine_articles WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if source:
            query += f" AND source = ${param_idx}"
            params.append(source)
            param_idx += 1

        if is_processed is not None:
            query += f" AND is_processed = ${param_idx}"
            params.append(is_processed)
            param_idx += 1

        query += (
            f" ORDER BY processed_date DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_article(row) for row in rows]

    async def get_unprocessed_articles(self, limit: int = 50) -> list[Article]:
        """Get articles that haven't been processed yet."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM marine_articles
                WHERE is_processed = FALSE
                ORDER BY processed_date ASC
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_article(row) for row in rows]

    async def mark_article_processed(
        self,
        article_id: str,
        opportunities_generated: int = 0,
    ) -> bool:
        """Mark an article as processed."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE marine_articles
                SET is_processed = TRUE,
                    opportunities_generated = $1,
                    updated_at = NOW()
                WHERE id = $2
            """,
                opportunities_generated,
                article_id,
            )
            return "UPDATE 1" in result

    async def delete_article(self, article_id: str) -> bool:
        """Delete an article (cascades to opportunities)."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM marine_articles WHERE id = $1", article_id
            )
            return "DELETE 1" in result

    # =========================================================================
    # Vector Search Operations (Semantic Search)
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def update_article_embedding(
        self,
        article_id: str,
        embedding: list[float],
    ) -> bool:
        """
        Update the embedding vector for an article.

        Args:
            article_id: Article ID
            embedding: 1536-dimensional embedding vector

        Returns:
            True if updated, False if article not found
        """
        if len(embedding) != 1536:
            raise ValueError(f"Embedding must be 1536 dimensions, got {len(embedding)}")

        async with self.pool.acquire() as conn:
            # Convert list to pgvector format string
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            result = await conn.execute(
                """
                UPDATE marine_articles
                SET embedding = $1::vector,
                    updated_at = NOW()
                WHERE id = $2
            """,
                embedding_str,
                article_id,
            )
            return "UPDATE 1" in result

    @with_retry(max_retries=3, base_delay=0.5)
    async def vector_search_articles(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_similarity: float = 0.6,
        retention_tiers: Optional[list[str]] = None,
    ) -> list[tuple[Article, float]]:
        """
        Search articles by semantic similarity using pgvector.

        Uses cosine similarity with HNSW index for fast approximate
        nearest neighbor search.

        Args:
            query_embedding: 1536-dimensional query embedding
            top_k: Maximum number of results to return
            min_similarity: Minimum cosine similarity threshold (0-1)
            retention_tiers: Optional filter by retention tier(s)

        Returns:
            List of (Article, similarity_score) tuples, sorted by similarity
        """
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Query embedding must be 1536 dimensions, got {len(query_embedding)}"
            )

        # Convert to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build query with optional tier filter
        if retention_tiers:
            tier_placeholders = ", ".join(
                f"${i + 3}" for i in range(len(retention_tiers))
            )
            query = f"""
                SELECT *,
                       1 - (embedding <=> $1::vector) as similarity
                FROM marine_articles
                WHERE embedding IS NOT NULL
                  AND retention_tier IN ({tier_placeholders})
                  AND 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT ${len(retention_tiers) + 3}
            """
            params = [embedding_str, min_similarity, *retention_tiers, top_k]
        else:
            query = """
                SELECT *,
                       1 - (embedding <=> $1::vector) as similarity
                FROM marine_articles
                WHERE embedding IS NOT NULL
                  AND 1 - (embedding <=> $1::vector) >= $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """
            params = [embedding_str, min_similarity, top_k]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            results = []
            for row in rows:
                article = self._row_to_article(row)
                similarity = float(row["similarity"])
                results.append((article, similarity))
            return results

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_similar_articles(
        self,
        article_id: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> list[tuple[Article, float]]:
        """
        Find articles similar to a given article.

        Args:
            article_id: Source article ID
            top_k: Maximum number of similar articles to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of (Article, similarity_score) tuples, excluding the source article
        """
        # Get the source article's embedding
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT embedding FROM marine_articles WHERE id = $1",
                article_id,
            )
            if not row or row["embedding"] is None:
                logger.warning(f"Article {article_id} has no embedding")
                return []

            # Parse embedding
            emb = row["embedding"]
            if isinstance(emb, str):
                query_embedding = [float(x) for x in emb.strip("[]").split(",")]
            else:
                query_embedding = list(emb)

        # Search for similar articles, excluding the source
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *,
                       1 - (embedding <=> $1::vector) as similarity
                FROM marine_articles
                WHERE embedding IS NOT NULL
                  AND id != $2
                  AND 1 - (embedding <=> $1::vector) >= $3
                ORDER BY embedding <=> $1::vector
                LIMIT $4
            """,
                embedding_str,
                article_id,
                min_similarity,
                top_k,
            )

            results = []
            for row in rows:
                article = self._row_to_article(row)
                similarity = float(row["similarity"])
                results.append((article, similarity))
            return results

    async def get_articles_without_embedding(self, limit: int = 100) -> list[Article]:
        """
        Get articles that don't have embeddings yet (for backfill).

        Args:
            limit: Maximum number of articles to return

        Returns:
            List of articles without embeddings
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM marine_articles
                WHERE embedding IS NULL
                ORDER BY created_at DESC
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_article(row) for row in rows]

    async def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about embedding coverage."""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM marine_articles")
            with_embedding = await conn.fetchval(
                "SELECT COUNT(*) FROM marine_articles WHERE embedding IS NOT NULL"
            )
            by_tier = await conn.fetch(
                """
                SELECT retention_tier, COUNT(*) as count
                FROM marine_articles
                GROUP BY retention_tier
            """
            )

            return {
                "total_articles": total,
                "with_embedding": with_embedding,
                "without_embedding": total - with_embedding,
                "embedding_coverage_pct": (
                    round(100 * with_embedding / total, 1) if total > 0 else 0
                ),
                "by_retention_tier": {
                    row["retention_tier"]: row["count"] for row in by_tier
                },
            }

    # =========================================================================
    # Retention Tier Operations
    # =========================================================================

    async def update_article_retention_tier(
        self,
        article_id: str,
        tier: str,
    ) -> bool:
        """
        Update the retention tier for an article.

        Args:
            article_id: Article ID
            tier: Retention tier (hot, warm, cold)

        Returns:
            True if updated, False if article not found
        """
        if tier not in ("hot", "warm", "cold"):
            raise ValueError(
                f"Invalid retention tier: {tier}. Must be hot, warm, or cold"
            )

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE marine_articles
                SET retention_tier = $1,
                    updated_at = NOW()
                WHERE id = $2
            """,
                tier,
                article_id,
            )
            return "UPDATE 1" in result

    async def get_articles_for_retention_transition(
        self,
        current_tier: str,
        min_age_days: int,
        limit: int = 100,
    ) -> list[Article]:
        """
        Get articles eligible for retention tier transition.

        Args:
            current_tier: Current retention tier
            min_age_days: Minimum age in days for transition
            limit: Maximum number of articles to return

        Returns:
            List of articles eligible for transition
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM marine_articles
                WHERE retention_tier = $1
                  AND created_at < NOW() - INTERVAL '1 day' * $2
                ORDER BY created_at ASC
                LIMIT $3
            """,
                current_tier,
                min_age_days,
                limit,
            )
            return [self._row_to_article(row) for row in rows]

    async def compress_article_to_warm(self, article_id: str) -> bool:
        """
        Compress article to warm tier: keep summary, embedding, metadata; truncate content.

        Args:
            article_id: Article ID

        Returns:
            True if compressed, False if article not found
        """
        async with self.pool.acquire() as conn:
            # First check if article has a summary, if not generate one placeholder
            row = await conn.fetchrow(
                "SELECT summary, content FROM marine_articles WHERE id = $1",
                article_id,
            )
            if not row:
                return False

            # Keep first 500 chars of content as excerpt if no summary
            summary = row["summary"]
            if not summary and row["content"]:
                summary = (
                    row["content"][:500] + "..."
                    if len(row["content"]) > 500
                    else row["content"]
                )

            result = await conn.execute(
                """
                UPDATE marine_articles
                SET retention_tier = 'warm',
                    content = NULL,
                    summary = COALESCE($1, summary),
                    updated_at = NOW()
                WHERE id = $2
            """,
                summary,
                article_id,
            )
            return "UPDATE 1" in result

    async def compress_article_to_cold(self, article_id: str) -> bool:
        """
        Compress article to cold tier: keep summary, embedding; minimize metadata.

        Args:
            article_id: Article ID

        Returns:
            True if compressed, False if article not found
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE marine_articles
                SET retention_tier = 'cold',
                    content = NULL,
                    metadata = '{}',
                    updated_at = NOW()
                WHERE id = $1
            """,
                article_id,
            )
            return "UPDATE 1" in result

    async def delete_old_articles(
        self,
        min_age_days: int = 1095,  # 3 years
        limit: int = 100,
    ) -> int:
        """
        Delete articles older than the specified age.

        Args:
            min_age_days: Minimum age in days for deletion (default 3 years)
            limit: Maximum number of articles to delete per call

        Returns:
            Number of articles deleted
        """
        async with self.pool.acquire() as conn:
            # Get IDs of articles to delete
            rows = await conn.fetch(
                """
                SELECT id FROM marine_articles
                WHERE created_at < NOW() - INTERVAL '1 day' * $1
                ORDER BY created_at ASC
                LIMIT $2
            """,
                min_age_days,
                limit,
            )

            if not rows:
                return 0

            ids = [row["id"] for row in rows]
            result = await conn.execute(
                "DELETE FROM marine_articles WHERE id = ANY($1)",
                ids,
            )

            # Extract count from "DELETE N"
            count = int(result.split()[1]) if result.startswith("DELETE") else 0
            logger.info(f"Deleted {count} articles older than {min_age_days} days")
            return count

    def _row_to_article(self, row) -> Article:
        """Convert database row to Article."""
        # Handle embedding - convert from pgvector string format if needed
        embedding = None
        if row.get("embedding") is not None:
            emb = row["embedding"]
            if isinstance(emb, str):
                # pgvector returns string like "[0.1,0.2,...]"
                embedding = [float(x) for x in emb.strip("[]").split(",")]
            elif isinstance(emb, (list, tuple)):
                embedding = list(emb)
            else:
                embedding = list(emb)

        return Article(
            id=row["id"],
            url=row["url"],
            url_hash=row["url_hash"],
            title=row["title"],
            source=row["source"],
            content=row["content"],
            summary=row["summary"],
            published_date=row["published_date"],
            processed_date=row["processed_date"],
            is_processed=row["is_processed"],
            opportunities_generated=row["opportunities_generated"],
            source_category=row["source_category"],
            metadata=(
                json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else (row["metadata"] if row["metadata"] else {})
            ),
            embedding=embedding,
            retention_tier=row.get("retention_tier", "hot"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Account Operations
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def save_account(self, account: Account) -> tuple[str, bool]:
        """
        Save or update an account.

        Uses normalized_name for deduplication. If account exists,
        updates mention_count and last_seen_date.

        Args:
            account: Account to save

        Returns:
            Tuple of (account_id, is_new)
        """
        async with self.pool.acquire() as conn:
            # Check if normalized name already exists
            existing = await conn.fetchrow(
                "SELECT id, mention_count FROM marine_accounts WHERE normalized_name = $1",
                account.normalized_name,
            )

            if existing:
                # Update existing account
                await conn.execute(
                    """
                    UPDATE marine_accounts
                    SET mention_count = mention_count + 1,
                        last_seen_date = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    existing["id"],
                )
                logger.debug(f"Account updated: {account.company_name}")
                return existing["id"], False

            # Insert new account
            await conn.execute(
                """
                INSERT INTO marine_accounts (
                    id, company_name, normalized_name, country, sector, website,
                    mention_count, opportunity_count, first_seen_date, last_seen_date,
                    total_score, priority_rank, crm_account_id, is_existing_customer,
                    aliases, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            """,
                account.id,
                account.company_name,
                account.normalized_name,
                account.country,
                account.sector,
                account.website,
                account.mention_count,
                account.opportunity_count,
                account.first_seen_date,
                account.last_seen_date,
                account.total_score,
                account.priority_rank,
                account.crm_account_id,
                account.is_existing_customer,
                account.aliases,
                account.metadata,
            )

            logger.info(f"New account saved: {account.company_name}")
            return account.id, True

    async def get_account(self, account_id: str) -> Optional[Account]:
        """Get an account by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_accounts WHERE id = $1", account_id
            )
            if row:
                return self._row_to_account(row)
        return None

    async def get_account_by_name(self, company_name: str) -> Optional[Account]:
        """Get an account by company name (using normalized name)."""
        normalized = Account.normalize_company_name(company_name)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_accounts WHERE normalized_name = $1", normalized
            )
            if row:
                return self._row_to_account(row)
        return None

    async def get_or_create_account(
        self,
        company_name: str,
        country: Optional[str] = None,
        sector: Optional[str] = None,
    ) -> tuple[Account, bool]:
        """
        Get existing account or create new one.

        Args:
            company_name: Company name
            country: Country (optional)
            sector: Sector (optional)

        Returns:
            Tuple of (account, is_new)
        """
        existing = await self.get_account_by_name(company_name)
        if existing:
            return existing, False

        account = Account.create(
            company_name=company_name,
            country=country,
            sector=sector,
            mention_count=1,
        )
        await self.save_account(account)
        return account, True

    @with_retry(max_retries=3, base_delay=0.5)
    async def list_accounts(
        self,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        is_existing_customer: Optional[bool] = None,
        min_mentions: int = 0,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Account]:
        """List accounts with optional filters."""
        query = "SELECT * FROM marine_accounts WHERE mention_count >= $1"
        params: list[Any] = [min_mentions]
        param_idx = 2

        if country:
            query += f" AND country = ${param_idx}"
            params.append(country)
            param_idx += 1

        if sector:
            query += f" AND sector = ${param_idx}"
            params.append(sector)
            param_idx += 1

        if is_existing_customer is not None:
            query += f" AND is_existing_customer = ${param_idx}"
            params.append(is_existing_customer)
            param_idx += 1

        query += f" ORDER BY total_score DESC, mention_count DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_account(row) for row in rows]

    async def get_top_accounts(
        self,
        limit: int = 20,
        by: str = "score",  # "score", "mentions", "opportunities"
    ) -> list[Account]:
        """Get top accounts by score, mentions, or opportunities."""
        order_by = {
            "score": "total_score DESC",
            "mentions": "mention_count DESC",
            "opportunities": "opportunity_count DESC",
        }.get(by, "total_score DESC")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM marine_accounts
                ORDER BY {order_by}
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_account(row) for row in rows]

    async def increment_account_opportunity_count(
        self,
        account_id: str,
        score_to_add: float = 0.0,
    ) -> bool:
        """Increment opportunity count and add to total score."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE marine_accounts
                SET opportunity_count = opportunity_count + 1,
                    total_score = total_score + $1,
                    updated_at = NOW()
                WHERE id = $2
            """,
                score_to_add,
                account_id,
            )
            return "UPDATE 1" in result

    async def update_account_crm_id(
        self,
        account_id: str,
        crm_account_id: str,
        is_existing_customer: bool = True,
    ) -> bool:
        """Update account CRM integration fields."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE marine_accounts
                SET crm_account_id = $1,
                    is_existing_customer = $2,
                    updated_at = NOW()
                WHERE id = $3
            """,
                crm_account_id,
                is_existing_customer,
                account_id,
            )
            return "UPDATE 1" in result

    async def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM marine_accounts WHERE id = $1", account_id
            )
            return "DELETE 1" in result

    def _row_to_account(self, row) -> Account:
        """Convert database row to Account."""
        return Account(
            id=row["id"],
            company_name=row["company_name"],
            normalized_name=row["normalized_name"],
            country=row["country"],
            sector=row["sector"],
            website=row["website"],
            mention_count=row["mention_count"],
            opportunity_count=row["opportunity_count"],
            first_seen_date=row["first_seen_date"],
            last_seen_date=row["last_seen_date"],
            total_score=row["total_score"],
            priority_rank=row["priority_rank"],
            crm_account_id=row["crm_account_id"],
            is_existing_customer=row["is_existing_customer"],
            aliases=list(row["aliases"]) if row["aliases"] else [],
            metadata=(
                json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else (row["metadata"] if row["metadata"] else {})
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Article-Account Mention Operations
    # =========================================================================

    async def save_article_account_mention(
        self,
        article_id: str,
        account_id: str,
        mention_context: Optional[str] = None,
    ) -> bool:
        """
        Save an article-account mention relationship.

        Args:
            article_id: Article ID
            account_id: Account ID
            mention_context: Excerpt where company was mentioned

        Returns:
            True if saved, False if already exists
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO marine_article_accounts (article_id, account_id, mention_context)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (article_id, account_id) DO NOTHING
                """,
                    article_id,
                    account_id,
                    mention_context,
                )
                return True
            except Exception as e:
                logger.error(f"Failed to save article-account mention: {e}")
                return False

    async def get_articles_for_account(self, account_id: str) -> list[Article]:
        """Get all articles that mention a specific account."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.* FROM marine_articles a
                JOIN marine_article_accounts aa ON a.id = aa.article_id
                WHERE aa.account_id = $1
                ORDER BY a.published_date DESC
            """,
                account_id,
            )
            return [self._row_to_article(row) for row in rows]

    async def get_accounts_in_article(self, article_id: str) -> list[Account]:
        """Get all accounts mentioned in a specific article."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT acc.* FROM marine_accounts acc
                JOIN marine_article_accounts aa ON acc.id = aa.account_id
                WHERE aa.article_id = $1
                ORDER BY acc.total_score DESC
            """,
                article_id,
            )
            return [self._row_to_account(row) for row in rows]

    # =========================================================================
    # Opportunity Operations (Primary sales opportunity storage)
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def save_opportunity(self, opp: MarineOpportunity) -> tuple[str, bool]:
        """
        Save a marine opportunity with deduplication.

        Uses URL hash to detect duplicates.

        Args:
            opp: MarineOpportunity to save

        Returns:
            Tuple of (opportunity_id, is_new). is_new=False means duplicate was skipped.
        """
        async with self.pool.acquire() as conn:
            # Check if URL hash already exists (deduplication)
            existing = await conn.fetchval(
                "SELECT id FROM marine_opportunities WHERE url_hash = $1", opp.url_hash
            )

            if existing:
                logger.debug(f"Duplicate opportunity skipped: {opp.source_url}")
                return existing, False

            # Insert new opportunity
            await conn.execute(
                """
                INSERT INTO marine_opportunities (
                    id, headline, source_name, source_url, url_hash,
                    sales_signals, region, vessel_types, sector,
                    companies_involved, country,
                    sales_explanation, suggested_action,
                    source_category, discovered_at, published_date, raw_content,
                    estimated_value, currency, engine_power_range, contact_info,
                    reviewed, exported_to_crm, priority
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24)
            """,
                opp.id,
                opp.headline,
                opp.source_name,
                opp.source_url,
                opp.url_hash,
                opp.sales_signals,
                opp.region,
                opp.vessel_types,
                opp.sector,
                opp.companies_involved,
                opp.country,
                opp.sales_explanation,
                opp.suggested_action,
                opp.source_category,
                opp.discovered_at,
                opp.published_date,
                opp.raw_content,
                opp.estimated_value,
                opp.currency,
                opp.engine_power_range,
                opp.contact_info,
                opp.reviewed,
                opp.exported_to_crm,
                opp.priority,
            )

            logger.info(f"New opportunity saved: {opp.headline[:50]}...")

            # Auto-create/update accounts from companies_involved
            if opp.companies_involved:
                for company in opp.companies_involved:
                    try:
                        account, is_new = await self.get_or_create_account(
                            company_name=company,
                            country=opp.country,
                            sector=opp.sector,
                        )
                        await self.increment_account_opportunity_count(
                            account.id, score_to_add=1.0
                        )
                    except Exception as e:
                        logger.warning(f"Failed to link account {company}: {e}")

            return opp.id, True

    async def check_url_exists(self, url: str) -> bool:
        """Check if a URL already exists in the database."""
        url_hash = MarineOpportunity.generate_url_hash(url)
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM marine_opportunities WHERE url_hash = $1)",
                url_hash,
            )
            return exists

    async def get_opportunity(self, opp_id: str) -> Optional[MarineOpportunity]:
        """Get an opportunity by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_opportunities WHERE id = $1", opp_id
            )
            if row:
                return self._row_to_opportunity(row)
        return None

    async def list_opportunities(
        self,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        sales_signal: Optional[str] = None,
        vessel_type: Optional[str] = None,
        reviewed: Optional[bool] = None,
        min_priority: int = 1,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MarineOpportunity]:
        """List opportunities with optional filters."""
        query = "SELECT * FROM marine_opportunities WHERE priority >= $1"
        params: list[Any] = [min_priority]
        param_idx = 2

        if region:
            query += f" AND region = ${param_idx}"
            params.append(region)
            param_idx += 1

        if sector:
            query += f" AND sector = ${param_idx}"
            params.append(sector)
            param_idx += 1

        if sales_signal:
            query += f" AND ${param_idx} = ANY(sales_signals)"
            params.append(sales_signal)
            param_idx += 1

        if vessel_type:
            query += f" AND ${param_idx} = ANY(vessel_types)"
            params.append(vessel_type)
            param_idx += 1

        if reviewed is not None:
            query += f" AND reviewed = ${param_idx}"
            params.append(reviewed)
            param_idx += 1

        query += f" ORDER BY priority DESC, discovered_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_opportunity(row) for row in rows]

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_recent_opportunities(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> list[MarineOpportunity]:
        """Get opportunities from the last N days.

        Uses published_date (real article date) for recency, with
        discovered_at as fallback for records without published_date.
        Records with real published_date are prioritized over those
        using discovered_at only.
        """
        # Validate days parameter to prevent any injection
        if not isinstance(days, int) or days < 1 or days > 365:
            days = 7
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            limit = 50

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM marine_opportunities
                WHERE COALESCE(published_date, discovered_at) >= NOW() - INTERVAL '1 day' * $1
                ORDER BY
                    (published_date IS NOT NULL) DESC,
                    COALESCE(published_date, discovered_at) DESC
                LIMIT $2
            """,
                days,
                limit,
            )
            return [self._row_to_opportunity(row) for row in rows]

    async def search_opportunities_by_company(
        self,
        company_name: str,
        limit: int = 15,
    ) -> list[MarineOpportunity]:
        """Search opportunities where a company is mentioned.

        Searches companies_involved array and headline for the company name.
        Results sorted by published_date (real date first, then discovered_at).
        """
        if not company_name or len(company_name) < 2:
            return []
        search_term = f"%{company_name}%"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM marine_opportunities
                WHERE headline ILIKE $1
                   OR EXISTS (
                       SELECT 1 FROM unnest(companies_involved) c
                       WHERE c ILIKE $1
                   )
                ORDER BY
                    (published_date IS NOT NULL) DESC,
                    COALESCE(published_date, discovered_at) DESC
                LIMIT $2
                """,
                search_term,
                limit,
            )
            return [self._row_to_opportunity(row) for row in rows]

    async def search_articles_by_company(
        self,
        company_name: str,
        limit: int = 10,
    ) -> list:
        """Search RSS articles mentioning a company by title.

        Returns list of dicts with title, url, published_date, source.
        """
        if not company_name or len(company_name) < 2:
            return []
        search_term = f"%{company_name}%"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT title, url, published_date, source, summary
                FROM marine_articles
                WHERE title ILIKE $1
                ORDER BY published_date DESC
                LIMIT $2
                """,
                search_term,
                limit,
            )
            return [dict(row) for row in rows]

    async def mark_reviewed(self, opp_id: str) -> bool:
        """Mark an opportunity as reviewed."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE marine_opportunities SET reviewed = TRUE, updated_at = NOW() WHERE id = $1",
                opp_id,
            )
            return "UPDATE 1" in result

    async def mark_exported(self, opp_id: str) -> bool:
        """Mark an opportunity as exported to CRM."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE marine_opportunities SET exported_to_crm = TRUE, updated_at = NOW() WHERE id = $1",
                opp_id,
            )
            return "UPDATE 1" in result

    async def update_priority(self, opp_id: str, priority: int) -> bool:
        """Update opportunity priority (1-10)."""
        priority = max(1, min(10, priority))  # Clamp to 1-10
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE marine_opportunities SET priority = $1, updated_at = NOW() WHERE id = $2",
                priority,
                opp_id,
            )
            return "UPDATE 1" in result

    async def delete_opportunity(self, opp_id: str) -> bool:
        """Delete an opportunity."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM marine_opportunities WHERE id = $1", opp_id
            )
            return "DELETE 1" in result

    def _row_to_opportunity(self, row) -> MarineOpportunity:
        """Convert database row to MarineOpportunity."""
        return MarineOpportunity(
            id=row["id"],
            headline=row["headline"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            url_hash=row["url_hash"],
            sales_signals=list(row["sales_signals"]) if row["sales_signals"] else [],
            region=row["region"],
            vessel_types=list(row["vessel_types"]) if row["vessel_types"] else [],
            sector=row["sector"],
            companies_involved=(
                list(row["companies_involved"]) if row["companies_involved"] else []
            ),
            country=row["country"],
            sales_explanation=row["sales_explanation"],
            suggested_action=row["suggested_action"],
            source_category=row["source_category"],
            discovered_at=row["discovered_at"],
            published_date=row["published_date"],
            raw_content=row["raw_content"],
            estimated_value=row["estimated_value"],
            currency=row["currency"],
            engine_power_range=row["engine_power_range"],
            contact_info=row["contact_info"],
            reviewed=row["reviewed"],
            exported_to_crm=row["exported_to_crm"],
            priority=row["priority"],
        )

    # =========================================================================
    # Job Operations
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def save_job(self, job: ResearchJob) -> str:
        """Save a research job."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO marine_research_jobs (
                    id, job_type, status, started_at, completed_at,
                    queries_executed, articles_processed, opportunities_found,
                    duplicates_skipped, errors, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    queries_executed = EXCLUDED.queries_executed,
                    articles_processed = EXCLUDED.articles_processed,
                    opportunities_found = EXCLUDED.opportunities_found,
                    duplicates_skipped = EXCLUDED.duplicates_skipped,
                    errors = EXCLUDED.errors,
                    error_message = EXCLUDED.error_message
            """,
                job.id,
                job.job_type,
                job.status,
                job.started_at,
                job.completed_at,
                job.queries_executed,
                job.articles_processed,
                job.opportunities_found,
                job.duplicates_skipped,
                job.errors,
                job.error_message,
            )
        return job.id

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_job(self, job_id: str) -> Optional[ResearchJob]:
        """Get a job by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_research_jobs WHERE id = $1", job_id
            )
            if row:
                return ResearchJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    queries_executed=row["queries_executed"],
                    articles_processed=row.get("articles_processed", 0) or 0,
                    opportunities_found=row["opportunities_found"],
                    duplicates_skipped=row["duplicates_skipped"],
                    errors=row["errors"],
                    error_message=row["error_message"],
                )
        return None

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_latest_job(self) -> Optional[ResearchJob]:
        """Get the most recent research job."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM marine_research_jobs ORDER BY started_at DESC LIMIT 1"
            )
            if row:
                return ResearchJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    queries_executed=row["queries_executed"],
                    articles_processed=row.get("articles_processed", 0) or 0,
                    opportunities_found=row["opportunities_found"],
                    duplicates_skipped=row["duplicates_skipped"],
                    errors=row["errors"],
                    error_message=row["error_message"],
                )
        return None

    @with_retry(max_retries=3, base_delay=0.5)
    async def cleanup_stale_jobs(self, stale_minutes: int = 10) -> int:
        """
        Mark stale running jobs as failed.

        A job is considered stale if:
        - Status is "running"
        - Started more than stale_minutes ago
        - No progress (queries_executed = 0)

        This handles orphaned jobs from container restarts.

        Args:
            stale_minutes: Minutes after which a running job with no progress is stale

        Returns:
            Number of jobs marked as failed
        """
        # Validate parameter
        if not isinstance(stale_minutes, int) or stale_minutes < 1:
            stale_minutes = 10

        async with self.pool.acquire() as conn:
            # Use simple interval - 10 minutes is the standard stale threshold
            # Handle NULL queries_executed (from old job records) by using COALESCE
            # Note: We only check queries_executed as articles_processed column
            # may not exist on older database schemas
            result = await conn.execute(
                """
                UPDATE marine_research_jobs
                SET status = 'failed',
                    completed_at = NOW(),
                    error_message = 'Job marked as stale - no progress after container restart'
                WHERE status = 'running'
                  AND COALESCE(queries_executed, 0) = 0
                  AND started_at < NOW() - INTERVAL '10 minutes'
            """
            )
            # Parse "UPDATE N" result from asyncpg
            # asyncpg returns string like "UPDATE 1" for UPDATE statements
            count = 0
            if result:
                try:
                    # Result format: "UPDATE N" where N is number of rows affected
                    parts = str(result).split()
                    if len(parts) >= 2 and parts[0].upper() == "UPDATE":
                        count = int(parts[1])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse UPDATE result '{result}': {e}")
            if count > 0:
                logger.info(f"Cleaned up {count} stale marine intel jobs")
            return count

    @with_retry(max_retries=3, base_delay=0.5)
    async def list_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> list[ResearchJob]:
        """
        List research jobs with optional filters.

        Args:
            job_type: Filter by job type (e.g., "daily_research")
            status: Filter by status (e.g., "completed", "failed")
            limit: Maximum number of jobs to return

        Returns:
            List of ResearchJob objects
        """
        # Validate limit
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            limit = 10

        query = "SELECT * FROM marine_research_jobs WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if job_type:
            query += f" AND job_type = ${param_idx}"
            params.append(job_type)
            param_idx += 1

        if status:
            query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        query += f" ORDER BY started_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                ResearchJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    queries_executed=row["queries_executed"],
                    articles_processed=row.get("articles_processed", 0) or 0,
                    opportunities_found=row["opportunities_found"],
                    duplicates_skipped=row["duplicates_skipped"],
                    errors=row["errors"],
                    error_message=row["error_message"],
                )
                for row in rows
            ]

    # =========================================================================
    # Statistics
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        async with self.pool.acquire() as conn:
            # Total counts
            total_opps = await conn.fetchval(
                "SELECT COUNT(*) FROM marine_opportunities"
            )
            unreviewed = await conn.fetchval(
                "SELECT COUNT(*) FROM marine_opportunities WHERE reviewed = FALSE"
            )
            high_priority = await conn.fetchval(
                "SELECT COUNT(*) FROM marine_opportunities WHERE priority >= 8"
            )

            # By region
            opps_by_region = {}
            rows = await conn.fetch(
                """
                SELECT region, COUNT(*) as count
                FROM marine_opportunities
                GROUP BY region
                ORDER BY count DESC
            """
            )
            for row in rows:
                opps_by_region[row["region"]] = row["count"]

            # By sales signal
            opps_by_signal = {}
            rows = await conn.fetch(
                """
                SELECT unnest(sales_signals) as signal, COUNT(*) as count
                FROM marine_opportunities
                GROUP BY signal
                ORDER BY count DESC
            """
            )
            for row in rows:
                opps_by_signal[row["signal"]] = row["count"]

            # By sector
            opps_by_sector = {}
            rows = await conn.fetch(
                """
                SELECT sector, COUNT(*) as count
                FROM marine_opportunities
                GROUP BY sector
                ORDER BY count DESC
            """
            )
            for row in rows:
                opps_by_sector[row["sector"]] = row["count"]

            # Recent activity
            last_7_days = await conn.fetchval(
                """
                SELECT COUNT(*) FROM marine_opportunities
                WHERE discovered_at >= NOW() - INTERVAL '7 days'
            """
            )

            return {
                "total_opportunities": total_opps,
                "unreviewed": unreviewed,
                "high_priority": high_priority,
                "last_7_days": last_7_days,
                "by_region": opps_by_region,
                "by_sales_signal": opps_by_signal,
                "by_sector": opps_by_sector,
            }


# Singleton instance
_db: Optional[MarineIntelDatabase] = None


def get_marine_intel_db() -> MarineIntelDatabase:
    """Get or create the marine intel database singleton."""
    global _db
    if _db is None:
        _db = MarineIntelDatabase()
    return _db


async def initialize_marine_intel_db() -> MarineIntelDatabase:
    """Initialize and return the marine intel database."""
    db = get_marine_intel_db()
    await db.initialize()
    return db
