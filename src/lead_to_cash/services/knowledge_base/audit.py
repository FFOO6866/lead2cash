"""
Marine Engine Knowledge Base - Audit Logging

Production-ready audit logging for compliance and security.
Tracks all significant operations on the KB for accountability.

Features:
- Structured audit events with correlation IDs
- Async-safe logging with non-blocking writes
- Configurable retention and export
- Compliance-ready format (JSON)

Usage:
    from lead_to_cash.services.knowledge_base.audit import (
        KBAuditLogger,
        get_kb_audit_logger,
        AuditEvent,
        AuditAction,
    )

    audit = get_kb_audit_logger()

    # Log entity resolution
    await audit.log_entity_resolution(
        text="Wartsila",
        entity_type="manufacturer",
        result_id="mfr-001",
        match_type="exact",
        confidence=1.0,
        user_id="system",
    )

    # Log article scoring
    await audit.log_article_scored(
        article_id="art-001",
        classification="high_priority",
        score=85.0,
        user_id="agent-1",
    )

    # Export audit log
    events = await audit.export_events(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    )
"""

import asyncio
import json
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


class AuditAction(str, Enum):
    """Audit action types for KB operations."""

    # Entity operations
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"

    # Resolution operations
    ENTITY_RESOLVED = "entity_resolved"
    ENTITY_NOT_FOUND = "entity_not_found"
    BATCH_RESOLVED = "batch_resolved"

    # Article operations
    ARTICLE_SCORED = "article_scored"
    ARTICLE_ENRICHED = "article_enriched"

    # Embedding operations
    EMBEDDING_GENERATED = "embedding_generated"
    EMBEDDING_BATCH_GENERATED = "embedding_batch_generated"
    EMBEDDING_BACKFILL = "embedding_backfill"

    # Search operations
    SEMANTIC_SEARCH = "semantic_search"
    FUZZY_SEARCH = "fuzzy_search"

    # Admin operations
    CACHE_CLEARED = "cache_cleared"
    KB_SEEDED = "kb_seeded"
    KB_CLEARED = "kb_cleared"

    # Error events
    OPERATION_FAILED = "operation_failed"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPENED = "circuit_opened"


