"""
Prometheus Metrics for Knowledge Base

Exposes metrics for monitoring:
- Circuit breaker state and transitions
- Rate limiter requests and rejections
- API call latencies
- Database connection pool stats
- Embedding service stats

Usage:
    from lead_to_cash.services.knowledge_base.metrics import (
        KBMetrics,
        get_kb_metrics,
    )

    metrics = get_kb_metrics()

    # Record circuit breaker state change
    metrics.record_circuit_breaker_state("kb_embedding", "OPEN")

    # Record API call
    with metrics.api_call_timer("openai", "embeddings"):
        response = await client.embeddings.create(...)

    # Record rate limit
    metrics.record_rate_limit_check("kb_embedding", allowed=True)

    # Get metrics for /metrics endpoint
    output = metrics.export()
"""

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Generator, List, Optional

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Counter:
    """Simple counter metric."""

    name: str
    help: str
    labels: List[str] = field(default_factory=list)
    _values: Dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _lock: Lock = field(default_factory=Lock)

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment counter."""
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[label_key] += value

    def get(self, **labels) -> float:
        """Get counter value."""
        label_key = tuple(sorted(labels.items()))
        return self._values.get(label_key, 0.0)

    def export(self) -> str:
        """Export in Prometheus format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        for label_key, value in self._values.items():
            if label_key:
                labels_str = ",".join(f'{k}="{v}"' for k, v in label_key)
                lines.append(f"{self.name}{{{labels_str}}} {value}")
            else:
                lines.append(f"{self.name} {value}")
        return "\n".join(lines)


@dataclass
class Gauge:
    """Simple gauge metric."""

    name: str
    help: str
    labels: List[str] = field(default_factory=list)
    _values: Dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _lock: Lock = field(default_factory=Lock)

    def set(self, value: float, **labels) -> None:
        """Set gauge value."""
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[label_key] = value

    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment gauge."""
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[label_key] += value

    def dec(self, value: float = 1.0, **labels) -> None:
        """Decrement gauge."""
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[label_key] -= value

    def get(self, **labels) -> float:
        """Get gauge value."""
        label_key = tuple(sorted(labels.items()))
        return self._values.get(label_key, 0.0)

    def export(self) -> str:
        """Export in Prometheus format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} gauge"]
        for label_key, value in self._values.items():
            if label_key:
                labels_str = ",".join(f'{k}="{v}"' for k, v in label_key)
                lines.append(f"{self.name}{{{labels_str}}} {value}")
            else:
                lines.append(f"{self.name} {value}")
        return "\n".join(lines)


