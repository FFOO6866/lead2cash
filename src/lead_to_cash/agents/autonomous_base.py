"""
Autonomous Agent Base Class

This module provides the foundation for truly autonomous agents using
Kaizen A2A framework patterns.

Key Features:
- 7 extension points for customization
- Autonomous tool selection (not hardcoded pipelines)
- Convergence detection via tool_calls field
- Typed response generation
- A2A communication capability

Extension Points:
1. _default_signature() - Define agent capabilities
2. _generate_system_prompt() - LLM instructions for autonomy
3. _select_tools() - Override for custom tool selection
4. _check_convergence() - Override for custom convergence logic
5. _pre_execution_hook() - Called before each cycle
6. _post_execution_hook() - Called after each cycle
7. _handle_error() - Error recovery strategies

Usage:
    from lead_to_cash.agents.autonomous_base import AutonomousAgent, AutonomousConfig
    from lead_to_cash.agents.signatures import MarineIntelSignature

    class MyAutonomousAgent(AutonomousAgent):
        def __init__(self, config: AutonomousConfig):
            super().__init__(
                agent_id="my_agent",
                config=config,
                signature_class=MarineIntelSignature,
            )

        def _generate_system_prompt(self) -> str:
            return "You are an autonomous agent..."

        async def _execute_cycle(self, inputs: dict) -> dict:
            # Your agent logic here
            return {"answer": "...", "tool_calls": []}

    # Execute autonomously
    agent = MyAutonomousAgent(config)
    response = await agent.execute("Find ferry contracts in APAC", session_id="abc123")
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional, Type

from lead_to_cash.agents.contracts import (
    AgentResponse,
    ConfidenceLevel,
)
from lead_to_cash.agents.signatures import AgentSignature

logger = logging.getLogger(__name__)


@dataclass
class AutonomousConfig:
    """
    Configuration for autonomous agents.

    Attributes:
        max_cycles: Maximum execution cycles before forced stop
        checkpoint_frequency: How often to checkpoint state
        enable_interrupts: Whether to handle interrupts gracefully
        graceful_shutdown_timeout: Timeout for graceful shutdown (seconds)
        tool_approval_required: Whether dangerous tools need approval
        dangerous_tools: List of tools that require approval
        llm_provider: LLM provider (openai, anthropic)
        model: Model name
        temperature: LLM temperature
    """

    max_cycles: int = 20
    checkpoint_frequency: int = 5
    enable_interrupts: bool = True
    graceful_shutdown_timeout: float = 5.0

    # Tool configuration
    tool_approval_required: bool = False
    dangerous_tools: list[str] = field(default_factory=list)

    # LLM configuration
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_BASE_MODEL", "gpt-4")
    temperature: float = 0.7

    # Logging
    log_cycles: bool = True
    log_tool_calls: bool = True


@dataclass
class ExecutionState:
    """
    State tracking for autonomous execution.

    Tracks cycles, tool calls, and intermediate results.
    """

    current_cycle: int = 0
    converged: bool = False
    tool_results: list[dict] = field(default_factory=list)
    cycle_history: list[dict] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def elapsed_ms(self) -> int:
        """Calculate elapsed time in milliseconds."""
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now(UTC)
        return int((end - self.started_at).total_seconds() * 1000)


class AutonomousAgent(ABC):
    """
    Base class for truly autonomous agents.

    Implements the Kaizen A2A pattern with:
    - Signature-based capability declaration
    - Autonomous tool selection (not hardcoded pipelines)
    - Convergence detection via tool_calls field
    - A2A communication capability
    - Typed response generation

    Subclasses MUST implement:
    - _generate_system_prompt(): Define agent personality
    - _execute_cycle(): Core execution logic
    - _call_tool(): Tool execution
    - _build_response(): Response formatting
    """

    def __init__(
        self,
        agent_id: str,
        config: AutonomousConfig,
        signature_class: Type[AgentSignature],
    ):
        """
        Initialize autonomous agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Autonomous execution configuration
            signature_class: The signature class defining capabilities
        """
        self.agent_id = agent_id
        self.config = config
        self.signature_class = signature_class
        self.signature = signature_class()

        # Execution state (reset on each execute call)
        self._state: Optional[ExecutionState] = None

        # Tool catalog (populated by subclass or discovery)
        self._available_tools: dict[str, dict] = {}

        # A2A communication (to be set by registry)
        self._message_bus: Optional[Any] = None

        # Registry reference for agent-to-agent communication
        self._registry: Optional[Any] = None

        logger.info(
            f"[{self.agent_id}] Initialized with signature {signature_class.__name__}"
        )

    # =========================================================================
    # Extension Point 1: Default Signature
    # =========================================================================
    def _default_signature(self) -> AgentSignature:
        """
        Return the agent's capability signature.

        Override to return a different signature dynamically.
        """
        return self.signature

    # =========================================================================
    # Extension Point 2: System Prompt Generation
    # =========================================================================
    @abstractmethod
    def _generate_system_prompt(self) -> str:
        """
        Generate system prompt for autonomous behavior.

        Subclasses MUST implement this to define:
        - Agent personality and role
        - Decision-making instructions
        - Tool usage guidelines
        - Convergence criteria

        Example:
            return '''You are an autonomous market intelligence agent.
            Your job is to find and analyze market opportunities.

            TOOLS AVAILABLE:
            - local_vectordb: Search local database
            - perplexity: Real-time web search
            - sap_mcp: Customer lookup

            CONVERGENCE:
            Return tool_calls=[] when you have sufficient data to answer.
            Keep calling tools until you have high confidence.
            '''
        """
        pass

    # =========================================================================
    # Extension Point 3: Tool Selection Strategy
    # =========================================================================
    def _select_tools(self, task: str, context: dict) -> list[str]:
        """
        Autonomously select tools based on task requirements.

        Override this to implement custom tool selection logic.
        Default: Return empty list - LLM will decide via tool_calls.

        Args:
            task: The task to perform
            context: Current execution context

        Returns:
            List of tool names to use (or empty for LLM-driven selection)
        """
        # Default: Let LLM decide via tool_calls in response
        return []

    # =========================================================================
    # Extension Point 4: Convergence Detection
    # =========================================================================
    def _check_convergence(self, result: dict) -> bool:
        """
        Check if agent has completed its task.

        Default: Check if tool_calls field is empty.
        Override for custom convergence logic.

        Args:
            result: Result from last execution cycle

        Returns:
            True if agent has converged (task complete)
        """
        tool_calls = result.get("tool_calls", [])

        # Empty or None means converged
        if tool_calls is None or tool_calls == []:
            return True

        # Also check for explicit convergence signal
        if result.get("converged", False):
            return True

        return False

    # =========================================================================
    # Extension Point 5: Pre-execution Hook
    # =========================================================================
    def _pre_execution_hook(self, inputs: dict) -> dict:
        """
        Called before each execution cycle.

        Use for:
        - Loading context
        - Checking permissions
        - Validating inputs
        - Setting up cycle-specific state

        Args:
            inputs: Current inputs for the cycle

        Returns:
            Modified inputs (or original if no changes)
        """
        if self._state:
            self._state.current_cycle += 1

            if self.config.log_cycles:
                logger.info(
                    f"[{self.agent_id}] Starting cycle {self._state.current_cycle}"
                )

        return inputs

    # =========================================================================
    # Extension Point 6: Post-execution Hook
    # =========================================================================
    def _post_execution_hook(self, result: dict) -> dict:
        """
        Called after each execution cycle.

        Use for:
        - Logging results
        - Updating state
        - Checkpointing
        - Triggering callbacks

        Args:
            result: Result from the execution cycle

        Returns:
            Modified result (or original if no changes)
        """
        if self._state:
            # Record cycle in history
            self._state.cycle_history.append(
                {
                    "cycle": self._state.current_cycle,
                    "tool_calls": result.get("tool_calls", []),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            # Checkpoint if needed
            if self._state.current_cycle % self.config.checkpoint_frequency == 0:
                self._checkpoint()

        return result

    # =========================================================================
    # Extension Point 7: Error Handling
    # =========================================================================
    def _handle_error(self, error: Exception, session_id: str) -> AgentResponse:
        """
        Handle execution errors.

        Override for custom error recovery strategies.

        Args:
            error: The exception that occurred
            session_id: Current session ID

        Returns:
            Error response
        """
        logger.error(f"[{self.agent_id}] Error: {error}")

        if self._state:
            self._state.error = str(error)
            self._state.completed_at = datetime.now(UTC)

        return AgentResponse.create_error(
            session_id=session_id,
            error=str(error),
        )

    # =========================================================================
    # Core Execution Loop
    # =========================================================================
    async def execute(
        self,
        task: str,
        session_id: str,
        context: Optional[dict] = None,
    ) -> AgentResponse:
        """
        Execute task autonomously.

        This is the main entry point. The agent will:
        1. Initialize execution state
        2. Execute cycles until convergence or max_cycles
        3. Execute tool calls between cycles
        4. Return typed response

        Args:
            task: The task to perform
            session_id: Session ID for response
            context: Optional additional context

        Returns:
            Typed AgentResponse
        """
        context = context or {}

        # Initialize execution state
        self._state = ExecutionState(
            started_at=datetime.now(UTC),
        )

        try:
            # Build initial inputs
            inputs = {
                "task": task,
                "system_prompt": self._generate_system_prompt(),
                "tool_catalog": self._get_tool_catalog(),
                **context,
            }

            # Validate inputs against signature
            validation_errors = self.signature_class.validate_inputs(
                {"query": task, **context}
            )
            if validation_errors:
                logger.warning(
                    f"[{self.agent_id}] Input validation warnings: {validation_errors}"
                )

            # Autonomous execution loop
            result = {}
            while (
                not self._state.converged
                and self._state.current_cycle < self.config.max_cycles
            ):
                # Pre-execution hook
                inputs = self._pre_execution_hook(inputs)

                # Execute one cycle
                result = await self._execute_cycle(inputs)

                # Post-execution hook
                result = self._post_execution_hook(result)

                # Check convergence
                self._state.converged = self._check_convergence(result)

                if not self._state.converged:
                    # Execute tool calls
                    tool_calls = result.get("tool_calls", [])
                    if tool_calls:
                        tool_results = await self._execute_tool_calls(tool_calls)
                        self._state.tool_results.extend(tool_results)

                        # Update inputs with tool results for next cycle
                        inputs["tool_results"] = self._state.tool_results
                        inputs["previous_result"] = result

            # Mark completion
            self._state.completed_at = datetime.now(UTC)

            # Log convergence status
            if self._state.converged:
                logger.info(
                    f"[{self.agent_id}] Converged after {self._state.current_cycle} cycles"
                )
            else:
                logger.warning(
                    f"[{self.agent_id}] Hit max_cycles ({self.config.max_cycles}) without convergence"
                )

            # Build final response
            return self._build_response(result, session_id)

        except Exception as e:
            return self._handle_error(e, session_id)

    @abstractmethod
    async def _execute_cycle(self, inputs: dict) -> dict:
        """
        Execute one cycle of autonomous processing.

        Subclasses MUST implement this to define their core logic.

        Args:
            inputs: Current inputs including task, tool_results, etc.

        Returns:
            Dict with at minimum: {"tool_calls": [...]}
            When tool_calls is empty, agent has converged.
        """
        pass

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """
        Execute tool calls and return results.

        Args:
            tool_calls: List of tool calls from last cycle

        Returns:
            List of tool results
        """
        results = []

        for call in tool_calls:
            tool_name = call.get("tool") or call.get("name")
            params = call.get("params") or call.get("arguments", {})

            if self.config.log_tool_calls:
                logger.info(f"[{self.agent_id}] Executing tool: {tool_name}")

            # Check if tool requires approval
            if (
                self.config.tool_approval_required
                and tool_name in self.config.dangerous_tools
            ):
                logger.warning(
                    f"[{self.agent_id}] Tool {tool_name} requires approval (skipped)"
                )
                results.append(
                    {
                        "tool": tool_name,
                        "params": params,
                        "result": {"error": "Tool requires approval"},
                        "status": "approval_required",
                    }
                )
                continue

            try:
                result = await self._call_tool(tool_name, params)
                results.append(
                    {
                        "tool": tool_name,
                        "params": params,
                        "result": result,
                        "status": "success",
                    }
                )
            except Exception as e:
                logger.error(f"[{self.agent_id}] Tool {tool_name} failed: {e}")
                results.append(
                    {
                        "tool": tool_name,
                        "params": params,
                        "result": {"error": str(e)},
                        "status": "error",
                    }
                )

        return results

    @abstractmethod
    async def _call_tool(self, tool_name: str, params: dict) -> dict:
        """
        Call a specific tool.

        Subclasses implement this to connect to actual tool implementations.

        Args:
            tool_name: Name of the tool to call
            params: Parameters for the tool

        Returns:
            Tool execution result
        """
        pass

    @abstractmethod
    def _build_response(self, result: dict, session_id: str) -> AgentResponse:
        """
        Build typed response from execution result.

        Subclasses implement this to format their specific response type.

        Args:
            result: Final execution result
            session_id: Session ID for response

        Returns:
            Typed AgentResponse
        """
        pass

    # =========================================================================
    # Tool Catalog
    # =========================================================================
    def register_tool(self, name: str, description: str, capabilities: list[str]):
        """
        Register a tool in the agent's catalog.

        Args:
            name: Tool name
            description: Tool description
            capabilities: What the tool can do
        """
        self._available_tools[name] = {
            "name": name,
            "description": description,
            "capabilities": capabilities,
        }

    def _get_tool_catalog(self) -> list[dict]:
        """Get the tool catalog for LLM context."""
        return list(self._available_tools.values())

    # =========================================================================
    # Checkpointing
    # =========================================================================
    def _checkpoint(self):
        """
        Checkpoint current state.

        Override to implement persistent checkpointing.
        """
        if self._state:
            logger.debug(
                f"[{self.agent_id}] Checkpoint at cycle {self._state.current_cycle}"
            )

    # =========================================================================
    # A2A Capability Card
    # =========================================================================
    def to_a2a_card(self) -> dict:
        """
        Generate A2A capability card for semantic matching.

        Returns:
            Dictionary with agent metadata for A2A registration
        """
        card = self.signature_class.to_a2a_card()
        card["agent_id"] = self.agent_id
        card["status"] = "active"
        card["tools"] = list(self._available_tools.keys())
        return card

    # =========================================================================
    # A2A Communication
    # =========================================================================
    def set_message_bus(self, message_bus: Any) -> None:
        """Set the A2A message bus for inter-agent communication."""
        self._message_bus = message_bus

    def set_registry(self, registry: Any) -> None:
        """
        Set the agent registry for A2A communication.

        The registry enables agents to find and communicate with other agents
        based on their capabilities.

        Args:
            registry: AgentRegistry instance for agent discovery
        """
        self._registry = registry
        logger.debug(f"[{self.agent_id}] Registry set for A2A communication")

    async def request_enrichment(self, capability: str, data: dict) -> Optional[dict]:
        """
        Request enrichment from another agent with matching capability.

        This enables agent-to-agent collaboration by finding an agent with
        the requested capability and delegating work to it.

        Args:
            capability: Capability needed (e.g., "customer_validation",
                       "competitor_analysis", "sanctions_screening")
            data: Data to send to the enrichment agent. Should include:
                  - task: Description of what to do (used for routing)
                  - Any domain-specific parameters

        Returns:
            Enrichment result dict or None if no agent available

        Example:
            # Request customer validation from DueDiligenceAgent
            result = await self.request_enrichment(
                capability="customer_validation",
                data={"task": "Validate customer", "customer_id": "1234567"}
            )
        """
        # Try registry first (preferred method)
        if self._registry:
            return await self._request_via_registry(capability, data)

        # Fall back to message bus if available
        if self._message_bus:
            logger.info(
                f"[{self.agent_id}] Requesting enrichment via message bus: {capability}"
            )
            # Message bus implementation would go here
            return None

        logger.warning(
            f"[{self.agent_id}] No registry or message bus configured for A2A communication"
        )
        return None

    async def _request_via_registry(
        self, capability: str, data: dict
    ) -> Optional[dict]:
        """
        Request enrichment using the agent registry.

        Args:
            capability: Capability needed
            data: Data to send to the enrichment agent

        Returns:
            Enrichment result or None
        """
        logger.info(f"[{self.agent_id}] Requesting enrichment: {capability}")

        # Find agent with matching capability
        matched_agent = self._registry.get_agent_for_capability(capability)

        if not matched_agent:
            logger.info(
                f"[{self.agent_id}] No agent found for capability: {capability}"
            )
            return None

        matched_agent_id = getattr(matched_agent, "agent_id", "unknown")
        logger.info(
            f"[{self.agent_id}] Found agent for {capability}: {matched_agent_id}"
        )

        # Execute enrichment request
        try:
            # Use run() method which all agents should have
            if hasattr(matched_agent, "run"):
                result = matched_agent.run(task=data.get("task", ""), **data)

                # Handle async result
                if asyncio.iscoroutine(result):
                    result = await result

                # Ensure result is a dict
                if not isinstance(result, dict):
                    result = {"result": result}

                logger.info(
                    f"[{self.agent_id}] Enrichment from {matched_agent_id}: "
                    f"success={result.get('success', 'unknown')}"
                )
                return result
            else:
                logger.warning(
                    f"[{self.agent_id}] Agent {matched_agent_id} has no run() method"
                )
                return None

        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Enrichment request to {matched_agent_id} failed: {e}"
            )
            return None

    # =========================================================================
    # Properties
    # =========================================================================
    @property
    def cycles_used(self) -> int:
        """Get number of cycles used in current/last execution."""
        return self._state.current_cycle if self._state else 0

    @property
    def execution_time_ms(self) -> int:
        """Get execution time in milliseconds."""
        return self._state.elapsed_ms() if self._state else 0

    @property
    def is_converged(self) -> bool:
        """Check if agent converged in last execution."""
        return self._state.converged if self._state else False

    @property
    def tool_results(self) -> list[dict]:
        """Get tool results from current/last execution."""
        return self._state.tool_results if self._state else []


# =============================================================================
# Helper: Simple Autonomous Agent
# =============================================================================


class SimpleAutonomousAgent(AutonomousAgent):
    """
    Simplified autonomous agent for straightforward use cases.

    Provides default implementations for common patterns.
    Subclasses only need to implement _process_task().
    """

    def __init__(
        self,
        agent_id: str,
        config: AutonomousConfig,
        signature_class: Type[AgentSignature],
        system_prompt: str,
    ):
        super().__init__(agent_id, config, signature_class)
        self._system_prompt = system_prompt

    def _generate_system_prompt(self) -> str:
        return self._system_prompt

    async def _execute_cycle(self, inputs: dict) -> dict:
        """
        Execute cycle by calling _process_task.

        Override _process_task for your logic.
        """
        task = inputs.get("task", "")
        tool_results = inputs.get("tool_results", [])

        return await self._process_task(task, tool_results, inputs)

    async def _process_task(
        self, task: str, tool_results: list[dict], context: dict
    ) -> dict:
        """
        Process the task and return result.

        Override this in subclasses.

        Returns:
            Dict with "answer" and "tool_calls" (empty when done)
        """
        # Default: Single cycle, no tool calls
        return {
            "answer": f"Processed: {task}",
            "tool_calls": [],
        }

    async def _call_tool(self, tool_name: str, params: dict) -> dict:
        """Default tool calling (override for real tools)."""
        return {"error": f"Tool {tool_name} not implemented"}

    def _build_response(self, result: dict, session_id: str) -> AgentResponse:
        """Build answer response from result."""
        return AgentResponse.create_answer(
            session_id=session_id,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            confidence=ConfidenceLevel.MEDIUM,
            tools_used=[r["tool"] for r in self.tool_results],
            execution_time_ms=self.execution_time_ms,
        )
