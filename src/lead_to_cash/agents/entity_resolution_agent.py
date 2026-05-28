"""
Entity Resolution Agent - Kaizen BaseAgent Implementation

Resolves company names to canonical entities using:
1. Local registry database (fuzzy match, aliases, Levenshtein)
2. ACRA (Singapore corporate registry)
3. GLEIF (Global LEI database)
4. Web search (Perplexity) as fallback

Architecture:
    - Built on Kaizen BaseAgent for production-ready agent features
    - Integrates with EntityResolutionService for database operations
    - Supports A2A semantic routing for capability discovery
    - SharedMemoryPool for multi-agent coordination

Usage:
    from lead_to_cash.agents import EntityResolutionAgent, EntityResolutionConfig

    config = EntityResolutionConfig()
    agent = EntityResolutionAgent(config)

    result = await agent.resolve_entity("stengg", country_hint="SG")
    if result.status == ResolutionStatus.EXACT_MATCH:
        print(f"Found: {result.exact_match.canonical_name}")
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.base_agent import BaseAgent

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.services.entity_registry.config import (
    AUTO_CONFIRM_THRESHOLD_PERCENT,
    FUZZY_SEARCH_THRESHOLD,
    MARGIN_THRESHOLD_PERCENT,
    MAX_CANDIDATES,
)
from lead_to_cash.services.entity_registry.models import (
    ResolutionResult,
    ResolutionStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Signature Definition
# =============================================================================


class EntityResolutionSignature(Signature):
    """
    Signature for A2A semantic routing.

    Enables Pipeline.router() to match entity resolution tasks
    by comparing keywords and semantic meaning of field descriptions.
    """

    # Input Fields
    entity_name: str = InputField(
        description="Company name to resolve - may contain typos, abbreviations, or partial names",
        examples=[
            "ST Engineering",
            "stengg",
            "Batam Fast Ferry",
            "maerks",
            "Batam Fast",
        ],
    )
    country_hint: str = InputField(
        description="Optional country code hint (e.g., SG, DK, US)",
        default=None,
    )

    # Output Fields
    resolved_entity_id: str = OutputField(
        description="Canonical entity ID from registry (or None if not found)"
    )
    canonical_name: str = OutputField(description="Full canonical company name")
    confidence_score: float = OutputField(description="Match confidence 0-100")
    requires_confirmation: str = OutputField(
        description="Whether user confirmation is needed: true or false"
    )
    candidates: str = OutputField(
        description="JSON array of candidate matches (if disambiguation needed)"
    )
    status: str = OutputField(
        description="Resolution status: exact_match, confirmation_required, no_match"
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class EntityResolutionConfig:
    """
    Configuration for Entity Resolution Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration (for potential future LLM-based resolution)
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.1  # Low temperature for consistent resolution
    max_tokens: int = 1500

    # Domain Configuration (from shared config)
    auto_confirm_threshold: float = AUTO_CONFIRM_THRESHOLD_PERCENT  # 80.0
    margin_threshold: float = MARGIN_THRESHOLD_PERCENT  # 15.0
    fuzzy_search_threshold: float = FUZZY_SEARCH_THRESHOLD  # 0.4
    max_candidates: int = MAX_CANDIDATES  # 5

    # Agent Metadata
    agent_name: str = "entity_resolution_agent"
    agent_description: str = (
        "Intelligent entity resolution for KYP using registry, ACRA, GLEIF, and web search"
    )


# =============================================================================
# Entity Resolution Agent Implementation
# =============================================================================


