"""
Data models for RRPS Lead-to-Cash POV.

This module defines canonical data models for the agentic lead-to-cash automation:
- SalesOrderProposal: Canonical order payload sent to SAP via CPI
- OpportunityData: CEC opportunity enriched with assessment results
- BOMData: IPAS configuration/BOM normalized for MS5 itemization
- DDSummary: Due diligence check results and audit trail
- KYPAssessment: Know Your Partner compliance from Aravo
- TwoTierValidation: Combined KYP + SAP validation
- POVMetrics: KPI tracking for baseline vs. pilot comparison

Based on POV Proposal Chapter 5 (Architecture) and Chapter 6 (Dataflow).
"""

from __future__ import annotations

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


class TwoTierValidationStatus(str, Enum):
    """Combined validation outcome from Tier 1 (KYP) + Tier 2 (SAP)."""
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"


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

# ============================================================================
# IPAS Models (XML-sourced order data for MS5 entry)
# ============================================================================

class IPASDocumentProperties(BaseModel):
    """IPAS XML DocumentProperties section."""
    created: str = Field(..., description="Creation timestamp (YYYYMMDD HH:MM:SS)")
    type: str = Field(default="IPAS", description="Document type")
    format_version: str = Field(default="1.0", description="IPAS SUN FORMAT version")
    source: str = Field(default="IPAS7.1", description="Source system")
    target_id: str = Field(default="", description="Target system ID")
    target_desc: str = Field(default="", description="Target description")
    message_id: str = Field(..., description="Unique message identifier")
    draft_version: str = Field(default="0", description="Draft version number")


class IPASBOMItem(BaseModel):
    """Single BOM item within an engine (material line)."""
    item_number: str = Field(..., description="Item sequence number")
    engine_number: str = Field(..., description="Parent engine number")
    material: str = Field(..., description="Material number (e.g., XS522010.00005)")
    material_desc: str = Field(default="", description="Material description")
    quantity: int = Field(default=1, description="Quantity")
    item_type: str = Field(default="M", description="Item type (M=Material)")
    assembly_note: str = Field(default="", description="Assembly note (e.g., M/A)")
    delivery_date: str = Field(default="", description="Delivery date (YYYYMMDD)")
    packaging_group: str = Field(default="", description="Packaging group")
    ship_to_party: str = Field(default="", description="Ship-to party override")
    sub_object_number: str = Field(default="", description="Sub-object reference")


class IPASEngine(BaseModel):
    """Single engine within an IPAS order."""
    engine_number: str = Field(..., description="Engine sequence (0001, 0002, ...)")
    engine_type: str = Field(..., description="Engine type (e.g., 12V2000G65SZ)")
    quantity: int = Field(default=1, description="Number of units")
    delivery_date: str = Field(..., description="Delivery date (YYYYMMDD)")
    ship_to_party: str = Field(default="", description="Ship-to party")
    shipping_type: str = Field(default="", description="Shipping type code")
    packaging_group: str = Field(default="", description="Packaging group")
    gross_price: float = Field(default=0.0, description="Gross price per engine")
    absolute_discount: float = Field(default=0.0, description="Absolute discount amount")
    acceptance_with_customer: str = Field(default="0", description="Customer acceptance flag")
    exhaust_regulation: str = Field(default="", description="Exhaust regulation code")
    take_from_stock: str = Field(default="0", description="Take from stock flag")
    items: List[IPASBOMItem] = Field(default_factory=list, description="BOM items for this engine")


