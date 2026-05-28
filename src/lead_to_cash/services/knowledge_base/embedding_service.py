"""
Marine Engine Knowledge Base - Embedding Service

OpenAI embeddings with pgvector storage for semantic search.
Uses text-embedding-3-small (1536 dimensions) for consistency
with the existing competitor_intel patterns.

Features:
- Distributed circuit breaker (Redis) for multi-worker protection
- Real rate limiting via RedisRateLimiter
- Retry with exponential backoff for transient failures
- Falls back to local circuit breaker if Redis unavailable
- Input validation and proper exception handling
- Operation-level timeouts for batch operations
"""

import asyncio
import os
import time
from typing import Optional, Union

import openai

from lead_to_cash.config import config
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.exceptions import (
    KBCircuitBreakerError,
    KBConfigurationError,
    KBRateLimitError,
    KBTimeoutError,
)
from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics
from lead_to_cash.services.knowledge_base.tracing import trace_operation
from lead_to_cash.services.knowledge_base.validation import (
    validate_entity_type,
    validate_float_range,
    validate_list,
    validate_positive_int,
    validate_text,
)
from lead_to_cash.utils.logging import get_logger
from lead_to_cash.utils.resilience import (
    CircuitBreaker,
    DistributedCircuitBreaker,
    RedisRateLimiter,
    retry_with_backoff,
)

# Use structured logger with correlation ID support
logger = get_logger(__name__)


