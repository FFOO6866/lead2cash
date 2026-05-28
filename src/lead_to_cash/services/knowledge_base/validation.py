"""
Marine Engine Knowledge Base - Input Validation

Production-ready input validation for all KB service methods.
Provides validators, decorators, and helper functions for
consistent validation across the codebase.

Usage:
    from lead_to_cash.services.knowledge_base.validation import (
        validate_embedding,
        validate_entity_type,
        validate_text,
        validate_positive_int,
    )

    # Direct validation
    validate_embedding(embedding)  # Raises KBValidationError if invalid

    # In method
    async def search_entities(self, query: str, entity_type: Optional[str] = None):
        validate_text(query, "query", min_length=1, max_length=10000)
        if entity_type:
            validate_entity_type(entity_type)
        ...
"""

import re
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from lead_to_cash.services.knowledge_base.exceptions import KBValidationError

# Valid entity types in the Knowledge Base
VALID_ENTITY_TYPES = frozenset(
    {
        "manufacturer",
        "engine_model",
        "engine_series",
        "application",
        "market_segment",
    }
)

# Valid match types for entity resolution
VALID_MATCH_TYPES = frozenset(
    {
        "exact",
        "alias",
        "fuzzy",
        "semantic",
    }
)

# Valid classification types for article scoring
VALID_CLASSIFICATIONS = frozenset(
    {
        "high_priority",
        "monitor",
        "ignore",
    }
)

# Embedding dimensions (OpenAI text-embedding-3-small)
EMBEDDING_DIMENSIONS = 1536


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_text(
    value: Any,
    field_name: str,
    min_length: int = 0,
    max_length: int = 10000,
    allow_empty: bool = False,
    pattern: Optional[str] = None,
) -> str:
    """
    Validate text input.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        min_length: Minimum string length
        max_length: Maximum string length
        allow_empty: Allow empty strings
        pattern: Optional regex pattern to match

    Returns:
        Validated string (stripped)

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        if allow_empty:
            return ""
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected="non-null string",
            actual="None",
        )

    if not isinstance(value, str):
        raise KBValidationError(
            message=f"{field_name} must be a string",
            field=field_name,
            expected="string",
            actual=type(value).__name__,
        )

    value = value.strip()

    if not allow_empty and len(value) == 0:
        raise KBValidationError(
            message=f"{field_name} cannot be empty",
            field=field_name,
            expected="non-empty string",
            actual="empty string",
        )

    if len(value) < min_length:
        raise KBValidationError(
            message=f"{field_name} is too short",
            field=field_name,
            expected=f"at least {min_length} characters",
            actual=len(value),
        )

    if len(value) > max_length:
        raise KBValidationError(
            message=f"{field_name} is too long",
            field=field_name,
            expected=f"at most {max_length} characters",
            actual=len(value),
        )

    if pattern and not re.match(pattern, value):
        raise KBValidationError(
            message=f"{field_name} does not match required pattern",
            field=field_name,
            expected=f"pattern: {pattern}",
            actual=value[:50] + "..." if len(value) > 50 else value,
        )

    return value


def validate_entity_type(
    value: Any,
    field_name: str = "entity_type",
    allow_none: bool = False,
) -> Optional[str]:
    """
    Validate entity type is one of the allowed values.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        allow_none: Allow None value

    Returns:
        Validated entity type

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected=f"one of {sorted(VALID_ENTITY_TYPES)}",
            actual="None",
        )

    if not isinstance(value, str):
        raise KBValidationError(
            message=f"{field_name} must be a string",
            field=field_name,
            expected="string",
            actual=type(value).__name__,
        )

    value = value.lower().strip()

    if value not in VALID_ENTITY_TYPES:
        raise KBValidationError(
            message=f"Invalid {field_name}",
            field=field_name,
            expected=f"one of {sorted(VALID_ENTITY_TYPES)}",
            actual=value,
        )

    return value


