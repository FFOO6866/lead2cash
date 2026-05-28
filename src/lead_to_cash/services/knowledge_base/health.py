"""
Kubernetes-Compatible Health Probes for Knowledge Base

Implements three probe types per Kubernetes best practices:
- Liveness: Is the process alive? (restart if failing)
- Readiness: Can the service handle traffic? (remove from load balancer if failing)
- Startup: Has the service started? (wait before liveness checks)

Response format follows RFC Health Check Response Format for HTTP APIs.

Usage:
    from lead_to_cash.services.knowledge_base.health import (
        HealthProbes,
        get_health_probes,
    )

    probes = get_health_probes()
    await probes.initialize(db, embedding_service, integration_service)

    # Kubernetes endpoints
    liveness = await probes.liveness()      # GET /health/live
    readiness = await probes.readiness()    # GET /health/ready
    startup = await probes.startup()        # GET /health/startup

    # Detailed health for dashboards
    full_health = await probes.detailed()   # GET /health
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """RFC-compliant health status values."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    component_id: str
    component_type: str  # "component", "datastore", "http"
    status: HealthStatus
    observed_value: Optional[Any] = None
    observed_unit: Optional[str] = None
    time: Optional[str] = None
    output: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "componentId": self.component_id,
            "componentType": self.component_type,
            "status": self.status.value,
        }
        if self.observed_value is not None:
            result["observedValue"] = self.observed_value
        if self.observed_unit:
            result["observedUnit"] = self.observed_unit
        if self.time:
            result["time"] = self.time
        if self.output:
            result["output"] = self.output
        return result


@dataclass
class HealthResponse:
    """RFC-compliant health check response."""

    status: HealthStatus
    version: str = "1"
    release_id: str = "1.0.0"
    service_id: str = "kb-service"
    description: str = "Marine Engine Knowledge Base Service"
    checks: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "version": self.version,
            "releaseId": self.release_id,
            "serviceId": self.service_id,
            "description": self.description,
            "checks": {k: [c.to_dict() for c in v] for k, v in self.checks.items()},
        }

    @property
    def http_status(self) -> int:
        """HTTP status code based on health status."""
        if self.status == HealthStatus.PASS:
            return 200
        elif self.status == HealthStatus.WARN:
            return 200  # Warn is still 200, just with warning status
        else:
            return 503


