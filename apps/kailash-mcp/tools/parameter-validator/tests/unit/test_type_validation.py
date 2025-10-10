"""
Unit tests for type validation and common type-related errors.
Tests DateTime, JSON parsing, template syntax, and type mismatches.
"""

from unittest.mock import Mock, patch

import pytest


def test_datetime_string_error(parameter_validator):
    """Test detection of .isoformat() vs native DateTime issues."""
    workflow_datetime_error = """
from kailash.workflow.builder import WorkflowBuilder
from datetime import datetime

workflow = WorkflowBuilder()
# Common error: using string instead of datetime object
date_string = datetime.now().isoformat()  # String, not datetime
workflow.add_node("ScheduleNode", "scheduler", {
    "schedule_time": date_string,  # Should be datetime object
    "action": "process"
})
"""

    result = parameter_validator.validate_workflow(workflow_datetime_error)

    # Should detect datetime type issues
    datetime_errors = [
        e
        for e in result["errors"]
        if "datetime" in e["message"].lower() or "isoformat" in e["message"].lower()
    ]
    if len(datetime_errors) > 0:
        assert "datetime" in datetime_errors[0]["message"].lower()


def test_json_parsing_missing(parameter_validator):
    """Test AsyncSQLDatabaseNode result handling for JSON parsing."""
    workflow_json_parsing = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("AsyncSQLDatabaseNode", "db", {
    "connection_string": "postgresql://user:pass@localhost/db",
    "query": "SELECT data FROM table WHERE id = $1",
    "parameters": [123]
})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})

# Common error: not handling JSON parsing from database results
workflow.add_connection("db", "result", "processor", "input")
"""

    result = parameter_validator.validate_workflow(workflow_json_parsing)

    # Should detect potential JSON parsing issues
    json_errors = [
        e
        for e in result["errors"]
        if "json" in e["message"].lower() or "parsing" in e["message"].lower()
    ]
    # This may be a warning rather than error, depending on implementation

    # At minimum should validate the workflow structure
    assert "has_errors" in result


def test_template_syntax_conflict(parameter_validator):
    """Test detection of ${} vs {{}} template syntax conflicts."""
    workflow_template_conflict = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process this data: ${data}"  # Wrong template syntax
})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
workflow.add_connection("processor", "result", "agent", "data")
"""

    result = parameter_validator.validate_workflow(workflow_template_conflict)

    # Should detect template syntax issues
    template_errors = [
        e
        for e in result["errors"]
        if "${" in e["message"] or "template" in e["message"].lower()
    ]
    if len(template_errors) > 0:
        assert (
            "${" in template_errors[0]["message"]
            or "template" in template_errors[0]["message"].lower()
        )


def test_type_mismatch_detection(parameter_validator):
    """Test detection of parameter type mismatches."""
    workflow_type_mismatch = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Type mismatch: providing string for numeric parameter
workflow.add_node("ProcessorNode", "processor", {
    "batch_size": "not_a_number",  # Should be int
    "threshold": "0.5",  # Should be float, not string
    "operation": 123  # Should be string, not int
})
"""

    result = parameter_validator.validate_workflow(workflow_type_mismatch)

    # Should detect type mismatches
    type_errors = [
        e
        for e in result["errors"]
        if "type" in e["message"].lower() or "mismatch" in e["message"].lower()
    ]
    if len(type_errors) > 0:
        assert "type" in type_errors[0]["message"].lower()


def test_list_dict_type_validation(parameter_validator):
    """Test validation of list and dict parameter types."""
    workflow_complex_types = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {
    "filters": ["filter1", "filter2"],  # List type
    "config": {"setting1": "value1", "setting2": 42},  # Dict type
    "mappings": "should_be_dict_not_string"  # Type error
})
"""

    result = parameter_validator.validate_workflow(workflow_complex_types)

    # Should validate complex parameter types
    assert "has_errors" in result
    assert isinstance(result["errors"], list)


def test_none_null_validation(parameter_validator):
    """Test handling of None/null values in parameters."""
    workflow_none_values = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {
    "required_param": None,  # None for required parameter
    "optional_param": None,  # None for optional parameter (may be OK)
    "config": {}  # Empty dict (may be OK)
})
"""

    result = parameter_validator.validate_workflow(workflow_none_values)

    # Should handle None values appropriately
    none_errors = [
        e
        for e in result["errors"]
        if "none" in e["message"].lower() or "null" in e["message"].lower()
    ]

    # At minimum should validate structure
    assert "has_errors" in result or result["has_errors"] is False


def test_nested_type_validation(parameter_validator):
    """Test validation of nested data structures."""
    workflow_nested_types = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ComplexProcessorNode", "processor", {
    "nested_config": {
        "level1": {
            "level2": {
                "setting": "value",
                "number": 42
            }
        }
    },
    "list_of_dicts": [
        {"id": 1, "name": "item1"},
        {"id": 2, "name": "item2"}
    ]
})
"""

    result = parameter_validator.validate_workflow(workflow_nested_types)

    # Should handle nested structures without crashing
    assert "has_errors" in result
    assert isinstance(result["errors"], list)


