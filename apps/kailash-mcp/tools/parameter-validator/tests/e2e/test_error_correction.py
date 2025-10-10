"""
End-to-end tests for complete error correction workflow.
Tests multi-round validation with error correction scenarios.
"""

import asyncio
from typing import Any, Dict, List

import pytest


@pytest.mark.asyncio
async def test_complete_fix_cycle():
    """Test Error → Suggestion → Fix → Success cycle."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("fix-cycle-test")

    # Stage 1: Start with completely broken workflow
    broken_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing all required params
workflow.add_node("ProcessorNode", "proc", {})   # Missing all required params
workflow.add_connection("agent", "proc")         # Wrong connection syntax
workflow.add_connection("proc", "output", "nonexistent", "input")  # Non-existent target
"""

    # Validate - should find multiple errors
    result1 = server.validation_tools.validator.validate_workflow(broken_workflow)
    assert result1["has_errors"]
    initial_errors = len(result1["errors"])
    assert initial_errors >= 3  # Should find multiple issues

    # Stage 2: Apply first round of fixes
    partially_fixed = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process data"
})  # Fixed: Added required parameters
workflow.add_node("ProcessorNode", "proc", {
    "operation": "transform"
})  # Fixed: Added required operation
workflow.add_connection("agent", "proc")  # Still wrong syntax
workflow.add_connection("proc", "output", "nonexistent", "input")  # Still bad target
"""

    # Validate - should have fewer errors
    result2 = server.validation_tools.validator.validate_workflow(partially_fixed)
    second_round_errors = len(result2["errors"])
    assert second_round_errors < initial_errors  # Should improve

    # Stage 3: Apply second round of fixes
    more_fixed = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process data"
})
workflow.add_node("ProcessorNode", "proc", {
    "operation": "transform"
})
workflow.add_node("OutputNode", "output", {
    "format": "json"
})  # Fixed: Added missing target node
workflow.add_connection("agent", "result", "proc", "input")  # Fixed: 4-param syntax
workflow.add_connection("proc", "result", "output", "data")  # Fixed: valid target
"""

    # Validate - should be much cleaner
    result3 = server.validation_tools.validator.validate_workflow(more_fixed)
    final_errors = len(result3["errors"])
    assert final_errors <= second_round_errors  # Should continue improving

    # Verify progression: broken → partially fixed → mostly fixed
    assert initial_errors > second_round_errors >= final_errors

    # Final workflow should have minimal critical errors
    critical_errors = [e for e in result3["errors"] if e["severity"] == "error"]
    assert len(critical_errors) <= 1  # Should be mostly clean


@pytest.mark.asyncio
async def test_multiple_error_handling():
    """Test handling multiple errors sequentially."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("multi-error-test")

    # Workflow with different types of errors
    multi_error_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()

# Error Type 1: Missing parameters (PAR004)
workflow.add_node("LLMAgentNode", "agent", {})

# Error Type 2: Wrong connection syntax (CON002)  
workflow.add_connection("agent", "processor")

# Error Type 3: Non-existent target (CON004)
workflow.add_connection("agent", "result", "missing_node", "input")

# Error Type 4: Circular dependency (CON005)
workflow.add_node("ProcessorNode", "proc1", {"operation": "transform"})
workflow.add_node("ProcessorNode", "proc2", {"operation": "filter"})
workflow.add_connection("proc1", "result", "proc2", "input")
workflow.add_connection("proc2", "result", "proc1", "input")  # Creates cycle
"""

    result = server.validation_tools.validator.validate_workflow(multi_error_workflow)

    # Should detect multiple error types
    assert result["has_errors"]
    assert len(result["errors"]) >= 4

    # Should have different error codes
    error_codes = {error["code"] for error in result["errors"]}
    expected_codes = {"PAR004", "CON002", "CON004", "CON005"}

    # Should detect at least 3 of the 4 error types
    detected_codes = expected_codes.intersection(error_codes)
    assert (
        len(detected_codes) >= 3
    ), f"Expected multiple error types, got: {error_codes}"

    # Generate suggestions for all errors
    suggestions = server.validation_tools.suggestion_engine.generate_fixes(
        result["errors"]
    )

    # Should provide suggestions for multiple error types
    assert len(suggestions) >= 3

    # Suggestions should address different error categories
    suggestion_codes = {s.get("error_code", "") for s in suggestions}
    assert len(suggestion_codes.intersection(expected_codes)) >= 2


