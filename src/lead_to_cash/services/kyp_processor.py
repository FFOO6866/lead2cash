"""
KYP (Know Your Partner) Report Processor

Processes KYP compliance reports for Tier 1 due diligence assessment.
Parses Word documents (.docx) and extracts risk ratings, compliance findings,
and approval recommendations.

KYP Risk Categories (per RRPS KYP Framework):
    - Country/Geographic Risk: Jurisdiction-based corruption indices
    - Sector Risk: Industry-specific regulatory exposure
    - Ownership & Transparency Risk: UBO disclosure, beneficial ownership
    - Regulatory/Legal Risk: Historical enforcement actions, legal history
    - ABC/Ethics Program Maturity: Anti-bribery policies, training
    - Financial Risk: Audited financials, credit standing

Risk Ratings:
    - LOW: Minimal risk, standard monitoring
    - MEDIUM: Moderate risk, enhanced monitoring
    - MEDIUM-HIGH: Elevated risk, requires EDD
    - HIGH: Significant risk, requires senior approval

Usage:
    from lead_to_cash.services.kyp_processor import KYPProcessor

    processor = KYPProcessor(reports_directory="data/")
    await processor.load_all_reports()  # Load all .docx files from directory

    assessment = await processor.get_risk_assessment("BatamFast")
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class RiskLevel(str, Enum):
    """KYP Risk rating levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    MEDIUM_HIGH = "MEDIUM-HIGH"
    HIGH = "HIGH"
    NOT_ASSESSED = "NOT_ASSESSED"


class ApprovalStatus(str, Enum):
    """KYP approval recommendation status."""

    APPROVED = "APPROVED"
    CONDITIONAL_APPROVAL = "CONDITIONAL_APPROVAL"
    REJECTED = "REJECTED"
    PENDING_EDD = "PENDING_EDD"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass
class RiskCategory:
    """Individual risk category assessment."""

    category: str
    rating: RiskLevel
    description: str
    findings: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)


@dataclass
class KYPReport:
    """Parsed KYP compliance report."""

    partner_name: str
    partner_legal_entity: str
    report_date: datetime
    classification: str = "Internal Compliance – Confidential"

    business_description: str = ""
    founded: str = ""
    geographies: list[str] = field(default_factory=list)

    overall_risk_rating: RiskLevel = RiskLevel.NOT_ASSESSED
    risk_categories: list[RiskCategory] = field(default_factory=list)

    regulatory_history: list[str] = field(default_factory=list)
    legal_history: list[str] = field(default_factory=list)
    compliance_program_status: str = ""
    financial_standing: str = ""

    approval_status: ApprovalStatus = ApprovalStatus.NOT_ASSESSED
    approval_conditions: list[str] = field(default_factory=list)
    required_mitigations: list[str] = field(default_factory=list)

    source_file: str = ""
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "partner_name": self.partner_name,
            "partner_legal_entity": self.partner_legal_entity,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "classification": self.classification,
            "business_description": self.business_description,
            "founded": self.founded,
            "geographies": self.geographies,
            "overall_risk_rating": self.overall_risk_rating.value,
            "risk_categories": [
                {
                    "category": rc.category,
                    "rating": rc.rating.value,
                    "description": rc.description,
                    "findings": rc.findings,
                    "mitigations": rc.mitigations,
                }
                for rc in self.risk_categories
            ],
            "regulatory_history": self.regulatory_history,
            "legal_history": self.legal_history,
            "compliance_program_status": self.compliance_program_status,
            "financial_standing": self.financial_standing,
            "approval_status": self.approval_status.value,
            "approval_conditions": self.approval_conditions,
            "required_mitigations": self.required_mitigations,
            "source_file": self.source_file,
            "processed_at": self.processed_at.isoformat(),
        }


@dataclass
class KYPAssessmentResult:
    """Result of KYP compliance assessment for customer validation."""

    partner_name: str
    kyp_status: str  # PASSED, FAILED, REQUIRES_EDD, NOT_FOUND
    risk_rating: RiskLevel
    approval_status: ApprovalStatus
    can_proceed: bool
    requires_enhanced_dd: bool
    issues: list[str]
    conditions: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "partner_name": self.partner_name,
            "kyp_status": self.kyp_status,
            "risk_rating": self.risk_rating.value,
            "approval_status": self.approval_status.value,
            "can_proceed": self.can_proceed,
            "requires_enhanced_dd": self.requires_enhanced_dd,
            "issues": self.issues,
            "conditions": self.conditions,
            "summary": self.summary,
        }


