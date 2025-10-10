"""
Core business logic package.

This package contains the core business logic for the app:
- models.py: Data models and entities
- services.py: Business logic and operations
"""

from .models import BaseModel
from .services import BaseService

__all__ = ["BaseModel", "BaseService"]