@pytest.mark.asyncio
async def test_edge_case_handling():
    """Test edge cases in error correction workflow."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("edge-case-test")

    # Edge Case 1: Empty workflow
    empty_workflow = """
from kailash.workflow.builder import WorkflowBuilder
workflow = WorkflowBuilder()
# No nodes or connections
"""

    result1 = server.validation_tools.validator.validate_workflow(empty_workflow)

    # Should handle empty workflow gracefully
    assert "has_errors" in result1
    assert isinstance(result1["errors"], list)
    # May or may not have errors (empty workflow might be valid)

    # Edge Case 2: Only imports, no workflow
    imports_only = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime
import os
import json
"""

    result2 = server.validation_tools.validator.validate_workflow(imports_only)

    # Should handle imports-only gracefully
    assert "has_errors" in result2
    assert isinstance(result2["errors"], list)

    # Edge Case 3: Workflow with complex expressions
    complex_expressions = """
from kailash.workflow.builder import WorkflowBuilder
import os

workflow = WorkflowBuilder()
models = ["gpt-4", "gpt-3.5-turbo"]
selected_model = models[0] if os.getenv("USE_GPT4") else models[1]

workflow.add_node("LLMAgentNode", "dynamic_agent", {
    "model": selected_model,
    "prompt": f"Using model: {selected_model}",
    "temperature": 0.7 if selected_model == "gpt-4" else 0.5
})
"""

    result3 = server.validation_tools.validator.validate_workflow(complex_expressions)

    # Should handle dynamic expressions
    assert "has_errors" in result3
    assert isinstance(result3["errors"], list)

    # All edge cases should return structured responses
    for result in [result1, result2, result3]:
        assert "errors" in result
        assert "warnings" in result
        assert isinstance(result["errors"], list)
        assert isinstance(result.get("warnings", []), list)


@pytest.mark.asyncio
async def test_iterative_improvement_workflow():
    """Test realistic iterative improvement scenario."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("iterative-test")

    # Iteration 1: Initial attempt
    iteration1 = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("FileReaderNode", "reader", {"file": "data.txt"})
workflow.add_node("LLMAgentNode", "analyzer", {"prompt": "Analyze this"})
workflow.add_connection("reader", "analyzer")
"""

    result1 = server.validation_tools.validator.validate_workflow(iteration1)
    errors1 = len(result1["errors"])

    # Should find issues (missing model, wrong connection syntax)
    assert result1["has_errors"]
    assert errors1 >= 2

    # Iteration 2: Address some issues
    iteration2 = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("FileReaderNode", "reader", {"file_path": "data.txt"})  # Fixed param name
workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",  # Added missing model
    "prompt": "Analyze this"
})
workflow.add_connection("reader", "analyzer")  # Still wrong syntax
"""

    result2 = server.validation_tools.validator.validate_workflow(iteration2)
    errors2 = len(result2["errors"])

    # Should show improvement
    assert errors2 <= errors1

    # Iteration 3: Fix remaining issues
    iteration3 = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("FileReaderNode", "reader", {"file_path": "data.txt"})
workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4",
    "prompt": "Analyze this data: {{content}}"
})
workflow.add_connection("reader", "content", "analyzer", "prompt")  # Fixed: 4-param syntax
"""

    result3 = server.validation_tools.validator.validate_workflow(iteration3)
    errors3 = len(result3["errors"])

    # Should continue improving
    assert errors3 <= errors2

    # Final iteration should be significantly better
    assert errors3 < errors1  # Overall improvement

    # Track error reduction over iterations
    error_progression = [errors1, errors2, errors3]

    # Should show general downward trend
    assert error_progression[-1] <= error_progression[0]


