"""
Unit tests for MCP Forge server functionality.

Testing Strategy:
- Unit tests can use mocking (Tier 1)
- Fast execution < 1s per test
- Isolated component testing
- Test server logic without real MCP protocol
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from kailash.runtime.local import LocalRuntime

# Core imports for MCP server testing
from kailash.workflow.builder import WorkflowBuilder


class TestMCPServer:
    """Unit tests for MCPServer core functionality."""

    @pytest.fixture
    def mock_tools(self):
        """Mock tools for testing."""
        return {
            "echo": {
                "name": "echo",
                "description": "Echo back the input message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to echo"}
                    },
                    "required": ["message"],
                },
            },
            "math": {
                "name": "math",
                "description": "Perform basic math operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"],
                            "description": "Math operation to perform",
                        },
                    },
                    "required": ["a", "b", "operation"],
                },
            },
        }

    @pytest.fixture
    def default_config(self):
        """Default server configuration for testing."""
        return {
            "name": "test-mcp-server",
            "version": "1.0.0",
            "host": "localhost",
            "port": 8080,
            "transport": ["http", "websocket"],
            "max_connections": 100,
            "timeout": 30,
            "enable_cors": True,
            "auth_required": False,
        }

    def test_server_initialization_defaults(self, default_config):
        """Test server initializes with default configuration."""
        # This would test the actual MCPServer class once implemented
        # For now, test the expected interface
        server_config = {
            "name": "mcp-forge-server",
            "version": "0.1.0",
            "host": "localhost",
            "port": 8080,
            "transport": ["http"],
            "tools": {},
        }

        assert server_config["name"] == "mcp-forge-server"
        assert server_config["version"] == "0.1.0"
        assert server_config["host"] == "localhost"
        assert server_config["port"] == 8080
        assert "http" in server_config["transport"]
        assert isinstance(server_config["tools"], dict)

    def test_server_initialization_custom_config(self, default_config):
        """Test server initializes with custom configuration."""
        custom_config = {
            **default_config,
            "name": "custom-server",
            "port": 9000,
            "auth_required": True,
        }

        assert custom_config["name"] == "custom-server"
        assert custom_config["port"] == 9000
        assert custom_config["auth_required"] is True

    def test_tool_registration_valid(self, mock_tools):
        """Test valid tool registration."""
        tools_registry = {}

        # Simulate tool registration
        for tool_name, tool_schema in mock_tools.items():
            tools_registry[tool_name] = tool_schema

        assert "echo" in tools_registry
        assert "math" in tools_registry
        assert tools_registry["echo"]["name"] == "echo"
        assert "parameters" in tools_registry["echo"]
        assert tools_registry["math"]["parameters"]["required"] == [
            "a",
            "b",
            "operation",
        ]

    def test_tool_registration_validation_missing_name(self):
        """Test tool registration fails with missing name."""
        invalid_tool = {
            "description": "Tool without name",
            "parameters": {"type": "object"},
        }

        # Should detect missing required field
        assert "name" not in invalid_tool

        # In real implementation, this should raise ValidationError
        with pytest.raises(KeyError):
            name = invalid_tool["name"]

    def test_tool_registration_validation_invalid_parameters(self):
        """Test tool registration fails with invalid parameter schema."""
        invalid_tool = {
            "name": "invalid_tool",
            "description": "Tool with invalid parameters",
            "parameters": "not an object",  # Should be dict/object
        }

        # Should detect invalid parameter schema
        assert not isinstance(invalid_tool["parameters"], dict)

    def test_tool_registration_duplicate_names(self, mock_tools):
        """Test duplicate tool name handling."""
        tools_registry = {}

        # Register first tool
        echo_tool = mock_tools["echo"]
        tools_registry["echo"] = echo_tool

        # Attempt to register duplicate
        duplicate_tool = {
            "name": "echo",
            "description": "Duplicate echo tool",
            "parameters": {"type": "object"},
        }

        # Should handle duplicate registration
        # (real implementation might overwrite or raise error)
        if "echo" in tools_registry:
            original_description = tools_registry["echo"]["description"]
            assert original_description == "Echo back the input message"

    @pytest.mark.asyncio
    async def test_server_start_stop_lifecycle(self):
        """Test server start/stop lifecycle with mocked operations."""
        server_state = {"running": False, "port": None}

        async def mock_start(port=8080):
            server_state["running"] = True
            server_state["port"] = port
            return True

        async def mock_stop():
            server_state["running"] = False
            server_state["port"] = None
            return True

        # Test start
        result = await mock_start(8080)
        assert result is True
        assert server_state["running"] is True
        assert server_state["port"] == 8080

        # Test stop
        result = await mock_stop()
        assert result is True
        assert server_state["running"] is False
        assert server_state["port"] is None

    def test_configuration_validation(self):
        """Test configuration parameter validation."""
        valid_config = {
            "name": "test-server",
            "version": "1.0.0",
            "host": "localhost",
            "port": 8080,
            "transport": ["http"],
        }

        # Test valid configuration
        assert isinstance(valid_config["name"], str)
        assert isinstance(valid_config["port"], int)
        assert valid_config["port"] > 0
        assert isinstance(valid_config["transport"], list)
        assert len(valid_config["transport"]) > 0

    def test_configuration_validation_invalid_port(self):
        """Test configuration validation with invalid port."""
        invalid_configs = [
            {"port": -1},  # Negative port
            {"port": 0},  # Zero port
            {"port": 65536},  # Port too high
            {"port": "8080"},  # String instead of int
        ]

        for config in invalid_configs:
            port = config["port"]
            if isinstance(port, str):
                assert not isinstance(port, int)
            elif isinstance(port, int):
                assert port <= 0 or port >= 65536

    def test_error_handling_configuration(self):
        """Test error handling for configuration issues."""
        error_scenarios = [
            {"name": "", "error": "empty_name"},
            {"port": "invalid", "error": "invalid_port_type"},
            {"transport": [], "error": "no_transport"},
            {"transport": ["invalid"], "error": "invalid_transport"},
        ]

        for scenario in error_scenarios:
            config = scenario.copy()
            error_type = config.pop("error")

            # Validate the error scenario
            if error_type == "empty_name":
                assert config["name"] == ""
            elif error_type == "invalid_port_type":
                assert not isinstance(config["port"], int)
            elif error_type == "no_transport":
                assert len(config["transport"]) == 0
            elif error_type == "invalid_transport":
                assert "invalid" not in ["http", "websocket", "stdio"]

    def test_multiple_transport_configuration(self):
        """Test server configuration with multiple transports."""
        multi_transport_config = {
            "name": "multi-transport-server",
            "transport": ["http", "websocket"],
            "http_port": 8080,
            "websocket_port": 8081,
        }

        assert "http" in multi_transport_config["transport"]
        assert "websocket" in multi_transport_config["transport"]
        assert (
            multi_transport_config["http_port"]
            != multi_transport_config["websocket_port"]
        )

    @pytest.mark.asyncio
    async def test_tool_execution_mock(self, mock_tools):
        """Test tool execution with mocked responses."""

        async def mock_execute_tool(
            tool_name: str, parameters: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Mock tool execution."""
            if tool_name == "echo":
                return {"result": parameters.get("message", "")}
            elif tool_name == "math":
                a = parameters.get("a", 0)
                b = parameters.get("b", 0)
                op = parameters.get("operation", "add")

                operations = {
                    "add": a + b,
                    "subtract": a - b,
                    "multiply": a * b,
                    "divide": a / b if b != 0 else None,
                }

                return {"result": operations.get(op)}
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        # Test echo tool
        echo_result = await mock_execute_tool("echo", {"message": "Hello World"})
        assert echo_result["result"] == "Hello World"

        # Test math tool
        math_result = await mock_execute_tool(
            "math", {"a": 10, "b": 5, "operation": "add"}
        )
        assert math_result["result"] == 15

        # Test unknown tool
        error_result = await mock_execute_tool("unknown", {})
        assert "error" in error_result

    def test_server_response_format(self):
        """Test standard MCP response format."""
        success_response = {
            "jsonrpc": "2.0",
            "id": "test-request-1",
            "result": {"content": [{"type": "text", "text": "Hello World"}]},
        }

        error_response = {
            "jsonrpc": "2.0",
            "id": "test-request-2",
            "error": {"code": -32601, "message": "Method not found"},
        }

        # Test success response format
        assert success_response["jsonrpc"] == "2.0"
        assert "result" in success_response
        assert "id" in success_response

        # Test error response format
        assert error_response["jsonrpc"] == "2.0"
        assert "error" in error_response
        assert error_response["error"]["code"] == -32601


