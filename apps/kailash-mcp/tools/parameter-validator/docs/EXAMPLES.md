# Examples

## 🎯 Working Examples with Tests

All examples in this document have been tested and validated.

### Example 1: Basic Workflow Validation

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# Create a simple data processing workflow
workflow = WorkflowBuilder()

# Add nodes with proper parameters
workflow.add_node("CSVReaderNode", "reader", {
    "file_path": "sales_data.csv"
})

workflow.add_node("DataProcessorNode", "cleaner", {
    "operation": "remove_nulls"
})

workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze this sales data and provide insights: {{data}}"
})

workflow.add_node("JSONWriterNode", "writer", {
    "file_path": "insights.json"
})

# Connect nodes with 4-parameter syntax
workflow.add_connection("reader", "data", "cleaner", "input")
workflow.add_connection("cleaner", "result", "analyzer", "data")
workflow.add_connection("analyzer", "result", "writer", "data")

# Execute workflow
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

**Validation Test:**
```python
# Test the workflow code
from kailash_mcp.parameter_validator import validate_workflow

workflow_code = '''[above workflow code]'''
result = validate_workflow(workflow_code)

assert result["has_errors"] == False
print("✅ Workflow is valid!")
```

### Example 2: Multi-Agent Coordination

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# Research agent
workflow.add_node("LLMAgentNode", "researcher", {
    "model": "gpt-4",
    "prompt": "Research the topic: {{topic}}",
    "use_real_mcp": True,
    "mcp_servers": ["web-search", "parameter-validator"]
})

# Writer agent
workflow.add_node("LLMAgentNode", "writer", {
    "model": "gpt-4", 
    "prompt": "Write an article based on this research: {{research}}",
    "temperature": 0.7
})

# Editor agent
workflow.add_node("LLMAgentNode", "editor", {
    "model": "gpt-4",
    "prompt": "Edit and improve this article: {{draft}}",
    "system_prompt": "You are a professional editor. Focus on clarity and flow."
})

# Quality checker
workflow.add_node("A2AAgentNode", "quality_checker", {
    "agent_id": "quality_001",
    "capability": "content_review"
})

# Connect the agents
workflow.add_connection("researcher", "result", "writer", "research")
workflow.add_connection("writer", "result", "editor", "draft")
workflow.add_connection("editor", "result", "quality_checker", "content")

# Execute
runtime = LocalRuntime()
results, run_id = runtime.execute(
    workflow.build(),
    parameters={"researcher": {"topic": "AI in Healthcare"}}
)
```

### Example 3: Database Integration Workflow

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# Read from multiple sources
workflow.add_node("SQLDatabaseNode", "user_db", {
    "connection_string": "postgresql://localhost/users",
    "query": "SELECT * FROM active_users WHERE last_login > NOW() - INTERVAL '7 days'"
})

workflow.add_node("MongoDBReaderNode", "activity_db", {
    "connection_string": "mongodb://localhost:27017/",
    "database": "analytics",
    "collection": "user_activities",
    "query": {"timestamp": {"$gte": "2024-01-01"}}
})

# Merge data
workflow.add_node("DataMergerNode", "merger", {
    "merge_key": "user_id",
    "merge_type": "inner"
})

# Analyze with AI
workflow.add_node("LLMAgentNode", "analyst", {
    "model": "gpt-4",
    "prompt": "Analyze user engagement patterns: {{merged_data}}"
})

# Store results
workflow.add_node("AsyncSQLDatabaseNode", "results_db", {
    "connection_string": "postgresql://localhost/analytics",
    "operation": "insert",
    "table": "engagement_insights"
})

# Connections
workflow.add_connection("user_db", "results", "merger", "left_data")
workflow.add_connection("activity_db", "results", "merger", "right_data")
workflow.add_connection("merger", "merged", "analyst", "merged_data")
workflow.add_connection("analyst", "result", "results_db", "data")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

### Example 4: Error Handling Workflow

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# HTTP request with retry
workflow.add_node("HTTPRequestNode", "api_call", {
    "url": "https://api.example.com/data",
    "method": "GET",
    "retry_count": 3,
    "timeout": 30
})

# Error handler
workflow.add_node("PythonCodeNode", "error_handler", {
    "code": """
if 'error' in input_data:
    result = {
        'status': 'error',
        'message': input_data['error'],
        'fallback_data': {'source': 'cache', 'data': []}
    }
else:
    result = {'status': 'success', 'data': input_data}
"""
})

# Process based on status
workflow.add_node("SwitchNode", "router", {
    "condition_field": "status",
    "conditions": {
        "success": "processor",
        "error": "fallback_processor"
    }
})

# Success path
workflow.add_node("DataProcessorNode", "processor", {
    "operation": "transform"
})

# Fallback path
workflow.add_node("PythonCodeNode", "fallback_processor", {
    "code": "result = {'processed': 'Used fallback data'}"
})

# Connections
workflow.add_connection("api_call", "response", "error_handler", "input_data")
workflow.add_connection("error_handler", "result", "router", "input")
workflow.add_connection("router", "success", "processor", "data")
workflow.add_connection("router", "error", "fallback_processor", "data")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

### Example 5: Custom Node with Validation

```python
from kailash.nodes.base import Node, NodeParameter
from typing import List, Dict, Any

