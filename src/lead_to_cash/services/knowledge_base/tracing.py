"""
Marine Engine Knowledge Base - Distributed Tracing

OpenTelemetry integration for distributed tracing across KB operations.
Enables end-to-end visibility into request flows and performance analysis.

Features:
- Automatic span creation for key operations
- Trace context propagation across services
- Integration with common observability platforms (Jaeger, Zipkin, OTLP)
- Sampling support for high-volume environments

Usage:
    from lead_to_cash.services.knowledge_base.tracing import (
        KBTracer,
        get_kb_tracer,
        trace_operation,
    )

    # Initialize tracer
    tracer = get_kb_tracer()
    tracer.configure(service_name="kb-service", endpoint="http://jaeger:4317")

    # Use decorator
    @trace_operation("resolve_entity")
    async def resolve_entity(text: str):
        ...

    # Manual spans
    async with tracer.span("search_entities", attributes={"query": query}):
        ...
"""

import asyncio
import functools
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Optional, TypeVar

from lead_to_cash.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import OpenTelemetry (optional dependency)
# Declare variables with Any type to satisfy mypy
trace: Any = None
TracerProvider: Any = None
BatchSpanProcessor: Any = None
Resource: Any = None
ResourceAttributes: Any = None
Status: Any = None
StatusCode: Any = None
SpanKind: Any = None
OTEL_AVAILABLE = False

try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.resources import Resource as _OtelResource
    from opentelemetry.sdk.trace import TracerProvider as _OtelTracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor as _OtelBatchSpanProcessor,
    )
    from opentelemetry.semconv.resource import (
        ResourceAttributes as _OtelResourceAttributes,
    )
    from opentelemetry.trace import SpanKind as _OtelSpanKind
    from opentelemetry.trace import Status as _OtelStatus
    from opentelemetry.trace import StatusCode as _OtelStatusCode

    OTEL_AVAILABLE = True
    trace = _otel_trace
    TracerProvider = _OtelTracerProvider
    BatchSpanProcessor = _OtelBatchSpanProcessor
    Resource = _OtelResource
    ResourceAttributes = _OtelResourceAttributes
    Status = _OtelStatus
    StatusCode = _OtelStatusCode
    SpanKind = _OtelSpanKind
except ImportError:
    pass  # Variables already set to None above


T = TypeVar("T", bound=Callable)


class NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def __init__(self, name: str = "", **kwargs):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: Optional[str] = None) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass

    def end(self) -> None:
        pass


class KBTracer:
    """
    Distributed tracer for Knowledge Base operations.

    Wraps OpenTelemetry SDK with KB-specific convenience methods.
    Falls back to no-op implementation if OTel is not available.
    """

    def __init__(
        self,
        service_name: str = "knowledge-base",
        service_version: str = "1.0.0",
    ):
        """
        Initialize tracer.

        Args:
            service_name: Name of the service for tracing
            service_version: Version of the service
        """
        self._service_name = service_name
        self._service_version = service_version
        self._configured = False
        self._tracer = None
        self._enabled = False

        # Statistics
        self._spans_created = 0
        self._spans_failed = 0

    def configure(
        self,
        endpoint: Optional[str] = None,
        exporter_type: str = "otlp",
        sampling_ratio: float = 1.0,
        enabled: bool = True,
    ) -> None:
        """
        Configure the tracer with an exporter.

        Args:
            endpoint: Trace collector endpoint (e.g., "http://jaeger:4317")
            exporter_type: Type of exporter ("otlp", "jaeger", "zipkin", "console")
            sampling_ratio: Fraction of traces to sample (0.0-1.0)
            enabled: Whether tracing is enabled
        """
        self._enabled = enabled

        if not enabled:
            logger.info("Distributed tracing disabled")
            return

        if not OTEL_AVAILABLE:
            logger.warning(
                "OpenTelemetry not installed. Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp"
            )
            return

        try:
            # Create resource with service info
            resource = Resource.create(
                {
                    ResourceAttributes.SERVICE_NAME: self._service_name,
                    ResourceAttributes.SERVICE_VERSION: self._service_version,
                }
            )

            # Create tracer provider with sampling
            from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

            sampler = TraceIdRatioBased(sampling_ratio)
            provider = TracerProvider(resource=resource, sampler=sampler)

            # Create exporter based on type
            exporter: Any = None
            if exporter_type == "otlp" and endpoint:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
            elif exporter_type == "jaeger" and endpoint:
                # Jaeger uses OTLP now
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
            elif exporter_type == "console":
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter

                exporter = ConsoleSpanExporter()

            if exporter:
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer instance
            self._tracer = trace.get_tracer(
                self._service_name,
                self._service_version,
            )

            self._configured = True
            logger.info(
                f"Distributed tracing configured: exporter={exporter_type}, "
                f"endpoint={endpoint}, sampling={sampling_ratio}"
            )

        except Exception as e:
            logger.error(f"Failed to configure tracing: {e}")
            self._configured = False

    @contextmanager
    def span(
        self,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[dict] = None,
    ):
        """
        Create a synchronous trace span.

        Args:
            name: Span name
            kind: Span kind (client, server, producer, consumer)
            attributes: Span attributes

        Yields:
            The span (or NoOpSpan if not configured)
        """
        if not self._enabled or not self._tracer:
            yield NoOpSpan(name)
            return

        try:
            span_kind = kind or SpanKind.INTERNAL
            with self._tracer.start_as_current_span(
                f"kb.{name}",
                kind=span_kind,
                attributes=attributes,
            ) as span:
                self._spans_created += 1
                yield span
        except Exception as e:
            self._spans_failed += 1
            logger.debug(f"Tracing error in span {name}: {e}")
            yield NoOpSpan(name)

    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[dict] = None,
    ):
        """
        Create an async trace span.

        Args:
            name: Span name
            kind: Span kind
            attributes: Span attributes

        Yields:
            The span (or NoOpSpan if not configured)
        """
        if not self._enabled or not self._tracer:
            yield NoOpSpan(name)
            return

        try:
            span_kind = kind or SpanKind.INTERNAL
            with self._tracer.start_as_current_span(
                f"kb.{name}",
                kind=span_kind,
                attributes=attributes,
            ) as span:
                self._spans_created += 1
                yield span
        except Exception as e:
            self._spans_failed += 1
            logger.debug(f"Tracing error in async span {name}: {e}")
            yield NoOpSpan(name)

    def get_stats(self) -> dict:
        """Get tracing statistics."""
        return {
            "enabled": self._enabled,
            "configured": self._configured,
            "otel_available": OTEL_AVAILABLE,
            "service_name": self._service_name,
            "spans_created": self._spans_created,
            "spans_failed": self._spans_failed,
        }


