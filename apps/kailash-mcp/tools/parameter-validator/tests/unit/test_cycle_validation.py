"""
Unit tests for CycleBuilder validation patterns.
"""

from typing import List
from unittest.mock import Mock, patch

import pytest

from kailash.nodes.base import NodeParameter


def test_validate_cycle_builder_syntax(parameter_validator):
    """Test validation of CycleBuilder API syntax."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})

# Correct CycleBuilder usage
cycle_builder = workflow.create_cycle("quality_improvement")
cycle_builder.connect("processor", "evaluator", mapping={"result": "input_data"})
cycle_builder.connect("evaluator", "processor", mapping={"feedback": "adjustment"})
cycle_builder.max_iterations(50)
cycle_builder.converge_when("quality > 0.95")
cycle_builder.timeout(300)
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should not have cycle-specific errors
    cycle_errors = [e for e in result["errors"] if e["code"].startswith("CYC")]
    assert len(cycle_errors) == 0


def test_detect_deprecated_cycle_parameter(parameter_validator):
    """Detect deprecated cycle=True parameter in connections."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})

# Deprecated syntax
workflow.add_connection("processor", "result", "evaluator", "input", cycle=True)
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect deprecated cycle parameter
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC001"]
    assert len(cycle_errors) >= 1
    assert any("deprecated" in e["message"].lower() for e in cycle_errors)


def test_detect_missing_cycle_configuration(parameter_validator):
    """Detect cycle builder without proper configuration."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})

# Missing configuration
cycle_builder = workflow.create_cycle("incomplete_cycle")
cycle_builder.connect("processor", "evaluator", mapping={"result": "input_data"})
cycle_builder.build()  # Missing max_iterations, converge_when, etc.
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect missing cycle configuration
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC002"]
    assert len(cycle_errors) >= 1
    assert any(
        "max_iterations" in e["message"] or "converge_when" in e["message"]
        for e in cycle_errors
    )


def test_detect_invalid_convergence_condition(parameter_validator):
    """Detect invalid convergence conditions."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})

cycle_builder = workflow.create_cycle("invalid_convergence")
cycle_builder.connect("processor", "processor", mapping={"result": "input"})
cycle_builder.max_iterations(10)
cycle_builder.converge_when("invalid syntax here!")  # Invalid condition
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect invalid convergence condition
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC003"]
    assert len(cycle_errors) >= 1
    assert any("convergence" in e["message"].lower() for e in cycle_errors)


def test_detect_cycle_without_connections(parameter_validator):
    """Detect cycle builder without connections."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})

# Cycle without connections
cycle_builder = workflow.create_cycle("empty_cycle")
cycle_builder.max_iterations(10)
cycle_builder.converge_when("quality > 0.95")
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect empty cycle
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC004"]
    assert len(cycle_errors) >= 1
    assert any("connections" in e["message"].lower() for e in cycle_errors)


def test_detect_invalid_cycle_mapping(parameter_validator):
    """Detect invalid mapping syntax in cycle connections."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})

cycle_builder = workflow.create_cycle("invalid_mapping")
cycle_builder.connect("processor", "evaluator", mapping="invalid_mapping_format")  # Should be dict
cycle_builder.max_iterations(10)
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect invalid mapping
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC005"]
    assert len(cycle_errors) >= 1
    assert any("mapping" in e["message"].lower() for e in cycle_errors)


def test_detect_excessive_cycle_iterations(parameter_validator):
    """Detect excessive max_iterations values."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})

cycle_builder = workflow.create_cycle("excessive_iterations")
cycle_builder.connect("processor", "processor", mapping={"result": "input"})
cycle_builder.max_iterations(10000)  # Excessive
cycle_builder.converge_when("quality > 0.95")
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should warn about excessive iterations
    warnings = result.get("warnings", [])
    cycle_warnings = [w for w in warnings if w["code"] == "CYC006"]
    assert len(cycle_warnings) >= 1
    assert any(
        "excessive" in w["message"].lower() or "high" in w["message"].lower()
        for w in cycle_warnings
    )


def test_validate_cycle_timeout_configuration(parameter_validator):
    """Test validation of cycle timeout configuration."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})

cycle_builder = workflow.create_cycle("timeout_test")
cycle_builder.connect("processor", "processor", mapping={"result": "input"})
cycle_builder.max_iterations(10)
cycle_builder.timeout(-1)  # Invalid negative timeout
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect invalid timeout
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC007"]
    assert len(cycle_errors) >= 1
    assert any("timeout" in e["message"].lower() for e in cycle_errors)


def test_validate_cycle_node_references(parameter_validator):
    """Test validation of node references in cycle connections."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})

cycle_builder = workflow.create_cycle("invalid_node_ref")
cycle_builder.connect("processor", "nonexistent_node", mapping={"result": "input"})  # Invalid node ref
cycle_builder.max_iterations(10)
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect invalid node reference
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC008"]
    assert len(cycle_errors) >= 1
    assert any("nonexistent_node" in e["message"] for e in cycle_errors)


def test_suggest_cycle_builder_migration(parameter_validator):
    """Test suggestions for migrating from old cycle syntax."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})

# Old deprecated syntax
workflow.add_connection("processor", "result", "evaluator", "input", cycle=True)
workflow.add_connection("evaluator", "feedback", "processor", "adjustment", cycle=True)
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Should detect deprecated cycle syntax
    assert result["has_errors"] is True
    cycle_errors = [e for e in result["errors"] if e["code"] == "CYC001"]
    assert len(cycle_errors) >= 2  # Should detect both deprecated connections


def test_validate_complex_cycle_patterns(parameter_validator):
    """Test validation of complex multi-node cycles."""
    workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DataProcessorNode", "processor", {"threshold": 0.9})
workflow.add_node("QualityEvaluatorNode", "evaluator", {"target_quality": 0.95})
workflow.add_node("FeedbackGeneratorNode", "feedback", {"sensitivity": 0.1})

# Complex cycle with multiple nodes
cycle_builder = workflow.create_cycle("complex_optimization")
cycle_builder.connect("processor", "evaluator", mapping={"result": "input_data"})
cycle_builder.connect("evaluator", "feedback", mapping={"quality_score": "input"})
cycle_builder.connect("feedback", "processor", mapping={"adjustment": "feedback_data"})
cycle_builder.max_iterations(25)
cycle_builder.converge_when("quality_score > 0.95 and adjustment < 0.01")
cycle_builder.timeout(600)
cycle_builder.build()
"""

    result = parameter_validator.validate_workflow(workflow_code)

    # Complex valid cycle should not have errors
    cycle_errors = [e for e in result["errors"] if e["code"].startswith("CYC")]
    assert len(cycle_errors) == 0
