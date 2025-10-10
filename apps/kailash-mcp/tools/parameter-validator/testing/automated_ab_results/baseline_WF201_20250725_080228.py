from kailash.runtime.local import LocalRuntime
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# Typical baseline implementation with common errors
workflow.add_node(
    "HTTPRequestNode", "fetch_data", {"url": "https://api.example.com/data"}
)
workflow.add_node("PythonCodeNode", "process", {"code": "result = input_data"})
workflow.add_node(
    "LLMAgentNode", "analyze", {"model": "gpt-4"}
)  # Missing prompt parameter

# Connect nodes (using old 2-parameter syntax)
workflow.add_connection("fetch_data", "process")
workflow.add_connection("process", "analyze")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
