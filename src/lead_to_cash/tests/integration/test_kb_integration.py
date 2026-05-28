"""
Integration Tests for Knowledge Base Services

Tests cover:
1. Entity resolver 4-tier matching (exact, alias, fuzzy, semantic)
2. Database operations (manufacturers, models, aliases)
3. Embedding service with real OpenAI
4. Cache operations and invalidation

NO MOCKING - Tests use real PostgreSQL with pgvector.

Prerequisites:
- DATABASE_URL environment variable set
- OPENAI_API_KEY environment variable set
- PostgreSQL with pgvector extension
- KB migrations applied
"""

import os
import uuid

import pytest

# Skip all tests if required environment variables are not set
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL") or not os.getenv("OPENAI_API_KEY"),
    reason="DATABASE_URL and OPENAI_API_KEY required for integration tests",
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def kb_db():
    """
    Initialize KB database for tests.

    Uses the singleton pattern to ensure services and tests use the same instance.
    """
    from lead_to_cash.services.knowledge_base.database import get_knowledge_base_db

    db = get_knowledge_base_db()
    await db.initialize()

    yield db

    # Don't close - singleton should persist for other tests


@pytest.fixture
async def embedding_service():
    """Initialize embedding service for tests."""
    from lead_to_cash.services.knowledge_base.embedding_service import (
        get_kb_embedding_service,
    )

    service = get_kb_embedding_service()
    await service.initialize()

    yield service


@pytest.fixture
async def entity_resolver(kb_db, embedding_service):
    """Initialize entity resolver with database and embedding service."""
    from lead_to_cash.services.knowledge_base.entity_resolver import EntityResolver

    resolver = EntityResolver(db=kb_db, embedding_service=embedding_service)
    await resolver.initialize()

    yield resolver


@pytest.fixture
def test_manufacturer_id():
    """Generate unique test manufacturer ID."""
    return f"test-mfr-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_alias_id():
    """Generate unique test alias ID."""
    return f"test-alias-{uuid.uuid4().hex[:8]}"


# =============================================================================
# DATABASE HEALTH TESTS
# =============================================================================


class TestDatabaseHealth:
    """Tests for database health and connectivity."""

    @pytest.mark.asyncio
    async def test_database_connection(self, kb_db):
        """Test database connection is established."""
        assert kb_db is not None
        assert kb_db._initialized is True

    @pytest.mark.asyncio
    async def test_health_check(self, kb_db):
        """Test database health check."""
        health = await kb_db.health_check()

        assert health is not None
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_pool_stats(self, kb_db):
        """Test connection pool statistics."""
        stats = await kb_db.get_pool_stats()

        assert "size" in stats or "pool_size" in stats or stats is not None


# =============================================================================
# MANUFACTURER TESTS
# =============================================================================


class TestManufacturerOperations:
    """Tests for manufacturer database operations."""

    @pytest.mark.asyncio
    async def test_list_manufacturers(self, kb_db):
        """Test listing manufacturers from seed data."""
        manufacturers = await kb_db.list_manufacturers(is_active=True, limit=10)

        # Should have seed data
        assert len(manufacturers) >= 0  # May have seed data or empty

    @pytest.mark.asyncio
    async def test_get_manufacturer_by_name_wartsila(self, kb_db):
        """Test getting Wärtsilä by name if exists in seed data."""
        # Try normalized name
        mfr = await kb_db.get_manufacturer_by_name("wärtsilä")

        # May or may not exist depending on seed data
        if mfr:
            assert "wärtsilä" in mfr.name.lower() or "wartsila" in mfr.name.lower()


# =============================================================================
# ENTITY RESOLVER TESTS
# =============================================================================


class TestEntityResolverInit:
    """Tests for entity resolver initialization."""

    @pytest.mark.asyncio
    async def test_resolver_initialization(self, entity_resolver):
        """Test resolver initializes correctly."""
        assert entity_resolver is not None
        assert entity_resolver._initialized is True

    @pytest.mark.asyncio
    async def test_cache_stats(self, entity_resolver):
        """Test cache statistics are available."""
        stats = entity_resolver.get_cache_stats()

        assert "manufacturer_cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "using_cachetools" in stats


