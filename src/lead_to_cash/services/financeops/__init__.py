"""
FinanceOps Service Module

Provides billing, collections, and payment terms management services
for the Finance Operations Agent.

Components:
    - PaymentTermsHarmonizer: Parse and standardize SAP payment terms text
    - FinOpsDataService: Aggregate billing/collections data
    - Models: Data structures for billing items, payment milestones

Usage:
    from lead_to_cash.services.financeops import (
        PaymentTermsHarmonizer,
        FinOpsDataService,
        BillingItem,
        HarmonizedPaymentTerm,
    )

    # Parse payment terms
    harmonizer = PaymentTermsHarmonizer()
    terms = harmonizer.parse("20% advance by TT, 80% balance before shipment")

    # Get billing summary
    service = FinOpsDataService()
    summary = await service.get_summary_counts()
"""

from lead_to_cash.services.financeops.data_service import FinOpsDataService
from lead_to_cash.services.financeops.escalation_service import EscalationService
from lead_to_cash.services.financeops.models import (
    BillingItem,
    BillingSummary,
    CollectionsSummary,
    EscalationEvent,
    EscalationLevel,
    EscalationStatus,
    HarmonizedPaymentTerm,
    MilestoneStatus,
    PaymentMethod,
    PaymentMilestone,
    PaymentTermType,
    TriggerEvent,
)
from lead_to_cash.services.financeops.payment_terms import PaymentTermsHarmonizer

__all__ = [
    # Models
    "PaymentTermType",
    "PaymentMethod",
    "TriggerEvent",
    "PaymentMilestone",
    "HarmonizedPaymentTerm",
    "MilestoneStatus",
    "BillingItem",
    "BillingSummary",
    "CollectionsSummary",
    "EscalationLevel",
    "EscalationStatus",
    "EscalationEvent",
    # Services
    "PaymentTermsHarmonizer",
    "FinOpsDataService",
    "EscalationService",
]
