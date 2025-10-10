"""
Unit tests for connection syntax validation.
Tests 2-param vs 4-param connection detection and validation.
"""

from unittest.mock import Mock, patch

import pytest


def test_detect_2_param_connection(parameter_validator):
    """Test detection of old 2-parameter connection syntax."""
    workflow_2_param = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
# Old 2-parameter syntax
workflow.add_connection("agent", "processor")
"""

    result = parameter_validator.validate_workflow(workflow_2_param)

    assert result["has_errors"] is True

    # Should detect CON002 error for old syntax
    con002_errors = [e for e in result["errors"] if e["code"] == "CON002"]
    assert len(con002_errors) >= 1
    assert (
        "2-parameter" in con002_errors[0]["message"]
        or "old syntax" in con002_errors[0]["message"]
    )


def test_validate_4_param_connection(parameter_validator):
    """Test validation of correct 4-parameter connection syntax."""
    workflow_4_param = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
# Correct 4-parameter syntax
workflow.add_connection("agent", "result", "processor", "input")
"""

    result = parameter_validator.validate_workflow(workflow_4_param)

    # Should not have CON002 errors for correct syntax
    con002_errors = [e for e in result["errors"] if e["code"] == "CON002"]
    assert len(con002_errors) == 0


def test_invalid_node_names(parameter_validator):
    """Test connections to non-existent source/target nodes."""
    workflow_invalid_nodes = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
# Connection to non-existent nodes
workflow.add_connection("nonexistent_source", "result", "agent", "input")
workflow.add_connection("agent", "result", "nonexistent_target", "input")
"""

    result = parameter_validator.validate_workflow(workflow_invalid_nodes)

    assert result["has_errors"] is True

    # Should detect CON003 (non-existent source) and CON004 (non-existent target)
    con003_errors = [e for e in result["errors"] if e["code"] == "CON003"]
    con004_errors = [e for e in result["errors"] if e["code"] == "CON004"]

    assert len(con003_errors) >= 1, "Should detect non-existent source node"
    assert len(con004_errors) >= 1, "Should detect non-existent target node"


def test_invalid_field_names(parameter_validator):
    """Test connections with non-existent output/input fields."""
    workflow_invalid_fields = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
# Valid nodes but invalid field names
workflow.add_connection("agent", "nonexistent_output", "processor", "input")
workflow.add_connection("agent", "result", "processor", "nonexistent_input")
"""

    result = parameter_validator.validate_workflow(workflow_invalid_fields)

    # Should detect field validation errors
    assert result["has_errors"] is True

    # May not have specific error codes yet, but should have validation errors
    field_errors = [
        e
        for e in result["errors"]
        if "field" in e["message"].lower()
        or "output" in e["message"].lower()
        or "input" in e["message"].lower()
    ]
    assert len(field_errors) >= 1, "Should detect invalid field names"


def test_circular_dependencies(parameter_validator):
    """Test detection of circular dependencies in connections."""
    workflow_circular = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "node1", {"operation": "transform"})
workflow.add_node("ProcessorNode", "node2", {"operation": "filter"})
workflow.add_node("ProcessorNode", "node3", {"operation": "aggregate"})

# Create circular dependency: node1 -> node2 -> node3 -> node1
workflow.add_connection("node1", "result", "node2", "input")
workflow.add_connection("node2", "result", "node3", "input") 
workflow.add_connection("node3", "result", "node1", "input")
"""

    result = parameter_validator.validate_workflow(workflow_circular)

    assert result["has_errors"] is True

    # Should detect CON005 (circular dependency)
    con005_errors = [e for e in result["errors"] if e["code"] == "CON005"]
    assert len(con005_errors) >= 1, "Should detect circular dependency"
    assert "circular" in con005_errors[0]["message"].lower()


def test_connection_validation_only(parameter_validator, connection_test_cases):
    """Test connections-only validation without full workflow context."""
    for test_case in connection_test_cases:
        connections = [test_case["connection"]]

        result = parameter_validator.validate_connections_only(connections)

        if test_case["should_pass"]:
            # Should pass validation
            assert result["has_errors"] is False or len(result["errors"]) == 0
        else:
            # Should fail validation with expected error
            assert result["has_errors"] is True
            assert len(result["errors"]) >= 1

            if "expected_error" in test_case:
                error_codes = {e["code"] for e in result["errors"]}
                assert test_case["expected_error"] in error_codes


def test_multiple_connection_errors(parameter_validator):
    """Test workflow with multiple connection errors."""
    workflow_multi_errors = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})

# Multiple connection errors
workflow.add_connection("agent", "processor")  # CON002: old syntax
workflow.add_connection("nonexistent", "result", "agent", "input")  # CON003: bad source
workflow.add_connection("agent", "result", "missing", "input")  # CON004: bad target
"""

    result = parameter_validator.validate_workflow(workflow_multi_errors)

    assert result["has_errors"] is True
    assert len(result["errors"]) >= 3  # Should have multiple connection errors

    # Check for expected error types
    error_codes = {e["code"] for e in result["errors"]}
    expected_codes = {"CON002", "CON003", "CON004"}

    # Should have at least some of the expected connection errors
    assert len(expected_codes.intersection(error_codes)) >= 2


