"""
Integration Tests for Query Understanding Module

Tests real OpenAI API calls for query parsing.
NO MOCKING - uses real infrastructure per testing policy.

Requires OPENAI_API_KEY environment variable to be set.
"""

import os

import pytest

from lead_to_cash.core.query_understanding import (
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
    get_query_engine,
    parse_query,
)

# Skip all tests if OPENAI_API_KEY not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - required for integration tests",
)


# =============================================================================
# Engine Initialization Tests
# =============================================================================


class TestEngineInitialization:
    """Tests for QueryUnderstandingEngine initialization."""

    def test_engine_initialization_success(self):
        """Test engine initializes with valid API key."""
        engine = QueryUnderstandingEngine()

        assert engine.model == "gpt-4o"
        assert engine.api_key is not None

    def test_engine_custom_model(self):
        """Test engine with custom model."""
        engine = QueryUnderstandingEngine(model="gpt-4o-mini")

        assert engine.model == "gpt-4o-mini"

    def test_engine_missing_api_key(self, monkeypatch):
        """Test engine raises error without API key."""
        # Temporarily remove API key
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY must be set"):
            QueryUnderstandingEngine()

    def test_singleton_pattern(self):
        """Test get_query_engine returns singleton."""
        engine1 = get_query_engine()
        engine2 = get_query_engine()

        assert engine1 is engine2


# =============================================================================
# Competitor Intelligence Query Tests
# =============================================================================


class TestCompetitorIntelQueries:
    """Tests for competitor intelligence query parsing."""

    @pytest.mark.asyncio
    async def test_caterpillar_query(self):
        """Test parsing Caterpillar competitor query."""
        query = "What contracts has Caterpillar won in the marine sector recently?"

        result = await parse_query(query)

        assert isinstance(result, ParsedQuery)
        assert result.intent == QueryIntent.COMPETITOR_INTEL
        assert result.intent_confidence >= 0.7
        assert "Caterpillar" in result.competitors or "CAT" in result.competitors

    @pytest.mark.asyncio
    async def test_cummins_query(self):
        """Test parsing Cummins competitor query."""
        query = "What is Cummins doing in the ferry segment in Europe?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.COMPETITOR_INTEL
        assert any("Cummins" in c for c in result.competitors)

    @pytest.mark.asyncio
    async def test_man_energy_query(self):
        """Test parsing MAN Energy Solutions query."""
        query = "How is MAN Energy Solutions performing in the cruise ship market?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.COMPETITOR_INTEL
        assert any("MAN" in c for c in result.competitors)

    @pytest.mark.asyncio
    async def test_wartsila_query(self):
        """Test parsing Wartsila query."""
        query = "What OSV contracts has Wartsila won in Southeast Asia?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.COMPETITOR_INTEL
        assert any("Wartsila" in c or "Wärtsilä" in c for c in result.competitors)
        assert "OSV" in result.vessel_types or any(
            "osv" in v.lower() for v in result.vessel_types
        )

    @pytest.mark.asyncio
    async def test_competitor_with_region(self):
        """Test competitor query with region extraction."""
        query = "What is Caterpillar's market share in APAC for offshore vessels?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.COMPETITOR_INTEL
        assert "Caterpillar" in result.competitors or "CAT" in result.competitors
        assert any("APAC" in r or "Asia" in r for r in result.regions)

    @pytest.mark.asyncio
    async def test_competitor_financial_query(self):
        """Test competitor financial query routes to financial_analysis."""
        query = (
            "What is Caterpillar's Q3 earnings and how does it compare to last year?"
        )

        result = await parse_query(query)

        # Financial analysis of competitors
        assert result.intent in [
            QueryIntent.FINANCIAL_ANALYSIS,
            QueryIntent.COMPETITOR_INTEL,
        ]
        assert "Caterpillar" in result.competitors or "CAT" in result.competitors


# =============================================================================
# Market News Query Tests
# =============================================================================


class TestMarketNewsQueries:
    """Tests for market news query parsing."""

    @pytest.mark.asyncio
    async def test_vessel_orders_query(self):
        """Test parsing vessel orders query."""
        query = "What are the latest ferry orders in Scandinavia?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.MARKET_NEWS
        assert (
            "ferry" in [v.lower() for v in result.vessel_types]
            or result.is_realtime_needed
        )

    @pytest.mark.asyncio
    async def test_shipyard_contracts_query(self):
        """Test parsing shipyard contracts query."""
        query = "What contracts has Samsung Heavy Industries won this quarter?"

        result = await parse_query(query)

        assert result.intent in [QueryIntent.MARKET_NEWS, QueryIntent.CUSTOMER_RESEARCH]
        assert any("Samsung" in c for c in result.companies)

    @pytest.mark.asyncio
    async def test_industry_trends_query(self):
        """Test parsing industry trends query."""
        query = "What are the trends in LNG-powered vessels for 2025?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.MARKET_NEWS

    @pytest.mark.asyncio
    async def test_fleet_expansion_query(self):
        """Test parsing fleet expansion query."""
        query = "Which operators are expanding their OSV fleet in the Gulf of Mexico?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.MARKET_NEWS
        assert any("osv" in v.lower() for v in result.vessel_types)
        assert any("Gulf" in r or "Mexico" in r for r in result.regions)