@pytest.mark.asyncio
async def test_suggestion_application_effectiveness():
    """Test that suggestions actually help fix problems."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("suggestion-effectiveness-test")

    # Start with workflow that has fixable issues
    fixable_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {})  # Missing parameters - fixable
workflow.add_connection("agent", "processor")  # Wrong syntax - fixable
"""

    # Get initial validation and suggestions
    initial_result = server.validation_tools.validator.validate_workflow(
        fixable_workflow
    )
    assert initial_result["has_errors"]

    suggestions = server.validation_tools.suggestion_engine.generate_fixes(
        initial_result["errors"]
    )
    assert len(suggestions) >= 2  # Should have suggestions for both issues

    # Apply suggested fixes (simulated)
    fixed_workflow = """
from kailash.workflow.builder import WorkflowBuilder

workflow = WorkflowBuilder()
# Applied suggestion: Add required parameters
workflow.add_node("LLMAgentNode", "agent", {
    "model": "gpt-4",
    "prompt": "Process data"
})
workflow.add_node("ProcessorNode", "processor", {"operation": "transform"})
# Applied suggestion: Use 4-parameter connection syntax
workflow.add_connection("agent", "result", "processor", "input")
"""

    # Validate fixed version
    fixed_result = server.validation_tools.validator.validate_workflow(fixed_workflow)

    # Should show significant improvement
    initial_error_count = len(initial_result["errors"])
    fixed_error_count = len(fixed_result["errors"])

    assert fixed_error_count < initial_error_count

    # Specific error codes should be resolved
    initial_codes = {e["code"] for e in initial_result["errors"]}
    fixed_codes = {e["code"] for e in fixed_result["errors"]}

    # PAR004 and CON002 should be resolved
    critical_codes = {"PAR004", "CON002"}
    resolved_codes = initial_codes - fixed_codes

    assert (
        len(resolved_codes.intersection(critical_codes)) >= 1
    )  # At least one critical error resolved


