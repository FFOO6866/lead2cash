"""
Resilience Utilities for Production Systems

Provides circuit breaker and retry patterns for handling transient failures
in external API calls and database operations.

Usage:
    from lead_to_cash.utils.resilience import (
        CircuitBreaker,
        retry_with_backoff,
        with_retry,
        is_transient_error,
    )

    # Circuit breaker for API calls
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
    if breaker.can_execute():
        try:
            result = await api_call()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
            raise

    # Retry with exponential backoff
    result = await retry_with_backoff(lambda: api_call(), max_retries=3)

    # Decorator for database operations
    @with_retry(max_retries=3)
    async def db_operation():
        ...
"""

import asyncio
import functools
import logging
import random
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

# Optional asyncpg import for database-specific error handling
try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    asyncpg = None  # type: ignore
    HAS_ASYNCPG = False

logger = logging.getLogger(__name__)

# Type variable for generic retry decorator
T = TypeVar("T")


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    Prevents cascading failures by temporarily blocking requests to a failing
    service, allowing it time to recover.

    States:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Too many failures, requests blocked
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        if breaker.can_execute():
            try:
                result = await api_call()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
                raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            half_open_max_calls: Number of test calls in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = "CLOSED"
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        """Get current circuit state, checking for timeout transitions."""
        if self._state == "OPEN" and self._last_failure_time:
            elapsed = (
                datetime.now(timezone.utc) - self._last_failure_time
            ).total_seconds()
            if elapsed >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
        return self._state

    def can_execute(self) -> bool:
        """Check if request can proceed."""
        state = self.state  # Triggers timeout check
        if state == "CLOSED":
            return True
        elif state == "HALF_OPEN":
            return self._half_open_calls < self.half_open_max_calls
        else:  # OPEN
            return False

    def record_success(self) -> None:
        """Record successful call."""
        if self._state == "HALF_OPEN":
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                # All half-open calls succeeded, close circuit
                self._state = "CLOSED"
                self._failure_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(timezone.utc)

        if self._state == "HALF_OPEN":
            # Failure in half-open state reopens circuit
            self._state = "OPEN"
        elif self._failure_count >= self.failure_threshold:
            self._state = "OPEN"

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


