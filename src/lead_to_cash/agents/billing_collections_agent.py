"""
Billing & Collections Agent

Kaizen-based AI agent for accounts receivable tracking and billing status.

Part of the Order Processing Domain (ADR-002) - Post-Order phase.

Capabilities:
    - Get billing items pending invoicing
    - Track collections status and overdue payments
    - Retrieve harmonized payment terms for customers
    - Provide aging bucket analysis
    - Explain payment schedules and milestones

Architecture:
    BillingCollectionsAgent → FinOpsDataService → CPI/MS5

Usage:
    from lead_to_cash.agents import BillingCollectionsAgent, BillingCollectionsConfig

    config = BillingCollectionsConfig()
    agent = BillingCollectionsAgent(config)

    # Get billing summary
    summary = await agent.get_billing_summary()

    # Get collections items
    items = await agent.get_collections_items(customer_id="0022005992")
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import BillingCollectionsSignature
from lead_to_cash.services.financeops import FinOpsDataService
from lead_to_cash.services.financeops.escalation_service import EscalationService

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class BillingCollectionsConfig:
    """Configuration for BillingCollectionsAgent."""

    # LLM settings (for future enhancement)
    model: str = os.getenv("BILLING_AGENT_MODEL", "claude-sonnet-4-20250514")
    temperature: float = 0.0
    max_tokens: int = 4096

    # Agent metadata
    agent_name: str = "BillingCollectionsAgent"
    agent_version: str = "1.0.0"


# =============================================================================
# Internal Kaizen Signature (for BaseAgent compatibility)
# =============================================================================


class BillingCollectionsAgentSignature(Signature):
    """Internal Kaizen signature for BaseAgent compatibility."""

    # Inputs
    customer_id: str = InputField(
        description="SAP customer ID for billing lookup",
        default="",
    )
    document_number: str = InputField(
        description="Specific billing document number to look up",
        default="",
    )
    query_type: str = InputField(
        description="Type of billing/collections query",
        default="summary",
    )
    status_filter: str = InputField(
        description="Filter by billing status",
        default="",
    )

    # Outputs
    billing_items: list = OutputField(
        description="List of billing items with status and amounts",
        default_factory=list,
    )
    collections_items: list = OutputField(
        description="List of items requiring collection action",
        default_factory=list,
    )
    summary: dict = OutputField(
        description="Summary counts for billing, collections, and overdue items",
        default_factory=dict,
    )
    aging_buckets: dict = OutputField(
        description="Aging bucket breakdown",
        default_factory=dict,
    )
    payment_terms: dict = OutputField(
        description="Harmonized payment terms for customer",
        default_factory=dict,
    )
    escalations: list = OutputField(
        description="List of escalation events for overdue items",
        default_factory=list,
    )
    escalation_summary: dict = OutputField(
        description="Escalation summary with counts by level",
        default_factory=dict,
    )
    downpayment_alerts: list = OutputField(
        description="Downpayment requests needing action (pending creation, awaiting payment, overdue)",
        default_factory=list,
    )
    overdue_downpayments: list = OutputField(
        description="Overdue downpayment requests requiring collection",
        default_factory=list,
    )
    payment_status: dict = OutputField(
        description="Comprehensive payment status with downpayments, invoices, and summary",
        default_factory=dict,
    )
    tool_calls: list = OutputField(
        description="Tool calls for convergence detection",
        default_factory=list,
    )


# =============================================================================
# Agent Implementation
# =============================================================================


class BillingCollectionsAgent(BaseAgent):
    """
    Billing & Collections Agent for AR tracking.

    Part of the Order Processing Domain (ADR-002) - Post-Order phase.

    This agent provides billing status, collections tracking, payment terms
    analysis, and aging bucket reporting for the FinanceOps dashboard.

    Domain: accounts_receivable (distinct from order_processing)
    """

    # Class-level signature reference for A2A capability matching
    SIGNATURE = BillingCollectionsSignature

    def __init__(self, config: Optional[BillingCollectionsConfig] = None):
        """Initialize BillingCollectionsAgent.

        Args:
            config: Agent configuration. Defaults to BillingCollectionsConfig().
        """
        self.config = config or BillingCollectionsConfig()

        super().__init__(
            config=self.config,
            signature=BillingCollectionsAgentSignature(),
        )

        # Initialize data service (lazy connection)
        self._data_service: Optional[FinOpsDataService] = None
        self._escalation_service: Optional[EscalationService] = None
        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Establish connection to data service."""
        if self._connected:
            return

        self._data_service = FinOpsDataService()
        await self._data_service.connect()

        # Escalation service shares the data service connection
        self._escalation_service = EscalationService(data_service=self._data_service)
        await self._escalation_service.connect()

        self._connected = True
        logger.info("BillingCollectionsAgent connected")

    async def disconnect(self) -> None:
        """Close connection."""
        # Escalation service doesn't own the data service, so just disconnect it
        if self._escalation_service:
            self._escalation_service._connected = False

        if self._data_service:
            await self._data_service.disconnect()

        self._connected = False
        logger.info("BillingCollectionsAgent disconnected")

    async def __aenter__(self) -> "BillingCollectionsAgent":
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
                "BillingCollectionsAgent not connected. "
                "Use async context manager or call connect()."
            )

    def is_connected(self) -> bool:
        """Check if agent is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def get_billing_summary(self) -> dict[str, Any]:
        """Get summary counts for dashboard badges.

        Returns:
            BillingSummary with billing, collections, and overdue counts
        """
        self._ensure_connected()

        summary = await self._data_service.get_summary_counts()
        return summary.to_dict()

    async def get_billing_items(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get billing items, optionally filtered.

        Args:
            customer_id: Filter by customer ID
            status: Filter by billing status

        Returns:
            List of billing item dictionaries
        """
        self._ensure_connected()

        items = await self._data_service.get_billing_items(
            customer_id=customer_id,
            status=status,
        )
        return [item.to_dict() for item in items]

    async def get_collections_items(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get items requiring collection action.

        Args:
            customer_id: Filter by customer ID
            status: Filter by status

        Returns:
            List of collection item dictionaries
        """
        self._ensure_connected()

        items = await self._data_service.get_collections_items(
            customer_id=customer_id,
            status=status,
        )
        return [item.to_dict() for item in items]

    async def get_aging_buckets(
        self, customer_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Get aging bucket breakdown.

        Args:
            customer_id: Optional SAP customer ID to filter by

        Returns:
            Dict with aging buckets and their counts/amounts
        """
        self._ensure_connected()

        return await self._data_service.get_aging_buckets(customer_id=customer_id)

    async def get_payment_terms(self, customer_id: str) -> Optional[dict[str, Any]]:
        """Get harmonized payment terms for a customer.

        Args:
            customer_id: SAP customer ID

        Returns:
            Dict with harmonized payment terms or None
        """
        self._ensure_connected()

        return await self._data_service.get_payment_terms(customer_id)

    async def get_escalations(
        self,
        customer_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get escalation events for overdue billing items.

        Args:
            customer_id: Optional filter by customer ID

        Returns:
            List of escalation event dictionaries
        """
        self._ensure_connected()

        events = await self._escalation_service.get_escalations(
            customer_id=customer_id,
        )
        return [event.to_dict() for event in events]

    async def get_escalation_summary(
        self,
        customer_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get escalation summary with counts by level.

        Args:
            customer_id: Optional filter by customer ID

        Returns:
            Summary dict with counts by level and total overdue amount
        """
        self._ensure_connected()

        return await self._escalation_service.get_escalation_summary(
            customer_id=customer_id,
        )

    # =========================================================================
    # Downpayment & Payment Status Operations
    # =========================================================================

    async def get_downpayment_alerts(
        self,
        customer_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get downpayment requests needing attention.

        Returns FAZ documents that are pending creation, pending collection,
        or overdue — the three states requiring finance team action.

        Args:
            customer_id: Optional filter by customer ID

        Returns:
            List of downpayment alert dictionaries
        """
        self._ensure_connected()

        items = await self._data_service.get_downpayment_alerts(
            customer_id=customer_id,
        )
        return [item.to_dict() for item in items]

    async def get_overdue_downpayments(
        self,
        customer_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get overdue downpayment requests requiring collection.

        Args:
            customer_id: Optional filter by customer ID

        Returns:
            List of overdue downpayment dictionaries
        """
        self._ensure_connected()

        items = await self._data_service.get_overdue_downpayments(
            customer_id=customer_id,
        )
        return [item.to_dict() for item in items]

    async def get_payment_status(
        self,
        customer_id: Optional[str] = None,
        sales_order: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get comprehensive payment status for customer or order.

        Combines downpayment requests and invoices with summary statistics.

        Args:
            customer_id: Optional filter by customer ID
            sales_order: Optional filter by sales order

        Returns:
            Dict with downpayments, invoices, and summary stats
        """
        self._ensure_connected()

        return await self._data_service.get_payment_status(
            customer_id=customer_id,
            sales_order=sales_order,
        )

    # =========================================================================
    # BaseAgent Implementation
    # =========================================================================

    async def _execute(self, **kwargs) -> dict[str, Any]:
        """Execute agent with signature-based inputs.

        This method is called by BaseAgent.run() with validated inputs.

        Args:
            **kwargs: Inputs matching BillingCollectionsAgentSignature

        Returns:
            Dictionary matching BillingCollectionsSignature output fields
        """
        customer_id = kwargs.get("customer_id", "")
        query_type = kwargs.get("query_type", "summary")
        status_filter = kwargs.get("status_filter", "")

        # Track tool calls for convergence
        tool_calls = []

        try:
            # Auto-connect if not already connected (A2A run() path)
            if not self._connected:
                await self.connect()

            result = {
                "billing_items": [],
                "collections_items": [],
                "summary": {},
                "aging_buckets": {},
                "payment_terms": {},
                "escalations": [],
                "escalation_summary": {},
                "downpayment_alerts": [],
                "overdue_downpayments": [],
                "payment_status": {},
                "tool_calls": [],
            }

            if query_type == "summary":
                # Get summary counts
                result["summary"] = await self.get_billing_summary()
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_summary_counts",
                        "success": True,
                    }
                )

            elif query_type == "billing":
                # Get billing items
                result["billing_items"] = await self.get_billing_items(
                    customer_id=customer_id if customer_id else None,
                    status=status_filter if status_filter else None,
                )
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_billing_items",
                        "success": True,
                    }
                )

            elif query_type == "collections":
                # Get collections items
                result["collections_items"] = await self.get_collections_items(
                    customer_id=customer_id if customer_id else None,
                    status=status_filter if status_filter else None,
                )
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_collections_items",
                        "success": True,
                    }
                )

            elif query_type == "aging":
                # Get aging buckets
                result["aging_buckets"] = await self.get_aging_buckets()
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_aging_buckets",
                        "success": True,
                    }
                )

            elif query_type == "payment_terms":
                # Get payment terms for specific customer
                if customer_id:
                    result["payment_terms"] = (
                        await self.get_payment_terms(customer_id) or {}
                    )
                    tool_calls.append(
                        {
                            "tool": "finops_data_service",
                            "action": "get_payment_terms",
                            "success": True,
                        }
                    )
                else:
                    tool_calls.append(
                        {
                            "tool": "validation",
                            "error": "customer_id required for payment_terms",
                            "success": False,
                        }
                    )

            elif query_type == "escalations":
                # Get escalation events
                result["escalations"] = await self.get_escalations(
                    customer_id=customer_id if customer_id else None,
                )
                result["escalation_summary"] = await self.get_escalation_summary(
                    customer_id=customer_id if customer_id else None,
                )
                tool_calls.append(
                    {
                        "tool": "escalation_service",
                        "action": "get_escalations",
                        "success": True,
                    }
                )

            elif query_type == "downpayment_alerts":
                # Get downpayment requests pending creation + overdue
                result["downpayment_alerts"] = await self.get_downpayment_alerts(
                    customer_id=customer_id if customer_id else None,
                )
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_downpayment_alerts",
                        "success": True,
                    }
                )

            elif query_type == "downpayment_overdue":
                # Get overdue downpayments requiring collection
                result["overdue_downpayments"] = await self.get_overdue_downpayments(
                    customer_id=customer_id if customer_id else None,
                )
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_overdue_downpayments",
                        "success": True,
                    }
                )

            elif query_type == "payment_status":
                # Get payment status for customer/order
                result["payment_status"] = await self.get_payment_status(
                    customer_id=customer_id if customer_id else None,
                )
                tool_calls.append(
                    {
                        "tool": "finops_data_service",
                        "action": "get_payment_status",
                        "success": True,
                    }
                )

            else:
                tool_calls.append(
                    {
                        "tool": "validation",
                        "error": f"Unknown query_type: {query_type}",
                        "success": False,
                    }
                )

            result["tool_calls"] = tool_calls
            return result

        except Exception as e:
            logger.error(f"BillingCollectionsAgent execution error: {e}")
            return {
                "billing_items": [],
                "collections_items": [],
                "summary": {},
                "aging_buckets": {},
                "payment_terms": {},
                "escalations": [],
                "escalation_summary": {},
                "downpayment_alerts": [],
                "overdue_downpayments": [],
                "payment_status": {},
                "tool_calls": [{"tool": "error", "message": str(e), "success": False}],
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
                    name="billing_tracking",
                    domain="accounts_receivable",  # Different from "order_processing"
                    level=CapabilityLevel.EXPERT,
                    description="Track billing documents and pending invoices",
                    keywords=[
                        "billing",
                        "invoice",
                        "outstanding",
                        "pending",
                        "AR",
                        "receivable",
                        "pending billing",
                    ],
                    examples=[
                        "What billing items are pending?",
                        "Show invoices for ST Engineering",
                        "Pending billing status",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="collections_monitoring",
                    domain="accounts_receivable",
                    level=CapabilityLevel.EXPERT,
                    description="Monitor collections, overdue payments, and aging",
                    keywords=[
                        "collections",
                        "overdue",
                        "aging",
                        "payment",
                        "due",
                        "dunning",
                        "outstanding",
                    ],
                    examples=[
                        "What invoices are overdue?",
                        "Show collections status",
                        "Aging bucket breakdown",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="payment_terms_analysis",
                    domain="accounts_receivable",
                    level=CapabilityLevel.ADVANCED,
                    description="Analyze and explain payment terms and milestones",
                    keywords=[
                        "payment terms",
                        "milestone",
                        "advance",
                        "down payment",
                        "balance",
                        "L/C",
                        "TT",
                    ],
                    examples=[
                        "Explain payment terms for this customer",
                        "What are the payment milestones?",
                        "Payment schedule",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="escalation_monitoring",
                    domain="accounts_receivable",
                    level=CapabilityLevel.EXPERT,
                    description="Monitor and manage overdue payment escalations (D+1/D+7/D+14)",
                    keywords=[
                        "escalate",
                        "escalation",
                        "D+1",
                        "D+7",
                        "D+14",
                        "overdue alert",
                        "urgent overdue",
                        "escalation level",
                    ],
                    examples=[
                        "Show escalations",
                        "What invoices need escalation?",
                        "Overdue payment alerts",
                        "Level 3 escalations",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="downpayment_tracking",
                    domain="accounts_receivable",
                    level=CapabilityLevel.EXPERT,
                    description="Track downpayment requests — pending creation, awaiting payment, and overdue",
                    keywords=[
                        "downpayment",
                        "down payment",
                        "DP",
                        "advance payment",
                        "FAZ",
                        "deposit",
                        "prepayment",
                    ],
                    examples=[
                        "Show downpayment alerts",
                        "Any overdue downpayments?",
                        "Which DPs need to be created?",
                        "Pending advance payments",
                    ],
                    constraints=[],
                ),
                Capability(
                    name="payment_status_inquiry",
                    domain="accounts_receivable",
                    level=CapabilityLevel.EXPERT,
                    description="Comprehensive payment status combining downpayments, invoices, and milestones",
                    keywords=[
                        "payment status",
                        "payment history",
                        "paid",
                        "unpaid",
                        "cleared",
                        "payment progress",
                        "how much paid",
                    ],
                    examples=[
                        "Payment status for ST Engineering",
                        "How much has CLLS paid?",
                        "Show payment progress for order 1000024001",
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

        Handles both direct calls and Pipeline.router calls (task=).

        Args:
            task: Primary input from Pipeline.router()
            query_type: Type of query (billing, collections, aging, payment_terms, summary)
            customer_id: Optional customer filter
            **kwargs: Additional parameters

        Returns:
            Standardized response dict with success, agent_id, result_data
        """
        import asyncio

        # Extract task (Pipeline.router convention)
        task = kwargs.get("task", "")
        query_type = kwargs.get("query_type", "summary")
        customer_id = kwargs.get("customer_id", "")
        status_filter = kwargs.get("status_filter", "")

        # Parse task to determine query type if not explicit
        if task and not kwargs.get("query_type"):
            task_lower = task.lower()
            if any(
                kw in task_lower
                for kw in ["escalat", "d+1", "d+7", "d+14", "overdue alert"]
            ):
                query_type = "escalations"
            elif any(
                kw in task_lower
                for kw in [
                    "overdue downpayment",
                    "overdue dp",
                    "overdue advance",
                    "dp overdue",
                ]
            ):
                query_type = "downpayment_overdue"
            elif any(
                kw in task_lower
                for kw in [
                    "downpayment",
                    "down payment",
                    "dp alert",
                    "advance payment",
                    "deposit",
                    "prepay",
                ]
            ):
                query_type = "downpayment_alerts"
            elif any(
                kw in task_lower
                for kw in [
                    "payment status",
                    "payment progress",
                    "how much paid",
                    "payment history",
                ]
            ):
                query_type = "payment_status"
            elif any(
                kw in task_lower for kw in ["billing", "invoice", "pending billing"]
            ):
                query_type = "billing"
            elif any(kw in task_lower for kw in ["collection", "overdue", "aging"]):
                query_type = "collections"
            elif "aging" in task_lower:
                query_type = "aging"
            elif "payment term" in task_lower:
                query_type = "payment_terms"

        async def _execute():
            try:
                if not self._connected:
                    await self.connect()

                result = await self._execute(
                    customer_id=customer_id,
                    query_type=query_type,
                    status_filter=status_filter,
                )
                return {
                    "success": True,
                    "agent_id": self.agent_id,
                    "result_data": result,
                    "error_message": None,
                    "metadata": {"routing": "a2a_run", "query_type": query_type},
                }
            except Exception as e:
                return {
                    "success": False,
                    "agent_id": self.agent_id,
                    "result_data": {},
                    "error_message": str(e),
                    "metadata": {"routing": "a2a_run"},
                }

        # Handle async/sync context properly
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # No running loop - safe to use asyncio.run()
            return asyncio.run(_execute())
        else:
            # Already in async context - schedule coroutine and wait
            # Use new_event_loop in a thread to avoid nested loop issues
            import concurrent.futures

            def run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(_execute())
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=60)  # 60 second timeout

    @classmethod
    def get_signature(cls) -> type:
        """Get the signature class for this agent.

        Returns:
            BillingCollectionsSignature from signatures.py
        """
        return cls.SIGNATURE


# =============================================================================
# Factory Function
# =============================================================================


def create_billing_collections_agent(
    config: Optional[BillingCollectionsConfig] = None,
) -> BillingCollectionsAgent:
    """Create a BillingCollectionsAgent instance.

    Factory function for consistent agent instantiation.

    Args:
        config: Optional configuration

    Returns:
        Configured BillingCollectionsAgent instance
    """
    return BillingCollectionsAgent(config=config)
