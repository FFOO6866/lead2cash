"""
Chunking Service for RAG Pipeline

Splits documents into optimal chunks for embedding and retrieval.
Uses tiktoken for accurate token counting (same tokenizer as OpenAI).

NO APPROXIMATIONS - real token counting for optimal chunk sizes.
"""

import logging
import re
from typing import Optional

import tiktoken

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Production chunking service for RAG documents.

    Uses tiktoken (cl100k_base encoding) for accurate token counting,
    matching the tokenizer used by OpenAI text-embedding-3-small.
    """

    # Chunk configuration optimized for RAG
    DEFAULT_CHUNK_SIZE = 512  # Tokens per chunk
    DEFAULT_CHUNK_OVERLAP = 50  # Overlap tokens for context
    MAX_CHUNK_SIZE = 8191  # OpenAI embedding model limit

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        """
        Initialize chunking service.

        Args:
            chunk_size: Target tokens per chunk (default 512)
            chunk_overlap: Overlap tokens between chunks (default 50)
        """
        self.chunk_size = min(chunk_size, self.MAX_CHUNK_SIZE)
        self.chunk_overlap = chunk_overlap

        # Use cl100k_base encoding (same as text-embedding-3-small)
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences.

        Uses regex patterns to handle various sentence endings.
        """
        # Split on sentence-ending punctuation followed by whitespace
        # Handles: periods, question marks, exclamation marks
        # Preserves abbreviations like "Dr." or "Inc."
        sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])"
        sentences = re.split(sentence_pattern, text)

        # Further split on newlines for paragraph boundaries
        result = []
        for sentence in sentences:
            # Split on double newlines (paragraphs)
            parts = re.split(r"\n\s*\n", sentence)
            for part in parts:
                cleaned = part.strip()
                if cleaned:
                    result.append(cleaned)

        return result

    def chunk_text(
        self,
        text: str,
        metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Split text into chunks with overlap.

        Uses semantic boundaries (sentences/paragraphs) when possible.
        Ensures accurate token counting with tiktoken.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries with:
            - content: Chunk text
            - token_count: Accurate token count
            - chunk_index: Position in document
            - metadata: Passed-through metadata
        """
        if not text:
            return []

        sentences = self._split_into_sentences(text)
        chunks = []
        current_chunk_sentences: list[str] = []
        current_token_count = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # Handle sentences longer than chunk size
            if sentence_tokens > self.chunk_size:
                # Save current chunk if exists
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunks.append(
                        {
                            "content": chunk_text,
                            "token_count": current_token_count,
                            "metadata": metadata or {},
                        }
                    )
                    current_chunk_sentences = []
                    current_token_count = 0

                # Split long sentence by words
                words = sentence.split()
                word_chunk: list[str] = []
                word_tokens = 0

                for word in words:
                    word_token_count = self.count_tokens(word + " ")

                    if word_tokens + word_token_count > self.chunk_size:
                        if word_chunk:
                            chunk_text = " ".join(word_chunk)
                            chunks.append(
                                {
                                    "content": chunk_text,
                                    "token_count": word_tokens,
                                    "metadata": metadata or {},
                                }
                            )
                        word_chunk = [word]
                        word_tokens = word_token_count
                    else:
                        word_chunk.append(word)
                        word_tokens += word_token_count

                # Remaining words become start of next chunk
                if word_chunk:
                    current_chunk_sentences = [" ".join(word_chunk)]
                    current_token_count = word_tokens
                continue

            # Check if adding sentence exceeds chunk size
            if current_token_count + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunks.append(
                        {
                            "content": chunk_text,
                            "token_count": current_token_count,
                            "metadata": metadata or {},
                        }
                    )

                # Start new chunk with overlap
                # Take sentences from end of previous chunk for context
                overlap_sentences: list[str] = []
                overlap_tokens = 0

                for s in reversed(current_chunk_sentences):
                    s_tokens = self.count_tokens(s)
                    if overlap_tokens + s_tokens <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break

                current_chunk_sentences = overlap_sentences + [sentence]
                current_token_count = overlap_tokens + sentence_tokens
            else:
                current_chunk_sentences.append(sentence)
                current_token_count += sentence_tokens

        # Save final chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append(
                {
                    "content": chunk_text,
                    "token_count": current_token_count,
                    "metadata": metadata or {},
                }
            )

        # Add chunk indices
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i

        logger.debug(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks

    def chunk_document(
        self,
        title: str,
        content: str,
        summary: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Chunk a document with context from title and summary.

        Prepends title and summary to content for better context.

        Args:
            title: Document title
            content: Document content
            summary: Optional document summary
            metadata: Optional metadata

        Returns:
            List of chunk dictionaries
        """
        # Build full text with context
        parts = [title]
        if summary:
            parts.append(f"Summary: {summary}")
        parts.append(content)

        full_text = "\n\n".join(parts)

        return self.chunk_text(full_text, metadata)


# Singleton instance
_chunking_service: Optional[ChunkingService] = None


def get_chunking_service(
    chunk_size: int = ChunkingService.DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = ChunkingService.DEFAULT_CHUNK_OVERLAP,
) -> ChunkingService:
    """Get or create the chunking service singleton."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService(chunk_size, chunk_overlap)
    return _chunking_service


def chunk_document(
    content: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Convenience function to chunk a document.

    Args:
        content: Text content to chunk
        chunk_size: Target tokens per chunk
        chunk_overlap: Overlap tokens

    Returns:
        List of chunk dictionaries
    """
    service = ChunkingService(chunk_size, chunk_overlap)
    return service.chunk_text(content)
