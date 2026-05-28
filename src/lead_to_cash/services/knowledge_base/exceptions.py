"""
Marine Engine Knowledge Base - Exception Hierarchy

Production-ready exception classes for proper error handling
and categorization across the KB service.

Exception Hierarchy:
    KBException (base)
    ├── KBValidationError - Input/parameter validation failures
    ├── KBNotFoundError - Entity/resource not found
    ├── KBTimeoutError - Operation timeout
    ├── KBConnectionError - Database/API connection issues
    ├── KBRateLimitError - Rate limit exceeded
    └── KBCircuitBreakerError - Circuit breaker open

Usage:
    from lead_to_cash.services.knowledge_base.exceptions import (
        KBException,
        KBValidationError,
        KBNotFoundError,
        KBTimeoutError,
    )

    # Raise with context
    raise KBValidationError(
        message="Invalid embedding dimensions",
        field="embedding",
        expected=1536,
        actual=len(embedding),
    )

    # Catch and handle
    try:
        result = await resolver.resolve(text)
    except KBNotFoundError as e:
        logger.warning(f"Entity not found: {e.entity_id}")
    except KBException as e:
        logger.error(f"KB error: {e}")
"""

from datetime import datetime, timezone
from typing import Any, Optional


class KBException(Exception):
    """
    Base exception for all Knowledge Base errors.

    Provides structured error information for logging, monitoring,
    and API responses.

    Attributes:
        message: Human-readable error description
        error_code: Machine-readable error code (e.g., "KB-001")
        details: Additional context as key-value pairs
        timestamp: When the error occurred (UTC)
        correlation_id: Request/operation correlation ID
    """

    # Error code prefix
    ERROR_CODE_PREFIX = "KB"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        self.message = message
        self.error_code = error_code or f"{self.ERROR_CODE_PREFIX}-000"
        self.details = details
        self.timestamp = datetime.now(timezone.utc)
        self.correlation_id = correlation_id

        # Build detailed message
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        full_message = f"[{self.error_code}] {message}"
        if detail_str:
            full_message += f" ({detail_str})"

        super().__init__(full_message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


class KBValidationError(KBException):
    """
    Raised when input validation fails.

    Examples:
    - Invalid embedding dimensions
    - Missing required fields
    - Invalid entity type
    - Parameter out of range
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        expected: Optional[Any] = None,
        actual: Optional[Any] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        if field:
            details["field"] = field
        if expected is not None:
            details["expected"] = expected
        if actual is not None:
            details["actual"] = actual

        super().__init__(
            message=message,
            error_code="KB-100",
            correlation_id=correlation_id,
            **details,
        )

        self.field = field
        self.expected = expected
        self.actual = actual


class KBNotFoundError(KBException):
    """
    Raised when a requested entity or resource is not found.

    Examples:
    - Manufacturer not found by ID
    - Engine model not found
    - Alias not resolved
    """

    def __init__(
        self,
        message: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        search_term: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        if entity_type:
            details["entity_type"] = entity_type
        if entity_id:
            details["entity_id"] = entity_id
        if search_term:
            details["search_term"] = search_term

        super().__init__(
            message=message,
            error_code="KB-200",
            correlation_id=correlation_id,
            **details,
        )

        self.entity_type = entity_type
        self.entity_id = entity_id
        self.search_term = search_term


class KBTimeoutError(KBException):
    """
    Raised when an operation times out.

    Examples:
    - Database query timeout
    - Embedding generation timeout
    - Batch operation timeout
    """

    def __init__(
        self,
        message: str,
        operation: str,
        timeout_seconds: float,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        details["operation"] = operation
        details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            error_code="KB-300",
            correlation_id=correlation_id,
            **details,
        )

        self.operation = operation
        self.timeout_seconds = timeout_seconds


class KBConnectionError(KBException):
    """
    Raised when database or API connection fails.

    Examples:
    - PostgreSQL connection failure
    - Redis connection failure
    - OpenAI API connection failure
    """

    def __init__(
        self,
        message: str,
        service: str,
        original_error: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        details["service"] = service
        if original_error:
            details["original_error"] = str(original_error)

        super().__init__(
            message=message,
            error_code="KB-400",
            correlation_id=correlation_id,
            **details,
        )

        self.service = service
        self.original_error = original_error


class KBRateLimitError(KBException):
    """
    Raised when rate limit is exceeded.

    Examples:
    - OpenAI API rate limit exceeded
    - Embedding generation rate limit
    """

    def __init__(
        self,
        message: str,
        limiter: str,
        retry_after_seconds: Optional[float] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        details["limiter"] = limiter
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds

        super().__init__(
            message=message,
            error_code="KB-500",
            correlation_id=correlation_id,
            **details,
        )

        self.limiter = limiter
        self.retry_after_seconds = retry_after_seconds


class KBCircuitBreakerError(KBException):
    """
    Raised when circuit breaker is open.

    Examples:
    - OpenAI circuit breaker open after failures
    - Database circuit breaker tripped
    """

    def __init__(
        self,
        message: str,
        circuit_name: str,
        state: str,
        retry_after_seconds: Optional[float] = None,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        details["circuit_name"] = circuit_name
        details["state"] = state
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds

        super().__init__(
            message=message,
            error_code="KB-600",
            correlation_id=correlation_id,
            **details,
        )

        self.circuit_name = circuit_name
        self.state = state
        self.retry_after_seconds = retry_after_seconds


class KBConfigurationError(KBException):
    """
    Raised when configuration is invalid or missing.

    Examples:
    - Missing OPENAI_API_KEY
    - Invalid DATABASE_URL
    - Missing required configuration
    """

    def __init__(
        self,
        message: str,
        config_key: str,
        correlation_id: Optional[str] = None,
        **details: Any,
    ):
        details["config_key"] = config_key

        super().__init__(
            message=message,
            error_code="KB-700",
            correlation_id=correlation_id,
            **details,
        )

        self.config_key = config_key


# =============================================================================
# EXCEPTION CODE REFERENCE
# =============================================================================
#
# KB-000: Generic/unclassified error
# KB-100: Validation errors
#   KB-101: Invalid field value
#   KB-102: Missing required field
#   KB-103: Invalid embedding dimensions
#   KB-104: Invalid entity type
#   KB-105: Invalid table name
# KB-200: Not found errors
#   KB-201: Manufacturer not found
#   KB-202: Engine model not found
#   KB-203: Alias not found
#   KB-204: Article not found
# KB-300: Timeout errors
#   KB-301: Database query timeout
#   KB-302: Embedding generation timeout
#   KB-303: Batch operation timeout
# KB-400: Connection errors
#   KB-401: PostgreSQL connection error
#   KB-402: Redis connection error
#   KB-403: OpenAI API connection error
# KB-500: Rate limit errors
#   KB-501: OpenAI rate limit exceeded
#   KB-502: Redis rate limit exceeded
# KB-600: Circuit breaker errors
#   KB-601: OpenAI circuit breaker open
#   KB-602: Database circuit breaker open
# KB-700: Configuration errors
#   KB-701: Missing API key
#   KB-702: Invalid connection string
#   KB-703: Invalid configuration value
