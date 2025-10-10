# New Project Template

This is a template for creating new projects using the Kailash SDK with a clean, scalable architecture.

## Quick Start

```bash
# Copy template to create new app
cp -r src/new_project src/my_new_app
cd src/my_new_app

# Customize for your app
# 1. Edit this README.md
# 2. Update setup.py
# 3. Modify config.py
# 4. Start development
```

## Project Structure

```
new_project/
├── core/                      # Core business logic
│   ├── gateway.py            # Main orchestrator
│   ├── auth.py               # Authentication logic
│   ├── session.py            # Session management
│   ├── models.py             # Data models
│   └── services.py           # Business services
│
├── services/                  # Service layer
│   ├── rag/                  # RAG-related services
│   │   ├── manager.py        # RAG manager
│   │   └── filters.py        # Role-based filters
│   ├── sharepoint/           # SharePoint integration
│   │   └── reader.py         # Document reader
│   └── mcp/                  # MCP services
│       └── servers/          # MCP server implementations
│           └── rag_tools.py  # RAG MCP tools
│
├── api/                      # API endpoints
│   ├── routers/             # FastAPI routers
│   └── middleware/          # API middleware
│
├── nodes/                    # Custom Kailash nodes
├── workflows/                # Workflow definitions
├── utils/                    # Utilities
├── tests/                    # All tests
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                     # Project documentation
│   ├── architecture/
│   ├── user_flows/
│   └── integration/
│
├── adr/                      # Architecture Decision Records
├── todos/                    # Task tracking
├── mistakes/                 # Lessons learned
└── instructions/             # Implementation guides
```

## Architecture Overview

This template follows a clean architecture pattern with clear separation of concerns:

1. **Core Layer** - Central business logic and orchestration
   - Gateway: Main orchestrator using kailash_sdk.gateway
   - Auth: Authentication with AccessControlManager
   - Session: Session management with security

2. **Services Layer** - Domain-specific services
   - RAG: Document indexing and retrieval with role-based filtering
   - SharePoint: Enterprise document integration
   - MCP: Model Context Protocol tools and servers

3. **API Layer** - External interfaces
   - FastAPI routers organized by domain
   - Middleware for cross-cutting concerns
   - OpenAPI documentation

4. **Infrastructure** - Supporting components
   - Custom nodes extending Kailash SDK
   - Workflows using WorkflowBuilder
   - Comprehensive test coverage

## Getting Started

### 1. Setup
```bash
# Copy template to create new project
cp -r src/new_project src/my_project
cd src/my_project

# Install in development mode
pip install -e .

# Initialize project structure
python -m my_project.setup
```

### 2. Implementation Guidelines

Each module contains instructional comments at the top explaining:
- Purpose and responsibilities
- Kailash SDK components to use
- Implementation patterns to follow
- Best practices and considerations

**Key Principles:**
- Use 100% Kailash SDK components
- Consult sdk-users/ for patterns and solutions
- No custom orchestration - use provided middleware
- Test extensively with real components (no mocks)

### 3. Development Workflow
1. Review instructions in target module
2. Check sdk-users/ for similar implementations
3. Implement using Kailash SDK components
4. Write tests (unit, integration, e2e)
5. Document decisions in adr/

### 4. Testing Strategy
```bash
# Run all tests
pytest tests/

# Test categories
pytest tests/unit/         # Component tests
pytest tests/integration/  # Service integration
pytest tests/e2e/          # Full workflow tests

# With coverage
pytest tests/ --cov=my_project
```

## App Metadata

Update this section for your app:

- **App Name**: my_new_app (CHANGE THIS)
- **Purpose**: What this app does (CHANGE THIS)
- **Owner**: Your name/team (CHANGE THIS)
- **Created**: YYYY-MM-DD (CHANGE THIS)
- **Status**: Development

## Next Steps

1. **Rename**: Change all references from "new_project" to your app name
2. **Customize**: Update setup.py with your app details
3. **Develop**: Start building your core models and workflows
4. **Test**: Write tests as you develop
5. **Document**: Keep your documentation updated

---

*Remember: This app is isolated - you can work on it without conflicts with other teams working on other apps!*