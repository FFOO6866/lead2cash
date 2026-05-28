"""
Marine Engine Knowledge Base Agent

Kaizen-based AI agent for marine engine knowledge base operations including:
- Entity extraction from news articles
- Entity resolution against the knowledge base
- Technical and market classification
- Relevance scoring and prioritization

Architecture:
    - Built on Kaizen BaseAgent for production-ready agent features
    - Integrates with knowledge base services for entity resolution
    - Uses LLM for structured entity extraction
    - PostgreSQL + pgvector for semantic search
    - Rule-based scoring for deterministic classification

Usage:
    from lead_to_cash.agents import KnowledgeBaseAgent, KnowledgeBaseConfig

    config = KnowledgeBaseConfig()
    agent = KnowledgeBaseAgent(config)

    # Process an article
    result = await agent.process_article(article_content, article_title)

    # Query the knowledge base
    answer = await agent.query("What engines does Wärtsilä make?")
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

from kaizen.core.base_agent import BaseAgent
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

from lead_to_cash.agents.signatures import ProductIntelSignature
from lead_to_cash.services.knowledge_base.constants import (
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_EXTRACTION_TEMPERATURE,
    DEFAULT_REASONING_MODEL,
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    MIN_EXTRACTION_CONFIDENCE,
    TARGET_POWER_MAX_KW,
    TARGET_POWER_MIN_KW,
    TARGET_RPM_MAX,
    TARGET_RPM_MIN,
    TIER_1_MANUFACTURERS,
)
from lead_to_cash.services.knowledge_base.database import (
    KnowledgeBaseDatabase,
    get_knowledge_base_db,
)
from lead_to_cash.services.knowledge_base.embedding_service import (
    KBEmbeddingService,
    get_kb_embedding_service,
)
from lead_to_cash.services.knowledge_base.entity_resolver import (
    EntityResolver,
    get_entity_resolver,
)
from lead_to_cash.services.knowledge_base.models import (
    ArticleScore,
    ClassifiedArticle,
    ExtractedEntity,
    MarketSegmentType,
    RelevanceClassification,
    ResolvedEntity,
)
from lead_to_cash.services.knowledge_base.scorer import (
    RelevanceScorer,
    ScoringInput,
    get_relevance_scorer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Signature Definitions
# =============================================================================


class EntityExtractionSignature(Signature):
    """
    Signature for extracting marine engine entities from article content.

    Takes article text and extracts manufacturers, engines, and related entities.
    """

    # Input Fields
    article_content: str = InputField(
        description="Full article text to analyze for marine engine entities"
    )
    article_title: str = InputField(
        description="Article title for context",
        default="",
    )

    # Output Fields
    entities: str = OutputField(
        description="""JSON array of extracted entities. Each entity must have:
- text: The exact text as found in the article
- entity_type: One of "manufacturer", "engine_series", "engine_model", "application", "vessel_type"
- confidence: 0-1 confidence in the extraction
- context: Surrounding text snippet
- rpm: Optional RPM value if mentioned
- power_kw: Optional power in kW if mentioned
- fuel_type: Optional fuel type if mentioned"""
    )
    summary: str = OutputField(
        description="Brief summary of key entities and their relevance (2-3 sentences)"
    )
    has_engine_content: str = OutputField(
        description="'true' if article contains marine engine related content, 'false' otherwise"
    )


class ClassificationSignature(Signature):
    """
    Signature for classifying articles with resolved entities.

    Takes resolved entities and article content to determine market segments
    and commercial signals.
    """

    # Input Fields
    article_content: str = InputField(
        description="Full article text for classification"
    )
    resolved_entities: str = InputField(
        description="JSON of resolved KB entities with their classifications"
    )

    # Output Fields
    market_segments: str = OutputField(
        description="""JSON array of applicable market segments:
- marine_transportation
- offshore_oil_gas
- fpso_offshore_production
- marine_power_generation
- land_power_plant"""
    )
    commercial_signals: str = OutputField(
        description="""JSON array of detected commercial signals:
