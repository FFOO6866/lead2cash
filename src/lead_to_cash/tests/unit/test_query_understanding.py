"""
Unit Tests for Query Understanding Module

Tests data structures, temporal parsing, and helper methods.
No API calls - pure unit tests.
"""

from datetime import datetime, timedelta, timezone

import pytest

from lead_to_cash.core.query_understanding import (
    INTENT_TO_AGENT,
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
)

# =============================================================================
# QueryIntent Tests
# =============================================================================


class TestQueryIntent:
    """Tests for QueryIntent enum."""

    def test_all_intents_exist(self):
        """Test all expected intents are defined."""
        assert QueryIntent.COMPETITOR_INTEL.value == "competitor_intel"
        assert QueryIntent.MARKET_NEWS.value == "market_news"
        assert QueryIntent.CUSTOMER_RESEARCH.value == "customer_research"
        assert QueryIntent.PRODUCT_INFO.value == "product_info"
        assert QueryIntent.SALES_OPPORTUNITY.value == "sales_opportunity"
        assert QueryIntent.FINANCIAL_ANALYSIS.value == "financial_analysis"
        assert QueryIntent.GENERAL_QUESTION.value == "general_question"

    def test_intent_count(self):
        """Test correct number of intents."""
        # Updated to match actual implementation which includes:
        # market_intel, competitor_intel, customer_intel, kyp_due_diligence,
        # product_fit, relationship_check, general_question, billing_ar,
        # market_news, customer_research, product_info, sales_opportunity, financial_analysis
        assert len(QueryIntent) == 13

    def test_intent_is_string_enum(self):
        """Test intent values are strings."""
        for intent in QueryIntent:
            assert isinstance(intent.value, str)


class TestIntentToAgentMapping:
    """Tests for intent to agent mapping."""

    def test_all_intents_mapped(self):
        """Test all intents have agent mappings."""
        for intent in QueryIntent:
            assert intent in INTENT_TO_AGENT, f"Missing mapping for {intent}"

    def test_mapping_values(self):
        """Test specific mappings."""
        assert INTENT_TO_AGENT[QueryIntent.COMPETITOR_INTEL] == "competitor_intel"
        assert INTENT_TO_AGENT[QueryIntent.MARKET_NEWS] == "marine_intel"
        assert INTENT_TO_AGENT[QueryIntent.CUSTOMER_RESEARCH] == "due_diligence"
        assert INTENT_TO_AGENT[QueryIntent.PRODUCT_INFO] == "knowledge_base"
        assert INTENT_TO_AGENT[QueryIntent.SALES_OPPORTUNITY] == "marine_intel"
        assert INTENT_TO_AGENT[QueryIntent.FINANCIAL_ANALYSIS] == "competitor_intel"
        assert INTENT_TO_AGENT[QueryIntent.GENERAL_QUESTION] == "sales_ops"


# =============================================================================
# ParsedQuery Tests
# =============================================================================