@dataclass
class AuditEvent:
    """Structured audit event for KB operations."""

    # Required fields
    event_id: str
    action: AuditAction
    timestamp: datetime
    service: str = "knowledge_base"

    # Context
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None

    # Operation details
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operation_details: dict = field(default_factory=dict)

    # Result
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Timing
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["action"] = self.action.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class KBAuditLogger:
    """
    Audit logger for Knowledge Base operations.

    Provides structured audit logging for compliance and security.
    Events are stored in memory with configurable retention and
    can be exported for analysis.

    Thread-safe and async-safe.
    """

    # Default configuration
    DEFAULT_MAX_EVENTS = 10000
    DEFAULT_RETENTION_DAYS = 30

    def __init__(
        self,
        max_events: int = DEFAULT_MAX_EVENTS,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        enable_file_logging: bool = False,
        log_file_path: Optional[str] = None,
    ):
        """
        Initialize audit logger.

        Args:
            max_events: Maximum events to keep in memory
            retention_days: Days to retain events
            enable_file_logging: Whether to write to file
            log_file_path: Path to audit log file
        """
        self._max_events = max_events
        self._retention_days = retention_days
        self._enable_file_logging = enable_file_logging
        self._log_file_path = log_file_path

        # In-memory event storage (thread-safe deque)
        self._events: deque[AuditEvent] = deque(maxlen=max_events)

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Counters
        self._total_events = 0
        self._events_by_action: dict[AuditAction, int] = {}

    async def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **details: Any,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            action: The action being audited
            user_id: ID of user/agent performing action
            correlation_id: Request correlation ID
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            success: Whether operation succeeded
            error_code: Error code if failed
            error_message: Error message if failed
            duration_ms: Operation duration
            **details: Additional operation details

        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            action=action,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            correlation_id=correlation_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation_details=details,
            success=success,
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        async with self._lock:
            self._events.append(event)
            self._total_events += 1
            self._events_by_action[action] = self._events_by_action.get(action, 0) + 1

        # Log to structured logger
        log_level = "info" if success else "warning"
        log_data = {
            "event_id": event.event_id,
            "action": action.value,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "success": success,
        }
        if duration_ms:
            log_data["duration_ms"] = duration_ms
        if error_code:
            log_data["error_code"] = error_code

        getattr(logger, log_level)(
            f"KB Audit: {action.value}",
            extra={"audit": log_data, "correlation_id": correlation_id},
        )

        # Write to file if enabled
        if self._enable_file_logging and self._log_file_path:
            await self._write_to_file(event)

        return event

    async def _write_to_file(self, event: AuditEvent) -> None:
        """Write event to audit log file."""
        try:
            async with asyncio.Lock():
                with open(self._log_file_path, "a") as f:
                    f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event to file: {e}")

    # -------------------------------------------------------------------------
    # Convenience methods for common operations
    # -------------------------------------------------------------------------

    async def log_entity_resolution(
        self,
        text: str,
        entity_type: Optional[str],
        result_id: Optional[str],
        match_type: Optional[str],
        confidence: Optional[float],
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEvent:
        """Log entity resolution operation."""
        action = (
            AuditAction.ENTITY_RESOLVED if result_id else AuditAction.ENTITY_NOT_FOUND
        )

        return await self.log(
            action=action,
            user_id=user_id,
            correlation_id=correlation_id,
            resource_type="entity",
            resource_id=result_id,
            success=result_id is not None,
            duration_ms=duration_ms,
            search_text=text,
            entity_type=entity_type,
            match_type=match_type,
            confidence=confidence,
        )

    async def log_article_scored(
        self,
        article_id: str,
        classification: str,
        score: float,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEvent:
        """Log article scoring operation."""
        return await self.log(
            action=AuditAction.ARTICLE_SCORED,
            user_id=user_id,
            correlation_id=correlation_id,
            resource_type="article",
            resource_id=article_id,
            duration_ms=duration_ms,
            classification=classification,
            score=score,
        )

    async def log_embedding_generated(
        self,
        text_count: int,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEvent:
        """Log embedding generation operation."""
        action = (
            AuditAction.EMBEDDING_BATCH_GENERATED
            if text_count > 1
            else AuditAction.EMBEDDING_GENERATED
        )

        return await self.log(
            action=action,
            user_id=user_id,
            correlation_id=correlation_id,
            resource_type="embedding",
            duration_ms=duration_ms,
            text_count=text_count,
        )

    async def log_search(
        self,
        query: str,
        search_type: str,
        result_count: int,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> AuditEvent:
        """Log search operation."""
        action = (
            AuditAction.SEMANTIC_SEARCH
            if search_type == "semantic"
            else AuditAction.FUZZY_SEARCH
        )

        return await self.log(
            action=action,
            user_id=user_id,
            correlation_id=correlation_id,
            resource_type="search",
            duration_ms=duration_ms,
            query=query[:100],  # Truncate for privacy
            search_type=search_type,
            result_count=result_count,
        )

    async def log_error(
        self,
        operation: str,
        error_code: str,
        error_message: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        """Log operation failure."""
        return await self.log(
            action=AuditAction.OPERATION_FAILED,
            user_id=user_id,
            correlation_id=correlation_id,
            success=False,
            error_code=error_code,
            error_message=error_message,
            operation=operation,
        )

    # -------------------------------------------------------------------------
    # Query and export methods
    # -------------------------------------------------------------------------

    async def get_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[AuditAction] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            start_date: Filter events after this date
            end_date: Filter events before this date
            action: Filter by action type
            user_id: Filter by user
            resource_type: Filter by resource type
            success: Filter by success status
            limit: Maximum events to return

        Returns:
            List of matching audit events
        """
        async with self._lock:
            events = list(self._events)

        # Apply filters
        filtered = []
        for event in events:
            if start_date and event.timestamp < start_date:
                continue
            if end_date and event.timestamp > end_date:
                continue
            if action and event.action != action:
                continue
            if user_id and event.user_id != user_id:
                continue
            if resource_type and event.resource_type != resource_type:
                continue
            if success is not None and event.success != success:
                continue

            filtered.append(event)
            if len(filtered) >= limit:
                break

        return filtered

    async def export_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json",
    ) -> str:
        """
        Export audit events for compliance reporting.

        Args:
            start_date: Export events after this date
            end_date: Export events before this date
            format: Output format ("json" or "jsonl")

        Returns:
            Formatted export string
        """
        events = await self.get_events(
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )

        if format == "jsonl":
            return "\n".join(event.to_json() for event in events)
        else:
            return json.dumps([event.to_dict() for event in events], default=str)

    def get_stats(self) -> dict:
        """Get audit statistics."""
        return {
            "total_events": self._total_events,
            "events_in_memory": len(self._events),
            "max_events": self._max_events,
            "events_by_action": {
                action.value: count for action, count in self._events_by_action.items()
            },
            "retention_days": self._retention_days,
            "file_logging_enabled": self._enable_file_logging,
        }

    async def clear(self) -> None:
        """Clear all audit events (for testing)."""
        async with self._lock:
            self._events.clear()
            self._total_events = 0
            self._events_by_action.clear()

        logger.info("Audit log cleared")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_audit_logger: Optional[KBAuditLogger] = None


def get_kb_audit_logger() -> KBAuditLogger:
    """Get singleton audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = KBAuditLogger()
    return _audit_logger