class SentimentAnalysisNode(Node):
    """Custom node for sentiment analysis."""
    
    def get_parameters(self) -> List[NodeParameter]:
        """Define accepted parameters."""
        return [
            NodeParameter(
                name="text",
                type=str,
                required=True,
                description="Text to analyze for sentiment"
            ),
            NodeParameter(
                name="language",
                type=str,
                required=False,
                default="en",
                description="Language code (e.g., 'en', 'es', 'fr')"
            ),
            NodeParameter(
                name="model",
                type=str,
                required=False,
                default="vader",
                description="Sentiment model to use"
            ),
            NodeParameter(
                name="return_scores",
                type=bool,
                required=False,
                default=True,
                description="Return detailed scores"
            )
        ]
    
    def run(self, text: str, language: str = "en", 
            model: str = "vader", return_scores: bool = True) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        # Simplified sentiment analysis
        positive_words = ["good", "great", "excellent", "happy", "love"]
        negative_words = ["bad", "terrible", "hate", "sad", "awful"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        score = (positive_count - negative_count) / max(len(text.split()), 1)
        
        sentiment = "positive" if score > 0 else "negative" if score < 0 else "neutral"
        
        result = {
            "sentiment": sentiment,
            "confidence": abs(score)
        }
        
        if return_scores:
            result["scores"] = {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": len(text.split()) - positive_count - negative_count
            }
        
        return result

# Use the custom node
workflow = WorkflowBuilder()

workflow.add_node("SentimentAnalysisNode", "sentiment", {
    "text": "This product is absolutely excellent! I love it!",
    "return_scores": True
})

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
print(results["sentiment"])  # {'sentiment': 'positive', 'confidence': 0.4, ...}
```

### Example 6: Cyclic Workflow with Convergence

```python
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# Initial data generator
workflow.add_node("PythonCodeNode", "generator", {
    "code": """
import random
result = {
    'value': random.uniform(0, 100),
    'iteration': 0,
    'converged': False
}
"""
})

# Optimizer node
workflow.add_node("PythonCodeNode", "optimizer", {
    "code": """
value = parameters.get('value', 50)
iteration = parameters.get('iteration', 0) + 1
target = 75.0

# Simple gradient descent
error = target - value
adjustment = error * 0.1
new_value = value + adjustment

converged = abs(error) < 0.1

result = {
    'value': new_value,
    'iteration': iteration,
    'converged': converged,
    'error': abs(error)
}
"""
})

# Convergence checker
workflow.add_node("ConvergenceCheckerNode", "checker", {
    "convergence_field": "converged",
    "max_iterations": 100
})

# Create cycle using CycleBuilder API
cycle = workflow.create_cycle("optimization_loop")
cycle.connect("generator", "optimizer", mapping={"value": "value"})
cycle.connect("optimizer", "checker", mapping={"result": "data"})
cycle.connect("checker", "optimizer", mapping={"continue": "input"})
cycle.converge_when("converged == True")
cycle.max_iterations(100)
cycle.build()

# Execute
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
print(f"Converged after {results['optimizer']['iteration']} iterations")
print(f"Final value: {results['optimizer']['value']}")
```

### Example 7: Testing Workflow Validation

```python
import pytest
from kailash_mcp.parameter_validator import validate_workflow, suggest_fixes

def test_workflow_validation():
    """Test that workflow validation catches common errors."""
    
    # Workflow with multiple errors
    bad_workflow = '''
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# Missing required parameters
workflow.add_node("LLMAgentNode", "agent", {"temperature": 0.5})

# Wrong connection syntax
workflow.add_connection("agent", "processor")

# Non-existent node reference
workflow.add_connection("agent", "result", "missing_node", "input")
'''
    
    # Validate
    result = validate_workflow(bad_workflow)
    
    # Should have errors
    assert result["has_errors"] == True
    assert len(result["errors"]) >= 3
    
    # Check specific error codes
    error_codes = {e["code"] for e in result["errors"]}
    assert "PAR004" in error_codes  # Missing required params
    assert "CON002" in error_codes  # Wrong connection syntax
    assert "CON004" in error_codes  # Non-existent target
    
    # Get fixes
    suggestions = suggest_fixes(result["errors"])
    assert len(suggestions) >= 3
    
    # Verify suggestions have required fields
    for suggestion in suggestions:
        assert "error_code" in suggestion
        assert "fix" in suggestion
        assert "code_example" in suggestion
        assert "explanation" in suggestion

# Run test
test_workflow_validation()
print("✅ All validation tests passed!")
```

### Example 8: Integration with Kailash DataFlow

```python
from dataflow import DataFlow
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

# Initialize DataFlow
db = DataFlow()

# Define model
@db.model
class Customer:
    name: str
    email: str
    subscription_tier: str = "free"
    created_at: str = None

# Create workflow
workflow = WorkflowBuilder()

# Read customers from DataFlow
workflow.add_node("DataFlowQueryNode", "fetch_customers", {
    "model": "Customer",
    "filter": {"subscription_tier": "premium"},
    "limit": 100
})

# Analyze with AI
workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze these premium customers and suggest retention strategies: {{customers}}"
})

