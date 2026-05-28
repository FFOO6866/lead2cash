"""
Unit Tests for Knowledge Base Entity Resolver

Tests pure functions and cache operations without database.
Integration tests with real PostgreSQL are in test_kb_integration.py.

Focus areas:
- MatchResult dataclass
- Cache operations (TTLCache and manual fallback)
- Cache statistics tracking
- Cache clearing and eviction
- Validation thresholds
"""

import time
from unittest.mock import MagicMock

import pytest

from lead_to_cash.services.knowledge_base.entity_resolver import (
    EntityResolver,
    MatchResult,
)
from lead_to_cash.services.knowledge_base.models import (
    ExtractedEntity,
    ManufacturerTier,
    PowerClass,
    ResolvedEntity,
    RPMClass,
)

# =============================================================================
# MATCH RESULT TESTS
# =============================================================================


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_match_result_creation(self):
        """Test creating a MatchResult with required fields."""
        result = MatchResult(
            entity_type="manufacturer",
            entity_id="mfr-001",
            entity_name="Wärtsilä",
            match_type="exact",
            confidence=1.0,
        )

        assert result.entity_type == "manufacturer"
        assert result.entity_id == "mfr-001"
        assert result.entity_name == "Wärtsilä"
        assert result.match_type == "exact"
        assert result.confidence == 1.0
        assert result.metadata is None

    def test_match_result_with_metadata(self):
        """Test creating a MatchResult with metadata."""
        result = MatchResult(
            entity_type="manufacturer",
            entity_id="mfr-001",
            entity_name="Wärtsilä",
            match_type="exact",
            confidence=1.0,
            metadata={"tier": 1, "country": "Finland"},
        )

        assert result.metadata == {"tier": 1, "country": "Finland"}

    def test_match_result_match_types(self):
        """Test all valid match types."""
        for match_type in ["exact", "alias", "fuzzy", "semantic"]:
            result = MatchResult(
                entity_type="manufacturer",
                entity_id="mfr-001",
                entity_name="Test",
                match_type=match_type,
                confidence=0.9,
            )
            assert result.match_type == match_type


# =============================================================================
# ENTITY RESOLVER INITIALIZATION TESTS
# =============================================================================


class TestEntityResolverInit:
    """Tests for EntityResolver initialization."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        assert EntityResolver.FUZZY_THRESHOLD == 0.85
        assert EntityResolver.SEMANTIC_THRESHOLD == 0.70

    def test_default_cache_config(self):
        """Test default cache configuration."""
        assert EntityResolver.CACHE_MAX_SIZE == 1000
        assert EntityResolver.CACHE_TTL_SECONDS == 3600

    def test_custom_cache_config(self):
        """Test custom cache configuration."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
            cache_max_size=500,
            cache_ttl_seconds=1800,
        )

        assert resolver._cache_max_size == 500
        assert resolver._cache_ttl_seconds == 1800

    def test_initial_cache_stats(self):
        """Test initial cache statistics are zero."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )

        assert resolver._cache_hits == 0
        assert resolver._cache_misses == 0


# =============================================================================
# CACHE OPERATIONS TESTS (WITH CACHETOOLS)
# =============================================================================


class TestCacheOperationsWithCachetools:
    """Tests for cache operations using cachetools.TTLCache."""

    @pytest.fixture
    def resolver_with_cachetools(self):
        """Create resolver with cachetools available."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        # Ensure cachetools is being used
        if not resolver._use_cachetools:
            pytest.skip("cachetools not available")
        return resolver

    def test_put_and_get_from_cache(self, resolver_with_cachetools):
        """Test basic cache put and get operations."""
        resolver = resolver_with_cachetools
        cache = resolver._manufacturer_cache

        # Create a mock manufacturer
        mock_mfr = MagicMock()
        mock_mfr.id = "mfr-001"
        mock_mfr.name = "Wärtsilä"

        # Put in cache
        resolver._put_in_cache(cache, "wartsila", mock_mfr)

        # Get from cache
        result = resolver._get_from_cache(cache, "wartsila")

        assert result is mock_mfr
        assert resolver._cache_hits == 1

    def test_cache_miss(self, resolver_with_cachetools):
        """Test cache miss increments counter."""
        resolver = resolver_with_cachetools
        cache = resolver._manufacturer_cache

        result = resolver._get_from_cache(cache, "nonexistent")

        assert result is None
        assert resolver._cache_misses == 1

    def test_cache_clear(self, resolver_with_cachetools):
        """Test cache clearing."""
        resolver = resolver_with_cachetools

        # Add some items
        mock_mfr = MagicMock()
        resolver._put_in_cache(resolver._manufacturer_cache, "test1", mock_mfr)
        resolver._put_in_cache(resolver._model_cache, "test2", mock_mfr)

        # Clear caches
        resolver.clear_cache()

        assert len(resolver._manufacturer_cache) == 0
        assert len(resolver._model_cache) == 0
        assert resolver._cache_hits == 0
        assert resolver._cache_misses == 0


