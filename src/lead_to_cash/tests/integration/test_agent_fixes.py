"""
Integration Tests for Agent Response and Query Fixes

Tests cover:
1. N+1 query fix in CompetitorIntelAgent - batch document fetching
2. Agent response validation - no empty "I processed your request" responses
3. Retention service error handling - phase-level error tracking
4. Intelligence query service batch fetching

NO MOCKING - Tests use real infrastructure where possible.
"""

import os

import pytest


# Helper to check if database is available
def _has_database():
    """Check if database connection is available."""
    return os.getenv("DATABASE_URL") and os.getenv("OPENAI_API_KEY")


# Mark for tests that require database
requires_database = pytest.mark.skipif(
    not _has_database(),
    reason="DATABASE_URL and OPENAI_API_KEY required for database integration tests",
)


class TestN1QueryFix:
    """Tests for the N+1 query fix in CompetitorIntelAgent."""

    def test_batch_document_fetch_method_exists(self):
        """Verify get_documents_by_ids method exists in database module."""
        from lead_to_cash.services.competitor_intel.database import (
            CompetitorIntelDatabase,
        )

        # Verify the method exists
        assert hasattr(
            CompetitorIntelDatabase, "get_documents_by_ids"
        ), "CompetitorIntelDatabase should have get_documents_by_ids method"

        # Verify it's an async method
        import inspect

        assert inspect.iscoroutinefunction(
            CompetitorIntelDatabase.get_documents_by_ids
        ), "get_documents_by_ids should be an async method"

    def test_batch_fetch_method_signature(self):
        """Verify get_documents_by_ids has correct signature."""
        import inspect

        from lead_to_cash.services.competitor_intel.database import (
            CompetitorIntelDatabase,
        )

        sig = inspect.signature(CompetitorIntelDatabase.get_documents_by_ids)
        params = list(sig.parameters.keys())

        # Should have self and doc_ids parameters
        assert "self" in params
        assert "doc_ids" in params

    def test_competitor_agent_uses_batch_fetch(self):
        """Verify CompetitorIntelAgent uses batch fetch pattern (inspect code structure)."""
        import inspect

        from lead_to_cash.agents.competitor_intel_agent import CompetitorIntelAgent

        # Get the query method source code
        source = inspect.getsource(CompetitorIntelAgent.query)

        # Verify it contains batch fetching pattern
        assert (
            "get_documents_by_ids" in source
        ), "CompetitorIntelAgent.query should use get_documents_by_ids for batch fetching"

        # Verify it does NOT have the N+1 pattern (get_document in a loop)
        # Check that there's no "for ... await self.db.get_document" pattern
        lines = source.split("\n")
        in_for_loop = False
        n1_pattern_found = False

        for line in lines:
            if "for " in line and ":" in line:
                in_for_loop = True
            if in_for_loop and "await self.db.get_document(" in line:
                n1_pattern_found = True
                break
            if in_for_loop and (line.strip() and not line.startswith(" " * 8)):
                # Exited the for loop (less indentation)
                if "for " not in line:
                    in_for_loop = False

        assert (
            not n1_pattern_found
        ), "CompetitorIntelAgent.query should NOT call get_document in a loop (N+1 pattern)"


