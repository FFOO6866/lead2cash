"""
Integration Tests for A2A Semantic Routing Architecture

Tests the A2A (Agent-to-Agent) semantic routing implementation as defined in ADR-003.
Verifies that:
- Agents properly expose capabilities via _extract_primary_capabilities()
- Pipeline.router() can route tasks based on semantic capability matching
- No hardcoded if/else routing - pure A2A semantic matching

Requirements:
- Full A2A support requires kailash.nodes.ai.a2a module
- Tests gracefully degrade when A2A module is not available
"""

import pytest

# Check if A2A module is available
try:
    from kaizen.nodes.ai.a2a import Capability  # noqa: F401

    HAS_A2A_MODULE = True
except ImportError:
    HAS_A2A_MODULE = False


# =============================================================================
# Test: Agent Capability Definitions
# =============================================================================


class TestAgentCapabilityDefinitions:
    """Test that agents define correct capabilities via _extract_primary_capabilities()."""

    def test_due_diligence_agent_capabilities(self):
        """Test DueDiligenceAgent exposes customer validation capabilities."""
        from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

        config = DueDiligenceConfig(llm_provider="mock")
        agent = DueDiligenceAgent(config)

        # Agent should have the capability extraction method
        assert hasattr(agent, "_extract_primary_capabilities")

        # Get capabilities
        capabilities = agent._extract_primary_capabilities()

        if HAS_A2A_MODULE:
            # With A2A module, should return Capability objects
            assert (
                len(capabilities) >= 2
            ), "DueDiligenceAgent should have at least 2 capabilities"

            # Check for expected capabilities
            cap_names = [c.name for c in capabilities]
            assert "customer_validation" in cap_names
            assert "credit_check" in cap_names

            # Verify capability structure
            for cap in capabilities:
                assert hasattr(cap, "name")
                assert hasattr(cap, "domain")
                assert hasattr(cap, "description")
                assert hasattr(cap, "keywords")
                assert len(cap.keywords) > 0
        else:
            # Without A2A module, returns empty list (graceful degradation)
            assert capabilities == []

    def test_web_search_agent_capabilities(self):
        """Test WebSearchAgent exposes web search capabilities."""
        from lead_to_cash.agents import WebSearchAgent, WebSearchConfig

        config = WebSearchConfig(llm_provider="mock")
        agent = WebSearchAgent(config)

        capabilities = agent._extract_primary_capabilities()

        if HAS_A2A_MODULE:
            assert len(capabilities) >= 2
            cap_names = [c.name for c in capabilities]
            assert "web_search" in cap_names
            assert "competitor_intel" in cap_names
        else:
            assert capabilities == []

    def test_database_agent_capabilities(self):
        """Test DatabaseAgent exposes database operation capabilities."""
        from lead_to_cash.agents import DatabaseAgent, DatabaseAgentConfig

        config = DatabaseAgentConfig(llm_provider="mock")
        agent = DatabaseAgent(config)

        capabilities = agent._extract_primary_capabilities()

        if HAS_A2A_MODULE:
            assert len(capabilities) >= 2
            cap_names = [c.name for c in capabilities]
            assert "db_query" in cap_names
            assert "db_store" in cap_names
        else:
            assert capabilities == []


# =============================================================================
# Test: A2A Card Generation
# =============================================================================


@pytest.mark.skipif(not HAS_A2A_MODULE, reason="Requires kaizen.nodes.ai.a2a module")
class TestA2ACardGeneration:
    """Test A2A capability generation from agents.

    Note: BaseAgent.to_a2a_card() has a bug in kaizen package (imports from wrong path).
    These tests use _extract_primary_capabilities() directly which is the recommended approach.
    """

    def test_extract_primary_capabilities_returns_valid_capabilities(self):
        """Test _extract_primary_capabilities() returns proper Capability objects."""
        from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

        config = DueDiligenceConfig(llm_provider="mock")
        agent = DueDiligenceAgent(config)

        capabilities = agent._extract_primary_capabilities()

        # Should return list of Capability objects
        assert isinstance(capabilities, list)
        assert len(capabilities) > 0

        # Each should be a Capability with required attributes
        for cap in capabilities:
            assert isinstance(cap, Capability)
            assert hasattr(cap, "name")
            assert hasattr(cap, "description")
            assert hasattr(cap, "keywords")

    def test_capabilities_have_correct_structure(self):
        """Test capabilities have all required fields."""
        from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

        config = DueDiligenceConfig(llm_provider="mock")
        agent = DueDiligenceAgent(config)

        capabilities = agent._extract_primary_capabilities()

        # Should have at least customer_validation and credit_check
        cap_names = {c.name for c in capabilities}
        assert "customer_validation" in cap_names
        assert "credit_check" in cap_names

        # Each capability should have keywords for matching
        for cap in capabilities:
            assert len(cap.keywords) > 0


# =============================================================================
# Test: Semantic Capability Matching
# =============================================================================


@pytest.mark.skipif(not HAS_A2A_MODULE, reason="Requires kailash.nodes.ai.a2a module")
class TestSemanticCapabilityMatching:
    """Test semantic matching of capabilities to tasks."""

    def test_capability_matches_requirement(self):
        """Test Capability.matches_requirement() for semantic matching."""
        from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

        config = DueDiligenceConfig(llm_provider="mock")
        agent = DueDiligenceAgent(config)

        capabilities = agent._extract_primary_capabilities()
        customer_val_cap = next(
            c for c in capabilities if c.name == "customer_validation"
        )

        # Should match related tasks
        assert customer_val_cap.matches_requirement("Validate customer 1234567")
        assert customer_val_cap.matches_requirement("Check customer master data")
        assert customer_val_cap.matches_requirement("due diligence on company")

    def test_capability_keyword_matching(self):
        """Test capability keyword-based matching."""
        from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

        config = DueDiligenceConfig(llm_provider="mock")
        agent = DueDiligenceAgent(config)

        capabilities = agent._extract_primary_capabilities()
        credit_cap = next(c for c in capabilities if c.name == "credit_check")

        # Keywords should include credit-related terms
        keywords_lower = [k.lower() for k in credit_cap.keywords]
        assert "credit" in keywords_lower
        assert "credit limit" in keywords_lower


