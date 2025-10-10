# API Reference

## MCP Tools

The parameter validator exposes 7 tools via MCP protocol:

### 1. `validate_workflow`

Validates a complete Kailash workflow for parameter and connection errors.

**Parameters:**
- `workflow_code` (string, required): Python code defining the workflow

**Returns:**
```json
{
  "has_errors": boolean,
  "errors": [
    {
      "code": "PAR001",
      "message": "Node class 'CustomNode' missing get_parameters() method",
      "line": 5,
      "severity": "error",
      "node_class": "CustomNode"
    }
  ],
  "warnings": [],
  "suggestions": []
}
```

**Example:**
```python
result = mcp_client.call_tool("validate_workflow", {
    "workflow_code": '''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
'''
})
```

### 2. `check_node_parameters`

Validates node parameter declarations in a node class definition.

**Parameters:**
- `node_code` (string, required): Python code defining the node class

**Returns:**
```json
{
  "has_errors": boolean,
  "errors": [
    {
      "code": "PAR003",
      "message": "NodeParameter missing required 'type' field",
      "parameter": "input_data",
      "severity": "error"
    }
  ],
  "warnings": [],
  "suggestions": []
}
```

**Example:**
```python
result = mcp_client.call_tool("check_node_parameters", {
    "node_code": '''
class MyNode(Node):
    def get_parameters(self):
        return [
            NodeParameter(name="input", type=str, required=True)
        ]
'''
})
```

### 3. `validate_connections`

Validates workflow connection syntax and structure.

**Parameters:**
- `connections` (array, required): List of connection objects

**Returns:**
```json
{
  "has_errors": boolean,
  "errors": [
    {
      "code": "CON002",
      "message": "Connection uses old 2-parameter syntax",
      "source": "node1",
      "target": "node2",
      "severity": "error"
    }
  ],
  "warnings": [],
  "suggestions": []
}
```

**Example:**
```python
result = mcp_client.call_tool("validate_connections", {
    "connections": [
        {"source": "node1", "output": "result", "target": "node2", "input": "data"},
        {"source": "node2", "target": "node3"}  # Wrong syntax
    ]
})
```

### 4. `suggest_fixes`

Generates fix suggestions for validation errors.

**Parameters:**
- `errors` (array, required): List of validation errors

**Returns:**
```json
[
  {
    "error_code": "PAR001",
    "description": "Add get_parameters() method to CustomNode",
    "fix": "Add get_parameters() method to CustomNode",
    "code_example": "def get_parameters(self) -> List[NodeParameter]:\n    return [\n        NodeParameter(\n            name=\"input_data\",\n            type=dict,\n            required=True\n        )\n    ]",
    "explanation": "Every node must implement get_parameters()..."
  }
]
```

**Example:**
```python
# First validate
validation = mcp_client.call_tool("validate_workflow", {"workflow_code": code})

# Then get suggestions
suggestions = mcp_client.call_tool("suggest_fixes", {
    "errors": validation["errors"]
})
```

### 5. `validate_gold_standards`

Validates code against Kailash SDK gold standards and best practices.

**Parameters:**
- `code` (string, required): Python code to validate
- `check_type` (string, optional): Specific check type

**Returns:**
```json
{
  "has_errors": boolean,
  "errors": [
    {
      "code": "GOLD002",
      "message": "Use runtime.execute(workflow.build()) pattern",
      "line": 10,
      "severity": "error"
    }
  ],
  "warnings": [],
  "suggestions": []
}
```

### 6. `get_validation_patterns`

Returns common validation patterns and examples.

**Parameters:** None

**Returns:**
```json
[
  {
    "name": "basic_workflow",
    "description": "Basic workflow pattern",
    "code_example": "from kailash.workflow.builder import WorkflowBuilder\n..."
  },
  {
    "name": "connected_nodes",
    "description": "Connected nodes pattern",
    "code_example": "workflow.add_connection(\"source\", \"output\", \"target\", \"input\")"
  }
]
```

### 7. `check_error_pattern`

Checks code for specific error patterns.

**Parameters:**
- `code` (string, required): Code to check
- `pattern_type` (string, required): Type of pattern to check for

**Returns:**
```json
{
  "has_pattern": boolean,
  "matches": [
    {
      "line": 5,
      "pattern": "2-param connection",
      "suggestion": "Use 4-parameter syntax"
    }
  ]
}
```

## Python API

### Core Classes

#### `ParameterValidator`

Main validation orchestrator.

```python
from kailash_mcp.parameter_validator import ParameterValidator

validator = ParameterValidator()

# Validate workflow
result = validator.validate_workflow(workflow_code)

# Validate node parameters
result = validator.validate_node_parameters(node_code)

# Validate connections only
result = validator.validate_connections_only(connections)
```

#### `FixSuggestionEngine`

Generates fix suggestions for errors.

```python
from kailash_mcp.parameter_validator import FixSuggestionEngine

engine = FixSuggestionEngine()

# Generate fixes
suggestions = engine.generate_fixes(errors)

# Get common patterns
patterns = engine.suggest_common_patterns()
```

#### `ParameterValidationServer`

MCP server implementation.

```python
from kailash_mcp.parameter_validator import ParameterValidationServer

server = ParameterValidationServer("my-validator")

# Start server
await server.start()

# Get capabilities
caps = server.get_capabilities()
```

### Validation Result Schema

All validation methods return a consistent result structure:

```python
{
    "has_errors": bool,              # True if any errors found
    "errors": List[Dict[str, Any]],  # List of error objects
    "warnings": List[Dict[str, Any]], # List of warning objects
    "suggestions": List[Dict[str, Any]] # List of suggestions
}
```

### Error Object Schema

```python
{
    "code": str,         # Error code (e.g., "PAR001")
    "message": str,      # Human-readable error message
    "severity": str,     # "error" or "warning"
    "line": int,         # Line number where error occurred (optional)
    "node_type": str,    # Node type involved (optional)
    "node_id": str,      # Node ID involved (optional)
    "parameter": str,    # Parameter name (optional)
    # Additional context fields based on error type
}
```

### Suggestion Object Schema

```python
{
    "error_code": str,      # Error code this fixes
    "description": str,     # Brief description
    "fix": str,            # Short fix description
    "code_example": str,   # Working code example
    "explanation": str     # Detailed explanation
}
```

## Error Codes Reference

See [ERROR_CODES.md](ERROR_CODES.md) for complete error code documentation.

## Advanced Usage

### Custom Validation Rules

```python
# Extend validator with custom rules
class CustomValidator(ParameterValidator):
    def validate_custom_rule(self, workflow_info):
        errors = []
        # Add custom validation logic
        return errors
```

### Batch Validation

```python
# Validate multiple workflows
workflows = ["workflow1.py", "workflow2.py", "workflow3.py"]
results = []

for workflow_file in workflows:
    with open(workflow_file) as f:
        code = f.read()
    result = validator.validate_workflow(code)
    results.append((workflow_file, result))
```

### Integration with CI/CD

```python
# Pre-commit hook example
import sys
from kailash_mcp.parameter_validator import validate_workflow

def validate_changed_workflows():
    # Get changed files from git
    # Validate each workflow file
    # Exit with error if validation fails
    pass

if __name__ == "__main__":
    validate_changed_workflows()
```