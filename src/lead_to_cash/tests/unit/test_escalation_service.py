"""
Unit Tests for Escalation Service

Tests escalation level determination, event detection from billing data,
alert formatting, and summary generation.

Tier 1 unit tests — mocks allowed for external CPI/MS5 dependencies.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lead_to_cash.services.financeops.escalation_service import EscalationService
from lead_to_cash.services.financeops.models import (
    BillingItem,
    BillingStatus,
    EscalationEvent,
    EscalationLevel,
    EscalationStatus,
    HarmonizedPaymentTerm,
    PaymentTermType,
)


# =============================================================================
# EscalationLevel Tests
# =============================================================================


class TestEscalationLevel:
    """Tests for EscalationLevel enum."""

    def test_level_values(self):
        """Test level values are correct."""
        assert EscalationLevel.L1.value == "L1"
        assert EscalationLevel.L2.value == "L2"
        assert EscalationLevel.L3.value == "L3"

    def test_days_threshold(self):
        """Test days thresholds for each level."""
        assert EscalationLevel.L1.days_threshold == 1
        assert EscalationLevel.L2.days_threshold == 7
        assert EscalationLevel.L3.days_threshold == 14

    def test_assigned_role(self):
        """Test assigned roles for each level."""
        assert EscalationLevel.L1.assigned_role == "sales_manager"
        assert EscalationLevel.L2.assigned_role == "operations_lead"
        assert EscalationLevel.L3.assigned_role == "director"

    def test_label(self):
        """Test human-readable labels."""
        assert "Sales Manager" in EscalationLevel.L1.label
        assert "Operations Lead" in EscalationLevel.L2.label
        assert "Director" in EscalationLevel.L3.label


# =============================================================================
# EscalationEvent Tests
# =============================================================================


class TestEscalationEvent:
    """Tests for EscalationEvent dataclass."""

    def test_basic_creation(self):
        """Test basic event creation."""
        event = EscalationEvent(
            customer_id="0021000090",
            customer_name="CLLS Power System",
            document_number="3228005112",
            amount=45000.0,
            currency="EUR",
            days_overdue=30,
            level=EscalationLevel.L3,
        )

        assert event.customer_id == "0021000090"
        assert event.customer_name == "CLLS Power System"
        assert event.document_number == "3228005112"
        assert event.amount == 45000.0
        assert event.currency == "EUR"
        assert event.days_overdue == 30
        assert event.level == EscalationLevel.L3
        assert event.status == EscalationStatus.OPEN

    def test_auto_assigned_role(self):
        """Test assigned_role is auto-populated from level."""
        event = EscalationEvent(
            customer_id="0021000090",
            customer_name="CLLS",
            document_number="123",
            amount=1000.0,
            currency="EUR",
            days_overdue=5,
            level=EscalationLevel.L1,
        )
        assert event.assigned_role == "sales_manager"

    def test_custom_assigned_role(self):
        """Test custom assigned_role overrides auto-assignment."""
        event = EscalationEvent(
            customer_id="0021000090",
            customer_name="CLLS",
            document_number="123",
            amount=1000.0,
            currency="EUR",
            days_overdue=5,
            level=EscalationLevel.L1,
            assigned_role="custom_role",
        )
        assert event.assigned_role == "custom_role"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        event = EscalationEvent(
            customer_id="0021000090",
            customer_name="CLLS Power System",
            document_number="3228005112",
            amount=45000.0,
            currency="EUR",
            days_overdue=30,
            level=EscalationLevel.L3,
            due_date=date(2025, 12, 1),
        )

        d = event.to_dict()
        assert d["customer_id"] == "0021000090"
        assert d["level"] == "L3"
        assert d["level_label"] == "Level 3 (Director)"
        assert d["status"] == "OPEN"
        assert d["assigned_role"] == "director"
        assert d["due_date"] == "2025-12-01"
        assert d["amount"] == 45000.0


# =============================================================================
# Escalation Level Determination Tests
# =============================================================================


class TestDetermineEscalationLevel:
    """Tests for EscalationService.determine_escalation_level()."""

    def test_not_yet_overdue(self):
        """Test 0 days overdue returns None."""
        assert EscalationService.determine_escalation_level(0) is None

    def test_negative_days(self):
        """Test negative days (not overdue) returns None."""
        assert EscalationService.determine_escalation_level(-5) is None

    def test_level_1_at_1_day(self):
        """Test 1 day overdue triggers L1."""
        assert EscalationService.determine_escalation_level(1) == EscalationLevel.L1

    def test_level_1_at_6_days(self):
        """Test 6 days overdue is still L1."""
        assert EscalationService.determine_escalation_level(6) == EscalationLevel.L1

    def test_level_2_at_7_days(self):
        """Test 7 days overdue triggers L2."""
        assert EscalationService.determine_escalation_level(7) == EscalationLevel.L2

    def test_level_2_at_13_days(self):
        """Test 13 days overdue is still L2."""
        assert EscalationService.determine_escalation_level(13) == EscalationLevel.L2

    def test_level_3_at_14_days(self):
        """Test 14 days overdue triggers L3."""
        assert EscalationService.determine_escalation_level(14) == EscalationLevel.L3

    def test_level_3_at_30_days(self):
        """Test 30 days overdue is still L3."""
        assert EscalationService.determine_escalation_level(30) == EscalationLevel.L3

    def test_level_3_at_100_days(self):
        """Test extreme overdue is L3."""
        assert EscalationService.determine_escalation_level(100) == EscalationLevel.L3


# =============================================================================
# Escalation Detection Tests (with mocked data service)
# =============================================================================


def _make_billing_item(
    customer_id: str,
    customer_name: str,
    doc_number: str,
    amount: float,
    currency: str,
    days_overdue: int,
    status: BillingStatus = BillingStatus.OVERDUE,
) -> BillingItem:
    """Helper to create a billing item for testing."""
    today = date.today()
    due_date = today - timedelta(days=days_overdue)
    return BillingItem(
        document_number=doc_number,
        customer_id=customer_id,
        customer_name=customer_name,
        document_date=due_date - timedelta(days=30),
        total_amount=amount,
        currency=currency,
        payment_term=HarmonizedPaymentTerm(
            raw_text="Net 30", term_type=PaymentTermType.NET
        ),
        status=status,
        next_action_date=due_date,
        days_to_action=-days_overdue,
        aging_bucket="45+"
        if days_overdue > 45
        else "30-45"
        if days_overdue > 30
        else "0-30",
    )


@pytest.fixture
def mock_data_service():
    """Create a mock FinOpsDataService."""
    service = AsyncMock()
    service._connected = True
    return service


@pytest.fixture
def escalation_service(mock_data_service):
    """Create EscalationService with mocked data service."""
    svc = EscalationService(data_service=mock_data_service)
    svc._connected = True
    return svc


class TestGetEscalations:
    """Tests for EscalationService.get_escalations()."""

    @pytest.mark.asyncio
    async def test_no_overdue_items(self, escalation_service, mock_data_service):
        """Test no escalations when no overdue items."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item(
                "0001",
                "TestCo",
                "DOC1",
                1000.0,
                "EUR",
                0,
                status=BillingStatus.PENDING_COLLECTION,
            ),
        ]

        result = await escalation_service.get_escalations()
        assert result == []

    @pytest.mark.asyncio
    async def test_single_overdue_l1(self, escalation_service, mock_data_service):
        """Test single overdue item at L1 (5 days)."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item(
                "0000100001", "Batam Fast Ferry", "DOC1", 5000.0, "SGD", 5
            ),
        ]

        result = await escalation_service.get_escalations()
        assert len(result) == 1
        assert result[0].level == EscalationLevel.L1
        assert result[0].customer_name == "Batam Fast Ferry"
        assert result[0].days_overdue == 5

    @pytest.mark.asyncio
    async def test_multiple_levels(self, escalation_service, mock_data_service):
        """Test items at different escalation levels."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item("0001", "CustomerA", "DOC1", 1000.0, "EUR", 2),  # L1
            _make_billing_item("0002", "CustomerB", "DOC2", 5000.0, "EUR", 10),  # L2
            _make_billing_item("0003", "CustomerC", "DOC3", 10000.0, "EUR", 30),  # L3
        ]

        result = await escalation_service.get_escalations()
        assert len(result) == 3
        # Should be sorted L3 first, then L2, then L1
        assert result[0].level == EscalationLevel.L3
        assert result[1].level == EscalationLevel.L2
        assert result[2].level == EscalationLevel.L1

    @pytest.mark.asyncio
    async def test_filter_by_customer(self, escalation_service, mock_data_service):
        """Test customer_id filter is passed to data service."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item("0001", "CustomerA", "DOC1", 1000.0, "EUR", 5),
        ]

        await escalation_service.get_escalations(customer_id="0001")
        mock_data_service.get_billing_items.assert_called_once_with(customer_id="0001")

    @pytest.mark.asyncio
    async def test_filter_by_level(self, escalation_service, mock_data_service):
        """Test filtering escalations by level."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item("0001", "CustomerA", "DOC1", 1000.0, "EUR", 2),  # L1
            _make_billing_item("0002", "CustomerB", "DOC2", 5000.0, "EUR", 10),  # L2
            _make_billing_item("0003", "CustomerC", "DOC3", 10000.0, "EUR", 30),  # L3
        ]

        result = await escalation_service.get_escalations(level=EscalationLevel.L3)
        assert len(result) == 1
        assert result[0].level == EscalationLevel.L3

    @pytest.mark.asyncio
    async def test_mixed_status_items(self, escalation_service, mock_data_service):
        """Test only OVERDUE items generate escalations."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item(
                "0001",
                "CustomerA",
                "DOC1",
                1000.0,
                "EUR",
                5,
                status=BillingStatus.OVERDUE,
            ),
            _make_billing_item(
                "0002",
                "CustomerB",
                "DOC2",
                2000.0,
                "EUR",
                10,
                status=BillingStatus.PENDING_COLLECTION,
            ),
            _make_billing_item(
                "0003",
                "CustomerC",
                "DOC3",
                3000.0,
                "EUR",
                0,
                status=BillingStatus.PAID,
            ),
        ]

        result = await escalation_service.get_escalations()
        assert len(result) == 1
        assert result[0].customer_name == "CustomerA"

    @pytest.mark.asyncio
    async def test_not_connected_raises(self):
        """Test that calling without connection raises RuntimeError."""
        svc = EscalationService()
        with pytest.raises(RuntimeError, match="not connected"):
            await svc.get_escalations()


# =============================================================================
# Escalation Summary Tests
# =============================================================================


class TestGetEscalationSummary:
    """Tests for EscalationService.get_escalation_summary()."""

    @pytest.mark.asyncio
    async def test_empty_summary(self, escalation_service, mock_data_service):
        """Test summary with no overdue items."""
        mock_data_service.get_billing_items.return_value = []

        summary = await escalation_service.get_escalation_summary()
        assert summary["total_count"] == 0
        assert summary["total_overdue_amount"] == 0.0
        assert summary["customers_affected_count"] == 0

    @pytest.mark.asyncio
    async def test_summary_with_escalations(
        self, escalation_service, mock_data_service
    ):
        """Test summary with mixed escalation levels."""
        mock_data_service.get_billing_items.return_value = [
            _make_billing_item("0001", "CustomerA", "DOC1", 1000.0, "EUR", 2),  # L1
            _make_billing_item("0001", "CustomerA", "DOC2", 2000.0, "EUR", 10),  # L2
            _make_billing_item("0002", "CustomerB", "DOC3", 5000.0, "EUR", 30),  # L3
        ]

        summary = await escalation_service.get_escalation_summary()
        assert summary["total_count"] == 3
        assert summary["total_overdue_amount"] == 8000.0
        assert summary["customers_affected_count"] == 2
        assert summary["by_level"]["L1"]["count"] == 1
        assert summary["by_level"]["L1"]["amount"] == 1000.0
        assert summary["by_level"]["L2"]["count"] == 1
        assert summary["by_level"]["L2"]["amount"] == 2000.0
        assert summary["by_level"]["L3"]["count"] == 1
        assert summary["by_level"]["L3"]["amount"] == 5000.0


# =============================================================================
# Alert Formatting Tests
# =============================================================================


class TestFormatEscalationAlert:
    """Tests for EscalationService.format_escalation_alert()."""

    def test_l1_alert_format(self):
        """Test L1 alert has NOTICE urgency."""
        event = EscalationEvent(
            customer_id="0001",
            customer_name="Batam Fast Ferry",
            document_number="3228005112",
            amount=5000.0,
            currency="SGD",
            days_overdue=5,
            level=EscalationLevel.L1,
            due_date=date(2025, 12, 1),
        )

        alert = EscalationService.format_escalation_alert(event)
        assert "NOTICE" in alert
        assert "Batam Fast Ferry" in alert
        assert "3228005112" in alert
        assert "SGD" in alert
        assert "5,000.00" in alert
        assert "sales_manager" in alert

    def test_l2_alert_format(self):
        """Test L2 alert has WARNING urgency."""
        event = EscalationEvent(
            customer_id="0002",
            customer_name="CLLS Power System",
            document_number="DOC2",
            amount=45000.0,
            currency="EUR",
            days_overdue=10,
            level=EscalationLevel.L2,
        )

        alert = EscalationService.format_escalation_alert(event)
        assert "WARNING" in alert
        assert "CLLS Power System" in alert
        assert "operations_lead" in alert

    def test_l3_alert_format(self):
        """Test L3 alert has URGENT urgency."""
        event = EscalationEvent(
            customer_id="0003",
            customer_name="Neptune Energy",
            document_number="DOC3",
            amount=100000.0,
            currency="EUR",
            days_overdue=30,
            level=EscalationLevel.L3,
        )

        alert = EscalationService.format_escalation_alert(event)
        assert "URGENT" in alert
        assert "Neptune Energy" in alert
        assert "director" in alert

    def test_alert_contains_box_characters(self):
        """Test alert uses box-drawing characters."""
        event = EscalationEvent(
            customer_id="0001",
            customer_name="TestCo",
            document_number="DOC1",
            amount=1000.0,
            currency="USD",
            days_overdue=5,
            level=EscalationLevel.L1,
        )

        alert = EscalationService.format_escalation_alert(event)
        assert "┌" in alert
        assert "└" in alert
        assert "│" in alert
        assert "├" in alert


# =============================================================================
# Summary Formatting Tests
# =============================================================================


class TestFormatEscalationSummary:
    """Tests for EscalationService.format_escalation_summary()."""

    def test_summary_format(self):
        """Test summary formatting output."""
        summary = {
            "total_count": 3,
            "total_overdue_amount": 8000.0,
            "customers_affected_count": 2,
            "customers_affected": ["CustomerA", "CustomerB"],
            "currency": "EUR",
            "by_level": {
                "L1": {
                    "count": 1,
                    "amount": 1000.0,
                    "label": "Level 1 (Sales Manager)",
                },
                "L2": {
                    "count": 1,
                    "amount": 2000.0,
                    "label": "Level 2 (Operations Lead)",
                },
                "L3": {"count": 1, "amount": 5000.0, "label": "Level 3 (Director)"},
            },
        }

        svc = EscalationService()
        result = svc.format_escalation_summary(summary)
        assert "ESCALATION SUMMARY" in result
        assert "Total Escalations: 3" in result
        assert "EUR" in result
        assert "8,000.00" in result

    def test_empty_summary_format(self):
        """Test summary formatting with no escalations."""
        summary = {
            "total_count": 0,
            "total_overdue_amount": 0.0,
            "customers_affected_count": 0,
            "customers_affected": [],
            "currency": "USD",
            "by_level": {
                "L1": {"count": 0, "amount": 0.0, "label": "Level 1 (Sales Manager)"},
                "L2": {"count": 0, "amount": 0.0, "label": "Level 2 (Operations Lead)"},
                "L3": {"count": 0, "amount": 0.0, "label": "Level 3 (Director)"},
            },
        }

        svc = EscalationService()
        result = svc.format_escalation_summary(summary)
        assert "Total Escalations: 0" in result


# =============================================================================
# Connection Lifecycle Tests
# =============================================================================


class TestEscalationServiceLifecycle:
    """Tests for EscalationService lifecycle management."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager pattern."""
        with patch(
            "lead_to_cash.services.financeops.escalation_service.FinOpsDataService"
        ) as MockDataService:
            mock_ds = AsyncMock()
            mock_ds._connected = False
            MockDataService.return_value = mock_ds

            async with EscalationService() as svc:
                assert svc._connected is True

    @pytest.mark.asyncio
    async def test_shared_data_service(self, mock_data_service):
        """Test escalation service shares data service connection."""
        svc = EscalationService(data_service=mock_data_service)
        await svc.connect()

        assert svc._connected is True
        assert svc._owns_data_service is False

    @pytest.mark.asyncio
    async def test_owned_data_service_disconnect(self):
        """Test owned data service is disconnected on close."""
        with patch(
            "lead_to_cash.services.financeops.escalation_service.FinOpsDataService"
        ) as MockDataService:
            mock_ds = AsyncMock()
            mock_ds._connected = False
            MockDataService.return_value = mock_ds

            svc = EscalationService()
            await svc.connect()
            await svc.disconnect()

            mock_ds.disconnect.assert_called_once()
