# Usage Patterns

## 🎯 Common Scenarios

### 1. Development-Time Validation

**Scenario:** Validate workflows as you write them to catch errors early.

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash_mcp.parameter_validator import validate_workflow

# Write your workflow
workflow_code = '''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "assistant", {
    "model": "gpt-4",
    "prompt": "Process this data: {{input}}"
})
workflow.add_node("DataProcessorNode", "processor", {
    "operation": "transform"
})
workflow.add_connection("assistant", "result", "processor", "input")
'''

# Validate immediately
result = validate_workflow(workflow_code)

if result["has_errors"]:
    print("❌ Validation errors found:")
    for error in result["errors"]:
        print(f"  - {error['code']}: {error['message']}")
else:
    print("✅ Workflow is valid!")
```

### 2. AI-Assisted Development

**Scenario:** LLMAgentNode automatically validates generated workflows.

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# Create workflow with AI assistant
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "ai_developer", {
    "model": "gpt-4",
    "prompt": "Create a data processing workflow that reads CSV and transforms it",
    "use_real_mcp": True,
    "mcp_servers": ["parameter-validator"],
    "system_prompt": "Always validate workflows using the parameter-validator tool"
})

# The AI will automatically:
# 1. Generate workflow code
# 2. Validate it using MCP tool
# 3. Fix any errors found
# 4. Return validated workflow

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

### 3. Iterative Error Correction

**Scenario:** Fix errors one by one with guided suggestions.

```python
from kailash_mcp.parameter_validator import validate_workflow, suggest_fixes

# Initial workflow with errors
workflow_v1 = '''
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing params
workflow.add_connection("agent", "processor")   # Wrong syntax
'''

# Iteration 1: Validate
result = validate_workflow(workflow_v1)
suggestions = suggest_fixes(result["errors"])

print("Found errors:", len(result["errors"]))
for suggestion in suggestions:
    print(f"\nError: {suggestion['error_code']}")
    print(f"Fix: {suggestion['fix']}")
    print(f"Example:\n{suggestion['code_example']}")

# Iteration 2: Apply fixes
workflow_v2 = '''
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process data"
})
workflow.add_connection("agent", "result", "processor", "input")
'''

# Re-validate
result = validate_workflow(workflow_v2)
print(f"\nAfter fixes: {len(result['errors'])} errors remaining")
```

### 4. CI/CD Integration

**Scenario:** Validate all workflows in CI pipeline.

```python
#!/usr/bin/env python
"""pre-commit hook for workflow validation"""

import os
import sys
from pathlib import Path
from kailash_mcp.parameter_validator import validate_workflow

def validate_project_workflows():
    """Validate all workflow files in project."""
    errors_found = False
    workflow_files = Path(".").glob("**/workflows/*.py")
    
    for workflow_file in workflow_files:
        print(f"Validating {workflow_file}...")
        
        with open(workflow_file) as f:
            code = f.read()
        
        result = validate_workflow(code)
        
        if result["has_errors"]:
            errors_found = True
            print(f"❌ {workflow_file}: {len(result['errors'])} errors")
            for error in result["errors"]:
                print(f"   Line {error.get('line', '?')}: {error['message']}")
        else:
            print(f"✅ {workflow_file}: Valid")
    
    return 0 if not errors_found else 1

if __name__ == "__main__":
    sys.exit(validate_project_workflows())
```

### 5. Custom Node Development

**Scenario:** Validate custom node implementations.

```python
from kailash_mcp.parameter_validator import check_node_parameters

# Your custom node code
node_code = '''
from kailash.nodes.base import Node, NodeParameter
from typing import List

class DataEnrichmentNode(Node):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(
                name="input_data",
                type=dict,
                required=True,
                description="Data to enrich"
            ),
            NodeParameter(
                name="enrichment_source",
                type=str,
                required=True,
                description="Source for enrichment data"
            ),
            NodeParameter(
                name="merge_strategy",
                type=str,
                required=False,
                default="left",
                description="How to merge data"
            )
        ]
    
    def run(self, **kwargs):
        # Implementation
        return {"enriched_data": {}}
'''

