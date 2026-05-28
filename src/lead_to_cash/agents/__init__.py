"""
Lead-to-Cash AI Agents Module

Production-ready Kaizen agents for RRPS sales intelligence operations.
Implements A2A (Agent-to-Agent) architecture using Kaizen Pipeline patterns.

Domain Agents (Non-Overlapping Responsibilities):
    - MarineIntelAgent (alias: MarketIntelAgent): Industry news, opportunities, events
    - CustomerMatcherAgent (alias: CustomerIntelAgent): Customer profiling, SAP lookup, matching
    - CompetitorIntelAgent: CAT, Cummins, MAN tracking - wins, products, threats
    - DueDiligenceAgent (alias: KYPAgent): Due diligence, risk assessment, compliance
    - KnowledgeBaseAgent (alias: ProductFitAgent): Engine matching, KB queries, specifications

Orchestrator:
    - SalesOpsAgent: Central orchestrator with multi-agent coordination

Infrastructure Agents:
    - WebSearchAgent: Real-time web search via Perplexity
    - DatabaseAgent: PostgreSQL operations for marine intel

Architecture (from agent_architecture.md):
    - Each domain agent owns specific capabilities exclusively
    - No overlaps between agents
    - SalesOpsAgent coordinates multi-angle analysis
    - A2A semantic routing via Pipeline.router()

Usage:
    # Option 1: Use the registry (recommended)
    from lead_to_cash.agents import create_agent_registry

    async def main():
        registry = await create_agent_registry()
        result = await registry.process("Tell me about Penguin Ferries")

    # Option 2: Use agents directly
    from lead_to_cash.agents import MarineIntelAgent, MarineIntelConfig

    async def research():
        config = MarineIntelConfig()
        async with MarineIntelAgent(config) as agent:
            result = await agent.run_daily_research()

    # Option 3: Use new alias names (same agents, clearer naming)
    from lead_to_cash.agents import MarketIntelAgent, CustomerIntelAgent, KYPAgent

Naming Convention:
    Original names are preserved for backward compatibility.
    New alias names reflect domain responsibilities more clearly:
    - MarineIntelAgent = MarketIntelAgent (industry/market intelligence)
    - CustomerMatcherAgent = CustomerIntelAgent (customer intelligence)
    - DueDiligenceAgent = KYPAgent (Know Your Partner)
    - KnowledgeBaseAgent = ProductFitAgent (product matching)
"""

# =============================================================================
# Standardized Response Structure
# =============================================================================

from lead_to_cash.agents.base_response import AgentResponse

# Billing & Collections Agent (AR tracking, post-order)
from lead_to_cash.agents.billing_collections_agent import (
    BillingCollectionsAgent,
    BillingCollectionsConfig,
    create_billing_collections_agent,
)

# Competitor Intelligence Agent (name unchanged)
from lead_to_cash.agents.competitor_intel_agent import (
    CompetitorIntelAgent,
    CompetitorIntelConfig,
    CompetitorIntelSignature,
    create_competitor_intel_agent,
)

# Customer Matching/Intelligence Agent
from lead_to_cash.agents.customer_matcher_agent import (
    CustomerMatchCandidate,
    CustomerMatcherAgent,
    CustomerMatcherConfig,
    CustomerMatcherSignature,
    CustomerMatchResult,
    MatchConfidence,
    MatchSource,
    create_customer_matcher_agent,
)

# Data Management Agent (MS5 entry assistance)
from lead_to_cash.agents.data_management_agent import (
    DataManagementAgent,
    DataManagementConfig,
    create_data_management_agent,
)
from lead_to_cash.agents.database_agent import (
    DatabaseAgent,
    DatabaseAgentConfig,
    DatabaseQuerySignature,
    create_database_agent,
)

# Due Diligence/KYP Agent
from lead_to_cash.agents.due_diligence_agent import (
    DueDiligenceAgent,
    DueDiligenceConfig,
    DueDiligenceSignature,
    PartnerFunctionType,
    ValidationResult,
    ValidationStatus,
)

# Entity Resolution Agent
from lead_to_cash.agents.entity_resolution_agent import (
    EntityResolutionAgent,
    EntityResolutionConfig,
    EntityResolutionSignature,
    get_entity_resolution_agent,
)