@dataclass
class Histogram:
    """Simple histogram metric with predefined buckets."""

    name: str
    help: str
    labels: List[str] = field(default_factory=list)
    buckets: List[float] = field(
        default_factory=lambda: [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]
    )
    _counts: Dict[tuple, Dict[float, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    _sums: Dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _totals: Dict[tuple, int] = field(default_factory=lambda: defaultdict(int))
    _lock: Lock = field(default_factory=Lock)

    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._sums[label_key] += value
            self._totals[label_key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[label_key][bucket] += 1

    def export(self) -> str:
        """Export in Prometheus format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]

        for label_key in set(list(self._counts.keys()) + list(self._sums.keys())):
            labels_str = (
                ",".join(f'{k}="{v}"' for k, v in label_key) if label_key else ""
            )
            prefix = f"{self.name}{{{labels_str}," if labels_str else f"{self.name}{{"

            # Bucket counts (cumulative)
            cumulative = 0
            for bucket in self.buckets:
                cumulative += self._counts[label_key].get(bucket, 0)
                lines.append(f'{prefix}le="{bucket}"}} {cumulative}')
            lines.append(f'{prefix}le="+Inf"}} {self._totals[label_key]}')

            # Sum and count
            if labels_str:
                lines.append(f"{self.name}_sum{{{labels_str}}} {self._sums[label_key]}")
                lines.append(
                    f"{self.name}_count{{{labels_str}}} {self._totals[label_key]}"
                )
            else:
                lines.append(f"{self.name}_sum {self._sums[label_key]}")
                lines.append(f"{self.name}_count {self._totals[label_key]}")

        return "\n".join(lines)


class KBMetrics:
    """
    Prometheus metrics for Knowledge Base service.

    Metrics exposed:
    - kb_circuit_breaker_state: Current state (0=closed, 1=open, 2=half_open)
    - kb_circuit_breaker_transitions_total: State transition count
    - kb_rate_limit_requests_total: Rate limit check count
    - kb_rate_limit_rejections_total: Rate limit rejection count
    - kb_api_calls_total: API call count by service/operation
    - kb_api_call_duration_seconds: API call latency histogram
    - kb_db_pool_connections: Database pool connection count
    - kb_embeddings_generated_total: Embedding generation count
    - kb_entities_resolved_total: Entity resolution count
    - kb_articles_scored_total: Article scoring count
    """

    # Circuit breaker state values
    CB_STATE_CLOSED = 0
    CB_STATE_OPEN = 1
    CB_STATE_HALF_OPEN = 2

    def __init__(self):
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            name="kb_circuit_breaker_state",
            help="Current circuit breaker state (0=closed, 1=open, 2=half_open)",
            labels=["name"],
        )
        self.circuit_breaker_transitions = Counter(
            name="kb_circuit_breaker_transitions_total",
            help="Total circuit breaker state transitions",
            labels=["name", "from_state", "to_state"],
        )

        # Rate limiter metrics
        self.rate_limit_requests = Counter(
            name="kb_rate_limit_requests_total",
            help="Total rate limit check requests",
            labels=["limiter"],
        )
        self.rate_limit_rejections = Counter(
            name="kb_rate_limit_rejections_total",
            help="Total rate limit rejections",
            labels=["limiter"],
        )

        # API call metrics
        self.api_calls = Counter(
            name="kb_api_calls_total",
            help="Total API calls",
            labels=["service", "operation", "status"],
        )
        self.api_call_duration = Histogram(
            name="kb_api_call_duration_seconds",
            help="API call duration in seconds",
            labels=["service", "operation"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        )

        # Database metrics
        self.db_pool_connections = Gauge(
            name="kb_db_pool_connections",
            help="Database connection pool stats",
            labels=["state"],  # active, idle, total
        )
        self.db_query_duration = Histogram(
            name="kb_db_query_duration_seconds",
            help="Database query duration in seconds",
            labels=["operation"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Business metrics
        self.embeddings_generated = Counter(
            name="kb_embeddings_generated_total",
            help="Total embeddings generated",
            labels=["model"],
        )
        self.entities_resolved = Counter(
            name="kb_entities_resolved_total",
            help="Total entities resolved",
            labels=["match_type"],  # exact, alias, fuzzy, semantic, unresolved
        )
        self.articles_scored = Counter(
            name="kb_articles_scored_total",
            help="Total articles scored",
            labels=["classification"],  # high_priority, monitor, ignore
        )

        # Error metrics
        self.errors = Counter(
            name="kb_errors_total",
            help="Total errors by type",
            labels=["service", "error_type"],
        )

        # Cache metrics
        self.cache_hits = Counter(
            name="kb_cache_hits_total",
            help="Total cache hits",
            labels=["cache_name"],
        )
        self.cache_misses = Counter(
            name="kb_cache_misses_total",
            help="Total cache misses",
            labels=["cache_name"],
        )
        self.cache_size = Gauge(
            name="kb_cache_size",
            help="Current cache size",
            labels=["cache_name"],
        )
        self.cache_evictions = Counter(
            name="kb_cache_evictions_total",
            help="Total cache evictions",
            labels=["cache_name"],
        )

        # =================================================================
        # Vector search and embedding observability metrics
        # =================================================================

        # Vector search latency - tracks pgvector similarity search duration
        self.vector_search_duration = Histogram(
            name="kb_vector_search_duration_seconds",
            help="Vector similarity search duration in seconds",
            labels=[
                "entity_type",
                "index_type",
            ],  # entity_type: manufacturer, model, alias
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Embedding generation latency - tracks OpenAI API call duration
        self.embedding_latency = Histogram(
            name="kb_embedding_latency_seconds",
            help="OpenAI embedding generation latency in seconds",
            labels=["model", "batch_size_bucket"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        # Cache hit ratio - updated periodically for dashboards
        self.cache_hit_ratio = Gauge(
            name="kb_cache_hit_ratio",
            help="Cache hit ratio (0.0-1.0)",
            labels=["cache_name"],
        )

        # Similarity score distribution - tracks quality of vector matches
        self.similarity_scores = Histogram(
            name="kb_similarity_score_distribution",
            help="Distribution of similarity scores from vector search",
            labels=["entity_type", "match_type"],
            buckets=[0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
        )

        # Track last state for transition detection
        self._last_cb_state: Dict[str, str] = {}

    def record_circuit_breaker_state(self, name: str, state: str) -> None:
        """
        Record circuit breaker state.

        Args:
            name: Circuit breaker name
            state: Current state (CLOSED, OPEN, HALF_OPEN)
        """
        state_value = {
            "CLOSED": self.CB_STATE_CLOSED,
            "OPEN": self.CB_STATE_OPEN,
            "HALF_OPEN": self.CB_STATE_HALF_OPEN,
        }.get(state, self.CB_STATE_CLOSED)

        self.circuit_breaker_state.set(state_value, name=name)

        # Track transitions
        last_state = self._last_cb_state.get(name)
        if last_state and last_state != state:
            self.circuit_breaker_transitions.inc(
                name=name, from_state=last_state, to_state=state
            )
            logger.info(f"Circuit breaker {name} transition: {last_state} -> {state}")

        self._last_cb_state[name] = state

    def record_rate_limit_check(self, limiter: str, allowed: bool) -> None:
        """
        Record rate limit check.

        Args:
            limiter: Rate limiter name
            allowed: Whether request was allowed
        """
        self.rate_limit_requests.inc(limiter=limiter)
        if not allowed:
            self.rate_limit_rejections.inc(limiter=limiter)

    @contextmanager
    def api_call_timer(
        self, service: str, operation: str
    ) -> Generator[None, None, None]:
        """
        Context manager to time API calls.

        Args:
            service: Service name (e.g., "openai", "database")
            operation: Operation name (e.g., "embeddings", "query")

        Yields:
            None

        Example:
            with metrics.api_call_timer("openai", "embeddings"):
                response = await client.embeddings.create(...)
        """
        start = time.monotonic()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.monotonic() - start
            self.api_calls.inc(service=service, operation=operation, status=status)
            self.api_call_duration.observe(
                duration, service=service, operation=operation
            )

    def record_api_call(
        self, service: str, operation: str, duration: float, success: bool = True
    ) -> None:
        """
        Record an API call directly.

        Args:
            service: Service name
            operation: Operation name
            duration: Duration in seconds
            success: Whether call succeeded
        """
        status = "success" if success else "error"
        self.api_calls.inc(service=service, operation=operation, status=status)
        self.api_call_duration.observe(duration, service=service, operation=operation)

    def record_db_pool_stats(self, active: int, idle: int, total: int) -> None:
        """
        Record database pool statistics.

        Args:
            active: Active connections
            idle: Idle connections
            total: Total connections
        """
        self.db_pool_connections.set(active, state="active")
        self.db_pool_connections.set(idle, state="idle")
        self.db_pool_connections.set(total, state="total")

    def record_embedding_generated(self, model: str, count: int = 1) -> None:
        """Record embedding generation."""
        self.embeddings_generated.inc(count, model=model)

    def record_entity_resolved(self, match_type: str) -> None:
        """Record entity resolution."""
        self.entities_resolved.inc(match_type=match_type)

    def record_article_scored(self, classification: str) -> None:
        """Record article scoring."""
        self.articles_scored.inc(classification=classification)

    def record_error(self, service: str, error_type: str) -> None:
        """Record an error."""
        self.errors.inc(service=service, error_type=error_type)

    def record_cache_hit(self, cache_name: str) -> None:
        """Record a cache hit."""
        self.cache_hits.inc(cache_name=cache_name)

    def record_cache_miss(self, cache_name: str) -> None:
        """Record a cache miss."""
        self.cache_misses.inc(cache_name=cache_name)

    def record_cache_size(self, cache_name: str, size: int) -> None:
        """Record current cache size."""
        self.cache_size.set(size, cache_name=cache_name)

    def record_cache_eviction(self, cache_name: str, count: int = 1) -> None:
        """Record cache eviction."""
        self.cache_evictions.inc(count, cache_name=cache_name)

    # =================================================================
    # Vector search and embedding observability methods
    # =================================================================

    def record_vector_search(
        self, duration: float, entity_type: str, index_type: str = "hnsw"
    ) -> None:
        """
        Record vector similarity search timing.

        Args:
            duration: Search duration in seconds
            entity_type: Type of entity being searched (manufacturer, model, alias, all)
            index_type: Index type used (hnsw, exact)
        """
        self.vector_search_duration.observe(
            duration, entity_type=entity_type, index_type=index_type
        )

    def record_embedding_latency(
        self, duration: float, model: str, batch_size: int
    ) -> None:
        """
        Record embedding generation latency.

        Args:
            duration: Generation duration in seconds
            model: Embedding model name (e.g., text-embedding-3-small)
            batch_size: Number of texts embedded in this call
        """
        # Bucket batch sizes: 1, 10, 50, 100, 500+
        if batch_size == 1:
            bucket = "1"
        elif batch_size <= 10:
            bucket = "10"
        elif batch_size <= 50:
            bucket = "50"
        elif batch_size <= 100:
            bucket = "100"
        else:
            bucket = "500+"

        self.embedding_latency.observe(duration, model=model, batch_size_bucket=bucket)

    def update_cache_hit_ratio(self, cache_name: str, hit_ratio: float) -> None:
        """
        Update cache hit ratio gauge.

        Args:
            cache_name: Name of the cache
            hit_ratio: Hit ratio (0.0 to 1.0)
        """
        self.cache_hit_ratio.set(hit_ratio, cache_name=cache_name)

    def record_similarity_score(
        self, score: float, entity_type: str, match_type: str
    ) -> None:
        """
        Record similarity score for distribution tracking.

        Args:
            score: Similarity score (0.0 to 1.0)
            entity_type: Type of entity matched
            match_type: Type of match (semantic, fuzzy)
        """
        self.similarity_scores.observe(
            score, entity_type=entity_type, match_type=match_type
        )

    def export(self) -> str:
        """
        Export all metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        metrics = [
            self.circuit_breaker_state,
            self.circuit_breaker_transitions,
            self.rate_limit_requests,
            self.rate_limit_rejections,
            self.api_calls,
            self.api_call_duration,
            self.db_pool_connections,
            self.db_query_duration,
            self.embeddings_generated,
            self.entities_resolved,
            self.articles_scored,
            self.errors,
            self.cache_hits,
            self.cache_misses,
            self.cache_size,
            self.cache_evictions,
            # Vector search and embedding observability
            self.vector_search_duration,
            self.embedding_latency,
            self.cache_hit_ratio,
            self.similarity_scores,
        ]

        output = []
        for metric in metrics:
            exported = metric.export()
            if exported.strip():
                output.append(exported)

        return "\n\n".join(output) + "\n"

    def get_stats(self) -> Dict[str, Any]:
        """
        Get metrics as a dictionary (for JSON endpoints).

        Returns:
            Dictionary of metric values
        """
        return {
            "circuit_breakers": {
                name: {
                    "state": state,
                    "state_value": self.circuit_breaker_state.get(name=name),
                }
                for name, state in self._last_cb_state.items()
            },
            "rate_limiters": {
                "requests": dict(self.rate_limit_requests._values),
                "rejections": dict(self.rate_limit_rejections._values),
            },
            "api_calls": {
                "total": dict(self.api_calls._values),
            },
            "database": {
                "pool_active": self.db_pool_connections.get(state="active"),
                "pool_idle": self.db_pool_connections.get(state="idle"),
                "pool_total": self.db_pool_connections.get(state="total"),
            },
            "business": {
                "embeddings_generated": dict(self.embeddings_generated._values),
                "entities_resolved": dict(self.entities_resolved._values),
                "articles_scored": dict(self.articles_scored._values),
            },
            "errors": dict(self.errors._values),
            "vector_search": {
                "duration_observations": sum(
                    self.vector_search_duration._totals.values()
                ),
            },
            "embedding_latency": {
                "observations": sum(self.embedding_latency._totals.values()),
            },
            "cache_hit_ratios": dict(self.cache_hit_ratio._values),
            "similarity_scores": {
                "observations": sum(self.similarity_scores._totals.values()),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_kb_metrics: Optional[KBMetrics] = None


def get_kb_metrics() -> KBMetrics:
    """Get singleton metrics instance."""
    global _kb_metrics
    if _kb_metrics is None:
        _kb_metrics = KBMetrics()
    return _kb_metrics
