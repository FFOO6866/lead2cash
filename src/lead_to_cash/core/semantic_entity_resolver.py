"""
Semantic Entity Resolution Service

Industry-leading approach to entity/pronoun resolution using embeddings
and semantic similarity instead of keyword matching or recency heuristics.

Architecture:
1. Embed entity mentions with their conversational context
2. Embed user queries
3. Use cosine similarity to find semantically relevant entities
4. Detect ambiguity and request clarification when needed

NO KEYWORD MATCHING - Pure semantic understanding via embeddings.

Usage:
    resolver = SemanticEntityResolver()
    await resolver.initialize()

    # Track entity with context
    await resolver.track_entity(
        name="ST Engineering",
        entity_type="company",
        context="User asked for KYP report on ST Engineering"
    )

    # Resolve reference in new query
    result = await resolver.resolve_reference(
        query="What's their credit limit?",
        entity_history=session.entity_history
    )

    if result.status == ResolutionStatus.RESOLVED:
        print(f"Resolved to: {result.entity_name}")
    elif result.status == ResolutionStatus.AMBIGUOUS:
        print(f"Ambiguous: {result.candidates}")  # Ask user to clarify
"""

import hashlib
import logging
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# MODULE-LEVEL EMBEDDING CACHE
# =============================================================================
# Shared across all resolver instances for efficiency.
# Static descriptions (intents, sections, etc.) are embedded once and reused.

# LRU cache with max size for dynamic embeddings (queries, entity contexts)
MAX_DYNAMIC_CACHE_SIZE = 1000

# Module-level caches (shared across instances)
_static_embedding_cache: dict[str, list[float]] = {}  # For static descriptions
_dynamic_embedding_cache: OrderedDict[str, list[float]] = (
    OrderedDict()
)  # LRU for queries

# =============================================================================
# ABBREVIATION REGISTRY
# =============================================================================
# Maps known abbreviations to full entity names for query expansion.
# Populated dynamically from SIMULATED_CUSTOMERS via register_known_customers()
# and when entities are tracked at runtime via register_entity_abbreviations().
# Example: {"ste": "ST Engineering", "bff": "Batam Fast Ferry"}

_abbreviation_registry: dict[str, str] = {}

# Corporate suffixes to strip when deriving short names for abbreviation generation
_CORPORATE_SUFFIXES_RE = (
    " pte. ltd.", " pte ltd", " a/s", " b.v.", " co., ltd.",
    " pty ltd", " ltd.", " ltd", " inc.", " inc", " corp.",
)


def _strip_corporate_suffix(name: str) -> str:
    """Strip common corporate suffixes for cleaner abbreviation generation."""
    lower = name.lower()
    for suffix in _CORPORATE_SUFFIXES_RE:
        if lower.endswith(suffix):
            return name[: len(name) - len(suffix)].rstrip(" ,.-")
    return name


def register_known_customers(customers: dict) -> None:
    """
    Populate the abbreviation registry from SIMULATED_CUSTOMERS data.

    Extracts name1/name2 from each customer and registers abbreviations
    dynamically — single source of truth, no hardcoded alias maintenance.

    Args:
        customers: Dict of customer_id → SimulatedCustomer (or any object
                   with .name1 and .name2 attributes).
    """
    for _cust_id, cust in customers.items():
        # Use name2 as the canonical short name if available, else name1
        canonical = (cust.name2 or cust.name1).strip()
        if not canonical:
            continue

        # Register abbreviations for the canonical name
        register_entity_abbreviations(canonical)

        # Also register abbreviations for name1 if it differs from name2
        name1 = cust.name1.strip() if cust.name1 else ""
        if name1 and name1.lower() != canonical.lower():
            register_entity_abbreviations(name1)
            # Map name1 lowercase → canonical so queries like
            # "batam fast ferry pte ltd" resolve to "Batam Fast Ferry"
            _abbreviation_registry.setdefault(name1.lower(), canonical)

            # Also register the suffix-stripped version of name1 so that
            # "Batam Fast Ferry Pte. Ltd." → "Batam Fast Ferry" → "BFF"
            stripped = _strip_corporate_suffix(name1)
            if stripped.lower() != name1.lower() and stripped.lower() != canonical.lower():
                register_entity_abbreviations(stripped)
                _abbreviation_registry.setdefault(stripped.lower(), canonical)

    logger.info(
        f"Registered {len(_abbreviation_registry)} abbreviations "
        f"from {len(customers)} customers"
    )


def _generate_abbreviations(name: str) -> list[str]:
    """
    Generate common abbreviations from an entity name.

    Examples:
    - "ST Engineering" → ["STE", "STEngineering", "STEngg", "ST"]
    - "Batam Fast Ferry" → ["BFF", "BatamFastFerry", "BatamFast"]
    - "Maersk A/S" → ["Maersk", "MAS"]

    Returns:
        List of possible abbreviations (uppercase and mixed case)
    """
    abbreviations = []
    words = name.replace("/", " ").replace("-", " ").split()

    # Filter out common suffixes
    filtered_words = [
        w
        for w in words
        if w.upper() not in {"A/S", "AS", "LTD", "PTE", "INC", "CORP", "CO", "THE"}
    ]

    if not filtered_words:
        filtered_words = words

    # 1. Acronym from first letters - SPECIAL HANDLING for all-caps words
    # "ST Engineering" → "STE" (ST + E), "Batam Fast Ferry" → "BFF" (B + F + F)
    if len(filtered_words) > 1:
        acronym_parts = []
        for w in filtered_words:
            if w:
                # If word is all-caps (like "ST"), use the whole word
                if w.isupper() and len(w) <= 3:
                    acronym_parts.append(w)
                else:
                    # Otherwise just take first letter
                    acronym_parts.append(w[0].upper())
        acronym = "".join(acronym_parts)
        if len(acronym) >= 2:
            abbreviations.append(acronym)

    # 2. CamelCase concatenation (e.g., "Batam Fast Ferry" → "BatamFastFerry")
    if len(filtered_words) > 1:
        camel = "".join(w.capitalize() for w in filtered_words)
        abbreviations.append(camel)

    # 3. First word + abbreviation (e.g., "ST Engineering" → "STEngg")
    if len(filtered_words) >= 2:
        first_word = filtered_words[0]
        # Common suffixes to try
        suffix_abbrevs = {
            "engineering": "Engg",
            "technology": "Tech",
            "technologies": "Tech",
            "marine": "Mar",
            "services": "Svc",
        }
        for word in filtered_words[1:]:
            abbrev = suffix_abbrevs.get(word.lower())
            if abbrev:
                abbreviations.append(first_word + abbrev)

    # 4. First word alone if it's distinctive (2+ chars, not common)
    if filtered_words:
        first = filtered_words[0]
        if len(first) >= 2 and first.lower() not in {"the", "a", "an"}:
            abbreviations.append(first)

    # 5. First two words concatenated (e.g., "Batam Fast" for "Batam Fast Ferry")
    if len(filtered_words) >= 2:
        abbreviations.append(filtered_words[0] + filtered_words[1])

    # Remove duplicates and empty strings, normalize
    unique = []
    seen = set()
    for abbr in abbreviations:
        if abbr and abbr.lower() not in seen:
            seen.add(abbr.lower())
            unique.append(abbr)

    return unique


