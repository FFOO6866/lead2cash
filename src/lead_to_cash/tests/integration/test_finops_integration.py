"""
FinanceOps Integration Tests

Tests the full FinanceOps flow using real data services (NO MOCKING), verifying:
- BillingCollectionsAgent with real CPISimulator data
- FinOpsDataService billing/collections retrieval
- Payment terms harmonization
- Role-based routing in registry
- Dynamic date calculations

These are Tier 2 integration tests following the NO MOCKING policy.
"""

import os
from datetime import date

import pytest
import pytest_asyncio

# Check for required environment variables
# Note: .env is loaded by conftest.py or pytest-dotenv plugin, NOT at module level.
# Loading .env at module level contaminates other test modules' skip conditions.
HAS_OPENAI_KEY = bool(os.getenv("OPENAI_API_KEY"))

# Skip marker for tests requiring OpenAI API
requires_openai = pytest.mark.skipif(
    not HAS_OPENAI_KEY,
    reason="OPENAI_API_KEY not set - required for LLM-based orchestration tests",
)

from lead_to_cash.agents.billing_collections_agent import (  # noqa: E402
    BillingCollectionsAgent,
)
from lead_to_cash.agents.finops_orchestrator_agent import (  # noqa: E402
    FinOpsOrchestratorAgent,
)
from lead_to_cash.integrations.cpi_simulator import CPISimulator  # noqa: E402
from lead_to_cash.services.financeops import FinOpsDataService  # noqa: E402
from lead_to_cash.services.financeops.models import BillingStatus  # noqa: E402
from lead_to_cash.services.financeops.payment_terms import (  # noqa: E402
    PaymentTermsHarmonizer,
)

# =============================================================================
# FinOpsDataService Integration Tests
# =============================================================================


@pytest_asyncio.fixture
async def finops_service():
    """Create FinOpsDataService with CPISimulator for integration testing."""
    simulator = CPISimulator()
    await simulator.connect()

    service = FinOpsDataService(cpi_client=simulator)
    await service.connect()

    yield service

    await service.disconnect()
    await simulator.disconnect()


@pytest.mark.asyncio
async def test_finops_service_get_summary_counts(finops_service):
    """Test getting billing/collections summary counts."""
    summary = await finops_service.get_summary_counts()

    # Should have counts
    assert summary.billing_count >= 0
    assert summary.collections_count >= 0
    assert summary.overdue_count >= 0

    # Should have amounts
    assert summary.billing_amount >= 0
    assert summary.collections_amount >= 0

    # Should have a date
    assert summary.as_of_date == date.today()


@pytest.mark.asyncio
async def test_finops_service_get_billing_items(finops_service):
    """Test getting billing items."""
    items = await finops_service.get_billing_items()

    # Should have items from simulator
    assert len(items) > 0

    # Check item structure
    item = items[0]
    assert item.document_number is not None
    assert item.customer_id is not None
    assert item.customer_name is not None
    assert item.total_amount > 0
    assert item.currency in ["SGD", "USD", "EUR", "AUD"]
    assert item.status is not None


@pytest.mark.asyncio
async def test_finops_service_get_billing_items_filtered_by_customer(finops_service):
    """Test filtering billing items by customer."""
    # Get items for ST Engineering
    items = await finops_service.get_billing_items(customer_id="0022005992")

    # Should have ST Engineering items
    for item in items:
        assert item.customer_id == "0022005992"
        assert "ST Engineering" in item.customer_name


@pytest.mark.asyncio
async def test_finops_service_get_collections_items(finops_service):
    """Test getting collections items."""
    items = await finops_service.get_collections_items()

    # Should have items
    assert len(items) > 0

    # All items should be in collection-relevant status
    for item in items:
        assert item.status in [
            BillingStatus.PENDING_COLLECTION,
            BillingStatus.PARTIALLY_PAID,
            BillingStatus.OVERDUE,
        ]


