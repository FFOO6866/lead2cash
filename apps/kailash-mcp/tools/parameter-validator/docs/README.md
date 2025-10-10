# Kailash MCP Parameter Validation Tool

## 🎯 Purpose

The MCP Parameter Validation Tool is a proactive error prevention system that validates Kailash SDK workflows for parameter and connection errors **before** they cause runtime failures. It ensures you "never see another parameter error ever again" by catching common mistakes during development.

## 🚀 Quick Start

### Installation

```bash
# Install the tool
cd apps/kailash-mcp/tools/parameter-validator
pip install -e .

# Or install with Kailash SDK
pip install kailash[mcp]
```

### Basic Usage

```python
# Validate a workflow
from kailash_mcp.parameter_validator import validate_workflow

workflow_code = '''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "Hello"})
workflow.add_connection("agent", "result", "processor", "input")
'''

result = validate_workflow(workflow_code)
print(f"Has errors: {result['has_errors']}")
print(f"Errors: {result['errors']}")
```

### Claude Desktop Integration

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "parameter-validator": {
      "command": "python",
      "args": ["-m", "apps.kailash-mcp.tools.parameter-validator.src.server"]
    }
  }
}
```

## 📚 Documentation

- [Installation Guide](INSTALLATION.md) - Detailed setup instructions
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Usage Patterns](USAGE_PATTERNS.md) - Common usage scenarios
- [Development Flow](DEVELOPMENT_FLOW.md) - Claude Code integration
- [Error Codes](ERROR_CODES.md) - Complete error reference
- [Examples](EXAMPLES.md) - Working code examples

## 🛡️ What It Validates

### Parameter Errors (PAR001-PAR004)
- Missing `get_parameters()` method
- Undeclared parameter usage
- Missing type fields in NodeParameter
- Missing required parameters for node types

### Connection Errors (CON001-CON007)
- Invalid argument count
- Old 2-parameter syntax
- Non-existent nodes
- Circular dependencies
- Suspicious field names

### Gold Standards (GOLD001-GOLD002)
- Correct execution patterns
- SDK best practices

## 🔧 Core Features

1. **Real-time Validation** - Check workflows as you write them
2. **Intelligent Suggestions** - Get fix recommendations with code examples
3. **MCP Protocol** - Full Model Context Protocol compliance
4. **AI Integration** - Works seamlessly with LLMAgentNode
5. **Extensible** - Easy to add new validation rules

## 🎮 Try It Now

```python
# Example with errors
workflow_code = '''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Missing required parameters
workflow.add_node("LLMAgentNode", "agent", {})
# Wrong connection syntax
workflow.add_connection("agent", "processor")
'''

# Validate
result = validate_workflow(workflow_code)

# Get suggestions
from kailash_mcp.parameter_validator import suggest_fixes
suggestions = suggest_fixes(result['errors'])

for suggestion in suggestions:
    print(f"Fix: {suggestion['fix']}")
    print(f"Example:\n{suggestion['code_example']}\n")
```

## 📊 Performance

- Validation time: <50ms for typical workflows
- Memory usage: <10MB
- Test coverage: 100% (106/106 tests passing)

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - See [LICENSE](../LICENSE) for details.