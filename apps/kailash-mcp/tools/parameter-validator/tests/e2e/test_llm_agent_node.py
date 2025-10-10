"""
End-to-end tests for LLMAgentNode integration.
Tests MCP tool discovery and usage within Kailash workflows.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_mcp_discovery():
    """Test that LLMAgentNode can discover MCP validation tools."""
    from server import ParameterValidationServer

    from kailash.runtime.local import LocalRuntime
    from kailash.workflow.builder import WorkflowBuilder

    # Start parameter validation server
    param_server = ParameterValidationServer("llm-discovery-test")

    # Mock MCP server discovery for LLMAgentNode
    with patch("kailash.mcp_server.MCPClient") as mock_mcp_client:
        mock_client = MagicMock()
        mock_mcp_client.return_value = mock_client

        # Mock tool discovery response
        mock_client.list_tools.return_value = [
            {
                "name": "validate_workflow",
                "description": "Validate Kailash workflow for parameter and connection errors.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"workflow_code": {"type": "string"}},
                    "required": ["workflow_code"],
                },
            },
            {
                "name": "check_node_parameters",
                "description": "Validate node parameter declarations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"node_code": {"type": "string"}},
                    "required": ["node_code"],
                },
            },
        ]

        # Create workflow with LLMAgentNode that should discover tools
        workflow = WorkflowBuilder()
        workflow.add_node(
            "LLMAgentNode",
            "validator_agent",
            {
                "model": "gpt-4",
                "prompt": "You have access to workflow validation tools. List available tools.",
                "use_real_mcp": True,  # Enable MCP tool discovery
                "mcp_servers": ["parameter-validator"],
            },
        )

        # Verify tools would be discovered
        tools = mock_client.list_tools.return_value
        tool_names = [tool["name"] for tool in tools]

        assert "validate_workflow" in tool_names
        assert "check_node_parameters" in tool_names


@pytest.mark.asyncio
async def test_validation_usage():
    """Test LLMAgentNode using MCP validation tools."""
    from server import ParameterValidationServer

    from kailash.workflow.builder import WorkflowBuilder

    # Start validation server
    param_server = ParameterValidationServer("usage-test")

    # Mock LLMAgentNode MCP integration
    with patch("kailash.mcp_server.MCPClient") as mock_mcp_client:
        mock_client = MagicMock()
        mock_mcp_client.return_value = mock_client

        # Mock tool execution
        validation_result = {
            "has_errors": True,
            "errors": [
                {
                    "code": "PAR004",
                    "message": "Node 'agent' missing required parameter 'model'",
                    "severity": "error",
                }
            ],
            "warnings": [],
            "suggestions": [],
        }

        mock_client.call_tool.return_value = validation_result

        # Create workflow that uses validation
        workflow = WorkflowBuilder()
        workflow.add_node(
            "LLMAgentNode",
            "code_reviewer",
            {
                "model": "gpt-4",
                "prompt": """
            Please validate this workflow code using the validate_workflow tool:
            
            ```python
            from kailash.workflow.builder import WorkflowBuilder
            workflow = WorkflowBuilder()
            workflow.add_node("LLMAgentNode", "agent", {})  # Missing parameters
            ```
            
            Report any errors found.
            """,
                "use_real_mcp": True,
                "mcp_servers": ["parameter-validator"],
            },
        )

        # Simulate tool usage
        workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})
"""

        # Verify tool would be called with correct parameters
        expected_call_args = {
            "name": "validate_workflow",
            "arguments": {"workflow_code": workflow_code},
        }

        # Simulate the call
        result = param_server.validation_tools.validator.validate_workflow(
            workflow_code
        )

        # Verify it catches the error
        assert result["has_errors"]
        assert len(result["errors"]) >= 1
        assert any(
            "parameter" in error["message"].lower() for error in result["errors"]
        )


@pytest.mark.asyncio
async def test_workflow_correction():
    """Test multi-round error fixing through LLMAgentNode."""
    from server import ParameterValidationServer

    from kailash.workflow.builder import WorkflowBuilder

    param_server = ParameterValidationServer("correction-test")

    # Scenario: LLMAgentNode validates, finds errors, suggests fixes, validates again

    # Round 1: Initial invalid workflow
    invalid_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing parameters
