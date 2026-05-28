"""
Unit Tests for Marine Intelligence Agent

Tests the MarineIntelAgent signature extraction and opportunity classification
without requiring external APIs (uses mock LLM provider).
"""

from unittest.mock import MagicMock, patch

import pytest

from lead_to_cash.agents.marine_intel_agent import (
    MarineIntelAgent,
    MarineIntelConfig,
    MarineIntelSignature,
)
from lead_to_cash.services.marine_intel.models import (
    Account,
    Article,
    MarineOpportunity,
    Region,
    SalesSignal,
    Sector,
    SourceCategory,
    VesselType,
)


class TestMarineIntelSignature:
    """Test the MarineIntelSignature definition."""

    def test_signature_input_fields(self):
        """Verify input fields are defined correctly."""
        sig = MarineIntelSignature()

        # Check input fields exist
        assert hasattr(sig, "raw_content")
        assert hasattr(sig, "query_context")
        assert hasattr(sig, "source_urls")

    def test_signature_output_fields(self):
        """Verify output fields are defined correctly."""
        sig = MarineIntelSignature()

        # Check output fields exist
        assert hasattr(sig, "opportunities")
        assert hasattr(sig, "summary")
        assert hasattr(sig, "total_opportunities")


class TestMarineIntelConfig:
    """Test the MarineIntelConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MarineIntelConfig()

        assert config.llm_provider == "openai"
        assert config.model == "gpt-4o-2024-08-06"
        assert config.temperature == 0.2  # Lower for consistent extraction
        assert config.max_tokens == 4000
        assert config.perplexity_model == "sonar"
        assert config.perplexity_timeout == 90
        assert config.max_queries_per_category == 3
        assert config.min_priority_threshold == 5
        assert config.delay_between_queries == 2.0
        assert config.agent_name == "marine_intel_agent"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MarineIntelConfig(
            llm_provider="anthropic",
            model="claude-3-opus",
            temperature=0.5,
            max_queries_per_category=5,
            min_priority_threshold=7,
        )

        assert config.llm_provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.5
        assert config.max_queries_per_category == 5
        assert config.min_priority_threshold == 7

    def test_priority_regions(self):
        """Test default priority regions."""
        config = MarineIntelConfig()

        assert "singapore" in config.priority_regions
        assert "indonesia" in config.priority_regions
        assert "malaysia" in config.priority_regions
        assert "thailand" in config.priority_regions
        assert "vietnam" in config.priority_regions


class TestMarineIntelModels:
    """Test the data models."""

    def test_marine_opportunity_url_hash(self):
        """Test URL hash generation for deduplication."""
        url = "https://example.com/news/ferry-order"
        hash1 = MarineOpportunity.generate_url_hash(url)
        hash2 = MarineOpportunity.generate_url_hash(url)

        # Same URL should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

        # Different URL should produce different hash
        hash3 = MarineOpportunity.generate_url_hash("https://example.com/different")
        assert hash1 != hash3

    def test_marine_opportunity_to_dict(self):
        """Test MarineOpportunity serialization."""
        opp = MarineOpportunity(
            id="test-123",
            headline="Singapore ferry operator orders 5 new vessels",
            source_name="Maritime Executive",
            source_url="https://example.com/news",
            url_hash=MarineOpportunity.generate_url_hash("https://example.com/news"),
            sales_signals=["newbuild", "fleet_expansion"],
            region="singapore",
            vessel_types=["ferry"],
            sector="marine_transportation",
            companies_involved=["Singapore Ferry Co", "Seatrium"],
            country="Singapore",
            sales_explanation="New ferry order requires propulsion systems",
            suggested_action="Contact Singapore Ferry Co procurement team",
            source_category="trade_media",
            priority=8,
        )

        data = opp.to_dict()

        assert data["id"] == "test-123"
        assert data["headline"] == "Singapore ferry operator orders 5 new vessels"
        assert "newbuild" in data["sales_signals"]
        assert data["priority"] == 8

    def test_article_model(self):
        """Test Article model creation and URL hash."""
        article = Article.create(
            url="https://maritimeexecutive.com/news/ferry-order",
            title="Major Ferry Order Announced",
            source="Maritime Executive",
            content="Full article content here...",
            source_category="trade_media",
        )

        assert article.id is not None
        assert article.url_hash == Article.generate_url_hash(article.url)
        assert article.source == "Maritime Executive"
        assert article.is_processed is False

    def test_opportunity_model(self):
        """Test MarineOpportunity model creation."""
        url = "https://example.com/news/ferry-order"
        opp = MarineOpportunity(
            id="opp-123",
            headline="Singapore ferry operator orders 5 new vessels",
            source_name="Maritime Executive",
            source_url=url,
            url_hash=MarineOpportunity.generate_url_hash(url),
            sales_signals=[
                SalesSignal.NEWBUILD.value,
                SalesSignal.FLEET_EXPANSION.value,
            ],
            region=Region.SINGAPORE.value,
            vessel_types=[VesselType.FERRY.value],
            sector=Sector.MARINE_TRANSPORTATION.value,
            companies_involved=["Penguin Ferry", "Seatrium"],
            country="Singapore",
            sales_explanation="New ferry order requires propulsion systems",
            suggested_action="Contact procurement team",
            source_category=SourceCategory.TRADE_MEDIA.value,
            priority=8,
        )

        assert opp.id == "opp-123"
        assert opp.headline == "Singapore ferry operator orders 5 new vessels"
        assert SalesSignal.NEWBUILD.value in opp.sales_signals
        assert opp.priority == 8
        assert opp.country == "Singapore"

    def test_account_normalize_company_name(self):
        """Test company name normalization."""
        # Test various corporate suffixes
        assert Account.normalize_company_name("Seatrium Ltd") == "seatrium"
        assert (
            Account.normalize_company_name("Penguin Shipyard Pte Ltd")
            == "penguin shipyard"
        )
        assert (
            Account.normalize_company_name("ASL Marine Holdings Ltd.")
            == "asl marine holdings"
        )
        assert Account.normalize_company_name("Caterpillar Inc") == "caterpillar"
        assert (
            Account.normalize_company_name("MAN Energy Solutions (Singapore)")
            == "man energy solutions"
        )

    def test_account_model(self):
        """Test Account model creation."""
        account = Account.create(
            company_name="Penguin Shipyard Pte Ltd",
            country="Singapore",
            sector=Sector.MARINE_ENGINEERING.value,
        )

        assert account.id is not None
        assert account.company_name == "Penguin Shipyard Pte Ltd"
        assert account.normalized_name == "penguin shipyard"
        assert account.mention_count == 0
        assert account.opportunity_count == 0


class TestMarineIntelAgentHelpers:
    """Test helper methods on the agent."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        return MarineIntelConfig(
            llm_provider="mock",  # Use mock provider
            model="mock-model",
        )

    @pytest.fixture
    def agent(self, mock_config):
        """Create agent instance with mocked dependencies."""
        with patch(
            "lead_to_cash.agents.marine_intel_agent.get_marine_intel_db"
        ) as mock_db:
            mock_db.return_value = MagicMock()
            agent = MarineIntelAgent(mock_config)
            return agent

    def test_map_country_to_region(self, agent):
        """Test country to region mapping."""
        assert agent._map_country_to_region("Singapore") == "singapore"
        assert agent._map_country_to_region("singapore") == "singapore"
        assert agent._map_country_to_region("SINGAPORE") == "singapore"
        assert agent._map_country_to_region("Indonesia") == "indonesia"
        assert agent._map_country_to_region("Malaysia") == "malaysia"
        assert agent._map_country_to_region("South Korea") == "korea"
        assert agent._map_country_to_region("Unknown Country") == "apac_other"

    def test_normalize_vessel_types(self, agent):
        """Test vessel type normalization."""
        assert "ferry" in agent._normalize_vessel_types("ferry")
        assert "ferry" in agent._normalize_vessel_types("Ferry vessel")
        assert "tug" in agent._normalize_vessel_types("tugboat")
        assert "osv" in agent._normalize_vessel_types("Offshore support vessel")
        assert "fpso" in agent._normalize_vessel_types("FPSO")
        assert "other" in agent._normalize_vessel_types("unknown vessel")

    def test_extract_source_name(self, agent):
        """Test source name extraction from URL."""
        assert (
            agent._extract_source_name("https://maritime-executive.com/article/123")
            == "Maritime Executive"
        )
        assert (
            agent._extract_source_name("https://splash247.com/news/ferry")
            == "Splash247"
        )
        assert (
            agent._extract_source_name("https://mpa.gov.sg/announcement")
            == "MPA Singapore"
        )
        assert agent._extract_source_name("https://seatrium.com/news") == "Seatrium"

    def test_infer_sector_offshore(self, agent):
        """Test sector inference for offshore opportunities."""
        opp_data = {
            "sales_signals": ["offshore_project"],
            "vessel_type": "osv",
            "headline": "FPSO contract awarded",
        }
        sector = agent._infer_sector(opp_data, "offshore project Indonesia")
        assert sector == "offshore_oil_gas"

    def test_infer_sector_marine_transportation(self, agent):
        """Test sector inference for marine transportation."""
        opp_data = {
            "sales_signals": ["newbuild"],
            "vessel_type": "ferry",
            "headline": "New ferry order",
        }
        sector = agent._infer_sector(opp_data, "ferry Singapore")
        assert sector == "marine_transportation"


