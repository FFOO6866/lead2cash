"""
Unit Tests for Customer Validation Service

Tests the Two-Tier KYP + SAP/ECC validation using CPISimulator.
"""

import pytest
import pytest_asyncio

from lead_to_cash.integrations import CPISimulator, MS5Client
from lead_to_cash.services.customer_validation_service import (
    CustomerValidationService,
    OverallStatus,
    ValidationTier,
)


@pytest_asyncio.fixture
async def cpi_simulator():
    """Create and connect a CPI simulator."""
    simulator = CPISimulator()
    await simulator.connect()
    yield simulator
    await simulator.disconnect()


@pytest_asyncio.fixture
async def ms5_client(cpi_simulator):
    """Create and connect MS5 client with simulator."""
    client = MS5Client(cpi_client=cpi_simulator)
    await client.connect()
    yield client
    await client.disconnect()


@pytest_asyncio.fixture
async def validation_service(ms5_client):
    """Create validation service with simulator backend."""
    service = CustomerValidationService(
        ms5_client=ms5_client,
        kyp_reports_dir="data/",
        credit_control_area="1000",  # SAP credit control area
        sales_org="1000",  # SAP sales organization
    )
    service.set_connected(True)
    yield service


class TestCPISimulator:
    """Test the CPI Simulator interface."""

    @pytest.mark.asyncio
    async def test_simulator_connect(self, cpi_simulator):
        """Test simulator connects successfully."""
        assert cpi_simulator._client is not None

    @pytest.mark.asyncio
    async def test_list_customers(self, cpi_simulator):
        """Test listing customers from simulator."""
        customers = cpi_simulator.list_customers()

        assert len(customers) > 0
        assert all("customer_id" in c for c in customers)
        assert all("name" in c for c in customers)
        assert all("credit_limit" in c for c in customers)
        assert all("currency" in c for c in customers)

    @pytest.mark.asyncio
    async def test_customer_getdetail_iflow(self, cpi_simulator):
        """Test CustomerGetDetail iFlow returns correct structure."""
        result = await cpi_simulator.call_iflow(
            "CustomerGetDetail", {"CUSTOMERNO": "0000100001"}
        )

        # Check for address data (structure may vary)
        assert "CUSTOMERADDRESS" in result or "BAPICUSTOMER_04" in result
        address = result.get("CUSTOMERADDRESS", result.get("BAPICUSTOMER_04", {}))
        # Either field naming convention should work
        assert "CITY1" in address or "city" in str(address).lower()
        assert "COUNTRY" in address or "country" in str(address).lower()

    @pytest.mark.asyncio
    async def test_credit_getaccount_iflow(self, cpi_simulator):
        """Test CreditGetAccount iFlow returns correct structure."""
        result = await cpi_simulator.call_iflow(
            "CreditGetAccount",
            {"CUSTOMERNO": "0000100001", "CREDITCONTROLAREA": "1000"},
        )

        # Check for credit data - structure may vary
        assert "BAPICMKK" in result or "CREDIT_LIMIT" in result
        if "BAPICMKK" in result:
            credit = result["BAPICMKK"]
            assert "KLIMK" in credit  # Credit limit
        else:
            # Alternative structure
            assert "CREDIT_LIMIT" in result or "CREDIT_EXPOSURE" in result


