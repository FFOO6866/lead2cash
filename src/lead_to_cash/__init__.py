"""
New Project Template

A clean architecture template for Kailash SDK projects with:
- Core business logic layer
- Service layer (RAG, SharePoint, MCP)
- API layer with FastAPI
- Custom nodes and workflows
- Comprehensive testing

Usage:
    cp -r src/new_project src/my_project
    cd src/my_project
    # Update setup.py, README.md, and config.py
    # Follow instructions in each module
    # Use 100% Kailash SDK components
"""

__version__ = "1.0.0"
__author__ = "Integrum"

# Import main components for easy access
from .config import AppConfig

__all__ = ["AppConfig"]
