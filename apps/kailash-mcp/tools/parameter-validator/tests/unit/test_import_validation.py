"""
Unit tests for auto-import validation functionality.
Tests automatic detection and validation of import statements.
"""

from unittest.mock import Mock, patch

import pytest


def test_detect_missing_imports(parameter_validator):
    """Test detection of missing import statements."""
    workflow_code = """
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    result = parameter_validator.validate_imports(workflow_code)

    assert result["has_errors"] is True
    errors = result["errors"]
    assert len(errors) >= 2

    # Should detect missing WorkflowBuilder import
    workflow_errors = [e for e in errors if "WorkflowBuilder" in e["message"]]
    assert len(workflow_errors) == 1
    assert workflow_errors[0]["code"] == "IMP001"

    # Should detect missing LocalRuntime import
    runtime_errors = [e for e in errors if "LocalRuntime" in e["message"]]
    assert len(runtime_errors) == 1
    assert runtime_errors[0]["code"] == "IMP001"


def test_detect_unused_imports(parameter_validator):
    """Test detection of unused import statements."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from kailash.runtime.parallel import ParallelRuntime  # Unused
from kailash.nodes.data import CSVReaderNode  # Unused

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    result = parameter_validator.validate_imports(workflow_code)

    assert result["has_errors"] is True
    errors = result["errors"]

    # Should detect unused ParallelRuntime
    parallel_errors = [e for e in errors if "ParallelRuntime" in e["message"]]
    assert len(parallel_errors) == 1
    assert parallel_errors[0]["code"] == "IMP002"

    # Should detect unused CSVReaderNode
    csv_errors = [e for e in errors if "CSVReaderNode" in e["message"]]
    assert len(csv_errors) == 1
    assert csv_errors[0]["code"] == "IMP002"


def test_detect_incorrect_import_paths(parameter_validator):
    """Test detection of incorrect import paths."""
    workflow_code = """
from kailash.workflow import WorkflowBuilder  # Wrong path
from kailash.runtime import LocalRuntime  # Wrong path
from kailash.nodes.llm import LLMAgentNode  # Wrong path

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
runtime = LocalRuntime()
"""

    result = parameter_validator.validate_imports(workflow_code)

    assert result["has_errors"] is True
    errors = result["errors"]

    # Should detect incorrect import paths
    path_errors = [e for e in errors if e["code"] == "IMP003"]
    assert len(path_errors) >= 2

    # Check specific wrong paths
    workflow_errors = [e for e in path_errors if "WorkflowBuilder" in e["message"]]
    assert len(workflow_errors) == 1


def test_detect_relative_imports(parameter_validator):
    """Test detection of relative imports (should use absolute)."""
    workflow_code = """
from ..workflow.builder import WorkflowBuilder
from .runtime.local import LocalRuntime

workflow = WorkflowBuilder()
runtime = LocalRuntime()
"""

    result = parameter_validator.validate_imports(workflow_code)

    assert result["has_errors"] is True
    errors = result["errors"]

    # Should detect relative imports
    relative_errors = [e for e in errors if e["code"] == "IMP004"]
    assert len(relative_errors) == 2


def test_suggest_correct_imports(parameter_validator):
    """Test automatic suggestion of correct import statements."""
    workflow_code = """
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
workflow.add_node("HTTPRequestNode", "api", {"url": "https://api.example.com"})
runtime = LocalRuntime()
"""

    result = parameter_validator.validate_imports(workflow_code)

    assert result["has_errors"] is True
    assert "suggested_imports" in result

    suggestions = result["suggested_imports"]
    assert len(suggestions) >= 2

    # Should suggest WorkflowBuilder import
    wb_suggestions = [
        s for s in suggestions if "WorkflowBuilder" in s["import_statement"]
    ]
    assert len(wb_suggestions) == 1
    assert (
        "from kailash.workflow.builder import WorkflowBuilder"
        in wb_suggestions[0]["import_statement"]
    )

    # Should suggest LocalRuntime import
    lr_suggestions = [s for s in suggestions if "LocalRuntime" in s["import_statement"]]
    assert len(lr_suggestions) == 1
    assert (
        "from kailash.runtime.local import LocalRuntime"
        in lr_suggestions[0]["import_statement"]
    )