# =============================================================================
# Test: Registry A2A Integration
# =============================================================================


class TestRegistryA2AIntegration:
    """Test AgentRegistry integration with A2A capabilities."""

    @pytest.mark.asyncio
    async def test_registry_uses_a2a_for_capability_lookup(self):
        """Test registry uses A2A cards for capability-based agent lookup."""
        from lead_to_cash.agents import AgentRegistry

        registry = AgentRegistry(llm_provider="mock")
        await registry.initialize()

        try:
            if HAS_A2A_MODULE:
                # With A2A, should find agent for capability
                agent = registry.get_agent_for_capability("customer_validation")
                assert agent is not None

                # Agent should be the DueDiligenceAgent
                from lead_to_cash.agents import DueDiligenceAgent

                assert isinstance(agent, DueDiligenceAgent)
            else:
                # Without A2A, returns None (graceful degradation)
                agent = registry.get_agent_for_capability("customer_validation")
                assert agent is None
        finally:
            await registry.shutdown()

    @pytest.mark.asyncio
    async def test_registry_keyword_search_uses_a2a(self):
        """Test registry keyword search uses A2A capability keywords."""
        from lead_to_cash.agents import AgentRegistry

        registry = AgentRegistry(llm_provider="mock")
        await registry.initialize()

        try:
            if HAS_A2A_MODULE:
                # Should find agents with "validate" keyword
                agents = registry.find_agents_by_keyword("validate")
                assert len(agents) > 0

                # Should find agents with "credit" keyword
                credit_agents = registry.find_agents_by_keyword("credit")
                assert len(credit_agents) > 0
            else:
                # Without A2A, returns empty list
                agents = registry.find_agents_by_keyword("validate")
                assert len(agents) == 0
        finally:
            await registry.shutdown()


# =============================================================================
# Test: Pipeline Router Integration (Requires A2A)
# =============================================================================


@pytest.mark.skipif(not HAS_A2A_MODULE, reason="Requires kailash.nodes.ai.a2a module")
class TestPipelineRouterIntegration:
    """Test Pipeline.router() semantic routing with A2A agents."""

    @pytest.mark.asyncio
    async def test_router_selects_agent_by_task(self):
        """Test Pipeline.router() selects appropriate agent based on task."""
        from lead_to_cash.agents import (
            DueDiligenceAgent,
            DueDiligenceConfig,
            WebSearchAgent,
            WebSearchConfig,
        )

        try:
            from kaizen.orchestration.pipeline import Pipeline
        except ImportError:
            pytest.skip("Requires kaizen.orchestration.pipeline")

        # Create agents
        dd_config = DueDiligenceConfig(llm_provider="mock")
        dd_agent = DueDiligenceAgent(dd_config)

        ws_config = WebSearchConfig(llm_provider="mock")
        ws_agent = WebSearchAgent(ws_config)
        await ws_agent.__aenter__()

        try:
            # Create router with semantic strategy
            router = Pipeline.router(
                agents=[dd_agent, ws_agent], routing_strategy="semantic"
            )

            # Router should be created successfully
            assert router is not None

            # Note: Full routing execution requires LLM calls
            # This test validates the router setup and agent registration
        finally:
            await ws_agent.__aexit__(None, None, None)


# =============================================================================
# Test: Architecture Compliance (ADR-003)
# =============================================================================


class TestArchitectureCompliance:
    """Test compliance with ADR-003 A2A architecture decisions."""

    def test_no_hardcoded_routing_in_registry(self):
        """Verify registry uses A2A cards, not hardcoded capability lists."""
        # RegisteredAgent should NOT have a capabilities field
        # Capabilities come from A2A cards at runtime
        import dataclasses

        from lead_to_cash.agents.registry import RegisteredAgent

        fields = {f.name for f in dataclasses.fields(RegisteredAgent)}

        assert (
            "capabilities" not in fields
        ), "RegisteredAgent should not have hardcoded capabilities field"

    def test_agents_implement_extract_capabilities(self):
        """Verify all major agents implement _extract_primary_capabilities()."""
        from lead_to_cash.agents import (
            DatabaseAgent,
            DatabaseAgentConfig,
            DueDiligenceAgent,
            DueDiligenceConfig,
            WebSearchAgent,
            WebSearchConfig,
        )

        agents_to_test = [
            (DueDiligenceAgent, DueDiligenceConfig(llm_provider="mock")),
            (WebSearchAgent, WebSearchConfig(llm_provider="mock")),
            (DatabaseAgent, DatabaseAgentConfig(llm_provider="mock")),
        ]

        for agent_class, config in agents_to_test:
            agent = agent_class(config)

            # Should have the method
            assert hasattr(
                agent, "_extract_primary_capabilities"
            ), f"{agent_class.__name__} should implement _extract_primary_capabilities()"

            # Method should be callable
            capabilities = agent._extract_primary_capabilities()

            # Should return a list
            assert isinstance(
                capabilities, list
            ), f"{agent_class.__name__}._extract_primary_capabilities() should return a list"