@pytest.mark.asyncio
async def test_finops_service_get_aging_buckets(finops_service):
    """Test getting aging bucket breakdown."""
    buckets = await finops_service.get_aging_buckets()

    # Should have all bucket categories
    # 4 aging buckets: CURRENT (green), 0-30 (amber), 30-45 (orange), 45+ (red)
    assert "CURRENT" in buckets
    assert "0-30" in buckets
    assert "30-45" in buckets
    assert "45+" in buckets

    # Each bucket should have count and amount
    for bucket_name, bucket_data in buckets.items():
        assert "count" in bucket_data
        assert "amount" in bucket_data
        assert bucket_data["count"] >= 0
        assert bucket_data["amount"] >= 0


@pytest.mark.asyncio
async def test_finops_service_dynamic_dates(finops_service):
    """Test that billing documents have dynamic dates relative to today."""
    items = await finops_service.get_billing_items()

    today = date.today()

    for item in items:
        # Document date should be in the past
        assert item.document_date <= today, (
            f"Document date {item.document_date} should be in past"
        )

        # Due date or next_action_date should exist
        if item.next_action_date:
            # Days to action should match the date difference
            expected_days = (item.next_action_date - today).days
            assert item.days_to_action == expected_days


# =============================================================================
# PaymentTermsHarmonizer Integration Tests
# =============================================================================


class TestPaymentTermsHarmonizer:
    """Test payment terms parsing with real patterns."""

    def test_parse_simple_net_terms(self):
        """Test parsing simple net payment terms."""
        harmonizer = PaymentTermsHarmonizer()
        result = harmonizer.parse("90 days after date of invoice")

        assert result.raw_text == "90 days after date of invoice"
        assert result.confidence > 0.5

    def test_parse_advance_payment_terms(self):
        """Test parsing advance payment terms."""
        harmonizer = PaymentTermsHarmonizer()
        result = harmonizer.parse(
            "20% advance payment by TT within 30 days upon invoice\n"
            "Balance 80% utilise credit line payable within 60 days after invoice"
        )

        assert len(result.milestones) >= 1
        assert result.total_advance_pct > 0 or result.total_balance_pct > 0

    def test_parse_lc_terms(self):
        """Test parsing L/C payment terms."""
        harmonizer = PaymentTermsHarmonizer()
        result = harmonizer.parse("100% Irrevocable L/C at Sight")

        assert result.has_lc is True

    def test_parse_milestone_terms(self):
        """Test parsing milestone-based payment terms."""
        harmonizer = PaymentTermsHarmonizer()
        result = harmonizer.parse(
            "30% DP by TT within 30 days upon PO, "
            "70% by Irrevocable L/C 6 weeks before shipment"
        )

        assert result.has_lc is True
        assert len(result.milestones) >= 1


# =============================================================================
# BillingCollectionsAgent Integration Tests
# =============================================================================


@pytest_asyncio.fixture
async def billing_agent():
    """Create BillingCollectionsAgent with CPISimulator for integration testing."""
    simulator = CPISimulator()
    await simulator.connect()

    service = FinOpsDataService(cpi_client=simulator)
    await service.connect()

    from lead_to_cash.services.financeops.escalation_service import EscalationService

    escalation_service = EscalationService(data_service=service)
    await escalation_service.connect()

    agent = BillingCollectionsAgent()
    agent._data_service = service
    agent._escalation_service = escalation_service
    agent._connected = True

    yield agent

    await service.disconnect()
    await simulator.disconnect()


@pytest.mark.asyncio
async def test_billing_agent_get_billing_summary(billing_agent):
    """Test agent getting billing summary."""
    summary = await billing_agent.get_billing_summary()

    assert isinstance(summary, dict)
    assert "billing_count" in summary
    assert "collections_count" in summary


@pytest.mark.asyncio
async def test_billing_agent_get_billing_items(billing_agent):
    """Test agent getting billing items."""
    items = await billing_agent.get_billing_items()

    assert isinstance(items, list)
    assert len(items) > 0


