"""
Knowledge Base Cache Invalidation System

Provides Redis pub/sub based cache invalidation for distributed deployments.
Falls back to no-op for single-instance deployments without Redis.

Usage:
    from lead_to_cash.services.knowledge_base.cache_events import (
        CacheEventType,
        CacheEventPublisher,
        CacheEventSubscriber,
        get_cache_event_publisher,
        get_cache_event_subscriber,
    )

    # Publisher (in database.py)
    publisher = get_cache_event_publisher()
    await publisher.initialize()
    await publisher.publish(CacheEventType.MANUFACTURER_CREATED, entity_id="mfr-001")

    # Subscriber (in entity_resolver.py)
    subscriber = get_cache_event_subscriber()
    await subscriber.initialize()
    await subscriber.subscribe(handler_callback)

Cache Event Flow:
    1. Database CREATE/UPDATE/DELETE triggers publish()
    2. Redis pub/sub broadcasts to all subscribers
    3. EntityResolver receives event and invalidates cache entry
    4. Falls back to no-op mode if Redis unavailable
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


# Optional Redis import - graceful degradation if not installed
try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore
    HAS_REDIS = False


class CacheEventType(str, Enum):
    """Types of cache invalidation events."""

    # Manufacturer events
    MANUFACTURER_CREATED = "manufacturer.created"
    MANUFACTURER_UPDATED = "manufacturer.updated"
    MANUFACTURER_DELETED = "manufacturer.deleted"

    # Engine model events
    MODEL_CREATED = "model.created"
    MODEL_UPDATED = "model.updated"
    MODEL_DELETED = "model.deleted"

    # Engine series events
    SERIES_CREATED = "series.created"
    SERIES_UPDATED = "series.updated"
    SERIES_DELETED = "series.deleted"

    # Alias events
    ALIAS_CREATED = "alias.created"
    ALIAS_UPDATED = "alias.updated"
    ALIAS_DELETED = "alias.deleted"

    # Embedding events
    EMBEDDING_UPDATED = "embedding.updated"
    EMBEDDING_BACKFILL_COMPLETED = "embedding.backfill_completed"

    # Bulk operations
    CACHE_CLEAR_ALL = "cache.clear_all"
    CACHE_CLEAR_MANUFACTURERS = "cache.clear_manufacturers"
    CACHE_CLEAR_MODELS = "cache.clear_models"


@dataclass
class CacheEvent:
    """
    Cache invalidation event.

    Attributes:
        event_type: Type of cache event
        entity_id: ID of affected entity (optional for bulk events)
        entity_type: Type of entity (manufacturer, model, alias, etc.)
        timestamp: When the event occurred (ISO format)
        metadata: Additional event context
    """

    event_type: CacheEventType
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    timestamp: str = ""
    metadata: Optional[dict] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Serialize to JSON for Redis pub/sub."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "CacheEvent":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        data["event_type"] = CacheEventType(data["event_type"])
        return cls(**data)


class CacheEventPublisher:
    """
    Publishes cache invalidation events via Redis pub/sub.

    Falls back to no-op if Redis is unavailable. This ensures the
    application continues to work in single-instance deployments.

    Attributes:
        redis_url: Redis connection URL
        is_available: Whether Redis is connected and available
    """

    CHANNEL = "kb:cache:events"

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize cache event publisher.

        Args:
            redis_url: Redis connection URL. If None, operates in no-op mode.
        """
        self.redis_url = redis_url
        self._redis: Optional[Any] = None
        self._available = False
        self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if Redis pub/sub is available."""
        return self._available

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return

        if not HAS_REDIS or not self.redis_url:
            logger.info("Cache event publisher running in no-op mode (no Redis)")
            self._initialized = True
            return

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._available = True
            self._initialized = True
            logger.info("Cache event publisher initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable for cache events: {e}")
            self._available = False
            self._initialized = True

    async def publish(
        self,
        event_type: CacheEventType,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Publish a cache invalidation event.

        Args:
            event_type: Type of cache event
            entity_id: ID of affected entity
            entity_type: Type of entity (manufacturer, model, alias)
            metadata: Additional event metadata

        Returns:
            True if published successfully, False if unavailable/failed
        """
        if not self._initialized:
            await self.initialize()

        if not self._available or not self._redis:
            return False

        event = CacheEvent(
            event_type=event_type,
            entity_id=entity_id,
            entity_type=entity_type,
            metadata=metadata,
        )

        try:
            await self._redis.publish(self.CHANNEL, event.to_json())
            logger.debug(f"Published cache event: {event_type.value} for {entity_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish cache event: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._available = False


class CacheEventSubscriber:
    """
    Subscribes to cache invalidation events via Redis pub/sub.

    Falls back to no-op if Redis is unavailable.

    Usage:
        subscriber = CacheEventSubscriber(redis_url="redis://localhost:6379/0")
        await subscriber.initialize()

        def on_cache_event(event: CacheEvent):
            if event.event_type.value.startswith("manufacturer"):
                clear_manufacturer_cache(event.entity_id)

        await subscriber.subscribe(on_cache_event)
    """

    CHANNEL = "kb:cache:events"

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize cache event subscriber.

        Args:
            redis_url: Redis connection URL. If None, operates in no-op mode.
        """
        self.redis_url = redis_url
        self._redis: Optional[Any] = None
        self._pubsub: Optional[Any] = None
        self._available = False
        self._initialized = False
        self._listener_task: Optional[asyncio.Task] = None
        self._handlers: list[Callable[[CacheEvent], None]] = []
        self._running = False

    @property
    def is_available(self) -> bool:
        """Check if Redis pub/sub is available."""
        return self._available

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return

        if not HAS_REDIS or not self.redis_url:
            logger.info("Cache event subscriber running in no-op mode (no Redis)")
            self._initialized = True
            return

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()
            self._available = True
            self._initialized = True
            logger.info("Cache event subscriber initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable for cache events: {e}")
            self._available = False
            self._initialized = True

    async def subscribe(
        self,
        handler: Callable[[CacheEvent], None],
    ) -> bool:
        """
        Subscribe to cache events with a handler.

        Multiple handlers can be registered. All handlers are called
        for each event received.

        Args:
            handler: Callback function to handle events

        Returns:
            True if subscribed successfully, False if unavailable
        """
        if not self._initialized:
            await self.initialize()

        self._handlers.append(handler)

        if not self._available or not self._pubsub:
            logger.debug("Handler registered but Redis unavailable")
            return False

        # Subscribe and start listener if this is the first handler
        if len(self._handlers) == 1:
            await self._pubsub.subscribe(self.CHANNEL)
            self._running = True
            self._listener_task = asyncio.create_task(self._listen())
            logger.info(f"Subscribed to cache events on channel: {self.CHANNEL}")

        return True

    async def _listen(self) -> None:
        """Listen for cache events and dispatch to handlers."""
        if not self._pubsub:
            return

        try:
            while self._running:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message is None:
                    continue

                if message["type"] == "message":
                    try:
                        event = CacheEvent.from_json(message["data"])
                        logger.debug(f"Received cache event: {event.event_type.value}")

                        for handler in self._handlers:
                            try:
                                handler(event)
                            except Exception as e:
                                logger.error(f"Cache event handler error: {e}")
                    except Exception as e:
                        logger.error(f"Failed to parse cache event: {e}")

        except asyncio.CancelledError:
            logger.debug("Cache event listener cancelled")
        except Exception as e:
            logger.error(f"Cache event listener error: {e}")

    async def unsubscribe(self, handler: Callable[[CacheEvent], None]) -> None:
        """
        Unsubscribe a handler.

        Args:
            handler: Handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

        # Stop listener if no handlers left
        if not self._handlers and self._listener_task:
            self._running = False
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

            if self._pubsub:
                await self._pubsub.unsubscribe(self.CHANNEL)

    async def close(self) -> None:
        """Close Redis connection and stop listening."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub:
            await self._pubsub.unsubscribe(self.CHANNEL)
            await self._pubsub.close()
            self._pubsub = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        self._handlers.clear()
        self._available = False


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_publisher: Optional[CacheEventPublisher] = None
_subscriber: Optional[CacheEventSubscriber] = None


def get_cache_event_publisher(redis_url: Optional[str] = None) -> CacheEventPublisher:
    """
    Get singleton publisher instance.

    Args:
        redis_url: Redis URL (uses config default if not specified)

    Returns:
        CacheEventPublisher instance
    """
    global _publisher
    if _publisher is None:
        from lead_to_cash.config import config

        url = redis_url or config.knowledge_base.redis_url
        _publisher = CacheEventPublisher(redis_url=url)
    return _publisher


def get_cache_event_subscriber(redis_url: Optional[str] = None) -> CacheEventSubscriber:
    """
    Get singleton subscriber instance.

    Args:
        redis_url: Redis URL (uses config default if not specified)

    Returns:
        CacheEventSubscriber instance
    """
    global _subscriber
    if _subscriber is None:
        from lead_to_cash.config import config

        url = redis_url or config.knowledge_base.redis_url
        _subscriber = CacheEventSubscriber(redis_url=url)
    return _subscriber


def reset_cache_event_singletons() -> None:
    """
    Reset singleton instances. For testing only.
    """
    global _publisher, _subscriber
    _publisher = None
    _subscriber = None
