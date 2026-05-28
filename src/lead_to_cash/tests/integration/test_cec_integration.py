"""
CEC Integration Tests

Tests the full CEC client flow using the CPI Simulator, verifying:
- Opportunity retrieval with all fields including milestone payment fields (ADR-006)
- Search functionality
- Account-based opportunity queries
- SAP field mapping
"""

import pytest
import pytest_asyncio

from lead_to_cash.integrations.cec_client import CECClient
from lead_to_cash.integrations.cpi_simulator import CPISimulator

# =============================================================================
# CEC Client with CPI Simulator Integration Tests
# =============================================================================


@pytest_asyncio.fixture
async def cec_client():
    """Create CEC client with CPI Simulator for integration testing."""
    simulator = CPISimulator()
    await simulator.connect()

    client = CECClient(cpi_client=simulator)
    await client.connect()

    yield client

    await client.disconnect()
    await simulator.disconnect()


@pytest.mark.asyncio
async def test_cec_get_opportunities_by_account_with_all_fields(cec_client):
    """Test getting opportunities for ST Engineering with all fields including ADR-006."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    # Should have opportunities for ST Engineering
    assert len(opps) > 0

    # Check first opportunity has all fields
    opp = opps[0]
    assert opp.opportunity_id is not None
    assert opp.account_id == "0022005992"
    assert opp.account_name == "ST Engineering"
    assert opp.status in ["Won", "Lost", "Open", "Qualified"]
    assert opp.expected_revenue > 0
    assert opp.currency == "SGD"

    # Check ADR-006 fields are present
    assert opp.title is not None
    assert opp.start_date is not None
    assert opp.win_probability in [10, 35, 65, 90]
    assert opp.sales_type in ["OE_SALES", "SERVICE_SALES"]


@pytest.mark.asyncio
async def test_cec_won_opportunities_have_sap_order_id(cec_client):
    """Test that won opportunities have SAP order IDs (ADR-006)."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    won_opps = [o for o in opps if o.status == "Won"]
    assert len(won_opps) > 0

    for opp in won_opps:
        # Won deals should have SAP order ID
        assert (
            opp.sap_order_id is not None
        ), f"Won deal {opp.opportunity_id} missing sap_order_id"
        # Should also have IPAS quote
        assert (
            opp.ipas_quote_id is not None
        ), f"Won deal {opp.opportunity_id} missing ipas_quote_id"


@pytest.mark.asyncio
async def test_cec_open_opportunities_have_ipas_quote_no_sap_order(cec_client):
    """Test that open opportunities have IPAS quotes but no SAP orders yet."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    open_opps = [o for o in opps if o.status == "Open"]
    assert len(open_opps) > 0

    for opp in open_opps:
        # Open deals should NOT have SAP order ID yet
        assert (
            opp.sap_order_id is None
        ), f"Open deal {opp.opportunity_id} should not have sap_order_id"
        # But should have IPAS quote
        assert (
            opp.ipas_quote_id is not None
        ), f"Open deal {opp.opportunity_id} missing ipas_quote_id"


@pytest.mark.asyncio
async def test_cec_lost_opportunities_have_ipas_quote_no_sap_order(cec_client):
    """Test that lost opportunities have IPAS quotes but no SAP orders."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    lost_opps = [o for o in opps if o.status == "Lost"]
    assert len(lost_opps) > 0

    for opp in lost_opps:
        # Lost deals should NOT have SAP order ID
        assert (
            opp.sap_order_id is None
        ), f"Lost deal {opp.opportunity_id} should not have sap_order_id"
        # But should have IPAS quote (quoted but lost)
        assert (
            opp.ipas_quote_id is not None
        ), f"Lost deal {opp.opportunity_id} missing ipas_quote_id"


@pytest.mark.asyncio
async def test_cec_get_single_opportunity_by_id(cec_client):
    """Test getting a single opportunity by ID."""
    # Get a known opportunity from simulated data
    opp = await cec_client.get_opportunity("OPP-2026-001")

    assert opp.opportunity_id == "OPP-2026-001"
    assert opp.title is not None
    # ADR-006 fields
    assert opp.ipas_quote_id is not None


