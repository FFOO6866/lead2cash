"""
Embedding Service for Competitor Intelligence

Generates embeddings using OpenAI text-embedding-3-small model
and stores them in PostgreSQL with pgvector for semantic search.

NO MOCKS, NO FALLBACKS - real OpenAI embeddings stored in pgvector.
"""

import logging
import os
import uuid
from typing import Optional

import httpx

from lead_to_cash.services.competitor_intel.chunking_service import (
    get_chunking_service,
)
from lead_to_cash.services.competitor_intel.models import (
    CompetitorDocument,
    DocumentChunk,
)

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_db = None


def _get_db():
    """Get database instance (lazy load to avoid circular imports)."""
    global _db
    if _db is None:
        from lead_to_cash.services.competitor_intel.database import get_competitor_db

        _db = get_competitor_db()
    return _db


class EmbeddingService:
    """
    Production embedding service for competitor intelligence.

    Uses OpenAI text-embedding-3-small (1536 dimensions) for embeddings.
    Stores vectors in PostgreSQL pgvector for semantic search.
    Uses tiktoken for accurate token counting via ChunkingService.
    """

    # Embedding model configuration
    MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    DIMENSIONS = 1536
    MAX_TOKENS = 8191  # Model limit

    def __init__(self):
        # Lazy initialization - don't validate API key until actually needed
        self._api_key: Optional[str] = None
        self.api_url = "https://api.openai.com/v1/embeddings"
        self._client: Optional[httpx.AsyncClient] = None
        self._chunking_service = get_chunking_service()

    @property
    def api_key(self) -> str:
        """Get API key, validating on first access."""
        if self._api_key is None:
            self._api_key = os.getenv("OPENAI_API_KEY")
            if not self._api_key:
                raise ValueError(
                    "OPENAI_API_KEY must be set for embedding generation. "
                    "Get your API key from https://platform.openai.com/api-keys"
                )
        return self._api_key

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def chunk_text(self, text: str, metadata: Optional[dict] = None) -> list[dict]:
        """
        Split text into chunks with overlap using tiktoken.

        Delegates to ChunkingService for accurate token counting.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries with content and metadata
        """
        chunks = self._chunking_service.chunk_text(text, metadata)
        # Normalize field names for compatibility
        return [
            {
                "text": c["content"],
                "token_count": c["token_count"],
                "metadata": c.get("metadata", {}),
            }
            for c in chunks
        ]

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
    # Document Processing with PostgreSQL pgvector
    # =========================================================================

    async def process_document(
        self, document: CompetitorDocument
    ) -> list[DocumentChunk]:
        """
        Process a document: chunk it, generate embeddings, store in pgvector.

        Args:
            document: Document to process

        Returns:
            List of document chunks with embeddings stored in PostgreSQL

        Raises:
            ValueError: If embedding generation fails (NO FALLBACKS)
        """
        logger.info(f"Processing document {document.id}: {document.title}")

        # Get database instance
        db = _get_db()

        # Prepare text with context
        full_text = f"{document.title}\n\n{document.content}"
        if document.summary:
            full_text = (
                f"{document.title}\n\nSummary: {document.summary}\n\n{document.content}"
            )

        # Chunk the document using tiktoken
        chunk_metadata = {
            "document_id": document.id,
            "competitor": document.competitor,
            "content_type": document.content_type,
            "source_url": document.source_url,
        }

        chunks_data = self.chunk_text(full_text, chunk_metadata)

        if not chunks_data:
            logger.warning(f"No chunks created for document {document.id}")
            return []

        # Generate embeddings for all chunks (NO FALLBACKS)
        texts = [c["text"] for c in chunks_data]
        embeddings = await self.generate_embeddings_batch(texts)

        # Create chunk objects
        chunks = []
        for i, (chunk_data, embedding) in enumerate(zip(chunks_data, embeddings)):
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                chunk_index=i,
                content=chunk_data["text"],
                embedding=embedding,
                token_count=chunk_data["token_count"],
                metadata=chunk_data["metadata"],
            )
            chunks.append(chunk)

        # Save chunks to PostgreSQL pgvector
        await db.save_chunks(chunks)

        logger.info(
            f"Created {len(chunks)} chunks with embeddings for document {document.id}"
        )

        return chunks

    async def process_all_documents(self) -> dict:
        """
        Process all unprocessed documents in PostgreSQL.

        Generates embeddings and stores in pgvector.

        Returns:
            Processing statistics
        """
        db = _get_db()
        await db.initialize()
        documents = await db.list_documents(limit=1000)

        processed = 0
        total_chunks = 0
        errors = 0

        for doc in documents:
            # Check if already has chunks in pgvector
            existing_chunks = await db.get_chunks_for_document(doc.id)
            if existing_chunks:
                logger.debug(
                    f"Document {doc.id} already has {len(existing_chunks)} chunks"
                )
                continue

            try:
                chunks = await self.process_document(doc)
                processed += 1
                total_chunks += len(chunks)
            except ValueError as e:
                logger.error(f"Embedding error for document {doc.id}: {e}")
                errors += 1
            except Exception as e:
                logger.error(f"Error processing document {doc.id}: {e}")
                errors += 1

        return {
            "documents_processed": processed,
            "chunks_created": total_chunks,
            "errors": errors,
        }


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
