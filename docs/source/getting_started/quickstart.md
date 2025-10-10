# Quickstart Guide

This guide will help you get started with the Kailash SDK Template in just a few minutes.

## Prerequisites

- Python 3.9 or higher
- Git
- Basic knowledge of Python

## Installation

1. **Clone the template repository:**

   ```bash
   git clone https://github.com/Integrum-Global/new_project_template.git my_project
   cd my_project
   ```

2. **Set up the development environment:**

   ```bash
   python scripts/setup_env.py
   ```

   This script will:
   - Create a virtual environment
   - Install all dependencies
   - Set up pre-commit hooks
   - Initialize the project structure

3. **Activate the virtual environment:**

   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

## Creating Your First Solution

1. **Create a new solution directory:**

   ```bash
   mkdir -p src/solutions/my_solution
   cd src/solutions/my_solution
   ```

2. **Create the basic files:**

   ```bash
   touch __init__.py __main__.py workflow.py config.py
   ```

3. **Define a simple workflow** in `workflow.py`:

   ```python
   >>> from kailash import Workflow, Runtime
   >>> from kailash.nodes import FileReaderNode, DataTransformerNode, FileWriterNode

   >>> def create_workflow():
   ...     workflow = Workflow("my_first_workflow")
   ...
   ...     # Add nodes
   ...     reader = FileReaderNode(
   ...         name="csv_reader",
   ...         file_path="data/input.csv"
   ...     )
   ...
   ...     transformer = DataTransformerNode(
   ...         name="data_processor",
   ...         operations=["clean", "normalize"]
   ...     )
   ...
   ...     writer = FileWriterNode(
   ...         name="output_writer",
   ...         file_path="data/output.csv"
   ...     )
   ...
   ...     # Connect nodes
   ...     workflow.add_nodes([reader, transformer, writer])
   ...     workflow.connect(reader, transformer)
   ...     workflow.connect(transformer, writer)
   ...
   ...     return workflow

   >>> # Example usage
   >>> workflow = create_workflow()
   >>> workflow.name
   'my_first_workflow'
   >>> len(workflow.nodes)
   3

   >>> # Execute the workflow
   >>> runtime = Runtime()
   >>> result = runtime.execute(workflow)
   >>> result["status"]
   'success'
   ```

4. **Run your workflow:**

   ```bash
   python -m src.solutions.my_solution
   ```

## Using Templates

The template includes code templates in `reference/templates/` you can use as starting points:

### Using Code Templates

```bash
# Copy workflow templates
cp -r reference/templates/workflow/* src/solutions/my_solution/

# Copy node templates
cp -r reference/templates/nodes/* src/solutions/my_solution/nodes/

# Customize the templates for your specific needs
```

## Testing Your Solution

1. **Create tests** in `src/solutions/my_solution/tests/`:

   ```python
   import pytest
   from src.solutions.my_solution.workflow import create_workflow

   def test_workflow_creation():
       workflow = create_workflow()
       assert workflow.name == "my_first_workflow"
       assert len(workflow.nodes) == 3

   def test_workflow_execution():
       workflow = create_workflow()
       runtime = Runtime()
       result = runtime.execute(workflow)
       assert result["status"] == "success"
   ```

2. **Run tests:**

   ```bash
   pytest src/solutions/my_solution/tests/
   ```

## Next Steps

- Check the ``sdk-users/`` directory for solution development guidance
- Explore the ``sdk-users/api/`` directory for API references
- Read best practices in ``sdk-users/developer/``
- Learn about [Migration](../migration/overview.md) if you have existing code

## Common Issues

### Import Errors

If you encounter import errors, ensure:
- Your virtual environment is activated
- You've run `pip install -e .` in the project root
- Your PYTHONPATH includes the project root

### Permission Errors

On Unix systems, you may need to make scripts executable:
```bash
chmod +x scripts/*.py
```

## Getting Help

- Check the ``sdk-users/developer/`` directory for troubleshooting guides
- Open an issue on [GitHub](https://github.com/Integrum-Global/new_project_template/issues)
- Review the [Kailash SDK documentation](https://kailash.readthedocs.io/)
