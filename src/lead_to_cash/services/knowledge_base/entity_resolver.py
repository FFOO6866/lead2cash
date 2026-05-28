"""
Marine Engine Knowledge Base - Entity Resolver

Hybrid entity resolution using multiple matching strategies:
1. Exact match on normalized text
2. Alias match from KB
3. Fuzzy match using rapidfuzz (>85% threshold)
4. Semantic match using pgvector embeddings (>0.7 cosine similarity)

Production features:
- Input validation and proper exception handling
- TTLCache with configurable TTL and size (via cachetools)
- Batch resolution with optimized queries
"""

import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    from cachetools import TTLCache

    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False
    TTLCache = None

from lead_to_cash.services.knowledge_base.cache_events import (
    CacheEvent,
    CacheEventSubscriber,
    CacheEventType,
    get_cache_event_subscriber,
)
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.embedding_service import (
    KBEmbeddingService,
    get_kb_embedding_service,
)
from lead_to_cash.services.knowledge_base.exceptions import (
    KBValidationError,
)
from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics
from lead_to_cash.services.knowledge_base.models import (
    ExtractedEntity,
    ManufacturerTier,
    PowerClass,
    ResolvedEntity,
    RPMClass,
)
from lead_to_cash.services.knowledge_base.tracing import trace_operation
from lead_to_cash.services.knowledge_base.validation import (
    validate_entity_type,
    validate_list,
    validate_text,
)
from lead_to_cash.utils.logging import get_logger

# Use structured logger with correlation ID support
logger = get_logger(__name__)


@dataclass
class MatchResult:
    """Result of entity matching."""

    entity_type: str
    entity_id: str
    entity_name: str
    match_type: str  # "exact", "alias", "fuzzy", "semantic"
    confidence: float
    metadata: Optional[dict] = None


