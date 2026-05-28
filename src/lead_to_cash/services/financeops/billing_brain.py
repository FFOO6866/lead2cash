"""
Billing Brain Service

Order-centric billing intelligence that derives actionable alerts from
sales order billing plan milestones (FPLT/FPLTR).

Instead of looking at billing documents in isolation, this service:
1. Scans ALL sales orders and their billing plan milestones
2. Cross-references with billing documents for payment/clearing status
3. Uses delivery dates (EDATU) for shipment-triggered milestone timing
4. Classifies each milestone into an actionable state
5. Generates prioritized alerts for the finance ops team

Milestone States:
    OVERDUE      — Open milestone past due date, no block → create billing doc NOW
    DUE_THIS_WEEK — Open milestone due within 7 days
    DUE_THIS_MONTH — Open milestone due within 30 days
    UPCOMING     — Open milestone due > 30 days
    BLOCKED      — Open milestone past due but billing-blocked (FAKSP=01)
    BILLED_UNPAID — Billing doc created but not cleared (AR open)
    BILLED_PAID  — Billing doc created and cleared (settled)

Architecture:
    BillingBrainService → CPISimulator._get_simulated_sales_orders()
                        → CPISimulator._get_dynamic_billing_docs()
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class MilestoneState(str, Enum):
    """Actionable state of a billing plan milestone."""

    OVERDUE = "OVERDUE"
    DUE_THIS_WEEK = "DUE_THIS_WEEK"
    DUE_THIS_MONTH = "DUE_THIS_MONTH"
    UPCOMING = "UPCOMING"
    BLOCKED = "BLOCKED"
    BILLED_UNPAID = "BILLED_UNPAID"
    BILLED_PAID = "BILLED_PAID"


# Priority order for sorting (lower = more urgent)
STATE_PRIORITY = {
    MilestoneState.OVERDUE: 0,
    MilestoneState.BLOCKED: 1,
    MilestoneState.DUE_THIS_WEEK: 2,
    MilestoneState.DUE_THIS_MONTH: 3,
    MilestoneState.BILLED_UNPAID: 4,
    MilestoneState.UPCOMING: 5,
    MilestoneState.BILLED_PAID: 6,
}


@dataclass
class MilestoneAlert:
    """A single billing plan milestone with computed actionable state."""

    # Order context
    order_number: str
    customer_id: str
    customer_name: str
    order_value: float
    order_currency: str

    # Milestone detail
    milestone_seq: str  # FPLTR (0001, 0002, ...)
    milestone_desc: str  # TETXT
    milestone_amount: float  # FAKWR
    milestone_pct: float  # BETEFP
    milestone_type: str  # FAZ (downpayment) or F2 (invoice)
    milestone_date: Optional[date]  # FDATU — when to bill
    delivery_date: Optional[date]  # EDATU from order items

    # Computed state
    state: MilestoneState
    days_until_due: int  # Negative = overdue
    is_blocked: bool  # FAKSP = "01"

    # Date derivation source
    date_source: str = ""  # Where FDATU comes from: "SoF_RELEASE" or "ITEM_EDATU"
    sof_date: Optional[date] = None  # ZSF document release date

    # Billing doc linkage
    billing_doc: str = ""  # VBELN if billed
    billing_status: str = ""  # FKSAF: A=open, B=billed
    clearing_date: Optional[date] = None
    clearing_doc: str = ""

    # Action guidance
    action_required: str = ""

    @property
    def is_downpayment(self) -> bool:
        return self.milestone_type == "FAZ"

    @property
    def urgency_label(self) -> str:
        abs_days = abs(self.days_until_due)
        if self.state == MilestoneState.BILLED_UNPAID:
            if self.days_until_due < -45:
                return f"Payment {abs_days} days overdue"
            elif self.days_until_due < 0:
                return f"Payment {abs_days} days overdue"
            else:
                return f"Awaiting payment · due in {self.days_until_due} days"
        return {
            MilestoneState.OVERDUE: f"{abs_days} days overdue",
            MilestoneState.BLOCKED: f"Blocked · {abs_days} days overdue",
            MilestoneState.DUE_THIS_WEEK: f"Due in {self.days_until_due} days",
            MilestoneState.DUE_THIS_MONTH: f"Due in {self.days_until_due} days",
            MilestoneState.UPCOMING: f"Due in {self.days_until_due} days",
            MilestoneState.BILLED_PAID: "Settled",
        }.get(self.state, self.state.value)

    @staticmethod
    def _fmt_date(d: Optional[date]) -> Optional[str]:
        """Format date as '27 Feb 2026' for UI display."""
        if d is None:
            return None
        return f"{d.day} {d.strftime('%b %Y')}"

    def to_dict(self) -> dict:
        return {
            "order_number": self.order_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "order_value": self.order_value,
            "order_currency": self.order_currency,
            "milestone_seq": self.milestone_seq,
            "milestone_desc": self.milestone_desc,
            "milestone_amount": self.milestone_amount,
            "milestone_pct": self.milestone_pct,
            "milestone_type": self.milestone_type,
            "is_downpayment": self.is_downpayment,
            "milestone_date": self.milestone_date.isoformat()
            if self.milestone_date
            else None,
            "milestone_date_fmt": self._fmt_date(self.milestone_date),
            "delivery_date": self.delivery_date.isoformat()
            if self.delivery_date
            else None,
            "delivery_date_fmt": self._fmt_date(self.delivery_date),
            "state": self.state.value,
            "days_until_due": self.days_until_due,
            "is_blocked": self.is_blocked,
            "date_source": self.date_source,
            "sof_date": self.sof_date.isoformat() if self.sof_date else None,
            "sof_date_fmt": self._fmt_date(self.sof_date),
            "billing_doc": self.billing_doc,
            "billing_status": self.billing_status,
            "clearing_date": self.clearing_date.isoformat()
            if self.clearing_date
            else None,
            "clearing_date_fmt": self._fmt_date(self.clearing_date),
            "clearing_doc": self.clearing_doc,
            "action_required": self.action_required,
            "urgency_label": self.urgency_label,
        }


@dataclass
class BillingBrainSummary:
    """Aggregate counts by milestone state for badge display."""

    overdue: int = 0
    due_this_week: int = 0
    due_this_month: int = 0
    upcoming: int = 0
    blocked: int = 0
    billed_unpaid: int = 0
    billed_paid: int = 0
    total_action_required: int = 0  # overdue + due_this_week + blocked + billed_unpaid
    total_overdue_amount: float = 0.0
    total_due_soon_amount: float = 0.0
    currency: str = "EUR"
    order_count: int = 0

    def to_dict(self) -> dict:
        return {
            "overdue": self.overdue,
            "due_this_week": self.due_this_week,
            "due_this_month": self.due_this_month,
            "upcoming": self.upcoming,
            "blocked": self.blocked,
            "billed_unpaid": self.billed_unpaid,
            "billed_paid": self.billed_paid,
            "total_action_required": self.total_action_required,
            "total_overdue_amount": self.total_overdue_amount,
            "total_due_soon_amount": self.total_due_soon_amount,
            "currency": self.currency,
            "order_count": self.order_count,
        }


class BillingBrainService:
    """
    Order-centric billing intelligence service.

    Scans all sales orders, analyses billing plan milestones, and generates
    prioritised actionable alerts for the finance operations team.
    """

    def __init__(self, cpi_client=None):
        self._cpi_client = cpi_client
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        # BillingBrain reads from simulated order data — CPI connection is optional.
        # Don't fail if CPI is unavailable (e.g. after credit check consumed it).
        if self._cpi_client is None:
            try:
                from lead_to_cash.integrations.client_factory import get_cpi_client

                self._cpi_client, _ = await get_cpi_client(use_case="BillingBrain")
            except Exception:
                pass
        if self._cpi_client:
            try:
                await self._cpi_client.connect()
            except Exception:
                logger.debug("BillingBrainService: CPI connect failed (non-critical)")
        self._connected = True

    async def disconnect(self) -> None:
        if self._cpi_client:
            await self._cpi_client.disconnect()
        self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError("BillingBrainService not connected")

    async def get_all_alerts(
        self,
        customer_id: Optional[str] = None,
        include_settled: bool = False,
    ) -> list[MilestoneAlert]:
        """
        Scan all orders and return milestone alerts sorted by urgency.

        Args:
            customer_id: Optional filter by SAP customer ID
            include_settled: Whether to include BILLED_PAID milestones

        Returns:
            List of MilestoneAlert sorted by urgency (most urgent first)
        """
        self._ensure_connected()

        today = date.today()

        # Get all sales orders from simulator
        from lead_to_cash.integrations.cpi_simulator import (
            _get_dynamic_billing_docs,
            _get_simulated_sales_orders,
        )

        orders = _get_simulated_sales_orders()
        billing_docs = _get_dynamic_billing_docs()

        # Index billing docs by document number for clearing lookup
        billing_doc_index = {}
        for doc_num, doc in billing_docs.items():
            billing_doc_index[doc_num] = doc

        alerts = []

        for order_num, order in orders.items():
            header = order.get("header", {})
            order_kunnr = header.get("KUNNR", "")

            # Customer filter
            if customer_id:
                if order_kunnr.lstrip("0") != customer_id.lstrip("0"):
                    continue

            order_value = header.get("NETWR", 0.0)
            order_currency = header.get("WAERK", "EUR")

            # Get customer name from partners
            customer_name = ""
            for partner in order.get("partners", []):
                if partner.get("PARVW") == "AG":
                    customer_name = partner.get("NAME1", "")
                    break

            # Get earliest delivery date from items
            delivery_date = None
            for item in order.get("items", []):
                edatu = item.get("EDATU", "")
                if edatu:
                    try:
                        d = date(int(edatu[:4]), int(edatu[4:6]), int(edatu[6:8]))
                        if delivery_date is None or d < delivery_date:
                            delivery_date = d
                    except (ValueError, IndexError):
                        pass

            # Process billing plan milestones
            bp = order.get("billing_plan", {})
            for ms in bp.get("dates", []):
                ms_seq = ms.get("FPLTR", "")
                ms_desc = ms.get("TETXT", "")
                ms_amount = ms.get("FAKWR", 0.0)
                ms_pct = ms.get("BETEFP", 0.0)
                ms_type = ms.get("FPFAR", "F2")
                ms_status = ms.get("FKSAF", "A")  # A=open, B=billed
                ms_block = ms.get("FAKSP", "")
                ms_vbeln = ms.get("VBELN", "")
                is_blocked = ms_block == "01"

                # Parse milestone date
                ms_date = None
                ms_date_str = ms.get("FDATU", "")
                if ms_date_str:
                    try:
                        ms_date = date.fromisoformat(ms_date_str)
                    except ValueError:
                        pass

                days_until_due = (ms_date - today).days if ms_date else 999

                # Look up billing doc clearing status
                clearing_date = None
                clearing_doc = ""
                if ms_vbeln and ms_vbeln in billing_doc_index:
                    bdoc = billing_doc_index[ms_vbeln]
                    cd = bdoc.get("clearing_date")
                    if cd:
                        try:
                            clearing_date = date.fromisoformat(cd)
                        except ValueError:
                            pass
                    clearing_doc = bdoc.get("clearing_doc", "") or ""

                # Classify milestone state
                state, action = self._classify_milestone(
                    ms_status,
                    is_blocked,
                    days_until_due,
                    ms_vbeln,
                    clearing_date,
                    ms_type,
                    ms_desc,
                    delivery_date,
                    today,
                )

                if not include_settled and state == MilestoneState.BILLED_PAID:
                    continue

                # Determine date derivation source
                sof_date_str = order.get("sof_date", "")
                sof_dt = None
                if sof_date_str:
                    try:
                        sof_dt = date.fromisoformat(sof_date_str)
                    except ValueError:
                        pass
                # FAZ (downpayment) → FDATU derived from SoF release date
                # F2 (invoice/progress) → FDATU derived from item first delivery date (EDATU)
                date_source = "SoF_RELEASE" if ms_type == "FAZ" else "ITEM_EDATU"

                alert = MilestoneAlert(
                    order_number=order_num,
                    customer_id=order_kunnr,
                    customer_name=customer_name,
                    order_value=order_value,
                    order_currency=order_currency,
                    milestone_seq=ms_seq,
                    milestone_desc=ms_desc,
                    milestone_amount=ms_amount,
                    milestone_pct=ms_pct,
                    milestone_type=ms_type,
                    milestone_date=ms_date,
                    delivery_date=delivery_date,
                    state=state,
                    days_until_due=days_until_due,
                    is_blocked=is_blocked,
                    billing_doc=ms_vbeln,
                    billing_status=ms_status,
                    clearing_date=clearing_date,
                    clearing_doc=clearing_doc,
                    action_required=action,
                    date_source=date_source,
                    sof_date=sof_dt,
                )
                alerts.append(alert)

        # Sort by urgency (most urgent first), then by days
        alerts.sort(key=lambda a: (STATE_PRIORITY.get(a.state, 99), a.days_until_due))

        return alerts

    def _classify_milestone(
        self,
        billing_status: str,
        is_blocked: bool,
        days_until_due: int,
        billing_doc: str,
        clearing_date: Optional[date],
        ms_type: str,
        ms_desc: str,
        delivery_date: Optional[date],
        today: date,
    ) -> tuple[MilestoneState, str]:
        """Classify a milestone into an actionable state with guidance."""

        type_label = "downpayment request" if ms_type == "FAZ" else "invoice"

        # BILLED milestones (FKSAF=B)
        if billing_status == "B":
            if billing_doc and clearing_date:
                return MilestoneState.BILLED_PAID, "Settled — no action required"
            elif billing_doc:
                return (
                    MilestoneState.BILLED_UNPAID,
                    f"Follow up payment for {type_label} {billing_doc}",
                )
            else:
                # Billed but no VBELN — treat as billed+unpaid
                return (
                    MilestoneState.BILLED_UNPAID,
                    f"Locate and link billing document for {ms_desc}",
                )

        # OPEN milestones (FKSAF=A)
        if is_blocked:
            if days_until_due < 0:
                return (
                    MilestoneState.BLOCKED,
                    f"Review billing block — {ms_desc} is D+{abs(days_until_due)} past due",
                )
            else:
                return (
                    MilestoneState.BLOCKED,
                    f"Blocked · {days_until_due} days until due (requires unblock)",
                )

        # Open + not blocked → timing-based classification
        if days_until_due < 0:
            return (
                MilestoneState.OVERDUE,
                f"Create {type_label} immediately — D+{abs(days_until_due)} overdue",
            )
        elif days_until_due <= 7:
            # Add delivery context for shipment-triggered milestones
            delivery_note = ""
            if delivery_date:
                del_days = (delivery_date - today).days
                if del_days > 0:
                    delivery_note = f" (delivery in {del_days} days)"
            return (
                MilestoneState.DUE_THIS_WEEK,
                f"Create {type_label} for {ms_desc} — due in {days_until_due} days{delivery_note}",
            )
        elif days_until_due <= 30:
            return (
                MilestoneState.DUE_THIS_MONTH,
                f"Prepare {type_label} for {ms_desc} — due in {days_until_due} days",
            )
        else:
            return (
                MilestoneState.UPCOMING,
                f"Scheduled — {ms_desc} due in {days_until_due} days",
            )

    async def get_summary(
        self,
        customer_id: Optional[str] = None,
    ) -> BillingBrainSummary:
        """Get aggregate milestone counts for badge display."""
        alerts = await self.get_all_alerts(
            customer_id=customer_id,
            include_settled=True,
        )

        summary = BillingBrainSummary()
        currencies = []

        order_numbers = set()
        for a in alerts:
            order_numbers.add(a.order_number)
            currencies.append(a.order_currency)

            if a.state == MilestoneState.OVERDUE:
                summary.overdue += 1
                summary.total_overdue_amount += a.milestone_amount
            elif a.state == MilestoneState.DUE_THIS_WEEK:
                summary.due_this_week += 1
                summary.total_due_soon_amount += a.milestone_amount
            elif a.state == MilestoneState.DUE_THIS_MONTH:
                summary.due_this_month += 1
                summary.total_due_soon_amount += a.milestone_amount
            elif a.state == MilestoneState.UPCOMING:
                summary.upcoming += 1
            elif a.state == MilestoneState.BLOCKED:
                summary.blocked += 1
                summary.total_overdue_amount += a.milestone_amount
            elif a.state == MilestoneState.BILLED_UNPAID:
                summary.billed_unpaid += 1
            elif a.state == MilestoneState.BILLED_PAID:
                summary.billed_paid += 1

        summary.total_action_required = (
            summary.overdue
            + summary.due_this_week
            + summary.blocked
            + summary.billed_unpaid
        )
        summary.order_count = len(order_numbers)
        if currencies:
            summary.currency = max(set(currencies), key=currencies.count)

        return summary
