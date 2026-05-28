"""
Opportunity Agent

Kaizen-based AI agent for extracting opportunity data from SAP CEC
and product configurations from IPAS for Lead-to-Cash processing.

Part of the Order Processing Domain (ADR-002).

Capabilities:
    - Read opportunities from SAP CEC (Sales Cloud)
    - Extract product configurations from IPAS (XML)
    - Link opportunities to product configurations
    - Prepare data for MS5 order creation

Architecture:
    OpportunityAgent → CECClient → CPI → SAP CEC
    OpportunityAgent → IPASClient → CPI → IPAS

Usage:
    from lead_to_cash.agents import OpportunityAgent, OpportunityConfig

    config = OpportunityConfig()
    agent = OpportunityAgent(config)

    # Get opportunity with configurations
    result = await agent.get_opportunity_with_config("OPP-12345")
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import OpportunitySignature
from lead_to_cash.integrations.cec_client import CECClient, Opportunity
from lead_to_cash.integrations.ipas_client import IPASClient, ProductConfiguration

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class OpportunityConfig:
    """Configuration for OpportunityAgent."""

    # Connection settings
    cpi_timeout_seconds: int = 30

    # Simulation mode - use CPISimulator for development/testing
    simulation_mode: bool = False

    # Processing settings
    include_ipas_by_default: bool = True
    max_configurations_per_opportunity: int = 10

    # LLM settings (for future enhancement)
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.0
    max_tokens: int = 4096

    # Agent metadata
    agent_name: str = "OpportunityAgent"
    agent_version: str = "1.0.0"


# =============================================================================
# Internal Kaizen Signature (for BaseAgent compatibility)
# =============================================================================


class OpportunityAgentSignature(Signature):
    """Internal Kaizen signature for BaseAgent compatibility."""

    # Inputs
    opportunity_id: str = InputField(
        description="CEC opportunity ID to retrieve",
        default="",
    )
    account_id: str = InputField(
        description="SAP customer ID to get all opportunities",
        default="",
    )
    include_ipas: bool = InputField(
        description="Whether to include IPAS product configurations",
        default=True,
    )

    # Outputs
    opportunities: list = OutputField(
        description="Retrieved opportunities with product data",
        default_factory=list,
    )
    product_configurations: list = OutputField(
        description="IPAS product configurations",
        default_factory=list,
    )
    ipas_quote_id: str = OutputField(
        description="Primary IPAS quote ID",
        default="",
    )
    tool_calls: list = OutputField(
        description="Tool calls for convergence detection",
        default_factory=list,
    )


# =============================================================================
# Agent Implementation
# =============================================================================


class OpportunityAgent(BaseAgent):
    """
    Opportunity Agent for CEC and IPAS data extraction.

    Part of the Order Processing Domain (ADR-002).

    This agent extracts opportunity data from SAP CEC and enriches it
    with product configurations from IPAS for downstream processing
    by DataManagementAgent and FinancialOpsAgent.
    """

    # Class-level signature reference for A2A capability matching
    SIGNATURE = OpportunitySignature

    def __init__(self, config: Optional[OpportunityConfig] = None):
        """Initialize OpportunityAgent.

        Args:
            config: Agent configuration. Defaults to OpportunityConfig().
        """
        self.domain_config = config or OpportunityConfig()

        super().__init__(
            config=self.domain_config,
            signature=OpportunityAgentSignature(),
        )

        # Initialize clients (lazy connection)
        self._cec_client: Optional[CECClient] = None
        self._ipas_client: Optional[IPASClient] = None
        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connections to CEC and IPAS via CPI.

        When simulation_mode is enabled, uses CPISimulator instead of real CPI
        to allow development and testing without SAP credentials.
        """
        if self._connected:
            return

        simulation_mode = self.domain_config.simulation_mode
        self._cec_client = CECClient(simulation_mode=simulation_mode)
        self._ipas_client = IPASClient(simulation_mode=simulation_mode)

        await self._cec_client.connect()
        await self._ipas_client.connect()

        self._connected = True
        mode_str = " (simulation mode)" if simulation_mode else ""
        logger.info(f"OpportunityAgent connected to CEC and IPAS{mode_str}")

    async def disconnect(self) -> None:
        """Close connections."""
        if self._cec_client:
            await self._cec_client.disconnect()
        if self._ipas_client:
            await self._ipas_client.disconnect()

        self._connected = False
        logger.info("OpportunityAgent disconnected")

    async def __aenter__(self) -> "OpportunityAgent":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    def _ensure_connected(self) -> None:
        """Ensure agent is connected."""
        if not self._connected:
            raise RuntimeError(
                "OpportunityAgent not connected. Use async context manager or call connect()."
            )

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def get_opportunity(self, opportunity_id: str) -> Opportunity:
        """Get a single opportunity by ID.

        Args:
            opportunity_id: CEC opportunity ID

        Returns:
            Opportunity data from CEC
        """
        self._ensure_connected()
        return await self._cec_client.get_opportunity(opportunity_id)

    async def get_opportunities_by_account(
        self, account_id: str, status: Optional[str] = None
    ) -> list[Opportunity]:
        """Get all opportunities for an account.

        Args:
            account_id: SAP customer ID (10-digit)
            status: Optional filter (Open, Won, Lost, Qualified)

        Returns:
            List of opportunities
        """
        self._ensure_connected()
        return await self._cec_client.get_opportunities_by_account(
            account_id=account_id, status=status
        )

    async def get_product_configurations(
        self, opportunity_id: str
    ) -> list[ProductConfiguration]:
        """Get IPAS product configurations for an opportunity.

        Args:
            opportunity_id: CEC opportunity ID

        Returns:
            List of product configurations from IPAS
        """
        self._ensure_connected()
        return await self._ipas_client.get_configuration_by_opportunity(opportunity_id)

    async def get_opportunity_with_config(
        self,
        opportunity_id: str,
        include_ipas: bool = True,
    ) -> dict[str, Any]:
        """Get opportunity with product configurations.

        This is the primary method for Order Processing domain.
        Retrieves CEC opportunity data and enriches with IPAS configurations.

        Args:
            opportunity_id: CEC opportunity ID
            include_ipas: Whether to include IPAS configurations

        Returns:
            Dictionary with opportunity and configurations:
            {
                "opportunity": Opportunity,
                "configurations": list[ProductConfiguration],
                "ipas_quote_id": str,
                "ready_for_order": bool,
            }
        """
        self._ensure_connected()

        # Get opportunity from CEC
        opportunity = await self._cec_client.get_opportunity(opportunity_id)

        # Get IPAS configurations if requested
        configurations = []
        ipas_quote_id = opportunity.ipas_quote_id or ""

        if include_ipas:
            try:
                configurations = (
                    await self._ipas_client.get_configuration_by_opportunity(
                        opportunity_id
                    )
                )
                # Extract quote ID from first configuration if not already set
                if not ipas_quote_id and configurations:
                    ipas_quote_id = configurations[0].config_id
            except Exception as e:
                logger.warning(f"Failed to get IPAS configurations: {e}")

        # Determine if ready for order creation
        ready_for_order = bool(
            opportunity.status in ("Won", "Qualified")
            and opportunity.account_id
            and (configurations or not include_ipas)
        )

        return {
            "opportunity": opportunity,
            "configurations": configurations,
            "ipas_quote_id": ipas_quote_id,
            "ready_for_order": ready_for_order,
        }

    # =========================================================================
    # BaseAgent Implementation
    # =========================================================================

    async def _execute(self, **kwargs) -> dict[str, Any]:
        """Execute agent with signature-based inputs.

        This method is called by BaseAgent.run() with validated inputs.

        Args:
            **kwargs: Inputs matching OpportunityAgentSignature

        Returns:
            Dictionary matching OpportunitySignature output fields
        """
        opportunity_id = kwargs.get("opportunity_id", "")
        account_id = kwargs.get("account_id", "")
        include_ipas = kwargs.get("include_ipas", self.config.include_ipas_by_default)

        # Track tool calls for convergence
        tool_calls = []

        opportunities = []
        configurations = []
        ipas_quote_id = ""

        try:
            await self.connect()

            if opportunity_id:
                # Get single opportunity with configurations
                result = await self.get_opportunity_with_config(
                    opportunity_id=opportunity_id,
                    include_ipas=include_ipas,
                )
                opportunities = [result["opportunity"].to_dict()]
                configurations = [
                    self._config_to_dict(cfg) for cfg in result["configurations"]
                ]
                ipas_quote_id = result["ipas_quote_id"]

                tool_calls.append(
                    {"tool": "cec_client", "action": "get_opportunity", "success": True}
                )
                if include_ipas:
                    tool_calls.append(
                        {
                            "tool": "ipas_client",
                            "action": "get_configurations",
                            "success": True,
                        }
                    )

            elif account_id:
                # Get all opportunities for account
                opps = await self.get_opportunities_by_account(account_id)
                opportunities = [opp.to_dict() for opp in opps]

                tool_calls.append(
                    {
                        "tool": "cec_client",
                        "action": "get_by_account",
                        "success": True,
                        "count": len(opps),
                    }
                )

                # Get configurations for each opportunity if requested
                if include_ipas and opps:
                    for opp in opps[: self.config.max_configurations_per_opportunity]:
                        try:
                            configs = await self.get_product_configurations(
                                opp.opportunity_id
                            )
                            configurations.extend(
                                [self._config_to_dict(cfg) for cfg in configs]
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to get configs for {opp.opportunity_id}: {e}"
                            )

            else:
                logger.warning("No opportunity_id or account_id provided")
                tool_calls.append(
                    {"tool": "validation", "action": "check_inputs", "success": False}
                )

        except Exception as e:
            logger.error(f"OpportunityAgent execution error: {e}")
            tool_calls.append({"tool": "error", "message": str(e), "success": False})

        finally:
            await self.disconnect()

        return {
            "opportunities": opportunities,
            "product_configurations": configurations,
            "ipas_quote_id": ipas_quote_id,
            "tool_calls": tool_calls,
        }

    def _config_to_dict(self, config: ProductConfiguration) -> dict[str, Any]:
        """Convert ProductConfiguration to dictionary."""
        return {
            "config_id": config.config_id,
            "product_id": config.product_id,
            "product_name": config.product_name,
            "variant": config.variant,
            "bom_items": config.bom_items,
            "characteristics": config.characteristics,
            "pricing_relevant": config.pricing_relevant,
        }

    # =========================================================================
    # A2A Capabilities
    # =========================================================================

    def _extract_primary_capabilities(self) -> list["Capability"]:
        """Extract primary capabilities for A2A semantic routing.

        Overrides BaseAgent method to provide rich capability descriptions
        for intelligent task routing via Pipeline.router().

        Returns:
            List of Capability objects for A2A matching
        """
        try:
            from kaizen.nodes.ai.a2a import Capability, CapabilityLevel

            return [
                Capability(
                    name="opportunity_extraction",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Extract opportunity data from SAP CEC Sales Cloud",
                    keywords=[
                        "opportunity",
                        "cec",
                        "sales cloud",
                        "pipeline",
                        "deal",
                        "prospect",
                        "extract",
                    ],
                    examples=[
                        "Get opportunity OPP-12345",
                        "Extract opportunity details",
                        "What's the status of this deal?",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="ipas_configuration",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Extract product configurations from IPAS",
                    keywords=[
                        "ipas",
                        "configuration",
                        "product config",
                        "bom",
                        "bill of materials",
                        "quote",
                    ],
                    examples=[
                        "Get IPAS configuration",
                        "What products are in this quote?",
                        "Extract BOM from IPAS",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="order_preparation",
                    domain="order_processing",
                    level=CapabilityLevel.ADVANCED,
                    description="Prepare data for sales order creation in SAP",
                    keywords=[
                        "order",
                        "prepare",
                        "sales order",
                        "ready",
                        "creation",
                    ],
                    examples=[
                        "Prepare order data",
                        "Is this opportunity ready for order?",
                        "What's missing for order creation?",
                    ],
                    constraints=[],
                ),
            ]
        except ImportError:
            return []

    def get_capabilities(self) -> list["Capability"]:
        """Get A2A capabilities for semantic routing.

        Alias for _extract_primary_capabilities() for backward compatibility.

        Returns:
            List of Capability objects for A2A matching
        """
        return self._extract_primary_capabilities()

    # =========================================================================
    # Synchronous Run Method (A2A Router Compatibility)
    # =========================================================================

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous run method for A2A Router compatibility.

        Handles both direct calls (opportunity_id=) and Pipeline.router calls (task=).

        Args:
            task: Primary input from Pipeline.router()
            opportunity_id: Direct opportunity ID input (alias for task)
            **kwargs: Additional parameters

        Returns:
            Standardized response dict with success, agent_id, result_data
        """
        import asyncio

        # Extract task (Pipeline.router convention) or opportunity_id
        task = kwargs.get("task", "")
        opportunity_id = kwargs.get("opportunity_id") or task

        if not opportunity_id:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": "No opportunity_id provided. Use task= or opportunity_id=",
                "metadata": {"routing": "a2a_run"},
            }

        async def _execute():
            try:
                if not self._connected:
                    await self.connect()

                result = await self.get_opportunity_with_config(opportunity_id)
                return {
                    "success": True,
                    "agent_id": self.agent_id,
                    "result_data": result,
                    "error_message": None,
                    "metadata": {
                        "routing": "a2a_run",
                        "opportunity_id": opportunity_id,
                    },
                }
            except Exception as e:
                return {
                    "success": False,
                    "agent_id": self.agent_id,
                    "result_data": {},
                    "error_message": str(e),
                    "metadata": {"routing": "a2a_run"},
                }

        try:
            asyncio.get_running_loop()
            # Already in async context - use thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _execute())
                return future.result()
        except RuntimeError:
            # No running loop - safe to run
            return asyncio.run(_execute())

    @classmethod
    def get_signature(cls) -> type:
        """Get the signature class for this agent.

        Returns:
            OpportunitySignature from signatures.py
        """
        return cls.SIGNATURE


# =============================================================================
# Factory Function
# =============================================================================


def create_opportunity_agent(
    config: Optional[OpportunityConfig] = None,
) -> OpportunityAgent:
    """Create an OpportunityAgent instance.

    Factory function for consistent agent instantiation.

    Args:
        config: Optional configuration

    Returns:
        Configured OpportunityAgent instance
    """
    return OpportunityAgent(config=config)
