# MCP Forge - Test Suite

This directory contains the comprehensive test suite for MCP Forge, following the 3-tier testing strategy mandated by the Kailash SDK.

## 🧪 Test Structure

```
tests/
├── unit/             # Tier 1: Fast, isolated, mocking allowed
│   └── mcp_forge/
│       ├── test_server.py       # Core server logic tests
│       ├── test_tools.py        # Tool framework tests
│       ├── test_config.py       # Configuration tests
│       ├── test_client.py       # Client logic tests
│       └── test_bridge.py       # Kailash bridge tests
├── integration/      # Tier 2: Real Docker services, NO MOCKING
│   └── mcp_forge/
│       ├── test_server_integration.py     # Real server tests
│       ├── test_client_integration.py     # Real client tests
│       ├── test_bridge_integration.py     # Real bridge tests
│       └── test_compliance_integration.py # Protocol compliance
├── e2e/             # Tier 3: Complete workflows, real infrastructure
│   ├── test_developer_journey.py         # 5-minute developer success
│   ├── test_kailash_integration.py       # Workflow → MCP tools
│   ├── test_ai_agent_workflow.py         # AI agent scenarios
│   ├── test_enterprise_deployment.py     # Production scenarios
│   ├── test_multi_framework.py           # Cross-framework testing
│   └── test_ecosystem_growth.py          # Community features
├── utils/           # Test utilities and infrastructure
│   └── test_mcp_server.py                # Real MCP server for testing
├── fixtures/        # Test data and configuration
│   └── data/
│       ├── sample_config.json            # Sample configurations
│       ├── sample_workflow.json          # Sample workflows
│       └── sample.csv                    # Sample data files
├── conftest.py      # Shared fixtures and configuration
├── pytest.ini      # Pytest configuration
└── README.md        # This file
```

## 🎯 Testing Strategy

### Tier 1: Unit Tests
- **Purpose**: Fast feedback during development
- **Requirements**: <1s per test, isolated components
- **Mocking**: ✅ Allowed and encouraged
- **Dependencies**: None (no Docker required)
- **Coverage**: >95% code coverage target

**Run Command:**
```bash
pytest tests/unit/ -v
```

### Tier 2: Integration Tests
- **Purpose**: Test component interactions with real services
- **Requirements**: <30s per test, real Docker services
- **Mocking**: ❌ **NO MOCKING** - Real PostgreSQL, Redis, MCP servers
- **Dependencies**: Docker services via `tests/utils/docker_config.py`
- **Coverage**: 100% API endpoint coverage

**Run Command:**
```bash
# Start test environment first
./test-env up
pytest tests/integration/ -v
```

### Tier 3: E2E Tests
- **Purpose**: Complete user workflows and scenarios
- **Requirements**: <10 minutes per workflow, real infrastructure
- **Mocking**: ❌ **NO MOCKING** - Complete real scenarios
- **Dependencies**: All Docker services including Ollama
- **Coverage**: 100% user workflow coverage

**Run Command:**
```bash
# Ensure all services are running
./test-env up
pytest tests/e2e/ -v
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# From project root
pip install -e ".[test]"
```

### 2. Start Test Environment
```bash
# Start Docker services
./test-env setup  # One-time setup
./test-env up     # Start services
```

### 3. Run Tests by Tier
```bash
# Fast unit tests (no Docker needed)
pytest tests/unit/ -v --tb=short

# Integration tests (requires Docker)
pytest tests/integration/ -v --tb=short

# E2E tests (requires all services)
pytest tests/e2e/ -v --tb=short
```

### 4. Run Specific Test Categories
```bash
# Run all MCP server tests
pytest -k "mcp_server" -v

# Run configuration tests only
pytest tests/unit/mcp_forge/test_config.py -v

# Run real MCP protocol tests
pytest -m "requires_mcp_server" -v
```

## 📊 Test Coverage Targets

| Test Tier | Coverage Target | Measurement |
|-----------|----------------|-------------|
| **Unit** | >95% code coverage | Lines covered by isolated tests |
| **Integration** | 100% API coverage | All endpoints tested with real services |
| **E2E** | 100% workflow coverage | All user journeys tested end-to-end |

## 🔧 Test Infrastructure

### Real MCP Server (`tests/utils/test_mcp_server.py`)
A complete, protocol-compliant MCP server for testing:
- WebSocket and HTTP transports
- JSON-RPC 2.0 messaging
- Tool execution with real handlers
- Resource discovery
- Error scenarios for testing