# =============================================================================
# DECORATOR FOR TRACING
# =============================================================================


def trace_operation(
    operation_name: str,
    extract_attributes: Optional[Callable[..., dict]] = None,
) -> Callable[[T], T]:
    """
    Decorator to trace a function/coroutine.

    Args:
        operation_name: Name for the trace span
        extract_attributes: Optional function to extract attributes from args

    Example:
        @trace_operation("resolve_entity")
        async def resolve_entity(text: str, entity_type: str):
            ...

        @trace_operation(
            "search",
            extract_attributes=lambda q, **_: {"query": q[:50]}
        )
        async def search(query: str, top_k: int = 10):
            ...
    """

    def decorator(func: T) -> T:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_kb_tracer()
            attributes = {}
            if extract_attributes:
                try:
                    attributes = extract_attributes(*args, **kwargs)
                except Exception:
                    pass

            async with tracer.async_span(operation_name, attributes=attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    if OTEL_AVAILABLE and hasattr(span, "set_status"):
                        span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if OTEL_AVAILABLE and hasattr(span, "record_exception"):
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    # Record error to Prometheus metrics
                    try:
                        from lead_to_cash.services.knowledge_base.metrics import (
                            get_kb_metrics,
                        )

                        get_kb_metrics().record_error(operation_name, type(e).__name__)
                    except Exception:
                        pass  # Don't fail if metrics unavailable
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_kb_tracer()
            attributes = {}
            if extract_attributes:
                try:
                    attributes = extract_attributes(*args, **kwargs)
                except Exception:
                    pass

            with tracer.span(operation_name, attributes=attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    if OTEL_AVAILABLE and hasattr(span, "set_status"):
                        span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    if OTEL_AVAILABLE and hasattr(span, "record_exception"):
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                    # Record error to Prometheus metrics
                    try:
                        from lead_to_cash.services.knowledge_base.metrics import (
                            get_kb_metrics,
                        )

                        get_kb_metrics().record_error(operation_name, type(e).__name__)
                    except Exception:
                        pass  # Don't fail if metrics unavailable
                    raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_kb_tracer: Optional[KBTracer] = None


def get_kb_tracer() -> KBTracer:
    """Get singleton tracer instance."""
    global _kb_tracer
    if _kb_tracer is None:
        _kb_tracer = KBTracer()
    return _kb_tracer


def configure_kb_tracing(
    endpoint: Optional[str] = None,
    exporter_type: str = "otlp",
    sampling_ratio: float = 1.0,
    enabled: bool = True,
) -> KBTracer:
    """
    Configure and return KB tracer.

    Args:
        endpoint: Trace collector endpoint
        exporter_type: Type of exporter
        sampling_ratio: Sampling ratio
        enabled: Whether tracing is enabled

    Returns:
        Configured tracer instance
    """
    tracer = get_kb_tracer()
    tracer.configure(
        endpoint=endpoint,
        exporter_type=exporter_type,
        sampling_ratio=sampling_ratio,
        enabled=enabled,
    )
    return tracer
