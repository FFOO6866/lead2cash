"""
Real MCP server implementation for testing MCP Forge.

This provides a real, working MCP server that follows the protocol specification
for use in integration and E2E tests. NO MOCKING - real MCP protocol implementation.
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional

import websockets


class MCPMessageType(Enum):
    """MCP message types according to specification."""

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


@dataclass
class MCPMessage:
    """MCP message structure."""

    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class TestMCPServer:
    """
    Real MCP server for testing MCP Forge against.

    This implements actual MCP protocol features:
    - Tool discovery and execution
    - WebSocket and HTTP transports
    - JSON-RPC 2.0 messaging
    - Error handling per MCP spec
    - Resource discovery
    - Capability negotiation
    """

    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.running = False
        self.tools = {}
        self.resources = {}
        self.clients = set()
        self.logger = logging.getLogger(__name__)

        # Register default test tools
        self._register_default_tools()
        self._register_default_resources()

    def _register_default_tools(self):
        """Register default test tools for comprehensive testing."""

        # Echo tool - simple text processing
        self.tools["echo"] = {
            "name": "echo",
            "description": "Echo back the input message with optional prefix",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back",
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Optional prefix to add",
                        "default": "Echo: ",
                    },
                },
                "required": ["message"],
            },
            "handler": self._echo_tool,
        }

        # Math tool - numerical operations
        self.tools["math"] = {
            "name": "math",
            "description": "Perform basic mathematical operations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "Operation to perform",
                    },
                },
                "required": ["a", "b", "operation"],
            },
            "handler": self._math_tool,
        }

        # File tool - file operations for testing
        self.tools["file_info"] = {
            "name": "file_info",
            "description": "Get information about a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to analyze"}
                },
                "required": ["path"],
            },
            "handler": self._file_info_tool,
        }

        # Error tool - for testing error scenarios
        self.tools["error"] = {
            "name": "error",
            "description": "Tool for testing error scenarios",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "error_type": {
                        "type": "string",
                        "enum": ["timeout", "exception", "invalid_params", "not_found"],
                        "description": "Type of error to simulate",
                    },
                    "delay": {
                        "type": "number",
                        "description": "Delay in seconds before error",
                        "default": 0,
                    },
                },
                "required": ["error_type"],
            },
            "handler": self._error_tool,
        }

        # Async tool - for testing asynchronous operations
        self.tools["async_process"] = {
            "name": "async_process",
            "description": "Simulate long-running asynchronous process",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "number",
                        "description": "Process duration in seconds",
                        "default": 1.0,
                    },
                    "steps": {
                        "type": "integer",
                        "description": "Number of processing steps",
                        "default": 5,
                    },
                },
                "required": [],
            },
            "handler": self._async_process_tool,
        }

    def _register_default_resources(self):
        """Register default test resources."""

        self.resources["test_data"] = {
            "uri": "test://data/sample.json",
            "name": "Sample Test Data",
            "description": "Sample JSON data for testing",
            "mimeType": "application/json",
            "handler": self._get_test_data_resource,
        }

        self.resources["config"] = {
            "uri": "test://config/server.yaml",
            "name": "Server Configuration",
            "description": "Test server configuration",
            "mimeType": "application/yaml",
            "handler": self._get_config_resource,
        }

    async def _echo_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Echo tool implementation."""
        message = params.get("message", "")
        prefix = params.get("prefix", "Echo: ")

        return {"content": [{"type": "text", "text": f"{prefix}{message}"}]}

    async def _math_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Math tool implementation."""
        a = params.get("a")
        b = params.get("b")
        operation = params.get("operation")

        operations = {
            "add": lambda x, y: x + y,
            "subtract": lambda x, y: x - y,
            "multiply": lambda x, y: x * y,
            "divide": lambda x, y: x / y if y != 0 else None,
        }

        if operation not in operations:
            raise ValueError(f"Unknown operation: {operation}")

        if operation == "divide" and b == 0:
            raise ValueError("Division by zero")

        result = operations[operation](a, b)

        return {
            "content": [{"type": "text", "text": f"Result: {result}"}],
            "result": result,
        }

    async def _file_info_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """File info tool implementation."""
        import os
        import stat
        from datetime import datetime

        path = params.get("path")

        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")

            file_stat = os.stat(path)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"File: {path}\nSize: {file_stat.st_size} bytes\nModified: {datetime.fromtimestamp(file_stat.st_mtime)}",
                    }
                ],
                "file_info": {
                    "path": path,
                    "size": file_stat.st_size,
                    "modified": file_stat.st_mtime,
                    "is_file": stat.S_ISREG(file_stat.st_mode),
                    "is_directory": stat.S_ISDIR(file_stat.st_mode),
                },
            }
        except Exception as e:
            raise ValueError(f"Error accessing file: {str(e)}")

    async def _error_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Error tool for testing error scenarios."""
        error_type = params.get("error_type")
        delay = params.get("delay", 0)

        if delay > 0:
            await asyncio.sleep(delay)

        if error_type == "timeout":
            # Simulate timeout by sleeping too long
            await asyncio.sleep(60)
        elif error_type == "exception":
            raise RuntimeError("Simulated tool execution error")
        elif error_type == "invalid_params":
            raise ValueError("Invalid parameters provided")
        elif error_type == "not_found":
            raise FileNotFoundError("Requested resource not found")
        else:
            raise ValueError(f"Unknown error type: {error_type}")

    async def _async_process_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Async process tool for testing long-running operations."""
        duration = params.get("duration", 1.0)
        steps = params.get("steps", 5)

        step_duration = duration / steps
        results = []

        for i in range(steps):
            await asyncio.sleep(step_duration)
            results.append(f"Step {i + 1}/{steps} completed")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Async process completed in {duration}s with {steps} steps",
                }
            ],
            "process_info": {"duration": duration, "steps": steps, "results": results},
        }

    async def _get_test_data_resource(self, uri: str) -> Dict[str, Any]:
        """Get test data resource."""
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(
                        {
                            "test_data": True,
                            "timestamp": time.time(),
                            "values": [1, 2, 3, 4, 5],
                        }
                    ),
                }
            ]
        }

    async def _get_config_resource(self, uri: str) -> Dict[str, Any]:
        """Get config resource."""
        config_yaml = """