class TestSalesSignalEnum:
    """Test SalesSignal enum values."""

    def test_all_signals_defined(self):
        """Verify all required sales signals are defined."""
        signals = [s.value for s in SalesSignal]

        assert "newbuild" in signals
        assert "retrofit_repower" in signals
        assert "offshore_project" in signals
        assert "regulation" in signals
        assert "fuel_transition" in signals
        assert "fleet_expansion" in signals
        assert "incident_reliability" in signals
        assert "financing_capex" in signals


class TestRegionEnum:
    """Test Region enum values."""

    def test_all_regions_defined(self):
        """Verify all priority regions are defined."""
        regions = [r.value for r in Region]

        assert "singapore" in regions
        assert "indonesia" in regions
        assert "malaysia" in regions
        assert "thailand" in regions
        assert "vietnam" in regions
        assert "philippines" in regions
        assert "australia" in regions
        assert "china" in regions
        assert "korea" in regions
        assert "japan" in regions
        assert "india" in regions


class TestVesselTypeEnum:
    """Test VesselType enum values."""

    def test_all_vessel_types_defined(self):
        """Verify all vessel types are defined."""
        vessel_types = [v.value for v in VesselType]

        assert "ferry" in vessel_types
        assert "tug" in vessel_types
        assert "osv" in vessel_types
        assert "fpso" in vessel_types
        assert "harbour_craft" in vessel_types


