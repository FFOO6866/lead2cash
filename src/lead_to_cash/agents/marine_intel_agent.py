"""
Marine Sales Intelligence Agent

Kaizen-based AI agent for daily research and identification of RRPS marine engine
sales opportunities in Singapore and Asia-Pacific markets.

MANDATORY GUIDE REFERENCE:
    This agent MUST follow the standardized output format defined in:
    `src/lead_to_cash/docs/guides/sales_intelligence_agent_guide.md`

    Key standards enforced (from unified guide):
    - Context & Identity: We are RRPS, "we" always means RRPS (Section 1)
    - Multi-Angle Analysis: Product Fit, Customer Intel, Competitor Threat,
      Risk Signal, Relationship (Section 4)
    - Output Standards: Source URL, confidence level, recommended action (Section 5)
    - KB enrichment for product fit analysis (Section 2.2)
    - MCP/SAP integration for customer relationship check (Section 2.4)

    Anti-Hallucination Rules (Section 5.1):
    - ONLY report facts explicitly stated in source documents
    - NEVER estimate contract values - use "Not disclosed"
    - NEVER guess engine types - use "Not specified"
    - All findings MUST include verifiable source URL

    Market/Industry Intel Requirements (Section 5.2):
    - Priority scoring (1-10) with rationale
    - Our Product Fit analysis (query KB for MTU series match)
    - Customer Impact assessment (check MCP for relationship)
    - Competitor Angle (are competitors involved?)
    - Timeline & Action for priority 6+ opportunities

Architecture:
    - Built on Kaizen BaseAgent for production-ready agent features
    - Integrates with Perplexity API for web research
    - Uses LLM for structured extraction of opportunities
    - PostgreSQL storage with URL hash-based deduplication
    - Supports daily automated research jobs

Usage:
    from lead_to_cash.agents import MarineIntelAgent, MarineIntelConfig

    config = MarineIntelConfig()
    agent = MarineIntelAgent(config)

    # Run daily research
    result = await agent.run_daily_research()

    # Or run specific query
    opportunities = await agent.research_query("newbuild ferry Singapore")
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

import httpx
from kaizen.core.base_agent import BaseAgent
from kaizen.core.structured_output import create_structured_output_config
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import IndustryIntelSignature
from lead_to_cash.services.marine_intel.database import get_marine_intel_db
from lead_to_cash.services.marine_intel.models import (
    QUERY_PATTERNS,
    MarineOpportunity,
    Region,
    Sector,
    SourceCategory,
    VesselType,
)
from lead_to_cash.utils.resilience import CircuitBreaker, retry_with_backoff

# KB Integration (optional - may not be initialized)
try:
    from lead_to_cash.services.knowledge_base.integration import (
        KBIntegrationService,
        get_kb_integration_service,
    )

    KB_AVAILABLE = True
except ImportError:
    KB_AVAILABLE = False
    KBIntegrationService = None

logger = logging.getLogger(__name__)

# =============================================================================
# MANDATORY GUIDE REFERENCE
# =============================================================================
# All output from this agent MUST comply with the unified sales intelligence guide.
# See: src/lead_to_cash/docs/guides/sales_intelligence_agent_guide.md

SALES_INTEL_GUIDE_PATH = (
    "src/lead_to_cash/docs/guides/sales_intelligence_agent_guide.md"
)

# Key requirements from unified guide:
# 1. Context & Identity (Section 1): "we" = RRPS, sales ops assistant
# 2. Multi-Angle Analysis (Section 4): Product Fit, Customer, Competitor, Risk, Relationship
# 3. Output Standards (Section 5): Source URL, confidence, action recommended
# 4. Anti-Hallucination (Section 5.1):
#    - Every finding MUST include source URL
#    - NEVER estimate values - use "Not disclosed"
#    - NEVER guess specifications - use "Not specified"
#    - Confidence < 0.7 requires verification
# 5. Market/Industry Intel (Section 5.2):
#    - Priority 1-10 scale
#    - Our Product Fit (query KB)
#    - Customer Impact (check MCP/SAP)
#    - Competitor Angle (threat assessment)
#    - Timeline & Action for priority 6+
# 6. Always query KB for product fit analysis (Section 2.2)
# 7. Always check MCP/SAP for customer relationship (Section 2.4)


# =============================================================================
# Signature Definition
# =============================================================================


class MarineIntelSignature(Signature):
    """
    Signature for marine sales intelligence extraction.

    Takes raw research content and extracts structured sales opportunities
    with classification, analysis, and recommended actions.
    """

    # Input Fields
    raw_content: str = InputField(
        description="Raw research content from Perplexity API containing news, announcements, or industry updates"
    )
    query_context: str = InputField(
        description="The research query that generated this content (e.g., 'newbuild ferry Singapore')",
        default="",
    )
    source_urls: str = InputField(
        description="JSON array of source URLs from the research",
        default="[]",
    )

    # Output Fields
    opportunities: str = OutputField(
        description="""JSON array of extracted opportunities. Each opportunity must have:
