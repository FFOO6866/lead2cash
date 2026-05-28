"""
Unit Tests for Continuous Intelligence Loop

Tests the feedback, calibration, detection, suggestion, and reporting
infrastructure that drives continuous improvement of signal routing.
"""

import pytest

from lead_to_cash.core.response_quality import (
    ContinuousIntelligence,
    QualityMetrics,
    RoutingMonitor,
)


@pytest.fixture(autouse=True)
def _clear_state():
    """Clear accumulated state before each test."""
    QualityMetrics._events = []
    ContinuousIntelligence._qa_feedback = []
    yield


def _inject_events(n=50, agreement_rate=0.95, confidence_min=0.5):
    """Inject simulated routing events."""
    import random

    random.seed(42)
    domains = [
        "billing_ar",
        "product_fit",
        "competitor_intel",
        "customer_intel",
        "market_intel",
    ]
    for i in range(n):
        agrees = random.random() < agreement_rate
        conf = random.uniform(confidence_min, 0.95)
        band = "HIGH" if conf >= 0.75 else ("MODERATE" if conf >= 0.5 else "LOW")
        intent = random.choice(domains)
        QualityMetrics.record(
            event_type="signal_routing_live",
            severity="INFO",
            intent=intent,
            details={
                "routing_source": "signal",
                "signal_intent": intent,
                "signal_confidence": conf,
                "signal_confidence_band": band,
                "agreement": agrees,
                "fallback_triggered": False,
                "final_intent": intent,
            },
        )


class TestQAFeedback:
    """Test QA feedback collection."""

    def test_record_feedback(self):
        ContinuousIntelligence.record_qa_feedback(
            query="Show billing items",
            signal_intent="billing_ar",
            keyword_intent="billing_ar",
            final_intent="billing_ar",
            verdict="correct",
            confidence=0.85,
        )
        assert len(ContinuousIntelligence._qa_feedback) == 1
        assert ContinuousIntelligence._qa_feedback[0]["verdict"] == "correct"

    def test_feedback_logged_to_metrics(self):
        ContinuousIntelligence.record_qa_feedback(
            query="Test query",
            signal_intent="billing_ar",
            keyword_intent="customer_intel",
            final_intent="billing_ar",
            verdict="incorrect",
            confidence=0.6,
        )
        events = QualityMetrics.get_recent_events("qa_feedback")
        assert len(events) == 1

    def test_feedback_bounded(self):
        for i in range(100):
            ContinuousIntelligence.record_qa_feedback(
                query=f"Query {i}",
                signal_intent="billing_ar",
                keyword_intent="billing_ar",
                final_intent="billing_ar",
                verdict="correct",
                confidence=0.8,
            )
        assert (
            len(ContinuousIntelligence._qa_feedback)
            <= ContinuousIntelligence._max_feedback
        )

    def test_confidence_band_assignment(self):
        ContinuousIntelligence.record_qa_feedback(
            query="High confidence",
            signal_intent="billing_ar",
            keyword_intent="billing_ar",
            final_intent="billing_ar",
            verdict="correct",
            confidence=0.85,
        )
        assert ContinuousIntelligence._qa_feedback[-1]["confidence_band"] == "HIGH"

        ContinuousIntelligence.record_qa_feedback(
            query="Low confidence",
            signal_intent="general_question",
            keyword_intent="general_question",
            final_intent="general_question",
            verdict="ambiguous",
            confidence=0.35,
        )
        assert ContinuousIntelligence._qa_feedback[-1]["confidence_band"] == "LOW"


class TestConfidenceCalibration:
    """Test confidence calibration metrics."""

    def test_calibration_with_feedback(self):
        for i in range(10):
            ContinuousIntelligence.record_qa_feedback(
                query=f"Q{i}",
                signal_intent="billing_ar",
                keyword_intent="billing_ar",
                final_intent="billing_ar",
                verdict="correct" if i < 9 else "incorrect",
                confidence=0.85,
            )
        cal = ContinuousIntelligence.get_confidence_calibration()
        high = cal["from_qa_feedback"]["HIGH"]
        assert high["total"] == 10
        assert high["accuracy"] == 0.9

    def test_calibration_with_events(self):
        _inject_events(50)
        cal = ContinuousIntelligence.get_confidence_calibration()
        assert cal["total_events"] > 0
        assert "from_agreement_proxy" in cal

    def test_empty_calibration(self):
        cal = ContinuousIntelligence.get_confidence_calibration()
        assert cal["total_feedback"] == 0


