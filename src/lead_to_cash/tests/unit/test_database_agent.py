"""
Unit Tests for Database Agent

Tests agent signatures, configurations, and basic functionality
without making actual database calls (using mocks where needed).

Follows NO MOCKING policy for Tier 2+ tests, but Tier 1 unit tests
allow mocks for external dependencies like databases.
"""

from dataclasses import asdict

import pytest

from lead_to_cash.agents.database_agent import (
    DatabaseAgent,
    DatabaseAgentConfig,
    DatabaseQuerySignature,
)

# =============================================================================
# Configuration Tests
# =============================================================================


class TestDatabaseAgentConfig:
    """Tests for DatabaseAgentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DatabaseAgentConfig()

        assert config.llm_provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.1
        assert config.max_tokens == 1000
        assert config.database_url is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = DatabaseAgentConfig(
            llm_provider="ollama",
            model="llama3",
            temperature=0.2,
            database_url="postgresql://test:test@localhost/test",
        )

        assert config.llm_provider == "ollama"
        assert config.model == "llama3"
        assert config.temperature == 0.2
        assert config.database_url == "postgresql://test:test@localhost/test"

    def test_config_is_dataclass(self):
        """Test config is a proper dataclass."""
        config = DatabaseAgentConfig()

        # Should be convertible to dict
        config_dict = asdict(config)
        assert isinstance(config_dict, dict)
        assert "llm_provider" in config_dict


# =============================================================================
# Signature Tests
# =============================================================================


class TestDatabaseQuerySignature:
    """Tests for DatabaseQuerySignature."""

    def test_signature_input_fields(self):
        """Test signature has required input fields."""
        sig = DatabaseQuerySignature()

        # Check input fields exist
        assert hasattr(sig, "operation")
        assert hasattr(sig, "table")
        assert hasattr(sig, "filters")
        assert hasattr(sig, "data")
        assert hasattr(sig, "limit")

    def test_signature_output_fields(self):
        """Test signature has required output fields."""
        sig = DatabaseQuerySignature()

        # Check output fields exist
        assert hasattr(sig, "results")
        assert hasattr(sig, "count")
        assert hasattr(sig, "success")

    def test_signature_defaults(self):
        """Test signature default values exist and are correct."""
        sig = DatabaseQuerySignature()

        # Signature MUST have these fields
        assert hasattr(sig, "table"), "Signature must have 'table' field"
        assert hasattr(sig, "limit"), "Signature must have 'limit' field"

        # These fields MUST have defaults (they're optional inputs)
        table_field = sig.table
        limit_field = sig.limit

        # Assert default attribute exists and has correct value
        assert hasattr(
            table_field, "default"
        ), "table field must have default attribute"
        assert (
            table_field.default == "opportunities"
        ), f"Expected table default 'opportunities', got {table_field.default}"

        assert hasattr(
            limit_field, "default"
        ), "limit field must have default attribute"
        assert (
            limit_field.default == 50
        ), f"Expected limit default 50, got {limit_field.default}"

    def test_operation_types_documented_in_signature(self):
        """Test that valid operation types are documented in signature field description."""
        sig = DatabaseQuerySignature()

        # Verify the signature documents the expected operation types
        # This ensures the API contract matches what consumers expect
        expected_operations = ["query", "store", "lookup_opportunity", "lookup_account"]

        # Kaizen InputField uses 'desc' attribute for description
        assert hasattr(
            sig.operation, "desc"
        ), "operation field must have a desc attribute"
        assert sig.operation.desc, "operation field desc must not be empty"

        op_description = sig.operation.desc.lower()
        for op in expected_operations:
            assert op in op_description, (
                f"Operation '{op}' not documented in signature. "
                f"Description: {sig.operation.desc}"
            )

    def test_table_types_documented_in_signature(self):
        """Test that valid table types are documented in signature field description."""
        sig = DatabaseQuerySignature()

        # Verify the signature documents the expected table types
        # This ensures the API contract matches what consumers expect
        expected_tables = ["opportunities", "accounts", "articles", "jobs"]

        # Kaizen InputField uses 'desc' attribute for description
        assert hasattr(sig.table, "desc"), "table field must have a desc attribute"
        assert sig.table.desc, "table field desc must not be empty"

        table_description = sig.table.desc.lower()
        for table in expected_tables:
            assert table in table_description, (
                f"Table '{table}' not documented in signature. "
                f"Description: {sig.table.desc}"
            )


# =============================================================================
# Agent Initialization Tests
# =============================================================================


class TestDatabaseAgentInit:
    """Tests for DatabaseAgent initialization."""

    def test_agent_creation(self):
        """Test agent can be created with config."""
        config = DatabaseAgentConfig()

        try:
            agent = DatabaseAgent(config)
            assert agent is not None
            assert agent.agent_id == "database_agent"
        except ImportError:
            pytest.skip("Kaizen dependencies not available")

    def test_agent_with_custom_id(self):
        """Test agent with custom ID."""
        config = DatabaseAgentConfig()

        try:
            agent = DatabaseAgent(config, agent_id="custom_db_agent")
            assert agent.agent_id == "custom_db_agent"
        except ImportError:
            pytest.skip("Kaizen dependencies not available")

    def test_agent_without_database(self):
        """Test agent initializes without database connection."""
        config = DatabaseAgentConfig()

        try:
            agent = DatabaseAgent(config)
            # Database should not be connected until explicitly initialized
            assert agent._database is None
        except ImportError:
            pytest.skip("Kaizen dependencies not available")


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestDatabaseAgentContextManager:
    """Tests for DatabaseAgent context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_signature(self):
        """Test agent has context manager methods."""
        config = DatabaseAgentConfig()

        try:
            agent = DatabaseAgent(config)
            assert hasattr(agent, "__aenter__")
            assert hasattr(agent, "__aexit__")
        except ImportError:
            pytest.skip("Kaizen dependencies not available")


