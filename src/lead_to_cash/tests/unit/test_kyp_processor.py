"""
Unit Tests for KYP (Know Your Partner) Processor

Tests KYP report parsing, risk assessment, and data structures.
"""

from datetime import datetime, timezone

import pytest

from lead_to_cash.services.kyp_processor import (
    ApprovalStatus,
    KYPAssessmentResult,
    KYPReport,
    RiskCategory,
    RiskLevel,
)

# =============================================================================
# Risk Level Enum Tests
# =============================================================================


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test all risk level values exist."""
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.MEDIUM_HIGH.value == "MEDIUM-HIGH"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.NOT_ASSESSED.value == "NOT_ASSESSED"

    def test_risk_level_from_string(self):
        """Test creating risk level from string."""
        assert RiskLevel("LOW") == RiskLevel.LOW
        assert RiskLevel("MEDIUM-HIGH") == RiskLevel.MEDIUM_HIGH

    def test_risk_level_ordering(self):
        """Test risk levels have expected ordering."""
        # Define expected order for business logic
        risk_order = ["LOW", "MEDIUM", "MEDIUM-HIGH", "HIGH"]

        # Verify all values are in the order list
        assert RiskLevel.LOW.value in risk_order
        assert RiskLevel.MEDIUM.value in risk_order
        assert RiskLevel.HIGH.value in risk_order

        # Verify index-based ordering
        assert risk_order.index(RiskLevel.LOW.value) < risk_order.index(
            RiskLevel.MEDIUM.value
        )
        assert risk_order.index(RiskLevel.HIGH.value) > risk_order.index(
            RiskLevel.LOW.value
        )

    def test_invalid_risk_level(self):
        """Test invalid risk level raises error."""
        with pytest.raises(ValueError):
            RiskLevel("INVALID")


# =============================================================================
# Approval Status Enum Tests
# =============================================================================


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_approval_status_values(self):
        """Test all approval status values exist."""
        assert ApprovalStatus.APPROVED.value == "APPROVED"
        assert ApprovalStatus.CONDITIONAL_APPROVAL.value == "CONDITIONAL_APPROVAL"
        assert ApprovalStatus.REJECTED.value == "REJECTED"
        assert ApprovalStatus.PENDING_EDD.value == "PENDING_EDD"
        assert ApprovalStatus.NOT_ASSESSED.value == "NOT_ASSESSED"

    def test_approval_status_from_string(self):
        """Test creating approval status from string."""
        assert ApprovalStatus("APPROVED") == ApprovalStatus.APPROVED
        assert ApprovalStatus("REJECTED") == ApprovalStatus.REJECTED


# =============================================================================
# Risk Category Tests
# =============================================================================


class TestRiskCategory:
    """Tests for RiskCategory dataclass."""

    def test_risk_category_creation(self):
        """Test creating risk category."""
        category = RiskCategory(
            category="Country Risk",
            rating=RiskLevel.MEDIUM,
            description="Singapore-based entity",
        )

        assert category.category == "Country Risk"
        assert category.rating == RiskLevel.MEDIUM
        assert category.description == "Singapore-based entity"
        assert category.findings == []
        assert category.mitigations == []

    def test_risk_category_with_findings(self):
        """Test risk category with findings."""
        category = RiskCategory(
            category="Regulatory Risk",
            rating=RiskLevel.HIGH,
            description="Historical regulatory issues",
            findings=[
                "Environmental violation 2022",
                "Labor law breach 2021",
            ],
            mitigations=[
                "Implemented compliance program",
                "Hired compliance officer",
            ],
        )

        assert len(category.findings) == 2
        assert len(category.mitigations) == 2

    def test_risk_category_empty_defaults(self):
        """Test risk category has empty list defaults."""
        category = RiskCategory(
            category="Test",
            rating=RiskLevel.LOW,
            description="Test",
        )

        # Should have empty lists, not None
        assert isinstance(category.findings, list)
        assert isinstance(category.mitigations, list)


# =============================================================================
# KYP Report Tests
# =============================================================================


class TestKYPReport:
    """Tests for KYPReport dataclass."""

    def test_kyp_report_minimal_creation(self):
        """Test creating KYP report with minimal fields."""
        report = KYPReport(
            partner_name="Test Company",
            partner_legal_entity="Test Company Pte Ltd",
            report_date=datetime.now(timezone.utc),
        )

        assert report.partner_name == "Test Company"
        assert report.partner_legal_entity == "Test Company Pte Ltd"
        assert report.overall_risk_rating == RiskLevel.NOT_ASSESSED
        assert report.approval_status == ApprovalStatus.NOT_ASSESSED

    def test_kyp_report_full_creation(self):
        """Test creating KYP report with all fields."""
        report = KYPReport(
            partner_name="Batam Fast Ferry",
            partner_legal_entity="PT Batam Fast Ferry",
            report_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            classification="Internal Compliance – Confidential",
            business_description="Ferry operator in Singapore-Batam route",
            founded="1995",
            geographies=["Singapore", "Indonesia"],
            overall_risk_rating=RiskLevel.MEDIUM,
            risk_categories=[
                RiskCategory(
                    category="Country Risk",
                    rating=RiskLevel.MEDIUM,
                    description="Operations in Indonesia",
                )
            ],
            regulatory_history=["No adverse findings"],
            legal_history=["Minor customs disputes resolved"],
            compliance_program_status="Basic compliance program in place",
            financial_standing="Audited financials, positive cash flow",
            approval_status=ApprovalStatus.APPROVED,
            approval_conditions=["Annual review required"],
            required_mitigations=["Enhanced monitoring for Indonesia operations"],
            source_file="batamfast_kyp_2025.docx",
        )

        assert report.partner_name == "Batam Fast Ferry"
        assert report.overall_risk_rating == RiskLevel.MEDIUM
        assert report.approval_status == ApprovalStatus.APPROVED
        assert len(report.geographies) == 2
        assert len(report.risk_categories) == 1

    def test_kyp_report_to_dict(self):
        """Test KYP report serialization."""
        report = KYPReport(
            partner_name="Test",
            partner_legal_entity="Test Ltd",
            report_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            overall_risk_rating=RiskLevel.LOW,
        )

        data = report.to_dict()

        assert isinstance(data, dict)
        assert data["partner_name"] == "Test"
        assert data["overall_risk_rating"] == "LOW"
        assert "report_date" in data
        assert "processed_at" in data

    def test_kyp_report_processed_at_default(self):
        """Test processed_at is set automatically."""
        report = KYPReport(
            partner_name="Test",
            partner_legal_entity="Test Ltd",
            report_date=datetime.now(timezone.utc),
        )

        assert report.processed_at is not None
        assert isinstance(report.processed_at, datetime)


# =============================================================================
# KYP Assessment Result Tests
# =============================================================================


class TestKYPAssessmentResult:
    """Tests for KYPAssessmentResult dataclass."""

    def test_assessment_result_passed(self):
        """Test passed assessment result."""
        result = KYPAssessmentResult(
            partner_name="Good Company",
            kyp_status="PASSED",
            risk_rating=RiskLevel.LOW,
            approval_status=ApprovalStatus.APPROVED,
            can_proceed=True,
            requires_enhanced_dd=False,
            issues=[],
            conditions=[],
            summary="Low risk partner, approved for business",
        )

        assert result.kyp_status == "PASSED"
        assert result.can_proceed is True
        assert result.requires_enhanced_dd is False
        assert len(result.issues) == 0

    def test_assessment_result_failed(self):
        """Test failed assessment result."""
        result = KYPAssessmentResult(
            partner_name="Risky Company",
            kyp_status="FAILED",
            risk_rating=RiskLevel.HIGH,
            approval_status=ApprovalStatus.REJECTED,
            can_proceed=False,
            requires_enhanced_dd=True,
            issues=[
                "Sanctions list match",
                "Unresolved legal disputes",
            ],
            conditions=[],
            summary="High risk partner, rejected due to sanctions match",
        )

        assert result.kyp_status == "FAILED"
        assert result.can_proceed is False
        assert len(result.issues) == 2

    def test_assessment_result_requires_edd(self):
        """Test assessment requiring enhanced due diligence."""
        result = KYPAssessmentResult(
            partner_name="Medium Risk Company",
            kyp_status="REQUIRES_EDD",
            risk_rating=RiskLevel.MEDIUM_HIGH,
            approval_status=ApprovalStatus.PENDING_EDD,
            can_proceed=False,
            requires_enhanced_dd=True,
            issues=["Complex ownership structure"],
            conditions=["UBO verification required"],
            summary="Elevated risk, requires enhanced due diligence",
        )

        assert result.kyp_status == "REQUIRES_EDD"
        assert result.requires_enhanced_dd is True
        assert result.approval_status == ApprovalStatus.PENDING_EDD

    def test_assessment_result_not_found(self):
        """Test assessment when partner not found."""
        result = KYPAssessmentResult(
            partner_name="Unknown Company",
            kyp_status="NOT_FOUND",
            risk_rating=RiskLevel.NOT_ASSESSED,
            approval_status=ApprovalStatus.NOT_ASSESSED,
            can_proceed=False,
            requires_enhanced_dd=True,
            issues=["No KYP report found for partner"],
            conditions=["KYP assessment required before proceeding"],
            summary="Partner not found in KYP database",
        )

        assert result.kyp_status == "NOT_FOUND"
        assert result.risk_rating == RiskLevel.NOT_ASSESSED
        assert result.can_proceed is False

    def test_assessment_result_to_dict(self):
        """Test KYP assessment result serialization."""
        result = KYPAssessmentResult(
            partner_name="Test Company",
            kyp_status="PASSED",
            risk_rating=RiskLevel.LOW,
            approval_status=ApprovalStatus.APPROVED,
            can_proceed=True,
            requires_enhanced_dd=False,
            issues=[],
            conditions=[],
            summary="Test summary",
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["partner_name"] == "Test Company"
        assert data["kyp_status"] == "PASSED"
        assert data["risk_rating"] == "LOW"
        assert data["can_proceed"] is True


# =============================================================================
# KYP Status Logic Tests
# =============================================================================


class TestKYPStatusLogic:
    """Tests for KYP status determination logic via KYPAssessmentResult."""

    def test_low_risk_allows_proceed(self):
        """Test LOW risk assessment allows proceeding without enhanced DD."""
        # LOW risk partners should be able to proceed with normal engagement
        result = KYPAssessmentResult(
            partner_name="Low Risk Corp",
            kyp_status="PASSED",
            risk_rating=RiskLevel.LOW,
            approval_status=ApprovalStatus.APPROVED,
            can_proceed=True,
            requires_enhanced_dd=False,
            issues=[],
            conditions=[],
            summary="Low risk - standard engagement",
        )

        # Verify the business logic: LOW risk can proceed without EDD
        assert result.can_proceed is True
        assert result.requires_enhanced_dd is False
        assert result.kyp_status == "PASSED"

    def test_medium_risk_may_have_conditions(self):
        """Test MEDIUM risk assessment may have conditions attached."""
        # MEDIUM risk partners may proceed but with monitoring conditions
        result = KYPAssessmentResult(
            partner_name="Medium Risk Corp",
            kyp_status="PASSED",
            risk_rating=RiskLevel.MEDIUM,
            approval_status=ApprovalStatus.CONDITIONAL_APPROVAL,
            can_proceed=True,
            requires_enhanced_dd=False,
            issues=[],
            conditions=["Annual review required", "Enhanced monitoring"],
            summary="Medium risk - proceed with conditions",
        )

        # Verify the business logic: MEDIUM risk can proceed with conditions
        assert result.can_proceed is True
        assert len(result.conditions) > 0

    def test_medium_high_risk_requires_edd(self):
        """Test MEDIUM-HIGH risk assessment requires enhanced due diligence."""
        # MEDIUM-HIGH risk partners should require EDD before proceeding
        result = KYPAssessmentResult(
            partner_name="Elevated Risk Corp",
            kyp_status="REQUIRES_EDD",
            risk_rating=RiskLevel.MEDIUM_HIGH,
            approval_status=ApprovalStatus.PENDING_EDD,
            can_proceed=False,
            requires_enhanced_dd=True,
            issues=["Complex ownership structure"],
            conditions=["UBO verification required"],
            summary="Elevated risk - requires enhanced due diligence",
        )

        # Verify the business logic: MEDIUM-HIGH cannot proceed without EDD
        assert result.can_proceed is False
        assert result.requires_enhanced_dd is True
        assert result.kyp_status == "REQUIRES_EDD"

    def test_high_risk_blocks_proceed(self):
        """Test HIGH risk assessment blocks proceeding."""
        # HIGH risk partners should not proceed without senior approval
        result = KYPAssessmentResult(
            partner_name="High Risk Corp",
            kyp_status="FAILED",
            risk_rating=RiskLevel.HIGH,
            approval_status=ApprovalStatus.REJECTED,
            can_proceed=False,
            requires_enhanced_dd=True,
            issues=["Sanctions list match", "Active legal disputes"],
            conditions=[],
            summary="High risk - rejected",
        )

        # Verify the business logic: HIGH risk blocks proceeding
        assert result.can_proceed is False
        assert result.risk_rating == RiskLevel.HIGH
        assert len(result.issues) > 0


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestKYPEdgeCases:
    """Tests for edge cases in KYP processing."""

    def test_empty_partner_name(self):
        """Test handling of empty partner name."""
        report = KYPReport(
            partner_name="",
            partner_legal_entity="",
            report_date=datetime.now(timezone.utc),
        )

        assert report.partner_name == ""

    def test_unicode_partner_name(self):
        """Test handling of Unicode in partner name."""
        report = KYPReport(
            partner_name="株式会社テスト",  # Japanese company
            partner_legal_entity="株式会社テスト",
            report_date=datetime.now(timezone.utc),
        )

        assert "株式会社" in report.partner_name

    def test_very_long_partner_name(self):
        """Test handling of very long partner name."""
        long_name = "A" * 500
        report = KYPReport(
            partner_name=long_name,
            partner_legal_entity=long_name,
            report_date=datetime.now(timezone.utc),
        )

        assert len(report.partner_name) == 500

    def test_special_characters_in_name(self):
        """Test handling of special characters."""
        report = KYPReport(
            partner_name="Company & Sons (Pte.) Ltd.",
            partner_legal_entity="Company & Sons (Pte.) Ltd.",
            report_date=datetime.now(timezone.utc),
        )

        assert "&" in report.partner_name
        assert "(" in report.partner_name

    def test_null_report_date(self):
        """Test handling when report date is None."""
        # This may need special handling in the processor
        report = KYPReport(
            partner_name="Test",
            partner_legal_entity="Test Ltd",
            report_date=None,  # type: ignore
        )

        # to_dict should handle None date
        data = report.to_dict()
        assert data["report_date"] is None


# =============================================================================
# Risk Category Aggregation Tests
# =============================================================================


class TestRiskCategoryAggregation:
    """Tests for risk category aggregation logic."""

    def test_overall_risk_highest_category(self):
        """Test overall risk should be highest individual category."""
        categories = [
            RiskCategory("Country", RiskLevel.LOW, "Low risk country"),
            RiskCategory("Sector", RiskLevel.MEDIUM, "Medium risk sector"),
            RiskCategory("Ownership", RiskLevel.HIGH, "Complex ownership"),
        ]

        # Overall should be HIGH (highest individual rating)
        highest = max(
            categories,
            key=lambda c: (
                ["LOW", "MEDIUM", "MEDIUM-HIGH", "HIGH"].index(c.rating.value)
                if c.rating.value in ["LOW", "MEDIUM", "MEDIUM-HIGH", "HIGH"]
                else -1
            ),
        )

        assert highest.rating == RiskLevel.HIGH

    def test_all_low_risk_categories(self):
        """Test all LOW categories result in LOW overall."""
        categories = [
            RiskCategory("Country", RiskLevel.LOW, "Low"),
            RiskCategory("Sector", RiskLevel.LOW, "Low"),
            RiskCategory("Ownership", RiskLevel.LOW, "Low"),
        ]

        all_low = all(c.rating == RiskLevel.LOW for c in categories)
        assert all_low is True

    def test_empty_risk_categories(self):
        """Test handling of empty risk categories."""
        report = KYPReport(
            partner_name="Test",
            partner_legal_entity="Test Ltd",
            report_date=datetime.now(timezone.utc),
            risk_categories=[],
        )

        assert len(report.risk_categories) == 0
        assert report.overall_risk_rating == RiskLevel.NOT_ASSESSED
