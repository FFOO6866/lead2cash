# Installation Guide

## 📋 Prerequisites

- Python 3.8+
- Kailash SDK installed
- (Optional) Claude Desktop for MCP integration

## 🔧 Installation Methods

### Method 1: With Kailash SDK (Recommended)

```bash
# Install Kailash with MCP tools
pip install kailash[mcp]

# Or install all features
pip install kailash[all]
```

### Method 2: Standalone Installation

```bash
# Clone the repository
git clone https://github.com/your-org/kailash-python-sdk.git
cd kailash-python-sdk/apps/kailash-mcp/tools/parameter-validator

# Install in development mode
pip install -e .

# Or install directly
pip install .
```

### Method 3: From PyPI (When Published)

```bash
pip install kailash-parameter-validator
```

## 🖥️ Claude Desktop Integration

### 1. Locate Claude Desktop Config

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

### 2. Add MCP Server Configuration

Edit the config file and add:

```json
{
  "mcpServers": {
    "parameter-validator": {
      "command": "python",
      "args": [
        "-m",
        "apps.kailash-mcp.tools.parameter-validator.src.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/kailash-python-sdk"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

The parameter validator will now be available in Claude Desktop.

## 🐳 Docker Installation

```dockerfile
FROM python:3.9-slim

# Install Kailash SDK and parameter validator
RUN pip install kailash[mcp]

# Copy validation server
COPY apps/kailash-mcp/tools/parameter-validator /app/parameter-validator

# Set working directory
WORKDIR /app

# Run MCP server
CMD ["python", "-m", "parameter-validator.src.server"]
```

Build and run:

```bash
docker build -t kailash-parameter-validator .
docker run -it kailash-parameter-validator
```

## 🧪 Verify Installation

### Test Basic Import

```python
# Test import
from kailash_mcp.parameter_validator import validate_workflow
print("✅ Import successful")

# Test validation
result = validate_workflow("workflow = WorkflowBuilder()")
print(f"✅ Validation working: {result['has_errors']}")
```

### Test MCP Server

```bash
# Start server manually
python -m apps.kailash-mcp.tools.parameter-validator.src.server

# In another terminal, test with MCP client
python -c "
from kailash.mcp_server import MCPClient
client = MCPClient('parameter-validator')
tools = client.list_tools()
print(f'Available tools: {len(tools)}')
"
```

### Test Claude Desktop Integration

1. Open Claude Desktop
2. Type: "List available MCP tools"
3. You should see parameter validation tools listed

## 🔍 Troubleshooting

### Import Errors

```bash
# Ensure PYTHONPATH includes SDK root
export PYTHONPATH=/path/to/kailash-python-sdk:$PYTHONPATH
```

### MCP Server Not Found

```bash
# Check if server module exists
python -c "import apps.kailash-mcp.tools.parameter-validator.src.server"

# If error, ensure proper installation
cd /path/to/kailash-python-sdk
pip install -e .
```

### Claude Desktop Not Detecting Tool

1. Check config file syntax (valid JSON)
2. Ensure absolute paths in config
3. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%LOCALAPPDATA%\Claude\Logs\`

### Permission Errors

```bash
# Ensure execute permissions
chmod +x apps/kailash-mcp/tools/parameter-validator/src/server.py
```

## 🌐 Environment Variables

Optional configuration via environment variables:

```bash
# Set validation strictness
export KAILASH_VALIDATION_LEVEL=strict  # strict, normal, lenient

# Enable debug logging
export KAILASH_MCP_DEBUG=true

# Set custom timeout
export KAILASH_MCP_TIMEOUT=30  # seconds
```

## 📦 Dependencies

The tool requires:

```
kailash>=0.8.0
asyncio
ast
typing
dataclasses
```

All dependencies are automatically installed with the package.

## 🚀 Next Steps

- Read the [Usage Patterns](USAGE_PATTERNS.md) guide
- Explore [API Reference](API_REFERENCE.md)
- Try the [Examples](EXAMPLES.md)