# Financial Operations Agent (MS5 draft order creation)
from lead_to_cash.agents.financial_ops_agent import (
    FinancialOpsAgent,
    FinancialOpsConfig,
    create_financial_ops_agent,
)

# FinOps Orchestrator Agent (for financeops role users)
from lead_to_cash.agents.finops_orchestrator_agent import (
    FinOpsOrchestratorAgent,
    FinOpsOrchestratorConfig,
    create_finops_orchestrator_agent,
)

# Knowledge Base/Product Fit Agent
from lead_to_cash.agents.knowledge_base_agent import (
    KnowledgeBaseAgent,
    KnowledgeBaseConfig,
)

# Marine/Market Intelligence Agent
from lead_to_cash.agents.marine_intel_agent import (
    MarineIntelAgent,
    MarineIntelConfig,
    MarineIntelSignature,
    create_marine_intel_agent,
)

# Opportunity Agent (CEC + IPAS extraction)
from lead_to_cash.agents.opportunity_agent import (
    OpportunityAgent,
    OpportunityConfig,
    create_opportunity_agent,
)
from lead_to_cash.agents.registry import (
    AgentRegistry,
    AgentStatus,
    RegisteredAgent,
    create_agent_registry,
)
from lead_to_cash.agents.sales_ops_agent import (
    AgentType,
    InteractiveSession,
    SalesOpsAgent,
    SalesOpsConfig,
    SalesOpsSignature,
    TaskContext,
    TaskType,
)
from lead_to_cash.agents.web_search_agent import (
    WebSearchAgent,
    WebSearchConfig,
    WebSearchSignature,
    create_web_search_agent,
)

# =============================================================================
# Domain Agents (Original Production-Ready Implementations)
# =============================================================================


# =============================================================================
# Order Processing Domain Agents (ADR-002)
# =============================================================================


# =============================================================================
# Infrastructure Agents
# =============================================================================


# =============================================================================
# Orchestrator & Registry
# =============================================================================


# =============================================================================
# Architecture Aliases (ADR-002 Lead-to-Cash Agent Architecture)
# =============================================================================

# IndustryIntelAgent = MarineIntelAgent (market trends, opportunities, fleet data, news)
# This is the canonical name per ADR-002 for the Industry Intelligence domain
IndustryIntelAgent = MarineIntelAgent
IndustryIntelConfig = MarineIntelConfig
IndustryIntelSignature = MarineIntelSignature
create_industry_intel_agent = create_marine_intel_agent

# ProductIntelAgent = KnowledgeBaseAgent (specs, fit scoring, recommendations)
# This is the canonical name per ADR-002 for the Product Intelligence domain
ProductIntelAgent = KnowledgeBaseAgent
ProductIntelConfig = KnowledgeBaseConfig
create_product_intel_agent = None  # No factory function exists for KB agent

# KYPAgent = DueDiligenceAgent (due diligence, sanctions, risk assessment)
# This is the canonical name per ADR-002 for the KYP agent
KYPAgent = DueDiligenceAgent
KYPConfig = DueDiligenceConfig
KYPSignature = DueDiligenceSignature
create_kyp_agent = None  # No factory function exists for due diligence

# =============================================================================
# Legacy Aliases (Backward Compatibility)
# =============================================================================

# MarketIntelAgent = MarineIntelAgent (legacy alias)
MarketIntelAgent = MarineIntelAgent
MarketIntelConfig = MarineIntelConfig
MarketIntelSignature = MarineIntelSignature
create_market_intel_agent = create_marine_intel_agent

# CustomerIntelAgent = CustomerMatcherAgent (customer profiling, SAP, matching)
CustomerIntelAgent = CustomerMatcherAgent
CustomerIntelConfig = CustomerMatcherConfig
create_customer_intel_agent = create_customer_matcher_agent

# ProductFitAgent = KnowledgeBaseAgent (legacy alias)
ProductFitAgent = KnowledgeBaseAgent
ProductFitConfig = KnowledgeBaseConfig
create_product_fit_agent = None  # No factory function exists for KB agent

