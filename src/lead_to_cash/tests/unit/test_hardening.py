"""
Unit Tests for Final Hardening Patch

Tests the 6 hardening fixes:
1. Tier-1-first source filtering
2. Strict mode trigger correction
3. Hard source gate strengthening
4. Citation cleanup for removed sources
5. Vector-DB safety for structured queries
6. Observability metrics
"""

import pytest

from lead_to_cash.core.data_inventory import DataSource, InventoryCheckResult
from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.response_quality import (
    SourceTier,
    filter_sources_tier1_first,
    get_source_tier,
    strip_ungrounded_citations,
)
from lead_to_cash.core.source_authority import (
    FallbackStrategy,
    SourceAuthority,
    WebSearchGate,
)


def _make_inventory(has_local_data: bool = True) -> InventoryCheckResult:
    return InventoryCheckResult(
        has_local_data=has_local_data,
        coverage=None,
        confidence="HIGH" if has_local_data else "LOW",
        gaps=[],
        recommended_sources=[],
    )


# =============================================================================
# Task 1: Tier-1-first source filtering
# =============================================================================


class TestTier1FirstFiltering:
    """When Tier 1 sources exist, ONLY Tier 1 should be shown."""

    def test_tier1_present_removes_lower_tiers(self):
        sources = ["SAP CPI (MS5)", "Intelligence Database", "Web Search"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_4_EXTERNAL_BROAD
        )
        assert kept == ["SAP CPI (MS5)"]
        assert "Intelligence Database" in removed
        assert "Web Search" in removed

    def test_tier1_present_keeps_multiple_tier1(self):
        sources = ["SAP CPI (MS5)", "Knowledge Base", "Web Search"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_4_EXTERNAL_BROAD
        )
        assert "SAP CPI (MS5)" in kept
        assert "Knowledge Base" in kept
        assert "Web Search" in removed

    def test_no_tier1_uses_max_tier(self):
        sources = ["Intelligence Database", "Web Search", "EODHD"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_3_EXTERNAL_TRUSTED
        )
        # No Tier 1, so keep up to Tier 3 (EODHD)
        assert "Intelligence Database" in kept
        assert "EODHD" in kept
        assert "Web Search" in removed

    def test_no_tier1_all_within_max_tier(self):
        sources = ["Intelligence Database", "EODHD"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_3_EXTERNAL_TRUSTED
        )
        assert kept == ["Intelligence Database", "EODHD"]
        assert removed == []

    def test_empty_sources(self):
        kept, removed = filter_sources_tier1_first([], SourceTier.TIER_4_EXTERNAL_BROAD)
        assert kept == []
        assert removed == []

    def test_all_tier1(self):
        sources = ["SAP CPI (MS5)", "Knowledge Base", "Product Database"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_1_INTERNAL_STRUCTURED
        )
        assert len(kept) == 3
        assert removed == []

    def test_billing_scenario_tier1_only(self):
        """Billing response with SAP + accidentally leaked web source."""
        sources = ["SAP CPI (MS5)", "Web Search"]
        kept, removed = filter_sources_tier1_first(
            sources, SourceTier.TIER_1_INTERNAL_STRUCTURED
        )
        assert kept == ["SAP CPI (MS5)"]
        assert removed == ["Web Search"]


# =============================================================================
# Task 4: Citation cleanup
# =============================================================================