# =============================================================================
# Customer Research Query Tests
# =============================================================================


class TestCustomerResearchQueries:
    """Tests for customer research/KYP query parsing."""

    @pytest.mark.asyncio
    async def test_company_background_query(self):
        """Test parsing company background query."""
        query = "What can you tell me about Svitzer's fleet and operations?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.CUSTOMER_RESEARCH
        assert any("Svitzer" in c for c in result.companies)

    @pytest.mark.asyncio
    async def test_due_diligence_query(self):
        """Test parsing due diligence query."""
        query = "Run a KYP check on Pacific Basin Shipping"

        result = await parse_query(query)

        assert result.intent == QueryIntent.CUSTOMER_RESEARCH
        assert any("Pacific" in c for c in result.companies)

    @pytest.mark.asyncio
    async def test_shipyard_research_query(self):
        """Test parsing shipyard research query."""
        query = "What is Sembcorp Marine's orderbook and financial health?"

        result = await parse_query(query)

        assert result.intent in [
            QueryIntent.CUSTOMER_RESEARCH,
            QueryIntent.FINANCIAL_ANALYSIS,
        ]
        assert any("Sembcorp" in c for c in result.companies)


# =============================================================================
# Product Information Query Tests
# =============================================================================


class TestProductInfoQueries:
    """Tests for RRPS product information query parsing."""

    @pytest.mark.asyncio
    async def test_mtu_engine_query(self):
        """Test parsing MTU engine query."""
        query = "What are the specifications of the MTU 8000 series?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.PRODUCT_INFO
        assert any("MTU" in p or "8000" in p for p in result.products)

    @pytest.mark.asyncio
    async def test_bergen_engine_query(self):
        """Test parsing Bergen engine query."""
        query = "Compare Bergen B35:40 with the previous generation"

        result = await parse_query(query)

        assert result.intent == QueryIntent.PRODUCT_INFO
        assert any("Bergen" in p or "B35" in p for p in result.products)

    @pytest.mark.asyncio
    async def test_product_comparison_query(self):
        """Test parsing product comparison query."""
        query = "Which RRPS engine is best for a 150m ferry?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.PRODUCT_INFO
        assert "ferry" in [v.lower() for v in result.vessel_types]


# =============================================================================
# Sales Opportunity Query Tests
# =============================================================================


class TestSalesOpportunityQueries:
    """Tests for sales opportunity query parsing."""

    @pytest.mark.asyncio
    async def test_pipeline_query(self):
        """Test parsing pipeline query."""
        query = "What opportunities do we have in the ferry segment?"

        result = await parse_query(query)

        assert result.intent == QueryIntent.SALES_OPPORTUNITY
        assert "ferry" in [v.lower() for v in result.vessel_types]

    @pytest.mark.asyncio
    async def test_leads_query(self):
        """Test parsing leads query."""
        query = "Are there any new leads from Indonesian shipyards?"

        result = await parse_query(query)

        assert result.intent in [QueryIntent.SALES_OPPORTUNITY, QueryIntent.MARKET_NEWS]
        assert any("Indonesia" in r for r in result.regions)


# =============================================================================
# Temporal Parsing Tests (Real API)
# =============================================================================


class TestTemporalParsingReal:
    """Tests for temporal parsing with real API."""

    @pytest.mark.asyncio
    async def test_explicit_time_period(self):
        """Test parsing query with explicit time period."""
        query = "What contracts did Caterpillar win in Q4 2024?"

        result = await parse_query(query)

        assert result.time_reference is not None or result.time_start is not None

    @pytest.mark.asyncio
    async def test_relative_time_recent(self):
        """Test parsing query with 'recent' keyword."""
        query = "What are the recent ferry orders in Europe?"

        result = await parse_query(query)

        assert result.is_realtime_needed is True or result.time_reference is not None

    @pytest.mark.asyncio
    async def test_relative_time_latest(self):
        """Test parsing query with 'latest' keyword."""
        query = "What is the latest news on Caterpillar's marine division?"

        result = await parse_query(query)

        assert result.is_realtime_needed is True

    @pytest.mark.asyncio
    async def test_no_time_competitor_query(self):
        """Test query without time period triggers clarification for time-sensitive query."""
        query = "What contracts has Caterpillar won?"

        result = await parse_query(query)

        # Should either have time reference or require clarification
        # The LLM should recognize this needs temporal context
        assert (
            result.time_reference is not None
            or result.requires_clarification is True
            or result.is_realtime_needed is True
        )


