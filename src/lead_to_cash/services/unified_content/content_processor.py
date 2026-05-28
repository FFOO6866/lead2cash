"""
Unified Content Processor

Multi-purpose content processing with:
- Entity extraction (single pass, not 3x)
- Mandatory KB entity resolution
- Multi-purpose classification (competitor, marine, KB)
- Embedding generation (via shared cache)

This replaces separate processing in:
- competitor_intel/competitor_intel_agent.py
- marine_intel/processing_service.py

Usage:
    from lead_to_cash.services.unified_content.content_processor import (
        ContentProcessor,
        process_content,
    )

    processor = ContentProcessor()
    await processor.initialize()
    processed_content = await processor.process(unified_content)
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from lead_to_cash.services.unified_content.database import (
    UnifiedContentDatabase,
    get_unified_content_db,
)
from lead_to_cash.services.unified_content.embedding_cache import (
    SharedEmbeddingService,
    get_shared_embedding_service,
)
from lead_to_cash.services.unified_content.models import (
    ContentClassification,
    ContentPurpose,
    EntityType,
    ExtractedEntity,
    UnifiedContent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Entity Patterns (for fast pre-filtering before LLM)
# =============================================================================

MANUFACTURER_PATTERNS = {
    "wartsila": {"normalized": "Wärtsilä", "tier": 1},
    "wärtsilä": {"normalized": "Wärtsilä", "tier": 1},
    "man energy": {"normalized": "MAN Energy Solutions", "tier": 1},
    "man es": {"normalized": "MAN Energy Solutions", "tier": 1},
    "caterpillar": {"normalized": "Caterpillar", "tier": 1},
    "cat marine": {"normalized": "Caterpillar", "tier": 1},
    "cummins": {"normalized": "Cummins", "tier": 1},
    "rolls-royce": {"normalized": "Rolls-Royce", "tier": 1},
    "mtu": {"normalized": "Rolls-Royce MTU", "tier": 1},
    "volvo penta": {"normalized": "Volvo Penta", "tier": 2},
    "yanmar": {"normalized": "Yanmar", "tier": 2},
    "abc engines": {"normalized": "ABC Engines", "tier": 2},
    "weichai": {"normalized": "Weichai", "tier": 2},
    "bergen engines": {"normalized": "Bergen Engines", "tier": 2},
    "himsen": {"normalized": "HiMSEN", "tier": 2},
}

ENGINE_MODEL_PATTERNS = [
    # Wärtsilä patterns
    r"\bW\d{2,3}[A-Z]?\b",  # W31, W46F
    r"\bWartsila\s?\d{2}\b",
    r"\bW\d{2}DF\b",  # W31DF (dual fuel)
    # MAN patterns
    r"\bMAN\s?\d{2}/\d{2}[A-Z]*\b",  # MAN 51/60
    r"\bD3876\b",
    r"\bD3872\b",
    # Caterpillar patterns
    r"\bC\d{2,3}[A-Z]?\b",  # C32, C175, C280
    r"\bCAT\s?C\d+\b",
    r"\b3500\s?series\b",
    r"\b3600\s?series\b",
    # Generic patterns
    r"\b\d{4,5}\s?kW\b",  # Power ratings
    r"\bIMO\s?Tier\s?[I]{1,3}\b",  # Emissions tier
]

VESSEL_TYPE_PATTERNS = [
    "ferry",
    "ro-ro",
    "roro",
    "cruise ship",
    "tanker",
    "bulk carrier",
    "container ship",
    "containership",
    "lng carrier",
    "lng carrier",
    "fpso",
    "fsru",
    "osv",
    "offshore supply",
    "platform supply",
    "psv",
    "ahts",
    "anchor handling",
    "tugboat",
    "tug boat",
    "dredger",
    "research vessel",
    "icebreaker",
    "submarine",
    "yacht",
    "superyacht",
    "mega yacht",
    "workboat",
    "patrol boat",
    "fast ferry",
    "catamaran",
    "trimaran",
    "monohull",
]

REGULATORY_PATTERNS = [
    "imo",
    "mepc",
    "eexi",
    "cii",
    "eca",
    "scrubber",
    "ballast water",
    "tier iii",
    "tier 3",
    "nox",
    "sox",
    "eu ets",
    "carbon intensity",
    "green corridor",
    "methanol",
    "ammonia",
    "lng bunkering",
    "shore power",
    "alternative fuel",
    "decarbonization",
    "zero emission",
]

REGION_PATTERNS = {
    "singapore": "Singapore",
    "southeast asia": "Southeast Asia",
    "malaysia": "Malaysia",
    "indonesia": "Indonesia",
    "philippines": "Philippines",
    "vietnam": "Vietnam",
    "thailand": "Thailand",
    "china": "China",
    "south korea": "South Korea",
    "japan": "Japan",
    "middle east": "Middle East",
    "europe": "Europe",
    "north america": "North America",
}

SHIPYARD_PATTERNS = [
    "keppel",
    "sembcorp",
    "seatrium",
    "hyundai heavy",
    "samsung heavy",
    "daewoo",
    "dsme",
    "china shipbuilding",
    "cssc",
    "jiangnan shipyard",
    "meyer werft",
    "fincantieri",
    "stx",
    "tsuneishi",
    "imabari",
    "mitsubishi heavy",
    "kawasaki heavy",
    "oshima shipyard",
]


@dataclass
class ProcessingResult:
    """Result of content processing."""

    content: UnifiedContent
    entities_extracted: int
    kb_entities_resolved: int
    embedding_generated: bool
    classification_score: Optional[int]
    processing_time_ms: int
    errors: list[str]


class ContentProcessor:
    """
    Unified content processor.

    Performs:
    1. Entity extraction (regex patterns + LLM)
    2. KB entity resolution (mandatory linking)
    3. Multi-purpose classification
    4. Embedding generation (via shared cache)
    """

    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        embedding_service: Optional[SharedEmbeddingService] = None,
        database: Optional[UnifiedContentDatabase] = None,
        use_llm_extraction: bool = True,
    ):
        """
        Initialize content processor.

        Args:
            openai_api_key: OpenAI API key (defaults to env var)
            embedding_service: Shared embedding service (uses singleton if not provided)
            database: Unified content database (uses singleton if not provided)
            use_llm_extraction: Whether to use LLM for entity extraction
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.embedding_service = embedding_service or get_shared_embedding_service()
        self.database = database
        self.use_llm_extraction = use_llm_extraction

        self._http_client: Optional[httpx.AsyncClient] = None
        self._kb_entity_cache: dict[str, dict[str, Any]] = {}  # Populated from KB

    async def initialize(self) -> None:
        """Initialize processor with database connection and KB cache."""
        if self.database is None:
            self.database = get_unified_content_db()
        await self.database.initialize()
        await self._load_kb_entities()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=60,
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close resources."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
        await self.embedding_service.close()
        await self.database.close()

    async def _load_kb_entities(self) -> None:
        """
        Load KB entities for fast resolution.

        Queries actual KB tables:
        - kb_manufacturers: Engine manufacturers
        - kb_engine_models: Specific engine models
        - kb_entity_aliases: Unified alias table for fuzzy matching

        Falls back to pattern-based resolution if KB tables don't exist.
        """
        logger.info("Loading KB entities for resolution...")

        # Pre-populate from MANUFACTURER_PATTERNS as fallback
        for pattern, info in MANUFACTURER_PATTERNS.items():
            self._kb_entity_cache[pattern.lower()] = {
                "entity_type": EntityType.MANUFACTURER.value,
                "normalized": info["normalized"],
                "tier": info["tier"],
                "kb_entity_id": None,  # Will be filled from DB
            }

        # Try to load from actual KB tables
        if self.database and self.database._pool:
            try:
                await self._load_kb_manufacturers()
                await self._load_kb_engine_models()
                await self._load_kb_aliases()
            except Exception as e:
                logger.warning(f"Could not load KB tables (may not exist yet): {e}")
                logger.info("Falling back to pattern-based KB resolution")

        logger.info(f"Loaded {len(self._kb_entity_cache)} KB entity patterns")

    async def _load_kb_manufacturers(self) -> None:
        """Load manufacturers from kb_manufacturers table."""
        try:
            async with self.database.pool.acquire() as conn:
                # Check if table exists
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'kb_manufacturers'
                    )
                    """
                )
                if not exists:
                    logger.debug("kb_manufacturers table does not exist")
                    return

                rows = await conn.fetch(
                    """
                    SELECT id, name, short_name, tier
                    FROM kb_manufacturers
                    WHERE is_active = TRUE
                    """
                )

                for row in rows:
                    # Index by name (lowercase)
                    name_key = row["name"].lower()
                    self._kb_entity_cache[name_key] = {
                        "entity_type": EntityType.MANUFACTURER.value,
                        "normalized": row["name"],
                        "tier": row["tier"],
                        "kb_entity_id": row["id"],
                        "kb_table": "kb_manufacturers",
                    }

                    # Also index by short_name if different
                    if row["short_name"] and row["short_name"].lower() != name_key:
                        self._kb_entity_cache[row["short_name"].lower()] = {
                            "entity_type": EntityType.MANUFACTURER.value,
                            "normalized": row["name"],
                            "tier": row["tier"],
                            "kb_entity_id": row["id"],
                            "kb_table": "kb_manufacturers",
                        }

                logger.info(f"Loaded {len(rows)} manufacturers from KB")

        except Exception as e:
            logger.debug(f"Error loading kb_manufacturers: {e}")

    async def _load_kb_engine_models(self) -> None:
        """Load engine models from kb_engine_models table."""
        try:
            async with self.database.pool.acquire() as conn:
                # Check if table exists
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'kb_engine_models'
                    )
                    """
                )
                if not exists:
                    logger.debug("kb_engine_models table does not exist")
                    return

                rows = await conn.fetch(
                    """
                    SELECT em.id, em.model_name, em.series_id, m.name as manufacturer_name
                    FROM kb_engine_models em
                    LEFT JOIN kb_engine_series es ON em.series_id = es.id
                    LEFT JOIN kb_manufacturers m ON es.manufacturer_id = m.id
                    WHERE em.is_active = TRUE
                    """
                )

                for row in rows:
                    model_key = row["model_name"].lower()
                    self._kb_entity_cache[model_key] = {
                        "entity_type": EntityType.ENGINE_MODEL.value,
                        "normalized": row["model_name"],
                        "manufacturer": row.get("manufacturer_name"),
                        "kb_entity_id": row["id"],
                        "kb_table": "kb_engine_models",
                    }

                logger.info(f"Loaded {len(rows)} engine models from KB")

        except Exception as e:
            logger.debug(f"Error loading kb_engine_models: {e}")

    async def _load_kb_aliases(self) -> None:
        """Load entity aliases from kb_entity_aliases table."""
        try:
            async with self.database.pool.acquire() as conn:
                # Check if table exists
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'kb_entity_aliases'
                    )
                    """
                )
                if not exists:
                    logger.debug("kb_entity_aliases table does not exist")
                    return

                rows = await conn.fetch(
                    """
                    SELECT alias_text, entity_type, entity_id, canonical_name
                    FROM kb_entity_aliases
                    WHERE is_active = TRUE
                    """
                )

                for row in rows:
                    alias_key = row["alias_text"].lower()
                    # Only add if not already in cache (prefer primary names)
                    if alias_key not in self._kb_entity_cache:
                        self._kb_entity_cache[alias_key] = {
                            "entity_type": row["entity_type"],
                            "normalized": row["canonical_name"],
                            "kb_entity_id": row["entity_id"],
                            "kb_table": "kb_entity_aliases",
                            "is_alias": True,
                        }

                logger.info(f"Loaded {len(rows)} entity aliases from KB")

        except Exception as e:
            logger.debug(f"Error loading kb_entity_aliases: {e}")

    # =========================================================================
    # Entity Extraction
    # =========================================================================

    def _extract_entities_regex(self, text: str) -> list[ExtractedEntity]:
        """
        Extract entities using regex patterns.

        Fast first-pass extraction before LLM refinement.
        """
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        # Manufacturers
        for pattern, info in MANUFACTURER_PATTERNS.items():
            if pattern in text_lower:
                # Find actual position for context
                idx = text_lower.find(pattern)
                context = text[
                    max(0, idx - 50) : min(len(text), idx + len(pattern) + 50)
                ]
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.MANUFACTURER.value,
                        raw_text=pattern,
                        normalized_text=info["normalized"],
                        confidence=0.9,  # High confidence for exact matches
                        context=context,
                        metadata={"tier": info["tier"]},
                    )
                )

        # Engine models
        for pattern in ENGINE_MODEL_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                idx = match.start()
                context = text[
                    max(0, idx - 50) : min(len(text), idx + len(match.group()) + 50)
                ]
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.ENGINE_MODEL.value,
                        raw_text=match.group(),
                        normalized_text=match.group().upper(),
                        confidence=0.7,
                        context=context,
                    )
                )

        # Vessel types
        for vt in VESSEL_TYPE_PATTERNS:
            if vt in text_lower:
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.VESSEL_TYPE.value,
                        raw_text=vt,
                        normalized_text=vt.title(),
                        confidence=0.85,
                    )
                )

        # Regions
        for pattern, normalized in REGION_PATTERNS.items():
            if pattern in text_lower:
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.REGION.value,
                        raw_text=pattern,
                        normalized_text=normalized,
                        confidence=0.9,
                    )
                )

        # Shipyards
        for shipyard in SHIPYARD_PATTERNS:
            if shipyard in text_lower:
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.SHIPYARD.value,
                        raw_text=shipyard,
                        normalized_text=shipyard.title(),
                        confidence=0.85,
                    )
                )

        # Regulatory mentions
        for reg in REGULATORY_PATTERNS:
            if reg in text_lower:
                entities.append(
                    ExtractedEntity(
                        entity_type=EntityType.REGULATORY_BODY.value,
                        raw_text=reg,
                        normalized_text=reg.upper() if len(reg) <= 5 else reg.title(),
                        confidence=0.8,
                    )
                )

        return entities

    async def _extract_entities_llm(
        self,
        title: str,
        content: str,
        regex_entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """
        Refine entity extraction using LLM.

        Uses regex results as hints, extracts additional entities.
        """
        if not self.openai_api_key or not self.use_llm_extraction:
            return regex_entities

        # Build context from regex hits
        regex_context = ", ".join(
            f"{e.entity_type}: {e.normalized_text}"
            for e in regex_entities[:10]  # Limit context
        )

        prompt = f"""Extract maritime entities from this article. Focus on:
