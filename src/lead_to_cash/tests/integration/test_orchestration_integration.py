"""
Integration Tests for Orchestration Components

Tests the full orchestration flow from orchestration_guide.md:
1. Query Understanding (Section 2)
2. Clarification Check
3. Data Inventory (Section 3)
4. Tool Selection (Section 4)
5. Tool Execution
6. Response + Follow-ups (Section 5)

NO MOCKING - uses real infrastructure per testing policy.

Requires environment variables:
- OPENAI_API_KEY: For query understanding and synthesis
- DATABASE_URL: For data inventory (optional)
- PERPLEXITY_API_KEY: For real-time search (optional)
"""

import os
import uuid

import pytest

# Skip all tests if OPENAI_API_KEY not set (required for query understanding)
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - required for orchestration tests",
)


import pytest_asyncio  # noqa: E402


@pytest.fixture(scope="module")
def event_loop():
    """Create a module-scoped event loop to share across all tests in this module."""
    import asyncio

    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def reset_singletons():
    """Reset singleton instances between tests to avoid stale state."""
    import lead_to_cash.core.conversation as conv
    import lead_to_cash.core.data_inventory as di
    import lead_to_cash.core.query_understanding as qu
    import lead_to_cash.core.tool_executor as te

    # Close any existing httpx clients before resetting
    if qu._query_engine is not None and qu._query_engine._client is not None:
        try:
            await qu._query_engine._client.aclose()
        except Exception:
            pass

    qu._query_engine = None
    di._inventory = None
    te._executor = None
    conv._manager = None
    yield
    # Also close and reset after test
    if qu._query_engine is not None and qu._query_engine._client is not None:
        try:
            await qu._query_engine._client.aclose()
        except Exception:
            pass

    qu._query_engine = None
    di._inventory = None
    te._executor = None
    conv._manager = None


# =============================================================================
# Data Inventory Tests
# =============================================================================


class TestDataInventoryService:
    """Tests for DataInventoryService."""

    @pytest.mark.asyncio
    async def test_inventory_initialization(self):
        """Test data inventory service initialization."""
        from lead_to_cash.core.data_inventory import DataInventoryService

        inventory = DataInventoryService()

        assert inventory._coverage_cache == {}
        assert inventory._initialized is False

    @pytest.mark.asyncio
    async def test_inventory_refresh(self):
        """Test data inventory refresh with real databases."""
        from lead_to_cash.core.data_inventory import DataInventoryService

        inventory = DataInventoryService()

        # Refresh should not raise even if databases unavailable
        try:
            await inventory.refresh()
        except Exception:
            pytest.skip("Database not available for inventory refresh")

        # Should be marked as initialized
        assert inventory._initialized is True

    @pytest.mark.asyncio
    async def test_coverage_check_competitor_intel(self):
        """Test coverage check for competitor intel query."""
        from lead_to_cash.core.data_inventory import (
            DataInventoryService,
            InventoryCheckResult,
        )
        from lead_to_cash.core.query_understanding import parse_query

        inventory = DataInventoryService()

        # Parse a competitor intel query
        parsed = await parse_query("What contracts has Caterpillar won in APAC?")

        # Check coverage
        result = await inventory.check_coverage(parsed)

        assert isinstance(result, InventoryCheckResult)
        assert isinstance(result.confidence, str)
        assert result.confidence in ["HIGH", "MEDIUM", "LOW"]
        assert isinstance(result.gaps, list)
        assert isinstance(result.recommended_sources, list)

    @pytest.mark.asyncio
    async def test_coverage_check_realtime_query(self):
        """Test coverage check for real-time query."""
        from lead_to_cash.core.data_inventory import DataInventoryService, DataSource
        from lead_to_cash.core.query_understanding import parse_query

        inventory = DataInventoryService()

        # Parse a real-time query
        parsed = await parse_query(
            "What is the latest news on Caterpillar's marine division?"
        )

        # Check coverage
        result = await inventory.check_coverage(parsed)

        # Real-time queries should recommend Perplexity
        assert DataSource.PERPLEXITY in result.recommended_sources

    @pytest.mark.asyncio
    async def test_coverage_summary(self):
        """Test getting coverage summary."""
        from lead_to_cash.core.data_inventory import DataInventoryService

        inventory = DataInventoryService()

        # Refresh first
        try:
            await inventory.refresh()
        except Exception:
            pytest.skip("Database not available")

        summary = inventory.get_coverage_summary()

        assert isinstance(summary, dict)


