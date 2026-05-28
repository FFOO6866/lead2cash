"""
Agent Registry with A2A Semantic Routing

Centralized registry for Lead-to-Cash agents with A2A capability discovery
and Pipeline.router() semantic routing.

Architecture (ADR-003):
    Uses Kaizen's Pipeline.router() with routing_strategy="semantic" for
    intelligent task routing based on agent capability cards (to_a2a_card()).

Features:
    - A2A semantic routing via Pipeline.router()
    - Agent capability discovery via to_a2a_card()
    - Health monitoring
    - Shared memory coordination
    - OpenTelemetry tracing with trace context propagation

Usage:
    from lead_to_cash.agents.registry import AgentRegistry

    registry = AgentRegistry()
    await registry.initialize()

    # Semantic routing - no keyword matching needed!
    result = await registry.process("Validate customer 1234567")
    # -> Automatically routes to DueDiligenceAgent based on A2A capabilities

    result = await registry.process("Search for vessel orders in Singapore")
    # -> Automatically routes to WebSearchAgent or MarineIntelAgent
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

# OpenTelemetry imports (optional)
try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode

    HAS_OTEL = True
except ImportError:
    trace = None  # type: ignore
    SpanContext = None  # type: ignore
    SpanKind = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    HAS_OTEL = False

if TYPE_CHECKING:
    from opentelemetry.trace import SpanContext

from kaizen.memory.shared_memory import SharedMemoryPool

try:
    from kaizen.orchestration.pipeline import Pipeline
except ImportError:
    # kaizen 2.3.0 doesn't have orchestration module — use stub
    class Pipeline:
        """Stub for kaizen versions without orchestration module."""

        @staticmethod
        def router(*args, **kwargs):
            return None


from lead_to_cash.agents.billing_collections_agent import (
    BillingCollectionsAgent,
    BillingCollectionsConfig,
)
from lead_to_cash.agents.competitor_intel_agent import (
    CompetitorIntelAgent,
    CompetitorIntelConfig,
)
from lead_to_cash.agents.database_agent import DatabaseAgent, DatabaseAgentConfig
from lead_to_cash.agents.due_diligence_agent import (
    DueDiligenceAgent,
    DueDiligenceConfig,
)
from lead_to_cash.agents.entity_resolution_agent import (
    EntityResolutionAgent,
    EntityResolutionConfig,
)
from lead_to_cash.agents.finops_orchestrator_agent import (
    FinOpsOrchestratorAgent,
    FinOpsOrchestratorConfig,
)
from lead_to_cash.agents.knowledge_base_agent import (
    KnowledgeBaseAgent,
    KnowledgeBaseConfig,
)
from lead_to_cash.agents.marine_intel_agent import MarineIntelAgent, MarineIntelConfig
from lead_to_cash.agents.sales_ops_agent import SalesOpsAgent, SalesOpsConfig
from lead_to_cash.agents.web_search_agent import WebSearchAgent, WebSearchConfig
from lead_to_cash.core.conversation import (
    ConversationManager,
    get_conversation_manager,
)
from lead_to_cash.core.data_inventory import (
    DataInventoryService,
    get_data_inventory,
)
from lead_to_cash.core.query_understanding import (
    INTENT_TO_AGENT,
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
)
from lead_to_cash.core.tool_executor import (
    ToolExecutor,
    get_tool_executor,
)
from lead_to_cash.utils.resilience import CircuitBreaker, is_transient_error

logger = logging.getLogger(__name__)

# Maximum retries for transient failures
MAX_AGENT_RETRIES = 2
RETRY_DELAY = 0.5  # seconds


class AgentStatus(str, Enum):
    """Agent status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    INITIALIZING = "initializing"


@dataclass
class RegisteredAgent:
    """Registered agent with metadata.

    Note: Agent capabilities are now managed via A2A cards (to_a2a_card())
    rather than a separate AgentCapability system. This ensures consistency
    with Kaizen's Pipeline.router() semantic routing.
    """

    agent_id: str
    agent_type: str
    agent: Any
    status: AgentStatus = AgentStatus.INACTIVE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health_check: Optional[datetime] = None
    error_count: int = 0


