"""
Competitor Intelligence Agent

RAG-based agent for tracking CAT, Cummins, MAN - their moves, wins,
products, and threat assessment for RRPS sales operations.

MANDATORY GUIDE REFERENCE:
    This agent MUST follow the standardized output format defined in:
    `src/lead_to_cash/docs/guides/competitor_intel_guide.md`

DOMAIN BOUNDARIES (from agent_architecture.md):
    This agent OWNS (exclusively):
    - Competitor wins (contract wins by CAT/Cummins/MAN)
    - Competitor products (product launches, specs)
    - Competitor partnerships (alliances, distributor deals)
    - Competitor financials (SEC filings, quarterly results)
    - Threat assessment (HIGH/MEDIUM/LOW threat level)
    - Competitor at customer (competitor activity at our accounts)
    - Market share (segment share analysis)
    - Competitor pricing (pricing intelligence when available)

    This agent does NOT own:
    - General industry news -> MarketIntelAgent
    - Customer relationship data -> CustomerIntelAgent
    - Competitor company risk -> KYPAgent
    - Our product positioning -> ProductFitAgent

    Anti-Hallucination Rules:
    - ONLY report facts from verified SEC filings or press releases
    - NEVER assert competitive advantages without evidence
    - NEVER estimate financials - use official filings only
    - All findings MUST include verifiable source URL

    Threat Levels:
    - HIGH: Competitor winning at our customer, or in our stronghold segment
    - MEDIUM: Competitor active in our market, general competitive pressure
    - LOW: Competitor activity outside our focus areas

    Tracked Competitors:
    - Caterpillar (CAT, MaK): M32C, M43C, M46DF
    - Cummins: QSK60, QSK78, QSK95
    - MAN Energy Solutions (MAN ES): 32/44CR, 48/60CR

Architecture:
    - Built on Kaizen BaseAgent for production-ready features
    - Uses vector similarity search for document retrieval
    - Generates contextual answers with source citations
    - Supports real-time Perplexity queries for fresh data
    - A2A semantic routing via Pipeline.router()

Usage:
    from lead_to_cash.agents import CompetitorIntelAgent, CompetitorIntelConfig

    config = CompetitorIntelConfig()
    agent = CompetitorIntelAgent(config)

    result = await agent.query("What are Caterpillar's recent marine engine wins?")
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.base_agent import BaseAgent
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from lead_to_cash.agents.signatures import CompetitorIntelSignature
from lead_to_cash.services.competitor_intel import get_scraper_service
from lead_to_cash.services.competitor_intel.database import get_competitor_db
from lead_to_cash.services.competitor_intel.embedding_service import (
    get_embedding_service,
)

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
# All output from this agent MUST comply with the competitor intelligence guide.
# See: src/lead_to_cash/docs/guides/competitor_intel_guide.md

GUIDE_PATH = "src/lead_to_cash/docs/guides/competitor_intel_guide.md"

# Domain boundaries (from agent_architecture.md):
# OWNS: competitor_wins, competitor_products, competitor_partnerships,
#       competitor_financials, threat_assessment, competitor_at_customer,
#       market_share, competitor_pricing
# DOES NOT OWN: general industry news, customer relationship, risk assessment, product positioning

# Key requirements from guide:
# 1. Competitor identification: CAT, Cummins, MAN (with aliases)
# 2. Activity types: WIN, LAUNCH, PARTNERSHIP, FINANCIAL
# 3. Threat Level (HIGH/MEDIUM/LOW):
#    - HIGH: Competitor winning at our customer, or in our stronghold
#    - MEDIUM: Competitor active in our market
#    - LOW: Activity outside our focus areas
# 4. Anti-Hallucination:
#    - Every finding MUST include source URL
#    - NEVER assert "market leader" without evidence
#    - Financial data MUST come from SEC filings


# =============================================================================
# Signature Definition (Internal Kaizen Signature)
# =============================================================================


class CompetitorIntelAgentSignature(Signature):
    """
    Internal Kaizen signature for BaseAgent compatibility.

    Answers questions about competitors using RAG with embedded documents
    and optional real-time search for the latest information.

    Note: For A2A capability matching, use CompetitorIntelSignature from signatures.py.
    """

    # Input Fields
    query: str = InputField(
        description="User question about competitors (Caterpillar, Cummins, MAN Energy Solutions)"
    )
    context: str = InputField(
        description="Retrieved competitor intelligence documents as context",
        default="",
    )
    competitor_filter: str = InputField(
        description="Optional competitor filter: caterpillar, cummins, man_energy, or all",
        default="all",
    )

    # Output Fields
    answer: str = OutputField(
        description="Detailed answer based on competitor intelligence. Include specific facts, "
        "figures, and dates. Highlight actionable insights for sales."
    )
    sources: str = OutputField(
        description="JSON array of source URLs and document references used"
    )
    confidence: str = OutputField(
        description="Confidence level: high (multiple sources), medium (limited sources), "
        "low (no direct sources, based on general knowledge)"
    )
    key_insights: str = OutputField(
        description="JSON array of 2-4 key takeaways for sales professionals"
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class CompetitorIntelConfig:
    """
    Configuration for Competitor Intelligence Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")  # gpt-4o supports JSON response format
    temperature: float = 0.3  # Lower for factual responses
    max_tokens: int = 2000
    # Note: use_async_llm only works with OpenAI provider (not mock/test)
    # Our execute_a2a() pattern uses async domain methods directly instead

    # RAG Configuration
    top_k_documents: int = 5  # Number of documents to retrieve
    min_similarity_score: float = 0.6  # Minimum similarity threshold
    use_realtime_search: bool = True  # Fall back to Perplexity for fresh data

    # KB Integration
    enable_kb_enrichment: bool = True  # Enable KB entity enrichment for queries

    # Agent Metadata
    agent_name: str = "competitor_intel"
    agent_description: str = (
        "Answers questions about marine engine competitors using embedded intelligence"
    )