class IPASHeader(BaseModel):
    """IPAS order header — core commercial and technical data."""
    ipas_order_status: str = Field(default="", description="Order status code")
    ipas_project_number: str = Field(default="", description="IPAS project number")
    ipas_order_number: str = Field(..., description="IPAS order number (primary key)")
    ipas_order_version: str = Field(default="00", description="Order version")
    document_date: str = Field(default="", description="Document date (YYYYMMDD)")
    engine_type: str = Field(default="", description="Primary engine type")
    series: str = Field(default="", description="Engine series")
    cylinder: str = Field(default="", description="Number of cylinders")
    power: str = Field(default="", description="Power rating")
    engine_speed: str = Field(default="", description="Engine speed (RPM)")
    sold_to_party: str = Field(default="", description="SAP sold-to customer number")
    bill_to_party: str = Field(default="", description="SAP bill-to party")
    ship_to_party: str = Field(default="", description="SAP ship-to party")
    end_customer: str = Field(default="", description="End customer SAP number")
    end_customer_country: str = Field(default="", description="End customer country code")
    purchase_order_number: str = Field(default="", description="Customer PO number")
    purchase_order_date: str = Field(default="", description="Customer PO date")
    incoterms_1: str = Field(default="", description="Incoterms code (EXW, FOB, etc.)")
    incoterms_2: str = Field(default="", description="Incoterms location")
    currency_code: str = Field(default="", description="Currency (CNY, EUR, USD)")
    terms_of_payment: str = Field(default="", description="Payment terms code")
    distribution_channel: str = Field(default="", description="Distribution channel")
    application_coarse: str = Field(default="", description="Application coarse code")
    application_fine: str = Field(default="", description="Application fine code")
    business_type: str = Field(default="", description="Business type code")
    classification_society: str = Field(default="", description="Classification society code")
    emission_cert_authority: str = Field(default="", description="Emission cert authority")
    billing_plan_rel: str = Field(default="", description="Billing plan relevance (X=yes)")
    product_category: str = Field(default="", description="Product category code")
    power_unit: str = Field(default="KW", description="Power unit (KW, HP)")


class IPASPartner(BaseModel):
    """Partner information from IPAS XML."""
    type: str = Field(..., description="Partner role (Bill-to, Commercial_Contact)")
    customer_code: str = Field(default="", description="Customer code")
    name1: str = Field(default="", description="Name line 1")
    name2: str = Field(default="", description="Name line 2")
    country: str = Field(default="", description="Country")
    city: str = Field(default="", description="City")
    # Employee fields
    partner_id: str = Field(default="", description="Employee partner ID")
    first_name: str = Field(default="", description="First name")
    last_name: str = Field(default="", description="Last name")
    department: str = Field(default="", description="Department")
    phone: str = Field(default="", description="Phone")
    email: str = Field(default="", description="Email")


class IPASOrder(BaseModel):
    """Complete IPAS order parsed from XML — one order per file."""
    document_properties: IPASDocumentProperties
    header: IPASHeader
    engines: List[IPASEngine] = Field(default_factory=list, description="Engines in this order")
    partners: List[IPASPartner] = Field(default_factory=list, description="Partner information")

    # Computed summary fields
    total_engines: int = Field(default=0, description="Number of engines")
    total_bom_items: int = Field(default=0, description="Total BOM items across all engines")
    total_value: float = Field(default=0.0, description="Sum of gross prices for all engines")
    source_file: str = Field(default="", description="Source XML filename")


class IPASSummary(BaseModel):
    """Summary of all IPAS orders available."""
    total_orders: int = Field(default=0, description="Number of IPAS XML files parsed")
    total_engines: int = Field(default=0, description="Total engines across all orders")
    total_value: float = Field(default=0.0, description="Total value across all orders")
    orders: List[Dict[str, Any]] = Field(default_factory=list, description="Order summaries")


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

    # KYP compliance (populated by Aravo KYP check during qualification)
    kyp_status: Optional[str] = Field(None, description="KYP outcome: APPROVED, CONDITIONAL, BLOCKED, PENDING, NOT_FOUND")
    kyp_risk_rating: Optional[str] = Field(None, description="Aravo risk rating (Low, Medium, High, Very High)")
    kyp_assessed_at: Optional[datetime] = Field(None, description="KYP assessment timestamp")


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

    # KYP assessment (Tier 1 — from Aravo)
    kyp_assessment: Optional[KYPAssessment] = Field(None, description="KYP compliance assessment from Aravo")

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
# KYP / Aravo Models (Know Your Partner - Due Diligence Tier 1)
# ============================================================================

class AravoEngagement(BaseModel):
    """Single engagement row from Aravo KYP report."""
    active: bool = Field(..., description="Whether the engagement is active")
    third_party_id: str = Field(..., description="Aravo third party identifier")
    third_party_name: str = Field(..., description="Third party company name")
    proposer: str = Field(..., description="Person who proposed the engagement")
    onboarding_status: str = Field(..., description="Third party onboarding status")
    third_party_status: str = Field(..., description="Third party approval status")
    ec_review_status: str = Field(..., description="Ethics & Compliance review status")
    sec_review_status: str = Field(..., description="Security & Export Control review status")
    risk_rating: str = Field(..., description="Engagement risk rating")
    engagement_id: int = Field(..., description="Aravo engagement ID")
    engagement_name: str = Field(..., description="Description of the engagement")
    partner_type: str = Field(..., description="Customer or Supplier")


