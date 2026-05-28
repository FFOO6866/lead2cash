"""
Data Management Agent

Kaizen-based AI agent for assisting with SAP MS5 data entry by
displaying IPAS product configuration data and suggesting field values.

Part of the Order Processing Domain (ADR-002).

Capabilities:
    - Display IPAS product configuration for user review
    - Suggest MS5 field values based on IPAS data
    - Validate data completeness before order creation
    - Map IPAS fields to SAP sales order fields

Architecture:
    DataManagementAgent → IPASClient → CPI → IPAS
    DataManagementAgent → MS5Client → CPI → SAP S/4HANA (for validation)

Usage:
    from lead_to_cash.agents import DataManagementAgent, DataManagementConfig

    config = DataManagementConfig()
    agent = DataManagementAgent(config)

    # Display IPAS data for MS5 entry
    result = await agent.prepare_for_ms5_entry("IPAS-2025-0892")
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import DataManagementSignature
from lead_to_cash.integrations.ipas_client import IPASClient, ProductConfiguration
from lead_to_cash.integrations.ms5_client import MS5Client

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DataManagementConfig:
    """Configuration for DataManagementAgent."""

    # Connection settings
    cpi_timeout_seconds: int = 30

    # Simulation mode - use CPISimulator for development/testing
    simulation_mode: bool = False

    # Display settings
    default_display_mode: str = "summary"  # summary, detail, bom_only
    default_target_system: str = "MS5"

    # Validation settings
    require_complete_bom: bool = True
    require_pricing: bool = True

    # LLM settings (for future enhancement)
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.0
    max_tokens: int = 4096

    # Agent metadata
    agent_name: str = "DataManagementAgent"
    agent_version: str = "1.0.0"


# =============================================================================
# Internal Kaizen Signature (for BaseAgent compatibility)
# =============================================================================


class DataManagementAgentSignature(Signature):
    """Internal Kaizen signature for BaseAgent compatibility."""

    # Inputs
    ipas_quote_id: str = InputField(
        description="IPAS quote ID to extract data from",
    )
    target_system: str = InputField(
        description="Target SAP system for field mapping",
        default="MS5",
    )
    display_mode: str = InputField(
        description="How to display data to user",
        default="summary",
    )

    # Outputs
    ipas_data_display: dict = OutputField(
        description="Formatted IPAS data for display",
        default_factory=dict,
    )
    suggested_fields: dict = OutputField(
        description="Suggested field values for MS5",
        default_factory=dict,
    )
    bom_items: list = OutputField(
        description="Bill of Materials items",
        default_factory=list,
    )
    validation_status: dict = OutputField(
        description="Data validation status",
        default_factory=dict,
    )
    tool_calls: list = OutputField(
        description="Tool calls for convergence detection",
        default_factory=list,
    )


# =============================================================================
# Agent Implementation
# =============================================================================


class DataManagementAgent(BaseAgent):
    """
    Data Management Agent for MS5 entry assistance.

    Part of the Order Processing Domain (ADR-002).

    This agent retrieves IPAS product configurations and formats them
    for display, helping users enter data into SAP MS5 accurately.
    """

    # Class-level signature reference for A2A capability matching
    SIGNATURE = DataManagementSignature

    def __init__(self, config: Optional[DataManagementConfig] = None):
        """Initialize DataManagementAgent.

        Args:
            config: Agent configuration. Defaults to DataManagementConfig().
        """
        self.domain_config = config or DataManagementConfig()

        super().__init__(
            config=self.domain_config,
            signature=DataManagementAgentSignature(),
        )

        # Initialize clients (lazy connection)
        self._ipas_client: Optional[IPASClient] = None
        self._ms5_client: Optional[MS5Client] = None
        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connections to IPAS and MS5 via CPI.

        When simulation_mode is enabled, uses CPISimulator instead of real CPI
        to allow development and testing without SAP credentials.
        """
        if self._connected:
            return

        simulation_mode = self.domain_config.simulation_mode
        self._ipas_client = IPASClient(simulation_mode=simulation_mode)
        self._ms5_client = MS5Client(simulation_mode=simulation_mode)

        await self._ipas_client.connect()
        await self._ms5_client.connect()

        self._connected = True
        mode_str = " (simulation mode)" if simulation_mode else ""
        logger.info(f"DataManagementAgent connected to IPAS and MS5{mode_str}")

    async def disconnect(self) -> None:
        """Close connections."""
        if self._ipas_client:
            await self._ipas_client.disconnect()
        if self._ms5_client:
            await self._ms5_client.disconnect()

        self._connected = False
        logger.info("DataManagementAgent disconnected")

    async def __aenter__(self) -> "DataManagementAgent":
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
                "DataManagementAgent not connected. Use async context manager or call connect()."
            )

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def get_ipas_configuration(self, config_id: str) -> ProductConfiguration:
        """Get IPAS product configuration by ID.

        Args:
            config_id: IPAS configuration/quote ID

        Returns:
            ProductConfiguration from IPAS
        """
        self._ensure_connected()
        return await self._ipas_client.get_configuration(config_id)

    def format_for_display(
        self,
        config: ProductConfiguration,
        display_mode: str = "summary",
    ) -> dict[str, Any]:
        """Format IPAS configuration for user display.

        Args:
            config: ProductConfiguration to format
            display_mode: summary, detail, or bom_only

        Returns:
            Formatted data dictionary for display
        """
        if display_mode == "bom_only":
            return {
                "config_id": config.config_id,
                "product_name": config.product_name,
                "bom_items": config.bom_items,
                "item_count": len(config.bom_items),
            }

        base_display = {
            "config_id": config.config_id,
            "product_id": config.product_id,
            "product_name": config.product_name,
            "variant": config.variant,
            "item_count": len(config.bom_items),
            "pricing_relevant": config.pricing_relevant,
        }

        if display_mode == "detail":
            base_display["bom_items"] = config.bom_items
            base_display["characteristics"] = config.characteristics

        return base_display

    def map_to_ms5_fields(self, config: ProductConfiguration) -> dict[str, Any]:
        """Map IPAS configuration to MS5 sales order fields.

        Args:
            config: ProductConfiguration to map

        Returns:
            Dictionary with suggested MS5 field values
        """
        # Convert BOM to SAP order item format
        order_items = config.to_order_items()

        return {
            "header_fields": {
                "IPAS_QUOTE_REF": config.config_id,
                "DOC_TYPE": "ZOR",  # Standard sales order
                "SALES_ORG": "",  # To be filled by user
                "DISTR_CHAN": "",  # To be filled by user
                "DIVISION": "",  # To be filled by user
            },
            "item_fields": order_items,
            "characteristics": config.characteristics,
            "notes": [
                f"Generated from IPAS configuration: {config.config_id}",
                f"Product: {config.product_name}",
                f"Items: {len(order_items)}",
            ],
        }

    def validate_for_order(self, config: ProductConfiguration) -> dict[str, Any]:
        """Validate configuration completeness for order creation.

        Args:
            config: ProductConfiguration to validate

        Returns:
            Validation status dictionary
        """
        errors = []
        warnings = []
        ready = True

        # Check BOM completeness
        if not config.bom_items:
            errors.append("BOM is empty - no items to order")
            ready = False
        elif self.config.require_complete_bom:
            for i, item in enumerate(config.bom_items):
                if not item.get("material"):
                    errors.append(f"Item {i + 1}: Missing material number")
                    ready = False
                if not item.get("quantity"):
                    warnings.append(
                        f"Item {i + 1}: No quantity specified (will default to 1)"
                    )

        # Check pricing relevance
        if self.config.require_pricing and not config.pricing_relevant:
            warnings.append("Configuration not marked as pricing relevant")

        # Check required characteristics
        chars = config.characteristics
        if not chars.get("SALES_ORG"):
            warnings.append("Sales organization not specified in configuration")

        return {
            "ready_for_order": ready and len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "item_count": len(config.bom_items),
            "has_pricing": config.pricing_relevant,
        }

    async def prepare_for_ms5_entry(
        self,
        ipas_quote_id: str,
        display_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """Prepare IPAS data for MS5 entry.

        This is the primary method for Order Processing domain.
        Retrieves IPAS configuration, formats for display, maps to MS5 fields,
        and validates for order creation.

        Args:
            ipas_quote_id: IPAS quote/configuration ID
            display_mode: Optional display mode override

        Returns:
            Complete data package for MS5 entry assistance
        """
        self._ensure_connected()

        display_mode = display_mode or self.config.default_display_mode

        # Get IPAS configuration
        config = await self.get_ipas_configuration(ipas_quote_id)

        # Format for display
        display_data = self.format_for_display(config, display_mode)

        # Map to MS5 fields
        suggested_fields = self.map_to_ms5_fields(config)

        # Validate
        validation = self.validate_for_order(config)

        return {
            "ipas_data_display": display_data,
            "suggested_fields": suggested_fields,
            "bom_items": config.bom_items,
            "validation_status": validation,
        }

    # =========================================================================
    # BaseAgent Implementation
    # =========================================================================

    async def _execute(self, **kwargs) -> dict[str, Any]:
        """Execute agent with signature-based inputs.

        This method is called by BaseAgent.run() with validated inputs.

        Args:
            **kwargs: Inputs matching DataManagementAgentSignature

        Returns:
            Dictionary matching DataManagementSignature output fields
        """
        ipas_quote_id = kwargs.get("ipas_quote_id", "")
        target_system = kwargs.get("target_system", self.config.default_target_system)
        display_mode = kwargs.get("display_mode", self.config.default_display_mode)

        # Track tool calls for convergence
        tool_calls = []

        if not ipas_quote_id:
            logger.warning("No ipas_quote_id provided")
            return {
                "ipas_data_display": {},
                "suggested_fields": {},
                "bom_items": [],
                "validation_status": {
                    "ready_for_order": False,
                    "errors": ["No IPAS quote ID provided"],
                    "warnings": [],
                },
                "tool_calls": [
                    {"tool": "validation", "action": "check_inputs", "success": False}
                ],
            }

        try:
            await self.connect()

            result = await self.prepare_for_ms5_entry(
                ipas_quote_id=ipas_quote_id,
                display_mode=display_mode,
            )

            tool_calls.append(
                {"tool": "ipas_client", "action": "get_configuration", "success": True}
            )
            tool_calls.append(
                {"tool": "mapper", "action": f"map_to_{target_system}", "success": True}
            )
            tool_calls.append(
                {"tool": "validator", "action": "validate_for_order", "success": True}
            )

            result["tool_calls"] = tool_calls
            return result

        except Exception as e:
            logger.error(f"DataManagementAgent execution error: {e}")
            return {
                "ipas_data_display": {},
                "suggested_fields": {},
                "bom_items": [],
                "validation_status": {
                    "ready_for_order": False,
                    "errors": [str(e)],
                    "warnings": [],
                },
                "tool_calls": [{"tool": "error", "message": str(e), "success": False}],
            }

        finally:
            await self.disconnect()

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
                    name="ipas_data_display",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Display IPAS product configuration data for MS5 entry",
                    keywords=[
                        "ipas",
                        "display",
                        "configuration",
                        "bom",
                        "data",
                        "show",
                        "view",
                    ],
                    examples=[
                        "Show IPAS configuration",
                        "Display product data for entry",
                        "What's in this configuration?",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="ms5_field_mapping",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Map IPAS fields to MS5 sales order fields",
                    keywords=[
                        "ms5",
                        "mapping",
                        "field",
                        "sales order",
                        "sap",
                        "transform",
                    ],
                    examples=[
                        "Map IPAS to MS5 fields",
                        "What SAP fields does this map to?",
                        "Transform configuration for SAP",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="order_validation",
                    domain="order_processing",
                    level=CapabilityLevel.ADVANCED,
                    description="Validate data completeness for order creation",
                    keywords=[
                        "validate",
                        "validation",
                        "complete",
                        "ready",
                        "check",
                        "order",
                    ],
                    examples=[
                        "Validate order data",
                        "Is this ready for order creation?",
                        "What's missing?",
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

        Handles both direct calls (config_id=) and Pipeline.router calls (task=).

        Args:
            task: Primary input from Pipeline.router()
            config_id: Direct IPAS configuration ID input (alias for task)
            **kwargs: Additional parameters

        Returns:
            Standardized response dict with success, agent_id, result_data
        """
        import asyncio

        # Extract task (Pipeline.router convention) or config_id
        task = kwargs.get("task", "")
        config_id = kwargs.get("config_id") or task

        if not config_id:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": "No config_id provided. Use task= or config_id=",
                "metadata": {"routing": "a2a_run"},
            }

        async def _execute():
            try:
                if not self._connected:
                    await self.connect()

                config = await self.get_configuration(config_id)
                display = self.format_for_display(config)
                return {
                    "success": True,
                    "agent_id": self.agent_id,
                    "result_data": {
                        "configuration": self._config_to_dict(config),
                        "display": display,
                    },
                    "error_message": None,
                    "metadata": {"routing": "a2a_run", "config_id": config_id},
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
            DataManagementSignature from signatures.py
        """
        return cls.SIGNATURE


# =============================================================================
# Factory Function
# =============================================================================


def create_data_management_agent(
    config: Optional[DataManagementConfig] = None,
) -> DataManagementAgent:
    """Create a DataManagementAgent instance.

    Factory function for consistent agent instantiation.

    Args:
        config: Optional configuration

    Returns:
        Configured DataManagementAgent instance
    """
    return DataManagementAgent(config=config)
