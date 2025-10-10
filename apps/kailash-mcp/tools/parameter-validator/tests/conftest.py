"""
Shared test fixtures for MCP parameter validator tests.
"""

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Add the Kailash SDK to the path
sdk_root = Path(__file__).parents[5]  # Go up to kailash_python_sdk root
sys.path.insert(0, str(sdk_root / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import ParameterValidationServer
from suggestions import FixSuggestionEngine
from tools import ParameterValidationTools
from validator import ParameterValidator

from kailash.mcp_server import MCPServer
from kailash.nodes.base import Node, NodeParameter, NodeRegistry
from kailash.workflow.builder import WorkflowBuilder
from kailash.workflow.validation import ParameterDeclarationValidator


@pytest.fixture
def mcp_server():
    """Create MCP server instance for testing."""
    # Create the full parameter validation server (not just basic MCPServer)
    param_server = ParameterValidationServer("parameter-validator-test")
    # Return the underlying MCP server with all methods properly delegated
    return param_server.mcp_server


@pytest.fixture
def parameter_validator():
    """Create parameter validator instance."""
    return ParameterValidator()


@pytest.fixture
def suggestion_engine():
    """Create fix suggestion engine instance."""
    return FixSuggestionEngine()


@pytest.fixture
def validation_tools():
    """Create validation tools instance."""
    return ParameterValidationTools()


@pytest.fixture
def sample_workflow():
    """Create a valid workflow for testing."""
    workflow = WorkflowBuilder()
    workflow.add_node("TestNode", "test", {"param": "value"})
    return workflow


@pytest.fixture
def invalid_workflow():
    """Create workflow with known parameter errors."""
    workflow = WorkflowBuilder()
    # Missing required parameters - will cause PAR004 error
    workflow.add_node("TestNode", "test", {})
    # Wrong connection syntax - will cause CON002 error
    workflow.add_connection("test", "other")
    return workflow


@pytest.fixture
def valid_workflow_code():
    """Python code for a valid workflow."""
    return """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "Hello"})
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""


@pytest.fixture
def invalid_workflow_code():
    """Python code for a workflow with parameter errors."""
    return """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
# Missing required parameters
workflow.add_node("LLMAgentNode", "agent", {})
# Wrong connection syntax (2-param instead of 4-param)
workflow.add_connection("agent", "processor")
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""


@pytest.fixture
def node_with_missing_parameters_code():
    """Node code missing get_parameters() method."""
    return """
from kailash.nodes.base import Node

class TestNode(Node):
    def run(self, **kwargs):
        return {"result": "value"}
"""


@pytest.fixture
def node_with_valid_parameters_code():
    """Node code with proper get_parameters() implementation."""
    return """
from kailash.nodes.base import Node, NodeParameter
from typing import List

class TestNode(Node):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(
                name="input_data",
                type=dict,
                required=True,
                description="Input data to process"
            )
        ]
    
    def run(self, **kwargs):
        return {"result": "value"}
"""


@pytest.fixture
def connection_test_cases():
    """Test cases for connection validation."""
    return [
        {
            "description": "Valid 4-parameter connection",
            "connection": {
                "source": "node1",
                "output": "result",
                "target": "node2",
                "input": "data",
            },
            "should_pass": True,
        },
        {
            "description": "Invalid 2-parameter connection",
            "connection": {"source": "node1", "target": "node2"},
            "should_pass": False,
            "expected_error": "CON002",
        },
        {
            "description": "Missing target parameter",
            "connection": {"source": "node1", "output": "result", "input": "data"},
            "should_pass": False,
            "expected_error": "CON001",
        },
    ]


@pytest.fixture
def validation_error_examples():
    """Examples of validation errors for testing fix suggestions."""
    return [
        {
            "code": "PAR001",
            "message": "Node 'TestNode' missing get_parameters() method",
            "line": 5,
            "severity": "error",
            "node_name": "TestNode",
        },
        {
            "code": "PAR002",
            "message": "Using undeclared parameter 'undeclared_param' in node 'TestNode'",
            "line": 12,
            "severity": "error",
            "node_name": "TestNode",
            "parameter_name": "undeclared_param",
        },
        {
            "code": "CON002",
            "message": "Connection uses old 2-parameter syntax, should use 4 parameters",
            "line": 8,
            "severity": "error",
            "source": "node1",
            "target": "node2",
        },
    ]


@pytest.fixture
def performance_test_workflow():
    """Large workflow for performance testing."""
    workflow = WorkflowBuilder()

    # Create 50 nodes with connections
    for i in range(50):
        workflow.add_node(
            "LLMAgentNode",
            f"agent_{i}",
            {"model": "gpt-4", "prompt": f"Process data {i}"},
        )

        # Connect each node to the next (except last)
        if i > 0:
            workflow.add_connection(f"agent_{i-1}", "result", f"agent_{i}", "prompt")

    return workflow


class TestNodeForValidation(Node):
    """Test node class for validation testing."""

    def get_parameters(self) -> list[NodeParameter]:
        return [
            NodeParameter(
                name="test_param", type=str, required=True, description="Test parameter"
            ),
            NodeParameter(
                name="optional_param",
                type=int,
                required=False,
                description="Optional parameter",
            ),
        ]

    def run(self, **kwargs):
        return {"result": f"Processed: {kwargs.get('test_param', 'default')}"}


class InvalidTestNode(Node):
    """Test node missing get_parameters() for validation testing."""

    def run(self, **kwargs):
        return {"result": "invalid"}


@pytest.fixture
def test_node_class():
    """Valid test node class."""
    return TestNodeForValidation


@pytest.fixture
def invalid_test_node_class():
    """Invalid test node class."""
    return InvalidTestNode


@pytest.fixture
def mcp_tool_schemas():
    """Expected MCP tool schemas for validation."""
    return {
        "validate_workflow": {
            "type": "function",
            "function": {
                "name": "validate_workflow",
                "description": "Validate Kailash workflow for parameter and connection errors.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow_code": {
                            "type": "string",
                            "description": "Python code defining the Kailash workflow",
                        }
                    },
                    "required": ["workflow_code"],
                },
            },
        },
        "check_node_parameters": {
            "type": "function",
            "function": {
                "name": "check_node_parameters",
                "description": "Validate node parameter declarations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_code": {
                            "type": "string",
                            "description": "Python code defining the node class",
                        }
                    },
                    "required": ["node_code"],
                },
            },
        },
    }


# Timeout enforcement for unit tests
@pytest.fixture(autouse=True)
def enforce_test_timeout(request):
    """Enforce timeout limits for different test tiers."""
    test_path = str(request.fspath)

    if "/unit/" in test_path:
        # Unit tests must complete in <1s
        request.node.add_marker(pytest.mark.timeout(1))
    elif "/integration/" in test_path:
        # Integration tests must complete in <5s
        request.node.add_marker(pytest.mark.timeout(5))
    elif "/e2e/" in test_path:
        # E2E tests must complete in <10s
        request.node.add_marker(pytest.mark.timeout(10))
