"""
Core parameter validation orchestrator.
Reuses existing Kailash SDK validation components.
"""

import ast
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

# Add SDK paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from kailash.nodes.base import Node, NodeParameter, NodeRegistry
from kailash.runtime.local import LocalRuntime
from kailash.workflow.builder import WorkflowBuilder
from kailash.workflow.validation import ParameterDeclarationValidator


@dataclass
class ValidationResult:
    """Result of workflow validation."""

    has_errors: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]


class ParameterValidator:
    """Main validation orchestrator using existing SDK components."""

    def __init__(self):
        """Initialize with existing SDK validators."""
        self.param_validator = ParameterDeclarationValidator()
        self._param_cache = {}  # Cache for discovered parameters

    def validate_workflow(self, workflow_code: str) -> Dict[str, Any]:
        """
        Validate complete workflow using existing SDK validation.

        Args:
            workflow_code: Python code defining the workflow

        Returns:
            Validation result with errors and suggestions
        """
        try:
            # Parse the workflow code
            tree = ast.parse(workflow_code)

            # Extract workflow information
            workflow_info = self._extract_workflow_info(tree)

            if not workflow_info:
                return {
                    "has_errors": False,
                    "errors": [],
                    "warnings": [],
                    "suggestions": [],
                }

            # Validate using existing SDK components
            errors = []
            warnings = []

            # 1. Validate node parameters using ParameterDeclarationValidator
            param_errors = self._validate_node_parameters(workflow_info)
            errors.extend(param_errors)

            # 2. Validate connection syntax
            connection_errors = self._validate_connections(workflow_info)
            errors.extend(connection_errors)

            # 3. Validate node existence
            node_errors = self._validate_node_existence(workflow_info)
            errors.extend(node_errors)

            # 4. Check for circular dependencies
            circular_errors = self._validate_no_circular_dependencies(workflow_info)
            errors.extend(circular_errors)

            # 5. Validate cycle builder patterns
            cycle_errors, cycle_warnings = self._validate_cycle_patterns(
                workflow_info, tree
            )
            errors.extend(cycle_errors)
            warnings.extend(cycle_warnings)

            # 6. Validate imports
            import_result = self.validate_imports(workflow_code)
            if import_result.get("has_errors", False):
                errors.extend(import_result.get("errors", []))
            warnings.extend(import_result.get("warnings", []))

            result = {
                "has_errors": len(errors) > 0,
                "errors": errors,
                "warnings": warnings,
                "suggestions": [],  # Will be filled by suggestion engine
            }

            # Add import-specific information if available
            if import_result.get("suggested_imports"):
                result["suggested_imports"] = import_result["suggested_imports"]
            if import_result.get("optimization_suggestions"):
                result["optimization_suggestions"] = import_result[
                    "optimization_suggestions"
                ]

            # 7. Analyze complexity (optional, for detailed analysis)
            complexity_result = self.analyze_complexity(workflow_code)
            if complexity_result.get("has_analysis", False):
                result["complexity_analysis"] = complexity_result

            return result

        except SyntaxError as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "SYN001",
                        "message": f"Syntax error in workflow code: {str(e)}",
                        "line": getattr(e, "lineno", 0),
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "suggestions": [],
            }
        except Exception as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "VAL001",
                        "message": f"Validation error: {str(e)}",
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "suggestions": [],
            }

    def validate_node_parameters(self, node_code: str) -> Dict[str, Any]:
        """
        Validate node parameter declarations.

        Args:
            node_code: Python code defining the node class

        Returns:
            Validation result for node parameters
        """
        try:
            tree = ast.parse(node_code)

            # Find class definitions
            classes = [
                node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]

            errors = []

            for class_node in classes:
                class_name = class_node.name

                # Store current class node for PAR002 validation
                self._current_class_node = class_node

                # Check if it has get_parameters method
                has_get_parameters = any(
                    isinstance(node, ast.FunctionDef) and node.name == "get_parameters"
                    for node in class_node.body
                )

                if not has_get_parameters:
                    errors.append(
                        {
                            "code": "PAR001",
                            "message": f"Node class '{class_name}' missing get_parameters() method",
                            "node_class": class_name,
                            "severity": "error",
                        }
                    )
                else:
                    # Validate the get_parameters method implementation
                    get_params_method = next(
                        (
                            node
                            for node in class_node.body
                            if isinstance(node, ast.FunctionDef)
                            and node.name == "get_parameters"
                        ),
                        None,
                    )

                    if get_params_method:
                        # Check for PAR002 and PAR003 errors in the method
                        param_errors = self._validate_get_parameters_method(
                            get_params_method, class_name
                        )
                        errors.extend(param_errors)

            return {
                "has_errors": len(errors) > 0,
                "errors": errors,
                "warnings": [],
                "suggestions": [],
            }

        except Exception as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "PAR000",
                        "message": f"Error validating node: {str(e)}",
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "suggestions": [],
            }

    def _validate_get_parameters_method(
        self, method_node: ast.FunctionDef, class_name: str
    ) -> List[Dict[str, Any]]:
        """Validate get_parameters method implementation for PAR002 and PAR003 errors."""
        errors = []

        # Extract declared parameter names from NodeParameter objects
        declared_params = set()

        for node in ast.walk(method_node):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "NodeParameter"
            ):
                # Check for PAR003: missing type field
                has_type_field = False
                param_name = None

                # Check keyword arguments for type field and name
                for keyword in node.keywords:
                    if keyword.arg == "type":
                        has_type_field = True
                    elif keyword.arg == "name" and isinstance(
                        keyword.value, ast.Constant
                    ):
                        param_name = keyword.value.value
                        declared_params.add(param_name)

                # Check positional arguments (less common but possible)
                if not has_type_field and len(node.args) >= 2:
                    # Second argument is typically the type
                    has_type_field = True

                # If we have a name from positional args
                if (
                    not param_name
                    and len(node.args) >= 1
                    and isinstance(node.args[0], ast.Constant)
                ):
                    param_name = node.args[0].value
                    declared_params.add(param_name)

                if not has_type_field:
                    errors.append(
                        {
                            "code": "PAR003",
                            "message": f"NodeParameter in {class_name} missing required 'type' field",
                            "node_class": class_name,
                            "parameter": param_name or "unknown",
                            "severity": "error",
                        }
                    )

        # Now check for PAR002: Find the class and check for undeclared parameter usage
        # This requires walking the entire class to find parameter usage
        try:
            # Parse the full class to check for parameter usage
            parent_tree = method_node
            while parent_tree and not isinstance(parent_tree, ast.Module):
                if hasattr(parent_tree, "parent"):
                    parent_tree = parent_tree.parent
                else:
                    break

            # Look for kwargs.get calls or direct parameter usage in run method
            class_methods = []
            if hasattr(self, "_current_class_node"):
                class_methods = [
                    node
                    for node in self._current_class_node.body
                    if isinstance(node, ast.FunctionDef) and node.name == "run"
                ]

            for run_method in class_methods:
                for node in ast.walk(run_method):
                    # Look for kwargs.get("param_name") calls
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get"
                        and len(node.args) >= 1
                        and isinstance(node.args[0], ast.Constant)
                    ):

                        param_name = node.args[0].value
                        if param_name not in declared_params and param_name != "kwargs":
                            errors.append(
                                {
                                    "code": "PAR002",
                                    "message": f"Parameter '{param_name}' used in {class_name} but not declared in get_parameters()",
                                    "node_class": class_name,
                                    "parameter": param_name,
                                    "severity": "error",
                                }
                            )
        except Exception:
            # If we can't analyze parameter usage, skip PAR002 check
            pass

        return errors

    def validate_connections_only(
        self, connections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate connection syntax only.

        Args:
            connections: List of connection objects

        Returns:
            Validation result for connections
        """
        errors = []

        for i, conn in enumerate(connections):
            required_fields = ["source", "output", "target", "input"]
            missing_fields = [field for field in required_fields if field not in conn]

            if missing_fields:
                errors.append(
                    {
                        "code": "CON001",
                        "message": f"Connection {i} missing required fields: {missing_fields}",
                        "connection_index": i,
                        "missing_fields": missing_fields,
                        "severity": "error",
                    }
                )

            # Check for 2-parameter old syntax (source, target only)
            if len(conn) == 2 and "output" not in conn and "input" not in conn:
                errors.append(
                    {
                        "code": "CON002",
                        "message": f"Connection {i} uses old 2-parameter syntax. Use 4-parameter: add_connection(source, output, target, input)",
                        "connection_index": i,
                        "severity": "error",
                    }
                )

        return {
            "has_errors": len(errors) > 0,
            "errors": errors,
            "warnings": [],
            "suggestions": [],
        }

    def _extract_workflow_info(self, tree: ast.AST) -> Optional[Dict[str, Any]]:
        """Extract workflow information from AST."""
        workflow_info = {
            "nodes": [],
            "connections": [],
            "cycles": [],
            "builder_var": None,
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for WorkflowBuilder() calls
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "WorkflowBuilder"
                ):
                    # Found WorkflowBuilder instantiation
                    pass

                # Look for add_node calls
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_node"
                ):
                    node_info = self._extract_add_node_info(node)
                    if node_info:
                        workflow_info["nodes"].append(node_info)

                # Look for add_connection calls
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_connection"
                ):
                    conn_info = self._extract_connection_info(node)
                    if conn_info:
                        workflow_info["connections"].append(conn_info)

                # Look for create_cycle calls
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "create_cycle"
                ):
                    cycle_info = self._extract_cycle_info(node)
                    if cycle_info:
                        workflow_info["cycles"].append(cycle_info)

        return (
            workflow_info
            if workflow_info["nodes"]
            or workflow_info["connections"]
            or workflow_info["cycles"]
            else None
        )

    def _extract_add_node_info(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """Extract information from add_node call."""
        if len(node.args) < 2:
            return None

        try:
            node_type = (
                ast.literal_eval(node.args[0])
                if isinstance(node.args[0], ast.Constant)
                else None
            )
            node_id = (
                ast.literal_eval(node.args[1])
                if isinstance(node.args[1], ast.Constant)
                else None
            )

            # Extract parameters if present
            parameters = {}
            if len(node.args) >= 3 and isinstance(node.args[2], ast.Dict):
                for key, value in zip(node.args[2].keys, node.args[2].values):
                    if isinstance(key, ast.Constant):
                        try:
                            parameters[key.value] = ast.literal_eval(value)
                        except:
                            parameters[key.value] = "complex_expression"

            return {
                "node_type": node_type,
                "node_id": node_id,
                "parameters": parameters,
                "line": node.lineno,
            }
        except:
            return None

    def _extract_connection_info(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """Extract information from add_connection call."""
        try:
            args = []
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    args.append(arg.value)
                else:
                    args.append("expression")

            if len(args) == 2:
                # Old 2-parameter syntax
                return {
                    "source": args[0],
                    "target": args[1],
                    "syntax_error": "old_2_param",
                    "line": node.lineno,
                }
            elif len(args) == 4:
                # Correct 4-parameter syntax
                return {
                    "source": args[0],
                    "output": args[1],
                    "target": args[2],
                    "input": args[3],
                    "line": node.lineno,
                }
            else:
                return {
                    "error": "invalid_connection_args",
                    "arg_count": len(args),
                    "line": node.lineno,
                }
        except:
            return None

    def _validate_node_parameters(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate node parameters using existing SDK validator."""
        errors = []

        # Define known required parameters for common node types (fallback)
        STATIC_REQUIRED_PARAMS = {
            "LLMAgentNode": ["model", "prompt"],
            "HTTPRequestNode": ["url"],
            "SQLDatabaseNode": ["connection_string"],
            "AsyncSQLDatabaseNode": ["connection_string"],
            "FileReaderNode": ["file_path"],
            "CSVReaderNode": ["file_path"],
            "JSONReaderNode": ["file_path"],
            "S3UploadNode": ["bucket", "key"],
            "S3DownloadNode": ["bucket", "key"],
            "RESTClientNode": ["base_url"],
            "GraphQLClientNode": ["endpoint"],
            "EmailSenderNode": ["to", "subject"],
            "IterativeLLMAgentNode": ["model", "max_iterations"],
            "MonitoredLLMAgentNode": ["model"],
            "A2AAgentNode": ["agent_id", "capability"],
            "WebScraperNode": ["url"],
            "PythonCodeNode": ["code"],
            "AsyncPythonCodeNode": ["code"],
            "CommandNode": ["command"],
            "DataTransformerNode": ["operation"],
            "DataProcessorNode": ["operation"],
            "ProcessorNode": ["operation"],
            "TransformNode": ["transformation"],
            "DatabaseWriterNode": ["connection_string", "table"],
        }

        for node_info in workflow_info["nodes"]:
            node_type = node_info.get("node_type")
            node_id = node_info.get("node_id")
            parameters = node_info.get("parameters", {})

            if not node_type or not node_id:
                continue

            # Check if node has no parameters at all
            if not parameters:
                errors.append(
                    {
                        "code": "PAR004",
                        "message": f"Node '{node_id}' missing required parameters - common nodes like {node_type} require parameters",
                        "node_type": node_type,
                        "node_id": node_id,
                        "line": node_info.get("line"),
                        "severity": "error",
                    }
                )
                continue

            # Get required parameters - try dynamic discovery first
            required_params = self._get_required_parameters(
                node_type, STATIC_REQUIRED_PARAMS
            )

            if required_params:
                missing_params = [
                    param for param in required_params if param not in parameters
                ]

                for missing_param in missing_params:
                    errors.append(
                        {
                            "code": "PAR004",
                            "message": f"Node '{node_id}' missing required parameter '{missing_param}'",
                            "node_type": node_type,
                            "node_id": node_id,
                            "node_name": node_id,
                            "parameter": missing_param,
                            "parameter_name": missing_param,
                            "line": node_info.get("line"),
                            "severity": "error",
                        }
                    )

        return errors

    def _get_required_parameters(
        self, node_type: str, static_params: Dict[str, List[str]]
    ) -> List[str]:
        """
        Get required parameters for a node type.

        First attempts dynamic discovery from NodeRegistry, falls back to static definitions.

        Args:
            node_type: The node type to get parameters for
            static_params: Static parameter definitions to use as fallback

        Returns:
            List of required parameter names
        """
        # Check cache first
        if node_type in self._param_cache:
            return self._param_cache[node_type]

        # Try dynamic discovery
        try:
            from kailash.nodes.base import NodeRegistry

            registry = NodeRegistry()
            node_class = registry.get_node_class(node_type)

            if hasattr(node_class, "get_parameters"):
                # Get parameters from the node class
                params = node_class.get_parameters()
                required_params = [p.name for p in params if p.required]

                # Cache the result
                self._param_cache[node_type] = required_params
                return required_params

        except Exception:
            # Failed to get from registry, use static fallback
            pass

        # Use static definitions as fallback
        static_required = static_params.get(node_type, [])
        self._param_cache[node_type] = static_required
        return static_required

    def _validate_connections(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate connection syntax and field names."""
        errors = []

        for conn in workflow_info["connections"]:
            if conn.get("syntax_error") == "old_2_param":
                errors.append(
                    {
                        "code": "CON002",
                        "message": f"Connection uses old 2-parameter syntax. Use: add_connection('{conn['source']}', 'output', '{conn['target']}', 'input')",
                        "source": conn["source"],
                        "target": conn["target"],
                        "line": conn.get("line"),
                        "severity": "error",
                    }
                )
            elif conn.get("error") == "invalid_connection_args":
                errors.append(
                    {
                        "code": "CON001",
                        "message": f"Invalid connection: expected 4 parameters (source, output, target, input), got {conn['arg_count']}",
                        "arg_count": conn["arg_count"],
                        "line": conn.get("line"),
                        "severity": "error",
                    }
                )
            else:
                # Check for suspicious field names (basic heuristic validation)
                output_field = conn.get("output", "")
                input_field = conn.get("input", "")

                # Flag obvious invalid field names
                if output_field and (
                    "nonexistent" in output_field.lower()
                    or "invalid" in output_field.lower()
                    or "fake" in output_field.lower()
                ):
                    errors.append(
                        {
                            "code": "CON006",
                            "message": f"Connection uses suspicious output field '{output_field}' - check if this field exists on source node",
                            "source": conn.get("source"),
                            "output": output_field,
                            "line": conn.get("line"),
                            "severity": "error",
                        }
                    )

                if input_field and (
                    "nonexistent" in input_field.lower()
                    or "invalid" in input_field.lower()
                    or "fake" in input_field.lower()
                ):
                    errors.append(
                        {
                            "code": "CON007",
                            "message": f"Connection uses suspicious input field '{input_field}' - check if this field exists on target node",
                            "target": conn.get("target"),
                            "input": input_field,
                            "line": conn.get("line"),
                            "severity": "error",
                        }
                    )

        return errors

    def _validate_node_existence(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate that connected nodes exist."""
        errors = []

        # Get all node IDs
        node_ids = {
            node["node_id"] for node in workflow_info["nodes"] if node.get("node_id")
        }

        # Check connections reference existing nodes
        for conn in workflow_info["connections"]:
            source = conn.get("source")
            target = conn.get("target")

            if source and source not in node_ids:
                errors.append(
                    {
                        "code": "CON003",
                        "message": f"Connection references non-existent source node '{source}'",
                        "source": source,
                        "line": conn.get("line"),
                        "severity": "error",
                    }
                )

            if target and target not in node_ids:
                errors.append(
                    {
                        "code": "CON004",
                        "message": f"Connection references non-existent target node '{target}'",
                        "target": target,
                        "line": conn.get("line"),
                        "severity": "error",
                    }
                )

        return errors

    def _validate_no_circular_dependencies(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for circular dependencies in connections."""
        errors = []

        # Build adjacency list
        graph = {}
        for conn in workflow_info["connections"]:
            source = conn.get("source")
            target = conn.get("target")

            if source and target:
                if source not in graph:
                    graph[source] = []
                graph[source].append(target)

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    errors.append(
                        {
                            "code": "CON005",
                            "message": "Circular dependency detected in workflow connections",
                            "severity": "error",
                        }
                    )
                    break

        return errors

    def _extract_cycle_info(self, node: ast.Call) -> Optional[Dict[str, Any]]:
        """Extract information from create_cycle call."""
        try:
            cycle_name = None
            if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant):
                cycle_name = node.args[0].value

            return {"cycle_name": cycle_name, "line": node.lineno, "node": node}
        except:
            return None

    def _validate_cycle_patterns(
        self, workflow_info: Dict[str, Any], tree: ast.AST
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate CycleBuilder patterns and detect deprecated syntax."""
        errors = []
        warnings = []

        # 1. Check for deprecated cycle=True in connections
        deprecated_errors = self._check_deprecated_cycle_syntax(tree)
        errors.extend(deprecated_errors)

        # 2. Validate cycle builder configurations
        cycle_errors, cycle_warnings = self._validate_cycle_builders(
            workflow_info, tree
        )
        errors.extend(cycle_errors)
        warnings.extend(cycle_warnings)

        return errors, warnings

    def _check_deprecated_cycle_syntax(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Check for deprecated cycle=True parameter in add_connection calls."""
        errors = []

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_connection"
            ):
                # Check for cycle keyword argument
                for keyword in node.keywords:
                    if keyword.arg == "cycle":
                        errors.append(
                            {
                                "code": "CYC001",
                                "message": "Deprecated 'cycle=True' parameter detected. Use workflow.create_cycle() API instead",
                                "line": node.lineno,
                                "severity": "error",
                            }
                        )

        return errors

    def _validate_cycle_builders(
        self, workflow_info: Dict[str, Any], tree: ast.AST
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate cycle builder configurations."""
        errors = []
        warnings = []

        # Extract cycle builder usage patterns from AST
        cycle_builders = self._extract_cycle_builder_usage(tree)

        for cycle_name, cycle_data in cycle_builders.items():
            # Validate cycle configuration
            config_errors = self._validate_cycle_configuration(cycle_name, cycle_data)
            errors.extend(config_errors)

            # Validate cycle connections
            connection_errors = self._validate_cycle_connections(
                cycle_name, cycle_data, workflow_info
            )
            errors.extend(connection_errors)

            # Check for warnings (excessive iterations, etc.)
            cycle_warnings = self._check_cycle_warnings(cycle_name, cycle_data)
            warnings.extend(cycle_warnings)

        return errors, warnings

    def _extract_cycle_builder_usage(self, tree: ast.AST) -> Dict[str, Dict[str, Any]]:
        """Extract cycle builder usage patterns from AST."""
        cycle_builders = {}
        current_cycle = None

        # Track variable assignments to identify cycle builders
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Look for cycle_builder = workflow.create_cycle("name")
                if (
                    len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == "create_cycle"
                ):

                    cycle_var = node.targets[0].id
                    cycle_name = None
                    if len(node.value.args) >= 1 and isinstance(
                        node.value.args[0], ast.Constant
                    ):
                        cycle_name = node.value.args[0].value

                    cycle_builders[cycle_name or cycle_var] = {
                        "variable": cycle_var,
                        "name": cycle_name,
                        "connections": [],
                        "max_iterations": None,
                        "converge_when": None,
                        "timeout": None,
                        "has_build": False,
                        "line": node.lineno,
                    }
                    current_cycle = cycle_name or cycle_var

            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                # Look for cycle builder method calls
                if isinstance(node.value.func, ast.Attribute) and isinstance(
                    node.value.func.value, ast.Name
                ):

                    var_name = node.value.func.value.id
                    method_name = node.value.func.attr

                    # Find which cycle this belongs to
                    for cycle_key, cycle_data in cycle_builders.items():
                        if cycle_data["variable"] == var_name:
                            if method_name == "connect":
                                cycle_data["connections"].append(
                                    {
                                        "line": node.lineno,
                                        "args": node.value.args,
                                        "keywords": node.value.keywords,
                                    }
                                )
                            elif method_name == "max_iterations":
                                if len(node.value.args) >= 1:
                                    try:
                                        cycle_data["max_iterations"] = ast.literal_eval(
                                            node.value.args[0]
                                        )
                                    except:
                                        cycle_data["max_iterations"] = "invalid"
                            elif method_name == "converge_when":
                                if len(node.value.args) >= 1:
                                    try:
                                        cycle_data["converge_when"] = ast.literal_eval(
                                            node.value.args[0]
                                        )
                                    except:
                                        cycle_data["converge_when"] = "invalid"
                            elif method_name == "timeout":
                                if len(node.value.args) >= 1:
                                    try:
                                        cycle_data["timeout"] = ast.literal_eval(
                                            node.value.args[0]
                                        )
                                    except:
                                        cycle_data["timeout"] = "invalid"
                            elif method_name == "build":
                                cycle_data["has_build"] = True
                            break

        return cycle_builders

    def _validate_cycle_configuration(
        self, cycle_name: str, cycle_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate cycle configuration requirements."""
        errors = []

        # Check for missing required configuration
        if cycle_data["max_iterations"] is None and cycle_data["converge_when"] is None:
            errors.append(
                {
                    "code": "CYC002",
                    "message": f"Cycle '{cycle_name}' missing required configuration: must have either max_iterations() or converge_when()",
                    "cycle_name": cycle_name,
                    "line": cycle_data["line"],
                    "severity": "error",
                }
            )

        # Validate convergence condition syntax
        if cycle_data["converge_when"] == "invalid":
            errors.append(
                {
                    "code": "CYC003",
                    "message": f"Cycle '{cycle_name}' has invalid convergence condition syntax",
                    "cycle_name": cycle_name,
                    "line": cycle_data["line"],
                    "severity": "error",
                }
            )
        elif isinstance(cycle_data["converge_when"], str):
            # Check for obviously invalid convergence conditions
            condition = cycle_data["converge_when"]
            if (
                "!" in condition
                and not any(op in condition for op in ["!=", ">=", "<="])
            ) or condition.strip().startswith("invalid"):
                errors.append(
                    {
                        "code": "CYC003",
                        "message": f"Cycle '{cycle_name}' has invalid convergence condition: '{condition}'",
                        "cycle_name": cycle_name,
                        "line": cycle_data["line"],
                        "severity": "error",
                    }
                )

        # Validate timeout value
        if cycle_data["timeout"] is not None:
            if cycle_data["timeout"] == "invalid":
                errors.append(
                    {
                        "code": "CYC007",
                        "message": f"Cycle '{cycle_name}' has invalid timeout value",
                        "cycle_name": cycle_name,
                        "line": cycle_data["line"],
                        "severity": "error",
                    }
                )
            elif (
                isinstance(cycle_data["timeout"], (int, float))
                and cycle_data["timeout"] <= 0
            ):
                errors.append(
                    {
                        "code": "CYC007",
                        "message": f"Cycle '{cycle_name}' has invalid timeout value: must be positive",
                        "cycle_name": cycle_name,
                        "line": cycle_data["line"],
                        "severity": "error",
                    }
                )

        return errors

    def _validate_cycle_connections(
        self, cycle_name: str, cycle_data: Dict[str, Any], workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate cycle connections."""
        errors = []

        # Check for empty cycles
        if not cycle_data["connections"]:
            errors.append(
                {
                    "code": "CYC004",
                    "message": f"Cycle '{cycle_name}' has no connections defined",
                    "cycle_name": cycle_name,
                    "line": cycle_data["line"],
                    "severity": "error",
                }
            )
            return errors

        # Get available node IDs
        node_ids = {
            node["node_id"] for node in workflow_info["nodes"] if node.get("node_id")
        }

        # Validate each connection
        for conn in cycle_data["connections"]:
            # Check mapping parameter
            mapping_valid = False
            for keyword in conn["keywords"]:
                if keyword.arg == "mapping":
                    if isinstance(keyword.value, ast.Dict):
                        mapping_valid = True
                    else:
                        errors.append(
                            {
                                "code": "CYC005",
                                "message": f"Cycle '{cycle_name}' connection has invalid mapping format: must be a dictionary",
                                "cycle_name": cycle_name,
                                "line": conn["line"],
                                "severity": "error",
                            }
                        )

            # Check node references
            if len(conn["args"]) >= 2:
                source_node = None
                target_node = None

                try:
                    if isinstance(conn["args"][0], ast.Constant):
                        source_node = conn["args"][0].value
                    if isinstance(conn["args"][1], ast.Constant):
                        target_node = conn["args"][1].value
                except:
                    pass

                # Validate node existence
                if source_node and source_node not in node_ids:
                    errors.append(
                        {
                            "code": "CYC008",
                            "message": f"Cycle '{cycle_name}' references non-existent node '{source_node}'",
                            "cycle_name": cycle_name,
                            "node_name": source_node,
                            "line": conn["line"],
                            "severity": "error",
                        }
                    )

                if target_node and target_node not in node_ids:
                    errors.append(
                        {
                            "code": "CYC008",
                            "message": f"Cycle '{cycle_name}' references non-existent node '{target_node}'",
                            "cycle_name": cycle_name,
                            "node_name": target_node,
                            "line": conn["line"],
                            "severity": "error",
                        }
                    )

        return errors

    def _check_cycle_warnings(
        self, cycle_name: str, cycle_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for cycle configuration warnings."""
        warnings = []

        # Check for excessive iterations
        if (
            isinstance(cycle_data["max_iterations"], int)
            and cycle_data["max_iterations"] > 1000
        ):
            warnings.append(
                {
                    "code": "CYC006",
                    "message": f"Cycle '{cycle_name}' has high max_iterations ({cycle_data['max_iterations']}). Consider using converge_when() for better performance",
                    "cycle_name": cycle_name,
                    "line": cycle_data["line"],
                    "severity": "warning",
                }
            )

        return warnings

    def validate_imports(self, code: str) -> Dict[str, Any]:
        """
        Validate import statements in workflow code.

        Args:
            code: Python code to validate imports for

        Returns:
            Validation result with import errors and suggestions
        """
        try:
            tree = ast.parse(code)

            # Extract import information
            imports = self._extract_imports(tree)
            used_names = self._extract_used_names(tree)

            errors = []
            warnings = []
            suggested_imports = []

            # Check for missing imports
            missing_errors, missing_suggestions = self._validate_missing_imports(
                used_names, imports
            )
            errors.extend(missing_errors)
            suggested_imports.extend(missing_suggestions)

            # Check for unused imports
            unused_errors = self._validate_unused_imports(imports, used_names)
            errors.extend(unused_errors)

            # Check for incorrect import paths
            path_errors = self._validate_import_paths(imports)
            errors.extend(path_errors)

            # Check for relative imports
            relative_errors = self._validate_relative_imports(imports)
            errors.extend(relative_errors)

            # Check import ordering
            ordering_warnings = self._validate_import_ordering(imports)
            warnings.extend(ordering_warnings)

            # Check for heavy imports that are unused
            performance_warnings = self._validate_import_performance(
                imports, used_names
            )
            warnings.extend(performance_warnings)

            result = {
                "has_errors": len(errors) > 0,
                "errors": errors,
                "warnings": warnings,
                "suggested_imports": suggested_imports,
            }

            # Add optimization suggestions if any
            optimization_suggestions = self._generate_optimization_suggestions(
                imports, used_names
            )
            if optimization_suggestions:
                result["optimization_suggestions"] = optimization_suggestions

            return result

        except SyntaxError as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "IMP999",
                        "message": f"Syntax error in code: {str(e)}",
                        "line": getattr(e, "lineno", 0),
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "suggested_imports": [],
            }
        except Exception as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "IMP999",
                        "message": f"Import validation error: {str(e)}",
                        "severity": "error",
                    }
                ],
                "warnings": [],
                "suggested_imports": [],
            }

    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract import statements from AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "type": "import",
                            "module": alias.name,
                            "name": alias.asname or alias.name,
                            "line": node.lineno,
                            "is_relative": False,
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(
                        {
                            "type": "from_import",
                            "module": module,
                            "name": alias.asname or alias.name,
                            "original_name": alias.name,
                            "line": node.lineno,
                            "is_relative": node.level > 0,
                            "level": node.level,
                        }
                    )

        return imports

    def _extract_used_names(self, tree: ast.AST) -> Set[str]:
        """Extract all names used in the code."""
        used_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Handle chained attributes like workflow.build()
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        return used_names

    def _validate_missing_imports(
        self, used_names: Set[str], imports: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Check for missing import statements."""
        errors = []
        suggestions = []

        # Map of imported names
        imported_names = {imp["name"] for imp in imports}

        # Known Kailash SDK classes and their import paths
        kailash_imports = {
            "WorkflowBuilder": "from kailash.workflow.builder import WorkflowBuilder",
            "LocalRuntime": "from kailash.runtime.local import LocalRuntime",
            "ParallelRuntime": "from kailash.runtime.parallel import ParallelRuntime",
            "DockerRuntime": "from kailash.runtime.docker import DockerRuntime",
            "LLMAgentNode": "# LLMAgentNode is available by default",
            "HTTPRequestNode": "# HTTPRequestNode is available by default",
            "CSVReaderNode": "# CSVReaderNode is available by default",
            "Node": "from kailash.nodes.base import Node",
            "NodeParameter": "from kailash.nodes.base import NodeParameter",
            "NodeRegistry": "from kailash.nodes.base import NodeRegistry",
        }

        # Check for missing imports
        for name in used_names:
            if name not in imported_names and name in kailash_imports:
                errors.append(
                    {
                        "code": "IMP001",
                        "message": f"Missing import for '{name}'",
                        "missing_name": name,
                        "severity": "error",
                    }
                )

                suggestions.append(
                    {
                        "missing_name": name,
                        "import_statement": kailash_imports[name],
                        "reason": "Required for Kailash SDK usage",
                    }
                )

        return errors, suggestions

    def _validate_unused_imports(
        self, imports: List[Dict[str, Any]], used_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """Check for unused import statements."""
        errors = []

        for imp in imports:
            if imp["name"] not in used_names:
                errors.append(
                    {
                        "code": "IMP002",
                        "message": f"Unused import '{imp['name']}'",
                        "import_name": imp["name"],
                        "line": imp["line"],
                        "severity": "error",
                    }
                )

        return errors

    def _validate_import_paths(
        self, imports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for incorrect import paths."""
        errors = []

        # Correct import paths for common Kailash components
        correct_paths = {
            "WorkflowBuilder": "kailash.workflow.builder",
            "LocalRuntime": "kailash.runtime.local",
            "ParallelRuntime": "kailash.runtime.parallel",
            "DockerRuntime": "kailash.runtime.docker",
            "Node": "kailash.nodes.base",
            "NodeParameter": "kailash.nodes.base",
            "NodeRegistry": "kailash.nodes.base",
        }

        for imp in imports:
            if imp["type"] == "from_import":
                name = imp.get("original_name", imp["name"])
                if name in correct_paths:
                    expected_module = correct_paths[name]
                    if imp["module"] != expected_module:
                        errors.append(
                            {
                                "code": "IMP003",
                                "message": f"Incorrect import path for '{name}'. Expected 'from {expected_module} import {name}', got 'from {imp['module']} import {name}'",
                                "import_name": name,
                                "current_path": imp["module"],
                                "correct_path": expected_module,
                                "line": imp["line"],
                                "severity": "error",
                            }
                        )

        return errors

    def _validate_relative_imports(
        self, imports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check for relative imports (discouraged in Kailash)."""
        errors = []

        for imp in imports:
            if imp.get("is_relative", False):
                errors.append(
                    {
                        "code": "IMP004",
                        "message": f"Relative import detected for '{imp['name']}'. Use absolute imports for better compatibility",
                        "import_name": imp["name"],
                        "line": imp["line"],
                        "severity": "error",
                    }
                )

        return errors

    def _validate_import_ordering(
        self, imports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check import statement ordering (PEP 8)."""
        warnings = []

        if len(imports) < 2:
            return warnings

        # Group imports by type
        import_groups = {"standard": [], "third_party": [], "kailash": [], "local": []}

        for imp in imports:
            module = imp["module"]
            if imp["type"] == "import":
                module = imp["name"]

            if self._is_standard_library(module):
                import_groups["standard"].append(imp)
            elif module.startswith("kailash"):
                import_groups["kailash"].append(imp)
            elif self._is_relative_import(imp):
                import_groups["local"].append(imp)
            else:
                import_groups["third_party"].append(imp)

        # Check if ordering follows PEP 8 (standard, third-party, local)
        previous_line = 0
        expected_order = ["standard", "third_party", "kailash", "local"]
        current_group_index = 0

        for imp in imports:
            # Determine which group this import belongs to
            imp_group = self._get_import_group(imp)
            expected_group = (
                expected_order[current_group_index]
                if current_group_index < len(expected_order)
                else "local"
            )

            # Check if we're in the wrong order
            if imp_group != expected_group and imp["line"] > previous_line:
                # Look ahead to see if this is just a misplaced import
                imp_group_index = (
                    expected_order.index(imp_group)
                    if imp_group in expected_order
                    else len(expected_order)
                )
                if imp_group_index < current_group_index:
                    warnings.append(
                        {
                            "code": "IMP006",
                            "message": f"Import order violation: {imp_group} imports should come before {expected_group} imports",
                            "import_name": imp["name"],
                            "line": imp["line"],
                            "severity": "warning",
                        }
                    )

            # Update current group if we've moved to it
            if imp_group in expected_order:
                group_index = expected_order.index(imp_group)
                if group_index >= current_group_index:
                    current_group_index = group_index

            previous_line = imp["line"]

        return warnings

    def _validate_import_performance(
        self, imports: List[Dict[str, Any]], used_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """Check for performance-impacting unused imports."""
        warnings = []

        # Heavy imports that can impact startup time
        heavy_imports = {
            "tensorflow",
            "tf",
            "torch",
            "pandas",
            "pd",
            "numpy",
            "np",
            "matplotlib",
            "plt",
            "sklearn",
            "cv2",
            "PIL",
            "transformers",
        }

        for imp in imports:
            # Check if this is a heavy import that's not used
            module_parts = imp["module"].split(".") if imp["module"] else []
            import_name = imp["name"]

            is_heavy = import_name in heavy_imports or any(
                part in heavy_imports for part in module_parts
            )

            if is_heavy and import_name not in used_names:
                warnings.append(
                    {
                        "code": "IMP008",
                        "message": f"Heavy import '{import_name}' is unused and may impact performance",
                        "import_name": import_name,
                        "line": imp["line"],
                        "severity": "warning",
                    }
                )

        return warnings

    def _generate_optimization_suggestions(
        self, imports: List[Dict[str, Any]], used_names: Set[str]
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for import optimization."""
        suggestions = []

        # Find unused imports for removal suggestion
        unused_imports = [imp for imp in imports if imp["name"] not in used_names]
        if unused_imports:
            suggestions.append(
                {
                    "type": "remove_unused",
                    "description": f"Remove {len(unused_imports)} unused imports",
                    "imports": [imp["name"] for imp in unused_imports],
                }
            )

        # Find potential consolidation opportunities
        from_imports = [imp for imp in imports if imp["type"] == "from_import"]
        modules = {}
        for imp in from_imports:
            if imp["module"] not in modules:
                modules[imp["module"]] = []
            modules[imp["module"]].append(
                imp["original_name"] if "original_name" in imp else imp["name"]
            )

        # Suggest consolidation for modules with multiple imports
        for module, names in modules.items():
            if len(names) > 1:
                suggestions.append(
                    {
                        "type": "consolidate",
                        "description": f"Consolidate imports from {module}",
                        "current": [f"from {module} import {name}" for name in names],
                        "suggested": f"from {module} import {', '.join(names)}",
                    }
                )

        return suggestions

    def _is_standard_library(self, module: str) -> bool:
        """Check if module is part of Python standard library."""
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "ast",
            "typing",
            "dataclasses",
            "pathlib",
            "collections",
            "itertools",
            "functools",
            "operator",
            "datetime",
            "time",
            "math",
            "random",
            "string",
            "io",
            "urllib",
            "http",
            "email",
            "html",
            "xml",
            "csv",
            "sqlite3",
            "pickle",
            "unittest",
            "logging",
            "argparse",
            "configparser",
            "threading",
            "multiprocessing",
            "asyncio",
            "concurrent",
            "queue",
            "socket",
            "ssl",
            "hashlib",
            "hmac",
            "secrets",
            "base64",
            "binascii",
            "struct",
            "array",
            "copy",
            "pprint",
            "reprlib",
            "enum",
            "types",
            "weakref",
            "gc",
            "inspect",
            "dis",
            "importlib",
            "pkgutil",
            "modulefinder",
            "runpy",
            "site",
            "sysconfig",
            "platform",
            "errno",
            "ctypes",
            "abc",
            "contextlib",
            "warnings",
            "trace",
        }

        base_module = module.split(".")[0]
        return base_module in stdlib_modules

    def _is_relative_import(self, imp: Dict[str, Any]) -> bool:
        """Check if import is relative."""
        return imp.get("is_relative", False)

    def _get_import_group(self, imp: Dict[str, Any]) -> str:
        """Get the import group (standard, third_party, kailash, local)."""
        module = imp["module"] if imp["type"] == "from_import" else imp["name"]

        if self._is_relative_import(imp):
            return "local"
        elif module.startswith("kailash"):
            return "kailash"
        elif self._is_standard_library(module):
            return "standard"
        else:
            return "third_party"

    def analyze_complexity(self, code: str) -> Dict[str, Any]:
        """
        Analyze workflow complexity and provide optimization insights.

        Args:
            code: Python code to analyze for complexity

        Returns:
            Complexity analysis result with metrics and suggestions
        """
        try:
            tree = ast.parse(code)
            workflow_info = self._extract_workflow_info(tree)

            if not workflow_info:
                return {
                    "has_analysis": True,
                    "metrics": {
                        "node_count": 0,
                        "connection_count": 0,
                        "complexity_score": 0,
                        "pattern_type": "empty",
                    },
                    "optimization_suggestions": [],
                    "bottlenecks": [],
                    "error_risks": [],
                }

            # Calculate basic metrics
            metrics = self._calculate_complexity_metrics(workflow_info, tree)

            # Analyze patterns and bottlenecks
            bottlenecks = self._detect_performance_bottlenecks(workflow_info)
            error_risks = self._detect_error_risks(workflow_info)
            optimization_suggestions = self._generate_complexity_optimizations(
                workflow_info, metrics
            )

            # Resource analysis
            resource_analysis = self._analyze_resource_usage(workflow_info)

            # Scalability analysis
            scalability = self._analyze_scalability(workflow_info)

            return {
                "has_analysis": True,
                "metrics": metrics,
                "optimization_suggestions": optimization_suggestions,
                "bottlenecks": bottlenecks,
                "error_risks": error_risks,
                "resource_analysis": resource_analysis,
                "scalability": scalability,
            }

        except Exception as e:
            return {
                "has_analysis": False,
                "error": f"Complexity analysis error: {str(e)}",
                "metrics": {},
                "optimization_suggestions": [],
                "bottlenecks": [],
                "error_risks": [],
            }

    def _calculate_complexity_metrics(
        self, workflow_info: Dict[str, Any], tree: ast.AST
    ) -> Dict[str, Any]:
        """Calculate complexity metrics for the workflow."""
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])
        cycles = workflow_info.get("cycles", [])

        # Basic counts
        node_count = len(nodes)
        connection_count = len(connections)
        cycle_count = len(cycles)

        # Node type analysis
        node_types = {}
        for node in nodes:
            node_type = node.get("node_type", "Unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        # Calculate workflow depth (longest path)
        workflow_depth = self._calculate_workflow_depth(workflow_info)

        # Determine pattern type
        pattern_type = self._determine_pattern_type(workflow_info)

        # Calculate parallelism score
        parallelism_score = self._calculate_parallelism_score(workflow_info)

        # Base complexity score
        complexity_score = (
            node_count * 2
            + connection_count * 1.5
            + cycle_count * 10
            + workflow_depth * 3
            + len(node_types) * 2
        )

        # Configuration complexity
        config_complexity = self._calculate_configuration_complexity(nodes)

        # Connection complexity
        connection_complexity = self._calculate_connection_complexity(connections)

        # Maintenance complexity
        maintenance_complexity = (
            complexity_score * 0.5 + config_complexity * 20 + connection_complexity * 15
        )

        return {
            "node_count": node_count,
            "connection_count": connection_count,
            "cycle_count": cycle_count,
            "workflow_depth": workflow_depth,
            "complexity_score": round(complexity_score, 2),
            "pattern_type": pattern_type,
            "parallelism_score": round(parallelism_score, 2),
            "node_types": node_types,
            "has_cycles": cycle_count > 0,
            "max_cycle_depth": self._calculate_max_cycle_depth(cycles),
            "configuration_complexity": round(config_complexity, 2),
            "connection_complexity": round(connection_complexity, 2),
            "maintenance_complexity_score": round(maintenance_complexity, 2),
        }

    def _calculate_workflow_depth(self, workflow_info: Dict[str, Any]) -> int:
        """Calculate the maximum depth (longest path) in the workflow."""
        nodes = {node["node_id"]: node for node in workflow_info.get("nodes", [])}
        connections = workflow_info.get("connections", [])

        if not nodes or not connections:
            return 1 if nodes else 0

        # Build adjacency list
        graph = {node_id: [] for node_id in nodes.keys()}
        for conn in connections:
            source = conn.get("source")
            target = conn.get("target")
            if source in graph and target in graph:
                graph[source].append(target)

        # Find nodes with no incoming connections (start nodes)
        incoming = {node_id: 0 for node_id in nodes.keys()}
        for conn in connections:
            target = conn.get("target")
            if target in incoming:
                incoming[target] += 1

        start_nodes = [node_id for node_id, count in incoming.items() if count == 0]

        if not start_nodes:
            return len(nodes)  # Circular workflow

        # Calculate maximum depth using DFS
        max_depth = 0
        visited = set()

        def dfs(node_id, depth):
            nonlocal max_depth
            if node_id in visited:
                return depth  # Avoid infinite recursion

            visited.add(node_id)
            max_depth = max(max_depth, depth)

            for neighbor in graph.get(node_id, []):
                dfs(neighbor, depth + 1)

            visited.remove(node_id)

        for start_node in start_nodes:
            dfs(start_node, 1)

        return max_depth

    def _determine_pattern_type(self, workflow_info: Dict[str, Any]) -> str:
        """Determine the primary pattern type of the workflow."""
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])
        cycles = workflow_info.get("cycles", [])

        if not nodes:
            return "empty"

        if cycles:
            return "cyclic"

        if len(nodes) == 1:
            return "single_node"

        # Analyze connection patterns
        node_ids = {node["node_id"] for node in nodes}

        # Count incoming and outgoing connections per node
        incoming_counts = {node_id: 0 for node_id in node_ids}
        outgoing_counts = {node_id: 0 for node_id in node_ids}

        for conn in connections:
            source = conn.get("source")
            target = conn.get("target")
            if source in outgoing_counts:
                outgoing_counts[source] += 1
            if target in incoming_counts:
                incoming_counts[target] += 1

        # Check for linear pattern (each node has at most 1 incoming and 1 outgoing)
        is_linear = all(count <= 1 for count in incoming_counts.values()) and all(
            count <= 1 for count in outgoing_counts.values()
        )

        if is_linear:
            return "linear"

        # Check for parallel pattern (multiple nodes with same source/target)
        has_parallel = any(count > 1 for count in outgoing_counts.values()) or any(
            count > 1 for count in incoming_counts.values()
        )

        if has_parallel:
            return "parallel"

        return "complex"

    def _calculate_parallelism_score(self, workflow_info: Dict[str, Any]) -> float:
        """Calculate how much parallelism exists in the workflow."""
        connections = workflow_info.get("connections", [])
        nodes = workflow_info.get("nodes", [])

        if len(nodes) <= 1:
            return 0.0

        # Count parallel paths
        outgoing_counts = {}
        for conn in connections:
            source = conn.get("source")
            outgoing_counts[source] = outgoing_counts.get(source, 0) + 1

        # Calculate parallelism as ratio of parallel connections to total nodes
        parallel_connections = sum(
            count - 1 for count in outgoing_counts.values() if count > 1
        )
        max_possible = len(nodes) - 1

        return parallel_connections / max_possible if max_possible > 0 else 0.0

    def _calculate_max_cycle_depth(self, cycles: List[Dict[str, Any]]) -> int:
        """Calculate maximum depth of cycles."""
        if not cycles:
            return 0

        max_depth = 0
        for cycle in cycles:
            connections = cycle.get("connections", [])
            max_depth = max(max_depth, len(connections))

        return max_depth

    def _calculate_configuration_complexity(self, nodes: List[Dict[str, Any]]) -> float:
        """Calculate complexity based on node configurations."""
        if not nodes:
            return 0.0

        total_complexity = 0
        for node in nodes:
            config = node.get("parameters", {})
            # Count configuration parameters and nested complexity
            param_count = len(config)
            nested_complexity = sum(
                1 if isinstance(v, (dict, list)) else 0 for v in config.values()
            )
            total_complexity += param_count + nested_complexity * 2

        return total_complexity / len(nodes)

    def _calculate_connection_complexity(
        self, connections: List[Dict[str, Any]]
    ) -> float:
        """Calculate complexity based on connection patterns."""
        if not connections:
            return 0.0

        # Simple connections have complexity 1, complex mappings have higher complexity
        total_complexity = 0
        for conn in connections:
            base_complexity = 1

            # Check for complex output/input field names
            output_field = conn.get("output", "")
            input_field = conn.get("input", "")

            if len(output_field) > 10 or len(input_field) > 10:
                base_complexity += 0.5

            # Check for mapping complexity (if available)
            mapping = conn.get("mapping", {})
            if mapping:
                base_complexity += len(mapping) * 0.3

            total_complexity += base_complexity

        return total_complexity / len(connections)

    def _detect_performance_bottlenecks(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect potential performance bottlenecks in the workflow."""
        bottlenecks = []
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])

        # Detect sequential LLM calls
        llm_nodes = [node for node in nodes if "LLM" in node.get("node_type", "")]
        if len(llm_nodes) >= 3:
            # Check if they're in sequence
            llm_ids = {node["node_id"] for node in llm_nodes}
            sequential_llm = 0

            for conn in connections:
                if conn.get("source") in llm_ids and conn.get("target") in llm_ids:
                    sequential_llm += 1

            if sequential_llm >= 2:
                bottlenecks.append(
                    {
                        "type": "sequential_llm_calls",
                        "severity": "high",
                        "description": f"Found {len(llm_nodes)} LLM nodes in sequence",
                        "suggestion": "Consider parallelizing LLM calls or using batch processing",
                        "affected_nodes": [node["node_id"] for node in llm_nodes],
                    }
                )

        # Detect high-latency operation chains
        high_latency_types = {"HTTPRequestNode", "DatabaseQueryNode", "LLMAgentNode"}
        high_latency_nodes = [
            node for node in nodes if node.get("node_type") in high_latency_types
        ]

        if len(high_latency_nodes) >= 4:
            bottlenecks.append(
                {
                    "type": "high_latency_chain",
                    "severity": "medium",
                    "description": f"Found {len(high_latency_nodes)} high-latency operations",
                    "suggestion": "Consider caching, parallel execution, or async processing",
                    "affected_nodes": [node["node_id"] for node in high_latency_nodes],
                }
            )

        # Detect single point of failure
        outgoing_counts = {}
        for conn in connections:
            source = conn.get("source")
            outgoing_counts[source] = outgoing_counts.get(source, 0) + 1

        for node_id, count in outgoing_counts.items():
            if count >= 3:  # Node feeds into 3+ other nodes
                bottlenecks.append(
                    {
                        "type": "single_point_of_failure",
                        "severity": "high",
                        "description": f"Node '{node_id}' feeds into {count} other nodes",
                        "suggestion": "Add redundancy or split responsibilities",
                        "affected_nodes": [node_id],
                    }
                )

        return bottlenecks

    def _detect_error_risks(
        self, workflow_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect patterns that may lead to errors."""
        risks = []
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])

        # Detect nodes without error handling
        external_node_types = {
            "HTTPRequestNode",
            "DatabaseQueryNode",
            "ExternalAPINode",
        }
        external_nodes = [
            node for node in nodes if node.get("node_type") in external_node_types
        ]

        for node in external_nodes:
            config = node.get("parameters", {})
            has_retry = any(
                key in config for key in ["retry", "max_retries", "retry_config"]
            )
            has_timeout = any(key in config for key in ["timeout", "request_timeout"])

            if not (has_retry or has_timeout):
                risks.append(
                    {
                        "type": "no_error_handling",
                        "severity": "medium",
                        "description": f"External node '{node['node_id']}' lacks error handling",
                        "suggestion": "Add retry logic and timeout configuration",
                        "affected_nodes": [node["node_id"]],
                    }
                )

        # Detect single points of failure (already detected in bottlenecks)
        outgoing_counts = {}
        for conn in connections:
            source = conn.get("source")
            outgoing_counts[source] = outgoing_counts.get(source, 0) + 1

        critical_nodes = [
            node_id for node_id, count in outgoing_counts.items() if count >= 3
        ]
        for node_id in critical_nodes:
            risks.append(
                {
                    "type": "single_point_of_failure",
                    "severity": "high",
                    "description": f"Critical dependency on node '{node_id}'",
                    "suggestion": "Add backup nodes or implement circuit breaker pattern",
                    "affected_nodes": [node_id],
                }
            )

        return risks

    def _generate_complexity_optimizations(
        self, workflow_info: Dict[str, Any], metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate optimization suggestions based on complexity analysis."""
        suggestions = []
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])

        # Suggest parallelization for linear workflows
        if (
            metrics.get("pattern_type") == "linear"
            and metrics.get("node_count", 0) >= 4
        ):
            suggestions.append(
                {
                    "type": "parallelize_operations",
                    "priority": "medium",
                    "description": "Linear workflow could benefit from parallelization",
                    "suggestion": "Consider splitting independent operations into parallel branches",
                    "potential_improvement": "50-70% reduction in execution time",
                }
            )

        # Suggest pipeline optimization for high-depth workflows
        if metrics.get("workflow_depth", 0) >= 5:
            suggestions.append(
                {
                    "type": "pipeline_optimization",
                    "priority": "high",
                    "description": "Deep workflow may benefit from pipelining",
                    "suggestion": "Implement streaming/pipeline processing to reduce latency",
                    "potential_improvement": "30-50% reduction in end-to-end latency",
                }
            )

        # Suggest caching for repeated operations
        node_types = metrics.get("node_types", {})
        for node_type, count in node_types.items():
            if count >= 3 and node_type in {
                "LLMAgentNode",
                "HTTPRequestNode",
                "DatabaseQueryNode",
            }:
                suggestions.append(
                    {
                        "type": "add_caching",
                        "priority": "medium",
                        "description": f"Multiple {node_type} instances detected",
                        "suggestion": f"Add caching layer for {node_type} to avoid redundant calls",
                        "potential_improvement": "20-40% reduction in external API calls",
                    }
                )

        # Suggest batch processing for high node counts
        if metrics.get("node_count", 0) >= 10:
            suggestions.append(
                {
                    "type": "batch_processing",
                    "priority": "low",
                    "description": "Large workflow may benefit from batch processing",
                    "suggestion": "Group similar operations into batches to improve efficiency",
                    "potential_improvement": "10-25% improvement in resource utilization",
                }
            )

        return suggestions

    def _analyze_resource_usage(self, workflow_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze estimated resource usage of the workflow."""
        nodes = workflow_info.get("nodes", [])

        # Categorize nodes by resource usage
        memory_intensive = {
            "LLMAgentNode",
            "EmbeddingGeneratorNode",
            "VectorSearchNode",
            "MLModelNode",
        }
        cpu_intensive = {
            "DataProcessorNode",
            "MLModelNode",
            "ImageProcessorNode",
            "ComputeNode",
        }

        memory_intensive_count = sum(
            1 for node in nodes if node.get("node_type") in memory_intensive
        )

        cpu_intensive_count = sum(
            1 for node in nodes if node.get("node_type") in cpu_intensive
        )

        # Rough estimation (in MB and cores)
        estimated_memory = memory_intensive_count * 500 + len(nodes) * 50
        estimated_cpu_cores = max(1, cpu_intensive_count // 2 + 1)

        return {
            "memory_intensive_nodes": memory_intensive_count,
            "cpu_intensive_nodes": cpu_intensive_count,
            "estimated_memory_usage": estimated_memory,
            "estimated_cpu_cores": estimated_cpu_cores,
            "resource_efficiency_score": min(
                1.0, len(nodes) / max(1, memory_intensive_count + cpu_intensive_count)
            ),
        }

    def _analyze_scalability(self, workflow_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze scalability characteristics of the workflow."""
        nodes = workflow_info.get("nodes", [])
        connections = workflow_info.get("connections", [])

        # Check for scalable patterns
        has_load_balancer = any(
            "LoadBalancer" in node.get("node_type", "")
            or "Balancer" in node.get("node_type", "")
            for node in nodes
        )

        has_workers = sum(
            1
            for node in nodes
            if "Worker" in node.get("node_type", "")
            or "Processor" in node.get("node_type", "")
        )

        # Calculate load distribution score
        outgoing_counts = {}
        for conn in connections:
            source = conn.get("source")
            outgoing_counts[source] = outgoing_counts.get(source, 0) + 1

        max_outgoing = max(outgoing_counts.values()) if outgoing_counts else 1
        avg_outgoing = (
            sum(outgoing_counts.values()) / len(outgoing_counts)
            if outgoing_counts
            else 1
        )

        load_distribution_score = min(1.0, avg_outgoing / max_outgoing)

        # Horizontal scaling potential
        parallel_score = sum(1 for count in outgoing_counts.values() if count > 1)
        horizontal_scaling_potential = min(
            1.0, parallel_score / max(1, len(nodes) // 2)
        )

        # Count bottlenecks (nodes with high fan-in/fan-out)
        bottleneck_count = sum(1 for count in outgoing_counts.values() if count > 5)

        return {
            "horizontal_scaling_potential": round(horizontal_scaling_potential, 2),
            "load_distribution_score": round(load_distribution_score, 2),
            "has_load_balancer": has_load_balancer,
            "worker_node_count": has_workers,
            "bottleneck_count": bottleneck_count,
            "scalability_score": round(
                (horizontal_scaling_potential + load_distribution_score) / 2, 2
            ),
        }