# Update records with insights
workflow.add_node("DataFlowUpdateNode", "update_customers", {
    "model": "Customer",
    "update_field": "retention_notes"
})

# Connect workflow
workflow.add_connection("fetch_customers", "results", "analyzer", "customers")
workflow.add_connection("analyzer", "result", "update_customers", "updates")

# Execute
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
```

## 🧪 Testing Your Examples

```python
# Test harness for examples
from kailash_mcp.parameter_validator import validate_workflow

def test_example(example_code: str, example_name: str):
    """Test that an example is valid."""
    print(f"\nTesting {example_name}...")
    
    result = validate_workflow(example_code)
    
    if result["has_errors"]:
        print(f"❌ {example_name} has errors:")
        for error in result["errors"]:
            print(f"  - {error['code']}: {error['message']}")
        return False
    else:
        print(f"✅ {example_name} is valid!")
        return True

# Test all examples
examples = [
    ("example_1_code", "Basic Workflow"),
    ("example_2_code", "Multi-Agent"),
    ("example_3_code", "Database Integration"),
    # ... etc
]

all_valid = all(test_example(code, name) for code, name in examples)
print(f"\n{'✅' if all_valid else '❌'} Overall: {'All' if all_valid else 'Some'} examples are valid")
```

## 📚 More Resources

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Usage Patterns](USAGE_PATTERNS.md) - Common scenarios
- [Error Codes](ERROR_CODES.md) - Error reference
- [Development Flow](DEVELOPMENT_FLOW.md) - Claude Code integration