# =============================================================================
# CACHE OPERATIONS TESTS (MANUAL FALLBACK)
# =============================================================================


class TestCacheOperationsManualFallback:
    """Tests for cache operations using manual dict fallback."""

    @pytest.fixture
    def resolver_manual_cache(self):
        """Create resolver with manual cache (simulating no cachetools)."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        # Force manual cache mode
        resolver._use_cachetools = False
        resolver._manufacturer_cache = {}
        resolver._model_cache = {}
        return resolver

    def test_put_and_get_manual_cache(self, resolver_manual_cache):
        """Test basic cache operations with manual implementation."""
        resolver = resolver_manual_cache
        cache = resolver._manufacturer_cache

        # Create a mock manufacturer
        mock_mfr = MagicMock()
        mock_mfr.id = "mfr-001"
        mock_mfr.name = "Wärtsilä"

        # Put in cache
        resolver._put_in_cache(cache, "wartsila", mock_mfr)

        # Get from cache
        result = resolver._get_from_cache(cache, "wartsila")

        assert result is mock_mfr
        assert resolver._cache_hits == 1

    def test_manual_cache_ttl_expiry(self, resolver_manual_cache):
        """Test TTL expiry in manual cache."""
        resolver = resolver_manual_cache
        resolver._cache_ttl_seconds = 0.1  # 100ms TTL
        cache = resolver._manufacturer_cache

        # Put in cache
        mock_mfr = MagicMock()
        resolver._put_in_cache(cache, "test", mock_mfr)

        # Should be in cache
        result = resolver._get_from_cache(cache, "test")
        assert result is mock_mfr

        # Wait for TTL to expire
        time.sleep(0.15)

        # Should be expired
        result = resolver._get_from_cache(cache, "test")
        assert result is None
        assert resolver._cache_misses == 1

    def test_manual_cache_eviction(self, resolver_manual_cache):
        """Test cache eviction when max size reached."""
        resolver = resolver_manual_cache
        resolver._cache_max_size = 10
        cache = resolver._manufacturer_cache

        # Fill cache beyond max size
        for i in range(15):
            mock_mfr = MagicMock()
            mock_mfr.id = f"mfr-{i}"
            resolver._put_in_cache(cache, f"key-{i}", mock_mfr)

        # Cache should have evicted some items (10% at a time)
        assert len(cache) <= resolver._cache_max_size

    def test_evict_oldest(self, resolver_manual_cache):
        """Test _evict_oldest removes oldest entries."""
        resolver = resolver_manual_cache
        cache = resolver._manufacturer_cache

        # Add items with different timestamps
        for i in range(5):
            mock = MagicMock()
            cache[f"key-{i}"] = (mock, time.time() + i * 0.01)
            time.sleep(0.01)

        # Evict 2 oldest
        resolver._evict_oldest(cache, count=2)

        assert len(cache) == 3
        # Oldest keys should be removed
        assert "key-0" not in cache
        assert "key-1" not in cache


# =============================================================================
# CACHE STATS TESTS
# =============================================================================


class TestCacheStats:
    """Tests for cache statistics tracking."""

    def test_get_cache_stats_structure(self):
        """Test cache stats return structure."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )

        stats = resolver.get_cache_stats()

        assert "manufacturer_cache_size" in stats
        assert "model_cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "hit_rate" in stats
        assert "max_size" in stats
        assert "ttl_seconds" in stats
        assert "using_cachetools" in stats

    def test_hit_rate_calculation(self):
        """Test hit rate is calculated correctly."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        resolver._cache_hits = 80
        resolver._cache_misses = 20

        stats = resolver.get_cache_stats()

        assert stats["hit_rate"] == 0.8  # 80/100

    def test_hit_rate_zero_queries(self):
        """Test hit rate with no queries doesn't divide by zero."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        resolver._cache_hits = 0
        resolver._cache_misses = 0

        stats = resolver.get_cache_stats()

        assert stats["hit_rate"] == 0.0