- headline: Concise headline (max 100 chars)
- published_date: Article publication date in YYYY-MM-DD format. Extract from article text, byline, or dateline. Use null if unknown.
- source_url: Primary source URL
- companies_involved: Array of company names mentioned
- country: Primary country (Singapore, Indonesia, Malaysia, etc.)
- vessel_type: Type of vessel (ferry, tug, osv, fpso, etc.)
- sales_signals: Array of applicable signals (newbuild, retrofit_repower, offshore_project, regulation, fuel_transition, fleet_expansion, incident_reliability, financing_capex)
- sales_explanation: Why this matters for RRPS engine sales (2-3 sentences)
- suggested_action: Specific recommended sales action
- priority: 1-10 (10 being highest priority for immediate sales action)"""
    )
    summary: str = OutputField(
        description="Brief summary of key findings (2-3 sentences)"
    )
    total_opportunities: str = OutputField(
        description="Number of distinct opportunities found"
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class MarineIntelConfig:
    """
    Configuration for Marine Intelligence Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration - Using GPT-4o with Structured Outputs for guaranteed schema
    llm_provider: str = "openai"
    model: str = os.getenv(
        "OPENAI_STRUCTURED_MODEL", "gpt-4o-2024-08-06"
    )  # Required for strict structured outputs
    temperature: float = 0.2  # Lower for consistent extraction
    max_tokens: int = 4000
    use_structured_output: bool = True  # Enable OpenAI structured outputs
    # Note: use_async_llm only works with OpenAI provider (not mock/test)
    # Our execute_a2a() pattern uses async domain methods directly instead

    # Research Configuration
    max_queries_per_category: int = 3  # Max queries to run per category
    min_priority_threshold: int = 5  # Minimum priority to save
    enable_deduplication: bool = True

    # Perplexity API Configuration
    perplexity_model: str = "sonar"  # sonar or sonar-pro
    perplexity_timeout: int = 90

    # Rate Limiting
    delay_between_queries: float = 2.0  # Seconds between API calls
    max_concurrent_queries: int = 3

    # KB Integration
    enable_kb_enrichment: bool = True  # Enable KB entity enrichment

    # A2A Enrichment
    max_enrichment_opportunities: int = (
        5  # Max opportunities to enrich with competitor intel
    )

    # Agent Metadata
    agent_name: str = "marine_intel_agent"
    agent_description: str = (
        "Marine sales intelligence research and opportunity identification"
    )

    # Priority Regions (higher research frequency)
    priority_regions: list[str] = field(
        default_factory=lambda: [
            "singapore",
            "indonesia",
            "malaysia",
            "thailand",
            "vietnam",
        ]
    )

    # Priority Sectors
    priority_sectors: list[str] = field(
        default_factory=lambda: [
            "marine_transportation",
            "offshore_oil_gas",
            "marine_engineering",
        ]
    )


# =============================================================================
# Marine Intelligence Agent Implementation
# =============================================================================


