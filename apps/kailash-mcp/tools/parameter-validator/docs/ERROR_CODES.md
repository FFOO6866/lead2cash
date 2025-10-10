# Error Codes Reference

## Parameter Errors (PAR001-PAR004)

### PAR001: Missing get_parameters() Method

**Description:** Node class is missing the required `get_parameters()` method.

**Example:**
```python
# ❌ Error
class CustomNode(Node):
    def run(self, **kwargs):
        return {"result": "data"}

# ✅ Fixed
class CustomNode(Node):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(
                name="input_data",
                type=dict,
                required=True,
                description="Data to process"
            )
        ]
    
    def run(self, **kwargs):
        return {"result": "data"}
```

**Impact:** High - Node won't properly validate parameters at runtime

### PAR002: Undeclared Parameter Usage

**Description:** Parameter is used in node but not declared in `get_parameters()`.

**Example:**
```python
# ❌ Error
class DataNode(Node):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(name="input", type=str, required=True)
        ]
    
    def run(self, **kwargs):
        input_data = kwargs.get("input")
        format_type = kwargs.get("format")  # PAR002: 'format' not declared
        return {"formatted": f"{input_data}:{format_type}"}

# ✅ Fixed
class DataNode(Node):
    def get_parameters(self) -> List[NodeParameter]:
        return [
            NodeParameter(name="input", type=str, required=True),
            NodeParameter(name="format", type=str, required=False, default="json")
        ]
    # ... rest of implementation
```

**Impact:** High - Undeclared parameters are filtered out by SDK

### PAR003: Missing Type Field

**Description:** NodeParameter is missing the required 'type' field.

**Example:**
```python
# ❌ Error
NodeParameter(
    name="config",
    required=True,
    description="Configuration"
    # Missing: type=dict
)

# ✅ Fixed
NodeParameter(
    name="config",
    type=dict,  # Required field
    required=True,
    description="Configuration"
)
```

**Impact:** High - Runtime validation will fail

### PAR004: Missing Required Parameters

**Description:** Node is missing required parameters for its type.

**Common Required Parameters:**
- **LLMAgentNode**: `model`, `prompt`
- **HTTPRequestNode**: `url`
- **CSVReaderNode**: `file_path`
- **SQLDatabaseNode**: `connection_string`
- **PythonCodeNode**: `code`

**Example:**
```python
# ❌ Error
workflow.add_node("LLMAgentNode", "agent", {
    "prompt": "Hello"  # Missing: model
})

# ✅ Fixed
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Hello"
})
```

**Impact:** Critical - Node execution will fail

## Connection Errors (CON001-CON007)

### CON001: Invalid Connection Arguments

**Description:** Connection has wrong number of arguments (should be 4).

**Example:**
```python
# ❌ Error
workflow.add_connection("node1", "output", "node2")  # 3 args

# ✅ Fixed
workflow.add_connection("node1", "output", "node2", "input")  # 4 args
```

**Impact:** Critical - Connection won't be created

### CON002: Old 2-Parameter Syntax

**Description:** Using deprecated 2-parameter connection syntax.

**Example:**
```python
# ❌ Error (Old syntax)
workflow.add_connection("source_node", "target_node")

# ✅ Fixed (New 4-parameter syntax)
workflow.add_connection("source_node", "result", "target_node", "input")
```

**Impact:** Critical - Old syntax is not supported

### CON003: Non-Existent Source Node

**Description:** Connection references a source node that doesn't exist.

**Example:**
```python
# ❌ Error
workflow.add_node("ProcessorNode", "processor", {"operation": "clean"})
workflow.add_connection("reader", "data", "processor", "input")  # 'reader' doesn't exist

# ✅ Fixed
workflow.add_node("CSVReaderNode", "reader", {"file_path": "data.csv"})
workflow.add_node("ProcessorNode", "processor", {"operation": "clean"})
workflow.add_connection("reader", "data", "processor", "input")
```

**Impact:** Critical - Workflow execution will fail

### CON004: Non-Existent Target Node

**Description:** Connection references a target node that doesn't exist.

**Example:**
```python
# ❌ Error
workflow.add_node("ReaderNode", "reader", {"file": "data.csv"})
workflow.add_connection("reader", "data", "analyzer", "input")  # 'analyzer' doesn't exist

# ✅ Fixed
workflow.add_node("ReaderNode", "reader", {"file": "data.csv"})
workflow.add_node("AnalyzerNode", "analyzer", {"mode": "statistical"})
workflow.add_connection("reader", "data", "analyzer", "input")
```

**Impact:** Critical - Workflow execution will fail

### CON005: Circular Dependency

**Description:** Connections form a circular dependency loop.

**Example:**
```python
# ❌ Error - Circular dependency
workflow.add_connection("node_a", "output", "node_b", "input")
workflow.add_connection("node_b", "output", "node_c", "input")
workflow.add_connection("node_c", "output", "node_a", "input")  # Creates cycle

# ✅ Fixed - Acyclic graph
workflow.add_connection("node_a", "output", "node_b", "input")
workflow.add_connection("node_b", "output", "node_c", "input")
workflow.add_connection("node_b", "status", "monitor", "input")  # No cycle
```