1. Engine manufacturers (Wärtsilä, MAN, Caterpillar, Cummins, etc.)
2. Specific engine models (W31, C32, D3872, etc.) with power ratings if mentioned
3. Vessel names and types (ferry, tanker, OSV, etc.)
4. Shipyards and operators
5. Contract values if mentioned

Already identified: {regex_context or "None"}

Title: {title}
Content: {content[:3000]}

Return JSON array:
[{{"entity_type": "manufacturer|engine_model|vessel|vessel_type|shipyard|operator|contract_value", "text": "...", "normalized": "...", "confidence": 0.0-1.0}}]"""

        try:
            client = await self._get_http_client()
            response = await client.post(
                self.OPENAI_API_URL,
                json={
                    "model": os.getenv("OPENAI_MINI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a maritime industry entity extractor. Return only valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 1000,
                },
            )

            if response.status_code != 200:
                logger.warning(f"LLM extraction failed: {response.status_code}")
                return regex_entities

            data = response.json()
            llm_output = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            json_match = re.search(r"\[.*\]", llm_output, re.DOTALL)
            if json_match:
                llm_entities_data = json.loads(json_match.group())
                llm_entities = [
                    ExtractedEntity(
                        entity_type=e.get("entity_type", "unknown"),
                        raw_text=e.get("text", ""),
                        normalized_text=e.get("normalized", e.get("text", "")),
                        confidence=float(e.get("confidence", 0.7)),
                    )
                    for e in llm_entities_data
                    if e.get("text")
                ]

                # Merge with regex entities (dedupe by normalized_text)
                seen = {e.normalized_text.lower() for e in regex_entities}
                for e in llm_entities:
                    if e.normalized_text.lower() not in seen:
                        regex_entities.append(e)
                        seen.add(e.normalized_text.lower())

        except Exception as e:
            logger.warning(f"LLM entity extraction error: {e}")

        return regex_entities

    async def extract_entities(
        self,
        content: UnifiedContent,
    ) -> list[ExtractedEntity]:
        """
        Extract entities from content.

        Two-phase extraction:
        1. Fast regex patterns
        2. LLM refinement (optional)
        """
        text = f"{content.title}\n{content.summary or ''}\n{content.content or ''}"

        # Phase 1: Regex extraction
        entities = self._extract_entities_regex(text)
        logger.debug(f"Regex extracted {len(entities)} entities")

        # Phase 2: LLM refinement
        if self.use_llm_extraction and content.content:
            entities = await self._extract_entities_llm(
                content.title,
                content.content,
                entities,
            )
            logger.debug(f"After LLM: {len(entities)} entities")

        return entities

    # =========================================================================
    # KB Entity Resolution
    # =========================================================================

    async def resolve_kb_entities(
        self,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """
        Resolve extracted entities against Knowledge Base.

        This is MANDATORY - all entities should be linked to KB when possible.

        Resolution strategy:
        1. Check in-memory cache (loaded from KB tables at init)
        2. Try fuzzy matching via database query if cache miss
        3. Mark as unresolved if no match found (for later review)

        Returns updated entities with kb_entity_id and kb_entity_type filled.
        """
        resolved_count = 0
        unresolved_entities: list[ExtractedEntity] = []

        for entity in entities:
            # Check cache for quick resolution
            cache_key = entity.normalized_text.lower()
            if cache_key in self._kb_entity_cache:
                kb_info = self._kb_entity_cache[cache_key]
                # Use actual KB entity ID if available, otherwise generate tracking ID
                if kb_info.get("kb_entity_id"):
                    entity.kb_entity_id = str(kb_info["kb_entity_id"])
                    entity.kb_entity_type = kb_info.get(
                        "kb_table", f"kb_{kb_info['entity_type']}s"
                    )
                else:
                    # Pattern-based fallback - mark as candidate for KB addition
                    entity.kb_entity_id = f"candidate:{kb_info['entity_type']}:{cache_key.replace(' ', '_')}"
                    entity.kb_entity_type = f"kb_{kb_info['entity_type']}s"
                entity.confidence = min(
                    entity.confidence + 0.1, 1.0
                )  # Boost confidence
                resolved_count += 1
                continue

            # Try alternative cache lookups (raw text, etc.)
            raw_key = entity.raw_text.lower()
            if raw_key != cache_key and raw_key in self._kb_entity_cache:
                kb_info = self._kb_entity_cache[raw_key]
                if kb_info.get("kb_entity_id"):
                    entity.kb_entity_id = str(kb_info["kb_entity_id"])
                    entity.kb_entity_type = kb_info.get(
                        "kb_table", f"kb_{kb_info['entity_type']}s"
                    )
                else:
                    entity.kb_entity_id = f"candidate:{kb_info['entity_type']}:{raw_key.replace(' ', '_')}"
                    entity.kb_entity_type = f"kb_{kb_info['entity_type']}s"
                entity.confidence = min(entity.confidence + 0.1, 1.0)
                resolved_count += 1
                continue

            # Cache miss - try database fuzzy search for high-confidence entities
            if entity.confidence >= 0.7:
                resolved = await self._resolve_entity_from_db(entity)
                if resolved:
                    resolved_count += 1
                    continue

            # Not resolved - mark for potential future KB addition
            unresolved_entities.append(entity)
            entity.kb_entity_id = f"unresolved:{entity.entity_type}:{entity.normalized_text.lower().replace(' ', '_')}"
            entity.kb_entity_type = None

        # Log unresolved entities for KB improvement
        if unresolved_entities:
            unresolved_summary = [
                f"{e.entity_type}:{e.normalized_text}" for e in unresolved_entities[:5]
            ]
            logger.debug(
                f"Unresolved entities (candidates for KB): {unresolved_summary}"
            )

        logger.info(f"Resolved {resolved_count}/{len(entities)} entities against KB")
        return entities

    async def _resolve_entity_from_db(self, entity: ExtractedEntity) -> bool:
        """
        Try to resolve entity using database fuzzy search.

        Returns True if resolved, False otherwise.
        """
        if not self.database or not self.database._pool:
            return False

        search_text = entity.normalized_text.lower()

        try:
            async with self.database.pool.acquire() as conn:
                # Try manufacturers
                if entity.entity_type == EntityType.MANUFACTURER.value:
                    row = await conn.fetchrow(
                        """
                        SELECT id, name
                        FROM kb_manufacturers
                        WHERE LOWER(name) LIKE $1
                           OR LOWER(short_name) LIKE $1
                        LIMIT 1
                        """,
                        f"%{search_text}%",
                    )
                    if row:
                        entity.kb_entity_id = str(row["id"])
                        entity.kb_entity_type = "kb_manufacturers"
                        # Cache for future use
                        self._kb_entity_cache[search_text] = {
                            "entity_type": EntityType.MANUFACTURER.value,
                            "normalized": row["name"],
                            "kb_entity_id": row["id"],
                            "kb_table": "kb_manufacturers",
                        }
                        return True

                # Try engine models
                elif entity.entity_type == EntityType.ENGINE_MODEL.value:
                    row = await conn.fetchrow(
                        """
                        SELECT id, model_name
                        FROM kb_engine_models
                        WHERE LOWER(model_name) LIKE $1
                        LIMIT 1
                        """,
                        f"%{search_text}%",
                    )
                    if row:
                        entity.kb_entity_id = str(row["id"])
                        entity.kb_entity_type = "kb_engine_models"
                        # Cache for future use
                        self._kb_entity_cache[search_text] = {
                            "entity_type": EntityType.ENGINE_MODEL.value,
                            "normalized": row["model_name"],
                            "kb_entity_id": row["id"],
                            "kb_table": "kb_engine_models",
                        }
                        return True

                # Try aliases for any entity type
                row = await conn.fetchrow(
                    """
                    SELECT entity_id, entity_type, canonical_name
                    FROM kb_entity_aliases
                    WHERE LOWER(alias_text) = $1
                    LIMIT 1
                    """,
                    search_text,
                )
                if row:
                    entity.kb_entity_id = str(row["entity_id"])
                    entity.kb_entity_type = row["entity_type"]
                    # Cache for future use
                    self._kb_entity_cache[search_text] = {
                        "entity_type": entity.entity_type,
                        "normalized": row["canonical_name"],
                        "kb_entity_id": row["entity_id"],
                        "kb_table": "kb_entity_aliases",
                        "is_alias": True,
                    }
                    return True

        except Exception as e:
            logger.debug(f"Error in DB entity resolution: {e}")

        return False

    # =========================================================================
    # Classification
    # =========================================================================

    async def classify_content(
        self,
        content: UnifiedContent,
        entities: list[ExtractedEntity],
    ) -> ContentClassification:
        """
        Generate multi-purpose classification for content.

        Scores content for:
        - Competitor intelligence (threat level)
        - Marine intelligence (sales opportunities)
        - KB relevance (technical/market/commercial)
        """
        classification = ContentClassification()
        text = (
            f"{content.title} {content.summary or ''} {content.content or ''}".lower()
        )

        # === Competitor Intel Scoring ===
        competitor_manufacturers = [
            e for e in entities if e.entity_type == EntityType.MANUFACTURER.value
        ]
        if competitor_manufacturers:
            classification.competitor_name = competitor_manufacturers[0].normalized_text

            # Threat signals
            threat_keywords = {
                "contract win": 30,
                "order": 20,
                "selected": 25,
                "won": 25,
                "partnership": 20,
                "new product": 25,
                "launch": 20,
                "expansion": 15,
                "market share": 20,
            }
            threat_score = 0
            for keyword, score in threat_keywords.items():
                if keyword in text:
                    threat_score += score
                    classification.competitor_signal_type = keyword.replace(" ", "_")

            classification.competitor_threat_score = min(threat_score, 100)

        # === Marine Intel Scoring (Sales Opportunities) ===
        opportunity_signals = []
        opportunity_keywords = {
            "newbuild": 30,
            "new build": 30,
            "retrofit": 25,
            "order": 20,
            "contract": 20,
            "tender": 25,
            "rfp": 30,
            "request for proposal": 30,
            "engine replacement": 35,
            "repower": 35,
        }
        opp_score = 0
        for keyword, score in opportunity_keywords.items():
            if keyword in text:
                opp_score += score
                opportunity_signals.append(keyword)

        # Boost for our target vessel types
        vessel_types = [
            e for e in entities if e.entity_type == EntityType.VESSEL_TYPE.value
        ]
        if vessel_types:
            classification.vessel_types = [v.normalized_text for v in vessel_types[:5]]
            opp_score += 10 * len(vessel_types)

        # Region boost
        regions = [e for e in entities if e.entity_type == EntityType.REGION.value]
        if regions:
            classification.region = regions[0].normalized_text
            if "singapore" in text or "southeast asia" in text:
                opp_score += 20  # Home market boost

        classification.sales_opportunity_score = min(opp_score, 100)
        classification.sales_signals = opportunity_signals[:5]

        # === KB Relevance Scoring ===
        # Technical (0-40): Engine specs, performance, emissions
        tech_score = 0
        tech_keywords = [
            "engine",
            "kw",
            "mw",
            "power",
            "rpm",
            "fuel consumption",
            "nox",
            "tier iii",
        ]
        for kw in tech_keywords:
            if kw in text:
                tech_score += 5
        tech_score += 5 * len(
            [e for e in entities if e.entity_type == EntityType.ENGINE_MODEL.value]
        )
        classification.technical_score = min(tech_score, 40)

        # Market (0-30): Market trends, competitive landscape
        market_score = 0
        market_keywords = ["market", "trend", "growth", "demand", "segment", "share"]
        for kw in market_keywords:
            if kw in text:
                market_score += 5
        classification.market_score = min(market_score, 30)

        # Commercial (0-30): Pricing, contracts, deals
        commercial_score = 0
        commercial_keywords = [
            "million",
            "billion",
            "price",
            "cost",
            "deal",
            "contract value",
        ]
        for kw in commercial_keywords:
            if kw in text:
                commercial_score += 5
        classification.commercial_score = min(commercial_score, 30)

        classification.kb_relevance_total = (
            classification.technical_score
            + classification.market_score
            + classification.commercial_score
        )

        # === Priority Calculation ===
        priority = 5  # Default
        if (
            classification.competitor_threat_score
            and classification.competitor_threat_score >= 50
        ):
            priority = max(priority, 8)
        if (
            classification.sales_opportunity_score
            and classification.sales_opportunity_score >= 50
        ):
            priority = max(priority, 9)
        if (
            classification.kb_relevance_total
            and classification.kb_relevance_total >= 70
        ):
            priority = max(priority, 7)

        classification.priority = priority
        classification.requires_review = priority >= 8

        return classification

    # =========================================================================
    # Main Processing
    # =========================================================================

    async def process(self, content: UnifiedContent) -> ProcessingResult:
        """
        Process unified content through full pipeline.

        Steps:
        1. Extract entities (regex + LLM)
        2. Resolve entities against KB (mandatory)
        3. Generate embedding (via shared cache)
        4. Classify content (multi-purpose)
        5. Save to database with KB links

        Args:
            content: UnifiedContent to process

        Returns:
            ProcessingResult with stats
        """
        start_time = datetime.now(timezone.utc)
        errors: list[str] = []
        entities_extracted = 0
        kb_resolved = 0
        embedding_generated = False

        try:
            # Step 1: Extract entities
            entities = await self.extract_entities(content)
            entities_extracted = len(entities)

            # Step 2: Resolve against KB (mandatory)
            entities = await self.resolve_kb_entities(entities)
            kb_resolved = len([e for e in entities if e.kb_entity_id])
            content.entities = entities
            content.entities_extracted_at = datetime.now(timezone.utc)

            # Step 3: Generate embedding
            try:
                embedding = await self.embedding_service.embed_content(
                    content.id,
                    content.title,
                    content.content,
                    content.summary,
                )
                content.embedding = embedding
                embedding_generated = True
            except Exception as e:
                errors.append(f"Embedding error: {e}")
                logger.warning(f"Failed to generate embedding: {e}")

            # Step 4: Classify content
            classification = await self.classify_content(content, entities)
            content.classification = classification

            # Step 5: Determine purposes based on classification
            purposes = [ContentPurpose.GENERAL.value]
            if (
                classification.competitor_threat_score
                and classification.competitor_threat_score > 20
            ):
                purposes.append(ContentPurpose.COMPETITOR_INTEL.value)
            if (
                classification.sales_opportunity_score
                and classification.sales_opportunity_score > 20
            ):
                purposes.append(ContentPurpose.MARINE_INTEL.value)
            if (
                classification.kb_relevance_total
                and classification.kb_relevance_total > 30
            ):
                purposes.append(ContentPurpose.PRODUCT_INTEL.value)
            content.purposes = purposes

            # Step 6: Mark as processed
            content.mark_processed()

            # Step 7: Save to database
            if self.database:
                content_id, is_new = await self.database.save_content(content)
                if is_new:
                    # Save entities
                    await self.database.save_entities(content_id, entities)

                    # Update KB linked flag if we have resolutions
                    if kb_resolved > 0:
                        await self.database.mark_kb_linked(content_id)

            logger.info(
                f"Processed content: {content.title[:50]}... "
                f"({entities_extracted} entities, {kb_resolved} KB links, "
                f"priority={classification.priority})"
            )

        except Exception as e:
            errors.append(f"Processing error: {e}")
            content.processing_errors.append(str(e))
            logger.error(f"Content processing error: {e}")

        elapsed_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        return ProcessingResult(
            content=content,
            entities_extracted=entities_extracted,
            kb_entities_resolved=kb_resolved,
            embedding_generated=embedding_generated,
            classification_score=(
                content.classification.priority if content.classification else None
            ),
            processing_time_ms=elapsed_ms,
            errors=errors,
        )

    async def process_batch(
        self,
        contents: list[UnifiedContent],
    ) -> list[ProcessingResult]:
        """
        Process multiple content items.

        Args:
            contents: List of UnifiedContent to process

        Returns:
            List of ProcessingResult
        """
        results = []
        for content in contents:
            result = await self.process(content)
            results.append(result)
        return results


# =============================================================================
# Convenience Functions
# =============================================================================

_processor: Optional[ContentProcessor] = None


async def get_processor() -> ContentProcessor:
    """Get or create the content processor singleton."""
    global _processor
    if _processor is None:
        _processor = ContentProcessor()
        await _processor.initialize()
    return _processor


async def process_content(content: UnifiedContent) -> ProcessingResult:
    """Process a single content item."""
    processor = await get_processor()
    return await processor.process(content)


async def process_content_batch(
    contents: list[UnifiedContent],
) -> list[ProcessingResult]:
    """Process multiple content items."""
    processor = await get_processor()
    return await processor.process_batch(contents)
