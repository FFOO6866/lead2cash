# Installation Guide

This guide covers the installation and setup of the Kailash SDK Template.

## System Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Disk Space**: 1GB free space

## Quick Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Integrum-Global/new_project_template.git
cd new_project_template
```

### 2. Run Setup Script

```bash
python scripts/setup_env.py
```

This automated setup script will:
- Create a virtual environment (`.venv`)
- Install all required dependencies
- Set up pre-commit hooks
- Configure the development environment

### 3. Activate Virtual Environment

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

**On Windows:**
```bash
.venv\Scripts\activate
```

## Manual Installation

If you prefer manual setup or the automated script fails:

### 1. Create Virtual Environment

```bash
python -m venv .venv
```

### 2. Activate Virtual Environment

See activation commands above.

### 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 4. Install Dependencies

```bash
pip install -e .
```

This installs the project in editable mode with all dependencies.

### 5. Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### 6. Set Up Pre-commit Hooks

```bash
pre-commit install
```

## Verify Installation

Run these commands to verify your installation:

```python
>>> import kailash_sdk
>>> kailash_sdk.__version__
'0.1.4'

>>> from kailash_sdk import Workflow, Runtime
>>> workflow = Workflow("test")
>>> workflow.name
'test'
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Development settings
DEBUG=True
LOG_LEVEL=INFO

# API Keys (if needed)
# API_KEY=your_api_key_here

# Database (if needed)
# DATABASE_URL=postgresql://user:pass@localhost/dbname
```

## IDE Configuration

### VS Code

1. Install Python extension
2. Select the virtual environment interpreter:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Type "Python: Select Interpreter"
   - Choose `./.venv/bin/python`

### PyCharm

1. Open project settings
2. Go to Project > Python Interpreter
3. Add interpreter > Existing environment
4. Select `./.venv/bin/python`

## Troubleshooting

### Common Issues

**ImportError: No module named 'kailash_sdk'**

Solution: Ensure you've activated the virtual environment and installed dependencies:
```bash
source .venv/bin/activate
pip install -e .
```

**Permission denied errors**

Solution: On Unix systems, make scripts executable:
```bash
chmod +x scripts/*.py
```

**SSL Certificate errors**

Solution: If behind a corporate proxy, configure pip:
```bash
pip config set global.trusted-host "pypi.org files.pythonhosted.org"
```

### Getting Help

- Check existing [GitHub Issues](https://github.com/Integrum-Global/new_project_template/issues)
- Contact support

## Next Steps

- Follow the [Quickstart Guide](quickstart.md)
- Explore [Project Structure](project_structure.md)
- Check the ``sdk-users/`` directory for development guidance