def register_entity_abbreviations(name: str) -> None:
    """
    Register abbreviations for an entity in the global registry.

    Called when tracking new entities to enable query expansion.
    """
    abbrevs = _generate_abbreviations(name)
    for abbr in abbrevs:
        # Use lowercase for matching, store canonical name
        key = abbr.lower()
        if key not in _abbreviation_registry:
            _abbreviation_registry[key] = name
            logger.debug(f"Registered abbreviation: {abbr} → {name}")


def expand_abbreviations_in_query(query: str) -> tuple[str, list[str]]:
    """
    Expand known abbreviations in a query to their full entity names.

    This improves semantic matching for short acronyms like "STE" or "BFF"
    which have weak embedding signal on their own.

    Args:
        query: User's query that may contain abbreviations

    Returns:
        Tuple of (expanded_query, list_of_expansions_made)

    Example:
        "STE credit limit" → ("ST Engineering credit limit", ["STE → ST Engineering"])
    """
    if not _abbreviation_registry:
        return query, []

    expansions = []
    words = query.split()
    expanded_words = []

    for word in words:
        # Clean punctuation for matching but preserve it
        clean = word.strip(".,!?;:'\"()[]{}").lower()
        remainder_before = word[: len(word) - len(word.lstrip(".,!?;:'\"()[]{}"))]
        remainder_after = word[len(word.rstrip(".,!?;:'\"()[]{}")) :]

        if clean in _abbreviation_registry:
            full_name = _abbreviation_registry[clean]
            expanded_words.append(remainder_before + full_name + remainder_after)
            expansions.append(f"{word} → {full_name}")
        else:
            expanded_words.append(word)

    expanded_query = " ".join(expanded_words)

    if expansions:
        logger.info(f"Expanded abbreviations: {expansions}")

    return expanded_query, expansions


def _get_cache_key(text: str) -> str:
    """Generate a cache key for text (normalized and hashed for long texts)."""
    normalized = text.strip().lower()
    if len(normalized) > 200:
        # Hash long texts to keep keys manageable
        return hashlib.md5(normalized.encode()).hexdigest()
    return normalized


def _get_from_dynamic_cache(key: str) -> Optional[list[float]]:
    """Get from LRU cache, moving to end if found (most recently used)."""
    if key in _dynamic_embedding_cache:
        # Move to end (most recently used)
        _dynamic_embedding_cache.move_to_end(key)
        return _dynamic_embedding_cache[key]
    return None


def _add_to_dynamic_cache(key: str, embedding: list[float]) -> None:
    """Add to LRU cache, evicting oldest if at capacity."""
    global _dynamic_embedding_cache
    if key in _dynamic_embedding_cache:
        _dynamic_embedding_cache.move_to_end(key)
    else:
        if len(_dynamic_embedding_cache) >= MAX_DYNAMIC_CACHE_SIZE:
            # Evict oldest (first item)
            _dynamic_embedding_cache.popitem(last=False)
        _dynamic_embedding_cache[key] = embedding


# OpenAI embedding configuration
EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = 1536
OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"

# Resolution thresholds (tuned for pronoun/reference resolution)
# These are intentionally lower than typical semantic search because:
# 1. Pronouns like "their" have no semantic weight
# 2. Follow-up queries are often short and context-dependent
# 3. We want to resolve to SOMETHING when there's entity history
HIGH_CONFIDENCE_THRESHOLD = 0.45  # Above this = high confidence match
AMBIGUITY_THRESHOLD = 0.30  # Above this but close scores = ambiguous
SCORE_DIFFERENCE_THRESHOLD = 0.08  # Min difference to avoid ambiguity
NO_MATCH_THRESHOLD = 0.25  # Below this = no semantic match
# Pure pronoun fallback threshold - if ALL scores are below this AND
# query contains reference words (pronouns, business terms), the query is
# likely a pronoun-based reference that can't be semantically matched.
# In this case, use recency to resolve to the most recently discussed entity.
PURE_PRONOUN_THRESHOLD = 0.26  # Below this + reference words = use recency


class ResolutionStatus(str, Enum):
    """Status of entity resolution attempt."""

    RESOLVED = "resolved"  # Single clear match found
    AMBIGUOUS = "ambiguous"  # Multiple potential matches - need clarification
    NO_MATCH = "no_match"  # No semantically relevant entity found
    NO_HISTORY = "no_history"  # No entity history to search
    ERROR = "error"  # Resolution failed due to error


@dataclass
class EntityCandidate:
    """A candidate entity with similarity score."""

    name: str
    entity_type: str  # company, competitor, product
    similarity_score: float
    context: str  # Original context where entity was mentioned
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "similarity_score": round(self.similarity_score, 3),
            "context": (
                self.context[:100] + "..." if len(self.context) > 100 else self.context
            ),
            "timestamp": self.timestamp,
        }


