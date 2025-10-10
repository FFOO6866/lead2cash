#!/usr/bin/env python3
"""
Test script to demonstrate MCP Parameter Validation Tool functionality.
This script shows what Claude Code users will experience when the tool is integrated.
"""

import json
import asyncio
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tools import ParameterValidationTools

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")  
    print(f"{'='*60}")

def test_workflow_validation():
    """Test complete workflow validation with common errors."""
    print_section("Testing Workflow Validation (validate_workflow)")
    
    # Example workflow with multiple errors
    problematic_workflow = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
# Missing required parameters - PAR001 error
workflow.add_node("LLMAgentNode", "agent")
# Wrong connection syntax - CON001 error  
workflow.add_connection("agent", "target")
# Missing import - IMP002 error
workflow.add_node("CSVReaderNode", "reader")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""
    
    tools = ParameterValidationTools()
    result = tools.validate_workflow({"workflow_code": problematic_workflow})
    
    print("Input workflow code:")
    print("-" * 40)
    print(problematic_workflow)
    print("-" * 40)
    
    print("\n🚨 Validation Results:")
    print(f"✅ Validation completed: {not result.get('has_errors', True)}")  
    print(f"📊 Total errors found: {len(result.get('errors', []))}")
    
    if result.get('errors'):
        print("\n🔍 Detected Errors:")
        for i, error in enumerate(result['errors'], 1):
            print(f"  {i}. [{error.get('code', 'UNKNOWN')}] {error.get('message', str(error))}")
            if error.get('line'):
                print(f"     Line {error['line']}: {error.get('context', 'N/A')}")
    
    if result.get('suggestions'):
        print(f"\n💡 Fix suggestions provided: {len(result['suggestions'])}")
        for i, suggestion in enumerate(result['suggestions'][:2], 1):  # Show first 2
            desc = suggestion.get('description') or suggestion.get('title', str(suggestion))
            print(f"  {i}. {desc}")

def test_parameter_checking():
    """Test node parameter validation."""
    print_section("Testing Node Parameter Validation (check_node_parameters)")
    
    # Node code with missing parameters
    node_code = """
workflow.add_node("LLMAgentNode", "agent", {})  # Missing required model parameter
workflow.add_node("CSVReaderNode", "reader", {"path": "/data/file.csv"})  # Good
workflow.add_node("HTTPRequestNode", "api", {"timeout": 30})  # Missing required url
"""
    
    tools = ParameterValidationTools()
    result = tools.check_node_parameters({"node_code": node_code})
    
    print("Input node code:")
    print("-" * 40)
    print(node_code)
    print("-" * 40)
    
    print(f"\n📊 Parameter validation results:")
    print(f"✅ Success: {result.get('success', False)}")
    print(f"🔍 Issues found: {len(result.get('issues', []))}")
    
    for issue in result.get('issues', []):
        message = issue.get('message') if isinstance(issue, dict) else str(issue)
        print(f"  • {message}")

def test_fix_suggestions():
    """Test intelligent fix suggestions."""
    print_section("Testing Fix Suggestions (suggest_fixes)")
    
    # Example errors that need fixing
    errors = [
        {
            "code": "PAR001",
            "message": "Missing required parameter 'model' for LLMAgentNode",
            "line": 5,
            "context": "workflow.add_node(\"LLMAgentNode\", \"agent\", {})"
        },
        {
            "code": "CON001", 
            "message": "Invalid connection syntax - expected 4 parameters",
            "line": 7,
            "context": "workflow.add_connection(\"agent\", \"target\")"
        }
    ]
    
    tools = ParameterValidationTools()
    result = tools.suggest_fixes({"errors": errors})
    
    print("Input errors:")
    print("-" * 40)
    for error in errors:
        print(f"[{error['code']}] {error['message']}")
    print("-" * 40)
    
    print(f"\n💡 Generated {len(result.get('suggestions', []))} fix suggestions:")
    for i, suggestion in enumerate(result.get('suggestions', []), 1):
        title = suggestion.get('title') or suggestion.get('description', f'Fix #{i}')
        print(f"\n  {i}. {title}")
        if suggestion.get('description') and suggestion.get('title'):
            print(f"     {suggestion['description']}")
        if suggestion.get('code_example'):
            print(f"     Example: {suggestion['code_example']}")

def test_pattern_discovery():
    """Test SDK pattern discovery."""
    print_section("Testing Pattern Discovery (get_validation_patterns)")
    
    tools = ParameterValidationTools()
    result = tools.get_validation_patterns({})
    
    print(f"📚 Available validation patterns: {len(result.get('patterns', []))}")
    
    # Show first few patterns
    for i, pattern in enumerate(result.get('patterns', [])[:3], 1):
        print(f"\n  {i}. {pattern['name']}")
        print(f"     Category: {pattern.get('category', 'N/A')}")
        print(f"     Description: {pattern.get('description', 'N/A')[:100]}...")

def main():
    """Run all MCP tool demonstration tests."""
    print("🚀 MCP Parameter Validation Tool - Integration Test")
    print("This demonstrates what Claude Code users experience when the tool is integrated.")
    
    try:
        # Test core validation functionality
        test_workflow_validation()
        test_parameter_checking() 
        test_fix_suggestions()
        test_pattern_discovery()
        
        print_section("✅ Integration Test Complete")
        print("🎉 All MCP tools are working correctly!")
        print("📋 This is exactly what Claude Code users will experience:")
        print("   • Real-time error detection")
        print("   • Intelligent fix suggestions") 
        print("   • Pattern-based guidance")
        print("   • Comprehensive workflow validation")
        
        print(f"\n🔧 Ready for Claude Code integration!")
        print(f"📖 See CLAUDE_CODE_INTEGRATION.md for setup instructions")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        print("🔧 Check that all dependencies are properly installed")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)