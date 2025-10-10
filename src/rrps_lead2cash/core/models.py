"""
Data models for RRPS Lead-to-Cash POV.

This module defines canonical data models for the agentic lead-to-cash automation:
- SalesOrderProposal: Canonical order payload sent to SAP via CPI
- OpportunityData: CEC opportunity enriched with assessment results
- BOMData: IPAS configuration/BOM normalized for MS5 itemization
- DDSummary: Due diligence check results and audit trail
- POVMetrics: KPI tracking for baseline vs. pilot comparison

Based on POV Proposal Chapter 5 (Architecture) and Chapter 6 (Dataflow).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, UUID4, field_validator
import uuid


# ============================================================================
# Enums for controlled vocabularies
# ============================================================================

class OrderStatus(str, Enum):
    """Sales order lifecycle states."""
    DRAFT = "draft"
    PROPOSED = "proposed"
    VALIDATED = "validated"
    POSTED = "posted"
    FAILED = "failed"


class DDCheckStatus(str, Enum):
    """Due diligence check outcomes."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ProvenanceType(str, Enum):
    """Field derivation methods for audit trail."""
    COPY = "copy"           # Direct copy from source system
    LOOKUP = "lookup"       # Master data lookup (e.g., customer → sold-to)
    DERIVATION = "derivation"  # Rule-based calculation
    USER_INPUT = "user_input"  # Manual entry by user


class AutomationBand(str, Enum):
    """Automation confidence bands (per POV Chapter 4)."""
    GREEN = "green"    # Direct/lookup - high confidence
    AMBER = "amber"    # Rule-derived - needs confirmation
    RED = "red"        # Human-only - prompts required


# ============================================================================
# Sub-models (nested structures)
# ============================================================================

class Incoterms(BaseModel):
    """Incoterms specification with location."""
    code: str = Field(..., description="Incoterms code (e.g., DAP, EXW, FOB)")
    location: Optional[str] = Field(None, description="Location/point (e.g., Singapore Port)")


class SalesOrderItem(BaseModel):
    """Individual line item in sales order."""
    line: int = Field(..., description="Line number (10, 20, 30...)")
    material: str = Field(..., description="Material code from IPAS BOM")
    quantity: float = Field(..., gt=0, description="Order quantity")
    uom: str = Field(..., description="Unit of measure (EA, KG, etc.)")
    plant: Optional[str] = Field(None, description="Manufacturing plant (e.g., SG01)")
    storage_location: Optional[str] = Field(None, description="Storage location code")
    requested_date: Optional[datetime] = Field(None, description="Item-level delivery date")
    text: Optional[str] = Field(None, max_length=1000, description="Line item text")


class Attachment(BaseModel):
    """Document/artefact attachment reference."""
    type: str = Field(..., description="Artefact type (FAT, Approval, Certificate)")
    uri: str = Field(..., description="Document URI (rrps://docs/... or ArchiveLink ID)")
    hash: Optional[str] = Field(None, description="Document hash (sha256:...) for integrity")
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp")
    uploaded_by: Optional[str] = Field(None, description="User who uploaded")


class FieldProvenance(BaseModel):
    """Audit trail for individual field derivation."""
    field: str = Field(..., description="Field path (e.g., header.soldTo, items.0.material)")
    source: str = Field(..., description="Source system.field (e.g., CEC.Account.Id)")
    derivation: ProvenanceType = Field(..., description="How value was derived")
    rule_id: Optional[str] = Field(None, description="Rule ID if derivation applied")
    confidence: Optional[AutomationBand] = Field(None, description="Automation band")


class Partner(BaseModel):
    """Business partner with role."""
    role: str = Field(..., description="Partner function (SP=Sold-To, SH=Ship-To, RE=Bill-To, etc.)")
    partner_id: str = Field(..., description="SAP customer/partner number")
    name: Optional[str] = Field(None, description="Partner name (from CEC)")


class PolicyCheck(BaseModel):
    """Individual policy validation result."""
    check_id: str = Field(..., description="Policy check identifier")
    check_name: str = Field(..., description="Human-readable check name")
    status: DDCheckStatus = Field(..., description="Check outcome")
    message: Optional[str] = Field(None, description="Explanation or error message")
    required_artefacts: List[str] = Field(default_factory=list, description="Required documents")
    blocking: bool = Field(default=False, description="Does this block order creation?")


# ============================================================================
# Canonical Models (main data structures)
# ============================================================================

