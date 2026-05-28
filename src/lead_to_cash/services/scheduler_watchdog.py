"""
Scheduler Watchdog Service

Unified monitoring for all background jobs across:
- Competitor Intelligence Scheduler
- Marine Sales Intelligence Scheduler

Features:
- Unified health check across all schedulers
- Job status monitoring and history
- Stale job detection
- Failure alerting
- Job execution metrics

Usage:
    from lead_to_cash.services.scheduler_watchdog import (
        get_watchdog,
        initialize_watchdog,
    )

    # Initialize during startup
    await initialize_watchdog()

    # Get unified health status
    health = await get_watchdog().get_health()

    # Get all job statuses
    jobs = await get_watchdog().get_all_job_statuses()
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class JobHealth(str, Enum):
    """Job health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SchedulerType(str, Enum):
    """Scheduler types."""

    COMPETITOR_INTEL = "competitor_intel"
    MARINE_INTEL = "marine_intel"


@dataclass
class JobStatus:
    """Status of a scheduled job."""

    job_id: str
    job_name: str
    scheduler: SchedulerType
    is_scheduled: bool
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    last_status: Optional[str]
    last_duration_seconds: Optional[float]
    run_count: int
    success_count: int
    failure_count: int
    health: JobHealth
    health_reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "scheduler": self.scheduler.value,
            "is_scheduled": self.is_scheduled,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status,
            "last_duration_seconds": self.last_duration_seconds,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "health": self.health.value,
            "health_reason": self.health_reason,
        }


@dataclass
class SchedulerHealth:
    """Health status of a scheduler."""

    scheduler: SchedulerType
    is_running: bool
    job_count: int
    healthy_jobs: int
    warning_jobs: int
    critical_jobs: int
    last_check: datetime
    health: JobHealth
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "scheduler": self.scheduler.value,
            "is_running": self.is_running,
            "job_count": self.job_count,
            "healthy_jobs": self.healthy_jobs,
            "warning_jobs": self.warning_jobs,
            "critical_jobs": self.critical_jobs,
            "last_check": self.last_check.isoformat(),
            "health": self.health.value,
            "details": self.details,
        }


@dataclass
class WatchdogHealth:
    """Overall watchdog health status."""

    overall_health: JobHealth
    competitor_intel: Optional[SchedulerHealth]
    marine_intel: Optional[SchedulerHealth]
    total_jobs: int
    healthy_jobs: int
    warning_jobs: int
    critical_jobs: int
    stale_jobs: int
    failed_jobs_24h: int
    timestamp: datetime
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "overall_health": self.overall_health.value,
            "competitor_intel": (
                self.competitor_intel.to_dict() if self.competitor_intel else None
            ),
            "marine_intel": (
                self.marine_intel.to_dict() if self.marine_intel else None
            ),
            "total_jobs": self.total_jobs,
            "healthy_jobs": self.healthy_jobs,
            "warning_jobs": self.warning_jobs,
            "critical_jobs": self.critical_jobs,
            "stale_jobs": self.stale_jobs,
            "failed_jobs_24h": self.failed_jobs_24h,
            "timestamp": self.timestamp.isoformat(),
            "alerts": self.alerts,
        }