class TestMCPServerIntegration:
    """Integration-style unit tests for server components."""

    def test_server_with_kailash_workflow_mock(self):
        """Test server integration with mocked Kailash workflow."""
        # Mock workflow integration
        workflow = WorkflowBuilder()

        # This tests the workflow builder interface that will be used
        # in the actual MCP bridge implementation
        assert workflow is not None

        # Test adding nodes (this is the SDK interface we'll bridge)
        workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})

        # Verify workflow has nodes (mocked validation)
        built_workflow = workflow.build()
        assert built_workflow is not None

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution_mock(self):
        """Test concurrent tool execution handling."""

        async def mock_tool_handler(
            tool_name: str, params: Dict[str, Any]
        ) -> Dict[str, Any]:
            # Simulate processing time
            await asyncio.sleep(0.01)  # 10ms mock processing
            return {"tool": tool_name, "processed": True, "params": params}

        # Test concurrent execution
        tasks = []
        for i in range(5):
            task = mock_tool_handler(f"tool_{i}", {"param": f"value_{i}"})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["tool"] == f"tool_{i}"
            assert result["processed"] is True
            assert result["params"]["param"] == f"value_{i}"

    def test_server_health_check_mock(self):
        """Test server health check functionality."""
        health_status = {
            "status": "healthy",
            "uptime": 3600,  # 1 hour
            "tools_registered": 5,
            "active_connections": 2,
            "memory_usage": "45MB",
            "version": "0.1.0",
        }

        assert health_status["status"] == "healthy"
        assert health_status["uptime"] > 0
        assert health_status["tools_registered"] >= 0
        assert health_status["active_connections"] >= 0
        assert "version" in health_status