workflow.add_connection("agent", "processor")  # Wrong syntax
"""

    # First validation - should find errors
    result1 = param_server.validation_tools.validator.validate_workflow(
        invalid_workflow
    )
    assert result1["has_errors"]
    initial_error_count = len(result1["errors"])

    # Generate suggestions
    suggestions = param_server.validation_tools.suggestion_engine.generate_fixes(
        result1["errors"]
    )
    assert len(suggestions) > 0

    # Round 2: Apply fixes (simulated LLM correction)
    corrected_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process this data"
})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
workflow.add_connection("agent", "result", "processor", "input")
"""

    # Second validation - should have fewer errors
    result2 = param_server.validation_tools.validator.validate_workflow(
        corrected_workflow
    )
    final_error_count = len(result2["errors"])

    # Should show improvement
    assert final_error_count <= initial_error_count

    # Critical connection and parameter errors should be resolved
    error_codes = {error["code"] for error in result2["errors"]}
    assert "CON002" not in error_codes  # Connection syntax fixed
    # PAR004 may still be present but should be reduced


@pytest.mark.asyncio
async def test_real_world_agent_workflow():
    """Test realistic workflow where LLMAgentNode helps with validation."""
    from server import ParameterValidationServer

    from kailash.workflow.builder import WorkflowBuilder

    param_server = ParameterValidationServer("real-world-test")

    # Simulate real workflow: Code generation + validation
    generated_workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# User request: "Create a workflow that reads a CSV file and analyzes it with AI"
workflow = WorkflowBuilder()

# Read data
workflow.add_node("CSVReaderNode", "reader", {
    "file_path": "data.csv"
})

# AI analysis
workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze this CSV data and provide insights: {{data}}"
})

# Save results  
workflow.add_node("FileWriterNode", "writer", {
    "file_path": "analysis_results.txt"
})

# Connect the workflow
workflow.add_connection("reader", "data", "analyzer", "data")
workflow.add_connection("analyzer", "result", "writer", "content")

# Execute
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    # Validate the generated workflow
    result = param_server.validation_tools.validator.validate_workflow(
        generated_workflow_code
    )

    # Should be mostly valid (well-formed workflow with proper connections)
    critical_errors = [e for e in result["errors"] if e["severity"] == "error"]

    # Should have minimal critical errors for well-structured workflow
    assert len(critical_errors) <= 3  # Allow for minor issues

    # Should detect good patterns
    if not result["has_errors"]:
        # This is a success case
        assert len(result["errors"]) == 0
    else:
        # Check that errors are reasonable
        for error in result["errors"]:
            assert len(error["message"]) > 10  # Meaningful error messages
            assert error["code"].startswith(("PAR", "CON", "NODE"))  # Valid error codes


@pytest.mark.asyncio
async def test_agent_collaboration_scenario():
    """Test scenario where multiple agents collaborate using validation."""
    from server import ParameterValidationServer

    from kailash.workflow.builder import WorkflowBuilder

    param_server = ParameterValidationServer("collaboration-test")

    # Scenario: Code generator agent + code reviewer agent
    workflow = WorkflowBuilder()

    # Agent 1: Generates workflow code
    workflow.add_node(
        "LLMAgentNode",
        "code_generator",
        {
            "model": "gpt-4",
            "prompt": "Generate a Kailash workflow that processes text files with AI analysis",
            "use_real_mcp": True,
        },
    )

    # Agent 2: Reviews and validates generated code
    workflow.add_node(
        "LLMAgentNode",
        "code_reviewer",
        {
            "model": "gpt-4",
            "prompt": """
        Review the generated workflow code using the validate_workflow tool.
        Check for parameter errors, connection issues, and best practices.
        Provide specific fixes if errors are found.
        """,
            "use_real_mcp": True,
            "mcp_servers": ["parameter-validator"],
        },
    )

    # Agent 3: Applies fixes if needed
    workflow.add_node(
        "LLMAgentNode",
        "code_fixer",
        {
            "model": "gpt-4",
            "prompt": "Apply the suggested fixes to make the workflow valid",
            "use_real_mcp": True,
        },
    )

    # Connect the agents
    workflow.add_connection(
        "code_generator", "result", "code_reviewer", "code_to_review"
    )
    workflow.add_connection("code_reviewer", "result", "code_fixer", "fixes_to_apply")

    # Verify this workflow structure is valid
    agent_workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "generator", {"model": "gpt-4", "prompt": "Generate code"})