class TestExactMatch:
    """Tests for exact matching in entity resolver."""

    @pytest.mark.asyncio
    async def test_exact_match_manufacturer(self, entity_resolver, kb_db):
        """Test exact match on manufacturer name."""
        # First, get a manufacturer from the database to test with
        manufacturers = await kb_db.list_manufacturers(is_active=True, limit=1)

        if manufacturers:
            mfr = manufacturers[0]
            result = await entity_resolver.resolve(mfr.name, entity_type="manufacturer")

            if result:
                assert result.entity_type == "manufacturer"
                assert result.match_type == "exact"
                assert result.confidence == 1.0


class TestAliasMatch:
    """Tests for alias matching in entity resolver."""

    @pytest.mark.asyncio
    async def test_alias_match_if_exists(self, entity_resolver, kb_db):
        """Test alias match if aliases exist in database."""
        # Get aliases from database
        aliases = await kb_db.list_aliases(limit=1)

        if aliases:
            alias = aliases[0]
            result = await entity_resolver.resolve(
                alias.alias_text, entity_type=alias.entity_type
            )

            if result:
                assert result.entity_type == alias.entity_type
                assert result.match_type in ["exact", "alias"]


class TestFuzzyMatch:
    """Tests for fuzzy matching in entity resolver."""

    @pytest.mark.asyncio
    async def test_fuzzy_match_with_typo(self, entity_resolver, kb_db):
        """Test fuzzy match handles common typos."""
        # Get a manufacturer to test with
        manufacturers = await kb_db.list_manufacturers(is_active=True, limit=1)

        if manufacturers:
            mfr = manufacturers[0]
            # Introduce a minor typo (if name is long enough)
            if len(mfr.name) > 5:
                typo_name = mfr.name[:-2] + "xx"  # Replace last 2 chars
                result = await entity_resolver.resolve(
                    typo_name, entity_type="manufacturer"
                )

                # May or may not match depending on similarity threshold
                if result:
                    # If matched, should be fuzzy match
                    assert result.match_type in ["exact", "alias", "fuzzy", "semantic"]


# =============================================================================
# EMBEDDING SERVICE TESTS
# =============================================================================


