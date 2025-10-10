# MCP Forge - Comprehensive Test Plan

**Date**: 2025-01-14
**Test Strategy**: 3-Tier Testing (Unit, Integration, E2E)
**Compliance**: sdk-users/testing/test-organization-policy.md

## Test Coverage Strategy

This test plan covers ALL components and user flows defined in TODO-114 with comprehensive test coverage across all three tiers.

### **Testing Philosophy**
- **Tier 1 (Unit)**: Fast, isolated, mocking allowed, <1s per test
- **Tier 2 (Integration)**: Real Docker services, NO MOCKING, <30s per test
- **Tier 3 (E2E)**: Complete workflows, real infrastructure, any duration

## Tier 1: Unit Tests (`tests/unit/`)

### **Core Components**

#### 1. MCPServer Unit Tests (`tests/unit/mcp_forge/test_server.py`)
- [ ] Server initialization with defaults
- [ ] Server initialization with custom config
- [ ] Tool registration and validation
- [ ] Invalid tool registration error handling
- [ ] Server start/stop lifecycle (mocked)
- [ ] Configuration validation
- [ ] Error handling and proper responses
- [ ] Multiple transport configuration

#### 2. MCPClient Unit Tests (`tests/unit/mcp_forge/test_client.py`)
- [ ] Client initialization with server URL
- [ ] Connection pooling configuration
- [ ] Response caching logic
- [ ] Circuit breaker behavior (mocked)
- [ ] Retry logic with exponential backoff
- [ ] Tool listing and schema retrieval
- [ ] Tool execution with mocked responses

#### 3. Tool Framework Unit Tests (`tests/unit/mcp_forge/test_tools.py`)
- [ ] @tool decorator basic functionality
- [ ] Schema generation from type hints
- [ ] Parameter validation logic
- [ ] Complex type support (List, Dict, Optional)
- [ ] Default parameter handling
- [ ] Tool execution context
- [ ] Error handling in tool execution

#### 4. KailashBridge Unit Tests (`tests/unit/mcp_forge/test_bridge.py`)
- [ ] Node to MCP tool conversion (mocked)
- [ ] Parameter mapping validation
- [ ] Workflow to MCP server conversion
- [ ] Error handling for unsupported nodes
- [ ] Schema generation for node parameters

#### 5. Configuration Unit Tests (`tests/unit/mcp_forge/test_config.py`)
- [ ] Default configuration values
- [ ] Environment variable override
- [ ] Configuration validation
- [ ] Progressive configuration (zero → simple → advanced)

#### 6. Compliance Validator Unit Tests (`tests/unit/mcp_forge/test_compliance.py`)
- [ ] MCP protocol validation logic
- [ ] Test case loading and execution
- [ ] Compliance report generation
- [ ] Badge generation logic

### **Utilities & Support**

#### 7. Registry Unit Tests (`tests/unit/mcp_forge/test_registry.py`)
- [ ] Tool registration and storage
- [ ] Search and discovery logic (mocked)
- [ ] Version management
- [ ] Rating and review handling

#### 8. AI Framework Bridges Unit Tests (`tests/unit/mcp_forge/test_ai_bridges.py`)
- [ ] LangChain integration patterns (mocked)
- [ ] AutoGen integration patterns (mocked)
- [ ] Framework adapter logic
- [ ] Error handling for unsupported frameworks

**Unit Test Totals**: ~80 tests across 8 files

## Tier 2: Integration Tests (`tests/integration/`)

### **Real Service Integration** (NO MOCKING)

#### 1. MCPServer Integration (`tests/integration/mcp_forge/test_server_integration.py`)
**Requirements**: Docker MCP server container
- [ ] Server startup with real HTTP/WebSocket endpoints
- [ ] Tool registration and discovery via real MCP protocol
- [ ] Real tool execution through MCP client
- [ ] Multiple transport communication (HTTP + WebSocket)
- [ ] Authentication and authorization with real tokens
- [ ] Performance under concurrent connections

#### 2. MCPClient Integration (`tests/integration/mcp_forge/test_client_integration.py`)
**Requirements**: Docker MCP server container
- [ ] Connection to real MCP server
- [ ] Real tool discovery and schema retrieval
- [ ] Tool execution with real parameters and responses
- [ ] Connection pooling with real connections
- [ ] Circuit breaker with real server failures
- [ ] Retry logic with real timeout scenarios

#### 3. Kailash Bridge Integration (`tests/integration/mcp_forge/test_bridge_integration.py`)
**Requirements**: Docker PostgreSQL (for node testing)
- [ ] Real CSVReaderNode to MCP tool conversion
- [ ] Real SQLDatabaseNode to MCP tool conversion
- [ ] Real HTTPRequestNode to MCP tool conversion
- [ ] Parameter mapping with real data flows
- [ ] Error propagation from real node failures
- [ ] Workflow execution through MCP interface