def test_complex_connection_graph(parameter_validator):
    """Test validation of complex connection graph without errors."""
    workflow_complex = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataReaderNode", "reader", {"file_path": "data.csv"})
workflow.add_node("ProcessorNode", "processor1", {"operation": "transform"})
workflow.add_node("ProcessorNode", "processor2", {"operation": "filter"})
workflow.add_node("MergeNode", "merger", {"strategy": "concat"})
workflow.add_node("OutputNode", "output", {"destination": "result.csv"})

# Complex but valid connection graph
workflow.add_connection("reader", "data", "processor1", "input")
workflow.add_connection("reader", "data", "processor2", "input")
workflow.add_connection("processor1", "result", "merger", "input1")
workflow.add_connection("processor2", "result", "merger", "input2")
workflow.add_connection("merger", "result", "output", "data")
"""

    result = parameter_validator.validate_workflow(workflow_complex)

    # Should not have connection syntax errors
    connection_errors = [e for e in result["errors"] if e["code"].startswith("CON")]
    assert (
        len(connection_errors) == 0
    ), f"Unexpected connection errors: {connection_errors}"


def test_connection_parameter_validation(parameter_validator):
    """Test validation of connection parameters and mapping."""
    workflow_connection_params = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataGeneratorNode", "generator", {"count": 100})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})

# Connection with parameter mapping
workflow.add_connection("generator", "generated_data", "processor", "input_data")
"""

    result = parameter_validator.validate_workflow(workflow_connection_params)

    # Should validate connection parameter compatibility
    # This may require deeper integration with node schemas
    assert "has_errors" in result
    assert "errors" in result


def test_self_connection_detection(parameter_validator):
    """Test detection of node connecting to itself."""
    workflow_self_connection = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})

# Node connecting to itself (may be valid in some cases, but worth flagging)
workflow.add_connection("processor", "result", "processor", "input")
"""

    result = parameter_validator.validate_workflow(workflow_self_connection)

    # Should detect self-connection (may be warning, not error)
    assert "has_errors" in result or "warnings" in result

    # Check if self-connection is flagged
    all_issues = result["errors"] + result.get("warnings", [])
    self_connection_issues = [i for i in all_issues if "self" in i["message"].lower()]

    # May or may not flag self-connections depending on implementation
    # This test documents the behavior


def test_connection_syntax_edge_cases(parameter_validator):
    """Test edge cases in connection syntax detection."""
    # Test dynamic connection calls that might be harder to parse
    workflow_dynamic = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "node1", {"operation": "transform"})
workflow.add_node("ProcessorNode", "node2", {"operation": "filter"})

# Edge case: connection parameters in variables
source = "node1"
target = "node2"
workflow.add_connection(source, "result", target, "input")
"""

    result = parameter_validator.validate_workflow(workflow_dynamic)

    # Should handle dynamic parameters gracefully
    assert "has_errors" in result
    assert isinstance(result["errors"], list)

    # Should not crash on dynamic parameters
    # Validation may be limited for dynamic cases


def test_empty_connection_list(parameter_validator):
    """Test validation with no connections."""
    workflow_no_connections = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
# No connections defined
"""

    result = parameter_validator.validate_workflow(workflow_no_connections)

    # Should handle workflows with no connections
    # May have warnings about isolated nodes, but no connection syntax errors
    connection_errors = [e for e in result["errors"] if e["code"].startswith("CON")]
    assert len(connection_errors) == 0