@pytest.mark.asyncio
async def test_complex_workflow_correction():
    """Test correction of complex, realistic workflow."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("complex-correction-test")

    # Complex workflow with multiple realistic issues
    complex_workflow = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()

# Data ingestion layer
workflow.add_node("CSVReaderNode", "csv_reader", {
    "file": "input.csv"  # Wrong parameter name (should be file_path)
})

workflow.add_node("JSONReaderNode", "json_reader", {
    "file_path": "config.json"
})

# Processing layer  
workflow.add_node("DataProcessorNode", "cleaner", {
    # Missing required operation parameter
    "filters": ["remove_nulls"]
})

workflow.add_node("LLMAgentNode", "analyzer", {
    "model": "gpt-4"
    # Missing required prompt parameter
})

# Output layer
workflow.add_node("DatabaseWriterNode", "db_writer", {
    "connection_string": "postgresql://localhost/db"
    # Missing required table parameter
})

# Connections with various issues
workflow.add_connection("csv_reader", "cleaner")  # Wrong syntax
workflow.add_connection("json_reader", "config", "analyzer", "config")  # Valid
workflow.add_connection("cleaner", "result", "analyzer", "data")  # Valid
workflow.add_connection("analyzer", "result", "db_writer", "data")  # Valid
workflow.add_connection("analyzer", "result", "missing_node", "input")  # Non-existent target

# Execution
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    # Initial validation - should find multiple issues
    result = server.validation_tools.validator.validate_workflow(complex_workflow)

    assert result["has_errors"]
    assert len(result["errors"]) >= 4  # Multiple parameter and connection issues

    # Should detect various error types
    error_codes = {e["code"] for e in result["errors"]}
    expected_error_types = {
        "PAR004",
        "CON002",
        "CON004",
    }  # Missing params, wrong syntax, bad target

    detected_types = error_codes.intersection(expected_error_types)
    assert (
        len(detected_types) >= 2
    ), f"Should detect multiple error types, got: {error_codes}"

    # Generate comprehensive suggestions
    suggestions = server.validation_tools.suggestion_engine.generate_fixes(
        result["errors"]
    )
    assert len(suggestions) >= 3  # Should provide multiple suggestions

    # Suggestions should be actionable
    for suggestion in suggestions:
        if "error_code" in suggestion:
            assert suggestion["error_code"] in error_codes
        if "fix" in suggestion:
            assert len(suggestion["fix"]) > 10  # Meaningful guidance
        if "code_example" in suggestion:
            assert len(suggestion["code_example"]) > 10  # Useful example


@pytest.mark.asyncio
async def test_error_correction_performance():
    """Test performance of error correction workflow."""
    import time

    from server import ParameterValidationServer

    server = ParameterValidationServer("performance-correction-test")

    # Large workflow with multiple errors (performance test)
    large_workflow_parts = [
        "from kailash.workflow.builder import WorkflowBuilder",
        "workflow = WorkflowBuilder()",
    ]

    # Add many nodes with issues
    for i in range(20):
        large_workflow_parts.append(
            f'workflow.add_node("ProcessorNode", "node_{i}", {{}})'
        )  # Missing parameters

    # Add problematic connections
    for i in range(19):
        large_workflow_parts.append(
            f'workflow.add_connection("node_{i}", "node_{i+1}")'
        )  # Wrong syntax

    large_workflow = "\n".join(large_workflow_parts)

    # Time the validation + suggestion generation
    start_time = time.time()

    # Validation
    result = server.validation_tools.validator.validate_workflow(large_workflow)

    # Suggestion generation
    if result["has_errors"]:
        suggestions = server.validation_tools.suggestion_engine.generate_fixes(
            result["errors"]
        )

    end_time = time.time()
    total_time = end_time - start_time

    # Should handle large workflows efficiently
    assert (
        total_time < 2.0
    ), f"Large workflow correction took {total_time:.3f}s, should be <2s"

    # Should still find errors accurately
    assert result["has_errors"]
    assert len(result["errors"]) >= 10  # Should find many issues

    # Should provide suggestions efficiently
    if result["has_errors"]:
        assert len(suggestions) >= 5  # Should provide multiple suggestions


@pytest.mark.asyncio
async def test_recovery_from_correction_failures():
    """Test recovery when error correction doesn't work perfectly."""
    from server import ParameterValidationServer

    server = ParameterValidationServer("recovery-test")

    # Workflow that's hard to fix automatically
    difficult_workflow = """
from kailash.workflow.builder import WorkflowBuilder
import complex_custom_module  # Import that doesn't exist

workflow = WorkflowBuilder()

# Dynamic node creation that's hard to validate statically
node_types = get_node_types_from_config()  # Undefined function
for i, node_type in enumerate(node_types):
    workflow.add_node(node_type, f"dynamic_{i}", get_dynamic_config(i))

# Complex connection logic
for connection in generate_connections():  # Undefined function
    workflow.add_connection(*connection)
"""

    # Should handle gracefully even when it can't fully validate
    result = server.validation_tools.validator.validate_workflow(difficult_workflow)

    # Should return structured response even for difficult cases
    assert "has_errors" in result
    assert "errors" in result
    assert isinstance(result["errors"], list)

    # Should not crash on complex/invalid code
    assert True  # If we reach here, it didn't crash

    # Should provide some useful feedback even for complex cases
    if result["has_errors"]:
        for error in result["errors"]:
            assert "message" in error
            assert len(error["message"]) > 5  # Some meaningful message

    # Should handle suggestion generation gracefully
    try:
        suggestions = server.validation_tools.suggestion_engine.generate_fixes(
            result["errors"]
        )
        assert isinstance(suggestions, list)  # Should return list even if empty
    except Exception as e:
        pytest.fail(f"Suggestion generation should not crash on difficult cases: {e}")
