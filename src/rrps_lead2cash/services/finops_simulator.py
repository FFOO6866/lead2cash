"""
FinOps Simulator Service.

Provides simulated financial operations data for the POV demo:
- Billing status and down payment tracking
- Collections and aging analysis
- Payment terms and financial document references

Data is based on real SAP table structures (BKPF/BSEG) but uses
static demo data derived from actual ST Engineering reference order.

Production will replace this with real SAP CPI calls to:
- BAPI_AR_ACC_GETKEYFIGURES (aging)
- BKPF/BSEG reads (financial documents)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# FinOps Models
# ============================================================================

class DownPayment(BaseModel):
    """Single down payment record (maps to SAP BKPF/BSEG)."""
    billing_doc: str = Field(..., description="SAP billing document number")
    percentage: float = Field(..., description="Down payment percentage")
    amount: float = Field(..., description="Down payment amount in local currency")
    currency: str = Field(default="EUR", description="Currency code")
    financial_doc: str = Field(default="", description="SAP financial document (BKPF BELNR)")
    clearing_date: str = Field(default="", description="Clearing entry date (BSEG AUGCP)")
    clearing_doc: str = Field(default="", description="Clearing document (BSEG AUGBL)")
    status: str = Field(default="OPEN", description="CLEARED, OPEN, or OVERDUE")
    company_code: str = Field(default="0011", description="SAP company code (BUKRS)")


class BillingStatus(BaseModel):
    """Billing overview for an order."""
    sales_order: str = Field(..., description="SAP sales order number")
    customer_id: str = Field(..., description="SAP customer number")
    customer_name: str = Field(default="", description="Customer name")
    order_value: float = Field(default=0.0, description="Total order value")
    currency: str = Field(default="EUR", description="Currency code")
    payment_terms_desc: str = Field(default="", description="Payment terms description")
    down_payments: List[DownPayment] = Field(default_factory=list, description="Down payment details")
    total_billed: float = Field(default=0.0, description="Total amount billed")
    total_collected: float = Field(default=0.0, description="Total amount collected/cleared")
    outstanding: float = Field(default=0.0, description="Outstanding balance")
    billing_plan_active: bool = Field(default=True, description="Billing plan is active")
    status: str = Field(default="ON_TRACK", description="ON_TRACK, AT_RISK, OVERDUE")


class AgingBucket(BaseModel):
    """Single aging bucket for receivables analysis."""
    bucket: str = Field(..., description="Aging bucket label")
    amount: float = Field(default=0.0, description="Amount in bucket")
    currency: str = Field(default="EUR", description="Currency code")
    doc_count: int = Field(default=0, description="Number of documents in bucket")


class AgingAnalysis(BaseModel):
    """Receivables aging analysis for a customer."""
    customer_id: str = Field(..., description="SAP customer number")
    customer_name: str = Field(default="", description="Customer name")
    company_code: str = Field(default="0011", description="SAP company code")
    total_receivables: float = Field(default=0.0, description="Total outstanding receivables")
    currency: str = Field(default="EUR", description="Currency code")
    buckets: List[AgingBucket] = Field(default_factory=list, description="Aging buckets")
    risk_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH based on aging profile")
    as_of_date: str = Field(default="", description="Analysis date")


class FinancialSummary(BaseModel):
    """Financial summary for a customer across all orders."""
    customer_id: str
    customer_name: str
    total_order_value: float
    total_billed: float
    total_collected: float
    total_outstanding: float
    currency: str
    orders: List[BillingStatus]
    aging: AgingAnalysis
    source: str = Field(default="CPI_SIMULATOR", description="Data source indicator")


# ============================================================================
# Demo Data — ST Engineering (from actual SAP reference data)
# ============================================================================

# Reference: Sales Order 3228005147, Customer 0022005992
# Down payments: 3851802713 (20% = 12,526), 3851802753 (80% = 50,104)
# NOTE: Order is EUR-denominated. Credit limit is in SGD (per SAP CCA 0111).
# RRPS contracts are commonly EUR even for SGD-credit customers.

_STE_BILLING = BillingStatus(
    sales_order="3228005147",
    customer_id="0022005992",
    customer_name="ST Engineering Marine Ltd",
    order_value=62630.00,
    currency="EUR",
    payment_terms_desc="20% Downpayment by T/T, 80% Balance upon notification of readiness for shipment by T/T",
    down_payments=[
        DownPayment(
            billing_doc="3851802713",
            percentage=20.0,
            amount=12526.00,
            currency="EUR",
            financial_doc="5130025522",
            clearing_date="20250620",
            clearing_doc="5140059754",
            status="CLEARED",
            company_code="0011",
        ),
        DownPayment(
            billing_doc="3851802753",
            percentage=80.0,
            amount=50104.00,
            currency="EUR",
            financial_doc="5130025815",
            clearing_date="20250730",
            clearing_doc="5140060121",
            status="CLEARED",
            company_code="0011",
        ),
    ],
    total_billed=62630.00,
    total_collected=62630.00,
    outstanding=0.00,
    billing_plan_active=True,
    status="ON_TRACK",
)

_STE_AGING = AgingAnalysis(
    customer_id="0022005992",
    customer_name="ST Engineering Marine Ltd",
    company_code="0011",
    total_receivables=0.00,
    currency="EUR",
    buckets=[
        AgingBucket(bucket="CURRENT", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="1-30", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="31-60", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="61-90", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="90+", amount=0.00, currency="EUR", doc_count=0),
    ],
    risk_level="LOW",
    as_of_date="20260319",
)

# ============================================================================
# Demo Data — CLLS POWER SYSTEM LTD (billing/payment simulation)
# ============================================================================

# Reference: Customer 0021000090
# NOTE: Credit data (limit, exposure) comes from REAL CPI — not this simulator

_CLLS_BILLING = BillingStatus(
    sales_order="3228006201",
    customer_id="0021000090",
    customer_name="CLLS POWER SYSTEM LTD",
    order_value=45000.00,
    currency="EUR",
    payment_terms_desc="30% Downpayment, 70% Balance upon delivery",
    down_payments=[
        DownPayment(
            billing_doc="3851803101",
            percentage=30.0,
            amount=13500.00,
            currency="EUR",
            financial_doc="5130026101",
            clearing_date="20260115",
            clearing_doc="5140060501",
            status="CLEARED",
            company_code="0011",
        ),
    ],
    total_billed=45000.00,
    total_collected=13500.00,
    outstanding=31500.00,
    billing_plan_active=True,
    status="ON_TRACK",
)

_CLLS_AGING = AgingAnalysis(
    customer_id="0021000090",
    customer_name="CLLS POWER SYSTEM LTD",
    company_code="0011",
    total_receivables=31500.00,
    currency="EUR",
    buckets=[
        AgingBucket(bucket="CURRENT", amount=31500.00, currency="EUR", doc_count=1),
        AgingBucket(bucket="1-30", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="31-60", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="61-90", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="90+", amount=0.00, currency="EUR", doc_count=0),
    ],
    risk_level="LOW",
    as_of_date="20260319",
)


# ============================================================================
# Demo Data — TIANJIN DINGSHENG CONSTRUCTION MACHINERY CO. LTD (billing/payment simulation)
# ============================================================================

# Reference: Customer 0022005601
# NOTE: Credit data (limit, exposure, BLOCKED status) comes from REAL CPI — not this simulator

_TIANJIN_BILLING = BillingStatus(
    sales_order="3228007450",
    customer_id="0022005601",
    customer_name="TIANJIN DINGSHENG CONSTRUCTION MACHINERY CO. LTD",
    order_value=5200000.00,
    currency="EUR",
    payment_terms_desc="20% Downpayment by L/C, 80% upon milestone completion",
    down_payments=[
        DownPayment(
            billing_doc="3851804201",
            percentage=20.0,
            amount=1040000.00,
            currency="EUR",
            financial_doc="5130027001",
            clearing_date="",
            clearing_doc="",
            status="OVERDUE",
            company_code="0011",
        ),
    ],
    total_billed=1040000.00,
    total_collected=0.00,
    outstanding=1040000.00,
    billing_plan_active=True,
    status="OVERDUE",
)

_TIANJIN_AGING = AgingAnalysis(
    customer_id="0022005601",
    customer_name="TIANJIN DINGSHENG CONSTRUCTION MACHINERY CO. LTD",
    company_code="0011",
    total_receivables=1040000.00,
    currency="EUR",
    buckets=[
        AgingBucket(bucket="CURRENT", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="1-30", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="31-60", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="61-90", amount=0.00, currency="EUR", doc_count=0),
        AgingBucket(bucket="90+", amount=1040000.00, currency="EUR", doc_count=1),
    ],
    risk_level="HIGH",
    as_of_date="20260319",
)


# Index by customer ID
_BILLING_DATA: Dict[str, List[BillingStatus]] = {
    "0022005992": [_STE_BILLING],
    "0021000090": [_CLLS_BILLING],
    "0022005601": [_TIANJIN_BILLING],
}

_AGING_DATA: Dict[str, AgingAnalysis] = {
    "0022005992": _STE_AGING,
    "0021000090": _CLLS_AGING,
    "0022005601": _TIANJIN_AGING,
}

# Also index by sales order
_BILLING_BY_ORDER: Dict[str, BillingStatus] = {
    "3228005147": _STE_BILLING,
    "3228006201": _CLLS_BILLING,
    "3228007450": _TIANJIN_BILLING,
}


# ============================================================================
# Service
# ============================================================================

class FinOpsSimulator:
    """
    Simulated FinOps service for POV demo.

    Returns billing, collections, and aging data based on real
    SAP reference data (BKPF/BSEG tables) for demo customers.

    Source: CPI_SIMULATOR (clearly labeled — not real SAP data).
    """

    def get_billing_status(self, sales_order: str) -> Optional[BillingStatus]:
        """Get billing status for a sales order."""
        return _BILLING_BY_ORDER.get(sales_order)

    def get_customer_billing(self, customer_id: str) -> List[BillingStatus]:
        """Get all billing records for a customer."""
        return _BILLING_DATA.get(customer_id, [])

    def get_aging_analysis(self, customer_id: str) -> Optional[AgingAnalysis]:
        """Get receivables aging analysis for a customer."""
        return _AGING_DATA.get(customer_id)

    def get_financial_summary(self, customer_id: str) -> Optional[FinancialSummary]:
        """Get complete financial summary for a customer."""
        orders = self.get_customer_billing(customer_id)
        aging = self.get_aging_analysis(customer_id)

        if not orders and not aging:
            return None

        customer_name = ""
        total_order_value = 0.0
        total_billed = 0.0
        total_collected = 0.0
        total_outstanding = 0.0
        currency = "EUR"

        for o in orders:
            customer_name = customer_name or o.customer_name
            total_order_value += o.order_value
            total_billed += o.total_billed
            total_collected += o.total_collected
            total_outstanding += o.outstanding
            currency = o.currency

        if aging is None:
            aging = AgingAnalysis(
                customer_id=customer_id,
                customer_name=customer_name,
                total_receivables=total_outstanding,
                currency=currency,
                buckets=[
                    AgingBucket(bucket="CURRENT", amount=total_outstanding, currency=currency),
                    AgingBucket(bucket="1-30", amount=0.0, currency=currency),
                    AgingBucket(bucket="31-60", amount=0.0, currency=currency),
                    AgingBucket(bucket="61-90", amount=0.0, currency=currency),
                    AgingBucket(bucket="90+", amount=0.0, currency=currency),
                ],
                as_of_date=datetime.utcnow().strftime("%Y%m%d"),
            )

        return FinancialSummary(
            customer_id=customer_id,
            customer_name=customer_name,
            total_order_value=total_order_value,
            total_billed=total_billed,
            total_collected=total_collected,
            total_outstanding=total_outstanding,
            currency=currency,
            orders=orders,
            aging=aging,
            source="CPI_SIMULATOR",
        )

    def list_customers(self) -> List[Dict[str, Any]]:
        """List customers with financial data."""
        results = []
        for cid, orders in _BILLING_DATA.items():
            name = orders[0].customer_name if orders else ""
            total = sum(o.order_value for o in orders)
            outstanding = sum(o.outstanding for o in orders)
            results.append({
                "customer_id": cid,
                "customer_name": name,
                "order_count": len(orders),
                "total_order_value": total,
                "total_outstanding": outstanding,
                "currency": orders[0].currency if orders else "EUR",
            })
        return results