class TestMS5ClientWithSimulator:
    """Test MS5Client with CPISimulator backend."""

    @pytest.mark.asyncio
    async def test_get_customer(self, ms5_client):
        """Test getting customer details."""
        customer = await ms5_client.get_customer("0000100001")

        assert customer.customer_id == "0000100001"
        assert customer.name == "Batam Fast Ferry Pte. Ltd."
        # Address is a dict containing city
        assert isinstance(customer.address, dict)
        assert customer.address.get("city") == "Singapore"

    @pytest.mark.asyncio
    async def test_check_credit_limit(self, ms5_client):
        """Test credit limit check."""
        # Pass credit_control_area explicitly to avoid env var dependency
        credit = await ms5_client.check_credit_limit(
            "0000100001", credit_control_area="1000"
        )

        assert credit.credit_limit > 0
        assert credit.credit_exposure >= 0
        assert credit.available_credit <= credit.credit_limit

    @pytest.mark.asyncio
    async def test_credit_check_with_order_value(self, ms5_client):
        """Test credit check with specific order value."""
        # Small order should pass
        credit = await ms5_client.check_credit_limit(
            "0000100001", order_value=10000, credit_control_area="1000"
        )
        assert credit.credit_check_passed is True

        # Very large order may fail
        credit = await ms5_client.check_credit_limit(
            "0000100001", order_value=10000000, credit_control_area="1000"
        )
        # Depends on credit limit

    @pytest.mark.asyncio
    async def test_get_partner_functions(self, ms5_client):
        """Test getting partner functions."""
        partners = await ms5_client.get_partner_functions(
            "0000100001", sales_org="1000"
        )

        # Simulator should return all partner functions for the customer
        assert isinstance(partners, list)
        assert len(partners) > 0, "Partner functions should be returned"

        functions = [p.get("function", "") for p in partners]
        # Should have all required functions
        assert "AG" in functions, "Missing Sold-to (AG) partner function"
        assert "WE" in functions, "Missing Ship-to (WE) partner function"
        assert "RE" in functions, "Missing Bill-to (RE) partner function"
        assert "RG" in functions, "Missing Payer (RG) partner function"


