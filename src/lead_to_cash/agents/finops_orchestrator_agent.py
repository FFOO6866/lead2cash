"""
Finance Ops Orchestrator Agent

Central orchestrator for FinanceOps users with intelligent A2A routing.

This orchestrator serves financeops role users (like sewsen.goh) and provides:
- Billing & Collections tracking (BillingCollectionsAgent)
- Customer intelligence & KYP (DueDiligenceAgent)
- Knowledge base queries (KnowledgeBaseAgent)
- Customer information (CustomerMatcherAgent)

Architecture:
    - Built on Kaizen BaseAgent with LLM-based intent interpretation
    - Routes queries to specialized domain agents via A2A semantic routing
    - Implements multi-angle analysis (primary + enrichment agents)
    - Maintains session context for multi-turn conversations

Multi-Angle Analysis Rule (MANDATORY):
    For every user query, this orchestrator MUST:
    1. Identify the PRIMARY agent based on intent
    2. Check if ENRICHMENT from other agents is needed
    3. Synthesize results from multiple agents when applicable

Usage:
    from lead_to_cash.agents import FinOpsOrchestratorAgent, FinOpsOrchestratorConfig

    config = FinOpsOrchestratorConfig()
    agent = FinOpsOrchestratorAgent(config)

    # Process user request - intelligent routing
    result = await agent.process_request("Show me overdue invoices")
    result = await agent.process_request("What do we know about CLLS?")  # Routes to KYP + KB
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Optional

from kaizen.core.base_agent import BaseAgent
from kaizen.core.structured_output import create_structured_output_config
from kaizen.signatures import InputField, OutputField, Signature

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from lead_to_cash.agents.billing_collections_agent import (
    BillingCollectionsAgent,
    BillingCollectionsConfig,
)
from lead_to_cash.agents.customer_matcher_agent import (
    CustomerMatcherAgent,
    CustomerMatcherConfig,
)
from lead_to_cash.agents.due_diligence_agent import (
    DueDiligenceAgent,
    DueDiligenceConfig,
)
from lead_to_cash.agents.knowledge_base_agent import (
    KnowledgeBaseAgent,
    KnowledgeBaseConfig,
)
from lead_to_cash.integrations.client_factory import get_cpi_client

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class FinOpsTaskType(str, Enum):
    """Types of tasks the FinOps orchestrator can handle."""

    # Billing/Collections Domain
    BILLING_SUMMARY = "billing_summary"
    BILLING_ITEMS = "billing_items"
    COLLECTIONS_ITEMS = "collections_items"
    AGING_ANALYSIS = "aging_analysis"
    PAYMENT_TERMS = "payment_terms"
    CUSTOMER_AR = "customer_ar"
    ESCALATION = "escalation"
    DOWNPAYMENT_ALERTS = "downpayment_alerts"
    DOWNPAYMENT_OVERDUE = "downpayment_overdue"
    PAYMENT_STATUS = "payment_status"

    # Intelligence Domain (shared with SalesOps)
    CUSTOMER_INTEL = "customer_intel"
    KYP_CHECK = "kyp_check"
    KNOWLEDGE_QUERY = "knowledge_query"

    # General
    GENERAL_QUERY = "general_query"
    UNKNOWN = "unknown"


class FinOpsAgentType(str, Enum):
    """Agent types available to FinOps orchestrator."""

    BILLING_COLLECTIONS = "billing_collections"
    DUE_DILIGENCE = "due_diligence"  # KYP
    KNOWLEDGE_BASE = "knowledge_base"
    CUSTOMER_MATCHER = "customer_matcher"


# =============================================================================
# Signature Definition (LLM-based Intent Interpretation)
# =============================================================================


class FinOpsOrchestratorSignature(Signature):
    """
    Finance Ops Orchestrator - Route queries to billing, collections, and customer intelligence agents.

    You are a Finance Operations assistant for Rolls-Royce Power Systems. Route user queries to the
    appropriate domain agent.

    ROUTING RULES:
    - billing_collections: ONLY for AR/financial data - billing items, collections, invoices, overdue, aging, payment status, escalations, downpayments
    - due_diligence: Company background, news, reputation, risk, compliance, KYP - anything about KNOWING the company
    - knowledge_base: Product information, technical specs, historical data
    - customer_matcher: Customer lookup, SAP customer search

    INTENT-BASED ROUTING (critical distinction):
    - If user wants FINANCIAL/AR data about a customer → billing_collections
    - If user wants to KNOW ABOUT/LEARN ABOUT a customer → due_diligence (KYP)

    The key question: Is the user asking about MONEY (billing/collections/AR) or INFORMATION (company background)?

    TASK TYPE CLASSIFICATION (CRITICAL - choose based on INTENT):

    AR/FINANCIAL INTENT (route to billing_collections):
    - "aging_analysis": aging buckets, aging report, how old are receivables
    - "billing_items": billing, pending invoices, items to bill
    - "collections_items": collections, outstanding, overdue, receivables
    - "billing_summary": summary, dashboard counts
    - "customer_ar": full AR picture for a customer
    - "payment_terms": payment terms, payment schedule
    - "escalation": escalation, escalate, overdue alert, D+1, D+7, D+14, urgent overdue
    - "downpayment_alerts": downpayment, DP, advance payment, deposit, prepayment - any DP needing action
    - "downpayment_overdue": overdue downpayment, overdue DP, overdue advance - specifically overdue DPs
    - "payment_status": payment status, payment progress, how much paid, payment history, what has been paid

    COMPANY KNOWLEDGE INTENT (route to due_diligence):
    - "kyp_check": Learn about company, news, issues, reputation, background, risk
    - "customer_intel": General company information, what do we know about them

    KEY DISTINCTION:
    - "show me ST Engineering billing" → billing_items (asking about MONEY)
    - "tell me about ST Engineering" → kyp_check (asking to KNOW about company)
    - "any issues with ST Engineering" → kyp_check (asking about company background)
    - "ST Engineering collections" → collections_items (asking about MONEY owed)
    - "any downpayments pending?" → downpayment_alerts (asking about DP status)
    - "overdue DPs" → downpayment_overdue (asking about overdue downpayments)
    - "payment status for CLLS" → payment_status (asking about overall payment progress)

    CRITICAL - NEVER ASK FOR CLARIFICATION ABOUT CUSTOMER NAMES:
    Customer entity resolution is handled SEPARATELY by CustomerMatcherAgent.
    Even if you don't recognize the customer name, DO NOT ask for clarification.
    Just route the query to billing_collections and let entity resolution handle it.

    NEVER set clarification_needed for billing/collections/invoice/aging queries.
    """

    # Input Fields
    user_request: str = InputField(
        description="Natural language request from financeops user"
    )
    conversation_history: str = InputField(
        description="Previous conversation context as JSON array. Use this to understand customer context from prior turns.",
        default="[]",
    )
    current_customer_context: str = InputField(
        description="Current customer ID or name in context (from previous turns)",
        default="",
    )

    # Output Fields - Using Literal types for strict enum enforcement
    task_type: Literal[
        "billing_summary",
        "billing_items",
        "collections_items",
        "aging_analysis",
        "payment_terms",
        "customer_ar",
        "escalation",
        "downpayment_alerts",
        "downpayment_overdue",
        "payment_status",
        "customer_intel",
        "kyp_check",
        "knowledge_query",
        "general_query",
        "unknown",
    ] = OutputField(description="The identified task type for this request")

    assigned_agent: Literal[
        "billing_collections",
        "due_diligence",
        "knowledge_base",
        "customer_matcher",
    ] = OutputField(description="Primary agent to handle this request")

    enrichment_agents: str = OutputField(
        description='JSON array of additional agents for enrichment. Example: ["knowledge_base"]. Empty array [] if none.'
    )

    extracted_params: str = OutputField(
        description="JSON object with extracted parameters like status_filter, document_number. Customer resolution is handled separately - do NOT try to extract customer names. Use {} for most queries."
    )

    clarification_needed: str = OutputField(
        description="ALWAYS EMPTY STRING for billing/collections queries. Customer names are resolved separately by CustomerMatcherAgent - do NOT ask for clarification about customer names. Only set clarification if the request type is truly ambiguous (not the customer)."
    )

    response_preview: str = OutputField(
        description="Brief preview of what action will be taken"
    )

    confidence: str = OutputField(description="Confidence: high, medium, low")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class FinOpsOrchestratorConfig:
    """Configuration for FinOps Orchestrator Agent."""

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = os.getenv(
        "OPENAI_PROD_MODEL", "gpt-4o"
    )  # Must use gpt-4o/gpt-4-turbo for JSON response_format support
    temperature: float = 0.5
    max_tokens: int = 2000

    # Agent Settings
    agent_name: str = "finops_orchestrator"
    agent_description: str = (
        "Finance Ops Orchestrator for billing, collections, and customer intelligence"
    )

    # Structured Output - enables strict enum enforcement for agent routing
    use_structured_output: bool = True

    # Connection Settings
    auto_connect: bool = True

    # Provider config (set dynamically for structured outputs)
    provider_config: Optional[Any] = None


# =============================================================================
# FinOps Orchestrator Agent
# =============================================================================


class FinOpsOrchestratorAgent(BaseAgent):
    """
    Finance Ops Orchestrator Agent.

    Provides intelligent A2A routing for financeops users, with access to:
    - BillingCollectionsAgent: AR tracking, billing, collections, aging
    - DueDiligenceAgent: KYP, risk assessment, compliance
    - KnowledgeBaseAgent: Product info, historical data
    - CustomerMatcherAgent: Customer lookup and profiling
    """

    signature = FinOpsOrchestratorSignature

    def __init__(self, config: Optional[FinOpsOrchestratorConfig] = None):
        """Initialize FinOps orchestrator with agent configuration.

        Args:
            config: Agent configuration. BaseAgent will auto-convert these fields.
        """
        self._config = config or FinOpsOrchestratorConfig()

        # Create signature instance
        signature = FinOpsOrchestratorSignature()

        # Enable OpenAI Structured Outputs for guaranteed schema compliance
        # This enforces Literal types so LLM MUST return exact agent names
        if getattr(self._config, "use_structured_output", True):
            try:
                provider_config = create_structured_output_config(
                    signature=signature,
                    strict=True,  # 100% schema compliance - enforces Literal types
                    name="finops_orchestrator_routing",
                )
                self._config.provider_config = provider_config
                logger.info(
                    "Enabled OpenAI Structured Outputs for FinOps routing (strict mode)"
                )
            except Exception as e:
                logger.warning(f"Failed to enable structured outputs: {e}")

        # Initialize BaseAgent with config object
        # BaseAgent expects config=config, not individual parameters
        super().__init__(
            config=self._config,
            signature=signature,
            agent_id=self._config.agent_name,
        )

        # Store config for domain-specific access
        self.domain_config = self._config

        # Agent pool (initialized on connect)
        self._agents: dict[FinOpsAgentType, Any] = {}
        self._cpi_client: Optional[Any] = None
        self._connected = False

        # Session state
        self._conversation_history: list[dict] = []
        self._current_customer: Optional[str] = None
        self._current_customer_name: Optional[str] = None

    # =========================================================================
    # A2A Card (Capabilities)
    # =========================================================================

    @classmethod
    def get_capabilities(cls) -> list["Capability"]:
        """Return A2A capabilities for agent discovery."""
        from kaizen.nodes.ai.a2a import Capability, CapabilityLevel

        return [
            Capability(
                name="finops_orchestration",
                domain="finance_operations",
                level=CapabilityLevel.EXPERT,
                description="Orchestrates Finance Ops queries across billing, collections, and customer intelligence",
                keywords=[
                    "billing",
                    "collections",
                    "AR",
                    "aging",
                    "customer",
                    "payment",
                    "overdue",
                    "invoice",
                ],
            ),
        ]

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def connect(self) -> None:
        """Initialize all sub-agents."""
        if self._connected:
            return

        logger.info("Initializing FinOps orchestrator sub-agents...")

        async def connect_agent(agent: Any, name: str) -> None:
            """Connect an agent using its available lifecycle method."""
            if hasattr(agent, "connect"):
                await agent.connect()
                logger.debug(f"{name} connected via connect()")
            elif hasattr(agent, "__aenter__"):
                await agent.__aenter__()
                logger.debug(f"{name} connected via __aenter__()")
            else:
                # Agent doesn't need explicit connection (stateless)
                logger.debug(f"{name} is stateless, no connection needed")

        try:
            # Initialize BillingCollectionsAgent
            self._agents[FinOpsAgentType.BILLING_COLLECTIONS] = BillingCollectionsAgent(
                config=BillingCollectionsConfig()
            )
            await connect_agent(
                self._agents[FinOpsAgentType.BILLING_COLLECTIONS],
                "BillingCollectionsAgent",
            )

            # Initialize DueDiligenceAgent (KYP)
            self._agents[FinOpsAgentType.DUE_DILIGENCE] = DueDiligenceAgent(
                config=DueDiligenceConfig()
            )
            await connect_agent(
                self._agents[FinOpsAgentType.DUE_DILIGENCE], "DueDiligenceAgent"
            )

            # Initialize KnowledgeBaseAgent
            self._agents[FinOpsAgentType.KNOWLEDGE_BASE] = KnowledgeBaseAgent(
                config=KnowledgeBaseConfig()
            )
            await connect_agent(
                self._agents[FinOpsAgentType.KNOWLEDGE_BASE], "KnowledgeBaseAgent"
            )

            # Initialize CustomerMatcherAgent with real CPI client for SAP customer search
            cpi_client, _is_real = await get_cpi_client(use_case="FinOps")
            self._cpi_client = cpi_client  # Store for cleanup

            self._agents[FinOpsAgentType.CUSTOMER_MATCHER] = CustomerMatcherAgent(
                config=CustomerMatcherConfig(),
                cpi_client=cpi_client,  # Pass CPI client for SAP search (None if unavailable)
            )
            await connect_agent(
                self._agents[FinOpsAgentType.CUSTOMER_MATCHER], "CustomerMatcherAgent"
            )

            self._connected = True
            logger.info("FinOps orchestrator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize FinOps orchestrator: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect all sub-agents and CPI simulator."""
        for agent in self._agents.values():
            if hasattr(agent, "disconnect"):
                await agent.disconnect()
            elif hasattr(agent, "__aexit__"):
                # Async context manager pattern
                await agent.__aexit__(None, None, None)
        self._agents.clear()

        # Clean up CPI simulator
        if self._cpi_client and hasattr(self._cpi_client, "disconnect"):
            await self._cpi_client.disconnect()
            self._cpi_client = None

        self._connected = False

    def is_connected(self) -> bool:
        """Check if agent is connected."""
        return self._connected

    def _ensure_connected(self) -> None:
        """Ensure orchestrator is connected."""
        if not self._connected:
            raise RuntimeError(
                "FinOpsOrchestratorAgent not connected. Call connect() first."
            )

    # =========================================================================
    # Request Processing (LLM-based Intent Interpretation)
    # =========================================================================

    def confirm_entity(
        self,
        customer_id: str,
        customer_name: str,
    ) -> None:
        """
        Confirm an entity selection from user.

        Called when user selects a customer from entity confirmation candidates.

        Args:
            customer_id: SAP customer ID from selected candidate
            customer_name: Customer name from selected candidate
        """
        self._current_customer = customer_id
        self._current_customer_name = customer_name
        logger.info(f"Entity confirmed: {customer_name} (ID: {customer_id})")

    async def process_request(
        self,
        request: str,
        customer_context: Optional[str] = None,
        confirmed_entity: Optional[dict] = None,
        original_task_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process a user request with intelligent A2A routing.

        Args:
            request: Natural language request from user
            customer_context: Optional customer ID from session context
            confirmed_entity: Optional confirmed entity from user selection
                             {"customer_id": ..., "customer_name": ...}
            original_task_type: Optional task type from entity confirmation flow
                               (to avoid re-interpretation after user confirms)

        Returns:
            Response dictionary with formatted output and structured data
        """
        self._ensure_connected()

        # Update session context
        if customer_context:
            self._current_customer = customer_context

        # Handle confirmed entity from user selection
        if confirmed_entity:
            self._current_customer = confirmed_entity.get("customer_id")
            self._current_customer_name = confirmed_entity.get("customer_name")
            logger.info(
                f"Using confirmed entity: {self._current_customer_name} "
                f"(ID: {self._current_customer})"
            )

        try:
            # Step 1: Use LLM to interpret the request (skip if we have original_task_type)
            if original_task_type and confirmed_entity:
                # Use preserved task type from entity confirmation flow
                interpretation = {
                    "task_type": original_task_type,
                    "assigned_agent": "billing_collections",  # Default for billing/collections tasks
                    "enrichment_agents": [],
                    "extracted_params": {},
                }
                logger.info(
                    f"Using preserved task_type from entity confirmation: {original_task_type}"
                )
            else:
                interpretation = await self._interpret_request(request)

            # Step 2: Check if clarification is needed
            if interpretation.get("clarification_needed"):
                return {
                    "success": True,
                    "response": f"I need a bit more information: {interpretation['clarification_needed']}",
                    "data": {},
                    "task_type": "clarification",
                    "clarification_needed": interpretation["clarification_needed"],
                }

            # Step 3: Extract parameters (with type validation on LLM output)
            extracted = interpretation.get("extracted_params", {})
            parsed = (
                json.loads(extracted)
                if isinstance(extracted, str)
                else (extracted or {})
            )
            params = parsed if isinstance(parsed, dict) else {}

            # Step 4: ENTITY RESOLUTION - KYP PATTERN
            # If entity already confirmed from previous selection, use it
            if confirmed_entity and confirmed_entity.get("customer_id"):
                params["customer_id"] = confirmed_entity["customer_id"]
                params["customer_name"] = confirmed_entity.get("customer_name", "")
                self._current_customer = params["customer_id"]
                self._current_customer_name = params.get("customer_name", "")
                logger.info(
                    f"Using confirmed entity: {params['customer_name']} (ID: {params['customer_id']})"
                )

            # If no confirmed entity and no customer_id, use LLM to detect customer
            elif not params.get("customer_id"):
                # KYP PATTERN: Pass ENTIRE user request to CustomerMatcherAgent
                # Let LLM semantically determine if a customer is mentioned
                resolved = await self._resolve_customer_from_request(request)

                if resolved.get("needs_confirmation"):
                    # Multiple candidates or low confidence - ask user to confirm
                    return {
                        "success": True,
                        "response": "I found potential customer matches. Please select the correct one:",
                        "data": {},
                        "task_type": "entity_confirmation",
                        "entity_confirmation_needed": True,
                        "candidates": resolved.get("candidates", []),
                        "query": request,
                        "original_task_type": interpretation["task_type"],
                    }

                if resolved.get("customer_id"):
                    # Auto-confirmed match - use it
                    params["customer_id"] = resolved["customer_id"]
                    params["customer_name"] = resolved.get("customer_name", "")
                    self._current_customer = params["customer_id"]
                    self._current_customer_name = params.get("customer_name", "")
                    logger.info(
                        f"Auto-confirmed entity: {params['customer_name']} (ID: {params['customer_id']})"
                    )

                elif resolved.get("no_customer_mentioned"):
                    # LLM determined no customer is mentioned in request - show all items
                    logger.info(
                        "No customer mentioned in request - will show all items"
                    )

                # else: no matches found, proceed without filter

            # Step 4: Route to primary agent
            assigned = interpretation.get("assigned_agent", "billing_collections")
            task = interpretation.get("task_type", "general_query")
            primary_agent = FinOpsAgentType(assigned)
            task_type = FinOpsTaskType(task)

            primary_result = await self._execute_agent(primary_agent, task_type, params)

            # Step 5: Execute enrichment agents if specified
            enrichment_results = {}
            # Handle both JSON string and list (with type validation on LLM output)
            enrichment_raw = interpretation.get("enrichment_agents", [])
            parsed_enrichment = (
                json.loads(enrichment_raw)
                if isinstance(enrichment_raw, str)
                else (enrichment_raw or [])
            )
            enrichment_agents = (
                parsed_enrichment if isinstance(parsed_enrichment, list) else []
            )
            for agent_name in enrichment_agents:
                try:
                    agent_type = FinOpsAgentType(agent_name)
                    if agent_type != primary_agent:
                        enrichment_result = await self._execute_agent(
                            agent_type, task_type, params
                        )
                        enrichment_results[agent_name] = enrichment_result
                except Exception as e:
                    logger.warning(f"Enrichment from {agent_name} failed: {e}")

            # Step 6: Synthesize response
            response = self._synthesize_response(
                task_type, primary_result, enrichment_results, interpretation
            )

            # Step 7: Update conversation history
            self._update_conversation(request, response)

            return response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            return {
                "success": False,
                "response": "I encountered an error processing your request. Please try again.",
                "data": {},
                "task_type": "error",
            }

    async def _interpret_request(self, request: str) -> dict[str, Any]:
        """
        Use LLM to interpret the user request.

        Returns interpretation with task_type, assigned_agent, and parameters.
        """
        # Build conversation history context
        history_json = json.dumps(self._conversation_history[-10:])

        # Run through signature-based LLM
        result = self.run(
            user_request=request,
            conversation_history=history_json,
            current_customer_context=self._current_customer_name
            or self._current_customer
            or "",
        )

        return result

    async def _resolve_customer_from_request(self, user_request: str) -> dict[str, Any]:
        """
        Resolve customer from user request using LLM-based semantic matching (KYP pattern).

        This follows the EXACT pattern used by KYP/SalesOpsAgent:
        1. Pass the ENTIRE user request to CustomerMatcherAgent
        2. Let CustomerMatcherAgent's LLM semantically understand if a customer is mentioned
        3. Return candidates for confirmation if low confidence, or auto-confirm if high confidence

        Args:
            user_request: The full natural language request from user

        Returns:
            dict with one of:
            - {"customer_id": ..., "customer_name": ...} for auto-confirmed match
            - {"needs_confirmation": True, "candidates": [...]} for user selection
            - {"no_customer_mentioned": True} if LLM determines no customer in request
            - {} if no matches found
        """
        matcher = self._agents.get(FinOpsAgentType.CUSTOMER_MATCHER)
        if not matcher:
            logger.warning("CustomerMatcherAgent not available")
            return {}

        try:
            # KYP PATTERN: Pass entire user request to matcher
            # The CustomerMatcherAgent uses LLM to semantically understand
            # if a customer is being referenced in the request
            result = await matcher.match_customer(user_request)

            # Check if LLM found no customer reference in the request
            if not result or not result.candidates:
                # Check if this is "no customer mentioned" vs "no matches found"
                if (
                    hasattr(result, "no_customer_mentioned")
                    and result.no_customer_mentioned
                ):
                    logger.info(
                        f"LLM determined no customer mentioned in: {user_request}"
                    )
                    return {"no_customer_mentioned": True}
                logger.info(f"No customer matches found for request: {user_request}")
                return {"no_customer_mentioned": True}  # Treat as no customer mentioned

            # Check if user confirmation is needed (like KYP entity resolution)
            if result.requires_user_confirmation:
                # Return candidates for user selection
                candidates = [
                    {
                        "rank": c.rank,
                        "name": c.name,
                        "customer_id": c.customer_id,
                        "confidence_score": c.confidence_score,
                        "source": (
                            c.source.value
                            if hasattr(c.source, "value")
                            else str(c.source)
                        ),
                        "match_reasons": c.match_reasons,
                    }
                    for c in result.candidates[:5]  # Limit to top 5
                ]
                return {
                    "needs_confirmation": True,
                    "candidates": candidates,
                    "query": user_request,
                }

            # Auto-confirmed - use best match
            best_match = result.best_match
            if best_match:
                return {
                    "customer_id": best_match.customer_id,
                    "customer_name": best_match.name,
                }

            return {"no_customer_mentioned": True}

        except Exception as e:
            logger.warning(
                f"Customer resolution from request failed: {e}", exc_info=True
            )
            return {}

    # =========================================================================
    # Agent Execution
    # =========================================================================

    async def _execute_agent(
        self,
        agent_type: FinOpsAgentType,
        task_type: FinOpsTaskType,
        params: dict,
    ) -> dict[str, Any]:
        """Execute a specific agent with the given parameters."""
        agent = self._agents.get(agent_type)
        if not agent:
            return {"error": f"Agent {agent_type.value} not available"}

        try:
            if agent_type == FinOpsAgentType.BILLING_COLLECTIONS:
                return await self._execute_billing_collections(agent, task_type, params)

            elif agent_type == FinOpsAgentType.DUE_DILIGENCE:
                return await self._execute_due_diligence(agent, params)

            elif agent_type == FinOpsAgentType.KNOWLEDGE_BASE:
                return await self._execute_knowledge_base(agent, params)

            elif agent_type == FinOpsAgentType.CUSTOMER_MATCHER:
                return await self._execute_customer_matcher(agent, params)

            return {"error": f"Unknown agent type: {agent_type.value}"}

        except Exception as e:
            logger.error(f"Agent {agent_type.value} execution failed: {e}")
            return {"error": str(e)}

    async def _execute_billing_collections(
        self,
        agent: BillingCollectionsAgent,
        task_type: FinOpsTaskType,
        params: dict,
    ) -> dict[str, Any]:
        """Execute BillingCollectionsAgent based on task type."""
        customer_id = params.get("customer_id")
        status_filter = params.get("status_filter")

        if task_type == FinOpsTaskType.BILLING_SUMMARY:
            summary = await agent.get_billing_summary()
            return {"summary": summary, "type": "billing_summary"}

        elif task_type == FinOpsTaskType.BILLING_ITEMS:
            # BILLING_ITEMS = only items pending invoice (PENDING_BILLING status)
            items = await agent.get_billing_items(
                customer_id=customer_id,
                status=status_filter or "PENDING_BILLING",  # Default to pending billing
            )
            aging = await agent.get_aging_buckets(customer_id=customer_id)
            return {
                "billing_items": items,
                "aging_buckets": aging,
                "type": "billing_items",
                "customer_filtered": bool(customer_id),
            }

        elif task_type == FinOpsTaskType.COLLECTIONS_ITEMS:
            items = await agent.get_collections_items(
                customer_id=customer_id,
                status=status_filter,
            )
            aging = await agent.get_aging_buckets(customer_id=customer_id)
            return {
                "collections_items": items,
                "aging_buckets": aging,
                "type": "collections_items",
                "customer_filtered": bool(customer_id),
            }

        elif task_type == FinOpsTaskType.AGING_ANALYSIS:
            # Get aging buckets - filtered by customer if specified
            aging = await agent.get_aging_buckets(customer_id=customer_id)
            # If customer specified, include their collections items for aging detail
            if customer_id:
                collections = await agent.get_collections_items(customer_id=customer_id)
                return {
                    "collections_items": collections,
                    "aging_buckets": aging,
                    "type": "aging_analysis",
                    "customer_filtered": True,
                }
            return {"aging_buckets": aging, "type": "aging_analysis"}

        elif task_type == FinOpsTaskType.PAYMENT_TERMS:
            if customer_id:
                terms = await agent.get_payment_terms(customer_id)
                return {"payment_terms": terms, "type": "payment_terms"}
            return {"error": "Customer ID required for payment terms"}

        elif task_type == FinOpsTaskType.ESCALATION:
            escalations = await agent.get_escalations(customer_id=customer_id)
            escalation_summary = await agent.get_escalation_summary(
                customer_id=customer_id
            )
            return {
                "escalations": escalations,
                "escalation_summary": escalation_summary,
                "type": "escalation",
                "customer_filtered": bool(customer_id),
            }

        elif task_type == FinOpsTaskType.DOWNPAYMENT_ALERTS:
            dp_alerts = await agent.get_downpayment_alerts(customer_id=customer_id)
            return {
                "downpayment_alerts": dp_alerts,
                "type": "downpayment_alerts",
                "customer_filtered": bool(customer_id),
            }

        elif task_type == FinOpsTaskType.DOWNPAYMENT_OVERDUE:
            overdue_dps = await agent.get_overdue_downpayments(customer_id=customer_id)
            return {
                "overdue_downpayments": overdue_dps,
                "type": "downpayment_overdue",
                "customer_filtered": bool(customer_id),
            }

        elif task_type == FinOpsTaskType.PAYMENT_STATUS:
            payment_status = await agent.get_payment_status(
                customer_id=customer_id,
                sales_order=params.get("sales_order"),
            )
            return {
                "payment_status": payment_status,
                "type": "payment_status",
                "customer_filtered": bool(customer_id),
            }

        elif task_type in [FinOpsTaskType.CUSTOMER_AR, FinOpsTaskType.CUSTOMER_INTEL]:
            # Full AR picture for a customer
            billing = await agent.get_billing_items(customer_id=customer_id)
            collections = await agent.get_collections_items(customer_id=customer_id)
            terms = await agent.get_payment_terms(customer_id) if customer_id else None
            aging = await agent.get_aging_buckets(customer_id=customer_id)
            return {
                "billing_items": billing,
                "collections_items": collections,
                "payment_terms": terms,
                "aging_buckets": aging,
                "type": "customer_ar",
            }

        # Default: return summary
        summary = await agent.get_billing_summary()
        return {"summary": summary, "type": "billing_summary"}

    async def _execute_due_diligence(
        self,
        agent: DueDiligenceAgent,
        params: dict,
    ) -> dict[str, Any]:
        """Execute DueDiligenceAgent for KYP checks."""
        customer_name = params.get("customer_name")
        customer_id = params.get("customer_id")

        if not customer_name and not customer_id:
            return {"error": "Customer name or ID required for KYP check"}

        try:
            # Use customer name for validation
            target = customer_name or customer_id
            result = await agent.validate_customer(target)
            return {"kyp_result": result, "type": "kyp_check"}
        except Exception as e:
            logger.error(f"KYP check failed: {e}")
            return {"error": str(e), "type": "kyp_check"}

    async def _execute_knowledge_base(
        self,
        agent: KnowledgeBaseAgent,
        params: dict,
    ) -> dict[str, Any]:
        """Execute KnowledgeBaseAgent for knowledge queries."""
        customer_name = params.get("customer_name")
        customer_id = params.get("customer_id")

        try:
            # Query knowledge base for customer information
            query = customer_name or customer_id or "general"
            result = await agent.query(query)
            return {"kb_result": result, "type": "knowledge_query"}
        except Exception as e:
            logger.error(f"Knowledge base query failed: {e}")
            return {"error": str(e), "type": "knowledge_query"}

    async def _execute_customer_matcher(
        self,
        agent: CustomerMatcherAgent,
        params: dict,
    ) -> dict[str, Any]:
        """Execute CustomerMatcherAgent for customer lookup."""
        customer_name = params.get("customer_name")

        if not customer_name:
            return {"error": "Customer name required for lookup"}

        try:
            result = await agent.match_customer(customer_name)
            return {"customer_result": result, "type": "customer_match"}
        except Exception as e:
            logger.error(f"Customer matching failed: {e}")
            return {"error": str(e), "type": "customer_match"}

    # =========================================================================
    # Response Synthesis
    # =========================================================================

    def _synthesize_response(
        self,
        task_type: FinOpsTaskType,
        primary_result: dict,
        enrichment_results: dict,
        interpretation: dict,
    ) -> dict[str, Any]:
        """Synthesize a response from primary and enrichment results."""

        # Build response text
        response_parts = []

        # Format primary result
        if primary_result.get("type") == "billing_items":
            items = primary_result.get("billing_items", [])
            response_parts.append(f"Found {len(items)} billing items.")

        elif primary_result.get("type") == "collections_items":
            items = primary_result.get("collections_items", [])
            overdue = [i for i in items if i.get("status") == "OVERDUE"]
            response_parts.append(
                f"Found {len(items)} collection items ({len(overdue)} overdue)."
            )

        elif primary_result.get("type") == "aging_analysis":
            aging = primary_result.get("aging_buckets", {})
            items = primary_result.get("collections_items", [])
            if items:
                response_parts.append(
                    f"Aging analysis for customer: {len(items)} items."
                )
            else:
                # Format aging buckets
                current = aging.get("CURRENT", {}).get("count", 0)
                bucket_0_30 = aging.get("0-30", {}).get("count", 0)
                bucket_30_45 = aging.get("30-45", {}).get("count", 0)
                bucket_45_plus = aging.get("45+", {}).get("count", 0)
                response_parts.append(
                    f"Aging: Current: {current}, 0-30 days: {bucket_0_30}, 30-45 days: {bucket_30_45}, 45+ days: {bucket_45_plus}."
                )

        elif primary_result.get("type") == "billing_summary":
            summary = primary_result.get("summary", {})
            response_parts.append(
                f"Billing: {summary.get('billing_count', 0)} items. "
                f"Collections: {summary.get('collections_count', 0)} items. "
                f"Overdue: {summary.get('overdue_count', 0)} items."
            )

        elif primary_result.get("type") == "escalation":
            escalations = primary_result.get("escalations", [])
            summary = primary_result.get("escalation_summary", {})
            l3 = summary.get("by_level", {}).get("L3", {}).get("count", 0)
            l2 = summary.get("by_level", {}).get("L2", {}).get("count", 0)
            l1 = summary.get("by_level", {}).get("L1", {}).get("count", 0)
            response_parts.append(
                f"Found {len(escalations)} escalations: "
                f"{l3} L3 (Director), {l2} L2 (Ops Lead), {l1} L1 (Sales Manager)."
            )

        elif primary_result.get("type") == "downpayment_alerts":
            dp_alerts = primary_result.get("downpayment_alerts", [])
            pending_billing = [
                d for d in dp_alerts if d.get("status") == "PENDING_BILLING"
            ]
            pending_collection = [
                d for d in dp_alerts if d.get("status") == "PENDING_COLLECTION"
            ]
            overdue = [d for d in dp_alerts if d.get("status") == "OVERDUE"]
            response_parts.append(
                f"Found {len(dp_alerts)} downpayment alerts: "
                f"{len(pending_billing)} to create, "
                f"{len(pending_collection)} awaiting payment, "
                f"{len(overdue)} overdue."
            )

        elif primary_result.get("type") == "downpayment_overdue":
            overdue_dps = primary_result.get("overdue_downpayments", [])
            total_overdue = sum(d.get("total_amount", 0) for d in overdue_dps)
            currencies = list({d.get("currency", "USD") for d in overdue_dps})
            currency = currencies[0] if len(currencies) == 1 else "mixed"
            response_parts.append(
                f"Found {len(overdue_dps)} overdue downpayments "
                f"totalling {currency} {total_overdue:,.2f}."
            )

        elif primary_result.get("type") == "payment_status":
            ps = primary_result.get("payment_status", {})
            summary = ps.get("summary", {})
            response_parts.append(
                f"Payment status: {summary.get('downpayment_count', 0)} downpayments, "
                f"{summary.get('invoice_count', 0)} invoices. "
                f"DP paid: {summary.get('currency', 'USD')} {summary.get('downpayment_paid', 0):,.2f}, "
                f"DP pending: {summary.get('currency', 'USD')} {summary.get('downpayment_pending', 0):,.2f}."
            )

        elif primary_result.get("type") == "kyp_check":
            primary_result.get("kyp_result", {})
            response_parts.append("KYP assessment completed.")

        elif primary_result.get("type") == "customer_ar":
            billing = primary_result.get("billing_items", [])
            collections = primary_result.get("collections_items", [])
            response_parts.append(
                f"Customer has {len(billing)} billing items and "
                f"{len(collections)} collection items."
            )

        # Add enrichment summaries
        if FinOpsAgentType.DUE_DILIGENCE.value in enrichment_results:
            response_parts.append("KYP intelligence included.")

        if FinOpsAgentType.KNOWLEDGE_BASE.value in enrichment_results:
            response_parts.append("Knowledge base information included.")

        # Build final response
        response_text = (
            " ".join(response_parts) if response_parts else "Request processed."
        )

        return {
            "success": True,
            "response": response_text,
            "data": {
                **primary_result,
                "enrichment": enrichment_results,
            },
            "task_type": task_type.value,
            "confidence": interpretation.get("confidence", "medium"),
        }

    def _update_conversation(self, request: str, response: dict) -> None:
        """Update conversation history for context."""
        self._conversation_history.append(
            {
                "role": "user",
                "content": request,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._conversation_history.append(
            {
                "role": "assistant",
                "content": response.get("response", ""),
                "task_type": response.get("task_type", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Keep only last 20 turns
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]


# =============================================================================
# Factory Function
# =============================================================================


async def create_finops_orchestrator_agent(
    config: Optional[FinOpsOrchestratorConfig] = None,
) -> FinOpsOrchestratorAgent:
    """
    Factory function to create and initialize a FinOps Orchestrator Agent.

    Args:
        config: Optional configuration for the orchestrator

    Returns:
        Initialized FinOpsOrchestratorAgent ready for use
    """
    agent = FinOpsOrchestratorAgent(config)
    await agent.connect()
    return agent
