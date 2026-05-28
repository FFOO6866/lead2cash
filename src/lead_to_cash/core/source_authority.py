"""
Source-of-Truth Routing Layer

Deterministic, rule-based gate that sits between intent classification
and tool execution. Decides which data sources are ALLOWED, REQUIRED,
and FORBIDDEN for each query based on intent and context.

This module solves the critical flaw where internal enterprise queries
(billing, credit, product specs) were polluted by web search results.

Architecture position:
    QueryUnderstandingEngine.parse()  →  intent + entities
    DataInventoryService.check()     →  coverage assessment
    SourceAuthority.decide()         →  SourceDecision  ← THIS MODULE
    ToolExecutor.execute()           →  uses ONLY permitted sources

Design principles:
    - Deterministic: no LLM involvement in source selection
    - Rule-based: lookup table with conditional gates
    - Enterprise-safe: internal data queries NEVER leak to web search
    - Extensible: new intents default to permissive, tightened as needed
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set

from lead_to_cash.core.data_inventory import DataSource, InventoryCheckResult
from lead_to_cash.core.query_understanding import ParsedQuery, QueryIntent
from lead_to_cash.core.response_quality import SourceTier

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class FallbackStrategy(str, Enum):
    """What to do when required sources return insufficient data."""

    INTERNAL_ONLY = "internal_only"
    """Return 'data unavailable'. Never escalate to web search."""

    ESCALATE_ONE_TIER = "escalate_one_tier"
    """Try next tier up (Tier 1 failed → Tier 2). Stop before Tier 4."""

    ESCALATE_WITH_GATE = "escalate_with_gate"
    """Allow Tier 4 only if gated condition is met (e.g., KYP sanctions)."""

    FULL_FALLBACK = "full_fallback"
    """Allow all tiers including web search (market intel, general)."""


class WebSearchGate(str, Enum):
    """Under what conditions web search (Perplexity/NewsAPI) is allowed."""

    BLOCKED = "blocked"
    """Web search is never allowed for this query type."""

    GATED_BY_SUBINTENT = "gated_by_subintent"
    """Web search allowed only when sub-intent signals external data needed."""

    ALLOWED_AS_SUPPLEMENT = "allowed_as_supplement"
    """Web search allowed but results must be labelled as external."""

    ALLOWED_PRIMARY = "allowed_primary"
    """Web search is a primary/expected source for this query type."""


# =============================================================================
# Source Decision
# =============================================================================


@dataclass(frozen=True)
class SourceDecision:
    """
    Deterministic decision about which data sources to use for a query.

    Produced by SourceAuthority.decide(), consumed by ToolExecutor.execute().
    """

    required_sources: tuple[DataSource, ...]
    """Sources that MUST be executed."""

    permitted_sources: tuple[DataSource, ...]
    """Sources that MAY be executed if needed (after required)."""

    forbidden_sources: frozenset[DataSource]
    """Sources that MUST NOT be executed under any circumstances."""

    max_tier: SourceTier
    """Highest (numerically largest) tier allowed."""

    fallback_strategy: FallbackStrategy
    """What to do when required sources return insufficient data."""

    web_search_gate: WebSearchGate
    """Under what conditions web search is allowed."""

    rationale: str
    """Human-readable explanation for logging/debugging."""

    def is_source_allowed(self, source: DataSource) -> bool:
        """Check if a specific source is allowed by this decision."""
        if source in self.forbidden_sources:
            return False
        if source in self.required_sources or source in self.permitted_sources:
            return True
        # OPENAI is always allowed (synthesis, not a data source)
        if source == DataSource.OPENAI:
            return True
        return False

    def get_execution_order(self) -> List[DataSource]:
        """Return the ordered list of sources to execute."""
        result = list(self.required_sources)
        for source in self.permitted_sources:
            if source not in result:
                result.append(source)
        # OPENAI always last (synthesis)
        if DataSource.OPENAI not in result:
            result.append(DataSource.OPENAI)
        return result

    def get_fallback_sources(self) -> List[DataSource]:
        """Return allowed fallback sources respecting strategy and gates."""
        if self.fallback_strategy == FallbackStrategy.INTERNAL_ONLY:
            # Only Tier 1-2 sources as fallbacks
            return [
                s
                for s in [
                    DataSource.LOCAL_VECTORDB,
                    DataSource.KNOWLEDGE_BASE,
                    DataSource.SAP_MCP,
                ]
                if s not in self.forbidden_sources and s not in self.required_sources
            ]

        if self.fallback_strategy == FallbackStrategy.ESCALATE_ONE_TIER:
            # Tier 1-3 sources, no web
            return [
                s
                for s in [
                    DataSource.LOCAL_VECTORDB,
                    DataSource.KNOWLEDGE_BASE,
                    DataSource.SAP_MCP,
                    DataSource.EODHD,
                ]
                if s not in self.forbidden_sources and s not in self.required_sources
            ]

        if self.fallback_strategy == FallbackStrategy.ESCALATE_WITH_GATE:
            # Include web only if gate allows
            sources = [
                s
                for s in [
                    DataSource.LOCAL_VECTORDB,
                    DataSource.KNOWLEDGE_BASE,
                    DataSource.SAP_MCP,
                    DataSource.EODHD,
                ]
                if s not in self.forbidden_sources and s not in self.required_sources
            ]
            if self.web_search_gate != WebSearchGate.BLOCKED:
                if DataSource.PERPLEXITY not in self.forbidden_sources:
                    sources.append(DataSource.PERPLEXITY)
            return sources

        # FULL_FALLBACK — everything except forbidden
        return [
            s
            for s in [
                DataSource.LOCAL_VECTORDB,
                DataSource.KNOWLEDGE_BASE,
                DataSource.SAP_MCP,
                DataSource.EODHD,
                DataSource.PERPLEXITY,
                DataSource.NEWSAPI,
            ]
            if s not in self.forbidden_sources and s not in self.required_sources
        ]


# =============================================================================
# DataSource to SourceTier mapping
# =============================================================================

DATASOURCE_TIER: Dict[DataSource, SourceTier] = {
    DataSource.BILLING_AGENT: SourceTier.TIER_1_INTERNAL_STRUCTURED,
    DataSource.SAP_MCP: SourceTier.TIER_1_INTERNAL_STRUCTURED,
    DataSource.KNOWLEDGE_BASE: SourceTier.TIER_1_INTERNAL_STRUCTURED,
    DataSource.LOCAL_VECTORDB: SourceTier.TIER_2_INTERNAL_SEMANTIC,
    DataSource.COMPETITOR_DB: SourceTier.TIER_2_INTERNAL_SEMANTIC,
    DataSource.EODHD: SourceTier.TIER_3_EXTERNAL_TRUSTED,
    DataSource.PERPLEXITY: SourceTier.TIER_4_EXTERNAL_BROAD,
    DataSource.NEWSAPI: SourceTier.TIER_4_EXTERNAL_BROAD,
}


def get_datasource_tier(source: DataSource) -> SourceTier:
    """Get the trust tier for a DataSource."""
    return DATASOURCE_TIER.get(source, SourceTier.TIER_4_EXTERNAL_BROAD)


# =============================================================================
# Web sources set (for quick lookup)
# =============================================================================

_WEB_SOURCES: FrozenSet[DataSource] = frozenset(
    {DataSource.PERPLEXITY, DataSource.NEWSAPI}
)


# =============================================================================
# Intent source rules — the core decision table
# =============================================================================


@dataclass(frozen=True)
class _IntentSourceRule:
    """Source selection rule for a single intent."""

    required: tuple[DataSource, ...]
    permitted: tuple[DataSource, ...]
    forbidden: frozenset[DataSource]
    max_tier: SourceTier
    fallback: FallbackStrategy
    web_gate: WebSearchGate
    rationale: str


# fmt: off
_INTENT_RULES: Dict[QueryIntent, _IntentSourceRule] = {
    # ── Finance / Internal Enterprise ──────────────────────────────────
    QueryIntent.BILLING_AR: _IntentSourceRule(
        required=(DataSource.BILLING_AGENT,),
        permitted=(),
        forbidden=frozenset({DataSource.PERPLEXITY, DataSource.NEWSAPI, DataSource.EODHD,
                             DataSource.LOCAL_VECTORDB, DataSource.SAP_MCP, DataSource.KNOWLEDGE_BASE}),
        max_tier=SourceTier.TIER_1_INTERNAL_STRUCTURED,
        fallback=FallbackStrategy.INTERNAL_ONLY,
        web_gate=WebSearchGate.BLOCKED,
        rationale="Billing/AR is 100% internal data. BillingBrain queries SAP internally.",
    ),
    QueryIntent.RELATIONSHIP_CHECK: _IntentSourceRule(
        required=(DataSource.SAP_MCP,),
        permitted=(DataSource.LOCAL_VECTORDB,),
        forbidden=frozenset({DataSource.PERPLEXITY, DataSource.NEWSAPI, DataSource.EODHD}),
        max_tier=SourceTier.TIER_2_INTERNAL_SEMANTIC,
        fallback=FallbackStrategy.INTERNAL_ONLY,
        web_gate=WebSearchGate.BLOCKED,
        rationale="Customer relationship data is internal CRM/SAP data only.",
    ),

    # ── Product / Knowledge Base ───────────────────────────────────────
    QueryIntent.PRODUCT_FIT: _IntentSourceRule(
        required=(DataSource.KNOWLEDGE_BASE,),
        permitted=(DataSource.LOCAL_VECTORDB,),
        forbidden=frozenset({DataSource.PERPLEXITY, DataSource.NEWSAPI, DataSource.EODHD}),
        max_tier=SourceTier.TIER_2_INTERNAL_SEMANTIC,
        fallback=FallbackStrategy.INTERNAL_ONLY,
        web_gate=WebSearchGate.BLOCKED,
        rationale="Product specs must come from verified KB. Web search risks hallucinated specs.",
    ),
    QueryIntent.PRODUCT_INFO: _IntentSourceRule(
        required=(DataSource.KNOWLEDGE_BASE,),
        permitted=(DataSource.LOCAL_VECTORDB,),
        forbidden=frozenset({DataSource.PERPLEXITY, DataSource.NEWSAPI, DataSource.EODHD}),
        max_tier=SourceTier.TIER_2_INTERNAL_SEMANTIC,
        fallback=FallbackStrategy.INTERNAL_ONLY,
        web_gate=WebSearchGate.BLOCKED,
        rationale="Product info must come from verified KB only.",
    ),

    # ── Customer Intelligence (sub-intent gated) ──────────────────────
    QueryIntent.CUSTOMER_INTEL: _IntentSourceRule(
        required=(DataSource.SAP_MCP, DataSource.LOCAL_VECTORDB),
        permitted=(DataSource.KNOWLEDGE_BASE,),
        forbidden=frozenset({DataSource.NEWSAPI}),
        max_tier=SourceTier.TIER_3_EXTERNAL_TRUSTED,
        fallback=FallbackStrategy.ESCALATE_WITH_GATE,
        web_gate=WebSearchGate.GATED_BY_SUBINTENT,
        rationale="SAP is primary for customer data. Web only if user asks for news (style=news).",
    ),
    QueryIntent.CUSTOMER_RESEARCH: _IntentSourceRule(
        required=(DataSource.SAP_MCP, DataSource.LOCAL_VECTORDB),
        permitted=(DataSource.KNOWLEDGE_BASE,),
        forbidden=frozenset({DataSource.NEWSAPI}),
        max_tier=SourceTier.TIER_3_EXTERNAL_TRUSTED,
        fallback=FallbackStrategy.ESCALATE_WITH_GATE,
        web_gate=WebSearchGate.GATED_BY_SUBINTENT,
        rationale="Legacy customer research — same rules as customer_intel.",
    ),

    # ── Competitor Intelligence (sub-intent gated) ────────────────────
    QueryIntent.COMPETITOR_INTEL: _IntentSourceRule(
        required=(DataSource.LOCAL_VECTORDB, DataSource.KNOWLEDGE_BASE),
        permitted=(DataSource.EODHD,),
        forbidden=frozenset({DataSource.NEWSAPI}),
        max_tier=SourceTier.TIER_3_EXTERNAL_TRUSTED,
        fallback=FallbackStrategy.ESCALATE_WITH_GATE,
        web_gate=WebSearchGate.GATED_BY_SUBINTENT,
        rationale="Competitor DB + KB primary. Perplexity only for news-style queries.",
    ),
    QueryIntent.FINANCIAL_ANALYSIS: _IntentSourceRule(
        required=(DataSource.EODHD,),
        permitted=(DataSource.LOCAL_VECTORDB,),
        forbidden=frozenset({DataSource.NEWSAPI}),
        max_tier=SourceTier.TIER_3_EXTERNAL_TRUSTED,
        fallback=FallbackStrategy.ESCALATE_WITH_GATE,
        web_gate=WebSearchGate.GATED_BY_SUBINTENT,
        rationale="EODHD is structured financial data. Perplexity only for analyst commentary if insufficient.",
    ),

    # ── KYP Due Diligence (targeted web allowed) ──────────────────────
    QueryIntent.KYP_DUE_DILIGENCE: _IntentSourceRule(
        required=(DataSource.SAP_MCP,),
        permitted=(DataSource.EODHD, DataSource.LOCAL_VECTORDB, DataSource.PERPLEXITY),
        forbidden=frozenset({DataSource.NEWSAPI}),
        max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
        fallback=FallbackStrategy.ESCALATE_WITH_GATE,
        web_gate=WebSearchGate.GATED_BY_SUBINTENT,
        rationale="KYP requires external sanctions/litigation checks via targeted Perplexity searches.",
    ),

    # ── Market Intelligence (web expected) ─────────────────────────────
    QueryIntent.MARKET_INTEL: _IntentSourceRule(
        required=(DataSource.LOCAL_VECTORDB,),
        permitted=(DataSource.SAP_MCP, DataSource.KNOWLEDGE_BASE, DataSource.PERPLEXITY),
        forbidden=frozenset(),
        max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
        fallback=FallbackStrategy.FULL_FALLBACK,
        web_gate=WebSearchGate.ALLOWED_AS_SUPPLEMENT,
        rationale="Market intel legitimately needs real-time web data, but internal first.",
    ),
    QueryIntent.MARKET_NEWS: _IntentSourceRule(
        required=(DataSource.LOCAL_VECTORDB,),
        permitted=(DataSource.PERPLEXITY, DataSource.NEWSAPI),
        forbidden=frozenset(),
        max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
        fallback=FallbackStrategy.FULL_FALLBACK,
        web_gate=WebSearchGate.ALLOWED_PRIMARY,
        rationale="News is inherently external. Web search is primary source.",
    ),
    QueryIntent.SALES_OPPORTUNITY: _IntentSourceRule(
        required=(DataSource.LOCAL_VECTORDB, DataSource.SAP_MCP),
        permitted=(DataSource.PERPLEXITY,),
        forbidden=frozenset(),
        max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
        fallback=FallbackStrategy.FULL_FALLBACK,
        web_gate=WebSearchGate.ALLOWED_AS_SUPPLEMENT,
        rationale="Sales opportunities — internal pipeline + market context.",
    ),

    # ── General / Catch-all ────────────────────────────────────────────
    QueryIntent.GENERAL_QUESTION: _IntentSourceRule(
        required=(DataSource.LOCAL_VECTORDB,),
        permitted=(DataSource.KNOWLEDGE_BASE, DataSource.PERPLEXITY),
        forbidden=frozenset(),
        max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
        fallback=FallbackStrategy.FULL_FALLBACK,
        web_gate=WebSearchGate.ALLOWED_AS_SUPPLEMENT,
        rationale="General questions have no domain constraint. All sources allowed.",
    ),
}
# fmt: on


# Default rule for unmapped intents — permissive to avoid blocking
_DEFAULT_RULE = _IntentSourceRule(
    required=(DataSource.LOCAL_VECTORDB,),
    permitted=(DataSource.KNOWLEDGE_BASE, DataSource.SAP_MCP, DataSource.PERPLEXITY),
    forbidden=frozenset(),
    max_tier=SourceTier.TIER_4_EXTERNAL_BROAD,
    fallback=FallbackStrategy.FULL_FALLBACK,
    web_gate=WebSearchGate.ALLOWED_AS_SUPPLEMENT,
    rationale="Default permissive rule for unmapped intent.",
)


# =============================================================================
# Source Authority
# =============================================================================


class SourceAuthority:
    """
    Deterministic source-of-truth routing layer.

    Decides which data sources are allowed for a query based on:
    1. Intent (from QueryUnderstandingEngine)
    2. Sub-intent signals (market_intel_style, competitor_intel_style)
    3. Inventory coverage (from DataInventoryService)

    This class contains NO LLM calls. All decisions are rule-based.
    """

    @classmethod
    def decide(
        cls,
        parsed_query: ParsedQuery,
        inventory: Optional[InventoryCheckResult] = None,
    ) -> SourceDecision:
        """
        Produce a deterministic source decision for a query.

        Args:
            parsed_query: Classified query from QueryUnderstandingEngine
            inventory: Coverage assessment from DataInventoryService (optional)

        Returns:
            SourceDecision with required, permitted, forbidden sources
        """
        intent = parsed_query.intent
        rule = _INTENT_RULES.get(intent, _DEFAULT_RULE)

        # Start with the base rule
        required = list(rule.required)
        permitted = list(rule.permitted)
        forbidden = set(rule.forbidden)
        max_tier = rule.max_tier
        fallback = rule.fallback
        web_gate = rule.web_gate
        rationale_parts = [rule.rationale]

        # ── Sub-intent gates ──────────────────────────────────────────
        # These conditionally allow or block web search based on query signals
        cls._apply_subintent_gates(
            parsed_query, required, permitted, forbidden, rationale_parts
        )

        # ── Inventory-based adjustments ──────────────────────────────
        if inventory:
            cls._apply_inventory_adjustments(
                parsed_query, inventory, required, permitted, forbidden, rationale_parts
            )

        # ── Competitor entity override ───────────────────────────────
        # If competitors extracted but intent is customer_intel, use competitor rules
        if (
            intent == QueryIntent.CUSTOMER_INTEL
            and parsed_query.competitors
            and not parsed_query.companies
        ):
            competitor_rule = _INTENT_RULES[QueryIntent.COMPETITOR_INTEL]
            required = list(competitor_rule.required)
            permitted = list(competitor_rule.permitted)
            forbidden = set(competitor_rule.forbidden)
            max_tier = competitor_rule.max_tier
            web_gate = competitor_rule.web_gate
            rationale_parts.append(
                "Reclassified to competitor_intel rules: competitors extracted with customer_intel intent."
            )

        # ── Ensure OPENAI is never forbidden (it's synthesis, not data)
        forbidden.discard(DataSource.OPENAI)

        decision = SourceDecision(
            required_sources=tuple(required),
            permitted_sources=tuple(permitted),
            forbidden_sources=frozenset(forbidden),
            max_tier=max_tier,
            fallback_strategy=fallback,
            web_search_gate=web_gate,
            rationale=" | ".join(rationale_parts),
        )

        logger.info(
            f"SourceAuthority decision: intent={intent.value}, "
            f"required={[s.value for s in required]}, "
            f"forbidden_count={len(forbidden)}, "
            f"web_gate={web_gate.value}, "
            f"fallback={fallback.value}"
        )

        return decision

    @classmethod
    def _apply_subintent_gates(
        cls,
        parsed_query: ParsedQuery,
        required: List[DataSource],
        permitted: List[DataSource],
        forbidden: Set[DataSource],
        rationale_parts: List[str],
    ) -> None:
        """Apply sub-intent specific source gates."""
        intent = parsed_query.intent

        # ── customer_intel: web only for news style ─────────────────
        if intent in (QueryIntent.CUSTOMER_INTEL, QueryIntent.CUSTOMER_RESEARCH):
            if getattr(parsed_query, "market_intel_style", "opportunities") == "news":
                # User wants news about a company — allow Perplexity
                if DataSource.PERPLEXITY not in permitted:
                    permitted.append(DataSource.PERPLEXITY)
                forbidden.discard(DataSource.PERPLEXITY)
                rationale_parts.append("Web allowed: customer news style detected.")
            else:
                # User wants SAP/CRM data — block Perplexity
                forbidden.add(DataSource.PERPLEXITY)
                if DataSource.PERPLEXITY in permitted:
                    permitted.remove(DataSource.PERPLEXITY)
                rationale_parts.append("Web blocked: customer data/pipeline style.")

        # ── competitor_intel: web only for news style ───────────────
        elif intent == QueryIntent.COMPETITOR_INTEL:
            if getattr(parsed_query, "competitor_intel_style", "news") == "news":
                # User wants competitor updates — allow Perplexity
                if DataSource.PERPLEXITY not in permitted:
                    permitted.append(DataSource.PERPLEXITY)
                forbidden.discard(DataSource.PERPLEXITY)
                rationale_parts.append("Web allowed: competitor news style detected.")
            else:
                # User wants competitive analysis — KB + Competitor DB only
                forbidden.add(DataSource.PERPLEXITY)
                if DataSource.PERPLEXITY in permitted:
                    permitted.remove(DataSource.PERPLEXITY)
                rationale_parts.append(
                    "Web blocked: competitive analysis style (KB/DB only)."
                )

        # ── financial_analysis: web for analyst commentary ──────────
        elif intent == QueryIntent.FINANCIAL_ANALYSIS:
            if parsed_query.is_realtime_needed:
                if DataSource.PERPLEXITY not in permitted:
                    permitted.append(DataSource.PERPLEXITY)
                forbidden.discard(DataSource.PERPLEXITY)
                rationale_parts.append(
                    "Web allowed: real-time financial data requested."
                )
            else:
                forbidden.add(DataSource.PERPLEXITY)
                if DataSource.PERPLEXITY in permitted:
                    permitted.remove(DataSource.PERPLEXITY)
                rationale_parts.append(
                    "Web blocked: standard financial analysis (EODHD only)."
                )

        # ── KYP: Perplexity is permitted for targeted searches ──────
        # KYP's Perplexity usage goes through _execute_kyp_intelligent()
        # which runs targeted category-specific searches, not broad web.
        # We keep it in permitted (set by rule) — no change needed.

    @classmethod
    def _apply_inventory_adjustments(
        cls,
        parsed_query: ParsedQuery,
        inventory: InventoryCheckResult,
        required: List[DataSource],
        permitted: List[DataSource],
        forbidden: Set[DataSource],
        rationale_parts: List[str],
    ) -> None:
        """Adjust source selection based on data inventory coverage."""
        # If no local data and LOCAL_VECTORDB is required, move to permitted
        # (don't waste time on empty search, but don't forbid it)
        if not inventory.has_local_data:
            if DataSource.LOCAL_VECTORDB in required:
                required.remove(DataSource.LOCAL_VECTORDB)
                if DataSource.LOCAL_VECTORDB not in permitted:
                    permitted.insert(0, DataSource.LOCAL_VECTORDB)
                rationale_parts.append(
                    "LOCAL_VECTORDB demoted: no local data available."
                )

            # Keep KNOWLEDGE_BASE for product intents — has Technical Reference fallback
            if DataSource.KNOWLEDGE_BASE in required and parsed_query.intent not in (
                QueryIntent.PRODUCT_FIT,
                QueryIntent.PRODUCT_INFO,
            ):
                required.remove(DataSource.KNOWLEDGE_BASE)
                if DataSource.KNOWLEDGE_BASE not in permitted:
                    permitted.insert(0, DataSource.KNOWLEDGE_BASE)
                rationale_parts.append(
                    "KNOWLEDGE_BASE demoted: no local data (non-product intent)."
                )

    @classmethod
    def is_web_source(cls, source: DataSource) -> bool:
        """Check if a DataSource is a web/external broad source."""
        return source in _WEB_SOURCES

    @classmethod
    def get_datasource_tier(cls, source: DataSource) -> SourceTier:
        """Get the trust tier for a DataSource."""
        return get_datasource_tier(source)
