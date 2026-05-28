"""
Unit Tests for SAP Integration MCP Server

Tests server initialization, input validation, idempotency manager,
tool schemas, and error handling for all 13 tools (CEC: 4, IPAS: 4, MS5: 5).

Tier 1 - Unit Tests: Mocking is allowed for external dependencies.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

# =============================================================================
# Input Validation Tests - Customer ID
# =============================================================================


class TestValidateCustomerId:
    """Tests for customer_id validation."""

    def test_valid_numeric_id(self):
        """Valid numeric ID should be zero-padded to 10 chars."""
        assert validate_customer_id("1234") == "0000001234"
        assert validate_customer_id("1") == "0000000001"

    def test_valid_alphanumeric_id(self):
        """Valid alphanumeric ID should be zero-padded."""
        assert validate_customer_id("ABC123") == "0000ABC123"

    def test_valid_10_char_id(self):
        """10-char ID should pass through unchanged."""
        assert validate_customer_id("1234567890") == "1234567890"
        assert validate_customer_id("ABCDEFGH12") == "ABCDEFGH12"

    def test_empty_id_raises_error(self):
        """Empty ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_customer_id("")
        assert exc_info.value.field == "customer_id"
        assert "required" in exc_info.value.message

    def test_too_long_id_raises_error(self):
        """ID longer than 10 chars should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_customer_id("12345678901")
        assert exc_info.value.field == "customer_id"
        assert "1-10 characters" in exc_info.value.message

    def test_special_chars_raise_error(self):
        """Special characters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_customer_id("123-456")
        assert exc_info.value.field == "customer_id"
        assert "alphanumeric" in exc_info.value.message

    def test_spaces_raise_error(self):
        """Spaces should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_customer_id("123 456")
        assert "alphanumeric" in exc_info.value.message


class TestValidateCreditControlArea:
    """Tests for credit_control_area validation."""

    def test_valid_cca(self):
        """Valid 4-char CCA should be uppercased."""
        assert validate_credit_control_area("US01") == "US01"
        assert validate_credit_control_area("eu01") == "EU01"

    def test_empty_cca_returns_empty(self):
        """Empty CCA should return empty (optional field)."""
        assert validate_credit_control_area("") == ""

    def test_wrong_length_raises_error(self):
        """CCA not exactly 4 chars should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_credit_control_area("US")
        assert exc_info.value.field == "credit_control_area"
        assert "exactly 4 characters" in exc_info.value.message

        with pytest.raises(ValidationError):
            validate_credit_control_area("US001")

    def test_special_chars_raise_error(self):
        """Special characters should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_credit_control_area("US-1")
        assert "alphanumeric" in exc_info.value.message


class TestValidateSalesOrg:
    """Tests for sales_org validation."""

    def test_valid_sales_org(self):
        """Valid 4-char sales org should be uppercased."""
        assert validate_sales_org("US10") == "US10"
        assert validate_sales_org("de10") == "DE10"

    def test_empty_raises_error(self):
        """Empty sales org should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_sales_org("")
        assert exc_info.value.field == "sales_org"
        assert "required" in exc_info.value.message

    def test_wrong_length_raises_error(self):
        """Sales org not exactly 4 chars should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_sales_org("US1")
        assert "exactly 4 characters" in exc_info.value.message


class TestValidateOrderItems:
    """Tests for order items validation."""

    def test_valid_items(self):
        """Valid items should be normalized."""
        items = [
            {"material": "MAT001", "quantity": 10},
            {"material": "MAT002", "quantity": 5.5, "unit": "KG", "plant": "1000"},
        ]
        result = validate_order_items(items)
        assert len(result) == 2
        assert result[0]["material"] == "MAT001"
        assert result[0]["quantity"] == 10.0
        assert result[0]["unit"] == "EA"  # Default
        assert result[0]["plant"] == ""  # Default
        assert result[1]["unit"] == "KG"
        assert result[1]["plant"] == "1000"

    def test_empty_list_raises_error(self):
        """Empty items list should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items([])
        assert exc_info.value.field == "items"
        assert "non-empty" in exc_info.value.message

    def test_none_raises_error(self):
        """None items should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items(None)
        assert exc_info.value.field == "items"

    def test_missing_material_raises_error(self):
        """Missing material should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items([{"quantity": 10}])
        assert "material is required" in exc_info.value.message

    def test_missing_quantity_raises_error(self):
        """Missing quantity should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items([{"material": "MAT001"}])
        assert "quantity is required" in exc_info.value.message

    def test_invalid_quantity_raises_error(self):
        """Non-positive quantity should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items([{"material": "MAT001", "quantity": 0}])
        assert "positive number" in exc_info.value.message

        with pytest.raises(ValidationError):
            validate_order_items([{"material": "MAT001", "quantity": -5}])

    def test_non_dict_item_raises_error(self):
        """Non-dict item should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_order_items(["item1"])
        assert "must be an object" in exc_info.value.message


# =============================================================================
# Input Validation Tests - Opportunity ID and Config ID
# =============================================================================


class TestValidateOpportunityId:
    """Tests for opportunity_id validation."""

    def test_valid_opportunity_id(self):
        """Valid opportunity ID should be trimmed and returned."""
        assert validate_opportunity_id("OPP-12345") == "OPP-12345"
        assert validate_opportunity_id("  OPP-123  ") == "OPP-123"

    def test_empty_raises_error(self):
        """Empty opportunity ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_opportunity_id("")
        assert exc_info.value.field == "opportunity_id"
        assert "required" in exc_info.value.message

    def test_whitespace_only_raises_error(self):
        """Whitespace-only ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_opportunity_id("   ")
        assert exc_info.value.field == "opportunity_id"
        assert "required" in exc_info.value.message


class TestValidateConfigId:
    """Tests for config_id validation."""

    def test_valid_config_id(self):
        """Valid config ID should be trimmed and returned."""
        assert validate_config_id("CFG-001") == "CFG-001"
        assert validate_config_id("  CFG-002  ") == "CFG-002"

    def test_empty_raises_error(self):
        """Empty config ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_config_id("")
        assert exc_info.value.field == "config_id"
        assert "required" in exc_info.value.message

    def test_whitespace_only_raises_error(self):
        """Whitespace-only ID should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_config_id("   ")
        assert exc_info.value.field == "config_id"
        assert "required" in exc_info.value.message


# =============================================================================
# IdempotencyManager Tests
# =============================================================================


class TestThreadSafeIdempotencyManager:
    """Tests for ThreadSafeIdempotencyManager."""

    @pytest.fixture
    def manager(self):
        """Create idempotency manager with short TTL for testing."""
        return ThreadSafeIdempotencyManager(ttl_seconds=1)

    def test_generate_key_deterministic(self, manager):
        """Same operation and payload should generate same key."""
        payload = {"customer_id": "1234", "items": [{"material": "A", "quantity": 1}]}
        key1 = manager.generate_key("create_order", payload)
        key2 = manager.generate_key("create_order", payload)
        assert key1 == key2
        assert len(key1) == 16  # 16-char hex

    def test_generate_key_different_for_different_payloads(self, manager):
        """Different payloads should generate different keys."""
        key1 = manager.generate_key("create_order", {"customer_id": "1234"})
        key2 = manager.generate_key("create_order", {"customer_id": "5678"})
        assert key1 != key2

    def test_generate_key_different_for_different_operations(self, manager):
        """Different operations should generate different keys."""
        payload = {"customer_id": "1234"}
        key1 = manager.generate_key("create_order", payload)
        key2 = manager.generate_key("simulate_order", payload)
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_check_duplicate_returns_none_for_new_key(self, manager):
        """New key should return None."""
        result = await manager.check_duplicate("new_key_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, manager):
        """Stored result should be retrievable."""
        key = "test_key_abc"
        result = {"success": True, "document_number": "12345"}

        await manager.store_result(key, result)
        retrieved = await manager.check_duplicate(key)

        assert retrieved == result

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self, manager):
        """Expired entry should return None."""
        key = "expire_test"
        result = {"success": True}

        await manager.store_result(key, result)

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        retrieved = await manager.check_duplicate(key)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, manager):
        """Concurrent access should be thread-safe."""

        async def store_and_check(i):
            key = f"key_{i}"
            result = {"value": i}
            await manager.store_result(key, result)
            retrieved = await manager.check_duplicate(key)
            return retrieved == result

        # Run 10 concurrent operations
        results = await asyncio.gather(*[store_and_check(i) for i in range(10)])
        assert all(results)


# =============================================================================
# Server Initialization Tests
# =============================================================================


class TestSAPCPIMCPServerInit:
    """Tests for SAPCPIMCPServer initialization."""

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_default_initialization(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Default initialization should create all clients and MCPServer."""
        _server = SAPCPIMCPServer(
            circuit_breaker_threshold=0
        )  # noqa: F841 - tests init side effects

        # All clients should be created
        mock_cpi.assert_called_once()
        mock_cec.assert_called_once()
        mock_ipas.assert_called_once()
        mock_ms5.assert_called_once()

        # MCPServer should be created with defaults
        mock_mcp.assert_called_once()
        call_kwargs = mock_mcp.call_args[1]
        assert call_kwargs["name"] == "sap-integration-server"
        assert call_kwargs["enable_cache"] is True
        assert call_kwargs["enable_metrics"] is True

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    def test_custom_cpi_client(self, mock_cpi_class, mock_mcp):
        """Custom CPIClient should be used instead of creating new."""
        custom_cpi = MagicMock()
        server = SAPCPIMCPServer(cpi_client=custom_cpi)

        # CPIClient class should NOT be called
        mock_cpi_class.assert_not_called()

        # Custom client should be stored
        assert server._cpi is custom_cpi

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    @patch("lead_to_cash.mcp.sap_cpi_server.APIKeyAuth")
    def test_api_keys_configuration(
        self, mock_auth, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """API keys should configure authentication."""
        api_keys = {"my-key": {"permissions": ["sap.read"]}}
        _server = SAPCPIMCPServer(
            api_keys=api_keys
        )  # noqa: F841 - tests init side effects

        # APIKeyAuth should be created
        mock_auth.assert_called_once_with(keys=api_keys, header_name="X-API-Key")

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_custom_rate_limit(self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp):
        """Custom rate limit should be passed to MCPServer."""
        _server = SAPCPIMCPServer(
            rate_limit_per_minute=50
        )  # noqa: F841 - tests init side effects

        call_kwargs = mock_mcp.call_args[1]
        assert call_kwargs["rate_limit_config"]["default_limit"] == 50

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_custom_circuit_breaker(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Custom circuit breaker threshold should be passed."""
        _server = SAPCPIMCPServer(
            circuit_breaker_threshold=10
        )  # noqa: F841 - tests init side effects

        call_kwargs = mock_mcp.call_args[1]
        assert call_kwargs["circuit_breaker_config"]["failure_threshold"] == 10

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_disable_cache_and_metrics(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Cache and metrics can be disabled."""
        _server = SAPCPIMCPServer(
            enable_cache=False, enable_metrics=False
        )  # noqa: F841 - tests init side effects

        call_kwargs = mock_mcp.call_args[1]
        assert call_kwargs["enable_cache"] is False
        assert call_kwargs["enable_metrics"] is False


# =============================================================================
# Tool Schema Tests
# =============================================================================


class TestToolSchemas:
    """Tests for MCP tool schemas."""

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_list_tools_returns_13_tools(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """list_tools should return 13 tools."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = server.list_tools()

        assert len(tools) == 13
        tool_names = [t["name"] for t in tools]

        # CEC tools (4)
        assert "cec_get_opportunity" in tool_names
        assert "cec_search_opportunities" in tool_names
        assert "cec_get_opportunities_by_account" in tool_names
        assert "cec_get_commercial_terms" in tool_names

        # IPAS tools (4)
        assert "ipas_get_configuration" in tool_names
        assert "ipas_get_configurations_by_opportunity" in tool_names
        assert "ipas_get_product_catalog" in tool_names
        assert "ipas_validate_configuration" in tool_names

        # MS5 tools (5)
        assert "sap_get_customer" in tool_names
        assert "sap_check_credit" in tool_names
        assert "sap_simulate_order" in tool_names
        assert "sap_create_order" in tool_names
        assert "sap_health_check" in tool_names

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_tool_schema_structure(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Each tool should have name, description, inputSchema."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = server.list_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_cec_opportunity_schema(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """cec_get_opportunity schema should be correct."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = {t["name"]: t for t in server.list_tools()}
        schema = tools["cec_get_opportunity"]["inputSchema"]

        assert "opportunity_id" in schema["properties"]
        assert "opportunity_id" in schema["required"]
        assert schema["properties"]["opportunity_id"]["type"] == "string"

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_ipas_configuration_schema(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """ipas_get_configuration schema should be correct."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = {t["name"]: t for t in server.list_tools()}
        schema = tools["ipas_get_configuration"]["inputSchema"]

        assert "config_id" in schema["properties"]
        assert "config_id" in schema["required"]
        assert schema["properties"]["config_id"]["type"] == "string"

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_get_customer_schema(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """sap_get_customer schema should be correct."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = {t["name"]: t for t in server.list_tools()}
        schema = tools["sap_get_customer"]["inputSchema"]

        assert "customer_id" in schema["properties"]
        assert "customer_id" in schema["required"]
        assert schema["properties"]["customer_id"]["type"] == "string"

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_create_order_schema(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """sap_create_order schema should include required fields."""
        server = SAPCPIMCPServer(circuit_breaker_threshold=0)
        tools = {t["name"]: t for t in server.list_tools()}
        schema = tools["sap_create_order"]["inputSchema"]

        assert "customer_id" in schema["required"]
        assert "sales_org" in schema["required"]
        assert "items" in schema["required"]
        assert "request_id" in schema["properties"]
        assert "test_run" in schema["properties"]


# =============================================================================
# Tool Call Error Handling Tests
# =============================================================================


class TestToolCallErrors:
    """Tests for tool call error handling."""

    @pytest.fixture
    def server(self):
        """Create server with mocked dependencies.

        We patch client classes for isolation.
        """
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            # Create async mocks
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5_class.return_value = AsyncMock()

            # Disable circuit breaker for unit tests (0 = disabled)
            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = False  # Ensure not connected
            return server

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, server):
        """Unknown tool should return error."""
        result = await server.call_tool("unknown_tool", {})

        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_TOOL"
        assert "unknown_tool" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_call_tool_not_initialized(self, server):
        """Calling tool before initialize should raise error."""
        with pytest.raises(RuntimeError) as exc_info:
            await server.call_tool("sap_get_customer", {"customer_id": "1234"})

        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_customer_validation_error_response(self, server):
        """Customer validation errors should return structured error."""
        server._connected = True  # Simulate initialized

        result = await server.call_tool("sap_get_customer", {"customer_id": ""})

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["field"] == "customer_id"

    @pytest.mark.asyncio
    async def test_opportunity_validation_error_response(self, server):
        """Opportunity validation errors should return structured error."""
        server._connected = True

        result = await server.call_tool("cec_get_opportunity", {"opportunity_id": ""})

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["field"] == "opportunity_id"

    @pytest.mark.asyncio
    async def test_config_validation_error_response(self, server):
        """Config validation errors should return structured error."""
        server._connected = True

        result = await server.call_tool("ipas_get_configuration", {"config_id": ""})

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["field"] == "config_id"


# =============================================================================
# CEC Tool Call Tests
# =============================================================================


class TestCECToolCalls:
    """Tests for CEC tool calls."""

    @pytest.fixture
    def connected_server(self):
        """Create connected server with mocked dependencies.

        Note: We don't patch MCPServer - we need the real tool registration.
        We only patch the client classes to isolate the tools being tested.
        """
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            # Create AsyncMock for all client instances
            mock_cpi_class.return_value = AsyncMock()
            mock_cec = AsyncMock()
            mock_cec_class.return_value = mock_cec
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5_class.return_value = AsyncMock()

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = True
            return server

    @pytest.mark.asyncio
    async def test_cec_get_opportunity_success(self, connected_server):
        """CEC get opportunity should return structured response with ADR-006 fields."""
        from datetime import datetime

        from lead_to_cash.integrations.cec_client import Opportunity

        mock_opp = MagicMock(spec=Opportunity)
        # Core identification
        mock_opp.opportunity_id = "OPP-001"
        mock_opp.account_id = "ACC-001"
        mock_opp.account_name = "Test Account"
        # Status and value
        mock_opp.status = "Open"
        mock_opp.expected_revenue = 100000.0
        mock_opp.currency = "EUR"
        # Dates (ADR-006)
        mock_opp.close_date = datetime(2026, 3, 15)
        mock_opp.start_date = datetime(2025, 12, 1)
        # Classification (ADR-006)
        mock_opp.title = "Test Opportunity Title"
        mock_opp.win_probability = 65
        mock_opp.sales_type = "OE_SALES"
        # Milestone Payment Fields (ADR-006)
        mock_opp.sap_order_id = None  # Open deal has no SAP order yet
        mock_opp.ipas_quote_id = "IPAS-2026-0001"
        # Products
        mock_opp.products = []
        mock_opp.to_sap_mapping.return_value = {"BSTKD": "OPP-001"}

        connected_server._cec.get_opportunity.return_value = mock_opp

        result = await connected_server.call_tool(
            "cec_get_opportunity", {"opportunity_id": "OPP-001"}
        )

        assert result["success"] is True
        assert result["opportunity_id"] == "OPP-001"
        assert result["account_name"] == "Test Account"
        # Verify ADR-006 fields are present
        assert result["title"] == "Test Opportunity Title"
        assert result["win_probability"] == 65
        assert result["sales_type"] == "OE_SALES"
        assert result["close_date"] == "2026-03-15T00:00:00"
        assert result["start_date"] == "2025-12-01T00:00:00"
        assert result["sap_order_id"] is None
        assert result["ipas_quote_id"] == "IPAS-2026-0001"

    @pytest.mark.asyncio
    async def test_cec_search_validation_error(self, connected_server):
        """CEC search without query should return validation error."""
        result = await connected_server.call_tool(
            "cec_search_opportunities", {"query": ""}
        )

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["field"] == "query"

    @pytest.mark.asyncio
    async def test_cec_by_account_validation_error(self, connected_server):
        """CEC by account without account_id should return validation error."""
        result = await connected_server.call_tool(
            "cec_get_opportunities_by_account", {"account_id": ""}
        )

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["field"] == "account_id"


# =============================================================================
# IPAS Tool Call Tests
# =============================================================================


class TestIPASToolCalls:
    """Tests for IPAS tool calls."""

    @pytest.fixture
    def connected_server(self):
        """Create connected server with mocked dependencies."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas = AsyncMock()
            mock_ipas_class.return_value = mock_ipas
            mock_ms5_class.return_value = AsyncMock()

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = True
            return server

    @pytest.mark.asyncio
    async def test_ipas_get_config_success(self, connected_server):
        """IPAS get configuration should return structured response."""
        from lead_to_cash.integrations.ipas_client import ProductConfiguration

        mock_cfg = MagicMock(spec=ProductConfiguration)
        mock_cfg.config_id = "CFG-001"
        mock_cfg.product_id = "PROD-001"
        mock_cfg.product_name = "Test Product"
        mock_cfg.variant = None
        mock_cfg.bom_items = [{"material": "MAT001", "quantity": 1}]
        mock_cfg.characteristics = {}
        mock_cfg.get_materials.return_value = ["MAT001"]
        mock_cfg.to_order_items.return_value = [{"MATERIAL": "MAT001"}]

        connected_server._ipas.get_configuration.return_value = mock_cfg

        result = await connected_server.call_tool(
            "ipas_get_configuration", {"config_id": "CFG-001"}
        )

        assert result["success"] is True
        assert result["config_id"] == "CFG-001"
        assert result["product_name"] == "Test Product"

    @pytest.mark.asyncio
    async def test_ipas_get_catalog_success(self, connected_server):
        """IPAS get catalog should work with optional parameters."""
        from lead_to_cash.integrations.ipas_client import ProductCatalog

        mock_product = MagicMock(spec=ProductCatalog)
        mock_product.product_id = "PROD-001"
        mock_product.name = "Test Product"
        mock_product.category = "Electronics"
        mock_product.configurable = True
        mock_product.base_price = 100.0
        mock_product.currency = "EUR"

        connected_server._ipas.get_product_catalog.return_value = [mock_product]

        result = await connected_server.call_tool("ipas_get_product_catalog", {})

        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_ipas_validate_config_success(self, connected_server):
        """IPAS validate configuration should return validation result."""
        connected_server._ipas.validate_configuration.return_value = {
            "is_valid": True,
            "messages": [],
            "errors": [],
            "warnings": [],
        }

        result = await connected_server.call_tool(
            "ipas_validate_configuration",
            {"config_id": "CFG-001", "characteristics": {"color": "red"}},
        )

        assert result["success"] is True
        assert result["is_valid"] is True


# =============================================================================
# MS5 Tool Call Tests
# =============================================================================


class TestMS5ToolCalls:
    """Tests for MS5 tool calls."""

    @pytest.fixture
    def connected_server(self):
        """Create connected server with mocked dependencies."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5 = AsyncMock()
            mock_ms5_class.return_value = mock_ms5

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = True
            return server

    @pytest.mark.asyncio
    async def test_get_customer_success(self, connected_server):
        """Get customer should return structured response."""
        from lead_to_cash.integrations.ms5_client import CustomerData

        mock_customer = MagicMock(spec=CustomerData)
        mock_customer.customer_id = "0000001234"
        mock_customer.name = "Test Customer"
        mock_customer.address = {"street": "123 Main St"}
        mock_customer.contact = {"phone": "555-1234"}
        mock_customer.messages = []

        connected_server._ms5.get_customer.return_value = mock_customer

        result = await connected_server.call_tool(
            "sap_get_customer", {"customer_id": "1234"}
        )

        assert result["success"] is True
        assert result["customer_id"] == "0000001234"
        assert result["name"] == "Test Customer"

    @pytest.mark.asyncio
    async def test_check_credit_success(self, connected_server):
        """Check credit should return structured response."""
        from lead_to_cash.integrations.ms5_client import CreditData

        mock_credit = MagicMock(spec=CreditData)
        mock_credit.customer_id = "0000001234"
        mock_credit.credit_control_area = "US01"
        mock_credit.credit_limit = 100000.0
        mock_credit.credit_exposure = 25000.0
        mock_credit.available_credit = 75000.0
        mock_credit.credit_check_passed = True
        mock_credit.utilization_percent = 25.0
        mock_credit.messages = []

        connected_server._ms5.check_credit_limit.return_value = mock_credit

        result = await connected_server.call_tool(
            "sap_check_credit", {"customer_id": "1234", "credit_control_area": "US01"}
        )

        assert result["success"] is True
        assert result["credit_limit"] == 100000.0
        assert result["credit_check_passed"] is True

    @pytest.mark.asyncio
    async def test_simulate_order_success(self, connected_server):
        """Simulate order should return structured response."""
        from lead_to_cash.integrations.ms5_client import SalesOrderSimulation

        mock_sim = MagicMock(spec=SalesOrderSimulation)
        mock_sim.is_valid = True
        mock_sim.net_value = 5000.0
        mock_sim.currency = "EUR"
        mock_sim.item_count = 1
        mock_sim.messages = []
        mock_sim.errors = []
        mock_sim.warnings = []

        connected_server._ms5.simulate_order.return_value = mock_sim

        result = await connected_server.call_tool(
            "sap_simulate_order",
            {
                "customer_id": "1234",
                "sales_org": "US10",
                "items": [{"material": "MAT001", "quantity": 10}],
            },
        )

        assert result["success"] is True
        assert result["is_valid"] is True
        assert result["net_value"] == 5000.0


# =============================================================================
# Configuration Helper Tests
# =============================================================================


class TestGetSAPCPIMCPConfig:
    """Tests for get_sap_cpi_mcp_config helper."""

    @patch.dict("os.environ", {"MCP_SERVER_HOST": "myhost", "MCP_SERVER_PORT": "9999"})
    def test_http_transport_config(self):
        """HTTP transport config should include URL and headers."""
        mcp_config = get_sap_cpi_mcp_config(transport="http")

        assert mcp_config["name"] == "sap-integration"
        assert mcp_config["transport"] == "http"
        assert "myhost" in mcp_config["url"]
        assert "9999" in mcp_config["url"]
        assert "X-API-Key" in mcp_config["headers"]

    def test_stdio_transport_config(self):
        """stdio transport config should include command and args."""
        mcp_config = get_sap_cpi_mcp_config(transport="stdio")

        assert mcp_config["name"] == "sap-integration"
        assert mcp_config["transport"] == "stdio"
        assert mcp_config["command"] == "python"
        assert "lead_to_cash.mcp.sap_cpi_server" in mcp_config["args"]

    @patch.dict("os.environ", {"ENVIRONMENT": "production"})
    def test_uses_environment_from_env(self):
        """Should use environment from config."""
        with patch("lead_to_cash.mcp.sap_cpi_server.config") as mock_config:
            mock_config.environment = "production"
            mock_config.sap_cpi.timeout_seconds = 60

            mcp_config = get_sap_cpi_mcp_config()

            assert mcp_config["headers"]["X-Environment"] == "production"

    def test_custom_environment(self):
        """Custom environment should override config."""
        with patch("lead_to_cash.mcp.sap_cpi_server.config") as mock_config:
            mock_config.environment = "development"
            mock_config.sap_cpi.timeout_seconds = 30

            mcp_config = get_sap_cpi_mcp_config(environment="qa")

            assert mcp_config["headers"]["X-Environment"] == "qa"


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestServerLifecycle:
    """Tests for server lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_connects_all_clients(self):
        """initialize should connect all clients via CPI."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.MCPServer"),
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client"),
        ):
            mock_cpi = AsyncMock()
            mock_cpi_class.return_value = mock_cpi

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            await server.initialize()

            mock_cpi.connect.assert_called_once()
            assert server._connected is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """initialize should be idempotent."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.MCPServer"),
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client"),
        ):
            mock_cpi = AsyncMock()
            mock_cpi_class.return_value = mock_cpi

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            await server.initialize()
            await server.initialize()  # Second call

            # Should only connect once
            mock_cpi.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_cpi(self):
        """shutdown should disconnect CPI client."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.MCPServer"),
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client"),
        ):
            mock_cpi = AsyncMock()
            mock_cpi_class.return_value = mock_cpi

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            await server.initialize()
            await server.shutdown()

            mock_cpi.disconnect.assert_called_once()
            assert server._connected is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Context manager should initialize and shutdown."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.MCPServer"),
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient"),
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client"),
        ):
            mock_cpi = AsyncMock()
            mock_cpi_class.return_value = mock_cpi

            async with SAPCPIMCPServer(circuit_breaker_threshold=0) as server:
                mock_cpi.connect.assert_called_once()
                assert server._connected is True

            mock_cpi.disconnect.assert_called_once()


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for Prometheus metrics export."""

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_metrics_disabled_returns_message(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Disabled metrics should return info message."""
        server = SAPCPIMCPServer(enable_metrics=False)
        metrics = server.get_prometheus_metrics()

        assert "Metrics disabled" in metrics

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_metrics_enabled_calls_export(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Enabled metrics should call server metrics export."""
        mock_metrics = MagicMock()
        mock_metrics.export_metrics.return_value = "mcp_calls_total 100"
        mock_mcp.return_value.metrics = mock_metrics

        server = SAPCPIMCPServer(enable_metrics=True)
        metrics = server.get_prometheus_metrics()

        mock_metrics.export_metrics.assert_called_once_with(format="prometheus")
        assert "mcp_calls_total" in metrics

    @patch("lead_to_cash.mcp.sap_cpi_server.MCPServer")
    @patch("lead_to_cash.mcp.sap_cpi_server.CPIClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.CECClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.IPASClient")
    @patch("lead_to_cash.mcp.sap_cpi_server.MS5Client")
    def test_metrics_export_error_handled(
        self, mock_ms5, mock_ipas, mock_cec, mock_cpi, mock_mcp
    ):
        """Metrics export error should be handled gracefully."""
        mock_metrics = MagicMock()
        mock_metrics.export_metrics.side_effect = Exception("Export failed")
        mock_mcp.return_value.metrics = mock_metrics

        server = SAPCPIMCPServer(enable_metrics=True)
        metrics = server.get_prometheus_metrics()

        assert "Error exporting metrics" in metrics


# =============================================================================
# Idempotency Integration Tests
# =============================================================================


class TestIdempotencyIntegration:
    """Tests for idempotency in order creation."""

    @pytest.mark.asyncio
    async def test_duplicate_order_returns_cached_result(self):
        """Duplicate order creation should return cached result."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            # Setup mocks
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5 = AsyncMock()
            mock_ms5_class.return_value = mock_ms5

            # First call succeeds
            from lead_to_cash.integrations.ms5_client import SalesOrderResult

            mock_ms5.create_order.return_value = SalesOrderResult(
                success=True,
                document_number="1234567890",
                committed=True,
                test_run=False,
                messages=[],
            )

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = True

            # First call
            args = {
                "customer_id": "1234",
                "sales_org": "US10",
                "items": [{"material": "MAT001", "quantity": 10}],
            }
            result1 = await server.call_tool("sap_create_order", args)
            assert result1["success"] is True
            assert result1["document_number"] == "1234567890"

            # Second call with same args (should be idempotent replay)
            result2 = await server.call_tool("sap_create_order", args)
            assert result2["success"] is True
            assert result2.get("idempotent_replay") is True
            assert result2["document_number"] == "1234567890"

            # MS5Client should only be called once
            mock_ms5.create_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_request_id_used_for_idempotency(self):
        """Custom request_id should be used as idempotency key."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5 = AsyncMock()
            mock_ms5_class.return_value = mock_ms5

            from lead_to_cash.integrations.ms5_client import SalesOrderResult

            mock_ms5.create_order.return_value = SalesOrderResult(
                success=True,
                document_number="9999999999",
                committed=True,
                test_run=False,
                messages=[],
            )

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            server._connected = True

            args = {
                "customer_id": "5678",
                "sales_org": "US10",
                "items": [{"material": "MAT002", "quantity": 5}],
                "request_id": "my-custom-id-123",
            }
            result = await server.call_tool("sap_create_order", args)

            assert result["success"] is True
            assert result["idempotency_key"] == "my-custom-id-123"


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check tool."""

    @pytest.mark.asyncio
    async def test_health_check_before_init(self):
        """Health check before init should return not_initialized status."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            mock_cpi_class.return_value = AsyncMock()
            mock_cec_class.return_value = AsyncMock()
            mock_ipas_class.return_value = AsyncMock()
            mock_ms5_class.return_value = AsyncMock()

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            # Not connected

            result = await server.call_tool("sap_health_check", {})

            assert result["success"] is True
            assert result["gateway"] == "SAP CPI"
            assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_health_check_after_init(self):
        """Health check after init should return connected status."""
        with (
            patch("lead_to_cash.mcp.sap_cpi_server.CPIClient") as mock_cpi_class,
            patch("lead_to_cash.mcp.sap_cpi_server.CECClient") as mock_cec_class,
            patch("lead_to_cash.mcp.sap_cpi_server.IPASClient") as mock_ipas_class,
            patch("lead_to_cash.mcp.sap_cpi_server.MS5Client") as mock_ms5_class,
        ):
            # Setup mocks for health_check methods
            mock_cpi = AsyncMock()
            mock_cpi.health_check.return_value = {"status": "healthy"}
            mock_cpi_class.return_value = mock_cpi

            mock_cec = AsyncMock()
            mock_cec.health_check.return_value = {"status": "healthy"}
            mock_cec_class.return_value = mock_cec

            mock_ipas = AsyncMock()
            mock_ipas.health_check.return_value = {"status": "healthy"}
            mock_ipas_class.return_value = mock_ipas

            mock_ms5 = AsyncMock()
            mock_ms5.health_check.return_value = {"status": "healthy"}
            mock_ms5_class.return_value = mock_ms5

            server = SAPCPIMCPServer(circuit_breaker_threshold=0)
            await server.initialize()

            result = await server.call_tool("sap_health_check", {})

            assert result["success"] is True
            assert result["connected"] is True
            # Systems is now a dict with health status for each system
            assert "cec" in result["systems"]
            assert "ipas" in result["systems"]
            assert "ms5" in result["systems"]