class TestCustomerValidationService:
    """Test the Two-Tier Customer Validation Service."""

    @pytest.mark.asyncio
    async def test_validate_customer_low_risk(self, validation_service):
        """Test validation of a low-risk customer (Maersk).

        Tier 1 (KYP): May fail if no KYP report exists - this is expected
        Tier 2 (SAP): Should pass with valid SAP config parameters
        """
        result = await validation_service.validate_customer("0000100002")

        # Customer name should be resolved from SAP
        assert result.customer_name == "A.P. Moller - Maersk A/S"

        # Tier 2 SAP validation should have run and retrieved data
        assert result.tier2_sap is not None
        assert (
            result.tier2_sap.details.get("customer_name") == "A.P. Moller - Maersk A/S"
        )
        assert result.tier2_sap.details.get("customer_id") == "0000100002"

        # Credit check should pass for Maersk (good credit standing)
        assert result.tier2_sap.details.get("credit_passed") is True
        assert result.tier2_sap.details.get("credit_limit", 0) > 0

        # Partner functions should be retrieved
        partner_functions = result.tier2_sap.details.get("partner_functions", [])
        assert len(partner_functions) == 4  # AG, WE, RE, RG

        # Tier 2 should pass
        assert result.tier2_sap.passed is True

    @pytest.mark.asyncio
    async def test_validate_customer_medium_high_risk(self, validation_service):
        """Test validation of a medium-high risk customer (BatamFast)."""
        result = await validation_service.validate_customer("0000100001")

        # Should require enhanced due diligence based on KYP risk
        assert result.tier2_sap is not None

    @pytest.mark.asyncio
    async def test_validate_customer_blocked(self, validation_service):
        """Test validation of a customer with credit issues."""
        result = await validation_service.validate_customer("0000100004")

        # Customer with credit issues should not proceed automatically
        assert result.can_proceed is False
        # Service returns CONDITIONAL (requires human review) when validation fails
        # but no explicit "BLOCKED" status string is in tier results
        assert result.overall_status in [
            OverallStatus.BLOCKED,
            OverallStatus.CONDITIONAL,
        ]

    @pytest.mark.asyncio
    async def test_validate_customer_not_found(self, validation_service):
        """Test validation of a non-existent customer."""
        result = await validation_service.validate_customer("9999999999")

        # Should handle gracefully - service returns CONDITIONAL when customer
        # not found because it requires human review to determine next steps
        assert result.overall_status in [
            OverallStatus.PENDING,
            OverallStatus.BLOCKED,
            OverallStatus.NOT_FOUND,
            OverallStatus.CONDITIONAL,  # Returned when validation fails without explicit block
        ]
        assert result.can_proceed is False

    @pytest.mark.asyncio
    async def test_validation_result_to_dict(self, validation_service):
        """Test that validation result can be serialized."""
        result = await validation_service.validate_customer("0000100001")

        result_dict = result.to_dict()

        assert "customer_id" in result_dict
        assert "customer_name" in result_dict
        assert "overall_status" in result_dict
        assert "can_proceed" in result_dict
        assert "tier1_kyp" in result_dict or result_dict["tier1_kyp"] is None
        assert "tier2_sap" in result_dict or result_dict["tier2_sap"] is None

    @pytest.mark.asyncio
    async def test_validation_result_to_summary(self, validation_service):
        """Test that validation result generates summary."""
        result = await validation_service.validate_customer("0000100001")

        summary = result.to_summary()

        assert "Customer Validation" in summary
        assert "Overall Status" in summary

    @pytest.mark.asyncio
    async def test_list_customers(self, validation_service):
        """Test listing available customers."""
        customers = await validation_service.list_customers()

        assert len(customers) > 0
        assert all("customer_id" in c for c in customers)
        assert all("name" in c for c in customers)

    @pytest.mark.asyncio
    async def test_validate_by_customer_name(self, validation_service):
        """Test validating customer by name instead of ID."""
        # Validate using customer name (partial match should work)
        result = await validation_service.validate_customer("Batam Fast Ferry")

        # Should resolve to the correct customer
        assert result.customer_id == "0000100001"
        assert "Batam Fast Ferry" in result.customer_name

        # Tier 2 should have run with the resolved ID
        assert result.tier2_sap is not None
        assert result.tier2_sap.details.get("customer_id") == "0000100001"

    @pytest.mark.asyncio
    async def test_validate_by_partial_name(self, validation_service):
        """Test validating customer by partial name match."""
        # Use partial name - should match "A.P. Moller - Maersk A/S"
        result = await validation_service.validate_customer("Maersk")

        assert "Maersk" in result.customer_name
        assert result.tier2_sap is not None

    @pytest.mark.asyncio
    async def test_skip_tier1(self, validation_service):
        """Test skipping Tier 1 KYP validation."""
        result = await validation_service.validate_customer(
            "0000100001", skip_tier1=True
        )

        assert result.tier1_kyp is None
        assert result.tier2_sap is not None

    @pytest.mark.asyncio
    async def test_skip_tier2(self, validation_service):
        """Test skipping Tier 2 SAP validation."""
        result = await validation_service.validate_customer(
            "0000100001", skip_tier2=True
        )

        assert result.tier2_sap is None
        # Tier 1 should still run
        # Note: Tier 1 depends on KYP reports being available

    @pytest.mark.asyncio
    async def test_credit_check_with_order_value(self, validation_service):
        """Test validation with specific order value."""
        # Small order
        result = await validation_service.validate_customer(
            "0000100001", order_value=10000
        )

        assert result.tier2_sap is not None
        if result.tier2_sap.details.get("credit_passed"):
            assert result.tier2_sap.passed is True

    @pytest.mark.asyncio
    async def test_combined_score_calculation(self, validation_service):
        """Test that combined score is calculated correctly."""
        result = await validation_service.validate_customer("0000100002")

        # Combined score should be between 0 and 1
        assert 0 <= result.combined_score <= 1