class EntityResolutionAgent(BaseAgent):
    """
    Entity Resolution Agent - Kaizen BaseAgent implementation.

    Resolves company names to canonical entities using multiple strategies:
    1. Local registry database (exact, alias, fuzzy, Levenshtein)
    2. ACRA (Singapore corporate registry)
    3. GLEIF (Global LEI database)
    4. Web search (Perplexity) as fallback

    Features:
    - A2A semantic routing for capability discovery
    - SharedMemoryPool for multi-agent coordination
    - Graceful degradation if database unavailable
    - Consistent with other Kaizen-based agents

    Example:
        config = EntityResolutionConfig()
        agent = EntityResolutionAgent(config)

        # Resolve entity
        result = await agent.resolve_entity("stengg", country_hint="SG")

        if result.status == ResolutionStatus.EXACT_MATCH:
            print(f"Found: {result.exact_match.canonical_name}")
        elif result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
            for c in result.candidates:
                print(f"  {c.rank}. {c.canonical_name}")
    """

    # Class-level threshold constants (from shared config)
    AUTO_CONFIRM_THRESHOLD = AUTO_CONFIRM_THRESHOLD_PERCENT  # 80.0
    MARGIN_THRESHOLD = MARGIN_THRESHOLD_PERCENT  # 15.0

    def __init__(
        self,
        config: Optional[EntityResolutionConfig] = None,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
        resolution_service: Optional[Any] = None,
    ):
        """
        Initialize Entity Resolution Agent.

        Args:
            config: Agent configuration (uses defaults if not provided)
            shared_memory: Shared memory pool for multi-agent coordination
            agent_id: Unique agent identifier
            resolution_service: Optional EntityResolutionService for dependency injection
        """
        config = config or EntityResolutionConfig()

        super().__init__(
            config=config,
            signature=EntityResolutionSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
        )

        self.domain_config = config
        self._service = resolution_service
        self._initialized = False

    def _extract_primary_capabilities(self) -> List["Capability"]:
        """
        Extract primary capabilities for A2A semantic routing.

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
                name="entity_resolution",
                domain="data_management",
                level=CapabilityLevel.EXPERT,
                description=(
                    "Resolve company names to canonical entities using fuzzy matching, "
                    "aliases, and external sources"
                ),
                keywords=[
                    "entity",
                    "resolution",
                    "company",
                    "match",
                    "fuzzy",
                    "registry",
                    "customer",
                    "identify",
                    "UEN",
                    "LEI",
                    "canonical",
                    "lookup",
                ],
                examples=[
                    "Resolve 'stengg' to ST Engineering",
                    "Find entity ID for company 'Batam Fast Ferry'",
                    "Match customer name to SAP record",
                    "Identify company from abbreviation",
                ],
                constraints=[
                    "Requires entity registry database for best results",
                    "Country hint improves accuracy",
                ],
            ),
            Capability(
                name="external_verification",
                domain="data_management",
                level=CapabilityLevel.ADVANCED,
                description="Verify entities via ACRA, GLEIF, and web search",
                keywords=[
                    "ACRA",
                    "GLEIF",
                    "verification",
                    "external",
                    "search",
                    "Singapore",
                    "LEI",
                    "corporate",
                    "registry",
                ],
                examples=[
                    "Verify company in ACRA (Singapore)",
                    "Get LEI from GLEIF for international company",
                    "Search web for unknown company",
                ],
                constraints=[
                    "ACRA only for Singapore companies",
                    "GLEIF requires company to have LEI",
                ],
            ),
        ]

    # -------------------------------------------------------------------------
    # Service Management
    # -------------------------------------------------------------------------

    async def _get_service(self) -> Optional[Any]:
        """
        Get or create EntityResolutionService with graceful degradation.

        Returns:
            EntityResolutionService instance, or None if unavailable
        """
        if self._service is None:
            try:
                from lead_to_cash.services.entity_registry.entity_resolution_service import (
                    EntityResolutionService,
                )

                self._service = EntityResolutionService()
            except ImportError as e:
                logger.warning(f"EntityResolutionService unavailable: {e}")
                return None

        if not self._initialized:
            try:
                await self._service.initialize()
                self._initialized = True
                logger.info("EntityResolutionService initialized")
            except Exception as e:
                logger.warning(
                    f"Service initialization failed: {e}. Operating in degraded mode."
                )
                self._service = None

        return self._service

    async def initialize(self) -> None:
        """
        Initialize the agent and its dependencies.

        Called automatically by resolve_entity() if needed.
        """
        await self._get_service()

    async def close(self) -> None:
        """Close agent resources."""
        self._service = None
        self._initialized = False

    # -------------------------------------------------------------------------
    # Core Resolution Logic
    # -------------------------------------------------------------------------

    async def resolve_entity(
        self,
        entity_name: str,
        country_hint: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Resolve a company name to a canonical entity.

        This is the main entry point for entity resolution.
        Delegates to EntityResolutionService for database and external searches.

        Args:
            entity_name: Company name to resolve (may contain typos, abbreviations)
            country_hint: Optional country code hint (e.g., "SG")
            session_id: Session ID for tracking

        Returns:
            ResolutionResult with status and candidates
        """
        service = await self._get_service()

        if service:
            # Use service's resolve method (has all search strategies)
            result = await service.resolve(
                query=entity_name,
                country_hint=country_hint,
                search_external=True,
                session_id=session_id,
            )
        else:
            # Degraded mode - return no match
            logger.warning("Entity registry unavailable - returning NO_MATCH")
            result = ResolutionResult(
                status=ResolutionStatus.NO_MATCH,
                query=entity_name,
                error_message="Entity registry unavailable",
            )

        # Write to shared memory for other agents
        if self._shared_memory and result.exact_match:
            try:
                self.write_to_memory(
                    content={
                        "entity_name": entity_name,
                        "resolved_id": result.exact_match.entity_id,
                        "canonical_name": result.exact_match.canonical_name,
                        "confidence": result.exact_match.confidence_score,
                        "uen": result.exact_match.uen,
                        "lei": result.exact_match.lei,
                    },
                    tags=["entity_resolution", entity_name.split()[0].lower()],
                    importance=0.9 if result.exact_match.confidence_score > 80 else 0.5,
                )
            except Exception as e:
                logger.debug(f"Could not write to shared memory: {e}")

        return result

    # Alias for backward compatibility
    async def resolve(
        self,
        raw_query: str,
        country_hint: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Resolve entity (backward compatibility alias).

        See resolve_entity() for details.
        """
        return await self.resolve_entity(raw_query, country_hint, session_id)

    # -------------------------------------------------------------------------
    # Signature-Based Methods
    # -------------------------------------------------------------------------

    async def _run_resolution_task(
        self,
        entity_name: str,
        country_hint: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run resolution and format for signature output.

        Called when run() is invoked in an async context.
        """
        result = await self.resolve_entity(entity_name, country_hint)
        return self._format_resolution_response(result)

    def _format_resolution_response(self, result: ResolutionResult) -> dict[str, Any]:
        """
        Format ResolutionResult into signature output format.

        Args:
            result: ResolutionResult from resolve_entity

        Returns:
            Dict matching EntityResolutionSignature output fields
        """
        exact_match = result.exact_match
        candidates = result.candidates or []

        return {
            "resolved_entity_id": exact_match.entity_id if exact_match else None,
            "canonical_name": exact_match.canonical_name if exact_match else None,
            "confidence_score": exact_match.confidence_score if exact_match else 0.0,
            "requires_confirmation": str(result.requires_confirmation).lower(),
            "candidates": json.dumps(
                [c.to_dict() for c in candidates[:5]] if candidates else []
            ),
            "status": result.status.value,
        }

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """
        Synchronous run method for A2A Router compatibility.

        Handles both direct calls (entity_name=) and Pipeline.router calls (task=).

        Args:
            **kwargs: Resolution parameters (entity_name/task, country_hint)

        Returns:
            Resolution results matching signature output fields
        """
        # Handle Pipeline.router calls with task= parameter
        task = kwargs.get("task", "")
        entity_name = kwargs.get("entity_name", "")
        country_hint = kwargs.get("country_hint")

        # Extract entity_name from task if provided
        if task and not entity_name:
            # Use task as entity name (the router matched this to entity resolution)
            entity_name = task

        if not entity_name:
            return {
                "resolved_entity_id": None,
                "canonical_name": None,
                "confidence_score": 0.0,
                "requires_confirmation": "false",
                "candidates": "[]",
                "status": "no_match",
                "error": "entity_name required",
            }

        logger.info(f"EntityResolutionAgent.run() - entity_name: {entity_name}")

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Return coroutine for the caller to await
                # This is handled by the registry's _direct_agent_execution
                return self._run_resolution_task(entity_name, country_hint)
            else:
                result = loop.run_until_complete(
                    self.resolve_entity(entity_name, country_hint)
                )
        except RuntimeError:
            # No event loop, create one
            result = asyncio.run(self.resolve_entity(entity_name, country_hint))

        return self._format_resolution_response(result)


# =============================================================================
# Singleton Factory
# =============================================================================

_agent_instance: Optional[EntityResolutionAgent] = None


def get_entity_resolution_agent() -> EntityResolutionAgent:
    """Get singleton agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EntityResolutionAgent()
    return _agent_instance


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================

# Keep these for backward compatibility with existing imports
EntityResolutionReActAgent = EntityResolutionAgent