#### 4. Compliance Testing (`tests/integration/mcp_forge/test_compliance_integration.py`)
**Requirements**: Docker MCP server containers
- [ ] Full MCP protocol compliance validation
- [ ] Test against reference MCP server implementation
- [ ] Multi-transport compliance testing
- [ ] Error handling compliance verification
- [ ] Performance compliance benchmarks

#### 5. AI Framework Integration (`tests/integration/mcp_forge/test_ai_integration.py`)
**Requirements**: Docker MCP server, Ollama
- [ ] Real LangChain agent using MCP tools
- [ ] Real AutoGen agent using MCP tools
- [ ] Tool execution in real agent workflows
- [ ] Error handling in real agent scenarios
- [ ] Performance with real LLM calls

#### 6. Registry Integration (`tests/integration/mcp_forge/test_registry_integration.py`)
**Requirements**: Docker PostgreSQL, Redis
- [ ] Tool registration in real database
- [ ] Search and discovery with real data
- [ ] Caching with real Redis
- [ ] Version management with real storage
- [ ] Community features with real user data

**Integration Test Totals**: ~60 tests across 6 files

## Tier 3: E2E Tests (`tests/e2e/`)

### **Complete User Workflows** (NO MOCKING)

#### 1. Developer Journey E2E (`tests/e2e/test_developer_journey.py`)
**Requirements**: All Docker services
**Workflow**: Complete 5-minute developer success story
- [ ] Install MCP Forge
- [ ] Create first MCP tool with @tool decorator
- [ ] Start MCP server
- [ ] Connect MCP client
- [ ] Execute tool via MCP protocol
- [ ] Register tool in ecosystem registry
- [ ] Discover and use tool from another client

#### 2. Kailash Integration E2E (`tests/e2e/test_kailash_integration.py`)
**Requirements**: Docker PostgreSQL, Redis, MCP server
**Workflow**: Existing Kailash workflow → MCP tools
- [ ] Convert existing Kailash workflow to MCP server
- [ ] AI agent discovers and uses converted tools
- [ ] Data flows correctly through MCP protocol
- [ ] Error handling preserves workflow semantics
- [ ] Performance meets SLA requirements

#### 3. AI Agent Workflow E2E (`tests/e2e/test_ai_agent_workflow.py`)
**Requirements**: Docker MCP server, Ollama, Redis
**Workflow**: AI agent using multiple MCP tools
- [ ] Agent discovers available MCP tools
- [ ] Agent executes complex multi-tool workflow
- [ ] Tool composition and chaining works correctly
- [ ] Error recovery and fallback mechanisms
- [ ] Performance under real LLM execution

#### 4. Enterprise Deployment E2E (`tests/e2e/test_enterprise_deployment.py`)
**Requirements**: All Docker services, auth systems
**Workflow**: Production deployment scenario
- [ ] Deploy MCP Forge with enterprise configuration
- [ ] Configure authentication and authorization
- [ ] Set up monitoring and health checks
- [ ] Load testing with concurrent users
- [ ] Failover and recovery scenarios
- [ ] Security compliance validation

#### 5. Multi-Framework E2E (`tests/e2e/test_multi_framework.py`)
**Requirements**: Docker MCP server, Ollama
**Workflow**: MCP tools used by multiple AI frameworks
- [ ] Same MCP tools used by LangChain agent
- [ ] Same MCP tools used by AutoGen agent
- [ ] Cross-framework compatibility validation
- [ ] Performance comparison across frameworks
- [ ] Error handling consistency

#### 6. Ecosystem Growth E2E (`tests/e2e/test_ecosystem_growth.py`)
**Requirements**: Docker PostgreSQL, Redis, MCP servers
**Workflow**: Community ecosystem features
- [ ] Developer publishes tool to registry
- [ ] Other developers discover and rate tool
- [ ] Tool versioning and update scenarios
- [ ] Community feedback and improvement cycles
- [ ] Quality assurance pipeline execution

**E2E Test Totals**: ~45 tests across 6 files

## Test Infrastructure Requirements

### **Docker Services Required**

#### For Integration Tests:
```yaml
# tests/integration/docker-compose.yml
services:
  mcp_reference_server:
    image: mcp-reference-server:latest
    ports: ["8080:8080"]

  postgres:
    image: postgres:15
    ports: ["5434:5432"]
    environment:
      POSTGRES_DB: mcp_forge_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
```

#### For E2E Tests:
```yaml
# tests/e2e/docker-compose.yml
services:
  mcp_reference_server:
    image: mcp-reference-server:latest
  postgres:
    image: postgres:15
  redis:
    image: redis:7
  ollama:
    image: ollama/ollama:latest
```

### **Real MCP Server Implementation**

