"""
Test cycle validation suggestions.
"""

import pytest


def test_cycle_migration_suggestions(suggestion_engine):
    """Test suggestions for migrating deprecated cycle syntax."""

    errors = [
        {
            "code": "CYC001",
            "message": "Deprecated 'cycle=True' parameter detected",
            "line": 10,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC001"
    assert "create_cycle" in suggestion["fix"]
    assert "CycleBuilder API" in suggestion["code_example"]


def test_cycle_configuration_suggestions(suggestion_engine):
    """Test suggestions for missing cycle configuration."""

    errors = [
        {
            "code": "CYC002",
            "message": "Cycle 'my_cycle' missing required configuration",
            "cycle_name": "my_cycle",
            "line": 15,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC002"
    assert "max_iterations" in suggestion["code_example"]
    assert "converge_when" in suggestion["code_example"]
    assert "my_cycle" in suggestion["code_example"]


def test_convergence_condition_suggestions(suggestion_engine):
    """Test suggestions for invalid convergence conditions."""

    errors = [
        {
            "code": "CYC003",
            "message": "Cycle 'test_cycle' has invalid convergence condition",
            "cycle_name": "test_cycle",
            "line": 20,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC003"
    assert "quality > 0.95" in suggestion["code_example"]
    assert "boolean expression" in suggestion["explanation"]


def test_cycle_connections_suggestions(suggestion_engine):
    """Test suggestions for empty cycles."""

    errors = [
        {
            "code": "CYC004",
            "message": "Cycle 'empty_cycle' has no connections",
            "cycle_name": "empty_cycle",
            "line": 25,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC004"
    assert "connect" in suggestion["code_example"]
    assert "mapping" in suggestion["code_example"]
    assert "empty_cycle" in suggestion["code_example"]


def test_cycle_mapping_suggestions(suggestion_engine):
    """Test suggestions for invalid cycle mapping."""

    errors = [
        {
            "code": "CYC005",
            "message": "Cycle 'mapping_cycle' has invalid mapping format",
            "cycle_name": "mapping_cycle",
            "line": 30,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC005"
    assert "dictionary" in suggestion["explanation"]
    assert "output_field" in suggestion["code_example"]


def test_cycle_timeout_suggestions(suggestion_engine):
    """Test suggestions for invalid timeout values."""

    errors = [
        {
            "code": "CYC007",
            "message": "Cycle 'timeout_cycle' has invalid timeout value",
            "cycle_name": "timeout_cycle",
            "line": 35,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC007"
    assert "positive number" in suggestion["fix"]
    assert "seconds" in suggestion["explanation"]


def test_cycle_node_reference_suggestions(suggestion_engine):
    """Test suggestions for non-existent node references."""

    errors = [
        {
            "code": "CYC008",
            "message": "Cycle 'ref_cycle' references non-existent node 'missing_node'",
            "cycle_name": "ref_cycle",
            "node_name": "missing_node",
            "line": 40,
            "severity": "error",
        }
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["error_code"] == "CYC008"
    assert "missing_node" in suggestion["code_example"]
    assert "Add the missing node" in suggestion["code_example"]
    assert "missing_node" in suggestion["explanation"]


def test_multiple_cycle_error_suggestions(suggestion_engine):
    """Test suggestions for multiple cycle errors."""

    errors = [
        {
            "code": "CYC001",
            "message": "Deprecated cycle=True parameter",
            "line": 10,
            "severity": "error",
        },
        {
            "code": "CYC002",
            "message": "Missing cycle configuration",
            "cycle_name": "incomplete_cycle",
            "line": 15,
            "severity": "error",
        },
    ]

    suggestions = suggestion_engine.generate_fixes(errors)

    assert len(suggestions) == 2
    error_codes = {s["error_code"] for s in suggestions}
    assert "CYC001" in error_codes
    assert "CYC002" in error_codes