# Validate node
result = check_node_parameters(node_code)

if result["has_errors"]:
    print("Node validation failed!")
else:
    print("Node parameters are properly declared!")
```

### 6. Workflow Testing Helper

**Scenario:** Validate test workflows before running tests.

```python
import pytest
from kailash_mcp.parameter_validator import validate_workflow

def create_test_workflow(code: str):
    """Helper to create and validate test workflows."""
    # First validate
    result = validate_workflow(code)
    
    if result["has_errors"]:
        error_msg = "\n".join([
            f"{e['code']}: {e['message']}" 
            for e in result["errors"]
        ])
        pytest.fail(f"Invalid test workflow:\n{error_msg}")
    
    # Then execute
    exec_globals = {}
    exec(code, exec_globals)
    return exec_globals.get("workflow")

def test_data_pipeline():
    """Test data processing pipeline."""
    workflow = create_test_workflow('''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("CSVReaderNode", "reader", {"file_path": "test.csv"})
workflow.add_node("DataProcessorNode", "processor", {"operation": "clean"})
workflow.add_connection("reader", "data", "processor", "input")
''')
    
    assert workflow is not None
    # Continue with test...
```

### 7. Interactive Development

**Scenario:** Real-time validation in Jupyter notebooks.

```python
# In Jupyter notebook
from IPython.display import display, HTML
from kailash_mcp.parameter_validator import validate_workflow, suggest_fixes

def validate_cell(code):
    """Validate workflow code in notebook cell."""
    result = validate_workflow(code)
    
    if result["has_errors"]:
        html = "<div style='background:#fee; padding:10px; border-radius:5px;'>"
        html += "<h4>❌ Validation Errors:</h4><ul>"
        
        for error in result["errors"]:
            html += f"<li><b>{error['code']}</b>: {error['message']}</li>"
        
        html += "</ul><h4>💡 Suggestions:</h4>"
        
        suggestions = suggest_fixes(result["errors"])
        for s in suggestions:
            html += f"<details><summary>{s['fix']}</summary>"
            html += f"<pre>{s['code_example']}</pre></details>"
        
        html += "</div>"
    else:
        html = "<div style='background:#efe; padding:10px; border-radius:5px;'>"
        html += "✅ <b>Workflow is valid!</b></div>"
    
    display(HTML(html))

# Use in cells
workflow_code = '''
workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
'''

validate_cell(workflow_code)
```

### 8. Bulk Validation Report

**Scenario:** Generate validation report for multiple workflows.

```python
import json
from pathlib import Path
from datetime import datetime
from kailash_mcp.parameter_validator import validate_workflow

def generate_validation_report(workflow_dir: str):
    """Generate comprehensive validation report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": 0, "valid": 0, "errors": 0},
        "workflows": []
    }
    
    for workflow_file in Path(workflow_dir).glob("**/*.py"):
        with open(workflow_file) as f:
            code = f.read()
        
        result = validate_workflow(code)
        
        workflow_report = {
            "file": str(workflow_file),
            "valid": not result["has_errors"],
            "error_count": len(result["errors"]),
            "errors": result["errors"]
        }
        
        report["workflows"].append(workflow_report)
        report["summary"]["total"] += 1
        
        if result["has_errors"]:
            report["summary"]["errors"] += 1
        else:
            report["summary"]["valid"] += 1
    
    # Save report
    with open("validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"Validation Report - {report['timestamp']}")
    print(f"Total workflows: {report['summary']['total']}")
    print(f"Valid: {report['summary']['valid']}")
    print(f"With errors: {report['summary']['errors']}")
    
    return report

# Generate report
report = generate_validation_report("./workflows")
```

## 🎨 Best Practices

1. **Validate Early and Often** - Don't wait until runtime
2. **Use with AI Agents** - Let LLMs self-correct using validation
3. **Automate in CI/CD** - Catch errors before merge
4. **Learn from Suggestions** - Improve your SDK knowledge
5. **Custom Validation** - Extend for domain-specific rules

## 🚀 Advanced Patterns

See [EXAMPLES.md](EXAMPLES.md) for more complex usage patterns.