class SchedulerWatchdog:
    """
    Unified monitoring service for all background job schedulers.

    Provides:
    - Health checks across all schedulers
    - Job status tracking
    - Stale job detection
    - Failure alerting
    """

    # Thresholds for health determination
    STALE_JOB_HOURS = 25  # Job is stale if not run in 25 hours (for daily jobs)
    WARNING_FAILURE_RATE = 0.1  # 10% failure rate = warning
    CRITICAL_FAILURE_RATE = 0.25  # 25% failure rate = critical

    def __init__(self):
        """Initialize watchdog."""
        self._initialized = False
        self._last_check: Optional[datetime] = None

    async def initialize(self) -> None:
        """Initialize the watchdog service."""
        if self._initialized:
            return

        logger.info("Initializing Scheduler Watchdog")
        self._initialized = True
        logger.info("Scheduler Watchdog initialized")

    async def get_health(self) -> WatchdogHealth:
        """
        Get unified health status across all schedulers.

        Returns:
            WatchdogHealth with overall status
        """
        now = datetime.now(timezone.utc)
        alerts: list[str] = []

        # Get health from each scheduler
        competitor_health = await self._get_competitor_health()
        marine_health = await self._get_marine_health()

        # Calculate totals
        total_jobs = 0
        healthy_jobs = 0
        warning_jobs = 0
        critical_jobs = 0

        for health in [competitor_health, marine_health]:
            if health:
                total_jobs += health.job_count
                healthy_jobs += health.healthy_jobs
                warning_jobs += health.warning_jobs
                critical_jobs += health.critical_jobs

        # Get stale and failed job counts
        stale_jobs = await self._count_stale_jobs()
        failed_jobs_24h = await self._count_failed_jobs_24h()

        # Generate alerts
        if competitor_health and not competitor_health.is_running:
            alerts.append("CRITICAL: Competitor Intel scheduler not running")
        if marine_health and not marine_health.is_running:
            alerts.append("CRITICAL: Marine Intel scheduler not running")
        if stale_jobs > 0:
            alerts.append(f"WARNING: {stale_jobs} stale job(s) detected")
        if failed_jobs_24h > 0:
            alerts.append(f"WARNING: {failed_jobs_24h} job failure(s) in last 24 hours")
        if critical_jobs > 0:
            alerts.append(f"CRITICAL: {critical_jobs} job(s) in critical state")

        # Determine overall health
        if critical_jobs > 0 or stale_jobs > 2 or failed_jobs_24h > 3:
            overall_health = JobHealth.CRITICAL
        elif warning_jobs > 0 or stale_jobs > 0 or failed_jobs_24h > 0:
            overall_health = JobHealth.WARNING
        elif total_jobs == 0:
            overall_health = JobHealth.UNKNOWN
        else:
            overall_health = JobHealth.HEALTHY

        self._last_check = now

        return WatchdogHealth(
            overall_health=overall_health,
            competitor_intel=competitor_health,
            marine_intel=marine_health,
            total_jobs=total_jobs,
            healthy_jobs=healthy_jobs,
            warning_jobs=warning_jobs,
            critical_jobs=critical_jobs,
            stale_jobs=stale_jobs,
            failed_jobs_24h=failed_jobs_24h,
            timestamp=now,
            alerts=alerts,
        )

    async def get_all_job_statuses(self) -> list[JobStatus]:
        """
        Get status of all scheduled jobs.

        Returns:
            List of JobStatus for all jobs
        """
        jobs: list[JobStatus] = []

        # Get competitor intel jobs
        competitor_jobs = await self._get_competitor_job_statuses()
        jobs.extend(competitor_jobs)

        # Get marine intel jobs
        marine_jobs = await self._get_marine_job_statuses()
        jobs.extend(marine_jobs)

        return jobs

    async def get_job_history(
        self,
        scheduler: Optional[SchedulerType] = None,
        job_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get recent job execution history.

        Args:
            scheduler: Filter by scheduler type
            job_type: Filter by job type
            limit: Maximum number of records

        Returns:
            List of job execution records
        """
        history: list[dict[str, Any]] = []

        if scheduler is None or scheduler == SchedulerType.COMPETITOR_INTEL:
            competitor_history = await self._get_competitor_job_history(job_type, limit)
            history.extend(competitor_history)

        if scheduler is None or scheduler == SchedulerType.MARINE_INTEL:
            marine_history = await self._get_marine_job_history(job_type, limit)
            history.extend(marine_history)

        # Sort by started_at descending
        history.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        return history[:limit]

    async def cleanup_stale_jobs(self) -> dict[str, int]:
        """
        Clean up stale jobs across all schedulers.

        Returns:
            Dictionary with cleanup counts per scheduler
        """
        results = {
            "competitor_intel": 0,
            "marine_intel": 0,
        }

        # Cleanup competitor intel stale jobs
        try:
            from lead_to_cash.services.competitor_intel import get_competitor_db

            db = get_competitor_db()
            if db and hasattr(db, "cleanup_stale_jobs"):
                results["competitor_intel"] = await db.cleanup_stale_jobs(
                    stale_minutes=60
                )
        except Exception as e:
            logger.warning(f"Competitor intel cleanup failed: {e}")

        # Cleanup marine intel stale jobs
        try:
            from lead_to_cash.services.marine_intel import get_marine_intel_db

            db = get_marine_intel_db()
            if db:
                results["marine_intel"] = await db.cleanup_stale_jobs(stale_minutes=60)
        except Exception as e:
            logger.warning(f"Marine intel cleanup failed: {e}")

        total = sum(results.values())
        if total > 0:
            logger.info(f"Cleaned up {total} stale job(s): {results}")

        return results

    # -------------------------------------------------------------------------
    # Competitor Intel Methods
    # -------------------------------------------------------------------------

    async def _get_competitor_health(self) -> Optional[SchedulerHealth]:
        """Get competitor intel scheduler health."""
        try:
            from lead_to_cash.services.competitor_intel import get_scheduler_health

            health_data = get_scheduler_health()

            # Count job health states
            jobs = health_data.get("jobs", [])
            healthy = 0
            warning = 0
            critical = 0

            for job in jobs:
                job_health = self._assess_job_health_from_scheduler(job)
                if job_health == JobHealth.HEALTHY:
                    healthy += 1
                elif job_health == JobHealth.WARNING:
                    warning += 1
                else:
                    critical += 1

            is_running = health_data.get("is_running", False)
            overall = (
                JobHealth.HEALTHY
                if is_running and critical == 0
                else (JobHealth.WARNING if warning > 0 else JobHealth.CRITICAL)
            )

            return SchedulerHealth(
                scheduler=SchedulerType.COMPETITOR_INTEL,
                is_running=is_running,
                job_count=health_data.get("job_count", 0),
                healthy_jobs=healthy,
                warning_jobs=warning,
                critical_jobs=critical,
                last_check=datetime.now(timezone.utc),
                health=overall,
                details=health_data,
            )

        except Exception as e:
            logger.warning(f"Failed to get competitor scheduler health: {e}")
            return SchedulerHealth(
                scheduler=SchedulerType.COMPETITOR_INTEL,
                is_running=False,
                job_count=0,
                healthy_jobs=0,
                warning_jobs=0,
                critical_jobs=0,
                last_check=datetime.now(timezone.utc),
                health=JobHealth.UNKNOWN,
                details={"error": str(e)},
            )

    async def _get_competitor_job_statuses(self) -> list[JobStatus]:
        """Get status of all competitor intel jobs."""
        jobs: list[JobStatus] = []

        try:
            from lead_to_cash.services.competitor_intel import get_scheduler_health

            health_data = get_scheduler_health()
            scheduler_jobs = health_data.get("jobs", [])

            # Get job history from database for run counts
            history = await self._get_competitor_job_history(None, 100)
            job_stats = self._calculate_job_stats(history)

            for job in scheduler_jobs:
                job_id = job.get("id", "unknown")
                stats = job_stats.get(job_id, {})

                next_run = job.get("next_run_time")
                if isinstance(next_run, str):
                    try:
                        next_run = datetime.fromisoformat(
                            next_run.replace("Z", "+00:00")
                        )
                    except ValueError:
                        next_run = None

                health, reason = self._assess_job_health(
                    last_run=stats.get("last_run"),
                    last_status=stats.get("last_status"),
                    failure_rate=stats.get("failure_rate", 0),
                    is_daily=True,
                )

                jobs.append(
                    JobStatus(
                        job_id=job_id,
                        job_name=job.get("name", job_id),
                        scheduler=SchedulerType.COMPETITOR_INTEL,
                        is_scheduled=True,
                        next_run=next_run,
                        last_run=stats.get("last_run"),
                        last_status=stats.get("last_status"),
                        last_duration_seconds=stats.get("last_duration"),
                        run_count=stats.get("run_count", 0),
                        success_count=stats.get("success_count", 0),
                        failure_count=stats.get("failure_count", 0),
                        health=health,
                        health_reason=reason,
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to get competitor job statuses: {e}")

        return jobs

    async def _get_competitor_job_history(
        self, job_type: Optional[str], limit: int
    ) -> list[dict[str, Any]]:
        """Get competitor intel job execution history."""
        try:
            from lead_to_cash.services.competitor_intel import get_competitor_db

            db = get_competitor_db()
            if db and hasattr(db, "list_jobs"):
                jobs = await db.list_jobs(job_type=job_type, limit=limit)
                return [
                    {
                        "scheduler": "competitor_intel",
                        "job_id": j.id,
                        "job_type": j.job_type,
                        "status": j.status,
                        "started_at": (
                            j.started_at.isoformat() if j.started_at else None
                        ),
                        "completed_at": (
                            j.completed_at.isoformat() if j.completed_at else None
                        ),
                        "documents_processed": getattr(j, "documents_processed", 0),
                        "chunks_created": getattr(j, "chunks_created", 0),
                        "error_message": getattr(j, "error_message", None),
                    }
                    for j in jobs
                ]
        except Exception as e:
            logger.warning(f"Failed to get competitor job history: {e}")

        return []

    # -------------------------------------------------------------------------
    # Marine Intel Methods
    # -------------------------------------------------------------------------

    async def _get_marine_health(self) -> Optional[SchedulerHealth]:
        """Get marine intel scheduler health."""
        try:
            from lead_to_cash.services.marine_intel.scheduler import (
                get_marine_scheduler,
            )

            scheduler = get_marine_scheduler()
            is_running = scheduler.running if scheduler else False
            jobs = scheduler.get_jobs() if scheduler else []

            # Count job health states
            healthy = 0
            warning = 0
            critical = 0

            for job in jobs:
                job_info = {
                    "id": job.id,
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                }
                job_health = self._assess_job_health_from_scheduler(job_info)
                if job_health == JobHealth.HEALTHY:
                    healthy += 1
                elif job_health == JobHealth.WARNING:
                    warning += 1
                else:
                    critical += 1

            overall = (
                JobHealth.HEALTHY
                if is_running and critical == 0
                else (JobHealth.WARNING if warning > 0 else JobHealth.CRITICAL)
            )

            return SchedulerHealth(
                scheduler=SchedulerType.MARINE_INTEL,
                is_running=is_running,
                job_count=len(jobs),
                healthy_jobs=healthy,
                warning_jobs=warning,
                critical_jobs=critical,
                last_check=datetime.now(timezone.utc),
                health=overall,
                details={
                    "jobs": [
                        {
                            "id": j.id,
                            "name": j.name,
                            "next_run": (
                                j.next_run_time.isoformat() if j.next_run_time else None
                            ),
                        }
                        for j in jobs
                    ]
                },
            )

        except Exception as e:
            logger.warning(f"Failed to get marine scheduler health: {e}")
            return SchedulerHealth(
                scheduler=SchedulerType.MARINE_INTEL,
                is_running=False,
                job_count=0,
                healthy_jobs=0,
                warning_jobs=0,
                critical_jobs=0,
                last_check=datetime.now(timezone.utc),
                health=JobHealth.UNKNOWN,
                details={"error": str(e)},
            )

    async def _get_marine_job_statuses(self) -> list[JobStatus]:
        """Get status of all marine intel jobs."""
        jobs: list[JobStatus] = []

        try:
            from lead_to_cash.services.marine_intel.scheduler import (
                get_marine_scheduler,
            )

            scheduler = get_marine_scheduler()
            scheduler_jobs = scheduler.get_jobs() if scheduler else []

            # Get job history from database
            history = await self._get_marine_job_history(None, 100)
            job_stats = self._calculate_job_stats(history)

            for job in scheduler_jobs:
                job_id = job.id
                stats = job_stats.get(job_id, {})

                next_run = job.next_run_time

                health, reason = self._assess_job_health(
                    last_run=stats.get("last_run"),
                    last_status=stats.get("last_status"),
                    failure_rate=stats.get("failure_rate", 0),
                    is_daily="daily" in job_id.lower(),
                )

                jobs.append(
                    JobStatus(
                        job_id=job_id,
                        job_name=job.name,
                        scheduler=SchedulerType.MARINE_INTEL,
                        is_scheduled=True,
                        next_run=next_run,
                        last_run=stats.get("last_run"),
                        last_status=stats.get("last_status"),
                        last_duration_seconds=stats.get("last_duration"),
                        run_count=stats.get("run_count", 0),
                        success_count=stats.get("success_count", 0),
                        failure_count=stats.get("failure_count", 0),
                        health=health,
                        health_reason=reason,
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to get marine job statuses: {e}")

        return jobs

    async def _get_marine_job_history(
        self, job_type: Optional[str], limit: int
    ) -> list[dict[str, Any]]:
        """Get marine intel job execution history."""
        try:
            from lead_to_cash.services.marine_intel import get_marine_intel_db

            db = get_marine_intel_db()
            if db:
                jobs = await db.list_jobs(job_type=job_type, limit=limit)
                return [
                    {
                        "scheduler": "marine_intel",
                        "job_id": j.id,
                        "job_type": j.job_type,
                        "status": j.status,
                        "started_at": (
                            j.started_at.isoformat() if j.started_at else None
                        ),
                        "completed_at": (
                            j.completed_at.isoformat() if j.completed_at else None
                        ),
                        "queries_executed": getattr(j, "queries_executed", 0),
                        "articles_processed": getattr(j, "articles_processed", 0),
                        "opportunities_found": getattr(j, "opportunities_found", 0),
                        "error_message": getattr(j, "error_message", None),
                    }
                    for j in jobs
                ]
        except Exception as e:
            logger.warning(f"Failed to get marine job history: {e}")

        return []

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _count_stale_jobs(self) -> int:
        """Count jobs that haven't run in expected timeframe."""
        count = 0
        now = datetime.now(timezone.utc)

        jobs = await self.get_all_job_statuses()
        for job in jobs:
            if job.last_run:
                age = now - job.last_run
                # Daily jobs should run within 25 hours
                if "daily" in job.job_id.lower() and age > timedelta(hours=25):
                    count += 1
                # Weekly jobs should run within 8 days
                elif "weekly" in job.job_id.lower() and age > timedelta(days=8):
                    count += 1

        return count

    async def _count_failed_jobs_24h(self) -> int:
        """Count job failures in last 24 hours."""
        count = 0
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        history = await self.get_job_history(limit=100)
        for job in history:
            started_at = job.get("started_at")
            if started_at:
                try:
                    job_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    if job_time > cutoff and job.get("status") == "failed":
                        count += 1
                except ValueError:
                    pass

        return count

    def _assess_job_health_from_scheduler(self, job: dict) -> JobHealth:
        """Assess job health from scheduler info."""
        next_run = job.get("next_run_time")
        if next_run is None:
            return JobHealth.WARNING
        return JobHealth.HEALTHY

    def _assess_job_health(
        self,
        last_run: Optional[datetime],
        last_status: Optional[str],
        failure_rate: float,
        is_daily: bool,
    ) -> tuple[JobHealth, str]:
        """
        Assess job health based on run history.

        Returns:
            Tuple of (health status, reason)
        """
        now = datetime.now(timezone.utc)

        # Check if job has never run
        if last_run is None:
            return JobHealth.WARNING, "Job has never run"

        # Check if job is stale
        age = now - last_run
        if is_daily and age > timedelta(hours=self.STALE_JOB_HOURS):
            return (
                JobHealth.CRITICAL,
                f"Job stale: last run {age.total_seconds()/3600:.1f}h ago",
            )

        # Check last status
        if last_status == "failed":
            return JobHealth.WARNING, "Last run failed"

        # Check failure rate
        if failure_rate >= self.CRITICAL_FAILURE_RATE:
            return (
                JobHealth.CRITICAL,
                f"High failure rate: {failure_rate*100:.0f}%",
            )
        if failure_rate >= self.WARNING_FAILURE_RATE:
            return (
                JobHealth.WARNING,
                f"Elevated failure rate: {failure_rate*100:.0f}%",
            )

        return JobHealth.HEALTHY, "Job running normally"

    def _calculate_job_stats(
        self, history: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Calculate statistics per job type from history."""
        stats: dict[str, dict[str, Any]] = {}

        for job in history:
            job_type = job.get("job_type", "unknown")

            if job_type not in stats:
                stats[job_type] = {
                    "run_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_run": None,
                    "last_status": None,
                    "last_duration": None,
                }

            stats[job_type]["run_count"] += 1

            if job.get("status") == "completed":
                stats[job_type]["success_count"] += 1
            elif job.get("status") == "failed":
                stats[job_type]["failure_count"] += 1

            # Track most recent run
            started_at = job.get("started_at")
            if started_at:
                try:
                    run_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    if (
                        stats[job_type]["last_run"] is None
                        or run_time > stats[job_type]["last_run"]
                    ):
                        stats[job_type]["last_run"] = run_time
                        stats[job_type]["last_status"] = job.get("status")

                        # Calculate duration if completed
                        completed_at = job.get("completed_at")
                        if completed_at:
                            try:
                                end_time = datetime.fromisoformat(
                                    completed_at.replace("Z", "+00:00")
                                )
                                stats[job_type]["last_duration"] = (
                                    end_time - run_time
                                ).total_seconds()
                            except ValueError:
                                pass
                except ValueError:
                    pass

        # Calculate failure rates
        for job_type, s in stats.items():
            if s["run_count"] > 0:
                s["failure_rate"] = s["failure_count"] / s["run_count"]
            else:
                s["failure_rate"] = 0

        return stats


# =============================================================================
# Singleton Instance
# =============================================================================

_watchdog: Optional[SchedulerWatchdog] = None


def get_watchdog() -> SchedulerWatchdog:
    """Get the singleton watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = SchedulerWatchdog()
    return _watchdog


async def initialize_watchdog() -> SchedulerWatchdog:
    """Initialize and return the watchdog instance."""
    watchdog = get_watchdog()
    await watchdog.initialize()
    return watchdog