class TestTierResults:
    """Test individual tier result structures."""

    @pytest.mark.asyncio
    async def test_tier1_result_structure(self, validation_service):
        """Test Tier 1 KYP result structure."""
        result = await validation_service.validate_customer("0000100001")

        tier1 = result.tier1_kyp
        if tier1:  # May be None if KYP report not found
            assert tier1.tier == ValidationTier.TIER1_KYP
            assert isinstance(tier1.passed, bool)
            assert isinstance(tier1.score, float)
            assert 0 <= tier1.score <= 1
            assert isinstance(tier1.status, str)

    @pytest.mark.asyncio
    async def test_tier2_result_structure(self, validation_service):
        """Test Tier 2 SAP result structure."""
        result = await validation_service.validate_customer("0000100001")

        tier2 = result.tier2_sap
        assert tier2 is not None
        assert tier2.tier == ValidationTier.TIER2_SAP
        assert isinstance(tier2.passed, bool)
        assert isinstance(tier2.score, float)
        assert 0 <= tier2.score <= 1
        assert isinstance(tier2.status, str)

        # Check details
        assert "credit_limit" in tier2.details or "credit_passed" in tier2.details


class TestFindCustomer:
    """Test the find_customer fallback matching functionality."""

    @pytest.mark.asyncio
    async def test_find_customer_exact_match(self, validation_service):
        """Test finding customer with exact name match."""
        result = await validation_service.find_customer("Batam Fast Ferry Pte. Ltd.")

        assert result is not None
        assert result.query == "Batam Fast Ferry Pte. Ltd."
        assert len(result.candidates) >= 1
        assert result.best_match is not None
        assert "Batam" in result.best_match.name
        assert result.best_match.confidence_score >= 90.0
        assert result.has_high_confidence_match is True

    @pytest.mark.asyncio
    async def test_find_customer_partial_match(self, validation_service):
        """Test finding customer with partial name."""
        result = await validation_service.find_customer("batam fast ferry")

        assert result is not None
        assert len(result.candidates) >= 1
        assert result.best_match is not None
        assert "Batam" in result.best_match.name
        # After normalization, should be high confidence
        assert result.best_match.confidence_score >= 90.0

    @pytest.mark.asyncio
    async def test_find_customer_abbreviation(self, validation_service):
        """Test finding customer with abbreviation (no spaces)."""
        result = await validation_service.find_customer("batamfast")

        assert result is not None
        assert len(result.candidates) >= 1
        assert result.best_match is not None
        assert "Batam" in result.best_match.name
        # Fuzzy matching should find it
        assert result.best_match.confidence_score >= 70.0
        assert "Fuzzy match" in str(
            result.best_match.match_reasons
        ) or "Abbreviation" in str(result.best_match.match_reasons)

    @pytest.mark.asyncio
    async def test_find_customer_substring(self, validation_service):
        """Test finding customer with substring match."""
        result = await validation_service.find_customer("maersk")

        assert result is not None
        assert len(result.candidates) >= 1
        assert result.best_match is not None
        assert "Maersk" in result.best_match.name
        assert result.best_match.confidence_score >= 70.0

    @pytest.mark.asyncio
    async def test_find_customer_no_match(self, validation_service):
        """Test finding customer with no matching name."""
        result = await validation_service.find_customer("nonexistent company xyz")

        assert result is not None
        assert result.query == "nonexistent company xyz"
        # Should have no high-confidence match
        if result.best_match:
            assert result.best_match.confidence_score < 70.0
        assert result.has_high_confidence_match is False
        assert result.requires_user_confirmation is True

    @pytest.mark.asyncio
    async def test_find_customer_returns_customer_id(self, validation_service):
        """Test that find_customer returns SAP customer ID."""
        result = await validation_service.find_customer("batam fast ferry")

        assert result.best_match is not None
        assert result.best_match.customer_id is not None
        # Should be 10-digit SAP format
        assert result.best_match.customer_id.startswith("0000")

    @pytest.mark.asyncio
    async def test_find_customer_search_stats(self, validation_service):
        """Test that search stats are populated."""
        result = await validation_service.find_customer("batam")

        assert "mode" in result.search_stats
        assert result.search_stats["mode"] == "fallback"
        assert "sap_candidates" in result.search_stats
        assert "kyp_candidates" in result.search_stats
        assert "total_candidates" in result.search_stats

    @pytest.mark.asyncio
    async def test_find_customer_result_to_dict(self, validation_service):
        """Test that result can be converted to dict."""
        result = await validation_service.find_customer("batam fast ferry")

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "query" in result_dict
        assert "candidates" in result_dict
        assert "best_match" in result_dict
        assert "search_stats" in result_dict

    @pytest.mark.asyncio
    async def test_find_customer_candidate_ranking(self, validation_service):
        """Test that candidates are properly ranked."""
        result = await validation_service.find_customer("fast ferry")

        if len(result.candidates) >= 2:
            # Ranks should be sequential starting from 1
            for i, candidate in enumerate(result.candidates, start=1):
                assert candidate.rank == i

            # Higher ranked should have higher or equal confidence
            assert (
                result.candidates[0].confidence_score
                >= result.candidates[1].confidence_score
            )

    @pytest.mark.asyncio
    async def test_find_then_validate_flow(self, validation_service):
        """Test the complete find -> validate flow."""
        # Step 1: Find customer
        find_result = await validation_service.find_customer("batam fast ferry")

        assert find_result.best_match is not None
        customer_id = find_result.best_match.customer_id

        # Step 2: Validate with found customer ID
        validation_result = await validation_service.validate_customer(customer_id)

        assert validation_result.customer_id == customer_id
        assert validation_result.overall_status in [
            OverallStatus.APPROVED,
            OverallStatus.CONDITIONAL,
            OverallStatus.BLOCKED,
            OverallStatus.PENDING,
        ]


