"""
Unit tests for SAP integration clients.

These tests verify:
1. Clients raise proper errors when credentials not configured
2. Data classes work correctly
3. Field mappings are accurate
"""

import os

import pytest

# =============================================================================
# CPI Client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cpi_client_raises_without_credentials():
    """Test CPI client raises ValueError when credentials not configured."""
    from lead_to_cash.integrations.cpi_client import CPIClient

    # Ensure no credentials
    client = CPIClient(client_id="", client_secret="")

    with pytest.raises(ValueError, match="CPI credentials not configured"):
        await client.connect()


@pytest.mark.asyncio
async def test_cpi_client_raises_without_token_url():
    """Test CPI client raises ValueError when token URL not configured."""
    from lead_to_cash.integrations.cpi_client import CPIClient

    # Has credentials but no token URL
    client = CPIClient(client_id="test", client_secret="test")
    client.token_url = ""

    with pytest.raises(ValueError, match="CPI token URL not configured"):
        await client.connect()


@pytest.mark.asyncio
async def test_cpi_client_raises_when_not_connected():
    """Test CPI client raises RuntimeError when calling iflow without connecting."""
    from lead_to_cash.integrations.cpi_client import CPIClient

    client = CPIClient()
    # Don't call connect()

    with pytest.raises(RuntimeError, match="CPI client not connected"):
        await client.call_iflow("TestFlow", {"test": "data"})


@pytest.mark.asyncio
async def test_cpi_client_health_check():
    """Test CPI client health check returns status."""
    from lead_to_cash.integrations.cpi_client import CPIClient

    client = CPIClient()
    health = await client.health_check()

    assert "status" in health
    assert "environment" in health
    assert "base_url" in health
    assert health["connected"] is False


# =============================================================================
# MS5 Client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_ms5_client_raises_when_not_connected():
    """Test MS5 client raises RuntimeError when not connected."""
    from lead_to_cash.integrations.ms5_client import MS5Client

    client = MS5Client()
    # Don't call connect()

    with pytest.raises(RuntimeError, match="MS5 client not connected"):
        await client.get_customer("1234")


@pytest.mark.asyncio
async def test_ms5_client_raises_when_not_connected_simulate():
    """Test MS5 client raises RuntimeError for simulate_order when not connected."""
    from lead_to_cash.integrations.ms5_client import MS5Client

    client = MS5Client()

    with pytest.raises(RuntimeError, match="MS5 client not connected"):
        await client.simulate_order({"header": {}, "items": []})


@pytest.mark.asyncio
async def test_ms5_client_raises_when_not_connected_create():
    """Test MS5 client raises RuntimeError for create_order when not connected."""
    from lead_to_cash.integrations.ms5_client import MS5Client

    client = MS5Client()

    with pytest.raises(RuntimeError, match="MS5 client not connected"):
        await client.create_order({"header": {}, "items": []})


@pytest.mark.asyncio
async def test_ms5_client_health_check():
    """Test MS5 client health check."""
    from lead_to_cash.integrations.ms5_client import MS5Client

    client = MS5Client()
    health = await client.health_check()

    assert "status" in health
    assert "cpi_status" in health
    assert health["status"] == "disconnected"


# =============================================================================
# CEC Client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cec_client_raises_without_cpi_configured():
    """Test CEC client raises ValueError when CPI not configured.

    CECClient routes all requests through CPIClient, so configuration
    errors come from the underlying CPI client.
    """
    from lead_to_cash.integrations.cec_client import CECClient
    from lead_to_cash.integrations.cpi_client import CPIClient

    # Create CPI client without configuration
    cpi = CPIClient()
    client = CECClient(cpi_client=cpi)

    with pytest.raises(ValueError, match="CPI.*not configured"):
        await client.connect()


