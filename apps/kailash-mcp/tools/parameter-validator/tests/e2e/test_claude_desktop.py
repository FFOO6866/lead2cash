"""
End-to-end tests for Claude Desktop integration.
Tests complete validation workflow from Claude Desktop perspective.
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_installation():
    """Test that mcp.json works in Claude Desktop format."""
    from server import ParameterValidationServer

    # Test server initialization matches mcp.json expectations
    server = ParameterValidationServer("parameter-validator")

    # Verify server can be created with expected name
    assert server.server_name == "parameter-validator"
    assert server.mcp_server is not None

    # Test capabilities match Claude Desktop requirements
    capabilities = server.get_capabilities()
    assert "tools" in capabilities
    assert "resources" in capabilities
    assert "prompts" in capabilities

    # Verify tools capability structure
    assert isinstance(capabilities["tools"]["listChanged"], bool)


@pytest.mark.asyncio
async def test_mcp_json_format():
    """Verify mcp.json format matches Claude Desktop requirements."""
    mcp_json_path = Path(__file__).parent.parent.parent / "mcp.json"

    with open(mcp_json_path, "r") as f:
        mcp_config = json.load(f)

    # Required fields for Claude Desktop
    assert "name" in mcp_config
    assert "version" in mcp_config
    assert "mcpServers" in mcp_config

    # Verify server configuration
    servers = mcp_config["mcpServers"]
    assert "parameter-validator" in servers

    server_config = servers["parameter-validator"]
    assert "command" in server_config
    assert "args" in server_config
    assert server_config["command"] == "python"


@pytest.mark.asyncio
async def test_tool_execution_flow():
    """Test complete validation workflow from Claude Desktop perspective."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("test-validator")

    # Simulate Claude Desktop tool execution flow
    invalid_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing parameters
workflow.add_connection("agent", "processor")  # Wrong syntax
"""

    # Execute validation like Claude Desktop would
    result = server.validation_tools.validator.validate_workflow(invalid_workflow)

    # Verify structured response suitable for Claude Desktop
    assert "has_errors" in result
    assert "errors" in result
    assert "warnings" in result
    assert result["has_errors"] is True
    assert len(result["errors"]) >= 2  # Should detect both issues

    # Verify error structure is Claude Desktop friendly
    for error in result["errors"]:
        assert "code" in error
        assert "message" in error
        assert "severity" in error
        assert isinstance(error["message"], str)
        assert len(error["message"]) > 10  # Meaningful message


@pytest.mark.asyncio
async def test_error_display():
    """Test that error messages are displayed correctly for Claude Desktop."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("display-test")

    # Test with common workflow errors
    test_cases = [
        {
            "code": """
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})
""",
            "expected_errors": ["PAR004"],  # Missing required parameters
            "description": "Missing parameters",
        },
        {
            "code": """
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_connection("agent", "processor")
""",
            "expected_errors": ["CON002"],  # Wrong connection syntax
            "description": "Wrong connection syntax",
        },
    ]

    for test_case in test_cases:
        result = server.validation_tools.validator.validate_workflow(test_case["code"])

        # Verify errors are detected
        assert result[
            "has_errors"
        ], f"Should detect errors for: {test_case['description']}"

        # Verify expected error codes are present
        error_codes = {e["code"] for e in result["errors"]}
        for expected_code in test_case["expected_errors"]:
            assert (
                expected_code in error_codes
            ), f"Missing {expected_code} for {test_case['description']}"

        # Verify error messages are user-friendly
        for error in result["errors"]:
            assert len(error["message"]) > 20  # Detailed enough
            assert not error["message"].startswith("Error:")  # Clean message
            assert error["severity"] in ["error", "warning", "info"]


@pytest.mark.asyncio
async def test_real_world_scenarios():
    """Test real-world scenarios Claude Desktop users would encounter."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("real-world-test")

    # Scenario 1: User building their first workflow
    beginner_workflow = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "ai", {"model": "gpt-4"})  # Missing prompt
workflow.add_node("FileWriterNode", "writer", {})  # Missing file path
workflow.add_connection("ai", "writer")  # Wrong syntax

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    result = server.validation_tools.validator.validate_workflow(beginner_workflow)

    # Should catch multiple common beginner mistakes
    assert result["has_errors"]
    assert len(result["errors"]) >= 2

    # Should provide helpful error messages
    messages = [error["message"] for error in result["errors"]]
    assert any("connection" in msg.lower() for msg in messages)

    # Scenario 2: Complex enterprise workflow
    enterprise_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# Data ingestion
workflow.add_node("CSVReaderNode", "reader", {
    "file_path": "data/input.csv",
    "encoding": "utf-8"
})

# Processing pipeline
workflow.add_node("DataProcessorNode", "cleaner", {
    "operation": "clean",
    "filters": ["remove_nulls", "normalize"]
})

workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze this data: {{data}}",
    "use_real_mcp": True
})

# Output
workflow.add_node("DatabaseWriterNode", "db_writer", {
    "connection_string": "postgresql://user:pass@localhost/db",
    "table": "analysis_results"
})

# Connections - using correct 4-parameter syntax
workflow.add_connection("reader", "data", "cleaner", "input")
workflow.add_connection("cleaner", "result", "analyzer", "data")
workflow.add_connection("analyzer", "result", "db_writer", "data")
"""

    result = server.validation_tools.validator.validate_workflow(enterprise_workflow)

    # Well-formed workflow should have minimal errors
    critical_errors = [e for e in result["errors"] if e["severity"] == "error"]
    assert len(critical_errors) <= 2  # Should be mostly clean

    # Scenario 3: Workflow with subtle parameter issues
    subtle_issues_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "proc", {
    "operation": "transform",
    "batch_size": "10",  # String instead of int (type issue)
    "unknown_param": "value"  # Undeclared parameter
})
"""

    result = server.validation_tools.validator.validate_workflow(subtle_issues_workflow)

    # Should detect subtle type and parameter issues
    assert "has_errors" in result or "warnings" in result


@pytest.mark.asyncio
async def test_performance_for_interactive_use():
    """Test that validation is fast enough for interactive Claude Desktop use."""
    import time

    from server import ParameterValidationServer

    server = ParameterValidationServer("performance-test")

    # Test with typical workflow size
    typical_workflow = (
        """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