class DistributedCircuitBreaker:
    """
    Distributed circuit breaker using Redis for multi-worker deployments.

    Provides the same interface as CircuitBreaker but stores state in Redis,
    ensuring consistent circuit state across all workers/processes.

    Falls back to local CircuitBreaker if Redis is unavailable.
    Automatically attempts reconnection on Redis failures.

    Usage:
        breaker = DistributedCircuitBreaker(
            name="openai_api",
            redis_url="redis://localhost:6379/0",
            failure_threshold=5,
            recovery_timeout=60
        )
        await breaker.initialize()

        if await breaker.can_execute():
            try:
                result = await api_call()
                await breaker.record_success()
            except Exception:
                await breaker.record_failure()
                raise
    """

    # Lua script for atomic state transitions
    STATE_CHECK_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local recovery_timeout = tonumber(ARGV[2])
    local half_open_max = tonumber(ARGV[3])

    local state = redis.call('HGET', key, 'state') or 'CLOSED'
    local last_failure = tonumber(redis.call('HGET', key, 'last_failure') or '0')
    local half_open_calls = tonumber(redis.call('HGET', key, 'half_open_calls') or '0')

    -- Check for timeout transition from OPEN to HALF_OPEN
    if state == 'OPEN' and last_failure > 0 then
        local elapsed = now - last_failure
        if elapsed >= recovery_timeout then
            redis.call('HSET', key, 'state', 'HALF_OPEN')
            redis.call('HSET', key, 'half_open_calls', '0')
            state = 'HALF_OPEN'
            half_open_calls = 0
        end
    end

    -- Return whether execution is allowed
    if state == 'CLOSED' then
        return 1
    elseif state == 'HALF_OPEN' then
        if half_open_calls < half_open_max then
            return 1
        else
            return 0
        end
    else
        return 0
    end
    """

    RECORD_SUCCESS_SCRIPT = """
    local key = KEYS[1]
    local half_open_max = tonumber(ARGV[1])

    local state = redis.call('HGET', key, 'state') or 'CLOSED'

    if state == 'HALF_OPEN' then
        local half_open_calls = tonumber(redis.call('HGET', key, 'half_open_calls') or '0') + 1
        redis.call('HSET', key, 'half_open_calls', tostring(half_open_calls))
        if half_open_calls >= half_open_max then
            redis.call('HSET', key, 'state', 'CLOSED')
            redis.call('HSET', key, 'failure_count', '0')
        end
    else
        redis.call('HSET', key, 'failure_count', '0')
    end
    return 1
    """

    RECORD_FAILURE_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local failure_threshold = tonumber(ARGV[2])
    local ttl = tonumber(ARGV[3])

    local state = redis.call('HGET', key, 'state') or 'CLOSED'
    local failure_count = tonumber(redis.call('HGET', key, 'failure_count') or '0') + 1

    redis.call('HSET', key, 'failure_count', tostring(failure_count))
    redis.call('HSET', key, 'last_failure', tostring(now))
    redis.call('EXPIRE', key, ttl)

    if state == 'HALF_OPEN' then
        redis.call('HSET', key, 'state', 'OPEN')
    elseif failure_count >= failure_threshold then
        redis.call('HSET', key, 'state', 'OPEN')
    end
    return 1
    """

    def __init__(
        self,
        name: str,
        redis_url: Optional[str] = None,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize distributed circuit breaker.

        Args:
            name: Unique name for this circuit breaker (e.g., "openai_api")
            redis_url: Redis connection URL
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            half_open_max_calls: Number of test calls in half-open state
        """
        self.name = name
        self.redis_url = redis_url
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._redis: Optional[Any] = None
        self._available = False
        self._initialized = False

        # Fallback to local circuit breaker
        self._local_fallback = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )

        # Key for Redis hash
        self._key = f"circuit_breaker:{name}"

        # Script SHAs (cached after loading)
        self._check_sha: Optional[str] = None
        self._success_sha: Optional[str] = None
        self._failure_sha: Optional[str] = None

        # Connection recovery settings
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 5.0  # seconds between reconnect attempts
        self._last_reconnect_attempt: Optional[datetime] = None

    async def _try_reconnect(self) -> bool:
        """Attempt to reconnect to Redis after connection failure."""
        if not HAS_REDIS or not self.redis_url:
            return False

        # Rate limit reconnection attempts
        now = datetime.now(timezone.utc)
        if self._last_reconnect_attempt:
            elapsed = (now - self._last_reconnect_attempt).total_seconds()
            if elapsed < self._reconnect_delay:
                return False

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            # Reset after cooldown period
            if self._last_reconnect_attempt:
                elapsed = (now - self._last_reconnect_attempt).total_seconds()
                if elapsed > self.recovery_timeout:
                    self._reconnect_attempts = 0
                else:
                    return False

        self._last_reconnect_attempt = now
        self._reconnect_attempts += 1

        try:
            # Close existing connection if any
            if self._redis:
                try:
                    await self._redis.close()
                except (OSError, ConnectionError, RuntimeError):
                    pass  # Ignore errors when closing existing connection

            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()

            # Reload Lua scripts
            self._check_sha = await self._redis.script_load(self.STATE_CHECK_SCRIPT)
            self._success_sha = await self._redis.script_load(
                self.RECORD_SUCCESS_SCRIPT
            )
            self._failure_sha = await self._redis.script_load(
                self.RECORD_FAILURE_SCRIPT
            )

            self._available = True
            self._reconnect_attempts = 0
            logger.info(f"Circuit breaker '{self.name}' reconnected to Redis")
            return True

        except Exception as e:
            logger.warning(
                f"Circuit breaker '{self.name}' reconnection attempt "
                f"{self._reconnect_attempts}/{self._max_reconnect_attempts} failed: {e}"
            )
            self._available = False
            return False

    async def initialize(self) -> bool:
        """Initialize Redis connection and load Lua scripts."""
        if self._initialized:
            return self._available

        if not HAS_REDIS:
            logger.warning(
                f"Circuit breaker '{self.name}': Redis not available, using local fallback"
            )
            self._initialized = True
            return False

        if not self.redis_url:
            logger.warning(
                f"Circuit breaker '{self.name}': No Redis URL, using local fallback"
            )
            self._initialized = True
            return False

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()

            # Load Lua scripts
            self._check_sha = await self._redis.script_load(self.STATE_CHECK_SCRIPT)
            self._success_sha = await self._redis.script_load(
                self.RECORD_SUCCESS_SCRIPT
            )
            self._failure_sha = await self._redis.script_load(
                self.RECORD_FAILURE_SCRIPT
            )

            self._available = True
            self._initialized = True
            logger.info(
                f"Distributed circuit breaker '{self.name}' initialized with Redis"
            )
            return True

        except Exception as e:
            logger.warning(
                f"Circuit breaker '{self.name}': Redis connection failed ({e}), using local fallback"
            )
            self._available = False
            self._initialized = True
            return False

    async def can_execute(self) -> bool:
        """Check if request can proceed (async for Redis)."""
        if not self._initialized:
            await self.initialize()

        if not self._available or not self._redis:
            # Try to reconnect if Redis was previously available
            if self.redis_url and HAS_REDIS:
                await self._try_reconnect()
            if not self._available:
                return self._local_fallback.can_execute()

        try:
            import time

            now = time.time()

            result = await self._redis.evalsha(  # type: ignore[union-attr]
                self._check_sha,
                1,
                self._key,
                str(now),
                str(self.recovery_timeout),
                str(self.half_open_max_calls),
            )
            return result == 1

        except Exception as e:
            logger.warning(f"Circuit breaker check failed: {e}, attempting reconnect")
            self._available = False
            await self._try_reconnect()
            return self._local_fallback.can_execute()

    async def record_success(self) -> None:
        """Record successful call (async for Redis)."""
        if not self._available or not self._redis:
            self._local_fallback.record_success()
            return

        try:
            await self._redis.evalsha(
                self._success_sha,
                1,
                self._key,
                str(self.half_open_max_calls),
            )
        except Exception as e:
            logger.warning(
                f"Circuit breaker success record failed: {e}, attempting reconnect"
            )
            self._available = False
            await self._try_reconnect()
            self._local_fallback.record_success()

    async def record_failure(self) -> None:
        """Record failed call (async for Redis)."""
        if not self._available or not self._redis:
            self._local_fallback.record_failure()
            return

        try:
            import time

            now = time.time()
            ttl = self.recovery_timeout * 2  # Keep state for 2x recovery timeout

            await self._redis.evalsha(
                self._failure_sha,
                1,
                self._key,
                str(now),
                str(self.failure_threshold),
                str(ttl),
            )
        except Exception as e:
            logger.warning(
                f"Circuit breaker failure record failed: {e}, attempting reconnect"
            )
            self._available = False
            await self._try_reconnect()
            self._local_fallback.record_failure()

    async def get_state(self) -> str:
        """Get current circuit state."""
        if not self._available or not self._redis:
            return self._local_fallback.state

        try:
            state = await self._redis.hget(self._key, "state")
            return state or "CLOSED"
        except Exception:
            return self._local_fallback.state

    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        if self._available and self._redis:
            try:
                await self._redis.delete(self._key)
            except Exception:
                pass
        self._local_fallback.reset()

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._available = False

    @property
    def is_distributed(self) -> bool:
        """Check if using distributed (Redis) or local mode."""
        return self._available


# =============================================================================
# Retry with Exponential Backoff
# =============================================================================


async def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to call (no arguments, use lambda for args)
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        jitter: Add random jitter to prevent thundering herd

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail

    Example:
        result = await retry_with_backoff(
            lambda: api.fetch_data(user_id),
            max_retries=3,
            base_delay=1.0
        )
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e

            if attempt < max_retries:
                delay = min(base_delay * (2**attempt), max_delay)
                if jitter:
                    delay = delay * (0.5 + random.random())

                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} after {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in retry logic")


# =============================================================================
# Database Retry Decorator
# =============================================================================

# Transient PostgreSQL error codes that warrant retry
TRANSIENT_ERROR_CODES = {
    # Connection errors
    "08000",  # connection_exception
    "08003",  # connection_does_not_exist
    "08006",  # connection_failure
    "08001",  # sqlclient_unable_to_establish_sqlconnection
    "08004",  # sqlserver_rejected_establishment_of_sqlconnection
    # Transaction errors (may be transient under load)
    "40001",  # serialization_failure
    "40P01",  # deadlock_detected
    # Server errors
    "53000",  # insufficient_resources
    "53100",  # disk_full
    "53200",  # out_of_memory
    "53300",  # too_many_connections
    "57P01",  # admin_shutdown
    "57P02",  # crash_shutdown
    "57P03",  # cannot_connect_now
}


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.

    Checks for:
    - asyncpg connection errors
    - PostgreSQL transient error codes
    - Connection timeout errors
    - Common transient error message patterns

    Args:
        error: The exception to check

    Returns:
        True if error is transient and should be retried
    """
    # asyncpg specific errors (if available)
    if HAS_ASYNCPG:
        if isinstance(error, asyncpg.PostgresConnectionError):
            return True
        if isinstance(error, asyncpg.InterfaceError):
            return True
        if isinstance(error, asyncpg.TooManyConnectionsError):
            return True

        # Check PostgreSQL error codes
        if isinstance(error, asyncpg.PostgresError):
            error_code = getattr(error, "sqlstate", None)
            if error_code and error_code in TRANSIENT_ERROR_CODES:
                return True

    # Connection timeout
    if isinstance(error, asyncio.TimeoutError):
        return True

    # Check error message for common transient patterns
    error_msg = str(error).lower()
    transient_patterns = [
        "connection refused",
        "connection reset",
        "connection timed out",
        "no connection",
        "pool is closed",
        "server closed the connection",
        "ssl connection has been closed",
        "too many connections",
    ]
    return any(pattern in error_msg for pattern in transient_patterns)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for database operations with retry logic.

    Implements exponential backoff with optional jitter for transient failures.
    Only retries transient errors (connection issues, timeouts, etc.).

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to delays

    Returns:
        Decorated function with retry logic

    Example:
        @with_retry(max_retries=3)
        async def fetch_user(user_id: str):
            return await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except Exception as e:
                    last_error = e

                    # Don't retry non-transient errors
                    if not is_transient_error(e):
                        raise

                    # Don't retry after max attempts
                    if attempt >= max_retries:
                        logger.error(
                            f"Database operation {func.__name__} failed after "
                            f"{max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (2**attempt), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Transient database error in {func.__name__} "
                        f"(attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_error:
                raise last_error
            raise RuntimeError(f"Unexpected state in retry logic for {func.__name__}")

        return wrapper  # type: ignore[return-value]

    return decorator


# =============================================================================
# Redis Rate Limiter (Distributed)
# =============================================================================

# Optional redis import
try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis = None  # type: ignore
    HAS_REDIS = False


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis sliding window algorithm.

    Works correctly with multiple workers/processes. Falls back to allowing
    requests if Redis is unavailable (fail-open for availability).

    Usage:
        limiter = RedisRateLimiter(
            redis_url="redis://localhost:6379/0",
            requests_per_window=100,
            window_seconds=60
        )
        await limiter.initialize()

        if await limiter.is_allowed("client_ip"):
            # Process request
        else:
            # Rate limited

    Algorithm: Atomic sliding window using Redis Lua script
    - Lua script ensures atomic check-and-add (no race conditions)
    - Old entries (outside window) are removed
    - Request only added if under limit
    """

    # Lua script for atomic rate limiting (no race conditions)
    # Returns: 1 if allowed, 0 if rate limited
    RATE_LIMIT_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window_start = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local ttl = tonumber(ARGV[4])

    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

    -- Get current count
    local current = redis.call('ZCARD', key)

    -- Check if under limit
    if current < limit then
        -- Add this request with timestamp as score and unique member
        redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
        redis.call('EXPIRE', key, ttl)
        return 1
    else
        return 0
    end
    """

    # Read-only check script: checks if under limit WITHOUT recording.
    # Used for login brute force protection where check and record are separate phases.
    # Returns: 1 if under limit, 0 if at/over limit
    CHECK_ONLY_SCRIPT = """
    local key = KEYS[1]
    local window_start = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])

    -- Remove old entries outside the window
    redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

    -- Get current count (read-only, no ZADD)
    local current = redis.call('ZCARD', key)

    if current < limit then
        return 1
    else
        return 0
    end
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        key_prefix: str = "ratelimit:",
    ):
        """
        Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            requests_per_window: Maximum requests allowed per window
            window_seconds: Window duration in seconds
            key_prefix: Prefix for Redis keys
        """
        self.redis_url = redis_url
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self._redis: Optional[Any] = None
        self._initialized = False
        self._available = False
        self._rate_limit_sha: Optional[str] = None
        self._check_only_sha: Optional[str] = None

        # Connection recovery settings
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 5.0  # seconds between reconnect attempts
        self._last_reconnect_attempt: Optional[datetime] = None

    async def _try_reconnect(self) -> bool:
        """Attempt to reconnect to Redis after connection failure."""
        if not HAS_REDIS or not self.redis_url:
            return False

        # Rate limit reconnection attempts
        now = datetime.now(timezone.utc)
        if self._last_reconnect_attempt:
            elapsed = (now - self._last_reconnect_attempt).total_seconds()
            if elapsed < self._reconnect_delay:
                return False

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            # Reset after cooldown period (60 seconds)
            if self._last_reconnect_attempt:
                elapsed = (now - self._last_reconnect_attempt).total_seconds()
                if elapsed > 60:
                    self._reconnect_attempts = 0
                else:
                    return False

        self._last_reconnect_attempt = now
        self._reconnect_attempts += 1

        try:
            # Close existing connection if any
            if self._redis:
                try:
                    await self._redis.close()
                except (OSError, ConnectionError, RuntimeError):
                    pass  # Ignore errors when closing existing connection

            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()

            # Reload Lua scripts
            self._rate_limit_sha = await self._redis.script_load(self.RATE_LIMIT_SCRIPT)
            self._check_only_sha = await self._redis.script_load(self.CHECK_ONLY_SCRIPT)

            self._available = True
            self._reconnect_attempts = 0
            logger.info("Redis rate limiter reconnected")
            return True

        except Exception as e:
            logger.warning(
                f"Rate limiter reconnection attempt "
                f"{self._reconnect_attempts}/{self._max_reconnect_attempts} failed: {e}"
            )
            self._available = False
            return False

    async def initialize(self) -> bool:
        """
        Initialize Redis connection and load Lua script.

        Returns:
            True if Redis is available and connected
        """
        if not HAS_REDIS:
            logger.warning("Redis package not installed - rate limiting disabled")
            return False

        if not self.redis_url:
            logger.warning("REDIS_URL not configured - rate limiting disabled")
            return False

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            await self._redis.ping()

            # Load and cache Lua scripts for atomic operations
            self._rate_limit_sha = await self._redis.script_load(self.RATE_LIMIT_SCRIPT)
            self._check_only_sha = await self._redis.script_load(self.CHECK_ONLY_SCRIPT)

            self._initialized = True
            self._available = True
            logger.info(
                f"Redis rate limiter initialized (atomic Lua): "
                f"{self.requests_per_window} req/{self.window_seconds}s"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
            self._available = False
            return False

    async def is_allowed(self, client_id: str) -> bool:
        """
        Check if client is allowed to make a request.

        Uses atomic Lua script for race-condition-free rate limiting.
        The script atomically checks the count and only adds the request
        if under the limit.

        Args:
            client_id: Unique client identifier (e.g., IP address, API key)

        Returns:
            True if request is allowed, False if rate limited
        """
        if not self._available or not self._redis:
            # Try to reconnect if Redis was previously available
            if self.redis_url and HAS_REDIS:
                await self._try_reconnect()
            if not self._available:
                # Fail open if Redis unavailable
                return True

        try:
            import time

            now = time.time()
            window_start = now - self.window_seconds
            key = f"{self.key_prefix}{client_id}"
            ttl = self.window_seconds + 1

            # Execute atomic Lua script
            if self._rate_limit_sha:
                result = await self._redis.evalsha(  # type: ignore[union-attr]
                    self._rate_limit_sha,
                    1,  # number of keys
                    key,  # KEYS[1]
                    str(now),  # ARGV[1]
                    str(window_start),  # ARGV[2]
                    str(self.requests_per_window),  # ARGV[3]
                    str(ttl),  # ARGV[4]
                )
            else:
                # Fallback to EVAL if script not loaded
                result = await self._redis.eval(  # type: ignore[union-attr]
                    self.RATE_LIMIT_SCRIPT,
                    1,
                    key,
                    str(now),
                    str(window_start),
                    str(self.requests_per_window),
                    str(ttl),
                )

            return result == 1

        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}, attempting reconnect")
            self._available = False
            await self._try_reconnect()
            # Fail open on errors
            return True

    async def check_only(self, client_id: str) -> bool:
        """
        Read-only check if client is under the rate limit WITHOUT recording.

        Unlike is_allowed(), this does NOT add an entry to the sorted set.
        Use this when check and record are separate phases (e.g., login brute
        force protection where you check before auth, but only record on failure).

        Args:
            client_id: Unique client identifier (e.g., IP address)

        Returns:
            True if under limit, False if at/over limit
        """
        if not self._available or not self._redis:
            if self.redis_url and HAS_REDIS:
                await self._try_reconnect()
            if not self._available:
                return True  # Fail open

        try:
            import time

            now = time.time()
            window_start = now - self.window_seconds
            key = f"{self.key_prefix}{client_id}"

            if self._check_only_sha:
                result = await self._redis.evalsha(  # type: ignore[union-attr]
                    self._check_only_sha,
                    1,  # number of keys
                    key,  # KEYS[1]
                    str(window_start),  # ARGV[1]
                    str(self.requests_per_window),  # ARGV[2]
                )
            else:
                result = await self._redis.eval(  # type: ignore[union-attr]
                    self.CHECK_ONLY_SCRIPT,
                    1,
                    key,
                    str(window_start),
                    str(self.requests_per_window),
                )

            return result == 1

        except Exception as e:
            logger.warning(f"Redis rate limit check_only failed: {e}, attempting reconnect")
            self._available = False
            await self._try_reconnect()
            return True  # Fail open

    async def get_remaining(self, client_id: str) -> int:
        """
        Get remaining requests for client in current window.

        Args:
            client_id: Unique client identifier

        Returns:
            Number of remaining requests allowed
        """
        if not self._available or not self._redis:
            return self.requests_per_window

        try:
            import time

            now = time.time()
            window_start = now - self.window_seconds
            key = f"{self.key_prefix}{client_id}"

            # Remove old and count
            await self._redis.zremrangebyscore(key, 0, window_start)
            current_count = await self._redis.zcard(key)

            return max(0, self.requests_per_window - current_count)

        except Exception:
            return self.requests_per_window

    async def acquire(self, client_id: str = "default") -> bool:
        """
        Acquire a rate limit slot (service-level rate limiting).

        This is an alias for is_allowed() that reads more naturally for
        service-level rate limiting rather than per-client limiting.

        Args:
            client_id: Optional client identifier (defaults to "default" for service-level)

        Returns:
            True if slot acquired, False if rate limited
        """
        return await self.is_allowed(client_id)

    async def reset(self, client_id: str = "default") -> None:
        """Reset rate limit for a client."""
        if self._available and self._redis:
            try:
                key = f"{self.key_prefix}{client_id}"
                await self._redis.delete(key)
            except Exception:
                pass

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if Redis rate limiter is available."""
        return self._available


__all__ = [
    "CircuitBreaker",
    "DistributedCircuitBreaker",
    "retry_with_backoff",
    "with_retry",
    "is_transient_error",
    "TRANSIENT_ERROR_CODES",
    "RedisRateLimiter",
    "HAS_REDIS",
]
