"""
Aravo Third-Party Risk Management (TPRM) Client

Handles SOAP/XML API calls to Aravo for supplier due diligence, compliance,
and governance. Integrates with KYP (Know Your Partner) assessment.

API Documentation Reference:
    - Aravo Postman README: Standard Postman Collection (April 2023)
    - SOAP Services: SupplierService4_2, BusinessRelationshipService4_2, etc.
    - REST Services: FileAttributes, BusinessProcess, Reports

Key Concepts:
    - Supplier: Parent entity (Third Party) - contains all other entity types
    - Business Relationship: Custom entity types (Engagement, Contract, Site)
    - Business Process: Workflow instance (due diligence, onboarding)
    - Association: Links between entities (Supplier <-> Contact)
"""

import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable
from xml.etree import ElementTree as ET

import httpx

from lead_to_cash.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class AravoError(Exception):
    """Base exception for all Aravo-related errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AravoAuthError(AravoError):
    """Authentication or authorization error."""

    pass


class AravoConnectionError(AravoError):
    """Connection or network error."""

    pass


class AravoSOAPFault(AravoError):
    """SOAP Fault returned from Aravo API."""

    def __init__(
        self,
        message: str,
        fault_code: str = "",
        fault_string: str = "",
        fault_detail: str = "",
    ):
        super().__init__(
            message,
            {
                "fault_code": fault_code,
                "fault_string": fault_string,
                "fault_detail": fault_detail,
            },
        )
        self.fault_code = fault_code
        self.fault_string = fault_string
        self.fault_detail = fault_detail


class AravoNotFoundError(AravoError):
    """Entity not found in Aravo."""

    pass


class AravoValidationError(AravoError):
    """Validation error for input data."""

    pass


# =============================================================================
# Enums
# =============================================================================


class SupplierStatus(Enum):
    """Aravo supplier/third-party status values."""

    APPROVED = "Approved"
    PENDING = "Pending"
    UNDER_REVIEW = "Under Review"
    REJECTED = "Rejected"
    INACTIVE = "Inactive"


class BusinessProcessStatus(Enum):
    """Aravo business process/workflow status values."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    ON_HOLD = "On Hold"


class TPRMStatus(Enum):
    """TPRM assessment status for KYP integration."""

    NO_ADVERSE_FINDINGS = "NO_ADVERSE_FINDINGS"
    ADVERSE_FINDINGS = "ADVERSE_FINDINGS"
    UNDER_REVIEW = "UNDER_REVIEW"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"


# =============================================================================
# Data Classes - Aravo Entities
# =============================================================================


@dataclass
class AravoSupplier:
    """Aravo Supplier/Third Party entity.

    The Supplier entity is the parent of all other entity types in Aravo.
    """

    supplier_id: str  # Aravo internal ID (sidType)
    identifier: str  # External identifier (customer-defined)
    name: str
    status: str = ""
    supplier_type: str = ""
    country: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state_region: str = ""
    postal_code: str = ""
    doing_business_as: str = ""
    tax_id: str = ""  # Custom field for UEN/Tax Number
    inherent_risk_score: Optional[float] = None
    custom_fields: dict = field(default_factory=dict)
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None


@dataclass
class AravoContact:
    """Aravo Supplier Contact entity."""

    person_id: str  # Aravo internal ID (pidType)
    supplier_id: str
    first_name: str
    last_name: str
    email: str = ""
    phone: str = ""
    title: str = ""
    is_primary: bool = False
    custom_fields: dict = field(default_factory=dict)


@dataclass
class AravoBusinessRelationship:
    """Aravo Business Relationship entity.

    Custom entity types defined in Aravo Data Dictionary (e.g., Engagement, Contract).
    """

    br_id: str  # Business Relationship ID
    supplier_id: str
    br_type: str  # Entity key from Data Dictionary (e.g., "TPMEngagement")
    name: str
    status: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    custom_fields: dict = field(default_factory=dict)


@dataclass
class AravoBusinessProcess:
    """Aravo Business Process (Workflow instance)."""

    bp_id: str  # Business Process ID
    supplier_id: str
    workflow_template_name: str
    status: str = ""
    current_task: str = ""
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    tasks: list = field(default_factory=list)


@dataclass
class AravoQuestionnaire:
    """Aravo Questionnaire/Assessment result."""

    questionnaire_id: str
    name: str
    status: str = ""
    score: Optional[float] = None
    max_score: Optional[float] = None
    completed_date: Optional[datetime] = None
    responses: list = field(default_factory=list)


# =============================================================================
# Data Classes - TPRM/KYP Integration
# =============================================================================


@dataclass
class TPRMSupplierStatus:
    """TPRM status for a supplier, used in KYP integration."""

    supplier_id: str
    aravo_supplier_id: str
    name: str
    identifier: str
    status: TPRMStatus
    supplier_status: str  # Aravo status (Approved, Pending, etc.)
    inherent_risk_score: Optional[float] = None
    active_workflow_count: int = 0
    completed_workflow_count: int = 0
    active_engagements: list = field(default_factory=list)
    questionnaire_scores: dict = field(default_factory=dict)
    last_assessment_date: Optional[datetime] = None
    notes: str = ""


@dataclass
class TPRMDueDiligenceStatus:
    """Due diligence workflow status from Aravo."""

    workflow_name: str
    status: str
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    current_task: str = ""
    completion_percent: float = 0.0


@dataclass
class TPRMAssessment:
    """Complete TPRM assessment for KYP report.

    This is the main data structure returned for KYP TPRM category.
    """

    supplier_id: str
    supplier_name: str
    aravo_supplier_id: str
    aravo_identifier: str

    # Overall TPRM Status
    tprm_status: TPRMStatus
    tprm_notes: str = ""

    # Supplier Status
    supplier_status: str = ""  # Approved, Pending, etc.
    inherent_risk_score: Optional[float] = None
    risk_score_max: float = 100.0

    # Due Diligence Workflows
    due_diligence_workflows: list[TPRMDueDiligenceStatus] = field(default_factory=list)

    # Active Engagements
    active_engagements: list[AravoBusinessRelationship] = field(default_factory=list)

    # Questionnaire/Assessment Scores
    questionnaire_scores: list[AravoQuestionnaire] = field(default_factory=list)

    # Timestamps
    last_assessment_date: Optional[datetime] = None
    data_retrieved_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def overall_risk_score(self) -> Optional[float]:
        """Calculate overall risk score from inherent risk and questionnaire scores."""
        scores = []

        # Add inherent risk score if available
        if self.inherent_risk_score is not None:
            scores.append(self.inherent_risk_score)

        # Add questionnaire scores
        for q in self.questionnaire_scores:
            if q.score is not None and q.max_score:
                normalized_score = (q.score / q.max_score) * 100
                scores.append(normalized_score)

        if not scores:
            return None

        return sum(scores) / len(scores)


