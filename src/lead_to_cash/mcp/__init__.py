"""
SAP Integration MCP Server Module

Production-ready MCP server that exposes SAP CPI operations as discoverable tools
for Kaizen agents. Routes ALL requests through SAP CPI as the single gateway.

Architecture:
    SAPIntegrationMCPServer (13 MCP Tools)
        ├── CECClient  ─┐
        ├── IPASClient ─┼─→ CPIClient ─→ SAP CPI ─→ Target Systems
        └── MS5Client  ─┘

    SAP CPI Routes:
        - CPI → SAP CEC (existing interface)
        - CPI → IPAS (NEW interface)
        - CPI → Cloud Connector → MS5/ECC (existing interface)

Features:
    - OAuth 2.0 token management with auto-refresh
    - Environment-aware (DEV/QA/PROD) configuration
    - Rate limiting and circuit breaker
    - Response caching
    - API key authentication
    - Prometheus metrics
    - Thread-safe idempotency for create operations
    - Comprehensive input validation

Tools (13 total):
    CEC (4):
        - cec_get_opportunity
        - cec_search_opportunities
        - cec_get_opportunities_by_account
        - cec_get_commercial_terms

    IPAS (4):
        - ipas_get_configuration
        - ipas_get_configurations_by_opportunity
        - ipas_get_product_catalog
        - ipas_validate_configuration

    MS5 (5):
        - sap_get_customer
        - sap_check_credit
        - sap_simulate_order
        - sap_create_order
        - sap_health_check

Usage:
    # Get MCP configuration for agents
    from lead_to_cash.mcp import get_sap_cpi_mcp_config

    workflow.add_node("IterativeLLMAgentNode", "agent", {
        "mcp_servers": [get_sap_cpi_mcp_config()],
        "auto_discover_tools": True,
    })

    # Use server directly
    from lead_to_cash.mcp import SAPCPIMCPServer

    async with SAPCPIMCPServer() as server:
        # CEC operation
        opp = await server.call_tool("cec_get_opportunity", {"opportunity_id": "OPP-123"})

        # IPAS operation
        cfg = await server.call_tool("ipas_get_configuration", {"config_id": "CFG-001"})

        # MS5 operation
        cust = await server.call_tool("sap_get_customer", {"customer_id": "1234"})

    # Run as standalone server
    python -m lead_to_cash.mcp.sap_cpi_server
"""

from lead_to_cash.mcp.sap_cpi_server import (
    SAPCPIMCPServer,
    ThreadSafeIdempotencyManager,
    ValidationError,
    get_sap_cpi_mcp_config,
    validate_config_id,
    validate_credit_control_area,
    validate_customer_id,
    validate_opportunity_id,
    validate_order_items,
    validate_sales_org,
)

__all__ = [
    # Main server class
    "SAPCPIMCPServer",
    # Configuration helper
    "get_sap_cpi_mcp_config",
    # Validation utilities
    "ValidationError",
    "validate_customer_id",
    "validate_credit_control_area",
    "validate_sales_org",
    "validate_order_items",
    "validate_opportunity_id",
    "validate_config_id",
    # Idempotency manager (for advanced use cases)
    "ThreadSafeIdempotencyManager",
]