@pytest.mark.asyncio
async def test_cec_search_opportunities(cec_client):
    """Test searching opportunities by query."""
    results = await cec_client.search_opportunities("ST Engineering")

    assert len(results) > 0
    for opp in results:
        # All results should be from ST Engineering
        assert (
            "ST Engineering" in opp.account_name or "engineering" in opp.title.lower()
        )


@pytest.mark.asyncio
async def test_cec_search_opportunities_by_status(cec_client):
    """Test searching opportunities filtered by status."""
    results = await cec_client.search_opportunities("", status="Open")

    # All results should have Open status
    for opp in results:
        assert opp.status == "Open"


@pytest.mark.asyncio
async def test_cec_opportunity_sap_mapping_integration(cec_client):
    """Test SAP mapping for retrieved opportunity includes ADR-006 fields."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    won_opp = next((o for o in opps if o.status == "Won"), None)
    assert won_opp is not None

    sap_mapping = won_opp.to_sap_mapping()

    # Verify ADR-006 milestone payment fields in mapping
    assert "VBELN_REF" in sap_mapping
    assert "IPAS_QUOTE" in sap_mapping
    assert sap_mapping["VBELN_REF"] != ""  # Won deal should have order
    assert sap_mapping["IPAS_QUOTE"] != ""  # Won deal should have quote


@pytest.mark.asyncio
async def test_cec_batam_fast_ferry_opportunities(cec_client):
    """Test getting opportunities for Batam Fast Ferry."""
    opps = await cec_client.get_opportunities_by_account("0000100001")

    assert len(opps) > 0

    # Check a mix of won/lost/open
    statuses = {o.status for o in opps}
    assert "Won" in statuses or "Open" in statuses

    # Check currency is SGD
    for opp in opps:
        assert opp.currency == "SGD"


@pytest.mark.asyncio
async def test_cec_maersk_opportunities_eur_currency(cec_client):
    """Test getting opportunities for Maersk with EUR currency."""
    opps = await cec_client.get_opportunities_by_account("0000100002")

    assert len(opps) > 0

    # Maersk uses EUR
    for opp in opps:
        assert opp.currency == "EUR"


@pytest.mark.asyncio
async def test_cec_clls_power_system_opportunities(cec_client):
    """Test getting opportunities for CLLS Power System."""
    opps = await cec_client.get_opportunities_by_account("0021000090")

    assert len(opps) > 0

    # Check account name
    for opp in opps:
        assert "CLLS" in opp.account_name


@pytest.mark.asyncio
async def test_cec_opportunity_to_dict_serialization(cec_client):
    """Test opportunity serialization to dictionary."""
    opps = await cec_client.get_opportunities_by_account("0022005992")
    opp = opps[0]

    opp_dict = opp.to_dict()

    # Verify all ADR-006 fields are in dictionary
    assert "sap_order_id" in opp_dict
    assert "ipas_quote_id" in opp_dict
    assert "title" in opp_dict
    assert "start_date" in opp_dict
    assert "win_probability" in opp_dict
    assert "sales_type" in opp_dict


@pytest.mark.asyncio
async def test_cec_health_check_with_simulator(cec_client):
    """Test CEC client health check returns connected status."""
    health = await cec_client.health_check()

    assert health["status"] == "connected"
    assert "cpi_status" in health
    assert health["cpi_status"]["status"] == "healthy"
    assert health["cpi_status"]["mode"] == "simulation"


@pytest.mark.asyncio
async def test_cec_kyp_metrics_calculation(cec_client):
    """Test calculating KYP metrics from CEC opportunities."""
    opps = await cec_client.get_opportunities_by_account("0022005992")

    # Calculate KYP metrics
    won_deals = [o for o in opps if o.status == "Won"]
    lost_deals = [o for o in opps if o.status == "Lost"]
    open_deals = [o for o in opps if o.status == "Open"]

    lifetime_value = sum(o.expected_revenue for o in won_deals)
    open_pipeline_value = sum(o.expected_revenue for o in open_deals)

    # ST Engineering should have significant lifetime value
    assert len(won_deals) >= 10
    assert len(lost_deals) >= 2
    assert len(open_deals) >= 1
    assert lifetime_value > 2_000_000  # > 2M SGD
    assert open_pipeline_value > 0