class TestParsedQuery:
    """Tests for ParsedQuery dataclass."""

    def test_basic_creation(self):
        """Test creating parsed query with required fields."""
        query = ParsedQuery(
            raw_query="What is Caterpillar doing in APAC?",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.95,
        )

        assert query.raw_query == "What is Caterpillar doing in APAC?"
        assert query.intent == QueryIntent.COMPETITOR_INTEL
        assert query.intent_confidence == 0.95

    def test_default_lists_are_empty(self):
        """Test default entity lists are empty."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.8,
        )

        assert query.competitors == []
        assert query.companies == []
        assert query.regions == []
        assert query.products == []
        assert query.vessel_types == []
        assert query.clarification_questions == []

    def test_default_booleans(self):
        """Test default boolean values."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.8,
        )

        assert query.is_realtime_needed is False
        assert query.requires_clarification is False

    def test_full_entity_creation(self):
        """Test creating query with all entities."""
        query = ParsedQuery(
            raw_query="What contracts has Caterpillar won for ferries in Singapore last quarter?",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.92,
            competitors=["Caterpillar"],
            companies=[],
            regions=["Singapore"],
            products=[],
            vessel_types=["ferry"],
            time_reference="last quarter",
            time_start="2025-10-01",
            time_end="2025-12-31",
            is_realtime_needed=False,
            requires_clarification=False,
        )

        assert query.competitors == ["Caterpillar"]
        assert query.regions == ["Singapore"]
        assert query.vessel_types == ["ferry"]
        assert query.time_reference == "last quarter"

    def test_primary_agent_property(self):
        """Test primary_agent property returns correct agent."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.9,
        )
        assert query.primary_agent == "competitor_intel"

        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.MARKET_NEWS,
            intent_confidence=0.9,
        )
        assert query.primary_agent == "marine_intel"

    def test_has_entities_true(self):
        """Test has_entities returns True when entities present."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.9,
            competitors=["Caterpillar"],
        )
        assert query.has_entities is True

        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.9,
            regions=["APAC"],
        )
        assert query.has_entities is True

    def test_has_entities_false(self):
        """Test has_entities returns False when no entities."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.9,
        )
        assert query.has_entities is False

    def test_has_temporal_scope_with_start(self):
        """Test has_temporal_scope with time_start."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.9,
            time_start="2025-01-01",
        )
        assert query.has_temporal_scope is True

    def test_has_temporal_scope_with_reference(self):
        """Test has_temporal_scope with time_reference."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.9,
            time_reference="last month",
        )
        assert query.has_temporal_scope is True

    def test_has_temporal_scope_false(self):
        """Test has_temporal_scope returns False when no temporal info."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.9,
        )
        assert query.has_temporal_scope is False

    def test_to_dict(self):
        """Test serialization to dictionary."""
        query = ParsedQuery(
            raw_query="What is Caterpillar's market share?",
            intent=QueryIntent.COMPETITOR_INTEL,
            intent_confidence=0.88,
            competitors=["Caterpillar"],
            regions=["global"],
        )

        d = query.to_dict()

        assert d["raw_query"] == "What is Caterpillar's market share?"
        assert d["intent"] == "competitor_intel"
        assert d["intent_confidence"] == 0.88
        assert d["competitors"] == ["Caterpillar"]
        assert d["regions"] == ["global"]
        assert "parsed_at" in d

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all expected fields."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.8,
        )

        d = query.to_dict()

        expected_keys = [
            "raw_query",
            "intent",
            "intent_confidence",
            "competitors",
            "companies",
            "regions",
            "products",
            "vessel_types",
            "time_reference",
            "time_start",
            "time_end",
            "is_realtime_needed",
            "requires_clarification",
            "clarification_questions",
            "clarification_reason",
            "parsed_at",
        ]

        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_parsed_at_timestamp(self):
        """Test parsed_at is set automatically."""
        query = ParsedQuery(
            raw_query="test",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.8,
        )

        assert query.parsed_at is not None
        # Should be ISO format
        assert "T" in query.parsed_at


# =============================================================================
# Temporal Parsing Tests
# =============================================================================


def _utc_today():
    """Get today's date in UTC (matches implementation behavior)."""
    return datetime.now(timezone.utc).date()