# =============================================================================
# RESOLVED ENTITY TESTS
# =============================================================================


class TestResolvedEntity:
    """Tests for ResolvedEntity dataclass."""

    def test_resolved_entity_creation(self):
        """Test creating a ResolvedEntity."""
        extracted = ExtractedEntity(
            text="Wärtsilä 31DF",
            entity_type="engine_model",
            confidence=0.9,
        )

        resolved = ResolvedEntity(
            extracted=extracted,
            entity_type="engine_model",
            entity_id="model-001",
            entity_name="Wärtsilä 31DF",
            match_type="exact",
            match_confidence=1.0,
            rpm_class=RPMClass.MEDIUM_SPEED,
            power_class=PowerClass.HIGH,
            manufacturer_tier=ManufacturerTier.TIER_1,
        )

        assert resolved.extracted is extracted
        assert resolved.entity_type == "engine_model"
        assert resolved.entity_id == "model-001"
        assert resolved.entity_name == "Wärtsilä 31DF"
        assert resolved.match_type == "exact"
        assert resolved.match_confidence == 1.0
        assert resolved.rpm_class == RPMClass.MEDIUM_SPEED
        assert resolved.power_class == PowerClass.HIGH
        assert resolved.manufacturer_tier == ManufacturerTier.TIER_1

    def test_resolved_entity_minimal(self):
        """Test ResolvedEntity with minimal fields."""
        extracted = ExtractedEntity(
            text="Test",
            entity_type="manufacturer",
            confidence=0.8,
        )

        resolved = ResolvedEntity(
            extracted=extracted,
            entity_type="manufacturer",
            entity_id="mfr-001",
            entity_name="Test Manufacturer",
            match_type="fuzzy",
            match_confidence=0.87,
        )

        assert resolved.rpm_class is None
        assert resolved.power_class is None
        assert resolved.manufacturer_tier is None


# =============================================================================
# EXTRACTED ENTITY TESTS
# =============================================================================


class TestExtractedEntity:
    """Tests for ExtractedEntity dataclass."""

    def test_extracted_entity_basic(self):
        """Test creating a basic ExtractedEntity."""
        entity = ExtractedEntity(
            text="W31DF",
            entity_type="engine_model",
            confidence=0.85,
        )

        assert entity.text == "W31DF"
        assert entity.entity_type == "engine_model"
        assert entity.confidence == 0.85
        assert entity.context is None
        assert entity.rpm is None
        assert entity.power_kw is None
        assert entity.fuel_type is None

    def test_extracted_entity_with_parsed_values(self):
        """Test ExtractedEntity with parsed technical values."""
        entity = ExtractedEntity(
            text="12-cylinder medium speed diesel",
            entity_type="engine_model",
            confidence=0.7,
            context="The vessel uses 12-cylinder medium speed diesel engines rated at 4000kW",
            rpm=600,
            power_kw=4000.0,
            fuel_type="diesel",
        )

        assert entity.rpm == 600
        assert entity.power_kw == 4000.0
        assert entity.fuel_type == "diesel"
        assert "4000kW" in entity.context


# =============================================================================
# CACHE EVENT HANDLING TESTS
# =============================================================================


