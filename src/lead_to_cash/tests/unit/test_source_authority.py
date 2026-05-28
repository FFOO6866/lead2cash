"""
Unit Tests for Source Authority (Source-of-Truth Routing Layer)

Tests that the deterministic source gate correctly restricts
data sources based on intent, sub-intent, and inventory signals.

Critical test scenarios:
- Internal-only intents NEVER allow web search
- Product queries NEVER allow web search
- Competitor analysis blocks web; competitor news allows it
- KYP allows targeted Perplexity (for sanctions/litigation)
- Market intel allows web as supplement
- Fallback strategies respect source boundaries
"""

import pytest

from lead_to_cash.core.data_inventory import DataSource, InventoryCheckResult
from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.source_authority import (
    FallbackStrategy,
    SourceAuthority,
    SourceDecision,
    WebSearchGate,
    get_datasource_tier,
)
from lead_to_cash.core.response_quality import SourceTier


# =============================================================================
# Helper to build ParsedQuery for tests
# =============================================================================


def _make_parsed(
    intent: QueryIntent,
    raw_query: str = "test query",
    companies: list | None = None,
    competitors: list | None = None,
    market_intel_style: str = "opportunities",
    competitor_intel_style: str = "news",
    is_realtime_needed: bool = False,
) -> ParsedQuery:
    return ParsedQuery(
        raw_query=raw_query,
        intent=intent,
        intent_confidence=0.9,
        companies=companies or [],
        competitors=competitors or [],
        market_intel_style=market_intel_style,
        competitor_intel_style=competitor_intel_style,
        is_realtime_needed=is_realtime_needed,
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
# Tier mapping tests
# =============================================================================


class TestDataSourceTiers:
    def test_sap_is_tier_1(self):
        assert (
            get_datasource_tier(DataSource.SAP_MCP)
            == SourceTier.TIER_1_INTERNAL_STRUCTURED
        )

    def test_billing_is_tier_1(self):
        assert (
            get_datasource_tier(DataSource.BILLING_AGENT)
            == SourceTier.TIER_1_INTERNAL_STRUCTURED
        )

    def test_knowledge_base_is_tier_1(self):
        assert (
            get_datasource_tier(DataSource.KNOWLEDGE_BASE)
            == SourceTier.TIER_1_INTERNAL_STRUCTURED
        )

    def test_vectordb_is_tier_2(self):
        assert (
            get_datasource_tier(DataSource.LOCAL_VECTORDB)
            == SourceTier.TIER_2_INTERNAL_SEMANTIC
        )

    def test_eodhd_is_tier_3(self):
        assert (
            get_datasource_tier(DataSource.EODHD) == SourceTier.TIER_3_EXTERNAL_TRUSTED
        )

    def test_perplexity_is_tier_4(self):
        assert (
            get_datasource_tier(DataSource.PERPLEXITY)
            == SourceTier.TIER_4_EXTERNAL_BROAD
        )

    def test_newsapi_is_tier_4(self):
        assert (
            get_datasource_tier(DataSource.NEWSAPI) == SourceTier.TIER_4_EXTERNAL_BROAD
        )


# =============================================================================
# BILLING_AR — INTERNAL ONLY, web BLOCKED
# =============================================================================


class TestBillingAR:
    """Billing queries must NEVER use web sources."""

    def test_billing_forbids_perplexity(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show billing items")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_billing_forbids_newsapi(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show aging buckets")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.NEWSAPI in decision.forbidden_sources

    def test_billing_requires_billing_agent(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show billing items")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.BILLING_AGENT in decision.required_sources

    def test_billing_web_gate_blocked(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show overdue invoices")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.web_search_gate == WebSearchGate.BLOCKED

    def test_billing_fallback_internal_only(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show collections")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.fallback_strategy == FallbackStrategy.INTERNAL_ONLY

    def test_billing_fallback_sources_no_web(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show aging")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        fallbacks = decision.get_fallback_sources()
        assert DataSource.PERPLEXITY not in fallbacks
        assert DataSource.NEWSAPI not in fallbacks

    def test_billing_execution_order_no_web(self):
        parsed = _make_parsed(QueryIntent.BILLING_AR, "Show billing items")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        order = decision.get_execution_order()
        assert DataSource.PERPLEXITY not in order
        assert DataSource.NEWSAPI not in order
        assert DataSource.BILLING_AGENT in order


# =============================================================================
# PRODUCT_FIT / PRODUCT_INFO — INTERNAL ONLY, web BLOCKED
# =============================================================================


class TestProductFit:
    """Product queries must NEVER use web sources — specs from KB only."""

    def test_product_fit_forbids_perplexity(self):
        parsed = _make_parsed(QueryIntent.PRODUCT_FIT, "MTU 12V 2000 specs")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_product_fit_requires_kb(self):
        parsed = _make_parsed(QueryIntent.PRODUCT_FIT, "Compare engines")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources

    def test_product_fit_web_gate_blocked(self):
        parsed = _make_parsed(QueryIntent.PRODUCT_FIT, "Engine fuel consumption")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.web_search_gate == WebSearchGate.BLOCKED

    def test_product_info_same_rules(self):
        parsed = _make_parsed(QueryIntent.PRODUCT_INFO, "Bergen B35:40 specs")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources

    def test_product_keeps_kb_even_without_local_data(self):
        """KB has Technical Reference fallback — never demote for product intents."""
        parsed = _make_parsed(QueryIntent.PRODUCT_FIT, "MTU specs")
        decision = SourceAuthority.decide(parsed, _make_inventory(has_local_data=False))
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources


# =============================================================================
# RELATIONSHIP_CHECK — INTERNAL ONLY, web BLOCKED
# =============================================================================


class TestRelationshipCheck:
    def test_relationship_forbids_web(self):
        parsed = _make_parsed(
            QueryIntent.RELATIONSHIP_CHECK, "Our position with Maersk"
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        assert DataSource.NEWSAPI in decision.forbidden_sources

    def test_relationship_requires_sap(self):
        parsed = _make_parsed(QueryIntent.RELATIONSHIP_CHECK, "Share of wallet")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.SAP_MCP in decision.required_sources


# =============================================================================
# CUSTOMER_INTEL — web GATED by sub-intent
# =============================================================================


class TestCustomerIntel:
    """Customer data queries block web. Customer news queries allow web."""

    def test_customer_data_blocks_perplexity(self):
        """Default style (opportunities) should block Perplexity."""
        parsed = _make_parsed(
            QueryIntent.CUSTOMER_INTEL,
            "What is ST Engineering's payment track record?",
            companies=["ST Engineering"],
            market_intel_style="opportunities",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_customer_news_allows_perplexity(self):
        """News style should allow Perplexity."""
        parsed = _make_parsed(
            QueryIntent.CUSTOMER_INTEL,
            "Latest news about ST Engineering",
            companies=["ST Engineering"],
            market_intel_style="news",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY not in decision.forbidden_sources
        assert DataSource.PERPLEXITY in decision.permitted_sources

    def test_customer_requires_sap(self):
        parsed = _make_parsed(QueryIntent.CUSTOMER_INTEL, "Customer profile")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.SAP_MCP in decision.required_sources

    def test_customer_web_gate_is_gated(self):
        parsed = _make_parsed(QueryIntent.CUSTOMER_INTEL, "Customer data")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.web_search_gate == WebSearchGate.GATED_BY_SUBINTENT


# =============================================================================
# COMPETITOR_INTEL — web GATED by sub-intent
# =============================================================================


class TestCompetitorIntel:
    """Competitive analysis blocks web. Competitor news allows web."""

    def test_competitor_analysis_blocks_perplexity(self):
        parsed = _make_parsed(
            QueryIntent.COMPETITOR_INTEL,
            "Competitive position against Caterpillar",
            competitors=["Caterpillar"],
            competitor_intel_style="analysis",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources

    def test_competitor_news_allows_perplexity(self):
        parsed = _make_parsed(
            QueryIntent.COMPETITOR_INTEL,
            "What are the latest updates from Caterpillar?",
            competitors=["Caterpillar"],
            competitor_intel_style="news",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY not in decision.forbidden_sources

    def test_competitor_requires_kb_and_vectordb(self):
        parsed = _make_parsed(QueryIntent.COMPETITOR_INTEL, "Competitor activity")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources
        assert DataSource.LOCAL_VECTORDB in decision.required_sources

    def test_competitor_forbids_newsapi(self):
        parsed = _make_parsed(QueryIntent.COMPETITOR_INTEL, "Competitor updates")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.NEWSAPI in decision.forbidden_sources


# =============================================================================
# KYP_DUE_DILIGENCE — targeted web allowed
# =============================================================================


class TestKYP:
    """KYP allows Perplexity for targeted sanctions/litigation searches."""

    def test_kyp_permits_perplexity(self):
        parsed = _make_parsed(QueryIntent.KYP_DUE_DILIGENCE, "Run KYP on Maersk")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.permitted_sources
        assert DataSource.PERPLEXITY not in decision.forbidden_sources

    def test_kyp_requires_sap(self):
        parsed = _make_parsed(QueryIntent.KYP_DUE_DILIGENCE, "KYP on ST Engineering")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.SAP_MCP in decision.required_sources

    def test_kyp_permits_eodhd(self):
        parsed = _make_parsed(QueryIntent.KYP_DUE_DILIGENCE, "Due diligence")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.EODHD in decision.permitted_sources

    def test_kyp_forbids_newsapi(self):
        parsed = _make_parsed(QueryIntent.KYP_DUE_DILIGENCE, "KYP check")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.NEWSAPI in decision.forbidden_sources


# =============================================================================
# MARKET_INTEL — web allowed as supplement
# =============================================================================


class TestMarketIntel:
    """Market intel can use web search, but internal first."""

    def test_market_intel_allows_perplexity(self):
        parsed = _make_parsed(QueryIntent.MARKET_INTEL, "Market opportunities in APAC")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY not in decision.forbidden_sources

    def test_market_intel_requires_vectordb(self):
        parsed = _make_parsed(QueryIntent.MARKET_INTEL, "APAC marine trends")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.LOCAL_VECTORDB in decision.required_sources

    def test_market_intel_web_gate_supplement(self):
        parsed = _make_parsed(QueryIntent.MARKET_INTEL, "Market trends")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.web_search_gate == WebSearchGate.ALLOWED_AS_SUPPLEMENT

    def test_market_news_allows_primary_web(self):
        parsed = _make_parsed(QueryIntent.MARKET_NEWS, "Latest maritime news")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert decision.web_search_gate == WebSearchGate.ALLOWED_PRIMARY
        assert DataSource.PERPLEXITY in decision.permitted_sources


# =============================================================================
# GENERAL_QUESTION — permissive
# =============================================================================


class TestGeneralQuestion:
    def test_general_allows_all(self):
        parsed = _make_parsed(QueryIntent.GENERAL_QUESTION, "What is an OSV?")
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert len(decision.forbidden_sources) == 0
        assert decision.fallback_strategy == FallbackStrategy.FULL_FALLBACK


# =============================================================================
# Source Decision methods
# =============================================================================


class TestSourceDecision:
    def test_is_source_allowed_required(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        assert decision.is_source_allowed(DataSource.BILLING_AGENT) is True

    def test_is_source_allowed_forbidden(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        assert decision.is_source_allowed(DataSource.PERPLEXITY) is False

    def test_is_source_allowed_openai_always(self):
        """OPENAI (synthesis) should always be allowed."""
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        assert decision.is_source_allowed(DataSource.OPENAI) is True

    def test_execution_order_ends_with_openai(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.PRODUCT_FIT, "specs"),
            _make_inventory(),
        )
        order = decision.get_execution_order()
        assert order[-1] == DataSource.OPENAI

    def test_execution_order_excludes_forbidden(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        order = decision.get_execution_order()
        for forbidden in decision.forbidden_sources:
            assert forbidden not in order


# =============================================================================
# Fallback strategy tests
# =============================================================================


class TestFallbackStrategies:
    def test_internal_only_no_web_fallbacks(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        fallbacks = decision.get_fallback_sources()
        for fb in fallbacks:
            assert SourceAuthority.is_web_source(fb) is False

    def test_full_fallback_includes_web(self):
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.MARKET_INTEL, "market trends"),
            _make_inventory(),
        )
        fallbacks = decision.get_fallback_sources()
        has_web = any(SourceAuthority.is_web_source(fb) for fb in fallbacks)
        assert has_web is True

    def test_escalate_with_gate_respects_gate(self):
        # Competitor analysis — gate is GATED_BY_SUBINTENT but Perplexity is forbidden
        decision = SourceAuthority.decide(
            _make_parsed(
                QueryIntent.COMPETITOR_INTEL,
                "Competitive position",
                competitor_intel_style="analysis",
            ),
            _make_inventory(),
        )
        fallbacks = decision.get_fallback_sources()
        # Perplexity was forbidden by sub-intent gate, so not in fallbacks
        assert DataSource.PERPLEXITY not in fallbacks


# =============================================================================
# Inventory adjustments
# =============================================================================


class TestInventoryAdjustments:
    def test_no_local_data_demotes_vectordb(self):
        parsed = _make_parsed(QueryIntent.COMPETITOR_INTEL, "Competitor activity")
        decision = SourceAuthority.decide(parsed, _make_inventory(has_local_data=False))
        # LOCAL_VECTORDB should be demoted from required to permitted
        assert DataSource.LOCAL_VECTORDB not in decision.required_sources
        assert DataSource.LOCAL_VECTORDB in decision.permitted_sources

    def test_product_fit_keeps_kb_without_local_data(self):
        parsed = _make_parsed(QueryIntent.PRODUCT_FIT, "MTU 4000 specs")
        decision = SourceAuthority.decide(parsed, _make_inventory(has_local_data=False))
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    def test_competitor_entity_in_customer_intent(self):
        """If competitors extracted but intent is customer_intel, use competitor rules."""
        parsed = _make_parsed(
            QueryIntent.CUSTOMER_INTEL,
            "What is Caterpillar doing?",
            competitors=["Caterpillar"],
            companies=[],
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        # Should reclassify to competitor rules
        assert DataSource.KNOWLEDGE_BASE in decision.required_sources

    def test_openai_never_forbidden(self):
        """OPENAI should never appear in forbidden_sources."""
        for intent in QueryIntent:
            parsed = _make_parsed(intent, "test")
            decision = SourceAuthority.decide(parsed, _make_inventory())
            assert DataSource.OPENAI not in decision.forbidden_sources

    def test_decision_is_frozen(self):
        """SourceDecision should be immutable."""
        decision = SourceAuthority.decide(
            _make_parsed(QueryIntent.BILLING_AR, "billing"),
            _make_inventory(),
        )
        with pytest.raises(AttributeError):
            decision.rationale = "hacked"

    def test_no_inventory_still_works(self):
        """Should work even without inventory."""
        parsed = _make_parsed(QueryIntent.BILLING_AR, "billing")
        decision = SourceAuthority.decide(parsed, None)
        assert DataSource.BILLING_AGENT in decision.required_sources


# =============================================================================
# The critical scenario that motivated this module
# =============================================================================


class TestCriticalScenario:
    """
    The failure that drove this work:
    'What is ST Engineering's payment track record?' was mixing web sources.
    """

    def test_payment_track_record_no_web(self):
        """Payment track record must use internal data ONLY."""
        parsed = _make_parsed(
            QueryIntent.CUSTOMER_INTEL,
            "What is ST Engineering's payment track record?",
            companies=["ST Engineering"],
            market_intel_style="opportunities",  # default — not news
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())

        # Web must be forbidden
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        assert DataSource.NEWSAPI in decision.forbidden_sources

        # SAP must be required
        assert DataSource.SAP_MCP in decision.required_sources

        # Execution order must have no web
        order = decision.get_execution_order()
        assert DataSource.PERPLEXITY not in order
        assert DataSource.NEWSAPI not in order

        # Fallback must have no web
        fallbacks = decision.get_fallback_sources()
        assert DataSource.PERPLEXITY not in fallbacks
        assert DataSource.NEWSAPI not in fallbacks

    def test_product_specs_no_web(self):
        """Engine specs must come from KB only, never web."""
        parsed = _make_parsed(
            QueryIntent.PRODUCT_FIT,
            "What are the specs for MTU 12V 2000 M93?",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        order = decision.get_execution_order()
        assert DataSource.PERPLEXITY not in order

    def test_billing_items_no_web(self):
        """Billing items must come from BillingBrain only, never web."""
        parsed = _make_parsed(
            QueryIntent.BILLING_AR,
            "Show overdue invoices for ST Engineering",
        )
        decision = SourceAuthority.decide(parsed, _make_inventory())
        assert DataSource.PERPLEXITY in decision.forbidden_sources
        assert DataSource.BILLING_AGENT in decision.required_sources
        assert (
            len(
                [
                    s
                    for s in decision.get_execution_order()
                    if SourceAuthority.is_web_source(s)
                ]
            )
            == 0
        )
