"""
Knowledge Base Integration Service

Bridges the Knowledge Base with MarineIntelAgent and CompetitorIntelAgent
to provide:
- Entity extraction and resolution for opportunities
- Relevance scoring based on engine specifications
- Competitor identification from article content
- Cross-agent coordination via shared memory

Architecture:
                                ┌────────────────────────┐
    MarineIntelAgent ──────────►│                        │
                                │  KBIntegrationService  │
    CompetitorIntelAgent ──────►│                        │
                                │  - extract_and_resolve │
                                │  - score_opportunity   │
                                │  - identify_competitors│
                                │  - enrich_document     │
                                └────────────┬───────────┘
                                             │
                                             ▼
                                ┌────────────────────────┐
                                │   KnowledgeBaseAgent   │
                                │   - entity extraction  │
                                │   - entity resolution  │
                                │   - scoring            │
                                └────────────────────────┘

Usage:
    from lead_to_cash.services.knowledge_base.integration import (
        KBIntegrationService,
        get_kb_integration_service,
    )

    # Initialize
    service = get_kb_integration_service()
    await service.initialize()

    # Enrich a marine opportunity
    enriched = await service.enrich_opportunity(
        content="Wärtsilä wins contract for 12 ferries with 31DF engines...",
        title="Ferry Contract Singapore",
        existing_data={
            "companies_involved": ["Singapore Ferry Co"],
            "vessel_type": "ferry",
            "region": "singapore",
        }
    )

    # enriched contains:
    # - engine_entities: resolved KB entities
    # - affected_competitors: ["Wärtsilä"]
    # - kb_score: 95 (HIGH_PRIORITY)
    # - technical_score, market_score, commercial_score
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from lead_to_cash.config import config
from lead_to_cash.services.knowledge_base.constants import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    MIN_EXTRACTION_CONFIDENCE,
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
    ExtractedEntity,
    MarketSegmentType,
    PowerClass,
    RelevanceClassification,
    ResolvedEntity,
    RPMClass,
)
from lead_to_cash.services.knowledge_base.scorer import (
    RelevanceScorer,
    ScoringInput,
    get_relevance_scorer,
)
from lead_to_cash.services.knowledge_base.seed_competitor_maps import (
    COMPETITIVE_MAPPINGS,
)
from lead_to_cash.utils.logging import get_logger
from lead_to_cash.utils.resilience import (
    CircuitBreaker,
    DistributedCircuitBreaker,
    RedisRateLimiter,
    retry_with_backoff,
)

# Use structured logger with correlation ID support
logger = get_logger(__name__)


# =============================================================================
# ENRICHMENT RESULT DATA STRUCTURES
# =============================================================================


@dataclass
class EnrichedOpportunity:
    """
    Result of KB enrichment for a marine opportunity.

    This is returned by enrich_opportunity() and can be used to
    update MarineOpportunity objects.
    """

    # KB-resolved entities
    engine_entities: list[ResolvedEntity] = field(default_factory=list)
    manufacturer_entities: list[ResolvedEntity] = field(default_factory=list)

    # Derived classifications
    affected_competitors: list[str] = field(default_factory=list)
    rpm_classes: list[RPMClass] = field(default_factory=list)
    power_classes: list[PowerClass] = field(default_factory=list)
    fuel_types: list[str] = field(default_factory=list)

    # KB Scoring (deterministic, rule-based)
    technical_score: float = 0.0
    market_score: float = 0.0
    commercial_score: float = 0.0
    kb_score: float = 0.0  # Total KB score (0-175)
    classification: str = RelevanceClassification.IGNORE.value

    # Score explanation
    score_explanation: Optional[str] = None

    # Metadata
    enriched_at: datetime = field(default_factory=datetime.utcnow)
    entity_count: int = 0
    resolution_rate: float = 0.0  # % of extracted entities resolved

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "engine_entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_name": e.entity_name,
                    "entity_type": e.entity_type,
                    "match_type": e.match_type,
                    "match_confidence": e.match_confidence,
                    "rpm_class": e.rpm_class.value if e.rpm_class else None,
                    "power_class": e.power_class.value if e.power_class else None,
                }
                for e in self.engine_entities
            ],
            "manufacturer_entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_name": e.entity_name,
                    "manufacturer_tier": (
                        e.manufacturer_tier.value if e.manufacturer_tier else None
                    ),
                }
                for e in self.manufacturer_entities
            ],
            "affected_competitors": self.affected_competitors,
            "rpm_classes": [r.value for r in self.rpm_classes],
            "power_classes": [p.value for p in self.power_classes],
            "fuel_types": self.fuel_types,
            "technical_score": self.technical_score,
            "market_score": self.market_score,
            "commercial_score": self.commercial_score,
            "kb_score": self.kb_score,
            "classification": self.classification,
            "score_explanation": self.score_explanation,
            "enriched_at": self.enriched_at.isoformat(),
            "entity_count": self.entity_count,
            "resolution_rate": self.resolution_rate,
        }


@dataclass
class EnrichedDocument:
    """
    Result of KB enrichment for a competitor document.

    This is returned by enrich_document() and can be used to
    update CompetitorDocument metadata.
    """

    # KB-resolved entities
    engine_entities: list[ResolvedEntity] = field(default_factory=list)
    manufacturer_entities: list[ResolvedEntity] = field(default_factory=list)

    # Derived classifications
    affected_competitors: list[str] = field(default_factory=list)
    rpm_classes: list[str] = field(default_factory=list)
    power_classes: list[str] = field(default_factory=list)

    # For filtering
    engine_ids: list[str] = field(default_factory=list)
    manufacturer_ids: list[str] = field(default_factory=list)

    # Competitive positioning (populated when competitor engines are found)
    competitive_positioning: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    enriched_at: datetime = field(default_factory=datetime.utcnow)
    entity_count: int = 0

    def to_metadata(self) -> dict[str, Any]:
        """Convert to metadata dict for document update."""
        return {
            "kb_enrichment": {
                "engine_ids": self.engine_ids,
                "manufacturer_ids": self.manufacturer_ids,
                "affected_competitors": self.affected_competitors,
                "rpm_classes": self.rpm_classes,
                "power_classes": self.power_classes,
                "competitive_positioning": self.competitive_positioning,
                "entity_count": self.entity_count,
                "enriched_at": self.enriched_at.isoformat(),
            }
        }


# =============================================================================
# INTEGRATION SERVICE
# =============================================================================


class KBIntegrationService:
    """
    Knowledge Base Integration Service.

    Provides high-level methods for integrating KB capabilities into
    MarineIntelAgent and CompetitorIntelAgent without requiring those
    agents to directly depend on KB internals.

    Features:
    - Entity extraction from article content (via LLM)
    - Entity resolution against KB (hybrid matching)
    - Deterministic scoring (rule-based, auditable)
    - Competitor identification
    - Cross-agent coordination support

    Usage:
        service = KBIntegrationService()
        await service.initialize()

        # For MarineIntelAgent opportunities
        enriched = await service.enrich_opportunity(
            content="Article text...",
            title="Article title",
            existing_data={
                "vessel_type": "ferry",
                "region": "singapore",
            }
        )

        # For CompetitorIntelAgent documents
        doc_enriched = await service.enrich_document(
            content="Document text...",
            title="Document title",
            competitor="caterpillar"
        )
    """

    def __init__(
        self,
        db: Optional[KnowledgeBaseDatabase] = None,
        embedding_service: Optional[KBEmbeddingService] = None,
        entity_resolver: Optional[EntityResolver] = None,
        scorer: Optional[RelevanceScorer] = None,
    ):
        """
        Initialize integration service.

        Args:
            db: Database instance (defaults to singleton)
            embedding_service: Embedding service (defaults to singleton)
            entity_resolver: Entity resolver (defaults to singleton)
            scorer: Relevance scorer (defaults to singleton)
        """
        # Load from config
        kb_config = config.knowledge_base

        self._db = db
        self._embedding_service = embedding_service
        self._entity_resolver = entity_resolver
        self._scorer = scorer
        self._llm_client = None
        self._initialized = False

        # Config values
        self._model = kb_config.openai_model
        self._extraction_temperature = kb_config.extraction_temperature
        self._max_content_chars = kb_config.max_content_chars
        self._enrichment_timeout = kb_config.enrichment_timeout

        # Distributed circuit breaker (uses Redis if available, falls back to local)
        self._circuit_breaker: DistributedCircuitBreaker | CircuitBreaker = (
            DistributedCircuitBreaker(
                name="kb_integration_openai",
                redis_url=kb_config.redis_url,
                failure_threshold=kb_config.circuit_failure_threshold,
                recovery_timeout=kb_config.circuit_recovery_timeout,
                half_open_max_calls=kb_config.circuit_half_open_calls,
            )
        )

        # Real rate limiter (uses Redis if available)
        self._rate_limiter: Optional[RedisRateLimiter] = None
        if kb_config.redis_url:
            self._rate_limiter = RedisRateLimiter(
                redis_url=kb_config.redis_url,
                requests_per_window=kb_config.rate_limit_requests,
                window_seconds=kb_config.rate_limit_window_seconds,
                key_prefix="ratelimit:kb_integration:",
            )

    async def initialize(self) -> None:
        """Initialize all services and resilience components."""
        if self._initialized:
            return

        logger.info("Initializing KB Integration Service...")

        # Initialize database
        if self._db is None:
            self._db = get_knowledge_base_db()
        await self._db.initialize()

        # Initialize embedding service
        if self._embedding_service is None:
            self._embedding_service = get_kb_embedding_service()
        await self._embedding_service.initialize()

        # Initialize entity resolver
        if self._entity_resolver is None:
            self._entity_resolver = get_entity_resolver()
        await self._entity_resolver.initialize()

        # Initialize scorer
        if self._scorer is None:
            self._scorer = get_relevance_scorer()

        # Initialize LLM client for entity extraction
        import openai

        api_key = config.knowledge_base.openai_api_key
        if api_key:
            self._llm_client = openai.AsyncOpenAI(api_key=api_key)

        # Initialize distributed circuit breaker
        await self._circuit_breaker.initialize()

        # Initialize rate limiter if available
        if self._rate_limiter:
            await self._rate_limiter.initialize()

        self._initialized = True
        cb_mode = (
            "distributed"
            if getattr(self._circuit_breaker, "is_distributed", False)
            else "local"
        )
        rl_mode = (
            "Redis"
            if (self._rate_limiter and self._rate_limiter.is_available)
            else "disabled"
        )
        logger.info(
            f"KB Integration Service initialized (circuit_breaker={cb_mode}, rate_limiter={rl_mode})"
        )

    async def _ensure_initialized(self) -> None:
        """Ensure services are initialized."""
        if not self._initialized:
            await self.initialize()

    # -------------------------------------------------------------------------
    # Entity Extraction (LLM-based)
    # -------------------------------------------------------------------------

    async def extract_entities(
        self, content: str, title: str = ""
    ) -> list[ExtractedEntity]:
        """
        Extract marine engine entities from text using LLM.

        Args:
            content: Article/document text
            title: Optional title for context

        Returns:
            List of extracted entities (before KB resolution)

        Features:
            - Distributed circuit breaker protection for OpenAI API
            - Real rate limiting via Redis (if available)
            - Retry with exponential backoff for transient failures
            - Configurable model, temperature, and content limits
        """
        await self._ensure_initialized()

        if not self._llm_client:
            logger.warning("LLM client not available, skipping entity extraction")
            return []

        if not content or len(content) < 50:
            return []

        # Check circuit breaker (async for distributed)
        can_execute = await self._circuit_breaker.can_execute()
        if not can_execute:
            state = await self._circuit_breaker.get_state()
            logger.warning(f"OpenAI API circuit breaker is open (state={state})")
            return []

        # Rate limiting (if Redis available)
        if self._rate_limiter and self._rate_limiter.is_available:
            allowed = await self._rate_limiter.acquire()
            if not allowed:
                logger.warning("Rate limit exceeded for KB integration API")
                return []

        # Truncate if too long (from config)
        text = content[: self._max_content_chars]
        if title:
            text = f"Title: {title}\n\n{text}"

        async def _call_api():
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": ENTITY_EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Extract marine engine entities from this text:\n\n{text}",
                    },
                ],
                temperature=self._extraction_temperature,
                response_format={"type": "json_object"},
            )
            return response

        try:
            # Retry with exponential backoff
            response = await retry_with_backoff(
                _call_api,
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
            )
            await self._circuit_breaker.record_success()

            result = response.choices[0].message.content
            data = json.loads(result)

            # Handle both array and object formats
            entities_data = data if isinstance(data, list) else data.get("entities", [])

            entities = []
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
                # Filter low confidence using constant threshold
                if entity.confidence >= MIN_EXTRACTION_CONFIDENCE and entity.text:
                    entities.append(entity)

            logger.debug(f"Extracted {len(entities)} entities from text")
            return entities

        except Exception as e:
            await self._circuit_breaker.record_failure()
            logger.error(f"Entity extraction failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Entity Resolution
    # -------------------------------------------------------------------------

    async def resolve_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[ResolvedEntity]:
        """
        Resolve extracted entities against the Knowledge Base.

        Uses hybrid matching: exact → alias → fuzzy → semantic

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

        logger.debug(f"Resolved {len(resolved)}/{len(entities)} entities")
        return resolved

    # -------------------------------------------------------------------------
    # Opportunity Enrichment (for MarineIntelAgent)
    # -------------------------------------------------------------------------

    async def enrich_opportunity(
        self,
        content: str,
        title: str = "",
        existing_data: Optional[dict[str, Any]] = None,
    ) -> EnrichedOpportunity:
        """
        Enrich a marine opportunity with KB data.

        This is the main integration point for MarineIntelAgent.
        Call this after LLM extraction to add:
        - Resolved engine entities
        - Affected competitors
        - KB-based scoring

        Args:
            content: Article text
            title: Article title
            existing_data: Existing opportunity data (vessel_type, region, etc.)

        Returns:
            EnrichedOpportunity with KB data
        """
        await self._ensure_initialized()

        existing_data = existing_data or {}

        # Step 1: Extract entities
        extracted = await self.extract_entities(content, title)

        # Step 2: Resolve entities
        resolved = await self.resolve_entities(extracted)

        # Step 3: Categorize entities
        engine_entities = [
            e for e in resolved if e.entity_type in ("engine_model", "engine_series")
        ]
        manufacturer_entities = [e for e in resolved if e.entity_type == "manufacturer"]

        # Step 4: Derive classifications
        affected_competitors = list(
            set(e.entity_name for e in resolved if e.entity_type == "manufacturer")
        )

        rpm_classes = list(set(e.rpm_class for e in resolved if e.rpm_class))
        power_classes = list(set(e.power_class for e in resolved if e.power_class))

        # Collect fuel types from extracted entities
        fuel_types = list(
            set(e.extracted.fuel_type for e in resolved if e.extracted.fuel_type)
        )

        # Step 5: Detect market segments
        market_segments = self._scorer.detect_market_segments(content)

        # Add segments from existing data (vessel_type, region)
        vessel_type = existing_data.get("vessel_type", "")
        if vessel_type:
            if vessel_type in ("osv", "fpso", "ahts", "psv"):
                market_segments.append(MarketSegmentType.OFFSHORE_OIL_GAS)
            elif vessel_type in ("ferry", "cargo", "tanker", "cruise"):
                market_segments.append(MarketSegmentType.MARINE_TRANSPORTATION)

        market_segments = list(set(market_segments))

        # Step 6: Detect commercial signals
        commercial_signals = self._scorer.detect_commercial_signals(content)

        # Also check existing data for signals
        sales_signals = existing_data.get("sales_signals", [])
        signal_mapping = {
            "newbuild": "new_vessel_order",
            "retrofit_repower": "fleet_retrofit",
            "regulation": "regulatory_change",
        }
        for signal in sales_signals:
            if signal in signal_mapping:
                commercial_signals.append(signal_mapping[signal])
        commercial_signals = list(set(commercial_signals))

        # Step 7: Calculate KB score
        import uuid

        scoring_input = ScoringInput(
            article_id=str(uuid.uuid4()),
            article_content=content,
            entities=resolved,
            market_segments=market_segments,
            commercial_signals=commercial_signals,
        )

        score = self._scorer.score(scoring_input)

        # Step 8: Build result
        resolution_rate = len(resolved) / len(extracted) if extracted else 0

        enriched = EnrichedOpportunity(
            engine_entities=engine_entities,
            manufacturer_entities=manufacturer_entities,
            affected_competitors=affected_competitors,
            rpm_classes=rpm_classes,
            power_classes=power_classes,
            fuel_types=fuel_types,
            technical_score=score.technical_score,
            market_score=score.market_score,
            commercial_score=score.commercial_score,
            kb_score=score.total_score,
            classification=score.classification,
            score_explanation=score.score_explanation,
            entity_count=len(resolved),
            resolution_rate=resolution_rate,
        )

        logger.info(
            f"Enriched opportunity: {len(resolved)} entities, "
            f"score={score.total_score} ({score.classification})"
        )

        return enriched

    # -------------------------------------------------------------------------
    # Document Enrichment (for CompetitorIntelAgent)
    # -------------------------------------------------------------------------

    async def enrich_document(
        self,
        content: str,
        title: str = "",
        competitor: Optional[str] = None,
    ) -> EnrichedDocument:
        """
        Enrich a competitor document with KB data.

        This is the main integration point for CompetitorIntelAgent.
        Call this during refresh_data() to add:
        - Resolved engine entities
        - Entity IDs for filtering
        - Classification metadata

        Args:
            content: Document text
            title: Document title
            competitor: Known competitor name (for context)

        Returns:
            EnrichedDocument with KB data
        """
        await self._ensure_initialized()

        # Step 1: Extract entities
        extracted = await self.extract_entities(content, title)

        # Step 2: Resolve entities
        resolved = await self.resolve_entities(extracted)

        # Step 3: Categorize
        engine_entities = [
            e for e in resolved if e.entity_type in ("engine_model", "engine_series")
        ]
        manufacturer_entities = [e for e in resolved if e.entity_type == "manufacturer"]

        # Step 4: Collect IDs for filtering
        engine_ids = [e.entity_id for e in engine_entities]
        manufacturer_ids = [e.entity_id for e in manufacturer_entities]

        # Step 5: Derive classifications
        affected_competitors = list(set(e.entity_name for e in manufacturer_entities))

        # Add known competitor if not already found
        if competitor and competitor not in [c.lower() for c in affected_competitors]:
            # Try to resolve competitor name
            match = await self._entity_resolver.resolve(
                competitor, entity_type="manufacturer"
            )
            if match:
                affected_competitors.append(match.entity_name)

        rpm_classes = list(set(e.rpm_class.value for e in resolved if e.rpm_class))
        power_classes = list(
            set(e.power_class.value for e in resolved if e.power_class)
        )

        # Step 6: Look up competitive positioning for competitor engines
        competitive_positioning = self._lookup_competitive_positioning(
            engine_entities, affected_competitors
        )

        enriched = EnrichedDocument(
            engine_entities=engine_entities,
            manufacturer_entities=manufacturer_entities,
            affected_competitors=affected_competitors,
            rpm_classes=rpm_classes,
            power_classes=power_classes,
            engine_ids=engine_ids,
            manufacturer_ids=manufacturer_ids,
            competitive_positioning=competitive_positioning,
            entity_count=len(resolved),
        )

        logger.debug(
            f"Enriched document: {len(resolved)} entities, "
            f"competitors={affected_competitors}, "
            f"competitive_positions={len(competitive_positioning)}"
        )

        return enriched

    # -------------------------------------------------------------------------
    # Competitive Positioning
    # -------------------------------------------------------------------------

    def _lookup_competitive_positioning(
        self,
        engine_entities: list[ResolvedEntity],
        affected_competitors: list[str],
    ) -> list[dict[str, Any]]:
        """
        Look up competitive positioning for competitor engines found in a document.

        Uses the pre-computed COMPETITIVE_MAPPINGS data to find apple-to-apple
        comparisons between MTU engines and competitor engines mentioned in the document.

        Args:
            engine_entities: Resolved engine entities from the document
            affected_competitors: List of competitor manufacturer names

        Returns:
            List of competitive positioning dicts with our_advantages, their_advantages,
            competitive_position, recommended_positioning, threat_level
        """
        if not engine_entities and not affected_competitors:
            return []

        # Build a set of competitor engine names (lowered) for matching
        competitor_engine_names = {
            e.entity_name.lower()
            for e in engine_entities
            if e.entity_name
        }
        competitor_mfg_names = {c.lower() for c in affected_competitors}

        positions = []
        seen_pairs = set()

        for mapping in COMPETITIVE_MAPPINGS:
            competitor_name = mapping.get("competitor_rating_name", "").lower()
            # Check if this competitor engine or manufacturer is mentioned
            matched = False
            for engine_name in competitor_engine_names:
                if competitor_name and (
                    competitor_name in engine_name or engine_name in competitor_name
                ):
                    matched = True
                    break

            if not matched:
                # Check by manufacturer name in the competitor rating name
                for mfg in competitor_mfg_names:
                    if mfg in competitor_name:
                        matched = True
                        break

            if matched:
                pair_key = (
                    mapping.get("our_rating_name", ""),
                    mapping.get("competitor_rating_name", ""),
                )
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                positions.append({
                    "our_engine": mapping.get("our_rating_name"),
                    "competitor_engine": mapping.get("competitor_rating_name"),
                    "competitive_position": mapping.get("competitive_position"),
                    "threat_level": mapping.get("threat_level"),
                    "our_advantages": mapping.get("our_advantages", []),
                    "their_advantages": mapping.get("their_advantages", []),
                    "recommended_positioning": mapping.get("recommended_positioning"),
                    "overlapping_applications": mapping.get("overlapping_applications", []),
                    "price_positioning": mapping.get("price_positioning"),
                })

        return positions

    # -------------------------------------------------------------------------
    # Scoring Utilities
    # -------------------------------------------------------------------------

    def blend_scores(
        self,
        llm_priority: int,
        kb_score: float,
        llm_weight: float = 0.3,
    ) -> int:
        """
        Blend LLM-generated priority with KB score.

        Args:
            llm_priority: LLM priority (1-10)
            kb_score: KB score (0-175)
            llm_weight: Weight for LLM priority (0-1)

        Returns:
            Blended priority (1-10)
        """
        # Normalize KB score to 1-10
        kb_normalized = 1 + (kb_score / 175) * 9

        # Blend
        blended = (llm_weight * llm_priority) + ((1 - llm_weight) * kb_normalized)

        # Round and clamp
        return max(1, min(10, round(blended)))

    def get_classification_from_score(self, score: float) -> str:
        """Get classification string from score."""
        return RelevanceClassification.from_score(score).value

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check service health.

        Returns:
            Health status with service_id, status, component availability,
            and circuit breaker state.
        """
        from datetime import datetime, timezone

        if not self._initialized:
            return {
                "service_id": "kb_integration",
                "status": "unhealthy",
                "error": "Not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            db_health = await self._db.health_check()

            # Get circuit breaker state
            cb_state = await self._circuit_breaker.get_state()
            cb_is_open = cb_state == "OPEN"

            # Determine overall status
            db_ok = db_health.get("healthy", False)
            llm_ok = self._llm_client is not None

            if not db_ok:
                status = "unhealthy"
            elif cb_is_open:
                status = "degraded"  # Circuit breaker is open
            elif llm_ok:
                status = "healthy"
            else:
                status = "degraded"  # DB ok but no LLM

            return {
                "service_id": "kb_integration",
                "status": status,
                "initialized": self._initialized,
                "llm_available": llm_ok,
                "database": db_health,
                "counts": db_health.get("counts", {}),
                "circuit_breaker": {
                    "state": cb_state,
                    "is_distributed": getattr(
                        self._circuit_breaker, "is_distributed", False
                    ),
                },
                "rate_limiter": {
                    "available": (
                        self._rate_limiter.is_available if self._rate_limiter else False
                    ),
                },
                "config": {
                    "model": self._model,
                    "max_content_chars": self._max_content_chars,
                    "enrichment_timeout": self._enrichment_timeout,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return {
                "service_id": "kb_integration",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_service: Optional[KBIntegrationService] = None


def get_kb_integration_service() -> KBIntegrationService:
    """Get singleton integration service instance."""
    global _service
    if _service is None:
        _service = KBIntegrationService()
    return _service


async def initialize_kb_integration_service() -> KBIntegrationService:
    """Initialize and return integration service instance."""
    service = get_kb_integration_service()
    await service.initialize()
    return service