class AgentRegistry:
    """
    Centralized registry with Unified Semantic Routing.

    Architecture:
        - ALL users go through the same routing path: process() -> ConversationManager
        - Agent selection is based on query CONTENT (semantic), not user role
        - RBAC controls DATA ACCESS at the response layer, not conversation routing
        - Users can ask any question; permissions filter what data they see

    Routing Flow:
        1. process() receives request with session_id
        2. ConversationManager.process_message() handles multi-turn orchestration
        3. QueryUnderstandingEngine classifies intent
        4. ToolExecutor selects and executes appropriate tools
        5. _enforce_data_access() filters response based on user permissions

    Example:
        registry = AgentRegistry()
        await registry.initialize()

        # Unified routing for ALL users (financeops, sales_ops, etc.)
        result = await registry.process(
            request="What contracts has Caterpillar won?",
            session_id="session-123",
            user_context={"roles": ["financeops"], "permissions": {...}}
        )
        # -> Routes through ConversationManager, not role-based orchestrator

    DEPRECATED Methods (kept for backwards compatibility):
        - get_orchestrator_for_role(): No longer used in production
        - get_finops_orchestrator(): No longer used in production
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        model: str = os.getenv(
            "OPENAI_PROD_MODEL", "gpt-4o"
        ),  # gpt-4o supports JSON response format
        enable_query_understanding: bool = True,
    ):
        """
        Initialize agent registry.

        Args:
            llm_provider: Default LLM provider for agents
            model: Default model for agents
            enable_query_understanding: Enable LLM-based query understanding
                for semantic intent classification (default: True)
        """
        self.llm_provider = llm_provider
        self.model = model
        self.enable_query_understanding = enable_query_understanding

        # Shared memory for all agents
        self.shared_memory = SharedMemoryPool()

        # Registered agents
        self._agents: dict[str, RegisteredAgent] = {}

        # Circuit breakers per agent (prevents cascading failures)
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Semantic router (created after agents registered)
        self._router: Optional[Pipeline] = None

        # Orchestrator for complex multi-agent tasks (default: SalesOpsAgent)
        self._orchestrator: Optional[SalesOpsAgent] = None

        # FinOps Orchestrator for financeops role users
        self._finops_orchestrator: Optional[FinOpsOrchestratorAgent] = None

        # Query Understanding Engine (orchestration_guide.md Section 2)
        # Uses GPT-4o for semantic intent classification, entity extraction,
        # temporal parsing, and clarification detection
        self._query_engine: Optional[QueryUnderstandingEngine] = None
        if enable_query_understanding:
            try:
                self._query_engine = QueryUnderstandingEngine()
                logger.info("Query Understanding Engine initialized")
            except ValueError as e:
                logger.warning(f"Query understanding unavailable: {e}")
                logger.warning("Falling back to keyword-based routing")

        # Data Inventory Service (orchestration_guide.md Section 3)
        # Tracks what data is available to answer queries
        self._data_inventory: Optional[DataInventoryService] = None

        # Tool Executor (orchestration_guide.md Section 4)
        # Executes tool chains based on query and inventory
        self._tool_executor: Optional[ToolExecutor] = None

        # Conversation Manager (orchestration_guide.md Section 5)
        # Manages multi-turn sessions with clarification blocking
        self._conversation_manager: Optional[ConversationManager] = None

        # Status
        self._initialized = False

        # OpenTelemetry tracer (optional)
        self._tracer = None
        if HAS_OTEL and trace:
            self._tracer = trace.get_tracer("lead_to_cash.agent_registry")

    async def initialize(self) -> None:
        """
        Initialize all agents and create semantic router.

        Creates and registers all specialized agents, then creates the
        Pipeline.router() with semantic A2A routing.

        Agent registration failures are handled gracefully - if one agent
        fails to initialize, others will still be registered.
        """
        if self._initialized:
            logger.warning("Registry already initialized")
            return

        logger.info("Initializing Lead-to-Cash agent registry with A2A routing...")

        # Track initialization errors for reporting
        init_errors = []

        # Register Due Diligence Agent
        try:
            await self._register_due_diligence_agent()
        except Exception as e:
            logger.error(f"Failed to register Due Diligence Agent: {e}")
            init_errors.append(("due_diligence", str(e)))

        # Register Competitor Intelligence Agent
        # This requires PostgreSQL + pgvector, so it may fail if database not configured
        try:
            await self._register_competitor_intel_agent()
        except Exception as e:
            logger.warning(f"Competitor Intelligence Agent unavailable: {e}")
            logger.warning("Set DATABASE_URL to enable competitor intelligence RAG")
            init_errors.append(("competitor_intel", str(e)))

        # Register A2A Infrastructure Agents (ADR-003)
        # WebSearchAgent - Real-time web search via Perplexity
        try:
            await self._register_web_search_agent()
        except Exception as e:
            logger.warning(f"WebSearchAgent unavailable: {e}")
            init_errors.append(("web_search", str(e)))

        # DatabaseAgent - PostgreSQL operations for marine intel
        try:
            await self._register_database_agent()
        except Exception as e:
            logger.warning(f"DatabaseAgent unavailable: {e}")
            init_errors.append(("database", str(e)))

        # MarineIntelAgent - Marine sales intelligence research
        try:
            await self._register_marine_intel_agent()
        except Exception as e:
            logger.warning(f"MarineIntelAgent unavailable: {e}")
            init_errors.append(("marine_intel", str(e)))

        # KnowledgeBaseAgent - Marine engine knowledge base with entity extraction
        # Requires PostgreSQL + pgvector for semantic search
        try:
            await self._register_knowledge_base_agent()
        except Exception as e:
            logger.warning(f"KnowledgeBaseAgent unavailable: {e}")
            logger.warning("Set DATABASE_URL to enable knowledge base features")
            init_errors.append(("knowledge_base", str(e)))

        # EntityResolutionAgent - Company name resolution using registry, ACRA, GLEIF
        # Requires entity registry database for full functionality
        try:
            await self._register_entity_resolution_agent()
        except Exception as e:
            logger.warning(f"EntityResolutionAgent unavailable: {e}")
            init_errors.append(("entity_resolution", str(e)))

        # BillingCollectionsAgent - AR/billing/collections tracking (ADR-002)
        # Part of Order Processing Domain - Post-Order phase
        try:
            await self._register_billing_collections_agent()
        except Exception as e:
            logger.warning(f"BillingCollectionsAgent unavailable: {e}")
            init_errors.append(("billing_collections", str(e)))

        # FinOpsOrchestratorAgent - Orchestrator for financeops role users
        # Routes billing/collections queries to BillingCollectionsAgent
        try:
            await self._register_finops_orchestrator_agent()
        except Exception as e:
            logger.warning(f"FinOpsOrchestratorAgent unavailable: {e}")
            init_errors.append(("finops_orchestrator", str(e)))

        # TODO: Register other agents as they are implemented
        # await self._register_opportunity_agent()
        # await self._register_data_management_agent()
        # await self._register_financial_ops_agent()

        # Register SalesOpsAgent as A2A-routable agent (ADR-003 activation)
        # This makes SalesOpsAgent participate in semantic routing instead of
        # being a separate orchestrator. It can now be selected for orchestration
        # tasks while other agents handle specialized tasks.
        try:
            await self._register_sales_ops_agent()
        except Exception as e:
            logger.error(f"Failed to register SalesOpsAgent: {e}")
            init_errors.append(("sales_ops", str(e)))

        # Create semantic router from ALL registered agents including SalesOpsAgent
        self._create_semantic_router()

        # Propagate registry reference to all agents for A2A communication
        self._propagate_registry_reference()

        # Fallback orchestrator is now the registered SalesOpsAgent
        # (set in _register_sales_ops_agent)
        if not self._orchestrator:
            logger.warning("No orchestrator available - fallback routing disabled")

        # Initialize orchestration components (orchestration_guide.md Sections 3-5)
        try:
            self._data_inventory = get_data_inventory()
            await self._data_inventory.refresh()
            logger.info("Data Inventory Service initialized")
        except Exception as e:
            logger.warning(f"Data Inventory Service unavailable: {e}")
            init_errors.append(("data_inventory", str(e)))

        try:
            self._tool_executor = get_tool_executor()
            logger.info("Tool Executor initialized")
        except Exception as e:
            logger.warning(f"Tool Executor unavailable: {e}")
            init_errors.append(("tool_executor", str(e)))

        try:
            self._conversation_manager = get_conversation_manager()
            logger.info("Conversation Manager initialized")
        except Exception as e:
            logger.warning(f"Conversation Manager unavailable: {e}")
            init_errors.append(("conversation_manager", str(e)))

        # Legacy orchestrator initialization removed - SalesOpsAgent is now
        # registered as A2A agent and set as orchestrator in _register_sales_ops_agent()

        # Report initialization errors if any
        if init_errors:
            logger.warning(f"Initialization completed with {len(init_errors)} errors:")
            for agent_name, error in init_errors:
                logger.warning(f"  - {agent_name}: {error}")

        self._initialized = True
        logger.info(
            f"Registry initialized with {len(self._agents)} agents "
            f"(A2A semantic routing ACTIVE)"
        )

    # Keep _initialize_orchestrator for backwards compatibility but mark deprecated
    async def _initialize_orchestrator(self) -> None:
        """Initialize the Sales Ops Orchestrator.

        DEPRECATED: Use _register_sales_ops_agent() instead.
        SalesOpsAgent is now registered as an A2A-routable agent.
        """
        if self._orchestrator:
            logger.warning(
                "Orchestrator already initialized via _register_sales_ops_agent"
            )
            return

        config = SalesOpsConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        self._orchestrator = SalesOpsAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="sales_ops_orchestrator",
        )

        logger.info("Initialized Sales Ops Orchestrator (legacy mode)")

    # -------------------------------------------------------------------------
    # Agent Registration Methods
    # -------------------------------------------------------------------------

    async def _register_due_diligence_agent(self) -> None:
        """Register the Due Diligence Agent.

        Agent capabilities are managed via A2A cards (to_a2a_card()) automatically
        inherited from BaseAgent based on DueDiligenceSignature.
        """
        config = DueDiligenceConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = DueDiligenceAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="due_diligence",
        )

        self._agents["due_diligence"] = RegisteredAgent(
            agent_id="due_diligence",
            agent_type="DueDiligenceAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered Due Diligence Agent")

    async def _register_competitor_intel_agent(self) -> None:
        """Register the Competitor Intelligence Agent.

        Agent capabilities are managed via A2A cards (to_a2a_card()) automatically
        inherited from BaseAgent based on CompetitorIntelSignature.
        """
        config = CompetitorIntelConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = CompetitorIntelAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="competitor_intel",
        )

        # Initialize the competitor database
        await agent.db.initialize()

        self._agents["competitor_intel"] = RegisteredAgent(
            agent_id="competitor_intel",
            agent_type="CompetitorIntelAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered Competitor Intelligence Agent")

    async def _register_web_search_agent(self) -> None:
        """Register the WebSearchAgent for A2A web search capabilities.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.
        """
        config = WebSearchConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = WebSearchAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="web_search",
        )

        # Enter async context to initialize service
        await agent.__aenter__()

        self._agents["web_search"] = RegisteredAgent(
            agent_id="web_search",
            agent_type="WebSearchAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered WebSearchAgent")

    async def _register_database_agent(self) -> None:
        """Register the DatabaseAgent for A2A database operations.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.
        """
        config = DatabaseAgentConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = DatabaseAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="database",
        )

        # Enter async context to initialize database connection
        await agent.__aenter__()

        self._agents["database"] = RegisteredAgent(
            agent_id="database",
            agent_type="DatabaseAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered DatabaseAgent")

    async def _register_marine_intel_agent(self) -> None:
        """Register the MarineIntelAgent for marine sales intelligence.

        Agent capabilities are managed via A2A cards (to_a2a_card()) automatically
        inherited from BaseAgent based on MarineIntelSignature.
        """
        config = MarineIntelConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = MarineIntelAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="marine_intel",
        )

        self._agents["marine_intel"] = RegisteredAgent(
            agent_id="marine_intel",
            agent_type="MarineIntelAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered MarineIntelAgent")

    async def _register_knowledge_base_agent(self) -> None:
        """Register the KnowledgeBaseAgent for marine engine knowledge base.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.

        Capabilities:
        - engine_entity_extraction: Extract entities from articles
        - article_relevance_scoring: Score article relevance
        - knowledge_base_query: Answer questions about engines

        Requires:
        - PostgreSQL with pgvector extension
        - DATABASE_URL environment variable
        - OPENAI_API_KEY for embeddings
        """
        config = KnowledgeBaseConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = KnowledgeBaseAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="knowledge_base",
        )

        # Initialize the knowledge base services (database, embeddings, resolver)
        await agent.initialize()

        self._agents["knowledge_base"] = RegisteredAgent(
            agent_id="knowledge_base",
            agent_type="KnowledgeBaseAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered KnowledgeBaseAgent")

    async def _register_entity_resolution_agent(self) -> None:
        """Register EntityResolutionAgent for A2A routing.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.

        Capabilities:
        - entity_resolution: Resolve company names to canonical entities
        - external_verification: Verify entities via ACRA, GLEIF, web

        Integrates with:
        - EntityResolutionService for database operations
        - ACRA client for Singapore companies
        - GLEIF client for global LEI lookups
        """
        config = EntityResolutionConfig()

        agent = EntityResolutionAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="entity_resolution",
        )

        # Initialize the entity resolution service (database connection)
        await agent.initialize()

        self._agents["entity_resolution"] = RegisteredAgent(
            agent_id="entity_resolution",
            agent_type="EntityResolutionAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered EntityResolutionAgent")

    async def _register_billing_collections_agent(self) -> None:
        """Register BillingCollectionsAgent for A2A routing.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.

        Capabilities:
        - billing_tracking: Track billing documents and pending invoices
        - collections_monitoring: Monitor collections, overdue payments, and aging
        - payment_terms_analysis: Analyze and explain payment terms

        Part of Order Processing Domain (ADR-002) - Post-Order phase.
        Domain: accounts_receivable (distinct from order_processing)
        """
        config = BillingCollectionsConfig()

        agent = BillingCollectionsAgent(config=config)

        # Initialize the agent (connects to data service)
        await agent.connect()

        self._agents["billing_collections"] = RegisteredAgent(
            agent_id="billing_collections",
            agent_type="BillingCollectionsAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        logger.info("Registered BillingCollectionsAgent")

    async def _register_finops_orchestrator_agent(self) -> None:
        """Register FinOpsOrchestratorAgent (DEPRECATED - kept for backwards compatibility).

        .. deprecated::
            Role-based routing has been replaced by unified semantic routing.
            All users now go through ConversationManager + ToolExecutor.
            RBAC controls DATA ACCESS, not conversation routing.
            This agent is kept for backwards compatibility with existing tests.

        The production chat endpoint does NOT use this orchestrator.
        BillingCollectionsAgent is accessed directly via semantic routing.
        """
        config = FinOpsOrchestratorConfig()

        agent = FinOpsOrchestratorAgent(config=config)

        # Store as the finops orchestrator (not in _agents since it's an orchestrator)
        self._finops_orchestrator = agent

        logger.info("Registered FinOpsOrchestratorAgent as financeops orchestrator")

    async def _register_sales_ops_agent(self) -> None:
        """Register SalesOpsAgent as A2A-routable agent.

        SalesOpsAgent handles complex orchestration tasks, customer validation,
        and acts as the central coordinator. By registering it as an A2A agent,
        it can be selected via semantic routing for appropriate tasks.

        Agent capabilities are managed via _extract_primary_capabilities() override
        which provides rich Capability objects for semantic routing.
        """
        config = SalesOpsConfig(
            llm_provider=self.llm_provider,
            model=self.model,
        )

        agent = SalesOpsAgent(
            config=config,
            shared_memory=self.shared_memory,
            agent_id="sales_ops",
        )

        self._agents["sales_ops"] = RegisteredAgent(
            agent_id="sales_ops",
            agent_type="SalesOpsAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        # Also set as orchestrator for fallback
        self._orchestrator = agent

        logger.info("Registered SalesOpsAgent as A2A-routable agent and orchestrator")

    def _create_semantic_router(self) -> None:
        """
        Create Pipeline.router() with semantic A2A routing.

        The router calls to_a2a_card() on each agent to get capabilities,
        then matches task requirements against those capabilities.

        This eliminates hardcoded if/else routing logic (ADR-003).
        """
        agents = [reg.agent for reg in self._agents.values()]

        if not agents:
            logger.warning("No agents registered - semantic router not created")
            return

        try:
            self._router = Pipeline.router(
                agents=agents,
                routing_strategy="semantic",  # A2A capability matching
                error_handling="graceful",  # Return error info on failure
            )
            logger.info(f"Created semantic router with {len(agents)} agents")
        except Exception as e:
            logger.error(f"Failed to create semantic router: {e}")
            self._router = None

    def _propagate_registry_reference(self) -> None:
        """
        Propagate registry reference to all agents for A2A communication.

        This enables agents to request enrichment from other agents via
        the registry's get_agent_for_capability() method.
        """
        propagated_count = 0

        for registered in self._agents.values():
            agent = registered.agent
            try:
                # Try set_registry() method (AutonomousAgent pattern)
                if hasattr(agent, "set_registry"):
                    agent.set_registry(self)
                    propagated_count += 1
                # Try direct _registry attribute (BaseAgent pattern)
                elif hasattr(agent, "_registry"):
                    agent._registry = self
                    propagated_count += 1
                # Set as attribute if neither exists (duck typing)
                else:
                    agent._registry = self
                    propagated_count += 1
            except Exception as e:
                logger.debug(f"Could not set registry on {registered.agent_id}: {e}")

        logger.info(f"Propagated registry reference to {propagated_count} agents")

    # -------------------------------------------------------------------------
    # Agent Access
    # -------------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> Optional[Any]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        registered = self._agents.get(agent_id)
        return registered.agent if registered else None

    def get_orchestrator(self) -> Optional[SalesOpsAgent]:
        """Get the Sales Ops Orchestrator (default)."""
        return self._orchestrator

    def get_finops_orchestrator(self) -> Optional[FinOpsOrchestratorAgent]:
        """Get the FinOps Orchestrator (DEPRECATED).

        .. deprecated::
            Role-based routing has been replaced by unified semantic routing.
            Use registry.process() which routes all users through ConversationManager.
            This method is kept for backwards compatibility with existing tests.
        """
        import warnings

        warnings.warn(
            "get_finops_orchestrator() is deprecated. Use registry.process() for unified routing.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._finops_orchestrator

    def get_orchestrator_for_role(self, roles: list[str]) -> Any:
        """Get orchestrator based on user roles (DEPRECATED).

        .. deprecated::
            Role-based routing has been replaced by unified semantic routing.
            All users now go through registry.process() -> ConversationManager.
            RBAC controls DATA ACCESS at the data layer, not conversation routing.
            This method is kept for backwards compatibility with existing tests.

        Args:
            roles: List of user role names

        Returns:
            FinOpsOrchestratorAgent for financeops users, SalesOpsAgent otherwise
        """
        import warnings

        warnings.warn(
            "get_orchestrator_for_role() is deprecated. Use registry.process() for unified routing.",
            DeprecationWarning,
            stacklevel=2,
        )
        if "financeops" in roles and self._finops_orchestrator:
            logger.debug("Using FinOpsOrchestratorAgent for financeops user")
            return self._finops_orchestrator

        # Default to Sales Ops orchestrator
        logger.debug("Using SalesOpsAgent as default orchestrator")
        return self._orchestrator

    def get_agent_for_capability(self, capability_name: str) -> Optional[Any]:
        """
        Get agent that can handle a specific capability.

        Uses _extract_primary_capabilities() to find agents with matching capabilities.
        Note: We use _extract_primary_capabilities() directly instead of to_a2a_card()
        because the kaizen package has a bug with incorrect import path.

        Args:
            capability_name: Name of the required capability

        Returns:
            Agent instance or None if no match
        """
        for registered in self._agents.values():
            try:
                if hasattr(registered.agent, "_extract_primary_capabilities"):
                    capabilities = registered.agent._extract_primary_capabilities()
                    for cap in capabilities:
                        if cap.name == capability_name:
                            return registered.agent
            except Exception:
                continue
        return None

    def find_agents_by_keyword(self, keyword: str) -> list[RegisteredAgent]:
        """
        Find agents whose capabilities match a keyword.

        Uses _extract_primary_capabilities() to search capabilities by keyword.

        Args:
            keyword: Search keyword

        Returns:
            List of matching registered agents
        """
        keyword_lower = keyword.lower()
        matches = []

        for registered in self._agents.values():
            try:
                if hasattr(registered.agent, "_extract_primary_capabilities"):
                    capabilities = registered.agent._extract_primary_capabilities()
                    for cap in capabilities:
                        if any(keyword_lower in kw.lower() for kw in cap.keywords):
                            matches.append(registered)
                            break
            except Exception:
                continue

        return matches

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents with their A2A capabilities."""
        result: list[dict[str, Any]] = []
        for reg in self._agents.values():
            agent_info: dict[str, Any] = {
                "agent_id": reg.agent_id,
                "agent_type": reg.agent_type,
                "status": reg.status.value,
                "registered_at": reg.registered_at.isoformat(),
                "capabilities": [],
            }

            # Get capabilities via _extract_primary_capabilities()
            try:
                if hasattr(reg.agent, "_extract_primary_capabilities"):
                    capabilities = reg.agent._extract_primary_capabilities()
                    agent_info["capabilities"] = [
                        {"name": c.name, "description": c.description}
                        for c in capabilities
                    ]
            except Exception:
                pass

            result.append(agent_info)

        return result

    def list_capabilities(self) -> list[dict[str, Any]]:
        """List all available capabilities across all agents."""
        result_capabilities = []
        for reg in self._agents.values():
            try:
                if hasattr(reg.agent, "_extract_primary_capabilities"):
                    capabilities = reg.agent._extract_primary_capabilities()
                    for cap in capabilities:
                        result_capabilities.append(
                            {
                                "name": cap.name,
                                "description": cap.description,
                                "agent_id": reg.agent_id,
                                "keywords": cap.keywords,
                            }
                        )
            except Exception:
                continue
        return result_capabilities

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _extract_company_name(self, request: str) -> Optional[str]:
        """
        Extract company name from request.

        Looks for company names after key phrases like 'due diligence',
        'validate customer', 'research', etc.

        Args:
            request: User request text

        Returns:
            Extracted company name or None
        """
        import re

        # Common patterns for company name extraction
        patterns = [
            r"due diligence[:\s]+([A-Za-z0-9\s&\-\.]+)",
            r"validate[:\s]+(?:customer[:\s]+)?([A-Za-z][A-Za-z0-9\s&\-\.]+)",
            r"research[:\s]+([A-Za-z][A-Za-z0-9\s&\-\.]+)",
            r"about[:\s]+([A-Za-z][A-Za-z0-9\s&\-\.]+)",
            r"company[:\s]+([A-Za-z][A-Za-z0-9\s&\-\.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Filter out common false positives
                stop_words = [
                    "a",
                    "the",
                    "this",
                    "that",
                    "please",
                    "help",
                    "me",
                    "with",
                ]
                if company.lower() not in stop_words and len(company) > 2:
                    return company

        # Fallback: look for capitalized words that might be company names
        # after removing common words
        words = request.split()
        for i, word in enumerate(words):
            # Look for capitalized words not at sentence start
            if i > 0 and word[0].isupper() and len(word) > 2:
                # Check it's not a common word
                common = ["I", "Please", "Help", "Can", "Could", "Would", "What", "How"]
                if word not in common:
                    return word

        return None

    def _has_sap_customer_id(self, request: str) -> bool:
        """
        Check if request contains a SAP customer ID pattern.

        SAP customer IDs are typically 7-10 digit numbers.

        Args:
            request: User request text

        Returns:
            True if SAP customer ID pattern found
        """
        import re

        # SAP customer IDs are typically 7-10 digits
        pattern = r"\b\d{7,10}\b"
        return bool(re.search(pattern, request))

    # -------------------------------------------------------------------------
    # Request Processing
    # -------------------------------------------------------------------------

    async def process(
        self,
        request: str,
        context: Optional[dict[str, Any]] = None,
        trace_context: Optional["SpanContext"] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
        session_id: Optional[str] = None,
        clarification_response: Optional[dict[str, Any]] = None,
        user_context: Optional[dict[str, Any]] = None,
        confirmed_entity: Optional[dict[str, Any]] = None,
        original_task_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process request using LLM-based query understanding and semantic routing.

        Implements the FULL orchestration flow from orchestration_guide.md:
        1. Query Understanding (Section 2) - Parse using GPT-4o
        2. Clarification Check - Block if clarification needed
        3. Data Inventory Check (Section 3) - Know what data we have
        4. Tool Selection (Section 4) - Plan tool execution
        5. Tool Execution - Execute tools with ReAct pattern
        6. Response + Follow-ups (Section 5) - Generate response with suggestions
        7. Data-layer RBAC (NEW) - Filter response based on user permissions

        Key Principle: RBAC controls DATA ACCESS, not conversation routing.
        - Any user can ask any question (market intel, competitor, KYP, billing, etc.)
        - The best agent is selected based on query CONTENT, not user role
        - user_context contains permissions that filter WHAT DATA the user can see
        - If user lacks permission for certain data, they get a graceful message

        Session-based vs Single-turn:
        - If session_id provided, uses ConversationManager for full orchestration
        - If no session_id, uses legacy single-turn processing

        Args:
            request: Natural language request
            context: Optional context data
            trace_context: Optional OpenTelemetry SpanContext for distributed tracing
            conversation_history: Optional previous conversation turns for context
            session_id: Optional session ID for multi-turn conversation
            clarification_response: Optional response to pending clarification
            user_context: User context for data-layer RBAC (roles, permissions)
            confirmed_entity: Entity confirmed by user from disambiguation
            original_task_type: Original task type preserved after entity confirmation

        Returns:
            Processing result with answer, sources, data_coverage, and follow_ups
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"Processing request: {request[:50]}...")

        # Session-based processing: Use ConversationManager for full orchestration
        if session_id and self._conversation_manager:
            logger.info(f"Session-based processing: {session_id}")
            try:
                result = await self._conversation_manager.process_message(
                    session_id=session_id,
                    message=request,
                    clarification_response=clarification_response,
                    user_context=user_context,
                    confirmed_entity=confirmed_entity,
                    original_task_type=original_task_type,
                )
                # Add trace context if available
                if trace_context and HAS_OTEL:
                    result["trace_id"] = format(trace_context.trace_id, "032x")

                # Apply data-layer RBAC filtering
                result = self._enforce_data_access(result, user_context)

                return result
            except Exception as e:
                logger.error(
                    f"Conversation manager failed: {e}, falling back to single-turn"
                )
                # Fall through to single-turn processing

        # Step 1: Parse query using Query Understanding Engine
        parsed_query: Optional[ParsedQuery] = None
        if self._query_engine:
            try:
                parsed_query = await self._query_engine.parse(
                    request, conversation_history
                )
                logger.info(
                    f"Query parsed: intent={parsed_query.intent.value}, "
                    f"confidence={parsed_query.intent_confidence:.2f}, "
                    f"clarification_needed={parsed_query.requires_clarification}"
                )
            except Exception as e:
                logger.warning(f"Query understanding failed: {e}, using fallback")

        # Step 2: Handle clarification if needed
        if parsed_query and parsed_query.requires_clarification:
            return self._build_clarification_response(parsed_query)

        # Step 3: Select agent using semantic A2A routing (primary) or intent-based (fallback)
        # Try semantic routing first via Pipeline.router()
        selected_agent, routing_metadata = self._try_semantic_routing(
            request, parsed_query
        )

        # Fall back to intent-based routing if semantic routing didn't match
        if not selected_agent:
            selected_agent = self._select_best_agent(request, parsed_query)
            routing_metadata["routing_method"] = "intent_based"

        if selected_agent:
            agent_id = selected_agent.agent_id
            logger.info(f"Selected agent: {agent_id}")

            # Get or create circuit breaker for this agent
            if agent_id not in self._circuit_breakers:
                self._circuit_breakers[agent_id] = CircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=60,
                    half_open_max_calls=3,
                )
            circuit = self._circuit_breakers[agent_id]

            # Check circuit breaker before calling agent
            if not circuit.can_execute():
                logger.warning(
                    f"Circuit breaker OPEN for agent {agent_id}, state={circuit.state}"
                )
                # Try fallback to orchestrator
                if self._orchestrator and selected_agent != self._orchestrator:
                    logger.info("Circuit open - falling back to orchestrator")
                    return await self._orchestrator.process_request(request, context)
                raise RuntimeError(
                    f"Agent {agent_id} unavailable - circuit breaker open"
                )

            # Execute with tracing if available
            result = await self._execute_agent_with_tracing(
                agent=selected_agent,
                agent_id=agent_id,
                request=request,
                context=context,
                circuit=circuit,
                trace_context=trace_context,
            )

            # Add parsed query metadata to result
            if parsed_query:
                result["query_understanding"] = {
                    "intent": parsed_query.intent.value,
                    "intent_confidence": parsed_query.intent_confidence,
                    "entities": {
                        "competitors": parsed_query.competitors,
                        "companies": parsed_query.companies,
                        "regions": parsed_query.regions,
                        "products": parsed_query.products,
                        "vessel_types": parsed_query.vessel_types,
                    },
                    "temporal": {
                        "time_reference": parsed_query.time_reference,
                        "time_start": parsed_query.time_start,
                        "time_end": parsed_query.time_end,
                        "is_realtime_needed": parsed_query.is_realtime_needed,
                    },
                }

            # Add routing metadata to result
            result["routing"] = routing_metadata.get("routing_method", "unknown")
            result["routing_metadata"] = routing_metadata

            # Apply data-layer RBAC filtering
            result = self._enforce_data_access(result, user_context)

            # Generate contextual follow-ups based on intent and permissions
            result = self._add_contextual_follow_ups(result, parsed_query, user_context)

            return result

        # Fallback to orchestrator for complex tasks
        if self._orchestrator:
            logger.info("Using orchestrator fallback")
            result = await self._execute_agent_with_tracing(
                agent=self._orchestrator,
                agent_id="sales_ops_orchestrator",
                request=request,
                context=context,
                circuit=None,
                trace_context=trace_context,
                is_fallback=True,
            )

            # Still include partial query understanding if available
            if parsed_query:
                result["query_understanding"] = {
                    "intent": parsed_query.intent.value,
                    "intent_confidence": parsed_query.intent_confidence,
                }

            # Apply data-layer RBAC filtering
            result = self._enforce_data_access(result, user_context)

            # Generate contextual follow-ups based on intent and permissions
            result = self._add_contextual_follow_ups(result, parsed_query, user_context)

            return result

        raise RuntimeError("No router or orchestrator available")

    # -------------------------------------------------------------------------
    # Data-Layer RBAC Enforcement
    # -------------------------------------------------------------------------

    def _enforce_data_access(
        self,
        result: dict[str, Any],
        user_context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Enforce data-layer RBAC on agent response.

        Key Principle: RBAC controls DATA ACCESS, not conversation routing.
        - Any user can ask any question
        - This method filters WHAT DATA they can see in the response
        - Users get a graceful message about what they can't access

        Permission mapping by data type:
        - billing_items, billing_summary -> billing:read
        - collections_items, aging_buckets -> collections:read
        - marine_intel, opportunities -> marine_intel:read
        - competitor_intel, competitor_data -> competitor_intel:read
        - kyp_result, risk_assessment -> insights:read
        - kb_result, product_fit -> knowledge_base:read

        Args:
            result: Agent response to filter
            user_context: User context with permissions

        Returns:
            Filtered response with access_denied info if applicable
        """
        if not user_context:
            # No user context = anonymous = allow public data only
            return result

        permissions = user_context.get("permissions", {})

        # Admin has full access
        if self._has_permission(permissions, "*", "*"):
            return result

        # Map data types to required permissions
        DATA_TYPE_PERMISSIONS = {
            # Finance data - requires billing/collections permissions
            "billing_items": ("billing", "read"),
            "billing_summary": ("billing", "read"),
            "collections_items": ("collections", "read"),
            "aging_buckets": ("collections", "read"),
            "aging_analysis": ("collections", "read"),
            "customer_ar": ("billing", "read"),
            # Intelligence data - requires respective permissions
            "marine_intel": ("marine_intel", "read"),
            "opportunities": ("marine_intel", "read"),
            "competitor_intel": ("competitor_intel", "read"),
            "competitor_data": ("competitor_intel", "read"),
            # Insights data - available to both roles
            "kyp_result": ("insights", "read"),
            "risk_assessment": ("insights", "read"),
            "financial_health": ("insights", "read"),
            # Knowledge base - generally accessible
            "kb_result": ("knowledge_base", "read"),
            "product_fit": ("knowledge_base", "read"),
            "engine_matches": ("knowledge_base", "read"),
        }

        # Check data in the 'data' field
        data = result.get("data", {})
        if not data or not isinstance(data, dict):
            return result

        filtered_data = {}
        access_denied_fields = []

        for field_name, field_value in data.items():
            permission_needed = DATA_TYPE_PERMISSIONS.get(field_name)

            if permission_needed is None:
                # Unknown field - allow through (safe default for new fields)
                filtered_data[field_name] = field_value
                continue

            resource, action = permission_needed
            if self._has_permission(permissions, resource, action):
                filtered_data[field_name] = field_value
            else:
                access_denied_fields.append((field_name, resource))
                logger.debug(
                    f"RBAC: Filtered {field_name} - user lacks {resource}:{action}"
                )

        result["data"] = filtered_data

        # Build access denied message if any fields were filtered
        if access_denied_fields:
            denied_resources = sorted(set(r for _, r in access_denied_fields))
            role_suggestions = self._get_role_suggestions(denied_resources)

            result["access_denied"] = {
                "message": f"Some data requires additional permissions: {', '.join(denied_resources)}",
                "required_permissions": denied_resources,
                "filtered_fields": [f for f, _ in access_denied_fields],
                "suggestion": role_suggestions,
            }

            # Check if ALL meaningful data was filtered (e.g., billing query by sales user)
            # In that case, replace the answer entirely to prevent data leakage via prose
            meaningful_remaining = {
                k: v
                for k, v in filtered_data.items()
                if v
                and k not in ("query", "customer_name", "customer_id", "session_id")
            }
            if not meaningful_remaining and result.get("answer"):
                # No data the user is allowed to see — replace answer with denial
                result["answer"] = (
                    f"I'm unable to share this information as it requires "
                    f"{', '.join(denied_resources)} permissions. "
                    f"{role_suggestions}"
                )
            elif result.get("answer"):
                # Some data remains — append note about filtered fields
                result["answer"] = (
                    result["answer"]
                    + f"\n\n*Note: Some data ({', '.join(denied_resources)}) "
                    f"requires additional permissions.*"
                )

        return result

    def _has_permission(
        self,
        permissions: dict[str, list[str]],
        resource: str,
        action: str,
    ) -> bool:
        """Check if permissions dict contains resource/action."""
        if not permissions:
            return False

        # Wildcard admin access
        if "*" in permissions:
            wildcard_actions = permissions.get("*", [])
            if "*" in wildcard_actions or action in wildcard_actions:
                return True

        # Check specific resource permission
        if resource in permissions:
            allowed_actions = permissions[resource]
            return "*" in allowed_actions or action in allowed_actions

        return False

    def _get_role_suggestions(self, denied_resources: list[str]) -> str:
        """Get role suggestion based on denied resources."""
        RESOURCE_TO_ROLE = {
            "billing": "financeops",
            "collections": "financeops",
            "marine_intel": "sales_ops",
            "competitor_intel": "sales_ops",
            "insights": "sales_ops or financeops",
        }

        roles_needed = set()
        for resource in denied_resources:
            if resource in RESOURCE_TO_ROLE:
                roles_needed.add(RESOURCE_TO_ROLE[resource])

        if roles_needed:
            return (
                f"Contact your admin to request: {', '.join(sorted(roles_needed))} role"
            )
        return "Contact your admin to request additional permissions"

    def _add_contextual_follow_ups(
        self,
        result: dict[str, Any],
        parsed_query: Optional["ParsedQuery"],
        user_context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate contextual follow-up suggestions based on:
        1. The query intent (what did the user ask about?)
        2. The data returned (what's available to explore?)
        3. User's permissions (don't suggest actions they can't do)

        Args:
            result: Agent response to enhance
            parsed_query: Parsed query with intent
            user_context: User context with permissions

        Returns:
            Result with contextual follow_up_suggestions
        """
        # Skip if already has good follow-ups or is an error
        if result.get("type") == "error":
            return result

        existing = result.get("follow_up_suggestions", [])

        # If we have generic follow-ups (like the old hardcoded ones), replace them
        generic_follow_ups = [
            "Show billing items",
            "Show collections",
            "Run KYP check",
            "Show aging breakdown",
            "List overdue items",
            "Filter by customer",
        ]
        if existing and all(f in generic_follow_ups for f in existing):
            existing = []  # Clear generic follow-ups

        # Don't override good contextual follow-ups
        if existing and len(existing) >= 3:
            return result

        permissions = (
            user_context.get("permissions", {}) if user_context else {"*": ["*"]}
        )

        suggestions = []

        # Intent-based suggestions
        if parsed_query:
            intent = parsed_query.intent

            INTENT_FOLLOW_UPS = {
                "competitor_intel": [
                    ("Compare with other competitors", "competitor_intel", "read"),
                    ("Show market share analysis", "competitor_intel", "read"),
                    ("What products do they offer?", "knowledge_base", "read"),
                ],
                "customer_intel": [
                    ("Run KYP due diligence check", "insights", "read"),
                    ("Show billing status", "billing", "read"),
                    ("What products fit this customer?", "knowledge_base", "read"),
                ],
                "kyp_due_diligence": [
                    ("Show detailed financial analysis", "insights", "read"),
                    ("Check billing history", "billing", "read"),
                    ("What's our relationship history?", "insights", "read"),
                ],
                "market_intel": [
                    (
                        "Who are the competitors in this space?",
                        "competitor_intel",
                        "read",
                    ),
                    (
                        "Which companies mentioned are our customers?",
                        "marine_intel",
                        "read",
                    ),
                    (
                        "What products fit these opportunities?",
                        "knowledge_base",
                        "read",
                    ),
                ],
                "product_fit": [
                    ("Compare with competitor products", "competitor_intel", "read"),
                    ("Show maintenance requirements", "knowledge_base", "read"),
                    ("What customers use these engines?", "marine_intel", "read"),
                ],
                "general_question": [
                    ("Tell me more about this topic", "knowledge_base", "read"),
                    ("Show related market intelligence", "marine_intel", "read"),
                    ("Who are the key players?", "competitor_intel", "read"),
                ],
            }

            intent_str = intent.value if hasattr(intent, "value") else str(intent)
            intent_suggestions = INTENT_FOLLOW_UPS.get(intent_str, [])

            for suggestion, resource, action in intent_suggestions:
                if self._has_permission(permissions, resource, action):
                    suggestions.append(suggestion)

            # Template substitution for extracted entities
            if parsed_query.competitors and suggestions:
                competitor = parsed_query.competitors[0]
                suggestions = [
                    s.replace("{competitor}", competitor) for s in suggestions
                ]

            if parsed_query.companies and suggestions:
                company = parsed_query.companies[0]
                suggestions = [s.replace("{company}", company) for s in suggestions]

        # Data-based suggestions (based on what we returned)
        data = result.get("data", {})
        if "billing_items" in data and self._has_permission(
            permissions, "collections", "read"
        ):
            if "Show collections status" not in suggestions:
                suggestions.append("Show collections status")

        if "kyp_result" in data and self._has_permission(
            permissions, "billing", "read"
        ):
            if "Check billing history" not in suggestions:
                suggestions.append("Check billing history")

        # Deduplicate and limit
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique_suggestions.append(s)

        # Keep existing non-generic ones and add new ones
        final_suggestions = existing + [
            s for s in unique_suggestions if s not in existing
        ]
        result["follow_up_suggestions"] = final_suggestions[:4]

        return result

    async def _execute_agent_with_tracing(
        self,
        agent: Any,
        agent_id: str,
        request: str,
        context: Optional[dict[str, Any]],
        circuit: Optional[CircuitBreaker],
        trace_context: Optional["SpanContext"] = None,
        is_fallback: bool = False,
    ) -> dict[str, Any]:
        """
        Execute agent with OpenTelemetry tracing.

        Creates child spans for agent execution when tracing is enabled,
        properly linking to the parent trace context from the gateway.

        Args:
            agent: Agent instance to execute
            agent_id: Agent identifier
            request: Natural language request
            context: Optional context data
            circuit: Circuit breaker for this agent (None for orchestrator)
            trace_context: Optional parent SpanContext for distributed tracing
            is_fallback: Whether this is a fallback execution

        Returns:
            Processing result from agent
        """
        # Retry loop for transient failures
        last_error: Optional[Exception] = None
        for attempt in range(MAX_AGENT_RETRIES + 1):
            try:
                # Execute with tracing if tracer available
                if self._tracer and HAS_OTEL:
                    result = await self._traced_agent_execution(
                        agent=agent,
                        agent_id=agent_id,
                        request=request,
                        context=context,
                        trace_context=trace_context,
                        attempt=attempt,
                        is_fallback=is_fallback,
                    )
                else:
                    # No tracing - direct execution
                    result = await self._direct_agent_execution(
                        agent=agent,
                        request=request,
                        context=context,
                    )

                # Ensure result format consistency
                if not isinstance(result, dict):
                    result = {"result": result}

                # Record success for circuit breaker
                if circuit:
                    circuit.record_success()

                # Add routing metadata
                result["routing"] = "fallback" if is_fallback else "semantic_a2a"
                result["selected_agent"] = agent_id
                return result

            except Exception as e:
                last_error = e

                # Check if it's a transient error worth retrying
                if is_transient_error(e) and attempt < MAX_AGENT_RETRIES:
                    logger.warning(
                        f"Agent {agent_id} transient error (attempt {attempt + 1}/"
                        f"{MAX_AGENT_RETRIES + 1}): {e}. Retrying..."
                    )
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue

                # Record failure for circuit breaker
                if circuit:
                    circuit.record_failure()
                logger.warning(
                    f"Agent {agent_id} failed "
                    f"(failures={circuit._failure_count if circuit else 'N/A'}): {e}"
                )

                # Try fallback to orchestrator (only if not already falling back)
                if (
                    not is_fallback
                    and self._orchestrator
                    and agent != self._orchestrator
                ):
                    logger.info("Falling back to orchestrator")
                    return await self._execute_agent_with_tracing(
                        agent=self._orchestrator,
                        agent_id="sales_ops_orchestrator",
                        request=request,
                        context=context,
                        circuit=None,
                        trace_context=trace_context,
                        is_fallback=True,
                    )
                raise

        # Should never reach here, but handle it just in case
        if last_error:
            raise last_error
        raise RuntimeError(f"Unexpected state in agent execution for {agent_id}")

    async def _traced_agent_execution(
        self,
        agent: Any,
        agent_id: str,
        request: str,
        context: Optional[dict[str, Any]],
        trace_context: Optional["SpanContext"],
        attempt: int,
        is_fallback: bool,
    ) -> Any:
        """Execute agent with OpenTelemetry span."""
        # Create span attributes
        span_attrs = {
            "agent.id": agent_id,
            "agent.type": type(agent).__name__,
            "request.length": len(request),
            "request.preview": request[:100],
            "execution.attempt": attempt + 1,
            "execution.is_fallback": is_fallback,
        }

        # Create proper span linking to parent context if available
        span_context_kwargs: dict[str, Any] = {}
        if trace_context and trace_context.is_valid:
            # Link to parent span from gateway
            from opentelemetry.trace import Link

            span_context_kwargs["links"] = [Link(trace_context)]

        with self._tracer.start_as_current_span(
            f"agent.{agent_id}.execute",
            kind=SpanKind.INTERNAL,
            attributes=span_attrs,
            **span_context_kwargs,
        ) as span:
            try:
                result = await self._direct_agent_execution(agent, request, context)

                # Add result info to span
                span.set_status(Status(StatusCode.OK))
                if isinstance(result, dict):
                    span.set_attribute(
                        "result.keys", ",".join(str(k) for k in result.keys())
                    )

                return result

            except Exception as e:
                # Record error in span
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e)[:500])
                span.record_exception(e)
                raise

    async def _direct_agent_execution(
        self,
        agent: Any,
        request: str,
        context: Optional[dict[str, Any]],
    ) -> Any:
        """Direct agent execution without tracing."""
        # Determine which method to call based on agent type
        if hasattr(agent, "run"):
            result = agent.run(task=request, context=context or {})
        elif hasattr(agent, "process_request"):
            result = agent.process_request(request, context)
        else:
            raise RuntimeError(
                f"Agent {type(agent).__name__} has no run/process_request method"
            )

        # Handle async results
        if asyncio.iscoroutine(result):
            result = await result

        return result

    def _select_best_agent(
        self, request: str, parsed_query: Optional[ParsedQuery] = None
    ) -> Optional[Any]:
        """
        Select the best agent for the request using LLM-based intent classification.

        Implements orchestration_guide.md intent-to-agent routing:
        1. If parsed_query available, use intent to select agent (semantic routing)
        2. Otherwise, fall back to keyword matching (legacy behavior)

        Args:
            request: Natural language request
            parsed_query: Optional ParsedQuery from query understanding

        Returns:
            Best matching agent or None
        """
        # Primary path: Use LLM-classified intent for agent selection
        if parsed_query:
            primary_agent_id = INTENT_TO_AGENT.get(parsed_query.intent)
            if primary_agent_id:
                agent = self._agents.get(primary_agent_id)
                if agent and agent.status == AgentStatus.ACTIVE:
                    logger.info(
                        f"Intent-based routing: {parsed_query.intent.value} -> {primary_agent_id}"
                    )
                    return agent.agent
                else:
                    logger.warning(
                        f"Primary agent {primary_agent_id} unavailable, trying alternatives"
                    )

        # Fallback path: Keyword-based routing (legacy behavior)
        request_lower = request.lower()

        # Fast path: explicit keyword routing for clear intents
        # This ensures specific agents are selected for unambiguous requests
        if any(
            kw in request_lower
            for kw in ["competitor", "caterpillar", "cummins", "man energy"]
        ):
            competitor_agent = self._agents.get("competitor_intel")
            if competitor_agent:
                logger.info("Direct routing to competitor_intel (keyword match)")
                return competitor_agent.agent

        best_agent = None
        best_score = 0.0

        logger.debug(f"Fallback: scoring agents for request: {request[:50]}...")

        for reg in self._agents.values():
            agent = reg.agent
            agent_score = 0.0

            try:
                if hasattr(agent, "_extract_primary_capabilities"):
                    capabilities = agent._extract_primary_capabilities()
                    for cap in capabilities:
                        cap_score = self._score_capability(cap, request_lower)
                        if cap_score > agent_score:
                            agent_score = cap_score
                            logger.debug(
                                f"  {reg.agent_id}.{cap.name}: score={cap_score:.2f}"
                            )

                if agent_score > best_score:
                    best_score = agent_score
                    best_agent = agent
                    logger.debug(
                        f"  New best: {reg.agent_id} with score {agent_score:.2f}"
                    )

            except Exception as e:
                logger.warning(f"Error scoring {reg.agent_id}: {e}")

        if best_agent:
            logger.info(f"Selected {best_agent.agent_id} with score {best_score:.2f}")
        else:
            logger.warning("No agent matched - will use fallback")

        return best_agent

    def _try_semantic_routing(
        self, request: str, parsed_query: Optional[ParsedQuery] = None
    ) -> tuple[Optional[Any], dict[str, Any]]:
        """
        AI-enhanced semantic routing using LLM intent + capability matching.

        This method combines two signals for intelligent routing:
        1. PRIMARY: LLM-extracted intent from ParsedQuery (GPT-4o based)
        2. SECONDARY: A2A capability matching using Kaizen's matches_requirement()

        The hybrid approach provides both semantic understanding (LLM) and
        fine-grained capability matching (A2A protocol).

        Args:
            request: Natural language request
            parsed_query: ParsedQuery from QueryUnderstandingEngine (GPT-4o)

        Returns:
            Tuple of (selected_agent, routing_metadata)
            - selected_agent: Best matching agent or None
            - routing_metadata: Dict with routing info (method, scores, etc.)
        """
        routing_metadata: dict[str, Any] = {
            "routing_method": "ai_enhanced_a2a",
            "llm_intent": None,
            "llm_confidence": 0.0,
            "capability_scores": {},
            "combined_scores": {},
            "final_score": 0.0,
        }

        if not self._agents:
            logger.debug("No agents registered, skipping A2A routing")
            routing_metadata["routing_method"] = "fallback_no_agents"
            return None, routing_metadata

        try:
            # Extract LLM intent signal (if available)
            llm_intent = None
            llm_confidence = 0.0
            if parsed_query:
                llm_intent = parsed_query.intent
                llm_confidence = parsed_query.intent_confidence
                routing_metadata["llm_intent"] = llm_intent.value
                routing_metadata["llm_confidence"] = llm_confidence

            # Weight configuration for hybrid scoring
            # When LLM intent is unavailable (no OpenAI), use capability-only routing
            if parsed_query and llm_confidence > 0:
                LLM_WEIGHT = 0.6  # Trust LLM intent classification
                CAPABILITY_WEIGHT = 0.4  # A2A capability fine-tuning
            else:
                # Fallback: capability-only routing (still works without OpenAI)
                LLM_WEIGHT = 0.0
                CAPABILITY_WEIGHT = 1.0
                routing_metadata["routing_method"] = "capability_only_fallback"
                logger.info("No LLM intent available - using capability-only routing")

            best_agent = None
            best_combined_score = 0.0

            for registered in self._agents.values():
                agent = registered.agent

                # Signal 1: LLM intent match (0.0 - 1.0), skip if LLM unavailable
                llm_score = 0.0
                if LLM_WEIGHT > 0:
                    llm_score = self._calculate_llm_intent_score(
                        agent, llm_intent, llm_confidence
                    )

                # Signal 2: A2A capability match using Kaizen API (0.0 - 1.0)
                capability_score = self._calculate_capability_score(agent, request)
                routing_metadata["capability_scores"][registered.agent_id] = (
                    capability_score
                )

                # Combined score with weights
                combined_score = (
                    LLM_WEIGHT * llm_score + CAPABILITY_WEIGHT * capability_score
                )
                routing_metadata["combined_scores"][registered.agent_id] = {
                    "llm_score": llm_score,
                    "capability_score": capability_score,
                    "combined": combined_score,
                }

                if combined_score > best_combined_score:
                    best_combined_score = combined_score
                    best_agent = agent

            # Accept if combined score is meaningful (> 0.3 means good LLM or capability match)
            COMBINED_THRESHOLD = 0.3
            if best_agent and best_combined_score >= COMBINED_THRESHOLD:
                routing_metadata["final_score"] = best_combined_score
                routing_metadata["selected_agent_id"] = getattr(
                    best_agent, "agent_id", "unknown"
                )
                logger.info(
                    f"AI-enhanced routing selected: {best_agent.agent_id} "
                    f"(combined={best_combined_score:.2f}, llm_intent={llm_intent.value if llm_intent else 'none'})"
                )
                return best_agent, routing_metadata
            else:
                routing_metadata["final_score"] = best_combined_score
                if best_agent:
                    routing_metadata["rejected_agent_id"] = getattr(
                        best_agent, "agent_id", "unknown"
                    )
                logger.debug(
                    f"Combined score {best_combined_score:.2f} below threshold "
                    f"{COMBINED_THRESHOLD}, falling back to intent-based routing"
                )
                routing_metadata["routing_method"] = "fallback_low_score"
                return None, routing_metadata

        except Exception as e:
            logger.warning(f"AI-enhanced routing failed: {e}, using fallback")
            routing_metadata["routing_method"] = "fallback_error"
            routing_metadata["error"] = str(e)

        return None, routing_metadata

    def _calculate_llm_intent_score(
        self,
        agent: Any,
        llm_intent: Optional[QueryIntent],
        llm_confidence: float,
    ) -> float:
        """
        Calculate score based on LLM-extracted intent matching agent's domain.

        Args:
            agent: Agent to score
            llm_intent: Intent classified by GPT-4o
            llm_confidence: Confidence of intent classification

        Returns:
            Score (0.0 to 1.0)
        """
        if not llm_intent:
            return 0.0

        # Map intents to agent capabilities
        INTENT_TO_CAPABILITY = {
            QueryIntent.MARKET_INTEL: ["marine_research", "opportunity_identification"],
            QueryIntent.MARKET_NEWS: ["marine_research", "opportunity_identification"],
            QueryIntent.SALES_OPPORTUNITY: [
                "marine_research",
                "opportunity_identification",
            ],
            QueryIntent.COMPETITOR_INTEL: ["competitor_intel", "competitor_analysis"],
            QueryIntent.CUSTOMER_INTEL: ["customer_matching", "customer_validation"],
            QueryIntent.CUSTOMER_RESEARCH: ["customer_matching", "customer_validation"],
            QueryIntent.KYP_DUE_DILIGENCE: [
                "customer_validation",
                "sanctions_screening",
                "kyp",
            ],
            QueryIntent.PRODUCT_FIT: ["product_fit", "knowledge_base", "product_info"],
            QueryIntent.PRODUCT_INFO: ["product_fit", "knowledge_base", "product_info"],
            QueryIntent.RELATIONSHIP_CHECK: [
                "customer_matching",
                "customer_validation",
            ],
            QueryIntent.GENERAL_QUESTION: [],  # Any agent can handle
        }

        expected_capabilities = INTENT_TO_CAPABILITY.get(llm_intent, [])

        if not expected_capabilities:
            # General question - give small boost to all agents
            return 0.2 * llm_confidence

        # Check if agent has matching capability
        try:
            if hasattr(agent, "_extract_primary_capabilities"):
                agent_capabilities = agent._extract_primary_capabilities()
                agent_cap_names = [c.name.lower() for c in agent_capabilities]

                for expected in expected_capabilities:
                    if expected.lower() in agent_cap_names:
                        # Strong match - return confidence-weighted score
                        return llm_confidence
        except Exception:
            pass

        return 0.0

    def _calculate_capability_score(self, agent: Any, task: str) -> float:
        """
        Calculate A2A capability match score using Kaizen's matches_requirement().

        Uses the framework's built-in capability matching algorithm instead of
        custom implementation.

        Args:
            agent: Agent to score
            task: Task description

        Returns:
            Match score (0.0 to 1.0)
        """
        try:
            if not hasattr(agent, "_extract_primary_capabilities"):
                return 0.0

            capabilities = agent._extract_primary_capabilities()
            if not capabilities:
                return 0.0

            # Use Kaizen's built-in matches_requirement() method
            best_score = 0.0
            for cap in capabilities:
                if hasattr(cap, "matches_requirement"):
                    # Kaizen's built-in semantic matching
                    score = cap.matches_requirement(task)
                    best_score = max(best_score, score)
                else:
                    # Fallback to manual keyword matching if method not available
                    score = self._fallback_keyword_score(cap, task)
                    best_score = max(best_score, score)

            return best_score

        except Exception as e:
            logger.debug(f"Error calculating capability score: {e}")
            return 0.0

    def _fallback_keyword_score(self, capability: Any, task: str) -> float:
        """
        Fallback keyword scoring when Kaizen's matches_requirement() unavailable.

        Args:
            capability: Capability object
            task: Task description

        Returns:
            Match score (0.0 to 1.0)
        """
        task_lower = task.lower()
        score = 0.0

        # Check name match
        if hasattr(capability, "name") and capability.name:
            if capability.name.lower().replace("_", " ") in task_lower:
                score = max(score, 0.9)

        # Check domain match
        if hasattr(capability, "domain") and capability.domain:
            if capability.domain.lower() in task_lower:
                score = max(score, 0.7)

        # Check keyword matches
        if hasattr(capability, "keywords") and capability.keywords:
            keyword_matches = sum(
                1 for kw in capability.keywords if kw.lower() in task_lower
            )
            if keyword_matches > 0:
                score = max(score, min(0.6 + (keyword_matches * 0.1), 0.8))

        return score

    def _build_clarification_response(
        self, parsed_query: ParsedQuery
    ) -> dict[str, Any]:
        """
        Build a clarification response when query understanding detects ambiguity.

        Implements orchestration_guide.md Section 5: Conversation Management.

        Args:
            parsed_query: ParsedQuery with clarification questions

        Returns:
            Clarification response dict
        """
        return {
            "type": "clarification_needed",
            "message": "I need a bit more information to help you better.",
            "clarification_reason": parsed_query.clarification_reason,
            "questions": parsed_query.clarification_questions,
            "partial_understanding": {
                "intent": parsed_query.intent.value,
                "intent_confidence": parsed_query.intent_confidence,
                "competitors": parsed_query.competitors,
                "companies": parsed_query.companies,
                "regions": parsed_query.regions,
                "products": parsed_query.products,
                "time_reference": parsed_query.time_reference,
            },
            "suggested_actions": self._generate_clarification_suggestions(parsed_query),
            "routing": "clarification",
        }

    def _generate_clarification_suggestions(
        self, parsed_query: ParsedQuery
    ) -> list[dict[str, str]]:
        """
        Generate suggested actions/buttons for clarification.

        Args:
            parsed_query: ParsedQuery with partial understanding

        Returns:
            List of suggestion dicts with label and value
        """
        suggestions = []

        # Time period suggestions for time-sensitive queries
        if (
            parsed_query.intent
            in [
                QueryIntent.COMPETITOR_INTEL,
                QueryIntent.MARKET_NEWS,
                QueryIntent.FINANCIAL_ANALYSIS,
            ]
            and not parsed_query.time_reference
        ):
            suggestions.extend(
                [
                    {"label": "Last 30 days", "value": "last 30 days"},
                    {"label": "Last quarter", "value": "last quarter"},
                    {"label": "Last year", "value": "last year"},
                    {"label": "All time", "value": "all available data"},
                ]
            )

        # Competitor suggestions if none specified
        if (
            parsed_query.intent == QueryIntent.COMPETITOR_INTEL
            and not parsed_query.competitors
        ):
            suggestions.extend(
                [
                    {"label": "Caterpillar/MaK", "value": "Caterpillar"},
                    {"label": "Cummins", "value": "Cummins"},
                    {"label": "MAN Energy", "value": "MAN Energy Solutions"},
                    {"label": "Wartsila", "value": "Wartsila"},
                ]
            )

        # Region suggestions
        if not parsed_query.regions:
            suggestions.extend(
                [
                    {"label": "APAC", "value": "APAC"},
                    {"label": "Europe", "value": "Europe"},
                    {"label": "Americas", "value": "Americas"},
                ]
            )

        return suggestions[:8]  # Limit to 8 suggestions

    def _score_capability(self, capability: Any, request_lower: str) -> float:
        """
        Score a capability against a request.

        Uses the same algorithm as Kaizen's A2A matching:
        1. Direct name match → 0.9
        2. Domain match → 0.7
        3. Keyword matches → 0.6 + 0.1 per match (max 0.8)
        4. Description overlap → 0.3 + 0.05 per word (max 0.5)

        Args:
            capability: Capability object
            request_lower: Lowercased request string

        Returns:
            Match score (0.0 to 0.9)
        """
        # 1. Direct name match (handle underscores)
        name_lower = capability.name.lower()
        name_normalized = name_lower.replace("_", " ")
        if name_lower in request_lower or name_normalized in request_lower:
            return 0.9

        # 2. Domain match
        if hasattr(capability, "domain") and capability.domain:
            if capability.domain.lower() in request_lower:
                return 0.7

        # 3. Keyword matches
        keyword_matches = 0
        if hasattr(capability, "keywords") and capability.keywords:
            for keyword in capability.keywords:
                if keyword.lower() in request_lower:
                    keyword_matches += 1

        if keyword_matches > 0:
            return min(0.6 + (keyword_matches * 0.1), 0.8)

        # 4. Description word overlap
        if hasattr(capability, "description") and capability.description:
            desc_words = set(capability.description.lower().split())
            req_words = set(request_lower.split())
            overlap = len(desc_words & req_words)
            if overlap > 0:
                return min(0.3 + (overlap * 0.05), 0.5)

        return 0.0

    # -------------------------------------------------------------------------
    # Health Monitoring
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all agents.

        Returns:
            Health status of all agents
        """
        results: dict[str, Any] = {
            "registry_status": "healthy",
            "initialized": self._initialized,
            "agent_count": len(self._agents),
            "query_understanding": {
                "enabled": self.enable_query_understanding,
                "available": self._query_engine is not None,
                "model": self._query_engine.model if self._query_engine else None,
            },
            "orchestration": {
                "data_inventory": {
                    "available": self._data_inventory is not None,
                    "coverage_summary": (
                        self._data_inventory.get_coverage_summary()
                        if self._data_inventory
                        else None
                    ),
                },
                "tool_executor": {
                    "available": self._tool_executor is not None,
                },
                "conversation_manager": {
                    "available": self._conversation_manager is not None,
                    "active_sessions": (
                        len(self._conversation_manager.sessions)
                        if self._conversation_manager
                        else 0
                    ),
                },
            },
            "agents": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for agent_id, registered in self._agents.items():
            try:
                if hasattr(registered.agent, "health_check"):
                    # Wrap in timeout
                    health = await asyncio.wait_for(
                        registered.agent.health_check(),
                        timeout=10.0,
                    )
                    registered.status = AgentStatus.ACTIVE
                    registered.error_count = 0
                else:
                    health = {"status": "no_health_check"}

                registered.last_health_check = datetime.now(timezone.utc)

                # Include circuit breaker status if available
                circuit_status = None
                agent_status = registered.status.value
                if agent_id in self._circuit_breakers:
                    circuit = self._circuit_breakers[agent_id]
                    circuit_state = circuit.state
                    circuit_status = {
                        "state": circuit_state,
                        "failure_count": circuit._failure_count,
                    }
                    # Degrade agent status if circuit is open
                    if circuit_state == "OPEN":
                        agent_status = "circuit_open"
                        registered.status = AgentStatus.ERROR
                    elif circuit_state == "HALF_OPEN":
                        agent_status = "recovering"

                results["agents"][agent_id] = {
                    "status": agent_status,
                    "health": health,
                    "circuit_breaker": circuit_status,
                }

            except asyncio.TimeoutError:
                registered.status = AgentStatus.ERROR
                registered.error_count += 1
                results["agents"][agent_id] = {
                    "status": "timeout",
                    "error": "Health check timed out",
                }

            except Exception as e:
                registered.status = AgentStatus.ERROR
                registered.error_count += 1
                results["agents"][agent_id] = {
                    "status": "error",
                    "error": str(e),
                }

        # Check orchestrator
        if self._orchestrator:
            try:
                results["orchestrator"] = await self._orchestrator.health_check()
            except Exception as e:
                results["orchestrator"] = {"status": "error", "error": str(e)}

        # Check overall registry status based on circuit breakers
        open_circuits = []
        half_open_circuits = []
        for agent_id, circuit in self._circuit_breakers.items():
            if circuit.state == "OPEN":
                open_circuits.append(agent_id)
            elif circuit.state == "HALF_OPEN":
                half_open_circuits.append(agent_id)

        # Add circuit summary
        results["circuit_summary"] = {
            "total_breakers": len(self._circuit_breakers),
            "open_count": len(open_circuits),
            "half_open_count": len(half_open_circuits),
            "open_agents": open_circuits,
            "recovering_agents": half_open_circuits,
        }

        # Degrade registry status if any circuits are open
        if open_circuits:
            results["registry_status"] = "degraded"
            results["degradation_reason"] = (
                f"Circuit breakers open for: {', '.join(open_circuits)}"
            )
        elif half_open_circuits:
            results["registry_status"] = "recovering"

        return results

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully shutdown all agents."""
        logger.info("Shutting down agent registry...")

        # Shutdown query understanding engine
        if self._query_engine:
            try:
                await self._query_engine.close()
                logger.info("Query understanding engine closed")
            except Exception as e:
                logger.warning(f"Error closing query engine: {e}")
            self._query_engine = None

        # Shutdown tool executor
        if self._tool_executor:
            try:
                await self._tool_executor.close()
                logger.info("Tool executor closed")
            except Exception as e:
                logger.warning(f"Error closing tool executor: {e}")
            self._tool_executor = None

        # Cleanup conversation manager sessions
        if self._conversation_manager:
            try:
                self._conversation_manager.cleanup_expired_sessions()
                logger.info("Conversation manager sessions cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up conversation manager: {e}")
            self._conversation_manager = None

        # Clear data inventory
        self._data_inventory = None

        # Shutdown orchestrator first
        if self._orchestrator:
            await self._orchestrator.shutdown()

        # Shutdown all registered agents
        for agent_id, registered in self._agents.items():
            try:
                if hasattr(registered.agent, "disconnect"):
                    await registered.agent.disconnect()
                elif hasattr(registered.agent, "shutdown"):
                    await registered.agent.shutdown()
                registered.status = AgentStatus.INACTIVE
                logger.info(f"Shutdown agent: {agent_id}")
            except Exception as e:
                logger.warning(f"Error shutting down {agent_id}: {e}")

        self._agents.clear()
        self._orchestrator = None
        self._initialized = False

        logger.info("Agent registry shutdown complete")

    async def __aenter__(self) -> "AgentRegistry":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()


# =============================================================================
# Factory Function
# =============================================================================


async def create_agent_registry(
    llm_provider: str = "openai",
    model: str = os.getenv("OPENAI_BASE_MODEL", "gpt-4"),
    auto_initialize: bool = True,
) -> AgentRegistry:
    """
    Factory function to create and optionally initialize an agent registry.

    Args:
        llm_provider: LLM provider for agents
        model: Model for agents
        auto_initialize: Whether to initialize immediately

    Returns:
        Configured AgentRegistry instance

    Example:
        registry = await create_agent_registry()
        result = await registry.process("Validate customer 1234567")
    """
    registry = AgentRegistry(
        llm_provider=llm_provider,
        model=model,
    )

    if auto_initialize:
        await registry.initialize()

    return registry