**Impact:** Critical - Workflow execution will deadlock

### CON006: Suspicious Output Field

**Description:** Connection uses a suspicious output field name.

**Example:**
```python
# ❌ Warning
workflow.add_connection("reader", "nonexistent_output", "processor", "input")

# ✅ Fixed - Use actual output field
workflow.add_connection("reader", "data", "processor", "input")
```

**Impact:** Medium - Field might not exist on node

### CON007: Suspicious Input Field

**Description:** Connection uses a suspicious input field name.

**Example:**
```python
# ❌ Warning
workflow.add_connection("reader", "data", "processor", "nonexistent_input")

# ✅ Fixed - Use actual input field
workflow.add_connection("reader", "data", "processor", "input")
```

**Impact:** Medium - Field might not exist on node

## Gold Standard Errors (GOLD001-GOLD002)

### GOLD002: Incorrect Execution Pattern

**Description:** Using wrong pattern for workflow execution.

**Example:**
```python
# ❌ Error - Wrong pattern
workflow.execute(runtime)

# ✅ Fixed - Correct pattern
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

**Impact:** Critical - Code won't work

## Other Errors

### SYN001: Python Syntax Error

**Description:** Python syntax error in workflow code.

**Common Causes:**
- Missing commas in dictionaries
- Unmatched parentheses/brackets
- Incorrect indentation
- Missing quotes

**Impact:** Critical - Code won't parse

### VAL001: General Validation Error

**Description:** Unexpected error during validation.

**Common Causes:**
- Malformed AST
- Unexpected code structure
- Internal validator error

**Impact:** Varies

### NODE001: Unknown Node Type

**Description:** Referenced node type is not recognized.

**Example:**
```python
# ❌ Error
workflow.add_node("NonExistentNode", "node", {})

# ✅ Fixed - Use valid node type
workflow.add_node("PythonCodeNode", "node", {"code": "result = {}"})
```

**Impact:** Critical - Node can't be instantiated

## Cycle Errors (CYC001-CYC008)

### CYC001: Deprecated cycle=True Parameter

**Description:** Using deprecated `cycle=True` parameter in connections.

**Example:**
```python
# ❌ Error - Deprecated syntax
workflow.add_connection("node1", "output", "node2", "input", cycle=True)

# ✅ Fixed - Use CycleBuilder API
cycle_builder = workflow.create_cycle("my_cycle")
cycle_builder.connect("node1", "node2", mapping={"output": "input"})
cycle_builder.max_iterations(50)
cycle_builder.converge_when("quality > 0.95")
cycle_builder.build()
```

**Impact:** Critical - Deprecated API will be removed

### CYC002: Missing Cycle Configuration

**Description:** Cycle builder missing required configuration (max_iterations or converge_when).

**Example:**
```python
# ❌ Error - Missing configuration
cycle_builder = workflow.create_cycle("incomplete")
cycle_builder.connect("n1", "n2", mapping={"out": "in"})
cycle_builder.build()  # Missing max_iterations or converge_when

# ✅ Fixed - Add configuration
cycle_builder = workflow.create_cycle("complete")
cycle_builder.connect("n1", "n2", mapping={"out": "in"})
cycle_builder.max_iterations(50)  # Or converge_when()
cycle_builder.build()
```

**Impact:** Critical - Cycle will fail at runtime

### CYC003: Invalid Convergence Condition

**Description:** Convergence condition has invalid syntax.

**Example:**
```python
# ❌ Error - Invalid condition
cycle_builder.converge_when("invalid syntax here!")

# ✅ Fixed - Valid boolean expressions
cycle_builder.converge_when("quality > 0.95")
cycle_builder.converge_when("error < 0.01 and iterations < 100")
```

**Impact:** Critical - Convergence evaluation will fail

### CYC004: Empty Cycle

**Description:** Cycle has no connections defined.

**Example:**
```python
# ❌ Error - No connections
cycle_builder = workflow.create_cycle("empty")
cycle_builder.max_iterations(10)
cycle_builder.build()  # No connections added

# ✅ Fixed - Add connections
cycle_builder = workflow.create_cycle("complete")
cycle_builder.connect("n1", "n2", mapping={"out": "in"})
cycle_builder.max_iterations(10)
cycle_builder.build()
```

**Impact:** Critical - Cycle has no flow

### CYC005: Invalid Cycle Mapping

**Description:** Cycle connection mapping is not in dictionary format.

**Example:**
```python
# ❌ Error - Invalid mapping format
cycle_builder.connect("n1", "n2", mapping="invalid")

# ✅ Fixed - Dictionary mapping
cycle_builder.connect("n1", "n2", mapping={"output": "input"})
```

**Impact:** Critical - Connection mapping will fail

### CYC006: Excessive Iterations Warning

**Description:** Cycle has very high max_iterations value.

**Example:**
```python
# ⚠️ Warning - High iteration count
cycle_builder.max_iterations(10000)  # Consider using converge_when