class TestTemporalParsing:
    """Tests for _parse_relative_time method."""

    @pytest.fixture
    def engine(self):
        """Create engine for testing temporal parsing.

        Note: This fixture does NOT require OPENAI_API_KEY because
        we're only testing the _parse_relative_time helper method.
        """
        # Use object.__new__ to avoid __init__ requiring API key
        engine = object.__new__(QueryUnderstandingEngine)
        return engine

    def test_today_reference(self, engine):
        """Test parsing 'today' reference."""
        today = _utc_today().isoformat()

        start, end = engine._parse_relative_time("today")
        assert start == today
        assert end == today

    def test_now_reference(self, engine):
        """Test parsing 'now' reference."""
        today = _utc_today().isoformat()

        start, end = engine._parse_relative_time("right now")
        assert start == today

    def test_yesterday_reference(self, engine):
        """Test parsing 'yesterday' reference."""
        yesterday = (_utc_today() - timedelta(days=1)).isoformat()

        start, end = engine._parse_relative_time("yesterday")
        assert start == yesterday

    def test_last_week_reference(self, engine):
        """Test parsing 'last week' reference."""
        week_ago = (_utc_today() - timedelta(days=7)).isoformat()

        start, end = engine._parse_relative_time("last week")
        assert start == week_ago

    def test_past_week_reference(self, engine):
        """Test parsing 'past week' reference."""
        week_ago = (_utc_today() - timedelta(days=7)).isoformat()

        start, end = engine._parse_relative_time("past week")
        assert start == week_ago

    def test_last_month_reference(self, engine):
        """Test parsing 'last month' reference."""
        month_ago = (_utc_today() - timedelta(days=30)).isoformat()

        start, end = engine._parse_relative_time("last month")
        assert start == month_ago

    def test_last_3_months_reference(self, engine):
        """Test parsing 'last 3 months' reference."""
        three_months_ago = (_utc_today() - timedelta(days=90)).isoformat()

        start, end = engine._parse_relative_time("last 3 months")
        assert start == three_months_ago

    def test_last_6_months_reference(self, engine):
        """Test parsing 'last 6 months' reference."""
        six_months_ago = (_utc_today() - timedelta(days=180)).isoformat()

        start, end = engine._parse_relative_time("last 6 months")
        assert start == six_months_ago

    def test_last_quarter_reference(self, engine):
        """Test parsing 'last quarter' reference."""
        quarter_ago = (_utc_today() - timedelta(days=90)).isoformat()

        start, end = engine._parse_relative_time("last quarter")
        assert start == quarter_ago

    def test_last_year_reference(self, engine):
        """Test parsing 'last year' reference."""
        year_ago = (_utc_today() - timedelta(days=365)).isoformat()

        start, end = engine._parse_relative_time("last year")
        assert start == year_ago

    def test_last_3_years_reference(self, engine):
        """Test parsing 'last 3 years' reference."""
        three_years_ago = (_utc_today() - timedelta(days=1095)).isoformat()

        start, end = engine._parse_relative_time("last 3 years")
        assert start == three_years_ago

    def test_7_days_reference(self, engine):
        """Test parsing '7 days' reference."""
        week_ago = (_utc_today() - timedelta(days=7)).isoformat()

        start, end = engine._parse_relative_time("7 days")
        assert start == week_ago

    def test_30_days_reference(self, engine):
        """Test parsing '30 days' reference."""
        month_ago = (_utc_today() - timedelta(days=30)).isoformat()

        start, end = engine._parse_relative_time("30 days")
        assert start == month_ago

    def test_90_days_reference(self, engine):
        """Test parsing '90 days' reference."""
        quarter_ago = (_utc_today() - timedelta(days=90)).isoformat()

        start, end = engine._parse_relative_time("90 days")
        assert start == quarter_ago

    def test_none_reference(self, engine):
        """Test parsing None reference."""
        start, end = engine._parse_relative_time(None)
        assert start is None
        assert end is None

    def test_empty_reference(self, engine):
        """Test parsing empty string reference."""
        start, end = engine._parse_relative_time("")
        assert start is None
        assert end is None

    def test_unrecognized_reference(self, engine):
        """Test parsing unrecognized reference returns None."""
        start, end = engine._parse_relative_time("some random text")
        assert start is None
        # End date is always today (UTC) if we attempt parsing
        assert end == _utc_today().isoformat()

    def test_end_date_always_today(self, engine):
        """Test end date is always today for relative references."""
        today = _utc_today().isoformat()

        _, end = engine._parse_relative_time("last month")
        assert end == today

        _, end = engine._parse_relative_time("last year")
        assert end == today

    def test_case_insensitive(self, engine):
        """Test parsing is case insensitive."""
        start1, _ = engine._parse_relative_time("Last Month")
        start2, _ = engine._parse_relative_time("LAST MONTH")
        start3, _ = engine._parse_relative_time("last month")

        assert start1 == start2 == start3


# =============================================================================
# Conversation Summary Tests
# =============================================================================


class TestConversationSummary:
    """Tests for _summarize_conversation method."""

    @pytest.fixture
    def engine(self):
        """Create engine for testing conversation summary."""
        engine = object.__new__(QueryUnderstandingEngine)
        return engine

    def test_empty_history(self, engine):
        """Test summarizing empty history."""
        result = engine._summarize_conversation([])
        assert result == "No previous context."

    def test_none_history(self, engine):
        """Test summarizing None history."""
        result = engine._summarize_conversation(None)
        assert result == "No previous context."

    def test_single_turn(self, engine):
        """Test summarizing single turn."""
        history = [{"role": "user", "content": "Hello"}]

        result = engine._summarize_conversation(history)

        assert "user:" in result.lower()
        assert "Hello" in result

    def test_multi_turn(self, engine):
        """Test summarizing multiple turns."""
        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]

        result = engine._summarize_conversation(history)

        assert "user" in result.lower()
        assert "assistant" in result.lower()

    def test_truncation_long_content(self, engine):
        """Test long content is truncated to 500 chars per turn."""
        long_content = "X" * 1000

        history = [{"role": "user", "content": long_content}]

        result = engine._summarize_conversation(history)

        # Content per turn should be truncated to 500 chars
        # The result includes headers so will be longer overall
        # but the 'X's should be capped at 500
        assert result.count("X") == 500

    def test_takes_last_5_turns(self, engine):
        """Test only last 5 turns are used (implementation takes 5, not 3)."""
        # Use unique identifiers to avoid confusion with [Turn N] labels
        history = [
            {"role": "user", "content": "FirstMessage"},
            {"role": "assistant", "content": "FirstReply"},
            {"role": "user", "content": "SecondMessage"},
            {"role": "assistant", "content": "SecondReply"},
            {"role": "user", "content": "ThirdMessage"},
            {"role": "assistant", "content": "ThirdReply"},
            {"role": "user", "content": "FourthMessage"},
            {"role": "assistant", "content": "FourthReply"},
            {"role": "user", "content": "FifthMessage"},  # Should be included
            {"role": "assistant", "content": "FifthReply"},  # Should be included
            {"role": "user", "content": "SixthMessage"},  # Should be included
        ]

        result = engine._summarize_conversation(history)

        # Only last 5 turns should be present
        assert "FirstMessage" not in result
        assert "FirstReply" not in result
        assert "SecondMessage" not in result
        # These should be present (last 5 turns)
        assert (
            "FifthMessage" in result
            or "FifthReply" in result
            or "SixthMessage" in result
        )


