"""
Unit Tests for Customer Matcher Agent

Tests the LLM-based customer matching functionality with mocked LLM responses.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from lead_to_cash.agents.customer_matcher_agent import (
    CustomerMatchCandidate,
    CustomerMatcherAgent,
    CustomerMatcherConfig,
    CustomerMatchResult,
    MatchConfidence,
    MatchSource,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return CustomerMatcherConfig(
        llm_provider="openai",
        model="gpt-4o",
        min_confidence_threshold=50.0,
        high_confidence_threshold=90.0,
        medium_confidence_threshold=70.0,
        max_candidates=10,
    )


@pytest.fixture
def mock_cpi_client():
    """Create mock CPI client with test customers."""
    mock = MagicMock()
    mock.list_customers.return_value = [
        {
            "customer_id": "0000100001",
            "name": "Batam Fast Ferry Pte. Ltd.",
            "city": "Singapore",
            "country": "SG",
            "credit_limit": 500000.00,
            "risk_category": "003",
        },
        {
            "customer_id": "0000100002",
            "name": "A.P. Moller - Maersk A/S",
            "city": "Copenhagen",
            "country": "DK",
            "credit_limit": 10000000.00,
            "risk_category": "001",
        },
        {
            "customer_id": "0000100003",
            "name": "Neptune Energy Netherlands B.V.",
            "city": "Den Haag",
            "country": "NL",
            "credit_limit": 2000000.00,
            "risk_category": "002",
        },
    ]
    return mock


@pytest.fixture
def mock_kyp_processor():
    """Create mock KYP processor with test reports."""
    mock = MagicMock()
    mock.list_reports.return_value = [
        {
            "partner_name": "batam fast ferry pte ltd",
            "legal_entity": "Batam Fast Ferry Pte. Ltd.",
            "risk_rating": "MEDIUM-HIGH",
            "approval_status": "CONDITIONAL_APPROVAL",
        },
        {
            "partner_name": "maersk",
            "legal_entity": "A.P. Moller - Maersk A/S",
            "risk_rating": "LOW",
            "approval_status": "APPROVED",
        },
    ]
    return mock


@pytest.fixture
def agent(config, mock_cpi_client, mock_kyp_processor):
    """Create agent with mocked dependencies."""
    return CustomerMatcherAgent(
        config=config,
        cpi_client=mock_cpi_client,
        kyp_processor=mock_kyp_processor,
    )


# =============================================================================
# Test Data Classes
# =============================================================================


class TestCustomerMatchCandidate:
    """Tests for CustomerMatchCandidate data class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        candidate = CustomerMatchCandidate(
            rank=1,
            name="Batam Fast Ferry Pte. Ltd.",
            customer_id="0000100001",
            source=MatchSource.SAP_CPI,
            confidence_score=95.0,
            confidence_level=MatchConfidence.HIGH,
            match_reasons=["Exact company name match"],
            sap_data={"credit_limit": 500000.0},
            kyp_data={"risk_rating": "MEDIUM-HIGH"},
        )

        result = candidate.to_dict()

        assert result["rank"] == 1
        assert result["name"] == "Batam Fast Ferry Pte. Ltd."
        assert result["customer_id"] == "0000100001"
        assert result["source"] == "SAP_CPI"
        assert result["confidence_score"] == 95.0
        assert result["confidence_level"] == "HIGH"
        assert "Exact company name match" in result["match_reasons"]

    def test_candidate_without_optional_data(self):
        """Test candidate with minimal data."""
        candidate = CustomerMatchCandidate(
            rank=1,
            name="Test Company",
            customer_id=None,
            source=MatchSource.KYP_REPORT,
            confidence_score=60.0,
            confidence_level=MatchConfidence.LOW,
            match_reasons=["Partial name match"],
        )

        result = candidate.to_dict()

        assert result["customer_id"] is None
        assert result["sap_data"] is None
        assert result["kyp_data"] is None