__all__ = [
    # ==========================================================================
    # STANDARDIZED RESPONSE
    # ==========================================================================
    "AgentResponse",
    # ==========================================================================
    # ARCHITECTURE NAMES (ADR-002 Lead-to-Cash Agent Architecture)
    # ==========================================================================
    # Intelligence Domain (4 agents)
    "IndustryIntelAgent",  # Market trends, opportunities, fleet data, news
    "IndustryIntelConfig",
    "IndustryIntelSignature",
    "create_industry_intel_agent",
    "CompetitorIntelAgent",  # Win/loss, pricing, threats, positioning
    "CompetitorIntelConfig",
    "CompetitorIntelSignature",
    "create_competitor_intel_agent",
    "ProductIntelAgent",  # Specs, fit scoring, recommendations
    "ProductIntelConfig",
    "create_product_intel_agent",
    "KYPAgent",  # Due diligence, sanctions, risk assessment
    "KYPConfig",
    "KYPSignature",
    "create_kyp_agent",
    # Order Processing Domain (4 agents)
    "OpportunityAgent",  # CEC + IPAS data extraction
    "OpportunityConfig",
    "create_opportunity_agent",
    "DataManagementAgent",  # MS5 entry assistance
    "DataManagementConfig",
    "create_data_management_agent",
    "FinancialOpsAgent",  # Draft order creation
    "FinancialOpsConfig",
    "create_financial_ops_agent",
    "BillingCollectionsAgent",  # AR tracking, billing/collections (post-order)
    "BillingCollectionsConfig",
    "create_billing_collections_agent",
    # ==========================================================================
    # ORCHESTRATORS
    # ==========================================================================
    "FinOpsOrchestratorAgent",  # Orchestrator for financeops role users
    "FinOpsOrchestratorConfig",
    "create_finops_orchestrator_agent",
    # ==========================================================================
    # ORIGINAL AGENT NAMES (Production Implementation Classes)
    # ==========================================================================
    # Marine Intelligence (implementation of IndustryIntelAgent)
    "MarineIntelAgent",
    "MarineIntelConfig",
    "MarineIntelSignature",
    "create_marine_intel_agent",
    # Customer Matcher
    "CustomerMatcherAgent",
    "CustomerMatcherConfig",
    "CustomerMatcherSignature",
    "CustomerMatchResult",
    "CustomerMatchCandidate",
    "MatchSource",
    "MatchConfidence",
    "create_customer_matcher_agent",
    # Due Diligence (implementation of KYPAgent)
    "DueDiligenceAgent",
    "DueDiligenceConfig",
    "DueDiligenceSignature",
    "ValidationResult",
    "ValidationStatus",
    "PartnerFunctionType",
    # Entity Resolution (company name to canonical entity)
    "EntityResolutionAgent",
    "EntityResolutionConfig",
    "EntityResolutionSignature",
    "get_entity_resolution_agent",
    # Knowledge Base (implementation of ProductIntelAgent)
    "KnowledgeBaseAgent",
    "KnowledgeBaseConfig",
    # ==========================================================================
    # LEGACY ALIASES (Backward Compatibility)
    # ==========================================================================
    "MarketIntelAgent",
    "MarketIntelConfig",
    "MarketIntelSignature",
    "create_market_intel_agent",
    "CustomerIntelAgent",
    "CustomerIntelConfig",
    "create_customer_intel_agent",
    "ProductFitAgent",
    "ProductFitConfig",
    "create_product_fit_agent",
    # ==========================================================================
    # INFRASTRUCTURE AGENTS
    # ==========================================================================
    "WebSearchAgent",
    "WebSearchConfig",
    "WebSearchSignature",
    "create_web_search_agent",
    "DatabaseAgent",
    "DatabaseAgentConfig",
    "DatabaseQuerySignature",
    "create_database_agent",
    # ==========================================================================
    # ORCHESTRATOR & REGISTRY
    # ==========================================================================
    "AgentRegistry",
    "AgentStatus",
    "RegisteredAgent",
    "create_agent_registry",
    "SalesOpsAgent",
    "SalesOpsConfig",
    "SalesOpsSignature",
    "TaskType",
    "TaskContext",
    "AgentType",
    "InteractiveSession",
]