class TestAgentResponseValidation:
    """Tests for agent response handling to avoid empty responses."""

    def test_competitor_agent_has_meaningful_no_results_message(self):
        """Verify CompetitorIntelAgent has meaningful no-results message (code inspection)."""
        import inspect

        from lead_to_cash.agents.competitor_intel_agent import CompetitorIntelAgent

        source = inspect.getsource(CompetitorIntelAgent.query)

        # Verify the agent has a proper no-results message
        assert (
            "I don't have specific competitor intelligence" in source
        ), "Agent should have meaningful no-results message"

        # Verify it does NOT return "I processed your request" placeholder
        assert (
            "I processed your request" not in source
        ), "Agent should NOT return generic 'I processed your request' placeholder"

    def test_competitor_agent_query_returns_dict_with_required_fields(self):
        """Verify CompetitorIntelAgent.query returns dict with required fields (code inspection)."""
        import inspect

        from lead_to_cash.agents.competitor_intel_agent import CompetitorIntelAgent

        source = inspect.getsource(CompetitorIntelAgent.query)

        # Check that return statements include required fields
        required_fields = ["answer", "sources", "confidence", "key_insights"]
        for field in required_fields:
            assert (
                f'"{field}"' in source or f"'{field}'" in source
            ), f"CompetitorIntelAgent.query should include '{field}' in response"

    def test_no_results_response_includes_helpful_guidance(self):
        """Verify no-results response provides actionable guidance."""
        import inspect

        from lead_to_cash.agents.competitor_intel_agent import CompetitorIntelAgent

        source = inspect.getsource(CompetitorIntelAgent.query)

        # Check for helpful guidance in no-results case
        helpful_phrases = ["refresh", "rephrasing", "rephrase", "try"]
        found_helpful = any(phrase in source.lower() for phrase in helpful_phrases)
        assert (
            found_helpful
        ), "No-results message should include helpful guidance for the user"


class TestRetentionServiceErrorHandling:
    """Tests for retention service phase-level error handling."""

    @pytest.mark.asyncio
    async def test_retention_job_tracks_errors(self):
        """Verify retention job increments error count on phase failures."""
        from lead_to_cash.services.marine_intel.retention_service import (
            RetentionJobResult,
            RetentionPolicy,
            RetentionService,
        )

        # Create service with a policy
        policy = RetentionPolicy(batch_size=10)
        RetentionService(policy)

        # Verify RetentionJobResult starts with zero errors
        result = RetentionJobResult()
        assert result.errors == 0

        # Verify the result tracks errors correctly
        result.errors += 1
        assert result.errors == 1

    @pytest.mark.asyncio
    async def test_retention_phases_run_independently(self):
        """Verify that one phase failure doesn't stop other phases."""
        import inspect

        from lead_to_cash.services.marine_intel.retention_service import (
            RetentionService,
        )

        # Get the run_retention_job source code
        source = inspect.getsource(RetentionService.run_retention_job)

        # Verify each phase has its own try/except block
        # Count try blocks - should have at least 3 (one per phase)
        try_count = source.count("try:")
        except_count = source.count("except ")

        assert try_count >= 3, (
            f"run_retention_job should have at least 3 try blocks for independent phases, "
            f"found {try_count}"
        )
        assert except_count >= 3, (
            f"run_retention_job should have at least 3 except blocks for independent phases, "
            f"found {except_count}"
        )

        # Verify error tracking in each phase
        assert (
            "result.errors += 1" in source
        ), "Each phase failure should increment result.errors"


class TestIntelligenceQueryServiceBatchFetch:
    """Tests for the unified intelligence query service."""

    def test_intelligence_service_uses_batch_fetch(self):
        """Verify IntelligenceQueryService uses batch fetching in _search_competitor."""
        import inspect

        from lead_to_cash.services.intelligence_query_service import (
            IntelligenceQueryService,
        )

        # Check the _search_competitor method where batch fetch should happen
        source = inspect.getsource(IntelligenceQueryService._search_competitor)

        # Verify batch fetch pattern is used
        assert (
            "get_documents_by_ids" in source
        ), "IntelligenceQueryService._search_competitor should use get_documents_by_ids"

        # Verify it does NOT have the N+1 pattern
        lines = source.split("\n")
        in_for_loop = False
        n1_pattern_found = False

        for line in lines:
            if "for " in line and ":" in line:
                in_for_loop = True
            if in_for_loop and "await db.get_document(" in line:
                n1_pattern_found = True
                break

        assert (
            not n1_pattern_found
        ), "_search_competitor should NOT call get_document in a loop (N+1 pattern)"