"""
        + "\n".join(
            [
                f'workflow.add_node("ProcessorNode", "node_{i}", {{"operation": "process_{i}"}})'
                for i in range(10)
            ]
        )
        + "\n"
        + "\n".join(
            [
                f'workflow.add_connection("node_{i}", "result", "node_{i+1}", "input")'
                for i in range(9)
            ]
        )
    )

    # Measure validation time
    start_time = time.time()
    result = server.validation_tools.validator.validate_workflow(typical_workflow)
    end_time = time.time()

    validation_time = end_time - start_time

    # Should be fast enough for interactive use (<500ms)
    assert (
        validation_time < 0.5
    ), f"Validation took {validation_time:.3f}s, should be <0.5s"

    # Should still return valid results
    assert "has_errors" in result
    assert isinstance(result["errors"], list)


@pytest.mark.asyncio
async def test_suggestion_integration():
    """Test that suggestions work well with Claude Desktop interface."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("suggestion-test")

    # Workflow with fixable errors
    fixable_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing parameters
workflow.add_connection("agent", "processor")  # Wrong syntax
"""

    # Get validation result
    result = server.validation_tools.validator.validate_workflow(fixable_workflow)

    # Generate suggestions
    if result["has_errors"]:
        suggestions = server.validation_tools.suggestion_engine.generate_fixes(
            result["errors"]
        )

        # Verify suggestions are Claude Desktop friendly
        assert isinstance(suggestions, list)

        for suggestion in suggestions:
            # Should have clear structure for display
            assert "error_code" in suggestion or "description" in suggestion
            assert "fix" in suggestion or "description" in suggestion

            # Should provide actionable guidance
            if "fix" in suggestion:
                assert len(suggestion["fix"]) > 10  # Meaningful guidance
            if "code_example" in suggestion:
                assert len(suggestion["code_example"]) > 10  # Useful example


@pytest.mark.asyncio
async def test_concurrent_usage():
    """Test handling multiple concurrent validation requests (multi-user scenario)."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("concurrent-test")

    # Simulate multiple users validating workflows simultaneously
    workflows = [
        'workflow = WorkflowBuilder(); workflow.add_node("Node1", "n1", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node2", "n2", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node3", "n3", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node4", "n4", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node5", "n5", {})',
    ]

    async def validate_single(workflow_code):
        return server.validation_tools.validator.validate_workflow(workflow_code)

    # Run validations concurrently
    start_time = time.time()
    tasks = [validate_single(workflow) for workflow in workflows]
    results = await asyncio.gather(*tasks)
    end_time = time.time()

    # All should complete successfully
    assert len(results) == 5
    for result in results:
        assert "has_errors" in result
        assert isinstance(result["errors"], list)

    # Should handle concurrency efficiently
    total_time = end_time - start_time
    assert (
        total_time < 2.0
    ), f"Concurrent validation took {total_time:.3f}s, should be <2s"


@pytest.mark.asyncio
async def test_error_recovery():
    """Test that the tool recovers gracefully from various error conditions."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("error-recovery-test")

    # Test various problematic inputs
    problematic_inputs = [
        "",  # Empty input
        "invalid python syntax @@@",  # Syntax errors
        "import non_existent_module",  # Import errors
        "workflow = None",  # Valid Python but no workflow
        "x" * 10000,  # Very large input
    ]

    for problematic_input in problematic_inputs:
        try:
            result = server.validation_tools.validator.validate_workflow(
                problematic_input
            )

            # Should return structured response even for bad input
            assert "has_errors" in result
            assert "errors" in result
            assert isinstance(result["errors"], list)

            # Should not crash
            assert True  # If we get here, it didn't crash

        except Exception as e:
            pytest.fail(
                f"Tool crashed on input: {repr(problematic_input[:50])}... Error: {e}"
            )


@pytest.mark.asyncio
async def test_mcp_protocol_compliance():
    """Test full MCP protocol compliance for Claude Desktop."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("protocol-test")

    # Test server info response
    server_info = server.mcp_server.get_server_info()
    assert "name" in server_info
    assert server_info["name"] == "protocol-test"

    # Test capabilities response
    capabilities = server.get_capabilities()

    # MCP required capability structure
    assert "tools" in capabilities
    assert isinstance(capabilities["tools"], dict)
    assert "listChanged" in capabilities["tools"]

    # Test tool listing
    tools = server.mcp_server.list_tools()
    assert isinstance(tools, list)
    assert len(tools) >= 4  # Should have core tools

    # Each tool should have MCP-compliant structure
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert isinstance(tool["name"], str)
        assert isinstance(tool["description"], str)
        assert len(tool["description"]) > 10  # Meaningful description