class TestCustomerMatchResult:
    """Tests for CustomerMatchResult data class."""

    def test_to_dict_with_candidates(self):
        """Test conversion with candidates."""
        candidate = CustomerMatchCandidate(
            rank=1,
            name="Test Company",
            customer_id="0000100001",
            source=MatchSource.BOTH,
            confidence_score=92.0,
            confidence_level=MatchConfidence.HIGH,
            match_reasons=["Exact match"],
        )

        result = CustomerMatchResult(
            query="test company",
            candidates=[candidate],
            best_match=candidate,
            has_high_confidence_match=True,
            requires_user_confirmation=False,
            search_stats={"sap_count": 3, "kyp_count": 2},
        )

        result_dict = result.to_dict()

        assert result_dict["query"] == "test company"
        assert len(result_dict["candidates"]) == 1
        assert result_dict["best_match"]["name"] == "Test Company"
        assert result_dict["has_high_confidence_match"] is True

    def test_get_candidate_by_rank(self):
        """Test retrieving candidate by rank."""
        candidates = [
            CustomerMatchCandidate(
                rank=1,
                name="First Match",
                customer_id="001",
                source=MatchSource.SAP_CPI,
                confidence_score=95.0,
                confidence_level=MatchConfidence.HIGH,
                match_reasons=["Best match"],
            ),
            CustomerMatchCandidate(
                rank=2,
                name="Second Match",
                customer_id="002",
                source=MatchSource.SAP_CPI,
                confidence_score=80.0,
                confidence_level=MatchConfidence.MEDIUM,
                match_reasons=["Second best"],
            ),
        ]

        result = CustomerMatchResult(
            query="test",
            candidates=candidates,
            best_match=candidates[0],
            has_high_confidence_match=True,
            requires_user_confirmation=True,
            search_stats={},
        )

        assert result.get_candidate_by_rank(1).name == "First Match"
        assert result.get_candidate_by_rank(2).name == "Second Match"
        assert result.get_candidate_by_rank(3) is None


# =============================================================================
# Test Agent Initialization
# =============================================================================


class TestAgentInitialization:
    """Tests for agent initialization."""

    def test_agent_creation(self, config, mock_cpi_client, mock_kyp_processor):
        """Test agent is created with correct configuration."""
        agent = CustomerMatcherAgent(
            config=config,
            cpi_client=mock_cpi_client,
            kyp_processor=mock_kyp_processor,
        )

        assert agent.domain_config == config
        assert agent._cpi == mock_cpi_client
        assert agent._kyp == mock_kyp_processor

    def test_agent_without_dependencies(self, config):
        """Test agent works without optional dependencies."""
        agent = CustomerMatcherAgent(config=config)

        assert agent._cpi is None
        assert agent._kyp is None


# =============================================================================
# Test Data Collection
# =============================================================================


class TestDataCollection:
    """Tests for candidate data collection."""

    @pytest.mark.asyncio
    async def test_get_sap_candidates(self, agent, mock_cpi_client):
        """Test SAP candidate retrieval."""
        candidates = await agent._get_sap_candidates()

        assert len(candidates) == 3
        assert candidates[0]["name"] == "Batam Fast Ferry Pte. Ltd."
        mock_cpi_client.list_customers.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_kyp_candidates(self, agent, mock_kyp_processor):
        """Test KYP candidate retrieval."""
        candidates = await agent._get_kyp_candidates()

        assert len(candidates) == 2
        assert candidates[0]["partner_name"] == "batam fast ferry pte ltd"
        mock_kyp_processor.list_reports.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_sap_candidates_no_client(self, config):
        """Test SAP candidate retrieval with no client."""
        agent = CustomerMatcherAgent(config=config, cpi_client=None)
        candidates = await agent._get_sap_candidates()

        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_kyp_candidates_no_processor(self, config):
        """Test KYP candidate retrieval with no processor."""
        agent = CustomerMatcherAgent(config=config, kyp_processor=None)
        candidates = await agent._get_kyp_candidates()

        assert candidates == []


# =============================================================================
# Test Matching Logic
# =============================================================================


