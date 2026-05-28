"""
Due Diligence Agent

Customer validation agent that validates customer master data against SAP MS5.
Performs credit limit checks, payment term verification, and partner function validation.

MANDATORY GUIDE REFERENCE:
    For external partner/customer due diligence, this agent MUST follow:
    `src/lead_to_cash/docs/guides/KYP_guide.md`

    Key standards enforced:
    - Use evidence-based terminology for validation results
    - Status codes: NO_ADVERSE_FINDINGS, ADVERSE_FINDINGS, UNABLE_TO_VERIFY
    - NEVER assert positive attributes without SAP data
    - All findings MUST include data source (SAP MS5 field reference)

Architecture:
    - Built on Kaizen BaseAgent for production-ready agent features
    - Integrates with SAP MS5 via CPI middleware
    - Supports async operations for non-blocking I/O
    - Human-in-the-loop for credit limit overrides

Usage:
    from lead_to_cash.agents import DueDiligenceAgent, DueDiligenceConfig

    config = DueDiligenceConfig()
    agent = DueDiligenceAgent(config)

    result = await agent.validate_customer("1234567")
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from kaizen.core.base_agent import BaseAgent

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import KYPSignature
from lead_to_cash.integrations import MS5Client

logger = logging.getLogger(__name__)

# =============================================================================
# MANDATORY GUIDE REFERENCE
# =============================================================================
# For external partner/customer due diligence, follow the KYP guide.
# See: src/lead_to_cash/docs/guides/KYP_guide.md

KYP_GUIDE_PATH = "src/lead_to_cash/docs/guides/KYP_guide.md"

# Key requirements from guide:
# 1. Use evidence-based terminology
# 2. Status codes: NO_ADVERSE_FINDINGS, ADVERSE_FINDINGS, UNABLE_TO_VERIFY
# 3. NEVER assert positive attributes without data
# 4. All findings MUST include data source


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ValidationStatus(str, Enum):
    """Validation result status per KYP guide terminology."""

    NO_ADVERSE_FINDINGS = "no_adverse_findings"
    ADVERSE_FINDINGS = "adverse_findings"
    UNABLE_TO_VERIFY = "unable_to_verify"
    PENDING_APPROVAL = "pending_approval"
    # Legacy aliases kept for backward compat with cached results
    PASSED = "no_adverse_findings"
    FAILED = "adverse_findings"
    WARNING = "adverse_findings"


class PartnerFunctionType(str, Enum):
    """SAP Partner Function types."""

    SOLD_TO = "AG"  # Auftraggeber
    SHIP_TO = "WE"  # Warenempfanger
    BILL_TO = "RE"  # Rechnungsempfanger
    PAYER = "RG"  # Regulierer


@dataclass
class ValidationResult:
    """Structured validation result."""

    status: ValidationStatus
    customer_id: str
    customer_name: str
    checks: dict[str, dict[str, Any]]
    overall_score: float
    can_proceed: bool
    required_approvals: list[str]
    messages: list[str]
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "checks": self.checks,
            "overall_score": self.overall_score,
            "can_proceed": self.can_proceed,
            "required_approvals": self.required_approvals,
            "messages": self.messages,
            "validated_at": self.validated_at.isoformat(),
        }


# =============================================================================
# Signature Definition
# =============================================================================


class DueDiligenceSignature(Signature):
    """
    Signature for customer due diligence validation.

    Validates customer master data against SAP MS5 system including:
    - Customer existence and active status
    - Credit limit availability
    - Payment terms validity
    - Partner functions completeness
    """

    # Input Fields
    customer_id: str = InputField(description="SAP customer number (KUNNR) to validate")
    sales_org: str = InputField(description="Sales organization code", default="")
    order_value: float = InputField(
        description="Proposed order value for credit check", default=0.0
    )
    check_types: str = InputField(
        description="Comma-separated validation checks: master_data,credit,payment_terms,partner_functions",
        default="master_data,credit,payment_terms,partner_functions",
    )

    # Output Fields
    validation_status: str = OutputField(
        description="Overall validation status: passed, failed, warning, or pending_approval"
    )
    customer_name: str = OutputField(description="Customer name from SAP master data")
    validation_summary: str = OutputField(
        description="Human-readable summary of validation results"
    )
    can_proceed: str = OutputField(
        description="Whether order can proceed: yes, no, or requires_approval"
    )
    issues_found: str = OutputField(
        description="JSON array of issues found during validation"
    )
    recommendations: str = OutputField(
        description="Recommendations for resolving any issues"
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DueDiligenceConfig:
    """
    Configuration for Due Diligence Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_BASE_MODEL", "gpt-4")
    temperature: float = 0.3  # Low temperature for consistent validation
    max_tokens: int = 2000
    # Note: use_async_llm only works with OpenAI provider (not mock/test)
    # Our execute_a2a() pattern uses async domain methods directly instead

    # Validation Thresholds
    min_credit_buffer_percent: float = 10.0  # Minimum buffer required
    max_credit_utilization_percent: float = 90.0  # Max allowed utilization
    required_partner_functions: list[str] = field(
        default_factory=lambda: [
            "AG",
            "WE",
            "RE",
            "RG",
        ]  # Sold-to, Ship-to, Bill-to, Payer
    )

    # Business Rules
    auto_approve_under_value: float = 10000.0  # Auto-approve orders under this value
    require_credit_check_over: float = 50000.0  # Mandatory credit check threshold

    # Agent Metadata
    agent_name: str = "due_diligence_agent"
    agent_description: str = "Customer validation and credit assessment"

    # Integration Mode
    # When True, uses CPISimulator instead of real SAP CPI (default for dev/test)
    use_simulator: bool = True


