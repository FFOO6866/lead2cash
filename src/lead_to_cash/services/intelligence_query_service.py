"""
Unified Intelligence Query Service

Provides a unified search interface across all intelligence sources:
- Marine Intelligence (articles, opportunities, accounts)
- Competitor Intelligence (documents, chunks)

Supports both semantic search (via embeddings) and structured queries.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceResult:
    """A single result from intelligence search."""

    id: str
    source: str  # "marine" or "competitor"
    title: str
    content_preview: str
    similarity: float
    metadata: dict = field(default_factory=dict)
    url: Optional[str] = None
    published_date: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "content_preview": self.content_preview,
            "similarity": round(self.similarity, 3),
            "metadata": self.metadata,
            "url": self.url,
            "published_date": (
                self.published_date.isoformat() if self.published_date else None
            ),
        }


@dataclass
class IntelligenceSearchResult:
    """Result from unified intelligence search."""

    query: str
    total_results: int
    results: list[IntelligenceResult]
    sources_searched: list[str]
    execution_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "total_results": self.total_results,
            "results": [r.to_dict() for r in self.results],
            "sources_searched": self.sources_searched,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


@dataclass
class IntelligenceAnswer:
    """Answer from RAG-based question answering."""

    question: str
    answer: str
    citations: list[IntelligenceResult]
    confidence: float
    model: str
    execution_time_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "confidence": round(self.confidence, 3),
            "model": self.model,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


class IntelligenceQueryService:
    """
    Unified query interface for all intelligence data.

    Supports:
    - Semantic search across marine and competitor intelligence
    - Natural language Q&A with RAG
    - Structured filtering

    Supports async context manager for proper resource cleanup:
        async with IntelligenceQueryService() as service:
            results = await service.search("query")
    """

    # Embedding configuration (same as other services)
    EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS = 1536

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set for intelligence queries")
        self.api_url = "https://api.openai.com/v1/embeddings"
        self.chat_url = "https://api.openai.com/v1/chat/completions"
        self._client: Optional[httpx.AsyncClient] = None
        self._owns_client = False

        # Lazy-loaded database instances
        self._marine_db = None
        self._competitor_db = None

    async def __aenter__(self) -> "IntelligenceQueryService":
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

    def _get_marine_db(self):
        """Get marine intel database (lazy load)."""
        if self._marine_db is None:
            from lead_to_cash.services.marine_intel.database import get_marine_intel_db

            self._marine_db = get_marine_intel_db()
        return self._marine_db

    def _get_competitor_db(self):
        """Get competitor intel database (lazy load)."""
        if self._competitor_db is None:
            from lead_to_cash.services.competitor_intel.database import (
                get_competitor_db,
            )

            self._competitor_db = get_competitor_db()
        return self._competitor_db

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for query text."""
        try:
            client = await self._get_client()
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text[:8000],
                    "model": self.EMBEDDING_MODEL,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                raise ValueError(
                    f"Embedding error: {response.status_code} - {response.text}"
                )
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to generate embedding: {e}")

    async def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        use_semantic: bool = True,
        filters: Optional[dict] = None,
        top_k: int = 20,
        min_similarity: float = 0.6,
    ) -> IntelligenceSearchResult:
        """
        Search across all intelligence sources.

        Args:
            query: Natural language search query
            sources: List of sources to search ("marine", "competitor")
                    Defaults to both.
            use_semantic: If True, use embedding-based semantic search.
                         If False, use text/structured search only.
            filters: Optional filters (source-specific)
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold for semantic search

        Returns:
            IntelligenceSearchResult with merged and ranked results
        """
        import time

        start_time = time.time()

        if sources is None:
            sources = ["marine", "competitor"]

        all_results: list[IntelligenceResult] = []
        sources_searched = []

        # Generate query embedding for semantic search
        query_embedding = None
        if use_semantic:
            try:
                query_embedding = await self._generate_embedding(query)
            except Exception as e:
                logger.warning(f"Failed to generate query embedding: {e}")
                use_semantic = False

        # Search marine intelligence
        if "marine" in sources:
            try:
                marine_results = await self._search_marine(
                    query=query,
                    query_embedding=query_embedding,
                    use_semantic=use_semantic,
                    filters=filters or {},
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
                all_results.extend(marine_results)
                sources_searched.append("marine")
            except Exception as e:
                logger.error(f"Error searching marine intelligence: {e}")

        # Search competitor intelligence
        if "competitor" in sources:
            try:
                competitor_results = await self._search_competitor(
                    query=query,
                    query_embedding=query_embedding,
                    use_semantic=use_semantic,
                    filters=filters or {},
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
                all_results.extend(competitor_results)
                sources_searched.append("competitor")
            except Exception as e:
                logger.error(f"Error searching competitor intelligence: {e}")

        # Sort by similarity and take top_k
        all_results.sort(key=lambda x: x.similarity, reverse=True)

        # Deduplicate by title across all sources
        seen: dict[str, "IntelligenceResult"] = {}
        deduped = []
        for r in all_results:
            title_key = r.title.strip().lower()
            if title_key not in seen:
                seen[title_key] = r
                deduped.append(r)
        all_results = deduped

        all_results = all_results[:top_k]

        execution_time = (time.time() - start_time) * 1000

        return IntelligenceSearchResult(
            query=query,
            total_results=len(all_results),
            results=all_results,
            sources_searched=sources_searched,
            execution_time_ms=execution_time,
        )

    async def _search_marine(
        self,
        query: str,
        query_embedding: Optional[list[float]],
        use_semantic: bool,
        filters: dict,
        top_k: int,
        min_similarity: float,
    ) -> list[IntelligenceResult]:
        """Search marine intelligence database."""
        results = []
        db = self._get_marine_db()
        await db.initialize()

        if use_semantic and query_embedding:
            # Semantic search
            articles = await db.vector_search_articles(
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=min_similarity,
            )

            for article, similarity in articles:
                # Safe content preview with length check
                if article.summary:
                    content_preview = article.summary
                elif article.content:
                    content_preview = (
                        article.content[:200] + "..."
                        if len(article.content) > 200
                        else article.content
                    )
                else:
                    content_preview = ""

                results.append(
                    IntelligenceResult(
                        id=article.id,
                        source="marine",
                        title=article.title,
                        content_preview=content_preview,
                        similarity=similarity,
                        metadata={
                            "source_publication": article.source,
                            "source_category": article.source_category,
                            "retention_tier": article.retention_tier,
                            "has_embedding": article.embedding is not None,
                        },
                        url=article.url,
                        published_date=article.published_date,
                    )
                )
        else:
            # Structured text search (fallback)
            articles = await db.list_articles(limit=top_k)
            for article in articles:
                # Simple text matching score
                query_lower = query.lower()
                score = 0.0
                if query_lower in article.title.lower():
                    score = 0.8
                elif article.content and query_lower in article.content.lower():
                    score = 0.6
                elif article.summary and query_lower in article.summary.lower():
                    score = 0.5

                if score >= min_similarity:
                    # Safe content preview with length check
                    if article.summary:
                        content_preview = article.summary
                    elif article.content:
                        content_preview = (
                            article.content[:200] + "..."
                            if len(article.content) > 200
                            else article.content
                        )
                    else:
                        content_preview = ""

                    results.append(
                        IntelligenceResult(
                            id=article.id,
                            source="marine",
                            title=article.title,
                            content_preview=content_preview,
                            similarity=score,
                            metadata={
                                "source_publication": article.source,
                                "source_category": article.source_category,
                            },
                            url=article.url,
                            published_date=article.published_date,
                        )
                    )

        return results

    async def _search_competitor(
        self,
        query: str,
        query_embedding: Optional[list[float]],
        use_semantic: bool,
        filters: dict,
        top_k: int,
        min_similarity: float,
    ) -> list[IntelligenceResult]:
        """Search competitor intelligence database."""
        results = []
        db = self._get_competitor_db()
        await db.initialize()

        if use_semantic and query_embedding:
            # Semantic search on document chunks using vector_search
            chunks = await db.vector_search(
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=min_similarity,
            )

            # Batch fetch all parent documents in a single query (avoid N+1)
            doc_ids = list({chunk.document_id for chunk, _ in chunks})
            docs_map = await db.get_documents_by_ids(doc_ids)

            for chunk, similarity in chunks:
                # Get parent document from pre-fetched map
                doc = docs_map.get(chunk.document_id)
                doc_title = doc.title if doc else f"Document {chunk.document_id}"
                doc_url = doc.source_url if doc else None

                # Safe content preview
                content = chunk.content or ""
                content_preview = (
                    content[:200] + "..." if len(content) > 200 else content
                )

                results.append(
                    IntelligenceResult(
                        id=chunk.id,
                        source="competitor",
                        title=doc_title,
                        content_preview=content_preview,
                        similarity=similarity,
                        metadata={
                            "document_id": chunk.document_id,
                            "chunk_index": chunk.chunk_index,
                            "competitor": chunk.metadata.get("competitor"),
                            "content_type": chunk.metadata.get("content_type"),
                        },
                        url=doc_url,
                        published_date=doc.published_date if doc else None,
                    )
                )

            # Deduplicate chunks from same document — keep best similarity, merge content
            doc_best: dict[str, "IntelligenceResult"] = {}
            for r in results:
                doc_id = r.metadata.get("document_id", r.id)
                if doc_id not in doc_best or r.similarity > doc_best[doc_id].similarity:
                    doc_best[doc_id] = r
            results = list(doc_best.values())

        else:
            # Structured text search (fallback)
            documents = await db.list_documents(limit=top_k)
            for doc in documents:
                query_lower = query.lower()
                score = 0.0
                if query_lower in doc.title.lower():
                    score = 0.8
                elif doc.content and query_lower in doc.content.lower():
                    score = 0.6

                if score >= min_similarity:
                    # Safe content preview with length check
                    if doc.summary:
                        content_preview = doc.summary
                    elif doc.content:
                        content_preview = (
                            doc.content[:200] + "..."
                            if len(doc.content) > 200
                            else doc.content
                        )
                    else:
                        content_preview = ""

                    results.append(
                        IntelligenceResult(
                            id=doc.id,
                            source="competitor",
                            title=doc.title,
                            content_preview=content_preview,
                            similarity=score,
                            metadata={
                                "competitor": doc.competitor,
                                "content_type": doc.content_type,
                            },
                            url=doc.source_url,
                            published_date=doc.published_date,
                        )
                    )

        return results

    async def ask(
        self,
        question: str,
        context_sources: Optional[list[str]] = None,
        top_k_context: int = 5,
        model: str = os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini"),
    ) -> IntelligenceAnswer:
        """
        Answer a natural language question using RAG.

        Args:
            question: Natural language question
            context_sources: Sources to search for context
            top_k_context: Number of context documents to use
            model: OpenAI model for answer generation

        Returns:
            IntelligenceAnswer with answer and citations
        """
        import time

        start_time = time.time()

        # Search for relevant context — fetch extra to allow deduplication
        search_results = await self.search(
            query=question,
            sources=context_sources,
            use_semantic=True,
            top_k=top_k_context * 3,
        )

        # Deduplicate by title (same article appears multiple times in vector DB)
        seen_titles: set[str] = set()
        unique_results = []
        for result in search_results.results:
            title_norm = result.title.strip().lower()
            if title_norm not in seen_titles:
                seen_titles.add(title_norm)
                unique_results.append(result)
            if len(unique_results) >= top_k_context:
                break
        search_results.results = unique_results

        # Build context from search results
        context_parts = []
        for i, result in enumerate(search_results.results, 1):
            context_parts.append(
                f"[{i}] {result.title}\n"
                f"Source: {result.source}\n"
                f"Content: {result.content_preview}\n"
            )

        context = "\n---\n".join(context_parts)

        # Generate answer using LLM
        prompt = f"""You are a maritime industry intelligence analyst. Synthesize an answer from the documents below.
Use the information available — even if documents are summaries, extract and combine the relevant facts.
Cite sources using [N] notation. Be specific and actionable.

Question: {question}

Intelligence Documents:
{context}

Answer:"""

        try:
            client = await self._get_client()
            response = await client.post(
                self.chat_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
            )

            if response.status_code == 200:
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                confidence = 0.8 if search_results.results else 0.2
            else:
                answer = f"Error generating answer: {response.status_code}"
                confidence = 0.0

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            answer = f"Error: {str(e)}"
            confidence = 0.0

        execution_time = (time.time() - start_time) * 1000

        return IntelligenceAnswer(
            question=question,
            answer=answer,
            citations=search_results.results,
            confidence=confidence,
            model=model,
            execution_time_ms=execution_time,
        )

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics from all intelligence sources."""
        stats: dict[str, Any] = {
            "marine": {},
            "competitor": {},
        }

        try:
            marine_db = self._get_marine_db()
            await marine_db.initialize()
            stats["marine"] = await marine_db.get_embedding_stats()
        except Exception as e:
            logger.error(f"Error getting marine stats: {e}")
            stats["marine"] = {"error": str(e)}

        try:
            competitor_db = self._get_competitor_db()
            await competitor_db.initialize()
            # Get basic stats
            docs = await competitor_db.list_documents(limit=1000)
            stats["competitor"] = {
                "total_documents": len(docs),
            }
        except Exception as e:
            logger.error(f"Error getting competitor stats: {e}")
            stats["competitor"] = {"error": str(e)}

        return stats


# Singleton instance
_query_service: Optional[IntelligenceQueryService] = None


def get_intelligence_query_service() -> IntelligenceQueryService:
    """
    Get or create the intelligence query service singleton.

    NOTE: Do NOT use the singleton with `async with` context manager.
    The singleton manages its own lifecycle - use close_intelligence_query_service()
    for application shutdown.

    For short-lived usage with automatic cleanup, create a new instance:
        async with IntelligenceQueryService() as service:
            results = await service.search("query")
    """
    global _query_service
    if _query_service is None:
        _query_service = IntelligenceQueryService()
    return _query_service


async def close_intelligence_query_service() -> None:
    """
    Close the singleton intelligence query service (call during application shutdown).

    Safe to call multiple times - will only close if service exists and is open.
    """
    global _query_service
    if _query_service is not None:
        await _query_service.close()
        _query_service = None


async def search_intelligence(
    query: str,
    sources: Optional[list[str]] = None,
    top_k: int = 20,
) -> IntelligenceSearchResult:
    """
    Convenience function for semantic search across intelligence.

    Args:
        query: Search query
        sources: Sources to search
        top_k: Maximum results

    Returns:
        Search results
    """
    service = get_intelligence_query_service()
    return await service.search(query=query, sources=sources, top_k=top_k)


async def ask_intelligence(
    question: str,
    sources: Optional[list[str]] = None,
) -> IntelligenceAnswer:
    """
    Convenience function for Q&A on intelligence data.

    Args:
        question: Natural language question
        sources: Sources to search

    Returns:
        Answer with citations
    """
    service = get_intelligence_query_service()
    return await service.ask(question=question, context_sources=sources)
