"""
DatabaseAgent - Kaizen BaseAgent for Database Operations

Provides A2A-compatible database access capabilities by wrapping PostgreSQL operations.
Enables other agents to query and store data via semantic A2A routing.

Capabilities:
    - db_query: Query database for opportunities, accounts, articles
    - db_store: Store new data (opportunities, research results)
    - opportunity_lookup: Look up specific opportunities
    - account_lookup: Look up marine accounts/companies
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.base_agent import BaseAgent
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.services.marine_intel.database import MarineIntelDatabase

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

logger = logging.getLogger(__name__)


class DatabaseQuerySignature(Signature):
    """Signature for database query operations."""

    operation: str = InputField(
        description="Operation type: 'query', 'store', 'lookup_opportunity', 'lookup_account'"
    )
    table: str = InputField(
        description="Table to operate on: 'opportunities', 'accounts', 'articles', 'jobs'",
        default="opportunities",
    )
    filters: dict = InputField(
        description="Query filters (region, sector, signal_type, etc.)",
        default_factory=dict,
    )
    data: dict = InputField(
        description="Data to store (for store operations)",
        default_factory=dict,
    )
    limit: int = InputField(description="Maximum results to return", default=50)

    results: list = OutputField(description="Query results")
    count: int = OutputField(description="Number of results")
    success: bool = OutputField(description="Operation success status")


@dataclass
class DatabaseAgentConfig:
    """Configuration for DatabaseAgent."""

    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.1
    max_tokens: int = 1000
    database_url: Optional[str] = None


class DatabaseAgent(BaseAgent):
    """
    Kaizen BaseAgent for database operations.

    Wraps MarineIntelDatabase to provide A2A-compatible database access.
    Other agents can invoke this agent via semantic routing when they need
    database operations.

    Capabilities:
        - db_query: Query opportunities, accounts, articles
        - db_store: Store new opportunities and research data
        - opportunity_lookup: Look up specific opportunities by ID or filters
        - account_lookup: Look up marine accounts/companies

    Usage:
        config = DatabaseAgentConfig()
        agent = DatabaseAgent(config)

        # Direct usage
        result = await agent.query_opportunities(region="singapore", limit=10)

        # Via A2A routing (recommended)
        router = Pipeline.router(agents=[database_agent, ...])
        result = router.run(task="Find opportunities in Singapore")
    """

    def __init__(
        self,
        config: DatabaseAgentConfig,
        shared_memory: Optional[Any] = None,
        agent_id: str = "database_agent",
    ):
        """Initialize DatabaseAgent.

        Args:
            config: DatabaseAgentConfig instance
            shared_memory: Optional SharedMemoryPool for A2A coordination
            agent_id: Unique identifier for this agent
        """
        super().__init__(config=config, signature=DatabaseQuerySignature())
        self.config = config
        self.agent_id = agent_id
        self._shared_memory = shared_memory
        self._database: Optional[MarineIntelDatabase] = None

    async def __aenter__(self) -> "DatabaseAgent":
        """Async context manager entry."""
        self._database = MarineIntelDatabase()
        await self._database.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._database:
            await self._database.close()
        self._database = None

    async def _ensure_database(self) -> MarineIntelDatabase:
        """Ensure database connection is available."""
        if self._database is None:
            self._database = MarineIntelDatabase()
            await self._database.connect()
        return self._database

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
                name="db_query",
                domain="database",
                level=CapabilityLevel.EXPERT,
                description="Query database for opportunities, accounts, and articles",
                keywords=[
                    "query",
                    "database",
                    "find",
                    "get",
                    "retrieve",
                    "data",
                    "select",
                    "fetch",
                    "read",
                    "list",
                ],
                examples=[
                    "Find opportunities in Singapore",
                    "Get accounts from database",
                    "Query marine intel data",
                ],
                constraints=[],
            ),
            Capability(
                name="db_store",
                domain="database",
                level=CapabilityLevel.EXPERT,
                description="Store new data including opportunities and research results",
                keywords=[
                    "store",
                    "save",
                    "insert",
                    "add",
                    "create",
                    "persist",
                    "write",
                    "record",
                ],
                examples=["Store new opportunity", "Save research results to database"],
                constraints=[],
            ),
            Capability(
                name="opportunity_lookup",
                domain="sales",
                level=CapabilityLevel.ADVANCED,
                description="Look up marine sales opportunities by region, sector, or signal type",
                keywords=[
                    "opportunity",
                    "opportunities",
                    "sales",
                    "prospect",
                    "lead",
                    "deal",
                    "pipeline",
                ],
                examples=[
                    "Find opportunities in offshore oil and gas",
                    "Look up Singapore opportunities",
                ],
                constraints=[],
            ),
            Capability(
                name="account_lookup",
                domain="crm",
                level=CapabilityLevel.ADVANCED,
                description="Look up marine accounts and company information",
                keywords=[
                    "account",
                    "accounts",
                    "company",
                    "companies",
                    "lookup",
                    "customer",
                    "client",
                ],
                examples=["Find accounts in Indonesia", "Look up shipping companies"],
                constraints=[],
            ),
        ]

    async def query_opportunities(
        self,
        region: Optional[str] = None,
        sector: Optional[str] = None,
        signal_type: Optional[str] = None,
        min_priority: int = 1,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query marine opportunities.

        Args:
            region: Filter by region (e.g., "singapore")
            sector: Filter by sector (e.g., "offshore_oil_gas")
            signal_type: Filter by signal type (e.g., "newbuild")
            min_priority: Minimum priority score (1-10)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Query results with opportunities list
        """
        db = await self._ensure_database()

        logger.info(
            f"DatabaseAgent querying opportunities: region={region}, sector={sector}"
        )

        try:
            opportunities = await db.get_opportunities(
                region=region,
                sector=sector,
                signal_type=signal_type,
                min_priority=min_priority,
                limit=limit,
                offset=offset,
            )

            result = {
                "results": opportunities,
                "count": len(opportunities),
                "success": True,
                "filters": {
                    "region": region,
                    "sector": sector,
                    "signal_type": signal_type,
                    "min_priority": min_priority,
                },
            }

            # Write to shared memory if available
            if self._shared_memory and opportunities:
                self.write_to_memory(
                    content={
                        "query": "opportunities",
                        "count": len(opportunities),
                        "filters": result["filters"],
                    },
                    tags=["database", "opportunities", region or "all"],
                    importance=0.7,
                )

            return result

        except Exception as e:
            logger.error(f"DatabaseAgent query error: {type(e).__name__}: {e}")
            return {
                "results": [],
                "count": 0,
                "success": False,
                "error": str(e),
            }

    async def query_accounts(
        self,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        min_score: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query marine accounts (companies).

        Args:
            country: Filter by country
            sector: Filter by sector
            min_score: Minimum priority score
            limit: Maximum results

        Returns:
            Query results with accounts list
        """
        db = await self._ensure_database()

        logger.info(f"DatabaseAgent querying accounts: country={country}")

        try:
            accounts = await db.get_accounts(
                country=country,
                sector=sector,
                min_score=min_score,
                limit=limit,
            )

            return {
                "results": accounts,
                "count": len(accounts),
                "success": True,
                "filters": {
                    "country": country,
                    "sector": sector,
                    "min_score": min_score,
                },
            }

        except Exception as e:
            logger.error(f"DatabaseAgent account query error: {type(e).__name__}: {e}")
            return {
                "results": [],
                "count": 0,
                "success": False,
                "error": str(e),
            }

    async def query_articles(
        self,
        source: Optional[str] = None,
        is_processed: Optional[bool] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query source articles.

        Args:
            source: Filter by source name
            is_processed: Filter by processing status
            limit: Maximum results

        Returns:
            Query results with articles list
        """
        db = await self._ensure_database()

        logger.info(f"DatabaseAgent querying articles: source={source}")

        try:
            articles = await db.get_articles(
                source=source,
                is_processed=is_processed,
                limit=limit,
            )

            return {
                "results": articles,
                "count": len(articles),
                "success": True,
                "filters": {
                    "source": source,
                    "is_processed": is_processed,
                },
            }

        except Exception as e:
            logger.error(f"DatabaseAgent article query error: {type(e).__name__}: {e}")
            return {
                "results": [],
                "count": 0,
                "success": False,
                "error": str(e),
            }

    async def store_opportunity(
        self, opportunity_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Store a new opportunity.

        Args:
            opportunity_data: Opportunity data to store

        Returns:
            Store result with new opportunity ID
        """
        db = await self._ensure_database()

        logger.info(
            f"DatabaseAgent storing opportunity: {opportunity_data.get('company_name', 'unknown')}"
        )

        try:
            opportunity_id = await db.store_opportunity(opportunity_data)

            return {
                "success": True,
                "opportunity_id": opportunity_id,
                "message": "Opportunity stored successfully",
            }

        except Exception as e:
            logger.error(f"DatabaseAgent store error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "opportunity_id": None,
                "error": str(e),
            }

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Stats including counts by region, signal type, etc.
        """
        db = await self._ensure_database()

        try:
            stats = await db.get_stats()
            return {
                "success": True,
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"DatabaseAgent stats error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "stats": {},
                "error": str(e),
            }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous run method for BaseAgent compatibility.

        Args:
            **kwargs: Operation parameters

        Returns:
            Operation results
        """
        import asyncio

        operation = kwargs.get("operation", "query")
        table = kwargs.get("table", "opportunities")
        filters = kwargs.get("filters", {})
        data = kwargs.get("data", {})
        limit = kwargs.get("limit", 50)

        async def execute():
            if operation == "store":
                return await self.store_opportunity(data)
            elif operation == "stats":
                return await self.get_stats()
            elif table == "opportunities":
                return await self.query_opportunities(
                    region=filters.get("region"),
                    sector=filters.get("sector"),
                    signal_type=filters.get("signal_type"),
                    min_priority=filters.get("min_priority", 1),
                    limit=limit,
                )
            elif table == "accounts":
                return await self.query_accounts(
                    country=filters.get("country"),
                    sector=filters.get("sector"),
                    min_score=filters.get("min_score", 0),
                    limit=limit,
                )
            elif table == "articles":
                return await self.query_articles(
                    source=filters.get("source"),
                    is_processed=filters.get("is_processed"),
                    limit=limit,
                )
            else:
                return {"success": False, "error": f"Unknown table: {table}"}

        return asyncio.get_event_loop().run_until_complete(execute())

    async def health_check(self) -> dict[str, Any]:
        """Check agent health.

        Returns:
            Health status with agent_id, status, capabilities, and database connectivity
        """
        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        try:
            db = await self._ensure_database()
            # Simple query to check connectivity
            stats = await db.get_stats()

            return {
                "agent_id": self.agent_id,
                "status": "healthy",
                "capabilities": capabilities,
                "database_connected": True,
                "shared_memory_available": self._shared_memory is not None,
                "stats": stats,
            }
        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "status": "unhealthy",
                "capabilities": capabilities,
                "database_connected": False,
                "shared_memory_available": self._shared_memory is not None,
                "error": str(e),
            }


async def create_database_agent(
    shared_memory: Optional[Any] = None,
) -> DatabaseAgent:
    """Factory function to create DatabaseAgent.

    Args:
        shared_memory: Optional SharedMemoryPool for A2A coordination

    Returns:
        Configured DatabaseAgent instance
    """
    config = DatabaseAgentConfig()
    agent = DatabaseAgent(config, shared_memory=shared_memory)
    await agent.__aenter__()
    return agent
