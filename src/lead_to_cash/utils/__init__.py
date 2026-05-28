"""
Utility modules for Lead-to-Cash platform.

Available modules:
- resilience: Circuit breaker and retry patterns for production systems
- http_client: Async HTTP client mixin for service classes
"""

from lead_to_cash.utils.http_client import AsyncHTTPClientMixin
from lead_to_cash.utils.resilience import (
    TRANSIENT_ERROR_CODES,
    CircuitBreaker,
    is_transient_error,
    retry_with_backoff,
    with_retry,
)

__all__ = [
    # HTTP Client
    "AsyncHTTPClientMixin",
    # Resilience
    "CircuitBreaker",
    "retry_with_backoff",
    "with_retry",
    "is_transient_error",
    "TRANSIENT_ERROR_CODES",
]
