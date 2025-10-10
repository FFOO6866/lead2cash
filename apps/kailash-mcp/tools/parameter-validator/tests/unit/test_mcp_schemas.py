"""
Unit tests for MCP tool schema generation and validation.
Tests OpenAI function format and MCP discovery responses.
"""

import json
from unittest.mock import Mock, patch

import pytest


def test_tool_schema_generation(validation_tools, mcp_server):
    """Test generation of OpenAI function schemas for MCP tools."""
    # Register tools with mock server
    validation_tools.register_tools(mcp_server)

    # Get tool schemas from server
    tools = mcp_server.list_tools()

    assert len(tools) >= 4  # Should have at least 4 core tools

    # Check that tools have proper schema structure
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool or "parameters" in tool

        # Validate schema structure
        schema = tool.get("inputSchema", tool.get("parameters", {}))
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema


def test_validate_workflow_schema(validation_tools, mcp_server):
    """Test schema for validate_workflow tool."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    # Find validate_workflow tool
    validate_tool = next((t for t in tools if t["name"] == "validate_workflow"), None)
    assert validate_tool is not None

    # Check schema structure
    schema = validate_tool.get("inputSchema", validate_tool.get("parameters", {}))
    assert "workflow_code" in schema["properties"]
    assert schema["properties"]["workflow_code"]["type"] == "string"
    assert "required" in schema
    assert "workflow_code" in schema["required"]


def test_check_node_parameters_schema(validation_tools, mcp_server):
    """Test schema for check_node_parameters tool."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    # Find check_node_parameters tool
    check_tool = next((t for t in tools if t["name"] == "check_node_parameters"), None)
    assert check_tool is not None

    # Check schema structure
    schema = check_tool.get("inputSchema", check_tool.get("parameters", {}))
    assert "node_code" in schema["properties"]
    assert schema["properties"]["node_code"]["type"] == "string"
    assert "required" in schema
    assert "node_code" in schema["required"]


def test_validate_connections_schema(validation_tools, mcp_server):
    """Test schema for validate_connections tool."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    # Find validate_connections tool
    connections_tool = next(
        (t for t in tools if t["name"] == "validate_connections"), None
    )
    assert connections_tool is not None

    # Check schema structure
    schema = connections_tool.get("inputSchema", connections_tool.get("parameters", {}))
    assert "connections" in schema["properties"]
    assert schema["properties"]["connections"]["type"] == "array"
    assert "required" in schema
    assert "connections" in schema["required"]


def test_suggest_fixes_schema(validation_tools, mcp_server):
    """Test schema for suggest_fixes tool."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    # Find suggest_fixes tool
    fixes_tool = next((t for t in tools if t["name"] == "suggest_fixes"), None)
    assert fixes_tool is not None

    # Check schema structure
    schema = fixes_tool.get("inputSchema", fixes_tool.get("parameters", {}))
    assert "errors" in schema["properties"]
    assert schema["properties"]["errors"]["type"] == "array"
    assert "required" in schema
    assert "errors" in schema["required"]


def test_tool_discovery_response(validation_tools, mcp_server):
    """Test MCP tool discovery response format."""
    validation_tools.register_tools(mcp_server)

    # Test discovery response
    discovery_response = mcp_server.get_server_info()

    assert "name" in discovery_response
    assert "version" in discovery_response
    assert discovery_response["name"] == "parameter-validator-test"


def test_tool_execution_response_format(validation_tools):
    """Test that tool execution returns properly formatted responses."""
    # Test validate_workflow response format
    result = validation_tools.validator.validate_workflow("invalid code")

    # Should have standard response structure
    assert "has_errors" in result
    assert "errors" in result
    assert "warnings" in result
    assert isinstance(result["has_errors"], bool)
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)

    # Test with valid suggestions added
    if result["has_errors"]:
        suggestions = validation_tools.suggestion_engine.generate_fixes(
            result["errors"]
        )
        assert isinstance(suggestions, list)


def test_error_response_schema(validation_tools):
    """Test error response schema structure."""
    # Generate an error response
    invalid_code = "invalid python syntax @@#"
    result = validation_tools.validator.validate_workflow(invalid_code)

    if result["has_errors"]:
        for error in result["errors"]:
            # Each error should have required fields
            assert "code" in error
            assert "message" in error
            assert "severity" in error

            # Validate field types
            assert isinstance(error["code"], str)
            assert isinstance(error["message"], str)
            assert error["severity"] in ["error", "warning", "info"]

            # Optional fields
            if "line" in error:
                assert isinstance(error["line"], int)