@pytest.mark.asyncio
async def test_cec_client_uses_shared_cpi_client():
    """Test CEC client can use a shared CPI client instance."""
    from lead_to_cash.integrations.cec_client import CECClient
    from lead_to_cash.integrations.cpi_client import CPIClient

    # Create a shared CPI client
    shared_cpi = CPIClient()
    client = CECClient(cpi_client=shared_cpi)

    # Verify shared client is used
    assert client.cpi is shared_cpi


@pytest.mark.asyncio
async def test_cec_client_raises_when_not_connected():
    """Test CEC client raises RuntimeError when not connected."""
    from lead_to_cash.integrations.cec_client import CECClient

    client = CECClient()
    # Don't call connect()

    with pytest.raises(RuntimeError, match="CEC client not connected"):
        await client.get_opportunity("OPP-001")


@pytest.mark.asyncio
async def test_cec_opportunity_to_sap_mapping():
    """Test CEC opportunity to SAP field mapping."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    opp = Opportunity(
        opportunity_id="OPP-001",
        account_id="ACC-001",
        account_name="Test Customer",
        status="Open",
        expected_revenue=100000.0,
        currency="EUR",
        close_date=datetime.now(),
        products=[
            {"product_id": "PROD-001", "quantity": 10, "requested_date": "2026-01-20"}
        ],
    )

    sap_mapping = opp.to_sap_mapping()
    assert sap_mapping["BSTKD"] == "OPP-001"  # Customer PO
    assert sap_mapping["KUNNR"] == "000ACC-001"  # Sold-to (padded to 10 chars)
    assert sap_mapping["WAERK"] == "EUR"  # Currency
    assert len(sap_mapping["items"]) == 1


@pytest.mark.asyncio
async def test_cec_client_health_check():
    """Test CEC client health check."""
    from lead_to_cash.integrations.cec_client import CECClient

    client = CECClient()
    health = await client.health_check()

    assert "status" in health
    assert health["status"] == "disconnected"
    assert "cpi_status" in health
    assert "iflows" in health


@pytest.mark.asyncio
async def test_cec_opportunity_with_milestone_fields():
    """Test CEC opportunity dataclass with milestone payment fields (ADR-006)."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    opp = Opportunity(
        opportunity_id="OPP-2026-001",
        account_id="0022005992",
        account_name="ST Engineering",
        status="Won",
        expected_revenue=450000.0,
        currency="SGD",
        close_date=datetime(2026, 1, 15),
        start_date=datetime(2025, 9, 1),
        title="MTU 16V4000 M65L Marine Propulsion",
        win_probability=90,
        sales_type="OE_SALES",
        products=[],
        sap_order_id="1000025001",
        ipas_quote_id="IPAS-2025-0001",
    )

    # Verify milestone payment fields
    assert opp.sap_order_id == "1000025001"
    assert opp.ipas_quote_id == "IPAS-2025-0001"

    # Verify new standard fields
    assert opp.title == "MTU 16V4000 M65L Marine Propulsion"
    assert opp.win_probability == 90
    assert opp.sales_type == "OE_SALES"
    assert opp.start_date == datetime(2025, 9, 1)


