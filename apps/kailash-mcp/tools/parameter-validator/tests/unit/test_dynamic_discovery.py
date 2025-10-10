"""
Unit tests for dynamic parameter discovery with NodeRegistry integration.
"""

from typing import List
from unittest.mock import MagicMock, Mock, patch

import pytest

from kailash.nodes.base import NodeParameter


def test_dynamic_parameter_discovery(parameter_validator):
    """Test that validator can discover parameters from NodeRegistry."""
    # Create mock node class with get_parameters
    mock_node_class = Mock()
    mock_node_class.get_parameters = Mock(
        return_value=[
            NodeParameter(name="dynamic_param", type=str, required=True),
            NodeParameter(name="optional_param", type=int, required=False),
        ]
    )

    # Mock NodeRegistry constructor and instance
    mock_registry_instance = Mock()
    mock_registry_instance.get_node_class.return_value = mock_node_class
    mock_registry_constructor = Mock(return_value=mock_registry_instance)

    # Patch the module where NodeRegistry is imported from
    with patch("kailash.nodes.base.NodeRegistry", mock_registry_constructor):
        workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("DynamicTestNode", "test", {"optional_param": 42})
"""

        result = parameter_validator.validate_workflow(workflow_code)

        # Should detect missing required parameter from dynamic discovery
        assert result["has_errors"] is True
        par004_errors = [e for e in result["errors"] if e["code"] == "PAR004"]
        assert len(par004_errors) >= 1
        assert any("dynamic_param" in e["message"] for e in par004_errors)


def test_fallback_to_static_when_registry_fails(parameter_validator):
    """Test fallback to static validation when NodeRegistry is unavailable."""
    # Mock failed registry constructor
    mock_registry_constructor = Mock(side_effect=Exception("Registry error"))

    with patch("kailash.nodes.base.NodeRegistry", mock_registry_constructor):
        workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})
"""

        result = parameter_validator.validate_workflow(workflow_code)

        # Should still detect errors using static definitions
        assert result["has_errors"] is True
        par004_errors = [e for e in result["errors"] if e["code"] == "PAR004"]
        assert len(par004_errors) >= 1


def test_custom_node_dynamic_discovery(parameter_validator):
    """Test discovery of custom node parameters."""

    # Create a custom node class
    class CustomAnalyzerNode:
        @classmethod
        def get_parameters(cls):
            return [
                NodeParameter(name="input_data", type=dict, required=True),
                NodeParameter(name="analysis_type", type=str, required=True),
                NodeParameter(
                    name="threshold", type=float, required=False, default=0.5
                ),
            ]

    mock_registry_instance = Mock()
    mock_registry_instance.get_node_class.return_value = CustomAnalyzerNode
    mock_registry_constructor = Mock(return_value=mock_registry_instance)

    with patch("kailash.nodes.base.NodeRegistry", mock_registry_constructor):
        workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Missing required params
workflow.add_node("CustomAnalyzerNode", "analyzer", {"threshold": 0.8})
"""

        result = parameter_validator.validate_workflow(workflow_code)

        assert result["has_errors"] is True
        par004_errors = [e for e in result["errors"] if e["code"] == "PAR004"]

        # Should detect both missing params
        error_messages = " ".join(e["message"] for e in par004_errors)
        assert "input_data" in error_messages
        assert "analysis_type" in error_messages


def test_cache_discovered_parameters(parameter_validator):
    """Test that discovered parameters are cached for performance."""
    mock_node_class = Mock()
    mock_node_class.get_parameters = Mock(
        return_value=[NodeParameter(name="param1", type=str, required=True)]
    )
    mock_registry_instance = Mock()
    mock_registry_instance.get_node_class.return_value = mock_node_class
    mock_registry_constructor = Mock(return_value=mock_registry_instance)

    with patch("kailash.nodes.base.NodeRegistry", mock_registry_constructor):
        # First validation
        workflow1 = """
workflow = WorkflowBuilder()
workflow.add_node("CachedNode", "node1", {"other_param": "value"})
"""
        parameter_validator.validate_workflow(workflow1)

        # Second validation with same node type
        workflow2 = """
workflow = WorkflowBuilder()
workflow.add_node("CachedNode", "node2", {"other_param": "value"})
"""
        parameter_validator.validate_workflow(workflow2)

        # Registry should be created for first validation due to fresh instance
        # But cache should prevent duplicate lookups
        assert mock_registry_constructor.call_count >= 1  # At least one creation
        assert (
            mock_registry_instance.get_node_class.call_count == 1
        )  # But only one registry lookup due to cache


def test_discover_parameters_from_actual_registry():
    """Test integration with actual NodeRegistry if available."""
    try:
        from kailash.nodes.base import NodeRegistry

        registry = NodeRegistry()

        # Check if we can get actual node classes
        node_types = ["LLMAgentNode", "HTTPRequestNode", "PythonCodeNode"]
        discovered_params = {}

        for node_type in node_types:
            try:
                node_class = registry.get_node_class(node_type)
                if hasattr(node_class, "get_parameters"):
                    params = node_class.get_parameters(node_class)
                    discovered_params[node_type] = [
                        p.name for p in params if p.required
                    ]
            except:
                pass

        # If we discovered any params, use them for validation
        if discovered_params:
            assert "LLMAgentNode" in discovered_params
            assert len(discovered_params["LLMAgentNode"]) > 0

    except ImportError:
        pytest.skip("NodeRegistry not available")


def test_mixed_static_and_dynamic_validation(parameter_validator):
    """Test validation with mix of static and dynamic node types."""

    # Mock registry that only knows about some nodes
    def get_node_side_effect(node_type):
        if node_type == "CustomNode":
            mock_class = Mock()
            mock_class.get_parameters = Mock(
                return_value=[
                    NodeParameter(name="custom_param", type=str, required=True)
                ]
            )
            return mock_class
        else:
            raise KeyError(f"Node {node_type} not in registry")

    mock_registry_instance = Mock()
    mock_registry_instance.get_node_class.side_effect = get_node_side_effect
    mock_registry_constructor = Mock(return_value=mock_registry_instance)

    with patch("kailash.nodes.base.NodeRegistry", mock_registry_constructor):
        workflow_code = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Static validation
workflow.add_node("LLMAgentNode", "agent", {})
# Dynamic validation
workflow.add_node("CustomNode", "custom", {})
"""

        result = parameter_validator.validate_workflow(workflow_code)

        assert result["has_errors"] is True
        errors = result["errors"]

        # Should have errors for both node types
        assert any("LLMAgentNode" in e.get("node_type", "") for e in errors)
        assert any("CustomNode" in e.get("node_type", "") for e in errors)