class TestCacheEventHandling:
    """Tests for cache event handling."""

    @pytest.fixture
    def resolver_with_cache(self):
        """Create resolver with populated cache."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        # Populate cache
        mock_mfr = MagicMock()
        mock_mfr.id = "mfr-001"
        mock_model = MagicMock()
        mock_model.id = "model-001"

        resolver._put_in_cache(resolver._manufacturer_cache, "mfr-001", mock_mfr)
        resolver._put_in_cache(resolver._model_cache, "model-001", mock_model)

        return resolver

    def test_clear_all_cache_event(self, resolver_with_cache):
        """Test CACHE_CLEAR_ALL event clears all caches."""
        from lead_to_cash.services.knowledge_base.cache_events import (
            CacheEvent,
            CacheEventType,
        )

        resolver = resolver_with_cache

        # Verify cache has items
        assert len(resolver._manufacturer_cache) > 0

        # Handle clear all event
        event = CacheEvent(event_type=CacheEventType.CACHE_CLEAR_ALL)
        resolver._handle_cache_event(event)

        # Cache should be empty
        assert len(resolver._manufacturer_cache) == 0
        assert len(resolver._model_cache) == 0

    def test_manufacturer_cache_clear_event(self, resolver_with_cache):
        """Test CACHE_CLEAR_MANUFACTURERS event."""
        from lead_to_cash.services.knowledge_base.cache_events import (
            CacheEvent,
            CacheEventType,
        )

        resolver = resolver_with_cache

        # Handle manufacturer clear event
        event = CacheEvent(event_type=CacheEventType.CACHE_CLEAR_MANUFACTURERS)
        resolver._handle_cache_event(event)

        # Only manufacturer cache should be empty
        assert len(resolver._manufacturer_cache) == 0
        assert len(resolver._model_cache) > 0

    def test_model_cache_clear_event(self, resolver_with_cache):
        """Test CACHE_CLEAR_MODELS event."""
        from lead_to_cash.services.knowledge_base.cache_events import (
            CacheEvent,
            CacheEventType,
        )

        resolver = resolver_with_cache

        # Handle model clear event
        event = CacheEvent(event_type=CacheEventType.CACHE_CLEAR_MODELS)
        resolver._handle_cache_event(event)

        # Only model cache should be empty
        assert len(resolver._manufacturer_cache) > 0
        assert len(resolver._model_cache) == 0

    def test_manufacturer_updated_event(self, resolver_with_cache):
        """Test MANUFACTURER_UPDATED event clears specific entry."""
        from lead_to_cash.services.knowledge_base.cache_events import (
            CacheEvent,
            CacheEventType,
        )

        resolver = resolver_with_cache

        # Add another manufacturer
        mock_mfr2 = MagicMock()
        mock_mfr2.id = "mfr-002"
        resolver._put_in_cache(resolver._manufacturer_cache, "mfr-002", mock_mfr2)

        # Handle update event for specific entity
        event = CacheEvent(
            event_type=CacheEventType.MANUFACTURER_UPDATED,
            entity_type="manufacturer",
            entity_id="mfr-001",
        )
        resolver._handle_cache_event(event)

        # Only the specific entry should be removed
        assert resolver._get_from_cache(resolver._manufacturer_cache, "mfr-001") is None
        assert (
            resolver._get_from_cache(resolver._manufacturer_cache, "mfr-002")
            is not None
        )


# =============================================================================
# THRESHOLD VALIDATION TESTS
# =============================================================================


class TestThresholds:
    """Tests for threshold values and their application."""

    def test_fuzzy_threshold_value(self):
        """Test fuzzy threshold is 85%."""
        assert EntityResolver.FUZZY_THRESHOLD == 0.85

    def test_semantic_threshold_value(self):
        """Test semantic threshold is 70%."""
        assert EntityResolver.SEMANTIC_THRESHOLD == 0.70

    def test_thresholds_are_reasonable(self):
        """Test thresholds are in reasonable range."""
        # Fuzzy should be strict (high threshold)
        assert 0.80 <= EntityResolver.FUZZY_THRESHOLD <= 0.95

        # Semantic can be more lenient
        assert 0.60 <= EntityResolver.SEMANTIC_THRESHOLD <= 0.85

        # Fuzzy should be stricter than semantic
        assert EntityResolver.FUZZY_THRESHOLD > EntityResolver.SEMANTIC_THRESHOLD


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_cache_stats(self):
        """Test stats with empty caches."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )

        stats = resolver.get_cache_stats()

        assert stats["manufacturer_cache_size"] == 0
        assert stats["model_cache_size"] == 0

    def test_cache_key_normalization(self):
        """Test that cache keys should be case-normalized by caller."""
        resolver = EntityResolver(
            db=MagicMock(),
            embedding_service=MagicMock(),
        )
        cache = resolver._manufacturer_cache

        mock_mfr = MagicMock()
        resolver._put_in_cache(cache, "wartsila", mock_mfr)

        # Keys are case-sensitive (caller is responsible for normalization)
        assert resolver._get_from_cache(cache, "wartsila") is mock_mfr
        assert resolver._get_from_cache(cache, "Wartsila") is None
        assert resolver._get_from_cache(cache, "WARTSILA") is None

    def test_match_result_equality(self):
        """Test MatchResult instances can be compared."""
        result1 = MatchResult(
            entity_type="manufacturer",
            entity_id="mfr-001",
            entity_name="Test",
            match_type="exact",
            confidence=1.0,
        )
        result2 = MatchResult(
            entity_type="manufacturer",
            entity_id="mfr-001",
            entity_name="Test",
            match_type="exact",
            confidence=1.0,
        )

        # Dataclasses support equality
        assert result1 == result2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