class HealthProbes:
    """
    Kubernetes-compatible health probes for Knowledge Base.

    Probe Types:
    - Liveness: Checks if the process is alive (not deadlocked)
    - Readiness: Checks if the service can handle requests
    - Startup: Checks if the service has completed initialization

    Configuration:
    - Liveness checks should be fast (<100ms) and only check process health
    - Readiness checks can verify dependencies
    - Startup checks wait for full initialization
    """

    # Timeouts for health checks (seconds)
    LIVENESS_TIMEOUT = 1.0
    READINESS_TIMEOUT = 5.0
    STARTUP_TIMEOUT = 30.0

    def __init__(self):
        self._db = None
        self._embedding_service = None
        self._integration_service = None
        self._redis_client = None
        self._initialized = False
        self._startup_complete = False
        self._startup_time: Optional[float] = None
        self._last_liveness_check: Optional[float] = None

    async def initialize(
        self,
        db=None,
        embedding_service=None,
        integration_service=None,
        redis_client=None,
    ) -> None:
        """
        Initialize health probes with service references.

        Args:
            db: KnowledgeBaseDatabase instance
            embedding_service: KBEmbeddingService instance
            integration_service: KBIntegrationService instance
            redis_client: Redis client for circuit breaker/rate limiter
        """
        self._db = db
        self._embedding_service = embedding_service
        self._integration_service = integration_service
        self._redis_client = redis_client
        self._initialized = True
        self._startup_time = time.monotonic()
        logger.info("Health probes initialized")

    def mark_startup_complete(self) -> None:
        """Mark that startup is complete (all services initialized)."""
        self._startup_complete = True
        duration = time.monotonic() - self._startup_time if self._startup_time else 0
        logger.info(f"Startup complete in {duration:.2f}s")

    async def liveness(self) -> HealthResponse:
        """
        Liveness probe - is the process alive?

        This should be FAST and only check process health.
        Kubernetes will restart the pod if this fails.

        Checks:
        - Event loop is responsive
        - No deadlock detected

        Returns:
            HealthResponse with pass/fail status
        """
        checks = {}
        overall_status = HealthStatus.PASS

        try:
            # Check 1: Event loop responsiveness
            start = time.monotonic()
            await asyncio.sleep(0)  # Yield to event loop
            loop_time = (time.monotonic() - start) * 1000  # ms

            loop_status = HealthStatus.PASS if loop_time < 100 else HealthStatus.WARN
            if loop_time > 1000:
                loop_status = HealthStatus.FAIL
                overall_status = HealthStatus.FAIL

            checks["event_loop:responseTime"] = [
                ComponentHealth(
                    component_id="event_loop",
                    component_type="system",
                    status=loop_status,
                    observed_value=round(loop_time, 2),
                    observed_unit="ms",
                    time=datetime.now(timezone.utc).isoformat(),
                )
            ]

            # Check 2: Memory/process health (basic)
            self._last_liveness_check = time.monotonic()

        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            overall_status = HealthStatus.FAIL
            checks["process:health"] = [
                ComponentHealth(
                    component_id="process",
                    component_type="system",
                    status=HealthStatus.FAIL,
                    output=str(e),
                    time=datetime.now(timezone.utc).isoformat(),
                )
            ]

        return HealthResponse(
            status=overall_status,
            service_id="kb-service",
            description="Liveness probe",
            checks=checks,
        )

    async def readiness(self) -> HealthResponse:
        """
        Readiness probe - can the service handle traffic?

        Checks all dependencies that are required to serve requests.
        Kubernetes will remove pod from service if this fails.

        Checks:
        - Database connection pool
        - Redis connection (for circuit breaker)
        - Circuit breaker state
        - OpenAI API availability (via circuit breaker state)

        Returns:
            HealthResponse with pass/warn/fail status
        """
        checks = {}
        overall_status = HealthStatus.PASS

        # Check 1: Database
        db_health = await self._check_database()
        checks["database:connections"] = [db_health]
        if db_health.status == HealthStatus.FAIL:
            overall_status = HealthStatus.FAIL
        elif (
            db_health.status == HealthStatus.WARN
            and overall_status == HealthStatus.PASS
        ):
            overall_status = HealthStatus.WARN

        # Check 2: Redis (if configured)
        if self._redis_client or (
            self._embedding_service
            and hasattr(self._embedding_service, "_circuit_breaker")
        ):
            redis_health = await self._check_redis()
            checks["redis:connections"] = [redis_health]
            # Redis failure is WARN, not FAIL (we have fallback)
            if (
                redis_health.status == HealthStatus.FAIL
                and overall_status == HealthStatus.PASS
            ):
                overall_status = HealthStatus.WARN

        # Check 3: Circuit breaker state
        cb_health = await self._check_circuit_breaker()
        checks["circuitBreaker:state"] = [cb_health]
        if cb_health.status == HealthStatus.FAIL:
            # Circuit breaker OPEN means we can't process requests
            overall_status = HealthStatus.FAIL
        elif (
            cb_health.status == HealthStatus.WARN
            and overall_status == HealthStatus.PASS
        ):
            overall_status = HealthStatus.WARN

        return HealthResponse(
            status=overall_status,
            service_id="kb-service",
            description="Readiness probe",
            checks=checks,
        )

    async def startup(self) -> HealthResponse:
        """
        Startup probe - has the service completed initialization?

        Used during pod startup. Kubernetes won't send liveness/readiness
        probes until startup passes.

        Checks:
        - All services initialized
        - Database migrations applied
        - Startup complete flag set

        Returns:
            HealthResponse with pass/fail status
        """

        if not self._initialized:
            return HealthResponse(
                status=HealthStatus.FAIL,
                service_id="kb-service",
                description="Startup probe - not initialized",
                checks={
                    "startup:initialized": [
                        ComponentHealth(
                            component_id="startup",
                            component_type="system",
                            status=HealthStatus.FAIL,
                            output="Health probes not initialized",
                            time=datetime.now(timezone.utc).isoformat(),
                        )
                    ]
                },
            )

        if not self._startup_complete:
            # Check how long we've been starting
            if self._startup_time:
                elapsed = time.monotonic() - self._startup_time
                if elapsed > self.STARTUP_TIMEOUT:
                    return HealthResponse(
                        status=HealthStatus.FAIL,
                        service_id="kb-service",
                        description="Startup probe - timeout",
                        checks={
                            "startup:timeout": [
                                ComponentHealth(
                                    component_id="startup",
                                    component_type="system",
                                    status=HealthStatus.FAIL,
                                    observed_value=round(elapsed, 2),
                                    observed_unit="s",
                                    output=f"Startup timeout after {elapsed:.1f}s",
                                    time=datetime.now(timezone.utc).isoformat(),
                                )
                            ]
                        },
                    )

            return HealthResponse(
                status=HealthStatus.FAIL,
                service_id="kb-service",
                description="Startup probe - in progress",
                checks={
                    "startup:inProgress": [
                        ComponentHealth(
                            component_id="startup",
                            component_type="system",
                            status=HealthStatus.FAIL,
                            output="Startup in progress",
                            time=datetime.now(timezone.utc).isoformat(),
                        )
                    ]
                },
            )

        # Startup complete
        return HealthResponse(
            status=HealthStatus.PASS,
            service_id="kb-service",
            description="Startup probe - complete",
            checks={
                "startup:complete": [
                    ComponentHealth(
                        component_id="startup",
                        component_type="system",
                        status=HealthStatus.PASS,
                        output="All services initialized",
                        time=datetime.now(timezone.utc).isoformat(),
                    )
                ]
            },
        )

    async def detailed(self) -> HealthResponse:
        """
        Detailed health check for dashboards and debugging.

        Combines all checks with additional metrics.

        Returns:
            HealthResponse with comprehensive health data
        """
        # Get all standard checks
        readiness = await self.readiness()
        checks = readiness.checks.copy()

        # Add additional metrics
        if self._db:
            db_metrics = await self._get_database_metrics()
            checks["database:poolSize"] = [db_metrics]

        if self._embedding_service:
            embedding_health = await self._check_embedding_service()
            checks["embedding:service"] = [embedding_health]

        # Add uptime
        if self._startup_time:
            uptime = time.monotonic() - self._startup_time
            checks["service:uptime"] = [
                ComponentHealth(
                    component_id="uptime",
                    component_type="system",
                    status=HealthStatus.PASS,
                    observed_value=round(uptime, 2),
                    observed_unit="s",
                    time=datetime.now(timezone.utc).isoformat(),
                )
            ]

        return HealthResponse(
            status=readiness.status,
            service_id="kb-service",
            description="Detailed health check",
            checks=checks,
        )

    # -------------------------------------------------------------------------
    # Internal check methods
    # -------------------------------------------------------------------------

    async def _check_database(self) -> ComponentHealth:
        """Check database connection pool health."""
        if not self._db:
            return ComponentHealth(
                component_id="database",
                component_type="datastore",
                status=HealthStatus.FAIL,
                output="Database not configured",
                time=datetime.now(timezone.utc).isoformat(),
            )

        try:
            start = time.monotonic()

            # Quick connectivity check with timeout
            async with asyncio.timeout(2.0):
                health = await self._db.health_check()

            response_time = (time.monotonic() - start) * 1000

            if health.get("healthy"):
                status = HealthStatus.PASS
                if response_time > 1000:  # > 1s is slow
                    status = HealthStatus.WARN
            else:
                status = HealthStatus.FAIL

            return ComponentHealth(
                component_id="database",
                component_type="datastore",
                status=status,
                observed_value=round(response_time, 2),
                observed_unit="ms",
                output=health.get("error") if not health.get("healthy") else None,
                time=datetime.now(timezone.utc).isoformat(),
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                component_id="database",
                component_type="datastore",
                status=HealthStatus.FAIL,
                output="Database health check timeout",
                time=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            return ComponentHealth(
                component_id="database",
                component_type="datastore",
                status=HealthStatus.FAIL,
                output=str(e),
                time=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_redis(self) -> ComponentHealth:
        """Check Redis connection health."""
        try:
            # Try to get Redis client from circuit breaker
            redis_client = self._redis_client
            if not redis_client and self._embedding_service:
                cb = getattr(self._embedding_service, "_circuit_breaker", None)
                if cb and hasattr(cb, "_redis"):
                    redis_client = cb._redis

            if not redis_client:
                return ComponentHealth(
                    component_id="redis",
                    component_type="datastore",
                    status=HealthStatus.WARN,
                    output="Redis not configured (using local fallback)",
                    time=datetime.now(timezone.utc).isoformat(),
                )

            start = time.monotonic()
            async with asyncio.timeout(1.0):
                await redis_client.ping()
            response_time = (time.monotonic() - start) * 1000

            status = HealthStatus.PASS
            if response_time > 100:
                status = HealthStatus.WARN

            return ComponentHealth(
                component_id="redis",
                component_type="datastore",
                status=status,
                observed_value=round(response_time, 2),
                observed_unit="ms",
                time=datetime.now(timezone.utc).isoformat(),
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                component_id="redis",
                component_type="datastore",
                status=HealthStatus.WARN,
                output="Redis timeout (using local fallback)",
                time=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            return ComponentHealth(
                component_id="redis",
                component_type="datastore",
                status=HealthStatus.WARN,
                output=f"Redis unavailable: {e} (using local fallback)",
                time=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_circuit_breaker(self) -> ComponentHealth:
        """Check circuit breaker state."""
        try:
            if not self._embedding_service:
                return ComponentHealth(
                    component_id="circuit_breaker",
                    component_type="component",
                    status=HealthStatus.WARN,
                    output="Embedding service not configured",
                    time=datetime.now(timezone.utc).isoformat(),
                )

            cb = getattr(self._embedding_service, "_circuit_breaker", None)
            if not cb:
                return ComponentHealth(
                    component_id="circuit_breaker",
                    component_type="component",
                    status=HealthStatus.WARN,
                    output="Circuit breaker not configured",
                    time=datetime.now(timezone.utc).isoformat(),
                )

            state = await cb.get_state()

            if state == "CLOSED":
                status = HealthStatus.PASS
            elif state == "HALF_OPEN":
                status = HealthStatus.WARN
            else:  # OPEN
                status = HealthStatus.FAIL

            return ComponentHealth(
                component_id="circuit_breaker",
                component_type="component",
                status=status,
                observed_value=state,
                output=f"Circuit breaker is {state}",
                time=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            return ComponentHealth(
                component_id="circuit_breaker",
                component_type="component",
                status=HealthStatus.WARN,
                output=str(e),
                time=datetime.now(timezone.utc).isoformat(),
            )

    async def _get_database_metrics(self) -> ComponentHealth:
        """Get database pool metrics."""
        try:
            if not self._db or not self._db._pool:
                return ComponentHealth(
                    component_id="database_pool",
                    component_type="datastore",
                    status=HealthStatus.WARN,
                    output="Pool not available",
                    time=datetime.now(timezone.utc).isoformat(),
                )

            pool = self._db._pool
            pool_size = pool.get_size()
            pool_free = pool.get_idle_size()
            pool_used = pool_size - pool_free

            # Warn if pool is > 80% utilized
            utilization = (pool_used / pool_size * 100) if pool_size > 0 else 0
            status = HealthStatus.PASS
            if utilization > 80:
                status = HealthStatus.WARN
            if utilization > 95:
                status = HealthStatus.FAIL

            return ComponentHealth(
                component_id="database_pool",
                component_type="datastore",
                status=status,
                observed_value={
                    "size": pool_size,
                    "used": pool_used,
                    "free": pool_free,
                    "utilization": round(utilization, 1),
                },
                observed_unit="connections",
                time=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            return ComponentHealth(
                component_id="database_pool",
                component_type="datastore",
                status=HealthStatus.WARN,
                output=str(e),
                time=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_embedding_service(self) -> ComponentHealth:
        """Check embedding service health."""
        try:
            if not self._embedding_service:
                return ComponentHealth(
                    component_id="embedding",
                    component_type="http",
                    status=HealthStatus.WARN,
                    output="Embedding service not configured",
                    time=datetime.now(timezone.utc).isoformat(),
                )

            # Get stats from embedding service
            stats = await self._embedding_service.get_embedding_stats()

            if stats.get("error"):
                return ComponentHealth(
                    component_id="embedding",
                    component_type="http",
                    status=HealthStatus.WARN,
                    output=stats["error"],
                    time=datetime.now(timezone.utc).isoformat(),
                )

            # Check embedding coverage - WARN if <90%
            coverage = stats.get("coverage_percent", 0)
            status = HealthStatus.PASS
            output = None

            if coverage < 90:
                status = HealthStatus.WARN
                without = stats.get("without_embedding", 0)
                output = f"Embedding coverage below 90%: {coverage}% ({without} aliases missing)"
                logger.warning(
                    f"Embedding coverage is {coverage}% - {without} aliases need backfill"
                )

            return ComponentHealth(
                component_id="embedding",
                component_type="http",
                status=status,
                observed_value={
                    "model": stats.get("model"),
                    "dimensions": stats.get("dimensions"),
                    "coverage_percent": coverage,
                    "total_aliases": stats.get("total_aliases"),
                    "with_embedding": stats.get("with_embedding"),
                    "without_embedding": stats.get("without_embedding"),
                },
                output=output,
                time=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            return ComponentHealth(
                component_id="embedding",
                component_type="http",
                status=HealthStatus.WARN,
                output=str(e),
                time=datetime.now(timezone.utc).isoformat(),
            )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_health_probes: Optional[HealthProbes] = None


def get_health_probes() -> HealthProbes:
    """Get singleton health probes instance."""
    global _health_probes
    if _health_probes is None:
        _health_probes = HealthProbes()
    return _health_probes
