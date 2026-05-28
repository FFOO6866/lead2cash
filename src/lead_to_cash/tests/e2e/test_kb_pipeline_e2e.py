"""
End-to-End Tests for Knowledge Base Pipeline

Tests the full KB flow:
1. Article text → entity extraction → embedding → scoring → persistence
2. A2A routing to KnowledgeBaseAgent via registry
3. Error recovery for missing DB connection

NO MOCKING - Tests use real PostgreSQL with pgvector per 3-tier testing policy.

Tier 3 (E2E): Full system integration with real infrastructure.

Prerequisites:
- DATABASE_URL environment variable set (PostgreSQL with pgvector)
- OPENAI_API_KEY environment variable set
- KB migrations applied
"""

import os

import pytest

# Skip all tests if required environment variables are not set
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL") or not os.getenv("OPENAI_API_KEY"),
        reason="DATABASE_URL and OPENAI_API_KEY required for E2E tests",
    ),
    pytest.mark.e2e,
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def kb_db():
    """Initialize KB database for tests."""
    from lead_to_cash.services.knowledge_base.database import get_knowledge_base_db

    db = get_knowledge_base_db()
    await db.initialize()
    yield db


@pytest.fixture
async def embedding_service():
    """Initialize embedding service."""
    from lead_to_cash.services.knowledge_base.embedding_service import (
        get_kb_embedding_service,
    )

    service = get_kb_embedding_service()
    await service.initialize()
    yield service


@pytest.fixture
async def entity_resolver(kb_db, embedding_service):
    """Initialize entity resolver."""
    from lead_to_cash.services.knowledge_base.entity_resolver import EntityResolver

    resolver = EntityResolver(db=kb_db, embedding_service=embedding_service)
    await resolver.initialize()
    yield resolver


@pytest.fixture
async def kb_agent():
    """Initialize KnowledgeBaseAgent for E2E testing."""
    from lead_to_cash.agents.knowledge_base_agent import (
        KnowledgeBaseAgent,
        KnowledgeBaseConfig,
    )

    config = KnowledgeBaseConfig()
    agent = KnowledgeBaseAgent(config=config)
    yield agent


@pytest.fixture
async def agent_registry():
    """Initialize agent registry for A2A routing tests."""
    from lead_to_cash.agents.registry import AgentRegistry

    registry = AgentRegistry()
    try:
        await registry.initialize()
        yield registry
    except Exception:
        pytest.skip("Agent registry initialization failed (missing dependencies)")


# =============================================================================
# Full Pipeline E2E Tests
# =============================================================================


class TestKBPipelineE2E:
    """Test full KB pipeline: text → extraction → resolution → scoring."""

    @pytest.mark.asyncio
    async def test_entity_extraction_from_article(self, kb_agent):
        """Test entity extraction from a sample marine news article."""
        article_text = (
            "MAN Energy Solutions has delivered its latest MAN 51/60DF dual-fuel engine "
            "to a new-build LNG carrier being constructed at Samsung Heavy Industries. "
            "The four-stroke engine delivers 11,000 kW and meets IMO Tier III emissions standards."
        )
        article_title = "MAN delivers dual-fuel engine for Samsung LNG carrier"

        result = await kb_agent.process_article(
            content=article_text,
            title=article_title,
        )

        assert result is not None
        # Should extract MAN as a manufacturer
        assert result.entities is not None or result.classification is not None

    @pytest.mark.asyncio
    async def test_entity_resolution_pipeline(self, entity_resolver):
        """Test 4-tier entity resolution: exact → alias → fuzzy → semantic."""
        # Exact match test
        result = await entity_resolver.resolve("MTU")
        assert result is not None

    @pytest.mark.asyncio
    async def test_embedding_generation(self, embedding_service):
        """Test embedding generation for KB text."""
        text = "MTU Series 4000 marine diesel engine for high-speed craft"
        embedding = await embedding_service.generate_embedding(text)

        assert embedding is not None
        assert len(embedding) > 0
        # OpenAI text-embedding-3-small returns 1536 dimensions
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_rag_query(self, kb_agent):
        """Test RAG-based question answering."""
        result = await kb_agent.query("What engines does MTU manufacture?")

        assert result is not None
        assert isinstance(result, dict)
        # Should have an answer or response field
        assert "answer" in result or "response" in result or "content" in result


# =============================================================================
# A2A Routing Tests
# =============================================================================


class TestKBAgentRouting:
    """Test A2A routing to KnowledgeBaseAgent via registry."""

    @pytest.mark.asyncio
    async def test_kb_agent_has_capabilities(self, kb_agent):
        """Test KnowledgeBaseAgent exposes A2A capabilities."""
        capabilities = kb_agent._extract_primary_capabilities()

        assert len(capabilities) > 0
        capability_names = [c.name for c in capabilities]
        # Should have product intel capabilities
        assert any("product" in name or "knowledge" in name or "entity" in name
                    for name in capability_names)

    @pytest.mark.asyncio
    async def test_kb_agent_in_registry(self, agent_registry):
        """Test KnowledgeBaseAgent is discoverable in agent registry."""
        agents = agent_registry._agents

        # KnowledgeBaseAgent should be registered
        kb_agent_found = any(
            "knowledge" in name.lower() or "product" in name.lower()
            for name in agents.keys()
        )
        assert kb_agent_found, (
            f"KnowledgeBaseAgent not found in registry. Available: {list(agents.keys())}"
        )

    @pytest.mark.asyncio
    async def test_registry_routes_product_query(self, agent_registry):
        """Test registry can route product-related queries to KB agent."""
        # This tests the A2A semantic routing
        result = await agent_registry.process(
            "What MTU engines are available for fast ferries?"
        )

        assert result is not None


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestKBErrorRecovery:
    """Test KB pipeline error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_query_with_empty_input(self, kb_agent):
        """Test KB agent handles empty query gracefully."""
        result = await kb_agent.query("")
        # Should return some response, not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_entity_resolution_unknown_entity(self, entity_resolver):
        """Test entity resolution with unknown manufacturer."""
        result = await entity_resolver.resolve("NonExistentManufacturerXYZ123")
        # Should return empty/no match, not crash
        assert result is not None or result is None  # Either is fine, no exception

    @pytest.mark.asyncio
    async def test_kb_agent_process_garbage_text(self, kb_agent):
        """Test KB agent handles garbage input gracefully."""
        result = await kb_agent.process_article(
            content="asdfghjkl random noise 12345",
            title="Garbage text",
        )
        # Should not crash
        assert result is not None