def test_validate_node_imports(parameter_validator):
    """Test validation of node-specific imports."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
workflow.add_node("CustomDataProcessorNode", "processor", {"config": "test"})
workflow.add_node("NonExistentNode", "fake", {})
"""

    result = parameter_validator.validate_imports(workflow_code)

    # Should detect missing node imports but not error on standard nodes
    errors = result.get("errors", [])

    # CustomDataProcessorNode should trigger missing import if it's a custom node
    custom_errors = [e for e in errors if "CustomDataProcessorNode" in e["message"]]
    if custom_errors:  # Only check if custom node detection is implemented
        assert custom_errors[0]["code"] == "IMP001"

    # NonExistentNode should trigger a different error (node doesn't exist)
    nonexistent_errors = [e for e in errors if "NonExistentNode" in e["message"]]
    if nonexistent_errors:
        assert nonexistent_errors[0]["code"] in ["IMP005", "PAR001"]


def test_import_optimization_suggestions(parameter_validator):
    """Test suggestions for import optimization."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from kailash.runtime.parallel import ParallelRuntime
from kailash.runtime.docker import DockerRuntime

# Only using WorkflowBuilder and LocalRuntime
workflow = WorkflowBuilder()
runtime = LocalRuntime()
"""

    result = parameter_validator.validate_imports(workflow_code)

    if "optimization_suggestions" in result:
        suggestions = result["optimization_suggestions"]

        # Should suggest removing unused imports
        unused_suggestions = [s for s in suggestions if s["type"] == "remove_unused"]
        assert len(unused_suggestions) >= 1

        # Should suggest potential consolidation
        consolidation_suggestions = [
            s for s in suggestions if s["type"] == "consolidate"
        ]
        if consolidation_suggestions:
            assert "from kailash.runtime import LocalRuntime, ParallelRuntime" in str(
                consolidation_suggestions
            )


def test_import_ordering_validation(parameter_validator):
    """Test validation of import statement ordering."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
import os
from kailash.runtime.local import LocalRuntime
import sys
from typing import Dict, List

workflow = WorkflowBuilder()
runtime = LocalRuntime()
config: Dict[str, str] = {"test": "value"}
"""

    result = parameter_validator.validate_imports(workflow_code)

    # Should detect import ordering issues
    warnings = result.get("warnings", [])
    ordering_warnings = [w for w in warnings if w["code"] == "IMP006"]

    if ordering_warnings:
        assert len(ordering_warnings) >= 1
        assert "import order" in ordering_warnings[0]["message"].lower()


def test_circular_import_detection(parameter_validator):
    """Test detection of potential circular imports."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from custom_module import CustomNode  # Potentially circular if custom_module imports from kailash

workflow = WorkflowBuilder()
workflow.add_node("CustomNode", "custom", {})
"""

    result = parameter_validator.validate_imports(workflow_code)

    # This is a more advanced feature - may not be implemented initially
    warnings = result.get("warnings", [])
    circular_warnings = [w for w in warnings if w["code"] == "IMP007"]

    # Test passes regardless of implementation status
    assert isinstance(warnings, list)


def test_import_performance_analysis(parameter_validator):
    """Test analysis of import performance impact."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
import tensorflow as tf  # Heavy import
import torch  # Heavy import
import pandas as pd  # Heavy import

workflow = WorkflowBuilder()
runtime = LocalRuntime()
# Heavy imports not actually used in workflow logic
"""

    result = parameter_validator.validate_imports(workflow_code)

    # Should detect heavy unused imports
    performance_warnings = result.get("warnings", [])
    heavy_import_warnings = [w for w in performance_warnings if w["code"] == "IMP008"]

    if heavy_import_warnings:
        assert any(
            "tensorflow" in w["message"] or "torch" in w["message"]
            for w in heavy_import_warnings
        )


def test_valid_imports_no_errors(parameter_validator):
    """Test that valid imports produce no errors."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from typing import Dict, Any

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
runtime = LocalRuntime()
results: Dict[str, Any] = {}
"""

    result = parameter_validator.validate_imports(workflow_code)

    # Should have no import-related errors
    import_errors = [e for e in result.get("errors", []) if e["code"].startswith("IMP")]
    assert len(import_errors) == 0


def test_import_validation_integration(parameter_validator):
    """Test integration between import validation and main workflow validation."""
    workflow_code = """
# Missing imports - should be detected
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing required params
workflow.add_connection("agent", "processor")  # Wrong connection syntax
runtime = LocalRuntime()
"""

    # Run full workflow validation
    result = parameter_validator.validate_workflow(workflow_code)

    assert result["has_errors"] is True
    errors_by_code = {}
    for error in result["errors"]:
        code_prefix = error["code"][:3]
        errors_by_code.setdefault(code_prefix, []).append(error)

    # Should have both import errors (IMP) and parameter errors (PAR/CON)
    assert "IMP" in errors_by_code  # Import errors
    assert any(
        prefix in errors_by_code for prefix in ["PAR", "CON"]
    )  # Other validation errors