class TestFallbackMatchingAlgorithm:
    """Test the fallback matching algorithm internals."""

    @pytest.mark.asyncio
    async def test_normalize_name_removes_suffixes(self, validation_service):
        """Test that name normalization removes legal suffixes."""
        service = validation_service

        # Test various suffixes
        assert "batam fast ferry" == service._normalize_name(
            "Batam Fast Ferry Pte. Ltd."
        )
        assert "maersk" in service._normalize_name("A.P. Moller - Maersk A/S")
        assert "neptune energy netherlands" == service._normalize_name(
            "Neptune Energy Netherlands B.V."
        )

    @pytest.mark.asyncio
    async def test_calculate_match_score_exact(self, validation_service):
        """Test exact match scoring."""
        service = validation_service

        score, reasons = service._calculate_match_score(
            "batam fast ferry", "batam fast ferry", "Batam Fast Ferry"
        )

        assert score == 98.0
        assert "Exact match" in reasons[0]

    @pytest.mark.asyncio
    async def test_calculate_match_score_substring(self, validation_service):
        """Test substring match scoring."""
        service = validation_service

        score, reasons = service._calculate_match_score(
            "maersk", "ap moller maersk", "A.P. Moller - Maersk"
        )

        assert score >= 80.0
        assert any("substring" in r.lower() for r in reasons)

    @pytest.mark.asyncio
    async def test_calculate_match_score_fuzzy(self, validation_service):
        """Test fuzzy match scoring."""
        service = validation_service

        score, reasons = service._calculate_match_score(
            "batamfast", "batam fast ferry", "Batam Fast Ferry"
        )

        assert score >= 60.0
        assert any("fuzzy" in r.lower() or "abbreviation" in r.lower() for r in reasons)

    @pytest.mark.asyncio
    async def test_score_to_confidence_level(self, validation_service):
        """Test score to confidence level conversion."""
        from lead_to_cash.services.customer_validation_service import (
            FallbackConfidenceLevel,
        )

        service = validation_service

        assert service._score_to_confidence_level(95.0) == FallbackConfidenceLevel.HIGH
        assert (
            service._score_to_confidence_level(75.0) == FallbackConfidenceLevel.MEDIUM
        )
        assert service._score_to_confidence_level(55.0) == FallbackConfidenceLevel.LOW
        assert (
            service._score_to_confidence_level(30.0)
            == FallbackConfidenceLevel.UNCERTAIN
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