server:
  name: test-mcp-server
  port: 8080
  host: localhost

tools:
  auto_discover: true
  timeout: 30

logging:
  level: INFO
"""
        return {
            "contents": [
                {"uri": uri, "mimeType": "application/yaml", "text": config_yaml}
            ]
        }

    async def handle_mcp_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP message according to protocol."""

        try:
            # Validate JSON-RPC structure
            if message.get("jsonrpc") != "2.0":
                return self._create_error_response(
                    message.get("id"),
                    -32600,  # Invalid Request
                    "Invalid JSON-RPC version",
                )

            method = message.get("method")
            params = message.get("params", {})
            request_id = message.get("id")

            if method == "initialize":
                return await self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return await self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tools_call(request_id, params)
            elif method == "resources/list":
                return await self._handle_resources_list(request_id)
            elif method == "resources/read":
                return await self._handle_resources_read(request_id, params)
            elif method == "ping":
                return await self._handle_ping(request_id)
            else:
                return self._create_error_response(
                    request_id, -32601, f"Unknown method: {method}"  # Method not found
                )

        except Exception as e:
            return self._create_error_response(
                message.get("id"),
                -32603,  # Internal error
                f"Internal server error: {str(e)}",
            )

    async def _handle_initialize(
        self, request_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        client_info = params.get("clientInfo", {})

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": True, "listChanged": True},
                },
                "serverInfo": {"name": "test-mcp-server", "version": "1.0.0"},
            },
        }

    async def _handle_tools_list(self, request_id: str) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools_list = []

        for tool_name, tool_info in self.tools.items():
            tools_list.append(
                {
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "inputSchema": tool_info["inputSchema"],
                }
            )

        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools_list}}

    async def _handle_tools_call(
        self, request_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        tool_params = params.get("arguments", {})

        if tool_name not in self.tools:
            return self._create_error_response(
                request_id, -32602, f"Unknown tool: {tool_name}"  # Invalid params
            )

        try:
            tool_info = self.tools[tool_name]
            handler = tool_info["handler"]

            # Validate parameters against schema
            # (In real implementation, would use jsonschema library)

            result = await handler(tool_params)

            return {"jsonrpc": "2.0", "id": request_id, "result": result}

        except Exception as e:
            return self._create_error_response(
                request_id, -32603, f"Tool execution failed: {str(e)}"  # Internal error
            )

    async def _handle_resources_list(self, request_id: str) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources_list = []

        for resource_uri, resource_info in self.resources.items():
            resources_list.append(
                {
                    "uri": resource_info["uri"],
                    "name": resource_info["name"],
                    "description": resource_info["description"],
                    "mimeType": resource_info["mimeType"],
                }
            )

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": resources_list},
        }

    async def _handle_resources_read(
        self, request_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")

        # Find resource by URI
        resource_info = None
        for resource_data in self.resources.values():
            if resource_data["uri"] == uri:
                resource_info = resource_data
                break

        if not resource_info:
            return self._create_error_response(
                request_id, -32602, f"Resource not found: {uri}"  # Invalid params
            )

        try:
            handler = resource_info["handler"]
            result = await handler(uri)

            return {"jsonrpc": "2.0", "id": request_id, "result": result}

        except Exception as e:
            return self._create_error_response(
                request_id, -32603, f"Resource read failed: {str(e)}"  # Internal error
            )

    async def _handle_ping(self, request_id: str) -> Dict[str, Any]:
        """Handle ping request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"status": "ok", "timestamp": time.time()},
        }

    def _create_error_response(
        self, request_id: Optional[str], code: int, message: str
    ) -> Dict[str, Any]:
        """Create MCP error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    async def start_websocket_server(self):
        """Start WebSocket server for MCP communication."""

        async def handle_websocket(websocket, path):
            """Handle WebSocket connection."""
            self.clients.add(websocket)
            self.logger.info(f"WebSocket client connected: {websocket.remote_address}")

            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        response = await self.handle_mcp_message(data)
                        await websocket.send(json.dumps(response))
                    except json.JSONDecodeError:
                        error_response = self._create_error_response(
                            None, -32700, "Parse error"
                        )
                        await websocket.send(json.dumps(error_response))

            except websockets.exceptions.ConnectionClosed:
                self.logger.info("WebSocket client disconnected")
            finally:
                self.clients.discard(websocket)

        self.logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")

        return await websockets.serve(
            handle_websocket, self.host, self.port, ping_interval=20, ping_timeout=10
        )

    async def start(self):
        """Start the test MCP server."""
        if self.running:
            return

        self.running = True
        self.logger.info(f"Starting Test MCP Server on {self.host}:{self.port}")

        try:
            # Start WebSocket server
            server = await self.start_websocket_server()

            self.logger.info("Test MCP Server started successfully")

            # Keep server running
            await server.wait_closed()

        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
        finally:
            self.running = False

    async def stop(self):
        """Stop the test MCP server."""
        if not self.running:
            return

        self.logger.info("Stopping Test MCP Server")

        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients], return_exceptions=True
            )
            self.clients.clear()

        self.running = False
        self.logger.info("Test MCP Server stopped")

    def is_healthy(self) -> bool:
        """Check if server is healthy and responding."""
        return self.running

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information for testing."""
        return {
            "host": self.host,
            "port": self.port,
            "running": self.running,
            "tools_count": len(self.tools),
            "resources_count": len(self.resources),
            "active_clients": len(self.clients),
            "websocket_url": f"ws://{self.host}:{self.port}",
            "protocol_version": "2024-11-05",
        }


class MCPServerManager:
    """
    Manager for starting/stopping test MCP servers in tests.

    Usage in tests:

    @pytest.fixture
    async def mcp_server():
        manager = MCPServerManager()
        server = await manager.start_server()
        yield server
        await manager.stop_server()
    """

    def __init__(self):
        self.servers: List[TestMCPServer] = []
        self.server_tasks: List[asyncio.Task] = []

    async def start_server(
        self, host: str = "localhost", port: int = 8080
    ) -> TestMCPServer:
        """Start a test MCP server and return server info."""
        server = TestMCPServer(host, port)

        # Start server in background task
        task = asyncio.create_task(server.start())

        # Wait a bit for server to start
        await asyncio.sleep(0.1)

        if not server.running:
            await asyncio.sleep(0.5)  # Give it more time

        self.servers.append(server)
        self.server_tasks.append(task)

        return server

    async def stop_server(self, server: Optional[TestMCPServer] = None):
        """Stop specific server or all servers."""
        if server:
            await server.stop()
            if server in self.servers:
                self.servers.remove(server)
        else:
            # Stop all servers
            await asyncio.gather(
                *[server.stop() for server in self.servers], return_exceptions=True
            )
            self.servers.clear()

        # Cancel server tasks
        for task in self.server_tasks:
            if not task.done():
                task.cancel()

        self.server_tasks.clear()

    async def get_available_port(self, start_port: int = 8080) -> int:
        """Find an available port for testing."""
        import socket

        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("localhost", port))
                    return port
            except OSError:
                continue

        raise RuntimeError("No available ports found")


# Pytest fixtures for easy test usage
def pytest_mcp_server_fixture():
    """
    Example pytest fixture for MCP server.
    Copy this to your conftest.py:

    @pytest.fixture
    async def mcp_server():
        from tests.utils.test_mcp_server import MCPServerManager

        manager = MCPServerManager()
        port = await manager.get_available_port()
        server = await manager.start_server(port=port)

        yield server

        await manager.stop_server()
    """
    pass


if __name__ == "__main__":
    # Run server standalone for manual testing
    async def main():
        logging.basicConfig(level=logging.INFO)

        server = TestMCPServer()

        try:
            await server.start()
        except KeyboardInterrupt:
            await server.stop()

    asyncio.run(main())