class TestMatchingLogic:
    """Tests for customer matching logic."""

    @pytest.mark.asyncio
    async def test_match_customer_batamfast(self, agent):
        """Test matching 'batam fast ferry' returns correct result."""
        # Mock the LLM run() method
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Batam Fast Ferry Pte. Ltd.",
                        "customer_id": "0000100001",
                        "source": "BOTH",
                        "confidence_score": 95,
                        "match_reasons": [
                            "Exact company name match",
                            "Found in both SAP and KYP systems",
                        ],
                    }
                ]
            ),
            "analysis_summary": "Strong match found for Batam Fast Ferry with 95% confidence.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("batam fast ferry")

        assert result.query == "batam fast ferry"
        assert len(result.candidates) == 1
        assert result.best_match.name == "Batam Fast Ferry Pte. Ltd."
        assert result.best_match.confidence_score == 95
        assert result.best_match.confidence_level == MatchConfidence.HIGH
        assert result.has_high_confidence_match is True

    @pytest.mark.asyncio
    async def test_match_customer_maersk(self, agent):
        """Test matching 'maersk' returns correct result."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "A.P. Moller - Maersk A/S",
                        "customer_id": "0000100002",
                        "source": "SAP_CPI",
                        "confidence_score": 88,
                        "match_reasons": [
                            "Maersk is common abbreviation for A.P. Moller - Maersk",
                            "Major shipping company well-known by this short name",
                        ],
                    }
                ]
            ),
            "analysis_summary": "Good match found for Maersk with 88% confidence.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("maersk")

        assert result.best_match.name == "A.P. Moller - Maersk A/S"
        assert result.best_match.confidence_level == MatchConfidence.MEDIUM

    @pytest.mark.asyncio
    async def test_match_customer_no_matches(self, agent):
        """Test matching with no valid matches."""
        mock_llm_response = {
            "ranked_matches": json.dumps([]),
            "analysis_summary": "No matching customers found for the search query.",
            "match_found": "false",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("unknown company xyz")

        assert len(result.candidates) == 0
        assert result.best_match is None
        assert result.has_high_confidence_match is False
        assert result.requires_user_confirmation is True

    @pytest.mark.asyncio
    async def test_match_customer_multiple_candidates(self, agent):
        """Test matching returns multiple ranked candidates."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Batam Fast Ferry Pte. Ltd.",
                        "customer_id": "0000100001",
                        "source": "SAP_CPI",
                        "confidence_score": 75,
                        "match_reasons": ["Partial name match"],
                    },
                    {
                        "name": "Neptune Energy Netherlands B.V.",
                        "customer_id": "0000100003",
                        "source": "SAP_CPI",
                        "confidence_score": 55,
                        "match_reasons": ["Weak match on 'energy' keyword"],
                    },
                ]
            ),
            "analysis_summary": "Found 2 possible matches.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("fast energy")

        assert len(result.candidates) == 2
        assert result.candidates[0].rank == 1
        assert result.candidates[1].rank == 2
        assert (
            result.candidates[0].confidence_score
            > result.candidates[1].confidence_score
        )

    @pytest.mark.asyncio
    async def test_match_filters_below_threshold(self, agent):
        """Test that matches below threshold are filtered out."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Company A",
                        "customer_id": "001",
                        "source": "SAP_CPI",
                        "confidence_score": 60,
                        "match_reasons": ["Above threshold"],
                    },
                    {
                        "name": "Company B",
                        "customer_id": "002",
                        "source": "SAP_CPI",
                        "confidence_score": 40,  # Below 50% threshold
                        "match_reasons": ["Below threshold"],
                    },
                ]
            ),
            "analysis_summary": "Found matches with varying confidence.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("test query")

        # Only the match above threshold should be included
        assert len(result.candidates) == 1
        assert result.candidates[0].name == "Company A"


# =============================================================================
# Test Convenience Methods
# =============================================================================


class TestConvenienceMethods:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_match_and_select_best_high_confidence(self, agent):
        """Test match_and_select_best returns best match above threshold."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Best Match",
                        "customer_id": "0000100001",
                        "source": "SAP_CPI",
                        "confidence_score": 92,
                        "match_reasons": ["Strong match"],
                    }
                ]
            ),
            "analysis_summary": "Strong match found.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_and_select_best("test", min_confidence=70.0)

        assert result is not None
        assert result.name == "Best Match"
        assert result.customer_id == "0000100001"

    @pytest.mark.asyncio
    async def test_match_and_select_best_below_threshold(self, agent):
        """Test match_and_select_best returns None below threshold."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Weak Match",
                        "customer_id": "0000100001",
                        "source": "SAP_CPI",
                        "confidence_score": 55,
                        "match_reasons": ["Weak match"],
                    }
                ]
            ),
            "analysis_summary": "Weak match found.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_and_select_best("test", min_confidence=70.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_customer_id(self, agent):
        """Test resolve_customer_id returns SAP ID."""
        mock_llm_response = {
            "ranked_matches": json.dumps(
                [
                    {
                        "name": "Batam Fast Ferry Pte. Ltd.",
                        "customer_id": "0000100001",
                        "source": "SAP_CPI",
                        "confidence_score": 95,
                        "match_reasons": ["Exact match"],
                    }
                ]
            ),
            "analysis_summary": "Strong match found.",
            "match_found": "true",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            customer_id = await agent.resolve_customer_id("batam fast ferry")

        assert customer_id == "0000100001"


# =============================================================================
# Test Health Check
# =============================================================================


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_all_configured(
        self, agent, mock_cpi_client, mock_kyp_processor
    ):
        """Test health check with all dependencies configured."""
        health = await agent.health_check()

        assert health["status"] == "healthy"
        assert health["sap_configured"] is True
        assert health["kyp_configured"] is True
        assert health["sap_candidates_available"] == 3
        assert health["kyp_candidates_available"] == 2

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, config):
        """Test health check with no dependencies."""
        agent = CustomerMatcherAgent(config=config)
        health = await agent.health_check()

        assert health["status"] == "degraded"
        assert health["sap_configured"] is False
        assert health["kyp_configured"] is False


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_candidates_lists(self, config):
        """Test matching with empty candidate lists."""
        mock_cpi = MagicMock()
        mock_cpi.list_customers.return_value = []

        mock_kyp = MagicMock()
        mock_kyp.list_reports.return_value = []

        agent = CustomerMatcherAgent(
            config=config,
            cpi_client=mock_cpi,
            kyp_processor=mock_kyp,
        )

        result = await agent.match_customer("test company")

        assert len(result.candidates) == 0
        assert result.best_match is None
        assert result.requires_user_confirmation is True
        assert result.search_stats["total_candidates"] == 0

    @pytest.mark.asyncio
    async def test_malformed_llm_response(self, agent):
        """Test handling of malformed LLM response."""
        mock_llm_response = {
            "ranked_matches": "not valid json",  # Malformed JSON
            "analysis_summary": "Error occurred.",
            "match_found": "false",
        }

        with patch.object(agent, "run_async", return_value=mock_llm_response):
            result = await agent.match_customer("test")

        # Should handle gracefully with empty results
        assert len(result.candidates) == 0

    @pytest.mark.asyncio
    async def test_llm_exception(self, agent):
        """Test handling of LLM exception."""
        with patch.object(agent, "run_async", side_effect=Exception("LLM Error")):
            result = await agent.match_customer("test")

        assert len(result.candidates) == 0
        assert result.best_match is None
        assert "error" in result.search_stats


# =============================================================================
# Test Enums
# =============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_match_source_values(self):
        """Test MatchSource enum values."""
        assert MatchSource.SAP_CPI.value == "SAP_CPI"
        assert MatchSource.KYP_REPORT.value == "KYP_REPORT"
        assert MatchSource.BOTH.value == "BOTH"

    def test_match_confidence_values(self):
        """Test MatchConfidence enum values."""
        assert MatchConfidence.HIGH.value == "HIGH"
        assert MatchConfidence.MEDIUM.value == "MEDIUM"
        assert MatchConfidence.LOW.value == "LOW"
        assert MatchConfidence.UNCERTAIN.value == "UNCERTAIN"
