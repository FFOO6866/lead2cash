"""
Unit Tests for Billing & Collections Agent

Tests agent signatures, configurations, and basic functionality
without making actual API calls (using mocks where needed).

Follows NO MOCKING policy for Tier 2+ tests, but Tier 1 unit tests
allow mocks for external dependencies.
"""

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lead_to_cash.agents.billing_collections_agent import (
    BillingCollectionsAgent,
    BillingCollectionsAgentSignature,
    BillingCollectionsConfig,
)
from lead_to_cash.agents.signatures import BillingCollectionsSignature

# =============================================================================
# Configuration Tests
# =============================================================================


class TestBillingCollectionsConfig:
    """Tests for BillingCollectionsConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BillingCollectionsConfig()

        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.agent_name == "BillingCollectionsAgent"
        assert config.agent_version == "1.0.0"

    def test_custom_config(self):
        """Test custom configuration."""
        config = BillingCollectionsConfig(
            model="gpt-4o",
            temperature=0.2,
            max_tokens=2048,
        )

        assert config.model == "gpt-4o"
        assert config.temperature == 0.2
        assert config.max_tokens == 2048

    def test_config_is_dataclass(self):
        """Test config is a proper dataclass."""
        config = BillingCollectionsConfig()

        # Should be convertible to dict
        config_dict = asdict(config)
        assert isinstance(config_dict, dict)
        assert "model" in config_dict
        assert "agent_name" in config_dict


# =============================================================================
# Signature Tests
# =============================================================================


class TestBillingCollectionsAgentSignature:
    """Tests for BillingCollectionsAgentSignature (internal Kaizen signature)."""

    def test_signature_input_fields(self):
        """Test signature has required input fields."""
        sig = BillingCollectionsAgentSignature()

        # Check input fields exist
        assert hasattr(sig, "customer_id")
        assert hasattr(sig, "document_number")
        assert hasattr(sig, "query_type")
        assert hasattr(sig, "status_filter")

    def test_signature_output_fields(self):
        """Test signature has required output fields."""
        sig = BillingCollectionsAgentSignature()

        # Check output fields exist
        assert hasattr(sig, "billing_items")
        assert hasattr(sig, "collections_items")
        assert hasattr(sig, "summary")
        assert hasattr(sig, "aging_buckets")
        assert hasattr(sig, "payment_terms")
        assert hasattr(sig, "tool_calls")

    def test_signature_defaults(self):
        """Test signature default values exist (InputField objects)."""
        sig = BillingCollectionsAgentSignature()

        # Signature fields are InputField objects in Kaizen
        # Check they have default values defined
        assert sig.customer_id.default == ""
        assert sig.document_number.default == ""
        assert sig.query_type.default == "summary"
        assert sig.status_filter.default == ""


class TestBillingCollectionsSignature:
    """Tests for BillingCollectionsSignature (A2A routing signature)."""

    def test_signature_input_fields(self):
        """Test A2A signature has required input fields."""
        sig = BillingCollectionsSignature()

        assert hasattr(sig, "customer_id")
        assert hasattr(sig, "document_number")
        assert hasattr(sig, "query_type")
        assert hasattr(sig, "status_filter")

    def test_signature_output_fields(self):
        """Test A2A signature has required output fields."""
        sig = BillingCollectionsSignature()

        assert hasattr(sig, "billing_items")
        assert hasattr(sig, "collections_items")
        assert hasattr(sig, "summary")
        assert hasattr(sig, "aging_buckets")
        assert hasattr(sig, "payment_terms")
        assert hasattr(sig, "tool_calls")


# =============================================================================
# Agent Instantiation Tests
# =============================================================================


class TestBillingCollectionsAgentInstantiation:
    """Tests for BillingCollectionsAgent instantiation."""

    def test_agent_instantiation_default_config(self):
        """Test agent can be instantiated with default config."""
        agent = BillingCollectionsAgent()

        assert agent is not None
        assert agent.config is not None
        # BaseAgent converts our config to BaseAgentConfig, check model
        assert agent.config.model == "claude-sonnet-4-20250514"

    def test_agent_instantiation_custom_config(self):
        """Test agent can be instantiated with custom config."""
        config = BillingCollectionsConfig(
            model="gpt-4o",
            temperature=0.1,
        )
        agent = BillingCollectionsAgent(config=config)

        assert agent.config.model == "gpt-4o"
        assert agent.config.temperature == 0.1

    def test_agent_has_signature_reference(self):
        """Test agent has class-level SIGNATURE reference."""
        agent = BillingCollectionsAgent()

        assert hasattr(agent, "SIGNATURE")
        assert agent.SIGNATURE == BillingCollectionsSignature

    def test_agent_get_signature_method(self):
        """Test agent get_signature class method."""
        sig_class = BillingCollectionsAgent.get_signature()

        assert sig_class == BillingCollectionsSignature


# =============================================================================
# A2A Capability Tests
# =============================================================================


class TestBillingCollectionsAgentCapabilities:
    """Tests for A2A capabilities."""

    def test_agent_has_capabilities(self):
        """Test agent provides A2A capabilities."""
        agent = BillingCollectionsAgent()
        capabilities = agent.get_capabilities()

        assert capabilities is not None
        assert len(capabilities) >= 1

    def test_capabilities_have_correct_domain(self):
        """Test capabilities use accounts_receivable domain."""
        agent = BillingCollectionsAgent()
        capabilities = agent.get_capabilities()

        for cap in capabilities:
            assert cap.domain == "accounts_receivable"

    def test_capabilities_cover_key_functions(self):
        """Test capabilities cover billing, collections, and payment terms."""
        agent = BillingCollectionsAgent()
        capabilities = agent.get_capabilities()

        cap_names = [cap.name for cap in capabilities]

        assert "billing_tracking" in cap_names
        assert "collections_monitoring" in cap_names
        assert "payment_terms_analysis" in cap_names

    def test_capabilities_have_keywords(self):
        """Test capabilities have relevant keywords for routing."""
        agent = BillingCollectionsAgent()
        capabilities = agent.get_capabilities()

        # Flatten all keywords
        all_keywords = []
        for cap in capabilities:
            all_keywords.extend(cap.keywords)

        # Check key routing keywords exist
        assert "billing" in all_keywords
        assert "invoice" in all_keywords
        assert "collections" in all_keywords
        assert "overdue" in all_keywords
        assert "payment terms" in all_keywords


# =============================================================================
# Run Method Tests (Synchronous A2A Interface)
# =============================================================================


class TestBillingCollectionsAgentRun:
    """Tests for synchronous run method (A2A router compatibility)."""

    @pytest.fixture
    def mock_data_service(self):
        """Mock the FinOpsDataService."""
        with patch(
            "lead_to_cash.agents.billing_collections_agent.FinOpsDataService"
        ) as mock:
            service_instance = MagicMock()
            service_instance.connect = AsyncMock()
            service_instance.disconnect = AsyncMock()
            service_instance.get_summary_counts = AsyncMock(
                return_value=MagicMock(
                    to_dict=lambda: {
                        "billing_count": 3,
                        "collections_count": 5,
                        "overdue_count": 2,
                    }
                )
            )
            service_instance.get_billing_items = AsyncMock(return_value=[])
            service_instance.get_collections_items = AsyncMock(return_value=[])
            service_instance.get_aging_buckets = AsyncMock(return_value={})
            service_instance.get_payment_terms = AsyncMock(return_value={})
            mock.return_value = service_instance
            yield mock

    def test_run_returns_standardized_response(self, mock_data_service):
        """Test run method returns standardized response structure."""
        agent = BillingCollectionsAgent()
        result = agent.run(task="Show billing summary", query_type="summary")

        assert "success" in result
        assert "agent_id" in result
        assert "result_data" in result
        assert "error_message" in result
        assert "metadata" in result

    def test_run_parses_task_for_billing(self, mock_data_service):
        """Test run method parses task string for billing queries."""
        agent = BillingCollectionsAgent()
        result = agent.run(task="Show billing items pending")

        assert result["success"] is True
        assert result["metadata"]["query_type"] == "billing"

    def test_run_parses_task_for_collections(self, mock_data_service):
        """Test run method parses task string for collections queries."""
        agent = BillingCollectionsAgent()
        # Use query without "invoice" to avoid billing keyword match
        result = agent.run(task="Show overdue items and aging")

        assert result["success"] is True
        assert result["metadata"]["query_type"] == "collections"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestBillingCollectionsAgentFactory:
    """Tests for factory function."""

    def test_create_billing_collections_agent(self):
        """Test factory function creates agent."""
        from lead_to_cash.agents.billing_collections_agent import (
            create_billing_collections_agent,
        )

        agent = create_billing_collections_agent()

        assert agent is not None
        assert isinstance(agent, BillingCollectionsAgent)

    def test_create_billing_collections_agent_with_config(self):
        """Test factory function accepts config."""
        from lead_to_cash.agents.billing_collections_agent import (
            create_billing_collections_agent,
        )

        config = BillingCollectionsConfig(model="gpt-4o")
        agent = create_billing_collections_agent(config=config)

        assert agent.config.model == "gpt-4o"