# =============================================================================
# Authentication Token
# =============================================================================


@dataclass
class AravoOAuthToken:
    """Aravo OAuth 2.0 token container."""

    access_token: str
    token_type: str
    expires_at: datetime
    scope: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60s buffer)."""
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(seconds=60))


# =============================================================================
# Protocol Definition
# =============================================================================


@runtime_checkable
class AravoClientProtocol(Protocol):
    """Protocol defining the Aravo client interface.

    Both AravoClient and AravoSimulator must implement this protocol
    to ensure API compatibility.
    """

    async def connect(self) -> None:
        """Establish connection and authenticate."""
        ...

    async def disconnect(self) -> None:
        """Close connection."""
        ...

    async def get_supplier(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> Optional[AravoSupplier]:
        """Get supplier by ID."""
        ...

    async def search_suppliers(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        max_results: int = 50,
    ) -> list[AravoSupplier]:
        """Search suppliers by criteria."""
        ...

    async def create_supplier(
        self,
        name: str,
        identifier: str,
        country: str = "",
        supplier_type: str = "",
        custom_fields: Optional[dict] = None,
    ) -> AravoSupplier:
        """Create a new supplier."""
        ...

    async def update_supplier(
        self,
        supplier_id: str,
        updates: dict[str, Any],
        sid_type: str = "internalId",
    ) -> AravoSupplier:
        """Update an existing supplier."""
        ...

    async def get_contacts(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoContact]:
        """Get contacts for a supplier."""
        ...

    async def get_business_process(self, bp_id: str) -> Optional[AravoBusinessProcess]:
        """Get business process details."""
        ...

    async def get_supplier_business_processes(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoBusinessProcess]:
        """Get all business processes for a supplier."""
        ...

    async def start_business_process(
        self,
        supplier_id: str,
        workflow_template_name: str,
        sid_type: str = "internalId",
    ) -> Optional[str]:
        """Start a business process for a supplier."""
        ...

    async def get_business_relationships(
        self,
        supplier_id: str,
        br_type: str,
        sid_type: str = "internalId",
    ) -> list[AravoBusinessRelationship]:
        """Get business relationships for a supplier."""
        ...

    async def get_questionnaires(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoQuestionnaire]:
        """Get questionnaire results for a supplier."""
        ...

    async def get_tprm_assessment(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
        engagement_type: Optional[str] = None,
    ) -> Optional[TPRMAssessment]:
        """Get complete TPRM assessment for KYP integration."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Check connectivity and status."""
        ...


# =============================================================================
# SOAP Envelope Templates
# =============================================================================


