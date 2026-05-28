"""
Tests for query understanding and entity resolution components.

TEST CATEGORIES:
1. Unit tests (mocked) - Test JSON parsing, serialization, threshold values
2. Integration tests - Would test actual LLM calls (marked with skip by default)

NOTE: The unit tests mock the OpenAI API to test the parsing logic.
For actual LLM interpretation testing, run integration tests with real API.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lead_to_cash.core.query_understanding import (
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
)


class TestQueryParsingUnit:
    """
    Unit tests for query parsing logic.

    These tests mock the LLM to verify:
    - JSON response parsing
    - Intent classification mapping
    - Field extraction and defaults
    """

    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response."""

        def create_response(
            intent: str,
            companies: list,
            raw_input: str,
            confidence: float = 0.85,
            **extra_fields,
        ):
            response_data = {
                "intent": intent,
                "intent_confidence": confidence,
                "companies": companies,
                "raw_company_input": raw_input,
                "competitors": extra_fields.get("competitors", []),
                "regions": extra_fields.get("regions", []),
                "products": extra_fields.get("products", []),
                "vessel_types": extra_fields.get("vessel_types", []),
                "time_reference": extra_fields.get("time_reference"),
                "time_start": extra_fields.get("time_start"),
                "time_end": extra_fields.get("time_end"),
                "is_realtime_needed": extra_fields.get("is_realtime_needed", False),
                "requires_clarification": extra_fields.get(
                    "requires_clarification", False
                ),
                "clarification_questions": extra_fields.get(
                    "clarification_questions", []
                ),
                "clarification_reason": extra_fields.get("clarification_reason"),
                "inherited_context": extra_fields.get("inherited_context"),
            }
            return {"choices": [{"message": {"content": json.dumps(response_data)}}]}

        return create_response

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_parses_kyp_intent(self, mock_openai_response):
        """Test that KYP intent is correctly parsed from LLM response."""
        with patch.object(QueryUnderstandingEngine, "_get_client") as mock_client:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_openai_response(
                intent="kyp_due_diligence",
                companies=["test company"],
                raw_input="test company",
                confidence=0.90,
            )
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http

            engine = QueryUnderstandingEngine()
            result = await engine.parse("kyp on test company")

            assert result.intent == QueryIntent.KYP_DUE_DILIGENCE
            assert result.companies == ["test company"]
            assert result.raw_company_input == "test company"
            assert result.intent_confidence == 0.90

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_parses_market_intel_intent(self, mock_openai_response):
        """Test that market intel intent is correctly parsed."""
        with patch.object(QueryUnderstandingEngine, "_get_client") as mock_client:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_openai_response(
                intent="market_intel",
                companies=[],
                raw_input=None,
                confidence=0.95,
                regions=["APAC", "Singapore"],
            )
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http

            engine = QueryUnderstandingEngine()
            result = await engine.parse("What's happening in Singapore market?")

            assert result.intent == QueryIntent.MARKET_INTEL
            assert "Singapore" in result.regions or "APAC" in result.regions

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_extracts_raw_company_input(self, mock_openai_response):
        """Test that raw company input is extracted exactly as provided."""
        with patch.object(QueryUnderstandingEngine, "_get_client") as mock_client:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            # Simulate LLM extracting raw input without interpretation
            mock_response.json.return_value = mock_openai_response(
                intent="kyp_due_diligence",
                companies=["stengg"],  # Raw, uninterpreted
                raw_input="stengg",
                confidence=0.85,
            )
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http

            engine = QueryUnderstandingEngine()
            result = await engine.parse("run kyp on stengg")

            # Raw input should be preserved exactly
            assert result.raw_company_input == "stengg"
            assert result.companies == ["stengg"]

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    async def test_handles_unknown_intent_gracefully(self, mock_openai_response):
        """Test that unknown intent falls back to general_question."""
        with patch.object(QueryUnderstandingEngine, "_get_client") as mock_client:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            # Simulate invalid intent from LLM
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "invalid_intent_xyz",
                                    "intent_confidence": 0.5,
                                    "companies": [],
                                    "raw_company_input": None,
                                    "competitors": [],
                                    "regions": [],
                                    "products": [],
                                    "vessel_types": [],
                                }
                            )
                        }
                    }
                ]
            }
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http

            engine = QueryUnderstandingEngine()
            result = await engine.parse("some random query")

            # Should fall back to general_question
            assert result.intent == QueryIntent.GENERAL_QUESTION


