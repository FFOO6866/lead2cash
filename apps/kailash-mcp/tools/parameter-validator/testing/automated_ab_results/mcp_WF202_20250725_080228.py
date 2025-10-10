from kailash.runtime.local import LocalRuntime
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# MCP-enhanced implementation with proper parameters
workflow.add_node(
    "JSONReaderNode",
    "load_data",
    {"file_path": "data/input.json", "schema_validation": True},
)

workflow.add_node(
    "DataTransformerNode",
    "process",
    {"transformation": "normalize", "parameters": {"method": "minmax"}},
)

# Connect nodes with proper 4-parameter syntax
workflow.add_connection("fetch_data", "response", "process", "input_data")
workflow.add_connection("process", "result", "analyze", "input")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