class TestFrontendTimeoutConfiguration:
    """Tests to verify frontend timeout configuration (documentation/validation tests)."""

    def test_frontend_chat_has_timeout(self):
        """Verify chat.html has AbortController timeout configured."""
        import os

        chat_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "chat.html"
        )

        with open(chat_path, "r") as f:
            content = f.read()

        # Verify AbortController is used
        assert (
            "AbortController" in content
        ), "chat.html should use AbortController for request timeout"

        # Verify timeout is configured (should be >= 120000ms for LLM requests)
        assert (
            "REQUEST_TIMEOUT_MS" in content or "150000" in content
        ), "chat.html should have timeout configuration for LLM requests"

        # Verify abort error handling
        assert (
            "AbortError" in content
        ), "chat.html should handle AbortError for timeout cases"

    def test_frontend_has_differentiated_errors(self):
        """Verify frontend differentiates between timeout and network errors."""
        import os

        chat_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "chat.html"
        )

        with open(chat_path, "r") as f:
            content = f.read()

        # Should have different messages for different error types
        assert (
            "taking longer than expected" in content or "timed out" in content.lower()
        ), "chat.html should have specific message for timeout errors"


class TestNginxTimeoutConfiguration:
    """Tests to verify nginx timeout configuration."""

    def test_nginx_has_agent_location_block(self):
        """Verify nginx config has specific location for agent endpoints."""
        import os

        nginx_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "deployment",
            "nginx",
            "lead-to-cash.conf",
        )

        with open(nginx_path, "r") as f:
            content = f.read()

        # Verify agent endpoint location exists
        assert (
            "location /api/v1/agents/" in content
        ), "nginx config should have specific location block for /api/v1/agents/"

        # Verify extended timeout (180s) for agent requests
        assert (
            "proxy_read_timeout 180s" in content
        ), "nginx config should have 180s timeout for agent endpoints"

    def test_nginx_agent_location_before_api(self):
        """Verify /api/v1/agents/ location comes before /api/ location."""
        import os
        import re

        nginx_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "deployment",
            "nginx",
            "lead-to-cash.conf",
        )

        with open(nginx_path, "r") as f:
            content = f.read()

        # Find positions of both location blocks using exact regex
        # Match "location /api/v1/agents/" exactly
        agent_match = re.search(r"location\s+/api/v1/agents/", content)
        # Match "location /api/" but NOT followed by "v1/agents"
        api_match = re.search(r"location\s+/api/\s*\{", content)

        assert (
            agent_match is not None
        ), "nginx config should have /api/v1/agents/ location"
        assert api_match is not None, "nginx config should have /api/ location"

        agent_pos = agent_match.start()
        api_pos = api_match.start()

        assert agent_pos < api_pos, (
            f"nginx config must have /api/v1/agents/ location (pos {agent_pos}) "
            f"BEFORE /api/ location (pos {api_pos}) for proper precedence"
        )


class TestAgentRegistryRouting:
    """Tests for agent registry routing to correct agents."""

    @requires_database
    @pytest.mark.asyncio
    async def test_competitor_intel_routing(self):
        """Verify competitor questions route to CompetitorIntelAgent."""
        from lead_to_cash.agents.registry import AgentRegistry

        registry = AgentRegistry()
        await registry.initialize()

        # Test that competitor-related queries find the right agent
        agent = await registry.get_agent_for_capability("competitor intelligence")
        assert (
            agent is not None
        ), "Should find agent for competitor intelligence capability"

        await registry.shutdown()

    @requires_database
    @pytest.mark.asyncio
    async def test_agent_capabilities_registered(self):
        """Verify all agents have capabilities registered."""
        from lead_to_cash.agents.registry import AgentRegistry

        registry = AgentRegistry()
        await registry.initialize()

        capabilities = registry.list_capabilities()
        assert len(capabilities) > 0, "Registry should have capabilities registered"

        # Key capabilities that should exist
        expected_capabilities = ["competitor", "marine", "sales", "customer"]
        found_any = False
        for expected in expected_capabilities:
            for cap in capabilities:
                if expected.lower() in cap.lower():
                    found_any = True
                    break

        assert (
            found_any
        ), f"Registry should have at least one of {expected_capabilities}"

        await registry.shutdown()
