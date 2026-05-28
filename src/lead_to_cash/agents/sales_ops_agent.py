"""
Sales Ops Orchestrator Agent

Central orchestrator for Lead-to-Cash operations with multi-agent coordination.

MANDATORY REFERENCE:
    This orchestrator follows the architecture defined in:
    `src/lead_to_cash/docs/architecture/agent_architecture.md`

Domain Agent Coordination:
    - MarketIntelAgent: Industry news, opportunities, events, regulations
    - CustomerIntelAgent: Customer profiling, SAP integration, matching
    - CompetitorIntelAgent: CAT, Cummins, MAN tracking
    - KYPAgent: Due diligence, risk assessment, compliance
    - ProductFitAgent: MTU/Bergen product matching, recommendations

Multi-Angle Analysis Rule (MANDATORY):
    For every user query, this orchestrator MUST:
    1. Identify the PRIMARY agent based on intent
    2. Check if ENRICHMENT from other agents is needed
    3. Synthesize results from multiple agents when applicable

Architecture:
    - Built on Kaizen BaseAgent with Control Protocol for interactive operations
    - Uses SharedMemoryPool for agent coordination
    - Implements supervisor-worker pattern for task delegation
    - Supports async operations for non-blocking SAP calls
    - A2A semantic routing via agent capabilities

Usage:
    from lead_to_cash.agents import SalesOpsAgent, SalesOpsConfig

    config = SalesOpsConfig()
    agent = SalesOpsAgent(config)

    # Process user request (multi-agent coordination automatic)
    result = await agent.process_request(
        "Tell me about Penguin Ferries"  # Invokes CustomerIntel + MarketIntel + CompetitorIntel
    )
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.autonomy.control import ControlProtocol
from kaizen.core.autonomy.control.transports import InMemoryTransport
from kaizen.core.base_agent import BaseAgent
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

# Import domain agents (original production-ready implementations)
from lead_to_cash.agents.competitor_intel_agent import (
    CompetitorIntelAgent,
    CompetitorIntelConfig,
)
from lead_to_cash.agents.customer_matcher_agent import (
    CustomerMatcherAgent,
    CustomerMatcherConfig,
    CustomerMatchResult,
)
from lead_to_cash.agents.data_management_agent import (
    DataManagementAgent,
    DataManagementConfig,
)
from lead_to_cash.agents.due_diligence_agent import (
    DueDiligenceAgent,
    DueDiligenceConfig,
    ValidationResult,
    ValidationStatus,
)
from lead_to_cash.agents.entity_resolution_agent import (
    EntityResolutionAgent,
    EntityResolutionConfig,
)
from lead_to_cash.agents.financial_ops_agent import (
    FinancialOpsAgent,
    FinancialOpsConfig,
)
from lead_to_cash.agents.knowledge_base_agent import (
    KnowledgeBaseAgent,
    KnowledgeBaseConfig,
)
from lead_to_cash.agents.marine_intel_agent import (
    MarineIntelAgent,
    MarineIntelConfig,
)
from lead_to_cash.agents.opportunity_agent import (
    OpportunityAgent,
    OpportunityConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class TaskType(str, Enum):
    """Types of tasks the orchestrator can handle."""

    VALIDATE_CUSTOMER = "validate_customer"
    CHECK_CREDIT = "check_credit"
    CREATE_ORDER = "create_order"
    SIMULATE_ORDER = "simulate_order"
    GET_OPPORTUNITY = "get_opportunity"
    CONVERT_OPPORTUNITY = "convert_opportunity"
    GET_PRODUCT_CONFIG = "get_product_config"
    HEALTH_CHECK = "health_check"
    UNKNOWN = "unknown"


class AgentType(str, Enum):
    """Specialized agent types mapped to production-ready agents.

    Intelligence Domain agents (non-overlapping responsibilities):
    - MARINE_INTEL: MarineIntelAgent - Industry news, opportunities, events
    - CUSTOMER_MATCHER: CustomerMatcherAgent - Customer profiling, SAP lookup, matching
    - COMPETITOR_INTEL: CompetitorIntelAgent - CAT, Cummins, MAN tracking
    - DUE_DILIGENCE: DueDiligenceAgent - KYP, risk assessment, compliance
    - KNOWLEDGE_BASE: KnowledgeBaseAgent - Engine matching, KB queries

    Order Processing Domain agents (ADR-002):
    - OPPORTUNITY: OpportunityAgent - CEC and IPAS data extraction
    - DATA_MANAGEMENT: DataManagementAgent - MS5 entry assistance
    - FINANCIAL_OPS: FinancialOpsAgent - Draft order creation

    Supporting agents:
    - ENTITY_RESOLUTION: EntityResolutionAgent - Company name to canonical entity
    """

    # Intelligence Domain agents
    MARINE_INTEL = "marine_intel"  # MarineIntelAgent
    CUSTOMER_MATCHER = "customer_matcher"  # CustomerMatcherAgent
    COMPETITOR_INTEL = "competitor_intel"  # CompetitorIntelAgent
    DUE_DILIGENCE = "due_diligence"  # DueDiligenceAgent
    KNOWLEDGE_BASE = "knowledge_base"  # KnowledgeBaseAgent

    # Order Processing Domain agents (ADR-002)
    OPPORTUNITY = "opportunity"  # OpportunityAgent
    DATA_MANAGEMENT = "data_management"  # DataManagementAgent
    FINANCIAL_OPS = "financial_ops"  # FinancialOpsAgent

    # Supporting agents
    ENTITY_RESOLUTION = "entity_resolution"  # EntityResolutionAgent


@dataclass
class TaskContext:
    """Context for a task being processed."""

    task_id: str
    task_type: TaskType
    user_request: str
    extracted_params: dict[str, Any]
    assigned_agent: Optional[AgentType]
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "user_request": self.user_request,
            "extracted_params": self.extracted_params,
            "assigned_agent": (
                self.assigned_agent.value if self.assigned_agent else None
            ),
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "result": self.result,
            "error": self.error,
        }


# =============================================================================
# Signature Definition
# =============================================================================


class SalesOpsSignature(Signature):
    """
    Signature for Sales Ops orchestration.

    Interprets user requests and determines the appropriate action
    and specialized agent to handle the request.
    """

    # Input Fields
    user_request: str = InputField(description="Natural language request from the user")
    conversation_history: str = InputField(
        description="Previous conversation context as JSON array", default="[]"
    )
    available_data: str = InputField(
        description="Available context data as JSON (customer IDs, opportunity IDs, etc.)",
        default="{}",
    )

    # Output Fields
    task_type: str = OutputField(
        description="Identified task type: validate_customer, check_credit, create_order, "
        "simulate_order, get_opportunity, convert_opportunity, get_product_config, health_check, unknown"
    )
    assigned_agent: str = OutputField(
        description="Agent to handle request: due_diligence, opportunity, data_management, financial_ops"
    )
    extracted_params: str = OutputField(
        description="JSON object with extracted parameters (customer_id, order_value, opportunity_id, etc.)"
    )
    clarification_needed: str = OutputField(
        description="If parameters are missing, what clarification is needed. Empty if none."
    )
    response_to_user: str = OutputField(
        description="Human-friendly response to the user explaining what will be done"
    )
    confidence: str = OutputField(
        description="Confidence in interpretation: high, medium, low"
    )


class TaskRoutingSignature(Signature):
    """Signature for routing decisions."""

    task_description: str = InputField(description="Description of the task")
    available_agents: str = InputField(
        description="JSON array of available agent capabilities"
    )

    selected_agent: str = OutputField(description="Agent ID to handle the task")
    routing_reason: str = OutputField(description="Reason for this routing decision")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SalesOpsConfig:
    """
    Configuration for Sales Ops Orchestrator Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_BASE_MODEL", "gpt-4")
    temperature: float = 0.5  # Balanced for interpretation
    max_tokens: int = 2000

    # Orchestration Settings
    max_concurrent_tasks: int = 5
    task_timeout_seconds: float = 120.0
    require_confirmation_for: list[str] = field(
        default_factory=lambda: ["create_order", "convert_opportunity"]
    )

    # Human-in-the-Loop Settings
    auto_approve_validations: bool = True  # Auto-approve validation requests
    require_approval_over_value: float = 100000.0  # Require approval for large orders

    # Agent Metadata
    agent_name: str = "sales_ops_orchestrator"
    agent_description: str = "Central orchestrator for Lead-to-Cash operations"

    # Memory Settings
    max_turns: int = 50  # Conversation memory


