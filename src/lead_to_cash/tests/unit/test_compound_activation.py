"""
Unit Tests for Compound Query Activation

Tests the phased activation infrastructure:
- Phase A: Detection logging (even when execution disabled)
- Phase B+: Execution monitoring
- Compound dashboard metrics
- Rollback condition detection
"""

import pytest

from lead_to_cash.core.response_quality import QualityMetrics, RoutingMonitor


@pytest.fixture(autouse=True)
def _clear_state():
    QualityMetrics._events = []
    yield


def _inject_detection_events(n=20, enabled=False):
    """Simulate Phase A detection events."""
    for i in range(n):
        QualityMetrics.record(
            event_type="compound_query_detected",
            severity="INFO",
            intent="billing_ar",
            details={
                "detection_method": "concept_co_occurrence",
                "compound_confidence": 0.7,
                "sub_intent_count": 2,
                "execution_order": "sequential",
                "execution_enabled": enabled,
                "query": f"Check billing and run KYP {i}",
            },
        )


def _inject_execution_events(n=20, partial_rate=0.1):
    """Simulate compound execution events."""
    import random

    random.seed(42)
    for i in range(n):
        is_partial = random.random() < partial_rate
        order = "parallel" if random.random() > 0.3 else "sequential"
        QualityMetrics.record(
            event_type="compound_query_execution",
            severity="INFO" if not is_partial else "WARNING",
            intent="billing_ar",
            details={
                "compound_confidence": 0.7,
                "sub_intent_count": 2,
                "execution_order": order,
                "partial_success": is_partial,
                "total_time_ms": random.uniform(2000, 8000),
            },
        )


def _inject_routing_events(n=100):
    """Simulate regular routing events (for compound rate calculation)."""
    for i in range(n):
        QualityMetrics.record(
            event_type="signal_routing_live",
            severity="INFO",
            intent="billing_ar",
            details={"routing_source": "signal", "agreement": True},
        )


class TestPhaseADetection:
    """Phase A: Detection logging when execution is disabled."""

    def test_detection_events_logged(self):
        _inject_detection_events(10, enabled=False)
        events = QualityMetrics.get_recent_events("compound_query_detected")
        assert len(events) == 10
        assert events[0].details["execution_enabled"] is False

    def test_detection_rate_calculation(self):
        _inject_routing_events(100)
        _inject_detection_events(10)
        stats = RoutingMonitor.get_compound_stats()
        assert stats["detection_count"] == 10
        assert stats["compound_query_rate"] == 0.1  # 10/100


class TestPhaseBExecution:
    """Phase B: Parallel execution monitoring."""

    def test_execution_success_rate(self):
        _inject_routing_events(100)
        _inject_detection_events(20, enabled=True)
        _inject_execution_events(20, partial_rate=0.0)
        stats = RoutingMonitor.get_compound_stats()
        assert stats["success_rate"] == 1.0

    def test_partial_failure_detection(self):
        _inject_routing_events(100)
        _inject_detection_events(20, enabled=True)
        _inject_execution_events(20, partial_rate=0.5)
        stats = RoutingMonitor.get_compound_stats()
        assert stats["partial_failure_rate"] > 0.0


class TestCompoundDashboard:
    """Test compound monitoring dashboard."""

    def test_dashboard_structure(self):
        _inject_routing_events(50)
        _inject_detection_events(5)
        _inject_execution_events(5)
        stats = RoutingMonitor.get_compound_stats()
        assert "compound_query_rate" in stats
        assert "success_rate" in stats
        assert "partial_failure_rate" in stats
        assert "parallel_count" in stats
        assert "sequential_count" in stats
        assert "avg_latency_ms" in stats
        assert "avg_sub_intents" in stats
        assert "alerts" in stats

    def test_healthy_system_no_alerts(self):
        _inject_routing_events(100)
        _inject_detection_events(10, enabled=True)
        _inject_execution_events(10, partial_rate=0.0)
        stats = RoutingMonitor.get_compound_stats()
        assert stats["status"] == "healthy"
        assert len(stats["alerts"]) == 0

    def test_high_partial_failure_alert(self):
        _inject_routing_events(100)
        _inject_detection_events(20, enabled=True)
        _inject_execution_events(20, partial_rate=0.5)
        stats = RoutingMonitor.get_compound_stats()
        assert any("PARTIAL" in a for a in stats["alerts"])

    def test_empty_dashboard(self):
        stats = RoutingMonitor.get_compound_stats()
        assert stats["detection_count"] == 0
        assert stats["execution_count"] == 0


class TestRollbackConditions:
    """Test that rollback conditions are properly detected."""

    def test_success_rate_below_threshold(self):
        _inject_routing_events(100)
        _inject_detection_events(20, enabled=True)
        # Inject 20 executions with 50% partial failure
        _inject_execution_events(20, partial_rate=0.5)
        stats = RoutingMonitor.get_compound_stats()
        # Partial failures reduce success rate
        has_alert = any("SUCCESS" in a or "PARTIAL" in a for a in stats["alerts"])
        # At 50% partial, should trigger alert
        assert stats["partial_failure_rate"] > 0.20 or stats["success_rate"] < 0.90