# =============================================================================
# Due Diligence Agent Implementation
# =============================================================================


class DueDiligenceAgent(BaseAgent):
    """
    Customer Due Diligence Validation Agent (alias: KYPAgent).

    Part of the Intelligence Domain (ADR-002).

    Validates customer master data against SAP MS5 including:
    - Master data existence and completeness
    - Credit limit checks
    - Payment terms verification
    - Partner function validation (sold-to, ship-to, bill-to, payer)

    Features:
    - Async SAP MS5 integration via CPI middleware
    - Structured validation results
    - Human-in-the-loop for credit overrides
    - Shared memory for multi-agent coordination

    Example:
        config = DueDiligenceConfig()
        agent = DueDiligenceAgent(config)

        # Validate customer
        result = await agent.validate_customer(
            customer_id="1234567",
            order_value=75000.0
        )

        if result.can_proceed:
            print("Customer validated, can proceed with order")
        else:
            print(f"Issues: {result.messages}")
    """

    # A2A signature reference for capability matching (ADR-002)
    SIGNATURE = KYPSignature

    def __init__(
        self,
        config: DueDiligenceConfig,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
        ms5_client: Optional[MS5Client] = None,
        aravo_client: Optional[Any] = None,
    ):
        """
        Initialize Due Diligence Agent.

        Args:
            config: Agent configuration
            shared_memory: Shared memory pool for multi-agent coordination
            agent_id: Unique agent identifier
            ms5_client: Optional MS5 client instance for dependency injection
            aravo_client: Optional Aravo client for sanctions screening
        """
        super().__init__(
            config=config,
            signature=DueDiligenceSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
        )

        self.domain_config = config
        self._shared_memory = shared_memory  # Store for consistent access
        self._ms5_client = ms5_client
        self._ms5_connected = False
        self._aravo_client = aravo_client
        self._aravo_connected = False

        # Registry reference for A2A communication (set by AgentRegistry)
        self._registry: Optional[Any] = None

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
                name="customer_validation",
                domain="validation",
                level=CapabilityLevel.EXPERT,
                description="Validate customer master data against SAP MS5 system",
                keywords=[
                    "validate",
                    "customer",
                    "validation",
                    "master data",
                    "sap",
                    "ms5",
                    "check",
                    "verify",
                    "due diligence",
                ],
                examples=[
                    "Validate customer 1234567",
                    "Check if customer master data is complete",
                    "Verify customer exists in SAP",
                ],
                constraints=[],
            ),
            Capability(
                name="credit_check",
                domain="finance",
                level=CapabilityLevel.EXPERT,
                description="Check customer credit limit availability and exposure",
                keywords=[
                    "credit",
                    "credit limit",
                    "credit check",
                    "exposure",
                    "available credit",
                    "credit assessment",
                    "financial",
                ],
                examples=[
                    "Check credit limit for customer 1234567",
                    "Verify customer has sufficient credit",
                    "Credit assessment for order",
                ],
                constraints=[],
            ),
            Capability(
                name="payment_terms_validation",
                domain="finance",
                level=CapabilityLevel.ADVANCED,
                description="Verify payment terms are valid and configured",
                keywords=[
                    "payment",
                    "payment terms",
                    "terms",
                    "net 30",
                    "net 60",
                    "billing",
                    "invoice terms",
                ],
                examples=[
                    "Validate payment terms for customer",
                    "Check if payment terms are configured",
                ],
                constraints=[],
            ),
            Capability(
                name="partner_function_validation",
                domain="sap",
                level=CapabilityLevel.ADVANCED,
                description="Validate SAP partner functions (sold-to, ship-to, bill-to, payer)",
                keywords=[
                    "partner",
                    "partner function",
                    "sold-to",
                    "ship-to",
                    "bill-to",
                    "payer",
                    "AG",
                    "WE",
                    "RE",
                    "RG",
                ],
                examples=[
                    "Check partner functions for customer",
                    "Validate sold-to and ship-to assignments",
                ],
                constraints=[],
            ),
            Capability(
                name="sanctions_screening",
                domain="compliance",
                level=CapabilityLevel.EXPERT,
                description="Screen entities against sanctions and blacklists (OFAC, EU, UN, MAS)",
                keywords=[
                    "sanctions",
                    "screening",
                    "ofac",
                    "blacklist",
                    "compliance",
                    "sdn",
                    "eu sanctions",
                    "un sanctions",
                    "mas",
                    "aml",
                    "kyc",
                    "kyp",
                    "blocked",
                    "restricted",
                ],
                examples=[
                    "Screen entity for sanctions",
                    "Check if company is on OFAC SDN list",
                    "Run sanctions check for new customer",
                    "KYP sanctions screening",
                ],
                constraints=[],
            ),
        ]

    # -------------------------------------------------------------------------
    # SAP MS5 Client Management
    # -------------------------------------------------------------------------

    async def _get_ms5_client(self) -> MS5Client:
        """
        Get or create MS5 client with connection management.

        Returns:
            Connected MS5Client instance
        """
        if self._ms5_client is None:
            # No simulator — use real CPI via client factory
            from lead_to_cash.integrations.client_factory import get_cpi_client

            cpi_client, _ = await get_cpi_client(use_case="DueDiligence-MS5")
            if not cpi_client:
                logger.warning(
                    "DueDiligence: CPI not available — SAP data will be unavailable"
                )
                return None
            self._ms5_client = MS5Client(cpi_client=cpi_client)

        if not self._ms5_connected:
            await self._ms5_client.connect()
            self._ms5_connected = True
            mode = "real CPI"
            logger.info(f"MS5 client connected for due diligence (mode: {mode})")

        return self._ms5_client

    async def disconnect(self) -> None:
        """Disconnect from SAP MS5 and Aravo."""
        if self._ms5_client and self._ms5_connected:
            await self._ms5_client.disconnect()
            self._ms5_connected = False
            logger.info("MS5 client disconnected")

        if self._aravo_client and self._aravo_connected:
            await self._aravo_client.disconnect()
            self._aravo_connected = False
            logger.info("Aravo client disconnected")

    # -------------------------------------------------------------------------
    # Aravo Client Management (Sanctions Screening)
    # -------------------------------------------------------------------------

    async def _get_aravo_client(self) -> Any:
        """
        Get or create Aravo client with connection management.

        No simulator fallback — returns None if real Aravo is unavailable.

        Returns:
            Connected Aravo client instance or None
        """
        if self._aravo_client is None:
            from lead_to_cash.integrations.client_factory import get_aravo_client

            client, is_real = await get_aravo_client(use_case="DueDiligence")
            if not client:
                logger.warning("Aravo not available — TPRM screening will be skipped")
                return None
            self._aravo_client = client
            self._aravo_connected = True

        if not self._aravo_connected:
            await self._aravo_client.connect()
            self._aravo_connected = True
            logger.info("Aravo client connected for sanctions screening")

        return self._aravo_client

    async def screen_sanctions(
        self,
        entity_name: str,
        uen: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Screen entity against sanctions and blacklists.

        This method performs sanctions screening as part of KYP (Know Your Partner)
        due diligence. It checks the entity against OFAC, EU, UN, and MAS lists.

        Per KYP_guide.md terminology:
        - NO_ADVERSE_FINDINGS: Entity not found on any sanctions list
        - ADVERSE_FINDINGS: Entity found on sanctions list

        Args:
            entity_name: Name of entity to screen
            uen: Optional UEN/Tax ID for additional matching
            country: Optional country for jurisdiction-specific screening

        Returns:
            Screening result with:
            - status: "NO_ADVERSE_FINDINGS" or "ADVERSE_FINDINGS"
            - checked_lists: List of sanctions databases checked
            - matches: List of matches found (if any)
            - details: Additional screening details
        """
        logger.info(f"Screening entity '{entity_name}' for sanctions")

        aravo = await self._get_aravo_client()
        result = await aravo.screen_entity(
            entity_name=entity_name,
            uen=uen,
            country=country,
        )

        # Log result for audit trail
        if result.get("status") == "ADVERSE_FINDINGS":
            logger.warning(
                f"ADVERSE_FINDINGS for '{entity_name}': "
                f"{result.get('match_count', 0)} matches found"
            )
        else:
            logger.info(f"NO_ADVERSE_FINDINGS for '{entity_name}'")

        return result

    # -------------------------------------------------------------------------
    # Shared Memory Methods
    # -------------------------------------------------------------------------

    async def _check_memory_for_context(
        self,
        key: str,
        tags: List[str],
        max_age_seconds: float = 3600.0,  # 1 hour default TTL
    ) -> Optional[Dict[str, Any]]:
        """
        Check shared memory for relevant context before expensive operations.

        This method enables multi-agent coordination by allowing agents to
        share validation results and avoid redundant operations.

        Args:
            key: Identifier for logging (e.g., customer_id)
            tags: Tags to filter insights by
            max_age_seconds: Maximum age of cached results to consider valid

        Returns:
            Cached result content if found and valid, None otherwise
        """
        if not self._shared_memory:
            return None

        try:
            # Read relevant insights from other agents (exclude our own)
            results = self._shared_memory.read_relevant(
                agent_id=self.agent_id,
                tags=tags,
                min_importance=0.5,  # Only consider meaningful results
                max_age_seconds=max_age_seconds,
                exclude_own=False,  # Include our own previous results
                limit=1,
            )

            if results:
                insight = results[0]
                logger.info(
                    f"Memory hit for {key} from agent '{insight.get('agent_id')}'"
                )
                return insight.get("content")

        except Exception as e:
            logger.debug(f"Memory search failed for {key}: {e}")

        return None

    def _is_validation_cache_valid(
        self,
        cached: Dict[str, Any],
        customer_id: str,
    ) -> bool:
        """
        Validate that cached validation result is still usable.

        Args:
            cached: Cached validation result
            customer_id: Customer ID being validated

        Returns:
            True if cache is valid and can be used
        """
        # Check customer ID matches
        if cached.get("customer_id") != customer_id:
            return False

        # Check it was a successful validation (not an error)
        if cached.get("status") == "failed":
            return False

        # Cache is valid
        return True

    # -------------------------------------------------------------------------
    # A2A Agent Communication
    # -------------------------------------------------------------------------

    async def request_enrichment(
        self,
        capability: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Request enrichment from another agent with matching capability.

        This enables agent-to-agent collaboration by finding an agent with
        the requested capability and delegating work to it.

        Args:
            capability: Capability needed (e.g., "competitor_analysis",
                       "customer_matching", "industry_intel")
            data: Data to send to the enrichment agent. Should include:
                  - task: Description of what to do (used for routing)
                  - Any domain-specific parameters

        Returns:
            Enrichment result dict or None if no agent available

        Example:
            # Request competitor analysis from CompetitorIntelAgent
            result = await self.request_enrichment(
                capability="competitor_analysis",
                data={"task": "Analyze competitor presence", "query": "CAT marine"}
            )
        """
        if not self._registry:
            logger.warning(
                f"[{self.agent_id}] No registry configured for A2A communication"
            )
            return None

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
            if hasattr(matched_agent, "run"):
                result = matched_agent.run(task=data.get("task", ""), **data)

                # Handle async result
                if asyncio.iscoroutine(result):
                    result = await result

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

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    async def validate_customer(
        self,
        customer_id: str,
        sales_org: str = "",
        order_value: float = 0.0,
        check_types: Optional[list[str]] = None,
    ) -> ValidationResult:
        """
        Perform comprehensive customer validation.

        Args:
            customer_id: SAP customer number (KUNNR)
            sales_org: Sales organization code
            order_value: Proposed order value for credit check
            check_types: List of validation checks to perform

        Returns:
            ValidationResult with detailed check results
        """
        if check_types is None:
            check_types = [
                "master_data",
                "credit",
                "payment_terms",
                "partner_functions",
            ]

        logger.info(f"Starting due diligence for customer {customer_id}")

        # Check shared memory for cached validation result
        cached = await self._check_memory_for_context(
            key=customer_id,
            tags=["validation", "due_diligence", customer_id],
            max_age_seconds=3600.0,  # 1 hour cache TTL
        )

        if cached and self._is_validation_cache_valid(cached, customer_id):
            logger.info(f"Using cached validation for customer {customer_id}")
            return ValidationResult(
                status=ValidationStatus(cached["status"]),
                customer_id=cached["customer_id"],
                customer_name=cached.get("customer_name", ""),
                checks=cached.get("checks", {}),
                overall_score=cached.get("overall_score", 0.0),
                can_proceed=cached.get("can_proceed", False),
                required_approvals=cached.get("required_approvals", []),
                messages=cached.get("messages", []) + ["(from cache)"],
            )

        # Initialize result tracking
        checks: dict[str, dict[str, Any]] = {}
        messages: list[str] = []
        required_approvals: list[str] = []
        all_passed = True

        try:
            ms5 = await self._get_ms5_client()

            # Perform validation checks in parallel where possible
            tasks = []

            if "master_data" in check_types:
                tasks.append(("master_data", self._check_master_data(ms5, customer_id)))

            if "credit" in check_types:
                tasks.append(
                    ("credit", self._check_credit(ms5, customer_id, order_value))
                )

            if "partner_functions" in check_types:
                tasks.append(
                    (
                        "partner_functions",
                        self._check_partner_functions(ms5, customer_id, sales_org),
                    )
                )

            # Execute checks concurrently
            results = await asyncio.gather(
                *[task[1] for task in tasks], return_exceptions=True
            )

            # Process results
            customer_name = ""
            for i, (check_name, _) in enumerate(tasks):
                result = results[i]

                if isinstance(result, Exception):
                    checks[check_name] = {
                        "passed": False,
                        "error": str(result),
                    }
                    messages.append(f"{check_name}: Error - {str(result)}")
                    all_passed = False
                else:
                    checks[check_name] = result

                    if check_name == "master_data" and result.get("passed"):
                        customer_name = result.get("customer_name", "")

                    if not result.get("passed", False):
                        all_passed = False
                        if result.get("message"):
                            messages.append(result["message"])

                    if result.get("requires_approval"):
                        required_approvals.extend(result.get("approval_types", []))

            # Payment terms check (requires master data)
            if "payment_terms" in check_types and "master_data" in checks:
                master_data = checks.get("master_data", {})
                if master_data.get("passed"):
                    payment_check = self._check_payment_terms(
                        master_data.get("payment_terms", "")
                    )
                    checks["payment_terms"] = payment_check
                    if not payment_check.get("passed", False):
                        all_passed = False
                        if payment_check.get("message"):
                            messages.append(payment_check["message"])

            # Calculate overall score
            passed_count = sum(1 for c in checks.values() if c.get("passed", False))
            overall_score = passed_count / len(checks) if checks else 0.0

            # Determine final status
            if all_passed:
                status = ValidationStatus.NO_ADVERSE_FINDINGS
                can_proceed = True
            elif required_approvals:
                status = ValidationStatus.PENDING_APPROVAL
                can_proceed = False
            elif overall_score >= 0.5:
                status = ValidationStatus.ADVERSE_FINDINGS
                can_proceed = True  # Can proceed with caution
            else:
                status = ValidationStatus.ADVERSE_FINDINGS
                can_proceed = False

            # A2A Enrichment: Request customer matching for alternative identities
            # This demonstrates actual A2A agent communication
            if customer_name and self._registry:
                try:
                    enrichment = await self.request_enrichment(
                        capability="customer_matching",
                        data={
                            "task": f"Find alternative identities for customer: {customer_name}",
                            "customer_name": customer_name,
                            "customer_id": customer_id,
                        },
                    )
                    if enrichment and enrichment.get("success"):
                        # CustomerMatcherAgent returns: result_data.match_result.candidates
                        result_data = enrichment.get("result_data", {})
                        match_result = result_data.get("match_result", {})
                        candidates = match_result.get("candidates", [])
                        best_match = match_result.get("best_match")

                        if candidates or best_match:
                            checks["customer_matching"] = {
                                "passed": True,
                                "alternative_identities": candidates,
                                "best_match": best_match,
                                "message": f"Found {len(candidates)} potential match(es)",
                            }
                            logger.info(
                                f"A2A enrichment found {len(candidates)} alternative identities for {customer_name}"
                            )
                except Exception as e:
                    # Enrichment is optional - don't fail validation if it fails
                    logger.debug(
                        f"Customer matching enrichment failed (non-critical): {e}"
                    )

            # Use LLM for intelligent summary if needed
            if messages:
                llm_result = self.run(
                    customer_id=customer_id,
                    sales_org=sales_org,
                    order_value=order_value,
                    check_types=",".join(check_types),
                )
                if llm_result.get("recommendations"):
                    messages.append(f"Recommendation: {llm_result['recommendations']}")

            result = ValidationResult(
                status=status,
                customer_id=customer_id,
                customer_name=customer_name,
                checks=checks,
                overall_score=overall_score,
                can_proceed=can_proceed,
                required_approvals=required_approvals,
                messages=messages,
            )

            # Write to shared memory for other agents (if available)
            if self._shared_memory:
                self.write_to_memory(
                    content=result.to_dict(),
                    tags=["validation", "due_diligence", customer_id],
                    importance=0.9 if not can_proceed else 0.7,
                )

            logger.info(
                f"Due diligence completed for {customer_id}: "
                f"status={status.value}, can_proceed={can_proceed}"
            )

            return result

        except Exception as e:
            logger.error(f"Due diligence failed for {customer_id}: {e}")
            return ValidationResult(
                status=ValidationStatus.UNABLE_TO_VERIFY,
                customer_id=customer_id,
                customer_name="",
                checks={"error": {"passed": False, "error": str(e)}},
                overall_score=0.0,
                can_proceed=False,
                required_approvals=[],
                messages=[f"Validation failed: {str(e)}"],
            )

    async def _check_master_data(
        self,
        ms5: MS5Client,
        customer_id: str,
    ) -> dict[str, Any]:
        """
        Check customer master data exists and is complete.

        Args:
            ms5: Connected MS5 client
            customer_id: SAP customer number

        Returns:
            Check result dictionary
        """
        try:
            customer = await ms5.get_customer(customer_id)

            # Validate required fields
            missing_fields = []
            if not customer.name:
                missing_fields.append("name")
            if not customer.address or not customer.address.get("country"):
                missing_fields.append("address")

            if missing_fields:
                return {
                    "passed": False,
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                    "customer_name": customer.name,
                    "missing_fields": missing_fields,
                }

            return {
                "passed": True,
                "customer_name": customer.name,
                "address": customer.address,
                "payment_terms": customer.payment_terms,
            }

        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "message": f"Failed to retrieve customer data: {e}",
            }

    async def _check_credit(
        self,
        ms5: MS5Client,
        customer_id: str,
        order_value: float,
    ) -> dict[str, Any]:
        """
        Check customer credit limit and availability.

        Args:
            ms5: Connected MS5 client
            customer_id: SAP customer number
            order_value: Proposed order value

        Returns:
            Check result dictionary
        """
        try:
            credit_info = await ms5.check_credit_limit(customer_id)

            credit_limit = credit_info.get("credit_limit", 0)
            available_credit = credit_info.get("available_credit", 0)
            credit_passed = credit_info.get("credit_check_passed", False)

            # Calculate utilization
            if credit_limit > 0:
                utilization = ((credit_limit - available_credit) / credit_limit) * 100
            else:
                utilization = 100.0  # No credit limit set

            # Check if order would exceed available credit
            order_exceeds = order_value > available_credit if order_value > 0 else False

            # Apply business rules
            requires_approval = False
            approval_types = []

            if order_exceeds:
                requires_approval = True
                approval_types.append("credit_override")

            if utilization > self.domain_config.max_credit_utilization_percent:
                requires_approval = True
                approval_types.append("high_utilization")

            # Auto-approve for small orders
            if order_value <= self.domain_config.auto_approve_under_value:
                requires_approval = False
                approval_types = []

            passed = credit_passed and not order_exceeds

            return {
                "passed": passed,
                "credit_limit": credit_limit,
                "available_credit": available_credit,
                "credit_exposure": credit_info.get("credit_exposure", 0),
                "utilization_percent": utilization,
                "order_value": order_value,
                "order_would_exceed": order_exceeds,
                "requires_approval": requires_approval,
                "approval_types": approval_types,
                "message": self._get_credit_message(
                    passed, order_exceeds, utilization, order_value, available_credit
                ),
            }

        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "message": f"Credit check failed: {e}",
            }

    def _get_credit_message(
        self,
        passed: bool,
        order_exceeds: bool,
        utilization: float,
        order_value: float,
        available_credit: float,
    ) -> str:
        """Generate human-readable credit check message."""
        if passed:
            return f"Credit check passed. Available credit: {available_credit:,.2f}"

        messages = []
        if order_exceeds:
            shortfall = order_value - available_credit
            messages.append(
                f"Order value ({order_value:,.2f}) exceeds available credit "
                f"({available_credit:,.2f}) by {shortfall:,.2f}"
            )
        if utilization > self.domain_config.max_credit_utilization_percent:
            messages.append(
                f"Credit utilization ({utilization:.1f}%) exceeds threshold "
                f"({self.domain_config.max_credit_utilization_percent:.1f}%)"
            )

        return "; ".join(messages) if messages else "Credit check failed"

    async def _check_partner_functions(
        self,
        ms5: MS5Client,
        customer_id: str,
        sales_org: str,
    ) -> dict[str, Any]:
        """
        Check partner functions are properly assigned.

        Args:
            ms5: Connected MS5 client
            customer_id: SAP customer number
            sales_org: Sales organization

        Returns:
            Check result dictionary
        """
        try:
            partners = await ms5.get_partner_functions(customer_id, sales_org)

            # Check for required partner functions
            assigned_functions = {p.get("function", ""): p for p in partners}
            required = self.domain_config.required_partner_functions
            missing = [f for f in required if f not in assigned_functions]

            # Map function codes to names for readability
            function_names = {
                "AG": "Sold-to Party",
                "WE": "Ship-to Party",
                "RE": "Bill-to Party",
                "RG": "Payer",
            }

            if missing:
                missing_names = [function_names.get(f, f) for f in missing]
                return {
                    "passed": False,
                    "assigned_functions": list(assigned_functions.keys()),
                    "missing_functions": missing,
                    "message": f"Missing partner functions: {', '.join(missing_names)}",
                }

            return {
                "passed": True,
                "assigned_functions": list(assigned_functions.keys()),
                "partner_details": partners,
            }

        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "message": f"Partner function check failed: {e}",
            }

    def _check_payment_terms(self, payment_terms: Optional[str]) -> dict[str, Any]:
        """
        Validate payment terms are set and valid.

        Args:
            payment_terms: Payment terms code from SAP

        Returns:
            Check result dictionary
        """
        if not payment_terms:
            return {
                "passed": False,
                "message": "No payment terms defined for customer",
            }

        # Valid payment terms (example - adjust to your SAP config)
        valid_terms = {"NT30", "NT45", "NT60", "NT90", "0001", "0002", "Z001", "Z002"}

        if payment_terms in valid_terms:
            return {
                "passed": True,
                "payment_terms": payment_terms,
            }
        else:
            return {
                "passed": True,  # Unknown terms don't block, just warn
                "payment_terms": payment_terms,
                "warning": f"Uncommon payment terms: {payment_terms}",
            }

    # -------------------------------------------------------------------------
    # A2A Router Compatibility
    # -------------------------------------------------------------------------

    async def _run_validation_task(
        self,
        customer_id: str,
        sales_org: str,
        order_value: float,
    ) -> dict[str, Any]:
        """Async helper for validation task execution.

        Called when run() is invoked from an async context (FastAPI).
        Returns formatted results after completing validation.

        Args:
            customer_id: SAP customer ID
            sales_org: Sales organization code
            order_value: Order value for credit check

        Returns:
            Formatted validation results dict
        """
        result = await self.validate_customer(customer_id, sales_org, order_value)
        return self._format_validation_response(result)

    def _format_validation_response(self, result: ValidationResult) -> dict[str, Any]:
        """Format ValidationResult into API response structure.

        Args:
            result: ValidationResult from validate_customer

        Returns:
            Formatted response dict for signature output
        """
        return {
            "validation_status": result.status.value,
            "customer_name": result.customer_name,
            "validation_summary": f"Validation {result.status.value}: {'; '.join(result.messages) if result.messages else 'No issues'}",
            "can_proceed": (
                "yes"
                if result.can_proceed
                else ("requires_approval" if result.required_approvals else "no")
            ),
            "issues_found": json.dumps(result.messages),
            "recommendations": (
                f"Required approvals: {', '.join(result.required_approvals)}"
                if result.required_approvals
                else "None required"
            ),
        }

    def _extract_customer_id(self, task: str, customer_id: str) -> Optional[str]:
        """Extract customer ID from task string or return provided ID.

        Args:
            task: Task description that may contain customer ID
            customer_id: Explicitly provided customer ID

        Returns:
            Extracted or provided customer ID, or None if not found
        """
        import re

        if customer_id:
            return customer_id

        if task:
            # Look for SAP customer ID pattern (7-10 digits)
            match = re.search(r"\b(\d{7,10})\b", task)
            if match:
                return match.group(1)

        return None

    async def execute_a2a(self, **kwargs: Any) -> dict[str, Any]:
        """Custom async domain method for A2A enrichment calls.

        NOTE: This is a CUSTOM method, NOT a Kaizen-native pattern.
        Kaizen's A2A (via to_a2a_card()) is for agent discovery, not execution.

        This method provides direct domain logic execution for inter-agent
        enrichment without the overhead of Kaizen's LLM/memory/hooks features.
        For signature-based execution with full Kaizen features, use run_async().

        Entry Points:
            - run() → Sync entry point, calls validate_customer directly
            - run_async() → Kaizen native, uses signatures/memory/hooks (inherited)
            - execute_a2a() → Custom async domain method (this method)

        Args:
            **kwargs: Validation parameters (customer_id/task, sales_org, order_value)

        Returns:
            Standardized A2A response dict with validation results
        """
        task = kwargs.get("task", "")
        customer_id = self._extract_customer_id(task, kwargs.get("customer_id", ""))
        sales_org = kwargs.get("sales_org", "")
        order_value = kwargs.get("order_value", 0.0)

        if not customer_id:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {
                    "validation_status": "failed",
                    "customer_name": "",
                    "validation_summary": "Customer ID required for validation",
                    "can_proceed": "no",
                    "issues_found": '["No customer ID provided"]',
                    "recommendations": "Please provide a valid SAP customer ID (7-10 digit number)",
                },
                "error_message": "No customer ID provided",
                "metadata": {"routing": "a2a_run_async"},
            }

        logger.info(f"DueDiligenceAgent.execute_a2a() - customer_id: {customer_id}")

        try:
            result = await self.validate_customer(customer_id, sales_org, order_value)
            return {
                "success": True,
                "agent_id": self.agent_id,
                "result_data": self._format_validation_response(result),
                "error_message": None,
                "metadata": {"routing": "a2a_run_async", "customer_id": customer_id},
            }
        except Exception as e:
            logger.error(f"DueDiligenceAgent.execute_a2a() failed: {e}")
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": str(e),
                "metadata": {"routing": "a2a_run_async"},
            }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous entry point for CLI/tests and A2A calls.

        This is the standard entry point for inter-agent communication.
        Uses domain-specific logic (validate_customer) without LLM/memory overhead.

        For signature-based execution with Kaizen features (memory, hooks, LLM),
        use the inherited run_async() method instead.

        Args:
            **kwargs: Validation parameters (customer_id/task, sales_org, order_value)

        Returns:
            Validation results (legacy format for backward compatibility)
        """
        task = kwargs.get("task", "")
        customer_id = self._extract_customer_id(task, kwargs.get("customer_id", ""))
        sales_org = kwargs.get("sales_org", "")
        order_value = kwargs.get("order_value", 0.0)

        if not customer_id:
            return {
                "validation_status": "failed",
                "customer_name": "",
                "validation_summary": "Customer ID required for validation",
                "can_proceed": "no",
                "issues_found": '["No customer ID provided"]',
                "recommendations": "Please provide a valid SAP customer ID",
            }

        logger.info(f"DueDiligenceAgent.run() - customer_id: {customer_id}")

        result = asyncio.run(
            self.validate_customer(customer_id, sales_org, order_value)
        )

        # Convert ValidationResult to signature output format
        return self._format_validation_response(result)

    # -------------------------------------------------------------------------
    # Quick Validation Methods
    # -------------------------------------------------------------------------

    async def quick_credit_check(
        self,
        customer_id: str,
        order_value: float,
    ) -> tuple[bool, str]:
        """
        Perform quick credit check only.

        Args:
            customer_id: SAP customer number
            order_value: Proposed order value

        Returns:
            Tuple of (passed, message)
        """
        ms5 = await self._get_ms5_client()
        result = await self._check_credit(ms5, customer_id, order_value)

        return result.get("passed", False), result.get("message", "")

    async def check_customer_exists(self, customer_id: str) -> tuple[bool, str]:
        """
        Quick check if customer exists in SAP.

        Args:
            customer_id: SAP customer number

        Returns:
            Tuple of (exists, customer_name)
        """
        ms5 = await self._get_ms5_client()
        result = await self._check_master_data(ms5, customer_id)

        if result.get("passed"):
            return True, result.get("customer_name", "")
        return False, ""

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        Check agent health and SAP connectivity.

        Returns:
            Health status with agent_id, status, capabilities, and connectivity info
        """
        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        # Check SAP MS5 connectivity
        ms5_connected = False
        try:
            ms5 = await self._get_ms5_client()
            ms5_health = await ms5.health_check()
            ms5_connected = ms5_health.get("connected", False)
        except Exception:
            pass

        status = "healthy" if ms5_connected else "degraded"

        return {
            "agent_id": self.agent_id,
            "status": status,
            "capabilities": capabilities,
            "ms5_connected": ms5_connected,
            "shared_memory_available": self._shared_memory is not None,
        }

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "DueDiligenceAgent":
        """Async context manager entry."""
        await self._get_ms5_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
