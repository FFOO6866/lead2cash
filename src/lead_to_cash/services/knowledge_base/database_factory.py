"""
Knowledge Base Database Factory

Provides connection routing for read/write operations with read replica support.
Automatically fails over to primary if replica is unavailable.

Usage:
    factory = get_database_factory()
    await factory.initialize()

    # For read operations
    async with factory.get_read_connection() as conn:
        result = await conn.fetch("SELECT * FROM kb_manufacturers")

    # For write operations
    async with factory.get_write_connection() as conn:
        await conn.execute("INSERT INTO ...")

    # Get pool statistics
    stats = await factory.get_pool_stats()

Features:
- Separate pools for primary (read-write) and replica (read-only)
- Automatic failover to primary if replica unavailable
- Health check monitoring with automatic recovery detection
- Pool statistics for monitoring
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg

from lead_to_cash.config import config
from lead_to_cash.services.knowledge_base.exceptions import (
    KBConfigurationError,
    KBConnectionError,
)
from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseFactory:
    """
    Database connection factory with read replica routing.

    Provides separate pools for read and write operations:
    - Write operations always go to primary
    - Read operations go to replica if available, else primary

    Features:
    - Automatic failover to primary if replica unavailable
    - Health check monitoring every 30 seconds
    - Connection pool management per database
    """

    # Default pool configuration
    DEFAULT_MIN_POOL_SIZE = 2
    DEFAULT_MAX_POOL_SIZE = 10
    DEFAULT_COMMAND_TIMEOUT = 30.0
    DEFAULT_HEALTH_CHECK_INTERVAL = 30.0

    def __init__(
        self,
        primary_url: Optional[str] = None,
        replica_url: Optional[str] = None,
        min_pool_size: int = DEFAULT_MIN_POOL_SIZE,
        max_pool_size: int = DEFAULT_MAX_POOL_SIZE,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ):
        """
        Initialize database factory.

        Args:
            primary_url: Primary database URL (read-write)
            replica_url: Read replica URL (optional)
            min_pool_size: Minimum connections per pool
            max_pool_size: Maximum connections per pool
            command_timeout: Default command timeout
        """
        kb_config = config.knowledge_base

        self.primary_url = primary_url or kb_config.database_url
        self.replica_url = replica_url or getattr(kb_config, "read_replica_url", None)
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.command_timeout = command_timeout

        if not self.primary_url:
            raise KBConfigurationError(
                message="Primary database URL not configured",
                config_key="KB_DATABASE_URL or DATABASE_URL",
            )

        self._primary_pool: Optional[asyncpg.Pool] = None
        self._replica_pool: Optional[asyncpg.Pool] = None
        self._replica_available = False
        self._initialized = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def has_replica(self) -> bool:
        """Check if read replica is configured and available."""
        return self._replica_available

    async def initialize(self) -> None:
        """Initialize connection pools."""
        if self._initialized:
            return

        # Initialize primary pool (required)
        try:
            self._primary_pool = await asyncpg.create_pool(
                self.primary_url,
                min_size=self.min_pool_size,
                max_size=self.max_pool_size,
                command_timeout=self.command_timeout,
            )
            # Verify connection
            async with self._primary_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("Primary database pool initialized")
        except Exception as e:
            raise KBConnectionError(
                message="Failed to connect to primary database",
                service="postgresql-primary",
                original_error=e,
            )

        # Initialize replica pool (optional)
        if self.replica_url:
            try:
                self._replica_pool = await asyncpg.create_pool(
                    self.replica_url,
                    min_size=self.min_pool_size,
                    max_size=self.max_pool_size,
                    command_timeout=self.command_timeout,
                )
                # Verify replica is responsive
                async with self._replica_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

                self._replica_available = True
                logger.info("Read replica pool initialized")
            except Exception as e:
                logger.warning(f"Read replica unavailable, using primary only: {e}")
                self._replica_available = False
                if self._replica_pool:
                    await self._replica_pool.close()
                    self._replica_pool = None

        # Start health check task
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        self._initialized = True

    async def _health_check_loop(self) -> None:
        """Periodically check replica health."""
        while self._running:
            await asyncio.sleep(self.DEFAULT_HEALTH_CHECK_INTERVAL)

            if not self._running:
                break

            # Check replica health if configured
            if self.replica_url:
                await self._check_replica_health()

    async def _check_replica_health(self) -> None:
        """Check and update replica availability."""
        if not self.replica_url:
            return

        # If we don't have a pool, try to create one
        if self._replica_pool is None:
            try:
                self._replica_pool = await asyncpg.create_pool(
                    self.replica_url,
                    min_size=self.min_pool_size,
                    max_size=self.max_pool_size,
                    command_timeout=self.command_timeout,
                )
            except Exception as e:
                logger.debug(f"Failed to create replica pool: {e}")
                return

        # Check if replica is responsive
        try:
            async with self._replica_pool.acquire(timeout=5.0) as conn:
                await conn.fetchval("SELECT 1")

            if not self._replica_available:
                self._replica_available = True
                logger.info("Read replica recovered and available")

        except Exception as e:
            if self._replica_available:
                self._replica_available = False
                logger.warning(f"Read replica became unavailable: {e}")

    @asynccontextmanager
    async def get_read_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a connection for read operations.

        Uses replica if available, falls back to primary.

        Yields:
            Database connection

        Raises:
            KBConnectionError: If no connection available
        """
        if not self._initialized:
            await self.initialize()

        # Choose pool: replica if available, else primary
        pool = (
            self._replica_pool
            if self._replica_available and self._replica_pool
            else self._primary_pool
        )

        if pool is None:
            raise KBConnectionError(
                message="No database connection pool available",
                service="postgresql",
            )

        async with pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def get_write_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a connection for write operations.

        Always uses primary database.

        Yields:
            Database connection

        Raises:
            KBConnectionError: If primary not available
        """
        if not self._initialized:
            await self.initialize()

        if self._primary_pool is None:
            raise KBConnectionError(
                message="Primary database connection pool not available",
                service="postgresql-primary",
            )

        async with self._primary_pool.acquire() as conn:
            yield conn

    async def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics for primary and replica
        """
        stats = {
            "initialized": self._initialized,
            "primary": {
                "size": self._primary_pool.get_size() if self._primary_pool else 0,
                "free": (
                    self._primary_pool.get_idle_size() if self._primary_pool else 0
                ),
                "min_size": (
                    self._primary_pool.get_min_size() if self._primary_pool else 0
                ),
                "max_size": (
                    self._primary_pool.get_max_size() if self._primary_pool else 0
                ),
            },
            "replica": None,
        }

        if self.replica_url:
            stats["replica"] = {
                "configured": True,
                "available": self._replica_available,
                "size": self._replica_pool.get_size() if self._replica_pool else 0,
                "free": (
                    self._replica_pool.get_idle_size() if self._replica_pool else 0
                ),
            }

        return stats

    async def close(self) -> None:
        """Close all connection pools."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        if self._primary_pool:
            await self._primary_pool.close()
            self._primary_pool = None

        if self._replica_pool:
            await self._replica_pool.close()
            self._replica_pool = None

        self._replica_available = False
        self._initialized = False
        logger.info("Database factory closed")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_factory: Optional[DatabaseFactory] = None


def get_database_factory() -> DatabaseFactory:
    """
    Get singleton database factory instance.

    Returns:
        DatabaseFactory instance
    """
    global _factory
    if _factory is None:
        _factory = DatabaseFactory()
    return _factory


async def initialize_database_factory() -> DatabaseFactory:
    """
    Initialize and return database factory instance.

    Returns:
        Initialized DatabaseFactory instance
    """
    factory = get_database_factory()
    await factory.initialize()
    return factory


def reset_database_factory() -> None:
    """
    Reset singleton instance. For testing only.
    """
    global _factory
    _factory = None
