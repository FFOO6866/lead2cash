# Quick Start Guide

> **From Zero to MCP Tool in 5 Minutes**

This guide gets you from installation to your first working MCP tool in under 5 minutes.

## Installation

```bash
# Install MCP Forge
pip install kailash-mcp

# Verify installation
mcp-forge --version
```

## Your First MCP Tool

Create a file called `my_first_tool.py`:

```python
from mcp_forge import MCPServer, tool

# Create server
server = MCPServer("my-tools")

# Add a tool with simple decorator
@server.tool
def greet_user(name: str, language: str = "en") -> dict:
    """Greet a user in their preferred language."""
    greetings = {
        "en": f"Hello, {name}!",
        "es": f"¡Hola, {name}!",
        "fr": f"Bonjour, {name}!",
        "de": f"Hallo, {name}!"
    }
    return {
        "message": greetings.get(language, greetings["en"]),
        "language": language
    }

# Start server (production-ready)
if __name__ == "__main__":
    server.start()
```

Run your MCP server:

```bash
python my_first_tool.py
```

**🎉 Congratulations!** You now have a production-ready MCP server running with:
- ✅ HTTP and WebSocket transports
- ✅ Tool discovery and schema validation
- ✅ Error handling and logging
- ✅ Health monitoring at `/health`
- ✅ Metrics at `/metrics`

## Test Your Tool

```python
# test_my_tool.py
from mcp_forge import MCPClient

# Connect to your server
client = MCPClient("http://localhost:8080")

# Discover available tools
tools = client.list_tools()
print("Available tools:", [tool.name for tool in tools])

# Call your tool
result = client.call_tool("greet_user", {
    "name": "Alice",
    "language": "es"
})
print("Result:", result)
# Output: {'message': '¡Hola, Alice!', 'language': 'es'}
```

## Add More Tools

```python
# Add more tools to your server
@server.tool
def calculate_fibonacci(n: int) -> dict:
    """Calculate the nth Fibonacci number."""
    if n <= 0:
        return {"error": "n must be positive"}
    elif n <= 2:
        return {"result": 1, "sequence": [1] * n}

    fib = [1, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])

    return {"result": fib[-1], "sequence": fib}

@server.resource("file://data/")
def data_resource():
    """Provide access to data files."""
    return {
        "type": "directory",
        "path": "/path/to/data",
        "files": ["dataset.csv", "config.json"]
    }
```

## Connect to AI Agents

Your MCP server is now ready for AI agents to discover and use:

```python
# Example: Use with LangChain
from langchain.agents import create_mcp_agent
from mcp_forge import MCPClient

client = MCPClient("http://localhost:8080")
agent = create_mcp_agent(mcp_client=client)

# Agent can now use your tools
response = agent.run("Greet John in French and calculate the 10th Fibonacci number")
```

## What's Next?

- **[Tool Development Guide](../user-guides/tool-development.md)** - Build sophisticated MCP tools
- **[Integration Patterns](../user-guides/integration-patterns.md)** - Connect to any system
- **[Production Deployment](../advanced/production-deployment.md)** - Scale to enterprise

---

**You've just created your first MCP tool!** The entire Model Context Protocol ecosystem is now available to your tools.
