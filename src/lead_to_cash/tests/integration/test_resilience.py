"""
Integration Tests for Resilience Patterns

Tests circuit breaker, retry logic, and Redis rate limiting implementations.
Uses real infrastructure (NO MOCKING) as per testing policy.

Requirements:
- Redis (for rate limiter tests) - optional, tests skip if unavailable
- Circuit breaker tests use simulated failures
"""

import asyncio
import os
import time

import pytest

from lead_to_cash.utils.resilience import (
    CircuitBreaker,
    RedisRateLimiter,
    is_transient_error,
    retry_with_backoff,
)

# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Test CircuitBreaker implementation."""

    def test_circuit_starts_closed(self):
        """Circuit should start in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        assert breaker.state == "CLOSED"
        assert breaker.can_execute() is True

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit should open after failure threshold is reached."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        # Record failures
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == "OPEN"
        assert breaker.can_execute() is False

    def test_circuit_stays_closed_below_threshold(self):
        """Circuit should stay closed if failures are below threshold."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        # Record some failures but below threshold
        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == "CLOSED"
        assert breaker.can_execute() is True

    def test_success_resets_failure_count(self):
        """Success should reset failure count."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        # Record some failures
        breaker.record_failure()
        breaker.record_failure()

        # Record success - should reset
        breaker.record_success()

        # Should be able to fail 3 more times before opening
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "CLOSED"

        breaker.record_failure()
        assert breaker.state == "OPEN"

    def test_circuit_transitions_to_half_open(self):
        """Circuit should transition to HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Should now be HALF_OPEN
        assert breaker.state == "HALF_OPEN"
        assert breaker.can_execute() is True

    def test_half_open_closes_on_success(self):
        """Circuit should close after successful calls in HALF_OPEN state."""
        breaker = CircuitBreaker(
            failure_threshold=2, recovery_timeout=1, half_open_max_calls=2
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait for recovery
        time.sleep(1.1)
        assert breaker.state == "HALF_OPEN"

        # Successful calls should close circuit
        breaker.record_success()
        breaker.record_success()

        assert breaker.state == "CLOSED"

    def test_half_open_reopens_on_failure(self):
        """Circuit should reopen on failure in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait for recovery
        time.sleep(1.1)
        assert breaker.state == "HALF_OPEN"

        # Failure should reopen
        breaker.record_failure()
        assert breaker.state == "OPEN"

    def test_reset_returns_to_closed(self):
        """Reset should return circuit to CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "OPEN"

        # Reset
        breaker.reset()
        assert breaker.state == "CLOSED"
        assert breaker._failure_count == 0


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestRetryWithBackoff:
    """Test retry_with_backoff implementation."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        """Should return immediately on success."""
        call_count = 0

        async def success_fn():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_fn, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry on failures up to max_retries."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Simulated failure")
            return "success"

        result = await retry_with_backoff(
            fail_then_succeed, max_retries=3, base_delay=0.1
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Should raise exception after max retries exhausted."""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await retry_with_backoff(always_fail, max_retries=2, base_delay=0.1)

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_backoff_delay_increases(self):
        """Verify delay increases between retries."""
        call_times = []

        async def track_time_and_fail():
            call_times.append(time.time())
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await retry_with_backoff(
                track_time_and_fail, max_retries=2, base_delay=0.1, jitter=False
            )

        # Check delays increase
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # First delay ~0.1s, second delay ~0.2s (exponential backoff)
        assert delay1 >= 0.05  # Allow some tolerance
        assert delay2 >= delay1


# =============================================================================
# Transient Error Detection Tests
# =============================================================================


class TestTransientErrorDetection:
    """Test is_transient_error function."""

    def test_timeout_is_transient(self):
        """asyncio.TimeoutError should be transient."""
        assert is_transient_error(asyncio.TimeoutError()) is True

    def test_connection_refused_is_transient(self):
        """Connection refused errors should be transient."""
        error = ConnectionError("Connection refused")
        assert is_transient_error(error) is True

    def test_connection_reset_is_transient(self):
        """Connection reset errors should be transient."""
        error = ConnectionError("Connection reset by peer")
        assert is_transient_error(error) is True

    def test_value_error_is_not_transient(self):
        """ValueError should not be transient."""
        assert is_transient_error(ValueError("Invalid input")) is False

    def test_key_error_is_not_transient(self):
        """KeyError should not be transient."""
        assert is_transient_error(KeyError("missing_key")) is False


# =============================================================================
# Redis Rate Limiter Tests (require Redis)
# =============================================================================


@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="Redis not available - set REDIS_URL to run these tests",
)
class TestRedisRateLimiter:
    """Test RedisRateLimiter implementation with real Redis."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Should allow requests under the limit."""
        limiter = RedisRateLimiter(
            redis_url=os.getenv("REDIS_URL"),
            requests_per_window=10,
            window_seconds=60,
            key_prefix="test_under_limit:",
        )
        await limiter.initialize()

        try:
            # Reset any existing state
            await limiter.reset("test_client")

            # Should allow requests under limit
            for i in range(5):
                assert await limiter.is_allowed("test_client") is True

            # Check remaining
            remaining = await limiter.get_remaining("test_client")
            assert remaining == 5  # 10 - 5 requests
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        """Should block requests over the limit."""
        limiter = RedisRateLimiter(
            redis_url=os.getenv("REDIS_URL"),
            requests_per_window=5,
            window_seconds=60,
            key_prefix="test_over_limit:",
        )
        await limiter.initialize()

        try:
            # Reset any existing state
            await limiter.reset("test_client")

            # Use up the limit
            for i in range(5):
                await limiter.is_allowed("test_client")

            # Next request should be blocked
            assert await limiter.is_allowed("test_client") is False
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_window_expiry(self):
        """Should reset after window expires."""
        limiter = RedisRateLimiter(
            redis_url=os.getenv("REDIS_URL"),
            requests_per_window=2,
            window_seconds=2,  # Short window for testing
            key_prefix="test_expiry:",
        )
        await limiter.initialize()

        try:
            # Reset any existing state
            await limiter.reset("test_client")

            # Use up limit
            await limiter.is_allowed("test_client")
            await limiter.is_allowed("test_client")
            assert await limiter.is_allowed("test_client") is False

            # Wait for window to expire
            await asyncio.sleep(2.5)

            # Should be allowed again
            assert await limiter.is_allowed("test_client") is True
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_per_client_isolation(self):
        """Each client should have separate rate limits."""
        limiter = RedisRateLimiter(
            redis_url=os.getenv("REDIS_URL"),
            requests_per_window=3,
            window_seconds=60,
            key_prefix="test_isolation:",
        )
        await limiter.initialize()

        try:
            # Reset
            await limiter.reset("client_a")
            await limiter.reset("client_b")

            # Exhaust client_a limit
            for _ in range(3):
                await limiter.is_allowed("client_a")
            assert await limiter.is_allowed("client_a") is False

            # client_b should still be allowed
            assert await limiter.is_allowed("client_b") is True
        finally:
            await limiter.close()

    @pytest.mark.asyncio
    async def test_graceful_degradation_without_redis(self):
        """Should fail open if Redis unavailable."""
        limiter = RedisRateLimiter(
            redis_url="redis://invalid-host:6379/0",  # Invalid host
            requests_per_window=5,
            window_seconds=60,
        )
        result = await limiter.initialize()

        assert result is False
        assert limiter.is_available is False

        # Should allow requests (fail open)
        assert await limiter.is_allowed("test_client") is True

        await limiter.close()


# =============================================================================
# Integration: Circuit Breaker + Retry
# =============================================================================


class TestCircuitBreakerWithRetry:
    """Test circuit breaker integrated with retry logic."""

    @pytest.mark.asyncio
    async def test_retry_with_circuit_breaker(self):
        """Circuit breaker should work with retry logic."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        call_count = 0

        async def protected_call():
            nonlocal call_count
            if not breaker.can_execute():
                raise RuntimeError("Circuit open")

            call_count += 1
            breaker.record_failure()
            raise ValueError("Simulated failure")

        # Retry should stop when circuit opens
        with pytest.raises((ValueError, RuntimeError)):
            await retry_with_backoff(protected_call, max_retries=5, base_delay=0.1)

        # Circuit should be open after 3 failures
        assert breaker.state == "OPEN"
        assert call_count == 3  # Stopped after circuit opened
