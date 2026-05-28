"""
WebSearchAgent - Kaizen BaseAgent for Web Search and Research

Provides A2A-compatible web search capabilities by wrapping the InsightsService.
Enables other agents to request web searches via semantic A2A routing.

MANDATORY GUIDE REFERENCES:
    - customer_research: MUST follow `src/lead_to_cash/docs/guides/KYP_guide.md`
    - industry_news: MUST follow `src/lead_to_cash/docs/guides/industry_news_guide.md`
    - competitor_intel: MUST follow `src/lead_to_cash/docs/guides/competitor_insights_guide.md`

    Key standards enforced:
    - EVERY finding MUST include verifiable source URL
    - Use evidence-based terminology (no unverified assertions)
    - Use status codes: NO_ADVERSE_FINDINGS, ADVERSE_FINDINGS, UNABLE_TO_VERIFY
    - NEVER assert positive attributes (e.g., "good reputation")
    - State what was NOT found, not positive assertions

Capabilities:
    - web_search: General web search queries via Perplexity
    - competitor_intel: Competitor news and updates
    - industry_news: Industry-specific news and trends
    - customer_research: KYP research on specific companies
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.services.insights_service import InsightsService

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

logger = logging.getLogger(__name__)

# =============================================================================
# MANDATORY GUIDE REFERENCES
# =============================================================================
# Each capability MUST follow its respective guide for output formatting.

KYP_GUIDE_PATH = "src/lead_to_cash/docs/guides/KYP_guide.md"
INDUSTRY_NEWS_GUIDE_PATH = "src/lead_to_cash/docs/guides/industry_news_guide.md"
COMPETITOR_INSIGHTS_GUIDE_PATH = (
    "src/lead_to_cash/docs/guides/competitor_insights_guide.md"
)

# Capability to Guide mapping:
CAPABILITY_GUIDES = {
    "customer_research": KYP_GUIDE_PATH,
    "industry_news": INDUSTRY_NEWS_GUIDE_PATH,
    "competitor_intel": COMPETITOR_INSIGHTS_GUIDE_PATH,
}

# Key requirements from KYP guide for customer_research:
# 1. Every finding MUST include source URL
# 2. Use status codes: NO_ADVERSE_FINDINGS, ADVERSE_FINDINGS, UNABLE_TO_VERIFY
# 3. NEVER assert positive attributes (e.g., "good reputation", "safe operator")
# 4. State what was NOT found: "No adverse findings from sources searched"
# 5. Document databases searched with dates


class WebSearchSignature(Signature):
    """Signature for web search operations."""

    query: str = InputField(description="Search query or topic to research")
    search_type: str = InputField(
        description="Type of search: 'general', 'competitor', 'industry', 'customer'",
        default="general",
    )
    context: dict = InputField(
        description="Additional context for the search",
        default_factory=dict,
    )

    result: str = OutputField(description="Search results summary")
    sources: list = OutputField(description="List of source URLs")
    raw_content: str = OutputField(description="Raw content from search")


@dataclass
class WebSearchConfig:
    """Configuration for WebSearchAgent."""

    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.3
    max_tokens: int = 2000
    perplexity_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


class WebSearchAgent(BaseAgent):
    """
    Kaizen BaseAgent for web search and research operations.

    Wraps InsightsService to provide A2A-compatible web search capabilities.
    Other agents can invoke this agent via semantic routing when they need
    real-time web data.

    Capabilities:
        - web_search: General purpose web search
        - competitor_intel: Competitor news (Caterpillar, Cummins, MAN)
        - industry_news: Marine/offshore industry news
        - customer_research: Research specific companies

    Usage:
        config = WebSearchConfig()
        agent = WebSearchAgent(config)

        # Direct usage
        result = await agent.search("vessel orders Singapore 2026")

        # Via A2A routing (recommended)
        router = Pipeline.router(agents=[web_search_agent, ...])
        result = router.run(task="Search for vessel orders")
    """

    def __init__(
        self,
        config: WebSearchConfig,
        shared_memory: Optional[Any] = None,
        agent_id: str = "web_search_agent",
    ):
        """Initialize WebSearchAgent.

        Args:
            config: WebSearchConfig instance
            shared_memory: Optional SharedMemoryPool for A2A coordination
            agent_id: Unique identifier for this agent
        """
        super().__init__(config=config, signature=WebSearchSignature())
        self.config = config
        self.agent_id = agent_id
        self._shared_memory = shared_memory
        self._insights_service: Optional[InsightsService] = None

    async def __aenter__(self) -> "WebSearchAgent":
        """Async context manager entry."""
        self._insights_service = InsightsService()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        self._insights_service = None

    def _ensure_service(self) -> InsightsService:
        """Ensure InsightsService is available."""
        if self._insights_service is None:
            self._insights_service = InsightsService()
        return self._insights_service

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
                name="web_search",
                domain="search",
                level=CapabilityLevel.EXPERT,
                description="Real-time web search using Perplexity API for current information",
                keywords=[
                    "search",
                    "web",
                    "internet",
                    "find",
                    "lookup",
                    "query",
                    "perplexity",
                    "real-time",
                    "current",
                    "latest",
                ],
                examples=[
                    "Search for vessel orders in Singapore",
                    "Find latest news about marine industry",
                    "Look up company information",
                ],
                constraints=[],
            ),
            Capability(
                name="competitor_intel",
                domain="market_intelligence",
                level=CapabilityLevel.ADVANCED,
                description="Competitor news, updates, and market intelligence",
                keywords=[
                    "competitor",
                    "caterpillar",
                    "cummins",
                    "man",
                    "rival",
                    "competition",
                    "market share",
                    "news",
                ],
                examples=[
                    "What's the latest news about Caterpillar?",
                    "Competitor updates in marine engines",
                ],
                constraints=[],
            ),
            Capability(
                name="industry_news",
                domain="news",
                level=CapabilityLevel.ADVANCED,
                description="Marine and offshore industry news and trends",
                keywords=[
                    "news",
                    "industry",
                    "marine",
                    "offshore",
                    "trends",
                    "oil",
                    "gas",
                    "shipping",
                    "vessel",
                ],
                examples=["Latest marine industry news", "Offshore oil and gas trends"],
                constraints=[],
            ),
            Capability(
                name="customer_research",
                domain="research",
                level=CapabilityLevel.ADVANCED,
                description="Research specific companies and potential customers",
                keywords=[
                    "research",
                    "company",
                    "customer",
                    "background",
                    "due diligence",
                    "information",
                ],
                examples=[
                    "Research Batam Fast Ferry company",
                    "Background information on shipping company",
                ],
                constraints=[],
            ),
        ]

    async def search(
        self,
        query: str,
        search_type: str = "general",
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a web search.

        Args:
            query: Search query or topic
            search_type: Type of search (general, competitor, industry, customer)
            context: Additional context for the search

        Returns:
            Search results with summary, sources, and raw content
        """
        context = context or {}
        service = self._ensure_service()

        logger.info(f"WebSearchAgent executing {search_type} search: {query[:50]}...")

        try:
            if search_type == "competitor":
                result = await service.get_competitor_updates()
            elif search_type == "industry":
                result = await service.get_industry_news()
            elif search_type == "customer":
                company_name = context.get("company_name", query)
                result = await service.get_customer_research(company_name)
            else:
                # General search
                result = await service.search_insights(query)

            # Extract response data from InsightResult dataclass
            # InsightResult has: content, sources, category, timestamp
            if result.category != "error":
                output = {
                    "result": result.content,
                    "sources": result.sources,
                    "raw_content": result.content,
                    "search_type": search_type,
                    "query": query,
                    "success": True,
                }
            else:
                output = {
                    "result": f"Search failed: {result.content}",
                    "sources": [],
                    "raw_content": "",
                    "search_type": search_type,
                    "query": query,
                    "success": False,
                }

            # Write to shared memory if available
            if self._shared_memory:
                self.write_to_memory(
                    content=output,
                    tags=["web_search", search_type, query.split()[0] if query else ""],
                    importance=0.8,
                )

            return output

        except Exception as e:
            logger.error(f"WebSearchAgent error: {type(e).__name__}: {e}")
            return {
                "result": f"Search error: {type(e).__name__}",
                "sources": [],
                "raw_content": "",
                "search_type": search_type,
                "query": query,
                "success": False,
                "error": str(e),
            }

    async def get_competitor_updates(self) -> dict[str, Any]:
        """Get latest competitor news and updates.

        Returns:
            Competitor intelligence for Caterpillar, Cummins, MAN
        """
        return await self.search("", search_type="competitor")

    async def get_industry_news(self) -> dict[str, Any]:
        """Get latest industry news.

        Returns:
            Marine and offshore industry news
        """
        return await self.search("", search_type="industry")

    async def research_customer(self, company_name: str) -> dict[str, Any]:
        """Research a specific company.

        Args:
            company_name: Name of company to research

        Returns:
            Company research results
        """
        return await self.search(
            company_name,
            search_type="customer",
            context={"company_name": company_name},
        )

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous run method for BaseAgent compatibility.

        Handles both direct calls (query=) and Pipeline.router calls (task=).

        Args:
            **kwargs: Search parameters (query/task, search_type, context)

        Returns:
            Search results
        """
        import asyncio

        # Handle both 'query' and 'task' parameters (Pipeline.router uses 'task')
        query = kwargs.get("query") or kwargs.get("task", "")
        search_type = kwargs.get("search_type", "general")
        context = kwargs.get("context", {})

        # Auto-detect search type from query if not specified
        if query and search_type == "general":
            query_lower = query.lower()
            competitors = [
                "caterpillar",
                "cummins",
                "man energy",
                "wartsila",
                "rolls-royce",
            ]
            if "competitor" in query_lower or any(
                c in query_lower for c in competitors
            ):
                search_type = "competitor"
            elif any(
                kw in query_lower for kw in ["industry", "news", "trend", "market"]
            ):
                search_type = "industry"
            elif any(
                kw in query_lower
                for kw in ["research", "company", "customer", "background"]
            ):
                search_type = "customer"

        logger.info(
            f"WebSearchAgent.run() - query: {query[:50]}..., search_type: {search_type}"
        )

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Return coroutine for the caller to await
                # This is handled by the registry's _direct_agent_execution
                return self.search(query, search_type, context)
            else:
                return loop.run_until_complete(self.search(query, search_type, context))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.search(query, search_type, context))

    async def health_check(self) -> dict[str, Any]:
        """Check agent health.

        Returns:
            Health status with agent_id, status, capabilities, and service availability
        """
        service = self._ensure_service()
        has_perplexity = bool(service.perplexity_api_key)
        has_openai = bool(service.openai_api_key)

        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        return {
            "agent_id": self.agent_id,
            "status": "healthy" if (has_perplexity or has_openai) else "degraded",
            "capabilities": capabilities,
            "perplexity_available": has_perplexity,
            "openai_available": has_openai,
            "shared_memory_available": self._shared_memory is not None,
        }


async def create_web_search_agent(
    shared_memory: Optional[Any] = None,
) -> WebSearchAgent:
    """Factory function to create WebSearchAgent.

    Args:
        shared_memory: Optional SharedMemoryPool for A2A coordination

    Returns:
        Configured WebSearchAgent instance
    """
    config = WebSearchConfig()
    agent = WebSearchAgent(config, shared_memory=shared_memory)
    await agent.__aenter__()
    return agent