class TestCitationCleanup:
    """Citations pointing to removed sources must be stripped."""

    def test_remove_citation_for_filtered_source(self):
        answer = "Revenue grew 15% [1]. Market cap is EUR 30B [2]."
        all_sources = ["SAP CPI (MS5)", "Web Search"]
        allowed = ["SAP CPI (MS5)"]  # Web Search removed
        cleaned, count = strip_ungrounded_citations(answer, allowed, all_sources)
        assert "[1]" in cleaned  # SAP citation kept
        assert "[2]" not in cleaned  # Web citation removed
        assert count == 1

    def test_keep_all_citations_when_all_allowed(self):
        answer = "Data from SAP [1] and KB [2]."
        all_sources = ["SAP CPI (MS5)", "Knowledge Base"]
        allowed = ["SAP CPI (MS5)", "Knowledge Base"]
        cleaned, count = strip_ungrounded_citations(answer, allowed, all_sources)
        assert cleaned == answer
        assert count == 0

    def test_remove_all_citations(self):
        answer = "Revenue [1] and profits [2] from web."
        all_sources = ["Web Search", "Perplexity Search"]
        allowed = []  # All removed
        cleaned, count = strip_ungrounded_citations(answer, allowed, all_sources)
        assert "[1]" not in cleaned
        assert "[2]" not in cleaned
        assert count == 2

    def test_empty_answer(self):
        cleaned, count = strip_ungrounded_citations("", [], [])
        assert cleaned == ""
        assert count == 0

    def test_no_citations_in_text(self):
        answer = "Simple text without citations."
        cleaned, count = strip_ungrounded_citations(answer, ["SAP CPI"], ["SAP CPI"])
        assert cleaned == answer
        assert count == 0


# =============================================================================
# Task 2: Strict mode trigger correction
# =============================================================================