# ✅ Better - Use convergence condition
cycle_builder.converge_when("quality > 0.95")
cycle_builder.max_iterations(100)  # Reasonable fallback
```

**Impact:** Warning - May impact performance

### CYC007: Invalid Timeout Value

**Description:** Cycle timeout value is invalid (negative or zero).

**Example:**
```python
# ❌ Error - Invalid timeout
cycle_builder.timeout(-1)    # Negative
cycle_builder.timeout(0)     # Zero
cycle_builder.timeout("5m")  # String

# ✅ Fixed - Positive number in seconds
cycle_builder.timeout(300)   # 5 minutes
```

**Impact:** Critical - Timeout configuration will fail

### CYC008: Non-Existent Node Reference

**Description:** Cycle references a node that doesn't exist in the workflow.

**Example:**
```python
# ❌ Error - Missing node
workflow.add_node("ProcessorNode", "processor", {})
cycle_builder.connect("processor", "missing_node", mapping={"out": "in"})

# ✅ Fixed - Use existing nodes
workflow.add_node("ProcessorNode", "processor", {})
workflow.add_node("EvaluatorNode", "evaluator", {})
cycle_builder.connect("processor", "evaluator", mapping={"out": "in"})
```

**Impact:** Critical - Cycle execution will fail

## Import Errors (IMP001-IMP008)

### IMP001: Missing Import Statement

**Description:** Code uses a class or function that hasn't been imported.

**Example:**
```python
# ❌ Error
workflow = WorkflowBuilder()  # WorkflowBuilder not imported
runtime = LocalRuntime()     # LocalRuntime not imported

# ✅ Fixed
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
runtime = LocalRuntime()
```

**Impact:** Critical - Code will fail with NameError

### IMP002: Unused Import

**Description:** Import statement is present but the imported item is never used.

**Example:**
```python
# ❌ Error
from kailash.runtime.parallel import ParallelRuntime  # Not used
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# ✅ Fixed
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
```

**Impact:** Low - Decreases performance and code clarity

### IMP003: Incorrect Import Path

**Description:** Import uses wrong module path for Kailash components.

**Example:**
```python
# ❌ Error
from kailash.workflow import WorkflowBuilder  # Wrong path

# ✅ Fixed
from kailash.workflow.builder import WorkflowBuilder
```

**Impact:** Critical - Import will fail

### IMP004: Relative Import

**Description:** Code uses relative imports instead of absolute imports.

**Example:**
```python
# ❌ Error
from ..workflow.builder import WorkflowBuilder
from .runtime.local import LocalRuntime

# ✅ Fixed
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
```

**Impact:** Medium - Can cause import issues in different contexts

### IMP006: Import Order Violation

**Description:** Imports are not ordered according to PEP 8 standards.

**Example:**
```python
# ❌ Error
from kailash.workflow.builder import WorkflowBuilder
import os  # Standard library should come first
from kailash.runtime.local import LocalRuntime
import sys  # Out of order

# ✅ Fixed
import os
import sys
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
```

**Impact:** Low - Affects code readability and consistency

### IMP008: Heavy Unused Import

**Description:** Heavy libraries (tensorflow, torch, etc.) are imported but not used.

**Example:**
```python
# ❌ Error
import tensorflow as tf  # Heavy import not used
import torch            # Heavy import not used
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# ✅ Fixed
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# ✅ Alternative - Lazy loading when needed
def process_data_with_tf(data):
    import tensorflow as tf  # Import only when needed
    return tf.process(data)
```

**Impact:** High - Significantly slows startup time

## Error Severity Levels

- **error**: Must be fixed before execution
- **warning**: Should be fixed but might work
- **info**: Suggestions for improvement

## Quick Error Lookup

| Code | Description | Severity |
|------|-------------|----------|
| PAR001 | Missing get_parameters() | error |
| PAR002 | Undeclared parameter usage | error |
| PAR003 | Missing type field | error |
| PAR004 | Missing required parameters | error |
| CON001 | Invalid connection args | error |
| CON002 | Old 2-param syntax | error |
| CON003 | Non-existent source | error |
| CON004 | Non-existent target | error |
| CON005 | Circular dependency | error |
| CON006 | Suspicious output field | error |
| CON007 | Suspicious input field | error |
| GOLD002 | Wrong execution pattern | error |
| SYN001 | Python syntax error | error |
| NODE001 | Unknown node type | error |
| CYC001 | Deprecated cycle=True parameter | error |
| CYC002 | Missing cycle configuration | error |
| CYC003 | Invalid convergence condition | error |
| CYC004 | Empty cycle | error |
| CYC005 | Invalid cycle mapping | error |
| CYC006 | Excessive iterations | warning |
| CYC007 | Invalid timeout value | error |
| CYC008 | Non-existent node reference | error |
| IMP001 | Missing import statement | error |
| IMP002 | Unused import | error |
| IMP003 | Incorrect import path | error |
| IMP004 | Relative import | error |
| IMP006 | Import order violation | warning |
| IMP008 | Heavy unused import | warning |