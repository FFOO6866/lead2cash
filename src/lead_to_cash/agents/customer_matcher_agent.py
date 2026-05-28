"""
Customer Matcher Agent - LLM-Based Intelligent Customer Matching

Uses Kaizen BaseAgent for intelligent fuzzy matching of customer names across
SAP/CPI customer data and KYP compliance reports.

Problem Solved:
    The current CustomerValidationService uses hardcoded lookup tables which are:
    - Fragile (requires manual updates for new customers)
    - Limited (exact/partial string matching only)
    - Error-prone (can't handle typos, abbreviations, variations)

Solution:
    LLM-based semantic matching that understands:
    - Company name variations (BatamFast vs Batam Fast Ferry Pte Ltd)
    - Abbreviations (RRPS vs Rolls-Royce Power Systems)
    - Typos and misspellings
    - Related entity names (subsidiaries, parent companies)

Architecture:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  CustomerMatcherAgent                                                    │
    │    ├── Input: Free-text customer name from sales team                   │
    │    │                                                                     │
    │    ├── Step 1: Search SAP/CPI for potential matches                     │
    │    │    └── CPISimulator.list_customers() or MS5Client search           │
    │    │                                                                     │
    │    ├── Step 2: Search KYP reports for partner matches                   │
    │    │    └── KYPProcessor.list_reports() for available reports           │
    │    │                                                                     │
    │    ├── Step 3: LLM analyzes and ranks candidates                        │
    │    │    ├── Semantic similarity scoring                                  │
    │    │    ├── Entity relationship analysis                                 │
    │    │    └── Confidence scoring (0-100%)                                  │
    │    │                                                                     │
    │    └── Output: Ranked list of CustomerMatchCandidate                    │
    └─────────────────────────────────────────────────────────────────────────┘

Flow for Human-in-the-Loop Confirmation:
    1. Sales enters "batam fast ferry" (free text)
    2. Agent returns ranked candidates:
       [1] Batam Fast Ferry Pte. Ltd. (SAP: 0000100001) - 95% confidence
       [2] BatamFast (KYP Report) - 92% confidence
    3. User selects [1] to confirm match
    4. System proceeds with customer_id=0000100001 for validation

Usage:
    from lead_to_cash.agents import CustomerMatcherAgent, CustomerMatcherConfig
    from lead_to_cash.integrations import CPISimulator
    from lead_to_cash.services.kyp_processor import KYPProcessor

    # Setup
    cpi = CPISimulator()
    await cpi.connect()
    kyp = KYPProcessor(reports_directory="data/")

    config = CustomerMatcherConfig()
    agent = CustomerMatcherAgent(config, cpi_client=cpi, kyp_processor=kyp)

    # Find matches
    result = await agent.match_customer("batam fast ferry")

    # Present to user
    for candidate in result.candidates:
        print(f"{candidate.rank}. {candidate.name} - {candidate.confidence}%")
        print(f"   Source: {candidate.source}, ID: {candidate.customer_id}")

    # User selects match
    selected = result.candidates[0]  # User chose first option
    customer_id = selected.customer_id

    # Proceed with validation using confirmed customer_id
    validation_result = await validation_service.validate_customer(customer_id)
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional

from kaizen.core.base_agent import BaseAgent
from kaizen.memory.shared_memory import SharedMemoryPool
from kaizen.signatures import InputField, OutputField, Signature

if TYPE_CHECKING:
    from kaizen.nodes.ai.a2a import Capability

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class MatchSource(str, Enum):
    """Source system where the customer match was found."""

    SAP_CPI = "SAP_CPI"  # SAP/CPI customer master data
    KYP_REPORT = "KYP_REPORT"  # KYP compliance report
    BOTH = "BOTH"  # Found in both systems


class MatchConfidence(str, Enum):
    """Confidence level categories for matching."""

    HIGH = "HIGH"  # >= 90% - Very likely correct match
    MEDIUM = "MEDIUM"  # 70-89% - Probable match, verify
    LOW = "LOW"  # 50-69% - Possible match, needs review
    UNCERTAIN = "UNCERTAIN"  # < 50% - Weak match


@dataclass
class CustomerMatchCandidate:
    """
    A candidate customer match with confidence scoring.

    Attributes:
        rank: Position in ranked results (1 = best match)
        name: Customer/partner name as stored in source system
        customer_id: SAP customer ID (if from SAP/CPI)
        source: Which system(s) the match came from
        confidence_score: 0-100 confidence percentage
        confidence_level: Categorical confidence (HIGH/MEDIUM/LOW/UNCERTAIN)
        match_reasons: Why LLM considers this a match
        sap_data: Additional SAP data if available (credit, address, etc.)
        kyp_data: Additional KYP data if available (risk rating, status)
    """

    rank: int
    name: str
    customer_id: Optional[str]
    source: MatchSource
    confidence_score: float
    confidence_level: MatchConfidence
    match_reasons: list[str]
    sap_data: Optional[dict[str, Any]] = None
    kyp_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "rank": self.rank,
            "name": self.name,
            "customer_id": self.customer_id,
            "source": self.source.value,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level.value,
            "match_reasons": self.match_reasons,
            "sap_data": self.sap_data,
            "kyp_data": self.kyp_data,
        }


@dataclass
class CustomerMatchResult:
    """
    Result of customer matching operation.

    Attributes:
        query: Original search query from user
        candidates: Ranked list of potential matches
        best_match: Top candidate (if confidence >= threshold)
        has_high_confidence_match: Whether any match has HIGH confidence
        requires_user_confirmation: Whether user should confirm the match
        search_stats: Statistics about the search
    """

    query: str
    candidates: list[CustomerMatchCandidate]
    best_match: Optional[CustomerMatchCandidate]
    has_high_confidence_match: bool
    requires_user_confirmation: bool
    search_stats: dict[str, Any]
    no_customer_mentioned: bool = False  # True if LLM determined no customer in query
    searched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "query": self.query,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_match": self.best_match.to_dict() if self.best_match else None,
            "has_high_confidence_match": self.has_high_confidence_match,
            "requires_user_confirmation": self.requires_user_confirmation,
            "search_stats": self.search_stats,
            "no_customer_mentioned": self.no_customer_mentioned,
            "searched_at": self.searched_at.isoformat(),
        }

    def get_candidate_by_rank(self, rank: int) -> Optional[CustomerMatchCandidate]:
        """Get candidate by rank number (1-indexed)."""
        for candidate in self.candidates:
            if candidate.rank == rank:
                return candidate
        return None


# =============================================================================
# Signature Definition
# =============================================================================


class CustomerMatcherSignature(Signature):
    """
    Signature for intelligent customer matching.

    Takes a free-text query (can be full user request or just customer name) and
    candidate data from SAP/KYP, then uses LLM to analyze, match, and rank candidates.

    CRITICAL: The search_query can be a full user request like "show me batam collections"
    or "what's overdue for ST Engineering". You must extract the customer reference from
    the request and match it against the candidates.

    If the query is a general request with NO customer mentioned (e.g., "show collections",
    "billing summary", "what's overdue"), set no_customer_mentioned to "true".
    """

    # Input Fields
    search_query: str = InputField(
        description="Free-text query - can be a customer name OR a full user request containing a customer reference. Examples: 'batam fast ferry', 'show me batam collections', 'what's overdue for ST Engineering', 'maersk invoices'. Extract the customer reference and match against candidates."
    )
    sap_candidates: str = InputField(
        description="JSON array of SAP/CPI customer records to consider as potential matches"
    )
    kyp_candidates: str = InputField(
        description="JSON array of KYP report partner records to consider as potential matches"
    )
    context: str = InputField(
        description="Additional context about the search (industry, region, relationship type)",
        default="",
    )

    # Output Fields
    ranked_matches: str = OutputField(
        description="""JSON array of ranked matches. Each match must have:
