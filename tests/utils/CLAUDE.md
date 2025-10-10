# Test Infrastructure Setup

## Quick Start

```bash
# Initial setup (checks ports, starts services, creates .docker-ports.lock)
python tests/utils/setup_local_docker.py

# Or use the wrapper script
./tests/utils/test-env setup
```

## Port Allocation

Ports are dynamically allocated per project to prevent conflicts:
- Base port = 5000 + (hash(project_name) % 1000) * 10
- PostgreSQL: base_port + 0
- Redis: base_port + 1
- Ollama: base_port + 2
- MySQL: base_port + 3
- MongoDB: base_port + 4

Your ports are locked in `tests/.docker-ports.lock` after first setup.

## Commands

```bash
# Check ports before setup
python tests/utils/setup_local_docker.py --check-ports

# Setup with custom port if conflicts
python tests/utils/setup_local_docker.py --custom-base-port 7000

# Clean up containers
python tests/utils/setup_local_docker.py --cleanup

# Using test-env wrapper
./tests/utils/test-env setup     # Setup infrastructure
./tests/utils/test-env status    # Check service status
./tests/utils/test-env logs      # View logs
./tests/utils/test-env stop      # Stop services
./tests/utils/test-env test tier1  # Run unit tests
```

## Testing Strategy

### Tier 1: Unit Tests
- No Docker required, mocking allowed
- `pytest tests/unit/ -m "not (integration or e2e or requires_docker)"`

### Tier 2: Integration Tests  
- Real Docker services required, NO MOCKING
- `pytest tests/integration/ -m "not e2e"`

### Tier 3: E2E Tests
- All services including Ollama, complete real scenarios
- `pytest tests/e2e/`

## Required Ollama Models

```bash
# Pull models (after setup)
curl -X POST http://localhost:${OLLAMA_PORT}/api/pull -d '{"name": "llama3.2:1b"}'
curl -X POST http://localhost:${OLLAMA_PORT}/api/pull -d '{"name": "nomic-embed-text"}'
```

## Troubleshooting

- **Port conflicts**: `python tests/utils/setup_local_docker.py --check-ports`
- **Container logs**: `docker logs ${PROJECT_NAME}_test_postgres`
- **Service health**: `python tests/utils/validate_ci_environment.py`

## Files

- `docker_config.py`: Unified configuration with dynamic ports
- `setup_local_docker.py`: Setup script with port conflict detection
- `test-env`: Wrapper script for common operations
- `.docker-ports.lock`: Auto-generated port assignments
- `docker-compose.test.yml`: Service definitions
- `docker-compose-example.yml`: Reference configuration