# =============================================================================
# Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Tests for entity extraction with real API."""

    @pytest.mark.asyncio
    async def test_multiple_competitors(self):
        """Test extracting multiple competitors."""
        query = "Compare Caterpillar and Cummins marine engine offerings"

        result = await parse_query(query)

        assert len(result.competitors) >= 2
        competitor_names = " ".join(result.competitors).lower()
        assert "caterpillar" in competitor_names or "cat" in competitor_names
        assert "cummins" in competitor_names

    @pytest.mark.asyncio
    async def test_multiple_regions(self):
        """Test extracting multiple regions."""
        query = "What ferry projects are happening in Singapore and Indonesia?"

        result = await parse_query(query)

        assert len(result.regions) >= 1
        region_names = " ".join(result.regions).lower()
        assert "singapore" in region_names or "indonesia" in region_names

    @pytest.mark.asyncio
    async def test_vessel_type_extraction(self):
        """Test extracting vessel types."""
        query = "What OSV and PSV contracts have been signed in the North Sea?"

        result = await parse_query(query)

        vessel_types_lower = [v.lower() for v in result.vessel_types]
        assert "osv" in vessel_types_lower or "psv" in vessel_types_lower

    @pytest.mark.asyncio
    async def test_complex_query_all_entities(self):
        """Test extracting all entity types from complex query."""
        query = """
        What MTU 8000 orders has Caterpillar's marine division competed for
        in the ferry segment in Singapore over the last 6 months?
        """

        result = await parse_query(query)

        assert result.intent == QueryIntent.COMPETITOR_INTEL
        # Should extract multiple entity types
        assert (
            result.competitors
            or result.products
            or result.regions
            or result.vessel_types
        )


# =============================================================================
# Clarification Detection Tests
# =============================================================================


class TestClarificationDetection:
    """Tests for clarification detection with real API."""

    @pytest.mark.asyncio
    async def test_ambiguous_competitor_reference(self):
        """Test ambiguous competitor reference detection."""
        query = "How is the competitor doing?"

        result = await parse_query(query)

        # Should require clarification for ambiguous "competitor"
        assert result.requires_clarification is True or len(result.competitors) == 0

    @pytest.mark.asyncio
    async def test_clear_query_no_clarification(self):
        """Test clear query does not require clarification."""
        query = "What is Caterpillar's market share in marine engines in 2024?"

        result = await parse_query(query)

        # Clear query with entity and time
        assert result.requires_clarification is False or result.intent_confidence >= 0.8


# =============================================================================
# Conversation Context Tests
# =============================================================================


class TestConversationContext:
    """Tests for conversation context handling."""

    @pytest.mark.asyncio
    async def test_query_with_conversation_history(self):
        """Test query parsing with conversation context."""
        history = [
            {"role": "user", "content": "Tell me about Caterpillar's marine business"},
            {
                "role": "assistant",
                "content": "Caterpillar has a strong marine engine portfolio including MaK engines...",
            },
        ]

        query = "What contracts have they won recently?"

        result = await parse_query(query, conversation_history=history)

        # Should understand "they" refers to Caterpillar from context
        # The model should either extract Caterpillar or ask for clarification
        assert isinstance(result, ParsedQuery)
        assert result.intent in [QueryIntent.COMPETITOR_INTEL, QueryIntent.MARKET_NEWS]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self):
        """Test empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await parse_query("")

    @pytest.mark.asyncio
    async def test_whitespace_query_raises_error(self):
        """Test whitespace-only query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await parse_query("   ")

    @pytest.mark.asyncio
    async def test_engine_close(self):
        """Test engine can be closed properly."""
        engine = QueryUnderstandingEngine()

        # Make a request to establish connection
        await engine.parse("Test query")

        # Close should not raise
        await engine.close()

        # Client should be None after close
        assert engine._client is None


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Basic performance tests."""

    @pytest.mark.asyncio
    async def test_response_time(self):
        """Test query parsing completes in reasonable time."""
        import time

        query = "What contracts has Caterpillar won in APAC?"

        start = time.time()
        result = await parse_query(query)
        elapsed = time.time() - start

        assert result is not None
        # Should complete within 30 seconds (allowing for API latency)
        assert elapsed < 30.0
