"""
Escalation Service for Overdue Payments

Implements multi-level escalation (D+1, D+7, D+14) for overdue billing items.

Escalation Logic:
    - D+1 (Level 1):  Notify Sales Manager
    - D+7 (Level 2):  Escalate to Operations Lead
    - D+14 (Level 3): Escalate to Director

Architecture:
    EscalationService → FinOpsDataService → CPI/MS5

Usage:
    from lead_to_cash.services.financeops.escalation_service import EscalationService

    service = EscalationService()
    await service.connect()
    escalations = await service.get_escalations()
    summary = await service.get_escalation_summary()
"""

import logging
from typing import Optional

from lead_to_cash.services.financeops.data_service import FinOpsDataService
from lead_to_cash.services.financeops.models import (
    BillingStatus,
    EscalationEvent,
    EscalationLevel,
    EscalationStatus,
)

logger = logging.getLogger(__name__)


class EscalationService:
    """
    Service for managing overdue payment escalations.

    Scans billing items from FinOpsDataService, determines escalation levels
    based on days overdue, and formats alerts for the FinOps dashboard.
    """

    def __init__(self, data_service: Optional[FinOpsDataService] = None):
        """
        Initialize the escalation service.

        Args:
            data_service: FinOpsDataService instance (creates one if not provided)
        """
        self._data_service = data_service
        self._owns_data_service = data_service is None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to data service."""
        if self._connected:
            return

        if self._data_service is None:
            self._data_service = FinOpsDataService()
            self._owns_data_service = True

        if not self._data_service._connected:
            await self._data_service.connect()

        self._connected = True
        logger.info("EscalationService connected")

    async def disconnect(self) -> None:
        """Close connections."""
        if self._owns_data_service and self._data_service:
            await self._data_service.disconnect()

        self._connected = False

    async def __aenter__(self) -> "EscalationService":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def _ensure_connected(self) -> None:
        """Ensure service is connected."""
        if not self._connected:
            raise RuntimeError("EscalationService not connected")

    @staticmethod
    def determine_escalation_level(days_overdue: int) -> Optional[EscalationLevel]:
        """
        Determine escalation level based on days overdue.

        Args:
            days_overdue: Number of days past due (positive = overdue)

        Returns:
            EscalationLevel or None if not yet escalation-eligible
        """
        if days_overdue >= 14:
            return EscalationLevel.L3
        elif days_overdue >= 7:
            return EscalationLevel.L2
        elif days_overdue >= 1:
            return EscalationLevel.L1
        return None

    async def get_escalations(
        self,
        customer_id: Optional[str] = None,
        level: Optional[EscalationLevel] = None,
    ) -> list[EscalationEvent]:
        """
        Get escalation events for overdue billing items.

        Scans all billing items, identifies overdue ones, and assigns
        escalation levels based on days overdue.

        Args:
            customer_id: Optional filter by customer ID
            level: Optional filter by escalation level

        Returns:
            List of EscalationEvent objects sorted by severity (L3 first)
        """
        self._ensure_connected()

        # Get all billing items (optionally filtered by customer)
        billing_items = await self._data_service.get_billing_items(
            customer_id=customer_id,
        )

        escalations = []
        for item in billing_items:
            # Only consider overdue items
            if item.status != BillingStatus.OVERDUE:
                continue

            days_overdue = abs(item.days_to_action)
            esc_level = self.determine_escalation_level(days_overdue)

            if esc_level is None:
                continue

            # Apply level filter if specified
            if level and esc_level != level:
                continue

            event = EscalationEvent(
                customer_id=item.customer_id,
                customer_name=item.customer_name,
                document_number=item.document_number,
                amount=item.total_amount,
                currency=item.currency,
                days_overdue=days_overdue,
                level=esc_level,
                status=EscalationStatus.OPEN,
                due_date=item.next_action_date,
            )
            escalations.append(event)

        # Sort by severity: L3 first, then L2, then L1 (within same level, most overdue first)
        level_order = {
            EscalationLevel.L3: 0,
            EscalationLevel.L2: 1,
            EscalationLevel.L1: 2,
        }
        escalations.sort(key=lambda e: (level_order.get(e.level, 99), -e.days_overdue))

        return escalations

    async def get_escalation_summary(
        self,
        customer_id: Optional[str] = None,
    ) -> dict:
        """
        Get summary of escalations by level.

        Args:
            customer_id: Optional filter by customer ID

        Returns:
            Dict with counts by level and total overdue amount
        """
        self._ensure_connected()

        escalations = await self.get_escalations(customer_id=customer_id)

        summary = {
            "total_count": len(escalations),
            "total_overdue_amount": 0.0,
            "by_level": {
                "L1": {"count": 0, "amount": 0.0, "label": EscalationLevel.L1.label},
                "L2": {"count": 0, "amount": 0.0, "label": EscalationLevel.L2.label},
                "L3": {"count": 0, "amount": 0.0, "label": EscalationLevel.L3.label},
            },
            "customers_affected": set(),
            "currency": "USD",
        }

        currencies = []
        for event in escalations:
            summary["total_overdue_amount"] += event.amount
            level_key = event.level.value
            summary["by_level"][level_key]["count"] += 1
            summary["by_level"][level_key]["amount"] += event.amount
            summary["customers_affected"].add(event.customer_name)
            currencies.append(event.currency)

        # Use most common currency (consistent with data_service.get_summary_counts)
        if currencies:
            summary["currency"] = max(set(currencies), key=currencies.count)

        # Convert set to count for serialization
        summary["customers_affected_count"] = len(summary["customers_affected"])
        summary["customers_affected"] = list(summary["customers_affected"])

        return summary

    @staticmethod
    def format_escalation_alert(event: EscalationEvent) -> str:
        """
        Format a single escalation event as a box-style alert.

        Args:
            event: EscalationEvent to format

        Returns:
            Formatted alert string
        """
        urgency = {
            EscalationLevel.L1: "NOTICE",
            EscalationLevel.L2: "WARNING",
            EscalationLevel.L3: "URGENT",
        }

        urgency_marker = urgency.get(event.level, "NOTICE")
        due_str = event.due_date.isoformat() if event.due_date else "N/A"

        alert = (
            f"┌─────────────────────────────────────────────────────┐\n"
            f"│ {urgency_marker}: {event.level.label:<42}│\n"
            f"├─────────────────────────────────────────────────────┤\n"
            f"│ Customer:  {event.customer_name:<40}│\n"
            f"│ Document:  {event.document_number:<40}│\n"
            f"│ Amount:    {event.currency} {event.amount:>12,.2f}                   │\n"
            f"│ Days Overdue: {event.days_overdue:<37}│\n"
            f"│ Due Date:  {due_str:<40}│\n"
            f"│ Assigned:  {event.assigned_role:<40}│\n"
            f"│ Status:    {event.status.value:<40}│\n"
            f"└─────────────────────────────────────────────────────┘"
        )
        return alert

    def format_escalation_summary(self, summary: dict) -> str:
        """
        Format escalation summary as a readable report.

        Args:
            summary: Summary dict from get_escalation_summary()

        Returns:
            Formatted summary string
        """
        currency = summary.get("currency", "USD")
        total_amount = summary.get("total_overdue_amount", 0)
        total_count = summary.get("total_count", 0)

        lines = [
            "═══════════════════════════════════════════════════════",
            "ESCALATION SUMMARY",
            "═══════════════════════════════════════════════════════",
            "",
            f"Total Escalations: {total_count}",
            f"Total Overdue:     {currency} {total_amount:,.2f}",
            f"Customers Affected: {summary.get('customers_affected_count', 0)}",
            "",
            "┌──────────┬───────┬────────────────────────┐",
            "│ Level    │ Count │ Amount                 │",
            "├──────────┼───────┼────────────────────────┤",
        ]

        for level_key in ["L3", "L2", "L1"]:
            level_data = summary.get("by_level", {}).get(level_key, {})
            count = level_data.get("count", 0)
            amount = level_data.get("amount", 0)
            label = level_data.get("label", level_key)
            if count > 0:
                lines.append(
                    f"│ {label[:8]:<8} │ {count:>5} │ {currency} {amount:>14,.2f}   │"
                )

        lines.extend(
            [
                "└──────────┴───────┴────────────────────────┘",
                "",
                "═══════════════════════════════════════════════════════",
            ]
        )

        return "\n".join(lines)
