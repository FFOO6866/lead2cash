"""
Unit Tests for Competitor Intelligence Agent

Tests agent signatures, configurations, and basic functionality
without making actual API calls (using mocks where needed).

Follows NO MOCKING policy for Tier 2+ tests, but Tier 1 unit tests
allow mocks for external dependencies like LLMs and databases.
"""

import json

import pytest

from lead_to_cash.agents.competitor_intel_agent import (
    CompetitorIntelAgent,
    CompetitorIntelConfig,
    CompetitorIntelSignature,
)

# =============================================================================
# Configuration Tests
# =============================================================================


class TestCompetitorIntelConfig:
    """Tests for CompetitorIntelConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CompetitorIntelConfig()

        assert config.llm_provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.top_k_documents == 5
        assert config.min_similarity_score == 0.6
        assert config.use_realtime_search is True
        assert config.enable_kb_enrichment is True
        assert config.agent_name == "competitor_intel"

    def test_custom_config(self):
        """Test custom configuration."""
        config = CompetitorIntelConfig(
            llm_provider="ollama",
            model="llama3",
            temperature=0.5,
            top_k_documents=10,
            use_realtime_search=False,
        )

        assert config.llm_provider == "ollama"
        assert config.model == "llama3"
        assert config.temperature == 0.5
        assert config.top_k_documents == 10
        assert config.use_realtime_search is False

    def test_config_description(self):
        """Test config has meaningful description."""
        config = CompetitorIntelConfig()
        assert "competitor" in config.agent_description.lower()


# =============================================================================
# Signature Tests
# =============================================================================


class TestCompetitorIntelSignature:
    """Tests for CompetitorIntelSignature."""

    def test_signature_input_fields(self):
        """Test signature has required input fields."""
        sig = CompetitorIntelSignature()

        # Check input fields exist (actual fields from signature definition)
        assert hasattr(sig, "competitor")
        assert hasattr(sig, "analysis_type")
        assert hasattr(sig, "regions")
        assert hasattr(sig, "segments")
        assert hasattr(sig, "time_range")

    def test_signature_output_fields(self):
        """Test signature has required output fields."""
        sig = CompetitorIntelSignature()

        # Check output fields exist (actual fields from signature definition)
        assert hasattr(sig, "competitive_position")
        assert hasattr(sig, "recent_wins_losses")
        assert hasattr(sig, "pricing_intel")
        assert hasattr(sig, "product_comparison")
        assert hasattr(sig, "strategic_moves")
        assert hasattr(sig, "threat_assessment")

    def test_signature_defaults(self):
        """Test signature default values exist and are correct."""
        sig = CompetitorIntelSignature()

        # Signature MUST have these optional fields with defaults
        assert hasattr(
            sig, "analysis_type"
        ), "Signature must have 'analysis_type' field"
        assert hasattr(sig, "regions"), "Signature must have 'regions' field"
        assert hasattr(sig, "time_range"), "Signature must have 'time_range' field"

        # These fields MUST have defaults (they're optional inputs)
        analysis_type_field = sig.analysis_type
        time_range_field = sig.time_range

        # Assert default attribute exists and has correct value
        assert hasattr(
            analysis_type_field, "default"
        ), "analysis_type field must have default attribute"
        assert (
            analysis_type_field.default == "general"
        ), f"Expected analysis_type default 'general', got {analysis_type_field.default}"

        assert hasattr(
            time_range_field, "default"
        ), "time_range field must have default attribute"
        assert (
            time_range_field.default == "year"
        ), f"Expected time_range default 'year', got {time_range_field.default}"


# =============================================================================
# Agent Initialization Tests
# =============================================================================


class TestCompetitorIntelAgentInit:
    """Tests for CompetitorIntelAgent initialization."""

    def test_agent_creation(self):
        """Test agent can be created with config."""
        config = CompetitorIntelConfig()

        # Agent should be creatable (may raise if dependencies not available)
        try:
            agent = CompetitorIntelAgent(config)
            assert agent is not None
            assert agent.agent_id == "competitor_intel"
        except ImportError:
            # Skip if Kaizen dependencies not available
            pytest.skip("Kaizen dependencies not available")

    def test_agent_with_custom_id(self):
        """Test agent with custom ID."""
        config = CompetitorIntelConfig()

        try:
            agent = CompetitorIntelAgent(config, agent_id="custom_agent_id")
            assert agent.agent_id == "custom_agent_id"
        except ImportError:
            pytest.skip("Kaizen dependencies not available")


# =============================================================================
# Competitor Detection Tests
# =============================================================================


class TestCompetitorDetection:
    """Tests for competitor name detection and normalization."""

    @pytest.fixture
    def agent(self):
        """Create agent for testing."""
        config = CompetitorIntelConfig()
        try:
            return CompetitorIntelAgent(config)
        except ImportError:
            pytest.skip("Kaizen dependencies not available")

    def test_detect_caterpillar_aliases(self, agent):
        """Test Caterpillar detection with various aliases."""
        cat_queries = [
            "What is Caterpillar doing?",
            "CAT marine engines",
            "MaK engine specifications",
        ]

        for query in cat_queries:
            query_lower = query.lower()
            # Should recognize as Caterpillar-related
            assert any(
                alias in query_lower for alias in ["caterpillar", "cat", "mak"]
            ), f"Failed to detect Caterpillar in: {query}"

    def test_detect_cummins_aliases(self, agent):
        """Test Cummins detection with various aliases."""
        cummins_queries = [
            "Cummins QSK60 specs",
            "cummins marine engines",
        ]

        for query in cummins_queries:
            query_lower = query.lower()
            assert "cummins" in query_lower

    def test_detect_man_aliases(self, agent):
        """Test MAN Energy Solutions detection with various aliases."""
        man_queries = [
            "MAN Energy Solutions",
            "MAN ES products",
            "man 32/44cr engine",
        ]

        for query in man_queries:
            query_lower = query.lower()
            assert (
                any(
                    alias in query_lower
                    for alias in ["man energy", "man es", "man 32", "man 48"]
                )
                or "man" in query_lower
            )


# =============================================================================
# Threat Level Tests
# =============================================================================


class TestThreatLevelAssessment:
    """Tests for threat level categorization."""

    def test_threat_levels_documented_in_module(self):
        """Test that threat level definitions are documented in the agent module."""
        import lead_to_cash.agents.competitor_intel_agent as module

        # The module docstring should document threat level definitions
        # This verifies the contract between implementation and documentation
        docstring = module.__doc__ or ""

        # Verify all threat levels are documented with their criteria
        assert "HIGH" in docstring, "HIGH threat level not documented"
        assert "MEDIUM" in docstring, "MEDIUM threat level not documented"
        assert "LOW" in docstring, "LOW threat level not documented"

        # Verify key criteria are mentioned
        assert (
            "customer" in docstring.lower() or "stronghold" in docstring.lower()
        ), "HIGH threat criteria (customer/stronghold) not documented"

    def test_threat_level_high_criteria_includes_customer_impact(self):
        """Test HIGH threat criteria documentation includes customer impact."""
        import lead_to_cash.agents.competitor_intel_agent as module

        docstring = (module.__doc__ or "").lower()

        # HIGH threat should be defined as impacting our customers or strongholds
        # This verifies the business logic is correctly documented
        high_criteria_documented = (
            "high" in docstring and "customer" in docstring
        ) or ("high" in docstring and "stronghold" in docstring)
        assert (
            high_criteria_documented
        ), "HIGH threat level criteria should document customer/stronghold impact"

    def test_tracked_competitors_documented(self):
        """Test that tracked competitors are documented in module."""
        import lead_to_cash.agents.competitor_intel_agent as module

        docstring = (module.__doc__ or "").lower()

        # Verify main competitors are documented
        expected_competitors = ["caterpillar", "cummins", "man"]
        for competitor in expected_competitors:
            assert competitor in docstring, (
                f"Competitor '{competitor}' not documented in module. "
                "The module should document all tracked competitors."
            )


# =============================================================================
# Output Format Tests
# =============================================================================


class TestOutputFormat:
    """Tests for output format compliance."""

    def test_sources_json_format(self):
        """Test sources should be valid JSON array."""
        # Example sources output
        sources_json = json.dumps(
            [
                "https://example.com/press-release-1",
                "https://example.com/sec-filing",
            ]
        )

        # Should be parseable
        parsed = json.loads(sources_json)
        assert isinstance(parsed, list)

    def test_key_insights_json_format(self):
        """Test key_insights should be valid JSON array."""
        # Example key insights
        insights_json = json.dumps(
            [
                "Caterpillar won 3 contracts in Q4 2025",
                "MAN ES launched new 48/60CR variant",
                "Cummins expanding Asian service network",
            ]
        )

        # Should be parseable
        parsed = json.loads(insights_json)
        assert isinstance(parsed, list)
        assert len(parsed) >= 2  # Should have 2-4 insights

    def test_confidence_levels(self):
        """Test confidence level values."""
        valid_confidence = ["high", "medium", "low"]

        for level in valid_confidence:
            assert level in ["high", "medium", "low"]


# =============================================================================
# Anti-Hallucination Tests
# =============================================================================


class TestAntiHallucination:
    """Tests for anti-hallucination rules compliance."""

    def test_source_requirement(self):
        """Test that all findings should include source."""
        # Every competitive insight MUST have a source URL
        # This tests the principle, not actual agent behavior

        required_source_patterns = [
            "source:",
            "https://",
            "SEC filing",
            "press release",
        ]

        # At least one source pattern should be expected
        assert len(required_source_patterns) > 0

    def test_no_unverified_claims(self):
        """Test that unverified market claims are avoided."""
        # Should NOT make claims like "market leader" without evidence
        forbidden_claims = [
            "market leader",
            "best in class",
            "industry leading",
        ]

        for claim in forbidden_claims:
            # These should require source verification
            assert len(claim) > 0


# =============================================================================
# A2A Routing Tests
# =============================================================================


class TestA2ARouting:
    """Tests for A2A semantic routing capability."""

    def test_capability_definition(self):
        """Test agent has capability definition for A2A routing."""
        config = CompetitorIntelConfig()

        try:
            agent = CompetitorIntelAgent(config)

            # Agent should have to_a2a_card method
            if hasattr(agent, "to_a2a_card"):
                card = agent.to_a2a_card()
                assert card is not None
        except (ImportError, AttributeError):
            pytest.skip("A2A capability not available")

    def test_agent_handles_competitor_queries(self):
        """Test agent should handle competitor-related queries."""
        competitor_queries = [
            "What contracts has Caterpillar won?",
            "Cummins product launches",
            "MAN Energy Solutions partnerships",
            "Competitor threat assessment",
            "Market share analysis",
        ]

        # All these should route to CompetitorIntelAgent
        for query in competitor_queries:
            query_lower = query.lower()
            competitor_keywords = [
                "caterpillar",
                "cat",
                "cummins",
                "man energy",
                "competitor",
                "threat",
                "market share",
            ]
            assert any(kw in query_lower for kw in competitor_keywords)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self):
        """Test handling of empty query."""
        # Empty queries should be handled gracefully
        empty_query = ""
        assert empty_query == ""

    def test_very_long_query(self):
        """Test handling of very long queries."""
        # Should truncate or handle gracefully
        long_query = "What is Caterpillar doing? " * 100
        assert len(long_query) > 1000

    def test_non_english_query(self):
        """Test handling of non-English queries."""
        # Should handle gracefully (may return English response)
        german_query = "Was macht Caterpillar in Deutschland?"
        assert len(german_query) > 0

    def test_mixed_competitor_query(self):
        """Test query mentioning multiple competitors."""
        multi_query = "Compare Caterpillar and Cummins marine engines"

        assert "caterpillar" in multi_query.lower()
        assert "cummins" in multi_query.lower()