@pytest.mark.asyncio
async def test_cec_opportunity_to_sap_mapping_with_milestone_fields():
    """Test CEC opportunity SAP mapping includes milestone payment fields (ADR-006)."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    opp = Opportunity(
        opportunity_id="OPP-2026-001",
        account_id="0022005992",
        account_name="ST Engineering",
        status="Won",
        expected_revenue=450000.0,
        currency="SGD",
        close_date=datetime(2026, 1, 15),
        products=[],
        sales_org="1000",
        distribution_channel="10",
        division="10",
        sap_order_id="1000025001",
        ipas_quote_id="IPAS-2025-0001",
    )

    sap_mapping = opp.to_sap_mapping()

    # Verify milestone payment fields in SAP mapping
    assert sap_mapping["VBELN_REF"] == "1000025001"
    assert sap_mapping["IPAS_QUOTE"] == "IPAS-2025-0001"

    # Verify other SAP fields
    assert sap_mapping["BSTKD"] == "OPP-2026-001"
    assert sap_mapping["KUNNR"] == "0022005992"
    assert sap_mapping["WAERK"] == "SGD"
    assert sap_mapping["VKORG"] == "1000"


@pytest.mark.asyncio
async def test_cec_opportunity_to_sap_mapping_with_none_milestone_fields():
    """Test CEC opportunity SAP mapping handles None milestone fields."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    # Open opportunity without SAP order yet
    opp = Opportunity(
        opportunity_id="OPP-2026-002",
        account_id="0022005992",
        account_name="ST Engineering",
        status="Open",
        expected_revenue=500000.0,
        currency="SGD",
        close_date=datetime(2026, 3, 15),
        products=[],
        sap_order_id=None,  # No SAP order yet
        ipas_quote_id="IPAS-2026-0001",  # Has IPAS quote
    )

    sap_mapping = opp.to_sap_mapping()

    # Verify None fields are converted to empty strings
    assert sap_mapping["VBELN_REF"] == ""
    assert sap_mapping["IPAS_QUOTE"] == "IPAS-2026-0001"


@pytest.mark.asyncio
async def test_cec_opportunity_to_dict():
    """Test CEC opportunity serialization to dictionary."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    close_date = datetime(2026, 1, 15)
    start_date = datetime(2025, 9, 1)

    opp = Opportunity(
        opportunity_id="OPP-2026-001",
        account_id="0022005992",
        account_name="ST Engineering",
        status="Won",
        expected_revenue=450000.0,
        currency="SGD",
        close_date=close_date,
        start_date=start_date,
        title="MTU 16V4000 M65L Marine Propulsion",
        win_probability=90,
        sales_type="OE_SALES",
        products=[{"product_id": "MTU-16V4000", "quantity": 2}],
        sap_order_id="1000025001",
        ipas_quote_id="IPAS-2025-0001",
    )

    opp_dict = opp.to_dict()

    # Verify all fields are serialized
    assert opp_dict["opportunity_id"] == "OPP-2026-001"
    assert opp_dict["account_id"] == "0022005992"
    assert opp_dict["account_name"] == "ST Engineering"
    assert opp_dict["status"] == "Won"
    assert opp_dict["expected_revenue"] == 450000.0
    assert opp_dict["currency"] == "SGD"
    assert opp_dict["close_date"] == close_date.isoformat()
    assert opp_dict["start_date"] == start_date.isoformat()
    assert opp_dict["title"] == "MTU 16V4000 M65L Marine Propulsion"
    assert opp_dict["win_probability"] == 90
    assert opp_dict["sales_type"] == "OE_SALES"
    assert len(opp_dict["products"]) == 1
    assert opp_dict["sap_order_id"] == "1000025001"
    assert opp_dict["ipas_quote_id"] == "IPAS-2025-0001"


@pytest.mark.asyncio
async def test_cec_opportunity_win_probability_values():
    """Test CEC opportunity win probability valid values."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    # Test all valid win probability values
    for prob in [10, 35, 65, 90]:
        opp = Opportunity(
            opportunity_id="OPP-001",
            account_id="ACC-001",
            account_name="Test",
            status="Open",
            expected_revenue=100000.0,
            currency="EUR",
            close_date=datetime.now(),
            products=[],
            win_probability=prob,
        )
        assert opp.win_probability == prob