class TestQueryPatterns:
    """Test the query patterns configuration."""

    def test_query_patterns_defined(self):
        """Verify query patterns are defined for each category."""
        from lead_to_cash.services.marine_intel.models import QUERY_PATTERNS

        assert "newbuild" in QUERY_PATTERNS
        assert "repower_retrofit" in QUERY_PATTERNS
        assert "offshore_project" in QUERY_PATTERNS
        assert "fuel_transition" in QUERY_PATTERNS
        assert "incidents" in QUERY_PATTERNS
        assert "regulations" in QUERY_PATTERNS
        assert "fleet_expansion" in QUERY_PATTERNS

    def test_query_patterns_not_empty(self):
        """Verify each category has at least one query."""
        from lead_to_cash.services.marine_intel.models import QUERY_PATTERNS

        for category, queries in QUERY_PATTERNS.items():
            assert len(queries) > 0, f"Category {category} has no queries"


class TestMandatorySources:
    """Test the mandatory sources configuration."""

    def test_mandatory_sources_defined(self):
        """Verify mandatory sources are defined."""
        from lead_to_cash.services.marine_intel.models import MANDATORY_SOURCES

        assert "singapore_regulatory" in MANDATORY_SOURCES
        assert "trade_media" in MANDATORY_SOURCES
        assert "shipyards" in MANDATORY_SOURCES

    def test_singapore_regulatory_sources(self):
        """Verify Singapore regulatory sources are included."""
        from lead_to_cash.services.marine_intel.models import MANDATORY_SOURCES

        sg_sources = MANDATORY_SOURCES["singapore_regulatory"]
        source_names = [s["name"] for s in sg_sources]

        assert "MPA Singapore" in source_names
        assert "SMF (Singapore Maritime Foundation)" in source_names
        assert "SSA (Singapore Shipping Association)" in source_names

    def test_trade_media_sources(self):
        """Verify trade media sources are included."""
        from lead_to_cash.services.marine_intel.models import MANDATORY_SOURCES

        media_sources = MANDATORY_SOURCES["trade_media"]
        source_names = [s["name"] for s in media_sources]

        assert "Maritime Executive" in source_names
        assert "Seatrade Maritime" in source_names
        assert "Splash247" in source_names
        assert "Offshore Engineer" in source_names

    def test_shipyard_sources(self):
        """Verify shipyard sources are included."""
        from lead_to_cash.services.marine_intel.models import MANDATORY_SOURCES

        shipyards = MANDATORY_SOURCES["shipyards"]
        source_names = [s["name"] for s in shipyards]

        assert "Seatrium" in source_names
        assert "PaxOcean" in source_names
        assert "ASL Marine" in source_names
        assert "Penguin Shipyard" in source_names