class SalesOrderProposal(BaseModel):
    """
    Canonical sales order proposal sent from agents → CPI → MS5.

    This is the contract defined in POV Proposal Chapter 5 (Architecture).
    CPI maps this to BAPI_SALESORDER_SIMULATE (dryRun=true) or ORDERS05 IDoc (dryRun=false).
    """

    # Header fields
    sales_org: str = Field(..., description="Sales organization (e.g., 1000)")
    distribution_channel: str = Field(..., description="Distribution channel (e.g., 10)")
    division: str = Field(..., description="Division (e.g., 00)")

    # Partners (from CEC)
    sold_to: str = Field(..., description="Sold-to party (customer number)")
    ship_to: Optional[str] = Field(None, description="Ship-to party")
    bill_to: Optional[str] = Field(None, description="Bill-to party")
    payer: Optional[str] = Field(None, description="Payer")

    # Commercial terms
    incoterms: Incoterms = Field(..., description="Incoterms specification")
    payment_terms: str = Field(..., description="Payment terms code (e.g., 0001)")
    requested_date: datetime = Field(..., description="Requested delivery date")
    purchase_order_number: Optional[str] = Field(None, description="Customer PO number")

    # Line items (from IPAS BOM via Data Mgmt Agent)
    items: List[SalesOrderItem] = Field(..., min_length=1, description="Order line items")

    # Attachments (from Due Diligence Agent)
    attachments: List[Attachment] = Field(default_factory=list, description="Supporting documents")

    # Provenance (audit trail)
    provenance: List[FieldProvenance] = Field(default_factory=list, description="Field-level derivation trail")

    # Metadata
    correlation_id: str = Field(default_factory=lambda: f"klx-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}",
                                 description="Correlation ID for tracing")
    dry_run: bool = Field(default=True, description="If true, simulate only; if false, create order")
    proposed_by: Optional[str] = Field(None, description="User/agent who proposed order")
    proposed_at: datetime = Field(default_factory=datetime.utcnow, description="Proposal timestamp")

    # SAP response fields (populated after posting)
    cpi_message_id: Optional[str] = Field(None, description="CPI Message ID from IDoc send")
    sap_order_number: Optional[str] = Field(None, description="VBELN (sales document number)")
    status: OrderStatus = Field(default=OrderStatus.DRAFT, description="Order lifecycle status")


class OpportunityData(BaseModel):
    """
    CEC opportunity enriched with assessment results.

    Used by Opportunity Assessment Agent to score readiness.
    Source: CEC OData via CPI.
    """

    # CEC identifiers
    opportunity_id: str = Field(..., description="CEC opportunity ID")
    opportunity_name: str = Field(..., description="Opportunity name/description")
    stage: str = Field(..., description="Sales stage (e.g., Proposal, Negotiation, Closed Won)")

    # Account & partners
    account_id: str = Field(..., description="CEC account ID")
    account_name: str = Field(..., description="Account name")
    partners: List[Partner] = Field(default_factory=list, description="Business partners with roles")

    # Commercial terms (from CEC)
    payment_terms: Optional[str] = Field(None, description="Payment terms code")
    incoterms_code: Optional[str] = Field(None, description="Incoterms code")
    incoterms_location: Optional[str] = Field(None, description="Incoterms location")

    # Dates
    requested_delivery_date: Optional[datetime] = Field(None, description="Customer requested date")
    expected_close_date: Optional[datetime] = Field(None, description="Expected close date")

    # Configuration status (from IPAS)
    configuration_id: Optional[str] = Field(None, description="IPAS configuration ID")
    configuration_status: Optional[str] = Field(None, description="Config health (OK, INCOMPLETE, ERROR)")

    # Assessment results (populated by Opportunity Assessment Agent)
    readiness_score: Optional[float] = Field(None, ge=0, le=100, description="Readiness score (0-100)")
    readiness_flags: List[str] = Field(default_factory=list, description="Gaps/blockers (e.g., 'Missing ship-to')")
    assessed_at: Optional[datetime] = Field(None, description="Assessment timestamp")
    assessed_by: Optional[str] = Field(None, description="Agent/user who assessed")


class BOMData(BaseModel):
    """
    IPAS configuration/BOM normalized for MS5 itemization.

    Produced by Data Management Agent from IPAS read via proxy.
    Maps IPAS BOM lines to MS5-compatible materials/UoM.
    """

    # IPAS identifiers
    configuration_id: str = Field(..., description="IPAS configuration ID")
    configuration_version: Optional[str] = Field(None, description="Configuration version/revision")

    # BOM items (normalized)
    items: List[SalesOrderItem] = Field(default_factory=list, description="Normalized BOM items ready for MS5")

    # Validation results
    validation_status: Literal["OK", "WARNINGS", "ERRORS"] = Field("OK", description="Overall BOM health")
    mismatches: List[Dict[str, Any]] = Field(default_factory=list,
                                              description="Material/UoM mismatches or missing mappings")

    # Metadata
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="IPAS retrieval timestamp")
    normalized_by: str = Field(default="DataManagementAgent", description="Agent that normalized BOM")


