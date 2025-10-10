"""
Unit tests for parameter validation rules (PAR001-PAR004).
Tests core validation logic without external dependencies.
"""

from unittest.mock import Mock, patch

import pytest


def test_par001_empty_parameters(
    parameter_validator, node_with_missing_parameters_code
):
    """Test PAR001: Node missing get_parameters() method."""
    result = parameter_validator.validate_node_parameters(
        node_with_missing_parameters_code
    )

    assert result["has_errors"] is True
    assert len(result["errors"]) >= 1

    # Find PAR001 error
    par001_error = next((e for e in result["errors"] if e["code"] == "PAR001"), None)
    assert par001_error is not None
    assert "get_parameters" in par001_error["message"]
    assert par001_error["severity"] == "error"


def test_par002_undeclared_access(parameter_validator):
    """Test PAR002: Parameter used but not declared."""
    # Code that uses parameter not declared in get_parameters()
    code_with_undeclared = """
from kailash.core.nodes.base import BaseNode
from kailash.core.parameter import NodeParameter
from typing import List

class TestNode(BaseNode):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(name="declared_param", type=str, required=True, description="Declared")
        ]
    
    def run(self, **kwargs):
        # Using undeclared parameter
        undeclared_value = kwargs.get("undeclared_param")
        return {"result": undeclared_value}
"""

    result = parameter_validator.validate_node_parameters(code_with_undeclared)

    # Should detect undeclared parameter usage
    assert result["has_errors"] is True
    par002_errors = [e for e in result["errors"] if e["code"] == "PAR002"]
    assert len(par002_errors) >= 1
    assert "undeclared_param" in par002_errors[0]["message"]


def test_par003_missing_type(parameter_validator):
    """Test PAR003: NodeParameter missing type field."""
    code_missing_type = """
from kailash.core.nodes.base import BaseNode
from kailash.core.parameter import NodeParameter
from typing import List

class TestNode(BaseNode):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(name="param", required=True, description="Missing type field")
        ]
    
    def run(self, **kwargs):
        return {"result": "value"}
"""

    result = parameter_validator.validate_node_parameters(code_missing_type)

    assert result["has_errors"] is True
    par003_errors = [e for e in result["errors"] if e["code"] == "PAR003"]
    assert len(par003_errors) >= 1
    assert "type" in par003_errors[0]["message"]


def test_par004_missing_required(parameter_validator):
    """Test PAR004: Missing required parameter."""
    # Workflow that doesn't provide required parameters
    workflow_missing_required = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Node requires parameters but none provided
workflow.add_node("LLMAgentNode", "agent", {})
"""

    result = parameter_validator.validate_workflow(workflow_missing_required)

    assert result["has_errors"] is True
    par004_errors = [e for e in result["errors"] if e["code"] == "PAR004"]
    assert len(par004_errors) >= 1
    assert "required" in par004_errors[0]["message"].lower()


def test_multiple_validation_errors(parameter_validator):
    """Test workflow with multiple validation issues."""
    complex_invalid_workflow = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.core.nodes.base import BaseNode

# Node missing get_parameters (PAR001)
class BadNode(BaseNode):
    def run(self, **kwargs):
        return {"result": "bad"}

workflow = WorkflowBuilder()
# Missing required parameters (PAR004)
workflow.add_node("LLMAgentNode", "agent", {})
# Wrong connection syntax (CON002)
workflow.add_connection("agent", "processor")
"""

    result = parameter_validator.validate_workflow(complex_invalid_workflow)

    assert result["has_errors"] is True
    assert len(result["errors"]) >= 2  # Should have multiple errors

    # Check for different error types
    error_codes = {e["code"] for e in result["errors"]}

    # Should have at least PAR004 (missing required) and CON002 (connection syntax)
    expected_codes = {"PAR004", "CON002"}
    assert expected_codes.intersection(
        error_codes
    ), f"Expected codes {expected_codes}, got {error_codes}"


def test_valid_node_parameters(parameter_validator, node_with_valid_parameters_code):
    """Test that valid node parameters pass validation."""
    result = parameter_validator.validate_node_parameters(
        node_with_valid_parameters_code
    )

    # Should pass validation with no errors
    assert result["has_errors"] is False
    assert len(result["errors"]) == 0

    # Should have no PAR001-PAR004 errors
    par_errors = [e for e in result["errors"] if e["code"].startswith("PAR")]
    assert len(par_errors) == 0


def test_valid_workflow_parameters(parameter_validator, valid_workflow_code):
    """Test that valid workflow passes parameter validation."""
    result = parameter_validator.validate_workflow(valid_workflow_code)

    # May have warnings but should not have critical parameter errors
    critical_errors = [
        e
        for e in result["errors"]
        if e["severity"] == "error" and e["code"].startswith("PAR")
    ]
    assert len(critical_errors) == 0


def test_validation_performance(parameter_validator):
    """Test that validation completes quickly for simple cases."""
    import time

    simple_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "test"})
"""

    start_time = time.time()
    result = parameter_validator.validate_workflow(simple_code)
    end_time = time.time()

    # Should complete in well under 1 second (unit test timeout)
    duration = end_time - start_time
    assert duration < 0.5, f"Validation took {duration}s, should be <0.5s"

    # Result should be returned
    assert "has_errors" in result
    assert "errors" in result


def test_error_severity_levels(parameter_validator):
    """Test that validation errors have appropriate severity levels."""
    invalid_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing required params
"""

    result = parameter_validator.validate_workflow(invalid_code)

    assert result["has_errors"] is True

    # Check that errors have severity levels
    for error in result["errors"]:
        assert "severity" in error
        assert error["severity"] in ["error", "warning", "info"]

        # PAR004 (missing required) should be error severity
        if error["code"] == "PAR004":
            assert error["severity"] == "error"


def test_error_context_information(parameter_validator):
    """Test that errors include helpful context information."""
    code_with_context = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Line 4
"""

    result = parameter_validator.validate_workflow(code_with_context)

    # Should have errors with context
    assert result["has_errors"] is True

    for error in result["errors"]:
        # Should have message
        assert "message" in error
        assert len(error["message"]) > 0

        # Should have error code
        assert "code" in error
        assert error["code"].startswith(("PAR", "CON", "TOOL"))

        # Should have severity
        assert "severity" in error


def test_empty_code_validation(parameter_validator):
    """Test validation of empty or minimal code."""
    empty_code = ""

    # Should handle empty code gracefully
    result = parameter_validator.validate_workflow(empty_code)

    # Should return structured response even for empty code
    assert "has_errors" in result
    assert "errors" in result
    assert "warnings" in result

    # May have errors but shouldn't crash
    assert isinstance(result["errors"], list)


def test_malformed_code_validation(parameter_validator):
    """Test validation of syntactically invalid Python code."""
    malformed_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder(
# Syntax error - missing closing parenthesis
"""

    # Should handle syntax errors gracefully
    result = parameter_validator.validate_workflow(malformed_code)

    # Should return error information
    assert "has_errors" in result
    assert isinstance(result["errors"], list)

    # Should not crash, may have parsing errors
    if result["has_errors"]:
        assert len(result["errors"]) > 0