class TestStrictModeTrigger:
    """Strict mode must trigger for internal-only AND max_tier <= Tier 2."""

    def test_billing_triggers_strict_via_internal_only(self):
        parsed = ParsedQuery(
            raw_query="Show billing items",
            intent=QueryIntent.BILLING_AR,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        # Billing: fallback=INTERNAL_ONLY → strict
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY

    def test_product_triggers_strict_via_max_tier(self):
        parsed = ParsedQuery(
            raw_query="MTU 4000 specs",
            intent=QueryIntent.PRODUCT_FIT,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        # Product: max_tier = Tier 2 → strict
        assert decision.max_tier.value <= SourceTier.TIER_2_INTERNAL_SEMANTIC.value

    def test_relationship_triggers_strict_via_max_tier(self):
        parsed = ParsedQuery(
            raw_query="Our position with Maersk",
            intent=QueryIntent.RELATIONSHIP_CHECK,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.max_tier.value <= SourceTier.TIER_2_INTERNAL_SEMANTIC.value

    def test_market_intel_does_not_trigger_strict(self):
        parsed = ParsedQuery(
            raw_query="APAC ferry market trends",
            intent=QueryIntent.MARKET_INTEL,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy != FallbackStrategy.INTERNAL_ONLY
        assert decision.max_tier.value > SourceTier.TIER_2_INTERNAL_SEMANTIC.value

    def test_general_question_does_not_trigger_strict(self):
        parsed = ParsedQuery(
            raw_query="What is an OSV?",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy != FallbackStrategy.INTERNAL_ONLY
        assert decision.max_tier.value > SourceTier.TIER_2_INTERNAL_SEMANTIC.value


# =============================================================================
# Task 5: Vector-DB safety for structured queries
# =============================================================================


class TestVectorDBSafety:
    """Structured internal queries must not leak vector-db content."""

    def test_billing_forbids_vectordb(self):
        parsed = ParsedQuery(
            raw_query="Show billing items",
            intent=QueryIntent.BILLING_AR,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.LOCAL_VECTORDB in decision.forbidden_sources

    def test_product_permits_vectordb_as_secondary(self):
        """Product fit permits vectordb (for similar opportunities) but as permitted, not required."""
        parsed = ParsedQuery(
            raw_query="MTU 4000 specs",
            intent=QueryIntent.PRODUCT_FIT,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        # VectorDB is permitted but KB is the primary
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources
        assert DataSource.LOCAL_VECTORDB in decision.permitted_sources

    def test_relationship_permits_vectordb(self):
        parsed = ParsedQuery(
            raw_query="Our position with Maersk",
            intent=QueryIntent.RELATIONSHIP_CHECK,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.LOCAL_VECTORDB in decision.permitted_sources


# =============================================================================
# Task 3: Hard gate strengthening — verify gate blocks correctly
# =============================================================================


class TestHardGateStrength:
    """Source gate must block forbidden sources and report unambiguously."""

    def test_billing_perplexity_blocked(self):
        parsed = ParsedQuery(
            raw_query="Show billing items",
            intent=QueryIntent.BILLING_AR,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert not decision.is_source_allowed(DataSource.PERPLEXITY)
        assert not decision.is_source_allowed(DataSource.NEWSAPI)
        assert not decision.is_source_allowed(DataSource.EODHD)
        assert not decision.is_source_allowed(DataSource.LOCAL_VECTORDB)
        # BillingAgent IS allowed
        assert decision.is_source_allowed(DataSource.BILLING_AGENT)
        # OpenAI IS allowed (synthesis)
        assert decision.is_source_allowed(DataSource.OPENAI)

    def test_product_web_blocked(self):
        parsed = ParsedQuery(
            raw_query="MTU engine specs",
            intent=QueryIntent.PRODUCT_FIT,
            intent_confidence=0.9,
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert not decision.is_source_allowed(DataSource.PERPLEXITY)
        assert decision.is_source_allowed(DataSource.KNOWLEDGE_BASE)


# =============================================================================
# Integration: full pipeline test
# =============================================================================


class TestFullPipelineHardening:
    """End-to-end tests combining all hardening fixes."""

    def test_billing_full_pipeline(self):
        """Billing query: intent override → source authority → tier-1-first → clean."""
        from lead_to_cash.core.query_understanding import QueryUnderstandingEngine

        # LLM misclassifies as customer_intel
        parsed = ParsedQuery(
            raw_query="What is the payment history for ST Engineering?",
            intent=QueryIntent.CUSTOMER_INTEL,
            intent_confidence=0.7,
            companies=["ST Engineering"],
        )

        # Step 1: Stabilize intent
        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert stabilized.intent == QueryIntent.BILLING_AR
        assert stabilized.intent_source == "rule_override"

        # Step 2: Source authority
        decision = SourceAuthority.decide(stabilized, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY
        assert decision.web_search_gate == WebSearchGate.BLOCKED
        assert DataSource.PERPLEXITY in decision.forbidden_sources

        # Step 3: Tier-1-first filter
        mock_sources = ["SAP CPI (MS5)", "Web Search"]
        kept, removed = filter_sources_tier1_first(mock_sources, decision.max_tier)
        assert kept == ["SAP CPI (MS5)"]
        assert "Web Search" in removed

        # Step 4: Citation cleanup
        answer = "Payment on time [1]. According to web [2]."
        cleaned, count = strip_ungrounded_citations(answer, kept, mock_sources)
        assert "[2]" not in cleaned
        assert "[1]" in cleaned
        assert count == 1

    def test_product_full_pipeline(self):
        """Product query: override → authority → tier-1 → clean."""
        from lead_to_cash.core.query_understanding import QueryUnderstandingEngine

        parsed = ParsedQuery(
            raw_query="What are the MTU 12V 2000 engine specs?",
            intent=QueryIntent.GENERAL_QUESTION,
            intent_confidence=0.6,
        )

        stabilized = QueryUnderstandingEngine._stabilize_intent(parsed)
        assert stabilized.intent == QueryIntent.PRODUCT_FIT

        decision = SourceAuthority.decide(stabilized, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources

        mock_sources = ["Knowledge Base", "Intelligence Database"]
        kept, removed = filter_sources_tier1_first(mock_sources, decision.max_tier)
        assert kept == ["Knowledge Base"]
        assert "Intelligence Database" in removed

    def test_market_intel_preserves_web(self):
        """Market intel: no override → web allowed → all sources kept."""
        parsed = ParsedQuery(
            raw_query="What is happening in the APAC ferry market?",
            intent=QueryIntent.MARKET_INTEL,
            intent_confidence=0.9,
        )

        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY not in decision.forbidden_sources

        mock_sources = ["Intelligence Database", "Web Search"]
        kept, removed = filter_sources_tier1_first(mock_sources, decision.max_tier)
        # No Tier 1, so keep up to max_tier (Tier 4)
        assert "Intelligence Database" in kept
        assert "Web Search" in kept
        assert removed == []
