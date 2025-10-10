"""
Custom Kailash SDK nodes for the application.

This package contains custom node implementations that extend
the Kailash SDK functionality for specific business needs.

Node Development Guidelines:
1. Extend from appropriate base classes in kailash_sdk.nodes
2. Names must end with "Node" (e.g., CustomProcessorNode)
3. Set attributes BEFORE calling super().__init__()
4. Implement get_parameters() returning Dict[str, NodeParameter]
5. Use execute() method for processing (not process() or call())
6. Handle errors gracefully and provide meaningful messages
7. Add comprehensive docstrings and type hints

Example Custom Nodes:
- Domain-specific processors
- Custom data transformers
- Business logic nodes
- Integration adapters
- Validation nodes
"""