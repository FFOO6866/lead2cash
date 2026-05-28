"""
KYP Report Models - Comprehensive Due Diligence Report Structure

This module defines the structured JSON format for KYP (Know Your Partner) reports
that the frontend renders as rich card-based UI components.

The structure is designed to be:
1. Self-describing (type, status fields)
2. Flexible (sections array)
3. Source-attributed (every data point has a source)
4. Status-aware (PASSED/WARNING/FAILED/INFO)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SectionStatus(str, Enum):
    """Status for each KYP section.

    Terminology per KYP guide (Section 7.5-7.6):
    - NO_ADVERSE_FINDINGS: No issues found
    - ADVERSE_FINDINGS: Issues found (qualify with Active/Resolved/Historical)
    - UNABLE_TO_VERIFY: Could not access data (private company, etc.)
    - INFO: Informational (non-risk data like entity profile)
    """

    NO_ADVERSE_FINDINGS = "NO_ADVERSE_FINDINGS"
    ADVERSE_FINDINGS = "ADVERSE_FINDINGS"
    UNABLE_TO_VERIFY = "REVIEW PENDING"
    INFO = "INFO"


class OverallDecision(str, Enum):
    """Overall KYP decision."""

    PROCEED = "PROCEED"
    PROCEED_WITH_CAUTION = "PROCEED WITH CAUTION"
    DO_NOT_PROCEED = "DO NOT PROCEED"
    PENDING_REVIEW = "PENDING REVIEW"


@dataclass
class ReportField:
    """Single field in a report section."""

    label: str
    value: str
    source: Optional[str] = None
    field_type: str = "text"  # text, currency, link, status, percentage
    status: Optional[str] = None  # success, warning, error (for status type)
    badge: Optional[str] = None  # Optional badge text (e.g., "Large Cap")

    def to_dict(self) -> dict:
        result = {"label": self.label, "value": self.value}
        if self.source:
            result["source"] = self.source
        if self.field_type != "text":
            result["type"] = self.field_type
        if self.status:
            result["status"] = self.status
        if self.badge:
            result["badge"] = self.badge
        return result


@dataclass
class SanctionsCheck:
    """Single sanctions database check result."""

    database: str
    result: str
    status: str  # clear, match, error
    source_url: Optional[str] = None  # Authoritative source URL
    list_date: Optional[str] = None  # Publication date of the list data

    def to_dict(self) -> dict:
        d = {
            "database": self.database,
            "result": self.result,
            "status": self.status,
        }
        if self.source_url:
            d["source_url"] = self.source_url
        if self.list_date:
            d["list_date"] = self.list_date
        return d


@dataclass
class LitigationFinding:
    """Single litigation or regulatory finding."""

    title: str
    details: str
    outcome: Optional[str] = None
    status: str = "ACTIVE"  # ACTIVE, RESOLVED, PENDING
    resolution_date: Optional[str] = None
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "title": self.title,
            "details": self.details,
            "status": self.status,
        }
        if self.outcome:
            result["outcome"] = self.outcome
        if self.resolution_date:
            result["resolution_date"] = self.resolution_date
        if self.source_url:
            result["source_url"] = self.source_url
        return result


@dataclass
class ReportSubsection:
    """Subsection within a report section (e.g., Ownership within Financial Health)."""

    title: str
    fields: list[ReportField] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "fields": [f.to_dict() for f in self.fields],
        }


@dataclass
class ReportSection:
    """Single section of the KYP report."""

    id: str
    title: str
    icon: str
    status: SectionStatus
    source: str
    fields: list[ReportField] = field(default_factory=list)
    subsections: list[ReportSubsection] = field(default_factory=list)
    # For sanctions section
    checks: list[SanctionsCheck] = field(default_factory=list)
    checked_date: Optional[str] = None
    # For litigation section
    findings: list[LitigationFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "icon": self.icon,
            "status": self.status.value,
            "source": self.source,
        }
        if self.fields:
            result["fields"] = [f.to_dict() for f in self.fields]
        if self.subsections:
            result["subsections"] = [s.to_dict() for s in self.subsections]
        if self.checks:
            result["checks"] = [c.to_dict() for c in self.checks]
            result["checked_date"] = self.checked_date
        if self.findings:
            result["findings"] = [f.to_dict() for f in self.findings]
        return result


@dataclass
class AssessmentItem:
    """Single item in the assessment summary."""

    category: str
    status: SectionStatus
    notes: str

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass
class KYPReport:
    """Complete KYP Due Diligence Report.

    This is the main structure returned by the chat endpoint for KYP queries.
    The frontend detects type="kyp_report" and renders it using formatKYPReport().
    """

    entity_name: str
    overall_status: OverallDecision
    can_proceed: bool
    sections: list[ReportSection]
    assessment_summary: list[AssessmentItem]
    recommendation_decision: OverallDecision
    recommendation_text: str
    report_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    issues: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Build a text summary for the "answer" field so API clients can
        # access KYP results via the standard "answer" key.
        answer_text = (
            f"KYP Report for {self.entity_name}: "
            f"{self.recommendation_decision.value} "
            f"(Risk: {self.overall_status.value}). "
            f"{self.recommendation_text}"
        )
        return {
            "type": "kyp_report",
            "answer": answer_text,
            "entity_name": self.entity_name,
            "report_date": self.report_date,
            "overall_status": self.overall_status.value,
            "can_proceed": self.can_proceed,
            "sections": [s.to_dict() for s in self.sections],
            "assessment": {
                "summary": [a.to_dict() for a in self.assessment_summary],
            },
            "recommendation": {
                "decision": self.recommendation_decision.value,
                "text": self.recommendation_text,
            },
            "issues": self.issues,
            "conditions": self.conditions,
        }


# =============================================================================
# Builder Functions
# =============================================================================


def build_entity_profile_section(
    name: str,
    stock_code: Optional[str] = None,
    uen: Optional[str] = None,
    country: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    website: Optional[str] = None,
) -> ReportSection:
    """Build Entity Profile section from EODHD + SAP data."""
    fields = [ReportField(label="Registered Name", value=name, source="EODHD")]

    if stock_code:
        fields.append(ReportField(label="Stock Code", value=stock_code, source="EODHD"))
    if uen:
        fields.append(ReportField(label="UEN", value=uen, source="SAP"))
    if country:
        fields.append(ReportField(label="Country", value=country, source="EODHD"))
    if sector and industry:
        fields.append(
            ReportField(label="Sector", value=f"{sector} → {industry}", source="EODHD")
        )
    elif sector:
        fields.append(ReportField(label="Sector", value=sector, source="EODHD"))
    if website:
        fields.append(
            ReportField(
                label="Website", value=website, field_type="link", source="EODHD"
            )
        )

    return ReportSection(
        id="entity_profile",
        title="Entity Profile",
        icon="📋",
        status=SectionStatus.INFO,
        source="SAP",
        fields=fields,
    )


def build_sap_credit_section(
    customer_id: str,
    customer_name: str,
    credit_limit: float,
    credit_exposure: float,
    utilization_pct: float,
    currency: str = "SGD",
    credit_passed: bool = True,
) -> ReportSection:
    """Build SAP Credit Status section."""
    status = (
        SectionStatus.NO_ADVERSE_FINDINGS
        if credit_passed
        else SectionStatus.ADVERSE_FINDINGS
    )
    credit_status = "Approved" if credit_passed else "Review Required"
    status_type = "success" if credit_passed else "warning"

    return ReportSection(
        id="sap_credit",
        title="SAP Credit Status",
        icon="💳",
        status=status,
        source="MS5",
        fields=[
            ReportField(label="Customer ID", value=customer_id),
            ReportField(label="Customer Name", value=customer_name),
            ReportField(
                label="Credit Limit",
                value=f"{currency} {credit_limit:,.0f}",
                field_type="currency",
            ),
            ReportField(
                label="Credit Exposure",
                value=f"{currency} {credit_exposure:,.0f}",
                field_type="currency",
            ),
            ReportField(
                label="Utilization",
                value=f"{utilization_pct:.1f}%",
                field_type="percentage",
            ),
            ReportField(
                label="Status",
                value=credit_status,
                field_type="status",
                status=status_type,
            ),
        ],
    )


def build_financial_health_section(
    market_cap: Optional[float] = None,
    market_cap_badge: Optional[str] = None,
    revenue: Optional[float] = None,
    profit_margin: Optional[float] = None,
    pe_ratio: Optional[float] = None,
    pe_badge: Optional[str] = None,
    dividend_yield: Optional[float] = None,
    currency: str = "SGD",
    institutional_ownership: Optional[float] = None,
    float_shares: Optional[str] = None,
) -> ReportSection:
    """Build Financial Health section from EODHD fundamentals."""
    fields = []

    if market_cap:
        # Format large numbers
        if market_cap >= 1_000_000_000:
            value = f"{currency} {market_cap / 1_000_000_000:.1f}B"
        elif market_cap >= 1_000_000:
            value = f"{currency} {market_cap / 1_000_000:.1f}M"
        else:
            value = f"{currency} {market_cap:,.0f}"
        fields.append(
            ReportField(label="Market Cap", value=value, badge=market_cap_badge)
        )

    if revenue:
        if revenue >= 1_000_000_000:
            value = f"{currency} {revenue / 1_000_000_000:.2f}B"
        elif revenue >= 1_000_000:
            value = f"{currency} {revenue / 1_000_000:.1f}M"
        else:
            value = f"{currency} {revenue:,.0f}"
        fields.append(ReportField(label="Revenue (TTM)", value=value))

    if profit_margin is not None:
        fields.append(
            ReportField(
                label="Profit Margin",
                value=f"{profit_margin:.2f}%",
                field_type="percentage",
            )
        )

    if pe_ratio is not None:
        fields.append(
            ReportField(label="PE Ratio", value=f"{pe_ratio:.2f}", badge=pe_badge)
        )

    if dividend_yield is not None:
        fields.append(
            ReportField(
                label="Dividend Yield",
                value=f"{dividend_yield:.2f}%",
                field_type="percentage",
            )
        )

    subsections = []
    if institutional_ownership is not None or float_shares:
        ownership_fields = []
        if institutional_ownership is not None:
            ownership_fields.append(
                ReportField(
                    label="Institutional", value=f"{institutional_ownership:.2f}%"
                )
            )
        if float_shares:
            ownership_fields.append(ReportField(label="Float", value=float_shares))
        if ownership_fields:
            subsections.append(
                ReportSubsection(title="Ownership", fields=ownership_fields)
            )

    # Determine status based on financial health indicators
    status = SectionStatus.NO_ADVERSE_FINDINGS
    if market_cap and market_cap < 100_000_000:  # Small cap concern
        status = SectionStatus.ADVERSE_FINDINGS

    return ReportSection(
        id="financial_health",
        title="Financial Health",
        icon="📊",
        status=status,
        source="EODHD",
        fields=fields,
        subsections=subsections,
    )


def build_sanctions_section(
    checks: list[tuple[str, str, str]],  # (database, result, status)
    checked_date: Optional[str] = None,
) -> ReportSection:
    """Build Sanctions Screening section."""
    sanctions_checks = [
        SanctionsCheck(database=db, result=result, status=status)
        for db, result, status in checks
    ]

    # Determine overall status
    has_match = any(c.status == "match" for c in sanctions_checks)
    has_error = any(c.status == "error" for c in sanctions_checks)

    if has_match:
        status = SectionStatus.ADVERSE_FINDINGS
    elif has_error:
        status = SectionStatus.ADVERSE_FINDINGS
    else:
        status = SectionStatus.NO_ADVERSE_FINDINGS

    return ReportSection(
        id="sanctions",
        title="Sanctions Screening",
        icon="🛡️",
        status=status,
        source="Web Search",
        checks=sanctions_checks,
        checked_date=checked_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


def build_litigation_section(
    findings: list[
        dict
    ],  # Each dict has title, details, outcome, status, resolution_date
) -> ReportSection:
    """Build Litigation & Regulatory section."""
    litigation_findings = [
        LitigationFinding(
            title=f.get("title", ""),
            details=f.get("details", ""),
            outcome=f.get("outcome"),
            status=f.get("status", "ACTIVE"),
            resolution_date=f.get("resolution_date"),
            source_url=f.get("source_url"),
        )
        for f in findings
    ]

    # Determine status
    has_active = any(f.status == "ACTIVE" for f in litigation_findings)
    has_resolved = any(f.status == "RESOLVED" for f in litigation_findings)

    if has_active:
        status = SectionStatus.ADVERSE_FINDINGS
    elif has_resolved:
        status = SectionStatus.ADVERSE_FINDINGS
    elif not findings:
        status = SectionStatus.NO_ADVERSE_FINDINGS
    else:
        status = SectionStatus.INFO

    return ReportSection(
        id="litigation",
        title="Litigation & Regulatory",
        icon="⚖️",
        status=status,
        source="Web Search",
        findings=litigation_findings,
    )


def build_business_context_section(
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    relationship_status: Optional[
        str
    ] = None,  # "Existing Customer", "New Prospect", "Dormant"
    first_order_date: Optional[str] = None,
    total_orders: Optional[int] = None,
    total_revenue: Optional[float] = None,
    currency: str = "SGD",
    active_contracts: Optional[int] = None,
    pipeline_opportunities: Optional[int] = None,
    pipeline_value: Optional[float] = None,
    installed_base_units: Optional[int] = None,
    last_order_date: Optional[str] = None,
    account_manager: Optional[str] = None,
    # CEC-derived metrics (from opportunities)
    lifetime_value: Optional[float] = None,
    won_deals_count: Optional[int] = None,
    lost_deals_count: Optional[int] = None,
    open_opportunities_count: Optional[int] = None,
    open_pipeline_value: Optional[float] = None,
    next_expected_close: Optional[str] = None,
) -> ReportSection:
    """Build Business Context section (Phase 1 of Inside-Out approach).

    This section captures what we already know about the partner internally:
    - Existing Relationship: customer history, first/last order dates
    - Active Contracts: ongoing agreements
    - Pipeline: open opportunities from CEC
    - Revenue/Installed Base: historical spend, equipment in field
    - CEC Metrics: lifetime value, deal history, pipeline

    Args:
        customer_id: SAP customer ID
        customer_name: Customer name
        relationship_status: "Existing Customer", "New Prospect", "Dormant"
        first_order_date: Date of first order (YYYY-MM-DD)
        total_orders: Total number of orders placed
        total_revenue: Total revenue from customer (deprecated, use lifetime_value)
        currency: Currency code (default: SGD)
        active_contracts: Number of active contracts
        pipeline_opportunities: Number of open opportunities (deprecated)
        pipeline_value: Total value of pipeline (deprecated, use open_pipeline_value)
        installed_base_units: Number of units in customer's fleet
        last_order_date: Date of last order (YYYY-MM-DD)
        account_manager: Assigned account manager name
        lifetime_value: Sum of won opportunity values from CEC
        won_deals_count: Number of won opportunities
        lost_deals_count: Number of lost opportunities
        open_opportunities_count: Number of open opportunities from CEC
        open_pipeline_value: Sum of open opportunity values from CEC
        next_expected_close: Next expected close date from open opportunities

    Returns:
        ReportSection for Business Context
    """
    fields = []
    subsections = []

    # Relationship Status (key field)
    if relationship_status:
        status_value = relationship_status
        status_type = (
            "success" if relationship_status == "Existing Customer" else "warning"
        )
        if relationship_status == "New Prospect":
            status_type = "warning"
        elif relationship_status == "Dormant":
            status_type = "error"
        fields.append(
            ReportField(
                label="Relationship Status",
                value=status_value,
                field_type="status",
                status=status_type,
                source="SAP",
            )
        )

    if customer_id:
        fields.append(
            ReportField(label="SAP Customer ID", value=customer_id, source="SAP")
        )

    if customer_name:
        fields.append(
            ReportField(label="Customer Name", value=customer_name, source="SAP")
        )

    if account_manager:
        fields.append(
            ReportField(label="Account Manager", value=account_manager, source="CRM")
        )

    # Build Existing Relationship subsection
    relationship_fields = []
    if first_order_date:
        relationship_fields.append(
            ReportField(label="First Order", value=first_order_date, source="SAP")
        )
    if last_order_date:
        relationship_fields.append(
            ReportField(label="Last Order", value=last_order_date, source="SAP")
        )
    if total_orders is not None:
        relationship_fields.append(
            ReportField(label="Total Orders", value=str(total_orders), source="SAP")
        )
    if total_revenue is not None:
        if total_revenue >= 1_000_000:
            revenue_str = f"{currency} {total_revenue / 1_000_000:.2f}M"
        else:
            revenue_str = f"{currency} {total_revenue:,.0f}"
        relationship_fields.append(
            ReportField(
                label="Total Revenue",
                value=revenue_str,
                field_type="currency",
                source="SAP",
            )
        )
    if relationship_fields:
        subsections.append(
            ReportSubsection(title="Order History", fields=relationship_fields)
        )

    # Build CEC Metrics subsection (lifetime value, deal history)
    cec_fields = []
    if lifetime_value is not None:
        if lifetime_value >= 1_000_000:
            ltv_str = f"{currency} {lifetime_value / 1_000_000:.2f}M"
        else:
            ltv_str = f"{currency} {lifetime_value:,.0f}"
        cec_fields.append(
            ReportField(
                label="Lifetime Value",
                value=ltv_str,
                field_type="currency",
                source="CEC",
            )
        )
    if won_deals_count is not None or lost_deals_count is not None:
        won = won_deals_count or 0
        lost = lost_deals_count or 0
        cec_fields.append(
            ReportField(
                label="Deal History",
                value=f"{won} won, {lost} lost",
                source="CEC",
            )
        )
    if cec_fields:
        subsections.append(ReportSubsection(title="Customer Value", fields=cec_fields))

    # Build Pipeline subsection (CEC opportunities)
    pipeline_fields = []
    if open_opportunities_count is not None:
        opp_count = open_opportunities_count
        if open_pipeline_value is not None:
            if open_pipeline_value >= 1_000_000:
                val_str = f"{currency} {open_pipeline_value / 1_000_000:.2f}M"
            else:
                val_str = f"{currency} {open_pipeline_value:,.0f}"
            opp_str = f"{opp_count} ({val_str})"
        else:
            opp_str = str(opp_count)
        pipeline_fields.append(
            ReportField(
                label="Open Opportunities",
                value=opp_str,
                source="CEC",
            )
        )
    elif pipeline_opportunities is not None:
        # Fallback to legacy pipeline_opportunities if CEC data not available
        pipeline_fields.append(
            ReportField(
                label="Pipeline Opportunities",
                value=str(pipeline_opportunities),
                source="CRM",
            )
        )
    if next_expected_close:
        pipeline_fields.append(
            ReportField(
                label="Next Expected Close",
                value=next_expected_close,
                source="CEC",
            )
        )
    if pipeline_value is not None and open_pipeline_value is None:
        # Fallback to legacy pipeline_value if CEC data not available
        if pipeline_value >= 1_000_000:
            pipeline_str = f"{currency} {pipeline_value / 1_000_000:.2f}M"
        else:
            pipeline_str = f"{currency} {pipeline_value:,.0f}"
        pipeline_fields.append(
            ReportField(
                label="Pipeline Value",
                value=pipeline_str,
                field_type="currency",
                source="CRM",
            )
        )
    if pipeline_fields:
        subsections.append(
            ReportSubsection(title="Open Pipeline", fields=pipeline_fields)
        )

    # Build Contracts subsection
    contract_fields = []
    if active_contracts is not None:
        contracts_badge = "Active" if active_contracts > 0 else "None"
        contract_fields.append(
            ReportField(
                label="Active Contracts",
                value=str(active_contracts),
                badge=contracts_badge,
                source="SAP",
            )
        )
    if contract_fields:
        subsections.append(ReportSubsection(title="Contracts", fields=contract_fields))

    # Build Installed Base subsection
    if installed_base_units is not None:
        ib_fields = [
            ReportField(
                label="Units in Fleet", value=str(installed_base_units), source="SAP"
            )
        ]
        subsections.append(ReportSubsection(title="Installed Base", fields=ib_fields))

    # Determine status based on relationship
    if relationship_status == "Existing Customer":
        status = SectionStatus.NO_ADVERSE_FINDINGS
    elif relationship_status == "Dormant":
        status = SectionStatus.ADVERSE_FINDINGS
    else:  # New Prospect
        status = SectionStatus.INFO

    # Build source string with earliest record date if available
    source = "CEC"
    if first_order_date:
        source = f"CEC, Records from {first_order_date}"

    return ReportSection(
        id="business_context",
        title="Business Context",
        icon="🤝",
        status=status,
        source=source,
        fields=fields,
        subsections=subsections,
    )


def build_tprm_section(
    supplier_name: Optional[str] = None,
    supplier_id: Optional[str] = None,
    tprm_status: Optional[str] = None,
    inherent_risk_score: Optional[float] = None,
    overall_risk_score: Optional[float] = None,
    supplier_status: Optional[str] = None,
    due_diligence_status: Optional[str] = None,
    questionnaire_scores: Optional[list[dict]] = None,
    last_assessment_date: Optional[str] = None,
) -> ReportSection:
    """Build Third-Party Risk Management (TPRM) section from Aravo data.

    Args:
        supplier_name: Supplier name from Aravo
        supplier_id: Aravo supplier ID
        tprm_status: TPRM status (NO_ADVERSE_FINDINGS, ADVERSE_FINDINGS, etc.)
        inherent_risk_score: Inherent risk score (0-100)
        overall_risk_score: Calculated overall risk score (0-100)
        supplier_status: Aravo supplier status (Approved, Pending, etc.)
        due_diligence_status: Due diligence workflow status
        questionnaire_scores: List of questionnaire scores
        last_assessment_date: Date of last TPRM assessment

    Returns:
        ReportSection for TPRM
    """
    fields = []

    if supplier_name:
        fields.append(
            ReportField(label="Supplier Name", value=supplier_name, source="Aravo")
        )

    if supplier_id:
        fields.append(ReportField(label="Aravo ID", value=supplier_id, source="Aravo"))

    if supplier_status:
        status_type = (
            "success"
            if supplier_status.lower() in ("approved", "active")
            else "warning"
        )
        fields.append(
            ReportField(
                label="Supplier Status",
                value=supplier_status,
                field_type="status",
                status=status_type,
                source="Aravo",
            )
        )

    if inherent_risk_score is not None:
        risk_badge = None
        if inherent_risk_score >= 80:
            risk_badge = "Low Risk"
        elif inherent_risk_score >= 60:
            risk_badge = "Medium Risk"
        else:
            risk_badge = "High Risk"
        fields.append(
            ReportField(
                label="Inherent Risk Score",
                value=f"{inherent_risk_score:.0f}/100",
                badge=risk_badge,
                source="Aravo",
            )
        )

    if overall_risk_score is not None:
        fields.append(
            ReportField(
                label="Overall Risk Score",
                value=f"{overall_risk_score:.0f}/100",
                source="Aravo",
            )
        )

    if due_diligence_status:
        dd_status_type = (
            "success" if due_diligence_status.lower() == "completed" else "warning"
        )
        fields.append(
            ReportField(
                label="Due Diligence",
                value=due_diligence_status,
                field_type="status",
                status=dd_status_type,
                source="Aravo",
            )
        )

    if last_assessment_date:
        fields.append(
            ReportField(
                label="Last Assessment", value=last_assessment_date, source="Aravo"
            )
        )

    # Build questionnaire subsection if available
    subsections = []
    if questionnaire_scores:
        q_fields = []
        for q in questionnaire_scores[:3]:  # Limit to 3 questionnaires
            score = q.get("score", 0)
            max_score = q.get("max_score", 100)
            pct = (score / max_score * 100) if max_score > 0 else 0
            q_fields.append(
                ReportField(
                    label=q.get("name", "Questionnaire"),
                    value=f"{score:.0f}/{max_score:.0f} ({pct:.0f}%)",
                    source="Aravo",
                )
            )
        if q_fields:
            subsections.append(
                ReportSubsection(title="Questionnaire Scores", fields=q_fields)
            )

    # Determine section status based on TPRM status
    if tprm_status:
        if tprm_status == "NO_ADVERSE_FINDINGS":
            status = SectionStatus.NO_ADVERSE_FINDINGS
        elif tprm_status == "ADVERSE_FINDINGS":
            status = SectionStatus.ADVERSE_FINDINGS
        elif tprm_status == "UNDER_REVIEW":
            status = SectionStatus.ADVERSE_FINDINGS
        else:  # UNABLE_TO_VERIFY
            status = SectionStatus.UNABLE_TO_VERIFY
    else:
        status = SectionStatus.UNABLE_TO_VERIFY

    return ReportSection(
        id="tprm",
        title="Third-Party Risk Management",
        icon="🔒",
        status=status,
        source="Aravo",
        fields=fields,
        subsections=subsections,
    )
