"""
Database package for RRPS Lead-to-Cash.

Provides PostgreSQL connection pooling, schema management,
and the audit store for transaction events and field provenance.
"""

from .connection import DatabasePool, get_pool
from .audit_store import AuditStore

__all__ = ["DatabasePool", "get_pool", "AuditStore"]
