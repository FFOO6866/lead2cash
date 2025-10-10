"""
Unit tests for MCP resource endpoints for SDK pattern discovery.
"""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest


def test_list_available_patterns(validation_tools):
    """Test listing available SDK patterns."""
    # Mock the cheatsheet directory contents
    mock_patterns = [
        "003-quick-workflow-creation.md",
        "004-common-node-patterns.md",
        "005-connection-patterns.md",
        "025-mcp-integration.md",
    ]

    with patch("pathlib.Path.glob", return_value=[Path(p) for p in mock_patterns]):
        patterns = validation_tools.list_available_patterns()

        assert len(patterns) >= 4
        pattern_names = [p["name"] for p in patterns]
        assert "quick-workflow-creation" in str(pattern_names)
        assert "common-node-patterns" in str(pattern_names)
        assert "mcp-integration" in str(pattern_names)


def test_get_pattern_content(validation_tools):
    """Test retrieving specific pattern content."""
    mock_content = """# Quick Workflow Creation

## Basic Pattern
```python
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process: {{input}}"
})
```

## Usage
This pattern creates a simple workflow with an LLM agent.
"""

    with patch("builtins.open", mock_open(read_data=mock_content)):
        content = validation_tools.get_pattern_content("quick-workflow-creation")

        assert content is not None
        assert "Quick Workflow Creation" in content
        assert "WorkflowBuilder" in content
        assert "LLMAgentNode" in content


def test_search_patterns_by_keyword(validation_tools):
    """Test searching patterns by keyword."""
    mock_patterns = {
        "quick-workflow-creation.md": "Basic workflow creation with WorkflowBuilder",
        "mcp-integration.md": "MCP server integration and tool usage",
        "common-node-patterns.md": "LLMAgentNode, HTTPRequestNode patterns",
    }

    with patch.object(
        validation_tools, "_get_all_pattern_contents", return_value=mock_patterns
    ):
        # Search for workflow patterns
        results = validation_tools.search_patterns("workflow")
        assert len(results) >= 1
        assert any("workflow" in r["description"].lower() for r in results)

        # Search for MCP patterns
        results = validation_tools.search_patterns("mcp")
        assert len(results) >= 1
        assert any("mcp" in r["name"].lower() for r in results)


def test_get_pattern_by_node_type(validation_tools):
    """Test getting patterns specific to node types."""
    mock_patterns = [
        {"name": "llm-patterns", "filename": "llm-patterns.md", "category": "nodes"},
        {"name": "http-patterns", "filename": "http-patterns.md", "category": "nodes"},
        {"name": "data-patterns", "filename": "data-patterns.md", "category": "nodes"},
    ]

    mock_content_map = {
        "llm-patterns": "LLMAgentNode usage patterns with model and prompt",
        "http-patterns": "HTTPRequestNode for API calls",
        "data-patterns": "CSVReaderNode and DataProcessorNode examples",
    }

    with (
        patch.object(
            validation_tools, "list_available_patterns", return_value=mock_patterns
        ),
        patch.object(
            validation_tools,
            "get_pattern_content",
            side_effect=lambda name: mock_content_map.get(name),
        ),
    ):
        # Search for LLM patterns
        results = validation_tools.get_patterns_for_node_type("LLMAgentNode")
        assert len(results) >= 1
        assert any("llm" in r["name"].lower() for r in results)

        # Search for HTTP patterns
        results = validation_tools.get_patterns_for_node_type("HTTPRequestNode")
        assert len(results) >= 1


def test_get_error_specific_patterns(validation_tools):
    """Test getting patterns for specific error codes."""
    mock_patterns = [
        {
            "name": "parameter-patterns",
            "filename": "parameter-patterns.md",
            "category": "troubleshooting",
        },
        {
            "name": "connection-patterns",
            "filename": "connection-patterns.md",
            "category": "connections",
        },
        {
            "name": "cycle-patterns",
            "filename": "cycle-patterns.md",
            "category": "cycles",
        },
    ]

    mock_content_map = {
        "parameter-patterns": "PAR004 missing required parameters solutions",
        "connection-patterns": "CON002 connection syntax examples",
        "cycle-patterns": "CYC001 deprecated cycle syntax migration",
    }

    with (
        patch.object(
            validation_tools, "list_available_patterns", return_value=mock_patterns
        ),
        patch.object(
            validation_tools,
            "get_pattern_content",
            side_effect=lambda name: mock_content_map.get(name),
        ),
    ):
        # Get patterns for parameter errors
        results = validation_tools.get_patterns_for_error("PAR004")
        assert len(results) >= 1

        # Get patterns for connection errors
        results = validation_tools.get_patterns_for_error("CON002")
        assert len(results) >= 1


