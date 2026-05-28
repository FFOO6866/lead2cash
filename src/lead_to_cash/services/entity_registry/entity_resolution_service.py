"""
Entity Resolution Service

Multi-strategy entity resolution for KYP company matching.
Replaces hardcoded lookup tables with dynamic database + external source lookup.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lead_to_cash.services.entity_registry.clients.acra_client import ACRAClient
    from lead_to_cash.services.entity_registry.clients.gleif_client import GLEIFClient
    from lead_to_cash.services.entity_registry.clients.opencorporates_client import (
        OpenCorporatesClient,
    )

# Shared configuration (single source of truth)
from lead_to_cash.services.entity_registry.config import (
    AUTO_CONFIRM_THRESHOLD_RATIO,
    FUZZY_SEARCH_THRESHOLD,
    MARGIN_THRESHOLD_RATIO,
    MAX_CANDIDATES,
)
from lead_to_cash.services.entity_registry.database import (
    EntityRegistryDatabase,
    get_entity_registry_db,
)
from lead_to_cash.services.entity_registry.models import (
    Entity,
    EntityCandidate,
    ResolutionResult,
    ResolutionStatus,
)

logger = logging.getLogger(__name__)


class EntityResolutionService:
    """
    Entity Resolution Service for KYP company matching.

    Resolution Strategy (in order):
    1. Exact match on identifiers (UEN, LEI)
    2. Exact match on normalized canonical name
    3. Exact match on alias
    4. Fuzzy match using pg_trgm (>= 40% similarity) on canonical name
    5. Fuzzy match using pg_trgm on aliases
    6. Levenshtein distance match for typo correction (e.g., "Maerks" -> "Maersk")
    7. External source search (ACRA, OpenCorporates, GLEIF)

    Usage:
        service = EntityResolutionService()
        await service.initialize()

        result = await service.resolve("ST Engineering")

        if result.status == ResolutionStatus.EXACT_MATCH:
            entity = result.exact_match
        elif result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
            for c in result.candidates:
                print(f"{c.rank}. {c.canonical_name}")
    """

    # Thresholds from shared config (single source of truth)
    FUZZY_THRESHOLD = FUZZY_SEARCH_THRESHOLD
    AUTO_CONFIRM_THRESHOLD = AUTO_CONFIRM_THRESHOLD_RATIO  # 0.80
    MARGIN_THRESHOLD = MARGIN_THRESHOLD_RATIO  # 0.15
    MAX_CANDIDATES = MAX_CANDIDATES

    def __init__(
        self,
        db: Optional[EntityRegistryDatabase] = None,
        acra_client: Optional["ACRAClient"] = None,
        gleif_client: Optional["GLEIFClient"] = None,
        opencorporates_client: Optional["OpenCorporatesClient"] = None,
    ):
        self._db = db
        self._acra_client = acra_client
        self._gleif_client = gleif_client
        self._opencorporates_client = opencorporates_client
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database and external clients."""
        if self._initialized:
            return

        # Initialize database
        if self._db is None:
            self._db = get_entity_registry_db()
        await self._db.initialize()

        # Initialize external clients (lazy - will init on first use)
        self._initialized = True
        logger.info("EntityResolutionService initialized")

    async def _ensure_initialized(self) -> None:
        """Ensure service is initialized."""
        if not self._initialized:
            await self.initialize()

    async def search_registry(self, query: str) -> list[EntityCandidate]:
        """
        Search the internal entity registry database.

        This method is used by EntityResolutionAgent to search the local database
        without the full resolve() logic (no auto-confirm, no external sources).

        Strategies (in order):
        1. Exact match on canonical name
        2. Alias match
        3. Fuzzy match (pg_trgm)
        4. Levenshtein distance match

        Args:
            query: Company name to search

        Returns:
            List of EntityCandidate sorted by confidence (highest first)
        """
        await self._ensure_initialized()
        assert self._db is not None, "Database not initialized"

        query = query.strip()
        if not query:
            return []

        candidates: list[EntityCandidate] = []

        # Strategy 1: Exact match on canonical name
        exact_matches = await self._db.search_entities_exact(query)
        for entity in exact_matches:
            candidate = self._entity_to_candidate(entity, "exact", 98.0)
            candidate.match_reasons = ["Exact canonical name match"]
            candidates.append(candidate)

        # Strategy 2: Alias match
        if not candidates:
            alias_matches = await self._db.search_by_alias(query)
            for entity in alias_matches:
                confidence = float(entity.get("alias_confidence", 0.9)) * 100
                candidate = self._entity_to_candidate(entity, "alias", confidence)
                candidate.match_reasons = [
                    f"Alias match: {entity.get('alias_text', query)}"
                ]
                candidates.append(candidate)

        # Strategy 3: Fuzzy match on canonical name
        if not candidates:
            fuzzy_matches = await self._db.search_entities_fuzzy(
                query, threshold=self.FUZZY_THRESHOLD
            )
            for entity in fuzzy_matches:
                sim_score = float(entity.get("sim_score", 0.5)) * 100
                candidate = self._entity_to_candidate(entity, "fuzzy", sim_score)
                candidate.match_reasons = [f"Fuzzy match ({sim_score:.0f}% similar)"]
                candidates.append(candidate)

        # Strategy 4: Levenshtein distance match
        if not candidates:
            max_distance = self._calculate_max_edit_distance(query)

            levenshtein_matches = await self._db.search_entities_levenshtein(
                query, max_distance=max_distance
            )
            for entity in levenshtein_matches:
                edit_dist = entity.get("edit_distance", 99)
                confidence = max(60.0, 95.0 - (edit_dist * 15))
                candidate = self._entity_to_candidate(entity, "levenshtein", confidence)
                candidate.match_reasons = [
                    f"Similar spelling to '{entity['canonical_name']}' (edit distance: {edit_dist})"
                ]
                candidates.append(candidate)

            # Also check aliases with Levenshtein
            if not candidates:
                alias_levenshtein = await self._db.search_by_alias_levenshtein(
                    query, max_distance=max_distance
                )
                for entity in alias_levenshtein:
                    edit_dist = entity.get("edit_distance", 99)
                    confidence = max(60.0, 95.0 - (edit_dist * 15))
                    candidate = self._entity_to_candidate(
                        entity, "levenshtein_alias", confidence
                    )
                    candidate.match_reasons = [
                        f"Similar spelling to alias '{entity.get('alias_text', '')}' (edit distance: {edit_dist})"
                    ]
                    candidates.append(candidate)

        # Deduplicate and rank
        candidates = self._deduplicate_candidates(candidates)
        for i, c in enumerate(candidates[: self.MAX_CANDIDATES], start=1):
            c.rank = i

        return candidates[: self.MAX_CANDIDATES]

    async def resolve(
        self,
        query: str,
        country_hint: Optional[str] = None,
        search_external: bool = True,
        session_id: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Resolve a company name to an entity.

        Args:
            query: Company name to resolve
            country_hint: Optional ISO country code hint (e.g., "SG")
            search_external: Whether to search external sources if no match
            session_id: Optional session ID for history tracking

        Returns:
            ResolutionResult with match status and candidates
        """
        await self._ensure_initialized()
        assert self._db is not None, "Database not initialized"
        start_time = time.time()

        query = query.strip()
        if not query:
            return ResolutionResult(
                status=ResolutionStatus.NO_MATCH,
                query=query,
            )

        candidates: list[EntityCandidate] = []

        # Strategy 1: Check if query looks like an identifier
        if self._looks_like_uen(query):
            entity = await self._db.get_entity_by_uen(query)
            if entity:
                candidate = self._entity_to_candidate(entity, "identifier", 100.0)
                candidate.match_reasons = ["Exact UEN match"]
                return self._create_exact_match_result(query, candidate, start_time)

        if self._looks_like_lei(query):
            entity = await self._db.get_entity_by_lei(query)
            if entity:
                candidate = self._entity_to_candidate(entity, "identifier", 100.0)
                candidate.match_reasons = ["Exact LEI match"]
                return self._create_exact_match_result(query, candidate, start_time)

        # Strategy 2: Exact match on canonical name
        exact_matches = await self._db.search_entities_exact(query)
        if exact_matches:
            for entity in exact_matches:
                candidate = self._entity_to_candidate(entity, "exact", 98.0)
                candidate.match_reasons = ["Exact canonical name match"]
                candidates.append(candidate)

        # Strategy 3: Exact match on alias
        if not candidates:
            alias_matches = await self._db.search_by_alias(query)
            for entity in alias_matches:
                confidence = float(entity.get("alias_confidence", 0.9)) * 100
                candidate = self._entity_to_candidate(entity, "alias", confidence)
                candidate.match_reasons = [
                    f"Alias match: {entity.get('alias_text', query)}"
                ]
                candidates.append(candidate)

        # Strategy 4: Fuzzy match on canonical name
        if not candidates:
            fuzzy_matches = await self._db.search_entities_fuzzy(
                query, threshold=self.FUZZY_THRESHOLD
            )
            for entity in fuzzy_matches:
                sim_score = float(entity.get("sim_score", 0.5)) * 100
                candidate = self._entity_to_candidate(entity, "fuzzy", sim_score)
                candidate.match_reasons = [f"Fuzzy match ({sim_score:.0f}% similar)"]
                candidates.append(candidate)

        # Strategy 5: Fuzzy match on aliases
        if not candidates:
            alias_fuzzy = await self._db.search_by_alias_fuzzy(
                query, threshold=self.FUZZY_THRESHOLD
            )
            for entity in alias_fuzzy:
                sim_score = float(entity.get("sim_score", 0.5)) * 100
                candidate = self._entity_to_candidate(entity, "fuzzy_alias", sim_score)
                candidate.match_reasons = [
                    f"Similar to alias: {entity.get('alias_text', '')} ({sim_score:.0f}%)"
                ]
                candidates.append(candidate)

        # Strategy 6: Levenshtein distance match (catches typos like "Maerks" -> "Maersk")
        if not candidates:
            # Calculate max edit distance based on query length
            max_distance = self._calculate_max_edit_distance(query)

            levenshtein_matches = await self._db.search_entities_levenshtein(
                query, max_distance=max_distance
            )
            for entity in levenshtein_matches:
                edit_dist = entity.get("edit_distance", 99)
                # Convert edit distance to confidence score (lower distance = higher confidence)
                # Edit distance 1 = 90%, 2 = 75%, 3 = 60%
                confidence = max(60.0, 95.0 - (edit_dist * 15))
                candidate = self._entity_to_candidate(entity, "levenshtein", confidence)
                candidate.match_reasons = [
                    f"Similar spelling to '{entity['canonical_name']}' (edit distance: {edit_dist})"
                ]
                candidates.append(candidate)

            # Also check aliases with Levenshtein
            if not candidates:
                alias_levenshtein = await self._db.search_by_alias_levenshtein(
                    query, max_distance=max_distance
                )
                for entity in alias_levenshtein:
                    edit_dist = entity.get("edit_distance", 99)
                    confidence = max(60.0, 95.0 - (edit_dist * 15))
                    candidate = self._entity_to_candidate(
                        entity, "levenshtein_alias", confidence
                    )
                    candidate.match_reasons = [
                        f"Similar spelling to alias '{entity.get('alias_text', '')}' (edit distance: {edit_dist})"
                    ]
                    candidates.append(candidate)

        # Strategy 7: External source search
        external_results: list[EntityCandidate] = []
        if not candidates and search_external:
            external_results = await self._search_external_sources(query, country_hint)

        # Deduplicate and rank candidates
        candidates = self._deduplicate_candidates(candidates)
        for i, c in enumerate(candidates[: self.MAX_CANDIDATES], start=1):
            c.rank = i

        for i, c in enumerate(external_results[: self.MAX_CANDIDATES], start=1):
            c.rank = i

        # Determine result status
        elapsed_ms = int((time.time() - start_time) * 1000)

        if candidates:
            top_candidate = candidates[0]
            second_candidate = candidates[1] if len(candidates) > 1 else None

            # Auto-confirm if:
            # 1. High confidence (>= 80%)
            # 2. OR significant margin over second candidate (>= 15%)
            should_auto_confirm = False

            if top_candidate.confidence_score >= self.AUTO_CONFIRM_THRESHOLD * 100:
                should_auto_confirm = True
                logger.debug(
                    f"Auto-confirm: {top_candidate.canonical_name} "
                    f"(confidence={top_candidate.confidence_score}%)"
                )
            elif second_candidate:
                margin = (
                    top_candidate.confidence_score - second_candidate.confidence_score
                )
                if margin >= self.MARGIN_THRESHOLD * 100:
                    should_auto_confirm = True
                    logger.debug(
                        f"Auto-confirm by margin: {top_candidate.canonical_name} "
                        f"(margin={margin}% over {second_candidate.canonical_name})"
                    )

            if should_auto_confirm:
                return ResolutionResult(
                    status=ResolutionStatus.EXACT_MATCH,
                    query=query,
                    exact_match=top_candidate,
                    candidates=candidates,
                    requires_confirmation=False,
                    resolution_time_ms=elapsed_ms,
                )

            # Require confirmation only for truly ambiguous cases
            return ResolutionResult(
                status=ResolutionStatus.CONFIRMATION_REQUIRED,
                query=query,
                candidates=candidates[: self.MAX_CANDIDATES],
                requires_confirmation=True,
                confirmation_message=self._build_confirmation_message(
                    candidates[: self.MAX_CANDIDATES]
                ),
                resolution_time_ms=elapsed_ms,
            )

        if external_results:
            return ResolutionResult(
                status=ResolutionStatus.CONFIRMATION_REQUIRED,
                query=query,
                external_results=external_results[: self.MAX_CANDIDATES],
                requires_confirmation=True,
                confirmation_message=self._build_confirmation_message(
                    external_results[: self.MAX_CANDIDATES], is_external=True
                ),
                resolution_time_ms=elapsed_ms,
            )

        return ResolutionResult(
            status=ResolutionStatus.NO_MATCH,
            query=query,
            resolution_time_ms=elapsed_ms,
        )

    async def confirm_selection(
        self,
        session_id: str,
        candidate: EntityCandidate,
        user_id: Optional[str] = None,
    ) -> Entity:
        """
        Confirm user's entity selection.

        If entity doesn't exist in registry (from external source), creates it.
        Records resolution history for audit.

        Args:
            session_id: Conversation session ID
            candidate: Selected candidate
            user_id: Optional user identifier

        Returns:
            Confirmed Entity from registry
        """
        await self._ensure_initialized()
        assert self._db is not None, "Database not initialized"

        if candidate.entity_id:
            # Existing entity - just record the selection
            entity_dict = await self._db.get_entity_by_id(candidate.entity_id)
            if entity_dict:
                await self._db.record_resolution(
                    session_id=session_id,
                    user_query=candidate.canonical_name,
                    resolution_type="user_confirmed",
                    entity_id=candidate.entity_id,
                    selected_rank=candidate.rank,
                )
                return Entity.from_dict(entity_dict)

        # New entity from external source - create it
        entity_id = await self._db.create_entity(
            canonical_name=candidate.canonical_name,
            country_code=candidate.country_code,
            legal_name=candidate.legal_name,
            uen=candidate.uen,
            lei=candidate.lei,
            verification_status="user_confirmed",
            verified_by=user_id or "user",
            acra_data=candidate.external_data if candidate.source == "acra" else None,
            gleif_data=candidate.external_data if candidate.source == "gleif" else None,
            opencorporates_data=(
                candidate.external_data
                if candidate.source == "opencorporates"
                else None
            ),
        )

        # Add the original query as an alias
        await self._db.add_alias(
            entity_id=entity_id,
            alias_text=candidate.canonical_name,
            alias_type="common_name",
            source="user_input",
        )

        # Record resolution
        await self._db.record_resolution(
            session_id=session_id,
            user_query=candidate.canonical_name,
            resolution_type="new_entity",
            entity_id=entity_id,
            selected_rank=candidate.rank,
        )

        entity_dict = await self._db.get_entity_by_id(entity_id)
        return Entity.from_dict(entity_dict)

    async def get_entity_for_system(self, entity_id: str, system: str) -> Optional[str]:
        """
        Get external system ID for an entity.

        Args:
            entity_id: Entity registry ID
            system: Target system name ("sap", "eodhd", "aravo")

        Returns:
            External system ID or None
        """
        await self._ensure_initialized()
        assert self._db is not None, "Database not initialized"
        mapping = await self._db.get_external_mapping(entity_id, system)
        return mapping["external_id"] if mapping else None

    async def add_system_mapping(
        self,
        entity_id: str,
        system: str,
        external_id: str,
        external_data: Optional[dict] = None,
    ) -> None:
        """Add external system mapping for entity."""
        await self._ensure_initialized()
        assert self._db is not None, "Database not initialized"
        await self._db.add_external_mapping(
            entity_id=entity_id,
            external_system=system,
            external_id=external_id,
            external_data=external_data,
            verified=True,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _looks_like_uen(self, text: str) -> bool:
        """Check if text looks like a Singapore UEN."""
        import re

        # UEN format: 8-10 alphanumeric, ends with letter
        return bool(re.match(r"^[0-9]{8,9}[A-Za-z]$", text.strip()))

    def _looks_like_lei(self, text: str) -> bool:
        """Check if text looks like an LEI."""
        import re

        # LEI format: 20 alphanumeric characters
        return bool(re.match(r"^[A-Z0-9]{20}$", text.strip().upper()))

    def _calculate_max_edit_distance(self, query: str) -> int:
        """
        Calculate maximum allowed edit distance based on query length.

        Short names (< 6 chars): max 1 edit (e.g., "Maersk" -> "Maerks")
        Medium names (6-12 chars): max 2 edits
        Long names (> 12 chars): max 3 edits

        This prevents matching "ABC" to "XYZ" (edit distance 3) while
        still catching "Maersk" -> "Maerks" (edit distance 2).
        """
        query_len = len(query.strip())
        if query_len < 6:
            return 1
        elif query_len <= 12:
            return 2
        else:
            return 3

    def _entity_to_candidate(
        self, entity: dict, match_type: str, confidence: float
    ) -> EntityCandidate:
        """Convert entity dict to EntityCandidate."""
        return EntityCandidate(
            entity_id=str(entity["id"]),
            canonical_name=entity["canonical_name"],
            legal_name=entity.get("legal_name"),
            country_code=entity["country_code"],
            uen=entity.get("uen"),
            lei=entity.get("lei"),
            match_type=match_type,
            confidence_score=confidence,
            source="registry",
        )

    def _create_exact_match_result(
        self, query: str, candidate: EntityCandidate, start_time: float
    ) -> ResolutionResult:
        """Create result for exact match."""
        elapsed_ms = int((time.time() - start_time) * 1000)
        return ResolutionResult(
            status=ResolutionStatus.EXACT_MATCH,
            query=query,
            exact_match=candidate,
            candidates=[candidate],
            requires_confirmation=False,
            resolution_time_ms=elapsed_ms,
        )

    def _deduplicate_candidates(
        self, candidates: list[EntityCandidate]
    ) -> list[EntityCandidate]:
        """Remove duplicate candidates, keeping highest confidence."""
        seen: dict[str, EntityCandidate] = {}
        for c in candidates:
            key = c.entity_id or c.canonical_name.lower()
            if key not in seen or c.confidence_score > seen[key].confidence_score:
                seen[key] = c
        return sorted(seen.values(), key=lambda x: -x.confidence_score)

    async def _search_external_sources(
        self, query: str, country_hint: Optional[str]
    ) -> list[EntityCandidate]:
        """Search external sources for entity."""
        candidates: list[EntityCandidate] = []

        # ACRA for Singapore
        if country_hint == "SG" or not country_hint:
            try:
                if self._acra_client:
                    acra_results = await self._acra_client.search_by_name(query)
                    for r in acra_results[:3]:
                        candidates.append(
                            EntityCandidate(
                                entity_id=None,
                                canonical_name=r.entity_name,
                                legal_name=r.entity_name,
                                country_code="SG",
                                uen=r.uen,
                                match_type="external",
                                confidence_score=85.0,
                                match_reasons=["ACRA registry match"],
                                source="acra",
                                external_data=r.to_dict(),
                            )
                        )
            except Exception as e:
                logger.warning(f"ACRA search failed: {e}")

        # GLEIF for global
        try:
            if self._gleif_client:
                gleif_results = await self._gleif_client.search(
                    query, country=country_hint
                )
                for r in gleif_results[:3]:
                    candidates.append(
                        EntityCandidate(
                            entity_id=None,
                            canonical_name=r.legal_name,
                            legal_name=r.legal_name,
                            country_code=r.headquarters_country or "XX",
                            lei=r.lei,
                            match_type="external",
                            confidence_score=90.0,
                            match_reasons=["GLEIF LEI match"],
                            source="gleif",
                            external_data=r.to_dict(),
                        )
                    )
        except Exception as e:
            logger.warning(f"GLEIF search failed: {e}")

        # OpenCorporates for long-tail
        try:
            if self._opencorporates_client:
                oc_results = await self._opencorporates_client.search(
                    query, jurisdiction=country_hint
                )
                for r in oc_results[:3]:
                    # Extract country from jurisdiction_code (e.g., "sg" -> "SG")
                    country = (
                        r.jurisdiction_code.upper()[:2] if r.jurisdiction_code else "XX"
                    )
                    candidates.append(
                        EntityCandidate(
                            entity_id=None,
                            canonical_name=r.name,
                            legal_name=r.name,
                            country_code=country,
                            match_type="external",
                            confidence_score=75.0,
                            match_reasons=["OpenCorporates registry match"],
                            source="opencorporates",
                            external_data=r.to_dict(),
                        )
                    )
        except Exception as e:
            logger.warning(f"OpenCorporates search failed: {e}")

        return self._deduplicate_candidates(candidates)

    def _build_confirmation_message(
        self, candidates: list[EntityCandidate], is_external: bool = False
    ) -> str:
        """Build inline confirmation message for chat."""
        if is_external:
            lines = [
                "I couldn't find an exact match in our registry. Here are results from external sources:\n"
            ]
        else:
            lines = ["I found the following potential matches:\n"]

        for c in candidates:
            # Build identifier string
            identifiers = []
            if c.uen:
                identifiers.append(f"UEN: {c.uen}")
            if c.lei:
                identifiers.append(f"LEI: {c.lei}")
            id_str = " | ".join(identifiers) if identifiers else ""

            # Confidence bar
            confidence_bar = "█" * int(c.confidence_score / 10)

            lines.append(f"  {c.rank}. {c.canonical_name}")
            if id_str:
                lines.append(f"     {id_str}")
            lines.append(
                f"     Country: {c.country_code} | Confidence: {c.confidence_score:.0f}% {confidence_bar}"
            )
            if c.match_reasons:
                lines.append(f"     {c.match_reasons[0]}")
            lines.append("")

        # Dynamic message based on number of candidates
        num_candidates = len(candidates)
        if num_candidates == 1:
            lines.append("Reply with '1' or 'yes' to confirm, or provide more details.")
        else:
            lines.append(
                f"Please reply with a number (1-{num_candidates}) to confirm, or provide more details."
            )

        return "\n".join(lines)


# Singleton instance
_service_instance: Optional[EntityResolutionService] = None


def get_entity_resolution_service() -> EntityResolutionService:
    """Get singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = EntityResolutionService()
    return _service_instance