- name: The customer/partner name as stored in the source system
- customer_id: SAP customer ID (null if only in KYP)
- source: "SAP_CPI", "KYP_REPORT", or "BOTH"
- confidence_score: 0-100 percentage indicating match confidence
- match_reasons: Array of reasons why this is considered a match (e.g., "Exact company name match", "Name is abbreviation of full legal name", "Same parent company")

Ranking criteria (in order of importance):
1. Exact name match (highest confidence)
2. Legal entity name match (e.g., "Pte Ltd" vs "Pte. Ltd.")
3. Common abbreviation (e.g., "BatamFast" for "Batam Fast Ferry")
4. Parent/subsidiary relationship
5. Phonetic similarity (for typo tolerance)

Return empty array if no reasonable matches found."""
    )

    analysis_summary: str = OutputField(
        description="Brief summary of the matching analysis (2-3 sentences explaining the top match and any concerns)"
    )

    match_found: str = OutputField(
        description="'true' if at least one match with >= 50% confidence found, 'false' otherwise"
    )

    no_customer_mentioned: str = OutputField(
        description="'true' if the search_query is a general request with NO customer/company mentioned (e.g., 'show collections', 'billing summary', 'what items are overdue'). 'false' if a customer IS mentioned in the query (e.g., 'batam collections', 'ST Engineering billing', 'maersk invoices')."
    )


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class CustomerMatcherConfig:
    """
    Configuration for Customer Matcher Agent.

    BaseAgent will auto-convert these fields to BaseAgentConfig.
    """

    # LLM Configuration
    llm_provider: str = "openai"
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o")
    temperature: float = 0.2  # Low for consistent matching
    max_tokens: int = 2000
    use_async_llm: bool = True  # Enable async mode for run_async() calls

    # Matching Configuration
    min_confidence_threshold: float = 50.0  # Minimum % to include in results
    high_confidence_threshold: float = 90.0  # % for HIGH confidence
    medium_confidence_threshold: float = 70.0  # % for MEDIUM confidence
    max_candidates: int = 10  # Maximum candidates to return
    auto_confirm_threshold: float = (
        99.0  # Auto-confirm only for near-exact matches (like KYP)
    )

    # Agent Metadata
    agent_name: str = "customer_matcher_agent"
    agent_description: str = (
        "Intelligent customer name matching using LLM semantic analysis"
    )


# =============================================================================
# System Prompt
# =============================================================================

CUSTOMER_MATCHER_SYSTEM_PROMPT = """You are a customer matching specialist for Rolls-Royce Power Systems (RRPS).