- new_vessel_order
- fleet_retrofit
- product_launch
- regulatory_change
- financial_results"""
    )
    applications: str = OutputField(
        description="""JSON array of applicable applications:
- propulsion
- genset
- auxiliary
- offshore_power
- fpso
- drilling"""
    )


class KBQuerySignature(Signature):
    """
    Signature for answering questions about the knowledge base.
    """

    # Input Fields
    question: str = InputField(
        description="User's question about marine engines or manufacturers"
    )
    context: str = InputField(
        description="Retrieved context from knowledge base",
        default="",
    )

    # Output Fields
    answer: str = OutputField(
        description="Comprehensive answer based on the knowledge base"
    )
    sources: str = OutputField(
        description="JSON array of sources used to answer the question"
    )
    confidence: str = OutputField(
        description="Confidence level: 'high', 'medium', or 'low'"
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class KnowledgeBaseConfig:
    """
    Configuration for Knowledge Base Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    Uses constants from knowledge_base.constants for consistency.
    """

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = DEFAULT_REASONING_MODEL
    extraction_model: str = DEFAULT_EXTRACTION_MODEL
    temperature: float = DEFAULT_EXTRACTION_TEMPERATURE
    max_tokens: int = 4000

    # Entity Extraction Configuration
    min_confidence_threshold: float = MIN_EXTRACTION_CONFIDENCE
    enable_fuzzy_matching: bool = True
    enable_semantic_matching: bool = True

    # Scoring Configuration
    scoring_model_version: str = "v1"

    # Agent Metadata
    agent_name: str = "knowledge_base_agent"
    agent_description: str = (
        "Marine engine knowledge base with entity extraction, "
        "resolution, classification, and relevance scoring"
    )

    # Target engine specifications (from constants)
    target_rpm_min: int = TARGET_RPM_MIN
    target_rpm_max: int = TARGET_RPM_MAX
    target_power_min_kw: float = TARGET_POWER_MIN_KW
    target_power_max_kw: float = TARGET_POWER_MAX_KW

    # Tier-1 manufacturers (from constants)
    tier_1_manufacturers: list[str] = field(
        default_factory=lambda: TIER_1_MANUFACTURERS.copy()
    )


# =============================================================================
# Knowledge Base Agent Implementation
# =============================================================================


class KnowledgeBaseAgent(BaseAgent):
    """
    Marine Engine Knowledge Base Agent (alias: ProductIntelAgent).

    Part of the Intelligence Domain (ADR-002).

    Provides AI-powered knowledge base operations for marine engine intelligence:
    - Entity extraction from news articles
    - Entity resolution against structured KB
    - Technical and market classification
    - Rule-based relevance scoring
    - RAG-based question answering

    Capabilities:
    - Extract engine manufacturers, series, and models from text
    - Resolve extracted entities against the knowledge base
    - Classify articles by market segment and commercial signals
    - Score article relevance using deterministic rules
    - Answer questions about engines and manufacturers

    Features:
    - LLM-powered entity extraction
    - Hybrid entity resolution (exact → alias → fuzzy → semantic)
    - Rule-based scoring (no ML variance)
    - pgvector semantic search
    - Shared memory for multi-agent coordination

    Example:
        config = KnowledgeBaseConfig()
        agent = KnowledgeBaseAgent(config)

        # Process article
        result = await agent.process_article(content, title)
        print(f"Classification: {result.classification}")
        print(f"Score: {result.total_score}")

        # Query knowledge base
        answer = await agent.query("What is the power range of Wärtsilä 31?")
    """

    # A2A signature reference for capability matching (ADR-002)
    SIGNATURE = ProductIntelSignature

    def __init__(
        self,
        config: KnowledgeBaseConfig,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize Knowledge Base Agent.

        Args:
            config: Agent configuration
            shared_memory: Optional shared memory pool for multi-agent coordination
            agent_id: Unique agent identifier
        """
        super().__init__(
            config=config,
            signature=EntityExtractionSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
        )

        self._shared_memory = shared_memory
        self.domain_config = config

        # Initialize services (lazy)
        self._db: Optional[KnowledgeBaseDatabase] = None
        self._embedding_service: Optional[KBEmbeddingService] = None
        self._entity_resolver: Optional[EntityResolver] = None
        self._scorer: Optional[RelevanceScorer] = None
        self._initialized = False

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all knowledge base services."""
        if self._initialized:
            return

        logger.info("Initializing Knowledge Base Agent...")

        # Initialize database
        self._db = get_knowledge_base_db()
        await self._db.initialize()

        # Initialize embedding service
        self._embedding_service = get_kb_embedding_service()
        await self._embedding_service.initialize()

        # Initialize entity resolver
        self._entity_resolver = get_entity_resolver()
        await self._entity_resolver.initialize()

        # Initialize scorer
        self._scorer = get_relevance_scorer()

        self._initialized = True
        logger.info("Knowledge Base Agent initialized successfully")

    async def _ensure_initialized(self) -> None:
        """Ensure services are initialized."""
        if not self._initialized:
            await self.initialize()

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
                name="engine_entity_extraction",
                domain="marine_intelligence",
                level=CapabilityLevel.EXPERT,
                description="Extract marine engine entities from articles and documents",
                keywords=[
                    "engine",
                    "manufacturer",
                    "wärtsilä",
                    "wartsila",
                    "man",
                    "caterpillar",
                    "mak",
                    "hyundai",
                    "himsen",
                    "bergen",
                    "medium speed",
                    "marine engine",
                    "power rating",
                    "rpm",
                    "kilowatt",
                    "kw",
                    "dual fuel",
                    "lng",
                ],
                examples=[
                    "Extract engine information from this article",
                    "What manufacturer is mentioned in this news?",
                    "Identify the engine model specifications",
                    "Parse engine specs from this document",
                ],
                constraints=[],
            ),
            Capability(
                name="article_relevance_scoring",
                domain="marine_intelligence",
                level=CapabilityLevel.EXPERT,
                description="Score article relevance for marine engine commercial opportunities",
                keywords=[
                    "relevance",
                    "priority",
                    "score",
                    "classify",
                    "offshore",
                    "fpso",
                    "vessel order",
                    "contract",
                    "newbuild",
                    "retrofit",
                    "market",
                    "commercial",
                ],
                examples=[
                    "Score this article for commercial relevance",
                    "Is this article high priority for marine engines?",
                    "Classify this news by market segment",
                    "What is the relevance score of this article?",
                ],
                constraints=[],
            ),
            Capability(
                name="knowledge_base_query",
                domain="marine_engines",
                level=CapabilityLevel.EXPERT,
                description="Answer questions about marine engines and manufacturers",
                keywords=[
                    "engine",
                    "specs",
                    "specifications",
                    "power",
                    "rpm",
                    "manufacturer",
                    "model",
                    "series",
                    "compare",
                    "lookup",
                ],
                examples=[
                    "What is the power range of Wärtsilä 31?",
                    "Compare MAN 48/60CR with Bergen B36:45",
                    "Which engines are suitable for FPSO applications?",
                    "List all dual-fuel engines in the knowledge base",
                ],
                constraints=[],
            ),
        ]

    # -------------------------------------------------------------------------
    # Entity Extraction
    # -------------------------------------------------------------------------

    async def extract_entities(
        self, content: str, title: str = ""
    ) -> list[ExtractedEntity]:
        """
        Extract marine engine entities from article content using LLM.

        Args:
            content: Article text
            title: Article title for context

        Returns:
            List of extracted entities
        """
        await self._ensure_initialized()

        # Build prompt
        inputs = {
            "article_content": content[:15000],  # Truncate if too long
            "article_title": title,
        }

        try:
            # Run extraction through BaseAgent
            result = await self.run(
                input_data=inputs,
                system_prompt=ENTITY_EXTRACTION_SYSTEM_PROMPT,
            )

            # Parse entities from result
            entities_json = result.get("entities", "[]")
            if isinstance(entities_json, str):
                entities_data = json.loads(entities_json)
            else:
                entities_data = entities_json

            # Pre-compute normalized article text for grounding validation (once, outside loop)
            normalized_article_text = self._normalize_unicode(content[:15000])

            entities = []
            rejected_count = 0
            for e in entities_data:
                entity = ExtractedEntity(
                    text=e.get("text", ""),
                    entity_type=e.get("entity_type", "unknown"),
                    confidence=float(e.get("confidence", 0.5)),
                    context=e.get("context"),
                    rpm=e.get("rpm"),
                    power_kw=e.get("power_kw"),
                    fuel_type=e.get("fuel_type"),
                )
                if entity.confidence < self.domain_config.min_confidence_threshold:
                    continue

                # Grounding check: entity text must appear in the original article
                # This prevents prompt injection from inventing fake entities
                if not entity.text or not entity.text.strip():
                    logger.warning(
                        "Rejected entity with empty text (possible prompt injection)"
                    )
                    rejected_count += 1
                    continue

                # Use word boundary matching to avoid substring false positives
                # (e.g. "2000" matching inside "Series 2000" is OK, but not "200045")
                normalized_entity = self._normalize_unicode(entity.text)

                # Reject entities that normalize to empty (e.g. pure CJK characters)
                if not normalized_entity.strip():
                    logger.warning(
                        f"Rejected entity '{entity.text}' — normalizes to empty string"
                    )
                    rejected_count += 1
                    continue

                if not re.search(
                    r'\b' + re.escape(normalized_entity) + r'\b',
                    normalized_article_text,
                ):
                    logger.warning(
                        f"Rejected entity '{entity.text}' — not found in article text "
                        f"(possible prompt injection)"
                    )
                    rejected_count += 1
                    continue

                entities.append(entity)

            if rejected_count > 0:
                logger.warning(
                    f"Rejected {rejected_count} entities not grounded in article text"
                )

            # Article-level confidence quality gate:
            # If average confidence is too low, the extraction is unreliable
            if entities:
                avg_confidence = sum(e.confidence for e in entities) / len(entities)
                low_confidence_count = sum(
                    1 for e in entities if e.confidence < 0.7
                )
                low_confidence_ratio = low_confidence_count / len(entities)

                if avg_confidence < 0.6 or low_confidence_ratio > 0.5:
                    logger.warning(
                        f"Low-quality extraction: avg_confidence={avg_confidence:.2f}, "
                        f"low_confidence_ratio={low_confidence_ratio:.1%} "
                        f"({low_confidence_count}/{len(entities)} entities below 0.7). "
                        f"Flagging for review."
                    )
                    # Downgrade all entity confidences to signal low quality
                    for entity in entities:
                        entity.confidence = min(entity.confidence, 0.6)

            logger.info(f"Extracted {len(entities)} entities from article")
            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Entity Resolution
    # -------------------------------------------------------------------------

    async def resolve_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[ResolvedEntity]:
        """
        Resolve extracted entities against the knowledge base.

        Uses hybrid matching: exact → alias → fuzzy → semantic.

        Args:
            entities: List of extracted entities

        Returns:
            List of resolved entities with KB IDs
        """
        await self._ensure_initialized()

        resolved = []
        for entity in entities:
            result = await self._entity_resolver.resolve_extracted(entity)
            if result:
                resolved.append(result)

        logger.info(f"Resolved {len(resolved)}/{len(entities)} entities")
        return resolved

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------

    async def classify_article(
        self,
        content: str,
        resolved_entities: list[ResolvedEntity],
    ) -> tuple[list[MarketSegmentType], list[str], list[str]]:
        """
        Classify article by market segments and commercial signals.

        Args:
            content: Article text
            resolved_entities: Resolved entities from KB

        Returns:
            Tuple of (market_segments, commercial_signals, applications)
        """
        await self._ensure_initialized()

        # Use scorer's keyword detection for base classification
        market_segments = self._scorer.detect_market_segments(content)
        commercial_signals = self._scorer.detect_commercial_signals(content)

        # Also run through LLM for additional context
        try:
            # Prepare entities for prompt
            entities_summary = json.dumps(
                [
                    {
                        "name": e.entity_name,
                        "type": e.entity_type,
                        "rpm_class": e.rpm_class.value if e.rpm_class else None,
                        "power_class": e.power_class.value if e.power_class else None,
                    }
                    for e in resolved_entities
                ],
                indent=2,
            )

            # Use classification signature
            result = await self.run(
                input_data={
                    "article_content": content[:10000],
                    "resolved_entities": entities_summary,
                },
                signature=ClassificationSignature(),
            )

            # Merge LLM results with keyword-based detection
            llm_segments = json.loads(result.get("market_segments", "[]"))
            llm_signals = json.loads(result.get("commercial_signals", "[]"))
            llm_applications = json.loads(result.get("applications", "[]"))

            # Combine (deduplicate)
            all_segments = list(
                set(
                    [s for s in market_segments]
                    + [MarketSegmentType(s) for s in llm_segments if s]
                )
            )

            all_signals = list(set(commercial_signals + llm_signals))

            return all_segments, all_signals, llm_applications

        except Exception as e:
            logger.warning(f"LLM classification failed, using keyword-based: {e}")
            return market_segments, commercial_signals, []

    # -------------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------------

    async def score_article(
        self,
        article_id: str,
        content: str,
        entities: list[ResolvedEntity],
        market_segments: list[MarketSegmentType],
        commercial_signals: list[str],
    ) -> ArticleScore:
        """
        Score article relevance using rule-based scoring.

        Args:
            article_id: Unique article identifier
            content: Article text
            entities: Resolved entities
            market_segments: Detected market segments
            commercial_signals: Detected commercial signals

        Returns:
            ArticleScore with breakdown and classification
        """
        await self._ensure_initialized()

        scoring_input = ScoringInput(
            article_id=article_id,
            article_content=content,
            entities=entities,
            market_segments=market_segments,
            commercial_signals=commercial_signals,
        )

        score = self._scorer.score(scoring_input)

        # Save to database
        try:
            await self._db.create_article_score(score)
        except Exception as e:
            logger.warning(f"Failed to save article score: {e}")

        return score

    # -------------------------------------------------------------------------
    # Full Pipeline
    # -------------------------------------------------------------------------

    async def process_article(
        self, content: str, title: str = "", article_id: Optional[str] = None
    ) -> ClassifiedArticle:
        """
        Full article processing pipeline: extract → resolve → classify → score.

        Args:
            content: Article text
            title: Article title
            article_id: Optional article ID (generated if not provided)

        Returns:
            ClassifiedArticle with all classifications and scores
        """
        await self._ensure_initialized()

        import uuid

        if article_id is None:
            article_id = str(uuid.uuid4())

        logger.info(f"Processing article: {title[:50]}...")

        # 1. Extract entities
        extracted = await self.extract_entities(content, title)

        # 2. Resolve entities against KB
        resolved = await self.resolve_entities(extracted)

        # 3. Classify article
        market_segments, commercial_signals, applications = await self.classify_article(
            content, resolved
        )

        # 4. Score relevance
        score = await self.score_article(
            article_id, content, resolved, market_segments, commercial_signals
        )

        # 5. Build classified article
        # Collect classifications from resolved entities
        from lead_to_cash.services.knowledge_base.models import (
            ApplicationType,
        )

        rpm_classes = list(set(e.rpm_class for e in resolved if e.rpm_class))
        power_classes = list(set(e.power_class for e in resolved if e.power_class))

        # Collect affected manufacturers (competitors)
        affected_competitors = list(
            set(e.entity_name for e in resolved if e.entity_type == "manufacturer")
        )

        # Build summary
        summary = f"Article mentions {len(resolved)} marine engine entities"
        if affected_competitors:
            summary += f" from {', '.join(affected_competitors[:3])}"
        summary += f". Classification: {score.classification.upper()}"

        classified = ClassifiedArticle(
            article_id=article_id,
            article_title=title,
            article_summary=summary,
            entities=resolved,
            rpm_classes=rpm_classes,
            power_classes=power_classes,
            fuel_types=[],  # Would need to extract from entities
            market_segments=market_segments,
            applications=[ApplicationType(a) for a in applications if a],
            commercial_signals=commercial_signals,
            technical_score=score.technical_score,
            market_score=score.market_score,
            commercial_score=score.commercial_score,
            total_score=score.total_score,
            classification=RelevanceClassification(score.classification),
            affected_competitors=affected_competitors,
        )

        logger.info(
            f"Article processed: {score.classification} (score: {score.total_score})"
        )
        return classified

    # -------------------------------------------------------------------------
    # Knowledge Base Query
    # -------------------------------------------------------------------------

    async def query(
        self, question: str, user_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Answer questions about the knowledge base using RAG.

        Args:
            question: User's question
            user_id: Optional user identifier for per-user rate limiting

        Returns:
            Dict with answer, sources, and confidence
        """
        await self._ensure_initialized()

        # Search for relevant entities
        search_results = await self._embedding_service.search_entities(
            query=question,
            user_id=user_id,
            top_k=10,
            min_similarity=0.5,
        )

        # Build context from search results
        context_parts = []
        sources = []

        for result in search_results:
            entity_type = result["entity_type"]
            entity_id = result["entity_id"]

            # Fetch entity details — include all available fields for LLM context
            if entity_type == "manufacturer":
                entity = await self._db.get_manufacturer(entity_id)
                if entity:
                    parts = [f"Manufacturer: {entity.name} ({entity.country}), Tier: {entity.tier}"]
                    if entity.description:
                        parts.append(f"  Description: {entity.description}")
                    if entity.website:
                        parts.append(f"  Website: {entity.website}")
                    context_parts.append("\n".join(parts))
                    sources.append({"type": "manufacturer", "name": entity.name})

            elif entity_type == "engine_model":
                entity = await self._db.get_engine_model(entity_id)
                if entity:
                    parts = [
                        f"Engine: {entity.model_name}, "
                        f"RPM: {entity.rpm_min}-{entity.rpm_max}, "
                        f"Power: {entity.power_min_kw}-{entity.power_max_kw} kW"
                    ]
                    fuel_types = entity.get_fuel_types_list()
                    if fuel_types:
                        parts.append(f"  Fuel Types: {', '.join(fuel_types)}")
                    if entity.emission_tier:
                        parts.append(f"  Emission Tier: {entity.emission_tier}")
                    if entity.cylinders:
                        config_str = f"  Configuration: {entity.cylinders} cylinders"
                        if entity.configuration:
                            config_str += f" ({entity.configuration})"
                        parts.append(config_str)
                    if entity.dry_weight_kg:
                        parts.append(f"  Dry Weight: {entity.dry_weight_kg:,.0f} kg")
                    if entity.length_mm and entity.width_mm and entity.height_mm:
                        parts.append(
                            f"  Dimensions (LxWxH): "
                            f"{entity.length_mm:,.0f} x {entity.width_mm:,.0f} x {entity.height_mm:,.0f} mm"
                        )
                    if not entity.is_current_production:
                        parts.append("  Status: Discontinued")
                    context_parts.append("\n".join(parts))
                    sources.append({"type": "engine_model", "name": entity.model_name})

            elif entity_type == "engine_series":
                entity = await self._db.get_engine_series(entity_id)
                if entity:
                    parts = [f"Engine Series: {entity.brand} {entity.series_name}"]
                    if entity.description:
                        parts.append(f"  Description: {entity.description}")
                    if entity.year_introduced:
                        parts.append(f"  Introduced: {entity.year_introduced}")
                    if not entity.is_current:
                        parts.append("  Status: Discontinued")
                    context_parts.append("\n".join(parts))
                    sources.append({"type": "engine_series", "name": f"{entity.brand} {entity.series_name}"})

        # Cap context to avoid exceeding LLM input limits
        context = "\n".join(context_parts) if context_parts else "No relevant data found."
        if len(context) > 8000:
            context = context[:8000] + "\n[... additional results truncated]"

        # Guard: If no relevant data found in KB, return explicit "not found"
        # instead of letting the LLM synthesize/hallucinate an answer
        if not context_parts:
            return {
                "answer": (
                    "I don't have information about that in our product database. "
                    "The query did not match any verified engine models, manufacturers, "
                    "or product specifications in our knowledge base. "
                    "Please check the model name or ask about a specific MTU engine series "
                    "(e.g., Series 2000, Series 4000)."
                ),
                "sources": [],
                "confidence": "high",
                "context_used": False,
            }

        # Run through LLM (run() is synchronous)
        try:
            result = self.run(
                input_data={
                    "question": question,
                    "context": context,
                },
                signature=KBQuerySignature(),
            )

            answer_text = result.get("answer", "Unable to answer the question.")
            confidence = result.get("confidence", "low")

            # Grounding validation: check if answer stays within context
            grounded = self._check_answer_grounding(answer_text, context, sources)
            if not grounded:
                confidence = "low"
                logger.warning(
                    "Answer may contain claims not grounded in KB context — "
                    "downgraded confidence to low"
                )

            return {
                "answer": answer_text,
                "sources": sources,
                "confidence": confidence,
                "context_used": len(context_parts) > 0,
            }

        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return {
                "answer": (
                    "An error occurred processing your query. "
                    "Please try again or rephrase your question."
                ),
                "sources": [],
                "confidence": "low",
                "context_used": False,
            }

    # -------------------------------------------------------------------------
    # Grounding Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """Normalize Unicode to ASCII for grounding comparison (e.g. Wärtsilä → Wartsila)."""
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()

    @staticmethod
    def _check_answer_grounding(
        answer: str,
        context: str,
        sources: list[dict],
    ) -> bool:
        """
        Validate that the LLM answer is grounded in the provided context.

        Checks that numeric claims (kW, RPM, etc.) in the answer also appear
        in the KB context. This prevents the LLM from fabricating specifications.

        Args:
            answer: LLM-generated answer text
            context: KB context that was provided to the LLM
            sources: List of source dicts with entity names

        Returns:
            True if answer appears grounded, False if suspicious claims detected
        """
        if not answer:
            return True  # Nothing to validate

        # Extract numeric values (3+ digits) from answer and context
        answer_numbers = set(re.findall(r'\d{3,}', answer))
        context_numbers = set(re.findall(r'\d{3,}', context))

        # Numbers in answer but not in context could be hallucinated specs
        fabricated_numbers = answer_numbers - context_numbers
        # Filter out common non-spec numbers (years, series names)
        fabricated_numbers = {
            n for n in fabricated_numbers
            if not (1900 <= int(n) <= 2100)  # Years
            and int(n) not in (1000, 2000, 3000, 4000, 5000, 8000, 10000)  # Series names
        }

        if len(fabricated_numbers) > 1:
            logger.warning(
                f"Answer contains {len(fabricated_numbers)} numeric values "
                f"not found in context: {list(fabricated_numbers)[:5]}"
            )
            return False

        return True

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
                name="entity_extraction",
                domain="knowledge_base",
                level=CapabilityLevel.EXPERT,
                description="Extract marine engine entities from articles and text",
                keywords=[
                    "extract",
                    "entity",
                    "manufacturer",
                    "engine",
                    "model",
                    "series",
                    "marine",
                    "article",
                    "news",
                ],
                examples=[
                    "Extract engine mentions from this article",
                    "What manufacturers are mentioned?",
                    "Parse engine specifications from text",
                ],
                constraints=[],
            ),
            Capability(
                name="product_knowledge",
                domain="product_intel",
                level=CapabilityLevel.EXPERT,
                description="Answer questions about marine engine specifications, features, and applications",
                keywords=[
                    "engine",
                    "specification",
                    "specs",
                    "power",
                    "rpm",
                    "application",
                    "marine",
                    "propulsion",
                    "genset",
                    "wärtsilä",
                    "mtu",
                    "man",
                    "caterpillar",
                ],
                examples=[
                    "What is the power range of MTU 16V4000?",
                    "Compare Wärtsilä 31 vs MAN 51/60",
                    "Which engines are suitable for fast ferries?",
                ],
                constraints=[],
            ),
            Capability(
                name="product_fit",
                domain="product_intel",
                level=CapabilityLevel.ADVANCED,
                description="Evaluate product fit for specific applications and requirements",
                keywords=[
                    "fit",
                    "suitable",
                    "recommend",
                    "match",
                    "application",
                    "requirement",
                    "power range",
                    "rpm range",
                ],
                examples=[
                    "Which MTU engine fits a 500kW application?",
                    "Recommend engines for container vessel auxiliary",
                    "Is Wärtsilä 31 suitable for fast ferry?",
                ],
                constraints=[],
            ),
            Capability(
                name="article_classification",
                domain="intelligence",
                level=CapabilityLevel.ADVANCED,
                description="Classify articles by market segment and commercial signals",
                keywords=[
                    "classify",
                    "classification",
                    "market",
                    "segment",
                    "relevance",
                    "score",
                    "commercial",
                    "signal",
                ],
                examples=[
                    "Classify this article by market segment",
                    "Score article relevance for marine propulsion",
                    "What commercial signals are in this news?",
                ],
                constraints=[],
            ),
        ]

    # -------------------------------------------------------------------------
    # Synchronous Run Method (A2A Router Compatibility)
    # -------------------------------------------------------------------------

    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Synchronous run method for A2A Router compatibility.

        Handles both direct calls (query=) and Pipeline.router calls (task=).

        Args:
            task: Primary input from Pipeline.router()
            query: Direct query input (alias for task)
            **kwargs: Additional parameters

        Returns:
            Standardized response dict with success, agent_id, result_data
        """
        import asyncio

        # Extract task (Pipeline.router convention) or query
        task = kwargs.get("task", "")
        query = kwargs.get("query") or task

        if not query:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": "No query provided. Use task= or query=",
                "metadata": {"routing": "a2a_run"},
            }

        async def _execute():
            try:
                # Ensure initialized
                if not self._initialized:
                    await self.initialize()

                result = await self.query(query)
                return {
                    "success": True,
                    "agent_id": self.agent_id,
                    "result_data": result,
                    "error_message": None,
                    "metadata": {"routing": "a2a_run", "query": query},
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

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check agent and service health.

        Returns:
            Health status with agent_id, status, capabilities, and service availability
        """
        from datetime import datetime, timezone

        # Get capabilities via _extract_primary_capabilities()
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        if not self._initialized:
            return {
                "agent_id": self.agent_id,
                "status": "unhealthy",
                "capabilities": capabilities,
                "error": "Not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            db_health = await self._db.health_check()
            embedding_stats = await self._embedding_service.get_embedding_stats()

            # Determine overall status
            db_ok = db_health.get("healthy", False)
            embedding_ok = embedding_stats.get("with_embedding", 0) > 0

            if db_ok and embedding_ok:
                status = "healthy"
            elif db_ok:
                status = "degraded"  # DB ok but no embeddings
            else:
                status = "unhealthy"

            return {
                "agent_id": self.agent_id,
                "status": status,
                "capabilities": capabilities,
                "initialized": self._initialized,
                "database": db_health,
                "embeddings": embedding_stats,
                "config": {
                    "model": self.domain_config.model,
                    "min_confidence": self.domain_config.min_confidence_threshold,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "agent_id": self.agent_id,
                "status": "unhealthy",
                "capabilities": capabilities,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._db:
            await self._db.close()
        self._initialized = False
        logger.info("Knowledge Base Agent closed")