# =============================================================================
# Name Lookup Table
# =============================================================================

KYP_NAME_LOOKUP: dict[str, str] = {
    # Batam Fast Ferry - maps to normalized partner name from report
    "batamfast": "batam fast ferry pte ltd",
    "batam fast": "batam fast ferry pte ltd",
    "batam fast ferry": "batam fast ferry pte ltd",
    "batam fast ferry pte ltd": "batam fast ferry pte ltd",
    "0000100001": "batam fast ferry pte ltd",  # SAP customer ID
    # Maersk
    "maersk": "maersk",
    "maersk line": "maersk",
    "ap moller": "maersk",
    "ap moller - maersk": "maersk",
    "a p moller - maersk a/s": "maersk",
    "0000100002": "maersk",  # SAP customer ID
    # Neptune Energy
    "neptune": "neptune",
    "neptune energy": "neptune",
    # Blocked partners
    "blocked marine": "blocked_marine",
    "blocked": "blocked_marine",
}


# =============================================================================
# KYP Document Parser
# =============================================================================


class KYPDocumentParser:
    """Parser for KYP compliance documents in .docx format."""

    # Risk rating patterns
    RISK_PATTERNS = {
        RiskLevel.HIGH: [r"\bHIGH\b", r"\bhigh\s+risk\b"],
        RiskLevel.MEDIUM_HIGH: [r"\bMEDIUM-HIGH\b", r"\bmedium.?high\s+risk\b"],
        RiskLevel.MEDIUM: [r"\bMEDIUM\b(?!-)", r"\bmedium\s+risk\b"],
        RiskLevel.LOW: [r"\bLOW\b", r"\blow\s+risk\b"],
    }

    # Category names to look for
    RISK_CATEGORY_NAMES = [
        "Country/Geographic Risk",
        "Sector Risk",
        "Ownership & Transparency Risk",
        "Regulatory/Legal Risk",
        "ABC/Ethics Program Maturity",
        "Financial Risk",
    ]

    def parse(self, text: str, source_file: str = "") -> KYPReport:
        """
        Parse KYP document text into structured report.

        Args:
            text: Full text content from .docx file
            source_file: Source file name for reference

        Returns:
            KYPReport with extracted data
        """
        # Extract partner name
        partner_name = self._extract_partner_name(text)
        legal_entity = self._extract_legal_entity(text)

        # Extract date
        report_date = self._extract_date(text)

        # Extract overall risk rating
        overall_risk = self._extract_overall_risk_rating(text)

        # Extract risk categories
        risk_categories = self._extract_risk_categories(text)

        # Extract approval status
        approval_status = self._extract_approval_status(text)

        # Extract regulatory history
        regulatory_history = self._extract_regulatory_history(text)

        # Extract required mitigations
        required_mitigations = self._extract_mitigations(text)

        # Extract business description
        business_desc = self._extract_business_description(text)

        return KYPReport(
            partner_name=partner_name,
            partner_legal_entity=legal_entity or partner_name,
            report_date=report_date,
            business_description=business_desc,
            overall_risk_rating=overall_risk,
            risk_categories=risk_categories,
            regulatory_history=regulatory_history,
            approval_status=approval_status,
            required_mitigations=required_mitigations,
            source_file=os.path.basename(source_file),
        )

    def _extract_partner_name(self, text: str) -> str:
        """Extract partner name from document."""
        patterns = [
            r"Partner:\s*(.+?)(?:\n|$)",
            r"Subject:\s*KYP.*?[–-]\s*(.+?)(?:\n|$)",
            r"KYP.*?Report.*?[–-]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Remove parenthetical info
                name = re.sub(r"\s*\([^)]*\)\s*", "", name)
                return name
        return "Unknown Partner"

    def _extract_legal_entity(self, text: str) -> Optional[str]:
        """Extract legal entity name."""
        patterns = [
            r"Legal [Ee]ntity:\s*(.+?)(?:\n|$)",
            r"Registered [Nn]ame:\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_date(self, text: str) -> datetime:
        """Extract report date."""
        patterns = [
            r"Date:\s*(\d{1,2}\s+\w+\s+\d{4})",
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                # Try different formats
                for fmt in ["%d %B %Y", "%Y-%m-%d", "%d %b %Y"]:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        return datetime.now(timezone.utc)

    def _extract_overall_risk_rating(self, text: str) -> RiskLevel:
        """Extract overall risk rating."""
        # Look for explicit overall/preliminary risk rating
        overall_pattern = r"(?:Preliminary\s+)?(?:Overall\s+)?Risk\s+Rating:\s*(LOW|MEDIUM-HIGH|MEDIUM|HIGH)"
        match = re.search(overall_pattern, text, re.IGNORECASE)
        if match:
            rating_str = match.group(1).upper()
            try:
                return RiskLevel(rating_str)
            except ValueError:
                pass

        # Count risk levels mentioned to infer overall
        for level, patterns in self.RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return level

        return RiskLevel.NOT_ASSESSED

    def _extract_risk_categories(self, text: str) -> list[RiskCategory]:
        """Extract individual risk category assessments."""
        categories = []

        for cat_name in self.RISK_CATEGORY_NAMES:
            # Look for the category section
            pattern = rf"{re.escape(cat_name)}[:\s]*([^•]*?)(?=(?:{self._category_pattern()})|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

            if match:
                section = match.group(1)
                rating = self._find_rating_in_section(section)
                findings = self._extract_findings(section)

                categories.append(
                    RiskCategory(
                        category=cat_name,
                        rating=rating,
                        description=section[:200].strip() if section else "",
                        findings=findings,
                    )
                )

        return categories

    def _category_pattern(self) -> str:
        """Build regex pattern for category names."""
        escaped = [re.escape(name) for name in self.RISK_CATEGORY_NAMES]
        return "|".join(escaped)

    def _find_rating_in_section(self, section: str) -> RiskLevel:
        """Find risk rating within a section."""
        for level, patterns in self.RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, section, re.IGNORECASE):
                    return level
        return RiskLevel.NOT_ASSESSED

    def _extract_findings(self, section: str) -> list[str]:
        """Extract bullet point findings from section."""
        findings = []
        # Match bullet points or numbered items
        bullet_pattern = r"[•\-]\s*(.+?)(?:\n|$)"
        matches = re.findall(bullet_pattern, section)
        for match in matches:
            finding = match.strip()
            if finding and len(finding) > 10:  # Skip short entries
                findings.append(finding)
        return findings[:5]  # Limit to 5 findings

    def _extract_approval_status(self, text: str) -> ApprovalStatus:
        """Extract approval recommendation status."""
        if re.search(r"Conditional\s+Approval", text, re.IGNORECASE):
            return ApprovalStatus.CONDITIONAL_APPROVAL
        elif re.search(r"\bApproved\b", text, re.IGNORECASE) and not re.search(
            r"not\s+approved|conditional", text, re.IGNORECASE
        ):
            return ApprovalStatus.APPROVED
        elif re.search(
            r"Rejected|Not\s+Approved|Do\s+Not\s+Proceed", text, re.IGNORECASE
        ):
            return ApprovalStatus.REJECTED
        elif re.search(r"Pending|EDD\s+Required", text, re.IGNORECASE):
            return ApprovalStatus.PENDING_EDD
        return ApprovalStatus.NOT_ASSESSED

    def _extract_regulatory_history(self, text: str) -> list[str]:
        """Extract regulatory/legal history items."""
        history = []
        # Look for year prefixed items
        year_pattern = r"(\d{4})\s*[–-]\s*(.+?)(?:\n|$)"
        matches = re.findall(year_pattern, text)
        for year, item in matches:
            history.append(f"{year} - {item.strip()}")
        return history[:10]

    def _extract_mitigations(self, text: str) -> list[str]:
        """Extract required mitigations."""
        mitigations = []

        # Look for mitigations section
        mit_pattern = (
            r"Required\s+(?:Risk\s+)?Mitigation[s]?.*?(?:\n)(.*?)(?=\n\d+\.\s+[A-Z]|$)"
        )
        match = re.search(mit_pattern, text, re.IGNORECASE | re.DOTALL)

        if match:
            section = match.group(1)
            items = re.findall(r"[•\-]\s*(.+?)(?:\n|$)", section)
            mitigations = [item.strip() for item in items if item.strip()]

        return mitigations[:10]

    def _extract_business_description(self, text: str) -> str:
        """Extract business description."""
        patterns = [
            r"Business\s+Description:\s*(.+?)(?:\n\n|$)",
            r"Partner\s+Overview.*?\n(.+?)(?:\n\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:500]
        return ""


# =============================================================================
# KYP Processor Implementation
# =============================================================================


class KYPProcessor:
    """
    KYP Report Processor for Tier 1 compliance assessment.

    Loads and parses KYP reports from .docx files, providing risk assessment
    data for customer validation workflows.

    Usage:
        # Initialize with reports directory
        processor = KYPProcessor(reports_directory="data/")

        # Load all reports from directory
        await processor.load_all_reports()

        # Get assessment for customer
        assessment = await processor.get_risk_assessment("BatamFast")
    """

    def __init__(self, reports_directory: Optional[str] = None):
        """
        Initialize KYP processor.

        Args:
            reports_directory: Directory containing KYP report files (.docx)
        """
        self._reports_dir = reports_directory
        self._cached_reports: dict[str, KYPReport] = {}
        self._parser = KYPDocumentParser()
        self._loaded = False

    async def load_all_reports(self) -> int:
        """
        Load all KYP reports from the reports directory.

        Returns:
            Number of reports loaded
        """
        if not self._reports_dir:
            logger.warning("No reports directory configured")
            return 0

        reports_path = Path(self._reports_dir)
        if not reports_path.exists():
            logger.warning(f"Reports directory not found: {self._reports_dir}")
            return 0

        count = 0
        for docx_file in reports_path.glob("*.docx"):
            # Skip temp files
            if docx_file.name.startswith("~"):
                continue

            report = await self.load_report(str(docx_file))
            if report:
                count += 1
                logger.info(
                    f"Loaded KYP report: {report.partner_name} ({report.overall_risk_rating.value})"
                )

        self._loaded = True
        logger.info(f"Loaded {count} KYP reports from {self._reports_dir}")
        return count

    async def load_report(self, file_path: str) -> Optional[KYPReport]:
        """
        Load KYP report from a .docx file.

        Args:
            file_path: Path to KYP report file

        Returns:
            Parsed KYPReport or None if parsing fails
        """
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"KYP report file not found: {file_path}")
            return None

        if path.suffix.lower() != ".docx":
            logger.warning(f"Unsupported file format: {path.suffix}")
            return None

        try:
            # Import python-docx
            from docx import Document

            doc = Document(file_path)

            # Extract all text from paragraphs
            text_parts = []
            for para in doc.paragraphs:
                text_parts.append(para.text)

            # Also extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        text_parts.append(cell.text)

            text = "\n".join(text_parts)

            # Parse the text
            report = self._parser.parse(text, file_path)

            # Cache the report with normalized name key
            key = self._normalize_name(report.partner_name)
            self._cached_reports[key] = report

            return report

        except ImportError:
            logger.warning(
                "python-docx not installed. Install with: pip install python-docx"
            )
            return None
        except Exception as e:
            logger.error(f"Error loading KYP report {file_path}: {e}")
            return None

    async def get_risk_assessment(self, partner_name: str) -> KYPAssessmentResult:
        """
        Get KYP risk assessment for a partner.

        Args:
            partner_name: Partner name or identifier

        Returns:
            KYPAssessmentResult with compliance status
        """
        # Load reports if not already loaded
        if not self._loaded and self._reports_dir:
            await self.load_all_reports()

        # Normalize and lookup
        key = self._normalize_name(partner_name)

        # Check name lookup table
        if key in KYP_NAME_LOOKUP:
            key = KYP_NAME_LOOKUP[key]

        # Try partial match
        if key not in self._cached_reports:
            for name_key in KYP_NAME_LOOKUP:
                if name_key in key or key in name_key:
                    key = KYP_NAME_LOOKUP[name_key]
                    break

        # Also try to match against cached report names
        if key not in self._cached_reports:
            for cached_key in self._cached_reports:
                if key in cached_key or cached_key in key:
                    key = cached_key
                    break

        report = self._cached_reports.get(key)

        if not report:
            return KYPAssessmentResult(
                partner_name=partner_name,
                kyp_status="NOT_FOUND",
                risk_rating=RiskLevel.NOT_ASSESSED,
                approval_status=ApprovalStatus.NOT_ASSESSED,
                can_proceed=False,
                requires_enhanced_dd=True,
                issues=["No KYP report found for this partner"],
                conditions=["Full KYP assessment required before engagement"],
                summary=f"No KYP compliance report found for '{partner_name}'. "
                "A full Know Your Partner assessment must be completed before any business engagement.",
            )

        # Determine if can proceed
        can_proceed = report.approval_status in [
            ApprovalStatus.APPROVED,
            ApprovalStatus.CONDITIONAL_APPROVAL,
        ]

        requires_edd = (
            report.overall_risk_rating in [RiskLevel.MEDIUM_HIGH, RiskLevel.HIGH]
            or report.approval_status == ApprovalStatus.CONDITIONAL_APPROVAL
        )

        # Collect issues from risk categories
        issues = []
        for rc in report.risk_categories:
            if rc.rating in [RiskLevel.MEDIUM_HIGH, RiskLevel.HIGH]:
                issues.extend(rc.findings)

        issues.extend(report.regulatory_history)

        # Build status
        blocked = report.approval_status == ApprovalStatus.REJECTED
        if blocked:
            kyp_status = "FAILED"
        elif requires_edd:
            kyp_status = "REQUIRES_EDD"
        elif can_proceed:
            kyp_status = "PASSED"
        else:
            kyp_status = "PENDING"

        summary = self._generate_summary(report, kyp_status, requires_edd)

        return KYPAssessmentResult(
            partner_name=report.partner_name,
            kyp_status=kyp_status,
            risk_rating=report.overall_risk_rating,
            approval_status=report.approval_status,
            can_proceed=can_proceed and not blocked,
            requires_enhanced_dd=requires_edd,
            issues=issues[:10],
            conditions=report.approval_conditions + report.required_mitigations[:5],
            summary=summary,
        )

    def _generate_summary(
        self, report: KYPReport, kyp_status: str, requires_edd: bool
    ) -> str:
        """Generate human-readable summary of KYP assessment."""
        parts = [
            f"KYP Assessment for {report.partner_legal_entity}:",
            f"Overall Risk Rating: {report.overall_risk_rating.value}",
            f"Approval Status: {report.approval_status.value.replace('_', ' ').title()}",
        ]

        if kyp_status == "FAILED":
            parts.append(
                "BLOCKED: This partner has been rejected and cannot be engaged."
            )
        elif requires_edd:
            parts.append(
                "Enhanced Due Diligence (EDD) required before proceeding. "
                "See conditions for required mitigations."
            )
        elif kyp_status == "PASSED":
            parts.append("Partner has been approved with standard monitoring.")

        if report.regulatory_history:
            parts.append(
                f"Note: {len(report.regulatory_history)} regulatory/legal finding(s) on record."
            )

        return " ".join(parts)

    def _normalize_name(self, name: str) -> str:
        """Normalize partner name for lookup."""
        return name.lower().strip().replace(".", "").replace(",", "")

    def list_reports(self) -> list[dict[str, Any]]:
        """List all cached KYP reports."""
        return [
            {
                "partner_name": r.partner_name,
                "legal_entity": r.partner_legal_entity,
                "risk_rating": r.overall_risk_rating.value,
                "approval_status": r.approval_status.value,
                "report_date": r.report_date.isoformat() if r.report_date else None,
                "source_file": r.source_file,
            }
            for r in self._cached_reports.values()
        ]

    def get_report(self, partner_name: str) -> Optional[KYPReport]:
        """Get full KYP report for a partner."""
        key = self._normalize_name(partner_name)
        if key in KYP_NAME_LOOKUP:
            key = KYP_NAME_LOOKUP[key]
        return self._cached_reports.get(key)

    def add_report(self, report: KYPReport) -> None:
        """Add a report to the cache (for testing or manual loading)."""
        key = self._normalize_name(report.partner_name)
        self._cached_reports[key] = report
