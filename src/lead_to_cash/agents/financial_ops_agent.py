"""
Financial Operations Agent

Kaizen-based AI agent for creating draft sales orders in SAP MS5 (S/4HANA).

Part of the Order Processing Domain (ADR-002).

Capabilities:
    - Create draft sales orders in SAP MS5
    - Validate order data before submission
    - Handle order simulation
    - Perform credit checks
    - Track order status

Architecture:
    FinancialOpsAgent → MS5Client → CPI → SAP S/4HANA

Usage:
    from lead_to_cash.agents import FinancialOpsAgent, FinancialOpsConfig

    config = FinancialOpsConfig()
    agent = FinancialOpsAgent(config)

    # Create draft order
    result = await agent.create_draft_order(
        opportunity_id="OPP-12345",
        customer_id="0022005992",
        items=bom_items,
    )
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import FinancialOpsSignature
from lead_to_cash.integrations.ms5_client import (
    MS5Client,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class FinancialOpsConfig:
    """Configuration for FinancialOpsAgent."""

    # Connection settings
    cpi_timeout_seconds: int = 60  # Order creation may take longer

    # Order settings
    default_order_type: str = "draft"  # draft, simulation, final
    default_doc_type: str = "ZOR"  # SAP document type
    require_credit_check: bool = True
    default_sales_org: str = ""  # Must be provided
    default_distr_chan: str = ""  # Must be provided
    default_division: str = ""  # Must be provided

    # Safety settings
    allow_final_orders: bool = False  # Safety flag - require explicit enable

    # LLM settings (for future enhancement)
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.0
    max_tokens: int = 4096

    # Agent metadata
    agent_name: str = "FinancialOpsAgent"
    agent_version: str = "1.0.0"


# =============================================================================
# Internal Kaizen Signature (for BaseAgent compatibility)
# =============================================================================


class FinancialOpsAgentSignature(Signature):
    """Internal Kaizen signature for BaseAgent compatibility."""

    # Inputs
    opportunity_id: str = InputField(
        description="CEC opportunity ID for reference",
        default="",
    )
    customer_id: str = InputField(
        description="SAP customer ID (10-digit)",
    )
    ipas_quote_id: str = InputField(
        description="IPAS quote ID for product configuration",
        default="",
    )
    order_type: str = InputField(
        description="Order type: draft, simulation, or final",
        default="draft",
    )
    items: list = InputField(
        description="Order line items from IPAS BOM",
        default_factory=list,
    )
    sales_org: str = InputField(
        description="SAP sales organization",
        default="",
    )
    distr_chan: str = InputField(
        description="SAP distribution channel",
        default="",
    )
    division: str = InputField(
        description="SAP division",
        default="",
    )

    # Outputs
    order_id: str = OutputField(
        description="SAP sales order number if created",
        default="",
    )
    order_status: str = OutputField(
        description="Order status",
        default="",
    )
    simulation_result: dict = OutputField(
        description="Simulation result if order_type is simulation",
        default_factory=dict,
    )
    credit_check: dict = OutputField(
        description="Credit check result",
        default_factory=dict,
    )
    tool_calls: list = OutputField(
        description="Tool calls for convergence detection",
        default_factory=list,
    )


# =============================================================================
# Agent Implementation
# =============================================================================


class FinancialOpsAgent(BaseAgent):
    """
    Financial Operations Agent for MS5 order creation.

    Part of the Order Processing Domain (ADR-002).

    This agent creates draft sales orders in SAP MS5, performs
    credit checks, and handles order simulation and validation.

    SAFETY: By default, only draft and simulation orders are allowed.
    Final orders require explicit configuration (allow_final_orders=True).
    """

    # Class-level signature reference for A2A capability matching
    SIGNATURE = FinancialOpsSignature

    def __init__(self, config: Optional[FinancialOpsConfig] = None):
        """Initialize FinancialOpsAgent.

        Args:
            config: Agent configuration. Defaults to FinancialOpsConfig().
        """
        self.config = config or FinancialOpsConfig()

        super().__init__(
            config=self.config,
            signature=FinancialOpsAgentSignature(),
        )

        # Initialize client (lazy connection)
        self._ms5_client: Optional[MS5Client] = None
        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connection to MS5 via CPI."""
        if self._connected:
            return

        self._ms5_client = MS5Client()
        await self._ms5_client.connect()

        self._connected = True
        logger.info("FinancialOpsAgent connected to MS5")

    async def disconnect(self) -> None:
        """Close connection."""
        if self._ms5_client:
            await self._ms5_client.disconnect()

        self._connected = False
        logger.info("FinancialOpsAgent disconnected")

    async def __aenter__(self) -> "FinancialOpsAgent":
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
                "FinancialOpsAgent not connected. Use async context manager or call connect()."
            )

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def check_credit(
        self,
        customer_id: str,
        order_value: float = 0,
        credit_control_area: str = "1000",
    ) -> dict[str, Any]:
        """Check customer credit status.

        Args:
            customer_id: SAP customer ID
            order_value: Optional order value to check against
            credit_control_area: SAP credit control area

        Returns:
            Credit check result dictionary
        """
        self._ensure_connected()

        credit_data = await self._ms5_client.check_credit_limit(
            customer_id=customer_id,
            order_value=order_value,
            credit_control_area=credit_control_area,
        )

        return {
            "customer_id": credit_data.customer_id,
            "credit_limit": credit_data.credit_limit,
            "credit_exposure": credit_data.credit_exposure,
            "available_credit": credit_data.available_credit,
            "utilization_percent": credit_data.utilization_percent,
            "credit_check_passed": credit_data.credit_check_passed,
            "currency": credit_data.currency,
        }

    async def simulate_order(
        self,
        customer_id: str,
        items: list[dict],
        sales_org: str,
        distr_chan: str,
        division: str,
        opportunity_id: str = "",
    ) -> dict[str, Any]:
        """Simulate sales order without creating.

        Args:
            customer_id: SAP customer ID
            items: Order line items
            sales_org: SAP sales organization
            distr_chan: Distribution channel
            division: Division
            opportunity_id: Optional reference

        Returns:
            Simulation result dictionary
        """
        self._ensure_connected()

        order_data = self._build_order_data(
            customer_id=customer_id,
            items=items,
            sales_org=sales_org,
            distr_chan=distr_chan,
            division=division,
            opportunity_id=opportunity_id,
        )

        simulation = await self._ms5_client.simulate_order(order_data)

        return {
            "is_valid": simulation.is_valid,
            "net_value": simulation.net_value,
            "currency": simulation.currency,
            "item_count": simulation.item_count,
            "messages": simulation.messages,
            "errors": simulation.errors,
            "warnings": simulation.warnings,
        }

    async def create_draft_order(
        self,
        customer_id: str,
        items: list[dict],
        sales_org: str,
        distr_chan: str,
        division: str,
        opportunity_id: str = "",
        ipas_quote_id: str = "",
        perform_credit_check: bool = True,
    ) -> dict[str, Any]:
        """Create a draft sales order.

        Draft orders use test_run=True to validate without committing.
        This is the safest mode for AI-assisted order creation.

        Args:
            customer_id: SAP customer ID
            items: Order line items
            sales_org: SAP sales organization
            distr_chan: Distribution channel
            division: Division
            opportunity_id: CEC opportunity reference
            ipas_quote_id: IPAS quote reference
            perform_credit_check: Whether to check credit first

        Returns:
            Draft order result dictionary
        """
        self._ensure_connected()

        result = {
            "order_id": "",
            "order_status": "draft_pending",
            "simulation_result": {},
            "credit_check": {},
            "errors": [],
            "warnings": [],
        }

        # Perform credit check if requested
        if perform_credit_check:
            try:
                result["credit_check"] = await self.check_credit(customer_id)
                if not result["credit_check"].get("credit_check_passed", False):
                    result["warnings"].append(
                        "Credit check indicates potential issues - review before finalizing"
                    )
            except Exception as e:
                result["warnings"].append(f"Credit check failed: {e}")

        # Build order data
        order_data = self._build_order_data(
            customer_id=customer_id,
            items=items,
            sales_org=sales_org,
            distr_chan=distr_chan,
            division=division,
            opportunity_id=opportunity_id,
            ipas_quote_id=ipas_quote_id,
        )

        # Create draft (test_run=True)
        try:
            order_result = await self._ms5_client.create_order(
                order_data=order_data,
                test_run=True,  # Draft mode - validate only
            )

            result["order_status"] = (
                "draft_validated" if order_result.success else "draft_failed"
            )
            result["simulation_result"] = {
                "success": order_result.success,
                "document_number": order_result.document_number,
                "messages": order_result.messages,
            }

            if order_result.success:
                # Draft validated successfully
                result["order_id"] = f"DRAFT-{order_result.document_number}"
            else:
                result["errors"].extend(
                    [
                        m.get("MESSAGE", str(m))
                        for m in order_result.messages
                        if m.get("TYPE") == "E"
                    ]
                )

        except Exception as e:
            result["order_status"] = "draft_error"
            result["errors"].append(str(e))

        return result

    async def create_final_order(
        self,
        customer_id: str,
        items: list[dict],
        sales_org: str,
        distr_chan: str,
        division: str,
        opportunity_id: str = "",
        ipas_quote_id: str = "",
    ) -> dict[str, Any]:
        """Create a final (committed) sales order.

        WARNING: This creates a real order in SAP. Use with caution.
        Only available if config.allow_final_orders=True.

        Args:
            customer_id: SAP customer ID
            items: Order line items
            sales_org: SAP sales organization
            distr_chan: Distribution channel
            division: Division
            opportunity_id: CEC opportunity reference
            ipas_quote_id: IPAS quote reference

        Returns:
            Final order result dictionary

        Raises:
            RuntimeError: If final orders are not allowed
        """
        if not self.config.allow_final_orders:
            raise RuntimeError(
                "Final order creation is disabled. "
                "Set config.allow_final_orders=True to enable."
            )

        self._ensure_connected()

        # Build order data
        order_data = self._build_order_data(
            customer_id=customer_id,
            items=items,
            sales_org=sales_org,
            distr_chan=distr_chan,
            division=division,
            opportunity_id=opportunity_id,
            ipas_quote_id=ipas_quote_id,
        )

        # Create final order (test_run=False)
        order_result = await self._ms5_client.create_order(
            order_data=order_data,
            test_run=False,
        )

        return {
            "order_id": order_result.document_number,
            "order_status": "created" if order_result.success else "failed",
            "committed": order_result.committed,
            "messages": order_result.messages,
        }

    def _build_order_data(
        self,
        customer_id: str,
        items: list[dict],
        sales_org: str,
        distr_chan: str,
        division: str,
        opportunity_id: str = "",
        ipas_quote_id: str = "",
    ) -> dict[str, Any]:
        """Build SAP order data structure.

        Args:
            customer_id: SAP customer ID
            items: Order line items
            sales_org: SAP sales organization
            distr_chan: Distribution channel
            division: Division
            opportunity_id: CEC opportunity reference
            ipas_quote_id: IPAS quote reference

        Returns:
            Order data dictionary for MS5Client
        """
        # Use config defaults if not provided
        sales_org = sales_org or self.config.default_sales_org
        distr_chan = distr_chan or self.config.default_distr_chan
        division = division or self.config.default_division

        # Build header
        header = {
            "DOC_TYPE": self.config.default_doc_type,
            "SALES_ORG": sales_org,
            "DISTR_CHAN": distr_chan,
            "DIVISION": division,
            "PURCH_NO_C": opportunity_id or "",  # Customer PO reference
        }

        if ipas_quote_id:
            header["IPAS_QUOTE"] = ipas_quote_id

        # Build partners
        partners = [
            {
                "PARTN_ROLE": "AG",  # Sold-to party
                "PARTN_NUMB": customer_id.zfill(10),
            }
        ]

        # Format items
        formatted_items = []
        for i, item in enumerate(items):
            formatted_items.append(
                {
                    "ITM_NUMBER": item.get("ITM_NUMBER", str((i + 1) * 10).zfill(6)),
                    "MATERIAL": item.get("MATERIAL", item.get("material", "")),
                    "TARGET_QTY": item.get("TARGET_QTY", item.get("quantity", 1)),
                    "SALES_UNIT": item.get("SALES_UNIT", item.get("unit", "EA")),
                    "PLANT": item.get("PLANT", item.get("plant", "")),
                }
            )

        return {
            "header": header,
            "items": formatted_items,
            "partners": partners,
        }

    # =========================================================================
    # BaseAgent Implementation
    # =========================================================================

    async def _execute(self, **kwargs) -> dict[str, Any]:
        """Execute agent with signature-based inputs.

        This method is called by BaseAgent.run() with validated inputs.

        Args:
            **kwargs: Inputs matching FinancialOpsAgentSignature

        Returns:
            Dictionary matching FinancialOpsSignature output fields
        """
        opportunity_id = kwargs.get("opportunity_id", "")
        customer_id = kwargs.get("customer_id", "")
        ipas_quote_id = kwargs.get("ipas_quote_id", "")
        order_type = kwargs.get("order_type", self.config.default_order_type)
        items = kwargs.get("items", [])
        sales_org = kwargs.get("sales_org", self.config.default_sales_org)
        distr_chan = kwargs.get("distr_chan", self.config.default_distr_chan)
        division = kwargs.get("division", self.config.default_division)

        # Track tool calls for convergence
        tool_calls = []

        # Validate required inputs
        if not customer_id:
            return {
                "order_id": "",
                "order_status": "error",
                "simulation_result": {},
                "credit_check": {},
                "tool_calls": [
                    {
                        "tool": "validation",
                        "error": "customer_id required",
                        "success": False,
                    }
                ],
            }

        if not items:
            return {
                "order_id": "",
                "order_status": "error",
                "simulation_result": {},
                "credit_check": {},
                "tool_calls": [
                    {"tool": "validation", "error": "items required", "success": False}
                ],
            }

        try:
            await self.connect()

            if order_type == "simulation":
                # Simulation only
                simulation = await self.simulate_order(
                    customer_id=customer_id,
                    items=items,
                    sales_org=sales_org,
                    distr_chan=distr_chan,
                    division=division,
                    opportunity_id=opportunity_id,
                )
                tool_calls.append(
                    {"tool": "ms5_client", "action": "simulate_order", "success": True}
                )
                return {
                    "order_id": "",
                    "order_status": "simulated",
                    "simulation_result": simulation,
                    "credit_check": {},
                    "tool_calls": tool_calls,
                }

            elif order_type == "draft":
                # Draft order (default, safest)
                result = await self.create_draft_order(
                    customer_id=customer_id,
                    items=items,
                    sales_org=sales_org,
                    distr_chan=distr_chan,
                    division=division,
                    opportunity_id=opportunity_id,
                    ipas_quote_id=ipas_quote_id,
                    perform_credit_check=self.config.require_credit_check,
                )
                tool_calls.append(
                    {
                        "tool": "ms5_client",
                        "action": "create_draft",
                        "success": "error" not in result["order_status"],
                    }
                )
                result["tool_calls"] = tool_calls
                return result

            elif order_type == "final":
                # Final order (requires explicit config)
                result = await self.create_final_order(
                    customer_id=customer_id,
                    items=items,
                    sales_org=sales_org,
                    distr_chan=distr_chan,
                    division=division,
                    opportunity_id=opportunity_id,
                    ipas_quote_id=ipas_quote_id,
                )
                tool_calls.append(
                    {
                        "tool": "ms5_client",
                        "action": "create_final",
                        "success": result.get("order_status") == "created",
                    }
                )
                return {
                    "order_id": result.get("order_id", ""),
                    "order_status": result.get("order_status", ""),
                    "simulation_result": {},
                    "credit_check": {},
                    "tool_calls": tool_calls,
                }

            else:
                return {
                    "order_id": "",
                    "order_status": "error",
                    "simulation_result": {},
                    "credit_check": {},
                    "tool_calls": [
                        {
                            "tool": "validation",
                            "error": f"Unknown order_type: {order_type}",
                            "success": False,
                        }
                    ],
                }

        except Exception as e:
            logger.error(f"FinancialOpsAgent execution error: {e}")
            return {
                "order_id": "",
                "order_status": "error",
                "simulation_result": {},
                "credit_check": {},
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
                    name="draft_order_creation",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Create draft sales orders in SAP MS5",
                    keywords=[
                        "order",
                        "create",
                        "draft",
                        "sales order",
                        "ms5",
                        "sap",
                    ],
                    examples=[
                        "Create draft order",
                        "Generate sales order from opportunity",
                        "Submit order to SAP",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="order_simulation",
                    domain="order_processing",
                    level=CapabilityLevel.EXPERT,
                    description="Simulate sales orders for validation before creation",
                    keywords=[
                        "simulate",
                        "simulation",
                        "validate",
                        "test",
                        "preview",
                        "order",
                    ],
                    examples=[
                        "Simulate this order",
                        "Validate order before creation",
                        "Preview order pricing",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="credit_check",
                    domain="finance",
                    level=CapabilityLevel.ADVANCED,
                    description="Perform customer credit checks for order processing",
                    keywords=[
                        "credit",
                        "check",
                        "credit limit",
                        "exposure",
                        "customer credit",
                    ],
                    examples=[
                        "Check credit for customer",
                        "Can this customer place this order?",
                        "Credit availability check",
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
            config_id: IPAS configuration ID
            customer_id: Customer ID for credit check
            **kwargs: Additional parameters

        Returns:
            Standardized response dict with success, agent_id, result_data
        """
        import asyncio

        # Extract task (Pipeline.router convention) or opportunity_id
        task = kwargs.get("task", "")
        opportunity_id = kwargs.get("opportunity_id") or task
        config_id = kwargs.get("config_id")
        customer_id = kwargs.get("customer_id")

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

                result = await self.create_draft_order(
                    opportunity_id=opportunity_id,
                    config_id=config_id or "",
                    customer_id=customer_id or "",
                )
                return {
                    "success": result.get("draft_order", {}).get("created", False),
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
            FinancialOpsSignature from signatures.py
        """
        return cls.SIGNATURE


# =============================================================================
# Factory Function
# =============================================================================


def create_financial_ops_agent(
    config: Optional[FinancialOpsConfig] = None,
) -> FinancialOpsAgent:
    """Create a FinancialOpsAgent instance.

    Factory function for consistent agent instantiation.

    Args:
        config: Optional configuration

    Returns:
        Configured FinancialOpsAgent instance
    """
    return FinancialOpsAgent(config=config)