def validate_embedding(
    value: Any,
    field_name: str = "embedding",
    expected_dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[float]:
    """
    Validate embedding vector.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        expected_dimensions: Expected vector dimensions

    Returns:
        Validated embedding as list of floats

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected=f"list of {expected_dimensions} floats",
            actual="None",
        )

    if not isinstance(value, (list, tuple)):
        raise KBValidationError(
            message=f"{field_name} must be a list",
            field=field_name,
            expected="list",
            actual=type(value).__name__,
        )

    if len(value) != expected_dimensions:
        raise KBValidationError(
            message=f"{field_name} has wrong dimensions",
            field=field_name,
            expected=expected_dimensions,
            actual=len(value),
        )

    # Validate all elements are numbers
    try:
        result = [float(x) for x in value]
    except (TypeError, ValueError) as e:
        raise KBValidationError(
            message=f"{field_name} must contain only numbers",
            field=field_name,
            expected="list of floats",
            actual=f"contains non-numeric values: {e}",
        )

    return result


def validate_positive_int(
    value: Any,
    field_name: str,
    min_value: int = 1,
    max_value: int = 10000,
    allow_zero: bool = False,
) -> int:
    """
    Validate positive integer.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_zero: Allow zero value

    Returns:
        Validated integer

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected="positive integer",
            actual="None",
        )

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise KBValidationError(
            message=f"{field_name} must be an integer",
            field=field_name,
            expected="integer",
            actual=type(value).__name__,
        )

    if not allow_zero and value == 0:
        raise KBValidationError(
            message=f"{field_name} cannot be zero",
            field=field_name,
            expected=f"value >= {min_value}",
            actual=0,
        )

    if value < min_value:
        raise KBValidationError(
            message=f"{field_name} is too small",
            field=field_name,
            expected=f"value >= {min_value}",
            actual=value,
        )

    if value > max_value:
        raise KBValidationError(
            message=f"{field_name} is too large",
            field=field_name,
            expected=f"value <= {max_value}",
            actual=value,
        )

    return value


def validate_float_range(
    value: Any,
    field_name: str,
    min_value: float = 0.0,
    max_value: float = 1.0,
    allow_none: bool = False,
) -> Optional[float]:
    """
    Validate float within range.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_none: Allow None value

    Returns:
        Validated float

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected=f"float between {min_value} and {max_value}",
            actual="None",
        )

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise KBValidationError(
            message=f"{field_name} must be a number",
            field=field_name,
            expected="float",
            actual=type(value).__name__,
        )

    if value < min_value or value > max_value:
        raise KBValidationError(
            message=f"{field_name} is out of range",
            field=field_name,
            expected=f"value between {min_value} and {max_value}",
            actual=value,
        )

    return value


def validate_list(
    value: Any,
    field_name: str,
    min_length: int = 0,
    max_length: int = 10000,
    allow_empty: bool = True,
) -> list:
    """
    Validate list input.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        min_length: Minimum list length
        max_length: Maximum list length
        allow_empty: Allow empty lists

    Returns:
        Validated list

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        if allow_empty:
            return []
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected="list",
            actual="None",
        )

    if not isinstance(value, (list, tuple)):
        raise KBValidationError(
            message=f"{field_name} must be a list",
            field=field_name,
            expected="list",
            actual=type(value).__name__,
        )

    value = list(value)

    if not allow_empty and len(value) == 0:
        raise KBValidationError(
            message=f"{field_name} cannot be empty",
            field=field_name,
            expected="non-empty list",
            actual="empty list",
        )

    if len(value) < min_length:
        raise KBValidationError(
            message=f"{field_name} has too few items",
            field=field_name,
            expected=f"at least {min_length} items",
            actual=len(value),
        )

    if len(value) > max_length:
        raise KBValidationError(
            message=f"{field_name} has too many items",
            field=field_name,
            expected=f"at most {max_length} items",
            actual=len(value),
        )

    return value


def validate_id(
    value: Any,
    field_name: str = "id",
    allow_none: bool = False,
) -> Optional[str]:
    """
    Validate entity ID.

    Args:
        value: Value to validate
        field_name: Field name for error messages
        allow_none: Allow None value

    Returns:
        Validated ID string

    Raises:
        KBValidationError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise KBValidationError(
            message=f"{field_name} is required",
            field=field_name,
            expected="non-empty string",
            actual="None",
        )

    return validate_text(value, field_name, min_length=1, max_length=100)


# =============================================================================
# VALIDATION DECORATOR
# =============================================================================

T = TypeVar("T", bound=Callable)


def validate_args(**validators: Callable) -> Callable[[T], T]:
    """
    Decorator to validate function arguments.

    Args:
        **validators: Mapping of argument names to validator functions

    Example:
        @validate_args(
            text=lambda x: validate_text(x, "text", min_length=1),
            entity_type=lambda x: validate_entity_type(x, allow_none=True),
        )
        async def resolve(self, text: str, entity_type: Optional[str] = None):
            ...
    """

    def decorator(func: T) -> T:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Validate each argument that has a validator
            for arg_name, validator in validators.items():
                if arg_name in kwargs:
                    kwargs[arg_name] = validator(kwargs[arg_name])
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Validate each argument that has a validator
            for arg_name, validator in validators.items():
                if arg_name in kwargs:
                    kwargs[arg_name] = validator(kwargs[arg_name])
            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether func is async
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