class TestParsedQuerySerialization:
    """Test ParsedQuery serialization/deserialization."""

    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all expected fields."""
        parsed = ParsedQuery(
            raw_query="kyp onste",
            intent=QueryIntent.KYP_DUE_DILIGENCE,
            intent_confidence=0.85,
            companies=["onste"],
            raw_company_input="onste",
            regions=["APAC"],
        )

        data = parsed.to_dict()

        assert data["raw_query"] == "kyp onste"
        assert data["intent"] == "kyp_due_diligence"
        assert data["companies"] == ["onste"]
        assert data["raw_company_input"] == "onste"
        assert data["regions"] == ["APAC"]
        assert "parsed_at" in data

    def test_from_dict_restores_all_fields(self):
        """Test that from_dict correctly restores ParsedQuery."""
        data = {
            "raw_query": "kyp test company",
            "intent": "kyp_due_diligence",
            "intent_confidence": 0.85,
            "companies": ["test company"],
            "raw_company_input": "test company",
            "regions": ["Singapore"],
            "wants_full_report": True,
        }

        parsed = ParsedQuery.from_dict(data)

        assert parsed is not None
        assert parsed.raw_query == "kyp test company"
        assert parsed.intent == QueryIntent.KYP_DUE_DILIGENCE
        assert parsed.companies == ["test company"]
        assert parsed.raw_company_input == "test company"
        assert parsed.wants_full_report is True

    def test_from_dict_handles_none(self):
        """Test that from_dict handles None input."""
        assert ParsedQuery.from_dict(None) is None

    def test_from_dict_handles_invalid_intent(self):
        """Test that from_dict handles invalid intent by defaulting."""
        data = {
            "raw_query": "test",
            "intent": "not_a_real_intent",
            "intent_confidence": 0.5,
        }

        parsed = ParsedQuery.from_dict(data)

        assert parsed is not None
        assert parsed.intent == QueryIntent.GENERAL_QUESTION


class TestSharedConfigModule:
    """Test that shared config module exists and has correct values."""

    def test_config_module_exists(self):
        """Verify config module can be imported."""
        from lead_to_cash.services.entity_registry.config import (
            AUTO_CONFIRM_THRESHOLD_PERCENT,
            AUTO_CONFIRM_THRESHOLD_RATIO,
            FUZZY_SEARCH_THRESHOLD,
            MARGIN_THRESHOLD_PERCENT,
            MARGIN_THRESHOLD_RATIO,
            MAX_CANDIDATES,
            MAX_REACT_CYCLES,
        )

        # Percentage values
        assert AUTO_CONFIRM_THRESHOLD_PERCENT == 80.0
        assert MARGIN_THRESHOLD_PERCENT == 15.0

        # Ratio values (derived)
        assert AUTO_CONFIRM_THRESHOLD_RATIO == 0.80
        assert MARGIN_THRESHOLD_RATIO == 0.15

        # Other config
        assert FUZZY_SEARCH_THRESHOLD == 0.4
        assert MAX_CANDIDATES == 5
        assert MAX_REACT_CYCLES == 5


class TestThresholdConsistency:
    """Test that threshold values are consistent across components."""

    def test_service_uses_config_module(self):
        """Verify EntityResolutionService imports from config module."""
        from lead_to_cash.services.entity_registry.config import (
            AUTO_CONFIRM_THRESHOLD_RATIO,
            FUZZY_SEARCH_THRESHOLD,
            MARGIN_THRESHOLD_RATIO,
        )
        from lead_to_cash.services.entity_registry.entity_resolution_service import (
            EntityResolutionService,
        )

        service = EntityResolutionService()

        # Service should use config values
        assert service.AUTO_CONFIRM_THRESHOLD == AUTO_CONFIRM_THRESHOLD_RATIO
        assert service.MARGIN_THRESHOLD == MARGIN_THRESHOLD_RATIO
        assert service.FUZZY_THRESHOLD == FUZZY_SEARCH_THRESHOLD

    def test_agent_uses_config_module(self):
        """Verify EntityResolutionAgent imports from config module."""
        from lead_to_cash.agents.entity_resolution_agent import (
            EntityResolutionAgent,
        )
        from lead_to_cash.services.entity_registry.config import (
            AUTO_CONFIRM_THRESHOLD_PERCENT,
            MARGIN_THRESHOLD_PERCENT,
        )

        agent = EntityResolutionAgent()

        # Agent uses percentage values
        assert agent.AUTO_CONFIRM_THRESHOLD == AUTO_CONFIRM_THRESHOLD_PERCENT
        assert agent.MARGIN_THRESHOLD == MARGIN_THRESHOLD_PERCENT

    def test_no_circular_import(self):
        """Verify no circular import between agent and service."""
        # This should not raise ImportError
        from lead_to_cash.agents.entity_resolution_agent import (
            EntityResolutionAgent,
        )
        from lead_to_cash.services.entity_registry.entity_resolution_service import (
            EntityResolutionService,
        )

        # Both should be importable and instantiable
        service = EntityResolutionService()
        agent = EntityResolutionAgent()

        assert service is not None
        assert agent is not None


class TestEntityResolutionAgentStructure:
    """Test EntityResolutionAgent structure and imports (Kaizen BaseAgent)."""

    def test_agent_can_be_imported(self):
        """Verify agent can be imported without errors."""
        from lead_to_cash.agents.entity_resolution_agent import (
            EntityResolutionAgent,
            EntityResolutionReActAgent,
            get_entity_resolution_agent,
        )

        # EntityResolutionReActAgent is backward-compatible alias for EntityResolutionAgent
        assert EntityResolutionReActAgent is EntityResolutionAgent

        agent = get_entity_resolution_agent()
        assert agent is not None
        assert isinstance(agent, EntityResolutionAgent)

    def test_agent_inherits_from_kaizen_base_agent(self):
        """Verify agent inherits from Kaizen BaseAgent."""
        from kaizen.core.base_agent import BaseAgent

        from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

        agent = EntityResolutionAgent()

        # Should inherit from Kaizen BaseAgent
        assert isinstance(agent, BaseAgent)
        assert hasattr(agent, "agent_id")
        assert agent.agent_id == "entity_resolution_agent"

    def test_agent_has_required_methods(self):
        """Verify agent has required public methods."""
        import inspect

        from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

        agent = EntityResolutionAgent()

        # Required methods for Kaizen BaseAgent
        assert hasattr(agent, "resolve")  # Backward compatibility alias
        assert hasattr(agent, "resolve_entity")  # Primary method
        assert hasattr(agent, "initialize")
        assert hasattr(agent, "close")
        assert hasattr(agent, "run")  # A2A Router compatibility
        assert hasattr(agent, "_extract_primary_capabilities")  # A2A capabilities

        # Async methods
        assert inspect.iscoroutinefunction(agent.resolve)
        assert inspect.iscoroutinefunction(agent.resolve_entity)
        assert inspect.iscoroutinefunction(agent.initialize)
        assert inspect.iscoroutinefunction(agent.close)

        # Sync method for A2A routing
        assert callable(agent.run)

    def test_agent_has_a2a_capabilities(self):
        """Verify agent defines A2A capabilities for semantic routing."""
        from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

        agent = EntityResolutionAgent()
        capabilities = agent._extract_primary_capabilities()

        # Should have at least one capability
        assert len(capabilities) >= 1

        # Check capability names
        capability_names = [c.name for c in capabilities]
        assert "entity_resolution" in capability_names

    def test_agent_has_signature(self):
        """Verify agent has properly defined signature."""
        from lead_to_cash.agents.entity_resolution_agent import (
            EntityResolutionAgent,
            EntityResolutionSignature,
        )

        agent = EntityResolutionAgent()

        # Agent should have a signature property
        assert hasattr(agent, "signature")
        assert isinstance(agent.signature, EntityResolutionSignature)

    def test_agent_delegates_to_service(self):
        """Verify agent delegates to EntityResolutionService."""
        import inspect

        from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

        agent = EntityResolutionAgent()

        # Check that resolve_entity method delegates to service
        source = inspect.getsource(agent.resolve_entity)

        # Should call service.resolve (not internal DB logic)
        assert "service.resolve" in source or "self._service" in source

        # Should NOT have duplicate database search logic
        assert "self._db.search_entities_exact" not in source
        assert "self._db.search_by_alias" not in source


class TestEntityResolutionServiceSearchRegistry:
    """Test the new search_registry method on EntityResolutionService."""

    def test_service_has_search_registry_method(self):
        """Verify service has search_registry method."""
        import inspect

        from lead_to_cash.services.entity_registry.entity_resolution_service import (
            EntityResolutionService,
        )

        service = EntityResolutionService()

        assert hasattr(service, "search_registry")
        assert inspect.iscoroutinefunction(service.search_registry)


class TestConversationManagerIntegration:
    """Test ConversationManager integration with entity agent."""

    def test_conversation_manager_has_entity_agent(self):
        """Verify ConversationManager can access entity_agent."""
        from lead_to_cash.core.conversation import ConversationManager

        manager = ConversationManager()
        agent = manager.entity_agent

        assert agent is not None
        assert agent.AUTO_CONFIRM_THRESHOLD == 80.0
        assert agent.MARGIN_THRESHOLD == 15.0


# ============================================================================
# Integration Tests (require real API keys)
# ============================================================================


@pytest.mark.skip(reason="Integration test - requires OPENAI_API_KEY")
class TestQueryUnderstandingIntegration:
    """
    Integration tests for actual LLM query understanding.

    These tests require a valid OPENAI_API_KEY and make real API calls.
    Run with: pytest -m "not skip" --run-integration
    """

    @pytest.mark.asyncio
    async def test_llm_extracts_raw_company_input(self):
        """Test that LLM extracts company input without interpretation."""
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        engine = QueryUnderstandingEngine()

        # Test with a typo - LLM should extract raw, not interpret
        result = await engine.parse("run kyp on stengg")

        # The raw input should be preserved
        assert result.raw_company_input == "stengg"
        # companies should also be the raw input (no interpretation)
        assert "stengg" in result.companies

        await engine.close()


@pytest.mark.skip(reason="Integration test - requires database")
class TestEntityResolutionIntegration:
    """
    Integration tests for entity resolution with real database.

    These tests require a running database with entity registry.
    """

    @pytest.mark.asyncio
    async def test_agent_resolves_known_entity(self):
        """Test that agent can resolve a known entity from database."""
        from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

        agent = EntityResolutionAgent()
        await agent.initialize()

        # This would need a seeded database
        result = await agent.resolve("ST Engineering", country_hint="SG")

        # Should find match (if database is seeded)
        assert result.status.value in ["exact_match", "confirmation_required"]

        await agent.close()