@pytest.mark.asyncio
async def test_billing_agent_get_collections_items(billing_agent):
    """Test agent getting collections items."""
    items = await billing_agent.get_collections_items()

    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_billing_agent_capabilities(billing_agent):
    """Test agent A2A capabilities."""
    capabilities = billing_agent.get_capabilities()

    assert len(capabilities) == 6

    cap_names = [c.name for c in capabilities]
    assert "billing_tracking" in cap_names
    assert "collections_monitoring" in cap_names
    assert "payment_terms_analysis" in cap_names
    assert "escalation_monitoring" in cap_names

    # All capabilities should be in accounts_receivable domain
    for cap in capabilities:
        assert cap.domain == "accounts_receivable"


# =============================================================================
# FinOpsOrchestratorAgent Integration Tests
# =============================================================================


@pytest_asyncio.fixture
async def finops_orchestrator():
    """Create FinOpsOrchestratorAgent for integration testing."""
    agent = FinOpsOrchestratorAgent()
    await agent.connect()

    yield agent

    await agent.disconnect()


@requires_openai
@pytest.mark.asyncio
async def test_finops_orchestrator_process_billing_request(finops_orchestrator):
    """Test orchestrator processing billing request."""
    result = await finops_orchestrator.process_request(
        request="Show me pending billing items"
    )

    assert "response" in result
    assert "data" in result
    assert "task_type" in result
    assert result["task_type"] == "billing_items"


@requires_openai
@pytest.mark.asyncio
async def test_finops_orchestrator_process_collections_request(finops_orchestrator):
    """Test orchestrator processing collections request."""
    result = await finops_orchestrator.process_request(
        request="Show me all overdue collections"
    )

    assert "response" in result
    assert "data" in result
    assert result["task_type"] == "collections_items"


@requires_openai
@pytest.mark.asyncio
async def test_finops_orchestrator_process_summary_request(finops_orchestrator):
    """Test orchestrator processing summary request."""
    result = await finops_orchestrator.process_request(
        request="Give me a billing summary"
    )

    assert "response" in result
    assert "data" in result


# =============================================================================
# Registry Role-Based Routing Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_registry_has_finops_orchestrator():
    """Test that registry has finops orchestrator after initialization."""
    from lead_to_cash.agents.registry import AgentRegistry

    registry = AgentRegistry(enable_query_understanding=False)
    await registry.initialize()

    # Should have finops orchestrator
    finops_orch = registry.get_finops_orchestrator()
    assert finops_orch is not None

    # Should have sales ops orchestrator
    sales_orch = registry.get_orchestrator()
    assert sales_orch is not None


@pytest.mark.asyncio
async def test_registry_role_based_orchestrator_selection():
    """Test registry selects correct orchestrator based on role."""
    from lead_to_cash.agents.registry import AgentRegistry

    registry = AgentRegistry(enable_query_understanding=False)
    await registry.initialize()

    # For financeops user, should return finops orchestrator
    finops_orch = registry.get_orchestrator_for_role(["financeops"])
    assert finops_orch is not None
    assert finops_orch.__class__.__name__ == "FinOpsOrchestratorAgent"

    # For sales_ops user, should return sales ops orchestrator
    sales_orch = registry.get_orchestrator_for_role(["sales_ops"])
    assert sales_orch is not None
    assert sales_orch.__class__.__name__ == "SalesOpsAgent"

    # For user with no matching role, should return default (sales ops)
    default_orch = registry.get_orchestrator_for_role(["viewer"])
    assert default_orch is not None
    assert default_orch.__class__.__name__ == "SalesOpsAgent"


@pytest.mark.asyncio
async def test_registry_has_billing_collections_agent():
    """Test that registry has BillingCollectionsAgent registered."""
    from lead_to_cash.agents.registry import AgentRegistry

    registry = AgentRegistry(enable_query_understanding=False)
    await registry.initialize()

    # Should have billing_collections agent
    agent = registry.get_agent("billing_collections")
    assert agent is not None
    assert agent.__class__.__name__ == "BillingCollectionsAgent"