#### Custom Test MCP Server (`tests/utils/test_mcp_server.py`)
```python
class TestMCPServer:
    """Real MCP server for testing MCP Forge against."""

    def __init__(self):
        self.tools = {
            "echo": self.echo_tool,
            "math": self.math_tool,
            "error": self.error_tool
        }

    async def echo_tool(self, message: str) -> dict:
        return {"echo": message}

    async def math_tool(self, a: int, b: int, op: str) -> dict:
        ops = {"add": a + b, "sub": a - b, "mul": a * b}
        return {"result": ops.get(op, 0)}

    async def error_tool(self, error_type: str) -> dict:
        if error_type == "timeout":
            await asyncio.sleep(60)  # Force timeout
        elif error_type == "exception":
            raise ValueError("Test error")
        return {"error": "Unknown error type"}
```

## Test Data & Fixtures

### **Shared Test Fixtures** (`tests/fixtures/`)

#### MCP Test Data (`tests/fixtures/mcp_data.py`)
```python
# Standard test tools for consistent testing
TEST_TOOLS = {
    "simple_tool": {
        "name": "simple_tool",
        "description": "A simple test tool",
        "parameters": {"message": {"type": "string", "required": True}}
    },
    "complex_tool": {
        "name": "complex_tool",
        "description": "A complex test tool",
        "parameters": {
            "items": {"type": "array", "items": {"type": "string"}},
            "config": {"type": "object", "required": False}
        }
    }
}

# Standard test workflows for Kailash bridge testing
TEST_WORKFLOWS = {
    "csv_processing": WorkflowBuilder()
        .add_node("CSVReaderNode", "reader", {"file_path": "test.csv"})
        .add_node("DataTransformerNode", "transformer", {"operation": "filter"}),

    "api_integration": WorkflowBuilder()
        .add_node("HTTPRequestNode", "api", {"url": "https://api.test.com"})
        .add_node("JSONReaderNode", "parser", {"json_path": "$.data"})
}
```

#### Docker Configuration (`tests/fixtures/docker_fixtures.py`)
```python
@pytest.fixture(scope="session")
async def mcp_test_server():
    """Start real MCP server for testing."""
    container = await start_mcp_server_container()
    yield container.url
    await stop_mcp_server_container(container)

@pytest.fixture(scope="session")
async def postgres_db():
    """Real PostgreSQL for integration tests."""
    db_url = await start_postgres_container()
    yield db_url
    await cleanup_postgres_container()
```

## Test Execution Strategy

### **Development Workflow**
```bash
# Phase 1: Unit tests (fast feedback)
pytest tests/unit/ -v --tb=short -x

# Phase 2: Integration tests (before commit)
./test-env up
pytest tests/integration/ -v --tb=short --maxfail=5

# Phase 3: E2E tests (before release)
pytest tests/e2e/ -v --tb=short --maxfail=3
```

### **CI/CD Pipeline**
```bash
# PR Validation (5-10 minutes)
pytest tests/unit/ -m "not slow"

# Nightly Build (30-45 minutes)
pytest tests/integration/ tests/e2e/ --cov=mcp_forge

# Release Validation (60+ minutes)
pytest --cov=mcp_forge --benchmark-only
```

## Success Criteria

### **Coverage Requirements**
- **Unit Tests**: >95% code coverage
- **Integration Tests**: 100% API endpoint coverage
- **E2E Tests**: 100% user workflow coverage

### **Performance Requirements**
- **Unit Tests**: <1 second per test
- **Integration Tests**: <30 seconds per test
- **E2E Tests**: Complete in <10 minutes per workflow

### **Quality Requirements**
- **MCP Compliance**: 100% protocol specification adherence
- **Real Service Testing**: NO MOCKING in Tier 2/3 tests
- **Error Coverage**: All error scenarios tested
- **Documentation**: All test examples must work

## Test File Creation Priority

### **Phase 1: Foundation Tests** (Week 1)
1. `tests/unit/mcp_forge/test_server.py` - Core server logic
2. `tests/unit/mcp_forge/test_tools.py` - Tool framework
3. `tests/unit/mcp_forge/test_config.py` - Configuration
4. `tests/utils/test_mcp_server.py` - Real MCP server for testing

### **Phase 2: Integration Tests** (Week 2)
5. `tests/integration/mcp_forge/test_server_integration.py` - Real server
6. `tests/integration/mcp_forge/test_client_integration.py` - Real client
7. `tests/integration/mcp_forge/test_compliance_integration.py` - Protocol compliance

### **Phase 3: Advanced Tests** (Week 3+)
8. `tests/integration/mcp_forge/test_bridge_integration.py` - Kailash integration
9. `tests/e2e/test_developer_journey.py` - Complete workflows
10. `tests/e2e/test_ai_agent_workflow.py` - AI agent scenarios

---

**This test plan ensures comprehensive coverage of MCP Forge functionality while following the mandatory 3-tier testing strategy and NO MOCKING policy for integration/E2E tests.**