Your task is to match free-text customer names entered by sales teams to official customer records from:
1. SAP/CPI customer master data (has customer IDs, addresses, credit info)
2. KYP compliance reports (has partner names, risk ratings, approval status)

MATCHING RULES:

1. **Exact Matches (95-100% confidence)**
   - Same company name (case-insensitive)
   - Same legal entity with minor formatting differences
   - Example: "Batam Fast Ferry Pte Ltd" = "Batam Fast Ferry Pte. Ltd."

2. **Abbreviation Matches (85-94% confidence)**
   - Common business abbreviations
   - Example: "BatamFast" is abbreviation for "Batam Fast Ferry Pte Ltd"
   - Example: "AP Moller" = "A.P. Moller - Maersk A/S"

3. **Partial Matches (70-84% confidence)**
   - Contains key identifying words
   - Example: "Maersk Line" matches "A.P. Moller - Maersk A/S"

4. **Fuzzy Matches (50-69% confidence)**
   - Phonetically similar names
   - Possible typos (Levenshtein distance)
   - Related entities (subsidiaries, divisions)

5. **Cross-System Matching**
   - If same customer appears in both SAP and KYP, mark source as "BOTH"
   - SAP data takes precedence for customer_id
   - Combine reasons from both sources

IMPORTANT CONSIDERATIONS:
- RRPS customers are typically: shipyards, ferry operators, offshore companies, port authorities
- Pay attention to: Pte Ltd, A/S, B.V., GmbH, Ltd variations
- Singapore companies often have "Pte Ltd" or "Pte. Ltd."
- Nordic companies use A/S (Denmark), AS (Norway), AB (Sweden)

