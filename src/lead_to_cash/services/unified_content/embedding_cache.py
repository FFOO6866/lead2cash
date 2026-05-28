"""
Shared Embedding Cache Service

Eliminates duplicate OpenAI API calls across services by:
- Caching embeddings by content hash
- Providing single interface for all embedding needs
- Supporting batch operations with deduplication

This service replaces:
- competitor_intel/embedding_service.py
- marine_intel/embedding_service.py
- knowledge_base/embedding_service.py

Usage:
    from lead_to_cash.services.unified_content.embedding_cache import (
        SharedEmbeddingService,
        get_shared_embedding_service,
    )

    service = get_shared_embedding_service()
    embedding = await service.embed_text("Some content")
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingCacheEntry:
    """Cache entry for an embedding."""

    content_hash: str
    embedding: list[float]
    model: str
    created_at: datetime
    hit_count: int = 0


@dataclass
class EmbeddingStats:
    """Statistics for embedding service usage."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls: int = 0
    api_errors: int = 0
    total_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    @property
    def api_savings(self) -> int:
        """Number of API calls saved by caching."""
        return self.cache_hits


class SharedEmbeddingService:
    """
    Shared embedding service with in-memory cache.

    Features:
    - Content hash-based caching
    - Batch embedding with deduplication
    - Rate limiting
    - Statistics tracking
    - Graceful degradation on errors

    This is the SINGLE embedding service for all intel services.
    """

    OPENAI_API_URL = "https://api.openai.com/v1/embeddings"
    DEFAULT_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS = 1536

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_cache_size: int = 10000,
        timeout: int = 60,
    ):
        """
        Initialize shared embedding service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model to use
            max_cache_size: Maximum cache entries
            timeout: API request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.max_cache_size = max_cache_size
        self.timeout = timeout

        # In-memory cache (content_hash -> EmbeddingCacheEntry)
        self._cache: dict[str, EmbeddingCacheEntry] = {}

        # Statistics
        self._stats = EmbeddingStats()

        # HTTP client
        self._http_client: Optional[httpx.AsyncClient] = None

        # Rate limiting
        self._last_request_time: Optional[datetime] = None
        self._min_request_interval = 0.1  # seconds

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set - embeddings will fail")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    @staticmethod
    def _hash_content(text: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_from_cache(self, content_hash: str) -> Optional[list[float]]:
        """Get embedding from cache if exists."""
        entry = self._cache.get(content_hash)
        if entry:
            entry.hit_count += 1
            self._stats.cache_hits += 1
            return entry.embedding
        self._stats.cache_misses += 1
        return None

    def _add_to_cache(self, content_hash: str, embedding: list[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        # Simple LRU: if at capacity, remove least recently used
        if len(self._cache) >= self.max_cache_size:
            # Remove entry with lowest hit count
            min_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
            del self._cache[min_key]

        self._cache[content_hash] = EmbeddingCacheEntry(
            content_hash=content_hash,
            embedding=embedding,
            model=self.model,
            created_at=datetime.now(timezone.utc),
        )

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """
        Call OpenAI embeddings API.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input)
        """
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        # Rate limiting
        if self._last_request_time:
            elapsed = (
                datetime.now(timezone.utc) - self._last_request_time
            ).total_seconds()
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)

        client = await self._get_client()

        try:
            response = await client.post(
                self.OPENAI_API_URL,
                json={
                    "input": texts,
                    "model": self.model,
                },
            )

            self._last_request_time = datetime.now(timezone.utc)

            if response.status_code != 200:
                self._stats.api_errors += 1
                logger.error(
                    f"OpenAI API error: {response.status_code} - {response.text}"
                )
                raise httpx.HTTPStatusError(
                    f"API returned {response.status_code}",
                    request=response.request,
                    response=response,
                )

            data = response.json()

            # Track token usage
            self._stats.total_tokens += data.get("usage", {}).get("total_tokens", 0)
            self._stats.api_calls += 1

            # Extract embeddings in order
            embeddings_data = sorted(data["data"], key=lambda x: x["index"])
            return [e["embedding"] for e in embeddings_data]

        except httpx.TimeoutException as e:
            self._stats.api_errors += 1
            logger.error(f"OpenAI API timeout: {e}")
            raise
        except Exception as e:
            self._stats.api_errors += 1
            logger.error(f"OpenAI API error: {e}")
            raise

    async def embed_text(self, text: str) -> list[float]:
        """
        Get embedding for a single text.

        Uses cache if available, otherwise calls API.

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector
        """
        self._stats.total_requests += 1

        # Check cache
        content_hash = self._hash_content(text)
        cached = self._get_from_cache(content_hash)
        if cached:
            logger.debug(f"Cache hit for content hash {content_hash[:16]}...")
            return cached

        # Call API
        logger.debug(f"Cache miss, calling API for content hash {content_hash[:16]}...")
        embeddings = await self._call_api([text])
        embedding = embeddings[0]

        # Cache result
        self._add_to_cache(content_hash, embedding)

        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts with deduplication.

        Checks cache for each text, only calls API for misses.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (same order as input)
        """
        if not texts:
            return []

        results: list[Optional[list[float]]] = [None] * len(texts)
        to_embed: list[tuple[int, str, str]] = []  # (index, text, hash)

        # Check cache for each text
        for i, text in enumerate(texts):
            self._stats.total_requests += 1
            content_hash = self._hash_content(text)
            cached = self._get_from_cache(content_hash)
            if cached:
                results[i] = cached
            else:
                to_embed.append((i, text, content_hash))

        # Call API for cache misses
        if to_embed:
            texts_to_embed = [t[1] for t in to_embed]
            logger.info(
                f"Batch embedding: {len(texts_to_embed)} API calls (saved {len(texts) - len(to_embed)} via cache)"
            )

            # Batch API calls (OpenAI supports up to ~8000 tokens per batch)
            batch_size = 50
            for batch_start in range(0, len(texts_to_embed), batch_size):
                batch_texts = texts_to_embed[batch_start : batch_start + batch_size]
                batch_indices = to_embed[batch_start : batch_start + batch_size]

                embeddings = await self._call_api(batch_texts)

                for (orig_idx, text, content_hash), embedding in zip(
                    batch_indices, embeddings
                ):
                    results[orig_idx] = embedding
                    self._add_to_cache(content_hash, embedding)

                # Small delay between batches
                if batch_start + batch_size < len(texts_to_embed):
                    await asyncio.sleep(0.1)

        return [r for r in results if r is not None]

    async def embed_content(
        self,
        content_id: str,
        title: str,
        content: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> list[float]:
        """
        Get embedding for unified content.

        Combines title + summary + content for comprehensive embedding.

        Args:
            content_id: Content ID for logging
            title: Content title
            content: Full content (optional)
            summary: Content summary (optional)

        Returns:
            1536-dimensional embedding vector
        """
        # Build text to embed
        parts = [title]
        if summary:
            parts.append(summary)
        if content:
            # Limit content to avoid token limits
            parts.append(content[:5000])

        text_to_embed = " ".join(parts)

        logger.debug(f"Embedding content {content_id}: {len(text_to_embed)} chars")
        return await self.embed_text(text_to_embed)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_requests": self._stats.total_requests,
            "cache_hits": self._stats.cache_hits,
            "cache_misses": self._stats.cache_misses,
            "cache_hit_rate": f"{self._stats.hit_rate:.1f}%",
            "api_calls": self._stats.api_calls,
            "api_errors": self._stats.api_errors,
            "api_calls_saved": self._stats.api_savings,
            "total_tokens": self._stats.total_tokens,
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "model": self.model,
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = EmbeddingStats()

    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._cache.clear()


# =============================================================================
# Singleton Instance
# =============================================================================

_shared_embedding_service: Optional[SharedEmbeddingService] = None


def get_shared_embedding_service() -> SharedEmbeddingService:
    """Get or create the shared embedding service singleton."""
    global _shared_embedding_service
    if _shared_embedding_service is None:
        _shared_embedding_service = SharedEmbeddingService()
    return _shared_embedding_service


async def embed_text(text: str) -> list[float]:
    """Convenience function to embed text using shared service."""
    service = get_shared_embedding_service()
    return await service.embed_text(text)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convenience function to embed multiple texts using shared service."""
    service = get_shared_embedding_service()
    return await service.embed_texts(texts)


def get_embedding_stats() -> dict[str, Any]:
    """Get embedding service statistics."""
    service = get_shared_embedding_service()
    return service.get_stats()