def test_suggestion_response_schema(suggestion_engine, validation_error_examples):
    """Test suggestion response schema structure."""
    suggestions = suggestion_engine.generate_fixes(validation_error_examples)

    assert isinstance(suggestions, list)

    for suggestion in suggestions:
        # Each suggestion should have required fields
        assert "error_code" in suggestion
        assert "description" in suggestion
        assert "fix" in suggestion

        # Validate field types
        assert isinstance(suggestion["error_code"], str)
        assert isinstance(suggestion["description"], str)
        assert isinstance(suggestion["fix"], str)

        # Optional fields
        if "code_example" in suggestion:
            assert isinstance(suggestion["code_example"], str)


def test_json_serialization(validation_tools):
    """Test that all response objects are JSON serializable."""
    # Test workflow validation response
    result = validation_tools.validator.validate_workflow(
        "from kailash.workflow.builder import WorkflowBuilder"
    )

    try:
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed == result
    except (TypeError, ValueError) as e:
        pytest.fail(f"Response not JSON serializable: {e}")


def test_parameter_schemas_json_types(validation_tools, mcp_server):
    """Test that parameter schemas use correct JSON schema types."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    for tool in tools:
        schema = tool.get("inputSchema", tool.get("parameters", {}))

        # Check that all property types are valid JSON schema types
        for prop_name, prop_schema in schema.get("properties", {}).items():
            assert "type" in prop_schema
            assert prop_schema["type"] in [
                "string",
                "number",
                "integer",
                "boolean",
                "array",
                "object",
                "null",
            ]

            # If array, should have items schema
            if prop_schema["type"] == "array":
                assert "items" in prop_schema

            # If object, may have properties or additionalProperties
            if prop_schema["type"] == "object":
                assert (
                    "properties" in prop_schema or "additionalProperties" in prop_schema
                )


def test_tool_descriptions(validation_tools, mcp_server):
    """Test that all tools have meaningful descriptions."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    for tool in tools:
        assert len(tool["description"]) > 10  # Should have meaningful description
        assert (
            "validate" in tool["description"].lower()
            or "check" in tool["description"].lower()
            or "suggest" in tool["description"].lower()
        )


def test_required_parameters_specification(validation_tools, mcp_server):
    """Test that required parameters are properly specified."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    for tool in tools:
        schema = tool.get("inputSchema", tool.get("parameters", {}))

        if "required" in schema:
            # All required parameters should exist in properties
            for required_param in schema["required"]:
                assert required_param in schema["properties"]

            # Required array should not be empty if it exists
            assert len(schema["required"]) > 0


def test_tool_name_conventions(validation_tools, mcp_server):
    """Test that tool names follow proper conventions."""
    validation_tools.register_tools(mcp_server)
    tools = mcp_server.list_tools()

    expected_tools = {
        "validate_workflow",
        "check_node_parameters",
        "validate_connections",
        "suggest_fixes",
        "validate_gold_standards",
        "get_validation_patterns",
        "check_error_pattern",
    }

    actual_tools = {tool["name"] for tool in tools}

    # Should have all expected core tools
    core_tools = {
        "validate_workflow",
        "check_node_parameters",
        "validate_connections",
        "suggest_fixes",
    }
    assert core_tools.issubset(actual_tools)

    # Tool names should follow snake_case convention
    for tool_name in actual_tools:
        assert "_" in tool_name or tool_name.islower()
        assert (
            tool_name.replace("_", "").isalnum()
            or tool_name.replace("_", "").replace("-", "").isalnum()
        )


def test_schema_validation_edge_cases(validation_tools, mcp_server):
    """Test schema validation with edge cases."""
    validation_tools.register_tools(mcp_server)

    # Test with empty parameters
    try:
        result = validation_tools.validator.validate_workflow("")
        assert "has_errors" in result
    except Exception as e:
        pytest.fail(f"Should handle empty input gracefully: {e}")

    # Test with minimal valid input
    try:
        minimal_code = "workflow = None"
        result = validation_tools.validator.validate_workflow(minimal_code)
        assert "has_errors" in result
    except Exception as e:
        pytest.fail(f"Should handle minimal input gracefully: {e}")


def test_mcp_protocol_compliance(validation_tools, mcp_server):
    """Test MCP protocol compliance."""
    validation_tools.register_tools(mcp_server)

    # Test capabilities response
    capabilities = mcp_server.get_capabilities()
    assert "tools" in capabilities

    # Test tool listing
    tools = mcp_server.list_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0

    # Each tool should have MCP-compliant structure
    for tool in tools:
        required_fields = ["name", "description"]
        for field in required_fields:
            assert field in tool, f"Tool missing required field: {field}"
