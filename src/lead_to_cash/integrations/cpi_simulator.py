"""
SAP CPI Simulator - Mock SAP System Responses

Simulates SAP CPI gateway responses for development and testing.
Implements the same interface as CPIClient so it can be swapped in.

This simulator is designed to be a drop-in replacement for CPIClient
when SAP systems are not available (development, testing, demos).

SAP BAPIs Simulated:
    - BAPI_CUSTOMER_GETDETAIL2: Customer master data (KNA1, BAPICUSTOMER_04)
    - BAPI_CR_ACC_GETDETAIL: Credit management data (KNKK table)
    - BAPI_SALESORDER_SIMULATE: Order simulation
    - BAPI_SALESORDER_CREATEFROMDAT2: Order creation
    - BAPI_SALESORDER_GETDETAIL: Full order read with billing plan (FPLT/FPLTR)
    - BAPI_SALESORDER_GETSTATUS: Per-item delivery & billing status
    - BILLING_SCHEDULE_READ: Billing plan milestones
    - BAPI_BILLINGDOC_GETDETAIL1: Billing document header + items
    - BAPI_AR_ACC_GETOPENITEMS: Open AR receivables

iFlow Names (matching existing MS5Client/CECClient usage):
    - CustomerGetDetail: Customer master data
    - CreditGetAccount: Credit check
    - CustomerGetPartners: Partner functions
    - OrderSimulate: Order simulation
    - OrderCreate: Order creation
    - CECGetCommercialTerms: Commercial terms
    - MS5GetOrderDetail: Sales order with billing plan
    - MS5GetOrderStatus: Order delivery/billing status
    - MS5GetBillingPlan: Billing plan milestones (FPLT/FPLTR)
    - MS5GetBillingDocDetail: Billing document detail (VBRK/VBRP)
    - MS5GetOpenARItems: Open AR items for collections

Usage:
    # As drop-in replacement for CPIClient
    from lead_to_cash.integrations.cpi_simulator import CPISimulator

    # Instead of: cpi = CPIClient()
    cpi = CPISimulator()

    # Use with MS5Client
    ms5 = MS5Client(cpi_client=cpi)
    await ms5.connect()
    customer = await ms5.get_customer("0000100001")
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# SAP Constants (matching ms5_client.py)
# =============================================================================


class SAPMessageTypes:
    """SAP BAPI message types (field TYPE in BAPIRET1/BAPIRET2)."""

    SUCCESS = "S"
    ERROR = "E"
    WARNING = "W"
    INFO = "I"
    ABORT = "A"


class SAPPartnerRoles:
    """SAP partner function codes (PARVW field)."""

    SOLD_TO = "AG"
    SHIP_TO = "WE"
    BILL_TO = "RE"
    PAYER = "RG"


# =============================================================================
# Simulated Customer Data
# =============================================================================


@dataclass
class SimulatedCustomer:
    """Simulated customer data aligned with SAP structures."""

    # KNA1 Key Fields
    kunnr: str  # Customer number (10 chars, left-padded with zeros)
    bukrs: str = "1000"  # Company code

    # BAPICUSTOMER_04 Address Fields (matches MS5Client expectations)
    name1: str = ""
    name2: str = ""
    street: str = ""
    city: str = ""  # Maps to CITY1
    postl_code: str = ""  # Maps to POST_CODE1
    region: str = ""
    country: str = ""
    countryiso: str = ""
    telephone: str = ""
    fax: str = ""
    email: str = ""

    # Tax Number Fields (for KYP)
    stcd1: str = ""  # Tax Number 1 - UEN for Singapore
    stcd2: str = ""  # Tax Number 2

    # KNKK Credit Management Fields
    kkber: str = "1000"  # Credit control area
    klimk: float = 0.0  # Credit limit
    skfor: float = 0.0  # Total receivables
    sauft: float = 0.0  # Open order values
    ctlpc: str = ""  # Risk category (001=Low, 002=Medium, 003=Medium-High, 004=High)
    crblb: str = ""  # Credit block indicator

    # Sales Area Data (KNVV)
    vkorg: str = ""  # Sales organization
    vtweg: str = ""  # Distribution channel
    spart: str = ""  # Division
    zterm: str = ""  # Payment terms
    inco1: str = ""  # Incoterms part 1
    inco2: str = ""  # Incoterms location
    waerk: str = "EUR"  # Currency

    # Partner Functions
    partner_functions: list = field(default_factory=list)


# Sample customers including BatamFast (from KYP document)
SIMULATED_CUSTOMERS: dict[str, SimulatedCustomer] = {
    "0000100001": SimulatedCustomer(
        kunnr="0000100001",
        bukrs="1000",
        name1="Batam Fast Ferry Pte. Ltd.",
        name2="BatamFast",
        street="1 Harbour Front Place",
        city="Singapore",
        postl_code="098633",
        country="SG",
        countryiso="SG",
        telephone="+65 6270 2228",
        fax="+65 6270 2229",
        email="operations@batamfast.com.sg",
        stcd1="199901234A",  # UEN for Singapore
        stcd2="",
        klimk=500000.00,
        skfor=320000.00,
        sauft=75000.00,
        ctlpc="003",  # Medium-High risk
        vkorg="SG01",
        vtweg="10",
        spart="00",
        zterm="NT30",
        inco1="FOB",
        inco2="Singapore",
        waerk="SGD",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100001",
                "NAME": "Batam Fast Ferry Pte. Ltd.",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0000100001",
                "NAME": "Batam Fast Ferry Pte. Ltd.",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0000100001",
                "NAME": "Batam Fast Ferry Pte. Ltd.",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0000100001",
                "NAME": "Batam Fast Ferry Pte. Ltd.",
            },
        ],
    ),
    "0000100002": SimulatedCustomer(
        kunnr="0000100002",
        bukrs="1000",
        name1="A.P. Moller - Maersk A/S",
        name2="Maersk Line",
        street="Esplanaden 50",
        city="Copenhagen",
        postl_code="1098",
        country="DK",
        countryiso="DK",
        telephone="+45 33 63 33 63",
        email="info@maersk.com",
        stcd1="25505933",  # Danish CVR number
        stcd2="DK25505933",  # VAT number
        klimk=10000000.00,
        skfor=2500000.00,
        sauft=500000.00,
        ctlpc="001",  # Low risk
        vkorg="EU01",
        vtweg="10",
        spart="00",
        zterm="NT60",
        inco1="CIF",
        inco2="Copenhagen",
        waerk="EUR",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100002",
                "NAME": "A.P. Moller - Maersk A/S",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0000100003",
                "NAME": "Maersk Shipping Rotterdam",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0000100002",
                "NAME": "A.P. Moller - Maersk A/S",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0000100002",
                "NAME": "A.P. Moller - Maersk A/S",
            },
        ],
    ),
    "0000100003": SimulatedCustomer(
        kunnr="0000100003",
        bukrs="1000",
        name1="Neptune Energy Netherlands B.V.",
        name2="Neptune Energy",
        street="Bezuidenhoutseweg 195",
        city="Den Haag",
        postl_code="2594 AH",
        country="NL",
        countryiso="NL",
        telephone="+31 70 373 8300",
        email="info.netherlands@neptuneenergy.com",
        klimk=2000000.00,
        skfor=800000.00,
        sauft=200000.00,
        ctlpc="002",  # Medium risk
        vkorg="EU01",
        vtweg="10",
        spart="00",
        zterm="NT45",
        inco1="DDP",
        inco2="Rotterdam",
        waerk="EUR",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100003",
                "NAME": "Neptune Energy Netherlands B.V.",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0000100003",
                "NAME": "Neptune Energy Netherlands B.V.",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0000100003",
                "NAME": "Neptune Energy Netherlands B.V.",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0000100003",
                "NAME": "Neptune Energy Netherlands B.V.",
            },
        ],
    ),
    "0000100004": SimulatedCustomer(
        kunnr="0000100004",
        bukrs="1000",
        name1="Blocked Marine Services Ltd.",
        street="123 Port Road",
        city="Lagos",
        country="NG",
        countryiso="NG",
        klimk=100000.00,
        skfor=150000.00,  # Over limit
        ctlpc="004",  # High risk
        crblb="X",  # Credit blocked
        zterm="PREPAY",
        waerk="USD",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100004",
                "NAME": "Blocked Marine Services Ltd.",
            },
        ],
    ),
    "0000100005": SimulatedCustomer(
        kunnr="0000100005",
        bukrs="1000",
        name1="Pacific Maritime Solutions Pty Ltd",
        street="100 Wharf Street",
        city="Brisbane",
        postl_code="4000",
        region="QLD",
        country="AU",
        countryiso="AU",
        telephone="+61 7 3000 0000",
        email="contact@pacificmaritime.com.au",
        klimk=50000.00,
        skfor=0.00,
        ctlpc="002",  # Medium (new customer)
        vkorg="AP01",
        vtweg="10",
        spart="00",
        zterm="PREPAY",
        inco1="FOB",
        inco2="Brisbane",
        waerk="AUD",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100005",
                "NAME": "Pacific Maritime Solutions Pty Ltd",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0000100005",
                "NAME": "Pacific Maritime Solutions Pty Ltd",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0000100005",
                "NAME": "Pacific Maritime Solutions Pty Ltd",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0000100005",
                "NAME": "Pacific Maritime Solutions Pty Ltd",
            },
        ],
    ),
    "0022005992": SimulatedCustomer(
        kunnr="0022005992",
        bukrs="1000",
        name1="ST Engineering Ltd",
        name2="ST Engineering",
        street="1 Ang Mo Kio Electronics Park Road",
        city="Singapore",
        postl_code="567710",
        country="SG",
        countryiso="SG",
        telephone="+65 6722 1818",
        email="info@stengg.com",
        stcd1="199706231H",  # UEN for Singapore
        stcd2="",
        klimk=100000.00,  # Credit limit: 100k
        skfor=0.00,  # No exposure
        sauft=0.00,  # No open orders
        ctlpc="001",  # Low risk
        vkorg="SG01",
        vtweg="10",
        spart="00",
        zterm="NT30",
        inco1="FOB",
        inco2="Singapore",
        waerk="SGD",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0022005992",
                "NAME": "ST Engineering Ltd",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0022005992",
                "NAME": "ST Engineering Ltd",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0022005992",
                "NAME": "ST Engineering Ltd",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0022005992",
                "NAME": "ST Engineering Ltd",
            },
        ],
    ),
    # CLLS Power System - SSG Engines customer (EUR)
    "0021000090": SimulatedCustomer(
        kunnr="0021000090",
        bukrs="1000",
        name1="CLLS Power System LTD",
        name2="CLLS Power",
        street="Industrial Park Road",
        city="Singapore",
        postl_code="628500",
        country="SG",
        countryiso="SG",
        telephone="+65 6800 1234",
        email="info@cllspower.com",
        stcd1="",  # UEN not provided
        stcd2="",
        kkber="0111",  # SSG Engines Credit Cntrl Area
        klimk=150000.00,  # Credit limit: 150k EUR
        skfor=14023.07,  # Receivables/Credit exposure
        sauft=0.00,  # No open orders
        ctlpc="002",  # Medium risk (9.35% utilization)
        vkorg="SG01",
        vtweg="10",
        spart="00",
        zterm="NT30",
        inco1="FOB",
        inco2="Singapore",
        waerk="EUR",  # Euro currency
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0021000090",
                "NAME": "CLLS Power System LTD",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0021000090",
                "NAME": "CLLS Power System LTD",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0021000090",
                "NAME": "CLLS Power System LTD",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0021000090",
                "NAME": "CLLS Power System LTD",
            },
        ],
    ),
    # Tianjin Dingsheng Construction - Chinese customer (USD)
    "0000100006": SimulatedCustomer(
        kunnr="0000100006",
        bukrs="1000",
        name1="Tianjin Dingsheng Construction Co., Ltd.",
        name2="Dingsheng Construction",
        street="No. 88 Binhai Industrial Zone",
        city="Tianjin",
        postl_code="300457",
        country="CN",
        countryiso="CN",
        telephone="+86 22 6625 8888",
        email="contact@dingsheng-cn.com",
        stcd1="",  # Chinese tax number not provided
        stcd2="",
        klimk=3000000.00,  # Credit limit: 3M USD
        skfor=1200000.00,  # Current receivables
        sauft=800000.00,  # Open orders
        ctlpc="002",  # Medium risk
        vkorg="CN01",
        vtweg="10",
        spart="00",
        zterm="20% down payment, 80% balance T/T before EXW",
        inco1="EXW",
        inco2="Friedrichshafen",
        waerk="USD",
        partner_functions=[
            {
                "PARTN_ROLE": "AG",
                "PARTN_NUMB": "0000100006",
                "NAME": "Tianjin Dingsheng Construction Co., Ltd.",
            },
            {
                "PARTN_ROLE": "WE",
                "PARTN_NUMB": "0000100006",
                "NAME": "Tianjin Dingsheng Construction Co., Ltd.",
            },
            {
                "PARTN_ROLE": "RE",
                "PARTN_NUMB": "0000100006",
                "NAME": "Tianjin Dingsheng Construction Co., Ltd.",
            },
            {
                "PARTN_ROLE": "RG",
                "PARTN_NUMB": "0000100006",
                "NAME": "Tianjin Dingsheng Construction Co., Ltd.",
            },
        ],
    ),
}

# Suffixes to strip when generating name lookup variants
_CORPORATE_SUFFIXES = (
    "pte. ltd.",
    "pte ltd",
    "a/s",
    "b.v.",
    "co., ltd.",
    "pty ltd",
    "ltd.",
    "ltd",
    "inc.",
    "inc",
    "corp.",
)


def _build_customer_name_lookup() -> dict[str, str]:
    """Auto-generate name lookup from SIMULATED_CUSTOMERS — single source of truth."""
    lookup: dict[str, str] = {}
    for cust_id, cust in SIMULATED_CUSTOMERS.items():
        for raw_name in (cust.name1, cust.name2):
            if not raw_name:
                continue
            name = raw_name.strip()
            # Full name
            lookup.setdefault(name.lower(), cust_id)
            # Stripped version (remove corporate suffixes)
            stripped = name.lower()
            for suffix in _CORPORATE_SUFFIXES:
                if stripped.endswith(suffix):
                    stripped = stripped[: -len(suffix)].rstrip(" ,.-")
                    break
            if stripped and stripped != name.lower():
                lookup.setdefault(stripped, cust_id)
            # Individual significant words (2+ chars, not common suffixes)
            words = [
                w
                for w in name.split()
                if len(w) >= 2
                and w.lower() not in {"pte", "ltd", "a/s", "b.v.", "co.,", "pty"}
            ]
            # First word alone (e.g. "batamfast", "maersk", "neptune")
            if words and len(words[0]) >= 4:
                lookup.setdefault(words[0].lower(), cust_id)
            # First two words (e.g. "batam fast", "neptune energy", "blocked marine")
            if len(words) >= 2:
                lookup.setdefault(f"{words[0].lower()} {words[1].lower()}", cust_id)
    return lookup


# Name lookup for natural language queries (auto-generated from SIMULATED_CUSTOMERS)
CUSTOMER_NAME_LOOKUP: dict[str, str] = _build_customer_name_lookup()


# =============================================================================
# Simulated Opportunities (CEC Data)
# Used by CECGetOpportunitiesByAccount to derive business metrics
# =============================================================================

# =============================================================================
# Simulated CEC Opportunities (ADR-006: includes milestone payment fields)
# =============================================================================
# Fields per ADR-006:
#   - id: Opportunity ID
#   - account_id: SAP Customer ID (10-digit)
#   - account_name: Customer name
#   - status: Won, Lost, Open, Qualified
#   - expected_revenue: Expected value
#   - currency: ISO 4217 (EUR, USD, SGD)
#   - close_date: Expected close/award date
#   - start_date: Creation date (NEW)
#   - title: Opportunity name/subject (NEW)
#   - win_probability: 10, 35, 65, 90 (NEW)
#   - sales_type: OE_SALES or SERVICE_SALES (NEW)
#   - sap_order_id: SAP Sales Order Number (NEW - milestone payment)
#   - ipas_quote_id: IPAS Quote Number (NEW - milestone payment)
#   - products: Product list

SIMULATED_OPPORTUNITIES: dict[str, list[dict]] = {
    # =========================================================================
    # CLEARED: Opportunities now come from REAL SAP CPI (Integrum/GetOpportunity)
    # CEC_USE_REAL_CPI=true enables real CPI calls in CECClient
    # Simulator data removed — CPI iFlow fixed by Sri (CustomerNo field corrected)
    # =========================================================================
}


# =============================================================================
# Simulated Billing Documents (for FinanceOps Dashboard)
# =============================================================================


def _get_dynamic_billing_docs() -> dict[str, dict]:
    """
    Generate billing documents with dates relative to today.

    This ensures billing documents always have sensible dates regardless
    of when the simulator is used (avoiding stale hardcoded dates).

    Returns:
        Dictionary of billing documents keyed by document number
    """
    from datetime import date, timedelta

    today = date.today()

    return {
        # =====================================================================
        # Milestone Invoices (F2) - linked to sales orders with billing plans
        # =====================================================================
        # Batam Fast Ferry - Milestone 2 invoice (30% before shipment)
        "3228005112": {
            "document_number": "3228005112",
            "customer_id": "0000100001",
            "customer_name": "Batam Fast Ferry Pte. Ltd.",
            "amount": 126000.00,
            "currency": "SGD",
            "document_date": (today - timedelta(days=50)).isoformat(),
            "due_date": (today + timedelta(days=10)).isoformat(),
            "status": "PENDING_BILLING",
            "billing_type": "F2",
            "sales_order": "1000022101",
            "sales_order_item": "000010",
            "payment_terms_text": (
                "20% advance payment by TT within 30 days upon invoice\n"
                "Balance 80% utilise credit line payable within 60 days after invoice upon dispatch"
            ),
        },
        # ST Engineering - Milestone 2 invoice (80% before EXW)
        "3228005113": {
            "document_number": "3228005113",
            "customer_id": "0022005992",
            "customer_name": "ST Engineering Ltd",
            "amount": 336000.00,
            "currency": "SGD",
            "document_date": (today - timedelta(days=75)).isoformat(),
            "due_date": (today + timedelta(days=15)).isoformat(),
            "status": "PENDING_COLLECTION",
            "billing_type": "F2",
            "sales_order": "1000024001",
            "sales_order_item": "000010",
            "payment_terms_text": "100% upon FCA, due 90 days from invoice",
        },
        # ST Engineering - Service contract (no billing plan)
        "3228005117": {
            "document_number": "3228005117",
            "customer_id": "0022005992",
            "customer_name": "ST Engineering Ltd",
            "amount": 85000.00,
            "currency": "SGD",
            "document_date": (today - timedelta(days=55)).isoformat(),
            "due_date": (today + timedelta(days=5)).isoformat(),
            "status": "PENDING_COLLECTION",
            "billing_type": "F2",
            "sales_order": "1000025001",
            "sales_order_item": "000010",
            "payment_terms_text": "Net 60 days from invoice",
        },
        # CLLS Power - Milestone 2 invoice (10% 9mo before delivery) - OVERDUE
        "3228005114": {
            "document_number": "3228005114",
            "customer_id": "0021000090",
            "customer_name": "CLLS Power System LTD",
            "amount": 18000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=120)).isoformat(),
            "due_date": (today - timedelta(days=30)).isoformat(),
            "status": "OVERDUE",
            "billing_type": "F2",
            "sales_order": "1000023301",
            "sales_order_item": "000010",
            "payment_terms_text": (
                "10% upon order 90 days, "
                "10% 9mo before delivery 30 days, "
                "80% before collection 90 days"
            ),
        },
        # Tianjin Dingsheng - Milestone 2 invoice (80% TT before EXW)
        "3228005115": {
            "document_number": "3228005115",
            "customer_id": "0000100006",
            "customer_name": "Tianjin Dingsheng Construction Co., Ltd.",
            "amount": 1760000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=25)).isoformat(),
            "due_date": (today + timedelta(days=25)).isoformat(),
            "status": "PENDING_BILLING",
            "billing_type": "F2",
            "sales_order": "1000100006",
            "sales_order_item": "000010",
            "payment_terms_text": "20% down payment, 80% balance T/T before EXW",
        },
        # Maersk - Milestone 2 invoice (70% L/C before shipment) - Partially Paid
        "3228005116": {
            "document_number": "3228005116",
            "customer_id": "0000100002",
            "customer_name": "A.P. Moller - Maersk A/S",
            "amount": 385000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=90)).isoformat(),
            "due_date": (today + timedelta(days=3)).isoformat(),
            "status": "PARTIALLY_PAID",
            "billing_type": "F2",
            "sales_order": "1000024201",
            "sales_order_item": "000010",
            "payment_terms_text": (
                "30% DP by TT within 30 days upon PO, "
                "70% by Irrevocable L/C 6 weeks before shipment"
            ),
        },
        # Batam Fast Ferry - Second invoice (non-milestone service)
        "3228005118": {
            "document_number": "3228005118",
            "customer_id": "0000100001",
            "customer_name": "Batam Fast Ferry Pte. Ltd.",
            "amount": 95000.00,
            "currency": "SGD",
            "document_date": (today - timedelta(days=65)).isoformat(),
            "due_date": (today - timedelta(days=5)).isoformat(),
            "status": "PENDING_COLLECTION",
            "billing_type": "F2",
            "sales_order": "1000025101",
            "sales_order_item": "000010",
            "payment_terms_text": "Net 60 days from invoice",
        },
        # CLLS Power - Second invoice (non-milestone service)
        "3228005119": {
            "document_number": "3228005119",
            "customer_id": "0021000090",
            "customer_name": "CLLS Power System LTD",
            "amount": 42000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=45)).isoformat(),
            "due_date": (today + timedelta(days=15)).isoformat(),
            "status": "PENDING_COLLECTION",
            "billing_type": "F2",
            "sales_order": "1000025301",
            "sales_order_item": "000010",
            "payment_terms_text": "100% by TT within 60 days after invoice",
        },
        # =====================================================================
        # Downpayment Requests (FAZ) - linked to sales orders
        # =====================================================================
        # Batam Fast Ferry - 20% DP (SGD 84,000) - PAID
        "9200000001": {
            "document_number": "9200000001",
            "customer_id": "0000100001",
            "customer_name": "Batam Fast Ferry Pte. Ltd.",
            "amount": 84000.00,
            "currency": "SGD",
            "document_date": (today - timedelta(days=180)).isoformat(),
            "due_date": (today - timedelta(days=150)).isoformat(),
            "status": "PAID",
            "billing_type": "FAZ",
            "sales_order": "1000022101",
            "sales_order_item": "000010",
            "clearing_date": (today - timedelta(days=148)).isoformat(),
            "clearing_doc": "1400000001",
            "payment_terms_text": "20% advance upon PO",
        },
        # ST Engineering - 20% DP (EUR 399,999.60) - PAID
        # Linked to order 1000024001 (Testing 5, Won, EUR 1,999,998)
        "9200000002": {
            "document_number": "9200000002",
            "customer_id": "0022005992",
            "customer_name": "ST Engineering Ltd",
            "amount": 399999.60,
            "currency": "EUR",
            "document_date": (today - timedelta(days=200)).isoformat(),
            "due_date": (today - timedelta(days=170)).isoformat(),
            "status": "PAID",
            "billing_type": "FAZ",
            "sales_order": "1000024001",
            "sales_order_item": "000010",
            "clearing_date": (today - timedelta(days=168)).isoformat(),
            "clearing_doc": "1400000002",
            "payment_terms_text": "20% down payment by TT upon PO",
        },
        # Maersk - 30% DP (EUR 165,000) - PAID
        "9200000003": {
            "document_number": "9200000003",
            "customer_id": "0000100002",
            "customer_name": "A.P. Moller - Maersk A/S",
            "amount": 165000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=150)).isoformat(),
            "due_date": (today - timedelta(days=120)).isoformat(),
            "status": "PAID",
            "billing_type": "FAZ",
            "sales_order": "1000024201",
            "sales_order_item": "000010",
            "clearing_date": (today - timedelta(days=118)).isoformat(),
            "clearing_doc": "1400000003",
            "payment_terms_text": "30% DP by TT within 30 days upon PO",
        },
        # ST Engineering - 20% DP (EUR 199,999.80) - PAID
        # Linked to order 1000023301 (Testing 3, Won, EUR 999,999)
        "9200000004": {
            "document_number": "9200000004",
            "customer_id": "0022005992",
            "customer_name": "ST Engineering Ltd",
            "amount": 199999.80,
            "currency": "EUR",
            "document_date": (today - timedelta(days=250)).isoformat(),
            "due_date": (today - timedelta(days=160)).isoformat(),
            "status": "PAID",
            "billing_type": "FAZ",
            "sales_order": "1000023301",
            "sales_order_item": "000010",
            "clearing_date": (today - timedelta(days=158)).isoformat(),
            "clearing_doc": "1400000004",
            "payment_terms_text": "20% downpayment via T/T",
        },
        # Tianjin Dingsheng - 20% DP (EUR 440,000) - OVERDUE (10 days past due!)
        "9200000005": {
            "document_number": "9200000005",
            "customer_id": "0000100006",
            "customer_name": "Tianjin Dingsheng Construction Co., Ltd.",
            "amount": 440000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=40)).isoformat(),
            "due_date": (today - timedelta(days=10)).isoformat(),
            "status": "OVERDUE",
            "billing_type": "FAZ",
            "sales_order": "1000100006",
            "sales_order_item": "000010",
            "clearing_date": None,
            "clearing_doc": None,
            "payment_terms_text": "20% down payment upon PO",
        },
        # ST Engineering - 15% DP (EUR 25,350) - PENDING_COLLECTION (sent, awaiting payment)
        # Linked to order Testing5208 (PO TEST-PO10, Service/Parts, EUR 169,000)
        "9200000006": {
            "document_number": "9200000006",
            "customer_id": "0022005992",
            "customer_name": "ST Engineering Ltd",
            "amount": 25350.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=25)).isoformat(),
            "due_date": (today + timedelta(days=5)).isoformat(),
            "status": "PENDING_COLLECTION",
            "billing_type": "FAZ",
            "sales_order": "Testing5208",
            "sales_order_item": "000010",
            "clearing_date": None,
            "clearing_doc": None,
            "payment_terms_text": "15% advance by TT within 30 days upon PO",
        },
        # CLLS Power - 5% DP (EUR 624.65) - PENDING_BILLING (DP request to create)
        # Linked to order Testing5124 (PO TEST-PO3, MG16V4000A3, EUR 12,493)
        "9200000007": {
            "document_number": "9200000007",
            "customer_id": "0021000090",
            "customer_name": "CLLS Power System LTD",
            "amount": 624.65,
            "currency": "EUR",
            "document_date": (today - timedelta(days=5)).isoformat(),
            "due_date": (today + timedelta(days=25)).isoformat(),
            "status": "PENDING_BILLING",
            "billing_type": "FAZ",
            "sales_order": "Testing5124",
            "sales_order_item": "000010",
            "clearing_date": None,
            "clearing_doc": None,
            "payment_terms_text": "5% down payment upon PO",
        },
        # CLLS Power - 20% DP (EUR 6,000) - OVERDUE (DP past due, not collected)
        # Linked to order Testing5268 (PO TEST-PO15, Service/Parts, EUR 30,000)
        "9200000008": {
            "document_number": "9200000008",
            "customer_id": "0021000090",
            "customer_name": "CLLS Power System LTD",
            "amount": 6000.00,
            "currency": "EUR",
            "document_date": (today - timedelta(days=45)).isoformat(),
            "due_date": (today - timedelta(days=15)).isoformat(),
            "status": "OVERDUE",
            "billing_type": "FAZ",
            "sales_order": "Testing5268",
            "sales_order_item": "000010",
            "clearing_date": None,
            "clearing_doc": None,
            "payment_terms_text": "20% down payment upon PO",
        },
    }


# Lazy initialization - computed when first accessed
SIMULATED_BILLING_DOCS: dict[str, dict] = {}


# =============================================================================
# Simulated Sales Orders with Billing Plans (FPLT/FPLTR)
# Links to existing customers, opportunities (won deals), and billing docs
# =============================================================================


def _get_simulated_sales_orders() -> dict[str, dict]:
    """
    Generate sales orders with billing plans and dynamic dates.

    Each order is linked to:
    - A customer from SIMULATED_CUSTOMERS
    - A won opportunity from SIMULATED_OPPORTUNITIES (via sap_order_id)
    - Billing documents from _get_dynamic_billing_docs() (via sales_order ref)

    Returns:
        Dictionary of sales orders keyed by order number
    """
    from datetime import date, timedelta

    today = date.today()

    return {
        # =================================================================
        # Linked Orders (3 orders linked to opportunities)
        # Source: User Excel, modified to match opportunity values
        # =================================================================
        "1000024001": {
            # Linked to real CPI opportunity 3000072515 (Testing 5, Won, EUR 1,999,998)
            "linked_opportunity": {
                "id": "3000072515",
                "title": "Testing 5",
                "status": "Won",
                "value": 1999998.0,
                "currency": "EUR",
            },
            # Linked IPAS order (matched by PO Number TEST-PO8)
            "ipas_order_number": "1207889",
            "header": {
                "VBELN": "1000024001",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO8",
                "BSTDK": "20250406",
                "AUDAT": "20250406",
                "WAERK": "EUR",
                "NETWR": 1999998.00,
                "ZTERM": "Z090",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250406",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "20V8000M71L",
                    "ARKTX": "MTU 20V8000 M71L Marine Propulsion Engine",
                    "KWMENG": 14.0,
                    "VRKME": "EA",
                    "NETWR": 1799998.00,
                    "WAERK": "EUR",
                    "WERKS": "1000",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=45)).strftime("%Y%m%d"),
                },
                {
                    "POSNR": "000020",
                    "MATNR": "ACC_V8000_DIRECT",
                    "ARKTX": "Accessories and Direct Ship Components",
                    "KWMENG": 3.0,
                    "VRKME": "EA",
                    "NETWR": 200000.00,
                    "WAERK": "EUR",
                    "WERKS": "1000",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=45)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "A",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                    {
                        "POSNR": "000020",
                        "DLV_STAT": "A",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "0000000102",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 1999998.00,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today - timedelta(days=200)).isoformat(),
                        "TETXT": "Down Payment by TT upon PO",
                        "FAKWR": 399999.60,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "9200000002",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=15)).isoformat(),
                        "TETXT": "Balance by LC before shipment",
                        "FAKWR": 1399998.60,
                        "BETEFP": 70.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "3228005113",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "PSI completion payment",
                        "FAKWR": 199999.80,
                        "BETEFP": 10.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        "1000023301": {
            # Linked to real CPI opportunity 3000072513 (Testing 3, Won, EUR 999,999)
            # SoF (Sales Order Form) release date — drives downpayment milestone due date
            "sof_date": "2025-05-29",  # ZSF document released 29.05.2025
            "linked_opportunity": {
                "id": "3000072513",
                "title": "Testing 3",
                "status": "Won",
                "value": 999999.0,
                "currency": "EUR",
            },
            # Linked IPAS order (matched by PO Number TEST-PO4)
            "ipas_order_number": "1207809",
            "header": {
                "VBELN": "1000023301",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO4",
                "BSTDK": "20250225",
                "AUDAT": "20250225",
                "WAERK": "EUR",
                "NETWR": 999999.00,
                "ZTERM": "Z090",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250225",
                "ERZET": "110000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "MG20V4000A5",
                    "ARKTX": "MTU 20V4000 A5 Power Generation Genset",
                    "KWMENG": 6.0,
                    "VRKME": "EA",
                    "NETWR": 999999.00,
                    "WAERK": "EUR",
                    "WERKS": "1000",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=15)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {
                    "PARVW": "AG",
                    "KUNNR": "0022005992",
                    "NAME1": "ST Engineering Ltd",
                },
                {
                    "PARVW": "WE",
                    "KUNNR": "0022005992",
                    "NAME1": "ST Engineering Ltd",
                },
                {
                    "PARVW": "RE",
                    "KUNNR": "0022005992",
                    "NAME1": "ST Engineering Ltd",
                },
                {
                    "PARVW": "RG",
                    "KUNNR": "0022005992",
                    "NAME1": "ST Engineering Ltd",
                },
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "A",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "0000000104",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 999999.00,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": "2025-05-29",  # SoF release date (ZSF doc date)
                        "TETXT": "Downpayment via T/T",
                        "FAKWR": 199999.80,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "9200000004",
                    },
                    {
                        "FPLTR": "0002",
                        # F2 milestone: FDATU derived from first delivery date (EDATU)
                        "FDATU": (today - timedelta(days=30)).isoformat(),
                        "TETXT": "LC prior shipment (gensets)",
                        "FAKWR": 599999.40,
                        "BETEFP": 60.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "3228005114",
                    },
                    {
                        "FPLTR": "0003",
                        # F2 milestone: FDATU = first delivery date (EDATU from items)
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Balance T/T 30 days from invoice",
                        "FAKWR": 199999.80,
                        "BETEFP": 20.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        "1000100006": {
            # Tianjin Dingsheng (0000100006) — linked to CPI opp 3000072511
            "linked_opportunity": {
                "id": "3000072511",
                "title": "Testing 1",
                "status": "Won",
                "value": 2200000.0,
                "currency": "EUR",
            },
            # Linked IPAS order (matched by PO Number PO-DINGSHENG-2025-001)
            "ipas_order_number": "1207095",
            "header": {
                "VBELN": "1000100006",
                "AUART": "ZEN2",
                "VKORG": "CN01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "PO-DINGSHENG-2025-001",
                "BSTDK": (today - timedelta(days=35)).strftime("%Y%m%d"),
                "AUDAT": (today - timedelta(days=35)).strftime("%Y%m%d"),
                "WAERK": "EUR",
                "NETWR": 2200000.00,
                "ZTERM": "Z030",
                "INCO1": "EXW",
                "INCO2": "Friedrichshafen",
                "KUNNR": "0000100006",
                "ERDAT": (today - timedelta(days=35)).strftime("%Y%m%d"),
                "ERZET": "080000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "20V4000M93L",
                    "ARKTX": "MTU 20V4000 M93L Catamaran Propulsion Engine",
                    "KWMENG": 4.0,
                    "VRKME": "EA",
                    "NETWR": 1900000.00,
                    "WAERK": "EUR",
                    "WERKS": "1000",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=90)).strftime("%Y%m%d"),
                },
                {
                    "POSNR": "000020",
                    "MATNR": "MCS5",
                    "ARKTX": "MCS5 Control System Package",
                    "KWMENG": 4.0,
                    "VRKME": "EA",
                    "NETWR": 300000.00,
                    "WAERK": "EUR",
                    "WERKS": "1000",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=90)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {
                    "PARVW": "AG",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "WE",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "RE",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "RG",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {"PARVW": "ZV", "KUNNR": "0021200189", "NAME1": "End Customer (China)"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "",
                        "BILL_STAT": "A",
                        "REJ_STAT": "",
                    },
                    {
                        "POSNR": "000020",
                        "DLV_STAT": "",
                        "BILL_STAT": "A",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "A",  # A = open
            },
            "billing_plan": {
                "FPLNR": "0000000105",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 2200000.00,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today - timedelta(days=5)).isoformat(),
                        "TETXT": "Down payment 20% upon PO",
                        "FAKWR": 440000.00,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "9200000005",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=25)).isoformat(),
                        "TETXT": "Balance 80% T/T before EXW",
                        "FAKWR": 1760000.00,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "",
                        "VBELN": "3228005115",
                    },
                ],
            },
        },
        # =================================================================
        # Standalone Orders (12 orders from Excel, no opp link)
        # Source: AGentic AI - Sales Header/Line/PaymentTerms Excel files
        # =================================================================
        # Testing5113 — TIANJIN DINGSHENG CONSTRUCTION — IPAS 1207695
        "Testing5113": {
            "header": {
                "VBELN": "Testing5113",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO2",
                "BSTDK": "20250108",
                "AUDAT": "20250108",
                "WAERK": "EUR",
                "NETWR": 135250.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0000100006",
                "ERDAT": "20250108",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "DG20V4000B5C",
                    "ARKTX": "DG20V4000B5C",
                    "KWMENG": 25.0,
                    "VRKME": "EA",
                    "NETWR": 135250.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {
                    "PARVW": "AG",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "WE",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "RE",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
                {
                    "PARVW": "RG",
                    "KUNNR": "0000100006",
                    "NAME1": "TIANJIN DINGSHENG CONSTRUCTION",
                },
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5113",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 135250.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 10%",
                        "FAKWR": 13525.0,
                        "BETEFP": 10.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 10%",
                        "FAKWR": 13525.0,
                        "BETEFP": 10.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "Balance payment 80%",
                        "FAKWR": 108200.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5124 — CLLS Power System LTD — IPAS 1207766
        "Testing5124": {
            "header": {
                "VBELN": "Testing5124",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO3",
                "BSTDK": "20250127",
                "AUDAT": "20250127",
                "WAERK": "EUR",
                "NETWR": 12493.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0021000090",
                "ERDAT": "20250127",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "MG16V4000A3",
                    "ARKTX": "MG16V4000A3",
                    "KWMENG": 4.0,
                    "VRKME": "EA",
                    "NETWR": 9994.4,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
                {
                    "POSNR": "000020",
                    "MATNR": "ACC_V4000",
                    "ARKTX": "ACC_V4000",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 2498.6000000000004,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=45)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {
                    "PARVW": "AG",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "WE",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "RE",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "RG",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5124",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 12493.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 5%",
                        "FAKWR": 624.65,
                        "BETEFP": 5.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "A",
                        "FAKSP": "",
                        "VBELN": "9200000007",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 15%",
                        "FAKWR": 1873.95,
                        "BETEFP": 15.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "Balance payment 80%",
                        "FAKWR": 9994.4,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5143 — ST Engineering Ltd — IPAS 2201044
        "Testing5143": {
            # SoF release date — drives downpayment milestone due date
            "sof_date": "2025-05-15",  # ZSF doc released
            "header": {
                "VBELN": "Testing5143",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO5",
                "BSTDK": "20250226",
                "AUDAT": "20250314",
                "WAERK": "EUR",
                "NETWR": 24847.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250226",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "20V4000G23F",
                    "ARKTX": "20V4000G23F",
                    "KWMENG": 7.0,
                    "VRKME": "EA",
                    "NETWR": 8282.33,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
                {
                    "POSNR": "000020",
                    "MATNR": "SERV_V4000",
                    "ARKTX": "SERV_V4000",
                    "KWMENG": 7.0,
                    "VRKME": "EA",
                    "NETWR": 8282.33,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=45)).strftime("%Y%m%d"),
                },
                {
                    "POSNR": "000030",
                    "MATNR": "20V4000G63LF",
                    "ARKTX": "20V4000G63LF",
                    "KWMENG": 7.0,
                    "VRKME": "EA",
                    "NETWR": 8282.339999999998,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=60)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5143",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 24847.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": "2025-05-15",  # SoF release date (ZSF doc date)
                        "TETXT": "Down payment 20%",
                        "FAKWR": 4969.4,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        # F2 milestone: FDATU = first delivery date (EDATU from items)
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 19877.6,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5147 — ST Engineering Ltd — IPAS 1207814
        "Testing5147": {
            # SoF release date — drives downpayment milestone due date (ZSF doc 3228005147)
            "sof_date": "2025-05-29",  # ZSF doc released 29.05.2025
            "header": {
                "VBELN": "Testing5147",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO6",
                "BSTDK": "20250301",
                "AUDAT": "20250301",
                "WAERK": "EUR",
                "NETWR": 62630.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250301",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "16V4000P83",
                    "ARKTX": "16V4000P83",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 62630.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5147",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 62630.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": "2025-05-29",  # SoF release date (ZSF doc 3228005147)
                        "TETXT": "Down payment 20%",
                        "FAKWR": 12526.0,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        # F2 milestone: FDATU = first delivery date (EDATU from items)
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 50104.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5168 — ST Engineering Ltd — IPAS 1207869
        "Testing5168": {
            "header": {
                "VBELN": "Testing5168",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO7",
                "BSTDK": "20250402",
                "AUDAT": "20250402",
                "WAERK": "EUR",
                "NETWR": 24900.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250402",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "16V2000M72",
                    "ARKTX": "16V2000M72",
                    "KWMENG": 6.0,
                    "VRKME": "EA",
                    "NETWR": 24900.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5168",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 24900.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 10%",
                        "FAKWR": 2490.0,
                        "BETEFP": 10.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 10%",
                        "FAKWR": 2490.0,
                        "BETEFP": 10.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "Balance payment 80%",
                        "FAKWR": 19920.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5185 — ST Engineering Ltd — IPAS 1207914
        "Testing5185": {
            "header": {
                "VBELN": "Testing5185",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO9",
                "BSTDK": "20250519",
                "AUDAT": "20250519",
                "WAERK": "EUR",
                "NETWR": 22000.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250519",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 22000.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5185",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 22000.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 20%",
                        "FAKWR": 4400.0,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 17600.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5208 — ST Engineering Ltd — IPAS 0000000
        "Testing5208": {
            "header": {
                "VBELN": "Testing5208",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO10",
                "BSTDK": "20250822",
                "AUDAT": "20250822",
                "WAERK": "EUR",
                "NETWR": 169000.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250822",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 169000.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5208",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 169000.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 15%",
                        "FAKWR": 25350.0,
                        "BETEFP": 15.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "9200000006",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 50%",
                        "FAKWR": 84500.0,
                        "BETEFP": 50.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "Balance payment 25%",
                        "FAKWR": 42250.0,
                        "BETEFP": 25.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0004",
                        "FDATU": (today + timedelta(days=150)).isoformat(),
                        "TETXT": "Milestone 4 5%",
                        "FAKWR": 8450.0,
                        "BETEFP": 5.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0005",
                        "FDATU": (today + timedelta(days=210)).isoformat(),
                        "TETXT": "Final payment 5%",
                        "FAKWR": 8450.0,
                        "BETEFP": 5.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5221 — ST Engineering Ltd — IPAS 1208002
        "Testing5221": {
            "header": {
                "VBELN": "Testing5221",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO11",
                "BSTDK": "20250925",
                "AUDAT": "20250925",
                "WAERK": "EUR",
                "NETWR": 158089.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20250925",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 158089.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5221",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 158089.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 20%",
                        "FAKWR": 31617.8,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 126471.2,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5227 — ST Engineering Ltd — IPAS 1208002
        "Testing5227": {
            "header": {
                "VBELN": "Testing5227",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO12",
                "BSTDK": "20251006",
                "AUDAT": "20251006",
                "WAERK": "EUR",
                "NETWR": 288063.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20251006",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 288063.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5227",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 288063.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 30%",
                        "FAKWR": 86418.9,
                        "BETEFP": 30.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 70%",
                        "FAKWR": 201644.1,
                        "BETEFP": 70.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5230 — ST Engineering Ltd — IPAS 0000000
        "Testing5230": {
            "header": {
                "VBELN": "Testing5230",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO13",
                "BSTDK": "20251010",
                "AUDAT": "20251010",
                "WAERK": "EUR",
                "NETWR": 31750.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20251010",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 31750.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5230",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 31750.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 15%",
                        "FAKWR": 4762.5,
                        "BETEFP": 15.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 25400.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0003",
                        "FDATU": (today + timedelta(days=90)).isoformat(),
                        "TETXT": "Balance payment 5%",
                        "FAKWR": 1587.5,
                        "BETEFP": 5.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5242 — ST Engineering Ltd — IPAS 1208097
        "Testing5242": {
            "header": {
                "VBELN": "Testing5242",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO14",
                "BSTDK": "20251110",
                "AUDAT": "20251110",
                "WAERK": "EUR",
                "NETWR": 27200.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0022005992",
                "ERDAT": "20251110",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 27200.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {"PARVW": "AG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "WE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RE", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
                {"PARVW": "RG", "KUNNR": "0022005992", "NAME1": "ST Engineering Ltd"},
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5242",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 27200.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 20%",
                        "FAKWR": 5440.0,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 21760.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
        # Testing5268 — CLLS Power System LTD — IPAS 1208158
        "Testing5268": {
            "header": {
                "VBELN": "Testing5268",
                "AUART": "ZEN2",
                "VKORG": "SG01",
                "VTWEG": "10",
                "SPART": "00",
                "BSTNK": "TEST-PO15",
                "BSTDK": "20251218",
                "AUDAT": "20251218",
                "WAERK": "EUR",
                "NETWR": 30000.0,
                "ZTERM": "Z030",
                "INCO1": "FCA",
                "INCO2": "Singapore",
                "KUNNR": "0021000090",
                "ERDAT": "20251218",
                "ERZET": "090000",
            },
            "items": [
                {
                    "POSNR": "000010",
                    "MATNR": "SERVICE",
                    "ARKTX": "Service / Parts",
                    "KWMENG": 1.0,
                    "VRKME": "EA",
                    "NETWR": 30000.0,
                    "WAERK": "EUR",
                    "WERKS": "0011",
                    "PSTYV": "TAN",
                    "EDATU": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
            ],
            "partners": [
                {
                    "PARVW": "AG",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "WE",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "RE",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
                {
                    "PARVW": "RG",
                    "KUNNR": "0021000090",
                    "NAME1": "CLLS Power System LTD",
                },
            ],
            "status": {
                "items": [
                    {
                        "POSNR": "000010",
                        "DLV_STAT": "B",
                        "BILL_STAT": "B",
                        "REJ_STAT": "",
                    },
                ],
                "overall_status": "C",
            },
            "billing_plan": {
                "FPLNR": "BP-Testing5268",
                "FPART": "02",
                "WAESSION": "EUR",
                "FAKWR": 30000.0,
                "dates": [
                    {
                        "FPLTR": "0001",
                        "FDATU": (today + timedelta(days=-30)).isoformat(),
                        "TETXT": "Down payment 20%",
                        "FAKWR": 6000.0,
                        "BETEFP": 20.0,
                        "FPFAR": "FAZ",
                        "FKSAF": "B",
                        "FAKSP": "",
                        "VBELN": "9200000008",
                    },
                    {
                        "FPLTR": "0002",
                        "FDATU": (today + timedelta(days=30)).isoformat(),
                        "TETXT": "Progress payment 80%",
                        "FAKWR": 24000.0,
                        "BETEFP": 80.0,
                        "FPFAR": "F2",
                        "FKSAF": "A",
                        "FAKSP": "01",
                        "VBELN": "",
                    },
                ],
            },
        },
    }


# =============================================================================
# CPI Simulator - Compatible with CPIClient Interface
# =============================================================================


class CPISimulator:
    """
    SAP CPI Simulator implementing the same interface as CPIClient.

    Can be used as a drop-in replacement for CPIClient when SAP systems
    are not available. Inject into MS5Client, CECClient, or IPASClient.

    Usage:
        # Direct usage
        simulator = CPISimulator()
        await simulator.connect()
        result = await simulator.call_iflow("CustomerGetDetail", {...})

        # With MS5Client (drop-in replacement)
        simulator = CPISimulator()
        ms5 = MS5Client(cpi_client=simulator)
        await ms5.connect()
        customer = await ms5.get_customer("0000100001")
    """

    def __init__(self):
        """Initialize CPI simulator.

        In production, the simulator is only blocked when real SAP CPI credentials
        are configured (to prevent accidental use of simulated data when the real
        backend is available). When no real credentials exist, the simulator runs
        as a fallback so KYP reports still include SAP data.
        """
        if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
            has_real_cpi = bool(
                os.getenv("SAP_CPI_CLIENT_ID", "").strip()
                and os.getenv("SAP_CPI_CLIENT_SECRET", "").strip()
            )
            if has_real_cpi:
                raise RuntimeError(
                    "CPISimulator MUST NOT be instantiated in production when "
                    "real SAP CPI credentials are configured. Use CPIClient instead."
                )
            logger.warning(
                "CPISimulator running in production (no SAP CPI credentials configured). "
                "Data is simulated — configure SAP_CPI_CLIENT_ID and SAP_CPI_CLIENT_SECRET "
                "for real SAP connectivity."
            )
        self._connected = False
        self._client = None  # Compatibility with CPIClient._client checks

    async def connect(self) -> None:
        """Simulate connection to SAP CPI."""
        self._connected = True
        self._client = True  # For compatibility checks like `if cpi._client`
        logger.info("CPI Simulator connected (simulation mode)")

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        self._client = None
        logger.info("CPI Simulator disconnected")

    async def health_check(self) -> dict[str, Any]:
        """Return health status."""
        return {
            "status": "healthy",
            "mode": "simulation",
            "connected": self._connected,
            "customers_available": len(SIMULATED_CUSTOMERS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def send_request(
        self,
        iflow_name: str,
        payload: dict[str, Any],
        method: str = "POST",
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """
        Alias for call_iflow for compatibility with FinOpsDataService.

        This method provides the same interface as call_iflow.
        """
        return await self.call_iflow(iflow_name, payload, method, content_type)

    async def call_iflow(
        self,
        iflow_name: str,
        payload: dict[str, Any],
        method: str = "POST",
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """
        Simulate SAP CPI iFlow call.

        This method implements the same signature as CPIClient.call_iflow()
        so it can be used as a drop-in replacement.

        Args:
            iflow_name: Name of the CPI iFlow (matches existing client usage)
            payload: Request payload with BAPI parameters
            method: HTTP method (ignored in simulation)
            content_type: Content type (ignored in simulation)

        Returns:
            Mock response matching SAP BAPI structure
        """
        logger.debug(f"CPI Simulator: {iflow_name} called with {payload}")

        # Route to handlers matching existing client iFlow names
        handlers = {
            # MS5 iFlows (from ms5_client.py)
            "CustomerGetList": self._handle_customer_getlist,  # KYP search
            "CustomerGetDetail": self._handle_customer_getdetail,
            "CreditGetAccount": self._handle_credit_getdetail,
            "CustomerGetPartners": self._handle_get_partners,
            "OrderSimulate": self._handle_order_simulate,
            "OrderCreate": self._handle_order_create,
            "TransactionCommit": self._handle_transaction_commit,
            # CEC iFlows (from cec_client.py)
            "CECGetCommercialTerms": self._handle_get_commercial_terms,
            "CECGetOpportunity": self._handle_get_opportunity,
            "CECSearchOpportunities": self._handle_search_opportunities,
            "CECGetOpportunitiesByAccount": self._handle_get_opportunities_by_account,
            # IPAS iFlows (from ipas_client.py)
            "IPASGetConfiguration": self._handle_ipas_get_configuration,
            "IPASGetByOpportunity": self._handle_ipas_get_by_opportunity,
            "IPASGetProductCatalog": self._handle_ipas_get_product_catalog,
            "IPASValidateConfiguration": self._handle_ipas_validate_configuration,
            "IPASGetBOM": self._handle_ipas_get_bom,
            # FinanceOps iFlows (for Billing/Collections Dashboard)
            "MS5GetBillingDocuments": self._handle_get_billing_documents,
            "MS5GetOpenItems": self._handle_get_open_items,
            # Post-Order Payment/Billing Plan iFlows (Section 7 of BAPI doc)
            "MS5GetOrderDetail": self._handle_get_order_detail,
            "MS5GetOrderStatus": self._handle_get_order_status,
            "MS5GetBillingPlan": self._handle_get_billing_plan,
            "MS5GetBillingDocDetail": self._handle_get_billing_doc_detail,
            "MS5GetOpenARItems": self._handle_get_open_ar_items,
            # RFC_READ_TEXT (payment terms text for billing documents)
            "MS5ReadText": self._handle_read_text,
        }

        handler = handlers.get(iflow_name)
        if handler:
            return await handler(payload)

        logger.warning(f"Unknown iFlow: {iflow_name}")
        return {
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.ERROR,
                    "ID": "SY",
                    "NUMBER": "002",
                    "MESSAGE": f"Unknown iFlow: {iflow_name}",
                }
            ]
        }

    # =========================================================================
    # BAPI_CUSTOMER_GETLIST Handler (KYP Search)
    # =========================================================================

    async def _handle_customer_getlist(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle BAPI_CUSTOMER_GETLIST simulation for KYP customer search.

        Returns structure matching MS5Client.search_customers() expectations:
        - ADDRESSDATA array with matching customers
        - RETURN messages
        """
        max_rows = payload.get("MAXROWS", 50)
        name_range = payload.get("NAMERANGE", [])
        country_range = payload.get("COUNTRYRANGE", [])

        # Extract search pattern
        search_pattern = ""
        if name_range and len(name_range) > 0:
            search_pattern = name_range[0].get("LOW", "").upper()
            # Remove wildcards for matching
            search_pattern = search_pattern.replace("*", "")

        # Extract country filter
        country_filter = ""
        if country_range and len(country_range) > 0:
            country_filter = country_range[0].get("LOW", "").upper()

        # Check if search pattern matches a known alias first
        alias_customer_id = None
        search_lower = search_pattern.lower()
        if search_lower in CUSTOMER_NAME_LOOKUP:
            alias_customer_id = CUSTOMER_NAME_LOOKUP[search_lower]
        else:
            # Try partial alias match
            for alias, cid in CUSTOMER_NAME_LOOKUP.items():
                if alias in search_lower or search_lower in alias:
                    alias_customer_id = cid
                    break

        # Search customers
        results = []
        for customer_no, customer in SIMULATED_CUSTOMERS.items():
            # Name match: check alias first, then partial match on name1/name2
            name_match = (
                not search_pattern
                or (alias_customer_id and customer.kunnr == alias_customer_id)
                or search_pattern in customer.name1.upper()
                or search_pattern in customer.name2.upper()
            )

            # Country match
            country_match = (
                not country_filter or customer.country.upper() == country_filter
            )

            if name_match and country_match:
                results.append(
                    {
                        "CUSTOMER": customer.kunnr,
                        "NAME": customer.name1,
                        "STCD1": customer.stcd1,  # UEN / Tax ID
                        "STCD2": customer.stcd2,
                        "COUNTRY": customer.country,
                        "CITY": customer.city,
                    }
                )

                if len(results) >= max_rows:
                    break

        return {
            "ADDRESSDATA": results,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Found {len(results)} customers",
                }
            ],
        }

    # =========================================================================
    # BAPI_CUSTOMER_GETDETAIL2 Handler
    # =========================================================================

    async def _handle_customer_getdetail(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle BAPI_CUSTOMER_GETDETAIL2 simulation.

        Returns structure matching MS5Client.get_customer() expectations:
        - CUSTOMERADDRESS with NAME1, CITY1, POST_CODE1, STREET, COUNTRY, STCD1, STCD2
        - CUSTOMERGENERALDETAIL
        - RETURN messages
        """
        customer_no = payload.get("CUSTOMERNO", "").zfill(10)

        if customer_no not in SIMULATED_CUSTOMERS:
            return {
                "CUSTOMERADDRESS": {},
                "CUSTOMERGENERALDETAIL": {},
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "ID": "BAPI",
                        "NUMBER": "101",
                        "MESSAGE": f"Customer {customer_no} not found",
                        "MESSAGE_V1": customer_no,
                    }
                ],
            }

        customer = SIMULATED_CUSTOMERS[customer_no]

        # Build BAPICUSTOMER_04 structure (matching MS5Client field expectations)
        customer_address = {
            "NAME1": customer.name1,
            "NAME2": customer.name2,
            "STREET": customer.street,
            "CITY1": customer.city,  # MS5Client expects CITY1
            "POST_CODE1": customer.postl_code,  # MS5Client expects POST_CODE1
            "REGION": customer.region,
            "COUNTRY": customer.country,
            "COUNTRYISO": customer.countryiso,
            "TEL1_NUMBR": customer.telephone,
            "FAX_NUMBER": customer.fax,
            "E_MAIL": customer.email,
            "STCD1": customer.stcd1,  # UEN / Tax ID 1
            "STCD2": customer.stcd2,  # Tax ID 2
        }

        customer_general = {
            "CUSTOMER": customer.kunnr,
            "COMP_CODE": customer.bukrs,
        }

        return {
            "CUSTOMERADDRESS": customer_address,
            "CUSTOMERGENERALDETAIL": customer_general,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": "Customer data retrieved successfully",
                }
            ],
        }

    # =========================================================================
    # BAPI_CR_ACC_GETDETAIL Handler
    # =========================================================================

    async def _handle_credit_getdetail(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle BAPI_CR_ACC_GETDETAIL simulation.

        Returns structure matching MS5Client.check_credit_limit() expectations:
        - CREDIT_LIMIT, CREDIT_EXPOSURE fields
        - RETURN messages
        """
        customer_no = payload.get("CUSTOMER", "").zfill(10)

        if customer_no not in SIMULATED_CUSTOMERS:
            return {
                "CREDIT_LIMIT": 0,
                "CREDIT_EXPOSURE": 0,
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "MESSAGE": f"Customer {customer_no} not found",
                    }
                ],
            }

        customer = SIMULATED_CUSTOMERS[customer_no]
        total_exposure = customer.skfor + customer.sauft
        credit_blocked = customer.crblb == "X"

        return {
            "CREDIT_LIMIT": customer.klimk,
            "CREDIT_EXPOSURE": total_exposure,
            "CURRENCY": customer.waerk,  # Currency from customer master
            "RETURN": [
                {
                    "TYPE": (
                        SAPMessageTypes.WARNING
                        if credit_blocked
                        else SAPMessageTypes.SUCCESS
                    ),
                    "MESSAGE": (
                        "Credit blocked" if credit_blocked else "Credit data retrieved"
                    ),
                }
            ],
        }

    # =========================================================================
    # Partner Functions Handler
    # =========================================================================

    async def _handle_get_partners(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle customer partner functions retrieval.

        Returns PARTNER_FUNCTIONS key as expected by MS5Client.get_partner_functions().
        """
        customer_no = payload.get("CUSTOMERNO", "").zfill(10)

        if customer_no not in SIMULATED_CUSTOMERS:
            return {
                "PARTNER_FUNCTIONS": [],
                "RETURN": [
                    {"TYPE": SAPMessageTypes.ERROR, "MESSAGE": "Customer not found"}
                ],
            }

        customer = SIMULATED_CUSTOMERS[customer_no]

        # Return in format expected by MS5Client.get_partner_functions()
        # MS5Client looks for result.get("PARTNER_FUNCTIONS", [])
        return {
            "PARTNER_FUNCTIONS": [
                {
                    "function": pf["PARTN_ROLE"],
                    "partner_number": pf["PARTN_NUMB"],
                    "name": pf["NAME"],
                }
                for pf in customer.partner_functions
            ],
            "RETURN": [
                {"TYPE": SAPMessageTypes.SUCCESS, "MESSAGE": "Partners retrieved"}
            ],
        }

    # =========================================================================
    # CEC Commercial Terms Handler
    # =========================================================================

    async def _handle_get_commercial_terms(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle CECGetCommercialTerms simulation."""
        account_id = payload.get("account_id", "")
        customer_no = self._resolve_customer_id(account_id)

        if not customer_no or customer_no not in SIMULATED_CUSTOMERS:
            return {"payment_terms": "", "incoterms": "", "currency": "EUR"}

        customer = SIMULATED_CUSTOMERS[customer_no]
        return {
            "payment_terms": customer.zterm,
            "incoterms": customer.inco1,
            "incoterms_location": customer.inco2,
            "currency": customer.waerk,
        }

    # =========================================================================
    # Order Simulation Handler
    # =========================================================================

    async def _handle_order_simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle BAPI_SALESORDER_SIMULATE simulation."""
        items = payload.get("ORDER_ITEMS_IN", [])
        total_net_value = 0.0
        items_out = []

        for i, item in enumerate(items):
            qty = float(item.get("REQ_QTY", 1))
            # Validate quantity: must be positive and finite
            if qty <= 0:
                return {
                    "ORDER_ITEMS_OUT": [],
                    "RETURN": [
                        {
                            "TYPE": SAPMessageTypes.ERROR,
                            "MESSAGE": f"Item {i + 1}: quantity must be positive (got {qty})",
                        }
                    ],
                }
            if not (0 < qty <= 1e9):
                return {
                    "ORDER_ITEMS_OUT": [],
                    "RETURN": [
                        {
                            "TYPE": SAPMessageTypes.ERROR,
                            "MESSAGE": f"Item {i + 1}: quantity out of range (max 1,000,000,000)",
                        }
                    ],
                }
            unit_price = 10000.0
            net_value = qty * unit_price
            total_net_value += net_value

            items_out.append(
                {
                    "ITM_NUMBER": item.get("ITM_NUMBER", str((i + 1) * 10).zfill(6)),
                    "MATERIAL": item.get("MATERIAL", ""),
                    "REQ_QTY": qty,
                    "NET_VALUE": net_value,
                    "CURRENCY": "EUR",
                }
            )

        return {
            "ORDER_ITEMS_OUT": items_out,
            "RETURN": [
                {"TYPE": SAPMessageTypes.SUCCESS, "MESSAGE": "Simulation successful"}
            ],
        }

    # =========================================================================
    # Order Creation Handler
    # =========================================================================

    async def _handle_order_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle BAPI_SALESORDER_CREATEFROMDAT2 simulation."""
        test_run = payload.get("TESTRUN", "") == "X"
        doc_number = "" if test_run else f"100{datetime.now().strftime('%H%M%S%f')[:7]}"

        return {
            "SALESDOCUMENT": doc_number,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Order {'simulated' if test_run else 'created'}: {doc_number}",
                }
            ],
        }

    async def _handle_transaction_commit(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle BAPI_TRANSACTION_COMMIT simulation."""
        return {"RETURN": {"TYPE": SAPMessageTypes.SUCCESS, "MESSAGE": "Committed"}}

    # =========================================================================
    # CEC Opportunity Handlers
    # =========================================================================

    async def _handle_get_opportunity(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle CECGetOpportunity simulation.

        Returns opportunity with all fields including milestone payment fields (ADR-006).
        """
        opp_id = payload.get("opportunity_id", "OPP-001")

        # Look for the opportunity in SIMULATED_OPPORTUNITIES
        for account_opps in SIMULATED_OPPORTUNITIES.values():
            for opp in account_opps:
                if opp.get("id") == opp_id:
                    return opp

        # Default fallback opportunity if not found
        return {
            "id": opp_id,
            "account_id": "0000100001",
            "account_name": "Batam Fast Ferry Pte. Ltd.",
            "title": "MTU 16V4000 Marine Propulsion System",
            "status": "Open",
            "expected_revenue": 250000.00,
            "currency": "SGD",
            "close_date": "2026-06-15",
            "start_date": "2026-01-01",
            "win_probability": 65,
            "sales_type": "OE_SALES",
            "sap_order_id": None,
            "ipas_quote_id": "IPAS-2026-0999",
            "products": [{"product_id": "MTU-16V4000", "quantity": 2}],
        }

    async def _handle_search_opportunities(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle CECSearchOpportunities simulation.

        Returns matching opportunities with all fields including milestone payment fields.
        """
        query = payload.get("query", "").lower()
        status_filter = payload.get("status")
        limit = payload.get("limit", 50)

        results = []
        for account_opps in SIMULATED_OPPORTUNITIES.values():
            for opp in account_opps:
                # Filter by status if specified
                if status_filter and opp.get("status") != status_filter:
                    continue
                # Search in account_name and title
                account_name = opp.get("account_name", "").lower()
                title = opp.get("title", "").lower()
                if query and query not in account_name and query not in title:
                    continue
                results.append(opp)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        return {"items": results}

    async def _handle_get_opportunities_by_account(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle CECGetOpportunitiesByAccount simulation.

        Returns opportunity data from SIMULATED_OPPORTUNITIES for the given account.
        Each opportunity includes: id, name, value, status (Won/Lost/Open),
        close_date, and currency.
        """
        account_id = payload.get("account_id", "")
        # Normalize to 10-digit padded format
        if account_id.isdigit():
            account_id = account_id.zfill(10)

        opportunities = SIMULATED_OPPORTUNITIES.get(account_id, [])
        return {"items": opportunities}

    # =========================================================================
    # IPAS Handlers
    # =========================================================================

    async def _handle_ipas_get_configuration(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle IPASGetConfiguration simulation.

        Returns simulated product configuration based on SSZ sample.XML structure.
        """
        config_id = payload.get("config_id", "CFG-001")

        # Simulated configuration based on SSZ sample.XML
        return {
            "id": config_id,
            "config_id": config_id,
            "product_id": "12V2000G65SZ",
            "product_name": "MTU 12V2000G65SZ (765kW)",
            "variant": "300",
            "bom_items": [
                {
                    "material": "XS522010.00005",
                    "quantity": 1,
                    "item_number": "0001",
                    "unit": "EA",
                },
                {
                    "material": "XS524000.00019/S",
                    "quantity": 1,
                    "item_number": "0002",
                    "unit": "EA",
                },
            ],
            "characteristics": {
                "ENGINE_TYPE": "12V2000G65SZ",
                "POWER": "765",
                "CYLINDER": "16",
                "SERIES": "300",
                "CURRENCY": "CNY",
            },
            "pricing_relevant": True,
            "simulated": True,
        }

    async def _handle_ipas_get_by_opportunity(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle IPASGetByOpportunity simulation."""
        opportunity_id = payload.get("opportunity_id", "")

        # Return simulated configurations for the opportunity
        return {
            "items": [
                {
                    "id": f"CFG-{opportunity_id}-001",
                    "config_id": f"CFG-{opportunity_id}-001",
                    "product_id": "16V4000M65L",
                    "product_name": "MTU 16V4000 M65L Marine Propulsion",
                    "variant": "M65L",
                    "bom_items": [
                        {"material": "MTU-16V4000-CORE", "quantity": 1, "unit": "EA"},
                        {"material": "MTU-GEARBOX-ZF", "quantity": 1, "unit": "EA"},
                    ],
                    "characteristics": {
                        "ENGINE_TYPE": "16V4000M65L",
                        "POWER": "2000",
                    },
                    "pricing_relevant": True,
                    "simulated": True,
                }
            ]
        }

    async def _handle_ipas_get_product_catalog(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle IPASGetProductCatalog simulation."""
        return {
            "items": [
                {
                    "id": "12V2000",
                    "product_id": "12V2000",
                    "name": "MTU Series 2000 V12",
                    "description": "High-speed diesel engine for marine propulsion",
                    "category": "Marine",
                    "configurable": True,
                    "base_price": 150000.00,
                    "currency": "EUR",
                },
                {
                    "id": "16V4000",
                    "product_id": "16V4000",
                    "name": "MTU Series 4000 V16",
                    "description": "High-performance marine propulsion system",
                    "category": "Marine",
                    "configurable": True,
                    "base_price": 350000.00,
                    "currency": "EUR",
                },
                {
                    "id": "20V8000",
                    "product_id": "20V8000",
                    "name": "MTU Series 8000 V20",
                    "description": "Large vessel propulsion system",
                    "category": "Marine",
                    "configurable": True,
                    "base_price": 750000.00,
                    "currency": "EUR",
                },
            ]
        }

    async def _handle_ipas_validate_configuration(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle IPASValidateConfiguration simulation."""
        config_id = payload.get("config_id", "")
        characteristics = payload.get("characteristics", {})

        # Simple validation simulation
        is_valid = bool(config_id and characteristics)

        return {
            "is_valid": is_valid,
            "messages": ["Configuration validated successfully"] if is_valid else [],
            "errors": [] if is_valid else ["Missing required characteristics"],
            "warnings": [],
            "simulated": True,
        }

    async def _handle_ipas_get_bom(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle IPASGetBOM simulation."""
        product_id = payload.get("product_id", "")

        # Return simulated BOM items
        return {
            "bom_items": [
                {"material": f"{product_id}-CORE", "quantity": 1, "unit": "EA"},
                {"material": f"{product_id}-COOLING", "quantity": 1, "unit": "EA"},
                {"material": f"{product_id}-CONTROL", "quantity": 1, "unit": "EA"},
            ],
            "simulated": True,
        }

    # =========================================================================
    # FinanceOps Billing/Collections Handlers
    # =========================================================================

    async def _handle_get_billing_documents(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle MS5GetBillingDocuments simulation for FinanceOps Dashboard.

        Returns billing documents with payment terms text for harmonization.
        Supports optional filtering by customer_id and status.

        Args:
            payload: May contain customer_id and/or status filters

        Returns:
            Dict with 'success', 'documents' array, and 'RETURN' messages
        """
        customer_id = payload.get("customer_id", "")
        status_filter = payload.get("status", "")

        documents = []
        billing_docs = _get_dynamic_billing_docs()
        for doc_number, doc in billing_docs.items():
            # Apply customer filter if specified
            # Normalize both sides by stripping leading zeros to handle
            # padding mismatch (ms5_client strips zeros, docs have 10-digit IDs)
            if customer_id and doc["customer_id"].lstrip("0") != customer_id.lstrip(
                "0"
            ):
                continue

            # Apply status filter if specified
            if status_filter and doc["status"] != status_filter:
                continue

            documents.append(doc)

        return {
            "success": True,
            "documents": documents,
            "total_count": len(documents),
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Retrieved {len(documents)} billing documents",
                }
            ],
        }

    async def _handle_get_open_items(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle MS5GetOpenItems simulation for AR aging analysis.

        Returns open (unpaid) items for collections tracking.
        Filters out PAID status documents.

        Args:
            payload: May contain customer_id filter

        Returns:
            Dict with 'success', 'items' array for open AR items
        """
        customer_id = payload.get("customer_id", "")

        open_items = []
        billing_docs = _get_dynamic_billing_docs()
        for doc_number, doc in billing_docs.items():
            # Skip paid items
            if doc["status"] == "PAID":
                continue

            # Apply customer filter if specified
            # Normalize both sides by stripping leading zeros to handle
            # padding mismatch (ms5_client strips zeros, docs have 10-digit IDs)
            if customer_id and doc["customer_id"].lstrip("0") != customer_id.lstrip(
                "0"
            ):
                continue

            # Only include collection-relevant statuses
            if doc["status"] in (
                "PENDING_COLLECTION",
                "PARTIALLY_PAID",
                "OVERDUE",
            ):
                open_items.append(doc)

        return {
            "success": True,
            "items": open_items,
            "total_count": len(open_items),
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Retrieved {len(open_items)} open items",
                }
            ],
        }

    # =========================================================================
    # Post-Order: Sales Order Detail, Status, Billing Plan Handlers
    # =========================================================================

    async def _handle_get_order_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle BAPI_SALESORDER_GETDETAIL simulation.

        Returns full sales order including header, items, partners,
        billing plan, and conditions.

        Args:
            payload: Must contain SALESDOCUMENT (order number)

        Returns:
            Dict with ORDER_HEADER, ORDER_ITEMS, ORDER_PARTNERS,
            BILLING_PLAN, STATUS, and RETURN
        """
        order_number = payload.get("SALESDOCUMENT", "")
        orders = _get_simulated_sales_orders()

        if order_number not in orders:
            return {
                "ORDER_HEADER": {},
                "ORDER_ITEMS": [],
                "ORDER_PARTNERS": [],
                "BILLING_PLAN": {},
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "MESSAGE": f"Sales order {order_number} not found",
                    }
                ],
            }

        order = orders[order_number]
        return {
            "ORDER_HEADER": order["header"],
            "ORDER_ITEMS": order["items"],
            "ORDER_PARTNERS": order["partners"],
            "BILLING_PLAN": order.get("billing_plan", {}),
            "STATUS": order.get("status", {}),
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Order {order_number} retrieved successfully",
                }
            ],
        }

    async def _handle_get_order_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle BAPI_SALESORDER_GETSTATUS simulation.

        Returns per-item delivery and billing status.

        Args:
            payload: Must contain SALESDOCUMENT (order number)

        Returns:
            Dict with STATUSINFO table and RETURN
        """
        order_number = payload.get("SALESDOCUMENT", "")
        orders = _get_simulated_sales_orders()

        if order_number not in orders:
            return {
                "STATUSINFO": [],
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "MESSAGE": f"Sales order {order_number} not found",
                    }
                ],
            }

        order = orders[order_number]
        status_data = order.get("status", {})
        status_items = status_data.get("items", [])

        # Enrich with order-level info
        for item in status_items:
            item["DOC_NUMBER"] = order_number

        return {
            "STATUSINFO": status_items,
            "OVERALL_STATUS": status_data.get("overall_status", ""),
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Status for order {order_number} retrieved",
                }
            ],
        }

    async def _handle_get_billing_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle BILLING_SCHEDULE_READ simulation.

        Returns billing plan header (FPLT) and date lines (FPLTR)
        for a given sales order.

        Args:
            payload: Must contain SALESDOCUMENT (order number)
                     Optional: FPLNR (billing plan number)

        Returns:
            Dict with BILLING_PLAN_HEADER, BILLING_PLAN_DATES, and RETURN
        """
        order_number = payload.get("SALESDOCUMENT", "")
        orders = _get_simulated_sales_orders()

        if order_number not in orders:
            return {
                "BILLING_PLAN_HEADER": {},
                "BILLING_PLAN_DATES": [],
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "MESSAGE": f"No billing plan found for order {order_number}",
                    }
                ],
            }

        order = orders[order_number]
        bp = order.get("billing_plan", {})

        if not bp:
            return {
                "BILLING_PLAN_HEADER": {},
                "BILLING_PLAN_DATES": [],
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.WARNING,
                        "MESSAGE": f"Order {order_number} has no billing plan",
                    }
                ],
            }

        # Separate header from date lines
        header = {
            "FPLNR": bp.get("FPLNR", ""),
            "FPART": bp.get("FPART", ""),
            "WAESSION": bp.get("WAESSION", ""),
            "FAKWR": bp.get("FAKWR", 0.0),
            "SALESDOCUMENT": order_number,
        }

        dates = bp.get("dates", [])

        return {
            "BILLING_PLAN_HEADER": header,
            "BILLING_PLAN_DATES": dates,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": (
                        f"Billing plan {header['FPLNR']} retrieved "
                        f"with {len(dates)} milestones"
                    ),
                }
            ],
        }

    async def _handle_get_billing_doc_detail(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle BAPI_BILLINGDOC_GETDETAIL1 simulation.

        Returns billing document header and items for a specific document.

        Args:
            payload: Must contain BILLINGDOCUMENT (billing doc number)

        Returns:
            Dict with BILLINGDOCUMENTHEADER, BILLINGDOCUMENTITEM,
            BILLINGDOCUMENTPARTNER, and RETURN
        """
        doc_number = payload.get("BILLINGDOCUMENT", "")
        billing_docs = _get_dynamic_billing_docs()

        if doc_number not in billing_docs:
            return {
                "BILLINGDOCUMENTHEADER": {},
                "BILLINGDOCUMENTITEM": [],
                "BILLINGDOCUMENTPARTNER": [],
                "RETURN": [
                    {
                        "TYPE": SAPMessageTypes.ERROR,
                        "MESSAGE": f"Billing document {doc_number} not found",
                    }
                ],
            }

        doc = billing_docs[doc_number]

        # Build VBRK-style header
        header = {
            "VBELN": doc["document_number"],
            "FKART": doc.get("billing_type", "F2"),
            "FKDAT": doc.get("document_date", ""),
            "KUNAG": doc.get("customer_id", ""),
            "KUNRG": doc.get("customer_id", ""),  # Payer defaults to sold-to
            "NETWR": doc.get("amount", 0.0),
            "WAERK": doc.get("currency", "USD"),
            "ZTERM": "",  # Derived from payment_terms_text
            "ZLSCH": "",  # Payment method
            "FKSTO": "",  # Not cancelled
        }

        # Add clearing info for FAZ documents
        if doc.get("billing_type") == "FAZ":
            header["CLEARING_DATE"] = doc.get("clearing_date")
            header["CLEARING_DOC"] = doc.get("clearing_doc")

        # Build VBRP-style item
        items = [
            {
                "VBELN": doc["document_number"],
                "POSNR": "000010",
                "AUBEL": doc.get("sales_order", ""),
                "AUPOS": doc.get("sales_order_item", "000010"),
                "FKIMG": 1.0,
                "NETWR": doc.get("amount", 0.0),
                "WAERK": doc.get("currency", "USD"),
                "MWSBP": 0.0,  # No tax in simulation
            }
        ]

        # Build partner list
        customer_id = doc.get("customer_id", "")
        customer_name = doc.get("customer_name", "")
        partners = [
            {"PARVW": "AG", "KUNNR": customer_id, "NAME1": customer_name},
            {"PARVW": "RE", "KUNNR": customer_id, "NAME1": customer_name},
            {"PARVW": "RG", "KUNNR": customer_id, "NAME1": customer_name},
        ]

        return {
            "BILLINGDOCUMENTHEADER": header,
            "BILLINGDOCUMENTITEM": items,
            "BILLINGDOCUMENTPARTNER": partners,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Billing document {doc_number} retrieved",
                }
            ],
        }

    async def _handle_get_open_ar_items(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Handle BAPI_AR_ACC_GETOPENITEMS simulation.

        Returns open (unpaid) AR items for a customer, including
        outstanding downpayment requests and unpaid invoices.

        Args:
            payload: Must contain CUSTOMER (customer ID)
                     Optional: COMPANYCODE

        Returns:
            Dict with LINEITEMS (open AR items) and RETURN
        """
        customer_id = payload.get("CUSTOMER", "").zfill(10)
        billing_docs = _get_dynamic_billing_docs()

        open_items = []
        for doc_number, doc in billing_docs.items():
            # Filter by customer
            if doc["customer_id"] != customer_id:
                continue

            # Only include unpaid items
            if doc["status"] in ("PAID",):
                continue

            # Build AR line item
            item = {
                "BELNR": doc["document_number"],  # Accounting doc number
                "BUZEI": "001",  # Line item
                "BUKRS": "1000",  # Company code
                "KUNNR": customer_id,
                "BLART": "RV" if doc.get("billing_type") != "FAZ" else "DZ",
                "DMBTR": doc.get("amount", 0.0),  # Amount in local currency
                "WRBTR": doc.get("amount", 0.0),  # Amount in doc currency
                "WAERS": doc.get("currency", "USD"),
                "BUDAT": doc.get("document_date", ""),
                "ZFBDT": doc.get("due_date", ""),  # Baseline date
                "AUGDT": doc.get("clearing_date"),  # Clearing date (None if open)
                "AUGBL": doc.get("clearing_doc"),  # Clearing document
                "FKART": doc.get("billing_type", "F2"),
                "AUBEL": doc.get("sales_order", ""),  # Sales order reference
            }
            open_items.append(item)

        return {
            "LINEITEMS": open_items,
            "RETURN": [
                {
                    "TYPE": SAPMessageTypes.SUCCESS,
                    "MESSAGE": f"Retrieved {len(open_items)} open items for customer {customer_id}",
                }
            ],
        }

    # =========================================================================
    # RFC_READ_TEXT Handler
    # =========================================================================

    async def _handle_read_text(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle RFC_READ_TEXT for payment terms text.

        Looks up the billing document in simulated billing docs and converts
        the payment_terms_text field into SAP TEXT_LINES format.

        Args:
            payload: Must contain TEXT_NAME (billing document number)

        Returns:
            Dict with TEXT_LINES, MESSAGES, OBJECTLINKS
        """
        doc_number = payload.get("TEXT_NAME", "")
        billing_docs = _get_dynamic_billing_docs()
        doc = billing_docs.get(doc_number, {})
        payment_text = doc.get("payment_terms_text", "")

        if not payment_text:
            return {"TEXT_LINES": [], "MESSAGES": [], "OBJECTLINKS": []}

        # Convert text to TEXT_LINES format
        text_lines = []
        for line in payment_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            text_lines.append(
                {
                    "TDOBJECT": "VBBK",
                    "TDNAME": doc_number,
                    "TDID": "ZE06",
                    "TDSPRAS": "E",
                    "COUNTER": "000",
                    "TDFORMAT": "*",
                    "TDLINE": line,
                }
            )

        return {"TEXT_LINES": text_lines, "MESSAGES": [], "OBJECTLINKS": []}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _resolve_customer_id(self, identifier: str) -> Optional[str]:
        """Resolve customer identifier to SAP customer number."""
        padded_id = identifier.zfill(10) if identifier.isdigit() else None
        if padded_id and padded_id in SIMULATED_CUSTOMERS:
            return padded_id

        normalized = identifier.lower().strip()
        if normalized in CUSTOMER_NAME_LOOKUP:
            return CUSTOMER_NAME_LOOKUP[normalized]

        for name_key, cust_id in CUSTOMER_NAME_LOOKUP.items():
            if name_key in normalized or normalized in name_key:
                return cust_id

        return None

    def get_customer_by_name(self, name: str) -> Optional[SimulatedCustomer]:
        """Get customer by name lookup."""
        customer_id = self._resolve_customer_id(name)
        return SIMULATED_CUSTOMERS.get(customer_id) if customer_id else None

    def get_customer_by_uen(self, uen: str) -> Optional[SimulatedCustomer]:
        """
        Get customer by UEN (Tax Number 1) direct lookup.

        This provides O(1) lookup when entity resolution has already confirmed
        the entity's UEN, avoiding name-based fuzzy matching.

        Args:
            uen: Singapore Unique Entity Number (e.g., "199901234A")

        Returns:
            SimulatedCustomer if found, None otherwise
        """
        if not uen:
            return None

        uen_upper = uen.upper().strip()
        for customer in SIMULATED_CUSTOMERS.values():
            if customer.stcd1 and customer.stcd1.upper() == uen_upper:
                return customer
        return None

    def list_customers(self) -> list[dict[str, Any]]:
        """List all simulated customers."""
        return [
            {
                "customer_id": c.kunnr,
                "name": c.name1,
                "city": c.city,
                "country": c.country,
                "credit_limit": c.klimk,
                "credit_exposure": c.skfor + c.sauft,
                "risk_category": c.ctlpc,
                "currency": c.waerk,
            }
            for c in SIMULATED_CUSTOMERS.values()
        ]

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "CPISimulator":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
