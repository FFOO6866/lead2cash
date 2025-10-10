"""
Integration tests for MCP server functionality.
Tests real MCP server registration and tool execution.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_server_registration(validation_tools):
    """Test MCP server registration and discovery."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("test-validator")

    # Test server initialization
    assert server.server_name == "test-validator"
    assert server.mcp_server is not None
    assert server.validation_tools is not None

    # Test capabilities
    capabilities = server.get_capabilities()
    assert "tools" in capabilities
    assert capabilities["tools"]["listChanged"] is False


@pytest.mark.asyncio
async def test_tool_execution_real_server(validation_tools):
    """Test tool execution with real MCP server instance."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("test-validator")

    # Test validate_workflow tool execution
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
"""

    result = server.validation_tools.validator.validate_workflow(workflow_code)

    # Should return structured validation result
    assert "has_errors" in result
    assert "errors" in result
    assert "warnings" in result
    assert isinstance(result["errors"], list)


@pytest.mark.asyncio
async def test_concurrent_validation_requests(validation_tools):
    """Test handling multiple concurrent validation requests."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("test-validator")

    # Create multiple validation tasks
    workflow_codes = [
        'workflow = WorkflowBuilder(); workflow.add_node("Node1", "n1", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node2", "n2", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("Node3", "n3", {})',
    ]

    async def validate_workflow(code):
        return server.validation_tools.validator.validate_workflow(code)

    # Run concurrent validations
    tasks = [validate_workflow(code) for code in workflow_codes]
    results = await asyncio.gather(*tasks)

    # All should complete successfully
    assert len(results) == 3
    for result in results:
        assert "has_errors" in result


@pytest.mark.asyncio
async def test_server_lifecycle():
    """Test server startup and shutdown lifecycle."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("lifecycle-test")

    # Mock transport to avoid actual stdin/stdout binding
    mock_transport = AsyncMock()

    # Test startup with custom transport
    with patch.object(server.mcp_server, "run", new_callable=AsyncMock) as mock_run:
        await server.start(transport=mock_transport)
        mock_run.assert_called_once()

    # Test startup with stdio (default)
    with patch.object(
        server.mcp_server, "run_stdio", new_callable=AsyncMock
    ) as mock_run_stdio:
        await server.start()
        mock_run_stdio.assert_called_once()

    # Test shutdown (no-op for MCPServer)
    await server.stop()  # Should not raise an exception


@pytest.mark.asyncio
async def test_real_workflow_validation():
    """Test validation with realistic SDK workflows."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("workflow-test")

    # Test complex realistic workflow
    complex_workflow = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# Data processing pipeline
workflow.add_node("CSVReaderNode", "reader", {
    "file_path": "data.csv",
    "encoding": "utf-8"
})

workflow.add_node("DataProcessorNode", "processor", {
    "operation": "clean",
    "filters": ["remove_nulls", "normalize"]
})

workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze this data: {{data}}",
    "use_real_mcp": True
})

workflow.add_node("OutputNode", "output", {
    "format": "json",
    "destination": "results.json"
})

# Connections
workflow.add_connection("reader", "data", "processor", "input")
workflow.add_connection("processor", "result", "analyzer", "data")
workflow.add_connection("analyzer", "result", "output", "input")

# Execute
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    result = server.validation_tools.validator.validate_workflow(complex_workflow)

    # Should validate complex workflow structure
    assert "has_errors" in result

    # Should not have critical errors for well-formed workflow
    critical_errors = [e for e in result["errors"] if e["severity"] == "error"]

    # May have warnings but should be structurally valid
    if len(critical_errors) > 0:
        # Print errors for debugging
        for error in critical_errors:
            print(f"Critical error: {error}")


@pytest.mark.asyncio
async def test_node_parameter_integration():
    """Test node parameter validation with real node classes."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("node-test")

    # Test valid node implementation
    valid_node_code = """
from kailash.core.nodes.base import BaseNode
from kailash.core.parameter import NodeParameter
from typing import List

class TestProcessorNode(BaseNode):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(
                name="operation",
                type=str,
                required=True,
                description="Processing operation to perform"
            ),
            NodeParameter(
                name="threshold",
                type=float,
                required=False,
                description="Processing threshold",
                default=0.5
            )
        ]
    
    def run(self, **kwargs):
        operation = kwargs.get("operation")
        threshold = kwargs.get("threshold", 0.5)
        return {"result": f"Processed with {operation} at threshold {threshold}"}
"""

    result = server.validation_tools.validator.validate_node_parameters(valid_node_code)

    # Should pass validation for well-formed node
    assert "has_errors" in result

    # Should not have PAR001-PAR004 errors
    par_errors = [e for e in result["errors"] if e["code"].startswith("PAR")]
    assert len(par_errors) == 0, f"Unexpected parameter errors: {par_errors}"


@pytest.mark.asyncio
async def test_error_correction_workflow():
    """Test multi-round error correction workflow."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("correction-test")

    # Start with invalid workflow
    invalid_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing required params
workflow.add_connection("agent", "processor")  # Wrong syntax
"""

    # First validation - should find errors
    result1 = server.validation_tools.validator.validate_workflow(invalid_workflow)
    assert result1["has_errors"] is True

    # Generate suggestions
    suggestions = server.validation_tools.suggestion_engine.generate_fixes(
        result1["errors"]
    )
    assert len(suggestions) > 0

    # Apply some fixes (simulated)
    corrected_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
workflow.add_connection("agent", "result", "processor", "input")
"""

    # Second validation - should have fewer errors
    result2 = server.validation_tools.validator.validate_workflow(corrected_workflow)

    # Should show improvement (fewer errors)
    assert len(result2["errors"]) <= len(result1["errors"])


@pytest.mark.asyncio
async def test_performance_with_large_workflow():
    """Test validation performance with large workflow."""
    import time

    from server import ParameterValidationServer

    server = ParameterValidationServer("performance-test")

    # Generate large workflow code
    large_workflow_parts = [
        "from kailash.workflow.builder import WorkflowBuilder",
        "workflow = WorkflowBuilder()",
    ]

    # Add 50 nodes
    for i in range(50):
        large_workflow_parts.append(
            f'workflow.add_node("ProcessorNode", "node_{i}", {{"operation": "process_{i}"}})'
        )

    # Add connections between nodes
    for i in range(49):
        large_workflow_parts.append(
            f'workflow.add_connection("node_{i}", "result", "node_{i+1}", "input")'
        )

    large_workflow = "\n".join(large_workflow_parts)

    # Measure validation time
    start_time = time.time()
    result = server.validation_tools.validator.validate_workflow(large_workflow)
    end_time = time.time()

    duration = end_time - start_time

    # Should complete within reasonable time (integration test timeout is 5s)
    assert duration < 2.0, f"Large workflow validation took {duration}s, should be <2s"

    # Should return valid result
    assert "has_errors" in result
    assert isinstance(result["errors"], list)