OUTPUT FORMAT:
Return matches sorted by confidence_score (highest first).
Include match_reasons explaining WHY each is considered a match.
Be conservative - only include matches >= 50% confidence."""


# =============================================================================
# Customer Matcher Agent Implementation
# =============================================================================


class CustomerMatcherAgent(BaseAgent):
    """
    Customer Matcher Agent using LLM for intelligent fuzzy matching.

    Searches across SAP/CPI customer data and KYP compliance reports to find
    the best matches for free-text customer names entered by sales teams.

    Features:
    - Semantic understanding of company names
    - Handles abbreviations, typos, variations
    - Cross-references SAP and KYP data
    - Returns ranked candidates with confidence scores
    - Supports human-in-the-loop confirmation

    Example:
        config = CustomerMatcherConfig()
        agent = CustomerMatcherAgent(config, cpi_client=cpi, kyp_processor=kyp)

        # Find matches for user input
        result = await agent.match_customer("batam fast ferry")

        # Present candidates to user
        for c in result.candidates:
            print(f"{c.rank}. {c.name} ({c.confidence_score}%)")

        # User confirms selection
        selected = result.candidates[0]
        proceed_with_customer_id(selected.customer_id)
    """

    def __init__(
        self,
        config: CustomerMatcherConfig,
        cpi_client: Optional[Any] = None,
        kyp_processor: Optional[Any] = None,
        shared_memory: Optional[SharedMemoryPool] = None,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize Customer Matcher Agent.

        Args:
            config: Agent configuration
            cpi_client: CPISimulator or CPIClient for SAP customer data
            kyp_processor: KYPProcessor for compliance report data
            shared_memory: Optional shared memory pool for multi-agent coordination
            agent_id: Unique agent identifier
        """
        super().__init__(
            config=config,
            signature=CustomerMatcherSignature(),
            shared_memory=shared_memory,
            agent_id=agent_id or config.agent_name,
            system_prompt=CUSTOMER_MATCHER_SYSTEM_PROMPT,
        )

        self.domain_config = config
        self._cpi = cpi_client
        self._kyp = kyp_processor
        self._shared_memory = shared_memory  # Store for consistent access

    # -------------------------------------------------------------------------
    # Data Collection Methods
    # -------------------------------------------------------------------------

    async def _get_sap_candidates(self) -> list[dict[str, Any]]:
        """
        Get all SAP/CPI customers as potential match candidates.

        Returns:
            List of customer records with id, name, address, credit info
        """
        if not self._cpi:
            logger.warning("No CPI client configured, SAP candidates unavailable")
            return []

        try:
            # CPISimulator and MS5Client both support list_customers()
            if hasattr(self._cpi, "list_customers"):
                customers = self._cpi.list_customers()
                return customers
            else:
                logger.warning("CPI client does not support list_customers()")
                return []

        except Exception as e:
            logger.error(f"Error fetching SAP candidates: {e}")
            return []

    async def _get_kyp_candidates(self) -> list[dict[str, Any]]:
        """
        Get all KYP report partners as potential match candidates.

        Returns:
            List of partner records with name, risk rating, approval status
        """
        if not self._kyp:
            logger.warning("No KYP processor configured, KYP candidates unavailable")
            return []

        try:
            reports = self._kyp.list_reports()
            return [
                {
                    "partner_name": r["partner_name"],
                    "legal_entity": r.get("legal_entity", r["partner_name"]),
                    "risk_rating": r.get("risk_rating", "NOT_ASSESSED"),
                    "approval_status": r.get("approval_status", "NOT_ASSESSED"),
                    "report_date": r.get("report_date"),
                    "source_file": r.get("source_file"),
                }
                for r in reports
            ]

        except Exception as e:
            logger.error(f"Error fetching KYP candidates: {e}")
            return []

    # -------------------------------------------------------------------------
    # Shared Memory Methods
    # -------------------------------------------------------------------------

    async def _check_memory_for_context(
        self,
        key: str,
        tags: List[str],
        max_age_seconds: float = 1800.0,  # 30 min default TTL for matches
    ) -> Optional[dict[str, Any]]:
        """
        Check shared memory for relevant context before expensive operations.

        This method enables multi-agent coordination by allowing agents to
        share match results and avoid redundant LLM calls.

        Args:
            key: Identifier for logging (e.g., search query)
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
                    f"Memory hit for '{key}' from agent '{insight.get('agent_id')}'"
                )
                return insight.get("content")

        except Exception as e:
            logger.debug(f"Memory search failed for {key}: {e}")

        return None

    # -------------------------------------------------------------------------
    # Main Matching Method
    # -------------------------------------------------------------------------

    async def match_customer(
        self,
        search_query: str,
        context: str = "",
    ) -> CustomerMatchResult:
        """
        Find matching customers for a free-text search query.

        Args:
            search_query: Free-text customer name (e.g., "batam fast ferry")
            context: Optional context (e.g., "Singapore ferry operator")

        Returns:
            CustomerMatchResult with ranked candidates and analysis
        """
        logger.info(f"Matching customer: '{search_query}'")

        # Check shared memory for recent high-confidence match
        search_key = search_query.split()[0].lower() if search_query else ""
        cached = await self._check_memory_for_context(
            key=search_query,
            tags=["customer_matcher", "search", search_key],
            max_age_seconds=1800.0,  # 30 min cache TTL
        )

        if cached and cached.get("confidence", 0) >= 95:
            # High-confidence match found in cache - log and note it
            logger.info(
                f"High-confidence cached match: '{cached.get('best_match')}' "
                f"({cached.get('confidence')}%)"
            )
            # Note: Full caching would require storing CustomerMatchCandidate objects
            # For now, we log and proceed - other agents can use this insight

        # Step 1: Collect candidate data from both sources
        sap_candidates = await self._get_sap_candidates()
        kyp_candidates = await self._get_kyp_candidates()

        search_stats = {
            "sap_candidates_count": len(sap_candidates),
            "kyp_candidates_count": len(kyp_candidates),
            "total_candidates": len(sap_candidates) + len(kyp_candidates),
        }

        if not sap_candidates and not kyp_candidates:
            logger.warning("No candidates available from either SAP or KYP")
            return CustomerMatchResult(
                query=search_query,
                candidates=[],
                best_match=None,
                has_high_confidence_match=False,
                requires_user_confirmation=True,
                search_stats=search_stats,
            )

        # Step 2: Use LLM to analyze and rank candidates
        try:
            # Use run_async for async context (avoids asyncio.run() nesting issue)
            result = await self.run_async(
                search_query=search_query,
                sap_candidates=json.dumps(sap_candidates),
                kyp_candidates=json.dumps(kyp_candidates),
                context=context,
            )

            # Step 3: Parse LLM response
            ranked_matches = self._parse_ranked_matches(result)
            analysis_summary = result.get("analysis_summary", "")
            # Handle both boolean and string values from LLM
            match_found_raw = result.get("match_found", "false")
            _match_found = (  # noqa: F841 - parsed but used indirectly via ranked_matches
                match_found_raw
                if isinstance(match_found_raw, bool)
                else str(match_found_raw).lower() == "true"
            )

            # Check if LLM determined no customer was mentioned in the query
            no_customer_raw = result.get("no_customer_mentioned", "false")
            no_customer_mentioned = (
                no_customer_raw
                if isinstance(no_customer_raw, bool)
                else str(no_customer_raw).lower() == "true"
            )

            # If no customer mentioned, return early with special flag
            if no_customer_mentioned:
                logger.info(
                    f"LLM determined no customer mentioned in query: {search_query}"
                )
                return CustomerMatchResult(
                    query=search_query,
                    candidates=[],
                    best_match=None,
                    has_high_confidence_match=False,
                    requires_user_confirmation=False,
                    search_stats={**search_stats, "no_customer_in_query": True},
                    no_customer_mentioned=True,
                )

        except Exception as e:
            logger.error(f"LLM matching failed: {e}")
            return CustomerMatchResult(
                query=search_query,
                candidates=[],
                best_match=None,
                has_high_confidence_match=False,
                requires_user_confirmation=True,
                search_stats={**search_stats, "error": str(e)},
            )

        # Step 4: Convert to CustomerMatchCandidate objects
        candidates = self._create_candidates(
            ranked_matches, sap_candidates, kyp_candidates
        )

        # Step 5: Determine best match and confirmation requirements
        best_match = candidates[0] if candidates else None
        has_high_confidence = (
            best_match is not None
            and best_match.confidence_level == MatchConfidence.HIGH
        )

        # Auto-confirm only if single HIGH confidence match
        auto_confirm = (
            len(candidates) == 1
            and best_match is not None
            and best_match.confidence_score >= self.domain_config.auto_confirm_threshold
        )
        requires_confirmation = not auto_confirm

        # Write to shared memory for other agents
        if self._shared_memory and candidates:
            self.write_to_memory(
                content={
                    "query": search_query,
                    "best_match": best_match.name if best_match else None,
                    "confidence": best_match.confidence_score if best_match else 0,
                    "candidates_count": len(candidates),
                },
                tags=["customer_matcher", "search", search_query.split()[0]],
                importance=0.7,
            )

        return CustomerMatchResult(
            query=search_query,
            candidates=candidates,
            best_match=best_match,
            has_high_confidence_match=has_high_confidence,
            requires_user_confirmation=requires_confirmation,
            search_stats={
                **search_stats,
                "matches_found": len(candidates),
                "analysis_summary": analysis_summary,
            },
        )

    def _parse_ranked_matches(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse ranked_matches JSON from LLM response."""
        ranked_json = result.get("ranked_matches", "[]")

        try:
            if isinstance(ranked_json, str):
                matches = json.loads(ranked_json)
            else:
                matches = ranked_json

            return matches if isinstance(matches, list) else []

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse ranked_matches JSON: {e}")
            return []

    def _create_candidates(
        self,
        ranked_matches: list[dict[str, Any]],
        sap_candidates: list[dict[str, Any]],
        kyp_candidates: list[dict[str, Any]],
    ) -> list[CustomerMatchCandidate]:
        """
        Create CustomerMatchCandidate objects from LLM results.

        Enriches with additional data from SAP/KYP sources.
        """
        candidates = []

        # Create lookup maps for enrichment
        sap_by_name = {c.get("name", "").lower(): c for c in sap_candidates}
        sap_by_id = {c.get("customer_id", ""): c for c in sap_candidates}
        kyp_by_name = {c.get("partner_name", "").lower(): c for c in kyp_candidates}

        for rank, match in enumerate(ranked_matches, start=1):
            if rank > self.domain_config.max_candidates:
                break

            # Handle both confidence_score (0-100) and match_score (0-1) formats
            confidence_score = float(match.get("confidence_score", 0))
            if confidence_score == 0:
                # Try match_score (LLM sometimes uses this 0-1 format)
                match_score = float(match.get("match_score", 0))
                if match_score > 0:
                    # Convert 0-1 to 0-100 percentage
                    confidence_score = (
                        match_score * 100 if match_score <= 1 else match_score
                    )

            # Filter by minimum threshold
            if confidence_score < self.domain_config.min_confidence_threshold:
                continue

            # Determine confidence level
            if confidence_score >= self.domain_config.high_confidence_threshold:
                confidence_level = MatchConfidence.HIGH
            elif confidence_score >= self.domain_config.medium_confidence_threshold:
                confidence_level = MatchConfidence.MEDIUM
            elif confidence_score >= self.domain_config.min_confidence_threshold:
                confidence_level = MatchConfidence.LOW
            else:
                confidence_level = MatchConfidence.UNCERTAIN

            # Parse source
            source_str = match.get("source", "SAP_CPI")
            try:
                source = MatchSource(source_str)
            except ValueError:
                source = MatchSource.SAP_CPI

            # Get enriched data
            name = match.get("name", "")
            customer_id = match.get("customer_id")
            name_lower = name.lower()

            # Enrich with SAP data
            sap_data = None
            if customer_id and customer_id in sap_by_id:
                sap_data = sap_by_id[customer_id]
            elif name_lower in sap_by_name:
                sap_data = sap_by_name[name_lower]
                if not customer_id:
                    customer_id = sap_data.get("customer_id")

            # Enrich with KYP data
            kyp_data = None
            if name_lower in kyp_by_name:
                kyp_data = kyp_by_name[name_lower]
            else:
                # Try partial matching for KYP
                for kyp_name, kyp_record in kyp_by_name.items():
                    if kyp_name in name_lower or name_lower in kyp_name:
                        kyp_data = kyp_record
                        break

            # Get match reasons or provide default
            match_reasons = match.get("match_reasons", [])
            if not match_reasons:
                # Generate default reason based on confidence
                if confidence_score >= 90:
                    match_reasons = ["High similarity match"]
                elif confidence_score >= 70:
                    match_reasons = ["Probable match based on name similarity"]
                else:
                    match_reasons = ["Possible match - review recommended"]

            candidates.append(
                CustomerMatchCandidate(
                    rank=rank,
                    name=name,
                    customer_id=customer_id,
                    source=source,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    match_reasons=match_reasons,
                    sap_data=sap_data,
                    kyp_data=kyp_data,
                )
            )

        return candidates

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def match_and_select_best(
        self,
        search_query: str,
        min_confidence: float = 70.0,
    ) -> Optional[CustomerMatchCandidate]:
        """
        Match customer and return best match if above threshold.

        Convenience method for cases where auto-selection is acceptable.

        Args:
            search_query: Customer name to search
            min_confidence: Minimum confidence to return a match

        Returns:
            Best CustomerMatchCandidate or None if no good match
        """
        result = await self.match_customer(search_query)

        if result.best_match and result.best_match.confidence_score >= min_confidence:
            return result.best_match

        return None

    async def resolve_customer_id(
        self,
        search_query: str,
        min_confidence: float = 80.0,
    ) -> Optional[str]:
        """
        Resolve free-text customer name to SAP customer ID.

        Convenience method for getting just the customer ID.

        Args:
            search_query: Customer name to search
            min_confidence: Minimum confidence threshold

        Returns:
            SAP customer ID string or None
        """
        best = await self.match_and_select_best(search_query, min_confidence)
        return best.customer_id if best else None

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
                name="customer_matching",
                domain="crm",
                level=CapabilityLevel.EXPERT,
                description="LLM-based intelligent fuzzy matching of customer names across SAP/CPI and KYP data",
                keywords=[
                    "customer",
                    "match",
                    "matching",
                    "fuzzy",
                    "name",
                    "search",
                    "lookup",
                    "find",
                    "identify",
                    "resolve",
                    "sap",
                    "kyp",
                ],
                examples=[
                    "Find customer matching 'batam fast ferry'",
                    "Resolve customer name to SAP ID",
                    "Match customer across systems",
                ],
                constraints=[],
            ),
            Capability(
                name="customer_resolution",
                domain="sales",
                level=CapabilityLevel.ADVANCED,
                description="Resolve free-text customer names to SAP customer IDs",
                keywords=[
                    "resolve",
                    "customer_id",
                    "sap_id",
                    "identification",
                    "customer",
                    "id",
                ],
                examples=[
                    "Get SAP ID for customer 'Maersk Line'",
                    "Resolve 'BatamFast' to customer ID",
                ],
                constraints=[],
            ),
        ]

    # -------------------------------------------------------------------------
    # Synchronous Run Method (A2A Router Compatibility)
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
            task: Primary input from Pipeline.router()
            customer_name: Direct customer name input (alias for task)
            **kwargs: Additional parameters

        Returns:
            Standardized A2A response dict with success, agent_id, result_data
        """
        # Extract task (Pipeline.router convention) or customer_name
        task = kwargs.get("task", "")
        customer_name = kwargs.get("customer_name") or task

        if not customer_name:
            return {
                "success": False,
                "agent_id": self.agent_id,
                "result_data": {},
                "error_message": "No customer name provided. Use task= or customer_name=",
                "metadata": {"routing": "a2a_run_async"},
            }

        logger.info(
            f"CustomerMatcherAgent.execute_a2a() - customer_name: {customer_name}"
        )

        try:
            result = await self.match_customer(customer_name)
            return {
                "success": True,
                "agent_id": self.agent_id,
                "result_data": {
                    "match_result": result.to_dict() if result else None,
                    "customer_name": customer_name,
                },
                "error_message": None,
                "metadata": {"routing": "a2a_run_async"},
            }
        except Exception as e:
            logger.error(f"CustomerMatcherAgent.execute_a2a() failed: {e}")
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
        Uses domain-specific logic (match_customer) without LLM/memory overhead.

        For signature-based execution with Kaizen features (memory, hooks, LLM),
        use the inherited run_async() method instead.

        Args:
            task: Primary input from Pipeline.router()
            customer_name: Direct customer name input (alias for task)
            **kwargs: Additional parameters

        Returns:
            Standardized A2A response dict
        """
        return asyncio.run(self.execute_a2a(**kwargs))

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check health of customer matcher system.

        Returns:
            Health status with agent_id, status, capabilities, and system availability
        """
        # Get capabilities via _extract_primary_capabilities() (not buggy to_a2a_card)
        capabilities = [c.name for c in self._extract_primary_capabilities()]

        sap_ok = self._cpi is not None
        kyp_ok = self._kyp is not None

        sap_count = 0
        kyp_count = 0

        if sap_ok:
            try:
                sap_count = len(await self._get_sap_candidates())
            except Exception:
                sap_ok = False

        if kyp_ok:
            try:
                kyp_count = len(await self._get_kyp_candidates())
            except Exception:
                kyp_ok = False

        return {
            "agent_id": self.agent_id,
            "status": "healthy" if (sap_ok or kyp_ok) else "degraded",
            "capabilities": capabilities,
            "sap_configured": sap_ok,
            "kyp_configured": kyp_ok,
            "sap_candidates_available": sap_count,
            "kyp_candidates_available": kyp_count,
            "shared_memory_available": self._shared_memory is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# =============================================================================
# Factory Function
# =============================================================================


async def create_customer_matcher_agent(
    cpi_client: Optional[Any] = None,
    kyp_processor: Optional[Any] = None,
    llm_provider: str = "openai",
    model: str = os.getenv("OPENAI_PROD_MODEL", "gpt-4o"),
    shared_memory: Optional[SharedMemoryPool] = None,
) -> CustomerMatcherAgent:
    """
    Factory function to create a Customer Matcher Agent.

    Args:
        cpi_client: CPISimulator or CPIClient instance
        kyp_processor: KYPProcessor instance
        llm_provider: LLM provider (openai, anthropic)
        model: Model to use
        shared_memory: Optional shared memory pool

    Returns:
        Configured CustomerMatcherAgent instance
    """
    config = CustomerMatcherConfig(
        llm_provider=llm_provider,
        model=model,
    )

    return CustomerMatcherAgent(
        config=config,
        cpi_client=cpi_client,
        kyp_processor=kyp_processor,
        shared_memory=shared_memory,
    )
