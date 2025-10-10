"""
Fix suggestion engine for validation errors.
Provides actionable fixes for common parameter and connection mistakes.
"""

from typing import Any, Dict, List


class FixSuggestionEngine:
    """Generate fix suggestions for validation errors."""

    def __init__(self):
        """Initialize suggestion patterns."""
        self.error_patterns = {
            "PAR001": self._suggest_add_get_parameters,
            "PAR002": self._suggest_declare_parameter,
            "PAR003": self._suggest_add_parameter_type,
            "PAR004": self._suggest_add_required_parameter,
            "CON001": self._suggest_fix_connection_args,
            "CON002": self._suggest_fix_connection_syntax,
            "CON003": self._suggest_fix_missing_source,
            "CON004": self._suggest_fix_missing_target,
            "CON005": self._suggest_fix_circular_dependency,
            "NODE001": self._suggest_fix_unknown_node,
            "SYN001": self._suggest_fix_syntax_error,
            "GOLD002": self._suggest_fix_execution_pattern,
            "CYC001": self._suggest_migrate_cycle_syntax,
            "CYC002": self._suggest_add_cycle_configuration,
            "CYC003": self._suggest_fix_convergence_condition,
            "CYC004": self._suggest_add_cycle_connections,
            "CYC005": self._suggest_fix_cycle_mapping,
            "CYC007": self._suggest_fix_cycle_timeout,
            "CYC008": self._suggest_fix_cycle_node_reference,
            "IMP001": self._suggest_add_missing_import,
            "IMP002": self._suggest_remove_unused_import,
            "IMP003": self._suggest_fix_import_path,
            "IMP004": self._suggest_fix_relative_import,
            "IMP006": self._suggest_fix_import_order,
            "IMP008": self._suggest_optimize_heavy_import,
        }

    def generate_fixes(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate fix suggestions for a list of errors.

        Args:
            errors: List of validation errors

        Returns:
            List of fix suggestions with code examples
        """
        suggestions = []
        seen_suggestions = set()  # Track unique suggestions by description

        for error in errors:
            error_code = error.get("code", "")

            if error_code in self.error_patterns:
                suggestion = self.error_patterns[error_code](error)
                if suggestion:
                    # Create a unique key for this suggestion
                    suggestion_key = (
                        suggestion["error_code"],
                        suggestion["description"],
                    )

                    if suggestion_key not in seen_suggestions:
                        suggestions.append(suggestion)
                        seen_suggestions.add(suggestion_key)
            else:
                # Generic suggestion for unknown errors
                generic_suggestion = {
                    "error_code": error_code,
                    "description": f"Fix needed for: {error.get('message', 'Unknown error')}",
                    "fix": "# Manual fix required",
                    "code_example": "# Manual fix required",
                    "explanation": "This error requires manual attention.",
                }

                suggestion_key = (
                    generic_suggestion["error_code"],
                    generic_suggestion["description"],
                )
                if suggestion_key not in seen_suggestions:
                    suggestions.append(generic_suggestion)
                    seen_suggestions.add(suggestion_key)

        return suggestions

    def _suggest_add_get_parameters(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding get_parameters method to node."""
        # Try different fields that might contain the node type/name
        node_type = (
            error.get("node_type")
            or error.get("node_name")
            or error.get("node_class")
            or "YourNode"
        )

        # If it's LLMAgentNode, provide specific example
        if "LLM" in node_type.upper():
            example_param = 'NodeParameter(\n            name="model",\n            type=str,\n            required=True,\n            description="LLM model to use (e.g., gpt-4)"\n        )'
        else:
            example_param = 'NodeParameter(\n            name="example_param",\n            type=str,\n            required=True,\n            description="Example parameter description"\n        )'

        return {
            "error_code": "PAR001",
            "description": f"Add get_parameters() method to {node_type}",
            "fix": f"Add get_parameters() method to {node_type}",
            "code_example": f'''def get_parameters(self) -> List[NodeParameter]:
    """Define the parameters this node accepts."""
    return [
        {example_param}
    ]''',
            "explanation": "Every node must implement get_parameters() to declare what parameters it accepts. This is a security feature that prevents undeclared parameter usage.",
        }

    def _suggest_declare_parameter(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest declaring an undeclared parameter."""
        param_name = error.get("parameter", "unknown_param")
        node_id = error.get("node_id", "node")

        return {
            "error_code": "PAR002",
            "description": f"Declare parameter '{param_name}' in get_parameters()",
            "fix": f"Declare parameter '{param_name}' in get_parameters()",
            "code_example": f"""# Add to your node's get_parameters() method:
NodeParameter(
    name="{param_name}",
    type=str,  # Replace with appropriate type
    required=True,  # Set to False if optional
    description="Description of {param_name} parameter"
)""",
            "explanation": f"Parameter '{param_name}' is used in node '{node_id}' but not declared in get_parameters(). The SDK filters undeclared parameters for security.",
        }

    def _suggest_add_parameter_type(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding type to NodeParameter."""
        return {
            "error_code": "PAR003",
            "description": "Add type field to NodeParameter",
            "fix": "Add type field to NodeParameter",
            "code_example": """NodeParameter(
    name="parameter_name",
    type=str,  # Add this required field
    required=True,
    description="Parameter description"
)""",
            "explanation": "NodeParameter requires a 'type' field for runtime validation. Common types: str, int, float, bool, dict, list",
        }

    def _suggest_add_required_parameter(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding missing required parameter."""
        # Try multiple field names that might contain the parameter name
        param_name = (
            error.get("parameter_name") or error.get("parameter") or "missing_param"
        )

        # Try multiple field names that might contain the node name
        node_id = error.get("node_name") or error.get("node_id") or "node"

        return {
            "error_code": "PAR004",
            "description": f"Add required parameter '{param_name}' to node '{node_id}'",
            "fix": f"Add required parameter '{param_name}' to node '{node_id}'",
            "code_example": f"""# Add to your add_node call:
workflow.add_node("{error.get('node_type', 'NodeType')}", "{node_id}", {{
    "{param_name}": "your_value_here",  # Add this required parameter
    # ... other parameters
}})""",
            "explanation": f"Node '{node_id}' requires parameter '{param_name}' but it's not provided. You can provide it via node config, workflow connections, or runtime parameters.",
        }

    def _suggest_fix_connection_args(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing connection argument count."""
        arg_count = error.get("arg_count", 0)

        return {
            "error_code": "CON001",
            "description": f"Fix connection with {arg_count} arguments - need exactly 4",
            "fix": "Use 4 parameters for connection",
            "code_example": """# Correct connection syntax:
workflow.add_connection(
    "source_node_id",    # Source node ID
    "output_field",      # Output field name (e.g., "result")
    "target_node_id",    # Target node ID  
    "input_field"        # Input field name (e.g., "input", "data")
)""",
            "explanation": "Connections require exactly 4 parameters: source node, output field, target node, input field.",
        }

    def _suggest_fix_connection_syntax(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing old 2-parameter connection syntax."""
        source = error.get("source", "source_node")
        target = error.get("target", "target_node")

        return {
            "error_code": "CON002",
            "description": "Update to 4-parameter connection syntax",
            "fix": "Update to 4-parameter connection syntax",
            "code_example": f"""# Change from old syntax:
# workflow.add_connection("{source}", "{target}")

# To new 4-parameter syntax:
workflow.add_connection("{source}", "result", "{target}", "input")""",
            "explanation": "The 2-parameter connection syntax is deprecated. Use 4-parameter syntax: add_connection(source, output, target, input)",
        }

    def _suggest_fix_missing_source(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing connection to missing source node."""
        source = error.get("source", "missing_node")

        return {
            "error_code": "CON003",
            "description": f"Add missing source node '{source}' or fix connection",
            "fix": f"Add missing source node '{source}'",
            "code_example": f"""# Option 1: Add the missing source node
workflow.add_node("SomeNodeType", "{source}", {{
    "param": "value"
}})

# Option 2: Fix the connection to use existing node
workflow.add_connection("existing_node", "result", "target_node", "input")""",
            "explanation": f"Connection references source node '{source}' which doesn't exist in the workflow.",
        }

    def _suggest_fix_missing_target(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing connection to missing target node."""
        target = error.get("target", "missing_node")

        return {
            "error_code": "CON004",
            "description": f"Add missing target node '{target}' or fix connection",
            "fix": f"Add missing target node '{target}'",
            "code_example": f"""# Option 1: Add the missing target node
workflow.add_node("SomeNodeType", "{target}", {{
    "param": "value"
}})

# Option 2: Fix the connection to use existing node
workflow.add_connection("source_node", "result", "existing_node", "input")""",
            "explanation": f"Connection references target node '{target}' which doesn't exist in the workflow.",
        }

    def _suggest_fix_circular_dependency(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing circular dependencies."""
        return {
            "error_code": "CON005",
            "description": "Remove circular dependency in connections",
            "fix": "Remove circular dependency in connections",
            "code_example": """# Circular dependency example (BAD):
# Node A -> Node B -> Node C -> Node A

# Fix by breaking the cycle:
# Option 1: Remove one connection
# Option 2: Restructure workflow to be acyclic
# Option 3: Use intermediate nodes to break cycle

# Example linear flow (GOOD):
workflow.add_connection("node_a", "result", "node_b", "input")
workflow.add_connection("node_b", "result", "node_c", "input")
# Remove: workflow.add_connection("node_c", "result", "node_a", "input")""",
            "explanation": "Workflow connections form a circular dependency. Workflows must be directed acyclic graphs (DAGs).",
        }

    def _suggest_fix_unknown_node(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing unknown node type."""
        node_type = error.get("node_type", "UnknownNode")
        node_id = error.get("node_id", "node")

        return {
            "error_code": "NODE001",
            "description": f"Fix unknown node type '{node_type}'",
            "fix": f"Fix unknown node type '{node_type}'",
            "code_example": f"""# Check if node type is correct:
# Common node types: PythonCodeNode, HTTPRequestNode, LLMAgentNode, etc.

# Example fixes:
workflow.add_node("PythonCodeNode", "{node_id}", {{
    "code": "result = {{'output': 'value'}}"
}})

# Or check the Node Selection Guide:
# sdk-users/2-core-concepts/nodes/node-selection-guide.md""",
            "explanation": f"Node type '{node_type}' is not recognized. Check the node name spelling and ensure the node is imported/available.",
        }

    def _suggest_fix_syntax_error(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing Python syntax errors."""
        line = error.get("line", 0)

        return {
            "error_code": "SYN001",
            "description": f"Fix Python syntax error on line {line}",
            "fix": f"Fix Python syntax error on line {line}",
            "code_example": """# Common syntax fixes:
# 1. Missing commas in function calls
# 2. Unmatched parentheses or brackets
# 3. Incorrect indentation
# 4. Missing quotes around strings

# Example:
workflow.add_node("PythonCodeNode", "node_id", {
    "code": "result = {'key': 'value'}"  # Note the quotes
})""",
            "explanation": "Python syntax error in workflow code. Check for missing commas, quotes, parentheses, or indentation issues.",
        }

    def _suggest_fix_execution_pattern(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing execution pattern to use runtime.execute()."""
        return {
            "error_code": "GOLD002",
            "description": "Use correct execution pattern with runtime.execute()",
            "fix": "Use runtime.execute(workflow.build()) pattern",
            "code_example": """# ✅ CORRECT - Use this pattern:
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("PythonCodeNode", "process", {
    "code": "result = {'output': 'value'}"
})

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())""",
            "explanation": "Always use runtime.execute(workflow.build()) - never workflow.execute(runtime). This ensures proper parameter validation and runtime management.",
        }

    def suggest_common_patterns(self) -> List[Dict[str, Any]]:
        """Provide suggestions for common workflow patterns."""
        return [
            {
                "name": "basic_workflow",
                "description": "Basic workflow pattern",
                "code_example": """from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("PythonCodeNode", "process", {
    "code": "result = {'output': input_data}"
})

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())""",
            },
            {
                "name": "connected_nodes",
                "description": "Connected nodes pattern",
                "code_example": """workflow.add_node("HTTPRequestNode", "fetch", {
    "url": "https://api.example.com/data",
    "method": "GET"
})
workflow.add_node("PythonCodeNode", "process", {
    "code": "result = {'processed': data['response']}"
})
workflow.add_connection("fetch", "response", "process", "data")""",
            },
            {
                "name": "parameter_validation",
                "description": "Proper parameter declaration",
                "code_example": """class CustomNode(BaseNode):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(
                name="input_data",
                type=dict,
                required=True,
                description="Input data to process"
            ),
            NodeParameter(
                name="mode", 
                type=str,
                required=False,
                default="standard",
                description="Processing mode"
            )
        ]
    
    def run(self, input_data: dict, mode: str = "standard") -> dict:
        # Process data
        return {"result": "processed"}""",
            },
        ]

    def _suggest_migrate_cycle_syntax(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest migrating from deprecated cycle=True to CycleBuilder API."""
        return {
            "error_code": "CYC001",
            "description": "Migrate from deprecated cycle=True to CycleBuilder API",
            "fix": "Use workflow.create_cycle() API instead of cycle=True parameter",
            "code_example": """# ❌ DEPRECATED - Don't use this:
workflow.add_connection("node1", "output", "node2", "input", cycle=True)

# ✅ CORRECT - Use CycleBuilder API:
cycle_builder = workflow.create_cycle("my_cycle")
cycle_builder.connect("node1", "node2", mapping={"output": "input"})
cycle_builder.max_iterations(50)
cycle_builder.converge_when("condition > threshold")
cycle_builder.build()""",
            "explanation": "The cycle=True parameter is deprecated. Use the CycleBuilder API for better control over cycle behavior including convergence conditions, timeouts, and iteration limits.",
        }

    def _suggest_add_cycle_configuration(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding required cycle configuration."""
        cycle_name = error.get("cycle_name", "my_cycle")
        return {
            "error_code": "CYC002",
            "description": "Add required cycle configuration",
            "fix": "Add either max_iterations() or converge_when() to cycle",
            "code_example": f"""# Add configuration to your cycle:
cycle_builder = workflow.create_cycle("{cycle_name}")
cycle_builder.connect("node1", "node2", mapping={{"output": "input"}})

# Option 1: Use max_iterations
cycle_builder.max_iterations(50)

# Option 2: Use converge_when (recommended)
cycle_builder.converge_when("quality > 0.95")

# Optional: Add timeout for safety
cycle_builder.timeout(300)

cycle_builder.build()""",
            "explanation": "Cycles must have either a maximum iteration limit or a convergence condition to prevent infinite loops.",
        }

    def _suggest_fix_convergence_condition(
        self, error: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest fixing invalid convergence condition."""
        cycle_name = error.get("cycle_name", "my_cycle")
        return {
            "error_code": "CYC003",
            "description": "Fix invalid convergence condition syntax",
            "fix": "Use valid boolean expression for convergence condition",
            "code_example": """# ✅ VALID convergence conditions:
cycle_builder.converge_when("quality > 0.95")
cycle_builder.converge_when("error < 0.01")
cycle_builder.converge_when("quality > 0.95 and iterations < 100")
cycle_builder.converge_when("abs(current - previous) < threshold")

# ❌ INVALID conditions:
# cycle_builder.converge_when("invalid syntax here!")
# cycle_builder.converge_when("quality!")""",
            "explanation": "Convergence conditions must be valid boolean expressions that can be evaluated during cycle execution.",
        }

    def _suggest_add_cycle_connections(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding connections to empty cycle."""
        cycle_name = error.get("cycle_name", "my_cycle")
        return {
            "error_code": "CYC004",
            "description": "Add connections to cycle",
            "fix": "Add at least one connection to the cycle",
            "code_example": f"""# Add connections to your cycle:
cycle_builder = workflow.create_cycle("{cycle_name}")

# Add connections with proper mapping
cycle_builder.connect("source_node", "target_node", mapping={{
    "output_field": "input_field"
}})

# For feedback loops, connect back to source
cycle_builder.connect("target_node", "source_node", mapping={{
    "feedback": "adjustment"
}})

cycle_builder.max_iterations(50)
cycle_builder.build()""",
            "explanation": "Cycles must have at least one connection between nodes to define the cyclic flow.",
        }

    def _suggest_fix_cycle_mapping(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing invalid cycle mapping format."""
        cycle_name = error.get("cycle_name", "my_cycle")
        return {
            "error_code": "CYC005",
            "description": "Fix cycle connection mapping format",
            "fix": "Use dictionary format for mapping parameter",
            "code_example": """# ✅ CORRECT mapping format:
cycle_builder.connect("node1", "node2", mapping={
    "output_field": "input_field",
    "result": "data",
    "status": "feedback"
})

# ❌ INCORRECT mapping formats:
# cycle_builder.connect("node1", "node2", mapping="invalid")
# cycle_builder.connect("node1", "node2", mapping=["list", "format"])""",
            "explanation": "The mapping parameter must be a dictionary that maps output fields from the source node to input fields of the target node.",
        }

    def _suggest_fix_cycle_timeout(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing invalid cycle timeout value."""
        cycle_name = error.get("cycle_name", "my_cycle")
        return {
            "error_code": "CYC007",
            "description": "Fix cycle timeout value",
            "fix": "Use positive number for timeout value",
            "code_example": """# ✅ VALID timeout values:
cycle_builder.timeout(300)    # 5 minutes
cycle_builder.timeout(60)     # 1 minute
cycle_builder.timeout(1800)   # 30 minutes

# ❌ INVALID timeout values:
# cycle_builder.timeout(-1)    # Negative values not allowed
# cycle_builder.timeout(0)     # Zero timeout not allowed
# cycle_builder.timeout("5m")  # String values not allowed""",
            "explanation": "Timeout values must be positive numbers representing seconds. This prevents cycles from running indefinitely.",
        }

    def _suggest_fix_cycle_node_reference(
        self, error: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggest fixing invalid node reference in cycle."""
        cycle_name = error.get("cycle_name", "my_cycle")
        node_name = error.get("node_name", "missing_node")
        return {
            "error_code": "CYC008",
            "description": "Fix non-existent node reference in cycle",
            "fix": f"Add '{node_name}' node or use existing node name",
            "code_example": f"""# Option 1: Add the missing node
workflow.add_node("NodeType", "{node_name}", {{
    "parameter": "value"
}})

# Option 2: Use existing node name in cycle
cycle_builder.connect("existing_node", "other_existing_node", mapping={{
    "output": "input"
}})

# Make sure all referenced nodes exist before creating cycles""",
            "explanation": f"The cycle references node '{node_name}' which doesn't exist in the workflow. Either add this node or use an existing node name.",
        }

    def _suggest_add_missing_import(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest adding missing import statement."""
        missing_name = error.get("missing_name", "WorkflowBuilder")

        # Map common imports to their correct statements
        import_statements = {
            "WorkflowBuilder": "from kailash.workflow.builder import WorkflowBuilder",
            "LocalRuntime": "from kailash.runtime.local import LocalRuntime",
            "ParallelRuntime": "from kailash.runtime.parallel import ParallelRuntime",
            "DockerRuntime": "from kailash.runtime.docker import DockerRuntime",
            "Node": "from kailash.nodes.base import Node",
            "NodeParameter": "from kailash.nodes.base import NodeParameter",
            "NodeRegistry": "from kailash.nodes.base import NodeRegistry",
        }

        import_statement = import_statements.get(
            missing_name, f"# Add appropriate import for '{missing_name}'"
        )

        return {
            "error_code": "IMP001",
            "description": f"Add missing import for '{missing_name}'",
            "fix": "Add import statement at the top of your file",
            "code_example": f"""# ✅ CORRECT - Add this import at the top of your file:
{import_statement}

# Then your workflow code:
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {{"model": "gpt-4"}})
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())""",
            "explanation": f"The code uses '{missing_name}' but doesn't import it. Add the import statement to access Kailash SDK components.",
        }

    def _suggest_remove_unused_import(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest removing unused import statement."""
        import_name = error.get("import_name", "unused_import")
        line = error.get("line", 0)

        return {
            "error_code": "IMP002",
            "description": f"Remove unused import '{import_name}'",
            "fix": f"Delete the unused import statement on line {line}",
            "code_example": """# ❌ WRONG - Unused import:
from kailash.runtime.parallel import ParallelRuntime  # Not used anywhere

# ✅ CORRECT - Only import what you use:
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime  # Only LocalRuntime is used

workflow = WorkflowBuilder()
runtime = LocalRuntime()  # ParallelRuntime removed since not used""",
            "explanation": f"The import '{import_name}' is not used anywhere in the code. Remove unused imports to keep code clean and improve performance.",
        }

    def _suggest_fix_import_path(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing incorrect import path."""
        import_name = error.get("import_name", "WorkflowBuilder")
        current_path = error.get("current_path", "wrong.path")
        correct_path = error.get("correct_path", "kailash.workflow.builder")

        return {
            "error_code": "IMP003",
            "description": f"Fix import path for '{import_name}'",
            "fix": f"Use correct import path for '{import_name}'",
            "code_example": f"""# ❌ WRONG - Incorrect import path:
from {current_path} import {import_name}

# ✅ CORRECT - Use the correct import path:
from {correct_path} import {import_name}

# The correct paths for common Kailash components:
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from kailash.nodes.base import Node, NodeParameter""",
            "explanation": f"The import path '{current_path}' is incorrect for '{import_name}'. Use the correct path '{correct_path}' to properly import Kailash components.",
        }

    def _suggest_fix_relative_import(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing relative import to absolute import."""
        import_name = error.get("import_name", "module")
        line = error.get("line", 0)

        return {
            "error_code": "IMP004",
            "description": "Convert relative import to absolute import",
            "fix": f"Use absolute import instead of relative import for '{import_name}'",
            "code_example": """# ❌ WRONG - Relative imports:
from ..workflow.builder import WorkflowBuilder
from .runtime.local import LocalRuntime

# ✅ CORRECT - Absolute imports:
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# Always use absolute imports for Kailash SDK components:
from kailash.nodes.base import Node, NodeParameter
from kailash.workflow.validation import ParameterDeclarationValidator""",
            "explanation": "Relative imports (starting with . or ..) can cause import issues. Use absolute imports starting with 'kailash' for better compatibility and clarity.",
        }

    def _suggest_fix_import_order(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest fixing import statement order."""
        import_name = error.get("import_name", "import")
        line = error.get("line", 0)

        return {
            "error_code": "IMP006",
            "description": "Reorder imports according to PEP 8",
            "fix": "Reorganize imports in the correct order",
            "code_example": """# ✅ CORRECT - Proper import order (PEP 8):

# 1. Standard library imports first
import os
import sys
from typing import Dict, List

# 2. Third-party imports second
import numpy as np
import pandas as pd

# 3. Kailash SDK imports third
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
from kailash.nodes.base import Node

# 4. Local/relative imports last (if any)
from .my_custom_module import CustomClass""",
            "explanation": "Import statements should be ordered according to PEP 8: standard library, third-party packages, then Kailash SDK imports. This makes code more readable and consistent.",
        }

    def _suggest_optimize_heavy_import(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest optimizing heavy unused imports."""
        import_name = error.get("import_name", "heavy_module")
        line = error.get("line", 0)

        return {
            "error_code": "IMP008",
            "description": f"Remove heavy unused import '{import_name}'",
            "fix": f"Remove or lazy-load the heavy import '{import_name}'",
            "code_example": """# ❌ WRONG - Heavy import not used:
import tensorflow as tf  # Heavy import that slows startup
import torch  # Another heavy import
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()  # tf and torch never used

# ✅ CORRECT - Remove unused heavy imports:
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# ✅ ALTERNATIVE - Lazy loading if sometimes needed:
def process_with_tensorflow(data):
    import tensorflow as tf  # Import only when needed
    # Use tf here
    return tf.process(data)""",
            "explanation": f"Heavy imports like '{import_name}' can significantly slow down startup time. Remove unused heavy imports or use lazy loading to import them only when needed.",
        }
