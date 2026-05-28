"""
FinanceOps Data Models

Data structures for billing, collections, and payment terms management.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class PaymentTermType(str, Enum):
    """Type of payment term structure."""

    NET = "NET"  # Simple net payment (e.g., Net 30)
    ADVANCE = "ADVANCE"  # Advance payment required
    MILESTONE = "MILESTONE"  # Multi-milestone payment
    LC = "LC"  # Letter of Credit based
    COD = "COD"  # Cash on Delivery
    PREPAY = "PREPAY"  # Full prepayment
    UNKNOWN = "UNKNOWN"  # Could not parse


class PaymentMethod(str, Enum):
    """Payment method types."""

    TT = "TT"  # Telegraphic Transfer
    LC_SIGHT = "LC_SIGHT"  # Letter of Credit at Sight
    LC_30 = "LC_30"  # LC 30 days after sight
    LC_60 = "LC_60"  # LC 60 days after sight
    LC_90 = "LC_90"  # LC 90 days after sight
    CASH = "CASH"  # Cash payment
    CREDIT_LINE = "CREDIT_LINE"  # Use credit line
    UNKNOWN = "UNKNOWN"  # Could not determine


class TriggerEvent(str, Enum):
    """Payment milestone trigger events."""

    ORDER_PLACEMENT = "ORDER_PLACEMENT"  # Upon order/PO
    ORDER_CONFIRMATION = "ORDER_CONFIRMATION"  # Upon order confirmation
    INVOICE = "INVOICE"  # Upon invoice receipt
    BEFORE_SHIPMENT = "BEFORE_SHIPMENT"  # Before shipment/dispatch
    BEFORE_EXW = "BEFORE_EXW"  # Before ex-works
    FCA = "FCA"  # Free Carrier
    FAT = "FAT"  # Factory Acceptance Test
    SAT = "SAT"  # Site Acceptance Test
    NOR = "NOR"  # Notification of Readiness
    DELIVERY = "DELIVERY"  # Upon delivery
    DRAWING_DELIVERY = "DRAWING_DELIVERY"  # Upon drawing delivery
    COMMISSIONING = "COMMISSIONING"  # Upon commissioning
    CONTRACT_SIGNING = "CONTRACT_SIGNING"  # Upon contract signing
    UNKNOWN = "UNKNOWN"  # Could not determine


class BillingStatus(str, Enum):
    """Billing document status."""

    PENDING_BILLING = "PENDING_BILLING"  # Awaiting invoice creation
    PENDING_COLLECTION = "PENDING_COLLECTION"  # Invoice sent, awaiting payment
    PARTIALLY_PAID = "PARTIALLY_PAID"  # Partial payment received
    PAID = "PAID"  # Fully paid
    OVERDUE = "OVERDUE"  # Past due date
    DISPUTED = "DISPUTED"  # Under dispute


@dataclass
class PaymentMilestone:
    """A single payment milestone within a payment schedule."""

    percentage: float  # Payment percentage (e.g., 20.0)
    amount: Optional[float] = None  # Specific amount if mentioned
    currency: Optional[str] = None  # Currency if mentioned
    trigger: TriggerEvent = TriggerEvent.UNKNOWN  # When payment is due
    days_from_trigger: int = 0  # Days from trigger event
    payment_method: PaymentMethod = PaymentMethod.UNKNOWN
    terms_days: int = 0  # Net payment terms (e.g., 30, 60)
    description: str = ""  # Human-readable description
    requires_bank_guarantee: bool = False  # BG required for this milestone

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "percentage": self.percentage,
            "amount": self.amount,
            "currency": self.currency,
            "trigger": self.trigger.value,
            "days_from_trigger": self.days_from_trigger,
            "payment_method": self.payment_method.value,
            "terms_days": self.terms_days,
            "description": self.description,
            "requires_bank_guarantee": self.requires_bank_guarantee,
        }


@dataclass
class HarmonizedPaymentTerm:
    """Standardized payment term structure parsed from SAP text."""

    raw_text: str  # Original SAP text
    term_type: PaymentTermType = PaymentTermType.UNKNOWN
    milestones: list[PaymentMilestone] = field(default_factory=list)
    total_advance_pct: float = 0.0  # Sum of advance/downpayment %
    total_balance_pct: float = 0.0  # Sum of balance payment %
    primary_method: PaymentMethod = PaymentMethod.UNKNOWN
    has_lc: bool = False  # Requires Letter of Credit
    has_bank_guarantee: bool = False  # Requires Bank Guarantee
    confidence: float = 0.0  # Parsing confidence (0-1)
    parsing_notes: list[str] = field(default_factory=list)  # Parsing warnings/notes

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "raw_text": self.raw_text,
            "term_type": self.term_type.value,
            "milestones": [m.to_dict() for m in self.milestones],
            "total_advance_pct": self.total_advance_pct,
            "total_balance_pct": self.total_balance_pct,
            "primary_method": self.primary_method.value,
            "has_lc": self.has_lc,
            "has_bank_guarantee": self.has_bank_guarantee,
            "confidence": self.confidence,
            "parsing_notes": self.parsing_notes,
        }


@dataclass
class MilestoneStatus:
    """Status of a specific payment milestone."""

    milestone_index: int  # Index in the payment schedule
    percentage: float
    amount_due: float
    currency: str
    due_date: Optional[date] = None
    amount_paid: float = 0.0
    payment_date: Optional[date] = None
    status: str = "PENDING"  # PENDING, PAID, OVERDUE, PARTIAL
    days_overdue: int = 0  # Negative = not yet due

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "milestone_index": self.milestone_index,
            "percentage": self.percentage,
            "amount_due": self.amount_due,
            "currency": self.currency,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "amount_paid": self.amount_paid,
            "payment_date": (
                self.payment_date.isoformat() if self.payment_date else None
            ),
            "status": self.status,
            "days_overdue": self.days_overdue,
        }


@dataclass
class BillingItem:
    """A billing document/invoice for collections tracking."""

    document_number: str  # SAP billing doc number
    customer_id: str  # SAP customer ID
    customer_name: str
    document_date: date
    total_amount: float
    currency: str
    payment_term: HarmonizedPaymentTerm
    milestones: list[MilestoneStatus] = field(default_factory=list)
    status: BillingStatus = BillingStatus.PENDING_BILLING
    next_action_date: Optional[date] = None  # Next milestone due date
    days_to_action: int = 0  # Days until next action (negative = overdue)
    aging_bucket: str = (
        "CURRENT"  # "CURRENT" (green), "0-30" (amber), "30-45" (orange), "45+" (red)
    )
    billing_type: str = "F2"  # FAZ=downpayment request, F2=invoice
    sales_order: str = ""  # Linked SAP sales order number
    clearing_date: Optional[date] = None  # Date payment was cleared (FAZ)
    clearing_doc: str = ""  # Clearing document number (FAZ)

    @property
    def is_downpayment(self) -> bool:
        """Check if this is a downpayment request (FAZ)."""
        return self.billing_type == "FAZ"

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "document_number": self.document_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "document_date": self.document_date.isoformat(),
            "total_amount": self.total_amount,
            "currency": self.currency,
            "payment_term": self.payment_term.to_dict(),
            "milestones": [m.to_dict() for m in self.milestones],
            "status": self.status.value,
            "next_action_date": (
                self.next_action_date.isoformat() if self.next_action_date else None
            ),
            "days_to_action": self.days_to_action,
            "aging_bucket": self.aging_bucket,
            "billing_type": self.billing_type,
            "sales_order": self.sales_order,
            "is_downpayment": self.is_downpayment,
            "clearing_date": (
                self.clearing_date.isoformat() if self.clearing_date else None
            ),
            "clearing_doc": self.clearing_doc,
        }


@dataclass
class BillingSummary:
    """Summary statistics for billing dashboard."""

    billing_count: int = 0  # Pending billing items
    billing_amount: float = 0.0
    collections_count: int = 0  # Pending collection items
    collections_amount: float = 0.0
    overdue_count: int = 0  # Overdue items
    overdue_amount: float = 0.0
    downpayment_count: int = 0  # Actionable downpayment requests (pending/overdue)
    downpayment_amount: float = 0.0
    currency: str = "USD"  # Primary currency for display
    as_of_date: Optional[date] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "billing_count": self.billing_count,
            "billing_amount": self.billing_amount,
            "collections_count": self.collections_count,
            "collections_amount": self.collections_amount,
            "overdue_count": self.overdue_count,
            "overdue_amount": self.overdue_amount,
            "downpayment_count": self.downpayment_count,
            "downpayment_amount": self.downpayment_amount,
            "currency": self.currency,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
        }


class EscalationLevel(str, Enum):
    """Multi-level escalation tiers based on days overdue.

    D+1:  Level 1 — Sales Manager (initial notification)
    D+7:  Level 2 — Operations Lead (follow-up)
    D+14: Level 3 — Director (executive escalation)
    """

    L1 = "L1"  # D+1: Sales Manager
    L2 = "L2"  # D+7: Operations Lead
    L3 = "L3"  # D+14: Director

    @property
    def days_threshold(self) -> int:
        """Minimum days overdue to trigger this level."""
        return {"L1": 1, "L2": 7, "L3": 14}[self.value]

    @property
    def assigned_role(self) -> str:
        """Role responsible at this escalation level."""
        return {
            "L1": "sales_manager",
            "L2": "operations_lead",
            "L3": "director",
        }[self.value]

    @property
    def label(self) -> str:
        """Human-readable label for this level."""
        return {
            "L1": "Level 1 (Sales Manager)",
            "L2": "Level 2 (Operations Lead)",
            "L3": "Level 3 (Director)",
        }[self.value]


class EscalationStatus(str, Enum):
    """Status of an escalation event."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class EscalationEvent:
    """An escalation event for an overdue billing document."""

    customer_id: str
    customer_name: str
    document_number: str
    amount: float
    currency: str
    days_overdue: int
    level: EscalationLevel
    status: EscalationStatus = EscalationStatus.OPEN
    assigned_role: str = ""
    due_date: Optional[date] = None

    def __post_init__(self):
        if not self.assigned_role:
            self.assigned_role = self.level.assigned_role

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "document_number": self.document_number,
            "amount": self.amount,
            "currency": self.currency,
            "days_overdue": self.days_overdue,
            "level": self.level.value,
            "level_label": self.level.label,
            "status": self.status.value,
            "assigned_role": self.assigned_role,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }


@dataclass
class CollectionsSummary:
    """Collections summary with aging breakdown."""

    total_outstanding: float = 0.0
    currency: str = "USD"
    aging_buckets: dict = field(
        default_factory=dict
    )  # {"CURRENT": {count, amount}, ...}
    top_customers: list = field(default_factory=list)  # [{customer_id, name, amount}]
    as_of_date: Optional[date] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "total_outstanding": self.total_outstanding,
            "currency": self.currency,
            "aging_buckets": self.aging_buckets,
            "top_customers": self.top_customers,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
        }