class AravoReportMeta(BaseModel):
    """Metadata from Aravo report API response."""
    api_version: str = Field(..., description="Aravo API version")
    data_size: int = Field(..., description="Number of report records")
    report_id: str = Field(..., description="Aravo report ID")
    report_name: str = Field(..., description="Report name")
    etl_datetime: str = Field(..., description="Last ETL timestamp from Aravo")


class KYPAssessment(BaseModel):
    """
    KYP (Know Your Partner) compliance assessment result.

    Produced by querying the Aravo third-party risk management platform.
    Used as Tier 1 validation during opportunity qualification (Epic 1).
    Direct REST API call to Aravo — does NOT go through SAP CPI.
    """
    # Identification
    customer_name: str = Field(..., description="Customer/partner name queried")
    matched: bool = Field(..., description="Whether a match was found in Aravo")

    # Aravo engagement data (populated if matched)
    third_party_id: Optional[str] = Field(None, description="Aravo third party identifier")
    engagement_id: Optional[int] = Field(None, description="Aravo engagement ID")
    engagement_name: Optional[str] = Field(None, description="Engagement description")
    partner_type: Optional[str] = Field(None, description="Customer or Supplier")
    proposer: Optional[str] = Field(None, description="Engagement proposer")

    # KYP status fields
    onboarding_status: Optional[str] = Field(None, description="Onboarding lifecycle status")
    third_party_status: Optional[str] = Field(None, description="Overall approval status")
    risk_rating: Optional[str] = Field(None, description="Engagement risk rating")
    ec_review_status: Optional[str] = Field(None, description="Ethics & Compliance review")
    sec_review_status: Optional[str] = Field(None, description="Security & Export Control review")

    # Assessment outcome
    kyp_status: str = Field(..., description="KYP outcome: APPROVED, CONDITIONAL, BLOCKED, PENDING, NOT_FOUND")
    issues: List[str] = Field(default_factory=list, description="KYP issues or conditions")
    blocking: bool = Field(default=False, description="Whether KYP blocks proceeding")

    # Metadata
    assessed_at: datetime = Field(default_factory=datetime.utcnow, description="Assessment timestamp")
    source: str = Field(default="Aravo", description="Source system")
    report_etl_datetime: Optional[str] = Field(None, description="Aravo report ETL timestamp")


class TwoTierValidationRequest(BaseModel):
    """Request model for two-tier customer validation."""
    customer: str = Field(..., min_length=1, max_length=100, description="Customer name or SAP ID")
    order_value: float = Field(default=0.0, ge=0.0, description="Order value for credit check")


class CustomerValidationRequest(BaseModel):
    """Request model for customer validation via Due Diligence agent."""
    customer_id: str = Field(..., min_length=1, max_length=20, description="Customer ID")
    order_value: float = Field(default=0.0, ge=0.0, description="Order value for credit check")
    sales_org: Optional[str] = Field(None, max_length=10, description="Sales organization")


class TwoTierValidationResponse(BaseModel):
    """
    Combined two-tier customer validation response.

    Tier 1: KYP Compliance Assessment (Aravo — external due diligence)
    Tier 2: SAP/ECC Validation (transactional due diligence via CPI)
    """
    # Overall result
    status: TwoTierValidationStatus = Field(..., description="Combined validation outcome")
    customer: str = Field(..., description="Customer name or ID validated")

    # Tier 1: KYP results
    tier1_kyp: Optional[KYPAssessment] = Field(None, description="KYP compliance assessment from Aravo")

    # Tier 2: SAP results (placeholder — implemented via CPI in TE-12)
    tier2_sap: Optional[Dict[str, Any]] = Field(None, description="SAP master data and credit validation")

    # Combined issues
    issues: List[str] = Field(default_factory=list, description="All validation issues from both tiers")
    conditions: List[str] = Field(default_factory=list, description="Conditions for proceeding")

    # Metadata
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")
    correlation_id: str = Field(
        default_factory=lambda: f"val-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}",
        description="Validation correlation ID"
    )


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