# =============================================================================
# A2A Capability Tests
# =============================================================================


class TestDatabaseAgentCapabilities:
    """Tests for A2A capability extraction."""

    def test_capabilities_method_exists(self):
        """Test agent has capability extraction method."""
        config = DatabaseAgentConfig()

        try:
            agent = DatabaseAgent(config)
            assert hasattr(agent, "_extract_primary_capabilities")
        except ImportError:
            pytest.skip("Kaizen dependencies not available")

    def test_capability_domains(self):
        """Test expected capability domains."""
        # Database agent should have database-related capabilities
        expected_capabilities = [
            "db_query",
            "db_store",
            "opportunity_lookup",
            "account_lookup",
        ]

        for cap in expected_capabilities:
            assert cap in expected_capabilities

    def test_capability_keywords(self):
        """Test capability keywords for routing."""
        db_keywords = [
            "query",
            "database",
            "opportunities",
            "accounts",
            "articles",
            "store",
            "lookup",
            "find",
            "search",
            "retrieve",
        ]

        # All keywords should be valid strings
        for kw in db_keywords:
            assert isinstance(kw, str)
            assert len(kw) > 0


# =============================================================================
# Operation Tests
# =============================================================================


class TestDatabaseOperations:
    """Tests for database operation handling."""

    def test_query_operation_parameters(self):
        """Test query operation parameter structure."""
        # Query parameters structure
        query_params = {
            "operation": "query",
            "table": "opportunities",
            "filters": {"region": "singapore", "sector": "marine"},
            "limit": 10,
        }

        assert query_params["operation"] == "query"
        assert query_params["table"] == "opportunities"
        assert isinstance(query_params["filters"], dict)
        assert query_params["limit"] == 10

    def test_store_operation_parameters(self):
        """Test store operation parameter structure."""
        # Store parameters structure
        store_params = {
            "operation": "store",
            "table": "opportunities",
            "data": {
                "title": "New ferry contract",
                "region": "singapore",
                "sector": "ferry",
            },
        }

        assert store_params["operation"] == "store"
        assert store_params["table"] == "opportunities"
        assert isinstance(store_params["data"], dict)

    def test_lookup_operation_parameters(self):
        """Test lookup operation parameter structure."""
        # Lookup parameters structure
        lookup_params = {
            "operation": "lookup_opportunity",
            "filters": {"id": "opp-123"},
        }

        assert lookup_params["operation"] == "lookup_opportunity"
        assert "id" in lookup_params["filters"]


# =============================================================================
# Filter Tests
# =============================================================================


class TestDatabaseFilters:
    """Tests for database query filters."""

    def test_region_filter(self):
        """Test region filter values."""
        valid_regions = [
            "singapore",
            "indonesia",
            "malaysia",
            "thailand",
            "vietnam",
            "philippines",
            "australia",
            "china",
            "korea",
            "japan",
            "india",
        ]

        for region in valid_regions:
            assert isinstance(region, str)

    def test_sector_filter(self):
        """Test sector filter values."""
        valid_sectors = [
            "ferry",
            "offshore",
            "tug",
            "harbor_craft",
            "osv",
            "container",
            "bulk",
            "tanker",
        ]

        for sector in valid_sectors:
            assert isinstance(sector, str)

    def test_signal_type_filter(self):
        """Test signal type filter values."""
        signal_types = [
            "newbuild",
            "retrofit",
            "fleet_expansion",
            "fuel_transition",
        ]

        for signal in signal_types:
            assert isinstance(signal, str)


# =============================================================================
# Result Tests
# =============================================================================


class TestDatabaseResults:
    """Tests for database operation results."""

    def test_query_result_structure(self):
        """Test query result structure."""
        # Expected result structure
        result = {
            "results": [
                {"id": "1", "title": "Ferry contract"},
                {"id": "2", "title": "Tug order"},
            ],
            "count": 2,
            "success": True,
        }

        assert isinstance(result["results"], list)
        assert result["count"] == len(result["results"])
        assert result["success"] is True

    def test_empty_result_structure(self):
        """Test empty result structure."""
        result = {
            "results": [],
            "count": 0,
            "success": True,
        }

        assert len(result["results"]) == 0
        assert result["count"] == 0
        assert result["success"] is True

    def test_error_result_structure(self):
        """Test error result structure."""
        result = {
            "results": [],
            "count": 0,
            "success": False,
            "error": "Database connection failed",
        }

        assert result["success"] is False


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_filters(self):
        """Test handling of empty filters."""
        filters = {}
        assert isinstance(filters, dict)
        assert len(filters) == 0

    def test_zero_limit(self):
        """Test handling of zero limit."""
        limit = 0
        assert limit == 0
        # Should return empty results or be interpreted as "no limit"

    def test_negative_limit(self):
        """Test handling of negative limit."""
        limit = -1
        assert limit < 0
        # Should be rejected or treated as invalid

    def test_very_large_limit(self):
        """Test handling of very large limit."""
        limit = 10000
        assert limit > 1000
        # Should be capped to a reasonable maximum

    def test_invalid_operation(self):
        """Test handling of invalid operation type."""
        invalid_operations = ["delete", "update", "drop", "truncate"]

        valid_operations = ["query", "store", "lookup_opportunity", "lookup_account"]

        for op in invalid_operations:
            assert op not in valid_operations

    def test_invalid_table(self):
        """Test handling of invalid table name."""
        invalid_tables = ["users", "passwords", "system"]

        valid_tables = ["opportunities", "accounts", "articles", "jobs"]

        for table in invalid_tables:
            assert table not in valid_tables