# =============================================================================
# Build Parsed Query Tests
# =============================================================================


class TestBuildParsedQuery:
    """Tests for _build_parsed_query method."""

    @pytest.fixture
    def engine(self):
        """Create engine for testing query building."""
        engine = object.__new__(QueryUnderstandingEngine)
        return engine

    def test_basic_build(self, engine):
        """Test building basic parsed query from LLM result."""
        result = {
            "intent": "competitor_intel",
            "intent_confidence": 0.9,
            "competitors": ["Caterpillar"],
            "companies": [],
            "regions": ["APAC"],
            "products": [],
            "vessel_types": [],
            "time_reference": None,
            "time_start": None,
            "time_end": None,
            "is_realtime_needed": False,
            "requires_clarification": False,
            "clarification_questions": [],
            "clarification_reason": None,
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.raw_query == "Test query"
        assert query.intent == QueryIntent.COMPETITOR_INTEL
        assert query.intent_confidence == 0.9
        assert query.competitors == ["Caterpillar"]
        assert query.regions == ["APAC"]

    def test_unknown_intent_fallback(self, engine):
        """Test unknown intent falls back to general_question."""
        result = {
            "intent": "unknown_intent_type",
            "intent_confidence": 0.5,
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.intent == QueryIntent.GENERAL_QUESTION

    def test_missing_intent_fallback(self, engine):
        """Test missing intent falls back to general_question."""
        result = {
            "intent_confidence": 0.5,
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.intent == QueryIntent.GENERAL_QUESTION

    def test_relative_time_parsing(self, engine):
        """Test relative time reference is parsed to dates."""
        result = {
            "intent": "competitor_intel",
            "intent_confidence": 0.9,
            "time_reference": "last month",
            "time_start": None,  # Will be calculated
            "time_end": None,  # Will be calculated
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.time_reference == "last month"
        assert query.time_start is not None
        assert query.time_end is not None

    def test_explicit_dates_preserved(self, engine):
        """Test explicit dates are preserved over calculated ones."""
        result = {
            "intent": "competitor_intel",
            "intent_confidence": 0.9,
            "time_reference": "Q1 2025",
            "time_start": "2025-01-01",
            "time_end": "2025-03-31",
        }

        query = engine._build_parsed_query("Test query", result)

        # Explicit dates should be used
        assert query.time_start == "2025-01-01"
        assert query.time_end == "2025-03-31"

    def test_default_confidence(self, engine):
        """Test default confidence when not provided."""
        result = {
            "intent": "market_news",
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.intent_confidence == 0.8  # Default

    def test_clarification_fields(self, engine):
        """Test clarification fields are properly set."""
        result = {
            "intent": "competitor_intel",
            "intent_confidence": 0.7,
            "requires_clarification": True,
            "clarification_questions": ["Which competitor?", "What time period?"],
            "clarification_reason": "Multiple competitors mentioned without specificity",
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.requires_clarification is True
        assert len(query.clarification_questions) == 2
        assert (
            query.clarification_reason
            == "Multiple competitors mentioned without specificity"
        )

    def test_realtime_flag(self, engine):
        """Test realtime flag is properly set."""
        result = {
            "intent": "market_news",
            "intent_confidence": 0.95,
            "is_realtime_needed": True,
        }

        query = engine._build_parsed_query("Test query", result)

        assert query.is_realtime_needed is True
