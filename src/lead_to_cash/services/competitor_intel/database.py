"""
PostgreSQL + pgvector Database Layer for Competitor Intelligence

Production-ready database operations using raw asyncpg for performance.
NO MOCKS, NO FALLBACKS - real PostgreSQL with pgvector extension.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import asyncpg

from lead_to_cash.services.competitor_intel.models import (
    CompetitorDocument,
    DocumentChunk,
    ScrapingJob,
)
from lead_to_cash.services.competitor_intel.signal_models import (
    CompetitorFinancials,
    CompetitorSignal,
)

logger = logging.getLogger(__name__)


class CompetitorIntelDatabase:
    """
    PostgreSQL + pgvector database for competitor intelligence.

    Uses asyncpg for high-performance async database operations.
    Stores document embeddings in pgvector for semantic search.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection string. If not provided,
                         uses DATABASE_URL environment variable.

        Note: Database URL validation is deferred until actual connection
        to allow service construction without environment variables.
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
        - competitor_documents table
        - document_chunks table with vector column
        - scraping_jobs table
        - HNSW index on embeddings
        """
        if self._initialized:
            return

        logger.info("Initializing PostgreSQL + pgvector database")

        # Create connection pool
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        async with self.pool.acquire() as conn:
            # Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("pgvector extension enabled")

            # Create competitor_documents table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS competitor_documents (
                    id TEXT PRIMARY KEY,
                    competitor TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    source_url TEXT DEFAULT '',
                    published_date TIMESTAMPTZ,
                    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}',
                    customer_mentioned TEXT,
                    deal_value FLOAT,
                    region TEXT,
                    industry_segment TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create document_chunks table with vector column
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES competitor_documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(1536),
                    token_count INTEGER NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    competitor TEXT,
                    content_type TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Create scraping_jobs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    documents_processed INTEGER DEFAULT 0,
                    documents_failed INTEGER DEFAULT 0,
                    chunks_created INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """
            )

            # Create indexes
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_competitor
                ON competitor_documents(competitor)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_content_type
                ON competitor_documents(content_type)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_scraped_at
                ON competitor_documents(scraped_at DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                ON document_chunks(document_id)
            """
            )

            # Create HNSW index for vector similarity search
            # Using cosine distance (<=>) which is best for text embeddings
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
            )
            logger.info("HNSW vector index created")

            # =================================================================
            # Enhanced Competitor Intelligence Tables
            # =================================================================

            # Create competitor_signals table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS competitor_signals (
                    id TEXT PRIMARY KEY,
                    competitor TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    headline TEXT NOT NULL,
                    description TEXT,
                    raw_content TEXT,
                    score INTEGER DEFAULT 0,
                    score_breakdown JSONB DEFAULT '{}',
                    customer_mentioned TEXT,
                    project_name TEXT,
                    vessel_type TEXT,
                    engine_model TEXT,
                    fuel_type TEXT,
                    contract_value_usd FLOAT,
                    region TEXT,
                    country TEXT,
                    is_apac BOOLEAN DEFAULT FALSE,
                    is_singapore BOOLEAN DEFAULT FALSE,
                    keywords_matched JSONB DEFAULT '[]',
                    source_url TEXT DEFAULT '',
                    published_date TIMESTAMPTZ,
                    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )
            logger.info("competitor_signals table created")

            # Create competitor_financials table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS competitor_financials (
                    id TEXT PRIMARY KEY,
                    competitor TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    period_type TEXT NOT NULL,
                    fiscal_period TEXT NOT NULL,
                    report_date TIMESTAMPTZ NOT NULL,
                    revenue_usd FLOAT,
                    operating_income_usd FLOAT,
                    net_income_usd FLOAT,
                    rd_spending_usd FLOAT,
                    capex_usd FLOAT,
                    order_backlog_usd FLOAT,
                    marine_segment_revenue FLOAT,
                    energy_segment_revenue FLOAT,
                    power_systems_revenue FLOAT,
                    gross_margin_pct FLOAT,
                    operating_margin_pct FLOAT,
                    revenue_growth_yoy_pct FLOAT,
                    revenue_growth_qoq_pct FLOAT,
                    guidance_notes TEXT,
                    source_url TEXT DEFAULT '',
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    raw_data JSONB DEFAULT '{}',
                    UNIQUE (competitor, period_type, fiscal_period)
                )
            """
            )
            logger.info("competitor_financials table created")

            # Create indexes for signals
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_competitor
                ON competitor_signals(competitor)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_type
                ON competitor_signals(signal_type)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_score
                ON competitor_signals(score DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_discovered
                ON competitor_signals(discovered_at DESC)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_source_channel
                ON competitor_signals(source_channel)
            """
            )

            # Create indexes for financials
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financials_competitor
                ON competitor_financials(competitor)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financials_period
                ON competitor_financials(fiscal_period)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financials_report_date
                ON competitor_financials(report_date DESC)
            """
            )
            logger.info("Signal and financial indexes created")

        self._initialized = True
        logger.info("Database initialization complete")

    async def close(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False

    # =========================================================================
    # Document Operations
    # =========================================================================

    async def save_document(self, doc: CompetitorDocument) -> str:
        """
        Save a competitor document to the database.

        Args:
            doc: CompetitorDocument to save

        Returns:
            Document ID
        """
        # Serialize metadata dict to JSON string for JSONB column
        metadata_str = (
            json.dumps(doc.metadata) if isinstance(doc.metadata, dict) else doc.metadata
        )

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO competitor_documents (
                    id, competitor, content_type, source_type, title, content,
                    summary, source_url, published_date, scraped_at, metadata,
                    customer_mentioned, deal_value, region, industry_segment
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    summary = EXCLUDED.summary,
                    scraped_at = EXCLUDED.scraped_at,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """,
                doc.id,
                doc.competitor,
                doc.content_type,
                doc.source_type,
                doc.title,
                doc.content,
                doc.summary,
                doc.source_url,
                doc.published_date,
                doc.scraped_at,
                metadata_str,
                doc.customer_mentioned,
                doc.deal_value,
                doc.region,
                doc.industry_segment,
            )
        return doc.id

    async def get_document(self, doc_id: str) -> Optional[CompetitorDocument]:
        """Get a document by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM competitor_documents WHERE id = $1", doc_id
            )
            if row:
                return CompetitorDocument(
                    id=row["id"],
                    competitor=row["competitor"],
                    content_type=row["content_type"],
                    source_type=row["source_type"],
                    title=row["title"],
                    content=row["content"],
                    summary=row["summary"],
                    source_url=row["source_url"],
                    published_date=row["published_date"],
                    scraped_at=row["scraped_at"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                    customer_mentioned=row["customer_mentioned"],
                    deal_value=row["deal_value"],
                    region=row["region"],
                    industry_segment=row["industry_segment"],
                )
        return None

    async def get_document_by_url(self, url: str) -> Optional[CompetitorDocument]:
        """Get a document by source URL (for deduplication)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM competitor_documents WHERE source_url = $1", url
            )
            if row:
                return CompetitorDocument(
                    id=row["id"],
                    competitor=row["competitor"],
                    content_type=row["content_type"],
                    source_type=row["source_type"],
                    title=row["title"],
                    content=row["content"],
                    summary=row["summary"],
                    source_url=row["source_url"],
                    published_date=row["published_date"],
                    scraped_at=row["scraped_at"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                    customer_mentioned=row["customer_mentioned"],
                    deal_value=row["deal_value"],
                    region=row["region"],
                    industry_segment=row["industry_segment"],
                )
        return None

    async def get_documents_by_ids(
        self, doc_ids: list[str]
    ) -> dict[str, CompetitorDocument]:
        """
        Get multiple documents by their IDs in a single query.

        Args:
            doc_ids: List of document IDs to fetch

        Returns:
            Dictionary mapping document ID to CompetitorDocument
        """
        if not doc_ids:
            return {}

        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(doc_ids))

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM competitor_documents WHERE id = ANY($1)",
                unique_ids,
            )

            result = {}
            for row in rows:
                result[row["id"]] = CompetitorDocument(
                    id=row["id"],
                    competitor=row["competitor"],
                    content_type=row["content_type"],
                    source_type=row["source_type"],
                    title=row["title"],
                    content=row["content"],
                    summary=row["summary"],
                    source_url=row["source_url"],
                    published_date=row["published_date"],
                    scraped_at=row["scraped_at"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                    customer_mentioned=row["customer_mentioned"],
                    deal_value=row["deal_value"],
                    region=row["region"],
                    industry_segment=row["industry_segment"],
                )
            return result

    async def list_documents(
        self,
        competitor: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[CompetitorDocument]:
        """List documents with optional filters."""
        query = "SELECT * FROM competitor_documents WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if competitor:
            query += f" AND competitor = ${param_idx}"
            params.append(competitor)
            param_idx += 1

        if content_type:
            query += f" AND content_type = ${param_idx}"
            params.append(content_type)
            param_idx += 1

        query += f" ORDER BY scraped_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                CompetitorDocument(
                    id=row["id"],
                    competitor=row["competitor"],
                    content_type=row["content_type"],
                    source_type=row["source_type"],
                    title=row["title"],
                    content=row["content"],
                    summary=row["summary"],
                    source_url=row["source_url"],
                    published_date=row["published_date"],
                    scraped_at=row["scraped_at"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                    customer_mentioned=row["customer_mentioned"],
                    deal_value=row["deal_value"],
                    region=row["region"],
                    industry_segment=row["industry_segment"],
                )
                for row in rows
            ]

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its chunks (cascading)."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM competitor_documents WHERE id = $1", doc_id
            )
            return "DELETE 1" in result

    # =========================================================================
    # Chunk Operations with pgvector
    # =========================================================================

    async def save_chunk(self, chunk: DocumentChunk) -> str:
        """Save a document chunk with embedding."""
        async with self.pool.acquire() as conn:
            # Convert embedding list to pgvector format
            embedding_str = f"[{','.join(str(x) for x in chunk.embedding)}]"

            # Serialize metadata dict to JSON string for JSONB column
            metadata_str = (
                json.dumps(chunk.metadata)
                if isinstance(chunk.metadata, dict)
                else chunk.metadata
            )
            await conn.execute(
                """
                INSERT INTO document_chunks (
                    id, document_id, chunk_index, content, embedding,
                    token_count, metadata, competitor, content_type
                ) VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    token_count = EXCLUDED.token_count
            """,
                chunk.id,
                chunk.document_id,
                chunk.chunk_index,
                chunk.content,
                embedding_str,
                chunk.token_count,
                metadata_str,
                (
                    chunk.metadata.get("competitor")
                    if isinstance(chunk.metadata, dict)
                    else None
                ),
                (
                    chunk.metadata.get("content_type")
                    if isinstance(chunk.metadata, dict)
                    else None
                ),
            )
        return chunk.id

    async def save_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Save multiple chunks efficiently."""
        if not chunks:
            return 0

        async with self.pool.acquire() as conn:
            # Use COPY for bulk insert when possible
            for chunk in chunks:
                embedding_str = f"[{','.join(str(x) for x in chunk.embedding)}]"
                # Serialize metadata dict to JSON string for JSONB column
                metadata_str = (
                    json.dumps(chunk.metadata)
                    if isinstance(chunk.metadata, dict)
                    else chunk.metadata
                )
                await conn.execute(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, chunk_index, content, embedding,
                        token_count, metadata, competitor, content_type
                    ) VALUES ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9)
                    ON CONFLICT (id) DO NOTHING
                """,
                    chunk.id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.content,
                    embedding_str,
                    chunk.token_count,
                    metadata_str,
                    (
                        chunk.metadata.get("competitor")
                        if isinstance(chunk.metadata, dict)
                        else None
                    ),
                    (
                        chunk.metadata.get("content_type")
                        if isinstance(chunk.metadata, dict)
                        else None
                    ),
                )
        return len(chunks)

    async def get_chunks_for_document(self, doc_id: str) -> list[DocumentChunk]:
        """Get all chunks for a document."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, document_id, chunk_index, content,
                          embedding::text, token_count, metadata
                   FROM document_chunks
                   WHERE document_id = $1
                   ORDER BY chunk_index""",
                doc_id,
            )
            return [
                DocumentChunk(
                    id=row["id"],
                    document_id=row["document_id"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    embedding=self._parse_vector(row["embedding"]),
                    token_count=row["token_count"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                )
                for row in rows
            ]

    def _parse_vector(self, vector_str: str) -> list[float]:
        """Parse pgvector string representation to list of floats."""
        if not vector_str:
            return []
        # Remove brackets and parse
        clean = vector_str.strip("[]")
        if not clean:
            return []
        return [float(x) for x in clean.split(",")]

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        competitor: Optional[str] = None,
        content_type: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Perform semantic similarity search using pgvector.

        Uses cosine distance with HNSW index for fast search.

        Args:
            query_embedding: 1536-dim query vector
            top_k: Number of results to return
            competitor: Optional competitor filter
            content_type: Optional content type filter
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of (chunk, similarity_score) tuples
        """
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Build query with optional filters
        query = """
            SELECT
                id, document_id, chunk_index, content,
                embedding::text, token_count, metadata,
                1 - (embedding <=> $1::vector) as similarity
            FROM document_chunks
            WHERE embedding IS NOT NULL
        """
        params: list[Any] = [embedding_str]
        param_idx = 2

        if competitor:
            query += f" AND competitor = ${param_idx}"
            params.append(competitor)
            param_idx += 1

        if content_type:
            query += f" AND content_type = ${param_idx}"
            params.append(content_type)
            param_idx += 1

        if min_similarity > 0:
            query += f" AND 1 - (embedding <=> $1::vector) >= ${param_idx}"
            params.append(min_similarity)
            param_idx += 1

        query += f" ORDER BY embedding <=> $1::vector LIMIT ${param_idx}"
        params.append(top_k)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            results = []
            for row in rows:
                chunk = DocumentChunk(
                    id=row["id"],
                    document_id=row["document_id"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    embedding=self._parse_vector(row["embedding"]),
                    token_count=row["token_count"],
                    metadata=(
                        json.loads(row["metadata"])
                        if isinstance(row["metadata"], str)
                        else (row["metadata"] if row["metadata"] else {})
                    ),
                )
                results.append((chunk, row["similarity"]))
            return results

    # =========================================================================
    # Job Operations
    # =========================================================================

    async def save_job(self, job: ScrapingJob) -> str:
        """Save a scraping job."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scraping_jobs (
                    id, job_type, status, started_at, completed_at,
                    documents_processed, documents_failed, chunks_created, error_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    documents_processed = EXCLUDED.documents_processed,
                    documents_failed = EXCLUDED.documents_failed,
                    chunks_created = EXCLUDED.chunks_created,
                    error_message = EXCLUDED.error_message
            """,
                job.id,
                job.job_type,
                job.status,
                job.started_at,
                job.completed_at,
                job.documents_processed,
                job.documents_failed,
                job.chunks_created,
                job.error_message,
            )
        return job.id

    async def get_job(self, job_id: str) -> Optional[ScrapingJob]:
        """Get a job by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM scraping_jobs WHERE id = $1", job_id
            )
            if row:
                return ScrapingJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    documents_processed=row["documents_processed"],
                    documents_failed=row["documents_failed"],
                    chunks_created=row["chunks_created"],
                    error_message=row["error_message"],
                )
        return None

    async def get_latest_job(self) -> Optional[ScrapingJob]:
        """Get the most recent job."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM scraping_jobs ORDER BY started_at DESC LIMIT 1"
            )
            if row:
                return ScrapingJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    documents_processed=row["documents_processed"],
                    documents_failed=row["documents_failed"],
                    chunks_created=row["chunks_created"],
                    error_message=row["error_message"],
                )
        return None

    async def list_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> list[ScrapingJob]:
        """
        List scraping jobs with optional filters.

        Args:
            job_type: Filter by job type (e.g., "daily_refresh", "weekly_full")
            status: Filter by status (e.g., "completed", "failed")
            limit: Maximum number of jobs to return (default: 10, max: 100)

        Returns:
            List of ScrapingJob objects ordered by started_at descending
        """
        limit = min(max(1, limit), 100)

        conditions = []
        params = []
        param_idx = 1

        if job_type:
            conditions.append(f"job_type = ${param_idx}")
            params.append(job_type)
            param_idx += 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        query = f"""
            SELECT * FROM scraping_jobs
            {where_clause}
            ORDER BY started_at DESC
            LIMIT ${param_idx}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                ScrapingJob(
                    id=row["id"],
                    job_type=row["job_type"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    documents_processed=row["documents_processed"],
                    documents_failed=row["documents_failed"],
                    chunks_created=row["chunks_created"],
                    error_message=row["error_message"],
                )
                for row in rows
            ]

    async def cleanup_stale_jobs(self, stale_minutes: int = 60) -> int:
        """
        Clean up stale jobs that have been running too long.

        Marks as failed any jobs that have been "running" for more than
        stale_minutes with no progress. This handles orphaned jobs from
        container restarts.

        Args:
            stale_minutes: Minutes after which a running job is considered stale

        Returns:
            Number of jobs marked as failed
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE scraping_jobs
                SET status = 'failed',
                    completed_at = NOW(),
                    error_message = 'Job marked as failed by cleanup (stale)'
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '1 minute' * $1
                  AND documents_processed = 0
                """,
                stale_minutes,
            )
            # Extract count from "UPDATE N" result
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                logger.info(f"Cleaned up {count} stale competitor intel job(s)")
            return count

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        async with self.pool.acquire() as conn:
            # Total counts
            total_docs = await conn.fetchval(
                "SELECT COUNT(*) FROM competitor_documents"
            )
            total_chunks = await conn.fetchval("SELECT COUNT(*) FROM document_chunks")
            total_embedded = await conn.fetchval(
                "SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL"
            )

            # By competitor
            docs_by_competitor = {}
            rows = await conn.fetch(
                """
                SELECT competitor, COUNT(*) as count
                FROM competitor_documents
                GROUP BY competitor
            """
            )
            for row in rows:
                docs_by_competitor[row["competitor"]] = row["count"]

            # By content type
            docs_by_type = {}
            rows = await conn.fetch(
                """
                SELECT content_type, COUNT(*) as count
                FROM competitor_documents
                GROUP BY content_type
            """
            )
            for row in rows:
                docs_by_type[row["content_type"]] = row["count"]

            return {
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "total_embedded_chunks": total_embedded,
                "documents_by_competitor": docs_by_competitor,
                "documents_by_type": docs_by_type,
            }

    # =========================================================================
    # Competitor Signal Operations
    # =========================================================================

    async def save_signal(self, signal: CompetitorSignal) -> str:
        """
        Save a competitor signal to the database.

        Args:
            signal: CompetitorSignal to save

        Returns:
            Signal ID
        """
        import json

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO competitor_signals (
                    id, competitor, signal_type, source_channel,
                    headline, description, raw_content,
                    score, score_breakdown,
                    customer_mentioned, project_name, vessel_type, engine_model, fuel_type,
                    contract_value_usd, region, country, is_apac, is_singapore,
                    keywords_matched, source_url, published_date, discovered_at, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20, $21, $22, $23, $24
                )
                ON CONFLICT (id) DO UPDATE SET
                    score = EXCLUDED.score,
                    score_breakdown = EXCLUDED.score_breakdown,
                    description = EXCLUDED.description,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                signal.id,
                signal.competitor,
                signal.signal_type,
                signal.source_channel,
                signal.headline,
                signal.description,
                signal.raw_content,
                signal.score,
                json.dumps(signal.score_breakdown),
                signal.customer_mentioned,
                signal.project_name,
                signal.vessel_type,
                signal.engine_model,
                signal.fuel_type,
                signal.contract_value_usd,
                signal.region,
                signal.country,
                signal.is_apac,
                signal.is_singapore,
                json.dumps(signal.keywords_matched),
                signal.source_url,
                signal.published_date,
                signal.discovered_at,
                json.dumps(signal.metadata),
            )
        return signal.id

    async def save_signals(self, signals: list[CompetitorSignal]) -> int:
        """Save multiple signals efficiently."""
        if not signals:
            return 0
        count = 0
        for signal in signals:
            await self.save_signal(signal)
            count += 1
        return count

    async def get_signal(self, signal_id: str) -> Optional[CompetitorSignal]:
        """Get a signal by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM competitor_signals WHERE id = $1", signal_id
            )
            if row:
                return self._row_to_signal(row)
        return None

    async def list_signals(
        self,
        competitor: Optional[str] = None,
        signal_type: Optional[str] = None,
        source_channel: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CompetitorSignal]:
        """
        List signals with optional filters.

        Args:
            competitor: Filter by competitor
            signal_type: Filter by signal type
            source_channel: Filter by source channel
            min_score: Minimum score threshold
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            List of CompetitorSignal objects
        """
        query = "SELECT * FROM competitor_signals WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if competitor:
            query += f" AND competitor = ${param_idx}"
            params.append(competitor)
            param_idx += 1

        if signal_type:
            query += f" AND signal_type = ${param_idx}"
            params.append(signal_type)
            param_idx += 1

        if source_channel:
            query += f" AND source_channel = ${param_idx}"
            params.append(source_channel)
            param_idx += 1

        if min_score is not None:
            query += f" AND score >= ${param_idx}"
            params.append(min_score)
            param_idx += 1

        query += (
            f" ORDER BY discovered_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_signal(row) for row in rows]

    async def list_high_impact_signals(
        self,
        competitor: Optional[str] = None,
        limit: int = 50,
    ) -> list[CompetitorSignal]:
        """Get high-impact signals (score >= 60)."""
        return await self.list_signals(
            competitor=competitor,
            min_score=60,
            limit=limit,
        )

    async def get_signals_by_date_range(
        self,
        start_date: "datetime",
        end_date: "datetime",
        competitor: Optional[str] = None,
    ) -> list[CompetitorSignal]:
        """Get signals within a date range."""
        query = """
            SELECT * FROM competitor_signals
            WHERE discovered_at >= $1 AND discovered_at <= $2
        """
        params: list[Any] = [start_date, end_date]

        if competitor:
            query += " AND competitor = $3"
            params.append(competitor)

        query += " ORDER BY discovered_at DESC"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_signal(row) for row in rows]

    def _row_to_signal(self, row) -> CompetitorSignal:
        """Convert database row to CompetitorSignal."""
        from datetime import datetime, timezone

        return CompetitorSignal(
            id=row["id"],
            competitor=row["competitor"],
            signal_type=row["signal_type"],
            source_channel=row["source_channel"],
            headline=row["headline"],
            description=row["description"] or "",
            raw_content=row["raw_content"] or "",
            score=row["score"] or 0,
            score_breakdown=(
                dict(row["score_breakdown"]) if row["score_breakdown"] else {}
            ),
            customer_mentioned=row["customer_mentioned"],
            project_name=row["project_name"],
            vessel_type=row["vessel_type"],
            engine_model=row["engine_model"],
            fuel_type=row["fuel_type"],
            contract_value_usd=row["contract_value_usd"],
            region=row["region"],
            country=row["country"],
            is_apac=row["is_apac"] or False,
            is_singapore=row["is_singapore"] or False,
            keywords_matched=(
                list(row["keywords_matched"]) if row["keywords_matched"] else []
            ),
            source_url=row["source_url"] or "",
            published_date=row["published_date"],
            discovered_at=row["discovered_at"] or datetime.now(timezone.utc),
            metadata=(
                json.loads(row["metadata"])
                if isinstance(row["metadata"], str)
                else (row["metadata"] if row["metadata"] else {})
            ),
        )

    async def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal by ID."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM competitor_signals WHERE id = $1", signal_id
            )
            return "DELETE 1" in result

    # =========================================================================
    # Competitor Financials Operations
    # =========================================================================

    async def save_financials(self, financials: CompetitorFinancials) -> str:
        """
        Save competitor financial data.

        Uses UPSERT to update existing records for the same period.
        """
        import json

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO competitor_financials (
                    id, competitor, ticker, period_type, fiscal_period, report_date,
                    revenue_usd, operating_income_usd, net_income_usd,
                    rd_spending_usd, capex_usd, order_backlog_usd,
                    marine_segment_revenue, energy_segment_revenue, power_systems_revenue,
                    gross_margin_pct, operating_margin_pct,
                    revenue_growth_yoy_pct, revenue_growth_qoq_pct,
                    guidance_notes, source_url, fetched_at, raw_data
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                    $16, $17, $18, $19, $20, $21, $22, $23
                )
                ON CONFLICT (competitor, period_type, fiscal_period) DO UPDATE SET
                    revenue_usd = EXCLUDED.revenue_usd,
                    operating_income_usd = EXCLUDED.operating_income_usd,
                    net_income_usd = EXCLUDED.net_income_usd,
                    rd_spending_usd = EXCLUDED.rd_spending_usd,
                    capex_usd = EXCLUDED.capex_usd,
                    order_backlog_usd = EXCLUDED.order_backlog_usd,
                    marine_segment_revenue = EXCLUDED.marine_segment_revenue,
                    gross_margin_pct = EXCLUDED.gross_margin_pct,
                    operating_margin_pct = EXCLUDED.operating_margin_pct,
                    revenue_growth_yoy_pct = EXCLUDED.revenue_growth_yoy_pct,
                    revenue_growth_qoq_pct = EXCLUDED.revenue_growth_qoq_pct,
                    guidance_notes = EXCLUDED.guidance_notes,
                    fetched_at = EXCLUDED.fetched_at,
                    raw_data = EXCLUDED.raw_data
                """,
                financials.id,
                financials.competitor,
                financials.ticker,
                financials.period_type,
                financials.fiscal_period,
                financials.report_date,
                financials.revenue_usd,
                financials.operating_income_usd,
                financials.net_income_usd,
                financials.rd_spending_usd,
                financials.capex_usd,
                financials.order_backlog_usd,
                financials.marine_segment_revenue,
                financials.energy_segment_revenue,
                financials.power_systems_revenue,
                financials.gross_margin_pct,
                financials.operating_margin_pct,
                financials.revenue_growth_yoy_pct,
                financials.revenue_growth_qoq_pct,
                financials.guidance_notes,
                financials.source_url,
                financials.fetched_at,
                json.dumps(financials.raw_data),
            )
        return financials.id

    async def get_financials(
        self,
        competitor: str,
        period_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[CompetitorFinancials]:
        """Get financial data for a competitor."""
        query = "SELECT * FROM competitor_financials WHERE competitor = $1"
        params: list[Any] = [competitor]
        param_idx = 2

        if period_type:
            query += f" AND period_type = ${param_idx}"
            params.append(period_type)
            param_idx += 1

        query += f" ORDER BY report_date DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_financials(row) for row in rows]

    async def get_latest_financials(
        self, competitor: str
    ) -> Optional[CompetitorFinancials]:
        """Get the most recent financial data for a competitor."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM competitor_financials
                WHERE competitor = $1
                ORDER BY report_date DESC
                LIMIT 1
                """,
                competitor,
            )
            if row:
                return self._row_to_financials(row)
        return None

    async def get_all_latest_financials(self) -> dict[str, CompetitorFinancials]:
        """Get latest financials for all competitors."""
        result = {}
        for competitor in ["caterpillar", "cummins", "man_energy"]:
            financials = await self.get_latest_financials(competitor)
            if financials:
                result[competitor] = financials
        return result

    def _row_to_financials(self, row) -> CompetitorFinancials:
        """Convert database row to CompetitorFinancials."""
        from datetime import datetime, timezone

        return CompetitorFinancials(
            id=row["id"],
            competitor=row["competitor"],
            ticker=row["ticker"],
            period_type=row["period_type"],
            fiscal_period=row["fiscal_period"],
            report_date=row["report_date"],
            revenue_usd=row["revenue_usd"],
            operating_income_usd=row["operating_income_usd"],
            net_income_usd=row["net_income_usd"],
            rd_spending_usd=row["rd_spending_usd"],
            capex_usd=row["capex_usd"],
            order_backlog_usd=row["order_backlog_usd"],
            marine_segment_revenue=row["marine_segment_revenue"],
            energy_segment_revenue=row["energy_segment_revenue"],
            power_systems_revenue=row["power_systems_revenue"],
            gross_margin_pct=row["gross_margin_pct"],
            operating_margin_pct=row["operating_margin_pct"],
            revenue_growth_yoy_pct=row["revenue_growth_yoy_pct"],
            revenue_growth_qoq_pct=row["revenue_growth_qoq_pct"],
            guidance_notes=row["guidance_notes"],
            source_url=row["source_url"] or "",
            fetched_at=row["fetched_at"] or datetime.now(timezone.utc),
            raw_data=dict(row["raw_data"]) if row["raw_data"] else {},
        )

    # =========================================================================
    # Enhanced Statistics
    # =========================================================================

    async def get_signal_stats(self) -> dict[str, Any]:
        """Get statistics for competitor signals."""
        async with self.pool.acquire() as conn:
            total_signals = await conn.fetchval(
                "SELECT COUNT(*) FROM competitor_signals"
            )
            high_impact = await conn.fetchval(
                "SELECT COUNT(*) FROM competitor_signals WHERE score >= 60"
            )

            # By competitor
            signals_by_competitor = {}
            rows = await conn.fetch(
                """
                SELECT competitor, COUNT(*) as count, AVG(score) as avg_score
                FROM competitor_signals
                GROUP BY competitor
            """
            )
            for row in rows:
                signals_by_competitor[row["competitor"]] = {
                    "count": row["count"],
                    "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
                }

            # By signal type
            signals_by_type = {}
            rows = await conn.fetch(
                """
                SELECT signal_type, COUNT(*) as count
                FROM competitor_signals
                GROUP BY signal_type
            """
            )
            for row in rows:
                signals_by_type[row["signal_type"]] = row["count"]

            # By source channel
            signals_by_channel = {}
            rows = await conn.fetch(
                """
                SELECT source_channel, COUNT(*) as count
                FROM competitor_signals
                GROUP BY source_channel
            """
            )
            for row in rows:
                signals_by_channel[row["source_channel"]] = row["count"]

            return {
                "total_signals": total_signals,
                "high_impact_signals": high_impact,
                "signals_by_competitor": signals_by_competitor,
                "signals_by_type": signals_by_type,
                "signals_by_channel": signals_by_channel,
            }


# Singleton instance
_db: Optional[CompetitorIntelDatabase] = None


def get_competitor_db() -> CompetitorIntelDatabase:
    """Get or create the competitor intel database singleton."""
    global _db
    if _db is None:
        _db = CompetitorIntelDatabase()
    return _db


async def initialize_competitor_db() -> CompetitorIntelDatabase:
    """Initialize and return the competitor intel database."""
    db = get_competitor_db()
    await db.initialize()
    return db