class AravoSOAPTemplates:
    """SOAP envelope templates for Aravo API calls."""

    ENVELOPE_NS = "http://schemas.xmlsoap.org/soap/envelope/"
    SUPPLIER_NS = "http://supplier.webservices.aravo.com/"
    CONTACT_NS = "http://suppliercontact.webservices.aravo.com/"
    BR_NS = "http://businessrelationship.webservices.aravo.com/"
    BP_NS = "http://businessprocess.webservices.aravo.com/"
    ASSOC_NS = "http://association.webservices.aravo.com/"

    @staticmethod
    def get_supplier_request(supplier_id: str, sid_type: str = "internalId") -> str:
        """Generate getSuppliers SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:sup="{AravoSOAPTemplates.SUPPLIER_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <sup:getSuppliers>
            <request>
                <sid>{supplier_id}</sid>
                <sidType>{sid_type}</sidType>
            </request>
        </sup:getSuppliers>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def search_suppliers_request(
        field_name: str,
        field_value: str,
        operator: str = "CONTAINS",
    ) -> str:
        """Generate searchSuppliers SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:sup="{AravoSOAPTemplates.SUPPLIER_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <sup:searchSuppliers>
            <request>
                <searchCriteria>
                    <fieldName>{field_name}</fieldName>
                    <operator>{operator}</operator>
                    <value>{field_value}</value>
                </searchCriteria>
            </request>
        </sup:searchSuppliers>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def create_supplier_request(
        name: str,
        identifier: str,
        country: str = "",
        supplier_type: str = "",
        fields: Optional[dict] = None,
    ) -> str:
        """Generate createSuppliers SOAP request."""
        fields_xml = ""
        if fields:
            for field_name, field_value in fields.items():
                # Escape XML special characters
                escaped_value = (
                    str(field_value)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                fields_xml += f"""
                <fields>
                    <name>{field_name}</name>
                    <type>string</type>
                    <values>{escaped_value}</values>
                </fields>"""

        supplier_type_xml = ""
        if supplier_type:
            supplier_type_xml = f"""
                <fields>
                    <name>supplierType</name>
                    <type>code</type>
                    <values>{supplier_type}</values>
                </fields>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:sup="{AravoSOAPTemplates.SUPPLIER_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <sup:createSuppliers>
            <createRequest>
                <fields>
                    <name>name</name>
                    <type>string</type>
                    <values>{name}</values>
                </fields>
                <fields>
                    <name>identifier</name>
                    <type>string</type>
                    <values>{identifier}</values>
                </fields>
                <fields>
                    <name>country</name>
                    <type>code</type>
                    <values>{country}</values>
                </fields>{supplier_type_xml}{fields_xml}
            </createRequest>
        </sup:createSuppliers>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def update_supplier_request(
        supplier_id: str,
        updates: dict[str, Any],
        sid_type: str = "internalId",
    ) -> str:
        """Generate updateSuppliers SOAP request."""
        fields_xml = ""
        for field_name, field_value in updates.items():
            escaped_value = (
                str(field_value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            fields_xml += f"""
                <fields>
                    <name>{field_name}</name>
                    <type>string</type>
                    <values>{escaped_value}</values>
                </fields>"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:sup="{AravoSOAPTemplates.SUPPLIER_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <sup:updateSuppliers>
            <updateRequest>
                <sid>{supplier_id}</sid>
                <sidType>{sid_type}</sidType>{fields_xml}
            </updateRequest>
        </sup:updateSuppliers>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def get_contacts_request(supplier_id: str, sid_type: str = "internalId") -> str:
        """Generate getSupplierContacts SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:con="{AravoSOAPTemplates.CONTACT_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <con:getSupplierContacts>
            <request>
                <sid>{supplier_id}</sid>
                <sidType>{sid_type}</sidType>
            </request>
        </con:getSupplierContacts>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def get_business_process_details_request(bp_id: str) -> str:
        """Generate getBusinessProcessDetails SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:bus="{AravoSOAPTemplates.BP_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <bus:getBusinessProcessDetails>
            <request>
                <bpid>{bp_id}</bpid>
            </request>
        </bus:getBusinessProcessDetails>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def get_supplier_business_processes_request(
        supplier_id: str, sid_type: str = "internalId"
    ) -> str:
        """Generate getSupplierBusinessProcesses SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:bus="{AravoSOAPTemplates.BP_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <bus:getSupplierBusinessProcesses>
            <request>
                <sid>{supplier_id}</sid>
                <sidType>{sid_type}</sidType>
            </request>
        </bus:getSupplierBusinessProcesses>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def start_supplier_business_process_request(
        supplier_id: str,
        workflow_template_name: str,
        sid_type: str = "internalId",
    ) -> str:
        """Generate startSupplierBusinessProcesses SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:bus="{AravoSOAPTemplates.BP_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <bus:startSupplierBusinessProcesses>
            <request>
                <workflowTemplateName>{workflow_template_name}</workflowTemplateName>
                <subject>
                    <sid>{supplier_id}</sid>
                    <sidType>{sid_type}</sidType>
                </subject>
            </request>
        </bus:startSupplierBusinessProcesses>
    </soapenv:Body>
</soapenv:Envelope>"""

    @staticmethod
    def get_business_relationships_request(
        supplier_id: str,
        br_type: str,
        sid_type: str = "internalId",
    ) -> str:
        """Generate getBusinessRelationships SOAP request."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{AravoSOAPTemplates.ENVELOPE_NS}"
                  xmlns:bus="{AravoSOAPTemplates.BR_NS}">
    <soapenv:Header/>
    <soapenv:Body>
        <bus:getBusinessRelationships>
            <request>
                <sid>{supplier_id}</sid>
                <sidType>{sid_type}</sidType>
                <brType>{br_type}</brType>
            </request>
        </bus:getBusinessRelationships>
    </soapenv:Body>
</soapenv:Envelope>"""


# =============================================================================
# Aravo Client
# =============================================================================


class AravoClient:
    """Aravo Third-Party Risk Management Client.

    Provides access to Aravo SOAP/REST APIs for supplier due diligence,
    compliance management, and KYP integration.

    Usage:
        async with AravoClient() as client:
            # Get supplier by ID
            supplier = await client.get_supplier("12345")

            # Search suppliers by name
            suppliers = await client.search_suppliers(name="Acme")

            # Get TPRM assessment for KYP
            assessment = await client.get_tprm_assessment("12345")

    Authentication:
        Supports both OAuth 2.0 and Basic Auth. Configure via environment:
        - OAuth: ARAVO_CLIENT_ID, ARAVO_CLIENT_SECRET, ARAVO_TOKEN_URL
        - Basic: ARAVO_USERNAME, ARAVO_PASSWORD

    Raises:
        AravoError: Base class for all Aravo errors
        AravoAuthError: Authentication failures
        AravoConnectionError: Network/connection issues
        AravoSOAPFault: SOAP fault returned by API
        AravoNotFoundError: Entity not found
        AravoValidationError: Invalid input data
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize Aravo client.

        Args:
            base_url: Aravo base URL (defaults to config)
            client_id: OAuth client ID (defaults to config)
            client_secret: OAuth client secret (defaults to config)
            username: Basic auth username (defaults to config)
            password: Basic auth password (defaults to config)
        """
        self.base_url = base_url or config.aravo.base_url
        self.client_id = client_id or config.aravo.client_id
        self.client_secret = client_secret or config.aravo.client_secret
        self.username = username or config.aravo.username
        self.password = password or config.aravo.password
        self.token_url = config.aravo.token_url
        self.timeout = config.aravo.timeout_seconds
        self.retry_attempts = config.aravo.retry_attempts

        self._token: Optional[AravoOAuthToken] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

        # Internal supplier cache for search (populated on first search)
        self._supplier_cache: dict[str, AravoSupplier] = {}
        self._cache_populated = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connection and authenticate.

        Raises:
            AravoValidationError: If credentials are not configured
            AravoAuthError: If authentication fails
        """
        if not self.base_url:
            raise AravoValidationError(
                "Aravo URL not configured. Set ARAVO_URL environment variable."
            )

        has_oauth = bool(self.client_id and self.client_secret)
        has_basic = bool(self.username and self.password)

        if not has_oauth and not has_basic:
            raise AravoValidationError(
                "Aravo credentials not configured. "
                "Set ARAVO_CLIENT_ID/ARAVO_CLIENT_SECRET or ARAVO_USERNAME/ARAVO_PASSWORD."
            )

        self._client = httpx.AsyncClient(timeout=self.timeout)

        # Prefer OAuth if configured
        if has_oauth and self.token_url:
            await self._refresh_token()

        self._connected = True
        logger.info(f"Connected to Aravo: {self.base_url}")

        # Pre-fetch TPRM report data via REST API (used for supplier search)
        await self._fetch_rest_report()

    async def _fetch_rest_report(self) -> None:
        """Fetch supplier data from Aravo REST v5.0 reports endpoint.

        Populates the supplier cache so search_suppliers can work without SOAP.
        The report ID is configured via ARAVO_REPORT_ID env var.
        """
        report_id = config.aravo.tprm_report_id
        url = f"{self.base_url}{config.aravo.reports_v5_path}/{report_id}"

        import base64

        auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        }

        try:
            resp = await self._client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # Parse report rows into supplier cache
            # Aravo reports return rows with column values
            rows = (
                data
                if isinstance(data, list)
                else data.get("rows", data.get("data", []))
            )
            if isinstance(rows, list):
                for row in rows:
                    supplier = self._parse_rest_supplier(row)
                    if supplier:
                        self._supplier_cache[supplier.supplier_id] = supplier
                        # Also index by name (lowercase) for search
                        self._supplier_cache[f"name:{supplier.name.lower()}"] = supplier
                self._cache_populated = True
                logger.info(
                    f"Aravo REST report: loaded {len(rows)} suppliers from report {report_id}"
                )
            else:
                logger.warning(f"Aravo REST report: unexpected format — {type(data)}")

        except httpx.HTTPStatusError as e:
            logger.warning(f"Aravo REST report failed: {e}")
            raise AravoConnectionError(f"REST API error: {e}")
        except Exception as e:
            logger.warning(f"Aravo REST report error: {e}")
            raise AravoConnectionError(f"REST API error: {e}")

    def _parse_rest_supplier(self, row: Any) -> Optional[AravoSupplier]:
        """Parse a REST report row into an AravoSupplier."""
        try:
            # Aravo REST reports can return data in different formats:
            # - List of dicts with column names as keys
            # - Dict with "columns" and "values" arrays
            if isinstance(row, dict):
                name = (
                    row.get("supplierName")
                    or row.get("name")
                    or row.get("Supplier Name")
                    or row.get("Name")
                    or ""
                )
                supplier_id = str(
                    row.get("supplierId")
                    or row.get("internalId")
                    or row.get("Supplier ID")
                    or row.get("ID")
                    or ""
                )
                status = (
                    row.get("status")
                    or row.get("supplierStatus")
                    or row.get("Status")
                    or "Active"
                )
                risk_score = (
                    row.get("riskScore")
                    or row.get("inherentRiskScore")
                    or row.get("Risk Score")
                )
                country = row.get("country") or row.get("Country") or ""

                if name and supplier_id:
                    return AravoSupplier(
                        supplier_id=supplier_id,
                        name=name,
                        status=status,
                        country=country,
                        inherent_risk_score=int(risk_score) if risk_score else None,
                    )
        except Exception as e:
            logger.debug(f"Failed to parse REST supplier row: {e}")
        return None

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._token = None
        self._connected = False
        self._supplier_cache.clear()
        self._cache_populated = False
        logger.info("Disconnected from Aravo")

    def _ensure_connected(self) -> None:
        """Ensure client is connected.

        Raises:
            AravoConnectionError: If client not connected
        """
        if not self._connected:
            raise AravoConnectionError(
                "Aravo client not connected. "
                "Call connect() first or use async context manager."
            )

    # =========================================================================
    # Authentication
    # =========================================================================

    async def _refresh_token(self) -> None:
        """Refresh OAuth 2.0 access token.

        Raises:
            AravoAuthError: If token refresh fails
        """
        if not self.token_url or not self._client:
            return

        try:
            response = await self._client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

            self._token = AravoOAuthToken(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=data.get("expires_in", 3600)),
                scope=data.get("scope"),
            )
            logger.debug("Aravo OAuth token refreshed")
        except httpx.HTTPStatusError as e:
            raise AravoAuthError(
                f"OAuth token refresh failed: {e.response.status_code}",
                {"status_code": e.response.status_code, "response": e.response.text},
            )
        except Exception as e:
            raise AravoAuthError(f"OAuth token refresh failed: {e}")

    def _get_auth_header(self) -> dict[str, str]:
        """Get authentication header.

        Returns:
            Dict with Authorization header
        """
        if self._token and not self._token.is_expired:
            return {"Authorization": f"Bearer {self._token.access_token}"}
        elif self.username and self.password:
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            return {"Authorization": f"Basic {credentials}"}
        return {}

    # =========================================================================
    # SOAP Request Helpers
    # =========================================================================

    async def _call_soap(
        self,
        service: str,
        soap_body: str,
    ) -> dict[str, Any]:
        """Call Aravo SOAP service.

        Args:
            service: Service name (supplier, contact, business_relationship, etc.)
            soap_body: Complete SOAP envelope XML

        Returns:
            Parsed response as dict

        Raises:
            AravoConnectionError: If client not connected
            AravoSOAPFault: If SOAP fault is returned
            AravoAuthError: If authentication fails
        """
        self._ensure_connected()

        if not self._client:
            raise AravoConnectionError("HTTP client not initialized")

        url = config.aravo.get_service_url(service)
        if not url:
            raise AravoValidationError(f"Service URL not configured for: {service}")

        # Ensure valid token for OAuth
        if self._token and self._token.is_expired:
            await self._refresh_token()

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
            **self._get_auth_header(),
        }

        # Retry logic with exponential backoff
        last_error: Optional[Exception] = None
        for attempt in range(self.retry_attempts):
            try:
                response = await self._client.post(
                    url, content=soap_body, headers=headers
                )
                response.raise_for_status()

                # Parse XML response and check for SOAP faults
                return self._parse_soap_response(response.text)

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code

                if status_code == 401:
                    logger.warning("Aravo auth failed, refreshing token...")
                    try:
                        await self._refresh_token()
                        headers.update(self._get_auth_header())
                        continue
                    except AravoAuthError:
                        raise AravoAuthError(
                            f"Authentication failed after token refresh: {e}",
                            {"status_code": status_code},
                        )

                elif status_code == 403:
                    raise AravoAuthError(
                        f"Access forbidden: {e}", {"status_code": status_code}
                    )

                elif status_code >= 500:
                    # Exponential backoff for server errors
                    import asyncio

                    wait_time = (2**attempt) * 0.5
                    logger.warning(
                        f"Aravo server error (attempt {attempt + 1}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                else:
                    raise AravoError(
                        f"HTTP error: {e}",
                        {"status_code": status_code, "response": e.response.text},
                    )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Aravo request error (attempt {attempt + 1}): {e}")
                continue

        if last_error:
            if isinstance(last_error, httpx.HTTPStatusError):
                raise AravoConnectionError(
                    f"Request failed after {self.retry_attempts} attempts: {last_error}",
                    {"status_code": last_error.response.status_code},
                )
            raise AravoConnectionError(
                f"Request failed after {self.retry_attempts} attempts: {last_error}"
            )
        return {}

    def _parse_soap_response(self, xml_text: str) -> dict[str, Any]:
        """Parse SOAP XML response to dict.

        Args:
            xml_text: Raw XML response

        Returns:
            Parsed response as dict

        Raises:
            AravoSOAPFault: If response contains a SOAP fault
        """
        try:
            root = ET.fromstring(xml_text)

            # Check for SOAP Fault FIRST
            fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
            if fault is not None:
                fault_code = ""
                fault_string = ""
                fault_detail = ""

                # Extract fault components
                fc = fault.find("faultcode")
                if fc is not None and fc.text:
                    fault_code = fc.text
                fs = fault.find("faultstring")
                if fs is not None and fs.text:
                    fault_string = fs.text
                fd = fault.find("detail")
                if fd is not None:
                    fault_detail = ET.tostring(fd, encoding="unicode")

                raise AravoSOAPFault(
                    f"SOAP Fault: {fault_string}",
                    fault_code=fault_code,
                    fault_string=fault_string,
                    fault_detail=fault_detail,
                )

            # Find the Body element
            body = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
            if body is None:
                return {"raw_response": xml_text}

            # Convert first child of Body to dict
            if len(body) > 0:
                return self._element_to_dict(body[0])

            return {}

        except ET.ParseError as e:
            logger.warning(f"Failed to parse Aravo XML response: {e}")
            return {"raw_response": xml_text, "parse_error": str(e)}

    def _element_to_dict(self, element: ET.Element) -> dict[str, Any]:
        """Convert XML element to dictionary.

        Args:
            element: XML Element

        Returns:
            Dictionary representation
        """
        result: dict[str, Any] = {}

        # Get tag name without namespace
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        # Process attributes
        if element.attrib:
            result["@attributes"] = element.attrib

        # Process children
        children = list(element)
        if children:
            child_dict: dict[str, Any] = {}
            for child in children:
                child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                child_value = self._element_to_dict(child)

                # Handle multiple children with same tag
                if child_tag in child_dict:
                    if not isinstance(child_dict[child_tag], list):
                        child_dict[child_tag] = [child_dict[child_tag]]
                    child_dict[child_tag].append(child_value)
                else:
                    child_dict[child_tag] = child_value

            result[tag] = child_dict
        else:
            # Leaf node - just return text
            result[tag] = element.text or ""

        return result

    # =========================================================================
    # REST Request Helpers
    # =========================================================================

    async def _call_rest(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Call Aravo REST service.

        Args:
            service: Service name (reports, file_attributes, business_process_rest)
            endpoint: REST endpoint path (appended to service URL)
            method: HTTP method
            params: Query parameters
            json_body: JSON request body

        Returns:
            JSON response as dict
        """
        self._ensure_connected()

        if not self._client:
            raise AravoConnectionError("HTTP client not initialized")

        base_url = config.aravo.get_service_url(service)
        if not base_url:
            raise AravoValidationError(f"Service URL not configured for: {service}")

        url = f"{base_url}{endpoint}"

        # Ensure valid token
        if self._token and self._token.is_expired:
            await self._refresh_token()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self._get_auth_header(),
        }

        response = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
        )
        response.raise_for_status()

        return response.json() if response.text else {}

    # =========================================================================
    # Supplier Operations
    # =========================================================================

    async def get_supplier(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> Optional[AravoSupplier]:
        """Get supplier by ID.

        Args:
            supplier_id: Aravo supplier ID or external identifier
            sid_type: ID type - "internalId" or "externalId"

        Returns:
            AravoSupplier if found, None otherwise

        Raises:
            AravoSOAPFault: If SOAP error occurs
            AravoConnectionError: If connection fails
        """
        soap_body = AravoSOAPTemplates.get_supplier_request(supplier_id, sid_type)
        result = await self._call_soap("supplier", soap_body)

        # Parse response
        response_data = result.get("getSuppliersResponse", {})
        supplier_data = response_data.get("return", {}).get("supplier", {})

        if not supplier_data:
            return None

        supplier = self._parse_supplier(supplier_data)

        # Cache the supplier for search
        if supplier:
            self._supplier_cache[supplier.supplier_id] = supplier
            if supplier.identifier:
                self._supplier_cache[f"ext:{supplier.identifier}"] = supplier

        return supplier

    async def search_suppliers(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        max_results: int = 50,
    ) -> list[AravoSupplier]:
        """Search suppliers by criteria.

        Searches using Aravo's searchSuppliers SOAP API.
        Results are cached locally for subsequent searches.

        Args:
            name: Supplier name (partial match, case-insensitive)
            identifier: External identifier (exact match)
            country: Country code (exact match)
            tax_id: Tax ID / UEN (exact match)
            max_results: Maximum results to return

        Returns:
            List of matching suppliers

        Raises:
            AravoSOAPFault: If SOAP error occurs
            AravoConnectionError: If connection fails
        """
        self._ensure_connected()

        # If identifier is provided, do direct lookup first
        if identifier:
            supplier = await self.get_supplier(identifier, "externalId")
            if supplier:
                return [supplier]
            return []

        # Build search criteria
        results: list[AravoSupplier] = []

        # Search REST cache first (populated from report endpoint at connect time)
        if name and self._cache_populated:
            _search = name.lower().strip()
            for _key, _cached in self._supplier_cache.items():
                if not isinstance(_cached, AravoSupplier):
                    continue
                _sname = _cached.name.lower()
                if (
                    _search in _sname
                    or _sname in _search
                    or bool(set(_search.split()) & set(_sname.split()))
                ):
                    results.append(_cached)
            if results:
                logger.info(f"Aravo REST cache: found {len(results)} for '{name}'")
                return results[:max_results]

        # Fall back to SOAP API if REST cache has no results
        if name:
            try:
                soap_body = AravoSOAPTemplates.search_suppliers_request(
                    field_name="name",
                    field_value=name,
                    operator="CONTAINS",
                )
                result = await self._call_soap("supplier", soap_body)

                response_data = result.get("searchSuppliersResponse", {})
                suppliers_data = response_data.get("return", [])

                if not isinstance(suppliers_data, list):
                    suppliers_data = [suppliers_data] if suppliers_data else []

                for supplier_data in suppliers_data[:max_results]:
                    if supplier_data:
                        supplier = self._parse_supplier(supplier_data)
                        if supplier:
                            # Apply additional filters
                            if country and supplier.country.upper() != country.upper():
                                continue
                            if tax_id and supplier.tax_id != tax_id:
                                continue
                            results.append(supplier)
                            # Cache the result
                            self._supplier_cache[supplier.supplier_id] = supplier

            except AravoSOAPFault as e:
                # searchSuppliers may not be available in all Aravo versions
                # Fall back to cache-based search
                logger.warning(f"searchSuppliers not available, using cache: {e}")
                return self._search_cache(
                    name=name, country=country, tax_id=tax_id, max_results=max_results
                )

        # If no name provided, search by country or tax_id in cache
        if not name and (country or tax_id):
            return self._search_cache(
                country=country, tax_id=tax_id, max_results=max_results
            )

        return results[:max_results]

    def _search_cache(
        self,
        name: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        max_results: int = 50,
    ) -> list[AravoSupplier]:
        """Search the local supplier cache.

        Args:
            name: Supplier name (partial match)
            country: Country code
            tax_id: Tax ID
            max_results: Maximum results

        Returns:
            List of matching suppliers from cache
        """
        results = []
        seen_ids = set()

        for key, supplier in self._supplier_cache.items():
            # Skip external ID aliases
            if key.startswith("ext:"):
                continue

            if supplier.supplier_id in seen_ids:
                continue

            # Name filter (case-insensitive partial match)
            if name and name.lower() not in supplier.name.lower():
                continue

            # Country filter
            if country and supplier.country.upper() != country.upper():
                continue

            # Tax ID filter
            if tax_id and supplier.tax_id != tax_id:
                continue

            results.append(supplier)
            seen_ids.add(supplier.supplier_id)

            if len(results) >= max_results:
                break

        return results

    async def create_supplier(
        self,
        name: str,
        identifier: str,
        country: str = "",
        supplier_type: str = "",
        custom_fields: Optional[dict] = None,
    ) -> AravoSupplier:
        """Create a new supplier in Aravo.

        Args:
            name: Supplier name
            identifier: External identifier (must be unique)
            country: Country code (e.g., "SG", "US")
            supplier_type: Supplier type from Aravo data dictionary
            custom_fields: Additional custom fields

        Returns:
            Created AravoSupplier

        Raises:
            AravoValidationError: If required fields are missing
            AravoSOAPFault: If creation fails
        """
        if not name:
            raise AravoValidationError("Supplier name is required")
        if not identifier:
            raise AravoValidationError("Supplier identifier is required")

        soap_body = AravoSOAPTemplates.create_supplier_request(
            name=name,
            identifier=identifier,
            country=country,
            supplier_type=supplier_type or config.aravo.default_supplier_type,
            fields=custom_fields,
        )

        result = await self._call_soap("supplier", soap_body)

        response_data = result.get("createSuppliersResponse", {})
        supplier_data = response_data.get("return", {})

        if not supplier_data:
            raise AravoError("Failed to create supplier: No response data")

        # Get the created supplier ID and fetch full details
        supplier_id = supplier_data.get("id", "")
        if supplier_id:
            supplier = await self.get_supplier(supplier_id)
            if supplier:
                return supplier

        # If we can't fetch, return basic supplier from response
        return AravoSupplier(
            supplier_id=supplier_id,
            identifier=identifier,
            name=name,
            country=country,
            supplier_type=supplier_type,
        )

    async def update_supplier(
        self,
        supplier_id: str,
        updates: dict[str, Any],
        sid_type: str = "internalId",
    ) -> AravoSupplier:
        """Update an existing supplier.

        Args:
            supplier_id: Aravo supplier ID
            updates: Dictionary of field updates
            sid_type: ID type

        Returns:
            Updated AravoSupplier

        Raises:
            AravoNotFoundError: If supplier doesn't exist
            AravoSOAPFault: If update fails
        """
        # Verify supplier exists
        existing = await self.get_supplier(supplier_id, sid_type)
        if not existing:
            raise AravoNotFoundError(f"Supplier not found: {supplier_id}")

        soap_body = AravoSOAPTemplates.update_supplier_request(
            supplier_id=supplier_id,
            updates=updates,
            sid_type=sid_type,
        )

        result = await self._call_soap("supplier", soap_body)

        response_data = result.get("updateSuppliersResponse", {})
        if not response_data.get("return"):
            raise AravoError("Failed to update supplier: No response data")

        # Fetch updated supplier
        updated = await self.get_supplier(supplier_id, sid_type)
        if updated:
            return updated

        # Return existing with updates applied as fallback
        for key, value in updates.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
            else:
                existing.custom_fields[key] = value
        return existing

    def _parse_supplier(self, data: dict[str, Any]) -> AravoSupplier:
        """Parse supplier data from Aravo response.

        Args:
            data: Supplier data dict from SOAP response

        Returns:
            AravoSupplier object
        """
        # Extract nested values
        fields = data.get("fields", {})
        if isinstance(fields, list):
            fields = {f.get("name", ""): f.get("values", "") for f in fields}

        return AravoSupplier(
            supplier_id=data.get("id", ""),
            identifier=fields.get("identifier", ""),
            name=fields.get("name", ""),
            status=fields.get("status", ""),
            supplier_type=fields.get("supplierType", ""),
            country=fields.get("country", ""),
            address_line_1=fields.get("addressLine1", ""),
            address_line_2=fields.get("addressLine2", ""),
            city=fields.get("city", ""),
            state_region=fields.get("stateRegion", ""),
            postal_code=fields.get("postalCode", ""),
            doing_business_as=fields.get("doingBusinessAs", ""),
            tax_id=fields.get("taxId", fields.get("stcd1", "")),
            inherent_risk_score=self._parse_float(fields.get("totalInherentRiskScore")),
            custom_fields=fields,
        )

    # =========================================================================
    # Contact Operations
    # =========================================================================

    async def get_contacts(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoContact]:
        """Get contacts for a supplier.

        Args:
            supplier_id: Aravo supplier ID
            sid_type: ID type

        Returns:
            List of AravoContact objects
        """
        soap_body = AravoSOAPTemplates.get_contacts_request(supplier_id, sid_type)
        result = await self._call_soap("contact", soap_body)

        response_data = result.get("getSupplierContactsResponse", {})
        contacts_data = response_data.get("return", [])

        if not isinstance(contacts_data, list):
            contacts_data = [contacts_data] if contacts_data else []

        return [self._parse_contact(c, supplier_id) for c in contacts_data if c]

    def _parse_contact(self, data: dict[str, Any], supplier_id: str) -> AravoContact:
        """Parse contact data from Aravo response."""
        fields = data.get("fields", {})
        if isinstance(fields, list):
            fields = {f.get("name", ""): f.get("values", "") for f in fields}

        return AravoContact(
            person_id=data.get("id", ""),
            supplier_id=supplier_id,
            first_name=fields.get("firstName", ""),
            last_name=fields.get("lastName", ""),
            email=fields.get("email", ""),
            phone=fields.get("phone", ""),
            title=fields.get("title", ""),
            is_primary=fields.get("isPrimary", "").lower() == "true",
            custom_fields=fields,
        )

    # =========================================================================
    # Business Process Operations
    # =========================================================================

    async def get_business_process(self, bp_id: str) -> Optional[AravoBusinessProcess]:
        """Get business process details.

        Args:
            bp_id: Business Process ID

        Returns:
            AravoBusinessProcess if found
        """
        soap_body = AravoSOAPTemplates.get_business_process_details_request(bp_id)
        result = await self._call_soap("business_process", soap_body)

        response_data = result.get("getBusinessProcessDetailsResponse", {})
        bp_data = response_data.get("return", {})

        if not bp_data:
            return None

        return self._parse_business_process(bp_data)

    async def get_supplier_business_processes(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoBusinessProcess]:
        """Get all business processes for a supplier.

        Args:
            supplier_id: Aravo supplier ID
            sid_type: ID type

        Returns:
            List of AravoBusinessProcess objects
        """
        soap_body = AravoSOAPTemplates.get_supplier_business_processes_request(
            supplier_id, sid_type
        )
        result = await self._call_soap("business_process", soap_body)

        response_data = result.get("getSupplierBusinessProcessesResponse", {})
        bp_list = response_data.get("return", [])

        if not isinstance(bp_list, list):
            bp_list = [bp_list] if bp_list else []

        return [self._parse_business_process(bp) for bp in bp_list if bp]

    def _parse_business_process(self, data: dict[str, Any]) -> AravoBusinessProcess:
        """Parse business process data."""
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = [tasks] if tasks else []

        return AravoBusinessProcess(
            bp_id=data.get("bpid", data.get("id", "")),
            supplier_id=data.get("supplierId", ""),
            workflow_template_name=data.get("workflowTemplateName", ""),
            status=data.get("status", ""),
            current_task=data.get("currentTask", ""),
            started_date=self._parse_datetime(data.get("startedDate")),
            completed_date=self._parse_datetime(data.get("completedDate")),
            tasks=tasks,
        )

    async def start_business_process(
        self,
        supplier_id: str,
        workflow_template_name: str,
        sid_type: str = "internalId",
    ) -> Optional[str]:
        """Start a business process for a supplier.

        Args:
            supplier_id: Supplier ID
            workflow_template_name: Workflow template name
            sid_type: Supplier ID type

        Returns:
            Business Process ID if successful
        """
        soap_body = AravoSOAPTemplates.start_supplier_business_process_request(
            supplier_id, workflow_template_name, sid_type
        )
        result = await self._call_soap("business_process", soap_body)

        response_data = result.get("startSupplierBusinessProcessesResponse", {})
        return response_data.get("return", {}).get("bpid")

    # =========================================================================
    # Business Relationship Operations
    # =========================================================================

    async def get_business_relationships(
        self,
        supplier_id: str,
        br_type: str,
        sid_type: str = "internalId",
    ) -> list[AravoBusinessRelationship]:
        """Get business relationships for a supplier.

        Args:
            supplier_id: Supplier ID
            br_type: Business Relationship type key (from Data Dictionary)
            sid_type: Supplier ID type

        Returns:
            List of business relationships
        """
        soap_body = AravoSOAPTemplates.get_business_relationships_request(
            supplier_id, br_type, sid_type
        )
        result = await self._call_soap("business_relationship", soap_body)

        response_data = result.get("getBusinessRelationshipsResponse", {})
        br_list = response_data.get("return", [])

        if not isinstance(br_list, list):
            br_list = [br_list] if br_list else []

        return [self._parse_business_relationship(br) for br in br_list if br]

    def _parse_business_relationship(
        self, data: dict[str, Any]
    ) -> AravoBusinessRelationship:
        """Parse business relationship data."""
        fields = data.get("fields", {})
        if isinstance(fields, list):
            fields = {f.get("name", ""): f.get("values", "") for f in fields}

        return AravoBusinessRelationship(
            br_id=data.get("id", ""),
            supplier_id=data.get("supplierId", ""),
            br_type=data.get("brType", ""),
            name=fields.get("name", ""),
            status=fields.get("status", ""),
            start_date=self._parse_datetime(fields.get("startDate")),
            end_date=self._parse_datetime(fields.get("endDate")),
            custom_fields=fields,
        )

    # =========================================================================
    # Questionnaire Operations
    # =========================================================================

    async def get_questionnaires(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoQuestionnaire]:
        """Get questionnaire results for a supplier.

        Uses the Reports REST API to retrieve questionnaire data.

        Args:
            supplier_id: Aravo supplier ID
            sid_type: ID type

        Returns:
            List of AravoQuestionnaire objects
        """
        try:
            # Try to get questionnaires via business process data
            # Questionnaires are typically attached to business processes
            processes = await self.get_supplier_business_processes(
                supplier_id, sid_type
            )

            questionnaires = []
            for process in processes:
                # Extract questionnaire data from process tasks
                for task in process.tasks:
                    if isinstance(task, dict) and task.get("type") == "questionnaire":
                        q = AravoQuestionnaire(
                            questionnaire_id=task.get("id", ""),
                            name=task.get("name", ""),
                            status=task.get("status", ""),
                            score=self._parse_float(task.get("score")),
                            max_score=self._parse_float(task.get("maxScore", 100)),
                            completed_date=self._parse_datetime(
                                task.get("completedDate")
                            ),
                        )
                        questionnaires.append(q)

            return questionnaires

        except AravoSOAPFault:
            # Questionnaire API may not be available
            logger.debug(
                f"Could not retrieve questionnaires for supplier {supplier_id}"
            )
            return []

    # =========================================================================
    # Reports Operations (REST)
    # =========================================================================

    async def get_reports(self) -> list[dict[str, Any]]:
        """Get list of available reports.

        Returns:
            List of report metadata
        """
        result = await self._call_rest("reports", "/reports")
        return result.get("reports", [])

    async def get_report_data(self, report_id: str) -> dict[str, Any]:
        """Get report data by ID.

        Args:
            report_id: Report ID

        Returns:
            Report data
        """
        return await self._call_rest("reports", f"/reports/{report_id}")

    # =========================================================================
    # TPRM / KYP Integration
    # =========================================================================

    async def get_tprm_assessment(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
        engagement_type: Optional[str] = None,
    ) -> Optional[TPRMAssessment]:
        """Get complete TPRM assessment for KYP integration.

        This retrieves:
        - Supplier status and risk score
        - Active due diligence workflows
        - Active engagements
        - Questionnaire scores

        Args:
            supplier_id: Aravo supplier ID or external identifier
            sid_type: ID type ("internalId" or "externalId")
            engagement_type: Business relationship type for engagements

        Returns:
            TPRMAssessment for KYP report, or None if supplier not found
        """
        # Get supplier details
        supplier = await self.get_supplier(supplier_id, sid_type)
        if not supplier:
            return None

        # Determine TPRM status based on supplier status
        tprm_status = self._determine_tprm_status(supplier)

        # Get active engagements
        eng_type = engagement_type or config.aravo.default_engagement_type
        try:
            engagements = await self.get_business_relationships(
                supplier.supplier_id, eng_type
            )
            # Filter active engagements
            active_engagements = [
                e for e in engagements if e.status.lower() in ("active", "in progress")
            ]
        except AravoSOAPFault:
            active_engagements = []

        # Get due diligence workflows
        try:
            processes = await self.get_supplier_business_processes(supplier.supplier_id)
            due_diligence_workflows = [
                TPRMDueDiligenceStatus(
                    workflow_name=p.workflow_template_name,
                    status=p.status,
                    started_date=p.started_date,
                    completed_date=p.completed_date,
                    current_task=p.current_task,
                    completion_percent=self._calculate_completion_percent(p),
                )
                for p in processes
            ]
        except AravoSOAPFault:
            due_diligence_workflows = []

        # Get questionnaire scores
        try:
            questionnaires = await self.get_questionnaires(supplier.supplier_id)
        except AravoSOAPFault:
            questionnaires = []

        # Build assessment
        return TPRMAssessment(
            supplier_id=supplier_id,
            supplier_name=supplier.name,
            aravo_supplier_id=supplier.supplier_id,
            aravo_identifier=supplier.identifier,
            tprm_status=tprm_status,
            tprm_notes=self._get_tprm_notes(supplier, tprm_status),
            supplier_status=supplier.status,
            inherent_risk_score=supplier.inherent_risk_score,
            due_diligence_workflows=due_diligence_workflows,
            active_engagements=active_engagements,
            questionnaire_scores=questionnaires,
            last_assessment_date=supplier.modified_date,
        )

    def _calculate_completion_percent(self, process: AravoBusinessProcess) -> float:
        """Calculate workflow completion percentage."""
        if process.status.lower() == "completed":
            return 100.0
        if process.status.lower() == "not started":
            return 0.0

        # Estimate based on tasks if available
        if process.tasks:
            completed = sum(
                1
                for t in process.tasks
                if isinstance(t, dict) and t.get("status", "").lower() == "completed"
            )
            return (completed / len(process.tasks)) * 100

        # Default for in-progress
        return 50.0

    def _determine_tprm_status(self, supplier: AravoSupplier) -> TPRMStatus:
        """Determine TPRM status from supplier data.

        Args:
            supplier: Aravo supplier

        Returns:
            TPRMStatus enum value
        """
        status_lower = supplier.status.lower() if supplier.status else ""

        if status_lower in ("approved", "active"):
            return TPRMStatus.NO_ADVERSE_FINDINGS
        elif status_lower in ("rejected", "blocked", "terminated"):
            return TPRMStatus.ADVERSE_FINDINGS
        elif status_lower in ("pending", "under review", "in progress"):
            return TPRMStatus.UNDER_REVIEW
        else:
            return TPRMStatus.UNABLE_TO_VERIFY

    def _get_tprm_notes(self, supplier: AravoSupplier, status: TPRMStatus) -> str:
        """Generate TPRM notes for KYP report.

        Args:
            supplier: Aravo supplier
            status: TPRM status

        Returns:
            Notes string
        """
        notes = []

        if status == TPRMStatus.NO_ADVERSE_FINDINGS:
            notes.append(f"Supplier status: {supplier.status}")
            if supplier.inherent_risk_score is not None:
                notes.append(f"Risk score: {supplier.inherent_risk_score}/100")
        elif status == TPRMStatus.ADVERSE_FINDINGS:
            notes.append(f"Supplier status: {supplier.status}")
            notes.append("Review required before engagement")
        elif status == TPRMStatus.UNDER_REVIEW:
            notes.append(f"Due diligence in progress (Status: {supplier.status})")
        else:
            notes.append("Unable to verify TPRM status")

        return "; ".join(notes)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_float(self, value: Any) -> Optional[float]:
        """Safely parse a value to float.

        Args:
            value: Value to parse

        Returns:
            Float value or None if parsing fails
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Safely parse a datetime value.

        Args:
            value: Value to parse (ISO format string or timestamp)

        Returns:
            datetime or None if parsing fails
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            # Try ISO format
            if isinstance(value, str):
                # Handle various formats
                value = value.replace("Z", "+00:00")
                return datetime.fromisoformat(value)
            # Try timestamp
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, TypeError):
            pass
        return None

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check Aravo connectivity."""
        return {
            "status": "connected" if self._connected else "disconnected",
            "base_url": self.base_url,
            "auth_type": "oauth" if self._token else "basic",
            "token_valid": (
                self._token is not None and not self._token.is_expired
                if self._token
                else None
            ),
            "configured": config.aravo.is_configured(),
            "cached_suppliers": len(self._supplier_cache),
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "AravoClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