class KBEmbeddingService:
    """
    Embedding service for Marine Engine Knowledge Base.

    Generates OpenAI embeddings for entity aliases and provides
    semantic search capabilities via pgvector.

    Usage:
        service = KBEmbeddingService()
        await service.initialize()

        # Generate single embedding
        embedding = await service.generate_embedding("Wärtsilä 31")

        # Batch generate
        embeddings = await service.generate_embeddings_batch(["W31", "Cat", "MaK"])

        # Search by text
        results = await service.search_entities("wartsila engine")

        # Backfill missing embeddings
        count = await service.backfill_alias_embeddings(batch_size=100)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        db: Optional[KnowledgeBaseDatabase] = None,
    ):
        """
        Initialize embedding service.

        Args:
            api_key: OpenAI API key. Defaults to config/env.
            db: Database instance. Defaults to singleton.
        """
        # Load from config
        kb_config = config.knowledge_base

        self.api_key = api_key or kb_config.openai_api_key
        if not self.api_key:
            raise KBConfigurationError(
                message="OpenAI API key not configured",
                config_key="OPENAI_API_KEY",
            )

        # Model settings from config
        self.MODEL = kb_config.embedding_model
        self.DIMENSIONS = kb_config.embedding_dimensions

        self._client: Optional[openai.AsyncOpenAI] = None
        self._db: Optional[KnowledgeBaseDatabase] = db
        self._initialized = False

        # Distributed circuit breaker (uses Redis if available, falls back to local)
        self._circuit_breaker: Union[DistributedCircuitBreaker, CircuitBreaker] = (
            DistributedCircuitBreaker(
                name="kb_embedding_openai",
                redis_url=kb_config.redis_url,
                failure_threshold=kb_config.circuit_failure_threshold,
                recovery_timeout=kb_config.circuit_recovery_timeout,
                half_open_max_calls=kb_config.circuit_half_open_calls,
            )
        )

        # Real rate limiter (uses Redis if available)
        self._rate_limiter: Optional[RedisRateLimiter] = None
        if kb_config.redis_url:
            self._rate_limiter = RedisRateLimiter(
                redis_url=kb_config.redis_url,
                requests_per_window=kb_config.rate_limit_requests,
                window_seconds=kb_config.rate_limit_window_seconds,
                key_prefix="ratelimit:kb_embedding:",
            )

        # Fallback delay for batch operations (used when Redis unavailable)
        self._batch_delay = kb_config.batch_delay_seconds
        self._batch_size = kb_config.batch_size

    @property
    def db(self) -> KnowledgeBaseDatabase:
        """Get the database instance, raising if not initialized."""
        if self._db is None:
            raise KBConfigurationError(
                message="Database not initialized. Call initialize() first.",
                config_key="db",
            )
        return self._db

    async def initialize(self) -> None:
        """Initialize OpenAI client, database, and resilience components."""
        if self._initialized:
            return

        self._client = openai.AsyncOpenAI(api_key=self.api_key)

        if self._db is None:
            self._db = get_knowledge_base_db()
            await self._db.initialize()

        # Initialize distributed circuit breaker
        await self._circuit_breaker.initialize()

        # Initialize rate limiter if available
        if self._rate_limiter:
            await self._rate_limiter.initialize()

        self._initialized = True
        cb_mode = (
            "distributed"
            if getattr(self._circuit_breaker, "is_distributed", False)
            else "local"
        )
        rl_mode = (
            "Redis"
            if (self._rate_limiter and self._rate_limiter.is_available)
            else "delay-based"
        )
        logger.info(
            f"KB Embedding service initialized (circuit_breaker={cb_mode}, rate_limiter={rl_mode})"
        )

    @trace_operation(
        "generate_embedding",
        lambda text, **_: {"text_length": len(text) if text else 0},
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector

        Raises:
            KBValidationError: If text is invalid
            KBCircuitBreakerError: If circuit breaker is open
            KBRateLimitError: If rate limited
            openai.APIError: If OpenAI API fails after retries
        """
        # Input validation
        text = validate_text(text, "text", min_length=1, max_length=50000)

        if not self._initialized:
            await self.initialize()

        # Check circuit breaker (async for distributed)
        can_execute = await self._circuit_breaker.can_execute()
        if not can_execute:
            state = await self._circuit_breaker.get_state()
            raise KBCircuitBreakerError(
                message="OpenAI API circuit breaker is open",
                circuit_name="kb_embedding_openai",
                state=state,
            )

        # Rate limiting (if Redis available)
        if self._rate_limiter and self._rate_limiter.is_available:
            allowed = await self._rate_limiter.acquire()
            if not allowed:
                raise KBRateLimitError(
                    message="Rate limit exceeded for KB embedding API",
                    limiter="kb_embedding",
                )

        async def _call_api():
            response = await self._client.embeddings.create(
                model=self.MODEL,
                input=text,
            )
            return response.data[0].embedding

        try:
            # Track latency for metrics
            start_time = time.monotonic()

            # Retry with exponential backoff
            embedding = await retry_with_backoff(
                _call_api,
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
            )
            await self._circuit_breaker.record_success()

            # Record metrics
            duration = time.monotonic() - start_time
            metrics = get_kb_metrics()
            metrics.record_embedding_generated(self.MODEL)
            metrics.record_embedding_latency(duration, self.MODEL, 1)

            return embedding

        except Exception as e:
            await self._circuit_breaker.record_failure()
            get_kb_metrics().record_error("embedding", type(e).__name__)
            logger.error(f"OpenAI embedding generation failed: {e}")
            raise

    @trace_operation(
        "generate_embeddings_batch",
        lambda texts, **_: {"batch_size": len(texts) if texts else 0},
    )
    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
        timeout_seconds: float = 300.0,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with operation timeout.

        Args:
            texts: List of texts to embed
            batch_size: Maximum texts per API call
            timeout_seconds: Maximum total operation time (default 5 minutes)

        Returns:
            List of 1536-dimensional embedding vectors

        Raises:
            KBValidationError: If input is invalid
            KBCircuitBreakerError: If circuit breaker is open
            KBRateLimitError: If rate limited
            KBTimeoutError: If operation times out
            openai.APIError: If OpenAI API fails after retries
        """
        # Input validation
        texts = validate_list(texts, "texts", min_length=1, max_length=10000)
        batch_size = validate_positive_int(
            batch_size, "batch_size", min_value=1, max_value=2000
        )
        timeout_seconds = validate_float_range(
            timeout_seconds, "timeout_seconds", min_value=1.0, max_value=3600.0
        )

        if not self._initialized:
            await self.initialize()

        # Check circuit breaker (async for distributed)
        can_execute = await self._circuit_breaker.can_execute()
        if not can_execute:
            state = await self._circuit_breaker.get_state()
            raise KBCircuitBreakerError(
                message="OpenAI API circuit breaker is open",
                circuit_name="kb_embedding_openai",
                state=state,
            )

        all_embeddings = []

        # Helper to create API call with captured batch (avoids closure bug)
        def _make_api_call(batch_texts: list[str]):
            """Create async API call with batch captured by value."""

            async def _call():
                response = await self._client.embeddings.create(
                    model=self.MODEL,
                    input=batch_texts,
                )
                return [item.embedding for item in response.data]

            return _call

        async def _process_all_batches():
            """Process all batches with timeout protection."""
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_num = i // batch_size

                # Rate limiting per batch (if Redis available)
                if self._rate_limiter and self._rate_limiter.is_available:
                    allowed = await self._rate_limiter.acquire()
                    if not allowed:
                        raise KBRateLimitError(
                            message=f"Rate limit exceeded at batch {batch_num}",
                            limiter="kb_embedding",
                            batch_number=batch_num,
                        )
                elif i > 0:
                    # Fallback: simple delay between batches when no Redis
                    await asyncio.sleep(self._batch_delay)

                try:
                    # Retry with exponential backoff - batch captured by value via factory
                    batch_embeddings = await retry_with_backoff(
                        _make_api_call(batch),  # Captures batch by value
                        max_retries=3,
                        base_delay=1.0,
                        max_delay=10.0,
                    )
                    await self._circuit_breaker.record_success()
                    all_embeddings.extend(batch_embeddings)
                    # Record metrics for each embedding in the batch
                    for _ in batch_embeddings:
                        get_kb_metrics().record_embedding_generated(self.MODEL)

                except Exception as e:
                    await self._circuit_breaker.record_failure()
                    get_kb_metrics().record_error("embedding_batch", type(e).__name__)
                    logger.error(
                        f"OpenAI batch embedding failed at batch {batch_num}: {e}"
                    )
                    raise

            return all_embeddings

        # Execute with timeout
        try:
            return await asyncio.wait_for(
                _process_all_batches(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise KBTimeoutError(
                message=f"Batch embedding operation timed out after {timeout_seconds}s",
                operation="generate_embeddings_batch",
                timeout_seconds=timeout_seconds,
                texts_count=len(texts),
            )

    @trace_operation(
        "search_entities", lambda query, **_: {"query": query[:50] if query else ""}
    )
    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        top_k: int = 10,
        min_similarity: float = 0.6,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Search entities by semantic similarity.

        Args:
            query: Search query text
            entity_type: Optional filter ("manufacturer", "engine_model", etc.)
            top_k: Maximum results
            min_similarity: Minimum cosine similarity (0-1)
            user_id: Optional user identifier for per-user rate limiting

        Returns:
            List of matching entities with similarity scores

        Raises:
            KBValidationError: If input is invalid
            KBRateLimitError: If per-user rate limit exceeded
        """
        # Input validation — cap query length at 1000 chars (queries rarely need more)
        query = validate_text(query, "query", min_length=1, max_length=1000)

        # Per-user rate limiting (stricter than global)
        if user_id and self._rate_limiter and self._rate_limiter.is_available:
            allowed = await self._rate_limiter.is_allowed(f"user:{user_id}")
            if not allowed:
                raise KBRateLimitError(
                    message="Rate limit exceeded for KB queries. Please slow down.",
                    limiter="kb_embedding_per_user",
                )
        entity_type = validate_entity_type(entity_type, allow_none=True)
        top_k = validate_positive_int(top_k, "top_k", min_value=1, max_value=100)
        min_similarity = validate_float_range(
            min_similarity, "min_similarity", min_value=0.0, max_value=1.0
        )

        if not self._initialized:
            await self.initialize()

        # Generate query embedding
        query_embedding = await self.generate_embedding(query)

        # Search in database
        results = await self.db.search_aliases_by_embedding(
            embedding=query_embedding,
            entity_type=entity_type,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        return [
            {
                "entity_type": alias.entity_type,
                "entity_id": alias.entity_id,
                "alias_text": alias.alias_text,
                "alias_type": alias.alias_type,
                "confidence": alias.confidence,
                "similarity": similarity,
            }
            for alias, similarity in results
        ]

    async def backfill_alias_embeddings(self, batch_size: int = 100) -> int:
        """
        Generate embeddings for aliases that don't have them.

        Args:
            batch_size: Number of aliases to process per batch

        Returns:
            Number of aliases updated
        """
        if not self._initialized:
            await self.initialize()

        # Get aliases without embeddings
        aliases = await self.db.list_aliases_without_embeddings(limit=batch_size)

        if not aliases:
            logger.info("No aliases need embedding backfill")
            return 0

        # Generate embeddings in batch
        texts = [alias.alias_text for alias in aliases]
        embeddings = await self.generate_embeddings_batch(texts)

        # Update each alias
        updated = 0
        for alias, embedding in zip(aliases, embeddings):
            success = await self.db.update_alias_embedding(alias.id, embedding)
            if success:
                updated += 1

        logger.info(f"Backfilled embeddings for {updated} aliases")
        return updated

    async def backfill_all_embeddings(self, batch_size: int = 100) -> int:
        """
        Continuously backfill all aliases until none remain.

        Returns:
            Total number of aliases updated
        """
        total_updated = 0

        while True:
            updated = await self.backfill_alias_embeddings(batch_size)
            if updated == 0:
                break
            total_updated += updated

        logger.info(f"Total embeddings backfilled: {total_updated}")
        return total_updated

    async def get_embedding_stats(self) -> dict:
        """Get statistics about embedding coverage."""
        if not self._initialized:
            await self.initialize()

        health = await self.db.health_check()

        if not health.get("healthy"):
            return {"error": health.get("error", "Unknown error")}

        # Get aliases with and without embeddings
        async with self.db.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM kb_entity_aliases WHERE is_active = TRUE"
            )
            with_embedding = await conn.fetchval(
                "SELECT COUNT(*) FROM kb_entity_aliases WHERE embedding IS NOT NULL AND is_active = TRUE"
            )

        coverage = round(100 * with_embedding / total, 1) if total > 0 else 0

        return {
            "total_aliases": total,
            "with_embedding": with_embedding,
            "without_embedding": total - with_embedding,
            "coverage_percent": coverage,
            "model": self.MODEL,
            "dimensions": self.DIMENSIONS,
        }

    # =========================================================================
    # EMBEDDING VERSIONING METHODS
    # =========================================================================

    async def update_alias_embedding_with_version(
        self, alias_id: str, embedding: list[float]
    ) -> bool:
        """
        Update alias embedding with model version tracking.

        This method stores the embedding along with the model name
        that generated it, enabling stale embedding detection when
        the model is upgraded.

        Args:
            alias_id: ID of the alias to update
            embedding: Embedding vector (1536 dimensions)

        Returns:
            True if update succeeded, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        return await self.db.update_alias_embedding_versioned(
            alias_id=alias_id,
            embedding=embedding,
            embedding_model=self.MODEL,
        )

    async def get_stale_embeddings_count(self) -> dict:
        """
        Count embeddings using outdated models.

        This method identifies embeddings that were generated with
        a different model version than the current configuration.
        Useful for planning re-embedding migrations.

        Returns:
            Dictionary with stale embedding counts by table:
            {
                "current_model": os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"),
                "stale_aliases": 42,
                "stale_manufacturers": 0,
                "stale_engine_models": 5,
                "total_stale": 47
            }
        """
        if not self._initialized:
            await self.initialize()

        async with self.db.pool.acquire() as conn:
            # Count stale aliases
            stale_aliases = await conn.fetchval(
                """
                SELECT COUNT(*) FROM kb_entity_aliases
                WHERE embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                """,
                self.MODEL,
            )

            # Count stale manufacturers
            stale_manufacturers = await conn.fetchval(
                """
                SELECT COUNT(*) FROM kb_manufacturers
                WHERE name_embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                """,
                self.MODEL,
            )

            # Count stale engine models
            stale_engine_models = await conn.fetchval(
                """
                SELECT COUNT(*) FROM kb_engine_models
                WHERE model_embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                """,
                self.MODEL,
            )

        return {
            "current_model": self.MODEL,
            "stale_aliases": stale_aliases or 0,
            "stale_manufacturers": stale_manufacturers or 0,
            "stale_engine_models": stale_engine_models or 0,
            "total_stale": (stale_aliases or 0)
            + (stale_manufacturers or 0)
            + (stale_engine_models or 0),
        }

    async def backfill_stale_alias_embeddings(self, batch_size: int = 100) -> int:
        """
        Re-generate embeddings for aliases with outdated model versions.

        Args:
            batch_size: Number of aliases to process per batch

        Returns:
            Number of aliases updated
        """
        if not self._initialized:
            await self.initialize()

        # Get aliases with stale embeddings
        async with self.db.pool.acquire() as conn:
            stale_aliases = await conn.fetch(
                """
                SELECT id, alias_text FROM kb_entity_aliases
                WHERE embedding IS NOT NULL
                AND (embedding_model IS NULL OR embedding_model != $1)
                AND is_active = TRUE
                LIMIT $2
                """,
                self.MODEL,
                batch_size,
            )

        if not stale_aliases:
            logger.info("No stale alias embeddings to update")
            return 0

        # Generate new embeddings
        texts = [row["alias_text"] for row in stale_aliases]
        embeddings = await self.generate_embeddings_batch(texts)

        # Update each alias with versioning
        updated = 0
        for row, embedding in zip(stale_aliases, embeddings):
            success = await self.update_alias_embedding_with_version(
                row["id"], embedding
            )
            if success:
                updated += 1

        logger.info(f"Updated {updated} stale alias embeddings to {self.MODEL}")
        return updated


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_embedding_service: Optional[KBEmbeddingService] = None


def get_kb_embedding_service() -> KBEmbeddingService:
    """Get singleton embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = KBEmbeddingService()
    return _embedding_service


async def initialize_kb_embedding_service() -> KBEmbeddingService:
    """Initialize and return embedding service instance."""
    service = get_kb_embedding_service()
    await service.initialize()
    return service
