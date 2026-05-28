"""
SAP MS5 (S/4HANA) Client

Handles RFC/BAPI calls to SAP S/4HANA system.
Uses SAP CPI as middleware for connectivity.

BAPI Field Mappings (validated against SAP standards):
    - BAPI_CUSTOMER_GETDETAIL2: Address in CUSTOMERADDRESS structure (CITY1, POST_CODE1)
    - BAPI_CR_ACC_GETDETAIL: Credit data (NOT BAPI_CREDITMANAGEMENT_GETLIST)
    - BAPI_SALESORDER_SIMULATE: Net value from ORDER_ITEMS_OUT (sum of items)
    - BAPI_SALESORDER_CREATEFROMDAT2: Requires BAPI_TRANSACTION_COMMIT after success

SAP CPI Response Formats:
    - Combined response: Customer + Credit data returned together with nested CREDIT object
    - Separate responses: Individual BAPI calls for customer and credit data
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from lead_to_cash.config import config
from lead_to_cash.integrations.cpi_client import CPIClient

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CustomerSearchResult:
    """Customer search result from SAP for KYP lookup.

    Used when searching for customers by name before retrieving full details.
    """

    customer_id: str
    name: str
    tax_number_1: str = ""  # STCD1 - UEN for Singapore
    tax_number_2: str = ""  # STCD2
    country: str = ""
    city: str = ""


@dataclass
class CustomerData:
    """Customer master data from SAP.

    Note: Credit data can be included if retrieved via get_customer_with_credit().
    """

    customer_id: str
    name: str
    tax_number_1: str = ""  # STCD1 - UEN for Singapore
    tax_number_2: str = ""  # STCD2
    address: Optional[dict] = None
    contact: Optional[dict] = None
    messages: Optional[list] = None
    # Optional credit data (populated when using combined endpoint)
    credit: Optional["CreditData"] = None


@dataclass
class CreditData:
    """Customer credit data from SAP."""

    customer_id: str
    credit_control_area: str
    credit_limit: float
    credit_exposure: float
    available_credit: float
    credit_check_passed: bool
    utilization_percent: float
    currency: str = "SGD"  # Currency code from customer master (WAERK)
    messages: Optional[list] = None


@dataclass
class SalesOrderSimulation:
    """Sales order simulation result."""

    is_valid: bool
    net_value: float
    currency: str
    item_count: int
    messages: list[dict]
    errors: list[dict]
    warnings: list[dict]
    pricing_conditions: list[dict]
    schedule_lines: list[dict]


@dataclass
class SalesOrderResult:
    """Sales order creation result."""

    success: bool
    document_number: str
    committed: bool
    test_run: bool
    messages: list[dict]


@dataclass
class BillingPlanLine:
    """A single milestone/date line in a billing plan (FPLTR)."""

    sequence: str  # FPLTR line number
    billing_date: str  # FDATU
    description: str  # TETXT
    amount: float  # FAKWR
    percentage: float  # BETEFP
    billing_type: str  # FPFAR (FAZ=downpayment, F2=invoice)
    billing_status: str  # FKSAF (A=open, B=billed, C=cancelled)
    billing_block: str  # FAKSP (blank=no block)
    billing_doc: str  # VBELN of created billing document


@dataclass
class BillingPlanData:
    """Billing plan data from a sales order (FPLT + FPLTR)."""

    plan_number: str  # FPLNR
    plan_type: str  # FPART (01=periodic, 02=milestone)
    currency: str  # WAESSION
    total_value: float  # FAKWR
    sales_order: str
    milestones: list[BillingPlanLine]

    def redacted(self) -> "BillingPlanData":
        """Return a copy with sensitive amounts redacted."""
        return BillingPlanData(
            plan_number=self.plan_number,
            plan_type=self.plan_type,
            currency=self.currency,
            total_value=0.0,
            sales_order=self.sales_order,
            milestones=[
                BillingPlanLine(
                    sequence=m.sequence,
                    billing_date=m.billing_date,
                    description=m.description,
                    amount=0.0,
                    percentage=m.percentage,
                    billing_type=m.billing_type,
                    billing_status=m.billing_status,
                    billing_block=m.billing_block,
                    billing_doc=m.billing_doc,
                )
                for m in self.milestones
            ],
        )


REDACTED = "***REDACTED***"

# Sensitive header fields redacted for non-financial roles
_SENSITIVE_HEADER_FIELDS = {"NETWR", "ZTERM", "WAERK"}
# Sensitive partner fields
_SENSITIVE_PARTNER_FIELDS = {"KUNNR"}


@dataclass
class SalesOrderDetail:
    """Full sales order detail including billing plan."""

    order_number: str
    header: dict
    items: list[dict]
    partners: list[dict]
    billing_plan: Optional[BillingPlanData]
    status: dict
    messages: list[dict]

    def redacted(self) -> "SalesOrderDetail":
        """Return a copy with sensitive financial and partner fields redacted.

        Use this when returning order data to users without financial permissions.
        """
        redacted_header = {
            k: (REDACTED if k in _SENSITIVE_HEADER_FIELDS else v)
            for k, v in self.header.items()
        }
        redacted_partners = [
            {
                k: (REDACTED if k in _SENSITIVE_PARTNER_FIELDS else v)
                for k, v in partner.items()
            }
            for partner in self.partners
        ]
        redacted_items = [
            {k: (REDACTED if k in {"NETWR", "WAERK"} else v) for k, v in item.items()}
            for item in self.items
        ]
        redacted_bp = self.billing_plan.redacted() if self.billing_plan else None

        return SalesOrderDetail(
            order_number=self.order_number,
            header=redacted_header,
            items=redacted_items,
            partners=redacted_partners,
            billing_plan=redacted_bp,
            status=self.status,
            messages=self.messages,
        )


@dataclass
class BillingDocumentDetail:
    """Billing document detail (VBRK + VBRP)."""

    document_number: str
    billing_type: str  # F2=invoice, FAZ=downpayment, S1=credit memo
    billing_date: str
    customer_id: str
    payer_id: str
    net_value: float
    currency: str
    is_cancelled: bool
    clearing_date: Optional[str]  # For FAZ: when DP was paid
    clearing_doc: Optional[str]  # FI clearing document
    items: list[dict]
    partners: list[dict]
    sales_order: str  # Reference sales order
    messages: list[dict]


@dataclass
class OpenARItem:
    """Open accounts receivable item."""

    document_number: str
    line_item: str
    company_code: str
    customer_id: str
    document_type: str  # RV=invoice, DZ=downpayment
    amount: float
    currency: str
    posting_date: str
    due_date: str
    clearing_date: Optional[str]
    clearing_doc: Optional[str]
    billing_type: str  # F2/FAZ
    sales_order: str


@dataclass
class KYPAssessment:
    """KYP (Know Your Partner) assessment data from SAP.

    Combines customer details and credit information for due diligence.
    """

    customer_id: str
    customer_name: str
    tax_number_1: str  # UEN for Singapore
    tax_number_2: str
    credit_limit: float
    credit_exposure: float
    available_credit: float
    utilization_percent: float
    currency: str = "SGD"
    country: str = ""
    city: str = ""
    credit_messages: Optional[list] = None


# =============================================================================
# SAP BAPI Constants
# =============================================================================


class SAPBAPIs:
    """SAP BAPI function names (validated against SAP documentation)."""

    # Customer Master
    CUSTOMER_GETLIST = "BAPI_CUSTOMER_GETLIST"
    CUSTOMER_GETDETAIL = "BAPI_CUSTOMER_GETDETAIL2"

    # Credit Management (CORRECTED from BAPI_CREDITMANAGEMENT_GETLIST)
    CREDIT_ACC_GETDETAIL = "BAPI_CR_ACC_GETDETAIL"

    # Sales Order
    SALESORDER_SIMULATE = "BAPI_SALESORDER_SIMULATE"
    SALESORDER_CREATE = "BAPI_SALESORDER_CREATEFROMDAT2"
    SALESORDER_GETDETAIL = "BAPI_SALESORDER_GETDETAIL"
    SALESORDER_GETSTATUS = "BAPI_SALESORDER_GETSTATUS"
    TRANSACTION_COMMIT = "BAPI_TRANSACTION_COMMIT"

    # Billing
    BILLINGDOC_GETLIST = "BAPI_BILLINGDOC_GETLIST"
    BILLINGDOC_GETDETAIL = "BAPI_BILLINGDOC_GETDETAIL1"
    AR_ACC_GETOPENITEMS = "BAPI_AR_ACC_GETOPENITEMS"

    # Text
    READ_TEXT = "RFC_READ_TEXT"


class SAPPartnerRoles:
    """SAP partner role codes."""

    SOLD_TO = "AG"
    SHIP_TO = "WE"
    BILL_TO = "RE"
    PAYER = "RG"


# =============================================================================
# MS5 Client
# =============================================================================


class MS5Client:
    """SAP MS5 (S/4HANA) Integration Client.

    Provides access to SAP BAPIs via CPI middleware.

    Supported BAPIs (with correct field mappings):
        - BAPI_CUSTOMER_GETDETAIL2: Customer master data
          - Address fields in CUSTOMERADDRESS structure (CITY1, POST_CODE1)
        - BAPI_CR_ACC_GETDETAIL: Credit account data
          - Note: NOT BAPI_CREDITMANAGEMENT_GETLIST (does not exist)
        - BAPI_SALESORDER_SIMULATE: Order simulation
          - Net value calculated from ORDER_ITEMS_OUT (not ORDER_HEADER_OUT)
        - BAPI_SALESORDER_CREATEFROMDAT2: Order creation
          - Requires BAPI_TRANSACTION_COMMIT after successful creation

    Access Scope:
        Set `customer_scope` to restrict which customers' data this client
        can access. When set, methods that return order/billing/AR data
        will verify the data belongs to an allowed customer before returning.

    Usage:
        async with MS5Client() as client:
            # Combined customer + credit data (recommended for KYP)
            customer = await client.get_customer_with_credit("1234")
            print(customer.credit.credit_limit)

            # Or separate calls
            customer = await client.get_customer("1234")
            credit = await client.check_credit_limit("1234", order_value=50000)

            # Order operations
            simulation = await client.simulate_order(order_data)
            result = await client.create_order(order_data)

            # Scoped access (gateway sets this based on authenticated user)
            client.customer_scope = {"0000100001", "0000100002"}
    """

    # Default iFlow for combined customer + credit data
    DEFAULT_KYP_IFLOW = "Integrum/RequestTableData"

    def __init__(
        self,
        cpi_client: Optional[CPIClient] = None,
        simulation_mode: bool = False,
        customer_scope: Optional[set[str]] = None,
    ):
        """Initialize MS5 client.

        Args:
            cpi_client: Optional CPI client instance for reuse
            simulation_mode: If True, use CPISimulator instead of real CPI
            customer_scope: Optional set of customer IDs this client is
                allowed to access. None means unrestricted (admin/internal).
        """
        self._simulation_mode = simulation_mode

        if simulation_mode:
            # Use CPISimulator directly for development/testing
            from lead_to_cash.integrations.cpi_simulator import CPISimulator

            self.cpi = CPISimulator()
        else:
            self.cpi = cpi_client or CPIClient()

        self._connected = False
        self.customer_scope: Optional[set[str]] = customer_scope

        # Rate limiter for write operations (max 10 per minute)
        self._write_timestamps: list[float] = []
        self._write_rate_limit = 10
        self._write_rate_window = 60.0  # seconds
        self._write_lock = asyncio.Lock()

    async def _check_write_rate_limit(self) -> None:
        """Enforce rate limit on write operations.

        Raises:
            RuntimeError: If rate limit exceeded
        """
        async with self._write_lock:
            now = time.monotonic()
            # Remove timestamps outside the window
            self._write_timestamps = [
                t for t in self._write_timestamps if now - t < self._write_rate_window
            ]
            if len(self._write_timestamps) >= self._write_rate_limit:
                raise RuntimeError(
                    f"Rate limit exceeded: max {self._write_rate_limit} write "
                    f"operations per {self._write_rate_window:.0f}s"
                )
            self._write_timestamps.append(now)

    def _check_customer_scope(self, customer_id: str) -> None:
        """Verify customer_id is within the allowed scope.

        Args:
            customer_id: Customer ID to check (will be zero-padded)

        Raises:
            PermissionError: If customer_id is not in allowed scope
        """
        if self.customer_scope is None:
            return  # Unrestricted access
        normalized = customer_id.zfill(10)
        if normalized not in self.customer_scope:
            raise PermissionError(
                f"Access denied: customer {normalized} is not in allowed scope"
            )

    async def connect(self) -> None:
        """Establish connection via CPI."""
        await self.cpi.connect()
        self._connected = True
        logger.info("MS5 client connected via CPI")

    async def disconnect(self) -> None:
        """Close connection."""
        await self.cpi.disconnect()
        self._connected = False

    def _ensure_connected(self) -> None:
        """Ensure MS5 client is connected.

        Raises:
            RuntimeError: If client not connected
        """
        if not self._connected:
            raise RuntimeError(
                "MS5 client not connected. Call connect() first or use async context manager."
            )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_float(self, value: Any) -> float:
        """Safely parse a value to float.

        Handles string values like "100000.0000" from SAP.

        Args:
            value: Value to parse (string, int, float, or None)

        Returns:
            Float value, or 0.0 if parsing fails
        """
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_credit_data(
        self,
        result: dict[str, Any],
        customer_id: str,
        credit_control_area: str = "",
        order_value: float = 0,
    ) -> CreditData:
        """Parse credit data from SAP response.

        Handles both nested CREDIT structure and flat top-level fields.

        Note: SAP CPI may return credit errors (e.g., routine LF035U16) for some
        customers. Per SAP team guidance, we accept the credit values as-is and
        include error messages for reference without failing the request.

        Args:
            result: SAP response dict
            customer_id: Customer ID for the credit data
            credit_control_area: Credit control area code
            order_value: Optional order value to check against available credit

        Returns:
            CreditData object
        """
        # Check for nested CREDIT structure first (combined response)
        credit_data = result.get("CREDIT", {})
        if credit_data:
            credit_limit = self._parse_float(credit_data.get("CREDIT_LIMIT", 0))
            credit_exposure = self._parse_float(credit_data.get("CREDIT_EXPOSURE", 0))
            currency = credit_data.get("CURRENCY", "SGD")
            messages = credit_data.get("RETURN", [])
        else:
            # Fall back to top-level fields (separate credit response)
            credit_limit = self._parse_float(result.get("CREDIT_LIMIT", 0))
            credit_exposure = self._parse_float(result.get("CREDIT_EXPOSURE", 0))
            currency = result.get("CURRENCY", "SGD")
            messages = result.get("RETURN", [])

        available_credit = credit_limit - credit_exposure

        # Check for errors in credit messages (log but don't fail)
        has_credit_error = any(
            m.get("TYPE") in ("E", "A", "X") for m in messages if isinstance(m, dict)
        )
        if has_credit_error:
            logger.info(
                f"Credit data has SAP messages for customer {customer_id}: {messages}"
            )

        # Check for SAP credit block indicator (crblb="X" → WARNING "Credit blocked")
        is_credit_blocked = any(
            m.get("TYPE") == "W" and "blocked" in (m.get("MESSAGE", "") or "").lower()
            for m in messages
            if isinstance(m, dict)
        )

        # Determine credit check result based on actual values
        # Per SAP team: accept credit values as-is, don't fail on SAP errors
        if is_credit_blocked:
            credit_check_passed = False
        elif order_value > 0:
            credit_check_passed = order_value <= available_credit
        else:
            # Credit blocked if exposure exceeds limit (overdrawn)
            if credit_limit > 0 and credit_exposure > credit_limit:
                credit_check_passed = False
            else:
                credit_check_passed = credit_limit > 0 or credit_exposure == 0

        # Calculate utilization
        if credit_limit > 0:
            utilization = credit_exposure / credit_limit * 100
        elif credit_exposure > 0:
            utilization = 100  # Over limit
        else:
            utilization = 0  # No limit, no exposure

        return CreditData(
            customer_id=customer_id,
            credit_control_area=credit_control_area,
            credit_limit=credit_limit,
            credit_exposure=credit_exposure,
            available_credit=available_credit,
            credit_check_passed=credit_check_passed,
            utilization_percent=utilization,
            currency=currency,
            messages=messages if messages else None,
        )

    def _parse_customer_data(
        self, result: dict[str, Any], customer_id: str
    ) -> CustomerData:
        """Parse customer data from SAP response.

        Args:
            result: SAP response dict
            customer_id: Customer ID

        Returns:
            CustomerData object
        """
        # Extract from correct SAP structures
        # Address data is in CUSTOMERADDRESS (BAPICUSTOMER_04)
        address = result.get("CUSTOMERADDRESS", {})
        general = result.get("CUSTOMERGENERALDETAIL", {})

        return CustomerData(
            customer_id=customer_id,
            name=address.get("NAME1") or general.get("NAME1", ""),
            tax_number_1=address.get("STCD1", ""),  # UEN for Singapore
            tax_number_2=address.get("STCD2", ""),
            address={
                "street": address.get("STREET", ""),
                "city": address.get("CITY1", ""),  # CORRECT: CITY1, not CITY
                "postal_code": address.get("POST_CODE1", ""),  # CORRECT: POST_CODE1
                "country": address.get("COUNTRY", ""),
                "region": address.get("REGION", ""),
            },
            contact={
                "telephone": address.get("TEL1_NUMBR", ""),
                "fax": address.get("FAX_NUMBER", ""),
                "email": address.get("E_MAIL", ""),
            },
            messages=result.get("RETURN", []),
        )

    # =========================================================================
    # Customer Operations
    # =========================================================================

    async def search_customers(
        self,
        name: str,
        max_results: int = 50,
        country: Optional[str] = None,
    ) -> list[CustomerSearchResult]:
        """Search customers by name for KYP lookup.

        For real SAP CPI (production):
            Uses entity registry to resolve company names to SAP customer IDs,
            then fetches real customer data via Integrum/RequestTableData iFlow.

        For CPISimulator (development):
            Uses simulator's built-in customer search.

        Args:
            name: Customer name to search
            max_results: Maximum results to return (default 50)
            country: Optional country code filter

        Returns:
            List of CustomerSearchResult with matching customers

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        # Check if using simulator - use its native search
        from lead_to_cash.integrations.cpi_simulator import CPISimulator

        if isinstance(self.cpi, CPISimulator):
            # Simulator has built-in customer search via BAPI simulation
            search_pattern = name if "*" in name else f"*{name}*"
            payload: dict[str, Any] = {
                "bapi": SAPBAPIs.CUSTOMER_GETLIST,
                "MAXROWS": max_results,
                "NAMERANGE": [
                    {
                        "SIGN": "I",
                        "OPTION": "CP",
                        "LOW": search_pattern.upper(),
                    }
                ],
            }
            if country:
                payload["COUNTRYRANGE"] = [
                    {"SIGN": "I", "OPTION": "EQ", "LOW": country.upper()}
                ]

            result = await self.cpi.call_iflow(
                iflow_name="CustomerGetList",
                payload=payload,
            )

            customers = []
            for item in result.get("ADDRESSDATA", []):
                customers.append(
                    CustomerSearchResult(
                        customer_id=item.get("CUSTOMER", "").lstrip("0"),
                        name=item.get("NAME", ""),
                        tax_number_1=item.get("STCD1", ""),
                        tax_number_2=item.get("STCD2", ""),
                        country=item.get("COUNTRY", ""),
                        city=item.get("CITY", ""),
                    )
                )
            return customers

        # Real CPI: Use entity registry to resolve name to SAP customer ID
        # The real SAP CPI only has Integrum/RequestTableData which requires a customer ID
        try:
            from lead_to_cash.services.entity_registry import EntityResolutionService

            entity_service = EntityResolutionService()
            await entity_service.initialize()

            # Search entity registry for matching companies
            result = await entity_service.resolve(name, search_external=False)

            customers = []

            # Collect candidates (either exact match or confirmation candidates)
            candidates = []
            if result.exact_match:
                candidates = [result.exact_match]
            elif result.candidates:
                candidates = result.candidates[:max_results]

            # For each matching entity, get SAP customer ID and fetch real data
            for candidate in candidates:
                if not candidate.entity_id:
                    continue

                # Get SAP customer ID from entity mappings
                sap_id = await entity_service.get_entity_for_system(
                    candidate.entity_id, "sap"
                )

                if sap_id:
                    # Fetch real customer data from SAP
                    try:
                        customer_data = await self.get_customer_with_credit(
                            customer_id=sap_id,
                            credit_control_area="0111",  # Default CCA
                        )
                        address = customer_data.address or {}
                        customers.append(
                            CustomerSearchResult(
                                customer_id=sap_id.lstrip("0"),
                                name=customer_data.name,
                                tax_number_1=customer_data.tax_number_1,
                                tax_number_2=customer_data.tax_number_2,
                                country=address.get("country", ""),
                                city=address.get("city", ""),
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch SAP data for {sap_id}: {e}")
                        # Still add the entity info without SAP data
                        customers.append(
                            CustomerSearchResult(
                                customer_id=sap_id.lstrip("0"),
                                name=candidate.canonical_name,
                                tax_number_1=candidate.uen or "",
                                country=candidate.country_code or "",
                                city="",
                            )
                        )
                else:
                    # Entity exists but no SAP mapping - include with entity info
                    customers.append(
                        CustomerSearchResult(
                            customer_id="",  # No SAP ID
                            name=candidate.canonical_name,
                            tax_number_1=candidate.uen or "",
                            country=candidate.country_code or "",
                            city="",
                        )
                    )

            return customers[:max_results]

        except ImportError:
            logger.error("Entity registry module not available")
            return []
        except Exception as e:
            logger.error(f"Entity resolution failed: {e}")
            return []

    async def search_customer_by_uen(
        self,
        uen: str,
    ) -> Optional[CustomerSearchResult]:
        """Search for a customer by UEN (Tax Number 1) for direct lookup.

        This method provides O(1) lookup when entity resolution has already
        confirmed the entity's UEN, avoiding name-based fuzzy matching.

        For the simulator, this uses direct UEN lookup.
        For real SAP, this searches customers and filters by UEN.

        Args:
            uen: Singapore Unique Entity Number (e.g., "199901234A")

        Returns:
            CustomerSearchResult if found, None otherwise

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        if not uen:
            return None

        # Check if using simulator (has direct UEN lookup)
        from lead_to_cash.integrations.cpi_simulator import CPISimulator

        if isinstance(self.cpi, CPISimulator):
            customer = self.cpi.get_customer_by_uen(uen)
            if customer:
                return CustomerSearchResult(
                    customer_id=customer.kunnr.lstrip("0"),
                    name=customer.name1,
                    tax_number_1=customer.stcd1,
                    tax_number_2=customer.stcd2,
                    country=customer.country,
                    city=customer.city,
                )
            return None

        # For real SAP: Use Integrum/RequestTableData to query KNA1 by STCD1
        import re

        if not re.match(r"^[A-Za-z0-9\-]+$", uen):
            logger.warning("MS5Client: Invalid UEN format — must be alphanumeric")
            return None

        logger.debug(f"MS5Client: Searching for customer by UEN via SAP CPI")

        try:
            # Query KNA1 table filtered by STCD1 (Tax Number 1 = UEN)
            result = await self.cpi.call_iflow(
                iflow_name=self.DEFAULT_KYP_IFLOW,
                payload={
                    "table": "KNA1",
                    "fields": ["KUNNR", "NAME1", "STCD1", "STCD2", "LAND1", "ORT01"],
                    "filter": f"STCD1 eq '{uen}'",
                    "maxRows": 1,
                },
            )

            rows = result.get("DATA", [])
            if not rows:
                logger.debug(
                    f"MS5Client: No customer found with UEN ...{uen[-4:] if len(uen) > 4 else '[redacted]'}"
                )
                return None

            row = rows[0]
            return CustomerSearchResult(
                customer_id=row.get("KUNNR", "").lstrip("0"),
                name=row.get("NAME1", ""),
                tax_number_1=row.get("STCD1", ""),
                tax_number_2=row.get("STCD2", ""),
                country=row.get("LAND1", ""),
                city=row.get("ORT01", ""),
            )

        except Exception as e:
            logger.warning(
                f"MS5Client: UEN search via SAP CPI failed: {e}. "
                "Falling back to name-based search."
            )
            return None

    async def get_customer(self, customer_id: str) -> CustomerData:
        """Get customer master data.

        Uses BAPI_CUSTOMER_GETDETAIL2.
        Address data comes from CUSTOMERADDRESS structure with correct field names.

        Note: For KYP use cases, prefer get_customer_with_credit() which returns
        both customer and credit data in a single call.

        Args:
            customer_id: SAP customer number (KUNNR)

        Returns:
            CustomerData with master data including UEN/Tax IDs

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="CustomerGetDetail",
            payload={
                "bapi": SAPBAPIs.CUSTOMER_GETDETAIL,
                "CUSTOMERNO": customer_id.zfill(10),
            },
        )

        return self._parse_customer_data(result, customer_id)

    async def get_customer_with_credit(
        self,
        customer_id: str,
        credit_control_area: Optional[str] = None,
    ) -> CustomerData:
        """Get customer master data with credit information in a single call.

        Uses the combined SAP CPI endpoint that returns both CUSTOMERADDRESS
        and nested CREDIT data. More efficient than separate calls.

        Args:
            customer_id: SAP customer number (KUNNR)
            credit_control_area: Credit control area (optional)

        Returns:
            CustomerData with credit field populated

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        # Determine credit control area
        cca = (
            credit_control_area or config.sap_ms5.default_credit_control_area or "0111"
        )

        # Build XML payload for KYP request (CreditControlArea required for credit data)
        xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<KYPRequest>
    <CUSTOMERNO>{customer_id.zfill(10)}</CUSTOMERNO>
    <CreditControlArea>{cca}</CreditControlArea>
</KYPRequest>"""

        result = await self.cpi.call_iflow_raw(
            iflow_name=self.DEFAULT_KYP_IFLOW,
            xml_payload=xml_payload,
        )

        # Parse customer data
        customer = self._parse_customer_data(result, customer_id)

        # Parse credit data from nested CREDIT structure
        customer.credit = self._parse_credit_data(result, customer_id, cca)

        return customer

    # =========================================================================
    # Credit Operations
    # =========================================================================

    async def check_credit_limit(
        self,
        customer_id: str,
        credit_control_area: Optional[str] = None,
        order_value: float = 0,
    ) -> CreditData:
        """Check customer credit limit and exposure.

        Supports both:
        - Combined response with nested CREDIT structure
        - Separate BAPI_CR_ACC_GETDETAIL call with top-level fields

        Args:
            customer_id: SAP customer number
            credit_control_area: Credit control area (defaults to config value)
            order_value: Optional order value to check against available credit

        Returns:
            CreditData with credit information and pass/fail status

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        cca = (
            credit_control_area or config.sap_ms5.default_credit_control_area or "0111"
        )

        # Try combined endpoint first (more efficient)
        try:
            # CreditControlArea required for credit data retrieval
            xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<KYPRequest>
    <CUSTOMERNO>{customer_id.zfill(10)}</CUSTOMERNO>
    <CreditControlArea>{cca}</CreditControlArea>
</KYPRequest>"""

            result = await self.cpi.call_iflow_raw(
                iflow_name=self.DEFAULT_KYP_IFLOW,
                xml_payload=xml_payload,
            )

            return self._parse_credit_data(result, customer_id, cca, order_value)

        except Exception as e:
            logger.warning(
                f"Combined endpoint failed, falling back to separate credit call: {e}"
            )

            # Fall back to separate credit BAPI call
            result = await self.cpi.call_iflow(
                iflow_name="CreditGetAccount",
                payload={
                    "bapi": SAPBAPIs.CREDIT_ACC_GETDETAIL,
                    "CUSTOMER": customer_id.zfill(10),
                    "CREDITCONTROLAREA": cca,
                },
            )

            return self._parse_credit_data(result, customer_id, cca, order_value)

    # =========================================================================
    # KYP Operations
    # =========================================================================

    async def get_kyp_assessment(
        self,
        customer_id: str,
        credit_control_area: Optional[str] = None,
    ) -> KYPAssessment:
        """Get KYP (Know Your Partner) assessment for a customer.

        Uses the combined SAP CPI endpoint to retrieve customer master data
        and credit information in a single call.

        Args:
            customer_id: SAP customer number (KUNNR)
            credit_control_area: Credit control area (defaults to config)

        Returns:
            KYPAssessment with customer details and credit information

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        # Use combined endpoint for efficiency
        customer = await self.get_customer_with_credit(customer_id, credit_control_area)

        # Extract credit data (will be populated from combined response)
        credit = customer.credit
        if not credit:
            # Fallback if credit data wasn't in combined response
            credit = CreditData(
                customer_id=customer_id,
                credit_control_area=credit_control_area or "",
                credit_limit=0,
                credit_exposure=0,
                available_credit=0,
                credit_check_passed=False,
                utilization_percent=0,
            )

        return KYPAssessment(
            customer_id=customer_id,
            customer_name=customer.name,
            tax_number_1=customer.tax_number_1,
            tax_number_2=customer.tax_number_2,
            credit_limit=credit.credit_limit,
            credit_exposure=credit.credit_exposure,
            available_credit=credit.available_credit,
            utilization_percent=credit.utilization_percent,
            currency=credit.currency if credit.currency else "SGD",
            country=customer.address.get("country", "") if customer.address else "",
            city=customer.address.get("city", "") if customer.address else "",
            credit_messages=credit.messages,
        )

    # =========================================================================
    # Order Operations
    # =========================================================================

    async def simulate_order(
        self,
        order_data: dict[str, Any],
    ) -> SalesOrderSimulation:
        """Simulate sales order.

        Uses BAPI_SALESORDER_SIMULATE.
        IMPORTANT: Net value is calculated from ORDER_ITEMS_OUT (sum of item values),
        NOT from ORDER_HEADER_OUT which doesn't exist in this BAPI.

        Args:
            order_data: Order header and line items
                - header: Dict with DOC_TYPE, SALES_ORG, DISTR_CHAN, DIVISION
                - items: List of items with MATERIAL, REQ_QTY, SALES_UNIT, PLANT
                - partners: List of partners with PARTN_ROLE, PARTN_NUMB

        Returns:
            SalesOrderSimulation with pricing and validation

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="OrderSimulate",
            payload={
                "bapi": SAPBAPIs.SALESORDER_SIMULATE,
                "ORDER_HEADER_IN": order_data.get("header", {}),
                "ORDER_ITEMS_IN": order_data.get("items", []),
                "ORDER_PARTNERS": order_data.get("partners", []),
            },
        )

        messages = result.get("RETURN", [])
        has_errors = any(m.get("TYPE") in ("E", "A", "X") for m in messages)

        # CORRECT: Net value comes from ORDER_ITEMS_OUT, not ORDER_HEADER_OUT
        # ORDER_HEADER_OUT doesn't exist in BAPI_SALESORDER_SIMULATE
        items_out = result.get("ORDER_ITEMS_OUT", [])
        total_net_value = sum(
            self._parse_float(item.get("NET_VALUE", 0)) for item in items_out
        )
        currency = items_out[0].get("CURRENCY", "EUR") if items_out else "EUR"

        return SalesOrderSimulation(
            is_valid=not has_errors,
            net_value=total_net_value,
            currency=currency,
            item_count=len(items_out),
            messages=messages,
            errors=[m for m in messages if m.get("TYPE") in ("E", "A", "X")],
            warnings=[m for m in messages if m.get("TYPE") == "W"],
            pricing_conditions=result.get("ORDER_CONDITIONS_OUT", []),
            schedule_lines=result.get("ORDER_SCHEDULES_OUT", []),
        )

    async def create_order(
        self,
        order_data: dict[str, Any],
        test_run: bool = False,
    ) -> SalesOrderResult:
        """Create sales order.

        Uses BAPI_SALESORDER_CREATEFROMDAT2.
        CRITICAL: Also calls BAPI_TRANSACTION_COMMIT after successful creation.
        The BAPI does NOT auto-commit - commit is required!

        Args:
            order_data: Complete order data
                - header: Dict with DOC_TYPE, SALES_ORG, DISTR_CHAN, DIVISION, PURCH_NO_C
                - items: List of items
                - partners: List of partners
                - conditions: Optional pricing conditions
                - schedules: Optional schedule lines
            test_run: If True, validate only without creating

        Returns:
            SalesOrderResult with document number and commit status

        Raises:
            RuntimeError: If client not connected or rate limit exceeded
        """
        await self._check_write_rate_limit()
        self._ensure_connected()

        # Create order
        result = await self.cpi.call_iflow(
            iflow_name="OrderCreate",
            payload={
                "bapi": SAPBAPIs.SALESORDER_CREATE,
                "ORDER_HEADER_IN": order_data.get("header", {}),
                "ORDER_ITEMS_IN": order_data.get("items", []),
                "ORDER_PARTNERS": order_data.get("partners", []),
                "ORDER_CONDITIONS_IN": order_data.get("conditions", []),
                "ORDER_SCHEDULES_IN": order_data.get("schedules", []),
                "TESTRUN": "X" if test_run else "",
            },
        )

        messages = result.get("RETURN", [])
        has_errors = any(m.get("TYPE") in ("E", "A", "X") for m in messages)
        doc_number = result.get("SALESDOCUMENT", "")

        # CRITICAL: Call BAPI_TRANSACTION_COMMIT if successful and not test run
        committed = False
        if doc_number and not has_errors and not test_run:
            try:
                await self.cpi.call_iflow(
                    iflow_name="TransactionCommit",
                    payload={
                        "bapi": SAPBAPIs.TRANSACTION_COMMIT,
                        "WAIT": "X",  # Wait for commit to complete
                    },
                )
                committed = True
                logger.info(f"Order {doc_number} committed to SAP")
            except Exception as e:
                logger.error(f"Failed to commit order {doc_number}: {e}")
                # Order was created but not committed - this is a serious issue
                messages.append(
                    {
                        "TYPE": "E",
                        "MESSAGE": f"Order created but commit failed: {e}",
                    }
                )

        return SalesOrderResult(
            success=bool(doc_number) and not has_errors and (committed or test_run),
            document_number=doc_number,
            committed=committed,
            test_run=test_run,
            messages=messages,
        )

    # =========================================================================
    # Post-Order: Billing Plan & Downpayment Retrieval
    # =========================================================================

    async def get_order_detail(
        self,
        order_number: str,
    ) -> SalesOrderDetail:
        """Get full sales order detail including billing plan.

        Uses BAPI_SALESORDER_GETDETAIL via MS5GetOrderDetail iFlow.

        Args:
            order_number: SAP sales order number (VBELN)

        Returns:
            SalesOrderDetail with header, items, partners, billing plan, status

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetOrderDetail",
            payload={
                "bapi": SAPBAPIs.SALESORDER_GETDETAIL,
                "SALESDOCUMENT": order_number,
            },
        )

        messages = result.get("RETURN", [])

        # Parse billing plan if present
        bp_data = result.get("BILLING_PLAN", {})
        billing_plan = None
        if bp_data and bp_data.get("FPLNR"):
            milestones = []
            for date_line in bp_data.get("dates", []):
                milestones.append(
                    BillingPlanLine(
                        sequence=date_line.get("FPLTR", ""),
                        billing_date=date_line.get("FDATU", ""),
                        description=date_line.get("TETXT", ""),
                        amount=self._parse_float(date_line.get("FAKWR", 0)),
                        percentage=self._parse_float(date_line.get("BETEFP", 0)),
                        billing_type=date_line.get("FPFAR", ""),
                        billing_status=date_line.get("FKSAF", ""),
                        billing_block=date_line.get("FAKSP", ""),
                        billing_doc=date_line.get("VBELN", ""),
                    )
                )
            billing_plan = BillingPlanData(
                plan_number=bp_data.get("FPLNR", ""),
                plan_type=bp_data.get("FPART", ""),
                currency=bp_data.get("WAESSION", ""),
                total_value=self._parse_float(bp_data.get("FAKWR", 0)),
                sales_order=order_number,
                milestones=milestones,
            )

        detail = SalesOrderDetail(
            order_number=order_number,
            header=result.get("ORDER_HEADER", {}),
            items=result.get("ORDER_ITEMS", []),
            partners=result.get("ORDER_PARTNERS", []),
            billing_plan=billing_plan,
            status=result.get("STATUS", {}),
            messages=messages,
        )

        # Enforce customer scope on returned order
        order_customer = detail.header.get("KUNNR", "")
        if order_customer:
            self._check_customer_scope(order_customer)

        return detail

    async def get_order_status(
        self,
        order_number: str,
    ) -> dict[str, Any]:
        """Get sales order status including per-item billing status.

        Uses BAPI_SALESORDER_GETSTATUS via MS5GetOrderStatus iFlow.

        Args:
            order_number: SAP sales order number

        Returns:
            Dict with STATUSINFO (per-item status) and OVERALL_STATUS

        Raises:
            RuntimeError: If client not connected
            PermissionError: If order's customer is not in scope
        """
        # Pre-check: fetch order header to verify customer scope
        if self.customer_scope is not None:
            order_detail = await self.get_order_detail(order_number)
            # get_order_detail already enforces scope

        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetOrderStatus",
            payload={
                "bapi": SAPBAPIs.SALESORDER_GETSTATUS,
                "SALESDOCUMENT": order_number,
            },
        )
        return {
            "status_items": result.get("STATUSINFO", []),
            "overall_status": result.get("OVERALL_STATUS", ""),
            "messages": result.get("RETURN", []),
        }

    async def get_billing_plan(
        self,
        order_number: str,
    ) -> Optional[BillingPlanData]:
        """Get billing plan milestones for a sales order.

        Uses BILLING_SCHEDULE_READ via MS5GetBillingPlan iFlow.

        Args:
            order_number: SAP sales order number

        Returns:
            BillingPlanData with milestones, or None if no billing plan

        Raises:
            RuntimeError: If client not connected
            PermissionError: If order's customer is not in scope
        """
        # Pre-check: verify order belongs to allowed customer
        if self.customer_scope is not None:
            await self.get_order_detail(order_number)
            # get_order_detail enforces scope

        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetBillingPlan",
            payload={
                "SALESDOCUMENT": order_number,
            },
        )

        header = result.get("BILLING_PLAN_HEADER", {})
        if not header or not header.get("FPLNR"):
            return None

        milestones = []
        for date_line in result.get("BILLING_PLAN_DATES", []):
            milestones.append(
                BillingPlanLine(
                    sequence=date_line.get("FPLTR", ""),
                    billing_date=date_line.get("FDATU", ""),
                    description=date_line.get("TETXT", ""),
                    amount=self._parse_float(date_line.get("FAKWR", 0)),
                    percentage=self._parse_float(date_line.get("BETEFP", 0)),
                    billing_type=date_line.get("FPFAR", ""),
                    billing_status=date_line.get("FKSAF", ""),
                    billing_block=date_line.get("FAKSP", ""),
                    billing_doc=date_line.get("VBELN", ""),
                )
            )

        return BillingPlanData(
            plan_number=header.get("FPLNR", ""),
            plan_type=header.get("FPART", ""),
            currency=header.get("WAESSION", ""),
            total_value=self._parse_float(header.get("FAKWR", 0)),
            sales_order=order_number,
            milestones=milestones,
        )

    async def get_billing_doc_detail(
        self,
        billing_doc_number: str,
    ) -> BillingDocumentDetail:
        """Get billing document detail (invoice or downpayment request).

        Uses BAPI_BILLINGDOC_GETDETAIL1 via MS5GetBillingDocDetail iFlow.

        Args:
            billing_doc_number: SAP billing document number (VBELN)

        Returns:
            BillingDocumentDetail with header, items, clearing info

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetBillingDocDetail",
            payload={
                "bapi": SAPBAPIs.BILLINGDOC_GETDETAIL,
                "BILLINGDOCUMENT": billing_doc_number,
            },
        )

        header = result.get("BILLINGDOCUMENTHEADER", {})
        items = result.get("BILLINGDOCUMENTITEM", [])
        sales_order = items[0].get("AUBEL", "") if items else ""

        detail = BillingDocumentDetail(
            document_number=header.get("VBELN", billing_doc_number),
            billing_type=header.get("FKART", ""),
            billing_date=header.get("FKDAT", ""),
            customer_id=header.get("KUNAG", ""),
            payer_id=header.get("KUNRG", ""),
            net_value=self._parse_float(header.get("NETWR", 0)),
            currency=header.get("WAERK", ""),
            is_cancelled=header.get("FKSTO", "") == "X",
            clearing_date=header.get("CLEARING_DATE"),
            clearing_doc=header.get("CLEARING_DOC"),
            items=items,
            partners=result.get("BILLINGDOCUMENTPARTNER", []),
            sales_order=sales_order,
            messages=result.get("RETURN", []),
        )

        # Enforce customer scope on billing document
        if detail.customer_id:
            self._check_customer_scope(detail.customer_id)

        return detail

    async def get_open_ar_items(
        self,
        customer_id: str,
        company_code: str = "1000",
    ) -> list[OpenARItem]:
        """Get open accounts receivable items for a customer.

        Uses BAPI_AR_ACC_GETOPENITEMS via MS5GetOpenARItems iFlow.
        Returns unpaid invoices and outstanding downpayment requests.

        Args:
            customer_id: SAP customer number
            company_code: Company code (default 1000)

        Returns:
            List of OpenARItem with outstanding receivables

        Raises:
            RuntimeError: If client not connected
            PermissionError: If customer is not in scope
        """
        # Enforce customer scope before querying
        self._check_customer_scope(customer_id)

        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetOpenARItems",
            payload={
                "bapi": SAPBAPIs.AR_ACC_GETOPENITEMS,
                "CUSTOMER": customer_id.zfill(10),
                "COMPANYCODE": company_code,
            },
        )

        items = []
        for line in result.get("LINEITEMS", []):
            items.append(
                OpenARItem(
                    document_number=line.get("BELNR", ""),
                    line_item=line.get("BUZEI", ""),
                    company_code=line.get("BUKRS", ""),
                    customer_id=line.get("KUNNR", ""),
                    document_type=line.get("BLART", ""),
                    amount=self._parse_float(line.get("WRBTR", 0)),
                    currency=line.get("WAERS", ""),
                    posting_date=line.get("BUDAT", ""),
                    due_date=line.get("ZFBDT", ""),
                    clearing_date=line.get("AUGDT"),
                    clearing_doc=line.get("AUGBL"),
                    billing_type=line.get("FKART", ""),
                    sales_order=line.get("AUBEL", ""),
                )
            )
        return items

    async def get_billing_docs_for_order(
        self,
        order_number: str,
    ) -> list[dict[str, Any]]:
        """Get all billing documents linked to a sales order.

        Convenience method that filters billing documents by sales order reference.

        Args:
            order_number: SAP sales order number

        Returns:
            List of billing document dicts (both FAZ and F2 types)

        Raises:
            RuntimeError: If client not connected
        """
        self._ensure_connected()

        # Use the existing billing documents endpoint with order filter
        result = await self.cpi.call_iflow(
            iflow_name="MS5GetBillingDocuments",
            payload={},
        )

        # Filter by sales order reference
        docs = []
        for doc in result.get("documents", []):
            if doc.get("sales_order") == order_number:
                docs.append(doc)
        return docs

    # =========================================================================
    # Payment Terms Text
    # =========================================================================

    async def get_payment_terms_text(self, document_number: str) -> str:
        """Get payment terms text for a billing document via RFC_READ_TEXT.

        Args:
            document_number: SAP billing document number (VBELN)

        Returns:
            Formatted payment terms text string
        """
        self._ensure_connected()
        result = await self.cpi.call_iflow(
            iflow_name="MS5ReadText",
            payload={
                "bapi": SAPBAPIs.READ_TEXT,
                "TEXT_OBJECT": "VBBK",
                "TEXT_NAME": document_number,
                "TEXT_ID": "ZE06",
                "TEXT_LANGUAGE": "E",
            },
        )

        text_lines = result.get("TEXT_LINES", [])
        return self._parse_text_lines(text_lines)

    @staticmethod
    def _parse_text_lines(text_lines: list[dict]) -> str:
        """Parse SAP RFC_READ_TEXT TEXT_LINES into readable text.

        TDFORMAT='*' starts a new paragraph, empty continues previous line.
        """
        if not text_lines:
            return ""
        paragraphs: list[str] = []
        current: list[str] = []
        for item in text_lines:
            line = item.get("TDLINE", "").strip()
            if not line:
                continue
            fmt = item.get("TDFORMAT", "")
            if fmt == "*":
                if current:
                    paragraphs.append(" ".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            paragraphs.append(" ".join(current))
        return "\n".join(paragraphs)

    # =========================================================================
    # Partner Functions
    # =========================================================================

    async def get_partner_functions(
        self,
        customer_id: str,
        sales_org: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """Get partner functions for customer.

        Note: Partner functions are NOT returned by BAPI_CUSTOMER_GETDETAIL2.
        This method calls a separate partner function retrieval iFlow.

        Args:
            customer_id: SAP customer number
            sales_org: Sales organization (defaults to config value)

        Returns:
            List of partner function assignments

        Raises:
            RuntimeError: If client not connected
            ValueError: If sales_org not configured
        """
        self._ensure_connected()

        org = sales_org or config.sap_ms5.default_sales_org
        if not org:
            raise ValueError(
                "Sales organization not configured. "
                "Set SAP_MS5_SALES_ORG environment variable or pass sales_org parameter."
            )

        result = await self.cpi.call_iflow(
            iflow_name="CustomerGetPartners",
            payload={
                "CUSTOMERNO": customer_id.zfill(10),
                "SALES_ORG": org,
            },
        )

        return result.get("PARTNER_FUNCTIONS", [])

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check MS5 connectivity."""
        cpi_health = await self.cpi.health_check()
        return {
            "status": "connected" if self._connected else "disconnected",
            "cpi_status": cpi_health,
            "ms5_host": config.sap_ms5.host or "not_configured",
            "default_kyp_iflow": self.DEFAULT_KYP_IFLOW,
            "bapis": {
                "customer": SAPBAPIs.CUSTOMER_GETDETAIL,
                "credit": SAPBAPIs.CREDIT_ACC_GETDETAIL,
                "order_simulate": SAPBAPIs.SALESORDER_SIMULATE,
                "order_create": SAPBAPIs.SALESORDER_CREATE,
                "order_getdetail": SAPBAPIs.SALESORDER_GETDETAIL,
                "order_getstatus": SAPBAPIs.SALESORDER_GETSTATUS,
                "billingdoc_getdetail": SAPBAPIs.BILLINGDOC_GETDETAIL,
                "ar_getopenitems": SAPBAPIs.AR_ACC_GETOPENITEMS,
                "read_text": SAPBAPIs.READ_TEXT,
            },
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "MS5Client":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