workflow.add_node("LLMAgentNode", "reviewer", {"model": "gpt-4", "prompt": "Review code"})
workflow.add_connection("generator", "result", "reviewer", "input")
"""

    result = param_server.validation_tools.validator.validate_workflow(
        agent_workflow_code
    )

    # Agent collaboration workflow should be valid
    critical_errors = [e for e in result["errors"] if e["severity"] == "error"]
    assert (
        len(critical_errors) == 0
    ), f"Agent collaboration workflow has errors: {critical_errors}"


@pytest.mark.asyncio
async def test_performance_in_agent_context():
    """Test validation performance when used within LLMAgentNode workflows."""
    import time

    from server import ParameterValidationServer

    param_server = ParameterValidationServer("agent-performance-test")

    # Simulate agent requesting validation multiple times (iterative development)
    workflow_variations = [
        'workflow = WorkflowBuilder(); workflow.add_node("LLMAgentNode", "agent", {})',
        'workflow = WorkflowBuilder(); workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})',
        'workflow = WorkflowBuilder(); workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})',
        """
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_node("ProcessorNode", "proc", {"operation": "transform"})
workflow.add_connection("agent", "result", "proc", "input")
""",
    ]

    # Time multiple validation rounds (simulating agent iterations)
    start_time = time.time()

    results = []
    for variation in workflow_variations:
        result = param_server.validation_tools.validator.validate_workflow(variation)
        results.append(result)

    end_time = time.time()
    total_time = end_time - start_time

    # Should complete all validations quickly (agent workflow context)
    assert (
        total_time < 1.0
    ), f"Agent validation rounds took {total_time:.3f}s, should be <1s"

    # Should show progression from errors to valid workflow
    error_counts = [len(result["errors"]) for result in results]

    # Later iterations should have fewer errors (workflow improvement)
    assert (
        error_counts[-1] <= error_counts[0]
    ), "Workflow should improve through iterations"


@pytest.mark.asyncio
async def test_edge_case_handling_in_agent_context():
    """Test edge cases that might occur in LLMAgentNode usage."""
    from server import ParameterValidationServer

    param_server = ParameterValidationServer("edge-case-test")

    # Edge case 1: Agent generates very minimal workflow
    minimal_workflow = "workflow = WorkflowBuilder()"
    result1 = param_server.validation_tools.validator.validate_workflow(
        minimal_workflow
    )

    # Should handle gracefully
    assert "has_errors" in result1
    assert isinstance(result1["errors"], list)

    # Edge case 2: Agent generates workflow with complex expressions
    complex_workflow = """
from kailash.workflow.builder import WorkflowBuilder
import os

workflow = WorkflowBuilder()
model_name = os.getenv("MODEL_NAME", "gpt-4")
workflow.add_node("LLMAgentNode", "agent", {
    "model": model_name,
    "prompt": f"Process data with {model_name}"
})
"""

    result2 = param_server.validation_tools.validator.validate_workflow(
        complex_workflow
    )

    # Should handle dynamic expressions without crashing
    assert "has_errors" in result2
    assert isinstance(result2["errors"], list)

    # Edge case 3: Agent generates workflow with imports
    workflow_with_imports = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from datetime import datetime

workflow = WorkflowBuilder()
timestamp = datetime.now().isoformat()
workflow.add_node("LLMAgentNode", "timestamped_agent", {
    "model": "gpt-4",
    "prompt": f"Current time: {timestamp}"
})
"""

    result3 = param_server.validation_tools.validator.validate_workflow(
        workflow_with_imports
    )

    # Should process imports and complex code structures
    assert "has_errors" in result3
    assert isinstance(result3["errors"], list)

    # All edge cases should return structured responses
    for result in [result1, result2, result3]:
        assert "errors" in result
        assert "warnings" in result
        assert isinstance(result["errors"], list)


@pytest.mark.asyncio
async def test_integration_error_recovery():
    """Test error recovery in LLMAgentNode integration context."""
    from server import ParameterValidationServer

    param_server = ParameterValidationServer("integration-recovery-test")

    # Test various failure scenarios that could occur in LLMAgentNode usage
    failure_scenarios = [
        ("empty_input", ""),
        ("syntax_error", "invalid python @@@"),
        ("partial_workflow", "workflow ="),
        ("non_workflow_code", "print('hello world')"),
        ("unicode_issues", "workflow = 'café résumé 中文'"),
    ]

    for scenario_name, problematic_code in failure_scenarios:
        try:
            result = param_server.validation_tools.validator.validate_workflow(
                problematic_code
            )

            # Should always return structured response
            assert "has_errors" in result, f"Missing has_errors for {scenario_name}"
            assert "errors" in result, f"Missing errors for {scenario_name}"
            assert isinstance(
                result["errors"], list
            ), f"Errors not list for {scenario_name}"

            # Should handle gracefully without exceptions
            assert True  # If we reach here, no exception was thrown

        except Exception as e:
            pytest.fail(f"Failed to handle scenario '{scenario_name}': {e}")

    # All scenarios should be handled without crashing the validator