@pytest.mark.asyncio
async def test_cec_opportunity_sales_type_values():
    """Test CEC opportunity sales type valid values."""
    from datetime import datetime

    from lead_to_cash.integrations.cec_client import Opportunity

    # Test OE_SALES
    opp_oe = Opportunity(
        opportunity_id="OPP-001",
        account_id="ACC-001",
        account_name="Test",
        status="Open",
        expected_revenue=100000.0,
        currency="EUR",
        close_date=datetime.now(),
        products=[],
        sales_type="OE_SALES",
    )
    assert opp_oe.sales_type == "OE_SALES"

    # Test SERVICE_SALES
    opp_service = Opportunity(
        opportunity_id="OPP-002",
        account_id="ACC-001",
        account_name="Test",
        status="Open",
        expected_revenue=50000.0,
        currency="EUR",
        close_date=datetime.now(),
        products=[],
        sales_type="SERVICE_SALES",
    )
    assert opp_service.sales_type == "SERVICE_SALES"


# =============================================================================
# IPAS Client Tests
# =============================================================================


@pytest.mark.asyncio
async def test_ipas_client_raises_without_cpi_configured():
    """Test IPAS client raises ValueError when CPI not configured.

    IPASClient routes all requests through CPIClient, so configuration
    errors come from the underlying CPI client.
    """
    from lead_to_cash.integrations.cpi_client import CPIClient
    from lead_to_cash.integrations.ipas_client import IPASClient

    # Create CPI client without configuration
    cpi = CPIClient()
    client = IPASClient(cpi_client=cpi)

    with pytest.raises(ValueError, match="CPI.*not configured"):
        await client.connect()


@pytest.mark.asyncio
async def test_ipas_client_uses_shared_cpi_client():
    """Test IPAS client can use a shared CPI client instance."""
    from lead_to_cash.integrations.cpi_client import CPIClient
    from lead_to_cash.integrations.ipas_client import IPASClient

    # Create a shared CPI client
    shared_cpi = CPIClient()
    client = IPASClient(cpi_client=shared_cpi)

    # Verify shared client is used
    assert client.cpi is shared_cpi


@pytest.mark.asyncio
async def test_ipas_client_raises_when_not_connected():
    """Test IPAS client raises RuntimeError when not connected."""
    from lead_to_cash.integrations.ipas_client import IPASClient

    client = IPASClient()
    # Don't call connect()

    with pytest.raises(RuntimeError, match="IPAS client not connected"):
        await client.get_configuration("CFG-001")


@pytest.mark.asyncio
async def test_ipas_configuration_materials():
    """Test IPAS configuration material extraction."""
    from lead_to_cash.integrations.ipas_client import ProductConfiguration

    config = ProductConfiguration(
        config_id="CFG-001",
        product_id="PROD-001",
        product_name="Test Product",
        variant="Standard",
        bom_items=[
            {"material": "MAT-001", "quantity": 1},
            {"material": "MAT-002", "quantity": 2},
        ],
        characteristics={"color": "Blue"},
    )

    materials = config.get_materials()
    assert "MAT-001" in materials
    assert "MAT-002" in materials
    assert len(materials) == 2


@pytest.mark.asyncio
async def test_ipas_client_health_check():
    """Test IPAS client health check."""
    from lead_to_cash.integrations.ipas_client import IPASClient

    client = IPASClient()
    health = await client.health_check()

    assert "status" in health
    assert health["status"] == "disconnected"
    assert "cpi_status" in health
    assert "interface_type" in health
    assert health["interface_type"] == "NEW"
    assert "iflows" in health


# =============================================================================
# Integration Tests (require SAP credentials - skip if not available)
# =============================================================================


def sap_credentials_available():
    """Check if SAP credentials are available for integration tests."""
    return bool(
        os.getenv("SAP_CPI_CLIENT_ID")
        and os.getenv("SAP_CPI_CLIENT_SECRET")
        and os.getenv("SAP_CPI_TOKEN_URL")
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    not sap_credentials_available(), reason="SAP credentials not configured"
)
async def test_cpi_client_real_connection():
    """Test CPI client with real credentials (integration test)."""
    from lead_to_cash.integrations.cpi_client import CPIClient

    async with CPIClient() as client:
        health = await client.health_check()
        assert health["connected"] is True
        assert health["token_valid"] is True