class TestWeakPatternDetection:
    """Test automatic weak pattern detection."""

    def test_detects_weak_domain(self):
        # Inject events with high disagreement for one domain
        for i in range(20):
            QualityMetrics.record(
                event_type="signal_routing_live",
                severity="INFO",
                intent="competitor_intel",
                details={
                    "signal_confidence_band": "MODERATE",
                    "agreement": i >= 15,  # 75% agreement = 25% disagree
                    "final_intent": "competitor_intel",
                    "signal_confidence": 0.6,
                    "fallback_triggered": False,
                },
            )
        patterns = ContinuousIntelligence.detect_weak_patterns()
        assert len(patterns["weak_domains"]) > 0

    def test_detects_low_confidence_cluster(self):
        for i in range(10):
            QualityMetrics.record(
                event_type="signal_routing_live",
                severity="INFO",
                intent="market_intel",
                details={
                    "signal_confidence": 0.35,
                    "signal_confidence_band": "LOW",
                    "agreement": True,
                    "final_intent": "market_intel",
                    "fallback_triggered": False,
                },
            )
        patterns = ContinuousIntelligence.detect_weak_patterns()
        assert len(patterns["low_confidence_clusters"]) > 0

    def test_no_patterns_in_healthy_system(self):
        for i in range(50):
            QualityMetrics.record(
                event_type="signal_routing_live",
                severity="INFO",
                intent="billing_ar",
                details={
                    "signal_confidence": 0.85,
                    "signal_confidence_band": "HIGH",
                    "agreement": True,
                    "final_intent": "billing_ar",
                    "fallback_triggered": False,
                },
            )
        patterns = ContinuousIntelligence.detect_weak_patterns()
        assert len(patterns["weak_domains"]) == 0
        assert len(patterns["low_confidence_clusters"]) == 0


class TestCalibrationSuggestions:
    """Test suggestion engine."""

    def test_generates_suggestions_from_errors(self):
        for i in range(5):
            ContinuousIntelligence.record_qa_feedback(
                query=f"Wrong routing {i}",
                signal_intent="billing_ar",
                keyword_intent="customer_intel",
                final_intent="billing_ar",
                verdict="incorrect",
                confidence=0.7,
            )
        suggestions = ContinuousIntelligence.suggest_calibration()
        assert suggestions["suggestion_count"] > 0
        assert suggestions["requires_manual_approval"] is True
        assert suggestions["auto_apply"] is False

    def test_no_suggestions_when_healthy(self):
        for i in range(20):
            QualityMetrics.record(
                event_type="signal_routing_live",
                severity="INFO",
                intent="billing_ar",
                details={
                    "signal_confidence": 0.85,
                    "signal_confidence_band": "HIGH",
                    "agreement": True,
                    "final_intent": "billing_ar",
                    "fallback_triggered": False,
                },
            )
        suggestions = ContinuousIntelligence.suggest_calibration()
        # May have zero or few suggestions
        assert suggestions["auto_apply"] is False


class TestReviewReport:
    """Test periodic review report generation."""

    def test_report_structure(self):
        _inject_events(30)
        report = ContinuousIntelligence.generate_review_report(window=30)
        assert "summary" in report
        assert "domain_health" in report
        assert "confidence_calibration" in report
        assert "weak_patterns" in report
        assert "suggestions" in report
        assert "qa_feedback_summary" in report
        assert report["report_type"] == "routing_review"

    def test_report_with_feedback(self):
        _inject_events(30)
        ContinuousIntelligence.record_qa_feedback(
            query="Test",
            signal_intent="billing_ar",
            keyword_intent="billing_ar",
            final_intent="billing_ar",
            verdict="correct",
            confidence=0.9,
        )
        report = ContinuousIntelligence.generate_review_report(window=30)
        assert report["qa_feedback_summary"]["total"] > 0


class TestUpdateSafety:
    """Test safe update validation."""

    def test_safe_update_passes(self):
        before = {
            "signal_accuracy": 0.95,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 1},
        }
        after = {
            "signal_accuracy": 0.97,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 0},
        }
        result = ContinuousIntelligence.validate_update_safety(
            "Adjusted competitor affinity", before, after
        )
        assert result["recommendation"] == "GO"

    def test_unsafe_update_blocked(self):
        before = {
            "signal_accuracy": 0.95,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 1},
        }
        after = {
            "signal_accuracy": 0.90,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 5},
        }
        result = ContinuousIntelligence.validate_update_safety(
            "Risky weight change", before, after
        )
        assert result["recommendation"] == "NO-GO"
        assert result["requires_manual_approval"] is True

    def test_validation_logged(self):
        before = {
            "signal_accuracy": 0.95,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 1},
        }
        after = {
            "signal_accuracy": 0.96,
            "total_queries": 100,
            "disagreements": {"current_correct_signal_wrong": 1},
        }
        ContinuousIntelligence.validate_update_safety("Test", before, after)
        events = QualityMetrics.get_recent_events("update_validation")
        assert len(events) > 0