class MarineIntelAgent(BaseAgent):
    """
    Marine Sales Intelligence Agent (alias: IndustryIntelAgent).

    Performs daily research to identify RRPS marine engine sales opportunities
    by monitoring trade publications, regulatory announcements, and shipyard news.

    Part of the Intelligence Domain (ADR-002).

    Capabilities:
    - Newbuild vessel orders and shipyard contracts
    - Repower/retrofit opportunities
    - Offshore oil & gas project sanctions
    - Fuel transition and emissions compliance
    - Fleet expansion announcements
    - Incident-driven replacement opportunities

    Features:
    - Perplexity API integration for web research
    - LLM-powered structured extraction
    - URL hash-based deduplication
    - Priority scoring for sales relevance
    - Shared memory for multi-agent coordination

    Example:
        config = MarineIntelConfig()
        agent = MarineIntelAgent(config)

        # Daily research job
        result = await agent.run_daily_research()
        print(f"Found {result['opportunities_found']} opportunities")

        # Specific research query
        opps = await agent.research_query("FPSO contract Indonesia")
        for opp in opps:
            print(f"{opp.headline} - Priority: {opp.priority}")
    """

    # System prompt for Perplexity queries
    PERPLEXITY_SYSTEM_PROMPT = """You are a marine industry research analyst for Rolls-Royce Power Systems (RRPS).

Your role is to identify sales opportunities for marine engines in the following areas:
1. New vessel construction (newbuilds) requiring propulsion systems
2. Engine repowering and retrofit projects
3. Offshore oil & gas projects requiring vessel support
4. Fuel transition projects (LNG, methanol, ammonia, dual-fuel)
5. Fleet expansion by ferry operators, port authorities, offshore companies
6. Engine reliability issues creating replacement opportunities

Focus on: Singapore, Indonesia, Malaysia, Thailand, Vietnam, Philippines, Australia, China, Korea, Japan, India

Key sources to prioritize:
- MPA Singapore, Singapore Maritime Foundation, SSA, ASMI
- Maritime Executive, Seatrade Maritime, Splash247, TradeWinds, Lloyd's List
- Offshore Engineer, Asian Oil & Gas, Upstream Online
- Seatrium, PaxOcean, ASL Marine, Penguin Shipyard announcements

For each finding, provide:
- Specific company/customer names
- Contract values if disclosed
- Vessel types and quantities
- Timeline and project status
- Why this is relevant for marine engine sales"""

    # A2A signature reference for capability matching (ADR-002)
    SIGNATURE = IndustryIntelSignature

    def __init__(
        self,
        config: MarineIntelConfig,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize Marine Intelligence Agent.

        Args:
            config: Agent configuration
            shared_memory: Optional shared memory pool for multi-agent coordination
            agent_id: Unique agent identifier
        """
        # Create signature instance
        signature = MarineIntelSignature()

        # Enable OpenAI Structured Outputs for guaranteed schema compliance
        provider_config = None
        if getattr(config, "use_structured_output", False):
            try:
                provider_config = create_structured_output_config(
                    signature=signature,
                    strict=True,  # 100% schema compliance
                    name="marine_intel_opportunities",
                )
                logger.info("Enabled OpenAI Structured Outputs (strict mode)")
            except Exception as e:
                logger.warning(f"Failed to enable structured outputs: {e}")

        # Inject provider_config into config if created
        if provider_config:
            # Create modified config with provider_config
            config.provider_config = provider_config

        super().__init__(
            config=config,
            signature=signature,
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
        )

        self._shared_memory = shared_memory  # Store for consistent access
        self.domain_config = config
        self.db = get_marine_intel_db()
        self._perplexity_client: Optional[httpx.AsyncClient] = None
        self._perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")

        # Circuit breaker for Perplexity API
        # Opens after 5 failures, recovers after 60 seconds
        self._perplexity_circuit = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3,
        )

        # KB Integration for entity enrichment
        self._kb_service: Optional["KBIntegrationService"] = None
        if KB_AVAILABLE and config.enable_kb_enrichment:
            try:
                self._kb_service = get_kb_integration_service()
                logger.info("KB enrichment service initialized for MarineIntelAgent")
            except Exception as e:
                logger.warning(f"KB service initialization failed: {e}")

        # Registry for A2A agent-to-agent communication
        self._registry: Optional[Any] = None

        # A2A enrichment metrics for observability
        self._enrichment_success_count = 0
        self._enrichment_failure_count = 0
        self._enrichment_skip_count = 0  # Opportunities without companies

    def get_enrichment_metrics(self) -> dict[str, Any]:
        """Get A2A enrichment metrics for monitoring.

        Returns:
            Dict with success/failure counts and success rate
        """
        total = self._enrichment_success_count + self._enrichment_failure_count
        return {
            "enrichment_success": self._enrichment_success_count,
            "enrichment_failure": self._enrichment_failure_count,
            "enrichment_skipped": self._enrichment_skip_count,
            "enrichment_total_attempts": total,
            "enrichment_success_rate": (self._enrichment_success_count / max(1, total)),
        }

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
                name="marine_research",
                domain="marine_intelligence",
                level=CapabilityLevel.EXPERT,
                description="Marine sales intelligence research for RRPS engine opportunities in Asia-Pacific",
                keywords=[
                    "marine",
                    "vessel",
                    "ship",
                    "shipyard",
                    "ferry",
                    "tug",
                    "offshore",
                    "maritime",
                    "newbuild",
                    "repower",
                    "retrofit",
                    "engine",
                    "propulsion",
                ],
                examples=[
                    "Research newbuild ferry opportunities in Singapore",
                    "Find offshore vessel contracts in Indonesia",
                    "Search for marine engine sales opportunities",
                ],
                constraints=[],
            ),
            Capability(
                name="opportunity_identification",
                domain="sales_intelligence",
                level=CapabilityLevel.EXPERT,
                description="Identify marine engine sales opportunities from news and announcements",
                keywords=[
                    "opportunity",
                    "sales",
                    "lead",
                    "newbuild",
                    "repower",
                    "retrofit",
                    "contract",
                    "order",
                    "fleet",
                    "expansion",
                ],
                examples=[
                    "Identify sales opportunities in Southeast Asia",
                    "Find vessel orders requiring engines",
                    "Search for fleet expansion announcements",
                ],
                constraints=[],
            ),
            Capability(
                name="offshore_intelligence",
                domain="offshore_oil_gas",
                level=CapabilityLevel.ADVANCED,
                description="Track offshore oil & gas projects requiring vessel support",
                keywords=[
                    "offshore",
                    "fpso",
                    "osv",
                    "ahts",
                    "psv",
                    "oil",
                    "gas",
                    "project",
                    "sanction",
                    "platform",
                ],
                examples=[
                    "Find FPSO contracts in Asia Pacific",
                    "Track offshore project sanctions",
                    "Search for OSV requirements",
                ],
                constraints=[],
            ),
        ]

    def set_registry(self, registry: Any) -> None:
        """Set the agent registry for A2A communication.

        Called by the registry after registration to enable agent-to-agent
        collaboration via request_enrichment().

        Args:
            registry: AgentRegistry instance
        """
        self._registry = registry
        logger.debug(f"[{self.agent_id}] Registry reference set for A2A communication")

    async def request_enrichment(
        self,
        capability: str,
        data: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Request enrichment from another agent with matching capability.

        Enables agent-to-agent collaboration by finding an agent with
        the requested capability and delegating work to it.

        Args:
            capability: Capability needed (e.g., "competitor_intel", "customer_validation")
            data: Data to send to the enrichment agent. Should include:
                  - task: Description of what to do (used for routing)
                  - Any domain-specific parameters

        Returns:
            Enrichment result dict or None if no agent available
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

        # Execute enrichment request using standard Kaizen patterns
        # Priority: run() (standard sync entry point) with async handling
        try:
            if hasattr(matched_agent, "run"):
                # Standard Kaizen pattern: use run() as the primary entry point
                # For domain-specific A2A calls that don't need LLM/memory features
                result = matched_agent.run(task=data.get("task", ""), **data)
                # Handle if run() returns coroutine (shouldn't normally, but be safe)
                if asyncio.iscoroutine(result):
                    result = await result
            else:
                logger.warning(
                    f"[{self.agent_id}] Agent {matched_agent_id} has no run() method"
                )
                return None

            if not isinstance(result, dict):
                result = {"result": result}

            logger.info(
                f"[{self.agent_id}] Enrichment from {matched_agent_id}: "
                f"success={result.get('success', 'unknown')}"
            )
            return result

        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Enrichment request to {matched_agent_id} failed: {e}"
            )
            return None

    # -------------------------------------------------------------------------
    # HTTP Client Management
    # -------------------------------------------------------------------------

    async def _get_perplexity_client(self) -> httpx.AsyncClient:
        """Get or create Perplexity HTTP client."""
        if self._perplexity_client is None:
            self._perplexity_client = httpx.AsyncClient(
                timeout=self.domain_config.perplexity_timeout
            )
        return self._perplexity_client

    async def close(self) -> None:
        """Close HTTP client and database connections."""
        if self._perplexity_client:
            await self._perplexity_client.aclose()
            self._perplexity_client = None

    # -------------------------------------------------------------------------
    # Perplexity API Integration
    # -------------------------------------------------------------------------

    async def _query_perplexity(
        self,
        query: str,
        system_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Query Perplexity API for marine industry research.

        Features:
        - Circuit breaker protection (opens after 5 failures)
        - Automatic retry with exponential backoff
        - Comprehensive error logging

        Args:
            query: Research query string
            system_prompt: Optional custom system prompt

        Returns:
            Dict with 'content', 'sources', and optional 'error'
        """
        if not self._perplexity_api_key:
            logger.warning("PERPLEXITY_API_KEY not configured")
            return {"content": "", "sources": [], "error": "API key not configured"}

        # Check circuit breaker
        if not self._perplexity_circuit.can_execute():
            circuit_state = self._perplexity_circuit.state
            logger.warning(
                f"Circuit breaker OPEN - Perplexity API calls blocked (state={circuit_state})"
            )
            return {
                "content": "",
                "sources": [],
                "error": f"Service unavailable - circuit breaker {circuit_state}",
            }

        async def _make_request():
            """Inner function for retry wrapper."""
            client = await self._get_perplexity_client()
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._perplexity_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.domain_config.perplexity_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt or self.PERPLEXITY_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.2,
                    "return_citations": True,
                },
            )

            # Raise for non-success status codes to trigger retry
            if response.status_code != 200:
                error_msg = f"Perplexity API error: {response.status_code}"
                if response.status_code == 429:
                    error_msg = "Rate limit exceeded"
                elif response.status_code >= 500:
                    error_msg = f"Server error: {response.status_code}"
                raise httpx.HTTPStatusError(
                    error_msg, request=response.request, response=response
                )

            return response

        try:
            # Retry with exponential backoff
            response = await retry_with_backoff(
                _make_request,
                max_retries=3,
                base_delay=2.0,
                max_delay=30.0,
            )

            # Parse successful response
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            sources = []
            for c in citations:
                if isinstance(c, str):
                    sources.append(c)
                elif isinstance(c, dict):
                    sources.append(c.get("url", c.get("title", "Unknown")))

            # Record success for circuit breaker
            self._perplexity_circuit.record_success()

            return {"content": content, "sources": sources[:10]}

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Perplexity API HTTP error after retries: {e}",
                extra={
                    "query_preview": query[:100],
                    "status_code": e.response.status_code if e.response else "unknown",
                },
            )
            self._perplexity_circuit.record_failure()
            return {
                "content": "",
                "sources": [],
                "error": f"API error after retries: {e}",
            }

        except Exception as e:
            logger.error(
                f"Perplexity query error after retries: {e}",
                extra={"query_preview": query[:100]},
                exc_info=True,
            )
            self._perplexity_circuit.record_failure()
            return {"content": "", "sources": [], "error": str(e)}

    # -------------------------------------------------------------------------
    # Opportunity Extraction
    # -------------------------------------------------------------------------

    async def _extract_opportunities(
        self,
        raw_content: str,
        query_context: str,
        source_urls: list[str],
    ) -> list[MarineOpportunity]:
        """
        Extract structured opportunities from raw research content.

        Uses LLM to parse unstructured text into MarineOpportunity objects.

        Args:
            raw_content: Raw text from Perplexity
            query_context: Original query for context
            source_urls: List of source URLs

        Returns:
            List of MarineOpportunity objects
        """
        if not raw_content:
            return []

        # Use LLM to extract structured opportunities
        try:
            result = self.run(
                raw_content=raw_content,
                query_context=query_context,
                source_urls=json.dumps(source_urls),
            )

            # Parse opportunities - may be list (from LLM) or JSON string
            opportunities_raw = result.get("opportunities", [])
            if isinstance(opportunities_raw, list):
                # Already a list from LLM execution
                opportunities_data = opportunities_raw
            elif isinstance(opportunities_raw, str):
                # JSON string - parse it
                try:
                    opportunities_data = json.loads(opportunities_raw)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse opportunities JSON, attempting to extract manually"
                    )
                    opportunities_data = []
            else:
                opportunities_data = []

            # Fallback: If no opportunities but we have content, create one from summary
            if not opportunities_data and raw_content:
                summary = result.get("summary", "")
                if summary or raw_content:
                    # Extract first headline-like sentence from content
                    first_line = (
                        raw_content.split("\n")[0][:200]
                        if raw_content
                        else summary[:200]
                    )
                    opportunities_data = [
                        {
                            "headline": first_line.replace("**", "").strip(),
                            "sales_explanation": summary or raw_content[:500],
                            "country": "",
                            "sales_signals": ["general_intelligence"],
                            "priority": 5,
                        }
                    ]
                    logger.info("Created fallback opportunity from summary/content")

            # Convert to MarineOpportunity objects
            opportunities = []
            for opp_data in opportunities_data:
                try:
                    # Handle case where LLM returns string instead of dict
                    if isinstance(opp_data, str):
                        # Convert string to basic dict structure
                        opp_data = {
                            "headline": opp_data[:200],
                            "sales_explanation": opp_data,
                            "country": "",
                            "sales_signals": ["general_intelligence"],
                            "priority": 5,
                        }

                    # Determine region from country
                    country = opp_data.get("country", "").lower()
                    region = self._map_country_to_region(country)

                    # Determine sector from context
                    sector = self._infer_sector(opp_data, query_context)

                    # Get primary source URL
                    source_url = opp_data.get("source_url", "")
                    if not source_url and source_urls:
                        source_url = source_urls[0]

                    # Parse published_date if LLM extracted it
                    _agent_pub_date = None
                    _agent_pub_raw = opp_data.get("published_date")
                    if _agent_pub_raw and isinstance(_agent_pub_raw, str):
                        try:
                            from datetime import datetime as _dt

                            _agent_pub_date = _dt.strptime(
                                _agent_pub_raw[:10], "%Y-%m-%d"
                            )
                        except (ValueError, TypeError):
                            pass

                    # Create opportunity
                    opp = MarineOpportunity(
                        id=str(uuid.uuid4()),
                        headline=opp_data.get("headline", "")[:200],
                        source_name=self._extract_source_name(source_url),
                        source_url=source_url,
                        url_hash=MarineOpportunity.generate_url_hash(source_url),
                        sales_signals=opp_data.get("sales_signals", []),
                        region=region,
                        vessel_types=self._normalize_vessel_types(
                            opp_data.get("vessel_type", "")
                        ),
                        sector=sector,
                        companies_involved=opp_data.get("companies_involved", []),
                        country=opp_data.get("country", ""),
                        sales_explanation=opp_data.get("sales_explanation", ""),
                        suggested_action=opp_data.get("suggested_action", ""),
                        source_category=SourceCategory.PERPLEXITY.value,
                        raw_content=raw_content[:5000],  # Limit stored content
                        priority=int(opp_data.get("priority", 5)),
                        published_date=_agent_pub_date,
                    )
                    opportunities.append(opp)

                except Exception as e:
                    logger.warning(f"Failed to parse opportunity: {e}")
                    continue

            return opportunities

        except Exception as e:
            logger.error(f"Opportunity extraction failed: {e}")
            return []

    def _map_country_to_region(self, country: str) -> str:
        """Map country name to Region enum value."""
        country_lower = country.lower()
        country_map = {
            "singapore": Region.SINGAPORE.value,
            "indonesia": Region.INDONESIA.value,
            "malaysia": Region.MALAYSIA.value,
            "thailand": Region.THAILAND.value,
            "vietnam": Region.VIETNAM.value,
            "philippines": Region.PHILIPPINES.value,
            "australia": Region.AUSTRALIA.value,
            "china": Region.CHINA.value,
            "korea": Region.KOREA.value,
            "south korea": Region.KOREA.value,
            "japan": Region.JAPAN.value,
            "india": Region.INDIA.value,
        }
        return country_map.get(country_lower, Region.APAC_OTHER.value)

    def _infer_sector(self, opp_data: dict, query_context: str) -> str:
        """Infer sector from opportunity data and query context."""
        # Check for offshore indicators
        signals = opp_data.get("sales_signals", [])
        vessel_type = opp_data.get("vessel_type", "").lower()
        headline = opp_data.get("headline", "").lower()

        if "offshore_project" in signals or vessel_type in [
            "osv",
            "fpso",
            "ahts",
            "psv",
        ]:
            return Sector.OFFSHORE_OIL_GAS.value

        if (
            "offshore" in query_context.lower()
            or "fpso" in headline
            or "oil" in headline
        ):
            return Sector.OFFSHORE_OIL_GAS.value

        if vessel_type in ["ferry", "tug", "harbour_craft"]:
            return Sector.MARINE_TRANSPORTATION.value

        if "shipyard" in headline or "retrofit" in headline:
            return Sector.MARINE_ENGINEERING.value

        if "port" in headline or "terminal" in headline:
            return Sector.PORT_TERMINAL.value

        return Sector.MARINE_TRANSPORTATION.value  # Default

    def _normalize_vessel_types(self, vessel_type_str: str) -> list[str]:
        """Normalize vessel type string to list of VesselType values."""
        if not vessel_type_str:
            return []

        vessel_type_lower = vessel_type_str.lower()
        result = []

        # Map common terms to VesselType enum
        type_map = {
            "ferry": VesselType.FERRY.value,
            "tug": VesselType.TUG.value,
            "tugboat": VesselType.TUG.value,
            "osv": VesselType.OSV.value,
            "offshore support": VesselType.OSV.value,
            "psv": VesselType.PSV.value,
            "platform supply": VesselType.PSV.value,
            "ahts": VesselType.AHTS.value,
            "anchor handling": VesselType.AHTS.value,
            "fpso": VesselType.FPSO.value,
            "harbour craft": VesselType.HARBOUR_CRAFT.value,
            "harbor craft": VesselType.HARBOUR_CRAFT.value,
            "cargo": VesselType.CARGO.value,
            "tanker": VesselType.TANKER.value,
            "container": VesselType.CONTAINER.value,
            "cruise": VesselType.CRUISE.value,
            "yacht": VesselType.YACHT.value,
            "naval": VesselType.NAVAL.value,
            "fishing": VesselType.FISHING.value,
            "dredger": VesselType.DREDGER.value,
            "construction": VesselType.CONSTRUCTION.value,
        }

        for key, value in type_map.items():
            if key in vessel_type_lower:
                result.append(value)

        return result if result else [VesselType.OTHER.value]

    def _extract_source_name(self, url: str) -> str:
        """Extract source name from URL."""
        if not url:
            return "Unknown"

        # Map known domains to names
        domain_map = {
            "maritime-executive.com": "Maritime Executive",
            "seatrade-maritime.com": "Seatrade Maritime",
            "splash247.com": "Splash247",
            "tradewindsnews.com": "TradeWinds",
            "lloydslist": "Lloyd's List",
            "oedigital.com": "Offshore Engineer",
            "upstreamonline.com": "Upstream Online",
            "mpa.gov.sg": "MPA Singapore",
            "sgx.com": "SGX",
            "seatrium.com": "Seatrium",
            "paxocean.com": "PaxOcean",
            "asl.com.sg": "ASL Marine",
        }

        for domain, name in domain_map.items():
            if domain in url:
                return name

        # Extract domain from URL
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return "Unknown"

    # -------------------------------------------------------------------------
    # Shared Memory Methods
    # -------------------------------------------------------------------------

    async def _check_memory_for_context(
        self,
        key: str,
        tags: List[str],
        max_age_seconds: float = 3600.0,  # 1 hour default TTL
    ) -> Optional[dict[str, Any]]:
        """
        Check shared memory for relevant context before expensive operations.

        This method enables multi-agent coordination by allowing agents to
        share research results and avoid redundant queries.

        Args:
            key: Identifier for logging (e.g., query text)
            tags: Tags to filter insights by
            max_age_seconds: Maximum age of cached results to consider valid

        Returns:
            Cached result content if found and valid, None otherwise
        """
        if not self._shared_memory:
            return None

        try:
            results = self._shared_memory.read_relevant(
                agent_id=self.agent_id,
                tags=tags,
                min_importance=0.5,
                max_age_seconds=max_age_seconds,
                exclude_own=False,  # Include our own previous results
                limit=1,
            )

            if results:
                insight = results[0]
                logger.info(
                    f"Memory hit for '{key[:50]}' from agent '{insight.get('agent_id')}'"
                )
                return insight.get("content")

        except Exception as e:
            logger.debug(f"Memory search failed for {key}: {e}")

        return None

    # -------------------------------------------------------------------------
    # Main Research Methods
    # -------------------------------------------------------------------------

    async def research_query(
        self,
        query: str,
        save_to_db: bool = True,
    ) -> list[MarineOpportunity]:
        """
        Execute a single research query and extract opportunities.

        Args:
            query: Research query string
            save_to_db: Whether to save opportunities to database

        Returns:
            List of MarineOpportunity objects
        """
        logger.info(f"Executing research query: {query}")

        # Check shared memory for recent similar research
        query_key = query.split()[0].lower() if query else ""
        cached = await self._check_memory_for_context(
            key=query,
            tags=["marine_intel", "research", query_key],
            max_age_seconds=3600.0,  # 1 hour cache TTL
        )

        if cached and cached.get("opportunities_found", 0) > 0:
            logger.info(
                f"Recent research found in memory: {cached.get('opportunities_found')} "
                f"opportunities ({cached.get('high_priority_count', 0)} high priority)"
            )
            # Note: We still proceed to get fresh data, but log the insight
            # Full caching would require storing MarineOpportunity objects

        # Query Perplexity
        result = await self._query_perplexity(query)

        if result.get("error") or not result.get("content"):
            logger.warning(f"Query returned no content: {query}")
            return []

        # Extract opportunities
        opportunities = await self._extract_opportunities(
            raw_content=result["content"],
            query_context=query,
            source_urls=result["sources"],
        )

        # Enrich opportunities with KB entities (if available)
        if self._kb_service and opportunities:
            try:
                await self._kb_service.initialize()
                for opp in opportunities:
                    # Enrich with KB data (entities, classification, scores)
                    enriched = await self._kb_service.enrich_opportunity(
                        content=opp.raw_content or result["content"],
                        title=opp.headline,
                        existing_data={
                            "region": opp.region,
                            "sector": opp.sector,
                            "companies": opp.companies_involved,
                            "vessel_types": opp.vessel_types,
                        },
                    )
                    # Merge KB enrichment into opportunity
                    all_entities = (
                        enriched.engine_entities + enriched.manufacturer_entities
                    )
                    if all_entities:
                        opp.kb_entities = [
                            {
                                "entity_type": e.entity_type,
                                "entity_id": e.entity_id,
                                "entity_name": e.entity_name,
                                "match_type": e.match_type,
                                "match_confidence": e.match_confidence,
                            }
                            for e in all_entities
                        ]
                    if enriched.classification:
                        opp.kb_classification = {
                            "classification": enriched.classification,
                            "rpm_classes": [str(r) for r in enriched.rpm_classes],
                            "power_classes": [str(p) for p in enriched.power_classes],
                            "fuel_types": enriched.fuel_types,
                            "affected_competitors": enriched.affected_competitors,
                        }
                    if enriched.kb_score > 0:
                        opp.kb_score = {
                            "technical_score": enriched.technical_score,
                            "market_score": enriched.market_score,
                            "commercial_score": enriched.commercial_score,
                            "total_score": enriched.kb_score,
                            "explanation": enriched.score_explanation,
                        }
                        # Optionally boost priority based on KB score
                        if enriched.kb_score >= 70:  # HIGH_PRIORITY threshold
                            opp.priority = max(opp.priority, 8)
                        elif enriched.kb_score >= 40:  # MONITOR threshold
                            opp.priority = max(opp.priority, 5)
                logger.info(f"KB enriched {len(opportunities)} opportunities")
            except Exception as e:
                logger.warning(f"KB enrichment failed, continuing without: {e}")

        # A2A Enrichment: Request competitor intel for opportunities with companies
        # This demonstrates actual A2A agent communication
        if self._registry and opportunities:
            # Limit enrichment to highest priority opportunities to avoid API overload
            max_enrichment = self.domain_config.max_enrichment_opportunities
            sorted_opps = sorted(opportunities, key=lambda x: x.priority, reverse=True)
            enrichment_attempted = 0
            for opp in sorted_opps[:max_enrichment]:
                if opp.companies_involved:
                    enrichment_attempted += 1
                    try:
                        enrichment = await self.request_enrichment(
                            capability="competitor_intel",
                            data={
                                "task": f"Competitor analysis for {', '.join(opp.companies_involved[:3])}",
                                "query": f"competitor presence {opp.region or 'global'} {opp.sector or 'marine'}",
                            },
                        )
                        if enrichment and enrichment.get("success"):
                            # CompetitorIntelAgent returns: result_data with answer, insights, etc.
                            result_data = enrichment.get("result_data", {})
                            if result_data.get("answer") or result_data.get(
                                "key_insights"
                            ):
                                opp.competitor_intel = {
                                    "summary": result_data.get("answer"),
                                    "insights": result_data.get("key_insights", []),
                                    "confidence": result_data.get("confidence"),
                                    "sources": result_data.get("sources", []),
                                }
                                self._enrichment_success_count += 1
                                logger.info(
                                    f"A2A enriched opportunity '{opp.headline[:30]}...' with competitor intel"
                                )
                            else:
                                # Enrichment succeeded but returned empty data
                                self._enrichment_failure_count += 1
                                logger.warning(
                                    f"A2A enrichment returned empty data for '{opp.headline[:30]}...'"
                                )
                        else:
                            self._enrichment_failure_count += 1
                            error_msg = (
                                enrichment.get("error_message")
                                if enrichment
                                else "No response"
                            )
                            logger.warning(f"A2A enrichment failed: {error_msg}")
                    except Exception as e:
                        # Enrichment is optional - don't fail if it fails
                        self._enrichment_failure_count += 1
                        logger.warning(
                            f"Competitor enrichment exception (non-critical): {e}"
                        )
                else:
                    self._enrichment_skip_count += 1

            # Log enrichment summary
            if enrichment_attempted > 0:
                metrics = self.get_enrichment_metrics()
                logger.info(
                    f"A2A enrichment completed: {metrics['enrichment_success']}/{enrichment_attempted} successful "
                    f"(rate: {metrics['enrichment_success_rate']:.1%})"
                )

        # Save to database with deduplication
        saved_count = 0
        skipped_count = 0

        if save_to_db and opportunities:
            await self.db.initialize()

            for opp in opportunities:
                if opp.priority >= self.domain_config.min_priority_threshold:
                    opp_id, is_new = await self.db.save_opportunity(opp)
                    if is_new:
                        saved_count += 1
                    else:
                        skipped_count += 1

            logger.info(
                f"Query '{query[:50]}...': {saved_count} saved, {skipped_count} duplicates"
            )

        # Write to shared memory for other agents (if available)
        if self._shared_memory and opportunities:
            self.write_to_memory(
                content={
                    "query": query,
                    "opportunities_found": len(opportunities),
                    "high_priority_count": sum(
                        1 for o in opportunities if o.priority >= 8
                    ),
                },
                tags=["marine_intel", "research", query.split()[0]],
                importance=0.8,
            )

        return opportunities

    async def run_daily_research(self) -> dict[str, Any]:
        """
        Execute daily research job across all query patterns.

        Runs through all configured query patterns, extracts opportunities,
        and stores them with deduplication.

        NOTE: This method does NOT manage job records - the scheduler handles
        job lifecycle. This method only returns research statistics.

        Returns:
            Research statistics dict with keys:
            - queries_executed: Number of queries run
            - articles_processed: Number of source articles processed
            - opportunities_found: Number of opportunities discovered
            - duplicates_skipped: Number of duplicate opportunities skipped
            - errors: Number of errors encountered
        """
        logger.info("Starting daily marine intelligence research")

        await self.db.initialize()

        total_opportunities = 0
        total_duplicates = 0
        total_errors = 0
        queries_executed = 0
        articles_processed = 0

        # Execute queries by category
        for category, queries in QUERY_PATTERNS.items():
            logger.info(f"Processing category: {category}")

            # Limit queries per category
            queries_to_run = queries[: self.domain_config.max_queries_per_category]

            for query in queries_to_run:
                try:
                    opportunities = await self.research_query(query, save_to_db=True)
                    queries_executed += 1
                    # Each query processes one "article" (Perplexity response)
                    articles_processed += 1

                    for opp in opportunities:
                        if opp.priority >= self.domain_config.min_priority_threshold:
                            total_opportunities += 1

                    # Rate limiting
                    await asyncio.sleep(self.domain_config.delay_between_queries)

                except Exception as e:
                    logger.error(f"Query error for '{query}': {e}")
                    total_errors += 1

        # Calculate duplicates from current stats
        try:
            stats = await self.db.get_stats()
            # This is an approximation - actual dedup happens in save_opportunity
            total_duplicates = max(
                0, stats.get("total_opportunities", 0) - total_opportunities
            )
        except Exception as e:
            logger.warning(f"Could not fetch stats for duplicate count: {e}")

        result = {
            "queries_executed": queries_executed,
            "articles_processed": articles_processed,
            "opportunities_found": total_opportunities,
            "duplicates_skipped": total_duplicates,
            "errors": total_errors,
        }

        logger.info(
            f"Daily research complete: {total_opportunities} opportunities, "
            f"{total_duplicates} duplicates, {total_errors} errors"
        )

        return result

    async def run_targeted_research(
        self,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        custom_queries: Optional[list[str]] = None,
    ) -> list[MarineOpportunity]:
        """
        Run targeted research for specific region or sector.

        Args:
            region: Target region (e.g., 'singapore', 'indonesia')
            sector: Target sector (e.g., 'offshore_oil_gas')
            custom_queries: Custom query strings to execute

        Returns:
            List of discovered opportunities
        """
        all_opportunities = []

        if custom_queries:
            for query in custom_queries:
                opps = await self.research_query(query)
                all_opportunities.extend(opps)
                await asyncio.sleep(self.domain_config.delay_between_queries)

        elif region:
            # Build region-specific queries
            region_queries = [
                f"newbuild vessel shipyard {region}",
                f"engine repower retrofit {region}",
                f"offshore project vessel {region}",
                f"ferry fleet expansion {region}",
            ]
            for query in region_queries:
                opps = await self.research_query(query)
                all_opportunities.extend(opps)
                await asyncio.sleep(self.domain_config.delay_between_queries)

        elif sector:
            # Build sector-specific queries
            if sector == "offshore_oil_gas":
                sector_queries = [
                    "FPSO contract Asia Pacific",
                    "offshore project sanction Southeast Asia",
                    "OSV order newbuild Asia",
                    "oil gas vessel demand APAC",
                ]
            elif sector == "marine_transportation":
                sector_queries = [
                    "ferry newbuild Asia Pacific",
                    "tug order shipyard Singapore",
                    "harbour craft vessel Asia",
                    "port terminal vessel requirement APAC",
                ]
            else:
                sector_queries = [f"{sector} vessel marine Asia Pacific"]

            for query in sector_queries:
                opps = await self.research_query(query)
                all_opportunities.extend(opps)
                await asyncio.sleep(self.domain_config.delay_between_queries)

        return all_opportunities

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    async def get_opportunities(
        self,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        sales_signal: Optional[str] = None,
        unreviewed_only: bool = False,
        min_priority: int = 1,
        limit: int = 50,
    ) -> list[MarineOpportunity]:
        """
        Retrieve opportunities from database with filters.

        Args:
            region: Filter by region
            sector: Filter by sector
            sales_signal: Filter by sales signal
            unreviewed_only: Only return unreviewed opportunities
            min_priority: Minimum priority threshold
            limit: Maximum results

        Returns:
            List of MarineOpportunity objects
        """
        await self.db.initialize()
        return await self.db.list_opportunities(
            region=region,
            sector=sector,
            sales_signal=sales_signal,
            reviewed=False if unreviewed_only else None,
            min_priority=min_priority,
            limit=limit,
        )

    async def get_high_priority_opportunities(
        self,
        min_priority: int = 8,
        limit: int = 20,
    ) -> list[MarineOpportunity]:
        """Get high-priority opportunities requiring immediate attention."""
        await self.db.initialize()
        return await self.db.list_opportunities(
            min_priority=min_priority,
            limit=limit,
        )

    # -------------------------------------------------------------------------
    # A2A Router Compatibility
    # -------------------------------------------------------------------------

    async def _run_research_task(self, task: str) -> dict[str, Any]:
        """Async helper for research task execution.

        Called when run() is invoked from an async context (FastAPI).
        Returns formatted results after completing research.

        Args:
            task: Research task/query string

        Returns:
            Formatted research results dict
        """
        opportunities = await self.research_query(task, save_to_db=False)
        return self._format_opportunities_response(opportunities)

    def _format_opportunities_response(
        self, opportunities: list[MarineOpportunity]
    ) -> dict[str, Any]:
        """Format opportunities into API response structure.

        Args:
            opportunities: List of MarineOpportunity objects

        Returns:
            Formatted response dict with opportunities, summary, and metadata
        """
        return {
            "opportunities": [
                {
                    "headline": opp.headline,
                    "priority": opp.priority,
                    "region": opp.region,
                    "companies": opp.companies_involved,
                    "sales_explanation": opp.sales_explanation,
                    "suggested_action": opp.suggested_action,
                }
                for opp in opportunities
            ],
            "summary": f"Found {len(opportunities)} marine opportunities",
            "total_opportunities": str(len(opportunities)),
            "success": True,
        }

    async def execute_a2a(self, **kwargs: Any) -> dict[str, Any]:
        """Custom async domain method for A2A enrichment calls.

        NOTE: This is a CUSTOM method, NOT a Kaizen-native pattern.
        Kaizen's A2A (via to_a2a_card()) is for agent discovery, not execution.

        This method provides direct domain logic execution for inter-agent
        enrichment without the overhead of Kaizen's LLM/memory/hooks features.
        For signature-based execution with full Kaizen features, use run_async().

        Entry Points:
            - run() → Sync entry point, calls research_query directly
            - run_async() → Kaizen native, uses signatures/memory/hooks (inherited)
            - execute_a2a() → Custom async domain method (this method)

        Args:
            **kwargs: Parameters (raw_content/task, query_context, source_urls)

        Returns:
            Standardized A2A response dict with research results
        """
        task = kwargs.get("task", "")

        if not task:
            # No task provided - check for raw_content (signature-based call)
            raw_content = kwargs.get("raw_content", "")
            if not raw_content:
                return {
                    "success": False,
                    "agent_id": self.agent_id,
                    "result_data": {},
                    "error_message": "No task or raw_content provided",
                    "metadata": {"routing": "a2a_run_async"},
                }
            # For raw_content, delegate to parent
            return {
                "success": True,
                "agent_id": self.agent_id,
                "result_data": super().run(**kwargs),
                "error_message": None,
                "metadata": {"routing": "a2a_run_async", "mode": "signature"},
            }

        logger.info(f"MarineIntelAgent.execute_a2a() - task: {task[:50]}...")

        try:
            opportunities = await self.research_query(task, save_to_db=False)
            formatted = self._format_opportunities_response(opportunities)
            return {
                "success": True,
                "agent_id": self.agent_id,
                "result_data": formatted,
                "error_message": None,
                "metadata": {"routing": "a2a_run_async", "task": task[:50]},
            }
        except Exception as e:
            logger.error(f"MarineIntelAgent.execute_a2a() failed: {e}")
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
        Uses domain-specific logic (research_query) without LLM/memory overhead.

        For signature-based execution with Kaizen features (memory, hooks, LLM),
        use the inherited run_async() method instead.

        Args:
            **kwargs: Parameters (raw_content/task, query_context, source_urls)

        Returns:
            Research results or opportunity summary (legacy format)
        """
        task = kwargs.get("task", "")
        if task:
            # Research task
            logger.info(f"MarineIntelAgent.run() - task: {task[:50]}...")
            opportunities = asyncio.run(self.research_query(task, save_to_db=False))
            return self._format_opportunities_response(opportunities)

        # Handle direct signature-based calls (for internal extraction)
        raw_content = kwargs.get("raw_content", "")
        if not raw_content:
            return {
                "opportunities": "[]",
                "summary": "No content provided",
                "total_opportunities": "0",
            }

        # Use parent class run() for signature-based extraction
        return super().run(**kwargs)

    async def get_stats(self) -> dict[str, Any]:
        """Get marine intelligence statistics."""
        await self.db.initialize()
        return await self.db.get_stats()

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check health of marine intelligence system.

        Returns:
            Health status with agent_id, status, capabilities, and system availability
        """
        await self.db.initialize()

        # Get capabilities via _extract_primary_capabilities()
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        # Check Perplexity API
        perplexity_ok = bool(self._perplexity_api_key)

        # Get database stats
        stats = await self.db.get_stats()

        # Get latest job
        latest_job = await self.db.get_latest_job()

        return {
            "agent_id": self.agent_id,
            "status": "healthy" if perplexity_ok else "degraded",
            "capabilities": capabilities,
            "perplexity_configured": perplexity_ok,
            "total_opportunities": stats.get("total_opportunities", 0),
            "unreviewed": stats.get("unreviewed", 0),
            "high_priority": stats.get("high_priority", 0),
            "last_7_days": stats.get("last_7_days", 0),
            "latest_job": latest_job.to_dict() if latest_job else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "MarineIntelAgent":
        """Async context manager entry."""
        await self.db.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# =============================================================================
# Factory Function
# =============================================================================


async def create_marine_intel_agent(
    llm_provider: str = "openai",
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o"),
    shared_memory: Optional[SharedMemoryPool] = None,
) -> MarineIntelAgent:
    """
    Factory function to create a Marine Intelligence Agent.

    Args:
        llm_provider: LLM provider (openai, anthropic)
        model: Model to use
        shared_memory: Optional shared memory pool

    Returns:
        Configured MarineIntelAgent instance
    """
    config = MarineIntelConfig(
        llm_provider=llm_provider,
        model=model,
    )

    agent = MarineIntelAgent(
        config=config,
        shared_memory=shared_memory,
    )

    # Initialize database
    await agent.db.initialize()

    return agent
