"""
Unified Content Database

PostgreSQL storage for unified content with:
- URL hash deduplication
- pgvector embeddings
- Multi-purpose classification storage
- KB entity linking

Usage:
    from lead_to_cash.services.unified_content.database import (
        UnifiedContentDatabase,
        get_unified_content_db,
    )

    db = get_unified_content_db()
    await db.initialize()
    content_id, is_new = await db.save_content(content)
"""

import json
import logging
import os
from typing import Any, Optional

import asyncpg

from lead_to_cash.services.unified_content.models import (
    ContentClassification,
    ExtractedEntity,
    IngestionJob,
    UnifiedContent,
)
from lead_to_cash.utils.resilience import with_retry

logger = logging.getLogger(__name__)


class UnifiedContentDatabase:
    """
    PostgreSQL database for unified content storage.

    Single source of truth for all scraped/collected content.
    Replaces separate tables in competitor_intel and marine_intel.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection string (defaults to DATABASE_URL env var)

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
            raise ValueError("DATABASE_URL must be set")
        return url

    @property
    def pool(self) -> asyncpg.Pool:
        """Get connection pool."""
        if self._pool is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._pool

    async def initialize(self) -> None:
        """
        Initialize database connection pool and create tables.

        Creates:
        - unified_content: Main content storage
        - unified_content_entities: Extracted entities (normalized)
        - unified_content_kb_links: Links to KB entities
        - unified_ingestion_jobs: Job tracking
        """
        if self._initialized:
            return

        logger.info("Initializing Unified Content PostgreSQL database")

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        async with self.pool.acquire() as conn:
            # Enable pgvector
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Main content table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unified_content (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,

                    -- Content
                    title TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,

                    -- Source
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_tier INTEGER DEFAULT 3,
                    source_url TEXT,

                    -- Dates
                    published_date TIMESTAMPTZ,
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    processed_at TIMESTAMPTZ,

                    -- Purposes (JSON array)
                    purposes JSONB DEFAULT '["general"]',

                    -- Embedding
                    embedding vector(1536),
                    embedding_model TEXT DEFAULT 'text-embedding-3-small',

                    -- Entity extraction timestamp
                    entities_extracted_at TIMESTAMPTZ,

                    -- Classification (JSON)
                    classification JSONB,

                    -- KB Linking
                    kb_linked BOOLEAN DEFAULT FALSE,

                    -- Processing
                    is_processed BOOLEAN DEFAULT FALSE,
                    processing_errors JSONB DEFAULT '[]',

                    -- Metadata
                    author TEXT,
                    language TEXT DEFAULT 'en',
                    metadata JSONB DEFAULT '{}',

                    -- Retention
                    retention_tier TEXT DEFAULT 'hot',

                    -- Timestamps
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # Extracted entities table (many-to-many with content)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unified_content_entities (
                    id TEXT PRIMARY KEY,
                    content_id TEXT NOT NULL REFERENCES unified_content(id) ON DELETE CASCADE,
                    entity_type TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    kb_entity_id TEXT,
                    kb_entity_type TEXT,
                    confidence FLOAT DEFAULT 0.0,
                    context TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )

            # KB entity links (links unified content to kb_article_entities)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unified_content_kb_links (
                    content_id TEXT NOT NULL REFERENCES unified_content(id) ON DELETE CASCADE,
                    kb_article_entity_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (content_id, kb_article_entity_id)
                )
            """
            )

            # Ingestion job tracking
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unified_ingestion_jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    content_found INTEGER DEFAULT 0,
                    content_saved INTEGER DEFAULT 0,
                    duplicates_skipped INTEGER DEFAULT 0,
                    entities_extracted INTEGER DEFAULT 0,
                    kb_links_created INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    sources_processed JSONB DEFAULT '[]',
                    error_messages JSONB DEFAULT '[]'
                )
            """
            )

            # Indexes
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_url_hash ON unified_content(url_hash)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_source_type ON unified_content(source_type)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_source_name ON unified_content(source_name)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_published_date ON unified_content(published_date DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_ingested_at ON unified_content(ingested_at DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_is_processed ON unified_content(is_processed)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_kb_linked ON unified_content(kb_linked)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_retention ON unified_content(retention_tier)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_content_purposes ON unified_content USING GIN (purposes)"
            )

            # Vector index for semantic search
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_unified_content_embedding
                ON unified_content USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
            )

            # Entity indexes
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_entities_content ON unified_content_entities(content_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_entities_type ON unified_content_entities(entity_type)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_entities_kb ON unified_content_entities(kb_entity_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_entities_normalized ON unified_content_entities(normalized_text)"
            )

        self._initialized = True
        logger.info("Unified Content database initialization complete")

    async def close(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False

    # =========================================================================
    # Content Operations
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def save_content(self, content: UnifiedContent) -> tuple[str, bool]:
        """
        Save unified content with URL hash deduplication.

        Args:
            content: UnifiedContent to save

        Returns:
            Tuple of (content_id, is_new). is_new=False means duplicate was skipped.
        """
        async with self.pool.acquire() as conn:
            # Check for duplicate by URL hash
            existing = await conn.fetchval(
                "SELECT id FROM unified_content WHERE url_hash = $1",
                content.url_hash,
            )

            if existing:
                logger.debug(f"Duplicate content skipped: {content.url}")
                return existing, False

            # Prepare embedding for pgvector
            embedding_str = None
            if content.embedding:
                embedding_str = "[" + ",".join(str(x) for x in content.embedding) + "]"

            # Insert new content
            await conn.execute(
                """
                INSERT INTO unified_content (
                    id, url, url_hash, title, content, summary,
                    source_name, source_type, source_tier, source_url,
                    published_date, ingested_at, processed_at,
                    purposes, embedding, embedding_model, entities_extracted_at,
                    classification, kb_linked, is_processed, processing_errors,
                    author, language, metadata, retention_tier
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15::vector, $16, $17,
                    $18, $19, $20, $21, $22, $23, $24, $25
                )
            """,
                content.id,
                content.url,
                content.url_hash,
                content.title,
                content.content,
                content.summary,
                content.source_name,
                content.source_type,
                content.source_tier,
                content.source_url,
                content.published_date,
                content.ingested_at,
                content.processed_at,
                json.dumps(content.purposes),
                embedding_str,
                content.embedding_model,
                content.entities_extracted_at,
                (
                    json.dumps(content.classification.to_dict())
                    if content.classification
                    else None
                ),
                content.kb_linked,
                content.is_processed,
                json.dumps(content.processing_errors),
                content.author,
                content.language,
                json.dumps(content.metadata),
                content.retention_tier,
            )

            logger.info(f"New content saved: {content.title[:50]}...")
            return content.id, True

    async def get_content(self, content_id: str) -> Optional[UnifiedContent]:
        """Get content by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM unified_content WHERE id = $1",
                content_id,
            )
            if row:
                return self._row_to_content(row)
        return None

    async def get_content_by_url(self, url: str) -> Optional[UnifiedContent]:
        """Get content by URL (using hash)."""
        url_hash = UnifiedContent.generate_url_hash(url)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM unified_content WHERE url_hash = $1",
                url_hash,
            )
            if row:
                return self._row_to_content(row)
        return None

    async def check_url_exists(self, url: str) -> bool:
        """Check if content URL already exists."""
        url_hash = UnifiedContent.generate_url_hash(url)
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM unified_content WHERE url_hash = $1)",
                url_hash,
            )
            return exists

    async def list_content(
        self,
        source_type: Optional[str] = None,
        purposes: Optional[list[str]] = None,
        is_processed: Optional[bool] = None,
        kb_linked: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UnifiedContent]:
        """List content with optional filters."""
        query = "SELECT * FROM unified_content WHERE 1=1"
        params: list[Any] = []
        param_idx = 1

        if source_type:
            query += f" AND source_type = ${param_idx}"
            params.append(source_type)
            param_idx += 1

        if purposes:
            query += f" AND purposes ?| ${param_idx}"
            params.append(purposes)
            param_idx += 1

        if is_processed is not None:
            query += f" AND is_processed = ${param_idx}"
            params.append(is_processed)
            param_idx += 1

        if kb_linked is not None:
            query += f" AND kb_linked = ${param_idx}"
            params.append(kb_linked)
            param_idx += 1

        query += (
            f" ORDER BY ingested_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        )
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_content(row) for row in rows]

    async def get_unprocessed_content(self, limit: int = 50) -> list[UnifiedContent]:
        """Get content that hasn't been processed yet."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM unified_content
                WHERE is_processed = FALSE
                ORDER BY ingested_at ASC
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_content(row) for row in rows]

    async def get_content_without_embedding(
        self, limit: int = 100
    ) -> list[UnifiedContent]:
        """Get content without embeddings (for backfill)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM unified_content
                WHERE embedding IS NULL
                ORDER BY created_at DESC
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_content(row) for row in rows]

    async def get_content_without_kb_links(
        self, limit: int = 100
    ) -> list[UnifiedContent]:
        """Get content not linked to KB (for processing)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM unified_content
                WHERE kb_linked = FALSE AND is_processed = TRUE
                ORDER BY created_at DESC
                LIMIT $1
            """,
                limit,
            )
            return [self._row_to_content(row) for row in rows]

    @with_retry(max_retries=3, base_delay=0.5)
    async def update_embedding(
        self,
        content_id: str,
        embedding: list[float],
    ) -> bool:
        """Update content embedding."""
        if len(embedding) != 1536:
            raise ValueError(f"Embedding must be 1536 dimensions, got {len(embedding)}")

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE unified_content
                SET embedding = $1::vector,
                    updated_at = NOW()
                WHERE id = $2
            """,
                embedding_str,
                content_id,
            )
            return "UPDATE 1" in result

    async def update_classification(
        self,
        content_id: str,
        classification: ContentClassification,
    ) -> bool:
        """Update content classification."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE unified_content
                SET classification = $1,
                    updated_at = NOW()
                WHERE id = $2
            """,
                json.dumps(classification.to_dict()),
                content_id,
            )
            return "UPDATE 1" in result

    async def mark_processed(self, content_id: str) -> bool:
        """Mark content as processed."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE unified_content
                SET is_processed = TRUE,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
            """,
                content_id,
            )
            return "UPDATE 1" in result

    async def mark_kb_linked(self, content_id: str) -> bool:
        """Mark content as KB linked."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE unified_content
                SET kb_linked = TRUE,
                    updated_at = NOW()
                WHERE id = $1
            """,
                content_id,
            )
            return "UPDATE 1" in result

    # =========================================================================
    # Entity Operations
    # =========================================================================

    async def save_entity(
        self,
        content_id: str,
        entity: ExtractedEntity,
    ) -> str:
        """Save an extracted entity."""
        import uuid

        entity_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO unified_content_entities (
                    id, content_id, entity_type, raw_text, normalized_text,
                    kb_entity_id, kb_entity_type, confidence, context, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                entity_id,
                content_id,
                entity.entity_type,
                entity.raw_text,
                entity.normalized_text,
                entity.kb_entity_id,
                entity.kb_entity_type,
                entity.confidence,
                entity.context,
                json.dumps(entity.metadata),
            )

        return entity_id

    async def save_entities(
        self,
        content_id: str,
        entities: list[ExtractedEntity],
    ) -> list[str]:
        """Save multiple extracted entities."""
        entity_ids = []
        for entity in entities:
            entity_id = await self.save_entity(content_id, entity)
            entity_ids.append(entity_id)
        return entity_ids

    async def get_entities_for_content(self, content_id: str) -> list[ExtractedEntity]:
        """Get all entities for a content item."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM unified_content_entities
                WHERE content_id = $1
                ORDER BY confidence DESC
            """,
                content_id,
            )

            return [
                ExtractedEntity(
                    entity_type=row["entity_type"],
                    raw_text=row["raw_text"],
                    normalized_text=row["normalized_text"],
                    kb_entity_id=row["kb_entity_id"],
                    kb_entity_type=row["kb_entity_type"],
                    confidence=row["confidence"],
                    context=row["context"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
                for row in rows
            ]

    async def get_content_by_entity(
        self,
        kb_entity_id: str,
        limit: int = 100,
    ) -> list[UnifiedContent]:
        """Get all content mentioning a specific KB entity."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT uc.* FROM unified_content uc
                JOIN unified_content_entities uce ON uc.id = uce.content_id
                WHERE uce.kb_entity_id = $1
                ORDER BY uc.published_date DESC
                LIMIT $2
            """,
                kb_entity_id,
                limit,
            )
            return [self._row_to_content(row) for row in rows]

    # =========================================================================
    # KB Link Operations
    # =========================================================================

    async def add_kb_link(
        self,
        content_id: str,
        kb_article_entity_id: str,
    ) -> bool:
        """Add a KB article entity link."""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO unified_content_kb_links (content_id, kb_article_entity_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                """,
                    content_id,
                    kb_article_entity_id,
                )
                return True
            except Exception as e:
                logger.error(f"Error adding KB link: {e}")
                return False

    async def get_kb_links(self, content_id: str) -> list[str]:
        """Get KB article entity IDs linked to content."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT kb_article_entity_id FROM unified_content_kb_links
                WHERE content_id = $1
            """,
                content_id,
            )
            return [row["kb_article_entity_id"] for row in rows]

    # =========================================================================
    # Vector Search
    # =========================================================================

    @with_retry(max_retries=3, base_delay=0.5)
    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_similarity: float = 0.6,
        source_types: Optional[list[str]] = None,
        purposes: Optional[list[str]] = None,
    ) -> list[tuple[UnifiedContent, float]]:
        """
        Search content by semantic similarity.

        Args:
            query_embedding: 1536-dimensional query vector
            top_k: Maximum results
            min_similarity: Minimum cosine similarity (0-1)
            source_types: Filter by source types
            purposes: Filter by purposes

        Returns:
            List of (UnifiedContent, similarity_score) tuples
        """
        if len(query_embedding) != 1536:
            raise ValueError(
                f"Query must be 1536 dimensions, got {len(query_embedding)}"
            )

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build query with filters
        query = """
            SELECT *,
                   1 - (embedding <=> $1::vector) as similarity
            FROM unified_content
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) >= $2
        """
        params: list[Any] = [embedding_str, min_similarity]
        param_idx = 3

        if source_types:
            query += f" AND source_type = ANY(${param_idx})"
            params.append(source_types)
            param_idx += 1

        if purposes:
            query += f" AND purposes ?| ${param_idx}"
            params.append(purposes)
            param_idx += 1

        query += f" ORDER BY embedding <=> $1::vector LIMIT ${param_idx}"
        params.append(top_k)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            results = []
            for row in rows:
                content = self._row_to_content(row)
                similarity = float(row["similarity"])
                results.append((content, similarity))
            return results

    # =========================================================================
    # Job Operations
    # =========================================================================

    async def save_job(self, job: IngestionJob) -> str:
        """Save or update an ingestion job."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO unified_ingestion_jobs (
                    id, job_type, status, started_at, completed_at,
                    content_found, content_saved, duplicates_skipped,
                    entities_extracted, kb_links_created, errors,
                    sources_processed, error_messages
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = EXCLUDED.completed_at,
                    content_found = EXCLUDED.content_found,
                    content_saved = EXCLUDED.content_saved,
                    duplicates_skipped = EXCLUDED.duplicates_skipped,
                    entities_extracted = EXCLUDED.entities_extracted,
                    kb_links_created = EXCLUDED.kb_links_created,
                    errors = EXCLUDED.errors,
                    sources_processed = EXCLUDED.sources_processed,
                    error_messages = EXCLUDED.error_messages
            """,
                job.id,
                job.job_type,
                job.status,
                job.started_at,
                job.completed_at,
                job.content_found,
                job.content_saved,
                job.duplicates_skipped,
                job.entities_extracted,
                job.kb_links_created,
                job.errors,
                json.dumps(job.sources_processed),
                json.dumps(job.error_messages),
            )
        return job.id

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM unified_content")
            processed = await conn.fetchval(
                "SELECT COUNT(*) FROM unified_content WHERE is_processed = TRUE"
            )
            kb_linked = await conn.fetchval(
                "SELECT COUNT(*) FROM unified_content WHERE kb_linked = TRUE"
            )
            with_embedding = await conn.fetchval(
                "SELECT COUNT(*) FROM unified_content WHERE embedding IS NOT NULL"
            )

            by_source = await conn.fetch(
                """
                SELECT source_type, COUNT(*) as count
                FROM unified_content
                GROUP BY source_type
                ORDER BY count DESC
            """
            )

            by_purpose = await conn.fetch(
                """
                SELECT jsonb_array_elements_text(purposes) as purpose, COUNT(*) as count
                FROM unified_content
                GROUP BY purpose
                ORDER BY count DESC
            """
            )

            return {
                "total_content": total,
                "processed": processed,
                "kb_linked": kb_linked,
                "with_embedding": with_embedding,
                "by_source_type": {
                    row["source_type"]: row["count"] for row in by_source
                },
                "by_purpose": {row["purpose"]: row["count"] for row in by_purpose},
            }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_content(self, row) -> UnifiedContent:
        """Convert database row to UnifiedContent."""
        # Parse embedding
        embedding = None
        if row.get("embedding"):
            emb = row["embedding"]
            if isinstance(emb, str):
                embedding = [float(x) for x in emb.strip("[]").split(",")]
            elif isinstance(emb, (list, tuple)):
                embedding = list(emb)
            else:
                embedding = list(emb)

        # Parse classification
        classification = None
        if row.get("classification"):
            class_data = row["classification"]
            if isinstance(class_data, str):
                class_data = json.loads(class_data)
            classification = ContentClassification.from_dict(class_data)

        # Parse JSON fields
        purposes = row.get("purposes", ["general"])
        if isinstance(purposes, str):
            purposes = json.loads(purposes)

        processing_errors = row.get("processing_errors", [])
        if isinstance(processing_errors, str):
            processing_errors = json.loads(processing_errors)

        metadata = row.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return UnifiedContent(
            id=row["id"],
            url=row["url"],
            url_hash=row["url_hash"],
            title=row["title"],
            content=row.get("content"),
            summary=row.get("summary"),
            source_name=row["source_name"],
            source_type=row["source_type"],
            source_tier=row.get("source_tier", 3),
            source_url=row.get("source_url"),
            published_date=row.get("published_date"),
            ingested_at=row["ingested_at"],
            processed_at=row.get("processed_at"),
            purposes=purposes,
            embedding=embedding,
            embedding_model=row.get("embedding_model", os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")),
            entities_extracted_at=row.get("entities_extracted_at"),
            classification=classification,
            kb_linked=row.get("kb_linked", False),
            kb_article_entity_ids=[],  # Loaded separately if needed
            is_processed=row.get("is_processed", False),
            processing_errors=processing_errors,
            author=row.get("author"),
            language=row.get("language", "en"),
            metadata=metadata,
            retention_tier=row.get("retention_tier", "hot"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# =============================================================================
# Singleton
# =============================================================================

_unified_content_db: Optional[UnifiedContentDatabase] = None


def get_unified_content_db() -> UnifiedContentDatabase:
    """Get or create the unified content database singleton."""
    global _unified_content_db
    if _unified_content_db is None:
        _unified_content_db = UnifiedContentDatabase()
    return _unified_content_db


async def initialize_unified_content_db() -> UnifiedContentDatabase:
    """Initialize and return the unified content database."""
    db = get_unified_content_db()
    await db.initialize()
    return db