class DDSummary(BaseModel):
    """
    Due diligence check results and audit trail.

    Produced by Due Diligence Agent after applying commercial/policy checks.
    Attached to order proposal for audit.
    """

    # Reference
    correlation_id: str = Field(..., description="Correlation ID linking to order proposal")
    opportunity_id: Optional[str] = Field(None, description="Source CEC opportunity ID")

    # Check results
    checks: List[PolicyCheck] = Field(default_factory=list, description="Policy validation results")
    overall_status: DDCheckStatus = Field(DDCheckStatus.PENDING, description="Overall DD outcome")
    blocking_issues: List[str] = Field(default_factory=list, description="Blocking issues that prevent create")

    # Artefact tracking
    required_artefacts: List[str] = Field(default_factory=list, description="Required documents per policy")
    attached_artefacts: List[Attachment] = Field(default_factory=list, description="Actual attachments provided")
    missing_artefacts: List[str] = Field(default_factory=list, description="Still-missing documents")

    # Tasks created (for user follow-up)
    tasks_created: List[Dict[str, Any]] = Field(default_factory=list,
                                                  description="Just-in-time tasks raised (e.g., upload FAT)")

    # Metadata
    checked_at: datetime = Field(default_factory=datetime.utcnow, description="DD check timestamp")
    checked_by: str = Field(default="DueDiligenceAgent", description="Agent that performed checks")
    re_check_required: bool = Field(default=False, description="Must re-check before billing milestone?")


class POVMetrics(BaseModel):
    """
    KPI tracking for POV evaluation (baseline vs. pilot).

    Defined in POV Proposal Chapter 3 (Metrics).
    Captured per transaction for aggregation into scorecard.
    """

    # Transaction reference
    correlation_id: str = Field(..., description="Transaction correlation ID")
    cohort: Literal["baseline", "pilot"] = Field(..., description="Baseline or pilot cohort")
    order_type: str = Field(..., description="Pilot order type being measured")

    # KPI 1: Cycle time (order-ready → posted)
    order_ready_timestamp: Optional[datetime] = Field(None, description="When order was ready to post")
    order_posted_timestamp: Optional[datetime] = Field(None, description="When order was posted to MS5")
    cycle_time_seconds: Optional[float] = Field(None, description="Elapsed seconds (ready → posted)")

    # KPI 2: Acceptance rate (auto-filled fields)
    total_fields: Optional[int] = Field(None, description="Total fields in proposal")
    auto_filled_fields: Optional[int] = Field(None, description="Fields auto-filled by agents")
    accepted_fields: Optional[int] = Field(None, description="Auto-filled fields accepted by user")
    acceptance_rate: Optional[float] = Field(None, ge=0, le=1, description="Acceptance rate (0-1)")

    # KPI 3: First-time-right (posting success)
    first_post_success: Optional[bool] = Field(None, description="Posted successfully on first attempt?")
    rework_events: Optional[int] = Field(None, description="Number of rework cycles before success")

    # KPI 4: Artefact readiness (billing prerequisites)
    required_artefacts_count: Optional[int] = Field(None, description="Total artefacts required")
    present_artefacts_count: Optional[int] = Field(None, description="Artefacts present before billing")
    artefact_readiness_rate: Optional[float] = Field(None, ge=0, le=1, description="Readiness rate (0-1)")

    # KPI 5: Traceability (100% required)
    has_correlation_id: bool = Field(default=True, description="Correlation ID present?")
    has_cpi_message_id: bool = Field(default=False, description="CPI Message ID captured?")
    has_sap_document: bool = Field(default=False, description="SAP VBELN captured?")
    traceability_complete: bool = Field(default=False, description="End-to-end trace complete?")

    # Metadata
    captured_at: datetime = Field(default_factory=datetime.utcnow, description="Metrics capture timestamp")


# ============================================================================
# Error/Response Models
# ============================================================================

class ValidationIssue(BaseModel):
    """Business or technical validation error."""
    code: str = Field(..., description="Error code (e.g., INCOTERMS_MISSING)")
    field: Optional[str] = Field(None, description="Field path if field-specific")
    severity: Literal["ERROR", "WARNING", "INFO"] = Field("ERROR", description="Issue severity")
    message: str = Field(..., description="Human-readable error message")


class SAPValidationResponse(BaseModel):
    """Response from CPI/BAPI simulate or create."""
    correlation_id: str = Field(..., description="Correlation ID for tracing")
    status: Literal["SUCCESS", "BUSINESS_ERROR", "TECHNICAL_ERROR"] = Field(..., description="Outcome")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues from SAP")
    sap_order_number: Optional[str] = Field(None, description="VBELN if create succeeded")
    cpi_message_id: Optional[str] = Field(None, description="CPI Message ID for IDoc")
    message: Optional[str] = Field(None, description="Summary message")


# ============================================================================
# Example usage / validation
# ============================================================================

if __name__ == "__main__":
    # Test model instantiation
    proposal = SalesOrderProposal(
        sales_org="1000",
        distribution_channel="10",
        division="00",
        sold_to="CUST123",
        ship_to="CUST123-S",
        bill_to="CUST123-B",
        incoterms=Incoterms(code="DAP", location="Singapore"),
        payment_terms="0001",
        requested_date=datetime(2025, 9, 30),
        items=[
            SalesOrderItem(line=10, material="MAT-001", quantity=2, uom="EA", plant="SG01")
        ]
    )

    print("SalesOrderProposal instantiated:")
    print(f"  Correlation ID: {proposal.correlation_id}")
    print(f"  Status: {proposal.status}")
    print(f"  Items: {len(proposal.items)}")
    print(f"  Dry run: {proposal.dry_run}")

    # Test JSON serialization
    print("\nJSON serialization test:")
    print(proposal.model_dump_json(indent=2))