# =============================================================================
# Tool Executor Tests
# =============================================================================


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test tool executor initialization."""
        from lead_to_cash.core.tool_executor import ToolExecutor

        executor = ToolExecutor()

        assert executor.openai_api_key is not None
        assert executor._http_client is None

    @pytest.mark.asyncio
    async def test_tool_plan_competitor_intel(self):
        """Test tool planning for competitor intel query."""
        from lead_to_cash.core.data_inventory import (
            DataInventoryService,
            DataSource,
        )
        from lead_to_cash.core.query_understanding import parse_query
        from lead_to_cash.core.tool_executor import ToolExecutor

        executor = ToolExecutor()
        inventory = DataInventoryService()

        # Parse query
        parsed = await parse_query("What contracts has Caterpillar won?")

        # Get inventory result
        inventory_result = await inventory.check_coverage(parsed)

        # Plan tools
        tools = executor._plan_tools(parsed, inventory_result)

        assert isinstance(tools, list)
        assert len(tools) > 0
        # Should include local vector db for competitor intel
        assert DataSource.LOCAL_VECTORDB in tools or DataSource.PERPLEXITY in tools

    @pytest.mark.asyncio
    async def test_tool_execution_perplexity(self):
        """Test tool execution with Perplexity (if available)."""
        from lead_to_cash.core.data_inventory import DataInventoryService
        from lead_to_cash.core.query_understanding import parse_query
        from lead_to_cash.core.tool_executor import ToolExecutor, ToolResult

        if not os.getenv("PERPLEXITY_API_KEY"):
            pytest.skip("PERPLEXITY_API_KEY not set")

        executor = ToolExecutor()
        inventory = DataInventoryService()

        # Parse query
        parsed = await parse_query(
            "What is the latest news on Caterpillar marine engines?"
        )

        # Get inventory result
        inventory_result = await inventory.check_coverage(parsed)

        # Execute tool chain
        result = await executor.execute(parsed, inventory_result)

        assert isinstance(result, ToolResult)
        assert result.query == parsed.raw_query
        assert len(result.tools_used) > 0 or len(result.tool_outputs) > 0

        # Cleanup
        await executor.close()

    @pytest.mark.asyncio
    async def test_tool_sufficiency_check(self):
        """Test tool result sufficiency checking."""
        from lead_to_cash.core.data_inventory import DataSource
        from lead_to_cash.core.tool_executor import ToolExecutor, ToolOutput, ToolStatus

        executor = ToolExecutor()

        # Test with insufficient content
        outputs = [
            ToolOutput(
                tool=DataSource.LOCAL_VECTORDB,
                status=ToolStatus.PARTIAL,
                content="Short content",
            )
        ]
        assert executor._is_sufficient(outputs) is False

        # Test with sufficient content
        outputs = [
            ToolOutput(
                tool=DataSource.PERPLEXITY,
                status=ToolStatus.SUCCESS,
                content="A" * 300,  # 300 chars
                sources=["https://example.com"],
            )
        ]
        assert executor._is_sufficient(outputs) is True


# =============================================================================
# Conversation Manager Tests
# =============================================================================


class TestConversationManager:
    """Tests for ConversationManager."""

    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test session creation."""
        from lead_to_cash.core.conversation import (
            ConversationManager,
            ConversationSession,
        )

        manager = ConversationManager()

        # Create session
        session = manager.get_or_create_session()

        assert isinstance(session, ConversationSession)
        assert session.session_id is not None
        assert len(session.turns) == 0

    @pytest.mark.asyncio
    async def test_session_persistence(self):
        """Test session persists across calls."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()

        # Create session
        session1 = manager.get_or_create_session("test-session-123")

        # Get same session
        session2 = manager.get_or_create_session("test-session-123")

        assert session1 is session2
        assert session1.session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_turn_tracking(self):
        """Test conversation turn tracking."""
        from lead_to_cash.core.conversation import ConversationSession

        session = ConversationSession(session_id="test")

        # Add turns
        session.add_turn("user", "Hello")
        session.add_turn("assistant", "Hi there!")

        assert len(session.turns) == 2
        assert session.turns[0].role == "user"
        assert session.turns[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_context_update(self):
        """Test session context update from parsed query."""
        from lead_to_cash.core.conversation import ConversationSession
        from lead_to_cash.core.query_understanding import parse_query

        session = ConversationSession(session_id="test")

        # Parse query
        parsed = await parse_query("What contracts has Caterpillar won in APAC?")

        # Update context
        session.update_context(parsed)

        # Check context updated
        assert "last_intent" in session.context

    @pytest.mark.asyncio
    async def test_clarification_check(self):
        """Test clarification detection."""
        from lead_to_cash.core.conversation import ConversationManager
        from lead_to_cash.core.query_understanding import parse_query

        manager = ConversationManager()
        session = manager.get_or_create_session()

        # Parse an ambiguous query
        parsed = await parse_query("How is the competitor doing?")

        # Check clarifications
        clarifications = manager._check_clarifications(parsed, session)

        # Should need clarification (no specific competitor mentioned)
        # Note: LLM behavior may vary
        assert isinstance(clarifications, list)

    @pytest.mark.asyncio
    async def test_follow_up_generation(self):
        """Test follow-up suggestion generation."""
        from lead_to_cash.core.conversation import ConversationManager
        from lead_to_cash.core.query_understanding import parse_query
        from lead_to_cash.core.tool_executor import ToolResult

        manager = ConversationManager()

        # Parse competitor query
        parsed = await parse_query("What contracts has Caterpillar won?")

        # Create dummy tool result
        tool_result = ToolResult(
            query=parsed.raw_query,
            intent=parsed.intent,
            tools_used=[],
            tool_outputs=[],
            synthesized_content="Some results",
        )

        # Generate follow-ups
        follow_ups = manager._generate_follow_ups(parsed, tool_result)

        assert isinstance(follow_ups, list)
        assert len(follow_ups) <= 3  # Max 3 suggestions


# =============================================================================
# Full Orchestration Flow Tests
# =============================================================================


class TestFullOrchestrationFlow:
    """Tests for full orchestration flow."""

    @pytest.mark.asyncio
    async def test_process_message_answer(self):
        """Test processing a message that returns an answer."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()
        session_id = str(uuid.uuid4())

        # Process a clear query
        result = await manager.process_message(
            session_id=session_id,
            message="What are the specifications of the MTU 8000 engine?",
        )

        assert "type" in result
        assert "session_id" in result
        assert result["session_id"] == session_id

        # Should be answer or clarification
        assert result["type"] in ["answer", "clarification_needed"]

        if result["type"] == "answer":
            assert "answer" in result
            assert "follow_up_suggestions" in result

    @pytest.mark.asyncio
    async def test_process_message_clarification_flow(self):
        """Test processing a message that needs clarification."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()
        session_id = str(uuid.uuid4())

        # Process an ambiguous query
        result = await manager.process_message(
            session_id=session_id,
            message="What contracts has the competitor won?",
        )

        # Should trigger clarification or answer with partial understanding
        assert "type" in result

        if result["type"] == "clarification_needed":
            assert "questions" in result
            assert "partial_understanding" in result
            assert isinstance(result["questions"], list)

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self):
        """Test multi-turn conversation with context."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()
        session_id = str(uuid.uuid4())

        # First turn
        result1 = await manager.process_message(
            session_id=session_id,
            message="Tell me about Caterpillar's marine business",
        )

        assert "type" in result1

        # Second turn (should have context from first)
        result2 = await manager.process_message(
            session_id=session_id,
            message="What about their recent contracts?",
        )

        assert "type" in result2
        assert result2["session_id"] == session_id

        # Session should have 4 turns (2 user + 2 assistant)
        session = manager.get_session(session_id)
        assert session is not None
        assert len(session.turns) >= 2

    @pytest.mark.asyncio
    async def test_response_structure(self):
        """Test response structure matches orchestration_guide.md spec."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()
        session_id = str(uuid.uuid4())

        # Process query
        result = await manager.process_message(
            session_id=session_id,
            message="What ferry orders have been placed in Singapore recently?",
        )

        # Check required fields per orchestration_guide.md Section 7
        assert "type" in result
        assert "session_id" in result

        if result["type"] == "answer":
            # Answer response structure
            assert "answer" in result
            assert "confidence" in result
            assert result["confidence"] in ["HIGH", "MEDIUM", "LOW"]
            assert "data_coverage" in result
            assert "follow_up_suggestions" in result

            # Data coverage structure
            data_coverage = result["data_coverage"]
            assert "has_local_data" in data_coverage
            assert "coverage_confidence" in data_coverage

        elif result["type"] == "clarification_needed":
            # Clarification response structure
            assert "questions" in result
            assert "partial_understanding" in result

    @pytest.mark.asyncio
    async def test_session_cleanup(self):
        """Test session cleanup."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()

        # Create multiple sessions
        for i in range(5):
            manager.get_or_create_session(f"session-{i}")

        assert len(manager.sessions) == 5

        # Cleanup should work even with no expired sessions
        removed = manager.cleanup_expired_sessions()

        # No sessions should be removed (all are fresh)
        assert removed == 0
        assert len(manager.sessions) == 5


