from kailash.runtime.local import LocalRuntime
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# Typical baseline implementation with common errors
workflow.add_node("DataLoaderNode", "load")  # Missing parameters
workflow.add_node("ProcessorNode", "process", {})

# Connect nodes (using old 2-parameter syntax)
workflow.add_connection("fetch_data", "process")
workflow.add_connection("process", "analyze")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
