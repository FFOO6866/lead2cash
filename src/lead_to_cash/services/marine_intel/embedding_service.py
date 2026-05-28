"""
Embedding Service for Marine Intelligence

Generates embeddings using OpenAI text-embedding-3-small model
and stores them in PostgreSQL with pgvector for semantic search.

NO MOCKS, NO FALLBACKS - real OpenAI embeddings stored in pgvector.
"""

import logging
import os
from typing import Optional

import httpx

from lead_to_cash.services.marine_intel.models import Article

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_db = None


def _get_db():
    """Get database instance (lazy load to avoid circular imports)."""
    global _db
    if _db is None:
        from lead_to_cash.services.marine_intel.database import get_marine_intel_db

        _db = get_marine_intel_db()
    return _db


class MarineEmbeddingService:
    """
    Production embedding service for marine intelligence.

    Uses OpenAI text-embedding-3-small (1536 dimensions) for embeddings.
    Stores vectors in PostgreSQL pgvector for semantic search.

    Supports async context manager for proper resource cleanup:
        async with MarineEmbeddingService() as service:
            embedding = await service.generate_embedding("text")
    """

    # Embedding model configuration
    MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    DIMENSIONS = 1536
    MAX_TOKENS = 8191  # Model limit

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set for embedding generation. "
                "Get your API key from https://platform.openai.com/api-keys"
            )
        self.api_url = "https://api.openai.com/v1/embeddings"
        self._client: Optional[httpx.AsyncClient] = None
        self._owns_client = False  # Track if we created the client

    async def __aenter__(self) -> "MarineEmbeddingService":
        """Async context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - ensures client cleanup."""
        await self.close()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
            self._owns_client = True
        return self._client

    async def close(self):
        """Close HTTP client if we own it."""
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    # =========================================================================
    # Embedding Generation
    # =========================================================================

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector

        Raises:
            ValueError: If API call fails (NO FALLBACKS)
        """
        try:
            client = await self._get_client()
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text[:8000],  # Truncate to model limit
                    "model": self.MODEL,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                error_msg = (
                    f"OpenAI embedding error: {response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error generating embedding: {e}")
            raise ValueError(f"Failed to generate embedding: {e}")

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches using OpenAI.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 100)

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If any API call fails (NO FALLBACKS)
        """
        if not texts:
            return []

        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch = [t[:8000] for t in batch]  # Truncate to model limit

            try:
                client = await self._get_client()
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "input": batch,
                        "model": self.MODEL,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    # Sort by index to maintain order
                    sorted_data = sorted(data["data"], key=lambda x: x["index"])
                    embeddings.extend([d["embedding"] for d in sorted_data])
                else:
                    error_msg = f"Batch embedding error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

            except httpx.HTTPError as e:
                logger.error(f"HTTP error in batch embedding: {e}")
                raise ValueError(f"Failed to generate batch embeddings: {e}")

        return embeddings

    # =========================================================================
    # Article Processing with PostgreSQL pgvector
    # =========================================================================

    def _prepare_article_text(self, article: Article) -> str:
        """
        Prepare article text for embedding generation.

        Combines title, summary, and content into a single text
        with context for better semantic understanding.

        Args:
            article: Article to prepare

        Returns:
            Combined text for embedding
        """
        parts = [f"Title: {article.title}"]

        if article.source:
            parts.append(f"Source: {article.source}")

        if article.summary:
            parts.append(f"Summary: {article.summary}")

        if article.content:
            # Include content but truncate if very long
            content = article.content[:6000]  # Leave room for other fields
            parts.append(f"Content: {content}")

        return "\n\n".join(parts)

    async def process_article(self, article: Article) -> bool:
        """
        Generate embedding for an article and store in database.

        Args:
            article: Article to process

        Returns:
            True if embedding was generated and stored

        Raises:
            ValueError: If embedding generation fails (NO FALLBACKS)
        """
        logger.info(f"Processing article {article.id}: {article.title[:50]}...")

        # Prepare text
        text = self._prepare_article_text(article)

        # Generate embedding (NO FALLBACKS)
        embedding = await self.generate_embedding(text)

        # Store in database
        db = _get_db()
        success = await db.update_article_embedding(article.id, embedding)

        if success:
            logger.info(f"Embedding stored for article {article.id}")
        else:
            logger.warning(f"Failed to store embedding for article {article.id}")

        return success

    async def backfill_missing_embeddings(
        self,
        batch_size: int = 50,
        max_articles: int = 500,
    ) -> dict:
        """
        Backfill embeddings for articles that don't have them.

        Args:
            batch_size: Number of articles to process per batch
            max_articles: Maximum total articles to process

        Returns:
            Processing statistics
        """
        db = _get_db()
        await db.initialize()

        processed = 0
        errors = 0
        total_to_process = 0

        while processed + errors < max_articles:
            # Get batch of articles without embeddings
            articles = await db.get_articles_without_embedding(limit=batch_size)

            if not articles:
                break

            total_to_process += len(articles)

            # Prepare texts for batch embedding
            texts = [self._prepare_article_text(a) for a in articles]

            try:
                # Generate embeddings in batch
                embeddings = await self.generate_embeddings_batch(texts)

                # Store each embedding
                for article, embedding in zip(articles, embeddings):
                    try:
                        await db.update_article_embedding(article.id, embedding)
                        processed += 1
                    except Exception as e:
                        logger.error(f"Failed to store embedding for {article.id}: {e}")
                        errors += 1

            except ValueError as e:
                logger.error(f"Batch embedding failed: {e}")
                errors += len(articles)

        logger.info(
            f"Backfill complete: {processed} processed, {errors} errors "
            f"out of {total_to_process} articles"
        )

        return {
            "articles_processed": processed,
            "errors": errors,
            "total_attempted": total_to_process,
        }

    async def search_articles(
        self,
        query: str,
        top_k: int = 10,
        min_similarity: float = 0.6,
        retention_tiers: Optional[list[str]] = None,
    ) -> list[tuple[Article, float]]:
        """
        Search articles by semantic similarity.

        Args:
            query: Natural language search query
            top_k: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
            retention_tiers: Optional filter by retention tier(s)

        Returns:
            List of (Article, similarity_score) tuples
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)

        # Search in database
        db = _get_db()
        results = await db.vector_search_articles(
            query_embedding=query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            retention_tiers=retention_tiers,
        )

        return results

    async def find_similar_articles(
        self,
        article_id: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
    ) -> list[tuple[Article, float]]:
        """
        Find articles similar to a given article.

        Args:
            article_id: Source article ID
            top_k: Maximum number of similar articles
            min_similarity: Minimum similarity threshold

        Returns:
            List of (Article, similarity_score) tuples
        """
        db = _get_db()
        return await db.get_similar_articles(
            article_id=article_id,
            top_k=top_k,
            min_similarity=min_similarity,
        )


# Singleton instance
_embedding_service: Optional[MarineEmbeddingService] = None


def get_marine_embedding_service() -> MarineEmbeddingService:
    """
    Get or create the marine embedding service singleton.

    NOTE: Do NOT use the singleton with `async with` context manager.
    The singleton manages its own lifecycle - use close_marine_embedding_service()
    for application shutdown.

    For short-lived usage with automatic cleanup, create a new instance:
        async with MarineEmbeddingService() as service:
            embedding = await service.generate_embedding("text")
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = MarineEmbeddingService()
    return _embedding_service


async def close_marine_embedding_service() -> None:
    """
    Close the singleton embedding service (call during application shutdown).

    Safe to call multiple times - will only close if service exists and is open.
    """
    global _embedding_service
    if _embedding_service is not None:
        await _embedding_service.close()
        _embedding_service = None


async def initialize_marine_embedding_service() -> MarineEmbeddingService:
    """Initialize and return the marine embedding service singleton."""
    service = get_marine_embedding_service()
    return service