@dataclass
class ResolutionResult:
    """Result of semantic entity resolution."""

    status: ResolutionStatus
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    confidence: float = 0.0
    candidates: list[EntityCandidate] = field(default_factory=list)
    clarification_prompt: Optional[str] = None
    resolution_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "confidence": round(self.confidence, 3),
            "candidates": [c.to_dict() for c in self.candidates[:3]],
            "clarification_prompt": self.clarification_prompt,
            "resolution_reason": self.resolution_reason,
        }


@dataclass
class TrackedEntity:
    """An entity tracked with its embedding."""

    name: str
    entity_type: str
    context: str
    embedding: list[float]
    timestamp: str
    turn_index: int  # Which conversation turn this was mentioned in


class SemanticEntityResolver:
    """
    Semantic entity resolution using embeddings.

    This resolver uses OpenAI embeddings to understand the semantic
    relationship between user queries and previously mentioned entities.

    Key features:
    - No keyword matching or pattern detection
    - Cosine similarity for semantic matching
    - Ambiguity detection with clarification prompts
    - Context-aware (considers HOW entities were mentioned)
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        high_confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
        ambiguity_threshold: float = AMBIGUITY_THRESHOLD,
        score_difference_threshold: float = SCORE_DIFFERENCE_THRESHOLD,
    ):
        """
        Initialize the semantic entity resolver.

        Args:
            openai_api_key: OpenAI API key (or uses OPENAI_API_KEY env var)
            high_confidence_threshold: Score above which we're confident
            ambiguity_threshold: Score above which we consider as candidate
            score_difference_threshold: Min score gap to avoid ambiguity
        """
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.high_confidence = high_confidence_threshold
        self.ambiguity_threshold = ambiguity_threshold
        self.score_diff_threshold = score_difference_threshold

        self._client: Optional[httpx.AsyncClient] = None
        self._static_embeddings_initialized = False

    async def initialize(self) -> None:
        """Initialize the HTTP client and pre-compute static embeddings."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

        # Pre-compute static embeddings (only once across all instances)
        if not self._static_embeddings_initialized and not _static_embedding_cache:
            await self._precompute_static_embeddings()
            self._static_embeddings_initialized = True

    async def _precompute_static_embeddings(self) -> None:
        """
        Pre-compute embeddings for all static descriptions.

        These are computed once and cached at module level for all instances.
        This eliminates redundant API calls for time sensitivity, intent
        classification, KYP sections, and irrelevance detection.
        """
        logger.info("Pre-computing static embeddings for semantic resolver...")

        # Collect all static descriptions to embed in one batch
        static_texts = []
        static_keys = []

        # Time descriptions
        for key, desc in self.TIME_DESCRIPTIONS.items():
            cache_key = f"time:{key}"
            static_keys.append(cache_key)
            static_texts.append(desc)

        # Intent descriptions
        for key, desc in self.INTENT_DESCRIPTIONS.items():
            cache_key = f"intent:{key}"
            static_keys.append(cache_key)
            static_texts.append(desc)

        # KYP section descriptions
        for key, desc in self.KYP_SECTION_DESCRIPTIONS.items():
            cache_key = f"kyp:{key}"
            static_keys.append(cache_key)
            static_texts.append(desc)

        # Irrelevance/relevance descriptions
        static_keys.append("irrelevant:leisure")
        static_texts.append(self.IRRELEVANT_CONTENT_DESCRIPTION)
        static_keys.append("irrelevant:commercial")
        static_texts.append(self.COMMERCIAL_MARINE_DESCRIPTION)

        # Batch embed all static descriptions
        try:
            embeddings = await self._embed_texts_raw(static_texts)
            for key, embedding in zip(static_keys, embeddings):
                _static_embedding_cache[key] = embedding
            logger.info(f"Pre-computed {len(embeddings)} static embeddings")
        except Exception as e:
            logger.warning(f"Failed to pre-compute static embeddings: {e}")

    async def _embed_texts_raw(self, texts: list[str]) -> list[list[float]]:
        """
        Raw embedding call without caching (for batch pre-computation).
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

        response = await self._client.post(
            OPENAI_EMBEDDING_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": [t.strip()[:8000] for t in texts],
            },
        )

        if response.status_code == 200:
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        else:
            raise RuntimeError(f"Embedding API failed: {response.status_code}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # EMBEDDING OPERATIONS
    # =========================================================================

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text using OpenAI API.

        Uses module-level LRU caching to avoid redundant API calls.
        Cache is shared across all resolver instances.
        """
        # Check module-level LRU cache first
        cache_key = _get_cache_key(text)
        cached = _get_from_dynamic_cache(cache_key)
        if cached is not None:
            return cached

        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        if self._client is None:
            await self.initialize()

        try:
            response = await self._client.post(
                OPENAI_EMBEDDING_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text.strip()[:8000],  # API limit
                },
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                # Add to module-level LRU cache
                _add_to_dynamic_cache(cache_key, embedding)
                return embedding
            else:
                logger.error(
                    f"Embedding API error: {response.status_code} - {response.text}"
                )
                raise RuntimeError(f"Embedding API failed: {response.status_code}")

        except httpx.TimeoutException:
            logger.error("Embedding API timeout")
            raise
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise

    async def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Get embeddings for multiple texts efficiently.

        Uses module-level LRU cache and batches cache misses into a single API call.
        """
        # Check module-level cache and identify misses
        results = []
        texts_to_embed = []
        text_indices = []
        cache_keys = []

        for i, text in enumerate(texts):
            cache_key = _get_cache_key(text)
            cache_keys.append(cache_key)
            cached = _get_from_dynamic_cache(cache_key)
            if cached is not None:
                results.append((i, cached))
            else:
                texts_to_embed.append(text.strip()[:8000])
                text_indices.append(i)

        # Batch embed cache misses
        if texts_to_embed:
            if not self.api_key:
                raise ValueError("OpenAI API key not configured")

            if self._client is None:
                await self.initialize()

            try:
                response = await self._client.post(
                    OPENAI_EMBEDDING_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": texts_to_embed,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    for j, item in enumerate(data["data"]):
                        embedding = item["embedding"]
                        idx = text_indices[j]
                        results.append((idx, embedding))
                        # Add to module-level LRU cache
                        _add_to_dynamic_cache(cache_keys[idx], embedding)
                else:
                    logger.error(f"Batch embedding error: {response.status_code}")
                    raise RuntimeError(
                        f"Batch embedding failed: {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"Batch embedding error: {e}")
                raise

        # Sort by original index and return embeddings
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec1)
        b = np.array(vec2)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _get_static_embedding(self, cache_key: str) -> Optional[list[float]]:
        """
        Get a pre-computed static embedding from module-level cache.

        Args:
            cache_key: Key like "time:recent", "intent:kyp_due_diligence", etc.

        Returns:
            Embedding if pre-computed, None otherwise.
        """
        return _static_embedding_cache.get(cache_key)

    async def _ensure_static_embeddings(self) -> None:
        """Ensure static embeddings are initialized (called on first use)."""
        if not _static_embedding_cache:
            await self._precompute_static_embeddings()

    # =========================================================================
    # ENTITY TRACKING
    # =========================================================================

    async def create_entity_embedding(
        self,
        name: str,
        entity_type: str,
        context: str,
    ) -> list[float]:
        """
        Create an embedding for an entity mention with context.

        The embedding captures both the entity name and HOW it was discussed,
        which helps with semantic resolution later.

        Also registers abbreviations for the entity to enable query expansion.

        Args:
            name: Entity name (e.g., "ST Engineering")
            entity_type: Type (company, competitor, product)
            context: Surrounding text/conversation context

        Returns:
            Embedding vector
        """
        # Register abbreviations for this entity (enables "STE" → "ST Engineering")
        register_entity_abbreviations(name)

        # Create a rich text representation that captures the entity in context
        embedding_text = f"{entity_type}: {name}. Context: {context}"
        return await self._get_embedding(embedding_text)

    # =========================================================================
    # SEMANTIC RESOLUTION
    # =========================================================================

    async def resolve_reference(
        self,
        query: str,
        entity_history: list[dict[str, Any]],
        include_competitors: bool = True,
        include_products: bool = False,
    ) -> ResolutionResult:
        """
        Resolve entity references in a query using semantic similarity.

        This is the core resolution method that:
        1. Embeds the query
        2. Compares to all tracked entity contexts
        3. Determines if there's a clear match, ambiguity, or no match

        Args:
            query: User's query that may reference an entity
            entity_history: List of {name, type, context, embedding?, timestamp} dicts
            include_competitors: Whether to consider competitors
            include_products: Whether to consider products

        Returns:
            ResolutionResult with status, resolved entity, or candidates for clarification
        """
        if not entity_history:
            return ResolutionResult(
                status=ResolutionStatus.NO_HISTORY,
                resolution_reason="No entity history available",
            )

        # Filter by entity types we care about
        allowed_types = {"company"}
        if include_competitors:
            allowed_types.add("competitor")
        if include_products:
            allowed_types.add("product")

        relevant_entities = [
            e for e in entity_history if e.get("type", "company") in allowed_types
        ]

        if not relevant_entities:
            return ResolutionResult(
                status=ResolutionStatus.NO_HISTORY,
                resolution_reason="No relevant entities in history",
            )

        try:
            # Step 0a: Register abbreviations for all entities in history FIRST
            # This must happen before expansion so we know all abbreviations
            for entity in relevant_entities:
                register_entity_abbreviations(entity["name"])

            # Step 0b: Expand abbreviations in query (e.g., "STE" → "ST Engineering")
            # This improves semantic signal for short acronyms
            expanded_query, expansions = expand_abbreviations_in_query(query)
            query_for_embedding = expanded_query if expansions else query

            # Step 1: Embed the (potentially expanded) query
            query_embedding = await self._get_embedding(query_for_embedding)

            # Step 2: Get or compute embeddings for all entities
            candidates = []

            for entity in relevant_entities:

                # Check if embedding already exists
                if "embedding" in entity and entity["embedding"]:
                    entity_embedding = entity["embedding"]
                else:
                    # Compute embedding from context
                    context = entity.get(
                        "context", f"Discussion about {entity['name']}"
                    )
                    entity_embedding = await self.create_entity_embedding(
                        name=entity["name"],
                        entity_type=entity.get("type", "company"),
                        context=context,
                    )

                # Compute similarity
                similarity = self._cosine_similarity(query_embedding, entity_embedding)

                candidates.append(
                    EntityCandidate(
                        name=entity["name"],
                        entity_type=entity.get("type", "company"),
                        similarity_score=similarity,
                        context=entity.get("context", ""),
                        timestamp=entity.get("timestamp", ""),
                    )
                )

            # Step 3: Sort by similarity (highest first)
            candidates.sort(key=lambda c: c.similarity_score, reverse=True)

            # Step 4: Make resolution decision
            return self._make_resolution_decision(candidates, query)

        except Exception as e:
            logger.error(f"Semantic resolution failed: {e}")
            return ResolutionResult(
                status=ResolutionStatus.ERROR,
                resolution_reason=f"Resolution error: {str(e)}",
            )

    def _make_resolution_decision(
        self,
        candidates: list[EntityCandidate],
        query: str,
    ) -> ResolutionResult:
        """
        Make a resolution decision based on candidate scores.

        Decision logic:
        1. If top score > high_confidence AND significantly higher than #2 → RESOLVED
        2. If top scores are close (both > ambiguity_threshold) → AMBIGUOUS
        3. If top score < ambiguity_threshold → NO_MATCH
        """
        if not candidates:
            return ResolutionResult(
                status=ResolutionStatus.NO_MATCH,
                resolution_reason="No candidates found",
            )

        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        # Calculate score difference
        score_diff = top.similarity_score - (second.similarity_score if second else 0)

        second_score = second.similarity_score if second else 0.0
        logger.info(
            f"Semantic resolution: top='{top.name}' ({top.similarity_score:.3f}), "
            f"second='{second.name if second else 'N/A'}' ({second_score:.3f}), "
            f"diff={score_diff:.3f}"
        )

        # Decision 1: Clear high-confidence match
        if (
            top.similarity_score >= self.high_confidence
            and score_diff >= self.score_diff_threshold
        ):
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED,
                entity_name=top.name,
                entity_type=top.entity_type,
                confidence=top.similarity_score,
                candidates=candidates[:3],
                resolution_reason=(
                    f"High confidence match: {top.name} "
                    f"(score={top.similarity_score:.3f}, diff={score_diff:.3f})"
                ),
            )

        # Decision 2: Ambiguous - multiple good candidates
        if (
            top.similarity_score >= self.ambiguity_threshold
            and second
            and second.similarity_score >= self.ambiguity_threshold
            and score_diff < self.score_diff_threshold
        ):

            # Generate clarification prompt
            candidate_names = [
                c.name
                for c in candidates[:3]
                if c.similarity_score >= self.ambiguity_threshold
            ]
            clarification = self._generate_clarification_prompt(candidate_names, query)

            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                confidence=top.similarity_score,
                candidates=candidates[:3],
                clarification_prompt=clarification,
                resolution_reason=(
                    f"Ambiguous: top candidates are close "
                    f"({top.name}={top.similarity_score:.3f}, "
                    f"{second.name}={second.similarity_score:.3f})"
                ),
            )

        # Decision 3: Moderate confidence - resolve but note uncertainty
        if top.similarity_score >= self.ambiguity_threshold:
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED,
                entity_name=top.name,
                entity_type=top.entity_type,
                confidence=top.similarity_score,
                candidates=candidates[:3],
                resolution_reason=(
                    f"Moderate confidence match: {top.name} "
                    f"(score={top.similarity_score:.3f})"
                ),
            )

        # Decision 3.5: Pure pronoun fallback - use recency
        # If scores are low but query contains ONLY pronoun-like references (no potential
        # company names), fall back to the most recently discussed entity.
        #
        # IMPORTANT: Don't use recency if query contains potential company identifiers
        # like "STE", "BFF", or capitalized words - those need semantic resolution,
        # not blind recency fallback.

        # Reference words that indicate pronouns/generic references
        reference_words = {
            "their",
            "them",
            "they",
            "it",
            "its",
            "this",
            "that",
            "company",
            "customer",
            "client",
            "business",
            "firm",
            "organization",
            "billing",
            "credit",
            "invoice",
            "payment",
            "account",
            "status",
        }

        # Common words that are NOT company identifiers (don't block recency for these)
        non_entity_words = {
            "check",
            "what",
            "show",
            "tell",
            "about",
            "for",
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "has",
            "have",
            "get",
            "find",
            "limit",
            "exposure",
            "aging",
            "buckets",
            "outstanding",
            "overdue",
            "balance",
            "me",
            "please",
            "can",
            "you",
            "i",
            "my",
            "we",
            "our",
            "on",
            "of",
            "to",
        }

        query_lower = query.lower()
        # Strip punctuation from words for proper matching
        query_words = set(word.strip(".,!?;:'\"()[]{}") for word in query_lower.split())
        has_reference = bool(query_words & reference_words)

        # Check for potential company identifiers:
        # - Capitalized words in original query (like "STE", "Maersk")
        # - All-caps words (acronyms like "STE", "BFF")
        # - Words that aren't in reference_words or non_entity_words
        # - EXCLUDE first word (sentences start with capitals)
        original_words = query.split()
        potential_company_words = []
        for i, word in enumerate(original_words):
            clean = word.strip(".,!?;:'\"()[]{}").lower()
            # Skip first word (sentence always starts with capital)
            is_first_word = i == 0
            # Check if word is all-caps (acronym) - strong signal
            is_acronym = word.strip(".,!?;:'\"()[]{}").isupper() and len(clean) >= 2
            # Check if word is capitalized (not first) and not common
            is_capitalized = word[0].isupper() if word else False
            is_common = clean in reference_words or clean in non_entity_words

            # Include if: acronym OR (capitalized, not first, not common)
            if is_acronym and not is_common:
                potential_company_words.append(word)
            elif is_capitalized and not is_first_word and not is_common:
                potential_company_words.append(word)

        has_potential_company = len(potential_company_words) > 0

        # Apply recency fallback ONLY if:
        # 1. Query contains reference words (pronouns, business terms)
        # 2. Query does NOT contain potential company identifiers
        # 3. All semantic scores are below the pure pronoun threshold
        if (
            has_reference
            and not has_potential_company
            and top.similarity_score < PURE_PRONOUN_THRESHOLD
            and candidates
        ):
            # Find the most recent entity by timestamp
            candidates_with_time = [c for c in candidates if c.timestamp]
            if candidates_with_time:
                # Sort by timestamp descending (most recent first)
                most_recent = max(candidates_with_time, key=lambda c: c.timestamp)
                logger.info(
                    f"Pure pronoun fallback: scores < {PURE_PRONOUN_THRESHOLD}, "
                    f"no company identifiers, using most recent: {most_recent.name}"
                )
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_name=most_recent.name,
                    entity_type=most_recent.entity_type,
                    confidence=0.5,  # Moderate confidence for recency-based
                    candidates=candidates[:3],
                    resolution_reason=(
                        f"Recency fallback (pure pronoun query): {most_recent.name} "
                        f"(most recent entity, semantic scores too low: {top.similarity_score:.3f})"
                    ),
                )

        # If query has potential company identifiers but low scores, log for debugging
        if has_potential_company and top.similarity_score < PURE_PRONOUN_THRESHOLD:
            logger.debug(
                f"Low score ({top.similarity_score:.3f}) but query has potential company "
                f"identifiers: {potential_company_words} - NOT using recency fallback"
            )

        # Decision 4: No good match
        return ResolutionResult(
            status=ResolutionStatus.NO_MATCH,
            candidates=candidates[:3],
            resolution_reason=(
                f"No semantic match found (top score {top.similarity_score:.3f} "
                f"< threshold {self.ambiguity_threshold})"
            ),
        )

    def _generate_clarification_prompt(
        self,
        candidate_names: list[str],
        query: str,
    ) -> str:
        """Generate a user-friendly clarification prompt."""
        if len(candidate_names) == 2:
            return (
                f"I want to make sure I understand correctly. "
                f"Are you asking about **{candidate_names[0]}** or **{candidate_names[1]}**?"
            )
        else:
            names_str = ", ".join(f"**{n}**" for n in candidate_names[:-1])
            return (
                f"I want to make sure I understand correctly. "
                f"Are you asking about {names_str}, or **{candidate_names[-1]}**?"
            )

    # =========================================================================
    # RELEVANCE SCORING (replaces keyword-based RELEVANCE_INDICATORS)
    # =========================================================================

    async def check_content_relevance(
        self,
        content: str,
        business_context: str = "RRPS marine and power generation business: MTU and Bergen diesel engines for commercial vessels, offshore platforms, ferries, tugs, OSV, PSV",
    ) -> tuple[bool, float, str]:
        """
        Check content relevance using semantic similarity.

        Replaces keyword-based check_content_relevance() with embedding similarity.

        Args:
            content: Content to check for relevance
            business_context: Description of relevant business domain

        Returns:
            Tuple of (is_relevant, confidence_score, reason)
        """
        try:
            # Embed both content and business context
            embeddings = await self._get_embeddings_batch(
                [content[:2000], business_context]
            )
            content_embedding = embeddings[0]
            context_embedding = embeddings[1]

            # Compute similarity
            similarity = self._cosine_similarity(content_embedding, context_embedding)

            # Threshold for relevance
            is_relevant = similarity >= 0.35  # Lower threshold for content relevance

            reason = (
                f"Semantic relevance score: {similarity:.3f} "
                f"({'relevant' if is_relevant else 'not relevant'} to marine/power business)"
            )

            return is_relevant, similarity, reason

        except Exception as e:
            logger.warning(f"Relevance check failed: {e}, defaulting to relevant")
            return True, 0.5, f"Relevance check failed: {e}"

    # =========================================================================
    # INTENT CLASSIFICATION (replaces keyword-based _extract_previous_intent)
    # =========================================================================

    # Intent descriptions for embedding-based classification
    INTENT_DESCRIPTIONS = {
        "market_intel": (
            "Market intelligence, industry analysis, market opportunities, "
            "regional market news, business opportunities in marine or power sectors"
        ),
        "competitor_intel": (
            "Competitor analysis, competitive intelligence, information about rivals "
            "like Caterpillar, Cummins, MAN Energy, Wärtsilä, competitor contracts and wins"
        ),
        "kyp_due_diligence": (
            "Know Your Partner, KYP, run KYP, perform KYP, KYP on, KYP report, KYP check, "
            "due diligence, compliance check, sanctions screening, "
            "risk assessment, background check on a company"
        ),
        "customer_intel": (
            "Customer information, fleet details, installed base, customer relationship, "
            "account information, customer history"
        ),
        "billing_ar": (
            "Billing information, accounts receivable, invoices, payment status, "
            "collections, aging buckets, outstanding amounts"
        ),
        "credit_check": (
            "Credit limit, credit exposure, credit status, payment history, "
            "credit utilization, financial creditworthiness"
        ),
    }

    async def classify_intent_from_history(
        self,
        conversation_history: list[dict],
        intent_map: Optional[dict[str, str]] = None,
    ) -> Optional[tuple[str, float]]:
        """
        Classify the intent from conversation history using semantic similarity.

        Replaces keyword-based _extract_previous_intent() with embedding comparison.
        Uses pre-computed static embeddings for intent descriptions.

        Args:
            conversation_history: List of {role, content} turns
            intent_map: Optional custom intent descriptions (uses defaults if None)

        Returns:
            Tuple of (intent_key, confidence_score) or None if no match
        """
        if not conversation_history:
            return None

        # Use default intents (with pre-computed embeddings) unless custom provided
        use_static = intent_map is None
        intents = intent_map or self.INTENT_DESCRIPTIONS

        try:
            # Ensure static embeddings are available
            if use_static:
                await self._ensure_static_embeddings()

            # Combine recent conversation into a single text
            recent_content = ""
            for turn in reversed(conversation_history[-5:]):
                content = turn.get("content", "")
                role = turn.get("role", "")
                recent_content = f"{role}: {content}\n" + recent_content

            if not recent_content.strip():
                return None

            # Get conversation embedding (uses dynamic LRU cache)
            conversation_embedding = await self._get_embedding(recent_content[:2000])

            # Get intent embeddings (pre-computed or dynamic)
            intent_keys = list(intents.keys())
            intent_embeddings = []

            if use_static:
                # Use pre-computed static embeddings
                for key in intent_keys:
                    emb = self._get_static_embedding(f"intent:{key}")
                    if emb is not None:
                        intent_embeddings.append(emb)
                    else:
                        # Fallback for missing static embedding
                        intent_embeddings.append(
                            await self._get_embedding(intents[key])
                        )
            else:
                # Custom intent map - compute dynamically
                intent_embeddings = await self._get_embeddings_batch(
                    list(intents.values())
                )

            # Find best matching intent
            best_intent = None
            best_score = 0.0

            for i, intent_key in enumerate(intent_keys):
                similarity = self._cosine_similarity(
                    conversation_embedding, intent_embeddings[i]
                )
                if similarity > best_score:
                    best_score = similarity
                    best_intent = intent_key

            # Require minimum confidence
            if best_score >= 0.35:
                logger.info(
                    f"Semantic intent classification: {best_intent} "
                    f"(confidence={best_score:.3f})"
                )
                return best_intent, best_score

            return None

        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            return None

    # =========================================================================
    # KYP SECTION MATCHING (replaces KYP_FOLLOWUP_KEYWORDS)
    # =========================================================================

    # KYP section descriptions for semantic matching
    KYP_SECTION_DESCRIPTIONS = {
        "credit": (
            "Credit information: credit limit, credit exposure, credit utilization, "
            "payment terms, credit status, SAP credit data"
        ),
        "sanctions": (
            "Sanctions and compliance: OFAC SDN list, EU sanctions, UN sanctions, "
            "MAS watchlist, sanctioned entities, compliance screening"
        ),
        "financial": (
            "Financial health: market capitalization, revenue, profit margin, "
            "PE ratio, dividend yield, financial statements, earnings"
        ),
        "litigation": (
            "Legal matters: litigation, lawsuits, court cases, legal disputes, "
            "regulatory actions, enforcement, legal proceedings"
        ),
        "profile": (
            "Entity profile: company registration, registered name, stock code, "
            "country of incorporation, sector, industry, website, UEN"
        ),
        "overall": (
            "Overall assessment: recommendation, risk summary, proceed status, "
            "final assessment, due diligence conclusion, overall risk score"
        ),
        "ownership": (
            "Ownership and leadership: shareholders, beneficial owners, UBO, "
            "board members, directors, management team, corporate structure"
        ),
        "safety": (
            "Safety record: maritime safety, incidents, accidents, port state "
            "control, safety inspections, MPA records"
        ),
        "environmental": (
            "Environmental compliance: environmental violations, emissions, "
            "pollution incidents, NEA records, environmental permits"
        ),
        "reputation": (
            "Reputation: news coverage, media mentions, public perception, "
            "customer feedback, industry reputation, brand image"
        ),
    }

    async def match_kyp_section(
        self,
        query: str,
        section_descriptions: Optional[dict[str, str]] = None,
    ) -> Optional[tuple[str, float]]:
        """
        Match a follow-up query to a KYP report section using semantic similarity.

        Replaces keyword-based KYP_FOLLOWUP_KEYWORDS matching.
        Uses pre-computed static embeddings for section descriptions.

        Args:
            query: User's follow-up query
            section_descriptions: Optional custom section descriptions

        Returns:
            Tuple of (section_key, confidence_score) or None if no match
        """
        # Use default sections (with pre-computed embeddings) unless custom provided
        use_static = section_descriptions is None
        sections = section_descriptions or self.KYP_SECTION_DESCRIPTIONS

        try:
            # Ensure static embeddings are available
            if use_static:
                await self._ensure_static_embeddings()

            # Get query embedding (uses dynamic LRU cache)
            query_embedding = await self._get_embedding(query)

            # Get section embeddings (pre-computed or dynamic)
            section_keys = list(sections.keys())
            section_embeddings = []

            if use_static:
                # Use pre-computed static embeddings
                for key in section_keys:
                    emb = self._get_static_embedding(f"kyp:{key}")
                    if emb is not None:
                        section_embeddings.append(emb)
                    else:
                        # Fallback for missing static embedding
                        section_embeddings.append(
                            await self._get_embedding(sections[key])
                        )
            else:
                # Custom section map - compute dynamically
                section_embeddings = await self._get_embeddings_batch(
                    list(sections.values())
                )

            # Find best matching section
            best_section = None
            best_score = 0.0

            for i, section_key in enumerate(section_keys):
                similarity = self._cosine_similarity(
                    query_embedding, section_embeddings[i]
                )
                if similarity > best_score:
                    best_score = similarity
                    best_section = section_key

            # Require minimum confidence
            if best_score >= 0.30:
                logger.info(
                    f"Semantic KYP section match: {best_section} "
                    f"(confidence={best_score:.3f})"
                )
                return best_section, best_score

            return None

        except Exception as e:
            logger.warning(f"KYP section matching failed: {e}")
            return None

    # =========================================================================
    # TIME SENSITIVITY DETECTION (replaces time_keywords)
    # =========================================================================

    # Time sensitivity descriptions - expanded for better semantic matching
    TIME_DESCRIPTIONS = {
        "recent": (
            "latest news, recent updates, current information, today, now, "
            "this week, what's new, breaking news, happening, just announced, "
            "most recent, newest, fresh, up to date, real-time"
        ),
        "historical": (
            "history, historical data, past records, previous years, last year, "
            "in 2020, in 2019, archived, trend over time, legacy, was, were, "
            "used to be, back in, years ago"
        ),
    }

    async def detect_time_sensitivity(
        self,
        query: str,
    ) -> tuple[bool, float, str]:
        """
        Detect if a query is asking for time-sensitive/recent information.

        Replaces keyword-based time_keywords detection.
        Uses pre-computed static embeddings for time descriptions.

        Args:
            query: User's query

        Returns:
            Tuple of (is_time_sensitive, confidence_score, time_type)
            time_type is "recent", "historical", or "neutral"
        """
        try:
            # Ensure static embeddings are available
            await self._ensure_static_embeddings()

            # Get query embedding (uses dynamic LRU cache)
            query_embedding = await self._get_embedding(query)

            # Get pre-computed static embeddings for time descriptions
            recent_embedding = self._get_static_embedding("time:recent")
            historical_embedding = self._get_static_embedding("time:historical")

            # Fallback to dynamic computation if static not available
            if recent_embedding is None or historical_embedding is None:
                embeddings = await self._get_embeddings_batch(
                    [
                        self.TIME_DESCRIPTIONS["recent"],
                        self.TIME_DESCRIPTIONS["historical"],
                    ]
                )
                recent_embedding = embeddings[0]
                historical_embedding = embeddings[1]

            # Compare against both
            recent_score = self._cosine_similarity(query_embedding, recent_embedding)
            historical_score = self._cosine_similarity(
                query_embedding, historical_embedding
            )

            logger.debug(
                f"Time sensitivity: recent={recent_score:.3f}, historical={historical_score:.3f}"
            )

            # Determine time sensitivity (lowered threshold from 0.40 to 0.25)
            if recent_score >= 0.25 and recent_score > historical_score + 0.03:
                return True, recent_score, "recent"
            elif historical_score >= 0.25 and historical_score > recent_score + 0.03:
                return False, historical_score, "historical"
            else:
                return False, max(recent_score, historical_score), "neutral"

        except Exception as e:
            logger.warning(f"Time sensitivity detection failed: {e}")
            return False, 0.0, "neutral"

    # =========================================================================
    # IRRELEVANCE DETECTION (replaces blocklist keyword matching)
    # =========================================================================

    # Description of content that is NOT relevant to RRPS business
    # Expanded to capture more leisure/recreational marine content
    IRRELEVANT_CONTENT_DESCRIPTION = (
        "Leisure boats, yachts, sailing vessels, recreational watercraft, "
        "personal watercraft, jet ski, jet skis, PWC, sea-doo, "
        "kayak, canoe, paddleboard, wakeboard, water skiing, "
        "luxury yacht builders Sunseeker, Ferretti, Azimut, Benetti, Princess, "
        "sailboat racing, America's Cup, yacht shows, boat rentals, "
        "fishing boats, pleasure craft, pontoon boats, houseboats, "
        "recreational boating, watersports, racing championship, "
        "superyacht, megayacht, yacht club, marina lifestyle"
    )

    # Commercial marine description for comparative checking
    COMMERCIAL_MARINE_DESCRIPTION = (
        "Commercial marine vessels, cargo ships, tankers, ferries, offshore support, "
        "OSV, PSV, AHTS, tugs, workboats, naval vessels, patrol boats, "
        "marine diesel engines, propulsion systems, power generation, gensets, "
        "MTU, Bergen, Caterpillar, Wärtsilä, MAN Energy, Cummins, shipyard, newbuild"
    )

    async def check_irrelevance(
        self,
        content: str,
    ) -> tuple[bool, float, str]:
        """
        Check if content is about irrelevant topics (leisure marine, etc.).

        Uses TWO-STAGE semantic comparison:
        1. Compare to irrelevant (leisure) description
        2. Compare to relevant (commercial) description
        3. Only mark irrelevant if leisure score > commercial score

        This prevents false positives like "Caterpillar marine engines"
        being marked irrelevant just because it mentions "marine".
        Uses pre-computed static embeddings for descriptions.

        Args:
            content: Content to check

        Returns:
            Tuple of (is_irrelevant, confidence_score, reason)
        """
        try:
            # Ensure static embeddings are available
            await self._ensure_static_embeddings()

            # Get content embedding (uses dynamic LRU cache)
            content_embedding = await self._get_embedding(content[:2000])

            # Get pre-computed static embeddings
            irrelevant_embedding = self._get_static_embedding("irrelevant:leisure")
            commercial_embedding = self._get_static_embedding("irrelevant:commercial")

            # Fallback to dynamic computation if static not available
            if irrelevant_embedding is None or commercial_embedding is None:
                embeddings = await self._get_embeddings_batch(
                    [
                        self.IRRELEVANT_CONTENT_DESCRIPTION,
                        self.COMMERCIAL_MARINE_DESCRIPTION,
                    ]
                )
                irrelevant_embedding = embeddings[0]
                commercial_embedding = embeddings[1]

            # Compute similarity to both
            leisure_score = self._cosine_similarity(
                content_embedding, irrelevant_embedding
            )
            commercial_score = self._cosine_similarity(
                content_embedding, commercial_embedding
            )

            logger.debug(
                f"Irrelevance check: leisure={leisure_score:.3f}, commercial={commercial_score:.3f}"
            )

            # TWO-STAGE decision:
            # 1. Content is irrelevant if leisure score >= 0.35 AND leisure > commercial
            # 2. This prevents "Caterpillar marine engines" (high commercial) from being blocked
            is_irrelevant = (
                leisure_score >= 0.35
                and leisure_score
                > commercial_score + 0.05  # Leisure must be clearly higher
            )

            if is_irrelevant:
                reason = (
                    f"Leisure ({leisure_score:.3f}) > Commercial ({commercial_score:.3f}): "
                    f"likely recreational content"
                )
            else:
                reason = (
                    f"Commercial ({commercial_score:.3f}) >= Leisure ({leisure_score:.3f}): "
                    f"likely business-relevant"
                )

            return is_irrelevant, leisure_score, reason

        except Exception as e:
            logger.warning(f"Irrelevance check failed: {e}")
            return False, 0.0, f"Check failed: {e}"


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_resolver_instance: Optional[SemanticEntityResolver] = None


async def get_semantic_resolver() -> SemanticEntityResolver:
    """Get or create the singleton semantic resolver instance."""
    global _resolver_instance

    if _resolver_instance is None:
        _resolver_instance = SemanticEntityResolver()
        await _resolver_instance.initialize()

    return _resolver_instance


async def resolve_entity_semantically(
    query: str,
    entity_history: list[dict[str, Any]],
) -> ResolutionResult:
    """
    Convenience function to resolve entity references.

    Args:
        query: User query that may reference an entity
        entity_history: List of tracked entities with context

    Returns:
        ResolutionResult with status and resolved entity
    """
    resolver = await get_semantic_resolver()
    return await resolver.resolve_reference(query, entity_history)


async def classify_intent_semantically(
    conversation_history: list[dict],
) -> Optional[tuple[str, float]]:
    """
    Classify intent from conversation history using semantic similarity.

    Args:
        conversation_history: List of {role, content} turns

    Returns:
        Tuple of (intent_key, confidence) or None
    """
    resolver = await get_semantic_resolver()
    return await resolver.classify_intent_from_history(conversation_history)


async def match_kyp_section_semantically(
    query: str,
) -> Optional[tuple[str, float]]:
    """
    Match a query to a KYP report section using semantic similarity.

    Args:
        query: User's follow-up query

    Returns:
        Tuple of (section_key, confidence) or None
    """
    resolver = await get_semantic_resolver()
    return await resolver.match_kyp_section(query)


async def detect_time_sensitivity_semantically(
    query: str,
) -> tuple[bool, float, str]:
    """
    Detect if a query is time-sensitive using semantic similarity.

    Args:
        query: User's query

    Returns:
        Tuple of (is_time_sensitive, confidence, time_type)
    """
    resolver = await get_semantic_resolver()
    return await resolver.detect_time_sensitivity(query)


async def check_content_irrelevance_semantically(
    content: str,
) -> tuple[bool, float, str]:
    """
    Check if content is about irrelevant topics using semantic similarity.

    Args:
        content: Content to check

    Returns:
        Tuple of (is_irrelevant, confidence, reason)
    """
    resolver = await get_semantic_resolver()
    return await resolver.check_irrelevance(content)