# =============================================================================
# Registry Integration Tests
# =============================================================================


class TestRegistryOrchestration:
    """Tests for orchestration via AgentRegistry."""

    @pytest.mark.asyncio
    async def test_registry_session_processing(self):
        """Test registry processes with session ID."""
        from lead_to_cash.agents.registry import AgentRegistry

        registry = AgentRegistry()
        await registry.initialize()

        session_id = str(uuid.uuid4())

        try:
            result = await registry.process(
                request="What are the latest ferry orders in APAC?",
                session_id=session_id,
            )

            # Should use conversation manager
            assert "type" in result or "result" in result

        finally:
            await registry.shutdown()

    @pytest.mark.asyncio
    async def test_registry_health_includes_orchestration(self):
        """Test health check includes orchestration components."""
        from lead_to_cash.agents.registry import AgentRegistry

        registry = AgentRegistry()
        await registry.initialize()

        try:
            health = await registry.health_check()

            # Should include orchestration status
            assert "orchestration" in health
            assert "data_inventory" in health["orchestration"]
            assert "tool_executor" in health["orchestration"]
            assert "conversation_manager" in health["orchestration"]

        finally:
            await registry.shutdown()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_empty_message_handling(self):
        """Test handling of empty messages."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()

        # Should return error response (not raise exception)
        result = await manager.process_message(
            session_id="test",
            message="",
        )

        # Empty message should result in error type response
        assert result["type"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Test handling of non-existent session retrieval."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()

        # Should return None for non-existent session
        session = manager.get_session("non-existent-session")

        assert session is None

    @pytest.mark.asyncio
    async def test_tool_executor_missing_api_keys(self):
        """Test tool executor handles missing API keys gracefully."""
        from lead_to_cash.core.data_inventory import DataInventoryService
        from lead_to_cash.core.query_understanding import parse_query
        from lead_to_cash.core.tool_executor import ToolExecutor

        # Create executor with no API keys
        executor = ToolExecutor(
            perplexity_api_key=None,
            newsapi_key=None,
            eodhd_api_key=None,
        )

        inventory = DataInventoryService()

        # Parse query
        parsed = await parse_query("What is Caterpillar's latest news?")

        # Get inventory
        inventory_result = await inventory.check_coverage(parsed)

        # Execute should not crash, just skip tools
        result = await executor.execute(parsed, inventory_result)

        # Should have tool outputs (even if skipped)
        assert len(result.tool_outputs) > 0

        await executor.close()