class EntityResolver:
    """
    Resolves extracted entities against the Knowledge Base.

    Uses hybrid matching strategy:
    1. Exact match - Fast, high confidence
    2. Alias match - Lookup in aliases table
    3. Fuzzy match - rapidfuzz with 85% threshold
    4. Semantic match - pgvector with 0.7 cosine threshold

    Usage:
        resolver = EntityResolver()
        await resolver.initialize()

        # Resolve single entity
        result = await resolver.resolve("Wartsila", entity_type="manufacturer")

        # Resolve extracted entity
        extracted = ExtractedEntity(text="W31", entity_type="engine_series", confidence=0.8)
        resolved = await resolver.resolve_extracted(extracted)

        # Batch resolve
        results = await resolver.resolve_batch(["Wartsila", "MAN", "Cat"])
    """

    # Thresholds
    FUZZY_THRESHOLD = 0.85  # rapidfuzz similarity threshold
    SEMANTIC_THRESHOLD = 0.70  # pgvector cosine similarity threshold

    # Cache configuration
    CACHE_MAX_SIZE = 1000  # Maximum items in cache
    CACHE_TTL_SECONDS = 3600  # Cache TTL (1 hour)

    def __init__(
        self,
        db: Optional[KnowledgeBaseDatabase] = None,
        embedding_service: Optional[KBEmbeddingService] = None,
        cache_max_size: int = CACHE_MAX_SIZE,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        """
        Initialize entity resolver.

        Args:
            db: Database instance. Defaults to singleton.
            embedding_service: Embedding service. Defaults to singleton.
            cache_max_size: Maximum items in LRU cache.
            cache_ttl_seconds: Cache TTL in seconds.
        """
        self._db: Optional[KnowledgeBaseDatabase] = db
        self._embedding_service: Optional[KBEmbeddingService] = embedding_service
        self._initialized = False

        # Cache configuration
        self._cache_max_size = cache_max_size
        self._cache_ttl_seconds = cache_ttl_seconds

        # TTLCache for common lookups (production-grade caching)
        # Uses cachetools.TTLCache if available, falls back to manual dict implementation
        if CACHETOOLS_AVAILABLE:
            self._manufacturer_cache: Any = TTLCache(
                maxsize=cache_max_size, ttl=cache_ttl_seconds
            )
            self._model_cache: Any = TTLCache(
                maxsize=cache_max_size, ttl=cache_ttl_seconds
            )
            self._use_cachetools = True
            logger.debug("Using cachetools.TTLCache for entity caching")
        else:
            # Fallback: manual dict with timestamps
            self._manufacturer_cache = {}
            self._model_cache = {}
            self._use_cachetools = False
            logger.warning(
                "cachetools not available, using manual cache with TTL checks"
            )
        self._cache_hits = 0
        self._cache_misses = 0

        # Cache event subscriber for distributed invalidation
        self._cache_subscriber: Optional[CacheEventSubscriber] = None

    @property
    def db(self) -> KnowledgeBaseDatabase:
        """Get the database instance, raising if not initialized."""
        if self._db is None:
            raise KBValidationError(
                message="Database not initialized. Call initialize() first.",
                field="db",
            )
        return self._db

    @property
    def embedding_svc(self) -> KBEmbeddingService:
        """Get the embedding service, raising if not initialized."""
        if self._embedding_service is None:
            raise KBValidationError(
                message="Embedding service not initialized. Call initialize() first.",
                field="embedding_service",
            )
        return self._embedding_service

    async def initialize(self) -> None:
        """Initialize database and embedding service."""
        if self._initialized:
            return

        if self._db is None:
            self._db = get_knowledge_base_db()
            await self._db.initialize()

        if self._embedding_service is None:
            self._embedding_service = get_kb_embedding_service()
            await self._embedding_service.initialize()

        # Pre-load manufacturers into cache
        await self._load_manufacturer_cache()

        # Subscribe to cache invalidation events (if Redis available)
        self._cache_subscriber = get_cache_event_subscriber()
        await self._cache_subscriber.initialize()
        await self._cache_subscriber.subscribe(self._handle_cache_event)

        self._initialized = True
        logger.info("Entity resolver initialized")

    def _handle_cache_event(self, event: CacheEvent) -> None:
        """
        Handle cache invalidation events from Redis pub/sub.

        This method is called when another instance publishes a cache
        invalidation event. It clears the relevant cache entries.

        Args:
            event: Cache invalidation event
        """
        event_value = event.event_type.value

        # Clear all caches
        if event.event_type == CacheEventType.CACHE_CLEAR_ALL:
            self.clear_cache()
            logger.info("Cache cleared by CACHE_CLEAR_ALL event")
            return

        # Clear manufacturer caches
        if event.event_type == CacheEventType.CACHE_CLEAR_MANUFACTURERS:
            self._manufacturer_cache.clear()
            logger.info("Manufacturer cache cleared by event")
            return

        # Clear model caches
        if event.event_type == CacheEventType.CACHE_CLEAR_MODELS:
            self._model_cache.clear()
            logger.info("Model cache cleared by event")
            return

        # Handle individual entity events
        if event_value.startswith("manufacturer"):
            if event.entity_id:
                # Try to remove specific entry by ID
                if self._use_cachetools:
                    self._manufacturer_cache.pop(event.entity_id, None)
                else:
                    self._manufacturer_cache.pop(event.entity_id, None)
            else:
                # No specific ID - clear all manufacturer cache
                self._manufacturer_cache.clear()
            logger.debug(f"Manufacturer cache invalidated by {event_value}")

        elif event_value.startswith("model") or event_value.startswith("series"):
            if event.entity_id:
                if self._use_cachetools:
                    self._model_cache.pop(event.entity_id, None)
                else:
                    self._model_cache.pop(event.entity_id, None)
            else:
                self._model_cache.clear()
            logger.debug(f"Model cache invalidated by {event_value}")

        elif event_value.startswith("alias") or event_value.startswith("embedding"):
            # Alias changes may affect resolution results
            # For now, we don't cache alias lookups directly, but this
            # hook is here for future extensibility
            logger.debug(f"Alias/embedding event received: {event_value}")

    async def _load_manufacturer_cache(self) -> None:
        """Load all manufacturers into cache for fast lookup."""
        manufacturers = await self.db.list_manufacturers(is_active=True, limit=500)

        for mfr in manufacturers:
            self._put_in_cache(self._manufacturer_cache, mfr.id, mfr)
            self._put_in_cache(self._manufacturer_cache, mfr.name.lower().strip(), mfr)

        logger.info(f"Loaded {len(manufacturers)} manufacturers into cache")

    def _get_from_cache(self, cache: Any, key: str) -> Optional[Any]:
        """
        Get item from cache.

        Handles both cachetools.TTLCache (automatic TTL) and manual dict with timestamps.

        Args:
            cache: Cache (TTLCache or dict)
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if self._use_cachetools:
            # cachetools.TTLCache handles TTL automatically
            value = cache.get(key)
            if value is not None:
                self._cache_hits += 1
                return value
            self._cache_misses += 1
            return None
        else:
            # Manual fallback with timestamp checking
            if key not in cache:
                self._cache_misses += 1
                return None

            value, timestamp = cache[key]
            if time.time() - timestamp > self._cache_ttl_seconds:
                # Expired - remove from cache
                del cache[key]
                self._cache_misses += 1
                return None

            self._cache_hits += 1
            return value

    def _put_in_cache(self, cache: Any, key: str, value: Any) -> None:
        """
        Put item in cache.

        Handles both cachetools.TTLCache (automatic eviction) and manual dict.

        Args:
            cache: Cache (TTLCache or dict)
            key: Cache key
            value: Value to cache
        """
        if self._use_cachetools:
            # cachetools.TTLCache handles eviction automatically
            cache[key] = value
        else:
            # Manual fallback with eviction
            if len(cache) >= self._cache_max_size:
                self._evict_oldest(cache, count=self._cache_max_size // 10)
            cache[key] = (value, time.time())

    def _evict_oldest(self, cache: dict, count: int = 100) -> None:
        """
        Evict oldest entries from cache (manual fallback only).

        Args:
            cache: Cache dictionary (manual implementation)
            count: Number of entries to evict
        """
        if self._use_cachetools:
            # cachetools handles eviction automatically
            return

        if not cache:
            return

        # Sort by timestamp and remove oldest
        sorted_items = sorted(cache.items(), key=lambda x: x[1][1])
        for key, _ in sorted_items[:count]:
            del cache[key]

        logger.debug(f"Evicted {count} items from cache")

    def get_cache_stats(self) -> dict:
        """Get cache statistics and update metrics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0

        # Update Prometheus metrics with current hit rate
        metrics = get_kb_metrics()
        metrics.update_cache_hit_ratio("manufacturer", hit_rate)
        metrics.update_cache_hit_ratio("model", hit_rate)
        metrics.record_cache_size("manufacturer", len(self._manufacturer_cache))
        metrics.record_cache_size("model", len(self._model_cache))

        return {
            "manufacturer_cache_size": len(self._manufacturer_cache),
            "model_cache_size": len(self._model_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": round(hit_rate, 3),
            "max_size": self._cache_max_size,
            "ttl_seconds": self._cache_ttl_seconds,
            "using_cachetools": self._use_cachetools,
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._manufacturer_cache.clear()
        self._model_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Entity resolver caches cleared")

    @trace_operation("resolve_entity", lambda text, **_: {"query": text[:50]})
    async def resolve(
        self,
        text: str,
        entity_type: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """
        Resolve a text string to a KB entity.

        Args:
            text: Text to resolve
            entity_type: Optional type hint ("manufacturer", "engine_model", etc.)

        Returns:
            MatchResult if found, None otherwise

        Raises:
            KBValidationError: If input is invalid
        """
        # Input validation
        text = validate_text(text, "text", min_length=1, max_length=500)

        # Validate entity_type if provided, but allow unknown types (return None)
        # This is lenient to support integration with external extraction systems
        if entity_type is not None:
            try:
                entity_type = validate_entity_type(entity_type, allow_none=True)
            except KBValidationError:
                # Unknown entity type - treat as None (search all types)
                logger.debug(
                    f"Unknown entity_type '{entity_type}', searching all types"
                )
                entity_type = None

        if not self._initialized:
            await self.initialize()

        normalized = text.lower().strip()
        metrics = get_kb_metrics()

        # 1. Try exact match
        result = await self._exact_match(normalized, entity_type)
        if result:
            metrics.record_entity_resolved(result.match_type)
            return result

        # 2. Try alias match
        result = await self._alias_match(normalized, entity_type)
        if result:
            metrics.record_entity_resolved(result.match_type)
            return result

        # 3. Try fuzzy match
        result = await self._fuzzy_match(text, entity_type)
        if result:
            metrics.record_entity_resolved(result.match_type)
            return result

        # 4. Try semantic match
        result = await self._semantic_match(text, entity_type)
        if result:
            metrics.record_entity_resolved(result.match_type)
            return result

        logger.debug(f"Could not resolve entity: {text}")
        metrics.record_entity_resolved("unresolved")
        return None

    async def _exact_match(
        self, normalized_text: str, entity_type: Optional[str] = None
    ) -> Optional[MatchResult]:
        """Try exact match on normalized text using TTL cache."""
        # Check manufacturer cache first (with TTL)
        if entity_type in (None, "manufacturer"):
            mfr = self._get_from_cache(self._manufacturer_cache, normalized_text)
            if mfr:
                return MatchResult(
                    entity_type="manufacturer",
                    entity_id=mfr.id,
                    entity_name=mfr.name,
                    match_type="exact",
                    confidence=1.0,
                    metadata={"tier": mfr.tier, "country": mfr.country},
                )

        # Check database for exact manufacturer name
        if entity_type in (None, "manufacturer"):
            mfr = await self.db.get_manufacturer_by_name(normalized_text)
            if mfr:
                # Cache the result
                self._put_in_cache(self._manufacturer_cache, normalized_text, mfr)
                self._put_in_cache(self._manufacturer_cache, mfr.id, mfr)
                return MatchResult(
                    entity_type="manufacturer",
                    entity_id=mfr.id,
                    entity_name=mfr.name,
                    match_type="exact",
                    confidence=1.0,
                    metadata={"tier": mfr.tier, "country": mfr.country},
                )

        return None

    async def _alias_match(
        self, normalized_text: str, entity_type: Optional[str] = None
    ) -> Optional[MatchResult]:
        """
        Try alias match in KB.

        Uses cache-first approach to avoid N+1 queries when fetching entity details.
        """
        alias = await self.db.get_alias_by_normalized_text(normalized_text, entity_type)

        if alias:
            # Get entity details - use cache first to avoid N+1 queries
            entity_name = alias.alias_text
            metadata = {}

            if alias.entity_type == "manufacturer":
                # Try cache first (avoids DB query)
                mfr = self._get_from_cache(self._manufacturer_cache, alias.entity_id)
                if not mfr:
                    # Cache miss - fetch from DB and cache
                    mfr = await self.db.get_manufacturer(alias.entity_id)
                    if mfr:
                        self._put_in_cache(self._manufacturer_cache, mfr.id, mfr)
                        self._put_in_cache(
                            self._manufacturer_cache, mfr.name.lower().strip(), mfr
                        )
                if mfr:
                    entity_name = mfr.name
                    metadata = {"tier": mfr.tier, "country": mfr.country}
            elif alias.entity_type == "engine_model":
                # Try cache first (avoids DB query)
                model = self._get_from_cache(self._model_cache, alias.entity_id)
                if not model:
                    # Cache miss - fetch from DB and cache
                    model = await self.db.get_engine_model(alias.entity_id)
                    if model:
                        self._put_in_cache(self._model_cache, model.id, model)
                        self._put_in_cache(
                            self._model_cache, model.model_name.lower().strip(), model
                        )
                if model:
                    entity_name = model.model_name
                    metadata = {
                        "rpm_min": model.rpm_min,
                        "rpm_max": model.rpm_max,
                        "power_min_kw": model.power_min_kw,
                        "power_max_kw": model.power_max_kw,
                    }

            return MatchResult(
                entity_type=alias.entity_type,
                entity_id=alias.entity_id,
                entity_name=entity_name,
                match_type="alias",
                confidence=alias.confidence * 0.95,  # Slight penalty for alias match
                metadata=metadata,
            )

        return None

    async def _fuzzy_match(
        self, text: str, entity_type: Optional[str] = None
    ) -> Optional[MatchResult]:
        """
        Try fuzzy match using rapidfuzz.

        Supports matching against:
        - Manufacturers (entity_type=None or "manufacturer")
        - Engine models (entity_type=None or "engine_model")
        - Engine series (entity_type=None or "engine_series")
        """
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            logger.warning("rapidfuzz not installed, skipping fuzzy match")
            return None

        # Get candidates based on entity type
        candidates = []

        # Load manufacturers for fuzzy matching
        if entity_type in (None, "manufacturer"):
            manufacturers = await self.db.list_manufacturers(is_active=True)
            candidates.extend(
                [
                    (
                        "manufacturer",
                        mfr.id,
                        mfr.name,
                        {"tier": mfr.tier, "country": mfr.country},
                    )
                    for mfr in manufacturers
                ]
            )

        # Load engine models for fuzzy matching
        if entity_type in (None, "engine_model"):
            models = await self.db.list_engine_models(is_current=True)
            candidates.extend(
                [
                    (
                        "engine_model",
                        model.id,
                        model.model_name,
                        {
                            "rpm_min": model.rpm_min,
                            "rpm_max": model.rpm_max,
                            "power_min_kw": model.power_min_kw,
                            "power_max_kw": model.power_max_kw,
                            "series_id": model.series_id,
                        },
                    )
                    for model in models
                ]
            )

        # Load engine series for fuzzy matching
        if entity_type in (None, "engine_series"):
            series_list = await self.db.list_engine_series(is_current=True)
            candidates.extend(
                [
                    (
                        "engine_series",
                        series.id,
                        series.series_name,
                        {
                            "manufacturer_id": series.manufacturer_id,
                            "brand": series.brand,
                        },
                    )
                    for series in series_list
                ]
            )

        if not candidates:
            return None

        # Find best match using weighted ratio (handles partial matches well)
        names = [c[2] for c in candidates]
        result = process.extractOne(
            text,
            names,
            scorer=fuzz.WRatio,
            score_cutoff=self.FUZZY_THRESHOLD * 100,
        )

        if result:
            matched_name, score, idx = result
            matched_entity_type, entity_id, entity_name, metadata = candidates[idx]

            return MatchResult(
                entity_type=matched_entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                match_type="fuzzy",
                confidence=score / 100.0,
                metadata=metadata,
            )

        return None

    async def _semantic_match(
        self, text: str, entity_type: Optional[str] = None
    ) -> Optional[MatchResult]:
        """
        Try semantic match using pgvector embeddings.

        Uses cache-first approach to avoid N+1 queries:
        1. Check manufacturer cache first
        2. Check model cache first
        3. Fall back to DB only on cache miss
        """
        # Track vector search timing for observability
        start_time = time.monotonic()

        results = await self.embedding_svc.search_entities(
            query=text,
            entity_type=entity_type,
            top_k=1,
            min_similarity=self.SEMANTIC_THRESHOLD,
        )

        # Record vector search duration
        duration = time.monotonic() - start_time
        metrics = get_kb_metrics()
        metrics.record_vector_search(duration, entity_type or "all", "hnsw")

        if results:
            top = results[0]

            # Record similarity score distribution
            metrics.record_similarity_score(
                top["similarity"], top["entity_type"], "semantic"
            )

            # Get entity details - use cache first to avoid N+1 queries
            entity_name = top["alias_text"]
            metadata = {}

            if top["entity_type"] == "manufacturer":
                # Try cache first (avoids DB query)
                mfr = self._get_from_cache(self._manufacturer_cache, top["entity_id"])
                if not mfr:
                    # Cache miss - fetch from DB and cache
                    mfr = await self.db.get_manufacturer(top["entity_id"])
                    if mfr:
                        self._put_in_cache(self._manufacturer_cache, mfr.id, mfr)
                        self._put_in_cache(
                            self._manufacturer_cache, mfr.name.lower().strip(), mfr
                        )
                if mfr:
                    entity_name = mfr.name
                    metadata = {"tier": mfr.tier, "country": mfr.country}
            elif top["entity_type"] == "engine_model":
                # Try cache first (avoids DB query)
                model = self._get_from_cache(self._model_cache, top["entity_id"])
                if not model:
                    # Cache miss - fetch from DB and cache
                    model = await self.db.get_engine_model(top["entity_id"])
                    if model:
                        self._put_in_cache(self._model_cache, model.id, model)
                        self._put_in_cache(
                            self._model_cache, model.model_name.lower().strip(), model
                        )
                if model:
                    entity_name = model.model_name
                    metadata = {
                        "rpm_min": model.rpm_min,
                        "rpm_max": model.rpm_max,
                        "power_min_kw": model.power_min_kw,
                        "power_max_kw": model.power_max_kw,
                    }

            return MatchResult(
                entity_type=top["entity_type"],
                entity_id=top["entity_id"],
                entity_name=entity_name,
                match_type="semantic",
                confidence=top["similarity"] * top["confidence"],
                metadata=metadata,
            )

        return None

    async def resolve_extracted(
        self, extracted: ExtractedEntity
    ) -> Optional[ResolvedEntity]:
        """
        Resolve an ExtractedEntity to a ResolvedEntity.

        Args:
            extracted: Entity extracted from article

        Returns:
            ResolvedEntity if found, None otherwise
        """
        match = await self.resolve(extracted.text, extracted.entity_type)

        if not match:
            return None

        # Build resolved entity
        resolved = ResolvedEntity(
            extracted=extracted,
            entity_type=match.entity_type,
            entity_id=match.entity_id,
            entity_name=match.entity_name,
            match_type=match.match_type,
            match_confidence=match.confidence * extracted.confidence,
        )

        # Add classifications for engine models
        if match.entity_type == "engine_model" and match.metadata:
            rpm_max = match.metadata.get("rpm_max")
            power_max = match.metadata.get("power_max_kw")

            if rpm_max:
                resolved.rpm_class = RPMClass.from_rpm(rpm_max)
            if power_max:
                resolved.power_class = PowerClass.from_kw(power_max)

        # Add manufacturer tier
        if match.entity_type == "manufacturer" and match.metadata:
            tier = match.metadata.get("tier")
            if tier:
                # Handle both int (1, 2, 3) and string ("tier_1", "1") formats
                if isinstance(tier, int):
                    resolved.manufacturer_tier = ManufacturerTier(tier)
                elif isinstance(tier, str):
                    # Extract number from string like "tier_1" or just "1"
                    tier_num = int(tier.replace("tier_", "").strip())
                    resolved.manufacturer_tier = ManufacturerTier(tier_num)

        return resolved

    @trace_operation(
        "resolve_batch", lambda texts, **_: {"batch_size": len(texts) if texts else 0}
    )
    async def resolve_batch(
        self,
        texts: list[str],
        entity_type: Optional[str] = None,
    ) -> list[Optional[MatchResult]]:
        """
        Resolve multiple texts in batch.

        Args:
            texts: List of texts to resolve
            entity_type: Optional type hint for all texts

        Returns:
            List of MatchResults (None for unresolved)

        Raises:
            KBValidationError: If input is invalid
        """
        # Input validation
        texts = validate_list(texts, "texts", min_length=0, max_length=1000)
        entity_type = validate_entity_type(entity_type, allow_none=True)

        metrics = get_kb_metrics()
        results = []
        for text in texts:
            result = await self.resolve(text, entity_type)
            results.append(result)
            # Record metrics for each resolution
            if result:
                metrics.record_entity_resolved(result.match_type)
            else:
                metrics.record_entity_resolved("unresolved")
        return results


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_resolver: Optional[EntityResolver] = None


def get_entity_resolver() -> EntityResolver:
    """Get singleton entity resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver


async def initialize_entity_resolver() -> EntityResolver:
    """Initialize and return entity resolver instance."""
    resolver = get_entity_resolver()
    await resolver.initialize()
    return resolver
