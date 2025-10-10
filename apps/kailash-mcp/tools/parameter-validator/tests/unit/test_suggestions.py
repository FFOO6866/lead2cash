"""
Unit tests for fix suggestion generation.
Tests suggestion engine for all error types.
"""

from unittest.mock import Mock, patch

import pytest


def test_parameter_fix_suggestion(suggestion_engine):
    """Test suggestions for parameter-related errors."""
    par001_error = {
        "code": "PAR001",
        "message": "Node 'TestNode' missing get_parameters() method",
        "node_name": "TestNode",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([par001_error])

    assert len(suggestions) >= 1
    par001_suggestion = next(
        (s for s in suggestions if s["error_code"] == "PAR001"), None
    )
    assert par001_suggestion is not None

    # Should suggest adding get_parameters method
    assert "get_parameters" in par001_suggestion["fix"]
    assert "def get_parameters" in par001_suggestion["code_example"]
    assert "NodeParameter" in par001_suggestion["code_example"]


def test_connection_fix_suggestion(suggestion_engine):
    """Test suggestions for connection syntax errors."""
    con002_error = {
        "code": "CON002",
        "message": "Connection uses old 2-parameter syntax, should use 4 parameters",
        "source": "node1",
        "target": "node2",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([con002_error])

    assert len(suggestions) >= 1
    con002_suggestion = next(
        (s for s in suggestions if s["error_code"] == "CON002"), None
    )
    assert con002_suggestion is not None

    # Should suggest 4-parameter syntax
    assert (
        "4 parameters" in con002_suggestion["description"]
        or "4-parameter" in con002_suggestion["description"]
    )
    assert (
        'add_connection("node1", "result", "node2", "input")'
        in con002_suggestion["code_example"]
    )


def test_type_fix_suggestion(suggestion_engine):
    """Test suggestions for type-related errors."""
    type_error = {
        "code": "PAR003",
        "message": "NodeParameter missing type field",
        "parameter_name": "test_param",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([type_error])

    assert len(suggestions) >= 1
    par003_suggestion = next(
        (s for s in suggestions if s["error_code"] == "PAR003"), None
    )
    assert par003_suggestion is not None

    # Should suggest adding type field
    assert "type" in par003_suggestion["fix"]
    assert "type=" in par003_suggestion["code_example"]


def test_multiple_error_suggestions(suggestion_engine, validation_error_examples):
    """Test suggestions for multiple errors."""
    suggestions = suggestion_engine.generate_fixes(validation_error_examples)

    # Should have suggestions for all error types
    assert len(suggestions) >= len(validation_error_examples)

    # Should have suggestions for different error codes
    error_codes = {s["error_code"] for s in suggestions}
    expected_codes = {"PAR001", "PAR002", "CON002"}
    assert expected_codes.issubset(error_codes)


def test_suggestion_structure(suggestion_engine, validation_error_examples):
    """Test that suggestions have proper structure."""
    suggestions = suggestion_engine.generate_fixes(validation_error_examples)

    for suggestion in suggestions:
        # Required fields
        assert "error_code" in suggestion
        assert "description" in suggestion
        assert "fix" in suggestion
        assert "code_example" in suggestion

        # Field types
        assert isinstance(suggestion["error_code"], str)
        assert isinstance(suggestion["description"], str)
        assert isinstance(suggestion["fix"], str)
        assert isinstance(suggestion["code_example"], str)

        # Content validation
        assert len(suggestion["description"]) > 10
        assert len(suggestion["fix"]) > 5
        assert len(suggestion["code_example"]) > 10


def test_par004_missing_required_suggestion(suggestion_engine):
    """Test suggestion for missing required parameters."""
    par004_error = {
        "code": "PAR004",
        "message": "Missing required parameter 'model' for node 'agent'",
        "node_name": "agent",
        "parameter_name": "model",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([par004_error])

    par004_suggestion = next(
        (s for s in suggestions if s["error_code"] == "PAR004"), None
    )
    assert par004_suggestion is not None

    # Should suggest providing the required parameter
    assert "model" in par004_suggestion["fix"]
    assert "agent" in par004_suggestion["code_example"]
    assert '"model"' in par004_suggestion["code_example"]


def test_con003_nonexistent_source_suggestion(suggestion_engine):
    """Test suggestion for non-existent source node."""
    con003_error = {
        "code": "CON003",
        "message": "Connection source node 'nonexistent' not found",
        "source": "nonexistent",
        "target": "valid_node",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([con003_error])

    con003_suggestion = next(
        (s for s in suggestions if s["error_code"] == "CON003"), None
    )
    assert con003_suggestion is not None

    # Should suggest creating the node or fixing the reference
    assert (
        "add_node" in con003_suggestion["code_example"]
        or "nonexistent" in con003_suggestion["fix"]
    )


def test_con004_nonexistent_target_suggestion(suggestion_engine):
    """Test suggestion for non-existent target node."""
    con004_error = {
        "code": "CON004",
        "message": "Connection target node 'missing_target' not found",
        "source": "valid_node",
        "target": "missing_target",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([con004_error])

    con004_suggestion = next(
        (s for s in suggestions if s["error_code"] == "CON004"), None
    )
    assert con004_suggestion is not None

    # Should suggest creating the target node
    assert (
        "add_node" in con004_suggestion["code_example"]
        or "missing_target" in con004_suggestion["fix"]
    )


def test_con005_circular_dependency_suggestion(suggestion_engine):
    """Test suggestion for circular dependency."""
    con005_error = {
        "code": "CON005",
        "message": "Circular dependency detected in workflow",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([con005_error])

    con005_suggestion = next(
        (s for s in suggestions if s["error_code"] == "CON005"), None
    )
    assert con005_suggestion is not None

    # Should suggest removing or restructuring connections
    assert "circular" in con005_suggestion["description"].lower()
    assert (
        "remove" in con005_suggestion["fix"].lower()
        or "restructure" in con005_suggestion["fix"].lower()
    )


def test_gold_standard_suggestions(suggestion_engine):
    """Test suggestions for gold standard violations."""
    gold_error = {
        "code": "GOLD002",
        "message": "Use 'runtime.execute(workflow.build())' not 'workflow.execute(runtime)'",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([gold_error])

    gold_suggestion = next(
        (s for s in suggestions if s["error_code"] == "GOLD002"), None
    )
    assert gold_suggestion is not None

    # Should suggest correct execution pattern
    assert "runtime.execute(workflow.build())" in gold_suggestion["code_example"]
    assert "workflow.execute(runtime)" not in gold_suggestion["code_example"]


def test_common_patterns_suggestions(suggestion_engine):
    """Test common pattern suggestions."""
    common_patterns = suggestion_engine.suggest_common_patterns()

    assert isinstance(common_patterns, list)
    assert len(common_patterns) > 0

    for pattern in common_patterns:
        assert "name" in pattern
        assert "description" in pattern
        assert "code_example" in pattern

        # Should have meaningful patterns
        assert len(pattern["description"]) > 10
        assert len(pattern["code_example"]) > 20


def test_suggestion_prioritization(suggestion_engine):
    """Test that suggestions are prioritized by importance."""
    high_priority_errors = [
        {"code": "PAR001", "message": "Missing get_parameters", "severity": "error"},
        {"code": "CON002", "message": "Wrong connection syntax", "severity": "error"},
    ]

    low_priority_errors = [
        {"code": "GOLD001", "message": "Prefer absolute imports", "severity": "warning"}
    ]

    high_suggestions = suggestion_engine.generate_fixes(high_priority_errors)
    low_suggestions = suggestion_engine.generate_fixes(low_priority_errors)

    # High priority errors should get more detailed suggestions
    assert len(high_suggestions) >= len(low_suggestions)

    for suggestion in high_suggestions:
        assert len(suggestion["code_example"]) > 10


def test_contextual_suggestions(suggestion_engine):
    """Test that suggestions are contextual to the specific error."""
    # Test node-specific suggestion
    node_error = {
        "code": "PAR001",
        "message": "Node 'LLMAgentNode' missing get_parameters() method",
        "node_name": "LLMAgentNode",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([node_error])
    llm_suggestion = next((s for s in suggestions if s["error_code"] == "PAR001"), None)

    # Should reference the specific node type
    assert (
        "LLMAgentNode" in llm_suggestion["code_example"]
        or "LLM" in llm_suggestion["description"]
    )


def test_code_example_syntax(suggestion_engine, validation_error_examples):
    """Test that code examples are syntactically valid."""
    suggestions = suggestion_engine.generate_fixes(validation_error_examples)

    for suggestion in suggestions:
        code_example = suggestion["code_example"]

        # Basic syntax checks
        assert code_example.count("(") == code_example.count(
            ")"
        )  # Balanced parentheses
        assert code_example.count("[") == code_example.count("]")  # Balanced brackets
        assert code_example.count("{") == code_example.count("}")  # Balanced braces

        # Should not have obvious syntax errors
        assert not code_example.strip().endswith(",")  # No trailing commas
        assert (
            "def " not in code_example or ":" in code_example
        )  # Function definitions have colons


def test_suggestion_uniqueness(suggestion_engine):
    """Test that suggestions don't repeat for the same error."""
    duplicate_errors = [
        {"code": "PAR001", "message": "Missing get_parameters", "severity": "error"},
        {"code": "PAR001", "message": "Missing get_parameters", "severity": "error"},
    ]

    suggestions = suggestion_engine.generate_fixes(duplicate_errors)

    # Should deduplicate suggestions for same error type
    par001_suggestions = [s for s in suggestions if s["error_code"] == "PAR001"]

    # Should not have identical suggestions
    descriptions = [s["description"] for s in par001_suggestions]
    assert len(descriptions) == len(set(descriptions)), "Suggestions should be unique"


def test_empty_error_list(suggestion_engine):
    """Test handling of empty error list."""
    suggestions = suggestion_engine.generate_fixes([])

    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_unknown_error_code(suggestion_engine):
    """Test handling of unknown error codes."""
    unknown_error = {
        "code": "UNKNOWN999",
        "message": "Unknown error type",
        "severity": "error",
    }

    suggestions = suggestion_engine.generate_fixes([unknown_error])

    # Should handle unknown error codes gracefully
    assert isinstance(suggestions, list)

    # May provide generic suggestion or skip unknown codes
    if len(suggestions) > 0:
        generic_suggestion = suggestions[0]
        assert "error_code" in generic_suggestion


def test_malformed_error_structure(suggestion_engine):
    """Test handling of malformed error objects."""
    malformed_errors = [
        {"message": "Missing code field"},  # Missing code
        {"code": "PAR001"},  # Missing message
        {},  # Completely empty
    ]

    # Should handle malformed errors gracefully without crashing
    try:
        suggestions = suggestion_engine.generate_fixes(malformed_errors)
        assert isinstance(suggestions, list)
    except Exception as e:
        pytest.fail(f"Should handle malformed errors gracefully: {e}")


def test_suggestion_performance(suggestion_engine):
    """Test that suggestion generation is fast."""
    import time

    # Generate many errors
    many_errors = []
    for i in range(20):
        many_errors.append(
            {"code": "PAR001", "message": f"Error {i}", "severity": "error"}
        )

    start_time = time.time()
    suggestions = suggestion_engine.generate_fixes(many_errors)
    end_time = time.time()

    duration = end_time - start_time
    assert duration < 0.5, f"Suggestion generation took {duration}s, should be <0.5s"

    assert len(suggestions) > 0
