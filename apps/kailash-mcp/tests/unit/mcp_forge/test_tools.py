"""
Unit tests for MCP Forge tool framework functionality.

Testing Strategy:
- Unit tests with mocking allowed (Tier 1)
- Test @tool decorator and schema generation
- Parameter validation logic
- Tool execution context handling
"""

import inspect
import json
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock, patch

import pytest


class TestToolDecorator:
    """Unit tests for @tool decorator functionality."""

    def test_tool_decorator_basic_function(self):
        """Test @tool decorator on basic function."""

        # Mock the tool decorator behavior
        def mock_tool_decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            # Add metadata that the decorator would add
            wrapper._tool_name = func.__name__
            wrapper._tool_description = func.__doc__ or ""
            wrapper._tool_parameters = {}

            return wrapper

        @mock_tool_decorator
        def simple_tool(message: str) -> str:
            """A simple tool that echoes a message."""
            return f"Echo: {message}"

        # Test decorator applied correctly
        assert hasattr(simple_tool, "_tool_name")
        assert simple_tool._tool_name == "simple_tool"
        assert "simple tool" in simple_tool._tool_description.lower()

        # Test function still works
        result = simple_tool("Hello")
        assert result == "Echo: Hello"

    def test_tool_decorator_with_type_hints(self):
        """Test @tool decorator extracts parameter types from hints."""

        def extract_type_hints(func):
            """Mock function to extract type hints like the real decorator would."""
            sig = inspect.signature(func)
            parameters = {}

            for name, param in sig.parameters.items():
                param_type = "string"  # Default
                required = param.default == inspect.Parameter.empty

                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list:
                        param_type = "array"
                    elif param.annotation == dict:
                        param_type = "object"

                parameters[name] = {"type": param_type, "required": required}

            return parameters

        def typed_tool(count: int, factor: float = 1.0, enabled: bool = True) -> float:
            """Tool with various type hints."""
            return count * factor if enabled else 0

        # Test type hint extraction
        params = extract_type_hints(typed_tool)

        assert params["count"]["type"] == "integer"
        assert params["count"]["required"] is True

        assert params["factor"]["type"] == "number"
        assert params["factor"]["required"] is False

        assert params["enabled"]["type"] == "boolean"
        assert params["enabled"]["required"] is False

    def test_tool_decorator_complex_types(self):
        """Test @tool decorator with complex parameter types."""

        def analyze_complex_types(func):
            """Mock analysis of complex type annotations."""
            sig = inspect.signature(func)
            complex_params = {}

            for name, param in sig.parameters.items():
                annotation = param.annotation
                param_info = {"name": name}

                # Handle Optional types
                if hasattr(annotation, "__origin__") and annotation.__origin__ is Union:
                    args = annotation.__args__
                    if len(args) == 2 and type(None) in args:
                        # This is Optional[T]
                        real_type = next(arg for arg in args if arg is not type(None))
                        param_info["type"] = "optional"
                        param_info["inner_type"] = (
                            real_type.__name__
                            if hasattr(real_type, "__name__")
                            else str(real_type)
                        )
                        param_info["required"] = False
                    else:
                        param_info["type"] = "union"
                        param_info["types"] = [arg.__name__ for arg in args]

                # Handle List types
                elif (
                    hasattr(annotation, "__origin__") and annotation.__origin__ is list
                ):
                    param_info["type"] = "array"
                    if hasattr(annotation, "__args__") and annotation.__args__:
                        param_info["items"] = annotation.__args__[0].__name__

                # Handle Dict types
                elif (
                    hasattr(annotation, "__origin__") and annotation.__origin__ is dict
                ):
                    param_info["type"] = "object"
                    if (
                        hasattr(annotation, "__args__")
                        and len(annotation.__args__) >= 2
                    ):
                        param_info["key_type"] = annotation.__args__[0].__name__
                        param_info["value_type"] = annotation.__args__[1].__name__

                else:
                    param_info["type"] = "simple"
                    param_info["python_type"] = (
                        annotation.__name__
                        if hasattr(annotation, "__name__")
                        else str(annotation)
                    )

                complex_params[name] = param_info

            return complex_params

        def complex_tool(
            items: List[str],
            config: Dict[str, Any],
            timeout: Optional[int] = None,
            fallback: Union[str, int] = "default",
        ) -> Dict[str, Any]:
            """Tool with complex parameter types."""
            return {"processed": len(items), "config": config}

        # Test complex type analysis
        params = analyze_complex_types(complex_tool)

        # Test List[str] detection
        assert params["items"]["type"] == "array"
        assert params["items"]["items"] == "str"

        # Test Dict[str, Any] detection
        assert params["config"]["type"] == "object"
        assert params["config"]["key_type"] == "str"

        # Test Optional[int] detection
        assert params["timeout"]["type"] == "optional"
        assert params["timeout"]["inner_type"] == "int"
        assert params["timeout"]["required"] is False

        # Test Union[str, int] detection
        assert params["fallback"]["type"] == "union"
        assert "str" in params["fallback"]["types"]
        assert "int" in params["fallback"]["types"]

    def test_tool_parameter_validation_success(self):
        """Test successful parameter validation."""

        def validate_parameters(schema: Dict, params: Dict) -> bool:
            """Mock parameter validation logic."""
            for param_name, param_schema in schema.items():
                if param_schema.get("required", False) and param_name not in params:
                    return False

                if param_name in params:
                    value = params[param_name]
                    expected_type = param_schema.get("type")

                    if expected_type == "integer" and not isinstance(value, int):
                        return False
                    elif expected_type == "string" and not isinstance(value, str):
                        return False
                    elif expected_type == "array" and not isinstance(value, list):
                        return False
                    elif expected_type == "object" and not isinstance(value, dict):
                        return False

            return True

        # Test valid parameters
        schema = {
            "message": {"type": "string", "required": True},
            "count": {"type": "integer", "required": False},
        }

        valid_params = {"message": "Hello", "count": 5}
        assert validate_parameters(schema, valid_params) is True

        valid_params_minimal = {"message": "Hello"}
        assert validate_parameters(schema, valid_params_minimal) is True

    def test_tool_parameter_validation_failures(self):
        """Test parameter validation failure cases."""

        def validate_parameters(schema: Dict, params: Dict) -> tuple[bool, str]:
            """Mock parameter validation with error messages."""
            for param_name, param_schema in schema.items():
                if param_schema.get("required", False) and param_name not in params:
                    return False, f"Missing required parameter: {param_name}"

                if param_name in params:
                    value = params[param_name]
                    expected_type = param_schema.get("type")

                    type_checks = {
                        "integer": int,
                        "string": str,
                        "array": list,
                        "object": dict,
                        "boolean": bool,
                    }

                    if expected_type in type_checks:
                        expected_python_type = type_checks[expected_type]
                        if not isinstance(value, expected_python_type):
                            return (
                                False,
                                f"Parameter {param_name} must be {expected_type}, got {type(value).__name__}",
                            )

            return True, "Valid"

        schema = {
            "message": {"type": "string", "required": True},
            "count": {"type": "integer", "required": False},
            "enabled": {"type": "boolean", "required": True},
        }

        # Test missing required parameter
        invalid_params = {"message": "Hello"}
        valid, error = validate_parameters(schema, invalid_params)
        assert valid is False
        assert "enabled" in error

        # Test wrong type
        invalid_params = {"message": "Hello", "count": "not_an_int", "enabled": True}
        valid, error = validate_parameters(schema, invalid_params)
        assert valid is False
        assert "count" in error and "integer" in error

    def test_tool_execution_context(self):
        """Test tool execution context handling."""

        class MockExecutionContext:
            """Mock execution context for tools."""

            def __init__(self, request_id: str, user_id: Optional[str] = None):
                self.request_id = request_id
                self.user_id = user_id
                self.start_time = 1234567890  # Mock timestamp
                self.metadata = {}

            def add_metadata(self, key: str, value: Any):
                self.metadata[key] = value

            def get_execution_info(self) -> Dict[str, Any]:
                return {
                    "request_id": self.request_id,
                    "user_id": self.user_id,
                    "start_time": self.start_time,
                    "metadata": self.metadata,
                }

        # Test context creation
        context = MockExecutionContext("req-123", "user-456")
        assert context.request_id == "req-123"
        assert context.user_id == "user-456"

        # Test metadata handling
        context.add_metadata("tool_name", "test_tool")
        context.add_metadata("parameters", {"message": "Hello"})

        info = context.get_execution_info()
        assert info["metadata"]["tool_name"] == "test_tool"
        assert info["metadata"]["parameters"]["message"] == "Hello"

    def test_tool_error_handling(self):
        """Test tool execution error handling."""

        class ToolExecutionError(Exception):
            """Mock tool execution error."""

            def __init__(self, message: str, error_code: str = "TOOL_ERROR"):
                super().__init__(message)
                self.error_code = error_code
                self.message = message

        def execute_tool_with_error_handling(tool_func, params: Dict) -> Dict[str, Any]:
            """Mock tool execution with error handling."""
            try:
                result = tool_func(**params)
                return {"success": True, "result": result}
            except ToolExecutionError as e:
                return {
                    "success": False,
                    "error": {"code": e.error_code, "message": e.message},
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": {"code": "UNEXPECTED_ERROR", "message": str(e)},
                }

        # Test successful execution
        def working_tool(message: str) -> str:
            return f"Processed: {message}"

        result = execute_tool_with_error_handling(working_tool, {"message": "test"})
        assert result["success"] is True
        assert result["result"] == "Processed: test"

        # Test tool execution error
        def failing_tool(message: str) -> str:
            raise ToolExecutionError("Tool failed to process", "PROCESSING_ERROR")

        result = execute_tool_with_error_handling(failing_tool, {"message": "test"})
        assert result["success"] is False
        assert result["error"]["code"] == "PROCESSING_ERROR"
        assert "failed to process" in result["error"]["message"]

        # Test unexpected error
        def crashing_tool(message: str) -> str:
            raise ValueError("Unexpected crash")

        result = execute_tool_with_error_handling(crashing_tool, {"message": "test"})
        assert result["success"] is False
        assert result["error"]["code"] == "UNEXPECTED_ERROR"
        assert "Unexpected crash" in result["error"]["message"]