### Docker Integration
Uses the main SDK's Docker infrastructure:
- PostgreSQL: `localhost:5434`
- Redis: `localhost:6380`
- Ollama: `localhost:11435`
- Configuration: `tests/utils/docker_config.py`

### Shared Fixtures (`conftest.py`)
- MCP server management
- Docker service fixtures
- Test data helpers
- Performance timing utilities

## 🧪 Test Examples

### Unit Test Example
```python
def test_tool_registration_valid(mock_tools):
    """Test valid tool registration."""
    tools_registry = {}
    for tool_name, tool_schema in mock_tools.items():
        tools_registry[tool_name] = tool_schema

    assert "echo" in tools_registry
    assert tools_registry["echo"]["name"] == "echo"
```

### Integration Test Example
```python
@pytest.mark.integration
@pytest.mark.requires_mcp_server
async def test_real_mcp_communication(mcp_server):
    """Test real MCP server communication."""
    server_info = mcp_server.get_server_info()
    assert server_info["running"] is True

    # Test real MCP message handling
    message = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": "test-1"
    }
    response = await mcp_server.handle_mcp_message(message)
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
```

### E2E Test Example
```python
@pytest.mark.e2e
@pytest.mark.requires_docker
async def test_developer_journey_complete(full_test_environment, mcp_server):
    """Test complete 5-minute developer success story."""
    # 1. Create MCP tool with @tool decorator
    # 2. Start MCP server
    # 3. Connect MCP client
    # 4. Execute tool via MCP protocol
    # 5. Verify complete workflow
    pass
```

## 🔍 Test Organization

### File Naming Convention
- Unit tests: `test_*.py` in `tests/unit/`
- Integration tests: `test_*_integration.py` in `tests/integration/`
- E2E tests: `test_*.py` in `tests/e2e/`

### Test Class Organization
- `TestClassName` for grouped functionality
- `test_method_name` for individual test cases
- Descriptive names describing what is being tested

### Markers and Categories
- `@pytest.mark.unit` - Unit tests (auto-applied)
- `@pytest.mark.integration` - Integration tests (auto-applied)
- `@pytest.mark.e2e` - E2E tests (auto-applied)
- `@pytest.mark.requires_docker` - Needs Docker services
- `@pytest.mark.requires_mcp_server` - Needs real MCP server
- `@pytest.mark.slow` - Tests taking >10 seconds

## 🚨 Testing Rules

### NEVER in Integration/E2E Tests
- ❌ Mock external services (use real Docker services)
- ❌ Patch database connections (use real PostgreSQL)
- ❌ Mock MCP protocol (use real MCP servers)
- ❌ Simulate network calls (use real HTTP/WebSocket)

### ALWAYS in All Tests
- ✅ Use `node.execute()` not `node.run()`
- ✅ Follow SDK testing patterns
- ✅ Clean up resources in fixtures
- ✅ Use descriptive test names
- ✅ Document test purpose and expectations

## 📈 Performance Guidelines

### Unit Tests
- **Target**: <1 second per test
- **Total**: <2 minutes for full unit test suite
- **Parallelization**: Safe (no external dependencies)

### Integration Tests
- **Target**: <30 seconds per test
- **Total**: <10 minutes for full integration suite
- **Parallelization**: Limited (shared Docker services)

### E2E Tests
- **Target**: <10 minutes per workflow
- **Total**: <60 minutes for full E2E suite
- **Parallelization**: Sequential (complex scenarios)

## 🔧 Debugging Tests

### View Test Output
```bash
# Verbose output with full tracebacks
pytest tests/unit/ -v --tb=long

# Show local variables in failures
pytest tests/integration/ -v --showlocals

# Stop on first failure
pytest tests/e2e/ -x
```

### Debug Specific Issues
```bash
# Debug MCP server communication
pytest tests/integration/ -k "mcp_server" -v -s

# Debug configuration loading
pytest tests/unit/mcp_forge/test_config.py::TestConfigurationDefaults -v

# Debug with pdb
pytest tests/unit/ --pdb
```

### Check Test Dependencies
```bash
# Verify Docker services
./test-env status

# Check specific service health
docker logs kailash_sdk_test_postgres
docker logs kailash_sdk_test_redis
```

## 📚 References

- **Main SDK Testing**: `tests/CLAUDE.md` - Core testing infrastructure
- **Docker Configuration**: `tests/utils/docker_config.py` - Service setup
- **Test Plan**: `TEST_PLAN.md` - Comprehensive test strategy
- **SDK Testing Docs**: `sdk-users/testing/` - Full testing guides

---

**Test Philosophy**: Test-driven development with real services, comprehensive coverage, and production-quality validation.
