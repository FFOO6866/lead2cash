"""
Aravo Simulator for Development and Testing

Simulates Aravo TPRM API responses for development and testing purposes.
This is a drop-in replacement for AravoClient when Aravo is not available.

Usage:
    from lead_to_cash.integrations.aravo_simulator import AravoSimulator

    # Use as drop-in replacement for AravoClient
    async with AravoSimulator() as client:
        supplier = await client.get_supplier("ARAVO-001")
        assessment = await client.get_tprm_assessment("ARAVO-001")

Behavioral Consistency:
    This simulator implements the same AravoClientProtocol as AravoClient,
    ensuring identical API behavior for testing purposes.
"""

import logging
import uuid
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from lead_to_cash.integrations.aravo_client import (
    AravoBusinessProcess,
    AravoBusinessRelationship,
    AravoClientProtocol,
    AravoContact,
    AravoError,
    AravoNotFoundError,
    AravoQuestionnaire,
    AravoSupplier,
    AravoValidationError,
    SupplierStatus,
    TPRMAssessment,
    TPRMDueDiligenceStatus,
    TPRMStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Mock Data
# =============================================================================


@dataclass
class MockAravoSupplier:
    """Mock supplier data for simulation."""

    supplier_id: str
    identifier: str
    name: str
    status: str
    country: str = "SG"
    city: str = "Singapore"
    tax_id: str = ""  # UEN
    inherent_risk_score: float = 75.0
    supplier_type: str = "Supplier"

    def to_aravo_supplier(self) -> AravoSupplier:
        """Convert to AravoSupplier."""
        return AravoSupplier(
            supplier_id=self.supplier_id,
            identifier=self.identifier,
            name=self.name,
            status=self.status,
            supplier_type=self.supplier_type,
            country=self.country,
            city=self.city,
            tax_id=self.tax_id,
            inherent_risk_score=self.inherent_risk_score,
        )


# Pre-defined mock suppliers matching SAP customers in CPI simulator
MOCK_SUPPLIERS: dict[str, MockAravoSupplier] = {
    # Batam Fast Ferry - same as SAP customer 0000100001
    "ARAVO-001": MockAravoSupplier(
        supplier_id="ARAVO-001",
        identifier="BATAMFAST-SG",
        name="Batam Fast Ferry Pte Ltd",
        status=SupplierStatus.APPROVED.value,
        country="SG",
        city="Singapore",
        tax_id="199901234A",
        inherent_risk_score=82.0,
    ),
    # ST Engineering - same as SAP customer 0022005992
    "ARAVO-002": MockAravoSupplier(
        supplier_id="ARAVO-002",
        identifier="STENGG-SG",
        name="ST Engineering Ltd",
        status=SupplierStatus.APPROVED.value,
        country="SG",
        city="Singapore",
        tax_id="199706231H",
        inherent_risk_score=95.0,
    ),
    # Maersk - same as SAP customer 0000100002
    "ARAVO-003": MockAravoSupplier(
        supplier_id="ARAVO-003",
        identifier="MAERSK-DK",
        name="Maersk A/S",
        status=SupplierStatus.APPROVED.value,
        country="DK",
        city="Copenhagen",
        tax_id="25505933",
        inherent_risk_score=98.0,
    ),
    # Neptune Energy - same as SAP customer 0000100003
    "ARAVO-004": MockAravoSupplier(
        supplier_id="ARAVO-004",
        identifier="NEPTUNE-EU",
        name="Neptune Energy Group Holdings Ltd",
        status=SupplierStatus.PENDING.value,
        country="NL",
        city="Amsterdam",
        tax_id="",
        inherent_risk_score=70.0,
    ),
    # Blocked Marine - same as SAP customer 0000100004
    "ARAVO-005": MockAravoSupplier(
        supplier_id="ARAVO-005",
        identifier="BLOCKED-US",
        name="Blocked Marine Services Inc",
        status=SupplierStatus.REJECTED.value,
        country="US",
        city="Houston",
        tax_id="",
        inherent_risk_score=25.0,
    ),
    # Pacific Maritime - same as SAP customer 0000100005
    "ARAVO-006": MockAravoSupplier(
        supplier_id="ARAVO-006",
        identifier="PACIFIC-AU",
        name="Pacific Maritime Group Pty Ltd",
        status=SupplierStatus.UNDER_REVIEW.value,
        country="AU",
        city="Sydney",
        tax_id="",
        inherent_risk_score=65.0,
    ),
    # CLLS Power System - same as SAP customer 0021000090
    "ARAVO-007": MockAravoSupplier(
        supplier_id="ARAVO-007",
        identifier="CLLS-EU",
        name="CLLS Power System GmbH",
        status=SupplierStatus.APPROVED.value,
        country="DE",
        city="Munich",
        tax_id="DE123456789",
        inherent_risk_score=88.0,
    ),
}

# Lookup by identifier
MOCK_SUPPLIERS_BY_IDENTIFIER: dict[str, MockAravoSupplier] = {
    s.identifier: s for s in MOCK_SUPPLIERS.values()
}

# Lookup by name (lowercase for case-insensitive search)
MOCK_SUPPLIERS_BY_NAME: dict[str, MockAravoSupplier] = {
    s.name.lower(): s for s in MOCK_SUPPLIERS.values()
}

# Name aliases for fuzzy matching (maps alias to supplier_id)
SUPPLIER_NAME_ALIASES: dict[str, str] = {
    # ST Engineering aliases
    "st engineering": "ARAVO-002",
    "stengg": "ARAVO-002",
    "singapore technologies": "ARAVO-002",
    "singapore technologies engineering": "ARAVO-002",
    "singapore tech": "ARAVO-002",
    # Batam Fast aliases
    "batam fast": "ARAVO-001",
    "batamfast": "ARAVO-001",
    # Maersk aliases
    "maersk": "ARAVO-003",
    "ap moller": "ARAVO-003",
    "ap moller maersk": "ARAVO-003",
    # Neptune aliases
    "neptune": "ARAVO-004",
    "neptune energy": "ARAVO-004",
    # CLLS aliases
    "clls": "ARAVO-007",
    "clls power": "ARAVO-007",
}

# Lookup by UEN/Tax ID
MOCK_SUPPLIERS_BY_UEN: dict[str, MockAravoSupplier] = {
    s.tax_id: s for s in MOCK_SUPPLIERS.values() if s.tax_id
}


# =============================================================================
# Simulated Sanctions Database
# =============================================================================

# Simulated sanctions data for KYP screening
# Maps normalized entity names to sanctions findings
SIMULATED_SANCTIONS: dict[str, dict[str, Any]] = {
    # Blocked Marine Services - matches SAP customer 0000100004
    "blocked_marine": {
        "status": "BLOCKED",
        "list": "OFAC SDN",
        "reason": "Subject to US Treasury OFAC sanctions",
        "date_added": "2023-01-15",
        "program": "SDGT",
    },
    "blocked_marine_services": {
        "status": "BLOCKED",
        "list": "OFAC SDN",
        "reason": "Subject to US Treasury OFAC sanctions",
        "date_added": "2023-01-15",
        "program": "SDGT",
    },
    "blocked_marine_services_inc": {
        "status": "BLOCKED",
        "list": "OFAC SDN",
        "reason": "Subject to US Treasury OFAC sanctions",
        "date_added": "2023-01-15",
        "program": "SDGT",
    },
    # Test entries for unit testing
    "test_sanctioned": {
        "status": "BLOCKED",
        "list": "EU Consolidated",
        "reason": "Subject to EU restrictive measures",
        "date_added": "2024-03-20",
        "program": "EU-RUSSIA",
    },
    "sanctioned_entity_test": {
        "status": "BLOCKED",
        "list": "UN Security Council",
        "reason": "Subject to UN sanctions regime",
        "date_added": "2022-06-01",
        "program": "UNSC-1718",
    },
}

# Sanctions lists checked in screening
SANCTIONS_LISTS_CHECKED = [
    "OFAC SDN",
    "OFAC Consolidated",
    "EU Consolidated",
    "UN Security Council",
    "MAS Singapore",
    "UK HMT",
]

# Mock contacts
MOCK_CONTACTS: dict[str, list[AravoContact]] = {
    "ARAVO-001": [
        AravoContact(
            person_id="CON-001",
            supplier_id="ARAVO-001",
            first_name="John",
            last_name="Tan",
            email="john.tan@batamfast.sg",
            phone="+65-6234-5678",
            title="Procurement Manager",
            is_primary=True,
        ),
    ],
    "ARAVO-002": [
        AravoContact(
            person_id="CON-002",
            supplier_id="ARAVO-002",
            first_name="Sarah",
            last_name="Lee",
            email="sarah.lee@stengg.com",
            phone="+65-6765-4321",
            title="Vendor Relations",
            is_primary=True,
        ),
        AravoContact(
            person_id="CON-003",
            supplier_id="ARAVO-002",
            first_name="Michael",
            last_name="Wong",
            email="michael.wong@stengg.com",
            phone="+65-6765-4322",
            title="Finance Manager",
            is_primary=False,
        ),
    ],
    "ARAVO-003": [
        AravoContact(
            person_id="CON-004",
            supplier_id="ARAVO-003",
            first_name="Lars",
            last_name="Nielsen",
            email="lars.nielsen@maersk.com",
            phone="+45-3363-3363",
            title="Supplier Compliance",
            is_primary=True,
        ),
    ],
}

# Mock engagements
MOCK_ENGAGEMENTS: dict[str, list[AravoBusinessRelationship]] = {
    "ARAVO-001": [
        AravoBusinessRelationship(
            br_id="ENG-001",
            supplier_id="ARAVO-001",
            br_type="TPMEngagement",
            name="Engine Maintenance Contract 2024",
            status="Active",
        ),
    ],
    "ARAVO-002": [
        AravoBusinessRelationship(
            br_id="ENG-002",
            supplier_id="ARAVO-002",
            br_type="TPMEngagement",
            name="Marine Systems Integration",
            status="Active",
        ),
        AravoBusinessRelationship(
            br_id="ENG-003",
            supplier_id="ARAVO-002",
            br_type="TPMEngagement",
            name="Training Services Agreement",
            status="Active",
        ),
    ],
    "ARAVO-003": [
        AravoBusinessRelationship(
            br_id="ENG-004",
            supplier_id="ARAVO-003",
            br_type="TPMEngagement",
            name="Container Vessel Fleet Contract",
            status="Active",
        ),
    ],
}

# Mock questionnaire scores
MOCK_QUESTIONNAIRES: dict[str, list[AravoQuestionnaire]] = {
    "ARAVO-001": [
        AravoQuestionnaire(
            questionnaire_id="Q-001",
            name="Anti-Bribery Assessment",
            status="Complete",
            score=88.0,
            max_score=100.0,
        ),
        AravoQuestionnaire(
            questionnaire_id="Q-002",
            name="Data Privacy Assessment",
            status="Complete",
            score=92.0,
            max_score=100.0,
        ),
    ],
    "ARAVO-002": [
        AravoQuestionnaire(
            questionnaire_id="Q-003",
            name="Anti-Bribery Assessment",
            status="Complete",
            score=95.0,
            max_score=100.0,
        ),
        AravoQuestionnaire(
            questionnaire_id="Q-004",
            name="Data Privacy Assessment",
            status="Complete",
            score=98.0,
            max_score=100.0,
        ),
        AravoQuestionnaire(
            questionnaire_id="Q-005",
            name="ESG Assessment",
            status="Complete",
            score=90.0,
            max_score=100.0,
        ),
    ],
    "ARAVO-003": [
        AravoQuestionnaire(
            questionnaire_id="Q-006",
            name="Anti-Bribery Assessment",
            status="Complete",
            score=99.0,
            max_score=100.0,
        ),
    ],
}

# Mock due diligence workflows (business processes)
MOCK_BUSINESS_PROCESSES: dict[str, list[AravoBusinessProcess]] = {
    "ARAVO-001": [
        AravoBusinessProcess(
            bp_id="BP-001",
            supplier_id="ARAVO-001",
            workflow_template_name="InitialOnboarding",
            status="Completed",
            completed_date=datetime(2023, 6, 15, tzinfo=timezone.utc),
            tasks=[
                {
                    "id": "T1",
                    "name": "KYC Check",
                    "status": "Completed",
                    "type": "task",
                },
                {
                    "id": "T2",
                    "name": "Anti-Bribery Assessment",
                    "status": "Completed",
                    "type": "questionnaire",
                    "score": 88.0,
                    "maxScore": 100.0,
                },
            ],
        ),
        AravoBusinessProcess(
            bp_id="BP-002",
            supplier_id="ARAVO-001",
            workflow_template_name="AnnualReScreening",
            status="Completed",
            started_date=datetime(2024, 1, 5, tzinfo=timezone.utc),
            completed_date=datetime(2024, 1, 10, tzinfo=timezone.utc),
            tasks=[
                {
                    "id": "T3",
                    "name": "Re-screening Review",
                    "status": "Completed",
                    "type": "task",
                },
            ],
        ),
    ],
    "ARAVO-002": [
        AravoBusinessProcess(
            bp_id="BP-003",
            supplier_id="ARAVO-002",
            workflow_template_name="InitialOnboarding",
            status="Completed",
            completed_date=datetime(2022, 3, 20, tzinfo=timezone.utc),
            tasks=[
                {
                    "id": "T4",
                    "name": "KYC Check",
                    "status": "Completed",
                    "type": "task",
                },
                {
                    "id": "T5",
                    "name": "Anti-Bribery Assessment",
                    "status": "Completed",
                    "type": "questionnaire",
                    "score": 95.0,
                    "maxScore": 100.0,
                },
            ],
        ),
        AravoBusinessProcess(
            bp_id="BP-004",
            supplier_id="ARAVO-002",
            workflow_template_name="AnnualReScreening",
            status="Completed",
            completed_date=datetime(2024, 1, 5, tzinfo=timezone.utc),
            tasks=[],
        ),
    ],
    "ARAVO-004": [
        AravoBusinessProcess(
            bp_id="BP-005",
            supplier_id="ARAVO-004",
            workflow_template_name="InitialOnboarding",
            status="In Progress",
            started_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            current_task="Compliance Review",
            tasks=[
                {
                    "id": "T6",
                    "name": "KYC Check",
                    "status": "Completed",
                    "type": "task",
                },
                {
                    "id": "T7",
                    "name": "Compliance Review",
                    "status": "In Progress",
                    "type": "task",
                },
                {
                    "id": "T8",
                    "name": "Final Approval",
                    "status": "Not Started",
                    "type": "task",
                },
            ],
        ),
    ],
    "ARAVO-006": [
        AravoBusinessProcess(
            bp_id="BP-006",
            supplier_id="ARAVO-006",
            workflow_template_name="InitialOnboarding",
            status="In Progress",
            started_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
            current_task="Financial Assessment",
            tasks=[
                {
                    "id": "T9",
                    "name": "Financial Assessment",
                    "status": "In Progress",
                    "type": "task",
                },
                {
                    "id": "T10",
                    "name": "Risk Review",
                    "status": "Not Started",
                    "type": "task",
                },
            ],
        ),
    ],
}


# =============================================================================
# Aravo Simulator
# =============================================================================


class AravoSimulator:
    """Simulates Aravo TPRM API responses for development and testing.

    This simulator is designed to be a drop-in replacement for AravoClient
    when Aravo is not available (development, testing, demos).

    Implements AravoClientProtocol to ensure API compatibility with AravoClient.

    Usage:
        async with AravoSimulator() as client:
            supplier = await client.get_supplier("ARAVO-001")
            assessment = await client.get_tprm_assessment("ARAVO-001")
    """

    def __init__(self):
        """Initialize simulator.

        In production, the simulator is only blocked when real Aravo credentials
        are configured (to prevent accidental use of mock data when the real
        backend is available). When no real credentials exist, the simulator runs
        as a fallback so KYP reports still include TPRM data.
        """
        if os.getenv("ENVIRONMENT", "").strip().lower() == "production":
            has_real_aravo = bool(
                os.getenv("ARAVO_URL", "").strip()
                and os.getenv("ARAVO_CLIENT_ID", "").strip()
                and os.getenv("ARAVO_CLIENT_SECRET", "").strip()
            )
            if has_real_aravo:
                raise RuntimeError(
                    "AravoSimulator MUST NOT be instantiated in production when "
                    "real Aravo credentials are configured. Use AravoClient instead."
                )
            logger.warning(
                "AravoSimulator running in production (no Aravo credentials configured). "
                "Data is simulated — configure ARAVO_URL, ARAVO_CLIENT_ID, and "
                "ARAVO_CLIENT_SECRET for real Aravo TPRM connectivity."
            )
        self._connected = False
        # Mutable copy of suppliers for create/update operations
        self._suppliers: dict[str, MockAravoSupplier] = dict(MOCK_SUPPLIERS)
        self._next_supplier_id = len(MOCK_SUPPLIERS) + 1
        logger.info("AravoSimulator initialized (mock mode)")

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish simulated connection."""
        self._connected = True
        logger.info("AravoSimulator connected (mock mode)")

    async def disconnect(self) -> None:
        """Close simulated connection."""
        self._connected = False
        logger.info("AravoSimulator disconnected")

    def _ensure_connected(self) -> None:
        """Ensure simulator is connected."""
        if not self._connected:
            raise AravoError(
                "AravoSimulator not connected. "
                "Call connect() first or use async context manager."
            )

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
        """
        self._ensure_connected()

        # Find supplier
        mock_supplier = None
        if sid_type == "externalId":
            mock_supplier = MOCK_SUPPLIERS_BY_IDENTIFIER.get(supplier_id)
        else:
            mock_supplier = self._suppliers.get(supplier_id)

        if not mock_supplier:
            # Try name-based lookup as fallback
            mock_supplier = MOCK_SUPPLIERS_BY_NAME.get(supplier_id.lower())

        if mock_supplier:
            logger.debug(f"AravoSimulator: Found supplier {mock_supplier.name}")
            return mock_supplier.to_aravo_supplier()

        logger.debug(f"AravoSimulator: Supplier not found: {supplier_id}")
        return None

    async def search_suppliers(
        self,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        country: Optional[str] = None,
        tax_id: Optional[str] = None,
        max_results: int = 50,
    ) -> list[AravoSupplier]:
        """Search suppliers by criteria.

        Args:
            name: Supplier name (partial match)
            identifier: External identifier
            country: Country code
            tax_id: Tax ID / UEN
            max_results: Maximum results to return

        Returns:
            List of matching suppliers
        """
        self._ensure_connected()

        # If identifier is provided, do exact lookup
        if identifier:
            mock_supplier = MOCK_SUPPLIERS_BY_IDENTIFIER.get(identifier)
            if mock_supplier:
                return [mock_supplier.to_aravo_supplier()]
            return []

        results = []
        name_lower = name.lower() if name else ""

        # First, check name aliases for exact or partial match
        if name_lower:
            for alias, supplier_id in SUPPLIER_NAME_ALIASES.items():
                if alias in name_lower or name_lower in alias:
                    mock_supplier = self._suppliers.get(supplier_id)
                    if mock_supplier:
                        results.append(mock_supplier.to_aravo_supplier())
                        logger.debug(
                            f"AravoSimulator: Alias match '{alias}' -> {supplier_id}"
                        )
                        return results  # Return on first alias match

        for mock_supplier in self._suppliers.values():
            # Name filter (case-insensitive partial match)
            if name_lower and name_lower not in mock_supplier.name.lower():
                continue

            # Country filter
            if country and country.upper() != mock_supplier.country.upper():
                continue

            # Tax ID filter
            if tax_id and tax_id != mock_supplier.tax_id:
                continue

            results.append(mock_supplier.to_aravo_supplier())

            if len(results) >= max_results:
                break

        logger.debug(f"AravoSimulator: Search returned {len(results)} suppliers")
        return results

    async def create_supplier(
        self,
        name: str,
        identifier: str,
        country: str = "",
        supplier_type: str = "",
        custom_fields: Optional[dict] = None,
    ) -> AravoSupplier:
        """Create a new supplier.

        Args:
            name: Supplier name
            identifier: External identifier (must be unique)
            country: Country code
            supplier_type: Supplier type
            custom_fields: Additional fields

        Returns:
            Created AravoSupplier

        Raises:
            AravoValidationError: If required fields are missing
            AravoError: If identifier already exists
        """
        self._ensure_connected()

        if not name:
            raise AravoValidationError("Supplier name is required")
        if not identifier:
            raise AravoValidationError("Supplier identifier is required")

        # Check for duplicate identifier
        if identifier in MOCK_SUPPLIERS_BY_IDENTIFIER:
            raise AravoError(f"Supplier with identifier '{identifier}' already exists")

        # Create new supplier
        supplier_id = f"ARAVO-{self._next_supplier_id:03d}"
        self._next_supplier_id += 1

        mock_supplier = MockAravoSupplier(
            supplier_id=supplier_id,
            identifier=identifier,
            name=name,
            status=SupplierStatus.PENDING.value,
            country=country or "SG",
            supplier_type=supplier_type or "Supplier",
            tax_id=custom_fields.get("tax_id", "") if custom_fields else "",
            inherent_risk_score=50.0,  # Default risk score
        )

        self._suppliers[supplier_id] = mock_supplier
        logger.info(f"AravoSimulator: Created supplier {supplier_id}: {name}")

        return mock_supplier.to_aravo_supplier()

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
        """
        self._ensure_connected()

        mock_supplier = self._suppliers.get(supplier_id)
        if not mock_supplier:
            raise AravoNotFoundError(f"Supplier not found: {supplier_id}")

        # Apply updates
        for key, value in updates.items():
            if hasattr(mock_supplier, key):
                setattr(mock_supplier, key, value)

        logger.info(f"AravoSimulator: Updated supplier {supplier_id}")
        return mock_supplier.to_aravo_supplier()

    def get_supplier_by_uen(self, uen: str) -> Optional[AravoSupplier]:
        """Get supplier by UEN/Tax ID (synchronous helper).

        Args:
            uen: Unique Entity Number

        Returns:
            AravoSupplier if found
        """
        mock_supplier = MOCK_SUPPLIERS_BY_UEN.get(uen)
        return mock_supplier.to_aravo_supplier() if mock_supplier else None

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
        self._ensure_connected()

        return MOCK_CONTACTS.get(supplier_id, [])

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
        self._ensure_connected()

        # Search all business processes
        for processes in MOCK_BUSINESS_PROCESSES.values():
            for process in processes:
                if process.bp_id == bp_id:
                    return process

        return None

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
        self._ensure_connected()

        return MOCK_BUSINESS_PROCESSES.get(supplier_id, [])

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
            Business Process ID
        """
        self._ensure_connected()

        # Generate mock BP ID
        bp_id = f"BP-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            f"AravoSimulator: Started business process {bp_id} "
            f"for supplier {supplier_id}"
        )
        return bp_id

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
            br_type: Business Relationship type key
            sid_type: Supplier ID type

        Returns:
            List of business relationships
        """
        self._ensure_connected()

        # Get mock engagements
        engagements = MOCK_ENGAGEMENTS.get(supplier_id, [])

        # Filter by type if specified
        if br_type:
            engagements = [e for e in engagements if e.br_type == br_type]

        return engagements

    # =========================================================================
    # Questionnaire Operations
    # =========================================================================

    async def get_questionnaires(
        self,
        supplier_id: str,
        sid_type: str = "internalId",
    ) -> list[AravoQuestionnaire]:
        """Get questionnaire results for a supplier.

        Args:
            supplier_id: Aravo supplier ID
            sid_type: ID type

        Returns:
            List of AravoQuestionnaire objects
        """
        self._ensure_connected()

        return MOCK_QUESTIONNAIRES.get(supplier_id, [])

    # =========================================================================
    # Reports Operations
    # =========================================================================

    async def get_reports(self) -> list[dict[str, Any]]:
        """Get list of available reports."""
        self._ensure_connected()

        return [
            {"id": "RPT-001", "name": "Supplier Risk Summary", "type": "Summary"},
            {"id": "RPT-002", "name": "Due Diligence Status", "type": "Status"},
            {"id": "RPT-003", "name": "Compliance Overview", "type": "Compliance"},
        ]

    async def get_report_data(self, report_id: str) -> dict[str, Any]:
        """Get report data by ID."""
        self._ensure_connected()

        return {
            "id": report_id,
            "name": "Mock Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": [],
        }

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

        Args:
            supplier_id: Aravo supplier ID or external identifier
            sid_type: ID type
            engagement_type: Business relationship type for engagements

        Returns:
            TPRMAssessment for KYP report
        """
        self._ensure_connected()

        # Get supplier
        supplier = await self.get_supplier(supplier_id, sid_type)
        if not supplier:
            return None

        # Determine TPRM status
        tprm_status = self._determine_tprm_status(supplier)

        # Get engagements
        engagements = await self.get_business_relationships(
            supplier.supplier_id, engagement_type or "TPMEngagement"
        )
        # Filter active engagements
        active_engagements = [
            e for e in engagements if e.status.lower() in ("active", "in progress")
        ]

        # Get business processes and convert to due diligence status
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

        # Get questionnaires
        questionnaires = await self.get_questionnaires(supplier.supplier_id)

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
            last_assessment_date=datetime.now(timezone.utc),
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
        """Determine TPRM status from supplier data."""
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
        """Generate TPRM notes for KYP report."""
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
    # Sanctions Screening (KYP Integration)
    # =========================================================================

    async def screen_entity(
        self,
        entity_name: str,
        uen: Optional[str] = None,
        country: Optional[str] = None,
    ) -> dict[str, Any]:
        """Screen entity against simulated sanctions lists.

        This method implements sanctions screening for KYP (Know Your Partner)
        due diligence. It checks the entity against simulated sanctions databases.

        Per KYP_guide.md terminology:
        - NO_ADVERSE_FINDINGS: Entity not found on any sanctions list
        - ADVERSE_FINDINGS: Entity found on sanctions list

        Args:
            entity_name: Name of entity to screen
            uen: Optional UEN/Tax ID for additional matching
            country: Optional country for jurisdiction-specific screening

        Returns:
            Screening result with status and details:
            - status: "NO_ADVERSE_FINDINGS" or "ADVERSE_FINDINGS"
            - checked_lists: List of sanctions databases checked
            - matches: List of matches found (if any)
            - details: Additional screening details
            - simulated: True (indicates simulated data)
        """
        self._ensure_connected()

        # Normalize entity name for lookup
        normalized_name = entity_name.lower().strip()
        # Create variations for matching
        name_variations = [
            normalized_name,
            normalized_name.replace(" ", "_"),
            normalized_name.replace(" ", ""),
            "_".join(normalized_name.split()),
        ]

        # Check against simulated sanctions database
        matches = []
        for variation in name_variations:
            if variation in SIMULATED_SANCTIONS:
                match_data = SIMULATED_SANCTIONS[variation]
                matches.append(
                    {
                        "matched_name": entity_name,
                        "matched_variation": variation,
                        "list": match_data.get("list", "Unknown"),
                        "reason": match_data.get("reason", ""),
                        "date_added": match_data.get("date_added", ""),
                        "program": match_data.get("program", ""),
                    }
                )
                break  # One match is sufficient

        # Also check if UEN matches any blocked entity
        if uen and not matches:
            # Check if UEN belongs to a blocked supplier
            supplier = self.get_supplier_by_uen(uen)
            if supplier and supplier.status.lower() in (
                "rejected",
                "blocked",
                "terminated",
            ):
                matches.append(
                    {
                        "matched_name": supplier.name,
                        "matched_uen": uen,
                        "list": "Internal Blacklist",
                        "reason": f"Supplier status: {supplier.status}",
                        "date_added": "",
                        "program": "INTERNAL",
                    }
                )

        # Build response
        if matches:
            logger.info(f"AravoSimulator: Sanctions match found for '{entity_name}'")
            return {
                "status": "ADVERSE_FINDINGS",
                "entity_name": entity_name,
                "uen": uen,
                "country": country,
                "checked_lists": SANCTIONS_LISTS_CHECKED,
                "matches": matches,
                "match_count": len(matches),
                "details": {
                    "primary_match": matches[0],
                    "screening_date": datetime.now(timezone.utc).isoformat(),
                    "action_required": "Do not proceed. Escalate to compliance.",
                },
                "simulated": True,
            }

        logger.debug(f"AravoSimulator: No sanctions match for '{entity_name}'")
        return {
            "status": "NO_ADVERSE_FINDINGS",
            "entity_name": entity_name,
            "uen": uen,
            "country": country,
            "checked_lists": SANCTIONS_LISTS_CHECKED,
            "matches": [],
            "match_count": 0,
            "details": {
                "screening_date": datetime.now(timezone.utc).isoformat(),
                "message": "No matching records identified on checked sanctions lists",
            },
            "simulated": True,
        }

    def screen_entity_sync(
        self,
        entity_name: str,
        uen: Optional[str] = None,
        country: Optional[str] = None,
    ) -> dict[str, Any]:
        """Synchronous version of screen_entity for non-async contexts.

        Args:
            entity_name: Name of entity to screen
            uen: Optional UEN/Tax ID
            country: Optional country code

        Returns:
            Same as screen_entity()
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            # Already in async context - create task
            raise RuntimeError("Use screen_entity() in async context")
        except RuntimeError:
            # No running loop - safe to run
            return asyncio.run(self.screen_entity(entity_name, uen, country))

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check simulator status."""
        return {
            "status": "connected" if self._connected else "disconnected",
            "mode": "simulator",
            "base_url": "mock://aravo-simulator",
            "auth_type": "none",
            "token_valid": None,
            "configured": True,
            "suppliers_available": len(self._suppliers),
            "cached_suppliers": len(self._suppliers),
        }

    # =========================================================================
    # Context Manager
    # =========================================================================

    async def __aenter__(self) -> "AravoSimulator":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


# Protocol compliance check — skip in production where instantiation is blocked
if os.getenv("ENVIRONMENT", "").strip().lower() != "production":
    try:
        assert isinstance(AravoSimulator(), AravoClientProtocol)
    except (AssertionError, RuntimeError):
        logger.warning("AravoSimulator does not fully implement AravoClientProtocol")
