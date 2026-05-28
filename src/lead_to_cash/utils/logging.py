"""
Structured Logging Utilities for Lead-to-Cash

Provides:
- Correlation ID tracking for request tracing
- Structured JSON logging for production
- Context variables for automatic log enrichment
- Log filtering and formatting helpers

Usage:
    from lead_to_cash.utils.logging import (
        get_logger,
        correlation_id,
        with_correlation_id,
        setup_structured_logging,
    )

    # Setup once at app startup
    setup_structured_logging()

    # Get logger with automatic correlation ID injection
    logger = get_logger(__name__)

    # Set correlation ID for a request
    with with_correlation_id("req-123"):
        logger.info("Processing request")  # Includes correlation_id in output

    # Or set manually
    correlation_id.set("req-456")
    logger.info("Manual correlation ID")
"""

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Optional

# Context variable for correlation ID (thread-safe)
correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return f"kb-{uuid.uuid4().hex[:12]}"


class CorrelationIDContextManager:
    """Context manager for setting correlation ID."""

    def __init__(self, cid: Optional[str] = None):
        self.cid = cid or generate_correlation_id()
        self.token: Optional[contextvars.Token] = None

    def __enter__(self) -> str:
        self.token = correlation_id.set(self.cid)
        return self.cid

    def __exit__(self, *args):
        if self.token:
            correlation_id.reset(self.token)


def with_correlation_id(cid: Optional[str] = None) -> CorrelationIDContextManager:
    """
    Context manager to set correlation ID for a block.

    Args:
        cid: Optional correlation ID. If not provided, generates one.

    Returns:
        Context manager that sets and resets the correlation ID

    Example:
        with with_correlation_id("req-123"):
            logger.info("This log will have correlation_id=req-123")
    """
    return CorrelationIDContextManager(cid)


def correlation_id_decorator(func: Callable) -> Callable:
    """
    Decorator to automatically set correlation ID for a function.

    Example:
        @correlation_id_decorator
        async def process_article(article_id: str):
            logger.info("Processing")  # Auto-includes correlation ID
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        with with_correlation_id():
            return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        with with_correlation_id():
            return func(*args, **kwargs)

    if hasattr(func, "__wrapped__"):
        return async_wrapper if hasattr(func.__wrapped__, "__await__") else sync_wrapper
    return async_wrapper if hasattr(func, "__await__") else sync_wrapper


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Produces logs in JSON format with:
    - timestamp (ISO 8601)
    - level
    - logger name
    - message
    - correlation_id (if set)
    - extra fields
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base log record
        log_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if set
        cid = correlation_id.get()
        if cid:
            log_dict["correlation_id"] = cid

        # Add extra fields from record
        # Exclude standard LogRecord attributes
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "message",
            "asctime",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    log_dict[key] = value
                except (TypeError, ValueError):
                    log_dict[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_dict)


class CorrelationIDFilter(logging.Filter):
    """
    Filter that adds correlation ID to all log records.

    This allows using %(correlation_id)s in format strings even
    when not using structured (JSON) logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with correlation ID support.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance with correlation ID filter
    """
    logger = logging.getLogger(name)

    # Add correlation ID filter if not already present
    if not any(isinstance(f, CorrelationIDFilter) for f in logger.filters):
        logger.addFilter(CorrelationIDFilter())

    return logger


def setup_structured_logging(
    level: int = logging.INFO,
    json_format: bool = True,
    include_correlation: bool = True,
) -> None:
    """
    Setup structured logging for the application.

    Args:
        level: Log level (default INFO)
        json_format: Use JSON format (default True for production)
        include_correlation: Include correlation ID in logs (default True)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Set formatter
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        # Human-readable format with correlation ID
        format_str = "%(asctime)s - %(name)s - %(levelname)s"
        if include_correlation:
            format_str += " - [%(correlation_id)s]"
        format_str += " - %(message)s"
        handler.setFormatter(logging.Formatter(format_str))

    # Add correlation ID filter
    if include_correlation:
        handler.addFilter(CorrelationIDFilter())

    root_logger.addHandler(handler)


class LogContext:
    """
    Helper to add extra context to logs within a block.

    Example:
        with LogContext(article_id="123", operation="score"):
            logger.info("Processing")  # Includes article_id and operation
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self.old_factory = None

    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()

        context = self.context

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


# Export correlation ID decorator for async functions
def with_correlation(func: Callable) -> Callable:
    """
    Decorator alias for correlation_id_decorator.

    Usage:
        @with_correlation
        async def my_handler(request):
            logger.info("Handling request")
    """
    return correlation_id_decorator(func)


# Convenience function to get current correlation ID
def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id.get()


# Convenience function to set correlation ID
def set_correlation_id(cid: str) -> contextvars.Token:
    """Set the correlation ID and return token for reset."""
    return correlation_id.set(cid)