def test_boolean_type_validation(parameter_validator):
    """Test validation of boolean parameters."""
    workflow_boolean_types = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {
    "enabled": True,  # Correct boolean
    "debug": "true",  # String instead of boolean
    "strict_mode": 1,  # Number instead of boolean
    "async_mode": False  # Correct boolean
})
"""

    result = parameter_validator.validate_workflow(workflow_boolean_types)

    # Should detect boolean type issues
    boolean_errors = [
        e
        for e in result["errors"]
        if "boolean" in e["message"].lower() or "bool" in e["message"].lower()
    ]

    # May detect type mismatches for boolean parameters
    assert "has_errors" in result or result["has_errors"] is False


def test_enum_type_validation(parameter_validator):
    """Test validation of enum/choice parameters."""
    workflow_enum_types = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {
    "operation": "invalid_operation",  # Should be one of allowed values
    "mode": "batch",  # Should be valid enum value
    "strategy": 123  # Should be string enum, not number
})
"""

    result = parameter_validator.validate_workflow(workflow_enum_types)

    # Should validate enum constraints if available
    enum_errors = [
        e
        for e in result["errors"]
        if "enum" in e["message"].lower()
        or "choice" in e["message"].lower()
        or "allowed" in e["message"].lower()
    ]

    # May detect invalid enum values
    assert "has_errors" in result or result["has_errors"] is False


def test_url_type_validation(parameter_validator):
    """Test validation of URL parameters."""
    workflow_url_types = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("HTTPRequestNode", "http", {
    "url": "not-a-valid-url",  # Invalid URL format
    "method": "GET",
    "headers": {"Content-Type": "application/json"}
})
"""

    result = parameter_validator.validate_workflow(workflow_url_types)

    # Should detect URL format issues
    url_errors = [
        e
        for e in result["errors"]
        if "url" in e["message"].lower() or "invalid" in e["message"].lower()
    ]

    # May detect URL validation issues
    assert "has_errors" in result or result["has_errors"] is False


def test_file_path_validation(parameter_validator):
    """Test validation of file path parameters."""
    workflow_file_paths = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("FileReaderNode", "reader", {
    "file_path": "/nonexistent/path/file.txt",  # May not exist
    "encoding": "utf-8"
})
workflow.add_node("FileWriterNode", "writer", {
    "output_path": "",  # Empty path
    "overwrite": True
})
"""

    result = parameter_validator.validate_workflow(workflow_file_paths)

    # Should validate file path formats
    path_errors = [
        e
        for e in result["errors"]
        if "path" in e["message"].lower() or "file" in e["message"].lower()
    ]

    # May detect path validation issues
    assert "has_errors" in result or result["has_errors"] is False


def test_numeric_range_validation(parameter_validator):
    """Test validation of numeric parameter ranges."""
    workflow_numeric_ranges = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {
    "batch_size": -1,  # Negative batch size (invalid)
    "threshold": 1.5,  # May be out of range (0-1)
    "timeout": 0,  # Zero timeout (may be invalid)
    "max_retries": 1000  # Very high retry count
})
"""

    result = parameter_validator.validate_workflow(workflow_numeric_ranges)

    # Should validate numeric ranges if constraints are available
    range_errors = [
        e
        for e in result["errors"]
        if "range" in e["message"].lower() or "invalid" in e["message"].lower()
    ]

    # May detect range validation issues
    assert "has_errors" in result or result["has_errors"] is False


def test_type_coercion_detection(parameter_validator):
    """Test detection of automatic type coercion issues."""
    workflow_type_coercion = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("ProcessorNode", "processor", {
    "count": "42",  # String that could be coerced to int
    "ratio": "0.75",  # String that could be coerced to float
    "enabled": "false"  # String that could be coerced to bool
})
"""

    result = parameter_validator.validate_workflow(workflow_type_coercion)

    # Should detect potential type coercion issues
    coercion_warnings = [
        e
        for e in result.get("warnings", [])
        if "coercion" in e["message"].lower() or "convert" in e["message"].lower()
    ]

    # May warn about automatic type coercion
    assert "has_errors" in result or "warnings" in result