def test_resource_uri_patterns(validation_tools):
    """Test MCP resource URI patterns."""
    # Test pattern discovery URIs
    assert validation_tools._is_valid_pattern_uri("patterns://workflow/basic")
    assert validation_tools._is_valid_pattern_uri("patterns://node/LLMAgentNode")
    assert validation_tools._is_valid_pattern_uri("patterns://error/PAR004")
    assert validation_tools._is_valid_pattern_uri("patterns://search/mcp")

    # Invalid URIs
    assert not validation_tools._is_valid_pattern_uri("invalid://pattern")
    assert not validation_tools._is_valid_pattern_uri("patterns://")


def test_pattern_caching(validation_tools):
    """Test that patterns are cached for performance."""
    mock_content = "# Test Pattern\nSample content"

    # Mock both the file operations and glob
    mock_path = Path("test-pattern.md")
    with (
        patch("builtins.open", mock_open(read_data=mock_content)) as mock_file,
        patch("pathlib.Path.glob", return_value=[mock_path]),
    ):
        # First call
        content1 = validation_tools.get_pattern_content("test-pattern")

        # Second call
        content2 = validation_tools.get_pattern_content("test-pattern")

        # Should be same content
        assert content1 == content2

        # File should only be read once due to caching
        assert mock_file.call_count == 1


def test_pattern_metadata_extraction(validation_tools):
    """Test extracting metadata from pattern files."""
    mock_content = """# Quick Workflow Creation

**Difficulty:** Beginner
**Node Types:** WorkflowBuilder, LLMAgentNode
**Use Cases:** Basic automation, AI workflows

## Overview
Basic workflow pattern for getting started.

```python
workflow = WorkflowBuilder()
```
"""

    # Mock both file operations and glob
    mock_path = Path("quick-workflow-creation.md")
    with (
        patch("builtins.open", mock_open(read_data=mock_content)),
        patch("pathlib.Path.glob", return_value=[mock_path]),
    ):
        metadata = validation_tools.get_pattern_metadata("quick-workflow-creation")

        assert metadata["title"] == "Quick Workflow Creation"
        assert metadata["difficulty"] == "Beginner"
        assert "WorkflowBuilder" in metadata["node_types"]
        assert "LLMAgentNode" in metadata["node_types"]


def test_get_related_patterns(validation_tools):
    """Test finding related patterns based on content similarity."""
    mock_patterns = {
        "workflow-basics.md": "WorkflowBuilder basic usage patterns",
        "advanced-workflows.md": "Complex WorkflowBuilder patterns with cycles",
        "llm-integration.md": "LLMAgentNode integration examples",
        "data-processing.md": "DataProcessorNode usage patterns",
    }

    # Mock base pattern content
    base_content = "WorkflowBuilder basic usage patterns"

    with (
        patch.object(
            validation_tools, "_get_all_pattern_contents", return_value=mock_patterns
        ),
        patch.object(
            validation_tools, "get_pattern_content", return_value=base_content
        ),
    ):
        # Get patterns related to workflow basics
        related = validation_tools.get_related_patterns("workflow-basics")

        # Should find advanced workflows as related
        assert len(related) >= 1
        related_names = [p["name"] for p in related]
        assert "advanced-workflows" in str(related_names)


def test_pattern_usage_examples(validation_tools):
    """Test extracting code examples from patterns."""
    mock_content = """# Pattern Examples

## Basic Usage
```python
workflow = WorkflowBuilder()
workflow.add_node("TestNode", "test", {"param": "value"})
```

## Advanced Usage
```python
cycle_builder = workflow.create_cycle("advanced")
cycle_builder.connect("n1", "n2", mapping={"out": "in"})
cycle_builder.build()
```
"""

    # Mock both file operations and glob
    mock_path = Path("test-pattern.md")
    with (
        patch("builtins.open", mock_open(read_data=mock_content)),
        patch("pathlib.Path.glob", return_value=[mock_path]),
    ):
        examples = validation_tools.extract_code_examples("test-pattern")

        assert len(examples) >= 2
        assert any("WorkflowBuilder" in ex["code"] for ex in examples)
        assert any("create_cycle" in ex["code"] for ex in examples)


def test_pattern_validation_integration(parameter_validator, validation_tools):
    """Test integration between pattern discovery and validation."""
    # Mock pattern that contains valid workflow code
    mock_pattern = """# Valid Workflow Pattern

```python
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4", 
    "prompt": "Hello"
})
```
"""

    with patch.object(
        validation_tools, "get_pattern_content", return_value=mock_pattern
    ):
        # Get pattern content
        pattern = validation_tools.get_pattern_content("valid-workflow")

        # Extract code and validate it
        examples = validation_tools.extract_code_examples_from_content(pattern)
        if examples:
            result = parameter_validator.validate_workflow(examples[0]["code"])
            assert result["has_errors"] is False