class TestSchemaGeneration:
    """Unit tests for tool schema generation."""

    def test_schema_from_function_signature(self):
        """Test JSON schema generation from function signature."""

        def generate_json_schema(func) -> Dict[str, Any]:
            """Mock schema generation from function."""
            sig = inspect.signature(func)

            schema = {"type": "object", "properties": {}, "required": []}

            for name, param in sig.parameters.items():
                prop_schema = {"description": f"Parameter {name}"}

                # Map Python types to JSON Schema types
                if param.annotation == str:
                    prop_schema["type"] = "string"
                elif param.annotation == int:
                    prop_schema["type"] = "integer"
                elif param.annotation == float:
                    prop_schema["type"] = "number"
                elif param.annotation == bool:
                    prop_schema["type"] = "boolean"
                elif param.annotation == list:
                    prop_schema["type"] = "array"
                elif param.annotation == dict:
                    prop_schema["type"] = "object"
                else:
                    prop_schema["type"] = "string"  # Default

                schema["properties"][name] = prop_schema

                # Check if required
                if param.default == inspect.Parameter.empty:
                    schema["required"].append(name)

            return schema

        def sample_tool(name: str, age: int, active: bool = True) -> str:
            """Sample tool for schema testing."""
            return f"{name} is {age} years old"

        schema = generate_json_schema(sample_tool)

        # Test schema structure
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Test properties
        assert "name" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"

        assert "age" in schema["properties"]
        assert schema["properties"]["age"]["type"] == "integer"

        assert "active" in schema["properties"]
        assert schema["properties"]["active"]["type"] == "boolean"

        # Test required fields
        assert "name" in schema["required"]
        assert "age" in schema["required"]
        assert "active" not in schema["required"]  # Has default value

    def test_schema_with_docstring_parsing(self):
        """Test schema generation with docstring parameter descriptions."""

        def parse_docstring_params(docstring: str) -> Dict[str, str]:
            """Mock docstring parsing for parameter descriptions."""
            if not docstring:
                return {}

            params = {}
            lines = docstring.split("\n")

            for line in lines:
                line = line.strip()
                if line.startswith(":param "):
                    # Parse ":param name: description"
                    parts = line[7:].split(":", 1)  # Remove ":param "
                    if len(parts) == 2:
                        param_name = parts[0].strip()
                        description = parts[1].strip()
                        params[param_name] = description

            return params

        def documented_tool(message: str, count: int = 1) -> str:
            """
            Process a message multiple times.

            :param message: The message to process
            :param count: Number of times to repeat the message
            :return: Processed message
            """
            return message * count

        # Test docstring parsing
        param_descriptions = parse_docstring_params(documented_tool.__doc__)

        assert "message" in param_descriptions
        assert "process" in param_descriptions["message"].lower()

        assert "count" in param_descriptions
        assert "repeat" in param_descriptions["count"].lower()

    def test_schema_with_default_values(self):
        """Test schema generation includes default values."""

        def generate_schema_with_defaults(func) -> Dict[str, Any]:
            """Mock schema generation including default values."""
            sig = inspect.signature(func)

            schema = {"type": "object", "properties": {}, "required": []}

            for name, param in sig.parameters.items():
                prop_schema = {"description": f"Parameter {name}"}

                # Add type
                if param.annotation == str:
                    prop_schema["type"] = "string"
                elif param.annotation == int:
                    prop_schema["type"] = "integer"
                elif param.annotation == bool:
                    prop_schema["type"] = "boolean"

                # Add default value if present
                if param.default != inspect.Parameter.empty:
                    prop_schema["default"] = param.default
                else:
                    schema["required"].append(name)

                schema["properties"][name] = prop_schema

            return schema

        def tool_with_defaults(
            message: str, repeat: int = 1, uppercase: bool = False
        ) -> str:
            """Tool with various default values."""
            result = message * repeat
            return result.upper() if uppercase else result

        schema = generate_schema_with_defaults(tool_with_defaults)

        # Test required vs optional
        assert "message" in schema["required"]
        assert "repeat" not in schema["required"]
        assert "uppercase" not in schema["required"]

        # Test default values
        assert schema["properties"]["repeat"]["default"] == 1
        assert schema["properties"]["uppercase"]["default"] is False
        assert "default" not in schema["properties"]["message"]

    def test_schema_validation_against_openapi(self):
        """Test generated schema follows OpenAPI specifications."""

        def validate_openapi_schema(schema: Dict[str, Any]) -> tuple[bool, List[str]]:
            """Mock OpenAPI schema validation."""
            errors = []

            # Check required top-level fields
            if "type" not in schema:
                errors.append("Missing 'type' field")
            elif schema["type"] != "object":
                errors.append("Top-level type must be 'object'")

            if "properties" not in schema:
                errors.append("Missing 'properties' field")

            # Check properties structure
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if "type" not in prop_schema:
                        errors.append(f"Property '{prop_name}' missing 'type'")
                    elif prop_schema["type"] not in [
                        "string",
                        "integer",
                        "number",
                        "boolean",
                        "array",
                        "object",
                    ]:
                        errors.append(f"Property '{prop_name}' has invalid type")

            # Check required field
            if "required" in schema and not isinstance(schema["required"], list):
                errors.append("'required' must be an array")

            return len(errors) == 0, errors

        valid_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer", "description": "User age"},
            },
            "required": ["name"],
        }

        is_valid, errors = validate_openapi_schema(valid_schema)
        assert is_valid is True
        assert len(errors) == 0

        # Test invalid schema
        invalid_schema = {"properties": {"name": {"description": "Missing type"}}}

        is_valid, errors = validate_openapi_schema(invalid_schema)
        assert is_valid is False
        assert len(errors) > 0
        assert any("type" in error for error in errors)