# =============================================================================
# Agent Implementation
# =============================================================================


class CompetitorIntelAgent(BaseAgent):
    """
    RAG-based Competitor Intelligence Agent.

    Part of the Intelligence Domain (ADR-002).

    Retrieves relevant competitor documents from the vector store
    and generates intelligent responses with citations.

    Capabilities:
    - Contract wins and deal announcements
    - Customer success stories and case studies
    - Product launches and specifications
    - Strategic moves and partnerships
    - Market positioning and analysis
    - Financial performance

    Example:
        config = CompetitorIntelConfig()
        agent = CompetitorIntelAgent(config)

        # Ask about competitors
        result = await agent.query(
            "What marine engine contracts has Cummins won recently?"
        )
        print(result["answer"])
        print(result["sources"])
    """

    # A2A signature reference for capability matching (ADR-002)
    SIGNATURE = CompetitorIntelSignature

    def __init__(
        self,
        config: CompetitorIntelConfig,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize Competitor Intelligence Agent.

        Args:
            config: Agent configuration
            shared_memory: Optional shared memory pool
            agent_id: Unique agent identifier
        """
        super().__init__(
            config=config,
            signature=CompetitorIntelAgentSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
        )

        self.domain_config = config
        self._shared_memory = shared_memory  # Store for consistent access
        self.db = get_competitor_db()
        self.embedding_service = get_embedding_service()
        self.scraper_service = get_scraper_service()

        # KB Integration for entity enrichment
        self._kb_service: Optional["KBIntegrationService"] = None
        if KB_AVAILABLE and config.enable_kb_enrichment:
            try:
                self._kb_service = get_kb_integration_service()
                logger.info(
                    "KB enrichment service initialized for CompetitorIntelAgent"
                )
            except Exception as e:
                logger.warning(f"KB service initialization failed: {e}")

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
        share competitor intel results and avoid redundant queries.

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

    def _write_query_to_memory(
        self,
        query: str,
        result: dict[str, Any],
    ) -> None:
        """Write query result to shared memory for other agents."""
        if not self._shared_memory:
            return

        # Extract key words for tags
        query_words = [w.lower() for w in query.split()[:3] if len(w) > 2]
        tags = ["competitor", "intel", "query"] + query_words

        # Determine importance based on confidence and insights
        confidence = result.get("confidence", "low")
        importance = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(confidence, 0.5)

        try:
            self.write_to_memory(
                content={
                    "query": query,
                    "answer_summary": result.get("answer", "")[:200],
                    "confidence": confidence,
                    "documents_used": result.get("documents_used", 0),
                    "has_sources": len(result.get("sources", [])) > 0,
                },
                tags=tags,
                importance=importance,
            )
            logger.debug(f"Wrote competitor query result to memory: {query[:50]}")
        except Exception as e:
            logger.debug(f"Failed to write to memory: {e}")

    # -------------------------------------------------------------------------
    # Main Query Interface
    # -------------------------------------------------------------------------

    async def query(
        self,
        question: str,
        competitor: Optional[str] = None,
        content_type: Optional[str] = None,
        use_realtime: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Answer a question about competitors using RAG.

        Args:
            question: User's question
            competitor: Optional filter for specific competitor
            content_type: Optional filter for content type
            use_realtime: Override realtime search setting

        Returns:
            Dictionary with answer, sources, confidence, and insights
        """
        logger.info(f"Processing competitor query: {question[:100]}...")

        # Check shared memory for recent similar query
        query_words = [w.lower() for w in question.split()[:3] if len(w) > 2]
        cached = await self._check_memory_for_context(
            key=question,
            tags=["competitor"] + query_words,
            max_age_seconds=3600.0,  # 1 hour cache TTL
        )

        if cached and cached.get("confidence") == "high":
            logger.info(
                f"High-confidence cached result found for similar query "
                f"(docs_used={cached.get('documents_used', 0)})"
            )
            # Note: For full caching, would need to store complete response
            # Current implementation is for cross-agent awareness

        # Step 1: Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(question)

        # Step 2: Search for relevant documents
        search_results = await self.db.vector_search(
            query_embedding=query_embedding,
            top_k=self.domain_config.top_k_documents,
            competitor=competitor,
            content_type=content_type,
        )

        # Step 3: Batch fetch all parent documents in a single query (avoid N+1)
        # First, collect all unique document IDs from chunks above similarity threshold
        relevant_chunks = [
            (chunk, similarity)
            for chunk, similarity in search_results
            if similarity >= self.domain_config.min_similarity_score
        ]
        doc_ids = list({chunk.document_id for chunk, _ in relevant_chunks})
        docs_map = await self.db.get_documents_by_ids(doc_ids)

        # Step 4: Build context from retrieved documents
        context_parts = []
        sources = []
        document_ids = set()

        for chunk, similarity in relevant_chunks:
            # Get parent document from pre-fetched map
            doc = docs_map.get(chunk.document_id)
            if doc and doc.id not in document_ids:
                document_ids.add(doc.id)
                context_parts.append(
                    f"[{doc.competitor.upper()} - {doc.content_type}]\n"
                    f"Title: {doc.title}\n"
                    f"Content: {chunk.content}\n"
                    f"Source: {doc.source_url}\n"
                )
                if doc.source_url:
                    sources.append(
                        {
                            "url": doc.source_url,
                            "title": doc.title,
                            "competitor": doc.competitor,
                            "type": doc.content_type,
                        }
                    )

        context = "\n---\n".join(context_parts)

        # Step 4b: Enrich context with KB entities (if available)
        kb_enrichment = None
        if self._kb_service and context:
            try:
                await self._kb_service.initialize()
                kb_enrichment = await self._kb_service.enrich_document(
                    content=context,
                    title=question,
                    competitor=competitor,
                )
                # Add KB context to the main context
                all_entities = kb_enrichment.engine_entities + kb_enrichment.manufacturer_entities
                if all_entities:
                    kb_context = "\n[KB ENTITIES]\n"
                    for entity in all_entities[:5]:
                        kb_context += f"- {entity.entity_type}: {entity.entity_name} (confidence: {entity.match_confidence:.2f})\n"
                    context = kb_context + "\n---\n" + context
                # Add competitive positioning if available
                if kb_enrichment.competitive_positioning:
                    pos_context = "\n[COMPETITIVE POSITIONING]\n"
                    for pos in kb_enrichment.competitive_positioning[:3]:
                        pos_context += (
                            f"- {pos.get('our_engine', '?')} vs {pos.get('competitor_engine', '?')}: "
                            f"{pos.get('competitive_position', 'unknown')} "
                            f"(threat: {pos.get('threat_level', 'unknown')})\n"
                        )
                    context = pos_context + context
                logger.info(
                    f"KB enriched query context with {len(all_entities)} entities"
                )
            except Exception as e:
                logger.warning(f"KB enrichment failed for query: {e}")

        # Step 5: If no good results and realtime enabled, search live
        use_rt = (
            use_realtime
            if use_realtime is not None
            else self.domain_config.use_realtime_search
        )

        if not context and use_rt:
            logger.info("No stored documents found, using realtime search")
            realtime_result = await self.scraper_service.search_intelligence(
                question, competitor
            )
            if realtime_result.get("content"):
                context = f"[REALTIME SEARCH]\n{realtime_result['content']}"
                for url in realtime_result.get("sources", [])[:5]:
                    sources.append(
                        {"url": url, "title": "Realtime search", "type": "search"}
                    )

        # Step 6: Generate answer using LLM
        if not context:
            return {
                "answer": (
                    "I don't have specific competitor intelligence stored for this query. "
                    "You can trigger a data refresh to collect the latest information, "
                    "or try rephrasing your question."
                ),
                "sources": [],
                "confidence": "low",
                "key_insights": [],
                "documents_used": 0,
            }

        # Try to run through signature-based agent for enhanced response
        try:
            result = self.run(
                query=question,
                context=context,
                competitor_filter=competitor or "all",
            )

            # Parse outputs
            try:
                parsed_sources = json.loads(result.get("sources", "[]"))
            except json.JSONDecodeError:
                parsed_sources = sources

            try:
                key_insights = json.loads(result.get("key_insights", "[]"))
            except json.JSONDecodeError:
                key_insights = []

            response = {
                "answer": result.get("answer", "Unable to generate answer"),
                "sources": parsed_sources if parsed_sources else sources,
                "confidence": result.get("confidence", "medium"),
                "key_insights": key_insights,
                "documents_used": len(document_ids),
                "query": question,
                "competitor_filter": competitor,
            }
            # Add KB enrichment data if available
            if kb_enrichment:
                all_entities = kb_enrichment.engine_entities + kb_enrichment.manufacturer_entities
                response["kb_entities"] = [
                    {
                        "entity_type": e.entity_type,
                        "entity_id": e.entity_id,
                        "entity_name": e.entity_name,
                        "match_type": e.match_type,
                        "match_confidence": e.match_confidence,
                    }
                    for e in all_entities
                ]
                response["kb_classification"] = {
                    "rpm_classes": [str(r) for r in kb_enrichment.rpm_classes],
                    "power_classes": [str(p) for p in kb_enrichment.power_classes],
                    "affected_competitors": kb_enrichment.affected_competitors,
                }
                response["kb_score"] = {
                    "entity_count": kb_enrichment.entity_count,
                    "competitive_positioning": kb_enrichment.competitive_positioning,
                }

            # Write to shared memory for other agents
            self._write_query_to_memory(question, response)

            return response
        except Exception as e:
            # LLM call failed - return raw context as answer
            logger.warning(f"LLM call failed, returning raw context: {e}")
            fallback_response = {
                "answer": context,
                "sources": sources,
                "confidence": "medium",
                "key_insights": [],
                "documents_used": len(document_ids),
                "query": question,
                "competitor_filter": competitor,
                "note": "Raw intelligence data - LLM summarization unavailable",
            }
            # Still write fallback to memory
            self._write_query_to_memory(question, fallback_response)
            return fallback_response

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def get_competitor_summary(self, competitor: str) -> dict[str, Any]:
        """
        Get a comprehensive summary of a specific competitor.

        Args:
            competitor: Competitor identifier (caterpillar, cummins, man_energy)

        Returns:
            Summary with key information about the competitor
        """
        question = f"""Provide a comprehensive summary of {competitor}'s position in
        the marine engine market including: recent wins, product offerings,
        market position, and strategic initiatives."""

        return await self.query(question, competitor=competitor)

    async def compare_competitors(
        self,
        topic: str,
        competitors: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Compare competitors on a specific topic.

        Args:
            topic: Topic to compare (e.g., "hybrid propulsion", "service network")
            competitors: Optional list of competitors to compare

        Returns:
            Comparative analysis
        """
        comp_list = competitors or ["caterpillar", "cummins", "man_energy"]
        question = f"""Compare {', '.join(comp_list)} on: {topic}.
        Include specific strengths, weaknesses, and recent developments for each."""

        return await self.query(question)

    async def get_recent_wins(
        self,
        competitor: Optional[str] = None,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get recent contract wins.

        Args:
            competitor: Optional competitor filter
            region: Optional region filter (APAC, EMEA, Americas)

        Returns:
            Recent contract wins and deal announcements
        """
        region_filter = f" in {region}" if region else ""
        comp_filter = f" for {competitor}" if competitor else " across all competitors"

        question = f"What are the recent marine engine contract wins{comp_filter}{region_filter}?"

        return await self.query(question, competitor=competitor)

    # -------------------------------------------------------------------------
    # Data Management
    # -------------------------------------------------------------------------

    async def refresh_data(self, competitor: Optional[str] = None) -> dict[str, Any]:
        """
        Trigger a comprehensive data refresh for competitor intelligence.

        Uses all data sources:
        - Web scraping (BeautifulSoup) for product pages, press releases
        - PDF scraping (pypdf) for annual reports
        - Perplexity API for news and market intelligence

        Args:
            competitor: Optional specific competitor to refresh

        Returns:
            Refresh job status with statistics
        """
        from lead_to_cash.services.competitor_intel.pdf_scraper import get_pdf_scraper
        from lead_to_cash.services.competitor_intel.web_scraper import get_web_scraper

        total_docs = 0
        total_chunks = 0
        errors = 0

        # Step 1: Web scraping (BeautifulSoup)
        logger.info("Step 1: Web scraping competitor websites")
        web_scraper = get_web_scraper()
        try:
            if competitor:
                web_docs = await web_scraper.scrape_competitor(competitor)
            else:
                web_docs = await web_scraper.scrape_all_competitors()

            for doc in web_docs:
                try:
                    await self.db.save_document(doc)
                    total_docs += 1
                except Exception as e:
                    logger.error(f"Error saving web doc: {e}")
                    errors += 1
        finally:
            await web_scraper.close()

        # Step 2: Perplexity API (news and intelligence)
        logger.info("Step 2: Fetching news via Perplexity API")
        try:
            if competitor:
                result = await self.scraper_service.refresh_competitor(competitor)
                total_docs += result.get("documents_created", 0)
            else:
                job = await self.scraper_service.refresh_all_competitors()
                total_docs += job.documents_processed
        except Exception as e:
            logger.error(f"Perplexity scraping error: {e}")
            errors += 1

        # Step 3: PDF scraping (annual reports) - only for full refresh
        if not competitor:
            logger.info("Step 3: Scraping annual reports (PDF)")
            pdf_scraper = get_pdf_scraper()
            try:
                pdf_docs = await pdf_scraper.scrape_all_annual_reports()
                for doc in pdf_docs:
                    try:
                        await self.db.save_document(doc)
                        total_docs += 1
                    except Exception as e:
                        logger.error(f"Error saving PDF doc: {e}")
                        errors += 1
            finally:
                await pdf_scraper.close()

        # Step 4: Generate embeddings for all new documents
        logger.info("Step 4: Generating embeddings")
        embed_result = await self.embedding_service.process_all_documents()
        total_chunks = embed_result.get("chunks_created", 0)
        errors += embed_result.get("errors", 0)

        return {
            "status": "completed" if errors == 0 else "completed_with_errors",
            "competitor": competitor,
            "documents_created": total_docs,
            "chunks_created": total_chunks,
            "errors": errors,
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about stored competitor intelligence."""
        return await self.db.get_stats()

    # -------------------------------------------------------------------------
    # A2A Router Compatibility
    # -------------------------------------------------------------------------

    async def execute_a2a(self, **kwargs: Any) -> dict[str, Any]:
        """Custom async domain method for A2A enrichment calls.

        NOTE: This is a CUSTOM method, NOT a Kaizen-native pattern.
        Kaizen's A2A (via to_a2a_card()) is for agent discovery, not execution.

        This method provides direct domain logic execution for inter-agent
        enrichment without the overhead of Kaizen's LLM/memory/hooks features.
        For signature-based execution with full Kaizen features, use run_async().

        Entry Points:
            - run() → Sync entry point, calls domain methods directly
            - run_async() → Kaizen native, uses signatures/memory/hooks (inherited)
            - execute_a2a() → Custom async domain method (this method)

        Args:
            **kwargs: Query parameters (query/task, competitor_filter, context)

        Returns:
            Standardized A2A response dict with success, agent_id, result_data
        """
        # Handle both 'query' and 'task' parameters (Pipeline.router uses 'task')
        query = kwargs.get("query") or kwargs.get("task", "")
        competitor_filter = kwargs.get("competitor_filter", "all")

        if not query:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": "No query provided. Use query= or task=",
                "metadata": {"routing": "a2a_run_async"},
            }

        # Auto-detect competitor from query if not specified
        competitor = self._detect_competitor(query, competitor_filter)

        logger.info(
            f"CompetitorIntelAgent.execute_a2a() - query: {query[:50]}..., competitor: {competitor}"
        )

        try:
            query_result = await self.query(query, competitor=competitor)
            return {
                "success": True,
                "agent_id": self.agent_id,
                "result_data": {
                    "answer": query_result.get("answer"),
                    "sources": query_result.get("sources", []),
                    "confidence": query_result.get("confidence"),
                    "key_insights": query_result.get("key_insights", []),
                    "documents_used": query_result.get("documents_used", 0),
                },
                "error_message": None,
                "metadata": {"routing": "a2a_run_async", "competitor": competitor},
            }
        except Exception as e:
            logger.error(f"CompetitorIntelAgent.execute_a2a() failed: {e}")
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": str(e),
                "metadata": {"routing": "a2a_run_async"},
            }

    def _detect_competitor(self, query: str, competitor_filter: str) -> Optional[str]:
        """Auto-detect competitor from query text."""
        if competitor_filter != "all":
            return competitor_filter

        query_lower = query.lower()
        if "caterpillar" in query_lower:
            return "caterpillar"
        elif "cummins" in query_lower:
            return "cummins"
        elif "man" in query_lower or "man energy" in query_lower:
            return "man_energy"
        return None

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous entry point for CLI/tests and A2A calls.

        This is the standard entry point for inter-agent communication.
        Uses domain-specific logic (query) without LLM/memory overhead.

        For signature-based execution with Kaizen features (memory, hooks, LLM),
        use the inherited run_async() method instead.

        Args:
            **kwargs: Query parameters (query/task, competitor_filter, context)

        Returns:
            Standardized A2A response dict
        """
        return asyncio.run(self.execute_a2a(**kwargs))

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
                name="competitor_intel",
                domain="market_intelligence",
                level=CapabilityLevel.EXPERT,
                description="RAG-based competitor intelligence for marine engine market (Caterpillar, Cummins, MAN)",
                keywords=[
                    "competitor",
                    "competition",
                    "caterpillar",
                    "cummins",
                    "man",
                    "market",
                    "intelligence",
                    "analysis",
                    "rival",
                ],
                examples=[
                    "What contracts has Caterpillar won recently?",
                    "Compare competitors on marine propulsion",
                    "Get competitor summary for Cummins",
                ],
                constraints=[],
            ),
            Capability(
                name="competitor_research",
                domain="research",
                level=CapabilityLevel.ADVANCED,
                description="Research competitor news, products, and market moves",
                keywords=[
                    "research",
                    "news",
                    "products",
                    "strategy",
                    "wins",
                    "contracts",
                    "deals",
                ],
                examples=[
                    "Recent MAN Energy contract wins",
                    "Competitor product launches in marine sector",
                ],
                constraints=[],
            ),
        ]

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check health of competitor intelligence system.

        Returns:
            Health status with agent_id, status, capabilities, and database info
        """
        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        try:
            stats = await self.db.get_stats()
            return {
                "agent_id": self.agent_id,
                "status": "healthy",
                "capabilities": capabilities,
                "total_documents": stats["total_documents"],
                "total_chunks": stats["total_chunks"],
                "documents_by_competitor": stats["documents_by_competitor"],
                "shared_memory_available": self._shared_memory is not None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "status": "unhealthy",
                "capabilities": capabilities,
                "shared_memory_available": self._shared_memory is not None,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# =============================================================================
# Factory Function
# =============================================================================


async def create_competitor_intel_agent(
    llm_provider: str = "openai",
    model: str = os.getenv("OPENAI_BASE_MODEL", "gpt-4"),
    shared_memory: Optional[SharedMemoryPool] = None,
) -> CompetitorIntelAgent:
    """
    Factory function to create a Competitor Intelligence Agent.

    Args:
        llm_provider: LLM provider
        model: Model to use
        shared_memory: Optional shared memory pool

    Returns:
        Configured CompetitorIntelAgent instance
    """
    config = CompetitorIntelConfig(
        llm_provider=llm_provider,
        model=model,
    )

    agent = CompetitorIntelAgent(
        config=config,
        shared_memory=shared_memory,
    )

    # Initialize database
    await agent.db.initialize()

    return agent
