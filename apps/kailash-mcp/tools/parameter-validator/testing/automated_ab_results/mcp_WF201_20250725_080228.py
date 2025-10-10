from kailash.runtime.local import LocalRuntime
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# MCP-enhanced implementation with proper parameters
workflow.add_node(
    "HTTPRequestNode",
    "fetch_data",
    {
        "url": "https://api.example.com/data",
        "method": "GET",
        "timeout": 30,
        "retry_count": 3,
    },
)

workflow.add_node(
    "PythonCodeNode",
    "process",
    {
        "code": """
def process_data(input_data):
    # Process financial data
    return {'processed': input_data, 'timestamp': datetime.now().isoformat()}
    
result = process_data(input_data)
""",
        "imports": ["from datetime import datetime"],
    },
)

workflow.add_node(
    "LLMAgentNode",
    "analyze",
    {
        "model": "gpt-4",
        "prompt": "Analyze this financial data and provide insights: {input}",
        "temperature": 0.7,
    },
)

# Connect nodes with proper 4-parameter syntax
workflow.add_connection("fetch_data", "response", "process", "input_data")
workflow.add_connection("process", "result", "analyze", "input")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