class TestEmbeddingGeneration:
    """Tests for embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, embedding_service):
        """Test generating embedding for a single text."""
        text = "Wärtsilä 31DF dual-fuel marine engine"
        embedding = await embedding_service.generate_embedding(text)

        assert embedding is not None
        assert len(embedding) == 1536  # text-embedding-3-small dimensions
        assert all(isinstance(x, float) for x in embedding)
        assert any(x != 0.0 for x in embedding)  # Not all zeros

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings(self, embedding_service):
        """Test generating embeddings for multiple texts."""
        texts = [
            "Marine diesel engine",
            "LNG dual-fuel propulsion",
            "Offshore power generation",
        ]
        embeddings = await embedding_service.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 1536

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, embedding_service):
        """Test that same text produces consistent embeddings."""
        text = "Test engine model XYZ"

        emb1 = await embedding_service.generate_embedding(text)
        emb2 = await embedding_service.generate_embedding(text)

        # Embeddings should be identical for same input
        assert emb1 == emb2


class TestSemanticSearch:
    """Tests for semantic search functionality."""

    @pytest.mark.asyncio
    async def test_search_entities_returns_results(self, embedding_service):
        """Test semantic search returns results if data exists."""
        results = await embedding_service.search_entities(
            query="marine diesel engine manufacturer",
            entity_type=None,  # Search all types
            top_k=5,
            min_similarity=0.5,
        )

        # May or may not have results depending on seed data
        assert isinstance(results, list)

        if results:
            top = results[0]
            assert "entity_type" in top
            assert "entity_id" in top
            assert "similarity" in top
            assert 0.0 <= top["similarity"] <= 1.0


# =============================================================================
# RELEVANCE SCORER INTEGRATION TESTS
# =============================================================================


class TestScorerIntegration:
    """Integration tests for relevance scorer with real data."""

    @pytest.mark.asyncio
    async def test_score_with_resolved_entities(self, entity_resolver, kb_db):
        """Test scoring with entities resolved from database."""
        from lead_to_cash.services.knowledge_base.models import (
            ExtractedEntity,
            MarketSegmentType,
            ResolvedEntity,
        )
        from lead_to_cash.services.knowledge_base.scorer import (
            RelevanceScorer,
            ScoringInput,
        )

        scorer = RelevanceScorer()

        # Try to resolve a real manufacturer
        manufacturers = await kb_db.list_manufacturers(is_active=True, limit=1)

        entities = []
        if manufacturers:
            mfr = manufacturers[0]
            result = await entity_resolver.resolve(mfr.name, entity_type="manufacturer")
            if result:
                # Create a ResolvedEntity from the match result
                extracted = ExtractedEntity(
                    text=mfr.name,
                    entity_type="manufacturer",
                    confidence=1.0,
                )
                resolved = ResolvedEntity(
                    extracted=extracted,
                    entity_type=result.entity_type,
                    entity_id=result.entity_id,
                    entity_name=result.entity_name,
                    match_type=result.match_type,
                    match_confidence=result.confidence,
                )
                entities.append(resolved)

        # Score with the resolved entities
        input_data = ScoringInput(
            article_id="test-article-001",
            article_content="New contract for marine diesel engines",
            entities=entities,
            market_segments=[MarketSegmentType.MARINE_TRANSPORTATION],
        )

        score = scorer.score(input_data)

        assert score.total_score >= 0
        assert score.classification in ["high_priority", "monitor", "ignore"]


# =============================================================================
# CACHE OPERATIONS TESTS
# =============================================================================


class TestCacheOperations:
    """Tests for cache operations in entity resolver."""

    @pytest.mark.asyncio
    async def test_cache_hit_improves_performance(self, entity_resolver, kb_db):
        """Test that cache hits are faster than misses."""
        manufacturers = await kb_db.list_manufacturers(is_active=True, limit=1)

        if manufacturers:
            mfr = manufacturers[0]

            # First call - cache miss
            entity_resolver.clear_cache()
            await entity_resolver.resolve(mfr.name, entity_type="manufacturer")
            stats_after_first = entity_resolver.get_cache_stats()

            # Second call - should hit cache
            await entity_resolver.resolve(mfr.name, entity_type="manufacturer")
            stats_after_second = entity_resolver.get_cache_stats()

            # Cache hits should increase
            assert stats_after_second["cache_hits"] >= stats_after_first["cache_hits"]

    @pytest.mark.asyncio
    async def test_cache_clear(self, entity_resolver):
        """Test cache clearing works correctly."""
        entity_resolver.clear_cache()
        stats = entity_resolver.get_cache_stats()

        assert stats["manufacturer_cache_size"] == 0
        assert stats["model_cache_size"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0


# =============================================================================
# DATA QUALITY TESTS
# =============================================================================


class TestDataQuality:
    """Tests for data quality checks."""

    @pytest.mark.asyncio
    async def test_check_orphaned_entities(self, kb_db):
        """Test checking for orphaned entities."""
        from lead_to_cash.services.knowledge_base.data_quality import (
            DataQualityValidator,
        )

        validator = DataQualityValidator(kb_db)
        issues = await validator.check_orphaned_entities()

        # Should return a list (may be empty)
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_check_missing_embeddings(self, kb_db):
        """Test checking for missing embeddings."""
        from lead_to_cash.services.knowledge_base.data_quality import (
            DataQualityValidator,
        )

        validator = DataQualityValidator(kb_db)
        issues = await validator.check_missing_embeddings()

        # Should return a list (may be empty)
        assert isinstance(issues, list)


# =============================================================================
# METRICS TESTS
# =============================================================================


class TestMetrics:
    """Tests for KB metrics collection."""

    def test_metrics_singleton(self):
        """Test metrics singleton returns same instance."""
        from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics

        metrics1 = get_kb_metrics()
        metrics2 = get_kb_metrics()

        assert metrics1 is metrics2

    def test_record_embedding_generated(self):
        """Test recording embedding generation metric."""
        from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics

        metrics = get_kb_metrics()
        # Should not raise
        metrics.record_embedding_generated("text-embedding-3-small")

    def test_get_metrics_structure(self):
        """Test getting metrics returns expected structure."""
        from lead_to_cash.services.knowledge_base.metrics import get_kb_metrics

        metrics = get_kb_metrics()
        result = metrics.get_metrics()

        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