# =============================================================================
# Sales Ops Orchestrator Agent Implementation
# =============================================================================


class SalesOpsAgent(BaseAgent):
    """
    Sales Operations Orchestrator Agent.

    Central coordinator for Lead-to-Cash operations that:
    - Interprets natural language requests
    - Routes to specialized agents
    - Manages conversation context
    - Handles human-in-the-loop confirmations

    Architecture:
    - Supervisor-Worker pattern with semantic task routing
    - SharedMemoryPool for agent coordination
    - Control Protocol for interactive operations
    - Async execution for non-blocking SAP calls

    Example:
        config = SalesOpsConfig()
        agent = SalesOpsAgent(config)

        # Process a request
        result = await agent.process_request(
            "Check if customer 1234567 can place a $75,000 order"
        )

        # Interactive mode with approvals
        async with agent.interactive_session() as session:
            result = await session.process_with_confirmation(
                "Create order for opportunity OPP-12345"
            )
    """

    def __init__(
        self,
        config: SalesOpsConfig,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
        control_protocol: Optional[ControlProtocol] = None,
    ):
        """
        Initialize Sales Ops Orchestrator.

        Args:
            config: Agent configuration
            shared_memory: Shared memory pool for agent coordination
            agent_id: Unique agent identifier
            control_protocol: Control protocol for human-in-the-loop
        """
        # Create shared memory if not provided
        if shared_memory is None:
            shared_memory = SharedMemoryPool()

        super().__init__(
            config=config,
            signature=SalesOpsSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
            control_protocol=control_protocol,
        )

        self.domain_config = config
        self.shared_memory = shared_memory
        self._shared_memory = shared_memory  # Alias for consistent access pattern
        self._control_protocol = control_protocol

        # Initialize specialized agents
        # NOTE: Currently creates agents directly. In a future refactor, these
        # should be obtained from an AgentRegistry for better A2A coordination.
        self._agents: dict[AgentType, BaseAgent] = {}
        self._initialize_agents()

        # Service initialization tracking
        self._services_initialized = False

        # Task tracking
        self._active_tasks: dict[str, TaskContext] = {}
        self._conversation_history: list[dict[str, str]] = []
        self._task_counter = 0

    def _initialize_agents(self) -> None:
        """Initialize ALL production-ready domain agents.

        Domain Agent Architecture (non-overlapping responsibilities):
        - MarineIntelAgent: Industry news, opportunities, events, regulations
        - CustomerMatcherAgent: Customer profiling, SAP lookup, matching
        - CompetitorIntelAgent: CAT, Cummins, MAN tracking
        - DueDiligenceAgent: KYP, risk assessment, compliance
        - KnowledgeBaseAgent: Engine matching, KB queries, product fit
        """
        # 1. Marine Intelligence Agent - Industry news, opportunities
        marine_config = MarineIntelConfig(
            llm_provider=self.domain_config.llm_provider,
            model=self.domain_config.model,
        )
        self._agents[AgentType.MARINE_INTEL] = MarineIntelAgent(
            config=marine_config,
            shared_memory=self.shared_memory,
            agent_id="marine_intel_worker",
        )

        # 2. Customer Matcher Agent - Customer profiling, SAP lookup
        customer_config = CustomerMatcherConfig(
            llm_provider=self.domain_config.llm_provider,
            model=self.domain_config.model,
        )
        self._agents[AgentType.CUSTOMER_MATCHER] = CustomerMatcherAgent(
            config=customer_config,
            shared_memory=self.shared_memory,
            agent_id="customer_matcher_worker",
        )

        # 3. Competitor Intelligence Agent - CAT, Cummins, MAN tracking
        competitor_config = CompetitorIntelConfig(
            llm_provider=self.domain_config.llm_provider,
            model=self.domain_config.model,
        )
        self._agents[AgentType.COMPETITOR_INTEL] = CompetitorIntelAgent(
            config=competitor_config,
            shared_memory=self.shared_memory,
            agent_id="competitor_intel_worker",
        )

        # 4. Due Diligence Agent - KYP, risk assessment
        dd_config = DueDiligenceConfig(
            llm_provider=self.domain_config.llm_provider,
            model=self.domain_config.model,
        )
        self._agents[AgentType.DUE_DILIGENCE] = DueDiligenceAgent(
            config=dd_config,
            shared_memory=self.shared_memory,
            agent_id="due_diligence_worker",
        )

        # 5. Knowledge Base Agent - Engine matching, product fit
        kb_config = KnowledgeBaseConfig(
            llm_provider=self.domain_config.llm_provider,
            model=self.domain_config.model,
        )
        self._agents[AgentType.KNOWLEDGE_BASE] = KnowledgeBaseAgent(
            config=kb_config,
            shared_memory=self.shared_memory,
            agent_id="knowledge_base_worker",
        )

        # =====================================================================
        # Order Processing Domain Agents (ADR-002)
        # =====================================================================

        # 6. Opportunity Agent - CEC and IPAS data extraction
        opp_config = OpportunityConfig(
            model=self.domain_config.model,
        )
        self._agents[AgentType.OPPORTUNITY] = OpportunityAgent(config=opp_config)

        # 7. Data Management Agent - MS5 entry assistance
        dm_config = DataManagementConfig(
            model=self.domain_config.model,
        )
        self._agents[AgentType.DATA_MANAGEMENT] = DataManagementAgent(config=dm_config)

        # 8. Financial Operations Agent - Draft order creation
        fin_config = FinancialOpsConfig(
            model=self.domain_config.model,
            allow_final_orders=False,  # Safety: Only draft orders by default
        )
        self._agents[AgentType.FINANCIAL_OPS] = FinancialOpsAgent(config=fin_config)

        # =====================================================================
        # Supporting Agents
        # =====================================================================

        # 9. Entity Resolution Agent - Company name to canonical entity
        er_config = EntityResolutionConfig(
            model=self.domain_config.model,
        )
        self._agents[AgentType.ENTITY_RESOLUTION] = EntityResolutionAgent(
            config=er_config,
            shared_memory=self.shared_memory,
            agent_id="entity_resolution_worker",
        )

        logger.info(
            f"Initialized {len(self._agents)} domain agents: {list(self._agents.keys())}"
        )

    async def initialize_services(self) -> None:
        """
        Async initialization of databases and embedding services.

        MUST be called before processing requests. Each domain agent requires:
        - MarineIntelAgent: PostgreSQL (marine_intel DB)
        - CompetitorIntelAgent: PostgreSQL + pgvector embeddings
        - KnowledgeBaseAgent: PostgreSQL + pgvector embeddings
        - CustomerMatcherAgent: SAP/CPI connection (lazy)
        - DueDiligenceAgent: SAP MS5 connection (lazy)

        Usage:
            agent = SalesOpsAgent(config)
            await agent.initialize_services()  # Initialize DBs
            result = await agent.process_request("query")
            await agent.shutdown_services()  # Cleanup

        Or use as async context manager:
            async with SalesOpsAgent(config) as agent:
                result = await agent.process_request("query")
        """
        import asyncio

        init_tasks = []

        # KnowledgeBaseAgent has explicit initialize() for DB + embeddings
        kb_agent = self._agents.get(AgentType.KNOWLEDGE_BASE)
        if kb_agent and hasattr(kb_agent, "initialize"):
            init_tasks.append(kb_agent.initialize())
            logger.info("Initializing KnowledgeBaseAgent database and embeddings")

        # CompetitorIntelAgent database needs initialization
        competitor_agent = self._agents.get(AgentType.COMPETITOR_INTEL)
        if competitor_agent and hasattr(competitor_agent, "db"):
            if hasattr(competitor_agent.db, "initialize"):
                init_tasks.append(competitor_agent.db.initialize())
                logger.info("Initializing CompetitorIntelAgent database")

        # MarineIntelAgent database initializes lazily via get_marine_intel_db()
        # but we can ensure it's ready
        marine_agent = self._agents.get(AgentType.MARINE_INTEL)
        if marine_agent and hasattr(marine_agent, "db"):
            if hasattr(marine_agent.db, "initialize"):
                init_tasks.append(marine_agent.db.initialize())
                logger.info("Initializing MarineIntelAgent database")

        # Execute all initialization in parallel
        init_failures = []
        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Service initialization {i} failed: {result}")
                    init_failures.append(result)
                else:
                    logger.info(f"Service initialization {i} completed")

        # Only mark as initialized if ALL services succeeded
        if init_failures:
            self._services_initialized = False
            logger.error(
                f"Service initialization FAILED: {len(init_failures)} services failed to connect"
            )
            # Raise the first failure to alert the caller
            raise RuntimeError(
                f"Failed to initialize {len(init_failures)} services. "
                f"First error: {init_failures[0]}"
            )
        else:
            self._services_initialized = True
            logger.info("All agent services initialized successfully")

    async def shutdown_services(self) -> None:
        """
        Graceful shutdown of all agent database connections and services.
        """
        import asyncio

        shutdown_tasks = []

        # KnowledgeBaseAgent cleanup
        kb_agent = self._agents.get(AgentType.KNOWLEDGE_BASE)
        if kb_agent and hasattr(kb_agent, "close"):
            shutdown_tasks.append(kb_agent.close())

        # CompetitorIntelAgent cleanup
        competitor_agent = self._agents.get(AgentType.COMPETITOR_INTEL)
        if competitor_agent and hasattr(competitor_agent, "db"):
            if hasattr(competitor_agent.db, "close"):
                shutdown_tasks.append(competitor_agent.db.close())

        # MarineIntelAgent cleanup
        marine_agent = self._agents.get(AgentType.MARINE_INTEL)
        if marine_agent and hasattr(marine_agent, "db"):
            if hasattr(marine_agent.db, "close"):
                shutdown_tasks.append(marine_agent.db.close())

        # DueDiligenceAgent MS5 disconnect
        dd_agent = self._agents.get(AgentType.DUE_DILIGENCE)
        if dd_agent and hasattr(dd_agent, "disconnect"):
            shutdown_tasks.append(dd_agent.disconnect())

        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)

        self._services_initialized = False
        logger.info("All agent services shut down")

    async def __aenter__(self) -> "SalesOpsAgent":
        """Async context manager entry - initializes all services."""
        await self.initialize_services()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - shuts down all services."""
        await self.shutdown_services()

    # -------------------------------------------------------------------------
    # Request Processing
    # -------------------------------------------------------------------------

    async def process_request(
        self,
        user_request: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process a user request through the orchestrator.

        This is the main entry point for all user interactions.

        Args:
            user_request: Natural language request from user
            context: Optional context data (customer IDs, etc.)

        Returns:
            Processing result with response and any outputs
        """
        self._task_counter += 1
        task_id = (
            f"task_{self._task_counter}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
        )

        logger.info(f"Processing request [{task_id}]: {user_request[:100]}...")

        try:
            # Step 1: Interpret the request using LLM
            interpretation = await self._interpret_request(user_request, context)

            # Step 1.5: Auto-resolve customer name if needed
            interpretation, customer_resolution = (
                await self._resolve_customer_if_needed(interpretation, context)
            )

            # Add customer resolution to response metadata if available
            customer_metadata = {}
            if customer_resolution:
                customer_metadata["customer_resolution"] = customer_resolution
                logger.info(f"Customer resolution: {customer_resolution.get('status')}")

            # Step 2: Check if clarification is needed (including from customer resolution)
            if interpretation.get("clarification_needed"):
                result = await self._handle_clarification(
                    task_id, user_request, interpretation
                )
                if customer_metadata:
                    result["customer_resolution"] = customer_resolution
                return result

            # Step 3: Create task context
            task_context = TaskContext(
                task_id=task_id,
                task_type=TaskType(interpretation.get("task_type", "unknown")),
                user_request=user_request,
                extracted_params=json.loads(
                    interpretation.get("extracted_params", "{}")
                ),
                assigned_agent=(
                    AgentType(interpretation["assigned_agent"])
                    if interpretation.get("assigned_agent")
                    else None
                ),
                status="processing",
                started_at=datetime.now(timezone.utc),
            )
            self._active_tasks[task_id] = task_context

            # Step 4: Check if confirmation is required
            if await self._requires_confirmation(task_context):
                return await self._request_confirmation(task_context, interpretation)

            # Step 5: Route to specialized agent
            result = await self._route_to_agent(task_context)

            # Step 6: Update conversation history
            self._update_conversation(user_request, result)

            # Step 7: Format response
            response = self._format_response(task_context, result, interpretation)

            # Add customer resolution info if available
            if customer_metadata:
                response["customer_resolution"] = customer_resolution

            return response

        except Exception as e:
            logger.error(f"Error processing request [{task_id}]: {e}")
            return {
                "type": "error",  # Required for frontend response handling
                "success": False,
                "task_id": task_id,
                "error": str(e),
                "response": f"I encountered an error processing your request: {e}",
            }

    async def _interpret_request(
        self,
        user_request: str,
        context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Use LLM to interpret the user request.

        Args:
            user_request: Natural language request
            context: Optional context data

        Returns:
            Interpretation with task type, agent, and parameters
        """
        # Build conversation history for context
        history_json = json.dumps(self._conversation_history[-10:])  # Last 10 turns
        context_json = json.dumps(context or {})

        # Run through signature-based agent
        result = self.run(
            user_request=user_request,
            conversation_history=history_json,
            available_data=context_json,
        )

        return result

    async def _resolve_customer_if_needed(
        self,
        interpretation: dict[str, Any],
        context: Optional[dict[str, Any]],
    ) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
        """
        Auto-invoke CustomerMatcherAgent when customer identification is ambiguous.

        This method checks if:
        1. The task involves customer operations (validate, credit check, etc.)
        2. A customer name is mentioned but no customer_id is provided
        3. CustomerMatcherAgent can resolve the name to a customer_id

        Args:
            interpretation: Parsed interpretation from LLM
            context: Optional context with customer data

        Returns:
            Tuple of (updated_interpretation, customer_resolution_result)
            - If no resolution needed: (interpretation, None)
            - If resolved: (interpretation with customer_id, resolution_result)
            - If needs user selection: (interpretation with clarification, resolution_result)
        """
        context = context or {}
        extracted_params = json.loads(interpretation.get("extracted_params", "{}"))

        # Check if customer_id already provided
        if context.get("customer_id") or extracted_params.get("customer_id"):
            return interpretation, None

        # Check if customer name is mentioned but needs resolution
        customer_name = extracted_params.get("customer_name") or extracted_params.get(
            "customer"
        )
        if not customer_name:
            return interpretation, None

        # Check if this is a customer-related task
        task_type = interpretation.get("task_type", "")
        customer_tasks = [
            "validate_customer",
            "check_credit",
            "create_order",
            "simulate_order",
        ]
        if task_type not in customer_tasks:
            return interpretation, None

        logger.info(f"Auto-resolving customer name: {customer_name}")

        # Get CustomerMatcherAgent
        customer_matcher = self._agents.get(AgentType.CUSTOMER_MATCHER)
        if not customer_matcher:
            logger.warning("CustomerMatcherAgent not available")
            return interpretation, None

        try:
            # Invoke CustomerMatcherAgent
            match_result: CustomerMatchResult = await customer_matcher.match_customer(
                customer_name
            )

            if not match_result.candidates:
                # No matches found - add clarification
                interpretation["clarification_needed"] = (
                    f"I couldn't find a customer matching '{customer_name}'. "
                    "Please provide the exact customer name or SAP customer ID."
                )
                return interpretation, {"status": "no_matches", "query": customer_name}

            best_match = match_result.best_match

            # High confidence match (>=90%) - auto-select
            if best_match and best_match.confidence_score >= 90:
                logger.info(
                    f"Auto-selected customer: {best_match.name} "
                    f"(ID: {best_match.customer_id}, confidence: {best_match.confidence_score}%)"
                )
                # Update extracted_params with resolved customer_id
                extracted_params["customer_id"] = best_match.customer_id
                extracted_params["customer_name_resolved"] = best_match.name
                extracted_params["customer_match_confidence"] = (
                    best_match.confidence_score
                )
                interpretation["extracted_params"] = json.dumps(extracted_params)

                return interpretation, {
                    "status": "auto_resolved",
                    "customer_id": best_match.customer_id,
                    "customer_name": best_match.name,
                    "confidence": best_match.confidence_score,
                }

            # Multiple matches or low confidence - ask user to confirm
            if (
                match_result.requires_user_confirmation
                or len(match_result.candidates) > 1
            ):
                candidates_text = "\n".join(
                    [
                        f"  {i+1}. {c.name} (ID: {c.customer_id}, confidence: {c.confidence_score}%)"
                        for i, c in enumerate(match_result.candidates[:5])
                    ]
                )
                interpretation["clarification_needed"] = (
                    f"Multiple customers found matching '{customer_name}':\n"
                    f"{candidates_text}\n\n"
                    f"Please specify which customer you mean by providing the customer ID "
                    f"or confirming the name."
                )
                return interpretation, {
                    "status": "needs_selection",
                    "candidates": [c.to_dict() for c in match_result.candidates[:5]],
                }

            # Single match with medium confidence - use it but note uncertainty
            if best_match:
                extracted_params["customer_id"] = best_match.customer_id
                extracted_params["customer_name_resolved"] = best_match.name
                extracted_params["customer_match_confidence"] = (
                    best_match.confidence_score
                )
                interpretation["extracted_params"] = json.dumps(extracted_params)

                return interpretation, {
                    "status": "resolved_with_uncertainty",
                    "customer_id": best_match.customer_id,
                    "customer_name": best_match.name,
                    "confidence": best_match.confidence_score,
                }

        except Exception as e:
            logger.error(f"CustomerMatcherAgent error: {e}")
            # Continue without resolution - let user provide customer_id

        return interpretation, None

    async def _handle_clarification(
        self,
        task_id: str,
        user_request: str,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle case where clarification is needed from user."""
        clarification = interpretation.get("clarification_needed", "")

        # If we have control protocol, ask user directly
        if self._control_protocol:
            try:
                answer = await self.ask_user_question(
                    question=clarification,
                    options=["Provide details", "Cancel request"],
                )
                if answer == "Cancel request":
                    return {
                        "success": False,
                        "task_id": task_id,
                        "status": "cancelled",
                        "response": "Request cancelled. Let me know if you need anything else.",
                    }
            except Exception:
                pass  # Fall through to returning clarification request

        return {
            "success": False,
            "task_id": task_id,
            "status": "needs_clarification",
            "clarification_needed": clarification,
            "response": interpretation.get("response_to_user", clarification),
        }

    async def _requires_confirmation(self, task_context: TaskContext) -> bool:
        """Check if task requires user confirmation."""
        # Check if task type requires confirmation
        if task_context.task_type.value in self.domain_config.require_confirmation_for:
            return True

        # Check if order value exceeds threshold
        order_value = task_context.extracted_params.get("order_value", 0)
        if order_value > self.domain_config.require_approval_over_value:
            return True

        return False

    async def _request_confirmation(
        self,
        task_context: TaskContext,
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        """Request user confirmation for critical operations."""
        if self._control_protocol:
            try:
                # Build confirmation details
                details = {
                    "task_type": task_context.task_type.value,
                    "parameters": task_context.extracted_params,
                }

                approved = await self.request_approval(
                    action=f"Proceed with {task_context.task_type.value}",
                    details=details,
                )

                if approved:
                    # Proceed with task
                    result = await self._route_to_agent(task_context)
                    self._update_conversation(task_context.user_request, result)
                    return self._format_response(task_context, result, interpretation)
                else:
                    task_context.status = "cancelled"
                    return {
                        "success": False,
                        "task_id": task_context.task_id,
                        "status": "cancelled",
                        "response": "Operation cancelled by user.",
                    }

            except Exception as e:
                logger.warning(f"Confirmation request failed: {e}")

        # No control protocol or confirmation failed - return pending
        return {
            "success": False,
            "task_id": task_context.task_id,
            "status": "pending_confirmation",
            "response": interpretation.get("response_to_user", ""),
            "requires_confirmation": True,
            "task_details": task_context.to_dict(),
        }

    async def _route_to_agent(self, task_context: TaskContext) -> dict[str, Any]:
        """
        Route task to appropriate specialized agent with multi-agent coordination.

        Multi-Angle Analysis Rule:
        For company/customer queries, automatically invoke enrichment agents:
        - Primary: The agent assigned based on intent
        - Enrichment: Additional agents for comprehensive analysis

        Args:
            task_context: Task context with routing information

        Returns:
            Agent execution result (potentially synthesized from multiple agents)
        """
        agent_type = task_context.assigned_agent
        params = task_context.extracted_params
        user_request = task_context.user_request

        # Determine if multi-agent coordination is needed
        enrichment_agents = self._get_enrichment_agents(
            agent_type, user_request, params
        )

        # Execute primary agent
        primary_result = await self._execute_agent(agent_type, params, user_request)

        # If enrichment needed, execute additional agents and synthesize
        if enrichment_agents:
            enrichment_results = await self._execute_enrichment_agents(
                enrichment_agents, params, user_request
            )
            return await self._synthesize_multi_agent_results(
                primary_result, enrichment_results, user_request
            )

        return primary_result

    def _get_enrichment_agents(
        self, primary_agent: AgentType, user_request: str, params: dict[str, Any]
    ) -> list[AgentType]:
        """
        Determine which additional agents should be invoked for enrichment.

        Multi-Angle Analysis Rules (from agent_architecture.md):
        - Company queries: Always check customer status + competitor activity
        - Market intel: Check if mentioned companies are our customers
        - Customer queries: Check for competitor activity + product fit
        """
        enrichment = []
        request_lower = user_request.lower()

        # Check for company/customer name in request
        has_company_mention = any(
            indicator in request_lower
            for indicator in [
                "company",
                "customer",
                "about",
                "tell me",
                "who is",
                "ferries",
                "marine",
                "shipping",
            ]
        )

        if primary_agent == AgentType.MARINE_INTEL:
            # Market intel should check if companies are customers
            if has_company_mention:
                enrichment.append(AgentType.CUSTOMER_MATCHER)
            # Always check competitor angle for market intel
            enrichment.append(AgentType.COMPETITOR_INTEL)

        elif primary_agent == AgentType.CUSTOMER_MATCHER:
            # Customer queries should check competitor activity and product fit
            enrichment.append(AgentType.COMPETITOR_INTEL)
            enrichment.append(AgentType.KNOWLEDGE_BASE)

        elif primary_agent == AgentType.COMPETITOR_INTEL:
            # Competitor queries should check customer impact
            if has_company_mention:
                enrichment.append(AgentType.CUSTOMER_MATCHER)

        elif primary_agent == AgentType.DUE_DILIGENCE:
            # Due diligence may need customer context
            if params.get("customer_name") and not params.get("customer_id"):
                enrichment.append(AgentType.CUSTOMER_MATCHER)

        return enrichment

    async def _execute_agent(
        self, agent_type: AgentType, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute a single agent based on type."""
        if agent_type == AgentType.DUE_DILIGENCE:
            return await self._execute_due_diligence(params)

        elif agent_type == AgentType.CUSTOMER_MATCHER:
            return await self._execute_customer_matcher(params, user_request)

        elif agent_type == AgentType.MARINE_INTEL:
            return await self._execute_marine_intel(params, user_request)

        elif agent_type == AgentType.COMPETITOR_INTEL:
            return await self._execute_competitor_intel(params, user_request)

        elif agent_type == AgentType.KNOWLEDGE_BASE:
            return await self._execute_knowledge_base(params, user_request)

        elif agent_type == AgentType.OPPORTUNITY:
            return await self._execute_opportunity(params, user_request)

        elif agent_type == AgentType.DATA_MANAGEMENT:
            return await self._execute_data_management(params, user_request)

        elif agent_type == AgentType.FINANCIAL_OPS:
            return await self._execute_financial_ops(params, user_request)

        elif agent_type == AgentType.ENTITY_RESOLUTION:
            return await self._execute_entity_resolution(params, user_request)

        else:
            return {"error": f"Unknown agent type: {agent_type}"}

    async def _execute_enrichment_agents(
        self,
        enrichment_agents: list[AgentType],
        params: dict[str, Any],
        user_request: str,
    ) -> dict[AgentType, dict[str, Any]]:
        """Execute enrichment agents in parallel."""
        import asyncio

        results = {}
        tasks = []

        for agent_type in enrichment_agents:
            if agent_type in self._agents:
                tasks.append(self._execute_agent(agent_type, params, user_request))

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, agent_type in enumerate(enrichment_agents):
                if i < len(task_results):
                    result = task_results[i]
                    if isinstance(result, Exception):
                        results[agent_type] = {"error": str(result)}
                    else:
                        results[agent_type] = result

        return results

    async def _synthesize_multi_agent_results(
        self,
        primary_result: dict[str, Any],
        enrichment_results: dict[AgentType, dict[str, Any]],
        user_request: str,
    ) -> dict[str, Any]:
        """
        Synthesize results from multiple agents into a unified response.

        This combines primary results with enrichment data to provide
        comprehensive multi-angle analysis.
        """
        synthesized = {
            "primary_result": primary_result,
            "enrichment": {},
            "multi_agent_analysis": True,
        }

        # Add enrichment results with agent labels
        for agent_type, result in enrichment_results.items():
            if result and not result.get("error"):
                enrichment_key = agent_type.value
                synthesized["enrichment"][enrichment_key] = result

        # Create summary of multi-angle analysis
        angles_covered = ["primary"]
        if AgentType.CUSTOMER_MATCHER in enrichment_results:
            angles_covered.append("customer_status")
        if AgentType.COMPETITOR_INTEL in enrichment_results:
            angles_covered.append("competitor_activity")
        if AgentType.KNOWLEDGE_BASE in enrichment_results:
            angles_covered.append("product_fit")
        if AgentType.DUE_DILIGENCE in enrichment_results:
            angles_covered.append("risk_assessment")

        synthesized["analysis_angles"] = angles_covered
        synthesized["user_request"] = user_request

        return synthesized

    async def _execute_customer_matcher(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute customer matcher agent for customer identification."""
        agent: CustomerMatcherAgent = self._agents.get(AgentType.CUSTOMER_MATCHER)
        if not agent:
            return {"error": "Customer matcher agent not available"}

        customer_name = params.get("customer_name") or params.get("company_name")
        if not customer_name:
            # Try to extract company name from user request
            customer_name = user_request

        try:
            result = await agent.match_customer(customer_name)
            return {
                "status": "success",
                "agent": "customer_matcher",
                "matches": [
                    {
                        "name": c.name,
                        "sap_id": c.sap_id,
                        "confidence": c.confidence_score,
                        "source": c.source.value if c.source else "unknown",
                    }
                    for c in result.candidates[:5]
                ],
                "best_match": result.candidates[0].name if result.candidates else None,
                "requires_confirmation": result.requires_user_confirmation,
            }
        except Exception as e:
            logger.error(f"Customer matcher error: {e}")
            return {"error": str(e), "agent": "customer_matcher"}

    async def _execute_marine_intel(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute marine intel agent for market/industry intelligence."""
        agent: MarineIntelAgent = self._agents.get(AgentType.MARINE_INTEL)
        if not agent:
            return {"error": "Marine intel agent not available"}

        try:
            # Use the agent's query capabilities
            # MarineIntelAgent supports various research methods
            region = params.get("region")
            sector = params.get("sector")

            # Use run() method for general queries
            result = agent.run(query=user_request)
            return {
                "status": "success",
                "agent": "marine_intel",
                "result": result,
                "region": region,
                "sector": sector,
            }
        except Exception as e:
            logger.error(f"Marine intel error: {e}")
            return {"error": str(e), "agent": "marine_intel"}

    async def _execute_competitor_intel(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute competitor intel agent for competitor tracking."""
        agent: CompetitorIntelAgent = self._agents.get(AgentType.COMPETITOR_INTEL)
        if not agent:
            return {"error": "Competitor intel agent not available"}

        try:
            # CompetitorIntelAgent has query() method for RAG-based queries
            competitor_filter = params.get("competitor", "all")
            result = await agent.query(
                user_request, competitor_filter=competitor_filter
            )
            return {
                "status": "success",
                "agent": "competitor_intel",
                "answer": result.get("answer"),
                "sources": result.get("sources"),
                "confidence": result.get("confidence"),
                "key_insights": result.get("key_insights"),
            }
        except Exception as e:
            logger.error(f"Competitor intel error: {e}")
            return {"error": str(e), "agent": "competitor_intel"}

    async def _execute_knowledge_base(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute knowledge base agent for product matching."""
        agent: KnowledgeBaseAgent = self._agents.get(AgentType.KNOWLEDGE_BASE)
        if not agent:
            return {"error": "Knowledge base agent not available"}

        try:
            # KnowledgeBaseAgent has query() method for KB queries
            result = await agent.query(user_request)
            return {
                "status": "success",
                "agent": "knowledge_base",
                "result": result,
            }
        except Exception as e:
            logger.error(f"Knowledge base error: {e}")
            return {"error": str(e), "agent": "knowledge_base"}

    async def _execute_due_diligence(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute due diligence validation."""
        dd_agent: DueDiligenceAgent = self._agents[AgentType.DUE_DILIGENCE]

        customer_id = params.get("customer_id", "")
        if not customer_id:
            return {"error": "Customer ID is required for due diligence"}

        order_value = params.get("order_value", 0.0)
        sales_org = params.get("sales_org", "")

        async with dd_agent:
            result: ValidationResult = await dd_agent.validate_customer(
                customer_id=customer_id,
                sales_org=sales_org,
                order_value=order_value,
            )

        return {
            "success": result.can_proceed,
            "validation_result": result.to_dict(),
            "summary": self._summarize_validation(result),
        }

    def _summarize_validation(self, result: ValidationResult) -> str:
        """Generate human-readable validation summary."""
        status_emoji = {
            ValidationStatus.PASSED: "Passed",
            ValidationStatus.FAILED: "Failed",
            ValidationStatus.WARNING: "Warning",
            ValidationStatus.PENDING_APPROVAL: "Pending Approval",
        }

        lines = [
            f"Customer Validation: {status_emoji.get(result.status, result.status.value)}",
            f"Customer: {result.customer_name} ({result.customer_id})",
            f"Overall Score: {result.overall_score:.0%}",
        ]

        if result.can_proceed:
            lines.append("Status: Can proceed with order")
        else:
            lines.append("Status: Cannot proceed - issues need resolution")

        if result.messages:
            lines.append("\nIssues:")
            for msg in result.messages:
                lines.append(f"  - {msg}")

        if result.required_approvals:
            lines.append(
                f"\nRequired Approvals: {', '.join(result.required_approvals)}"
            )

        return "\n".join(lines)

    # =========================================================================
    # Order Processing Agent Execution Methods (ADR-002)
    # =========================================================================

    async def _execute_opportunity(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute opportunity agent for CEC/IPAS data extraction."""
        agent: OpportunityAgent = self._agents.get(AgentType.OPPORTUNITY)
        if not agent:
            return {"error": "Opportunity agent not available"}

        opportunity_id = params.get("opportunity_id", "")
        account_id = params.get("customer_id", "") or params.get("account_id", "")
        include_ipas = params.get("include_ipas", True)

        if not opportunity_id and not account_id:
            return {
                "error": "Either opportunity_id or customer_id/account_id is required",
                "agent": "opportunity",
            }

        try:
            async with agent:
                if opportunity_id:
                    # Get single opportunity with configurations
                    result = await agent.get_opportunity_with_config(
                        opportunity_id=opportunity_id,
                        include_ipas=include_ipas,
                    )
                    return {
                        "status": "success",
                        "agent": "opportunity",
                        "opportunity": result["opportunity"].to_dict(),
                        "configurations": [
                            {
                                "config_id": cfg.config_id,
                                "product_name": cfg.product_name,
                                "bom_items": cfg.bom_items,
                            }
                            for cfg in result["configurations"]
                        ],
                        "ipas_quote_id": result["ipas_quote_id"],
                        "ready_for_order": result["ready_for_order"],
                    }
                else:
                    # Get all opportunities for account
                    opportunities = await agent.get_opportunities_by_account(account_id)
                    return {
                        "status": "success",
                        "agent": "opportunity",
                        "opportunities": [opp.to_dict() for opp in opportunities],
                        "count": len(opportunities),
                    }
        except Exception as e:
            logger.error(f"Opportunity agent error: {e}")
            return {"error": str(e), "agent": "opportunity"}

    async def _execute_data_management(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute data management agent for MS5 entry assistance."""
        agent: DataManagementAgent = self._agents.get(AgentType.DATA_MANAGEMENT)
        if not agent:
            return {"error": "Data management agent not available"}

        ipas_quote_id = params.get("ipas_quote_id", "") or params.get("config_id", "")
        display_mode = params.get("display_mode", "summary")

        if not ipas_quote_id:
            return {
                "error": "ipas_quote_id or config_id is required",
                "agent": "data_management",
            }

        try:
            async with agent:
                result = await agent.prepare_for_ms5_entry(
                    ipas_quote_id=ipas_quote_id,
                    display_mode=display_mode,
                )
                return {
                    "status": "success",
                    "agent": "data_management",
                    "ipas_data_display": result["ipas_data_display"],
                    "suggested_fields": result["suggested_fields"],
                    "bom_items": result["bom_items"],
                    "validation_status": result["validation_status"],
                    "ready_for_order": result["validation_status"].get(
                        "ready_for_order", False
                    ),
                }
        except Exception as e:
            logger.error(f"Data management agent error: {e}")
            return {"error": str(e), "agent": "data_management"}

    async def _execute_financial_ops(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute financial operations agent for order creation/simulation."""
        agent: FinancialOpsAgent = self._agents.get(AgentType.FINANCIAL_OPS)
        if not agent:
            return {"error": "Financial operations agent not available"}

        customer_id = params.get("customer_id", "")
        if not customer_id:
            return {
                "error": "customer_id is required for financial operations",
                "agent": "financial_ops",
            }

        # Extract order parameters
        order_type = params.get("order_type", "draft")  # draft, simulation, final
        items = params.get("items", [])
        sales_org = params.get("sales_org", "")
        distr_chan = params.get("distr_chan", "")
        division = params.get("division", "")
        opportunity_id = params.get("opportunity_id", "")
        ipas_quote_id = params.get("ipas_quote_id", "")

        # If no items provided but want credit check only
        check_credit_only = params.get("check_credit_only", False)

        try:
            async with agent:
                # Credit check only mode
                if check_credit_only or not items:
                    credit_result = await agent.check_credit(
                        customer_id=customer_id,
                        order_value=params.get("order_value", 0),
                    )
                    return {
                        "status": "success",
                        "agent": "financial_ops",
                        "operation": "credit_check",
                        "credit_check": credit_result,
                        "credit_approved": credit_result.get(
                            "credit_check_passed", False
                        ),
                    }

                # Order simulation
                if order_type == "simulation":
                    result = await agent.simulate_order(
                        customer_id=customer_id,
                        items=items,
                        sales_org=sales_org,
                        distr_chan=distr_chan,
                        division=division,
                        opportunity_id=opportunity_id,
                    )
                    return {
                        "status": "success",
                        "agent": "financial_ops",
                        "operation": "simulation",
                        "simulation_result": result,
                        "is_valid": result.get("is_valid", False),
                    }

                # Draft order creation (default, safest)
                if order_type == "draft":
                    result = await agent.create_draft_order(
                        customer_id=customer_id,
                        items=items,
                        sales_org=sales_org,
                        distr_chan=distr_chan,
                        division=division,
                        opportunity_id=opportunity_id,
                        ipas_quote_id=ipas_quote_id,
                    )
                    return {
                        "status": "success",
                        "agent": "financial_ops",
                        "operation": "draft_order",
                        "order_id": result.get("order_id", ""),
                        "order_status": result.get("order_status", ""),
                        "credit_check": result.get("credit_check", {}),
                        "errors": result.get("errors", []),
                        "warnings": result.get("warnings", []),
                    }

                # Final order (requires explicit config)
                if order_type == "final":
                    try:
                        result = await agent.create_final_order(
                            customer_id=customer_id,
                            items=items,
                            sales_org=sales_org,
                            distr_chan=distr_chan,
                            division=division,
                            opportunity_id=opportunity_id,
                            ipas_quote_id=ipas_quote_id,
                        )
                        return {
                            "status": "success",
                            "agent": "financial_ops",
                            "operation": "final_order",
                            "order_id": result.get("order_id", ""),
                            "order_status": result.get("order_status", ""),
                            "committed": result.get("committed", False),
                        }
                    except RuntimeError as e:
                        # Final orders disabled
                        return {
                            "status": "error",
                            "agent": "financial_ops",
                            "error": str(e),
                            "message": "Final orders are disabled for safety. Use 'draft' or 'simulation' mode.",
                        }

                return {
                    "error": f"Unknown order_type: {order_type}",
                    "agent": "financial_ops",
                }

        except Exception as e:
            logger.error(f"Financial operations agent error: {e}")
            return {"error": str(e), "agent": "financial_ops"}

    async def _execute_entity_resolution(
        self, params: dict[str, Any], user_request: str
    ) -> dict[str, Any]:
        """Execute entity resolution agent for company name matching."""
        agent: EntityResolutionAgent = self._agents.get(AgentType.ENTITY_RESOLUTION)
        if not agent:
            return {"error": "Entity resolution agent not available"}

        entity_name = (
            params.get("entity_name")
            or params.get("company_name")
            or params.get("customer_name")
        )
        country_hint = params.get("country_hint") or params.get("country")

        if not entity_name:
            # Try to extract from user request
            entity_name = user_request

        try:
            # Initialize and resolve
            await agent.initialize()
            result = await agent.resolve_entity(
                entity_name=entity_name,
                country_hint=country_hint,
            )

            # Format response
            exact_match = result.exact_match
            candidates = result.candidates or []

            return {
                "status": "success",
                "agent": "entity_resolution",
                "resolution_status": result.status.value,
                "resolved_entity_id": exact_match.entity_id if exact_match else None,
                "canonical_name": exact_match.canonical_name if exact_match else None,
                "confidence_score": (
                    exact_match.confidence_score if exact_match else 0.0
                ),
                "uen": exact_match.uen if exact_match else None,
                "lei": exact_match.lei if exact_match else None,
                "requires_confirmation": result.requires_confirmation,
                "candidates": [
                    {
                        "entity_id": c.entity_id,
                        "canonical_name": c.canonical_name,
                        "confidence_score": c.confidence_score,
                        "match_type": c.match_type.value if c.match_type else None,
                    }
                    for c in candidates[:5]
                ],
            }
        except Exception as e:
            logger.error(f"Entity resolution agent error: {e}")
            return {"error": str(e), "agent": "entity_resolution"}

    def _update_conversation(
        self,
        user_request: str,
        result: dict[str, Any],
    ) -> None:
        """Update conversation history."""
        self._conversation_history.append(
            {
                "role": "user",
                "content": user_request,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._conversation_history.append(
            {
                "role": "assistant",
                "content": result.get("summary", str(result)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Trim history if too long
        max_history = self.domain_config.max_turns * 2
        if len(self._conversation_history) > max_history:
            self._conversation_history = self._conversation_history[-max_history:]

    def _format_response(
        self,
        task_context: TaskContext,
        result: dict[str, Any],
        interpretation: dict[str, Any],
    ) -> dict[str, Any]:
        """Format the final response."""
        task_context.status = "completed"
        task_context.completed_at = datetime.now(timezone.utc)
        task_context.result = result

        success = result.get("success", False)

        return {
            "type": "answer" if success else "error",  # Required for frontend
            "success": success,
            "task_id": task_context.task_id,
            "task_type": task_context.task_type.value,
            "answer": result.get("summary", interpretation.get("response_to_user", "")),
            "response": result.get(
                "summary", interpretation.get("response_to_user", "")
            ),
            "result": result,
            "confidence": interpretation.get("confidence", "medium"),
        }

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def validate_customer(
        self,
        customer_id: str,
        order_value: float = 0.0,
    ) -> dict[str, Any]:
        """
        Convenience method for customer validation.

        Args:
            customer_id: SAP customer number
            order_value: Proposed order value

        Returns:
            Validation result
        """
        return await self.process_request(
            f"Validate customer {customer_id} for an order of ${order_value:,.2f}",
            context={"customer_id": customer_id, "order_value": order_value},
        )

    async def check_credit(
        self,
        customer_id: str,
        order_value: float,
    ) -> dict[str, Any]:
        """
        Convenience method for credit check.

        Args:
            customer_id: SAP customer number
            order_value: Proposed order value

        Returns:
            Credit check result
        """
        dd_agent: DueDiligenceAgent = self._agents[AgentType.DUE_DILIGENCE]

        async with dd_agent:
            passed, message = await dd_agent.quick_credit_check(
                customer_id=customer_id,
                order_value=order_value,
            )

        return {
            "success": passed,
            "customer_id": customer_id,
            "order_value": order_value,
            "credit_approved": passed,
            "message": message,
        }

    # -------------------------------------------------------------------------
    # A2A Router Compatibility
    # -------------------------------------------------------------------------

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous run method for A2A Router compatibility.

        Handles both direct calls (user_request=) and Pipeline.router calls (task=).

        Args:
            **kwargs: Request parameters (user_request/task, context)

        Returns:
            Processing result
        """
        import asyncio

        # Handle both 'user_request' and 'task' parameters (Pipeline.router uses 'task')
        user_request = kwargs.get("user_request") or kwargs.get("task", "")
        context = kwargs.get("context", {})

        logger.info(f"SalesOpsAgent.run() - request: {user_request[:50]}...")

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Return coroutine for the caller to await
                # This is handled by the registry's _direct_agent_execution
                return self.process_request(user_request, context)
            else:
                return loop.run_until_complete(
                    self.process_request(user_request, context)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.process_request(user_request, context))

    # -------------------------------------------------------------------------
    # A2A Capabilities
    # -------------------------------------------------------------------------

    def _extract_primary_capabilities(self) -> List["Capability"]:
        """Extract primary capabilities for A2A semantic routing.

        Overrides BaseAgent method to provide rich capability descriptions
        for intelligent task routing via Pipeline.router().

        Returns:
            List of Capability objects for A2A matching
        """
        try:
            from kaizen.nodes.ai.a2a import Capability, CapabilityLevel
        except ImportError:
            return []

        return [
            Capability(
                name="sales_orchestration",
                domain="sales",
                level=CapabilityLevel.EXPERT,
                description="Central orchestrator for Lead-to-Cash operations including customer validation, credit checks, and order processing",
                keywords=[
                    "sales",
                    "orchestrator",
                    "lead",
                    "cash",
                    "order",
                    "validate",
                    "process",
                    "request",
                    "coordinate",
                ],
                examples=[
                    "Process customer validation request",
                    "Coordinate sales order workflow",
                    "Handle lead-to-cash operation",
                ],
                constraints=[],
            ),
            Capability(
                name="task_routing",
                domain="orchestration",
                level=CapabilityLevel.EXPERT,
                description="Route tasks to specialized agents (Due Diligence, Opportunity, Financial Ops)",
                keywords=[
                    "route",
                    "delegate",
                    "assign",
                    "task",
                    "agent",
                    "coordination",
                    "workflow",
                ],
                examples=[
                    "Route validation to due diligence agent",
                    "Delegate credit check to financial ops",
                ],
                constraints=[],
            ),
            Capability(
                name="natural_language_processing",
                domain="nlp",
                level=CapabilityLevel.ADVANCED,
                description="Interpret natural language sales requests and extract parameters",
                keywords=[
                    "interpret",
                    "understand",
                    "parse",
                    "request",
                    "natural language",
                    "nlp",
                ],
                examples=[
                    "Understand 'check if customer can place order'",
                    "Parse customer ID from request",
                ],
                constraints=[],
            ),
        ]

    async def health_check(self) -> dict[str, Any]:
        """Check health of all connected systems.

        Returns:
            Health status with agent_id, status, capabilities, and sub-agent health
        """
        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        agent_health = {}
        all_healthy = True

        # Check each agent
        for agent_type, agent in self._agents.items():
            try:
                if hasattr(agent, "health_check"):
                    agent_health[agent_type.value] = await agent.health_check()
                else:
                    agent_health[agent_type.value] = {"status": "available"}
            except Exception as e:
                agent_health[agent_type.value] = {
                    "status": "error",
                    "error": str(e),
                }
                all_healthy = False

        return {
            "agent_id": self.agent_id,
            "status": "healthy" if all_healthy else "degraded",
            "capabilities": capabilities,
            "agents": agent_health,
            "active_tasks": len(self._active_tasks),
            "shared_memory_available": self._shared_memory is not None,
            "control_protocol_available": self._control_protocol is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # Interactive Session Support
    # -------------------------------------------------------------------------

    def interactive_session(self) -> "InteractiveSession":
        """Create an interactive session with human-in-the-loop support."""
        return InteractiveSession(self)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator and all agents."""
        logger.info("Shutting down Sales Ops Orchestrator...")

        # Disconnect all agents
        for agent_type, agent in self._agents.items():
            try:
                if hasattr(agent, "disconnect"):
                    await agent.disconnect()
                logger.info(f"Disconnected {agent_type.value} agent")
            except Exception as e:
                logger.warning(f"Error disconnecting {agent_type.value}: {e}")

        self._agents.clear()
        self._active_tasks.clear()
        logger.info("Sales Ops Orchestrator shutdown complete")


# =============================================================================
# Interactive Session Context Manager
# =============================================================================


class InteractiveSession:
    """
    Interactive session with human-in-the-loop support.

    Provides context manager for interactive agent sessions with
    automatic control protocol setup and cleanup.

    Usage:
        async with agent.interactive_session() as session:
            result = await session.process_with_confirmation(
                "Create order for customer 1234567"
            )
    """

    def __init__(self, orchestrator: SalesOpsAgent):
        """Initialize interactive session."""
        self.orchestrator = orchestrator
        self._transport: Optional[InMemoryTransport] = None
        self._protocol: Optional[ControlProtocol] = None
        self._original_protocol: Optional[ControlProtocol] = None

    async def __aenter__(self) -> "InteractiveSession":
        """Enter interactive session."""
        # Store original protocol
        self._original_protocol = self.orchestrator._control_protocol

        # Create memory transport for testing/programmatic use
        # In production, you'd use CLITransport or HTTPTransport
        self._transport = InMemoryTransport()
        await self._transport.connect()

        self._protocol = ControlProtocol(self._transport)
        await self._protocol.start()

        # Inject protocol into orchestrator
        self.orchestrator._control_protocol = self._protocol

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit interactive session."""
        # Restore original protocol
        self.orchestrator._control_protocol = self._original_protocol

        # Cleanup
        if self._protocol:
            await self._protocol.stop()
        if self._transport:
            await self._transport.disconnect()

    async def process_with_confirmation(
        self,
        request: str,
        auto_approve: bool = False,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Process request with confirmation support.

        Args:
            request: User request
            auto_approve: Automatically approve all confirmations
            context: Optional context data

        Returns:
            Processing result
        """
        if auto_approve and self._transport:
            # Queue auto-approval response
            self._transport.queue_response(True)

        return await self.orchestrator.process_request(request, context)

    def queue_response(self, response: Any) -> None:
        """Queue a response for the next interaction."""
        if self._transport:
            self._transport.queue_response(response)
