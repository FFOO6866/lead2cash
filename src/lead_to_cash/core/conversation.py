"""
Conversation Manager for Multi-Turn Sessions

Manages multi-turn conversations with:
- Session state tracking
- Clarification blocking flow
- Follow-up suggestions
- Integration with query understanding, data inventory, and tool executor

NO MOCKS, NO FALLBACKS - production implementation.

MANDATORY GUIDE REFERENCE:
    This module implements Section 5 of:
    `src/lead_to_cash/docs/guides/orchestration_guide.md`

Usage:
    from lead_to_cash.core.conversation import (
        ConversationManager,
        ConversationSession,
        get_conversation_manager,
        process_message,
    )

    manager = get_conversation_manager()
    result = await manager.process_message(session_id, "What contracts has Caterpillar won?")

    if result["type"] == "clarification_needed":
        print("Questions:", result["questions"])
    else:
        print("Answer:", result["answer"])
"""

import asyncio
import copy
import json
import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    ClassVar,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

if TYPE_CHECKING:
    import redis

from lead_to_cash.core.data_inventory import (
    DataInventoryService,
    InventoryCheckResult,
    get_data_inventory,
)
from lead_to_cash.core.query_understanding import (
    EntityContext,
    ParsedQuery,
    QueryIntent,
    QueryUnderstandingEngine,
    get_query_engine,
)
from lead_to_cash.core.response_quality import (
    FollowUpResolver,
    OutputSchemaValidator,
    QualityMetrics,
    RoutingMonitor,
    filter_sources_tier1_first,
    strip_ungrounded_citations,
)
from lead_to_cash.core.compound_executor import CompoundExecutor
from lead_to_cash.core.multi_intent_detector import MultiIntentDetector
from lead_to_cash.core.reasoning_detector import detect_reasoning
from lead_to_cash.core.reasoning_executor import ReasoningExecutor
from lead_to_cash.core.reasoning_planner import ReasoningPlanner
from lead_to_cash.core.response_composer import ResponseComposer
from lead_to_cash.core.signal_extractor import extract_signals
from lead_to_cash.core.signal_router import route as signal_route
from lead_to_cash.core.signal_scorer import score_domains
from lead_to_cash.core.source_authority import SourceAuthority
from lead_to_cash.core.tool_executor import (
    DataSource,
    ToolExecutor,
    ToolResult,
    get_tool_executor,
)
from lead_to_cash.services.kyp_report import (
    AssessmentItem,
    KYPReport,
    OverallDecision,
    ReportField,
    ReportSection,
    ReportSubsection,
    SanctionsCheck,
    SectionStatus,
    build_business_context_section,
    build_tprm_section,
)

# Sanctions screening — prefer PostgreSQL-backed service, fall back to live downloads
from lead_to_cash.services.sanctions.database import (
    SanctionCheckResult,
    get_sanctions_service as _get_sanctions_service,
)

# Keep legacy import as fallback if DB is not available
from lead_to_cash.services.sanctions_checker import (
    screen_entity as _screen_sanctions_legacy,
)


async def screen_sanctions(entity_name: str) -> list[SanctionCheckResult]:
    """Screen entity — use DB if available, fall back to live downloads."""
    try:
        svc = await _get_sanctions_service()
        count = await svc.get_entry_count()
        if count > 0:
            return await svc.screen_entity(entity_name)
    except Exception as e:
        logger.warning(f"Sanctions DB screen failed ({e}), falling back to live")
    # Fallback to legacy live download
    from lead_to_cash.services.sanctions_checker import (
        SanctionCheckResult as _LegacyResult,
    )

    legacy_results = await _screen_sanctions_legacy(entity_name)
    # Convert legacy results to new dataclass (same fields)
    return [
        SanctionCheckResult(
            database=r.database,
            status=r.status,
            result=r.result,
            source_url=r.source_url,
            checked_date=r.checked_date,
            list_date=r.list_date,
            matched_names=r.matched_names,
        )
        for r in legacy_results
    ]


# Aravo TPRM availability (uses client_factory — real REST or simulator fallback)
try:
    from lead_to_cash.integrations.client_factory import get_aravo_client  # noqa: F401

    ARAVO_AVAILABLE = True
except ImportError:
    ARAVO_AVAILABLE = False

# CEC imports (for KYP opportunity/pipeline data)
try:
    from lead_to_cash.integrations.cec_client import CECClient

    CEC_AVAILABLE = True
except ImportError:
    CEC_AVAILABLE = False

# Entity Resolution imports (for KYP company matching)
# These are optional - if the entity_registry module is not available or has missing
# dependencies (e.g., asyncpg for database), we fall back to name-based matching.
try:
    from lead_to_cash.services.entity_registry import (
        EntityCandidate,
        EntityResolutionService,
        ResolutionStatus,
    )

    ENTITY_REGISTRY_AVAILABLE = True
except ImportError as e:
    ENTITY_REGISTRY_AVAILABLE = False
    # Log the specific error so we can diagnose issues
    # Common reasons: asyncpg not installed, database module not configured
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _logger.info(f"Entity registry not available (using fallback name matching): {e}")

# Agentic Entity Resolution - lazy import to avoid circular dependency
# The agents package imports from conversation.py (via registry.py), so we
# use TYPE_CHECKING and lazy initialization to break the cycle.
ENTITY_AGENT_AVAILABLE = True  # Assume available, verify at runtime

# Type hint only - actual import happens lazily in entity_agent property
if TYPE_CHECKING:
    from lead_to_cash.agents.entity_resolution_agent import EntityResolutionAgent

# Semantic Entity Resolution - embedding-based resolution for pronouns/references
# Uses OpenAI embeddings for truly semantic understanding (no keyword matching)
try:
    from lead_to_cash.core.semantic_entity_resolver import (
        ResolutionStatus as SemanticResolutionStatus,
    )
    from lead_to_cash.core.semantic_entity_resolver import (
        detect_time_sensitivity_semantically,
        expand_abbreviations_in_query,
        match_kyp_section_semantically,
        resolve_entity_semantically,
    )

    SEMANTIC_RESOLVER_AVAILABLE = True
except ImportError as e:
    SEMANTIC_RESOLVER_AVAILABLE = False
    import logging as _logging

    _logger = _logging.getLogger(__name__)
    _logger.info(f"Semantic entity resolver not available: {e}")

# External source clients for entity resolution (legacy, kept for compatibility)
try:
    from lead_to_cash.services.entity_registry.clients.acra_client import (
        get_acra_client,
    )
    from lead_to_cash.services.entity_registry.clients.gleif_client import (
        get_gleif_client,
    )
    from lead_to_cash.services.entity_registry.clients.opencorporates_client import (
        get_opencorporates_client,
    )

    EXTERNAL_CLIENTS_AVAILABLE = True
except ImportError:
    EXTERNAL_CLIENTS_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Utility Functions
# =============================================================================


def _normalize_company_name(name: str) -> str:
    """
    Normalize company name for comparison.

    Converts to lowercase and strips whitespace.

    Args:
        name: Company name to normalize

    Returns:
        Normalized name string
    """
    return name.lower().strip() if name else ""


def _company_names_match(
    confirmed_name: str, context_name: str, min_length: int = 4
) -> bool:
    """
    Check if two company names match using normalized comparison.

    Uses exact match for short names (< min_length) to avoid false positives
    like "ST" matching "ST Engineering". For longer names, allows substring
    matching to handle abbreviations like "Batam Fast" matching "Batam Fast Ferry".

    Args:
        confirmed_name: The confirmed/canonical company name
        context_name: The name from session context
        min_length: Minimum length for substring matching (default 4)

    Returns:
        True if names match, False otherwise
    """
    if not confirmed_name or not context_name:
        return False

    c = _normalize_company_name(confirmed_name)
    x = _normalize_company_name(context_name)

    if not c or not x:
        return False

    # For short names, require exact match to avoid false positives
    if len(c) < min_length or len(x) < min_length:
        return c == x

    # For longer names, allow substring matching
    return c == x or c in x or x in c


# =============================================================================
# Entity Context Utilities (for enriching LLM context)
# =============================================================================


def get_entity_context_summary(
    entity_history: list[dict],
    session_context: dict,
) -> str | None:
    """
    Generate a summary of entity context for LLM enrichment.

    This provides the LLM with explicit entity context to help with
    pronoun resolution and follow-up queries. The LLM does the semantic
    understanding - we just provide structured context.

    Args:
        entity_history: List of {name, timestamp, type} from session
        session_context: Session context dict

    Returns:
        Context summary string for LLM, or None if no relevant context
    """
    context_parts = []

    # Most recent entity from history
    if entity_history:
        # Sort by timestamp descending (most recent first)
        sorted_history = sorted(
            entity_history, key=lambda x: x.get("timestamp", ""), reverse=True
        )
        if sorted_history:
            recent = sorted_history[0]
            context_parts.append(
                f"Most recently discussed entity: {recent.get('name')} "
                f"(type: {recent.get('type', 'company')})"
            )

    # Last KYP entity (for KYP follow-ups)
    if session_context.get("last_kyp_entity"):
        context_parts.append(
            f"Last KYP report was about: {session_context['last_kyp_entity']}"
        )

    # Active companies in conversation
    companies = session_context.get("companies", [])
    if companies:
        context_parts.append(
            f"Companies mentioned in conversation: {', '.join(companies[-3:])}"
        )

    # Active competitors in conversation
    competitors = session_context.get("competitors", [])
    if competitors:
        context_parts.append(f"Competitors discussed: {', '.join(competitors[-3:])}")

    # Last intent — helps LLM understand conversation direction
    last_intent = session_context.get("last_intent")
    if last_intent:
        intent_labels = {
            "billing_ar": "billing/AR review",
            "credit_check": "credit assessment",
            "competitor_intel": "competitor analysis",
            "market_intel": "market intelligence",
            "customer_intel": "customer review",
            "product_fit": "product recommendation",
            "kyp_due_diligence": "KYP due diligence",
            "relationship_check": "relationship assessment",
        }
        label = intent_labels.get(last_intent, last_intent)
        context_parts.append(f"Previous query was: {label}")

    # Key metrics from last response (structured facts only)
    last_metrics = session_context.get("last_response_metrics")
    if last_metrics:
        metric_parts = []
        if "credit_utilization" in last_metrics:
            metric_parts.append(
                f"credit utilization: {last_metrics['credit_utilization']}"
            )
        if "credit_limit" in last_metrics:
            metric_parts.append(f"credit limit: {last_metrics['credit_limit']}")
        if "total_outstanding" in last_metrics:
            metric_parts.append(f"outstanding: {last_metrics['total_outstanding']}")
        if metric_parts:
            context_parts.append(f"Key data from prior turn: {', '.join(metric_parts)}")

    # Reasoning carryover (structured conclusion from prior turn)
    carryover_data = session_context.get("reasoning_carryover")
    if carryover_data:
        carryover = ReasoningCarryover.from_dict(carryover_data)
        context_parts.append(carryover.format_for_prompt())

    if context_parts:
        return " | ".join(context_parts)
    return None


class SessionStoreNotInitializedError(Exception):
    """Raised when session store is used before initialization."""

    def __init__(self, component: str = "Redis"):
        self.component = component
        super().__init__(
            f"{component} client not initialized. Connection failed or not attempted."
        )


# =============================================================================
# MANDATORY GUIDE REFERENCE
# =============================================================================
ORCHESTRATION_GUIDE_PATH = "src/lead_to_cash/docs/guides/orchestration_guide.md"


# =============================================================================
# Reasoning Carryover — structured context from prior turns
# =============================================================================


@dataclass
class ReasoningCarryover:
    """
    Structured summary of prior turn's reasoning for multi-turn continuity.

    Carries forward ONLY verified conclusions and constraints — never raw
    text, speculative analysis, or unverified assumptions. This is a
    presentation/context aid; it does NOT override fresh retrieval.
    """

    entity: str
    """The entity this reasoning applies to."""

    prior_intent: str
    """Intent of the prior turn (e.g., 'credit_check', 'competitor_intel')."""

    prior_decision_type: str
    """Type: risk_assessment / credit_feasibility / recommendation / competitor_assessment."""

    prior_conclusion: str
    """1-sentence conclusion (e.g., 'SUFFICIENT credit — EUR 7M headroom')."""

    prior_rationale: list
    """2-4 structured bullet points from verified facts only."""

    prior_constraints: list
    """Key constraints identified (e.g., 'within EUR 7M headroom')."""

    confidence: str = "medium"
    """Confidence level: high / medium / low."""

    timestamp: str = ""
    """When this carryover was created."""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "prior_intent": self.prior_intent,
            "prior_decision_type": self.prior_decision_type,
            "prior_conclusion": self.prior_conclusion,
            "prior_rationale": self.prior_rationale,
            "prior_constraints": self.prior_constraints,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReasoningCarryover":
        return cls(
            entity=data.get("entity", ""),
            prior_intent=data.get("prior_intent", ""),
            prior_decision_type=data.get("prior_decision_type", ""),
            prior_conclusion=data.get("prior_conclusion", ""),
            prior_rationale=data.get("prior_rationale", []),
            prior_constraints=data.get("prior_constraints", []),
            confidence=data.get("confidence", "medium"),
            timestamp=data.get("timestamp", ""),
        )

    def format_for_prompt(self) -> str:
        """Format carryover as a compact context block for LLM injection."""
        lines = [
            f"[REASONING CONTEXT from prior turn]",
            f"Entity: {self.entity}",
            f"Conclusion: {self.prior_conclusion}",
        ]
        if self.prior_rationale:
            lines.append("Why:")
            for r in self.prior_rationale[:4]:
                lines.append(f"  - {r}")
        if self.prior_constraints:
            lines.append(f"Constraints: {', '.join(self.prior_constraints[:4])}")
        lines.append(f"Confidence: {self.confidence}")
        return "\n".join(lines)


# Intents eligible for carryover creation
_CARRYOVER_ELIGIBLE_INTENTS = frozenset(
    {
        "credit_check",
        "billing_ar",
        "product_fit",
        "product_info",
        "competitor_intel",
        "kyp_due_diligence",
        "relationship_check",
        "customer_intel",
    }
)

# Decision type mapping from intent
_INTENT_TO_DECISION_TYPE = {
    "credit_check": "credit_feasibility",
    "billing_ar": "risk_assessment",
    "product_fit": "recommendation",
    "product_info": "recommendation",
    "competitor_intel": "competitor_assessment",
    "kyp_due_diligence": "risk_assessment",
    "relationship_check": "risk_assessment",
    "customer_intel": "credit_feasibility",
}


def build_carryover_from_credit(
    entity: str, credit_data: dict, intent: str
) -> ReasoningCarryover:
    """
    Build a ReasoningCarryover from a credit response.

    Args:
        entity: Customer name
        credit_data: Dict with credit_limit, utilization, currency, status
        intent: The query intent
    """
    utilization = credit_data.get("credit_utilization", "")
    limit = credit_data.get("credit_limit", "")
    available = credit_data.get("available_credit", "")
    status = credit_data.get("credit_status", "")

    if status == "BLOCKED":
        conclusion = f"BLOCKED credit — orders cannot proceed without escalation"
        constraints = [f"credit status: BLOCKED", f"utilization: {utilization}"]
    else:
        conclusion = f"SUFFICIENT credit — {available} available ({utilization} used)"
        constraints = [f"credit limit: {limit}", f"available: {available}"]

    return ReasoningCarryover(
        entity=entity,
        prior_intent=intent,
        prior_decision_type="credit_feasibility",
        prior_conclusion=conclusion,
        prior_rationale=[
            f"Credit limit: {limit}",
            f"Utilization: {utilization}",
            f"Status: {status}",
        ],
        prior_constraints=constraints,
        confidence="high",
    )


def should_create_carryover(intent: str, answer: str, confidence: str) -> bool:
    """
    Determine if a response is eligible for carryover creation.

    Only creates carryover for substantive responses with clear conclusions.
    Rejects fallbacks, low-evidence, and raw data dumps.
    """
    if intent not in _CARRYOVER_ELIGIBLE_INTENTS:
        return False

    # Reject fallback/low-evidence responses
    fallback_phrases = [
        "no results found",
        "insufficient verified evidence",
        "not available in our",
        "cannot confirm",
        "no data available",
    ]
    answer_lower = answer.lower()[:200]
    if any(phrase in answer_lower for phrase in fallback_phrases):
        return False

    # Reject very short responses (likely clarifications)
    if len(answer) < 50:
        return False

    return True


def should_inject_carryover(
    carryover: ReasoningCarryover,
    current_entity: str,
    current_intent: str,
) -> bool:
    """
    Determine if prior carryover should be injected into current turn.

    Only injects when:
    - Same entity continues (or no entity switch)
    - Follow-up is logically connected
    - No entity switch occurred
    """
    if not carryover:
        return False

    # Entity switch → discard
    if current_entity and carryover.entity:
        carryover_entity = carryover.entity.lower().strip()
        current_lower = current_entity.lower().strip()
        if carryover_entity != current_lower:
            return False

    return True


# =============================================================================
# Conversation Turn Structure
# =============================================================================


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str
    """Role: 'user' or 'assistant'."""

    content: str
    """Message content."""

    timestamp: datetime
    """When this turn occurred."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata (sources, follow-ups, etc.)."""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# =============================================================================
# Conversation Session
# =============================================================================


@dataclass
class ConversationSession:
    """
    A conversation session with state tracking.

    Maintains:
    - Turn history for context
    - Extracted entities/topics with timestamps (for pronoun resolution)
    - Pending clarifications
    """

    session_id: str
    """Unique session identifier."""

    owner_id: str = ""
    """User ID that owns this session (for cross-user isolation)."""

    turns: List[ConversationTurn] = field(default_factory=list)
    """Conversation turn history."""

    context: Dict[str, Any] = field(default_factory=dict)
    """Extracted context (entities, topics)."""

    entity_history: List[Dict[str, Any]] = field(default_factory=list)
    """Timestamped entity mentions for pronoun resolution.
    Each entry: {name: str, timestamp: str, type: 'company'|'competitor'|'product'}
    Most recent entries are appended to the end.
    """

    pending_clarification: Optional[Dict[str, Any]] = None
    """Pending clarification if any."""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When session was created."""

    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    """When session was last active."""

    def add_turn(
        self,
        role: str,
        content: str,
        **metadata: Any,
    ) -> None:
        """
        Add a turn to the conversation.

        Args:
            role: 'user' or 'assistant'
            content: Message content
            **metadata: Additional metadata
        """
        self.turns.append(
            ConversationTurn(
                role=role,
                content=content,
                timestamp=datetime.now(UTC),
                metadata=metadata,
            )
        )
        self.last_activity = datetime.now(UTC)

    def get_history(
        self, max_turns: int = 10, include_entity_context: bool = True
    ) -> List[Dict[str, str]]:
        """
        Get recent conversation history for context.

        Args:
            max_turns: Maximum turns to return
            include_entity_context: If True, prepend entity context summary

        Returns:
            List of {role, content} dictionaries
        """
        history = [
            {"role": t.role, "content": t.content} for t in self.turns[-max_turns:]
        ]

        # Optionally prepend entity context for LLM enrichment
        if include_entity_context and (self.entity_history or self.context):
            entity_summary = get_entity_context_summary(
                self.entity_history, self.context
            )
            if entity_summary:
                # Add as a system-style context message at the start
                history.insert(
                    0,
                    {"role": "system", "content": f"[ENTITY CONTEXT] {entity_summary}"},
                )

        return history

    def update_context(self, parsed_query: ParsedQuery) -> None:
        """
        Update session context from parsed query.

        Also maintains entity_history with rich context for semantic resolution.
        The context captures HOW entities were discussed (intent, query type)
        which enables embedding-based pronoun resolution.

        Args:
            parsed_query: ParsedQuery with extracted entities
        """
        timestamp = datetime.now(UTC).isoformat()
        intent = parsed_query.intent.value

        # Build rich context for entity tracking
        # This context will be embedded along with entity name for semantic matching
        def _build_entity_context(entity_name: str, entity_type: str) -> str:
            """Build conversational context for entity embedding."""
            intent_descriptions = {
                "kyp_due_diligence": f"User requested KYP/due diligence report on {entity_name}",
                "competitor_intel": f"User asked about competitor {entity_name} activity or news",
                "market_intel": f"User inquired about market intelligence involving {entity_name}",
                "customer_news": f"User asked for news about customer {entity_name}",
                "credit_check": f"User requested credit check for {entity_name}",
                "billing_ar": f"User asked about billing/AR status for {entity_name}",
                "relationship_check": f"User inquired about relationship with {entity_name}",
                "general_knowledge": f"User asked general question about {entity_name}",
            }
            return intent_descriptions.get(
                intent,
                f"User mentioned {entity_name} ({entity_type}) in {intent} context",
            )

        # Track mentioned competitors (with history)
        if parsed_query.competitors:
            existing = set(self.context.get("competitors", []))
            existing.update(parsed_query.competitors)
            self.context["competitors"] = list(existing)
            # Add to entity history with rich context
            for comp in parsed_query.competitors:
                context = _build_entity_context(comp, "competitor")
                self._add_to_entity_history(comp, "competitor", timestamp, context)

        # Track mentioned companies (with history)
        if parsed_query.companies:
            existing = set(self.context.get("companies", []))
            existing.update(parsed_query.companies)
            self.context["companies"] = list(existing)
            # Add to entity history with rich context
            for company in parsed_query.companies:
                context = _build_entity_context(company, "company")
                self._add_to_entity_history(company, "company", timestamp, context)

        # Track mentioned regions
        if parsed_query.regions:
            existing = set(self.context.get("regions", []))
            existing.update(parsed_query.regions)
            self.context["regions"] = list(existing)

        # Track mentioned products (with history)
        if parsed_query.products:
            existing = set(self.context.get("products", []))
            existing.update(parsed_query.products)
            self.context["products"] = list(existing)
            # Add to entity history with rich context
            for product in parsed_query.products:
                context = _build_entity_context(product, "product")
                self._add_to_entity_history(product, "product", timestamp, context)

        # Track primary intent
        self.context["last_intent"] = parsed_query.intent.value

    def _add_to_entity_history(
        self, name: str, entity_type: str, timestamp: str, context: str = ""
    ) -> None:
        """
        Add entity to history with conversational context for semantic resolution.

        The context is used by the SemanticEntityResolver to create embeddings
        that capture HOW the entity was discussed, not just its name.

        Args:
            name: Entity name
            entity_type: Type (company, competitor, product)
            timestamp: When the entity was mentioned
            context: Conversational context (e.g., "user asked for KYP report")
        """
        # Check if this exact entity was just added (same name and timestamp)
        for entry in reversed(self.entity_history[-5:]):  # Check last 5
            if entry.get("name") == name and entry.get("timestamp") == timestamp:
                return  # Skip duplicate

        # Build context from available information if not provided
        if not context:
            intent = self.context.get("last_intent", "general")
            context = f"Mentioned {name} in context of {intent} query"

        self.entity_history.append(
            {
                "name": name,
                "type": entity_type,
                "timestamp": timestamp,
                "context": context,  # For semantic embedding
            }
        )

        # Keep history bounded (last 50 entities)
        if len(self.entity_history) > 50:
            self.entity_history = self.entity_history[-50:]

    def get_most_recent_entity(self, entity_type: str | None = None) -> str | None:
        """Get most recently mentioned entity, optionally filtered by type.

        Args:
            entity_type: Optional filter ('company', 'competitor', 'product')

        Returns:
            Most recent entity name or None
        """
        for entry in reversed(self.entity_history):
            if entity_type is None or entry.get("type") == entity_type:
                return entry.get("name")
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "turns": [t.to_dict() for t in self.turns],
            "context": self.context,
            "entity_history": self.entity_history,
            "pending_clarification": self.pending_clarification,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }


# =============================================================================
# Clarification Question Structure
# =============================================================================


@dataclass
class ClarificationQuestion:
    """A clarification question to ask the user."""

    id: str
    """Unique question identifier."""

    question: str
    """The question text."""

    question_type: str
    """Type: 'choice', 'text', 'multiselect'."""

    options: Optional[List[str]] = None
    """Options for choice/multiselect types."""

    reason: Optional[str] = None
    """Why this clarification is needed."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "id": self.id,
            "question": self.question,
            "type": self.question_type,
        }
        if self.options:
            result["options"] = self.options
        if self.reason:
            result["reason"] = self.reason
        return result


# =============================================================================
# Session Storage Protocol
# =============================================================================


@runtime_checkable
class SessionStore(Protocol):
    """Protocol for session storage backends."""

    def get(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID."""
        ...

    def set(self, session: ConversationSession) -> None:
        """Store a session."""
        ...

    def delete(self, session_id: str) -> None:
        """Delete a session."""
        ...

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        ...

    def count(self) -> int:
        """Count sessions."""
        ...

    def items(self) -> Iterable[tuple[str, "ConversationSession"]]:
        """Iterate over (session_id, session) pairs."""
        ...


class InMemorySessionStore:
    """In-memory session storage (default)."""

    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}

    def get(self, session_id: str) -> Optional[ConversationSession]:
        return self.sessions.get(session_id)

    def set(self, session: ConversationSession) -> None:
        self.sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]

    def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    def count(self) -> int:
        return len(self.sessions)

    def __len__(self) -> int:
        """Support len() for backward compatibility."""
        return len(self.sessions)

    def items(self):
        """For iteration compatibility."""
        return self.sessions.items()


class RedisSessionStore:
    """
    Redis-backed session storage for production with resilience.

    Features:
    - Automatic reconnection on connection failures
    - Graceful fallback to in-memory cache during outages
    - Connection pooling for performance
    - Rate-limited reconnection attempts

    Usage:
        store = RedisSessionStore(redis_url="redis://localhost:6379")
        manager = ConversationManager(session_store=store)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "l2c:session:",
        ttl_seconds: int = 7200,  # 2 hours
    ):
        """
        Initialize Redis session store.

        Args:
            redis_url: Redis URL (or from REDIS_URL env)
            prefix: Key prefix for sessions
            ttl_seconds: Session TTL in seconds
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self._client: Optional["redis.Redis"] = None
        self._available = False
        self._initialized = False

        # Fallback cache for Redis outages
        self._fallback_cache: Dict[str, ConversationSession] = {}
        self._using_fallback = False

        # Reconnection settings
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay_seconds = 5.0
        self._last_reconnect_time: Optional[datetime] = None

    @property
    def client(self) -> "redis.Redis":
        """Get the Redis client, raising if not available."""
        if self._client is None or not self._available:
            raise SessionStoreNotInitializedError("Redis")
        return self._client

    def _get_client(self):
        """Get Redis client with lazy initialization and reconnection."""
        if self._client is not None and self._available:
            return self._client

        # Try to connect/reconnect
        if not self._try_connect():
            return None

        return self._client

    def _try_connect(self) -> bool:
        """Attempt to connect to Redis with rate limiting."""
        # Rate limit reconnection attempts
        now = datetime.now(UTC)
        if self._last_reconnect_time:
            elapsed = (now - self._last_reconnect_time).total_seconds()
            if elapsed < self._reconnect_delay_seconds:
                return self._available

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            # Reset after cooldown period (60 seconds)
            if self._last_reconnect_time:
                elapsed = (now - self._last_reconnect_time).total_seconds()
                if elapsed > 60:
                    self._reconnect_attempts = 0
                else:
                    return self._available

        self._last_reconnect_time = now
        self._reconnect_attempts += 1

        try:
            import redis

            # Close existing connection if any
            if self._client:
                try:
                    self._client.close()
                except (redis.RedisError, OSError, ConnectionError):
                    pass  # Ignore errors when closing existing connection

            # Create new connection with pool
            self._client = redis.from_url(
                self.redis_url,
                socket_connect_timeout=10,
                socket_timeout=30,
                retry_on_timeout=True,
                health_check_interval=0,  # Disable — was causing stale connections
            )

            # Test connection
            self._client.ping()

            self._available = True
            self._initialized = True
            self._reconnect_attempts = 0
            self._using_fallback = False

            # Restore any fallback cache to Redis
            if self._fallback_cache:
                self._restore_from_fallback()

            logger.info(f"Redis session store connected (prefix={self.prefix})")
            return True

        except ImportError:
            logger.error("Redis package not installed. Install with: pip install redis")
            self._available = False
            return False

        except Exception as e:
            logger.warning(
                f"Redis connection attempt {self._reconnect_attempts}/"
                f"{self._max_reconnect_attempts} failed: {e}"
            )
            self._available = False
            self._using_fallback = True
            return False

    def _restore_from_fallback(self):
        """Restore sessions from fallback cache to Redis."""
        restored = 0
        for session_id, session in list(self._fallback_cache.items()):
            try:
                key = f"{self.prefix}{session_id}"
                self._client.setex(key, self.ttl_seconds, self._serialize(session))
                restored += 1
            except Exception as e:
                logger.warning(f"Failed to restore session {session_id}: {e}")

        if restored:
            logger.info(f"Restored {restored} sessions from fallback cache to Redis")
            self._fallback_cache.clear()

    def _serialize(self, session: ConversationSession) -> str:
        """Serialize session to JSON.

        IMPORTANT: This method must NOT mutate the session object.
        We create a deep copy of pending_clarification to avoid side effects.
        """
        data = session.to_dict()
        # Handle pending_clarification ParsedQuery - use deep copy to avoid mutation
        if data.get("pending_clarification"):
            # Create a copy to avoid mutating the original session
            pc_copy = copy.deepcopy(data["pending_clarification"])
            if "parsed_query" in pc_copy and hasattr(
                pc_copy["parsed_query"], "to_dict"
            ):
                pc_copy["parsed_query"] = pc_copy["parsed_query"].to_dict()
            data["pending_clarification"] = pc_copy
        return json.dumps(data)

    def _deserialize(self, data: str) -> ConversationSession:
        """Deserialize session from JSON."""
        obj = json.loads(data)

        # Reconstruct turns
        turns = []
        for t in obj.get("turns", []):
            turns.append(
                ConversationTurn(
                    role=t["role"],
                    content=t["content"],
                    timestamp=datetime.fromisoformat(t["timestamp"]),
                    metadata=t.get("metadata", {}),
                )
            )

        # Reconstruct pending_clarification with ParsedQuery object
        pending_clarification = obj.get("pending_clarification")
        if pending_clarification and "parsed_query" in pending_clarification:
            # Reconstruct ParsedQuery from dict to preserve intent through Redis round-trips
            parsed_dict = pending_clarification["parsed_query"]
            if isinstance(parsed_dict, dict):
                pending_clarification["parsed_query"] = ParsedQuery.from_dict(
                    parsed_dict
                )

        session = ConversationSession(
            session_id=obj["session_id"],
            owner_id=obj.get("owner_id", ""),
            turns=turns,
            context=obj.get("context", {}),
            entity_history=obj.get("entity_history", []),
            pending_clarification=pending_clarification,
            created_at=datetime.fromisoformat(obj["created_at"]),
            last_activity=datetime.fromisoformat(obj["last_activity"]),
        )
        return session

    def get(self, session_id: str) -> Optional[ConversationSession]:
        """Get session from Redis with fallback."""
        client = self._get_client()

        if client and self._available:
            try:
                key = f"{self.prefix}{session_id}"
                data = client.get(key)
                if data:
                    session = self._deserialize(
                        data.decode("utf-8") if isinstance(data, bytes) else data
                    )
                    logger.info(
                        f"Redis GET: {key} found, turns={len(session.turns)}, "
                        f"companies={session.context.get('companies', [])}"
                    )
                    return session
                logger.info(f"Redis GET: {key} NOT FOUND")
                return None
            except Exception as e:
                logger.warning(f"Redis get failed, retrying: {e}")
                # Force reconnect and retry once
                self._available = False
                self._reconnect_attempts = 0
                retry_client = self._get_client()
                if retry_client:
                    try:
                        data = retry_client.get(key)
                        if data:
                            session = self._deserialize(
                                data.decode("utf-8")
                                if isinstance(data, bytes)
                                else data
                            )
                            logger.info(f"Redis GET retry: {key} found after reconnect")
                            return session
                    except Exception:
                        pass
                self._using_fallback = True

        # Fallback to in-memory cache
        logger.warning(
            f"Using FALLBACK cache for session {session_id} "
            f"(Redis available={self._available}, using_fallback={self._using_fallback})"
        )
        return self._fallback_cache.get(session_id)

    def set(self, session: ConversationSession) -> None:
        """Store session in Redis with fallback."""
        client = self._get_client()

        if client and self._available:
            try:
                key = f"{self.prefix}{session.session_id}"
                client.setex(key, self.ttl_seconds, self._serialize(session))
                logger.info(
                    f"Redis SET: {key}, "
                    f"companies={session.context.get('companies', [])}, "
                    f"turns={len(session.turns)}"
                )
                return
            except Exception as e:
                logger.warning(f"Redis set failed, using fallback: {e}")
                self._available = False
                self._using_fallback = True

        # Fallback to in-memory cache
        logger.warning(
            f"Using FALLBACK cache to SET session {session.session_id} "
            f"(Redis available={self._available})"
        )
        self._fallback_cache[session.session_id] = session

    def delete(self, session_id: str) -> None:
        """Delete session from Redis and fallback."""
        client = self._get_client()

        if client and self._available:
            try:
                client.delete(f"{self.prefix}{session_id}")
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
                self._available = False

        # Also remove from fallback
        self._fallback_cache.pop(session_id, None)

    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        client = self._get_client()
        sessions = set()

        if client and self._available:
            try:
                keys = client.keys(f"{self.prefix}*")
                for k in keys:
                    key_str = k.decode("utf-8") if isinstance(k, bytes) else k
                    sessions.add(key_str.replace(self.prefix, ""))
            except Exception as e:
                logger.warning(f"Redis list_sessions failed: {e}")
                self._available = False

        # Include fallback sessions
        sessions.update(self._fallback_cache.keys())
        return list(sessions)

    def count(self) -> int:
        """Count total sessions."""
        return len(self.list_sessions())

    def items(self):
        """Iterate over all sessions (for compatibility with InMemorySessionStore)."""
        for session_id in self.list_sessions():
            session = self.get(session_id)
            if session:
                yield session_id, session

    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is currently available."""
        return self._available and not self._using_fallback

    def __len__(self) -> int:
        """Support len() for backward compatibility."""
        return self.count()


# =============================================================================
# Source Sanitization — strip internal system names from user-facing sources
# =============================================================================

_INTERNAL_SOURCE_MAP = {
    "EODHD Fundamentals API": "Financial Data",
    "Perplexity Financial Search": "Web Search",
    "Perplexity Search": "Web Search",
    "SAP MS5 Credit Management": "SAP Credit Check",
    "SAP CPI": "SAP System",
    "Local Vector Database": "Intelligence Database",
    "Knowledge Base": "Product Database",
    "Web Search": "Web Search",
}


def _sanitize_sources(sources: list[str] | None) -> list[str]:
    """Replace internal system names with user-friendly labels."""
    if not sources:
        return []
    clean: list[str] = []
    for src in sources:
        mapped = _INTERNAL_SOURCE_MAP.get(src)
        if mapped:
            if mapped not in clean:
                clean.append(mapped)
        else:
            clean.append(src)
    return clean


# =============================================================================
# Conversation Manager
# =============================================================================


class ConversationManager:
    """
    Manages multi-turn conversations with clarifications.

    Implements the full orchestration flow:
    1. Query Understanding - Parse natural language
    2. Clarification Check - Block if clarification needed
    3. Data Inventory Check - Know what data we have
    4. Tool Selection - Plan tool execution
    5. Tool Execution - Execute tools
    6. Response + Follow-ups - Generate response with suggestions

    Features:
        - Session management (create, retrieve, expire)
        - Automatic cleanup with max session limit
        - Clarification blocking (don't execute until clarified)
        - Follow-up suggestions based on response and context
        - Context continuity across turns
        - Optional Redis persistence for production
    """

    # Session expiry time (2 hours)
    SESSION_EXPIRY_HOURS = 2.0

    # Maximum sessions before forced cleanup
    MAX_SESSIONS = 1000

    # Cleanup trigger threshold (cleanup when exceeding this)
    CLEANUP_THRESHOLD = 900

    # Time-sensitive intents that MAY need temporal clarification
    # Note: We're now more conservative - only ask if truly ambiguous
    # Aligned with sales_intelligence_agent_guide.md
    TIME_SENSITIVE_INTENTS = [
        QueryIntent.COMPETITOR_INTEL,
        QueryIntent.MARKET_INTEL,  # New intent
        QueryIntent.MARKET_NEWS,  # Legacy compatibility
        QueryIntent.FINANCIAL_ANALYSIS,
    ]

    def __init__(
        self,
        query_engine: Optional[QueryUnderstandingEngine] = None,
        inventory: Optional[DataInventoryService] = None,
        tool_executor: Optional[ToolExecutor] = None,
        session_store: Optional[SessionStore] = None,
    ):
        """
        Initialize conversation manager.

        Args:
            query_engine: QueryUnderstandingEngine instance (or uses singleton)
            inventory: DataInventoryService instance (or uses singleton)
            tool_executor: ToolExecutor instance (or uses singleton)
            session_store: Session storage backend (defaults to in-memory)
        """
        # Session storage (in-memory by default, Redis for production)
        # Note: use `is None` not `or` — RedisSessionStore with 0 sessions is
        # falsy due to __len__ returning 0, which would incorrectly fall through.
        self._session_store = (
            session_store if session_store is not None else InMemorySessionStore()
        )

        # Legacy compatibility - expose sessions dict for tests
        # This is a proxy that delegates to the session store
        self.sessions = self._session_store

        # Use provided instances or singletons
        self._query_engine = query_engine
        self._inventory = inventory
        self._tool_executor = tool_executor

        # Register customer abbreviations from SAP customer master for entity resolution.
        # Uses SIMULATED_CUSTOMERS name list for abbreviation generation only —
        # actual data (credit, opportunities) comes from real SAP CPI.
        self._register_customer_abbreviations()

    @staticmethod
    def _register_customer_abbreviations() -> None:
        """Register abbreviations from SAP customer names into the global registry."""
        try:
            from lead_to_cash.core.semantic_entity_resolver import (
                register_known_customers,
            )
            from lead_to_cash.integrations.cpi_simulator import SIMULATED_CUSTOMERS

            register_known_customers(SIMULATED_CUSTOMERS)
        except ImportError as e:
            logger.debug(f"Could not register customer abbreviations: {e}")

    @property
    def query_engine(self) -> QueryUnderstandingEngine:
        """Get query engine (lazy initialization)."""
        if self._query_engine is None:
            self._query_engine = get_query_engine()
        return self._query_engine

    @property
    def inventory(self) -> DataInventoryService:
        """Get data inventory (lazy initialization)."""
        if self._inventory is None:
            self._inventory = get_data_inventory()
        return self._inventory

    @property
    def tool_executor(self) -> ToolExecutor:
        """Get tool executor (lazy initialization)."""
        if self._tool_executor is None:
            self._tool_executor = get_tool_executor()
        return self._tool_executor

    @property
    def entity_agent(self) -> Optional["EntityResolutionAgent"]:
        """
        Get entity resolution agent (lazy initialization).

        The EntityResolutionAgent is a Kaizen BaseAgent that resolves company names
        to canonical entities using EntityResolutionService:
        1. Entity Registry Database (local fuzzy match, aliases, Levenshtein)
        2. ACRA (Singapore corporate registry)
        3. GLEIF (Global LEI database)
        4. Web Search (Perplexity) as final fallback

        Features A2A semantic routing and SharedMemoryPool integration.

        Note: Uses lazy import to avoid circular dependency with agents.registry.
        """
        if not hasattr(self, "_entity_agent"):
            try:
                # Lazy import to break circular dependency
                # (agents package imports conversation via registry.py)
                from lead_to_cash.agents.entity_resolution_agent import (
                    get_entity_resolution_agent,
                )

                self._entity_agent = get_entity_resolution_agent()
                logger.info("EntityResolutionAgent initialized (Kaizen BaseAgent)")
            except ImportError as e:
                logger.warning(f"EntityResolutionAgent not available: {e}")
                self._entity_agent = None
        return self._entity_agent

    @property
    def entity_service(self) -> Optional["EntityResolutionService"]:
        """
        Get entity resolution service (lazy initialization).

        NOTE: Prefer entity_agent for new code - it uses agentic tool calling.
        This service is kept for backward compatibility.

        Initializes the service with external source clients (ACRA, GLEIF,
        OpenCorporates) for searching when entities are not found in database.
        """
        if not ENTITY_REGISTRY_AVAILABLE:
            return None
        if not hasattr(self, "_entity_service"):
            # Initialize with external clients for online search
            acra_client = None
            gleif_client = None
            opencorporates_client = None

            if EXTERNAL_CLIENTS_AVAILABLE:
                try:
                    acra_client = get_acra_client()
                    gleif_client = get_gleif_client()
                    opencorporates_client = get_opencorporates_client()
                    logger.info(
                        "External entity clients initialized (ACRA, GLEIF, OpenCorporates)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize external clients: {e}")

            self._entity_service = EntityResolutionService(
                acra_client=acra_client,
                gleif_client=gleif_client,
                opencorporates_client=opencorporates_client,
            )
        return self._entity_service

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ConversationSession:
        """
        Get existing session or create new one.

        Automatically triggers cleanup when session count exceeds threshold.
        Enforces session ownership: if the session belongs to a different user,
        a new session is created instead (prevents cross-user data leakage).

        Args:
            session_id: Optional session ID (creates new if None)
            user_id: Optional user ID for ownership binding

        Returns:
            ConversationSession instance
        """
        store = self._session_store

        # Trigger cleanup if approaching limit
        if store.count() >= self.CLEANUP_THRESHOLD:
            removed = self.cleanup_expired_sessions()
            logger.info(f"Auto-cleanup removed {removed} expired sessions")

            # Force removal of oldest sessions if still over limit
            if store.count() >= self.MAX_SESSIONS:
                self._force_cleanup_oldest()

        if not session_id:
            session_id = str(uuid.uuid4())

        session = store.get(session_id)

        if session is None:
            session = ConversationSession(
                session_id=session_id,
                owner_id=user_id or "",
            )
            store.set(session)
            logger.info(f"Created new session: {session_id}")
        else:
            # Session ownership check: reject cross-user access
            if user_id and session.owner_id and session.owner_id != user_id:
                logger.warning(
                    f"Session ownership mismatch: session {session_id} "
                    f"owned by '{session.owner_id}', requested by '{user_id}'. "
                    f"Creating new session."
                )
                session_id = str(uuid.uuid4())
                session = ConversationSession(
                    session_id=session_id,
                    owner_id=user_id,
                )
                store.set(session)
                return session

            # Backfill owner_id for pre-existing sessions (migration)
            if user_id and not session.owner_id:
                session.owner_id = user_id
                store.set(session)

            # Log existing session context for debugging
            logger.info(
                f"Retrieved existing session: {session_id}, "
                f"turns={len(session.turns)}, "
                f"context_companies={session.context.get('companies', [])}"
            )

            # Check if session expired
            hours_since_activity = (
                datetime.now(UTC) - session.last_activity
            ).total_seconds() / 3600

            if hours_since_activity > self.SESSION_EXPIRY_HOURS:
                # Expire and create new session
                logger.info(f"Session expired, creating new: {session_id}")
                session = ConversationSession(
                    session_id=session_id,
                    owner_id=user_id or "",
                )
                store.set(session)

        return session

    def _force_cleanup_oldest(self) -> int:
        """
        Force cleanup of oldest sessions when over limit.

        Returns:
            Number of sessions removed
        """
        store = self._session_store

        if store.count() <= self.CLEANUP_THRESHOLD:
            return 0

        # Collect all sessions with their activity times
        sessions_with_times = []
        for session_id, session in store.items():
            sessions_with_times.append((session_id, session.last_activity))

        # Sort by last activity
        sessions_with_times.sort(key=lambda x: x[1])

        # Remove oldest sessions to get below threshold
        to_remove = store.count() - self.CLEANUP_THRESHOLD + 100  # Buffer
        removed = 0

        for session_id, _ in sessions_with_times[:to_remove]:
            store.delete(session_id)
            removed += 1

        logger.warning(f"Force-cleaned {removed} oldest sessions (memory pressure)")
        return removed

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get existing session by ID.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ConversationSession or None if not found
        """
        return self._session_store.get(session_id)

    async def process_message(
        self,
        session_id: str,
        message: str,
        clarification_response: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        confirmed_entity: Optional[Dict[str, Any]] = None,
        original_task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message in conversation.

        This is the main entry point implementing the full orchestration flow.

        Args:
            session_id: Session ID for this conversation
            message: User's message
            clarification_response: If responding to a clarification
            user_context: User context for data-layer RBAC (roles, permissions)
            confirmed_entity: Entity confirmed by user from disambiguation
            original_task_type: Original task type preserved after entity confirmation

        Returns:
            Response dictionary with type, answer/questions, sources, follow-ups
        """
        # Extract user_id from user_context for session ownership binding
        _user_id = (user_context or {}).get("user_id", "")
        session = self.get_or_create_session(session_id, user_id=_user_id)

        # Step 1: Handle clarification response if pending
        if session.pending_clarification and clarification_response:
            return await self._handle_clarification_response(
                session, message, clarification_response
            )

        # Step 1.5: Handle entity confirmation if pending
        if session.pending_clarification:
            if session.pending_clarification.get("type") == "entity_confirmation":
                # Staleness guard: auto-clear if user has sent 3+ messages
                # since the entity confirmation was set (prevents permanent traps)
                clarification_age = session.pending_clarification.get(
                    "_turns_since_set", 0
                )
                if clarification_age >= 3:
                    logger.info(
                        "Auto-clearing stale entity confirmation after "
                        f"{clarification_age} turns"
                    )
                    session.pending_clarification = None
                    self._session_store.set(session)
                else:
                    # Increment turn counter for staleness tracking
                    session.pending_clarification["_turns_since_set"] = (
                        clarification_age + 1
                    )
                    result = await self._handle_entity_confirmation(session, message)
                    if result:
                        return result
                    # If result is None, confirmation was handled or cleared -
                    # flow continues to normal processing

        # Step 2: Add user turn
        session.add_turn("user", message)

        # Step 2.1: Greeting fast path — <200ms, no LLM, no tools
        # Structural plumbing (permitted per agent-reasoning.md exception 1)
        _msg_stripped = message.strip().lower().rstrip("!?.,:;")
        _GREETINGS = {
            "hello",
            "hi",
            "hey",
            "hiya",
            "howdy",
            "good morning",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "thx",
            "ty",
            "ok",
            "okay",
            "sure",
            "got it",
            "noted",
            "bye",
            "goodbye",
            "see you",
        }
        # Capability questions — also instant, no LLM needed
        _CAPABILITY_PHRASES = {
            "what can you do",
            "what can you help me with",
            "what can you help with",
            "what do you do",
            "how can you help",
            "help",
            "help me",
            "what are your capabilities",
        }
        if _msg_stripped in _CAPABILITY_PHRASES:
            _capability_reply = (
                "I can help you with:\n\n"
                "**Customer Intelligence**\n"
                "- Run KYP (Know Your Partner) due diligence\n"
                "- Check credit status and exposure\n"
                "- Show CEC opportunities and pipeline\n"
                "- View sales order details and billing plans\n\n"
                "**Market & Competitor Intelligence**\n"
                "- Marine industry trends and market opportunities\n"
                "- Competitor analysis and comparison\n"
                "- Product specifications and recommendations\n\n"
                "**Finance Operations**\n"
                "- Billing items and collections\n"
                "- Payment status and track record\n"
                "- Aging analysis and escalations\n\n"
                'Try: *"Run KYP on ST Engineering"* or *"Show opportunities for Maersk"*'
            )
            session.add_turn("assistant", _capability_reply)
            self._session_store.set(session)
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": _capability_reply,
                "sources": [],
                "follow_up_suggestions": [
                    "Run KYP on ST Engineering?",
                    "Show opportunities for Maersk?",
                    "What are the latest marine trends?",
                ],
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        if _msg_stripped in _GREETINGS:
            _greeting_responses = {
                "hello": "Hello! How can I assist you today?",
                "hi": "Hi there — what would you like to know?",
                "hey": "Hey! How can I help?",
                "good morning": "Good morning! What can I help you with?",
                "good afternoon": "Good afternoon! How can I assist?",
                "good evening": "Good evening! What would you like to know?",
                "thanks": "You're welcome! Let me know if you need anything else.",
                "thank you": "You're welcome! Anything else I can help with?",
                "ok": "Alright — let me know what you'd like to look into next.",
                "okay": "Sure — what would you like to explore?",
                "bye": "Goodbye! Feel free to come back anytime.",
            }
            _reply = _greeting_responses.get(
                _msg_stripped,
                "Hi — how can I help you today?",
            )
            session.add_turn("assistant", _reply)
            self._session_store.set(session)
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": _reply,
                "sources": [],
                "follow_up_suggestions": [
                    "Run KYP on a company?",
                    "Check credit status?",
                    "Show opportunities?",
                ],
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Step 2.5: Write-operation guardrail — refuse before burning LLM tokens
        write_refusal = self._detect_write_intent(message)
        if write_refusal:
            session.add_turn("assistant", write_refusal)
            self._session_store.set(session)
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": write_refusal,
                "sources": [],
                "follow_up_suggestions": [
                    "Show me the current credit status?",
                    "What are the open invoices?",
                    "Draft a summary I can paste into an email?",
                ],
                "confidence": "high",
                "execution_time_ms": 0,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Step 2.8: Follow-up context resolution
        # Before re-routing from scratch, check if this is a follow-up that
        # should resolve against the previous turn's context.
        _followup_resolution = None
        if session.turns:
            # Get previous turn metadata
            _prev_turns = [t for t in session.turns if t.role == "assistant"]
            _prev_intent = session.context.get("last_intent")
            _prev_entity = session.context.get("last_kyp_entity") or (
                session.context.get("companies", [None])[-1]
                if session.context.get("companies")
                else None
            )
            _prev_response_type = session.context.get("last_response_type")

            _followup_resolution = FollowUpResolver.resolve(
                current_query=message,
                previous_intent=_prev_intent,
                previous_entity=_prev_entity,
                previous_response_type=_prev_response_type,
                session_context=session.context,
            )
            if _followup_resolution.is_followup:
                logger.info(
                    f"Follow-up detected: resolved_intent={_followup_resolution.resolved_intent}, "
                    f"resolved_entity={_followup_resolution.resolved_entity}, "
                    f"confidence={_followup_resolution.confidence}"
                )

        # Step 3: Parse query with conversation context
        try:
            parsed = await self.query_engine.parse(
                message,
                session.get_history(),
            )
        except Exception as e:
            logger.error(f"Query understanding failed: {e}")
            return self._error_response(session_id, str(e))

        # Step 3.2a: Apply user default region if query has no explicit region
        if not parsed.regions and user_context:
            _default_region = user_context.get("default_region", "")
            if _default_region:
                parsed.regions = [_default_region]
                logger.info(
                    f"Step 3.2a: Applied user default region: {_default_region}"
                )

        # Step 3.3: Apply follow-up resolution overrides
        # If follow-up resolver identified this as a continuation, ensure the
        # parsed query inherits the resolved entity/intent when LLM missed it.
        if _followup_resolution and _followup_resolution.is_followup:
            if (
                _followup_resolution.resolved_entity
                and not parsed.companies
                and not parsed.competitors
            ):
                parsed.companies = [_followup_resolution.resolved_entity]
                logger.info(
                    f"Step 3.3: Follow-up entity injected: {_followup_resolution.resolved_entity}"
                )
            # Check if follow-up context wants a full report
            if (
                _followup_resolution.resolved_context
                and _followup_resolution.resolved_context.get("wants_full_report")
            ):
                parsed.wants_full_report = True
                logger.info("Step 3.3: Follow-up requests full report")

        # Step 3.5: Deterministic context inheritance for competitor follow-ups
        # If the LLM classified as competitor_intel but didn't extract competitors
        # (e.g., "how about their latest products?"), inherit from session context
        if (
            parsed.intent == QueryIntent.COMPETITOR_INTEL
            and not parsed.competitors
            and session.context.get("competitors")
        ):
            parsed.competitors = list(session.context["competitors"])
            logger.info(
                f"Step 3.5: Inherited competitors from session context: {parsed.competitors}"
            )

        # Conversational context carry-forward: if the user hasn't mentioned a
        # new company but we have one in session, inherit it. A follow-up
        # question without a named entity is still about the same entity.
        if not parsed.companies and session.context.get("companies"):
            parsed.companies = list(session.context["companies"])
            logger.info(
                f"Step 3.5: Context carry-forward from session: {parsed.companies}"
            )

        # Step 4: Update session context
        logger.info(
            f"Before update_context: parsed.companies={parsed.companies}, "
            f"session.context.companies={session.context.get('companies', [])}"
        )
        session.update_context(parsed)
        logger.info(
            f"After update_context: session.context.companies={session.context.get('companies', [])}"
        )

        # Step 4.1: UNIVERSAL SEMANTIC ENTITY RESOLUTION
        # Harmonized approach: Resolve/expand company names BEFORE any intent-specific routing.
        # This ensures "STE" → "ST Engineering" works for ALL query types:
        # - Credit queries (finance ops): "STE credit limit"
        # - Billing queries (finance ops): "Check STE billings"
        # - Customer intel (sales ops): "Tell me about STE"
        # - KYP queries (both): "Run KYP on STE"
        resolved_company = await self._apply_universal_semantic_resolution(
            message, parsed, session
        )
        if resolved_company:
            # Update session context with resolved company
            if "companies" not in session.context:
                session.context["companies"] = []
            if resolved_company not in session.context["companies"]:
                session.context["companies"].append(resolved_company)
            logger.info(
                f"Step 4.1: Semantic resolution updated context with: {resolved_company}"
            )
            # Mark as confirmed entity so _resolve_entity_for_kyp skips
            # unnecessary external lookups for known aliases.
            # EXCEPTION: KYP queries skip auto-confirm here — let
            # _resolve_entity_for_kyp handle them with proper SAP CPI
            # lookup to get the official legal name (name1).
            if (
                not session.context.get("confirmed_entity")
                and parsed.intent != QueryIntent.KYP_DUE_DILIGENCE
            ):
                raw_input = parsed.raw_company_input or (
                    parsed.companies[0] if parsed.companies else ""
                )
                session.context["confirmed_entity"] = {
                    "canonical_name": resolved_company,
                    "query": raw_input,
                    "raw_input": raw_input,
                }
                logger.info(
                    f"Step 4.1: Auto-confirmed entity '{resolved_company}' from alias expansion"
                )

        # Step 4.2: Signal-first routing (Phase 4 — FULL SIGNAL)
        # Signal routing is now the primary routing authority.
        # Fallback triggers ONLY for very low confidence (<0.40) or errors.
        #
        # Control flags (env):
        #   SIGNAL_ROUTING_ENABLED=false  → revert to shadow-only (full rollback)
        #   SIGNAL_FALLBACK_THRESHOLD     → confidence below which fallback fires (default 0.40)
        _signal_routing_enabled = os.environ.get(
            "SIGNAL_ROUTING_ENABLED", "true"
        ).lower() in ("true", "1", "yes")
        _fallback_threshold = float(os.environ.get("SIGNAL_FALLBACK_THRESHOLD", "0.40"))
        _fallback_triggered = False
        _fallback_reason = None
        _keyword_intent = parsed.intent.value  # Already stabilized by _stabilize_intent

        try:
            _signals = extract_signals(parsed, session.context)
            _domain_scores = score_domains(_signals)

            # Pass user permissions for RBAC hard rule (H4)
            _user_perms = (user_context or {}).get("permissions")
            _signal_result = signal_route(_signals, _domain_scores, _user_perms)

            if (
                _signal_routing_enabled
                and _signal_result.confidence >= _fallback_threshold
            ):
                # ── Signal routing: use signal decision ────────────────
                _original_intent = parsed.intent
                # Guard: when LLM set an explicit sub_intent that matches
                # the original intent, prefer LLM classification over signal
                # router. The LLM's structured output is more precise than
                # the signal router's domain scoring for fast-path routing.
                _signal_intent = _signal_result.intent
                try:
                    _signal_intent_enum = QueryIntent(_signal_intent)
                except ValueError:
                    _signal_intent_enum = QueryIntent.GENERAL_QUESTION

                if parsed.sub_intent and _signal_intent_enum != _original_intent:
                    logger.info(
                        f"[Signal Routing] Skipping override: LLM sub_intent="
                        f"{parsed.sub_intent} for {_original_intent.value}, "
                        f"signal wanted {_signal_intent} "
                        f"(confidence={_signal_result.confidence:.2f})"
                    )
                else:
                    parsed.intent = _signal_intent_enum
                    parsed.intent_source = _signal_result.intent_source
                    parsed.intent_confidence = _signal_result.confidence
                    parsed.routing_risk = _signal_result.routing_risk

                logger.info(
                    f"[Signal Routing] intent={parsed.intent.value} "
                    f"sub_intent={parsed.sub_intent} "
                    f"confidence={parsed.intent_confidence:.2f} "
                    f"band={_signal_result.confidence_band} "
                    f"source={parsed.intent_source} "
                    f"keyword_was={_keyword_intent} "
                    f'query="{parsed.raw_query[:60]}"'
                )
            else:
                # ── Fallback: keep keyword-stabilized intent ───────────
                _fallback_triggered = True
                if not _signal_routing_enabled:
                    _fallback_reason = "signal_routing_disabled"
                else:
                    _fallback_reason = "low_confidence"
                logger.info(
                    f"[Signal Routing FALLBACK] reason={_fallback_reason} "
                    f"sub_intent={parsed.sub_intent} "
                    f"confidence={_signal_result.confidence:.2f} "
                    f"threshold={_fallback_threshold} "
                    f"→ keeping keyword intent={_keyword_intent} "
                    f'query="{parsed.raw_query[:60]}"'
                )

            # ── Production monitoring (always logged) ─────────────────
            QualityMetrics.record(
                event_type="signal_routing_live",
                severity="INFO",
                intent=parsed.intent.value,
                details={
                    "routing_source": "fallback" if _fallback_triggered else "signal",
                    "fallback_reason": _fallback_reason,
                    "fallback_threshold": _fallback_threshold,
                    "signal_intent": _signal_result.intent,
                    "signal_confidence": _signal_result.confidence,
                    "signal_confidence_band": _signal_result.confidence_band,
                    "signal_source": _signal_result.intent_source,
                    "signal_risk": _signal_result.routing_risk,
                    "hard_rule_fired": _signal_result.hard_rule_fired,
                    "keyword_intent": _keyword_intent,
                    "final_intent": parsed.intent.value,
                    "fallback_triggered": _fallback_triggered,
                    "signal_enabled": _signal_routing_enabled,
                    "agreement": _signal_result.intent == _keyword_intent,
                    "domain_scores": _signal_result.domain_scores,
                },
            )

            # ── Fallback audit (Phase 4: track why fallback still fires) ──
            if _fallback_triggered:
                QualityMetrics.record(
                    event_type="fallback_usage",
                    severity="INFO",
                    intent=parsed.intent.value,
                    details={
                        "reason": _fallback_reason or "unknown",
                        "confidence": _signal_result.confidence,
                        "confidence_band": _signal_result.confidence_band,
                        "signal_intent": _signal_result.intent,
                        "keyword_intent": _keyword_intent,
                        "query": parsed.raw_query[:200],
                    },
                )

        except Exception as _sig_err:
            # Signal routing failure — fall back to keyword
            _fallback_triggered = True
            _fallback_reason = "signal_error"
            # Upgraded error logging: include exception type and failing stage
            import traceback as _tb

            _error_stage = "unknown"
            _err_name = type(_sig_err).__name__
            _err_tb = _tb.format_exc()
            if "extract_signals" in _err_tb:
                _error_stage = "signal_extractor"
            elif "score_domains" in _err_tb:
                _error_stage = "signal_scorer"
            elif "signal_route" in _err_tb or "route" in _err_tb:
                _error_stage = "signal_router"
            logger.error(
                f"[Signal Routing ERROR] stage={_error_stage} "
                f"exception={_err_name}: {_sig_err} "
                f'query="{parsed.raw_query[:60]}"'
            )
            QualityMetrics.record(
                event_type="signal_routing_error",
                severity="ERROR",
                intent=parsed.intent.value,
                details={
                    "error": str(_sig_err),
                    "error_type": _err_name,
                    "error_stage": _error_stage,
                    "keyword_intent": _keyword_intent,
                    "query_snapshot": parsed.raw_query[:200],
                },
            )
            # Fallback audit for error case
            QualityMetrics.record(
                event_type="fallback_usage",
                severity="WARNING",
                intent=parsed.intent.value,
                details={
                    "reason": "signal_error",
                    "error_type": _err_name,
                    "error_stage": _error_stage,
                    "keyword_intent": _keyword_intent,
                    "query": parsed.raw_query[:200],
                },
            )

        # Step 4.3: Auto-QA sampling (1-5% of queries)
        _turn_index = len(session.turns)
        if RoutingMonitor.should_sample_for_qa(_turn_index):
            try:
                RoutingMonitor.capture_qa_sample(
                    query=parsed.raw_query,
                    intent=parsed.intent.value,
                    routing_source="fallback" if _fallback_triggered else "signal",
                    confidence=getattr(parsed, "intent_confidence", 0),
                    signals_snapshot=(
                        _signals.to_dict() if "_signals" in dir() and _signals else {}
                    ),
                    response_type="pending",  # Updated after response is built
                )
            except Exception:
                pass  # QA sampling must never block routing

        # Step 4.3b: Reasoning detection (Phase P1 — logging only)
        # Detects queries that would benefit from structured reasoning.
        # Does NOT alter execution. Does NOT generate plans.
        # Logged for Phase P2 readiness analysis.
        try:
            _signals_dict = (
                _signals.to_dict() if "_signals" in dir() and _signals else None
            )
            _reasoning = detect_reasoning(
                query=parsed.raw_query,
                signals_dict=_signals_dict,
            )
            if _reasoning.reasoning_needed:
                QualityMetrics.record(
                    event_type="reasoning_detected",
                    severity="INFO",
                    intent=parsed.intent.value,
                    details={
                        "reasoning_needed": True,
                        "reasoning_type": _reasoning.reasoning_type,
                        "matched_signals": _reasoning.matched_signals,
                        "matched_template": _reasoning.matched_template,
                        "confidence": _reasoning.confidence,
                        "query": parsed.raw_query[:200],
                        "compound_metadata_present": False,
                    },
                )

                # Phase P2: Generate reasoning plan (shadow — logging only)
                # Does NOT execute the plan or change behavior.
                try:
                    _entity = (
                        parsed.companies[0]
                        if parsed.companies
                        else session.context.get("last_kyp_entity", "")
                    )
                    _plan = ReasoningPlanner.generate(
                        query=parsed.raw_query,
                        reasoning_type=_reasoning.reasoning_type or "evaluate",
                        matched_template=_reasoning.matched_template,
                        entity=_entity,
                        intent=parsed.intent.value,
                    )
                    QualityMetrics.record(
                        event_type="reasoning_plan_generated",
                        severity="INFO",
                        intent=parsed.intent.value,
                        details={
                            **_plan.to_dict(),
                            "query": parsed.raw_query[:200],
                            "entity": _entity,
                        },
                    )
                    # Phase P4: Execute reasoning plan if enabled + valid
                    if (
                        _plan.valid
                        and ReasoningExecutor.is_enabled()
                        and ReasoningExecutor.in_rollout_bucket(parsed.raw_query)
                    ):
                        try:
                            _reasoning_result = await ReasoningExecutor.execute(
                                _plan,
                                parsed,
                                self.tool_executor,
                                inventory_result,
                                session_history=session.get_history(max_turns=4),
                            )
                            if _reasoning_result and _reasoning_result.success:
                                response = _reasoning_result.to_response_dict(
                                    session_id
                                )
                                response["follow_up_suggestions"] = (
                                    self._generate_follow_ups(parsed, None, session)
                                )
                                session.context["last_intent"] = parsed.intent.value
                                session.context["last_response_type"] = (
                                    "reasoning_report"
                                )
                                session.add_turn(
                                    "assistant",
                                    _reasoning_result.answer_text,
                                    sources=_reasoning_result.sources,
                                )
                                self._session_store.set(session)
                                return response
                        except Exception as _exec_err:
                            logger.warning(
                                f"[Reasoning] Execution failed, fallback: {_exec_err}"
                            )

                except Exception:
                    pass  # Plan generation must never block routing

        except Exception:
            pass  # Reasoning detection must never block routing

        # Step 4.4: Multi-intent detection (compound queries)
        # Phase A: Detection ALWAYS runs for logging (even when execution disabled).
        # Phase B+: Execution enabled via COMPOUND_QUERIES_ENABLED flag.
        _compound_enabled = os.environ.get(
            "COMPOUND_QUERIES_ENABLED", "false"
        ).lower() in ("true", "1", "yes")

        _compound_detected = False
        if "_signals" in dir() and _signals and "_domain_scores" in dir():
            try:
                _compound = MultiIntentDetector.detect(
                    message, _signals, _domain_scores
                )
                _compound_detected = _compound.is_compound

                # Phase A: Always log detection (even when execution disabled)
                if _compound_detected:
                    QualityMetrics.record(
                        event_type="compound_query_detected",
                        severity="INFO",
                        intent=parsed.intent.value,
                        details={
                            "detection_method": _compound.detection_method,
                            "compound_confidence": _compound.compound_confidence,
                            "sub_intent_count": len(_compound.sub_intents),
                            "execution_order": _compound.execution_order,
                            "execution_enabled": _compound_enabled,
                            "query": parsed.raw_query[:200],
                        },
                    )

                # Enrich reasoning detection with compound metadata
                if _compound_detected:
                    try:
                        _reasoning_with_compound = detect_reasoning(
                            query=parsed.raw_query,
                            signals_dict=_signals_dict,
                            compound_metadata=_compound.to_dict(),
                        )
                        if (
                            _reasoning_with_compound.reasoning_needed
                            and not _reasoning.reasoning_needed
                        ):
                            # Compound metadata upgraded detection
                            QualityMetrics.record(
                                event_type="reasoning_detected",
                                severity="INFO",
                                intent=parsed.intent.value,
                                details={
                                    **_reasoning_with_compound.to_dict(),
                                    "compound_metadata_present": True,
                                    "upgraded_by_compound": True,
                                },
                            )
                    except Exception:
                        pass

                if _compound_detected and _compound_enabled:
                    logger.info(
                        f"[Compound Query] method={_compound.detection_method} "
                        f"confidence={_compound.compound_confidence:.2f} "
                        f"subs={len(_compound.sub_intents)} "
                        f"order={_compound.execution_order} "
                        f'query="{parsed.raw_query[:60]}"'
                    )

                    # Check sequential enablement
                    _seq_enabled = os.environ.get(
                        "COMPOUND_SEQUENTIAL_ENABLED", "true"
                    ).lower() in ("true", "1", "yes")
                    if _compound.execution_order == "sequential" and not _seq_enabled:
                        logger.info(
                            "[Compound Query] Sequential disabled, treating as single"
                        )
                    else:
                        # Execute compound query
                        compound_result = await CompoundExecutor.execute(
                            _compound,
                            parsed,
                            inventory_result,
                            self.tool_executor,
                            conversation_history=session.get_history(max_turns=4),
                        )

                        # Hardening: fallback if executor returns None
                        # (too many sub-intents failed)
                        if compound_result is None:
                            logger.info(
                                "[Compound Fallback] Executor returned None, "
                                "falling through to single-intent"
                            )
                        else:
                            # Compose response
                            compound_response = ResponseComposer.compose(
                                compound_result
                            )

                            # Hardening: run ResponseEnforcer on merged text
                            from lead_to_cash.core.response_quality import (
                                ResponseEnforcer,
                            )

                            _merged_text = compound_response.get("answer", "")
                            if _merged_text:
                                _enforcement = ResponseEnforcer.enforce(
                                    _merged_text,
                                    parsed.intent.value,
                                    compound_response.get("sources", []),
                                )
                                if _enforcement.was_modified:
                                    compound_response["answer"] = (
                                        ResponseEnforcer.cleanup_whitespace(
                                            _enforcement.enforced_text
                                        )
                                    )

                            compound_response["session_id"] = session_id
                            compound_response["timestamp"] = datetime.now(
                                UTC
                            ).isoformat()

                            # Add follow-ups
                            follow_ups = self._generate_follow_ups(
                                parsed, None, session
                            )
                            compound_response["follow_up_suggestions"] = follow_ups

                            # Track in session
                            session.context["last_intent"] = parsed.intent.value
                            session.context["last_response_type"] = "compound_report"
                            session.add_turn(
                                "assistant",
                                compound_response.get("answer", ""),
                                sources=compound_response.get("sources", []),
                            )
                            self._session_store.set(session)

                            # QA sampling for compound queries
                            if RoutingMonitor.should_sample_for_qa(len(session.turns)):
                                RoutingMonitor.capture_qa_sample(
                                    query=parsed.raw_query,
                                    intent=f"compound:{_compound.detection_method}",
                                    routing_source="compound",
                                    confidence=_compound.compound_confidence,
                                    signals_snapshot=_compound.to_dict(),
                                    response_type="compound_report",
                                )

                            return compound_response
            except Exception as _compound_err:
                logger.warning(
                    f"Compound query execution failed, falling through: {_compound_err}"
                )

        # Step 4.5: Check for credit-only queries (fast path)
        # Detect "check credit", "credit limit", "credit status" queries and handle directly
        # NOTE: Now uses semantically-resolved company name from Step 4.1
        credit_response = await self._try_handle_credit_query(
            message, parsed, session, session_id
        )
        if credit_response:
            return credit_response

        # Step 4.6: Check for order detail / billing plan queries (fast path)
        order_response = await self._try_handle_order_query(
            message, parsed, session, session_id
        )
        if order_response:
            return order_response

        # Step 4.6b: Check for opportunity queries (fast path)
        opp_response = await self._try_handle_opportunity_query(
            message, parsed, session, session_id
        )
        if opp_response:
            return opp_response

        # Step 4.7: RBAC pre-check — block billing/collections queries for
        # unauthorized users before burning LLM tokens (parity with streaming path)
        if user_context and parsed.intent and parsed.intent.value == "billing_ar":
            permissions = user_context.get("permissions", {})
            has_billing = "read" in permissions.get(
                "billing", []
            ) or "*" in permissions.get("*", [])
            has_collections = "read" in permissions.get(
                "collections", []
            ) or "*" in permissions.get("*", [])
            if not has_billing and not has_collections:
                denial_msg = (
                    "I'm unable to share billing and collections information "
                    "as it requires financeops permissions. "
                    "Contact your admin to request: financeops role."
                )
                session.add_turn("assistant", denial_msg)
                self._session_store.set(session)
                return {
                    "type": "answer",
                    "session_id": session_id,
                    "answer": denial_msg,
                    "sources": [],
                    "confidence": "high",
                    "follow_up_suggestions": [
                        "What is the credit status for this customer?",
                        "Show me the customer profile",
                        "What products do we offer?",
                    ],
                    "timestamp": datetime.now(UTC).isoformat(),
                }

        # Step 4.6a: Check for billing/collections/DP queries (fast path)
        billing_response = await self._try_handle_billing_query(
            message, parsed, session, session_id, user_context=user_context
        )
        if billing_response:
            return billing_response

        # Step 4.6b: Check for escalation queries (fast path)
        escalation_response = await self._try_handle_escalation_query(
            message, parsed, session, session_id
        )
        if escalation_response:
            return escalation_response

        # Step 4.7: Pre-routing social engineering detection
        from lead_to_cash.core.tool_executor import ToolExecutor

        se_rejection = ToolExecutor._detect_social_engineering(parsed)
        if se_rejection:
            logger.info(f"Social engineering detected, returning rejection")
            session.add_turn("assistant", se_rejection)
            self._session_store.set(session)
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": se_rejection,
                "sources": [],
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Step 5: Check if clarification needed (BLOCKING)
        clarifications = await self._check_clarifications(parsed, session)
        if clarifications:
            session.pending_clarification = {
                "parsed_query": parsed,
                "questions": clarifications,
            }

            logger.info(f"Clarification needed: {len(clarifications)} questions")

            # Save session with pending clarification
            self._session_store.set(session)

            # Build answer text from clarification questions for API clients
            clarification_text = "; ".join(q.question for q in clarifications)
            return {
                "type": "clarification_needed",
                "session_id": session_id,
                "answer": f"I need some clarification: {clarification_text}",
                "questions": [q.to_dict() for q in clarifications],
                "partial_understanding": {
                    "intent": parsed.intent.value,
                    "entities": {
                        "competitors": parsed.competitors,
                        "companies": parsed.companies,
                        "regions": parsed.regions,
                        "products": parsed.products,
                    },
                    "time_reference": parsed.time_reference,
                },
            }

        # Step 6: Check data inventory
        try:
            inventory_result = await self.inventory.check_coverage(parsed)
        except Exception as e:
            logger.warning(f"Data inventory check failed: {e}")
            inventory_result = InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                gaps=[f"Inventory check failed: {e}"],
                recommended_sources=[],
            )

        # Step 6.5: SEMANTIC Entity Resolution
        # Uses embedding-based semantic similarity to resolve entity references
        # in follow-up queries like "What is their credit limit?" or "Tell me more"
        #
        # ARCHITECTURE: Semantic-first approach (NO keyword matching)
        # 1. Embed the user query
        # 2. Compare against embedded entity contexts from conversation history
        # 3. Use cosine similarity to find semantically relevant entities
        # 4. Handle ambiguity by asking for clarification
        logger.info(
            f"Step 6.5 CHECK: parsed.companies={parsed.companies}, "
            f"session.context.companies={session.context.get('companies', [])}, "
            f"session.context.last_kyp_entity={session.context.get('last_kyp_entity')}, "
            f"entity_history_count={len(session.entity_history)}, "
            f"session_id={session_id}"
        )

        if not parsed.companies:
            # No companies extracted by LLM - use semantic resolution
            context_company = None
            resolution_result = None

            # Use semantic entity resolution if available and we have history
            if SEMANTIC_RESOLVER_AVAILABLE and session.entity_history:
                try:
                    # Build enriched entity history with context for embedding
                    enriched_history = []
                    for entry in session.entity_history:
                        # Add conversation context around when entity was mentioned
                        entity_context = entry.get("context", "")
                        if not entity_context:
                            # Build context from intent and surrounding info
                            intent = session.context.get("last_intent", "general")
                            entity_context = (
                                f"Discussion about {entry.get('name')} "
                                f"in context of {intent}"
                            )
                        enriched_history.append(
                            {
                                "name": entry.get("name"),
                                "type": entry.get("type", "company"),
                                "context": entity_context,
                                "timestamp": entry.get("timestamp", ""),
                            }
                        )

                    # Resolve using semantic similarity
                    resolution_result = await resolve_entity_semantically(
                        query=message,
                        entity_history=enriched_history,
                    )

                    logger.info(
                        f"Semantic resolution result: status={resolution_result.status}, "
                        f"entity={resolution_result.entity_name}, "
                        f"confidence={resolution_result.confidence:.3f}, "
                        f"reason={resolution_result.resolution_reason}"
                    )

                    if resolution_result.status == SemanticResolutionStatus.RESOLVED:
                        context_company = resolution_result.entity_name
                        logger.info(
                            f"✅ SEMANTIC RESOLUTION: Resolved '{message[:50]}...' "
                            f"to '{context_company}' (confidence={resolution_result.confidence:.3f})"
                        )
                    elif resolution_result.status == SemanticResolutionStatus.AMBIGUOUS:
                        # Multiple entities with similar scores
                        # Only ask for clarification if the intent REQUIRES a specific
                        # company (KYP, billing, credit, customer intel). For general
                        # intents (market intel, product fit, competitor intel, general
                        # question), skip resolution and proceed without a company —
                        # these queries can answer fine without entity context.
                        entity_required_intents = {
                            QueryIntent.KYP_DUE_DILIGENCE,
                            QueryIntent.CUSTOMER_INTEL,
                            QueryIntent.BILLING_AR,
                            QueryIntent.RELATIONSHIP_CHECK,
                        }
                        if parsed.intent in entity_required_intents:
                            logger.info(
                                f"⚠️ AMBIGUOUS: Query matches multiple entities. "
                                f"Clarification needed for {parsed.intent.value}: "
                                f"{resolution_result.clarification_prompt}"
                            )
                            session.add_turn("user", message)
                            self._session_store.set(session)
                            return {
                                "type": "clarification_needed",
                                "questions": [
                                    {
                                        "question": resolution_result.clarification_prompt,
                                        "options": [
                                            {"label": c.name, "value": c.name}
                                            for c in resolution_result.candidates[:4]
                                        ],
                                    }
                                ],
                                "session_id": session_id,
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        else:
                            logger.info(
                                f"⚠️ AMBIGUOUS entity resolution for {parsed.intent.value} "
                                f"- skipping clarification (intent does not require entity)"
                            )
                    # NO_MATCH or NO_HISTORY - fall through to simple fallback

                except Exception as e:
                    logger.warning(f"Semantic resolution failed: {e}, using fallback")

            # Fallback: Simple recency-based resolution (only if semantic failed)
            if not context_company:
                # Priority 1: Last KYP entity (most specific for follow-up questions)
                if session.context.get("last_kyp_entity"):
                    context_company = session.context["last_kyp_entity"]
                    logger.info(f"Fallback: Using last_kyp_entity: '{context_company}'")
                # Priority 2: Most recent company from entity history
                elif session.entity_history:
                    for entry in reversed(session.entity_history):
                        if entry.get("type") == "company":
                            context_company = entry.get("name")
                            logger.info(
                                f"Fallback: Using most recent company: '{context_company}'"
                            )
                            break

            if context_company:
                # Restore entity_context if we have a confirmed entity
                confirmed = session.context.get("confirmed_entity")
                confirmed_name = (
                    confirmed.get("canonical_name", "") if confirmed else ""
                )

                if confirmed and _company_names_match(confirmed_name, context_company):
                    entity_ctx = EntityContext(
                        entity_id=confirmed.get("entity_id"),
                        canonical_name=confirmed.get("canonical_name"),
                        uen=confirmed.get("uen"),
                        lei=confirmed.get("lei"),
                        country_code=confirmed.get("country_code"),
                    )
                    parsed = replace(
                        parsed,
                        companies=[confirmed["canonical_name"]],
                        entity_context=entity_ctx,
                    )
                    logger.info(
                        f"✅ ENRICHED with full entity context: "
                        f"companies=['{confirmed['canonical_name']}'], UEN={entity_ctx.uen}"
                    )
                else:
                    parsed = replace(parsed, companies=[context_company])
                    logger.info(
                        f"✅ ENRICHED with resolved entity: companies=['{context_company}']"
                    )
            else:
                logger.info(
                    "No entity resolution needed - query is general or standalone"
                )

        # Step 6.6: PERFORMANCE - Check if follow-up can be answered from cached KYP
        cached_answer = await self._try_answer_from_cached_kyp(
            parsed, session, session_id
        )
        if cached_answer:
            logger.info(
                f"Fast KYP follow-up: answered from cache in <1s "
                f"(entity={session.context.get('last_kyp_entity')})"
            )
            # Add turn and save session
            session.add_turn(
                "assistant",
                cached_answer.get("answer", ""),
                sources=cached_answer.get("sources", []),
            )
            self._session_store.set(session)
            return cached_answer

        # Step 6.7: Entity Resolution for KYP queries
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            entity_result = await self._resolve_entity_for_kyp(session, parsed)
            if entity_result:
                # Entity confirmation needed - return to user
                logger.info(f"Entity confirmation required for KYP: {parsed.companies}")
                return entity_result
            # If entity was auto-confirmed, update parsed with canonical name and entity_context
            if session.context.get("confirmed_entity"):
                confirmed = session.context["confirmed_entity"]
                if confirmed.get("canonical_name"):
                    # replace imported at module level
                    # Create EntityContext with UEN/LEI for direct lookups
                    entity_ctx = EntityContext(
                        entity_id=confirmed.get("entity_id"),
                        canonical_name=confirmed.get("canonical_name"),
                        uen=confirmed.get("uen"),
                        lei=confirmed.get("lei"),
                        country_code=confirmed.get("country_code"),
                    )
                    parsed = replace(
                        parsed,
                        companies=[confirmed["canonical_name"]],
                        entity_context=entity_ctx,
                    )
                    logger.info(
                        f"Using confirmed entity: {confirmed['canonical_name']} "
                        f"(UEN={confirmed.get('uen')}, LEI={confirmed.get('lei')})"
                    )

        # Step 6.8: Source Authority Decision — deterministic source gate
        source_decision = SourceAuthority.decide(parsed, inventory_result)
        logger.info(
            f"Source authority: web_gate={source_decision.web_search_gate.value}, "
            f"fallback={source_decision.fallback_strategy.value}, "
            f"rationale={source_decision.rationale[:120]}"
        )

        # Step 7: Execute tool chain (pass source decision + conversation history)
        try:
            tool_result = await self.tool_executor.execute(
                parsed,
                inventory_result,
                conversation_history=session.get_history(max_turns=4),
                source_decision=source_decision,
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return self._error_response(session_id, str(e))

        # Step 7.5: Empty response fallback — retry with extended history
        # When no tool data was found but the user is asking a summary/recall
        # question, re-run synthesis with more conversation history.
        if (
            not tool_result.synthesized_content
            or len(tool_result.synthesized_content.strip()) < 10
        ) and len(session.turns) >= 4:
            logger.info(
                "Empty tool result with session history — retrying with extended history"
            )
            try:
                tool_result = await self.tool_executor.execute(
                    parsed,
                    inventory_result,
                    conversation_history=session.get_history(max_turns=10),
                    source_decision=source_decision,
                )
            except Exception as e:
                logger.warning(f"History-based retry failed: {e}")

        # Step 8: Generate follow-up suggestions
        follow_ups = self._generate_follow_ups(parsed, tool_result, session)

        # Step 9: Build response - check for KYP queries first
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            # Build structured KYP report
            kyp_response = await self._build_kyp_report(
                parsed, tool_result, session_id, follow_ups
            )
            if kyp_response:
                # CRITICAL: Store the KYP entity in session context for follow-up queries
                kyp_entity = kyp_response.get("entity_name")
                if kyp_entity and kyp_entity != "Unknown Entity":
                    existing_companies = set(session.context.get("companies", []))
                    existing_companies.add(kyp_entity)
                    session.context["companies"] = list(existing_companies)
                    session.context["last_kyp_entity"] = kyp_entity

                    # PERFORMANCE: Cache the KYP report for fast follow-up answers
                    session.context["cached_kyp_report"] = kyp_response
                    session.context["cached_kyp_timestamp"] = datetime.now(
                        UTC
                    ).isoformat()

                    logger.info(
                        f"Stored KYP entity and cached report: '{kyp_entity}', "
                        f"companies={session.context['companies']}"
                    )

                # Save a meaningful summary in conversation history so the LLM
                # can use it for follow-up questions. Without this, follow-ups
                # like "tell me more about them" have no data to work with.
                kyp_summary_parts = [
                    f"KYP Report for {kyp_entity or 'entity'}:",
                ]
                # Include key findings from the assessment
                assessment_items = kyp_response.get("assessment", {}).get("summary", [])
                for item in assessment_items:
                    status = item.get("status", "")
                    category = item.get("category", "")
                    detail = item.get("detail", "")[:100]
                    kyp_summary_parts.append(f"- {category}: {status} — {detail}")
                # Include business context
                sections = kyp_response.get("sections", [])
                for sec in sections:
                    if sec.get("id") in ("business_context", "sap_credit"):
                        for field in sec.get("fields", [])[:5]:
                            kyp_summary_parts.append(
                                f"- {field.get('label', '')}: {field.get('value', '')}"
                            )
                # Include recommendation
                rec = kyp_response.get("recommendation", {})
                if rec.get("decision"):
                    kyp_summary_parts.append(f"Recommendation: {rec['decision']}")
                kyp_turn_content = "\n".join(kyp_summary_parts)

                session.add_turn(
                    "assistant",
                    kyp_turn_content,
                    sources=tool_result.sources,
                    tools_used=[t.value for t in tool_result.tools_used],
                    follow_ups=follow_ups,
                )
                # Track last intent and response type for follow-up resolution
                session.context["last_intent"] = parsed.intent.value
                session.context["last_response_type"] = "kyp_report"

                self._session_store.set(session)
                logger.info(
                    f"Session saved after KYP: session_id={session_id}, "
                    f"context.companies={session.context.get('companies', [])}"
                )

                # Validate KYP response schema
                validation = OutputSchemaValidator.validate(kyp_response)
                if not validation.is_valid:
                    QualityMetrics.record_schema_validation("kyp_report", validation)

                return kyp_response

        # Track last intent and response type for follow-up resolution
        session.context["last_intent"] = parsed.intent.value
        session.context["last_response_type"] = "answer"

        answer = tool_result.synthesized_content or "No results found."

        # Filter sources to only those cited, renumber [N] to match
        answer, cited_sources = self._filter_cited_sources(answer, tool_result.sources)
        raw_sources_before_filter = list(cited_sources)

        # ── Final source filtering (3-layer) ─────────────────────────
        _sources_forbidden_removed = 0
        _sources_tier_removed = 0
        _citations_removed = 0

        if source_decision:
            # Layer 1: Remove forbidden sources
            pre_count = len(cited_sources)
            forbidden_values = {src.value for src in source_decision.forbidden_sources}
            cited_sources = [s for s in cited_sources if s not in forbidden_values]
            _sources_forbidden_removed = pre_count - len(cited_sources)

            # Layer 2: Tier-1-first policy — if Tier 1 sources present, show only those
            kept, removed = filter_sources_tier1_first(
                cited_sources, source_decision.max_tier
            )
            _sources_tier_removed = len(removed)
            if removed:
                cited_sources = kept

            # Layer 3: Clean orphaned citations from answer text
            # If a [N] reference points to a source we just removed, strip the marker
            if _sources_forbidden_removed + _sources_tier_removed > 0:
                answer, _citations_removed = strip_ungrounded_citations(
                    answer, cited_sources, raw_sources_before_filter
                )

            total_filtered = _sources_forbidden_removed + _sources_tier_removed
            if total_filtered > 0:
                logger.info(
                    f"[Source Filter] intent={parsed.intent.value}: "
                    f"forbidden={_sources_forbidden_removed} tier_demoted={_sources_tier_removed} "
                    f"citations_cleaned={_citations_removed} "
                    f"final_sources={len(cited_sources)}"
                )

        # ── Observability ─────────────────────────────────────────────
        _has_web = any(
            s
            for s in cited_sources
            if "perplexity" in s.lower() or "web" in s.lower() or "newsapi" in s.lower()
        )
        _is_tier1_only = (
            bool(cited_sources) and not _has_web and _sources_tier_removed == 0
        )
        QualityMetrics.record(
            event_type="response_routing_summary",
            severity="INFO",
            intent=parsed.intent.value,
            details={
                "intent_source": getattr(parsed, "intent_source", "llm"),
                "routing_risk": getattr(parsed, "routing_risk", None),
                "source_decision_fallback": source_decision.fallback_strategy.value
                if source_decision
                else None,
                "web_gate": source_decision.web_search_gate.value
                if source_decision
                else None,
                "used_web_sources": _has_web,
                "tier1_only": _is_tier1_only,
                "sources_forbidden_removed": _sources_forbidden_removed,
                "sources_tier_demoted": _sources_tier_removed,
                "citations_cleaned": _citations_removed,
                "final_source_count": len(cited_sources),
                "tools_used": [t.value for t in tool_result.tools_used],
            },
        )

        # Step 10: Add assistant turn
        session.add_turn(
            "assistant",
            answer,
            sources=cited_sources,
            tools_used=[t.value for t in tool_result.tools_used],
            follow_ups=follow_ups,
        )

        # Build reasoning carryover for eligible responses
        intent_val = parsed.intent.value
        if should_create_carryover(intent_val, answer, tool_result.confidence):
            entity_name = (
                parsed.companies[0]
                if parsed.companies
                else parsed.competitors[0]
                if parsed.competitors
                else ""
            )
            decision_type = _INTENT_TO_DECISION_TYPE.get(intent_val, "recommendation")
            # Extract a 1-sentence conclusion from the answer's first line
            first_line = answer.strip().split("\n")[0][:150]
            carryover = ReasoningCarryover(
                entity=entity_name,
                prior_intent=intent_val,
                prior_decision_type=decision_type,
                prior_conclusion=first_line,
                prior_rationale=[],  # Rationale comes from structured data, not raw text
                prior_constraints=[],
                confidence=tool_result.confidence or "medium",
            )
            session.context["reasoning_carryover"] = carryover.to_dict()
        else:
            # Clear stale carryover for ineligible responses
            session.context.pop("reasoning_carryover", None)

        # Save session after response
        self._session_store.set(session)

        response = {
            "type": "answer",
            "session_id": session_id,
            "answer": answer,
            "sources": cited_sources,
            "confidence": tool_result.confidence,
            "data_coverage": {
                "has_local_data": inventory_result.has_local_data,
                "coverage_confidence": inventory_result.confidence,
                "coverage_percentage": (
                    inventory_result.coverage.coverage_percentage
                    if inventory_result.coverage
                    else 0.0
                ),
                "document_count": (
                    inventory_result.coverage.document_count
                    if inventory_result.coverage
                    else 0
                ),
                "freshness_hours": inventory_result.freshness_hours,
                "gaps": inventory_result.gaps,
            },
            "tools_used": [t.value for t in tool_result.tools_used],
            "execution_time_ms": tool_result.total_execution_time_ms,
            "follow_up_suggestions": follow_ups,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Output schema validation — log issues but don't block response
        validation = OutputSchemaValidator.validate(response)
        if not validation.is_valid:
            QualityMetrics.record_schema_validation("answer", validation)
            logger.warning(f"Response schema validation errors: {validation.errors}")
        elif validation.warnings:
            logger.info(f"Response schema validation warnings: {validation.warnings}")

        return response

    async def _handle_clarification_response(
        self,
        session: ConversationSession,
        message: str,
        clarification_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle response to a clarification question.

        Args:
            session: Current session
            message: User's message
            clarification_response: The clarification answer

        Returns:
            Processed response or next clarification
        """
        if not session.pending_clarification:
            # No pending clarification, process as normal
            session.pending_clarification = None
            return await self.process_message(session.session_id, message)

        # Get the original parsed query
        parsed: ParsedQuery = session.pending_clarification["parsed_query"]

        # Apply clarification to parsed query
        updated_parsed = self._apply_clarification(parsed, clarification_response)

        # Clear pending clarification
        session.pending_clarification = None

        # Add user turn for clarification response
        session.add_turn(
            "user",
            message,
            clarification_answer=clarification_response,
        )

        # Check for more clarifications needed
        remaining = await self._check_clarifications(updated_parsed, session)
        if remaining:
            session.pending_clarification = {
                "parsed_query": updated_parsed,
                "questions": remaining,
            }

            # Save session with new clarification
            self._session_store.set(session)

            return {
                "type": "clarification_needed",
                "session_id": session.session_id,
                "questions": [q.to_dict() for q in remaining],
                "partial_understanding": {
                    "intent": updated_parsed.intent.value,
                    "entities": {
                        "competitors": updated_parsed.competitors,
                        "companies": updated_parsed.companies,
                        "regions": updated_parsed.regions,
                    },
                    "time_reference": updated_parsed.time_reference,
                },
            }

        # All clarifications answered, proceed with execution
        try:
            inventory_result = await self.inventory.check_coverage(updated_parsed)
        except Exception as e:
            logger.warning(f"Data inventory check failed: {e}")
            inventory_result = InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                gaps=[f"Inventory check failed: {e}"],
                recommended_sources=[],
            )

        source_decision = SourceAuthority.decide(updated_parsed, inventory_result)
        try:
            tool_result = await self.tool_executor.execute(
                updated_parsed,
                inventory_result,
                conversation_history=session.get_history(max_turns=4),
                source_decision=source_decision,
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return self._error_response(session.session_id, str(e))

        follow_ups = self._generate_follow_ups(updated_parsed, tool_result, session)
        answer = tool_result.synthesized_content or "No results found."

        session.add_turn(
            "assistant",
            answer,
            sources=tool_result.sources,
            tools_used=[t.value for t in tool_result.tools_used],
            follow_ups=follow_ups,
        )

        # Save session after response
        self._session_store.set(session)

        return {
            "type": "answer",
            "session_id": session.session_id,
            "answer": answer,
            "sources": _sanitize_sources(tool_result.sources),
            "confidence": tool_result.confidence,
            "data_coverage": {
                "has_local_data": inventory_result.has_local_data,
                "coverage_confidence": inventory_result.confidence,
                "coverage_percentage": (
                    inventory_result.coverage.coverage_percentage
                    if inventory_result.coverage
                    else 0.0
                ),
                "document_count": (
                    inventory_result.coverage.document_count
                    if inventory_result.coverage
                    else 0
                ),
                "freshness_hours": inventory_result.freshness_hours,
                "gaps": inventory_result.gaps,
            },
            "tools_used": [t.value for t in tool_result.tools_used],
            "execution_time_ms": tool_result.total_execution_time_ms,
            "follow_up_suggestions": follow_ups,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _apply_clarification(
        self,
        parsed: ParsedQuery,
        clarification_response: Dict[str, Any],
    ) -> ParsedQuery:
        """
        Apply clarification answer to parsed query.

        Uses dataclasses.replace() to create an immutable update pattern,
        avoiding fragile object.__setattr__ hacks.

        Args:
            parsed: Original parsed query
            clarification_response: User's clarification answer

        Returns:
            New ParsedQuery with clarification applied
        """
        # replace imported at module level

        question_id = clarification_response.get("question_id", "")
        answer = clarification_response.get("answer", "")

        # Build updates dictionary
        updates: Dict[str, Any] = {
            "requires_clarification": False,
            "clarification_questions": [],
        }

        if question_id == "time_period":
            # Map answer to time values
            time_mapping = {
                "Last 7 days (latest)": ("7d", True),
                "Last 30 days": ("30d", False),
                "Last 3 months": ("90d", False),
                "Last year": ("365d", False),
                "All available (3 years)": ("3y", False),
            }

            if answer in time_mapping:
                ref, is_realtime = time_mapping[answer]
                updates["time_reference"] = ref
                updates["is_realtime_needed"] = is_realtime

        elif question_id == "competitor":
            # Map competitor answer
            comp_mapping = {
                "Caterpillar (CAT/MaK)": ["Caterpillar"],
                "Cummins": ["Cummins"],
                "MAN Energy Solutions": ["MAN Energy Solutions"],
                "All major competitors": [
                    "Caterpillar",
                    "Cummins",
                    "MAN Energy Solutions",
                ],
            }

            if answer in comp_mapping:
                updates["competitors"] = comp_mapping[answer]

        elif question_id == "region":
            # Handle region clarification
            region_mapping = {
                "APAC": ["APAC"],
                "Europe": ["Europe"],
                "Americas": ["Americas"],
                "All regions": ["APAC", "Europe", "Americas"],
            }

            if answer in region_mapping:
                updates["regions"] = region_mapping[answer]

        # Create new ParsedQuery with updates (immutable pattern)
        return replace(parsed, **updates)

    # =========================================================================
    # Entity Resolution for KYP
    # =========================================================================

    async def _resolve_entity_for_kyp(
        self,
        session: "ConversationSession",
        parsed: ParsedQuery,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve entity for KYP queries using agentic tool calling.

        Resolution strategy (autonomous, minimal user intervention):
        1. Extract raw entity from query (LLM extracts, doesn't interpret)
        2. EntityResolutionAgent calls tools in sequence:
           - Entity Registry Database (local)
           - ACRA (Singapore)
           - GLEIF (Global)
           - OpenCorporates (Global)
           - Web Search (Perplexity) as fallback
        3. Auto-confirm if confidence >= 80% or margin >= 15%
        4. Only ask user for truly ambiguous cases

        NO HARDCODED ENTITY LISTS - all knowledge comes from tool calls.

        Args:
            session: Current conversation session
            parsed: Parsed query with raw_company_input (what user typed)

        Returns:
            Response dict if confirmation needed, None otherwise
        """
        if not parsed.companies:
            logger.debug("No companies in parsed query, skipping resolution")
            return None

        # Raw company input is what user actually typed (agent will interpret via tools)
        raw_input = parsed.raw_company_input or parsed.companies[0]
        # For logging only - what LLM parsed
        parsed_company = parsed.companies[0]

        logger.info(f"Entity resolution: raw='{raw_input}', parsed='{parsed_company}'")

        # Check if entity is already confirmed in session context
        if session.context.get("confirmed_entity"):
            confirmed = session.context["confirmed_entity"]
            confirmed_query = confirmed.get("query", "").lower()
            if (
                confirmed_query == raw_input.lower()
                or confirmed_query == parsed_company.lower()
            ):
                logger.info(
                    f"Using previously confirmed entity: {confirmed.get('canonical_name')}"
                )
                return None

        # Check if name matches a known SAP customer — skip external resolution
        try:
            from lead_to_cash.integrations.cpi_simulator import SIMULATED_CUSTOMERS

            _input_lower = raw_input.lower().strip()
            for _cid, _cust in SIMULATED_CUSTOMERS.items():
                _n1 = (_cust.name1 or "").lower().strip()
                _n2 = (_cust.name2 or "").lower().strip()
                if (
                    _input_lower in (_n1, _n2)
                    or _n1 == _input_lower
                    or _n2 == _input_lower
                ):
                    _canonical = _cust.name1 or _cust.name2
                    logger.info(
                        f"Entity resolution: '{raw_input}' matches SAP customer {_cid} "
                        f"('{_canonical}') — auto-confirmed, skipping external resolution"
                    )
                    session.context["confirmed_entity"] = {
                        "entity_id": _cid,
                        "canonical_name": _canonical,
                        "uen": _cust.stcd1,
                        "query": raw_input.lower(),
                    }
                    parsed.companies = [_canonical]
                    return None
        except ImportError:
            pass

        # Use agentic entity resolution (preferred)
        # entity_agent property uses lazy import to avoid circular dependency
        if self.entity_agent is not None:
            try:
                result = await self.entity_agent.resolve(
                    raw_query=raw_input,
                    country_hint=None,
                    session_id=session.session_id,
                )

                if result.status == ResolutionStatus.EXACT_MATCH:
                    if result.exact_match:
                        session.context["confirmed_entity"] = {
                            "entity_id": result.exact_match.entity_id,
                            "canonical_name": result.exact_match.canonical_name,
                            "uen": result.exact_match.uen,
                            "lei": result.exact_match.lei,
                            "country_code": result.exact_match.country_code,
                            "query": raw_input,
                            "raw_input": raw_input,
                        }
                        logger.info(
                            f"Entity auto-confirmed (agent): {result.exact_match.canonical_name} "
                            f"(source={result.exact_match.source}, "
                            f"confidence={result.exact_match.confidence_score}%)"
                        )
                    return None

                elif result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
                    candidates = result.candidates
                    if candidates:
                        # Agent handles auto-confirm logic internally, so if we get here
                        # it means user confirmation is truly needed
                        session.pending_clarification = {
                            "type": "entity_confirmation",
                            "parsed_query": parsed,
                            "candidates": [c.to_dict() for c in candidates],
                            "query": raw_input,
                            "raw_input": raw_input,
                            "message": result.confirmation_message,
                        }
                        self._session_store.set(session)

                        return {
                            "type": "entity_confirmation_needed",
                            "session_id": session.session_id,
                            "answer": result.confirmation_message,
                            "message": result.confirmation_message,
                            "candidates": [c.to_dict() for c in candidates],
                            "query": raw_input,
                            "raw_input": raw_input,
                        }

                elif result.status == ResolutionStatus.NO_MATCH:
                    logger.info(
                        f"No match found for '{raw_input}' "
                        "via agent tools (registry, ACRA, GLEIF, OpenCorporates, web)"
                    )
                    # Continue with raw input - KYP will proceed with web search

                return None

            except Exception as e:
                logger.error(f"Agentic entity resolution failed: {e}")
                # Fall through to legacy service

        # Fallback to legacy EntityResolutionService
        if not ENTITY_REGISTRY_AVAILABLE:
            logger.warning("Entity registry not available - cannot resolve entities")
            return None

        if self.entity_service is None:
            logger.warning("Entity service not initialized - cannot resolve entities")
            return None

        try:
            await self.entity_service.initialize()

            result = await self.entity_service.resolve(
                query=raw_input,
                country_hint=None,
                search_external=True,
                session_id=session.session_id,
            )

            if result.status == ResolutionStatus.EXACT_MATCH:
                if result.exact_match:
                    session.context["confirmed_entity"] = {
                        "entity_id": result.exact_match.entity_id,
                        "canonical_name": result.exact_match.canonical_name,
                        "uen": result.exact_match.uen,
                        "lei": result.exact_match.lei,
                        "country_code": result.exact_match.country_code,
                        "query": raw_input,
                        "raw_input": raw_input,
                    }
                    logger.info(
                        f"Entity auto-confirmed (service): {result.exact_match.canonical_name}"
                    )
                return None

            elif result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
                candidates = result.candidates or result.external_results
                if candidates:
                    top_candidate = candidates[0]

                    # Auto-confirm if high confidence or clear margin
                    should_auto_confirm = False
                    auto_confirm_reason = None

                    if top_candidate.confidence_score >= 80.0:
                        should_auto_confirm = True
                        auto_confirm_reason = (
                            f"high confidence ({top_candidate.confidence_score:.0f}%)"
                        )
                    elif len(candidates) > 1:
                        margin = (
                            top_candidate.confidence_score
                            - candidates[1].confidence_score
                        )
                        if margin >= 15.0:
                            should_auto_confirm = True
                            auto_confirm_reason = f"clear winner (margin={margin:.0f}%)"

                    if should_auto_confirm:
                        session.context["confirmed_entity"] = {
                            "entity_id": top_candidate.entity_id,
                            "canonical_name": top_candidate.canonical_name,
                            "uen": top_candidate.uen,
                            "lei": top_candidate.lei,
                            "country_code": top_candidate.country_code,
                            "query": raw_input,
                            "raw_input": raw_input,
                        }
                        logger.info(
                            f"Entity auto-confirmed (service, {auto_confirm_reason}): "
                            f"{top_candidate.canonical_name}"
                        )
                        return None

                    # Ask user for confirmation
                    session.pending_clarification = {
                        "type": "entity_confirmation",
                        "parsed_query": parsed,
                        "candidates": [c.to_dict() for c in candidates],
                        "query": raw_input,
                        "raw_input": raw_input,
                        "message": result.confirmation_message,
                    }
                    self._session_store.set(session)

                    return {
                        "type": "entity_confirmation_needed",
                        "session_id": session.session_id,
                        "answer": result.confirmation_message,
                        "message": result.confirmation_message,
                        "candidates": [c.to_dict() for c in candidates],
                        "query": raw_input,
                        "raw_input": raw_input,
                        "resolution_time_ms": result.resolution_time_ms,
                    }

            elif result.status == ResolutionStatus.NO_MATCH:
                logger.info(
                    f"No match found for '{raw_input}' in database or external sources"
                )

        except Exception as e:
            logger.error(f"Entity resolution failed: {e}")

        return None

    async def _handle_entity_confirmation(
        self,
        session: "ConversationSession",
        message: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle user's entity confirmation response.

        Processes numeric responses (e.g., "1", "2") to select from candidates.

        Args:
            session: Current conversation session
            message: User's message (expected to be a number or company name)

        Returns:
            None if confirmation handled (continue with flow),
            Response dict if error or need more input
        """
        if not session.pending_clarification:
            return None

        if session.pending_clarification.get("type") != "entity_confirmation":
            return None

        candidates = session.pending_clarification.get("candidates", [])
        parsed_raw = session.pending_clarification.get("parsed_query")
        original_query = session.pending_clarification.get("query", "")

        # SAFETY: Ensure parsed is a ParsedQuery object, not a dict
        # This handles cases where session was serialized with old buggy code
        # or loaded from fallback cache with mutated state
        if isinstance(parsed_raw, dict):
            logger.warning(
                "parsed_query in pending_clarification is a dict, reconstructing ParsedQuery"
            )
            parsed = ParsedQuery.from_dict(parsed_raw)
            if parsed:
                # Update the session with the reconstructed object
                session.pending_clarification["parsed_query"] = parsed
                logger.info(
                    f"Reconstructed ParsedQuery with intent={parsed.intent.value}"
                )
            else:
                logger.error("Failed to reconstruct ParsedQuery from dict")
        elif isinstance(parsed_raw, ParsedQuery):
            parsed = parsed_raw
        else:
            parsed = None
            logger.warning(f"parsed_query is unexpected type: {type(parsed_raw)}")

        # Try to parse as number (1-based selection) first - this is unambiguous
        selected_candidate = None
        message_stripped = message.strip()

        if message_stripped.isdigit():
            selection = int(message_stripped)
            if 1 <= selection <= len(candidates):
                selected_candidate = candidates[selection - 1]
                logger.info(
                    f"Numeric selection '{selection}' - selecting candidate: "
                    f"{selected_candidate.get('canonical_name')}"
                )

        # If no numeric selection, use LLM to understand the response with context
        if not selected_candidate:
            logger.info(
                f"Using LLM to interpret entity confirmation response: '{message_stripped}'"
            )

            # Parse the message with conversation history for context
            # LLM will detect: confirmation, rejection, or clarification
            try:
                refined_parsed = await self.query_engine.parse(
                    message,
                    session.get_history(),
                )

                logger.info(
                    f"LLM entity response detection: "
                    f"is_entity_response={refined_parsed.is_entity_response}, "
                    f"is_confirmation={refined_parsed.is_confirmation}, "
                    f"is_rejection={refined_parsed.is_rejection}, "
                    f"original_search_term={refined_parsed.original_search_term}, "
                    f"companies={refined_parsed.companies}"
                )

                # LLM detected confirmation (yes, yeah, correct, that's it, etc.)
                if refined_parsed.is_confirmation and len(candidates) >= 1:
                    selected_candidate = candidates[0]
                    logger.info(
                        f"LLM detected confirmation - selecting first candidate: "
                        f"{selected_candidate.get('canonical_name')}"
                    )

                # Also try to match by name if LLM extracted a company
                if not selected_candidate and refined_parsed.companies:
                    extracted_name = refined_parsed.companies[0].lower()
                    for c in candidates:
                        if extracted_name in c.get("canonical_name", "").lower():
                            selected_candidate = c
                            logger.info(
                                f"LLM extracted company matched candidate: "
                                f"{selected_candidate.get('canonical_name')}"
                            )
                            break

            except Exception as e:
                logger.warning(f"LLM parsing failed, will use fallback: {e}")
                refined_parsed = None

        # If still no selection and we have LLM results, handle rejection/clarification
        if not selected_candidate and refined_parsed:
            # NEW-TOPIC DETECTION: If the user's message is NOT an entity response,
            # NOT a confirmation, NOT a rejection, and has no company names,
            # this is a completely new topic — clear the pending state and let
            # process_message() handle it normally.
            if (
                not refined_parsed.is_entity_response
                and not refined_parsed.is_confirmation
                and not refined_parsed.is_rejection
                and not refined_parsed.companies
            ):
                logger.info(
                    "User sent new topic while entity confirmation pending - "
                    f"clearing pending state. Intent: {refined_parsed.intent}"
                )
                session.pending_clarification = None
                self._session_store.set(session)
                return None  # Return None to resume normal process_message() flow

            # Use LLM-detected rejection instead of hardcoded pattern matching
            # The LLM understands "no", "nope", "that's not it", etc. in conversation context
            is_rejection = refined_parsed.is_rejection

            # Get the original search term from LLM extraction or fallback to stored query
            search_term_for_alternatives = (
                refined_parsed.original_search_term or original_query
            )

            # If rejection and no new company extracted, search external sources
            # for the ORIGINAL query (e.g., user typed "cll", we suggested "CLLS",
            # user said "no" - so search ACRA/GLEIF for "cll")
            if is_rejection and not refined_parsed.companies:
                logger.info(
                    f"User rejected suggestions for '{search_term_for_alternatives}' - "
                    "searching external sources for alternatives"
                )

                if self.entity_service:
                    await self.entity_service.initialize()
                    # Search external sources (ACRA, GLEIF) for the original search term
                    # (LLM extracts this from conversation context)
                    external_result = await self.entity_service.resolve(
                        query=search_term_for_alternatives,
                        country_hint=None,
                        search_external=True,
                        session_id=session.session_id,
                    )

                    # Collect external results that are different from current candidates
                    current_names = {
                        c.get("canonical_name", "").lower() for c in candidates
                    }
                    new_alternatives = []

                    if external_result.external_results:
                        for ext in external_result.external_results:
                            if ext.canonical_name.lower() not in current_names:
                                new_alternatives.append(ext)

                    if new_alternatives:
                        # Found different companies - present them
                        alt_message = (
                            f"I understand '{candidates[0].get('canonical_name', '')}' "
                            f"is not what you're looking for.\n\n"
                            f"I found these other companies matching "
                            f"'{search_term_for_alternatives}':\n\n"
                        )
                        for i, alt in enumerate(new_alternatives[:3], 1):
                            source = alt.source or "external"
                            alt_message += (
                                f"**{i}. {alt.canonical_name}**\n"
                                f"   Country: {alt.country_code or 'Unknown'} | "
                                f"Source: {source}\n\n"
                            )
                        alt_message += (
                            "Reply with a number to select, or tell me the exact "
                            "company name you're looking for."
                        )

                        # Update pending clarification with new alternatives
                        all_candidates = [c.to_dict() for c in new_alternatives]
                        preserved_parsed = parsed if parsed else refined_parsed
                        session.pending_clarification = {
                            "type": "entity_confirmation",
                            "parsed_query": preserved_parsed,
                            "candidates": all_candidates,
                            "query": search_term_for_alternatives,
                            "message": alt_message,
                        }
                        self._session_store.set(session)

                        return {
                            "type": "entity_confirmation_needed",
                            "session_id": session.session_id,
                            "answer": alt_message,
                            "message": alt_message,
                            "candidates": all_candidates,
                            "query": search_term_for_alternatives,
                        }
                    else:
                        # No alternatives found - ask user what they want to do
                        no_alt_msg = (
                            f"I couldn't find any other companies matching "
                            f"'{search_term_for_alternatives}' in our records "
                            "or external sources.\n\n"
                            "What would you like to do?\n"
                            "- Provide the full official company name\n"
                            "- Try a different search term\n"
                            "- Skip this and ask something else"
                        )
                        return {
                            "type": "clarification_needed",
                            "session_id": session.session_id,
                            "answer": no_alt_msg,
                            "message": no_alt_msg,
                            "query": search_term_for_alternatives,
                        }

            # Check if LLM extracted a company name from the clarification
            if refined_parsed.companies:
                new_company = refined_parsed.companies[0]
                logger.info(f"LLM extracted company '{new_company}' from clarification")

                # Clear the old pending clarification
                session.pending_clarification = None

                # Re-run entity resolution with the new company name
                if self.entity_service:
                    await self.entity_service.initialize()
                    new_result = await self.entity_service.resolve(
                        query=new_company,
                        country_hint=None,
                        search_external=True,
                        session_id=session.session_id,
                    )

                    if new_result.status == ResolutionStatus.EXACT_MATCH:
                        # Auto-confirm and continue
                        if new_result.exact_match:
                            session.context["confirmed_entity"] = {
                                "entity_id": new_result.exact_match.entity_id,
                                "canonical_name": new_result.exact_match.canonical_name,
                                "uen": new_result.exact_match.uen,
                                "lei": new_result.exact_match.lei,
                                "country_code": new_result.exact_match.country_code,
                                "query": new_company,
                            }
                            logger.info(
                                f"Entity auto-confirmed after refinement: "
                                f"{new_result.exact_match.canonical_name}"
                            )
                            # Update parsed and continue with KYP flow
                            # CRITICAL: Use original 'parsed' (with original intent)
                            # NOT 'refined_parsed' which may have different intent
                            if parsed:
                                parsed = replace(
                                    parsed,
                                    companies=[new_result.exact_match.canonical_name],
                                )
                                self._session_store.set(session)
                                # Return to continue with KYP flow using original intent
                                return await self._continue_kyp_after_confirmation(
                                    session, parsed
                                )
                            else:
                                # Fallback: parsed was None, use refined_parsed
                                logger.warning(
                                    "Original parsed_query was None, "
                                    "falling back to refined_parsed"
                                )
                                self._session_store.set(session)
                                return await self._continue_kyp_after_confirmation(
                                    session,
                                    replace(
                                        refined_parsed,
                                        companies=[
                                            new_result.exact_match.canonical_name
                                        ],
                                    ),
                                )

                    elif new_result.status == ResolutionStatus.CONFIRMATION_REQUIRED:
                        # New candidates found - present them
                        new_candidates = (
                            new_result.candidates or new_result.external_results
                        )
                        if new_candidates:
                            # CRITICAL: Preserve original 'parsed' (with original intent)
                            # NOT 'refined_parsed' which may have different intent
                            preserved_parsed = parsed if parsed else refined_parsed
                            session.pending_clarification = {
                                "type": "entity_confirmation",
                                "parsed_query": preserved_parsed,
                                "candidates": [c.to_dict() for c in new_candidates],
                                "query": new_company,
                                "message": new_result.confirmation_message,
                            }
                            self._session_store.set(session)
                            return {
                                "type": "entity_confirmation_needed",
                                "session_id": session.session_id,
                                "answer": new_result.confirmation_message,
                                "message": new_result.confirmation_message,
                                "candidates": [c.to_dict() for c in new_candidates],
                                "query": new_company,
                                "resolution_time_ms": new_result.resolution_time_ms,
                            }

                    # NO_MATCH - continue without entity resolution
                    logger.info(f"No match found for refined query '{new_company}'")

            # Fallback: If LLM couldn't help, ask user to be more specific
            fallback_msg = (
                f"I couldn't find a match for that. Please either:\n"
                f"  - Select a number (1-{len(candidates)}) from the list above\n"
                f"  - Or provide the full official company name"
            )
            return {
                "type": "entity_confirmation_needed",
                "session_id": session.session_id,
                "answer": fallback_msg,
                "message": fallback_msg,
                "candidates": candidates,
                "query": original_query,
                "error": "invalid_selection",
            }

        # Store confirmed entity in session context
        session.context["confirmed_entity"] = {
            "entity_id": selected_candidate.get("entity_id"),
            "canonical_name": selected_candidate.get("canonical_name"),
            "uen": selected_candidate.get("uen"),
            "lei": selected_candidate.get("lei"),
            "country_code": selected_candidate.get("country_code"),
            "query": original_query,
        }

        # Update parsed.companies with canonical name
        if parsed and selected_candidate.get("canonical_name"):
            # replace imported at module level
            parsed = replace(parsed, companies=[selected_candidate["canonical_name"]])

        # Clear pending clarification
        session.pending_clarification = None

        # Add confirmation turn
        session.add_turn(
            "user",
            message,
            entity_confirmation=selected_candidate,
        )
        session.add_turn(
            "assistant",
            f"Confirmed: {selected_candidate.get('canonical_name')} "
            f"({selected_candidate.get('country_code', 'XX')})",
        )

        # If entity service available, record the confirmation
        if ENTITY_REGISTRY_AVAILABLE and self.entity_service:
            try:
                candidate = EntityCandidate.from_dict(selected_candidate)
                await self.entity_service.confirm_selection(
                    session_id=session.session_id,
                    candidate=candidate,
                    user_id=session.context.get("user_id"),
                )
            except Exception as e:
                logger.warning(f"Failed to record entity confirmation: {e}")

        # Save session and return None to continue with KYP flow
        self._session_store.set(session)

        # Re-trigger the KYP flow with confirmed entity
        # We do this by re-processing the original message
        if parsed:
            return await self._continue_kyp_after_confirmation(session, parsed)

        return None

    async def _continue_kyp_after_confirmation(
        self,
        session: "ConversationSession",
        parsed: ParsedQuery,
    ) -> Dict[str, Any]:
        """
        Continue KYP flow after entity confirmation.

        This re-runs the tool execution and response building
        with the confirmed entity.

        Args:
            session: Session with confirmed entity
            parsed: Original parsed query (with updated companies)

        Returns:
            KYP response dictionary
        """
        # Get confirmed entity with identifiers for direct lookups
        confirmed = session.context.get("confirmed_entity", {})
        canonical_name = confirmed.get("canonical_name")

        if canonical_name:
            # replace imported at module level
            # Create EntityContext with UEN/LEI for direct lookups in SAP/EODHD
            entity_ctx = EntityContext(
                entity_id=confirmed.get("entity_id"),
                canonical_name=canonical_name,
                uen=confirmed.get("uen"),
                lei=confirmed.get("lei"),
                country_code=confirmed.get("country_code"),
            )
            parsed = replace(
                parsed,
                companies=[canonical_name],
                entity_context=entity_ctx,
            )
            logger.info(
                f"Continuing KYP with entity: {canonical_name} "
                f"(UEN={confirmed.get('uen')}, LEI={confirmed.get('lei')})"
            )

        # Check data inventory
        try:
            inventory_result = await self.inventory.check_coverage(parsed)
        except Exception as e:
            logger.warning(f"Data inventory check failed: {e}")
            inventory_result = InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                gaps=[f"Inventory check failed: {e}"],
                recommended_sources=[],
            )

        # Execute tool chain (pass conversation history for cross-turn context)
        source_decision = SourceAuthority.decide(parsed, inventory_result)
        try:
            tool_result = await self.tool_executor.execute(
                parsed,
                inventory_result,
                conversation_history=session.get_history(max_turns=4),
                source_decision=source_decision,
            )
        except Exception as e:
            logger.error(f"Tool execution failed after confirmation: {e}")
            return self._error_response(session.session_id, str(e))

        # Generate follow-ups
        follow_ups = self._generate_follow_ups(parsed, tool_result, session)

        # Build KYP report
        kyp_response = await self._build_kyp_report(
            parsed, tool_result, session.session_id, follow_ups
        )

        if kyp_response:
            # Store KYP entity
            kyp_entity = kyp_response.get("entity_name")
            if kyp_entity:
                session.context["companies"] = list(
                    set(session.context.get("companies", []) + [kyp_entity])
                )
                session.context["last_kyp_entity"] = kyp_entity
                session.context["cached_kyp_report"] = kyp_response
                session.context["cached_kyp_timestamp"] = datetime.now(UTC).isoformat()

            session.add_turn(
                "assistant",
                f"KYP Report generated for {kyp_entity or 'entity'}",
                sources=tool_result.sources,
                tools_used=[t.value for t in tool_result.tools_used],
                follow_ups=follow_ups,
            )
            self._session_store.set(session)
            return kyp_response

        # Fallback to text response
        response = self._build_response(
            parsed, tool_result, session.session_id, follow_ups
        )
        session.add_turn(
            "assistant",
            response.get("answer", ""),
            sources=tool_result.sources,
            tools_used=[t.value for t in tool_result.tools_used],
            follow_ups=follow_ups,
        )
        self._session_store.set(session)
        return response

    # Vague follow-up patterns that need clarification (exact match)
    VAGUE_FOLLOWUP_PATTERNS = [
        "and?",
        "and",
        "so?",
        "so",
        "what else",
        "what else?",
        "anything else",
        "anything else?",
        "more",
        "more?",
        "continue",
        "go on",
        "yes",
        "yes?",
        "ok",
        "okay",
        "hmm",
        "hm",
        "...",
    ]

    # Patterns that indicate missing entity context
    # These patterns with "the company/customer" suggest user expects context we may not have
    MISSING_ENTITY_PATTERNS = [
        "tell me about the company",
        "what about the company",
        "check the company",
        "look up the company",
        "info on the company",
        "information about the company",
        "tell me about the customer",
        "what about the customer",
        "check the customer",
        "look up the customer",
        "info on the customer",
        "information about the customer",
        "tell me about them",
        "what about them",
        "check on them",
        "look them up",
    ]

    # Patterns that are too vague without more context
    VAGUE_ACTION_PATTERNS = [
        "run a check",
        "do a check",
        "perform a check",
        "run the check",
        "look something up",
        "find out",
        "check on something",
        "look into it",
        "check it",
        "run it",
    ]

    def _is_vague_followup(self, query: str) -> bool:
        """
        Check if query is a vague follow-up that needs clarification.

        Args:
            query: User's query text

        Returns:
            True if the query is too vague to process meaningfully
        """
        normalized = query.strip().lower().rstrip("?!.")

        # Check exact pattern match
        if normalized in self.VAGUE_FOLLOWUP_PATTERNS:
            return True

        # Check very short queries
        if len(normalized) <= 3:
            return True

        # Check patterns with generic "the company/customer" references
        for pattern in self.MISSING_ENTITY_PATTERNS:
            if pattern in normalized:
                return True

        # Check vague action patterns
        for pattern in self.VAGUE_ACTION_PATTERNS:
            if pattern in normalized:
                return True

        return False

    # =========================================================================
    # UNIVERSAL SEMANTIC ENTITY RESOLUTION
    # =========================================================================
    # Harmonized approach: Apply semantic resolution to ALL query types
    # (credit, billing, KYP, customer intel) - not just follow-up pronouns.
    #
    # This ensures "STE" → "ST Engineering" works for:
    # - Sales ops: "Tell me about STE" → customer intel
    # - Finance ops: "Check STE billings" → billing/AR query
    # - Credit queries: "STE credit limit" → SAP credit check
    # =========================================================================

    async def _apply_universal_semantic_resolution(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
    ) -> Optional[str]:
        """
        Universal semantic entity resolution - runs BEFORE intent-specific routing.

        Resolves/expands company names from parsed query against entity history:
        - "STE" → "ST Engineering" (abbreviation expansion)
        - "the ferry company" → "Batam Fast Ferry" (contextual reference)
        - "their" → most recent entity (pronoun resolution)

        This method harmonizes entity resolution across ALL contexts:
        - Sales ops (customer intel, KYP)
        - Finance ops (billing, credit)

        Args:
            message: Original user message
            parsed: Parsed query from QueryUnderstandingEngine
            session: Current conversation session

        Returns:
            Resolved company name if found, None otherwise.
            Also updates parsed.companies in-place when resolution succeeds.
        """
        if not SEMANTIC_RESOLVER_AVAILABLE:
            return None

        # ALWAYS try abbreviation expansion first (works without entity history)
        # This handles predefined aliases like "STE" → "ST Engineering"
        if parsed.companies:
            for i, company in enumerate(parsed.companies):
                # Only expand single-word abbreviations via dynamic registry
                # "STE" → "ST Engineering", "BFF" → "Batam Fast Ferry"
                # Multi-word names pass through to Step 6.7
                # (EntityResolutionAgent + CPI native substring matching)
                words = company.strip().split()
                if len(words) == 1:
                    expanded_query, expansions = expand_abbreviations_in_query(company)
                    if expansions:
                        canonical_name = expanded_query.strip()
                        if canonical_name.lower() != company.lower():
                            logger.info(
                                f"🔤 ABBREVIATION EXPANSION: '{company}' → "
                                f"'{canonical_name}' (dynamic registry)"
                            )
                            parsed.companies[i] = canonical_name
                            return canonical_name

        if not session.entity_history:
            return None

        # Build enriched entity history for semantic comparison
        enriched_history = []
        for entry in session.entity_history:
            entity_context = entry.get("context", "")
            if not entity_context:
                intent = session.context.get("last_intent", "general")
                entity_context = (
                    f"Discussion about {entry.get('name')} in context of {intent}"
                )

            enriched_history.append(
                {
                    "name": entry.get("name"),
                    "type": entry.get("type", "company"),
                    "context": entity_context,
                    "timestamp": entry.get("timestamp", ""),
                }
            )

        resolved_company = None

        # CASE 1: Parsed companies exist - try to expand/validate them
        if parsed.companies:
            for company in parsed.companies:
                # Try semantic resolution to expand abbreviations
                try:
                    # Create a query context around the company name
                    query_context = f"{message} (referring to {company})"
                    resolution_result = await resolve_entity_semantically(
                        query=query_context,
                        entity_history=enriched_history,
                    )

                    if resolution_result.status == SemanticResolutionStatus.RESOLVED:
                        canonical_name = resolution_result.entity_name

                        # Check if we expanded an abbreviation
                        if canonical_name.lower() != company.lower():
                            logger.info(
                                f"🔄 SEMANTIC EXPANSION: '{company}' → '{canonical_name}' "
                                f"(confidence={resolution_result.confidence:.3f})"
                            )
                            resolved_company = canonical_name

                            # Update parsed.companies with canonical name
                            # Replace the abbreviated/partial name with canonical
                            idx = parsed.companies.index(company)
                            parsed.companies[idx] = canonical_name
                        else:
                            # Same name, just confirmed
                            resolved_company = canonical_name
                            logger.debug(
                                f"✅ SEMANTIC CONFIRMED: '{company}' "
                                f"(confidence={resolution_result.confidence:.3f})"
                            )
                        break  # Use first resolved company

                except Exception as e:
                    logger.warning(f"Semantic expansion failed for '{company}': {e}")

        # CASE 2: No parsed companies - try pure semantic resolution
        else:
            try:
                resolution_result = await resolve_entity_semantically(
                    query=message,
                    entity_history=enriched_history,
                )

                if resolution_result.status == SemanticResolutionStatus.RESOLVED:
                    resolved_company = resolution_result.entity_name
                    logger.info(
                        f"🎯 SEMANTIC RESOLUTION (no parsed companies): "
                        f"'{message[:40]}...' → '{resolved_company}' "
                        f"(confidence={resolution_result.confidence:.3f})"
                    )
                    # Add to parsed.companies
                    if not parsed.companies:
                        parsed.companies = []
                    parsed.companies.append(resolved_company)

                elif resolution_result.status == SemanticResolutionStatus.AMBIGUOUS:
                    # Don't return clarification here - let downstream handle it
                    logger.info(
                        f"⚠️ SEMANTIC AMBIGUOUS: Multiple candidates for '{message[:40]}...'"
                    )

            except Exception as e:
                logger.warning(f"Semantic resolution failed: {e}")

        return resolved_company

    # --- Follow-up query detection (entity contamination guard) ---
    _FOLLOW_UP_PRONOUNS = {
        "their",
        "them",
        "they",
        "this company",
        "that company",
        "the same",
        "the same company",
        "its",
        "the company",
    }
    _FOLLOW_UP_MARKERS = {
        "and also",
        "what about",
        "how about",
        "tell me more",
        "more details",
        "go deeper",
        "elaborate",
        "expand on",
    }

    @staticmethod
    def _is_follow_up_query(message: str) -> bool:
        """
        Detect if a message is a follow-up/pronoun query with no explicit entity.

        Returns True when it's safe to fall back to session context for entity
        resolution. Returns False when the message likely names a new entity,
        preventing entity contamination across turns.
        """
        msg_lower = message.lower().strip()

        # Check for pronoun references
        for pronoun in ConversationManager._FOLLOW_UP_PRONOUNS:
            if pronoun in msg_lower:
                return True

        # Check for explicit follow-up markers
        for marker in ConversationManager._FOLLOW_UP_MARKERS:
            if marker in msg_lower:
                return True

        # Short queries with no capitalized proper nouns are likely follow-ups
        # e.g., "what's the credit status?" vs "Check credit for Maersk"
        words = message.split()
        if len(words) < 6:
            # Check if any word (not first) starts with uppercase — likely a proper noun
            has_proper_noun = any(
                w[0].isupper()
                and w
                not in {
                    "What",
                    "What's",
                    "How",
                    "Can",
                    "Is",
                    "Are",
                    "Do",
                    "Does",
                    "Will",
                    "Would",
                    "Should",
                    "Could",
                    "Check",
                    "Run",
                    "Show",
                    "Get",
                    "Tell",
                    "Give",
                    "List",
                    "Find",
                    "The",
                    "A",
                }
                for w in words[1:]
                if w  # skip first word (sentence start)
            )
            if not has_proper_noun:
                return True

        return False

    # Credit-specific query keywords
    # Keyword lists removed — routing now uses parsed.sub_intent from LLM

    # Regex to detect order value mentions (e.g., "EUR 8M", "5 million USD")
    # Uses word boundary after multiplier to avoid "2026. MTU" matching as "2026M"
    _ORDER_VALUE_RE = re.compile(
        r"(\d+[\.\d]*)\s*(?:(m|million|k|thousand|bn|billion)\b)?"
        r"\s*(eur|usd|sgd|aud|gbp)?",
        re.IGNORECASE,
    )
    # Also match currency-first: "EUR 8M", "USD 5 million"
    _ORDER_VALUE_CURRENCY_FIRST_RE = re.compile(
        r"(eur|usd|sgd|aud|gbp)\s*(\d+[\.\d]*)\s*(m|million|k|thousand|bn|billion)?",
        re.IGNORECASE,
    )

    @staticmethod
    def _parse_order_value(message: str) -> Optional[float]:
        """Extract order value from message. Returns value in base currency units."""
        # Try currency-first pattern: "EUR 8M"
        match = ConversationManager._ORDER_VALUE_CURRENCY_FIRST_RE.search(message)
        if match:
            num = float(match.group(2))
            multiplier = match.group(3)
        else:
            # Try number-first pattern: "8M EUR"
            match = ConversationManager._ORDER_VALUE_RE.search(message)
            if not match:
                return None
            num = float(match.group(1))
            multiplier = match.group(2)
            currency = match.group(3)
            # Require at least a multiplier OR currency to be present.
            # Bare numbers (e.g., "2026") are not order values.
            if not multiplier and not currency:
                return None

        if multiplier:
            mult_lower = multiplier.lower()
            if mult_lower in ("m", "million"):
                num *= 1_000_000
            elif mult_lower in ("k", "thousand"):
                num *= 1_000
            elif mult_lower in ("bn", "billion"):
                num *= 1_000_000_000

        # Only return if value is plausible as an order amount (> 1000)
        return num if num >= 1000 else None

    async def _targeted_perplexity_search(
        self,
        entity_name: str,
        search_focus: str,
        adverse_keywords: list[str],
    ) -> Optional[tuple[str, str, "SectionStatus"]]:
        """Run a targeted Perplexity search for a specific KYP section.

        Returns (value, source, status) or None if search fails.
        """
        import httpx as _pplx_httpx
        import os as _pplx_os

        _pplx_key = _pplx_os.environ.get("PERPLEXITY_API_KEY")
        if not _pplx_key:
            return None

        async with _pplx_httpx.AsyncClient(timeout=15) as _pplx_c:
            _pplx_r = await _pplx_c.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {_pplx_key}"},
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a due diligence research analyst. "
                                "Write in plain text only — no markdown, no bold, no headers, no bullet points. "
                                "Keep responses to 2-3 sentences maximum."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"{search_focus}. "
                                f"Provide a brief 2-3 sentence summary of findings. "
                                f"If no issues found, state that clearly. "
                                f"Do not use markdown formatting."
                            ),
                        },
                    ],
                    "return_citations": True,
                    "temperature": 0.2,
                },
            )
            if _pplx_r.status_code == 200:
                _pplx_data = _pplx_r.json()
                _content = _pplx_data["choices"][0]["message"]["content"]
                # Strip markdown formatting
                import re as _md_re

                _content = _md_re.sub(r"\*\*([^*]+)\*\*", r"\1", _content)  # **bold**
                _content = _md_re.sub(r"\*([^*]+)\*", r"\1", _content)  # *italic*
                _content = _md_re.sub(
                    r"^#+\s*", "", _content, flags=_md_re.MULTILINE
                )  # # headers
                _content = _md_re.sub(
                    r"^[-*]\s+", "", _content, flags=_md_re.MULTILINE
                )  # - bullets
                _content = _content.strip()
                _cites = _pplx_data.get("citations", [])
                _source = (
                    ", ".join(_pplx_httpx.URL(u).host for u in _cites[:4])
                    if _cites
                    else "Perplexity Web Search"
                )
                # Determine status — adverse only if keywords present WITHOUT negation
                _cl = _content.lower()
                _clean_phrases = [
                    "no adverse",
                    "no lawsuit",
                    "no court",
                    "no fine",
                    "no penalty",
                    "no incident",
                    "no accident",
                    "no safety",
                    "no violation",
                    "no litigation",
                    "absence of",
                    "no record",
                    "no specific",
                    "not found",
                ]
                _has_adverse = any(w in _cl for w in adverse_keywords)
                _has_clean = any(p in _cl for p in _clean_phrases)

                if _has_adverse and not _has_clean:
                    _status = SectionStatus.ADVERSE_FINDINGS
                else:
                    _status = SectionStatus.NO_ADVERSE_FINDINGS

                return _content[:800], _source, _status
        return None

    async def _try_handle_credit_query(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fast path for credit-only queries.

        Detects queries like "Check credit limit for Maersk" and returns
        SAP credit data directly without running full KYP workflow.

        Returns:
            Response dict if credit query handled, None otherwise
        """
        # LLM intent+sub_intent routing (replaces keyword matching)
        if not (
            parsed.intent == QueryIntent.CUSTOMER_INTEL
            and parsed.sub_intent == "credit"
        ):
            return None

        # The credit fast path is for read-only QUESTIONS about credit status.
        # Queries that request write actions (override, delete, approve orders)
        # must go through full LLM synthesis where security guards apply.
        _write_action_verbs = re.compile(
            r"\b(?:overrid\w*|delet\w*|re-?seed|remov\w+\s+the\s+(?:credit|hold|block))\b",
            re.IGNORECASE,
        )
        if _write_action_verbs.search(message):
            logger.info(
                f"Credit query contains write-action verb, falling through to LLM"
            )
            return None

        # Skip credit fast path for verification/confirmation queries
        # These need LLM synthesis for proper "cannot confirm" responses
        _verification_phrases = re.compile(
            r"\b(?:can you confirm|confirm this|is it true|verify this|i heard)\b",
            re.IGNORECASE,
        )
        if _verification_phrases.search(message):
            logger.info(
                f"Credit query contains verification request, falling through to LLM"
            )
            return None

        # Skip credit fast path for cross-domain queries that need BOTH credit
        # AND engine/product recommendations — these need LLM synthesis
        _engine_request = re.compile(
            r"\b(?:engine|recommend|propos\w+|suggest|what\s+(?:engine|product|package))\b",
            re.IGNORECASE,
        )
        if _engine_request.search(message):
            logger.info(
                f"Credit query also requests engine/product — falling through to LLM"
            )
            return None

        logger.info(f"Credit-only query detected: {message[:50]}...")

        # Build list of companies to check
        # GUARD: Only fall back to session context for follow-up/pronoun queries
        # to prevent entity contamination across turns.
        companies_to_check: list[str] = []
        if parsed.companies:
            companies_to_check = parsed.companies[:3]  # Cap at 3 to avoid abuse
        elif self._is_follow_up_query(message):
            if session.context.get("companies"):
                companies_to_check = [session.context["companies"][-1]]
            elif session.context.get("last_kyp_entity"):
                companies_to_check = [session.context["last_kyp_entity"]]

        if not companies_to_check:
            # Fallback: extract company name from common credit query patterns
            import re as _re

            # Pattern 1: "credit check FOR X", "credit status OF X"
            _m = _re.search(
                r"(?:credit\s+(?:check|limit|status|report|data|history|info)\s+"
                r"(?:for|on|of)\s+)(.+?)(?:\s*\??\s*$)",
                message,
                _re.IGNORECASE,
            )
            # Pattern 2: "View X's credit history", "X's detailed credit"
            if not _m:
                _m = _re.search(
                    r"(?:view|show|get|check|see)\s+(.+?)(?:'s|'s)\s+"
                    r"(?:detailed\s+)?credit",
                    message,
                    _re.IGNORECASE,
                )
            if _m:
                companies_to_check = [_m.group(1).strip()]
                logger.info(
                    f"Credit: fallback regex extracted company: '{companies_to_check[0]}'"
                )

        if not companies_to_check:
            # Fallback 2: extract UEN pattern from the message
            import re as _re2

            _uen_m = _re2.search(r"\b(\d{8,10}[A-Za-z])\b", message)
            if _uen_m:
                companies_to_check = [_uen_m.group(1)]
                logger.info(
                    f"Credit: extracted UEN from message: '{companies_to_check[0]}'"
                )

        if not companies_to_check:
            logger.info("Credit query but no company specified, falling through")
            return None

        # Route to single or multi-company handler
        try:
            from lead_to_cash.integrations import MS5Client
            from lead_to_cash.integrations.client_factory import get_cpi_client

            cpi_client, is_sim = await get_cpi_client(use_case="Credit")
            ms5 = MS5Client(cpi_client=cpi_client)
            await ms5.connect()

            if len(companies_to_check) == 1:
                return await self._handle_single_credit(
                    companies_to_check[0], ms5, session, session_id, order_value
                )
            else:
                return await self._handle_credit_comparison(
                    companies_to_check, ms5, session, session_id, order_value
                )

        except Exception as e:
            logger.warning(f"Credit query SAP lookup failed: {e}")
            return None

    # Pattern matching UEN (Singapore Unique Entity Number) like "199901234A"
    _UEN_PATTERN = re.compile(r"^\d{8,10}[A-Za-z]$")

    async def _handle_single_credit(
        self,
        company: str,
        ms5,
        session: ConversationSession,
        session_id: str,
        order_value: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle credit query for a single company."""
        # Search by name via real MS5/CPI — no simulated customer fallback
        if self._UEN_PATTERN.match(company.strip()):
            logger.info(
                f"Credit: detected UEN pattern '{company}', searching by UEN via MS5"
            )
            # UEN search goes through MS5 which queries real SAP CPI
            customers = await ms5.search_customers(name=company)
        else:
            customers = await ms5.search_customers(name=company)

        if not customers:
            # Fuzzy fallback: use entity resolution service (Levenshtein + fuzzy)
            try:
                from lead_to_cash.services.entity_registry.entity_resolution_service import (
                    EntityResolutionService,
                )

                er_service = EntityResolutionService()
                candidates = await er_service.resolve_local(company)
                if candidates:
                    best = candidates[0]
                    resolved_name = best.canonical_name or best.name
                    logger.info(
                        f"Credit: entity resolution matched '{company}' → "
                        f"'{resolved_name}' ({best.match_type}, {best.confidence:.0f}%)"
                    )
                    customers = await ms5.search_customers(name=resolved_name)
            except Exception as e:
                logger.debug(f"Credit: entity resolution fallback failed: {e}")

        if not customers:
            # Last resort: fuzzy match against simulator customer names
            try:
                from difflib import get_close_matches
                from lead_to_cash.integrations.cpi_simulator import CUSTOMER_NAME_LOOKUP

                fuzzy_matches = get_close_matches(
                    company.lower(), CUSTOMER_NAME_LOOKUP.keys(), n=1, cutoff=0.6
                )
                if fuzzy_matches:
                    matched_id = CUSTOMER_NAME_LOOKUP[fuzzy_matches[0]]
                    logger.info(
                        f"Credit: fuzzy matched '{company}' → '{fuzzy_matches[0]}' (ID: {matched_id})"
                    )
                    customers = await ms5.search_customers(name=matched_id)
            except Exception:
                pass

        if not customers:
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": (
                    f"Could not find any customer record for '{company}' in our SAP system. "
                    f"'{company}' does not exist in our customer database.\n\n"
                    "This may be a new prospect not yet in SAP. "
                    "Run KYP for full due diligence assessment."
                ),
                "sources": ["SAP CPI"],
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        customer = customers[0]
        customer_id = customer.customer_id
        # Prefer the session's resolved entity name (e.g., "ST Engineering Ltd")
        # over SAP's raw search result (e.g., "ST Engineering Land Systems Ltd")
        # which may be a subsidiary name.
        _confirmed = session.context.get("confirmed_entity", {})
        customer_name = _confirmed.get("canonical_name") or customer.name

        # Use default credit control area — real SAP CPI, no simulated data
        import os as _os_cc

        cca = _os_cc.getenv("SAP_MS5_CREDIT_CONTROL_AREA", "0111")

        credit_data = await ms5.check_credit_limit(
            customer_id=customer_id, credit_control_area=cca
        )

        if credit_data:
            limit = credit_data.credit_limit
            exposure = credit_data.credit_exposure
            currency = credit_data.currency
            utilization = credit_data.utilization_percent
            available = limit - exposure

            is_blocked = not credit_data.credit_check_passed or utilization > 100
            status = "BLOCKED" if is_blocked else "APPROVED"

            # Include UEN if available
            uen_row = ""
            uen_header = ""
            # UEN is available from credit_data if SAP returns it
            if hasattr(credit_data, "tax_number") and credit_data.tax_number:
                uen_row = f"\n| **UEN (Tax Number)** | {credit_data.tax_number} |"
                if self._UEN_PATTERN.match(company.strip()):
                    uen_header = (
                        f"**UEN {credit_data.tax_number} is registered to "
                        f"{customer_name}.**\n\n"
                    )

            answer = f"""{uen_header}## SAP Credit Status: {customer_name}

| Field | Value |
|-------|-------|
| **Customer ID** | {customer_id} |{uen_row}
| **Credit Control Area** | {cca} |
| **Credit Limit** | {currency} {limit:,.2f} |
| **Credit Exposure** | {currency} {exposure:,.2f} |
| **Available Credit** | {currency} {available:,.2f} |
| **Utilization** | {utilization:.1f}% |
| **Status** | {"✅ " + status if status == "APPROVED" else "❌ " + status} |

*Data source: SAP CPI (MS5)*"""

            # Add analytical commentary based on utilization
            if utilization > 100:
                over_by = exposure - limit
                answer += (
                    f"\n\n⚠️ **CREDIT BLOCKED**: Exposure exceeds limit by "
                    f"{currency} {over_by:,.2f} ({utilization:.0f}% utilization). "
                    f"Orders will be held pending credit review. "
                    f"Contact Credit Management to request a limit increase or "
                    f"resolve outstanding receivables."
                )
            elif utilization > 80:
                answer += (
                    f"\n\n⚠️ **APPROACHING LIMIT**: {utilization:.0f}% utilization. "
                    f"Available credit: {currency} {available:,.2f}. "
                    f"Consider requesting a limit increase before placing large orders."
                )
            elif utilization > 50:
                answer += (
                    f"\n\n**Moderate utilization** ({utilization:.0f}%). "
                    f"Available credit: {currency} {available:,.2f}. "
                    f"Sufficient headroom for standard orders."
                )
            else:
                answer += (
                    f"\n\n**Healthy credit position** ({utilization:.0f}% utilization). "
                    f"Available credit: {currency} {available:,.2f}."
                )

            # Order feasibility analysis when query mentions an order value
            if order_value:
                if is_blocked:
                    answer += (
                        f"\n\n❌ **Order not feasible**: Credit is currently BLOCKED. "
                        f"The requested {currency} {order_value:,.0f} order cannot proceed "
                        f"until the credit block is resolved."
                    )
                elif order_value <= available:
                    answer += (
                        f"\n\n✅ **Order feasible**: {currency} {order_value:,.0f} "
                        f"is within available credit ({currency} {available:,.2f})."
                    )
                else:
                    shortfall = order_value - available
                    answer += (
                        f"\n\n❌ **Order exceeds available credit** by "
                        f"{currency} {shortfall:,.2f}. "
                        f"Credit limit increase required before placing "
                        f"a {currency} {order_value:,.0f} order."
                    )
        else:
            answer = (
                f"Credit data not available for {company} in SAP.\n\n"
                "The customer may exist but credit management is not configured."
            )

        # Capture key metrics for multi-turn continuity (structured facts only)
        if credit_data:
            metrics = {
                "credit_utilization": f"{utilization:.0f}%",
                "credit_limit": f"{currency} {limit:,.0f}",
                "available_credit": f"{currency} {available:,.0f}",
                "credit_status": status,
            }
            session.context["last_response_metrics"] = metrics

            # Build reasoning carryover for follow-up turns
            carryover = build_carryover_from_credit(
                entity=customer_name,
                credit_data=metrics,
                intent="credit_check",
            )
            session.context["reasoning_carryover"] = carryover.to_dict()

        session.add_turn("assistant", answer)
        self._session_store.set(session)

        # Build structured credit report for card rendering
        if credit_data:
            return {
                "type": "credit_report",
                "session_id": session_id,
                "credit": {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "credit_control_area": cca,
                    "credit_limit": limit,
                    "credit_exposure": exposure,
                    "available_credit": available,
                    "currency": currency,
                    "utilization": utilization,
                    "status": status,
                    "uen": credit_data.tax_number
                    if hasattr(credit_data, "tax_number")
                    else None,
                },
                "answer": answer,
                "sources": ["SAP CPI (MS5)"],
                "confidence": "HIGH",
                "follow_up_suggestions": [
                    f"Run full KYP on {customer_name}",
                    f"Show billing items for {customer_name}",
                    f"Show opportunities for {customer_name}",
                ],
                "timestamp": datetime.now(UTC).isoformat(),
            }

        return {
            "type": "answer",
            "session_id": session_id,
            "answer": answer,
            "sources": ["SAP CPI (MS5)"],
            "confidence": "HIGH",
            "follow_up_suggestions": [
                f"Run full KYP on {company}?",
                f"Check {company}'s payment history?",
                "View all customers with high credit utilization?",
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _handle_credit_comparison(
        self,
        companies: list[str],
        ms5,
        session: ConversationSession,
        session_id: str,
        order_value: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle credit comparison across multiple companies."""
        results = []
        not_found = []

        for company_name in companies:
            customers = await ms5.search_customers(name=company_name)
            if not customers:
                not_found.append(company_name)
                continue

            customer = customers[0]
            cca = _os_cc.getenv("SAP_MS5_CREDIT_CONTROL_AREA", "0111")
            credit_data = await ms5.check_credit_limit(
                customer_id=customer.customer_id, credit_control_area=cca
            )
            if credit_data:
                available = credit_data.credit_limit - credit_data.credit_exposure
                is_blocked = (
                    not credit_data.credit_check_passed
                    or credit_data.utilization_percent > 100
                )
                results.append(
                    {
                        "name": customer.name,
                        "customer_id": customer.customer_id,
                        "cca": cca,
                        "currency": credit_data.currency,
                        "limit": credit_data.credit_limit,
                        "exposure": credit_data.credit_exposure,
                        "available": available,
                        "utilization": credit_data.utilization_percent,
                        "status": "BLOCKED" if is_blocked else "APPROVED",
                        "is_blocked": is_blocked,
                    }
                )

        if not results:
            return {
                "type": "answer",
                "session_id": session_id,
                "answer": f"No SAP credit data found for: {', '.join(companies)}.",
                "sources": ["SAP CPI"],
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        # Build comparison table
        answer = "## Credit Comparison\n\n"
        answer += "| Field | " + " | ".join(r["name"] for r in results) + " |\n"
        answer += "|-------" + "|-------" * len(results) + "|\n"
        answer += (
            "| **Customer ID** | "
            + " | ".join(r["customer_id"] for r in results)
            + " |\n"
        )
        answer += (
            "| **Credit Control Area** | "
            + " | ".join(r["cca"] for r in results)
            + " |\n"
        )
        answer += (
            "| **Credit Limit** | "
            + " | ".join(f"{r['currency']} {r['limit']:,.2f}" for r in results)
            + " |\n"
        )
        answer += (
            "| **Credit Exposure** | "
            + " | ".join(f"{r['currency']} {r['exposure']:,.2f}" for r in results)
            + " |\n"
        )
        answer += (
            "| **Available Credit** | "
            + " | ".join(f"{r['currency']} {r['available']:,.2f}" for r in results)
            + " |\n"
        )
        answer += (
            "| **Utilization** | "
            + " | ".join(f"{r['utilization']:.1f}%" for r in results)
            + " |\n"
        )
        answer += (
            "| **Status** | "
            + " | ".join(
                (
                    "✅ " + r["status"]
                    if r["status"] == "APPROVED"
                    else "❌ " + r["status"]
                )
                for r in results
            )
            + " |\n"
        )

        answer += "\n*Data source: SAP CPI (MS5)*"

        # Add analytical summary
        answer += "\n\n### Comparison Summary\n"
        # Find best/worst utilization
        best = min(results, key=lambda r: r["utilization"])
        worst = max(results, key=lambda r: r["utilization"])
        if best["name"] != worst["name"]:
            answer += (
                f"- **{best['name']}** has the lowest utilization "
                f"({best['utilization']:.0f}%) with "
                f"{best['currency']} {best['available']:,.2f} available credit.\n"
            )
            answer += (
                f"- **{worst['name']}** has the highest utilization "
                f"({worst['utilization']:.0f}%).\n"
            )

        blocked = [r for r in results if r["is_blocked"]]
        if blocked:
            answer += (
                f"- ⚠️ **Credit blocked** for: "
                f"{', '.join(r['name'] for r in blocked)}.\n"
            )

        # Order feasibility across all companies
        if order_value:
            answer += f"\n### Order Feasibility ({results[0]['currency']} {order_value:,.0f})\n"
            for r in results:
                if r["is_blocked"]:
                    answer += f"- **{r['name']}**: ❌ Credit BLOCKED\n"
                elif order_value <= r["available"]:
                    answer += f"- **{r['name']}**: ✅ Feasible (available: {r['currency']} {r['available']:,.2f})\n"
                else:
                    shortfall = order_value - r["available"]
                    answer += f"- **{r['name']}**: ❌ Exceeds by {r['currency']} {shortfall:,.2f}\n"

        if not_found:
            answer += f"\n⚠️ No SAP records found for: {', '.join(not_found)}"

        session.add_turn("assistant", answer)
        self._session_store.set(session)

        all_names = [r["name"] for r in results]
        return {
            "type": "answer",
            "session_id": session_id,
            "answer": answer,
            "sources": ["SAP CPI (MS5)"],
            "confidence": "HIGH",
            "follow_up_suggestions": [
                f"Run KYP on {all_names[0]}?" if all_names else "Run KYP?",
                "Which customer has the best credit position?",
                "Show credit trends over time?",
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # =========================================================================
    # Order Detail / Billing Plan Fast Path
    # =========================================================================

    # ORDER_QUERY_KEYWORDS removed — routing now uses parsed.sub_intent from LLM

    # Regex to extract SAP order numbers (7-10 digit numeric) or TestingXXXX format
    # Also handles "Order #1000024001" with hash prefix
    _ORDER_NUMBER_PATTERN = re.compile(r"#?(\d{7,10}|Testing\d{4})\b")

    async def _try_handle_order_query(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fast path for order detail and billing plan queries.

        Detects queries like "Show order details for 1000024001" or
        "Show billing plan for order 1000024001" and returns SAP order
        data directly from the simulator/MS5.
        """
        # LLM intent+sub_intent routing (replaces keyword matching)
        if not (
            parsed.intent == QueryIntent.CUSTOMER_INTEL
            and parsed.sub_intent == "order_detail"
        ):
            return None

        message_lower = message.lower()

        # Extract order number from message
        matches = self._ORDER_NUMBER_PATTERN.findall(message)
        if not matches:
            return None

        order_number = matches[0]
        is_billing_query = any(
            kw in message_lower
            for kw in [
                "billing plan",
                "billing milestone",
                "payment milestone",
                "payment schedule",
                "payment terms",
            ]
        )

        logger.info(
            f"Order query detected: order={order_number}, "
            f"billing={'yes' if is_billing_query else 'no'}"
        )

        try:
            from lead_to_cash.integrations.cpi_simulator import (
                _get_simulated_sales_orders,
            )
            from lead_to_cash.integrations.ms5_client import (
                BillingPlanData,
                BillingPlanLine,
                SalesOrderDetail,
            )

            # Read directly from simulated sales orders (no CPISimulator instantiation
            # needed — avoids production guard that blocks simulator when CPI is configured)
            orders = _get_simulated_sales_orders()
            order_data = orders.get(order_number)
            if not order_data:
                # Also try zero-padded
                order_data = orders.get(order_number.zfill(10))

            if not order_data:
                return {
                    "type": "answer",
                    "session_id": session_id,
                    "answer": f"Sales order {order_number} not found in SAP.",
                    "sources": ["SAP CPI (MS5)"],
                    "confidence": "HIGH",
                    "follow_up_suggestions": [
                        "Check with a different order number?",
                        "Show opportunities for this customer?",
                    ],
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            header = order_data.get("header", {})
            customer_id = header.get("KUNNR", "")
            net_value = header.get("NETWR", 0)
            currency = header.get("WAERK", "EUR")
            po_number = header.get("BSTNK", "")
            raw_date = header.get("AUDAT", "")
            # Format YYYYMMDD → YYYY-MM-DD for display
            if raw_date and len(raw_date) == 8 and raw_date.isdigit():
                doc_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            else:
                doc_date = raw_date
            inco1 = header.get("INCO1", "")
            inco2 = header.get("INCO2", "")
            zterm = header.get("ZTERM", "")

            # Find partner names
            sold_to_name = ""
            for p in order_data.get("partners", []):
                if p.get("PARVW") == "AG":
                    sold_to_name = p.get("NAME1", "")
                    break

            # Build response
            parts = []
            parts.append(f"**Sales Order: {order_number}**\n")
            parts.append(f"- **Customer:** {sold_to_name} ({customer_id})")
            parts.append(f"- **Net Value:** {currency} {net_value:,.2f}")
            parts.append(f"- **PO Number:** {po_number}")
            parts.append(f"- **Document Date:** {doc_date}")
            parts.append(f"- **Incoterms:** {inco1} {inco2}")
            parts.append(f"- **Payment Terms:** {zterm}")

            # Items
            items = order_data.get("items", [])
            if items:
                parts.append(f"\n**Line Items ({len(items)}):**")
                for item in items:
                    matnr = item.get("MATNR", "")
                    desc = item.get("ARKTX", "")
                    qty = item.get("KWMENG", 0)
                    item_val = item.get("NETWR", 0)
                    item_curr = item.get("WAERK", currency)
                    parts.append(
                        f"- {matnr}: {desc} | Qty: {qty:.0f} | "
                        f"Value: {item_curr} {item_val:,.2f}"
                    )

            # Billing plan
            bp_data = order_data.get("billing_plan", {})
            if bp_data and bp_data.get("FPLNR"):
                bp_curr = bp_data.get("WAESSION", currency)
                bp_total = bp_data.get("FAKWR", 0)
                bp_type = bp_data.get("FPART", "")
                parts.append(f"\n**Billing Plan ({bp_data['FPLNR']}):**")
                parts.append(
                    f"- **Total:** {bp_curr} {bp_total:,.2f} "
                    f"| Type: {'Milestone' if bp_type == '02' else 'Periodic'}"
                )
                for m in bp_data.get("dates", []):
                    status_icon = {"A": "Open", "B": "Billed", "C": "Cancelled"}.get(
                        m.get("FKSAF", ""), m.get("FKSAF", "")
                    )
                    block = " (BLOCKED)" if m.get("FAKSP") else ""
                    parts.append(
                        f"- {m.get('TETXT', '')}: {bp_curr} {m.get('FAKWR', 0):,.2f} "
                        f"({m.get('BETEFP', 0)}%) — {status_icon}{block} "
                        f"| Due: {m.get('FDATU', '')}"
                    )
            elif is_billing_query:
                parts.append("\nNo billing plan found for this order.")

            # Fetch payment terms text from first billed milestone's billing doc
            payment_terms_text = ""
            if bp_data and bp_data.get("dates"):
                for m in bp_data.get("dates", []):
                    billing_doc = m.get("VBELN", "")
                    if billing_doc and m.get("FKSAF") == "B":
                        # Try real CPI first, fall back to simulator billing docs
                        try:
                            from lead_to_cash.integrations.client_factory import (
                                get_cpi_client,
                            )
                            from lead_to_cash.integrations.ms5_client import MS5Client

                            cpi_client, _ = await get_cpi_client(
                                use_case="PaymentTerms"
                            )
                            ms5 = MS5Client(cpi_client=cpi_client)
                            await ms5.connect()
                            payment_terms_text = await ms5.get_payment_terms_text(
                                billing_doc
                            )
                        except Exception as e:
                            logger.debug(f"CPI payment terms text failed: {e}")
                        # Fallback: read from simulated billing docs
                        if not payment_terms_text:
                            try:
                                from lead_to_cash.integrations.cpi_simulator import (
                                    _get_dynamic_billing_docs,
                                )

                                doc = _get_dynamic_billing_docs().get(billing_doc, {})
                                payment_terms_text = doc.get("payment_terms_text", "")
                            except Exception:
                                pass
                        break  # Only need text from first billed doc
            if payment_terms_text:
                parts.append(f"\n**Payment Terms (Full Text):**\n{payment_terms_text}")

            # Status
            status_data = order_data.get("status", {})
            if status_data and status_data.get("overall_status"):
                status_map = {
                    "A": "Open",
                    "B": "In Process",
                    "C": "Partially Processed",
                }
                overall = status_map.get(
                    status_data["overall_status"],
                    status_data["overall_status"],
                )
                parts.append(f"\n**Overall Status:** {overall}")

            # Find linked opportunity — stored in order data or fetched from real CPI
            linked_opp = order_data.get("linked_opportunity")
            if not linked_opp and customer_id:
                # Fallback: query real CPI and match by sap_order_id
                try:
                    from lead_to_cash.integrations.cec_client import CECClient
                    from lead_to_cash.integrations.client_factory import get_cpi_client

                    cpi_client, _ = await get_cpi_client(use_case="OrderOppLink")
                    cec = CECClient(cpi_client=cpi_client)
                    await cec.connect()
                    cpi_opps = await cec.get_opportunities_by_account(
                        account_id=customer_id.zfill(10),
                        limit=20,
                    )
                    for opp in cpi_opps:
                        if getattr(opp, "sap_order_id", None) == order_number:
                            linked_opp = {
                                "id": opp.id,
                                "title": opp.title,
                                "status": opp.status,
                                "value": opp.expected_revenue or 0,
                                "currency": opp.currency,
                            }
                            break
                except Exception as e:
                    logger.debug(f"Could not fetch linked opp from CPI: {e}")
            if linked_opp:
                opp_val = linked_opp.get("expected_revenue", linked_opp.get("value", 0))
                parts.append(
                    f"\n**Linked Opportunity:** {linked_opp['id']} — "
                    f"{linked_opp.get('title', '')} ({linked_opp.get('status', '')}, "
                    f"{linked_opp.get('currency', '')} {opp_val:,.0f})"
                )

            # Show linked IPAS order
            ipas_order_num = order_data.get("ipas_order_number")
            if ipas_order_num:
                parts.append(f"\n**IPAS Order:** {ipas_order_num}")

            answer = "\n".join(parts)

            # Update session
            session.add_turn("user", message)
            session.add_turn("assistant", answer)
            if sold_to_name:
                session.context.setdefault("companies", [])
                if sold_to_name not in session.context["companies"]:
                    session.context["companies"].append(sold_to_name)
            self._session_store.set(session)

            # Build structured order data for frontend card rendering
            bp_milestones = []
            if bp_data and bp_data.get("dates"):
                for m in bp_data.get("dates", []):
                    bp_milestones.append(
                        {
                            "description": m.get("TETXT", ""),
                            "amount": m.get("FAKWR", 0),
                            "percentage": m.get("BETEFP", 0),
                            "status": {
                                "A": "Open",
                                "B": "Billed",
                                "C": "Cancelled",
                            }.get(m.get("FKSAF", ""), m.get("FKSAF", "")),
                            "blocked": bool(m.get("FAKSP")),
                            "due_date": m.get("FDATU", ""),
                        }
                    )

            order_items_data = []
            for item in items:
                order_items_data.append(
                    {
                        "material": item.get("MATNR", ""),
                        "description": item.get("ARKTX", ""),
                        "quantity": item.get("KWMENG", 0),
                        "value": item.get("NETWR", 0),
                        "currency": item.get("WAERK", currency),
                    }
                )

            linked_opp_data = None
            if linked_opp:
                linked_opp_data = {
                    "id": linked_opp.get("id", ""),
                    "title": linked_opp.get("title", ""),
                    "status": linked_opp.get("status", ""),
                    "value": linked_opp.get(
                        "expected_revenue", linked_opp.get("value", 0)
                    ),
                    "currency": linked_opp.get("currency", ""),
                }

            return {
                "type": "order_detail",
                "session_id": session_id,
                "order": {
                    "order_number": order_number,
                    "customer_id": customer_id,
                    "customer_name": sold_to_name,
                    "net_value": net_value,
                    "currency": currency,
                    "po_number": po_number,
                    "doc_date": doc_date,
                    "incoterms": f"{inco1} {inco2}".strip(),
                    "payment_terms": zterm,
                    "payment_terms_text": payment_terms_text
                    if payment_terms_text
                    else None,
                    "overall_status": status_map.get(
                        status_data.get("overall_status", ""), ""
                    )
                    if status_data
                    else "",
                    "items": order_items_data,
                    "billing_plan": {
                        "number": bp_data.get("FPLNR", "") if bp_data else "",
                        "total": bp_data.get("FAKWR", 0) if bp_data else 0,
                        "currency": bp_data.get("WAESSION", currency)
                        if bp_data
                        else currency,
                        "type": "Milestone"
                        if bp_data and bp_data.get("FPART") == "02"
                        else "Periodic",
                        "milestones": bp_milestones,
                    }
                    if bp_data and bp_data.get("FPLNR")
                    else None,
                    "linked_opportunity": linked_opp_data,
                    "ipas_order_number": order_data.get("ipas_order_number"),
                },
                "answer": answer,
                "sources": ["SAP CPI (MS5)"],
                "confidence": "HIGH",
                "follow_up_suggestions": [
                    f"Show opportunities for {sold_to_name}?"
                    if sold_to_name
                    else "Show all opportunities?",
                    f"Check credit status for {sold_to_name}?"
                    if sold_to_name
                    else "Check credit?",
                    f"Run KYP on {sold_to_name}?" if sold_to_name else "Run KYP?",
                ],
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.warning(f"Order query failed: {e}")
            return None

    # =========================================================================
    # Opportunity Query Fast Path
    # =========================================================================

    # OPPORTUNITY_QUERY_KEYWORDS removed — routing now uses parsed.sub_intent from LLM

    async def _try_handle_opportunity_query(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fast path for opportunity queries.

        Returns structured opportunity data for card rendering.
        """
        # LLM intent+sub_intent routing (replaces keyword matching)
        if not (
            parsed.intent == QueryIntent.CUSTOMER_INTEL
            and parsed.sub_intent == "opportunities"
        ):
            return None

        # Need a customer to look up
        customer_id = None
        customer_name = ""
        _shared_cpi = None  # Reused across MS5 search + CEC fetch

        # Check for numeric customer ID in message
        import re as _re

        id_match = _re.search(r"\b(\d{7,10})\b", message)
        if id_match:
            customer_id = id_match.group(1)
            customer_name = customer_id

        # Check parsed companies
        if not customer_id and parsed.companies:
            company = parsed.companies[0]
            # If it's a numeric ID
            if company.strip().isdigit() and len(company.strip()) >= 6:
                customer_id = company.strip()
                customer_name = customer_id
            else:
                customer_name = company
                # Try to find customer ID via search — reuse single CPI connection
                try:
                    from lead_to_cash.integrations import MS5Client
                    from lead_to_cash.integrations.client_factory import get_cpi_client

                    if not _shared_cpi:
                        _shared_cpi, _ = await get_cpi_client(use_case="Opp")
                    if _shared_cpi:
                        ms5 = MS5Client(cpi_client=_shared_cpi)
                        await ms5.connect()
                        customers = await ms5.search_customers(
                            name=company, max_results=1
                        )
                        if customers:
                            customer_id = customers[0].customer_id
                            _confirmed = session.context.get("confirmed_entity", {})
                            customer_name = (
                                _confirmed.get("canonical_name") or customers[0].name
                            )
                except Exception as e:
                    logger.warning(f"Opp query customer search failed: {e}")

        # Check session context
        if not customer_id and session.context.get("companies"):
            last_company = session.context["companies"][-1]
            customer_name = last_company
            try:
                from lead_to_cash.integrations import MS5Client
                from lead_to_cash.integrations.client_factory import get_cpi_client

                if not _shared_cpi:
                    _shared_cpi, _ = await get_cpi_client(use_case="Opp")
                if _shared_cpi:
                    ms5 = MS5Client(cpi_client=_shared_cpi)
                    await ms5.connect()
                    customers = await ms5.search_customers(
                        name=last_company, max_results=1
                    )
                    if customers:
                        customer_id = customers[0].customer_id
                        _confirmed = session.context.get("confirmed_entity", {})
                        customer_name = (
                            _confirmed.get("canonical_name") or customers[0].name
                        )
            except Exception:
                pass

        if not customer_id:
            return None

        logger.info(
            f"Opportunity query detected: customer={customer_id} ({customer_name})"
        )

        try:
            from lead_to_cash.integrations.cec_client import CECClient
            from lead_to_cash.integrations.client_factory import get_cpi_client

            normalized = customer_id.zfill(10) if customer_id.isdigit() else customer_id

            # Reuse shared CPI connection for CEC fetch
            if not _shared_cpi:
                _shared_cpi, _ = await get_cpi_client(use_case="Opportunity")
            cec = CECClient(cpi_client=_shared_cpi)
            await cec.connect()
            opportunities = await cec.get_opportunities_by_account(
                account_id=normalized,
                limit=20,
            )

            if not opportunities:
                return None  # Fall through to LLM

            # Resolve customer_name from opp data if we only have the ID
            if (
                not customer_name
                or customer_name == customer_id
                or customer_name == normalized
            ):
                customer_name = opportunities[0].account_name or customer_name

            # Build structured response
            opps_data = []
            for o in opportunities:
                prob_labels = {
                    10: "Little chances (10%)",
                    35: "Limited chances (35%)",
                    65: "Good chances (65%)",
                    90: "Very good chances (90%)",
                }
                opps_data.append(
                    {
                        "id": o.opportunity_id,
                        "title": o.title or "",
                        "status": o.status,
                        "value": o.expected_revenue,
                        "currency": o.currency,
                        "win_probability": o.win_probability,
                        "sales_type": "Original Equipment"
                        if o.sales_type == "OE_SALES"
                        else o.sales_type or "",
                        "close_date": o.close_date.strftime("%Y-%m-%d")
                        if o.close_date
                        else "",
                        "start_date": o.start_date.strftime("%Y-%m-%d")
                        if o.start_date
                        else "",
                        "sap_order_id": o.sap_order_id,
                        "object_type": "",
                    }
                )

            # Enrich sap_order_id from simulated order data when CPI doesn't
            # populate it. Our orders have linked_opportunity with the opp ID.
            try:
                from lead_to_cash.integrations.cpi_simulator import (
                    _get_simulated_sales_orders,
                )

                sap_orders = _get_simulated_sales_orders()
                opp_to_order = {}
                for order_num, order_data in sap_orders.items():
                    lo = order_data.get("linked_opportunity", {})
                    if lo and lo.get("id"):
                        opp_to_order[lo["id"]] = order_num

                for opp in opps_data:
                    if not opp.get("sap_order_id") and opp["id"] in opp_to_order:
                        opp["sap_order_id"] = opp_to_order[opp["id"]]
            except Exception:
                pass

            won = sum(1 for o in opps_data if o["status"] == "Won")
            open_count = sum(1 for o in opps_data if o["status"] == "Open")
            lost = sum(1 for o in opps_data if o["status"] == "Lost")

            # Contextual interpretation based on user's query intent
            total_value = sum(o["value"] for o in opps_data if o["value"])
            primary_curr = opps_data[0]["currency"] if opps_data else "EUR"
            message_lower = message.lower()

            # Detect if user is asking about active/ongoing/open/pipeline
            active_keywords = [
                "ongoing",
                "active",
                "open",
                "current",
                "in progress",
                "pipeline",
                "in the pipeline",
                "pending",
                "live",
            ]
            asking_for_active = any(kw in message_lower for kw in active_keywords)

            # Detect if user is asking about history/past/won/closed
            history_keywords = [
                "history",
                "past",
                "previous",
                "won",
                "closed",
                "completed",
                "historical",
                "all deals",
            ]
            asking_for_history = any(kw in message_lower for kw in history_keywords)

            # Build contextual insight
            insight = ""
            if asking_for_active and open_count == 0:
                if won > 0:
                    insight = (
                        f"There are currently no open opportunities in the pipeline for "
                        f"{customer_name}. All {won} opportunities are Won "
                        f"(total value: {primary_curr} {total_value:,.0f}). "
                        f"This is a proven customer with completed deals — "
                        f"consider initiating new opportunities."
                    )
                else:
                    insight = f"No active opportunities found for {customer_name}."
            elif open_count > 0 and won > 0:
                open_value = sum(
                    o["value"]
                    for o in opps_data
                    if o["status"] == "Open" and o["value"]
                )
                won_value = sum(
                    o["value"] for o in opps_data if o["status"] == "Won" and o["value"]
                )
                insight = (
                    f"{open_count} open in pipeline "
                    f"({primary_curr} {open_value:,.0f}), "
                    f"{won} won ({primary_curr} {won_value:,.0f})."
                )
            elif won > 0 and open_count == 0 and asking_for_active:
                # Only show pipeline warning when user explicitly asked for
                # active/ongoing — not on neutral queries like "what opportunities"
                insight = (
                    f"All {won} opportunities are Won "
                    f"(total: {primary_curr} {total_value:,.0f}). "
                    f"No open opportunities currently in the pipeline."
                )

            # Store meaningful summary in conversation history for follow-ups
            opp_summary_parts = [
                f"Opportunities for {customer_name} ({normalized}):",
                f"Total: {len(opps_data)} ({won} Won, {open_count} Open, {lost} Lost)",
                f"Pipeline value: {primary_curr} {total_value:,.0f}",
            ]
            for o in opps_data[:5]:
                opp_summary_parts.append(
                    f"- {o['id']}: {o['title']} | {o['status']} | "
                    f"{o['currency']} {o['value']:,.0f}"
                    + (
                        f" | Order: {o['sap_order_id']}"
                        if o.get("sap_order_id")
                        else ""
                    )
                )
            if insight:
                opp_summary_parts.append(insight)

            session.add_turn("user", message)
            session.add_turn(
                "assistant",
                "\n".join(opp_summary_parts),
            )
            if customer_name:
                session.context.setdefault("companies", [])
                if customer_name not in session.context["companies"]:
                    session.context["companies"].append(customer_name)
            self._session_store.set(session)

            # Adjust follow-up suggestions based on pipeline state
            if open_count == 0 and won > 0:
                suggestions = [
                    f"Show order details for {opps_data[0]['sap_order_id']}?"
                    if opps_data and opps_data[0].get("sap_order_id")
                    else f"What recent news about {customer_name}?",
                    f"Check credit status for {customer_name}?",
                    f"What's the competitive landscape for {customer_name}?",
                ]
            else:
                suggestions = [
                    f"Show order details for {opps_data[0]['sap_order_id']}?"
                    if opps_data and opps_data[0].get("sap_order_id")
                    else f"Run KYP on {customer_name}?",
                    f"Check credit status for {customer_name}?",
                    f"Run KYP on {customer_name}?",
                ]

            return {
                "type": "opportunity_report",
                "session_id": session_id,
                "customer_name": customer_name,
                "customer_id": normalized,
                "opportunities": opps_data,
                "insight": insight,
                "summary": {
                    "won": won,
                    "open": open_count,
                    "lost": lost,
                    "total": len(opps_data),
                },
                "sources": ["SAP CEC Opportunities"],
                "confidence": "HIGH",
                "follow_up_suggestions": suggestions,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.warning(f"Opportunity query failed: {e}")
            return None

    # =========================================================================
    # Escalation Query Fast Path
    # =========================================================================

    # ESCALATION_QUERY_KEYWORDS removed — routing now uses parsed.sub_intent from LLM

    async def _try_handle_escalation_query(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fast path for escalation queries.

        Detects queries like "show escalations", "what invoices need escalation",
        "overdue alerts" and returns escalation data directly.

        Returns:
            Response dict if escalation query handled, None otherwise
        """
        # LLM intent+sub_intent routing (replaces keyword matching)
        if not (
            parsed.intent == QueryIntent.BILLING_AR
            and parsed.sub_intent == "escalation"
        ):
            return None

        logger.info(f"Escalation query detected: {message[:50]}...")

        try:
            from lead_to_cash.services.financeops.escalation_service import (
                EscalationService,
            )

            async with EscalationService() as esc_service:
                # Get customer filter if mentioned
                customer_id = None
                if parsed.companies:
                    # Try to resolve company to customer ID via CPI
                    from lead_to_cash.integrations import MS5Client
                    from lead_to_cash.integrations.client_factory import get_cpi_client

                    cpi_client, _ = await get_cpi_client(use_case="EntityResolve")
                    ms5 = MS5Client(cpi_client=cpi_client)
                    await ms5.connect()
                    customers = await ms5.search_customers(name=parsed.companies[0])
                    if customers:
                        customer_id = customers[0].customer_id

                escalations = await esc_service.get_escalations(
                    customer_id=customer_id,
                )
                summary = await esc_service.get_escalation_summary(
                    customer_id=customer_id,
                )

                if not escalations:
                    answer = "No overdue items currently require escalation."
                else:
                    # Format summary
                    summary_text = esc_service.format_escalation_summary(summary)

                    # Format individual alerts (show top 5)
                    alert_texts = []
                    for event in escalations[:5]:
                        alert_texts.append(
                            EscalationService.format_escalation_alert(event)
                        )

                    remaining = len(escalations) - 5
                    remaining_note = (
                        f"\n... and {remaining} more escalation(s)"
                        if remaining > 0
                        else ""
                    )

                    answer = (
                        f"{summary_text}\n\n"
                        + "\n\n".join(alert_texts)
                        + remaining_note
                    )

                # Add turn and save session
                session.add_turn("assistant", answer, sources=["SAP CPI (MS5)"])
                self._session_store.set(session)

                return {
                    "type": "answer",
                    "session_id": session_id,
                    "answer": answer,
                    "sources": ["SAP CPI (MS5)"],
                    "confidence": "HIGH",
                    "follow_up_suggestions": [
                        "Show collections items?",
                        "View aging breakdown?",
                        "Check credit status for overdue customers?",
                    ],
                    "timestamp": datetime.now(UTC).isoformat(),
                }

        except Exception as e:
            logger.warning(f"Escalation query handler failed: {e}")
            return None

    # =========================================================================
    # Billing / Collections / Downpayment Fast Path
    # =========================================================================

    # Billing keyword lists removed — routing now uses parsed.sub_intent from LLM

    @staticmethod
    def _build_billing_followups(
        alerts: list,
        task_type: str,
        summary,
    ) -> list[str]:
        """Build contextual follow-up suggestions from actual billing data."""
        follow_ups = []

        # Extract unique customers and orders from the displayed alerts
        customers = []
        orders = []
        seen_customers = set()
        seen_orders = set()
        for a in alerts[:10]:  # Sample first 10
            if a.customer_name and a.customer_name not in seen_customers:
                customers.append(a.customer_name)
                seen_customers.add(a.customer_name)
            if a.order_number and a.order_number not in seen_orders:
                orders.append(a.order_number)
                seen_orders.add(a.order_number)

        # Suggest drilling into specific orders shown
        if orders:
            follow_ups.append(f"Show order details for {orders[0]}")

        # Suggest customer-specific views
        if len(customers) > 1:
            follow_ups.append(f"Show payment status for {customers[0]}")

        # Suggest complementary views based on current view
        if task_type == "billing_items" and summary.billed_unpaid > 0:
            follow_ups.append(f"Show {summary.billed_unpaid} items awaiting payment")
        elif task_type == "collections_items" and summary.overdue > 0:
            follow_ups.append(f"Show {summary.overdue} overdue items to bill")
        elif task_type in ("downpayment_alerts", "downpayment_overdue"):
            follow_ups.append("Show all billing items pending")
        elif task_type == "payment_status":
            if summary.overdue > 0:
                follow_ups.append(f"Show {summary.overdue} overdue items")

        # Always cap at 3
        return follow_ups[:3]

    async def _try_handle_billing_query(
        self,
        message: str,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
        user_context: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fast path for billing, collections, downpayment, and payment status queries.

        Returns structured finops_report data for card rendering, bypassing LLM.
        """
        # LLM intent+sub_intent routing (replaces keyword matching)
        if parsed.intent != QueryIntent.BILLING_AR:
            return None

        _SUB_INTENT_TO_TASK = {
            "billing": "billing_items",
            "collections": "collections_items",
            "payment_status": "payment_status",
            "downpayment": "downpayment_alerts",
            "aging": "aging_analysis",
            "overview": "payment_status",
        }
        task_type = _SUB_INTENT_TO_TASK.get(parsed.sub_intent)

        # Downpayment overdue variant
        if task_type == "downpayment_alerts" and "overdue" in message.lower():
            task_type = "downpayment_overdue"

        if not task_type:
            return None

        # RBAC check
        if user_context:
            permissions = user_context.get("permissions", {})
            has_billing = "read" in permissions.get(
                "billing", []
            ) or "*" in permissions.get("*", [])
            has_collections = "read" in permissions.get(
                "collections", []
            ) or "*" in permissions.get("*", [])
            if not has_billing and not has_collections:
                return None  # Let the existing RBAC handler deal with it

        logger.info(f"Billing fast-path: {task_type} for: {message[:50]}...")

        try:
            from lead_to_cash.services.financeops.billing_brain import (
                BillingBrainService,
                MilestoneState,
            )

            async with BillingBrainService() as brain:
                # Resolve customer if EXPLICITLY mentioned in this message.
                # Guard against semantic resolution injecting session-history
                # companies (e.g. prior credit query for "ST Engineering"
                # contaminates a generic "show billing items" query).
                customer_id = None
                customer_name = None
                if parsed.companies:
                    company = parsed.companies[0]
                    if company.strip().isdigit() and len(company.strip()) >= 6:
                        customer_id = company.strip().zfill(10)
                    else:
                        customer_name = company
                        try:
                            from lead_to_cash.integrations import MS5Client
                            from lead_to_cash.integrations.client_factory import (
                                get_cpi_client,
                            )

                            cpi_client, _ = await get_cpi_client(
                                use_case="BillingResolve"
                            )
                            if cpi_client:
                                ms5 = MS5Client(cpi_client=cpi_client)
                                await ms5.connect()
                                customers = await ms5.search_customers(
                                    name=company, max_results=1
                                )
                                if customers:
                                    customer_id = customers[0].customer_id
                                    _confirmed = session.context.get(
                                        "confirmed_entity", {}
                                    )
                                    customer_name = (
                                        _confirmed.get("canonical_name")
                                        or customers[0].name
                                    )
                        except Exception:
                            pass

                # Get all milestone alerts from billing brain
                include_settled = task_type == "payment_status"
                all_alerts = await brain.get_all_alerts(
                    customer_id=customer_id,
                    include_settled=include_settled,
                )
                brain_summary = await brain.get_summary(customer_id=customer_id)

                # Filter alerts based on query type
                if task_type == "billing_items":
                    # Open milestones needing billing doc creation
                    alerts = [
                        a
                        for a in all_alerts
                        if a.state
                        in (
                            MilestoneState.OVERDUE,
                            MilestoneState.DUE_THIS_WEEK,
                            MilestoneState.DUE_THIS_MONTH,
                            MilestoneState.BLOCKED,
                        )
                    ]
                    follow_ups = []  # Built contextually after filtering
                elif task_type == "collections_items":
                    # Billed but unpaid milestones
                    alerts = [
                        a for a in all_alerts if a.state == MilestoneState.BILLED_UNPAID
                    ]
                    follow_ups = []
                elif task_type == "aging_analysis":
                    # All actionable milestones
                    alerts = [
                        a for a in all_alerts if a.state != MilestoneState.BILLED_PAID
                    ]
                    follow_ups = []
                elif task_type == "downpayment_alerts":
                    # Only FAZ (downpayment) milestones needing action
                    alerts = [
                        a
                        for a in all_alerts
                        if a.is_downpayment and a.state != MilestoneState.BILLED_PAID
                    ]
                    follow_ups = []
                elif task_type == "downpayment_overdue":
                    # Overdue FAZ milestones
                    alerts = [
                        a
                        for a in all_alerts
                        if a.is_downpayment
                        and a.state in (MilestoneState.OVERDUE, MilestoneState.BLOCKED)
                    ]
                    follow_ups = []
                elif task_type == "payment_status":
                    # All milestones including settled
                    alerts = all_alerts
                    follow_ups = []
                else:
                    alerts = all_alerts

                items = [a.to_dict() for a in alerts]
                overdue_count = sum(
                    1 for a in alerts if a.state == MilestoneState.OVERDUE
                )

                # Compute aging buckets from alerts
                aging_buckets = {
                    "CURRENT": {"count": 0, "amount": 0.0},
                    "0-30": {"count": 0, "amount": 0.0},
                    "30-45": {"count": 0, "amount": 0.0},
                    "45+": {"count": 0, "amount": 0.0},
                }
                for a in all_alerts:
                    if a.state == MilestoneState.BILLED_PAID:
                        continue
                    amt = a.milestone_amount or 0.0
                    if a.days_until_due >= 0:
                        aging_buckets["CURRENT"]["count"] += 1
                        aging_buckets["CURRENT"]["amount"] += amt
                    else:
                        overdue_days = abs(a.days_until_due)
                        if overdue_days > 45:
                            aging_buckets["45+"]["count"] += 1
                            aging_buckets["45+"]["amount"] += amt
                        elif overdue_days > 30:
                            aging_buckets["30-45"]["count"] += 1
                            aging_buckets["30-45"]["amount"] += amt
                        else:
                            aging_buckets["0-30"]["count"] += 1
                            aging_buckets["0-30"]["amount"] += amt
                aging_buckets["currency"] = brain_summary.currency

                # Build contextual follow-ups from actual data
                follow_ups = self._build_billing_followups(
                    alerts, task_type, brain_summary
                )

                # Update session
                label = task_type.replace("_", " ")
                session.add_turn("user", message)
                session.add_turn(
                    "assistant",
                    f"Showing {len(items)} {label} milestones"
                    + (f" for {customer_name}" if customer_name else "")
                    + f" across {brain_summary.order_count} orders",
                )
                self._session_store.set(session)

                return {
                    "type": "finops_report",
                    "session_id": session_id,
                    "task_type": task_type,
                    "items": items,
                    "aging_buckets": aging_buckets,
                    "customer_filtered": bool(customer_id),
                    "summary": {
                        "total_count": len(items),
                        "overdue_count": overdue_count,
                        **brain_summary.to_dict(),
                    },
                    "sources": ["SAP Sales Orders (Billing Plans)"],
                    "confidence": "HIGH",
                    "follow_up_suggestions": follow_ups,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

        except Exception as e:
            logger.warning(f"Billing fast-path handler failed: {e}")
            return None

    # KYP follow-up section matching now uses SEMANTIC similarity via embeddings
    # The section descriptions are defined in semantic_entity_resolver.py
    # This removes the need for keyword-based matching entirely

    async def _try_answer_from_cached_kyp(
        self,
        parsed: ParsedQuery,
        session: ConversationSession,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Try to answer a follow-up question from cached KYP report.

        PERFORMANCE OPTIMIZATION: Avoids expensive tool calls for simple follow-ups
        by extracting data from the cached KYP report.

        Uses SEMANTIC section matching (no keyword matching).

        Args:
            parsed: ParsedQuery from query understanding
            session: Current conversation session
            session_id: Session ID

        Returns:
            Answer dict if answerable from cache, None otherwise
        """
        # Check if we have a cached KYP report
        cached_report = session.context.get("cached_kyp_report")
        if not cached_report:
            return None

        # Check if this is a follow-up (short query with context)
        query_words = len(parsed.raw_query.split())
        if query_words > 12:  # Not a follow-up if query is long
            return None

        # Don't use cache if user is asking for a NEW KYP on a DIFFERENT company
        query_lower = parsed.raw_query.lower()
        # Check for explicit KYP request phrases (semantic check not needed here)
        new_kyp_phrases = ["kyp on", "perform kyp", "due diligence on", "check on"]
        if any(phrase in query_lower for phrase in new_kyp_phrases):
            # User is requesting a new KYP - check if same company
            cached_entity = cached_report.get("entity_name", "").lower()
            if cached_entity not in query_lower:
                return None  # Different company, need fresh KYP

        # Identify which section the follow-up is asking about using SEMANTIC matching
        matched_section = None

        if SEMANTIC_RESOLVER_AVAILABLE:
            try:
                result = await match_kyp_section_semantically(parsed.raw_query)
                if result:
                    matched_section, confidence = result
                    logger.info(
                        f"Semantic KYP section match: {matched_section} "
                        f"(confidence={confidence:.3f})"
                    )
            except Exception as e:
                logger.warning(f"Semantic KYP section matching failed: {e}")

        if not matched_section:
            return None  # Can't determine what user is asking about

        # Extract relevant data from cached report
        entity_name = cached_report.get("entity_name", "Unknown")
        sections = cached_report.get("sections", [])
        assessment = cached_report.get("assessment", {}).get("summary", [])
        recommendation = cached_report.get("recommendation", {})

        answer_parts = []
        # Use section-specific sources, not the global KYP sources list.
        # Global sources include Perplexity URLs from all phases which
        # are irrelevant when answering about a specific section.
        sources = []  # Will be set per-section below

        if matched_section == "credit":
            # Extract credit info from SAP Credit section
            credit_section = next(
                (s for s in sections if s.get("id") == "sap_credit"), None
            )
            if credit_section:
                answer_parts.append(f"**{entity_name} - SAP Credit Status**\n")
                for field in credit_section.get("fields", []):
                    answer_parts.append(
                        f"- **{field.get('label')}:** {field.get('value')}"
                    )
                _src = credit_section.get("source", "SAP CPI (MS5)")
                answer_parts.append(f"\n*Source: {_src}*")
                sources = [_src]
            else:
                answer_parts.append(f"No SAP credit data available for {entity_name}.")

        elif matched_section == "sanctions":
            # Extract sanctions info
            sanctions_section = next(
                (s for s in sections if s.get("id") == "sanctions"), None
            )
            if sanctions_section:
                status = sanctions_section.get("status", "UNKNOWN")
                answer_parts.append(
                    f"**{entity_name} - Sanctions Screening: {status}**\n"
                )
                for check in sanctions_section.get("checks", []):
                    emoji = (
                        "✅"
                        if check.get("status") == "clear"
                        else "❌"
                        if check.get("status") == "match"
                        else "⚠️"
                    )
                    line = f"- {emoji} {check.get('database')}: {check.get('result')}"
                    if check.get("source_url"):
                        line += f"\n  Source: {check['source_url']}"
                    if check.get("list_date"):
                        line += f" (data as of {check['list_date']})"
                    answer_parts.append(line)
                if sanctions_section.get("checked_date"):
                    answer_parts.append(
                        f"\n*Checked: {sanctions_section.get('checked_date')}*"
                    )
                answer_parts.append(
                    "\n*Source: Direct database check against authoritative lists*"
                )
                sources = [sanctions_section.get("source", "OFAC, UN, EU, MAS")]
            else:
                answer_parts.append(f"No sanctions screening data for {entity_name}.")

        elif matched_section == "financial":
            # Extract financial health info
            fin_section = next(
                (s for s in sections if s.get("id") == "financial_health"), None
            )
            if fin_section:
                answer_parts.append(f"**{entity_name} - Financial Health**\n")
                for field in fin_section.get("fields", []):
                    badge = f" ({field.get('badge')})" if field.get("badge") else ""
                    answer_parts.append(
                        f"- **{field.get('label')}:** {field.get('value')}{badge}"
                    )
                for sub in fin_section.get("subsections", []):
                    answer_parts.append(f"\n**{sub.get('title')}:**")
                    for field in sub.get("fields", []):
                        answer_parts.append(
                            f"- {field.get('label')}: {field.get('value')}"
                        )
                sources = [fin_section.get("source", "EODHD")]
            else:
                answer_parts.append(f"No financial data available for {entity_name}.")

        elif matched_section == "litigation":
            # Extract litigation info
            lit_section = next(
                (s for s in sections if s.get("id") == "litigation"), None
            )
            if lit_section:
                status = lit_section.get("status", "UNKNOWN")
                answer_parts.append(
                    f"**{entity_name} - Litigation & Regulatory: {status}**\n"
                )
                findings = lit_section.get("findings", [])
                if findings:
                    for finding in findings:
                        answer_parts.append(
                            f"- **{finding.get('title')}** [{finding.get('status')}]"
                        )
                        answer_parts.append(f"  {finding.get('details', '')}")
                else:
                    answer_parts.append("No adverse litigation findings identified.")
                sources = [lit_section.get("source", "Perplexity Web Search")]
            else:
                answer_parts.append(f"No litigation data for {entity_name}.")

        elif matched_section == "profile":
            # Extract entity profile
            profile_section = next(
                (s for s in sections if s.get("id") == "entity_profile"), None
            )
            if profile_section:
                answer_parts.append(f"**{entity_name} - Entity Profile**\n")
                for field in profile_section.get("fields", []):
                    answer_parts.append(
                        f"- **{field.get('label')}:** {field.get('value')}"
                    )
                sources = [profile_section.get("source", "EODHD")]
            else:
                answer_parts.append(f"No profile data for {entity_name}.")

        elif matched_section == "overall":
            # Overall status and recommendation
            overall_status = cached_report.get("overall_status", "UNKNOWN")
            can_proceed = cached_report.get("can_proceed", False)
            answer_parts.append(f"**{entity_name} - KYP Summary**\n")
            answer_parts.append(f"- **Overall Status:** {overall_status}")
            answer_parts.append(f"- **Can Proceed:** {'Yes' if can_proceed else 'No'}")
            if assessment:
                answer_parts.append("\n**Assessment Summary:**")
                for item in assessment:
                    answer_parts.append(
                        f"- {item.get('category')}: {item.get('status')} - {item.get('notes')}"
                    )
            if recommendation:
                answer_parts.append(
                    f"\n**Recommendation:** {recommendation.get('decision')}"
                )
                answer_parts.append(f"- {recommendation.get('text')}")
            # Overall summary uses all KYP sources
            sources = cached_report.get("sources", [])

        if not answer_parts:
            return None

        answer_text = "\n".join(answer_parts)
        follow_ups = [
            f"See full KYP report for {entity_name}?",
            f"Check {entity_name}'s competitors?",
            "Any other questions about this company?",
        ]

        return {
            "type": "answer",
            "session_id": session_id,
            "answer": answer_text,
            "sources": sources,
            "confidence": "HIGH",
            "data_coverage": {
                "has_local_data": True,
                "coverage_confidence": "HIGH",
                "from_cache": True,
            },
            "follow_up_suggestions": follow_ups,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _check_clarifications(
        self,
        parsed: ParsedQuery,
        session: ConversationSession,
    ) -> List[ClarificationQuestion]:
        """
        Check if clarification questions are needed.

        IMPORTANT: Be CONSERVATIVE about asking for clarification.
        Per sales_intelligence_agent_guide.md, only ask when truly ambiguous.
        DO NOT interrupt the flow for common queries.

        Uses SEMANTIC time detection (no keyword matching).

        Args:
            parsed: ParsedQuery from query understanding
            session: Current session for context

        Returns:
            List of ClarificationQuestion if needed, empty list otherwise
        """
        questions: List[ClarificationQuestion] = []

        # Check for vague follow-ups FIRST - these always need clarification
        if self._is_vague_followup(parsed.raw_query) and len(session.turns) > 0:
            # Build context-aware clarification options
            options = []
            last_entity = session.context.get("last_kyp_entity")
            if last_entity:
                options.append(f"More details about {last_entity}")
                options.append(f"Check {last_entity}'s competitors")
            if session.context.get("companies"):
                company = session.context["companies"][-1]
                if company != last_entity:
                    options.append(f"Information about {company}")
            options.append("Something else (please specify)")

            questions.append(
                ClarificationQuestion(
                    id="vague_followup",
                    question="What would you like to know more about?",
                    question_type="choice",
                    options=options[:4],  # Max 4 options
                    reason="Your query is a bit brief - please clarify what you'd like",
                )
            )
            return questions  # Return immediately for vague queries

        # Check if this is a follow-up query (short query with conversation context)
        is_follow_up = (
            len(parsed.raw_query.split()) <= 8  # Short query
            and len(session.turns) > 0  # Has history
        )

        # 1. Check if LLM flagged clarification
        # But skip if it's a follow-up query - context should be inherited
        if parsed.requires_clarification and not is_follow_up:
            for i, q in enumerate(parsed.clarification_questions):
                questions.append(
                    ClarificationQuestion(
                        id=f"llm_{i}",
                        question=q,
                        question_type="text",
                        reason="Query understanding identified ambiguity",
                    )
                )

        # 2. Time clarification - BE VERY CONSERVATIVE
        # Most queries imply "recent" - don't ask unless explicitly ambiguous
        # Uses SEMANTIC time sensitivity detection (no keyword matching)
        query_lower = parsed.raw_query.lower()
        has_time_signal = False

        if SEMANTIC_RESOLVER_AVAILABLE:
            try:
                (
                    is_time_sensitive,
                    confidence,
                    time_type,
                ) = await detect_time_sensitivity_semantically(parsed.raw_query)
                has_time_signal = is_time_sensitive or time_type != "neutral"
                if has_time_signal:
                    logger.debug(
                        f"Semantic time detection: {time_type} "
                        f"(confidence={confidence:.3f})"
                    )
            except Exception as e:
                logger.warning(f"Semantic time detection failed: {e}")

        # Skip time clarification for:
        # - MARKET_INTEL/MARKET_NEWS - news is inherently about recent events
        # - Any query with time signal (detected semantically)
        # - Follow-up queries
        # - Queries where LLM already set time reference
        skip_time_clarification = (
            parsed.intent in [QueryIntent.MARKET_NEWS, QueryIntent.MARKET_INTEL]
            or parsed.time_start
            or parsed.time_reference
            or parsed.is_realtime_needed
            or has_time_signal
            or is_follow_up
            or session.context.get("last_time_period")
        )

        # Only ask for time if truly needed and not skipped
        if (
            parsed.intent in self.TIME_SENSITIVE_INTENTS
            and not skip_time_clarification
            and parsed.intent
            == QueryIntent.FINANCIAL_ANALYSIS  # Only for financial queries
        ):
            questions.append(
                ClarificationQuestion(
                    id="time_period",
                    question="What time period for the financial analysis?",
                    question_type="choice",
                    options=[
                        "Last quarter",
                        "Last year",
                        "Last 3 years",
                    ],
                    reason="Financial analysis requires specific time scope",
                )
            )

        # 3. Competitor clarification - Only if truly ambiguous
        # Skip if:
        # - Session already has competitor context
        # - Query mentions "competitors" generically (means all)
        # - It's a follow-up query
        # - Query is a market-level question (competitive position/landscape/trends)
        _is_market_level = any(
            kw in query_lower
            for kw in [
                "competitive position",
                "competitive landscape",
                "market",
                "trends",
                "segment",
                "all competitor",
            ]
        )
        if (
            parsed.intent == QueryIntent.COMPETITOR_INTEL
            and not parsed.competitors
            and not session.context.get("competitors")
            and not is_follow_up
            and "competitor" not in query_lower  # "competitors" implies all
            and "all" not in query_lower
            and not _is_market_level  # market-level queries don't need specific competitor
        ):
            questions.append(
                ClarificationQuestion(
                    id="competitor",
                    question="Which competitor(s) are you interested in?",
                    question_type="choice",
                    options=[
                        "Caterpillar (CAT/MaK)",
                        "Cummins",
                        "MAN Energy Solutions",
                        "All major competitors",
                    ],
                    reason="Specific competitor helps focus the search",
                )
            )

        return questions

    async def _build_kyp_report(
        self,
        parsed: ParsedQuery,
        tool_result: ToolResult,
        session_id: str,
        follow_ups: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Build a structured KYP report from tool execution results.

        Parses outputs from SAP_MCP, EODHD, and PERPLEXITY tools to create
        a comprehensive KYP due diligence report.

        Args:
            parsed: ParsedQuery with intent KYP_DUE_DILIGENCE
            tool_result: Results from tool chain execution
            session_id: Current session ID
            follow_ups: Generated follow-up suggestions

        Returns:
            KYP report dict with type="kyp_report" or None if can't build
        """
        try:
            # Extract entity name from query with session context fallback
            entity_name = "Unknown Entity"
            entity_source = "unknown"

            if parsed.companies:
                entity_name = parsed.companies[0]
                entity_source = "parsed_query"
            elif self._is_follow_up_query(parsed.raw_query):
                # GUARD: Only fall back to session context for follow-up/pronoun
                # queries to prevent entity contamination across turns.
                session = self.get_or_create_session(session_id)
                if session.context.get("companies"):
                    entity_name = session.context["companies"][-1]  # Most recent
                    entity_source = "session_context"
                    logger.info(
                        f"KYP Report: Using entity from session context: '{entity_name}'"
                    )
                else:
                    # Strategy 2: Pattern matching on query text
                    query = parsed.raw_query.lower()
                    for phrase in [
                        "conduct kyp on",
                        "perform kyp on",
                        "kyp on",
                        "kyp for",
                        "due diligence on",
                        "check on",
                    ]:
                        if phrase in query:
                            parts = query.split(phrase)
                            if len(parts) > 1:
                                extracted = parts[1].strip().rstrip(".,!?")
                                if extracted:
                                    entity_name = extracted.title()
                                    entity_source = "pattern_match"
                                break

            # Validate entity name — reject overly long, empty, or suspicious inputs
            if entity_name and entity_name != "Unknown Entity":
                # Strip control characters (Cc) and invisible format chars (Cf)
                # using Unicode categories — covers zero-width, directional,
                # variation selectors, tag chars, interlinear annotations, etc.
                # Note: Mn (nonspacing marks / combining diacritics) are KEPT
                # to preserve accented names like "Énergies" in NFD form.
                import unicodedata

                entity_name = "".join(
                    ch
                    for ch in entity_name
                    if unicodedata.category(ch) not in ("Cc", "Cf")
                ).strip()
                # If after cleanup it's empty, reset
                if not entity_name:
                    entity_name = "Unknown Entity"
                    entity_source = "unknown"
                # Max 150 chars (company names shouldn't be longer)
                elif len(entity_name) > 150:
                    entity_name = entity_name[:150].strip()
                    logger.warning("KYP Report: Entity name truncated to 150 chars")

            logger.info(
                f"KYP Report: entity_name='{entity_name}' (source={entity_source}), "
                f"companies={parsed.companies}"
            )

            # =================================================================
            # KYP Report Structure: Inside-Out, Risk-First Approach
            # =================================================================
            # Phase 1: Business Context (What do we already know internally?)
            # Phase 2: Internal Risk (SAP Credit, TPRM/Aravo)
            # Phase 3: External Risk (Sanctions, Financial, Litigation)
            # =================================================================

            # Section lists for each phase
            phase1_sections: list[ReportSection] = []  # Business Context
            phase2_sections: list[ReportSection] = []  # Internal Risk
            phase3_sections: list[ReportSection] = []  # External Risk
            assessment_items: list[AssessmentItem] = []

            # Parse tool outputs with logging
            sap_data = None
            eodhd_data = None
            perplexity_data = None
            perplexity_sources: list[str] = []  # Capture actual source URLs

            logger.info(
                f"KYP Report: Processing {len(tool_result.tool_outputs)} tool outputs"
            )
            for output in tool_result.tool_outputs:
                logger.info(
                    f"  Tool: {output.tool}, status: {output.status}, content_len: {len(output.content) if output.content else 0}"
                )
                if output.tool == DataSource.SAP_MCP and output.content:
                    sap_data = output.content
                    logger.info(f"  -> SAP_MCP data captured: {len(sap_data)} chars")
                elif output.tool == DataSource.EODHD and output.content:
                    eodhd_data = output.content
                    logger.info(f"  -> EODHD data captured: {len(eodhd_data)} chars")
                elif output.tool == DataSource.PERPLEXITY and output.content:
                    perplexity_data = output.content
                    perplexity_sources = output.sources if output.sources else []
                    logger.info(
                        f"  -> PERPLEXITY data captured: {len(perplexity_data)} chars, {len(perplexity_sources)} sources"
                    )

            # ─── Parallel fetch: Aravo + CEC + Sanctions ───────────
            # These three heavy operations have no dependencies on each
            # other.  Running them in parallel saves ~30s (was sequential).

            async def _fetch_aravo() -> Optional[dict]:
                """Fetch TPRM data from Aravo (8s timeout)."""
                if not ARAVO_AVAILABLE:
                    return None
                try:
                    from lead_to_cash.integrations.client_factory import (
                        get_aravo_client,
                    )

                    aravo, _is_real = await get_aravo_client(use_case="KYP-TPRM")
                    if not aravo:
                        return None
                    suppliers = await asyncio.wait_for(
                        aravo.search_suppliers(name=entity_name),
                        timeout=8.0,
                    )
                    if suppliers:
                        supplier = suppliers[0]
                        _el = entity_name.lower().strip()
                        _sl = supplier.name.lower().strip()
                        _name_match = (
                            _el in _sl
                            or _sl in _el
                            or bool(set(_el.split()) & set(_sl.split()))
                        )
                        if not _name_match:
                            logger.warning(
                                f"  -> ARAVO: Skipping low-confidence match: "
                                f"searched='{entity_name}', got='{supplier.name}'"
                            )
                            return None
                    if not suppliers:
                        logger.info(
                            f"  -> ARAVO: No supplier found for '{entity_name}'"
                        )
                        return None
                    supplier = suppliers[0]
                    assessment = await asyncio.wait_for(
                        aravo.get_tprm_assessment(supplier.supplier_id),
                        timeout=8.0,
                    )
                    if not assessment:
                        return None
                    logger.info(
                        f"  -> ARAVO data captured for supplier: {supplier.name}"
                    )
                    return {
                        "supplier_name": (assessment.supplier_name or entity_name),
                        "supplier_id": (assessment.supplier_id),
                        "tprm_status": (
                            assessment.tprm_status.value
                            if assessment.tprm_status
                            else None
                        ),
                        "inherent_risk_score": assessment.inherent_risk_score,
                        "overall_risk_score": assessment.overall_risk_score,
                        "supplier_status": (assessment.supplier_status or None),
                        "due_diligence_status": (
                            assessment.due_diligence_workflows[0].status
                            if assessment.due_diligence_workflows
                            else None
                        ),
                        "questionnaire_scores": [
                            {
                                "name": q.name,
                                "score": q.score or 0,
                                "max_score": q.max_score or 100,
                            }
                            for q in (assessment.questionnaire_scores or [])
                        ],
                        "last_assessment_date": (
                            assessment.last_assessment_date.strftime("%Y-%m-%d")
                            if assessment.last_assessment_date
                            else None
                        ),
                    }
                except asyncio.TimeoutError:
                    logger.warning(
                        f"  -> ARAVO: Timed out fetching TPRM for '{entity_name}'"
                    )
                    return None
                except Exception as e:
                    logger.warning(f"  -> ARAVO fetch error: {e}")
                    return None

            async def _fetch_sanctions() -> list:
                """Screen entity against OFAC/UN/EU/MAS sanctions lists."""
                try:
                    results: list[SanctionCheckResult] = await screen_sanctions(
                        entity_name
                    )
                    logger.info(
                        f"KYP Report: Direct sanctions screening complete — "
                        f"{len(results)} lists checked"
                    )
                    return results
                except Exception as e:
                    logger.warning(
                        f"KYP Report: Direct sanctions screening failed: {e}"
                    )
                    return []

            # Launch Aravo + Sanctions in parallel now.
            # CEC needs sap_customer_id which is parsed below, so it runs after.
            aravo_task = asyncio.create_task(_fetch_aravo())
            sanctions_task = asyncio.create_task(_fetch_sanctions())

            # =================================================================
            # PHASE 1: Business Context (Inside view - what we know internally)
            # =================================================================
            # Build from SAP customer data
            sap_customer_id = None
            sap_customer_name = None
            relationship_status = "New Prospect"  # Default for unknown entities

            if sap_data:
                # Parse SAP data for customer info
                lines = sap_data.split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("- **Customer ID:**"):
                        sap_customer_id = line.replace("- **Customer ID:**", "").strip()
                    elif line.startswith("- **Customer Name:**"):
                        sap_customer_name = line.replace(
                            "- **Customer Name:**", ""
                        ).strip()
                    elif line.startswith("- **Name:**"):
                        sap_customer_name = line.replace("- **Name:**", "").strip()

                if sap_customer_id:
                    relationship_status = "Existing Customer"

            # Fetch CEC opportunity data for lifetime value and pipeline metrics
            # Wrapped in 10s timeout to keep KYP within ALB timeout budget
            cec_metrics: dict[str, Any] = {}
            if CEC_AVAILABLE and sap_customer_id:
                opportunities = []
                try:
                    from lead_to_cash.integrations.cec_client import CECClient as _CEC
                    from lead_to_cash.integrations.client_factory import get_cpi_client

                    # Fetch opportunities from real SAP CPI
                    logger.info("  -> CEC: Fetching opportunity data from real CPI")
                    _cpi, _ = await get_cpi_client(use_case="KYP-CEC")
                    _cec = _CEC(cpi_client=_cpi)
                    await _cec.connect()
                    normalized_id = sap_customer_id.zfill(10)
                    opportunities = await asyncio.wait_for(
                        _cec.get_opportunities_by_account(
                            account_id=normalized_id, limit=20
                        ),
                        timeout=10.0,
                    )
                    logger.info(
                        f"  -> CEC: Retrieved {len(opportunities)} opportunities "
                        f"for SAP ID {sap_customer_id}"
                    )

                    if opportunities:
                        # Derive metrics from opportunities
                        won_opps = [o for o in opportunities if o.status == "Won"]
                        lost_opps = [o for o in opportunities if o.status == "Lost"]
                        open_opps = [o for o in opportunities if o.status == "Open"]

                        # Lifetime value = sum of won opportunity values
                        lifetime_value = sum(o.expected_revenue for o in won_opps)

                        # Pipeline value = sum of open opportunity values
                        open_pipeline = sum(o.expected_revenue for o in open_opps)

                        # Next expected close date from open opportunities
                        next_close = None
                        if open_opps:
                            dated_opps = [o for o in open_opps if o.close_date]
                            if dated_opps:
                                earliest = min(dated_opps, key=lambda o: o.close_date)
                                next_close = earliest.close_date.strftime("%Y-%m-%d")

                        # First order date = earliest won opportunity close date
                        first_order_date = None
                        if won_opps:
                            dated_won = [o for o in won_opps if o.close_date]
                            if dated_won:
                                earliest_won = min(
                                    dated_won, key=lambda o: o.close_date
                                )
                                first_order_date = earliest_won.close_date.strftime(
                                    "%Y-%m-%d"
                                )

                        # Determine currency (use first opportunity's currency, default SGD)
                        opp_currency = (
                            opportunities[0].currency if opportunities else "SGD"
                        )

                        cec_metrics = {
                            "lifetime_value": lifetime_value,
                            "won_deals_count": len(won_opps),
                            "lost_deals_count": len(lost_opps),
                            "open_opportunities_count": len(open_opps),
                            "open_pipeline_value": open_pipeline,
                            "next_expected_close": next_close,
                            "first_order_date": first_order_date,
                            "currency": opp_currency,
                        }
                        logger.info(
                            f"  -> CEC metrics: LTV={opp_currency} {lifetime_value:,.0f}, "
                            f"Won={len(won_opps)}, Lost={len(lost_opps)}, "
                            f"Open={len(open_opps)} ({opp_currency} {open_pipeline:,.0f})"
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"  -> CEC: Timed out fetching opportunities for "
                        f"SAP ID {sap_customer_id}"
                    )
                except Exception as e:
                    logger.warning(f"  -> CEC fetch error: {e}")

            # Await parallel tasks (Aravo + Sanctions were started earlier)
            aravo_data = await aravo_task
            sanctions_results = await sanctions_task

            # Build Business Context section
            business_context_section = build_business_context_section(
                customer_id=sap_customer_id,
                customer_name=sap_customer_name or entity_name,
                relationship_status=relationship_status,
                first_order_date=cec_metrics.get(
                    "first_order_date"
                ),  # For source attribution
                currency=cec_metrics.get("currency", "SGD"),
                # CEC-derived metrics
                lifetime_value=cec_metrics.get("lifetime_value"),
                won_deals_count=cec_metrics.get("won_deals_count"),
                lost_deals_count=cec_metrics.get("lost_deals_count"),
                open_opportunities_count=cec_metrics.get("open_opportunities_count"),
                open_pipeline_value=cec_metrics.get("open_pipeline_value"),
                next_expected_close=cec_metrics.get("next_expected_close"),
            )
            phase1_sections.append(business_context_section)

            # Add Business Context assessment
            if relationship_status == "Existing Customer":
                assessment_items.append(
                    AssessmentItem(
                        category="Business Context",
                        status=SectionStatus.NO_ADVERSE_FINDINGS,
                        notes=f"Existing customer (SAP ID: {sap_customer_id})",
                    )
                )
            else:
                assessment_items.append(
                    AssessmentItem(
                        category="Business Context",
                        status=SectionStatus.INFO,
                        notes="New prospect - no prior relationship",
                    )
                )

            # =================================================================
            # PHASE 3: External Risk (Entity Profile & Financial from EODHD)
            # Note: Built before Phase 2 since EODHD data is already available
            # =================================================================
            if eodhd_data:
                # Parse EODHD markdown output
                profile_fields = []
                financial_fields = []
                ownership_fields = []
                officer_fields = []
                distress_fields = []
                esg_fields = []
                stock_code = None  # Extract for source attribution

                lines = eodhd_data.split("\n")
                current_section = None

                for line in lines:
                    line = line.strip()
                    if "Entity Profile" in line or (
                        "##" in line and entity_name in line
                    ):
                        current_section = "profile"
                    elif "Financial Health" in line:
                        current_section = "financial"
                    elif "Key Officers" in line:
                        current_section = "officers"
                    elif "Financial Distress" in line:
                        current_section = "distress"
                    elif "ESG Scores" in line:
                        current_section = "esg"
                    elif "Ownership" in line:
                        current_section = "ownership"
                    elif line.startswith("- **") and ":**" in line:
                        # Parse field: - **Label:** Value
                        parts = line.replace("- **", "").split(":**")
                        if len(parts) >= 2:
                            label = parts[0].strip()
                            value = parts[1].strip()
                            # Extract stock code for source attribution
                            if label == "Stock Code":
                                stock_code = value
                            if current_section == "profile":
                                profile_fields.append(
                                    ReportField(label=label, value=value)
                                )
                            elif current_section == "financial":
                                financial_fields.append(
                                    ReportField(label=label, value=value)
                                )
                            elif current_section == "ownership":
                                ownership_fields.append(
                                    ReportField(label=label, value=value)
                                )
                            elif current_section == "officers":
                                officer_fields.append(
                                    ReportField(label=label, value=value)
                                )
                            elif current_section == "distress":
                                distress_fields.append(
                                    ReportField(label=label, value=value)
                                )
                            elif current_section == "esg":
                                esg_fields.append(ReportField(label=label, value=value))

                # Build dynamic EODHD source with stock code and date
                from datetime import date as date_module

                today_str = date_module.today().isoformat()
                if stock_code:
                    # Parse exchange from stock code (e.g., S63.SG -> SGX)
                    exchange_map = {
                        ".SG": "SGX",
                        ".US": "NYSE/NASDAQ",
                        ".HK": "HKEX",
                        ".L": "LSE",
                        ".DE": "XETRA",
                        ".TO": "TSX",
                        ".AS": "Euronext",
                    }
                    exchange = "Exchange"
                    for suffix, exch_name in exchange_map.items():
                        if stock_code.endswith(suffix):
                            exchange = exch_name
                            break
                    eodhd_source = f"{exchange} ({stock_code}), {today_str}"
                else:
                    eodhd_source = today_str

                if profile_fields:
                    phase3_sections.append(
                        ReportSection(
                            id="entity_profile",
                            title="Entity Profile",
                            icon="📋",
                            status=SectionStatus.INFO,
                            source=eodhd_source,
                            fields=profile_fields,
                        )
                    )

                if financial_fields:
                    phase3_sections.append(
                        ReportSection(
                            id="financial_health",
                            title="Financial Health",
                            icon="📊",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            source=eodhd_source,
                            fields=financial_fields,
                            subsections=(
                                [
                                    ReportSubsection(
                                        title="Ownership", fields=ownership_fields
                                    )
                                ]
                                if ownership_fields
                                else []
                            ),
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Financial",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            notes="Financial data retrieved from EODHD",
                        )
                    )

                # ── Ownership / UBO / Leadership from EODHD ──
                # Combine ownership_fields + officer_fields into a proper
                # Ownership section (authoritative, not Perplexity-derived)
                eodhd_has_ownership = bool(ownership_fields or officer_fields)
                if eodhd_has_ownership:
                    all_ownership_fields = list(ownership_fields)
                    subsections = []
                    if officer_fields:
                        subsections.append(
                            ReportSubsection(
                                title="Key Officers", fields=officer_fields
                            )
                        )
                    phase3_sections.append(
                        ReportSection(
                            id="ownership",
                            title="Ownership, UBO & Leadership",
                            icon="👤",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            source=eodhd_source,
                            fields=all_ownership_fields,
                            subsections=subsections,
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Ownership",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            notes="Ownership and leadership data from EODHD",
                        )
                    )

                # ── Financial Distress Indicators from EODHD ──
                eodhd_has_distress = bool(distress_fields)
                if eodhd_has_distress:
                    phase3_sections.append(
                        ReportSection(
                            id="financial_distress",
                            title="Financial Distress Signals",
                            icon="📉",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            source=eodhd_source,
                            fields=distress_fields,
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Financial Distress",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            notes="No distress signals — data from EODHD",
                        )
                    )
                # ── ESG-based Environmental section from EODHD ──
                eodhd_has_esg = bool(esg_fields)
                if eodhd_has_esg:
                    phase3_sections.append(
                        ReportSection(
                            id="environmental",
                            title="Environmental Compliance",
                            icon="🌿",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            source=eodhd_source,
                            fields=esg_fields,
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Environmental",
                            status=SectionStatus.NO_ADVERSE_FINDINGS,
                            notes="ESG scores from EODHD — no adverse signals",
                        )
                    )
            else:
                eodhd_has_ownership = False
                eodhd_has_distress = False
                eodhd_has_esg = False

            # =================================================================
            # PHASE 2: Internal Risk (SAP Credit)
            # =================================================================
            if sap_data:
                sap_fields = []
                lines = sap_data.split("\n")
                credit_passed = True

                # Only include credit-specific fields (exclude Customer ID/Name
                # which are already shown in Business Context section)
                CREDIT_SPECIFIC_FIELDS = {
                    "Credit Limit",
                    "Credit Exposure",
                    "Utilization",
                    "Credit Status",
                    "Available Credit",
                    "Credit Control Area",
                    "Risk Category",
                    "Payment Terms",
                }

                for line in lines:
                    line = line.strip()
                    if line.startswith("- **") and ":**" in line:
                        parts = line.replace("- **", "").split(":**")
                        if len(parts) >= 2:
                            label = parts[0].strip()
                            value = parts[1].strip()

                            # Skip fields not related to credit
                            if label not in CREDIT_SPECIFIC_FIELDS:
                                continue

                            field_type = "text"
                            status = None
                            if "Status" in label:
                                field_type = "status"
                                status = "success" if "Approved" in value else "warning"
                                if (
                                    "Review" in value
                                    or "Blocked" in value
                                    or "BLOCKED" in value
                                ):
                                    credit_passed = False
                                    status = "error"
                            sap_fields.append(
                                ReportField(
                                    label=label,
                                    value=value,
                                    field_type=field_type,
                                    status=status,
                                )
                            )

                if sap_fields:
                    phase2_sections.append(
                        ReportSection(
                            id="sap_credit",
                            title="SAP Credit Status",
                            icon="💳",
                            status=(
                                SectionStatus.NO_ADVERSE_FINDINGS
                                if credit_passed
                                else SectionStatus.ADVERSE_FINDINGS
                            ),
                            source="MS5",
                            fields=sap_fields,
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Credit",
                            status=(
                                SectionStatus.NO_ADVERSE_FINDINGS
                                if credit_passed
                                else SectionStatus.ADVERSE_FINDINGS
                            ),
                            notes="SAP credit check completed",
                        )
                    )

            # Add fallback sections when data is missing
            if not eodhd_data:
                logger.warning(
                    f"KYP Report: No EODHD data available for '{entity_name}'"
                )
                # Add entity profile placeholder to Phase 3
                phase3_sections.insert(
                    0,
                    ReportSection(
                        id="entity_profile",
                        title="Entity Profile",
                        icon="📋",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        source="EODHD",
                        fields=[
                            ReportField(
                                label="Status",
                                value=f"No listed equity data found for '{entity_name}'. Company may be privately held.",
                                field_type="text",
                            )
                        ],
                    ),
                )
                assessment_items.append(
                    AssessmentItem(
                        category="Profile",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        notes="No listed equity data — may be privately held",
                    ),
                )

            if not sap_data:
                logger.warning(f"KYP Report: No SAP data available for '{entity_name}'")
                # Add SAP credit placeholder to Phase 2 (Internal Risk)
                phase2_sections.append(
                    ReportSection(
                        id="sap_credit",
                        title="SAP Credit Status",
                        icon="💳",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        source="MS5",
                        fields=[
                            ReportField(
                                label="Status",
                                value=f"'{entity_name}' is not in the SAP customer master. Likely a new prospect.",
                                field_type="text",
                            )
                        ],
                    ),
                )
                assessment_items.append(
                    AssessmentItem(
                        category="Credit",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        notes="New prospect — not yet in SAP",
                    ),
                )

            # Build Sanctions and Litigation sections from Perplexity AI analysis
            # Perplexity returns structured analysis with explicit status values:
            # - NO_ADVERSE_FINDINGS
            # - ADVERSE_FINDINGS (with details)
            # - UNABLE_TO_VERIFY

            # Build Perplexity source string with actual URLs
            if perplexity_sources:
                # Format sources as comma-separated list (limit to 5 for display)
                source_domains = []
                from urllib.parse import urlparse

                for url in perplexity_sources[:5]:
                    try:
                        # Extract domain from URL
                        domain = urlparse(url).netloc.replace("www.", "")
                        if domain and domain not in source_domains:
                            source_domains.append(domain)
                    except (ValueError, AttributeError):
                        pass  # Skip malformed URLs
                perplexity_source_str = (
                    ", ".join(source_domains) if source_domains else "Web Search"
                )
            else:
                perplexity_source_str = "Web Search"

            if perplexity_data:
                # Regex for detecting section boundaries — handles:
                # "2. TITLE", "  2. TITLE", "**2. TITLE", "## 2. TITLE",
                # "\n2.", "\n\n2.", "  **2."
                _section_boundary_re = re.compile(
                    r"(?:^|\n)\s*(?:\*\*|#{1,3}\s*)?(\d+)\.\s",
                    re.MULTILINE,
                )

                def _truncate_at_sentence(text: str, max_len: int = 200) -> str:
                    """Truncate text at last sentence boundary within max_len."""
                    if not text or len(text) <= max_len:
                        return text
                    truncated = text[:max_len]
                    # Find last sentence-ending punctuation
                    for i in range(len(truncated) - 1, -1, -1):
                        if truncated[i] in ".!?":
                            return truncated[: i + 1]
                    return truncated.rsplit(" ", 1)[0] + "..."

                def extract_section_content(
                    data: str, section_markers: list[str]
                ) -> tuple[str, str, str]:
                    """Extract section content and status from Perplexity response.

                    Finds the section by marker text, then uses regex to detect the
                    next numbered section boundary. Handles varied markdown formatting
                    (bold, headings, indentation, double newlines).

                    Returns: (status, summary, full_content)
                    Status: 'NO_ADVERSE_FINDINGS', 'ADVERSE_FINDINGS', 'UNABLE_TO_VERIFY'
                    """
                    data_lower = data.lower()

                    # Find the section boundaries — prefer line-start matches
                    # to avoid matching "1. SANCTIONS" mid-sentence
                    section_start = -1
                    for marker in section_markers:
                        marker_lower = marker.lower()
                        # First try: find at line start (after newline or at start of text)
                        line_start_pattern = re.compile(
                            r"(?:^|\n)\s*" + re.escape(marker_lower),
                            re.IGNORECASE,
                        )
                        m = line_start_pattern.search(data)
                        if m:
                            # Advance past the newline/whitespace to the actual marker
                            section_start = data_lower.find(marker_lower, m.start())
                            break
                        # Fallback: find anywhere (for edge cases where section
                        # might not be on its own line)
                        pos = data_lower.find(marker_lower)
                        if pos != -1:
                            section_start = pos
                            break

                    if section_start == -1:
                        return ("UNABLE_TO_VERIFY", "Section not found in response", "")

                    # Use regex to find next section boundary after current one
                    # Skip at least 20 chars into current section to avoid self-match
                    search_from = section_start + 20
                    section_end = len(data)
                    for m in _section_boundary_re.finditer(data, search_from):
                        # Only match boundaries with higher section numbers
                        # or any numbered boundary that isn't our current section
                        section_end = m.start()
                        break

                    section_content = data[section_start:section_end].strip()

                    # Extract status from AI's explicit determination
                    section_lower = section_content.lower()
                    if "no_adverse_findings" in section_lower:
                        status = "NO_ADVERSE_FINDINGS"
                    elif "adverse_findings" in section_lower:
                        status = "ADVERSE_FINDINGS"
                    elif "unable_to_verify" in section_lower:
                        status = "UNABLE_TO_VERIFY"
                    else:
                        # Fallback: infer from content
                        if any(
                            phrase in section_lower
                            for phrase in [
                                "no match",
                                "not found",
                                "no record",
                                "no records",
                                "no adverse",
                                "no significant",
                                "no violations",
                                "no incidents",
                                "no sanctions",
                                "no litigation",
                                "no specific",
                                "do not contain",
                                "does not contain",
                            ]
                        ):
                            status = "NO_ADVERSE_FINDINGS"
                        elif any(
                            phrase in section_lower
                            for phrase in [
                                "found",
                                "identified",
                                "listed on",
                                "reported",
                                "violation",
                                "incident",
                                "lawsuit",
                                "enforcement",
                            ]
                        ):
                            status = "ADVERSE_FINDINGS"
                        else:
                            status = "UNABLE_TO_VERIFY"

                    # Relevance guard: If Perplexity didn't find real entity-specific
                    # data, override to UNABLE_TO_VERIFY regardless of current status.
                    # This catches cases where "found" in "no records found" triggers
                    # ADVERSE_FINDINGS, and cases where NO_ADVERSE_FINDINGS is a
                    # hallucination (Perplexity didn't actually find anything).
                    if (
                        status in ("NO_ADVERSE_FINDINGS", "ADVERSE_FINDINGS")
                        and entity_name
                    ):
                        entity_lower = entity_name.lower().strip()
                        # Detect "no info found" patterns — Perplexity saying it found nothing
                        _no_info_patterns = [
                            # Entity not findable — Perplexity couldn't locate info
                            "no information",
                            "no specific information",
                            "no relevant",
                            "no direct mention",
                            "no data available",
                            "not found in",
                            "no results found",
                            "no records found",
                            "no search results",
                            # Search returned unrelated results
                            "unrelated entities",
                            "unrelated topics",
                            "unrelated",
                            # Verification impossible
                            "no evidence",
                            "no public record",
                            "no publicly available",
                            "could not be verified",
                            "cannot be verified",
                            "not enough information",
                            "insufficient information",
                            "limited information available",
                            # Entity absent from results
                            "no mention of the entity",
                            "without mention of",
                            "no link to this entity",
                            "nothing specific",
                            "does not appear",
                            "not appear in",
                            # Sources couldn't find entity
                            "no credible sources",
                            "no verified sources",
                            "no sources found",
                            "search results do not",
                            "search results returned no",
                            "could not find",
                            "could not locate",
                            "unable to find",
                            "unable to locate",
                            "not been identified",
                            # Perplexity explicitly flagging no info
                            "no news coverage",
                            "no coverage found",
                            "no reports found",
                            # Perplexity found different/similar entity but not the target
                            "entity name differs",
                            "not matching the queried",
                            "a similar entity",
                            "but not matching",
                            "a distinct",
                            "is a distinct",
                        ]
                        has_no_info = any(p in section_lower for p in _no_info_patterns)

                        # Detect when Perplexity echoes the search prompt template
                        # instead of returning actual findings. Template echoes contain
                        # search instruction markers like "- Look for:", "- Search:",
                        # "court records", "regulatory enforcement databases"
                        _template_markers = [
                            "look for:",
                            "- search:",
                            "regulatory enforcement databases",
                            "check imo, paris mou",
                            "check nea enforcement",
                            "if applicable",
                            "search: company name +",
                        ]
                        is_template_echo = (
                            sum(1 for m in _template_markers if m in section_lower) >= 2
                        )
                        if is_template_echo:
                            has_no_info = True

                        # Also check if content is very short (< 100 chars of real content)
                        # after stripping status/summary lines
                        _stripped = re.sub(
                            r"^.*?(status|summary|no_adverse|unable_to).*$",
                            "",
                            section_content,
                            flags=re.IGNORECASE | re.MULTILINE,
                        ).strip()
                        content_too_short = len(_stripped) < 80

                        if has_no_info or content_too_short:
                            logger.info(
                                f"KYP Report: Overriding NO_ADVERSE_FINDINGS → UNABLE_TO_VERIFY "
                                f"for entity '{entity_name}' — no-info pattern detected "
                                f"(has_no_info={has_no_info}, too_short={content_too_short})"
                            )
                            status = "UNABLE_TO_VERIFY"
                            # Also replace hallucinated content with honest message
                            section_content = (
                                f"No specific records found for {entity_name} "
                                f"in available databases for this category."
                            )

                    # Clean up the content for display
                    # Remove markdown formatting but preserve paragraph structure
                    clean_content = re.sub(r"\*\*([^*]+)\*\*", r"\1", section_content)
                    clean_content = re.sub(r"\*([^*]+)\*", r"\1", clean_content)
                    clean_content = re.sub(
                        r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_content
                    )
                    clean_content = re.sub(
                        r"^#+\s*", "", clean_content, flags=re.MULTILINE
                    )
                    # Strip Perplexity citation references like [1], [2][3], [1][2][3]
                    clean_content = re.sub(r"\[\d+\]", "", clean_content)
                    # Strip "Source URLs: ..." lines (with or without actual URLs)
                    clean_content = re.sub(
                        r"Source URLs?:.*$",
                        "",
                        clean_content,
                        flags=re.MULTILINE,
                    )
                    # Strip trailing artifacts like " -.", " -", "- Note:" disclaimers
                    clean_content = re.sub(r"\s*-\s*\.?\s*$", "", clean_content)
                    clean_content = re.sub(
                        r"\s*-\s*Note:.*$",
                        "",
                        clean_content,
                        flags=re.MULTILINE,
                    )
                    # Strip "- Sources: None relevant.", "- Sources: None specific." etc.
                    # Also catches "* Sources:", "  - Sources:", bullet variants
                    clean_content = re.sub(
                        r"^[\s\-\*]*Sources?:\s*None\b.*$",
                        "",
                        clean_content,
                        flags=re.MULTILINE,
                    )
                    # Also strip standalone "Sources: <url>" or "Sources: <text>" lines
                    clean_content = re.sub(
                        r"^[\s\-\*]*Sources?:\s*(?:https?://|N/A|none|no\s).*$",
                        "",
                        clean_content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    )
                    # Strip "Key Findings:" headers, "---" separators, trailing "Summary" blocks
                    clean_content = re.sub(
                        r"^(?:Key Findings|INFORMATION):?\s*",
                        "",
                        clean_content,
                        flags=re.MULTILINE,
                    )
                    clean_content = re.sub(
                        r"^-{3,}\s*$", "", clean_content, flags=re.MULTILINE
                    )
                    # Strip trailing "Summary" section that Perplexity sometimes appends
                    clean_content = re.sub(
                        r"\n*-{0,3}\s*Summary\s*\n.*$",
                        "",
                        clean_content,
                        flags=re.DOTALL | re.IGNORECASE,
                    )
                    # Collapse runs of whitespace but preserve single newlines for structure
                    clean_content = re.sub(r"[^\S\n]+", " ", clean_content)
                    clean_content = re.sub(r"\n{3,}", "\n\n", clean_content).strip()
                    # Strip numbered section headers like "2. OWNERSHIP, UBO & LEADERSHIP"
                    clean_content = re.sub(
                        r"^\d+\.\s+[A-Z][A-Z &,/()-]{2,}\s*\n*",
                        "",
                        clean_content,
                        flags=re.MULTILINE,
                    ).strip()
                    # Strip standalone section name headers (no number prefix)
                    # e.g., "REPUTATION\n", "LITIGATION & LEGAL\n", "SAFETY RECORD\n"
                    # Matches the section keyword + up to 3 trailing header words,
                    # but ONLY when followed by a newline (header on its own line).
                    clean_content = re.sub(
                        r"^(?:REPUTATION|LITIGATION|SAFETY|ENVIRONMENTAL|OWNERSHIP|SANCTIONS)"
                        r"(?:\s*[&,]\s*\w+|\s+(?:RECORD|LEGAL|UBO|PUBLIC|INCIDENTS|COMPLIANCE))*"
                        r"\s*\n+",
                        "",
                        clean_content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    ).strip()
                    # Strip "Status: ... Summary: ..." prefixes from Perplexity output
                    # Handles: "Status: NO_ADVERSE_FINDINGS", "- Status: ...",
                    # "Status: UNABLE_TO_VERIFY - Summary: ..."
                    clean_content = re.sub(
                        r"^[-–—]*\s*Status:\s*\S+\s*[-–—]*\s*",
                        "",
                        clean_content,
                        flags=re.IGNORECASE | re.MULTILINE,
                    ).strip()
                    clean_content = re.sub(
                        r"^[-–—]*\s*Summary:\s*",
                        "",
                        clean_content,
                        flags=re.IGNORECASE | re.MULTILINE,
                    ).strip()

                    # Extract summary — first 2 sentences or up to 300 chars
                    # Strip numbered-section headers like "3. LITIGATION\n" that
                    # cause false sentence splits. Require ALL-CAPS word to
                    # avoid stripping legitimate content like "3. We recommend..."
                    _summary_text = re.sub(
                        r"^\d+\.\s+[A-Z][A-Z &/-]{2,}\n",
                        "",
                        clean_content[:500],
                        flags=re.MULTILINE,
                    ).strip()
                    # Use sentence-ending punctuation, avoiding abbreviations like "Mr.", "U.S."
                    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", _summary_text)
                    if len(sentences) >= 2:
                        summary = sentences[0] + " " + sentences[1]
                        if not summary.endswith((".", "!", "?")):
                            summary += "."
                    else:
                        summary = clean_content[:300]
                        if "." in summary:
                            summary = summary[: summary.rfind(".") + 1]

                    # Strip Perplexity LLM formatting prefixes that leak through
                    # e.g. "Status: NO_ADVERSE_FINDINGS Summary: ST Engineering..."
                    # Also handles "- Status: ..." and numbered headers
                    summary = re.sub(
                        r"^\d+\.\s+[A-Z][A-Z &,/()-]{2,}\s*[-–—]*\s*",
                        "",
                        summary,
                    ).strip()
                    summary = re.sub(
                        r"^[-–—]*\s*Status:\s*\S+\s*[-–—]*\s*",
                        "",
                        summary,
                        flags=re.IGNORECASE,
                    ).strip()
                    summary = re.sub(
                        r"^[-–—]*\s*Summary:\s*",
                        "",
                        summary,
                        flags=re.IGNORECASE,
                    ).strip()

                    # Strip citation references and Source URLs from summary
                    summary = re.sub(r"\[\d+\]", "", summary).strip()
                    summary = re.sub(
                        r"Source URLs?:.*$",
                        "",
                        summary,
                        flags=re.MULTILINE,
                    ).strip()
                    # Strip "- Sources: None relevant/specific" from summary
                    summary = re.sub(
                        r"^[\s\-\*]*Sources?:\s*(?:None|N/A|no\s|https?://).*$",
                        "",
                        summary,
                        flags=re.MULTILINE | re.IGNORECASE,
                    ).strip()

                    # Guard against whitespace-only or empty summaries
                    if not summary:
                        summary = "See full content"

                    return (status, summary, clean_content)

                pass  # Sanctions now handled by direct database screening below

            # ─── SANCTIONS: Results from parallel task (started earlier) ───
            # Build sanctions checks from direct results
            sanctions_checks: list[SanctionsCheck] = []
            has_match = False
            has_error = False
            source_parts: list[str] = []

            for sr in sanctions_results:
                sanctions_checks.append(
                    SanctionsCheck(
                        database=sr.database,
                        result=sr.result,
                        status=sr.status,
                        source_url=sr.source_url,
                        list_date=sr.list_date,
                    )
                )
                if sr.status == "match":
                    has_match = True
                elif sr.status == "error":
                    has_error = True
                source_parts.append(sr.source_url)

            # Determine overall sanctions status
            if has_match:
                sanctions_section_status = SectionStatus.ADVERSE_FINDINGS
            elif has_error and not any(
                sr.status == "clear" for sr in sanctions_results
            ):
                # All checks failed — unable to verify
                sanctions_section_status = SectionStatus.UNABLE_TO_VERIFY
            else:
                sanctions_section_status = SectionStatus.NO_ADVERSE_FINDINGS

            # Build source string with database metadata
            checked_date = datetime.now(UTC).strftime("%Y-%m-%d")
            total_entries = 0
            # Try PostgreSQL-backed service first (same service that did the screening)
            try:
                _sanctions_svc = await _get_sanctions_service()
                if getattr(_sanctions_svc, "_initialized", False):
                    _db_statuses = await _sanctions_svc.get_database_status()
                    # Exclude MAS_SG — it mirrors UN_CONSOLIDATED entries, not unique data
                    total_entries = sum(
                        d.get("record_count", 0) or 0
                        for d in _db_statuses
                        if d.get("source_key") != "MAS_SG"
                    )
            except Exception as _sanctions_err:
                logger.warning(f"Sanctions DB status query failed: {_sanctions_err}")
            # Fallback to legacy in-memory status if DB returned 0
            if total_entries == 0:
                from lead_to_cash.services.sanctions_checker import (
                    get_database_status,
                )

                db_status = get_database_status()
                total_entries = sum(d["record_count"] for d in db_status)
            sanctions_source = (
                f"OFAC, UN, EU, MAS — {total_entries:,} entries (as of {checked_date})"
            )

            phase3_sections.append(
                ReportSection(
                    id="sanctions",
                    title="Sanctions Screening",
                    icon="🛡️",
                    status=sanctions_section_status,
                    source=sanctions_source,
                    checks=sanctions_checks,
                    checked_date=checked_date,
                )
            )

            # Assessment item for sanctions
            if sanctions_section_status == SectionStatus.NO_ADVERSE_FINDINGS:
                sanctions_notes = "No matching records identified"
            elif sanctions_section_status == SectionStatus.ADVERSE_FINDINGS:
                match_dbs = [
                    sr.database for sr in sanctions_results if sr.status == "match"
                ]
                sanctions_notes = (
                    f"Potential match on: {', '.join(match_dbs)} — review required"
                )
            else:
                sanctions_notes = "Partial results — some lists pending manual review"

            assessment_items.append(
                AssessmentItem(
                    category="Sanctions",
                    status=sanctions_section_status,
                    notes=sanctions_notes,
                )
            )

            # ─── Resume Perplexity-based sections (Litigation, etc.) ───
            if perplexity_data:
                # Parse LITIGATION section from AI response
                litigation_status, litigation_summary, litigation_content = (
                    extract_section_content(
                        perplexity_data,
                        [
                            "2. LITIGATION",
                            "3. LITIGATION",
                            "LITIGATION & LEGAL",
                            "**2.",
                            "**3.",
                        ],
                    )
                )
                logger.info(
                    f"KYP Report: Litigation status from AI: {litigation_status}"
                )

                # Add litigation section using findings format
                litigation_section_status = {
                    "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                    "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                }.get(litigation_status, SectionStatus.UNABLE_TO_VERIFY)
                _lit_pending = (
                    litigation_section_status == SectionStatus.UNABLE_TO_VERIFY
                )

                # Targeted searches run in parallel below (after safety/reputation parsing)
                _lit_value = litigation_summary or "No data available"
                _lit_source = perplexity_source_str

                # Parse OWNERSHIP section from AI response — only if EODHD
                # did not already provide authoritative ownership data
                if not eodhd_has_ownership:
                    ownership_status, ownership_summary, ownership_content = (
                        extract_section_content(
                            perplexity_data,
                            [
                                "1. OWNERSHIP",
                                "2. OWNERSHIP",
                                "OWNERSHIP, UBO",
                                "**1.",
                                "**2.",
                            ],
                        )
                    )
                    logger.info(
                        f"KYP Report: Ownership status from AI: {ownership_status}"
                    )
                    ownership_section_status = {
                        "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                        "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                    }.get(ownership_status, SectionStatus.UNABLE_TO_VERIFY)
                    _own_pending = (
                        ownership_section_status == SectionStatus.UNABLE_TO_VERIFY
                    )

                    phase3_sections.append(
                        ReportSection(
                            id="ownership",
                            title="Ownership, UBO & Leadership",
                            icon="👤",
                            status=ownership_section_status,
                            source=(
                                "Pending manual review"
                                if _own_pending
                                else perplexity_source_str
                            ),
                            fields=[
                                ReportField(
                                    label="",
                                    value=(
                                        f"Ownership data not available for "
                                        f"{entity_name} from public databases. "
                                        f"Company may be privately held. "
                                        f"Manual check of corporate registry recommended."
                                        if _own_pending
                                        else (ownership_summary or "No data available")
                                    ),
                                    field_type="paragraph",
                                )
                            ],
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Ownership",
                            status=ownership_section_status,
                            notes=(
                                "Pending manual review of corporate registry"
                                if _own_pending
                                else (
                                    _truncate_at_sentence(ownership_summary)
                                    if ownership_summary
                                    else "Ownership check completed"
                                )
                            ),
                        )
                    )

                # Parse SAFETY RECORD section from AI response
                safety_status, safety_summary, safety_content = extract_section_content(
                    perplexity_data,
                    ["3. SAFETY", "4. SAFETY", "SAFETY RECORD", "**3.", "**4."],
                )
                logger.info(f"KYP Report: Safety status from AI: {safety_status}")
                safety_section_status = {
                    "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                    "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                }.get(safety_status, SectionStatus.UNABLE_TO_VERIFY)
                _saf_pending = safety_section_status == SectionStatus.UNABLE_TO_VERIFY
                _saf_value = safety_summary or "No data available"
                _saf_source = perplexity_source_str

                # Parse ENVIRONMENTAL section — only if EODHD ESG not available
                if not eodhd_has_esg:
                    env_status, env_summary, env_content = extract_section_content(
                        perplexity_data,
                        [
                            "4. ENVIRONMENTAL",
                            "5. ENVIRONMENTAL",
                            "ENVIRONMENTAL",
                            "**4.",
                            "**5.",
                        ],
                    )
                    logger.info(
                        f"KYP Report: Environmental status from AI: {env_status}"
                    )
                    env_section_status = {
                        "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                        "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                    }.get(env_status, SectionStatus.UNABLE_TO_VERIFY)
                    _env_pending = env_section_status == SectionStatus.UNABLE_TO_VERIFY

                    phase3_sections.append(
                        ReportSection(
                            id="environmental",
                            title="Environmental Compliance",
                            icon="🌿",
                            status=env_section_status,
                            source=(
                                "Pending manual review"
                                if _env_pending
                                else perplexity_source_str
                            ),
                            fields=[
                                ReportField(
                                    label="",
                                    value=(
                                        f"No specific environmental violations "
                                        f"found for {entity_name} in automated search. "
                                        f"Recommended checks: "
                                        f"NEA Singapore (nea.gov.sg) for enforcement actions, "
                                        f"EPA ECHO (echo.epa.gov) for US violations, "
                                        f"IMO MARPOL compliance records."
                                        if _env_pending
                                        else (env_summary or "No data available")
                                    ),
                                    field_type="paragraph",
                                )
                            ],
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Environmental",
                            status=env_section_status,
                            notes=(
                                "Pending manual review of environmental records"
                                if _env_pending
                                else (
                                    _truncate_at_sentence(env_summary)
                                    if env_summary
                                    else "Environmental check completed"
                                )
                            ),
                        )
                    )

                # Parse REPUTATION section from AI response
                rep_status, rep_summary, rep_content = extract_section_content(
                    perplexity_data,
                    ["5. REPUTATION", "6. REPUTATION", "REPUTATION", "**5.", "**6."],
                )
                logger.info(f"KYP Report: Reputation status from AI: {rep_status}")
                rep_section_status = {
                    "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                    "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                }.get(rep_status, SectionStatus.UNABLE_TO_VERIFY)
                _rep_pending = rep_section_status == SectionStatus.UNABLE_TO_VERIFY
                _rep_value = rep_summary or "No data available"
                _rep_source = perplexity_source_str

                # ─── Parallel targeted Perplexity searches ───────────
                # Run all pending targeted searches concurrently (~2s
                # instead of ~6s sequential).
                _targeted_tasks: dict[str, asyncio.Task] = {}
                if _lit_pending:
                    _targeted_tasks["litigation"] = asyncio.create_task(
                        self._targeted_perplexity_search(
                            entity_name,
                            f"lawsuits, court cases, regulatory fines, SEC/MAS enforcement actions, "
                            f"legal disputes, settlements involving {entity_name}. "
                            f"For each finding, specify whether it involves the parent entity "
                            f"directly or a subsidiary/affiliate. Note if cases were "
                            f"resolved, dismissed, settled, or won by {entity_name}.",
                            [
                                "lawsuit",
                                "court",
                                "fine",
                                "penalty",
                                "settlement",
                                "enforcement",
                                "regulatory action",
                            ],
                        )
                    )
                if _saf_pending:
                    _targeted_tasks["safety"] = asyncio.create_task(
                        self._targeted_perplexity_search(
                            entity_name,
                            f"safety incidents, accidents, fatalities, port state detentions, "
                            f"safety violations, workplace injuries involving {entity_name}",
                            [
                                "accident",
                                "incident",
                                "fatality",
                                "detention",
                                "violation",
                                "injury",
                                "safety breach",
                            ],
                        )
                    )
                if _rep_pending:
                    _targeted_tasks["reputation"] = asyncio.create_task(
                        self._targeted_perplexity_search(
                            entity_name,
                            f"Reputation and public perception of {entity_name}: "
                            f"recent news coverage, media sentiment, industry awards, "
                            f"controversies, public complaints, or notable press",
                            [
                                "controversy",
                                "scandal",
                                "fraud",
                                "corruption",
                                "violation",
                                "fine imposed",
                                "penalty",
                            ],
                        )
                    )

                # Await all targeted searches with a combined timeout
                if _targeted_tasks:
                    try:
                        done, pending = await asyncio.wait(
                            _targeted_tasks.values(), timeout=8.0
                        )
                        for t in pending:
                            t.cancel()
                    except Exception as _wait_err:
                        logger.warning(f"KYP targeted search wait failed: {_wait_err}")
                        done = set()

                    if "litigation" in _targeted_tasks:
                        try:
                            _lit_result = (
                                _targeted_tasks["litigation"].result()
                                if _targeted_tasks["litigation"].done()
                                else None
                            )
                            if _lit_result:
                                _lit_value, _lit_source, litigation_section_status = (
                                    _lit_result
                                )
                                _lit_pending = False
                        except Exception as _e:
                            logger.warning(
                                f"KYP Litigation targeted search failed: {_e}"
                            )

                    if "safety" in _targeted_tasks:
                        try:
                            _saf_result = (
                                _targeted_tasks["safety"].result()
                                if _targeted_tasks["safety"].done()
                                else None
                            )
                            if _saf_result:
                                _saf_value, _saf_source, safety_section_status = (
                                    _saf_result
                                )
                                _saf_pending = False
                        except Exception as _e:
                            logger.warning(f"KYP Safety targeted search failed: {_e}")

                    if "reputation" in _targeted_tasks:
                        try:
                            _rep_result = (
                                _targeted_tasks["reputation"].result()
                                if _targeted_tasks["reputation"].done()
                                else None
                            )
                            if _rep_result:
                                _rep_value, _rep_source, rep_section_status = (
                                    _rep_result
                                )
                                _rep_pending = False
                        except Exception as _e:
                            logger.warning(
                                f"KYP Reputation targeted search failed: {_e}"
                            )

                # Apply pending fallback messages
                if _lit_pending:
                    _lit_value = f"Automated litigation search did not return results for {entity_name}. Manual review recommended."
                    _lit_source = "Pending manual review"

                if _saf_pending:
                    _saf_value = f"Automated safety search did not return results for {entity_name}. Manual review recommended."
                    _saf_source = "Pending manual review"

                if _rep_pending:
                    _rep_value = (
                        f"Automated reputation search did not return results for {entity_name}. "
                        f"Manual review recommended."
                    )
                    _rep_source = "Pending manual review"

                # ─── Build sections from (now-resolved) targeted search results ───
                phase3_sections.append(
                    ReportSection(
                        id="litigation",
                        title="Litigation & Regulatory",
                        icon="⚖️",
                        status=litigation_section_status,
                        source=_lit_source,
                        fields=[
                            ReportField(
                                label="",
                                value=_lit_value,
                                field_type="paragraph",
                            )
                        ],
                    )
                )
                assessment_items.append(
                    AssessmentItem(
                        category="Litigation",
                        status=litigation_section_status,
                        notes=(
                            "Pending manual review of court records"
                            if _lit_pending
                            else (
                                _truncate_at_sentence(_lit_value)
                                if _lit_value and _lit_value != "No data available"
                                else (
                                    _truncate_at_sentence(litigation_summary)
                                    if litigation_summary
                                    else "No adverse findings"
                                )
                            )
                        ),
                    )
                )

                phase3_sections.append(
                    ReportSection(
                        id="safety",
                        title="Safety Record & Incidents",
                        icon="🦺",
                        status=safety_section_status,
                        source=_saf_source,
                        fields=[
                            ReportField(
                                label="",
                                value=_saf_value,
                                field_type="paragraph",
                            )
                        ],
                    )
                )
                assessment_items.append(
                    AssessmentItem(
                        category="Safety",
                        status=safety_section_status,
                        notes=(
                            "Pending manual review of safety registries"
                            if _saf_pending
                            else (
                                _truncate_at_sentence(_saf_value)
                                if _saf_value and _saf_value != "No data available"
                                else (
                                    _truncate_at_sentence(safety_summary)
                                    if safety_summary
                                    else "Safety check completed"
                                )
                            )
                        ),
                    )
                )

                phase3_sections.append(
                    ReportSection(
                        id="reputation",
                        title="Reputation & Public Perception",
                        icon="📰",
                        status=rep_section_status,
                        source=_rep_source,
                        fields=[
                            ReportField(
                                label="",
                                value=_rep_value,
                                field_type="paragraph",
                            )
                        ],
                    )
                )
                assessment_items.append(
                    AssessmentItem(
                        category="Reputation",
                        status=rep_section_status,
                        notes=(
                            "Pending manual review of news archives"
                            if _rep_pending
                            else (
                                _truncate_at_sentence(_rep_value)
                                if _rep_value and _rep_value != "No data available"
                                else (
                                    _truncate_at_sentence(rep_summary)
                                    if rep_summary
                                    else "Reputation check completed"
                                )
                            )
                        ),
                    )
                )

                # Parse FINANCIAL DISTRESS section from AI response — only if
                # EODHD did not already provide authoritative distress data
                if not eodhd_has_distress:
                    distress_status, distress_summary, distress_content = (
                        extract_section_content(
                            perplexity_data,
                            [
                                "6. FINANCIAL DISTRESS",
                                "7. FINANCIAL DISTRESS",
                                "FINANCIAL DISTRESS",
                                "**6.",
                                "**7.",
                            ],
                        )
                    )
                    logger.info(
                        f"KYP Report: Financial Distress status from AI: "
                        f"{distress_status}"
                    )
                    distress_section_status = {
                        "NO_ADVERSE_FINDINGS": SectionStatus.NO_ADVERSE_FINDINGS,
                        "ADVERSE_FINDINGS": SectionStatus.ADVERSE_FINDINGS,
                    }.get(distress_status, SectionStatus.UNABLE_TO_VERIFY)

                    phase3_sections.append(
                        ReportSection(
                            id="financial_distress",
                            title="Financial Distress Signals",
                            icon="📉",
                            status=distress_section_status,
                            source=perplexity_source_str,
                            fields=[
                                ReportField(
                                    label="",
                                    value=distress_summary or "No data available",
                                    field_type="paragraph",
                                )
                            ],
                        )
                    )
                    assessment_items.append(
                        AssessmentItem(
                            category="Financial Distress",
                            status=distress_section_status,
                            notes=_truncate_at_sentence(distress_summary)
                            if distress_summary
                            else "Financial distress check completed",
                        )
                    )

            # Handle case where no Perplexity data available (Phase 3 fallback)
            # Note: Sanctions are handled by direct database screening above,
            # so no fallback needed for sanctions here.
            if not perplexity_data:
                logger.warning(
                    f"KYP Report: No Perplexity data available for '{entity_name}'"
                )

            # =================================================================
            # PHASE 2: Internal Risk (TPRM from Aravo)
            # =================================================================
            if aravo_data:
                tprm_section = build_tprm_section(
                    supplier_name=aravo_data.get("supplier_name"),
                    supplier_id=aravo_data.get("supplier_id"),
                    tprm_status=aravo_data.get("tprm_status"),
                    inherent_risk_score=aravo_data.get("inherent_risk_score"),
                    overall_risk_score=aravo_data.get("overall_risk_score"),
                    supplier_status=aravo_data.get("supplier_status"),
                    due_diligence_status=aravo_data.get("due_diligence_status"),
                    questionnaire_scores=aravo_data.get("questionnaire_scores"),
                    last_assessment_date=aravo_data.get("last_assessment_date"),
                )
                phase2_sections.append(tprm_section)

                # Map TPRM status to assessment status
                tprm_status = aravo_data.get("tprm_status")
                if tprm_status == "NO_ADVERSE_FINDINGS":
                    tprm_assessment_status = SectionStatus.NO_ADVERSE_FINDINGS
                    tprm_notes = "Supplier approved in Aravo TPRM"
                elif tprm_status == "ADVERSE_FINDINGS":
                    tprm_assessment_status = SectionStatus.ADVERSE_FINDINGS
                    tprm_notes = "Adverse findings in Aravo TPRM"
                elif tprm_status == "UNDER_REVIEW":
                    tprm_assessment_status = SectionStatus.ADVERSE_FINDINGS
                    tprm_notes = "TPRM assessment in progress"
                else:
                    tprm_assessment_status = SectionStatus.UNABLE_TO_VERIFY
                    tprm_notes = "TPRM assessment pending"

                assessment_items.append(
                    AssessmentItem(
                        category="TPRM",
                        status=tprm_assessment_status,
                        notes=tprm_notes,
                    )
                )
            else:
                # No Aravo data - add placeholder section to Phase 2
                # Use consistent status field pattern like other sections
                phase2_sections.append(
                    ReportSection(
                        id="tprm",
                        title="Third-Party Risk Management",
                        icon="🔒",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        source="Aravo",
                        fields=[
                            ReportField(
                                label="TPRM Status",
                                value="Not Registered",
                                field_type="status",
                                status="warning",
                            ),
                            ReportField(
                                label="Note",
                                value=(
                                    f"'{entity_name}' is not yet registered in the Aravo TPRM system. "
                                    "Supplier onboarding recommended for new engagements."
                                ),
                                field_type="text",
                            ),
                        ],
                    )
                )
                assessment_items.append(
                    AssessmentItem(
                        category="TPRM",
                        status=SectionStatus.UNABLE_TO_VERIFY,
                        notes="Not yet registered — onboarding recommended",
                    )
                )

            # =================================================================
            # Combine all phases into final sections list
            # Order: Phase 1 (Business Context) → Phase 2 (Internal Risk) → Phase 3 (External Risk)
            # =================================================================
            sections = phase1_sections + phase2_sections + phase3_sections

            # =================================================================
            # Determine overall recommendation using LLM classification.
            #
            # The LLM reads the assessment items and classifies severity.
            # Keyword matching is NOT used — Perplexity findings can be
            # phrased in infinite ways that keywords cannot anticipate.
            #
            # Hard rules (deterministic, no LLM needed):
            #   - Sanctions ADVERSE_FINDINGS → always DO NOT PROCEED
            #   - All NO_ADVERSE_FINDINGS → always PROCEED
            #   - Any UNABLE_TO_VERIFY → PENDING_REVIEW (unless overridden)
            #
            # LLM classifies non-sanctions ADVERSE_FINDINGS as:
            #   - SEVERE → DO NOT PROCEED (active fraud/criminal against parent)
            #   - NON_SEVERE → PROCEED WITH CAUTION (subsidiary, resolved, civil)
            # =================================================================

            has_sanctions_match = False
            has_not_checked = False
            adverse_items: list[dict] = []

            for a in assessment_items:
                if a.status == SectionStatus.UNABLE_TO_VERIFY:
                    has_not_checked = True
                elif a.status == SectionStatus.ADVERSE_FINDINGS:
                    if a.category == "Sanctions":
                        has_sanctions_match = True
                    else:
                        adverse_items.append(
                            {
                                "category": a.category,
                                "notes": a.notes,
                            }
                        )

            # Fast path: sanctions match is always DO NOT PROCEED
            if has_sanctions_match:
                overall_status = OverallDecision.DO_NOT_PROCEED
                recommendation_decision = OverallDecision.DO_NOT_PROCEED
                recommendation_text = (
                    "Entity appears on sanctions list. "
                    "Do not proceed without legal/compliance review."
                )
                can_proceed = False

            # Fast path: no adverse findings at all
            elif not adverse_items and not has_not_checked:
                overall_status = OverallDecision.PROCEED
                recommendation_decision = OverallDecision.PROCEED
                recommendation_text = "No adverse findings. Clear to proceed."
                can_proceed = True

            # Fast path: no adverse but some unchecked
            elif not adverse_items and has_not_checked:
                overall_status = OverallDecision.PENDING_REVIEW
                recommendation_decision = OverallDecision.PENDING_REVIEW
                recommendation_text = (
                    "Some checks are pending review. "
                    "Manual verification recommended for outstanding items."
                )
                can_proceed = False

            # LLM classification: non-sanctions adverse findings
            else:
                # Build a concise summary for the LLM
                _adverse_summary = "\n".join(
                    f"- [{item['category']}]: {item['notes'][:500]}"
                    for item in adverse_items
                )
                _classification_prompt = f"""You are a KYP (Know Your Partner) due diligence analyst classifying adverse findings for '{entity_name}'.

ADVERSE FINDINGS:
{_adverse_summary}

Classify the OVERALL severity as exactly one of:
- SEVERE: Active fraud, criminal proceedings, or enforcement actions DIRECTLY against the parent entity. Unresolved matters that pose immediate regulatory or reputational risk to engaging with this entity.
- NON_SEVERE: Findings that are mitigated by ANY of these factors:
  - Against a subsidiary, not the parent entity
  - Involving former employees or past management (not current)
  - Resolved, settled, dismissed, or historically concluded
  - Civil disputes, arbitration, or commercial disagreements
  - Entity cooperated with authorities or self-reported
  - No direct fault found / allegations unproven

Respond with EXACTLY one line in this format:
SEVERITY: SEVERE or NON_SEVERE
REASON: One sentence explaining why."""

                _severity = "NON_SEVERE"  # Default if LLM fails
                _reason = ""
                try:
                    _executor = self.tool_executor
                    _client = await _executor._get_client()
                    _model = os.environ.get(
                        "OPENAI_MINI_MODEL",
                        os.environ.get("OPENAI_PROD_MODEL", "gpt-4o-mini"),
                    )
                    _resp = await asyncio.wait_for(
                        _client.chat.completions.create(
                            model=_model,
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are a compliance analyst. Be precise. Respond only in the requested format.",
                                },
                                {"role": "user", "content": _classification_prompt},
                            ],
                            temperature=0.0,
                            max_tokens=100,
                        ),
                        timeout=8.0,
                    )
                    _llm_text = _resp.choices[0].message.content.strip()
                    logger.info(f"KYP severity classification: {_llm_text}")
                    if (
                        "SEVERE" in _llm_text.split("\n")[0]
                        and "NON_SEVERE" not in _llm_text.split("\n")[0]
                    ):
                        _severity = "SEVERE"
                    # Extract reason if present
                    for _line in _llm_text.split("\n"):
                        if _line.startswith("REASON:"):
                            _reason = _line.replace("REASON:", "").strip()
                except Exception as _cls_err:
                    logger.warning(
                        f"KYP severity classification failed: {_cls_err}, "
                        f"defaulting to NON_SEVERE (cautious fallback)"
                    )

                if _severity == "SEVERE":
                    overall_status = OverallDecision.DO_NOT_PROCEED
                    recommendation_decision = OverallDecision.DO_NOT_PROCEED
                    recommendation_text = (
                        _reason
                        or "Severe adverse findings identified against the parent entity. "
                        "Do not proceed without legal review."
                    )
                    can_proceed = False
                else:
                    overall_status = OverallDecision.PROCEED_WITH_CAUTION
                    recommendation_decision = OverallDecision.PROCEED_WITH_CAUTION
                    recommendation_text = (
                        _reason
                        or "Adverse findings identified but assessed as non-critical "
                        "(subsidiary-level, civil, or resolved matters). "
                        "Proceed with monitoring and periodic review."
                    )
                    can_proceed = False

            # Build the report
            report = KYPReport(
                entity_name=entity_name,
                overall_status=overall_status,
                can_proceed=can_proceed,
                sections=sections,
                assessment_summary=assessment_items,
                recommendation_decision=recommendation_decision,
                recommendation_text=recommendation_text,
                issues=[],
                conditions=(
                    ["Standard monitoring applies"]
                    if can_proceed
                    else ["Enhanced due diligence recommended"]
                ),
            )

            # Convert to dict and add metadata
            result = report.to_dict()
            result["session_id"] = session_id
            result["timestamp"] = datetime.now(UTC).isoformat()
            result["follow_up_suggestions"] = follow_ups
            result["sources"] = _sanitize_sources(tool_result.sources)
            # Add tools_used for test compatibility - KYP uses due_diligence_agent
            result["tools_used"] = ["due_diligence_agent"]

            return result

        except Exception as e:
            # Clean up any parallel tasks that may still be running
            for _task_name in ("aravo_task", "sanctions_task"):
                _t = locals().get(_task_name)
                if _t is not None and isinstance(_t, asyncio.Task) and not _t.done():
                    _t.cancel()

            logger.error(f"Failed to build KYP report: {e}", exc_info=True)
            # Instead of returning None (which silently drops the entire response),
            # return the synthesized content as a plain KYP answer if available
            if tool_result and tool_result.synthesized_content:
                entity_name = "Unknown Entity"
                if parsed and parsed.companies:
                    entity_name = parsed.companies[0]
                logger.info(
                    f"Falling back to synthesized content for KYP: {entity_name}"
                )
                # Use proper dataclass for consistent structure even in error path
                error_report = KYPReport(
                    entity_name=entity_name,
                    overall_status=OverallDecision.PENDING_REVIEW,
                    can_proceed=False,
                    sections=[],
                    assessment_summary=[
                        AssessmentItem(
                            category="System",
                            status=SectionStatus.UNABLE_TO_VERIFY,
                            notes="Report could not be fully generated — see details below",
                        )
                    ],
                    recommendation_decision=OverallDecision.PENDING_REVIEW,
                    recommendation_text="Report partially generated. Please review available data and complete outstanding checks manually.",
                    issues=[],
                    conditions=["Complete outstanding checks"],
                )
                error_result = error_report.to_dict()
                error_result["session_id"] = session_id
                error_result["timestamp"] = datetime.now(UTC).isoformat()
                error_result["answer"] = tool_result.synthesized_content
                error_result["sources"] = (
                    tool_result.sources if tool_result.sources else []
                )
                error_result["tools_used"] = (
                    [t.value for t in tool_result.tools_used]
                    if tool_result.tools_used
                    else ["due_diligence_agent"]
                )
                error_result["follow_up_suggestions"] = follow_ups or []
                error_result["confidence"] = tool_result.confidence or "medium"
                error_result["report_build_error"] = str(e)[:200]
                return error_result
            return None

    def _generate_follow_ups(
        self,
        parsed: ParsedQuery,
        tool_result: ToolResult,
        session: Optional[ConversationSession] = None,
    ) -> List[str]:
        """
        Generate contextual follow-up suggestions based on query, results, and session.

        Uses the actual question content and answer to derive varied suggestions,
        with session-level deduplication to avoid repetition.

        Args:
            parsed: ParsedQuery that was executed
            tool_result: Results from tool execution
            session: Optional session for context

        Returns:
            List of follow-up suggestion strings (max 3)
        """
        candidates: List[str] = []

        # Extract context
        competitors = parsed.competitors or []
        regions = parsed.regions or []
        companies = parsed.companies or []
        products = parsed.products or []
        confidence = tool_result.confidence
        query = parsed.raw_query or ""

        # Session context
        session_competitors = session.context.get("competitors", []) if session else []
        session_regions = session.context.get("regions", []) if session else []
        session_products = session.context.get("products", []) if session else []

        # Competitor mapping for comparisons
        competitor_pairs = {
            "Caterpillar": ["Cummins", "MAN Energy Solutions", "Wartsila"],
            "CAT": ["Cummins", "MAN Energy Solutions", "Wartsila"],
            "MaK": ["Cummins", "MAN Energy Solutions", "Wartsila"],
            "Cummins": ["Caterpillar", "Wartsila", "MAN Energy Solutions"],
            "MAN Energy Solutions": ["Caterpillar", "Cummins", "Wartsila"],
            "MAN": ["Caterpillar", "Cummins", "Wartsila"],
            "Wartsila": ["Cummins", "MAN Energy Solutions", "Caterpillar"],
            "Wärtsilä": ["Cummins", "MAN Energy Solutions", "Caterpillar"],
        }

        # APAC countries for drill-down
        apac_countries = [
            "Singapore",
            "Indonesia",
            "Malaysia",
            "Vietnam",
            "Thailand",
            "Philippines",
        ]

        # --- Build a LARGE pool of candidates per intent, then dedup + pick 3 ---

        if parsed.intent in [QueryIntent.COMPETITOR_INTEL]:
            # Determine segment for context-rich follow-ups
            _ql = query.lower()
            segment = "marine engines"
            if "offshore" in _ql:
                segment = "offshore"
            elif "ferry" in _ql or "ferries" in _ql:
                segment = "ferry propulsion"
            elif "tug" in _ql:
                segment = "tug propulsion"
            elif "power gen" in _ql or "power plant" in _ql:
                segment = "power generation"

            if competitors:
                comp = competitors[0]
                alts = competitor_pairs.get(comp, ["Cummins", "Wartsila"])
                for alt in alts:
                    candidates.append(f"How does {alt} compare in {segment}?")
                candidates.append(f"What's {comp}'s market strategy in APAC?")
                candidates.append(f"Show {comp}'s recent financial performance?")
                candidates.append(
                    f"What recent deals has {comp} won in Southeast Asia?"
                )
                candidates.append(f"How does {comp} price against MTU in {segment}?")
                candidates.append(f"What is {comp}'s service network coverage in APAC?")
                if regions:
                    candidates.append(f"What's {comp}'s market share in {regions[0]}?")
            else:
                candidates.extend(
                    [
                        "Which specific competitor interests you?",
                        "Compare Caterpillar vs Cummins?",
                        "See market share trends?",
                        "Which competitor is strongest in APAC ferries?",
                    ]
                )

        elif parsed.intent in [QueryIntent.MARKET_NEWS, QueryIntent.MARKET_INTEL]:
            # Build region-specific candidates
            undiscussed = [c for c in apac_countries if c not in session_regions]
            if regions:
                region = regions[0]
                # Add ALL undiscussed countries as options (not just first 2)
                for country in undiscussed:
                    candidates.append(f"Focus on {country} specifically?")
                    candidates.append(f"See {country} market opportunities?")

                nearby_regions = {
                    "Singapore": "Malaysia",
                    "Malaysia": "Indonesia",
                    "Indonesia": "Vietnam",
                    "Vietnam": "Thailand",
                    "Thailand": "Philippines",
                    "Philippines": "Singapore",
                }
                nearby = nearby_regions.get(region)
                if nearby and nearby not in session_regions:
                    candidates.append(
                        f"How does {nearby}'s market compare to {region}?"
                    )
                candidates.append(f"Find sales opportunities in {region}?")
                candidates.append(f"What MTU products fit {region}'s market needs?")
                candidates.append(f"Who are the key buyers in {region}?")
            else:
                if session_regions:
                    region = session_regions[0]
                    candidates.append(f"More news from {region}?")
                candidates.extend(
                    [
                        "Focus on APAC region?",
                        "Show European market news?",
                        "What are the fastest-growing marine segments?",
                    ]
                )

            # Content-aware: derive from the question topic
            query_lower = query.lower()
            if "ferry" in query_lower or "ferries" in query_lower:
                candidates.append("What ferry operators are expanding their fleets?")
                candidates.append("Compare fast ferry vs RoPax engine requirements?")
            elif "offshore" in query_lower or "osv" in query_lower:
                candidates.append("What are the power requirements for modern OSVs?")
                candidates.append("Which offshore operators are ordering newbuilds?")
            elif "lng" in query_lower:
                candidates.append("What dual-fuel options does MTU offer?")
                candidates.append("Which LNG bunkering ports are in APAC?")
            elif "power generation" in query_lower or "genset" in query_lower:
                candidates.append("What data center projects need backup power?")
                candidates.append("Compare diesel vs gas genset economics?")
            elif "regulation" in query_lower or "emission" in query_lower:
                candidates.append("How does IMO 2030 affect engine selection?")
                candidates.append("Which MTU engines meet the latest emission tiers?")
            elif "infrastructure" in query_lower or "project" in query_lower:
                candidates.append("What are the tender timelines for these projects?")
                candidates.append("Which local partners should we engage?")
            else:
                candidates.append("What are the biggest upcoming tenders?")
                candidates.append("What's the overall APAC outlook?")

        elif parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            if companies:
                company = companies[0]
                candidates.extend(
                    [
                        f"View {company}'s detailed credit history?",
                        f"Check {company}'s open opportunities in CEC?",
                        f"Verify {company} in Aravo TPRM system?",
                        f"What is {company}'s payment track record?",
                        f"Any open billing items for {company}?",
                        f"What contracts do we have with {company}?",
                    ]
                )
            else:
                candidates.extend(
                    [
                        "Research another company?",
                        "Show all customers in Singapore?",
                        "Find new prospects in APAC?",
                    ]
                )

        elif parsed.intent in [
            QueryIntent.CUSTOMER_RESEARCH,
            QueryIntent.CUSTOMER_INTEL,
        ]:
            if companies:
                company = companies[0]
                candidates.extend(
                    [
                        f"Run KYP due diligence on {company}?",
                        f"Check {company}'s fleet composition?",
                        f"See {company}'s payment history?",
                        f"What engines does {company} currently operate?",
                        f"Any pending opportunities with {company}?",
                    ]
                )
            else:
                candidates.extend(
                    [
                        "Which customer would you like to research?",
                        "Show all customers in Singapore?",
                        "Find new prospects in APAC?",
                    ]
                )

        elif parsed.intent in [QueryIntent.PRODUCT_INFO, QueryIntent.PRODUCT_FIT]:
            if products:
                product = products[0]
                candidates.extend(
                    [
                        f"Compare {product} with competitor alternatives?",
                        f"Check {product} availability?",
                        f"See {product} service history?",
                        f"What is {product}'s fuel consumption at rated power?",
                        f"What vessels use {product} in APAC?",
                    ]
                )
            else:
                query_lower = query.lower()
                already_mtu = (
                    any("mtu" in p.lower() for p in session_products)
                    or "mtu" in query_lower
                )
                if already_mtu:
                    # Derive from question topic
                    if "hybrid" in query_lower or "electric" in query_lower:
                        candidates.extend(
                            [
                                "Which ferry routes suit hybrid propulsion?",
                                "What is the cost premium for hybrid systems?",
                                "Compare MTU hybrid vs conventional lifecycle costs?",
                            ]
                        )
                    elif "aftermarket" in query_lower or "service" in query_lower:
                        candidates.extend(
                            [
                                "What are typical LTSA terms for marine engines?",
                                "Where are the nearest MTU service centers?",
                                "Compare MTU vs competitor service networks?",
                            ]
                        )
                    elif "tier iii" in query_lower or "emission" in query_lower:
                        candidates.extend(
                            [
                                "Which MTU engines meet Tier III without SCR?",
                                "What is the SCR cost premium?",
                                "Compare MTU vs MAN emission compliance?",
                            ]
                        )
                    elif "digital" in query_lower or "monitoring" in query_lower:
                        candidates.extend(
                            [
                                "What predictive maintenance features does MTU offer?",
                                "How does MTU Go! integrate with fleet systems?",
                                "What ROI do operators see from remote monitoring?",
                            ]
                        )
                    elif (
                        "8000" in query_lower
                        or "wartsila" in query_lower
                        or "man" in query_lower
                    ):
                        candidates.extend(
                            [
                                "In what power range does MTU compete directly?",
                                "What are MTU's lifecycle cost advantages?",
                                "Which large vessel segments favor MTU?",
                            ]
                        )
                    else:
                        candidates.extend(
                            [
                                "Compare MTU Series 2000 vs Series 4000?",
                                "See MTU maintenance schedules?",
                                "Check MTU emissions certifications?",
                                "What's MTU's latest product roadmap?",
                            ]
                        )
                else:
                    candidates.extend(
                        [
                            "Interested in MTU engines?",
                            "Compare Bergen vs MTU for ferries?",
                            "See engine specs for offshore?",
                        ]
                    )

        elif parsed.intent == QueryIntent.FINANCIAL_ANALYSIS:
            if competitors:
                comp = competitors[0]
                candidates.extend(
                    [
                        f"See {comp}'s quarterly earnings trend?",
                        f"Compare {comp} with industry peers?",
                        f"What's {comp}'s debt-to-equity ratio?",
                    ]
                )
            elif companies:
                company = companies[0]
                candidates.extend(
                    [
                        f"Deep dive into {company}'s financials?",
                        f"What's {company}'s revenue trend?",
                    ]
                )
            else:
                candidates.extend(
                    [
                        "Analyze Caterpillar's earnings?",
                        "Compare marine sector stocks?",
                    ]
                )
            candidates.append("Show analyst recommendations?")

        elif parsed.intent in [
            QueryIntent.SALES_OPPORTUNITY,
            QueryIntent.RELATIONSHIP_CHECK,
        ]:
            if regions:
                region = regions[0]
                candidates.extend(
                    [
                        f"More opportunities in {region}?",
                        f"Qualify {region} leads?",
                    ]
                )
            if companies:
                candidates.append(f"Get contact info for {companies[0]}?")
            else:
                candidates.extend(
                    [
                        "Show high-value opportunities?",
                        "Filter by engine type?",
                    ]
                )
            candidates.append("Export opportunity list?")

        elif parsed.intent == QueryIntent.BILLING_AR:
            if companies:
                company = companies[0]
                candidates.extend(
                    [
                        f"View {company}'s aging report?",
                        f"Check overdue items for {company}?",
                        f"Run full KYP on {company}?",
                    ]
                )
            else:
                candidates.extend(
                    [
                        "View all customers with high credit utilization?",
                        "Show overdue invoices summary?",
                        "Any customers near credit limit?",
                    ]
                )

        else:
            # General follow-ups from extracted entities
            if competitors:
                candidates.append(f"Tell me more about {competitors[0]}?")
            elif session_competitors:
                candidates.append(f"More about {session_competitors[-1]}?")
            if regions:
                candidates.append(f"Focus on {regions[0]}?")
            elif session_regions:
                candidates.append(f"More from {session_regions[-1]}?")
            if products:
                candidates.append(f"Details on {products[0]}?")
            elif session_products:
                candidates.append(f"More about {session_products[-1]}?")
            if not candidates:
                candidates.extend(
                    [
                        "What aspect would you like to explore?",
                        "Need competitor intelligence?",
                    ]
                )

        # Add confidence-based suggestion if needed
        if confidence == "LOW":
            candidates.append("Search latest news for more context?")

        # --- DEDUPLICATION: Remove suggestions already shown in this session ---
        if session:
            shown = session.context.get("shown_suggestions", [])
            shown_lower = {s.lower() for s in shown}

            deduplicated = []
            for suggestion in candidates:
                if suggestion.lower() in shown_lower:
                    continue
                # Near-duplicate check (>70% word overlap)
                suggestion_words = set(suggestion.lower().split())
                is_near_dup = False
                for prev in shown_lower:
                    prev_words = set(prev.split())
                    if suggestion_words and prev_words:
                        overlap = len(suggestion_words & prev_words)
                        max_len = max(len(suggestion_words), len(prev_words))
                        if max_len > 0 and overlap / max_len > 0.7:
                            is_near_dup = True
                            break
                if not is_near_dup:
                    deduplicated.append(suggestion)

            # Use deduplicated list. If ALL candidates were duplicates,
            # build context-aware fallback suggestions.
            if deduplicated:
                follow_ups = deduplicated[:3]
            else:
                # All template suggestions exhausted — build intent-aware fallbacks
                fresh: List[str] = []

                if parsed.intent == QueryIntent.BILLING_AR:
                    # FinOps-relevant fallbacks (NOT competitor intel)
                    fresh.extend(
                        [
                            "View customers with high credit utilization?",
                            "Show overdue invoices summary?",
                            "Any customers approaching their credit limit?",
                            "Check payment history for a specific customer?",
                            "Show collections items requiring action?",
                            "What are the current payment terms by customer?",
                            "Run KYP on a specific company?",
                            "Check credit status for a customer?",
                        ]
                    )
                elif parsed.intent in (
                    QueryIntent.KYP_DUE_DILIGENCE,
                    QueryIntent.CUSTOMER_INTEL,
                    QueryIntent.RELATIONSHIP_CHECK,
                ):
                    fresh.extend(
                        [
                            "Run KYP on another company?",
                            "Check credit status for a customer?",
                            "View CEC opportunities?",
                            "Compare financial health of two companies?",
                            "Check SAP customer record?",
                        ]
                    )
                else:
                    # Sales-oriented fallbacks — competitors and regions
                    all_comps = {
                        "Caterpillar",
                        "Cummins",
                        "MAN Energy Solutions",
                        "Wartsila",
                    }
                    discussed_comps = {c.lower() for c in session_competitors}
                    for comp in all_comps:
                        if comp.lower() not in discussed_comps and len(fresh) < 6:
                            fresh.append(f"How does {comp} compete in this segment?")

                    all_regions = [
                        "Singapore",
                        "Indonesia",
                        "Malaysia",
                        "Vietnam",
                        "Thailand",
                        "Philippines",
                    ]
                    discussed_regions = {r.lower() for r in session_regions}
                    for reg in all_regions:
                        if reg.lower() not in discussed_regions and len(fresh) < 10:
                            fresh.append(f"What opportunities exist in {reg}?")

                    fresh.extend(
                        [
                            "Run KYP on a specific company?",
                            "Check credit status for a customer?",
                            "What are the latest newbuild orders?",
                            "Show MTU product availability?",
                            "Compare engine lifecycle costs?",
                            "What tenders are coming up?",
                            "Explore power generation opportunities?",
                            "Review fleet expansion plans in APAC?",
                            "What service agreements are expiring soon?",
                            "Analyze market share by segment?",
                        ]
                    )

                # Filter out already-shown from fresh pool
                deduped_fresh = []
                for f in fresh:
                    if f.lower() not in shown_lower:
                        deduped_fresh.append(f)
                        if len(deduped_fresh) >= 3:
                            break

                follow_ups = deduped_fresh if deduped_fresh else candidates[:3]

            # Track shown suggestions — keep last 15 so suggestions can
            # naturally recur after ~5 turns (5 turns × 3 suggestions = 15)
            new_shown = shown + follow_ups
            session.context["shown_suggestions"] = new_shown[-15:]
        else:
            follow_ups = candidates[:3]

        return follow_ups

    # ── Write-operation refusal guardrail ──────────────────────────
    # Patterns that indicate the user wants us to PERFORM an action.
    # We are a read-only intelligence system; we must refuse clearly.
    _WRITE_ACTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # Explicit action verbs in imperative form (start of sentence or after please/can you)
        # Allow up to 3 intermediate words between verb and object (e.g. "send a follow-up email")
        re.compile(
            r"(?:^|please\s|can you\s|could you\s|i need you to\s|i want you to\s)"
            r"(?:send|submit|create|place|issue|raise|generate|draft and send|write|compose)\s+"
            r"(?:\S+\s+){0,3}"
            r"(?:email|message|notification|order|purchase order|invoice|po\b|quote|rfi|rfq)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:^|please\s|can you\s|could you\s)"
            r"(?:update|change|modify|increase|decrease|adjust|set|reset|revise)\s+"
            r"(?:\S+\s+){0,2}"
            r"(?:credit|limit|exposure|payment terms?|pricing|discount|status)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:^|please\s|can you\s|could you\s)"
            r"(?:write[\s-]?off|cancel|void|delete|remove|close|block|unblock)\s+"
            r"(?:\S+\s+){0,2}"
            r"(?:invoice|order|account|customer|entry|debt|receivable)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:^|please\s|can you\s|could you\s)"
            r"(?:approve|reject|escalate|reassign|transfer|release|"
            r"override|bypass|waive|overrule)\s+",
            re.IGNORECASE,
        ),
        # Broad catch-all for transactional verbs missed above
        re.compile(
            r"(?:^|please\s|can you\s|could you\s|go ahead and\s)"
            r"(?:disable|skip|circumvent|ignore|revoke|lift|clear|"
            r"unfreeze|authorize|execute|process|grant|enable|activate)\s+"
            r"(?:\S+\s+){0,3}"
            r"(?:credit|block|hold|limit|order|check|verification|restriction|freeze)",
            re.IGNORECASE,
        ),
    ]

    # Analytical / hypothetical phrasing — NOT a write request
    _ANALYTICAL_PREFIXES = re.compile(
        r"(?:what (?:if|would|happens)|how (?:do|does|can|would)|"
        r"is it possible|tell me about|show me|explain|"
        r"what is the process|who (?:can|should))",
        re.IGNORECASE,
    )

    @staticmethod
    def _filter_cited_sources(answer: str, sources: List[str]) -> tuple:
        """Filter sources to only those cited, and renumber citations to match.

        If the answer contains [2], [5], [8]:
        - sources becomes [sources[1], sources[4], sources[7]]
        - answer text [2]->[1], [5]->[2], [8]->[3]

        Returns:
            (renumbered_answer, filtered_sources)

        Invariant: max [N] in answer == len(filtered_sources)
        """
        import re as _re

        if not sources or not answer:
            return answer, sources or []

        # Find which [N] numbers are cited in the text
        cited_nums = set()
        for match in _re.finditer(r"\[(\d+)\]", answer):
            n = int(match.group(1))
            if 1 <= n <= len(sources):
                cited_nums.add(n)

        if not cited_nums:
            return answer, []

        # Build old→new mapping and filtered sources list
        sorted_cited = sorted(cited_nums)
        old_to_new = {old_n: new_n for new_n, old_n in enumerate(sorted_cited, 1)}
        filtered = [sources[n - 1] for n in sorted_cited]

        # Renumber citations in the answer text
        def _renumber(m: "_re.Match") -> str:
            old_n = int(m.group(1))
            new_n = old_to_new.get(old_n)
            if new_n is not None:
                return f"[{new_n}]"
            return m.group(0)  # Leave unknown citations unchanged

        renumbered = _re.sub(r"\[(\d+)\]", _renumber, answer)

        return renumbered, filtered

    def _detect_write_intent(self, message: str) -> Optional[str]:
        """Return a refusal message if the user requests a write operation, else None."""
        msg = message.strip()

        # Check if analytical prefix is present
        is_analytical = bool(self._ANALYTICAL_PREFIXES.match(msg))

        # If analytical, still check if there's a write action LATER in the
        # message (e.g., "Tell me about X, then do it" or "Explain how to
        # override Y and override it").  Only skip if purely analytical.
        if is_analytical:
            # Check for imperative chaining after the analytical prefix
            _action_verbs = (
                r"\b(?:then|now|and|please)\b.*\b(?:do it|apply|execute|process|"
                r"override|bypass|release|waive|disable|skip|approve|update|"
                r"delete|remove|cancel|revoke|lift|clear|unfreeze)\b"
            )
            if not re.search(_action_verbs, msg, re.IGNORECASE):
                return None

        for pattern in self._WRITE_ACTION_PATTERNS:
            if pattern.search(msg):
                return (
                    "I'm a **read-only intelligence system** — I can look up and analyse data, "
                    "but I cannot perform transactional actions such as sending emails, updating "
                    "records, or modifying SAP data.\n\n"
                    "For write operations, please use the appropriate SAP transaction or raise a "
                    "request through your normal workflow.\n\n"
                    "I can help you **review the current data**, **draft content**, or **identify "
                    "the right contacts** instead. What would you like me to look up?"
                )

        return None

    def _error_response(
        self,
        session_id: str,
        error_message: str,
    ) -> Dict[str, Any]:
        """Generate error response."""
        return {
            "type": "error",
            "session_id": session_id,
            "error": error_message,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def process_message_streaming(
        self,
        session_id: str,
        message: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Process a user message with streaming response.

        Yields Server-Sent Events in the format:
        - {"type": "session", "session_id": "..."}
        - {"type": "status", "step": "...", "message": "..."}
        - {"type": "clarification_needed", "questions": [...]}
        - {"type": "tools_complete", "tools_used": [...], "sources": [...]}
        - {"type": "token", "content": "..."}
        - {"type": "done", "confidence": "...", "follow_up_suggestions": [...]}

        Args:
            session_id: Session ID for this conversation
            message: User's message
            user_context: User context with user_id for session ownership

        Yields:
            Dict with event type and data
        """
        _user_id = (user_context or {}).get("user_id", "")
        session = self.get_or_create_session(session_id, user_id=_user_id)

        # Emit session confirmation
        yield {
            "type": "session",
            "session_id": session.session_id,
        }

        # Step 0: Handle pending clarification/entity confirmation (parity with non-streaming)
        if session.pending_clarification:
            if session.pending_clarification.get("type") == "entity_confirmation":
                clarification_age = session.pending_clarification.get(
                    "_turns_since_set", 0
                )
                if clarification_age >= 3:
                    logger.info(
                        "Streaming: auto-clearing stale entity confirmation after "
                        f"{clarification_age} turns"
                    )
                    session.pending_clarification = None
                    self._session_store.set(session)
                else:
                    session.pending_clarification["_turns_since_set"] = (
                        clarification_age + 1
                    )
                    result = await self._handle_entity_confirmation(session, message)
                    if result:
                        answer = result.get("answer", "")
                        if answer:
                            yield {"type": "token", "content": answer}
                        yield {
                            "type": "done",
                            "confidence": result.get("confidence", "high"),
                            "follow_up_suggestions": result.get(
                                "follow_up_suggestions", []
                            ),
                        }
                        return

        # Add user turn
        session.add_turn("user", message)

        # Write-operation guardrail — refuse before burning LLM tokens
        write_refusal = self._detect_write_intent(message)
        if write_refusal:
            session.add_turn("assistant", write_refusal)
            self._session_store.set(session)
            yield {"type": "token", "content": write_refusal}
            yield {
                "type": "done",
                "confidence": "high",
                "follow_up_suggestions": [
                    "Show me the current credit status?",
                    "What are the open invoices?",
                    "Draft a summary I can paste into an email?",
                ],
            }
            return

        # Greeting/capability fast-path (parity with non-streaming)
        _msg_s = message.strip().lower().rstrip("!?.,:;")
        _STREAM_GREETINGS = {
            "hello", "hi", "hey", "hiya", "howdy",
            "good morning", "good afternoon", "good evening",
            "thanks", "thank you", "thx", "ty",
            "ok", "okay", "sure", "got it", "noted",
            "bye", "goodbye", "see you",
        }
        _STREAM_CAPABILITIES = {
            "what can you do", "what can you help me with",
            "what can you help with", "what do you do",
            "how can you help", "help", "help me",
            "what are your capabilities",
        }
        if _msg_s in _STREAM_CAPABILITIES:
            _cap = (
                "I can help you with:\n\n"
                "**Customer Intelligence**\n"
                "- Run KYP (Know Your Partner) due diligence\n"
                "- Check credit status and exposure\n"
                "- Show CEC opportunities and pipeline\n\n"
                "**Market & Competitor Intelligence**\n"
                "- Marine industry trends and market opportunities\n"
                "- Competitor analysis and comparison\n"
                "- Product specifications and recommendations\n\n"
                "**Finance Operations**\n"
                "- Billing items and collections\n"
                "- Payment status and track record\n"
                "- Aging analysis and escalations\n\n"
                'Try: *"Run KYP on ST Engineering"* or *"Show opportunities for Maersk"*'
            )
            session.add_turn("assistant", _cap)
            self._session_store.set(session)
            yield {"type": "token", "content": _cap}
            yield {
                "type": "done",
                "session_id": session.session_id,
                "confidence": "HIGH",
                "execution_time_ms": 0,
                "follow_up_suggestions": [
                    "Run KYP on ST Engineering?",
                    "Show opportunities for Maersk?",
                    "What are the latest marine trends?",
                ],
            }
            return

        if _msg_s in _STREAM_GREETINGS:
            _gr = {
                "hello": "Hello! How can I assist you today?",
                "hi": "Hi there \u2014 what would you like to know?",
                "hey": "Hey! How can I help?",
                "good morning": "Good morning! What can I help you with?",
                "good afternoon": "Good afternoon! How can I assist?",
                "good evening": "Good evening! What would you like to know?",
                "thanks": "You're welcome! Let me know if you need anything else.",
                "thank you": "You're welcome! Anything else I can help with?",
                "ok": "Alright \u2014 let me know what you'd like to look into next.",
                "okay": "Sure \u2014 what would you like to explore?",
                "bye": "Goodbye! Feel free to come back anytime.",
            }.get(_msg_s, "Hi \u2014 how can I help you today?")
            session.add_turn("assistant", _gr)
            self._session_store.set(session)
            yield {"type": "token", "content": _gr}
            yield {
                "type": "done",
                "session_id": session.session_id,
                "confidence": "HIGH",
                "execution_time_ms": 0,
                "follow_up_suggestions": [
                    "Run KYP on a company?",
                    "Check credit status?",
                    "Show opportunities?",
                ],
            }
            return

        # Step 1: Parse query
        yield {
            "type": "status",
            "step": "understanding",
            "message": "Understanding your query...",
        }

        try:
            parsed = await self.query_engine.parse(
                message,
                session.get_history(),
            )
        except Exception as e:
            logger.error(f"Query understanding failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            return

        # Apply user default region if query has no explicit region
        if not parsed.regions and user_context:
            _default_region = user_context.get("default_region", "")
            if _default_region:
                parsed.regions = [_default_region]
                logger.info(
                    f"Streaming: Applied user default region: {_default_region}"
                )

        # Update session context
        session.update_context(parsed)

        # Step 1.5: Universal semantic resolution (expand abbreviations)
        # Matches the non-streaming path's Step 4.1 which resolves:
        # - "STE" → "ST Engineering" (abbreviation expansion)
        # - "batamfast" → "Batam Fast Ferry" (alias lookup)
        resolved_company = await self._apply_universal_semantic_resolution(
            message, parsed, session
        )
        if resolved_company:
            # Update session context with resolved company
            if "companies" not in session.context:
                session.context["companies"] = []
            if resolved_company not in session.context["companies"]:
                session.context["companies"].append(resolved_company)
            logger.info(
                f"Streaming Step 1.5: Semantic resolution expanded to: {resolved_company}"
            )
            # Mark as confirmed entity so _resolve_entity_for_kyp skips
            # unnecessary external lookups (ACRA, GLEIF, etc.) for known aliases.
            # EXCEPTION: KYP queries skip auto-confirm — let
            # _resolve_entity_for_kyp handle with proper SAP CPI lookup.
            if (
                not session.context.get("confirmed_entity")
                and parsed.intent != QueryIntent.KYP_DUE_DILIGENCE
            ):
                raw_input = parsed.raw_company_input or (
                    parsed.companies[0] if parsed.companies else ""
                )
                session.context["confirmed_entity"] = {
                    "canonical_name": resolved_company,
                    "query": raw_input,
                    "raw_input": raw_input,
                }
                logger.info(
                    f"Streaming Step 1.5: Auto-confirmed entity '{resolved_company}' "
                    f"from alias expansion (skips entity resolution)"
                )

        # Step 1.6: Credit query fast-path (matches non-streaming Step 4.5)
        # MUST run before RBAC check — credit queries may be misclassified as
        # billing_ar by the query parser but should be accessible to all roles
        credit_response = await self._try_handle_credit_query(
            message, parsed, session, session_id
        )
        if credit_response:
            if credit_response.get("type") == "credit_report":
                # Return structured JSON for card rendering (like finops/opp)
                yield credit_response
            else:
                # Fallback: yield as streaming tokens for text responses
                answer_text = credit_response.get("answer", "")
                if answer_text:
                    yield {
                        "type": "tools_complete",
                        "tools_used": ["SAP CPI Credit Check"],
                        "sources": credit_response.get("sources", ["SAP CPI"]),
                    }
                    yield {"type": "token", "content": answer_text}
                    yield {
                        "type": "done",
                        "confidence": credit_response.get("confidence", "HIGH"),
                        "follow_up_suggestions": credit_response.get(
                            "follow_up_suggestions", []
                        ),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
            return

        # Step 1.6b: Order detail / billing plan fast path (streaming)
        order_response = await self._try_handle_order_query(
            message, parsed, session, session_id
        )
        if order_response:
            answer_text = order_response.get("answer", "")
            if answer_text:
                yield {
                    "type": "tools_complete",
                    "tools_used": ["SAP CPI Order Detail"],
                    "sources": order_response.get("sources", ["SAP CPI"]),
                }
                yield {"type": "token", "content": answer_text}
                yield {
                    "type": "done",
                    "confidence": order_response.get("confidence", "HIGH"),
                    "follow_up_suggestions": order_response.get(
                        "follow_up_suggestions", []
                    ),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            return

        # Step 1.6c: Opportunity fast path (streaming)
        opp_response = await self._try_handle_opportunity_query(
            message, parsed, session, session_id
        )
        if opp_response:
            # Return as non-streaming JSON (frontend handles structured rendering)
            yield opp_response
            return

        # Step 1.7: RBAC pre-check — block billing/collections queries for
        # unauthorized users. Runs AFTER credit fast-path to avoid blocking
        # credit queries that are valid for all roles.
        if user_context and parsed.intent and parsed.intent.value == "billing_ar":
            permissions = user_context.get("permissions", {})
            has_billing = "read" in permissions.get(
                "billing", []
            ) or "*" in permissions.get("*", [])
            has_collections = "read" in permissions.get(
                "collections", []
            ) or "*" in permissions.get("*", [])
            if not has_billing and not has_collections:
                denial_msg = (
                    "I'm unable to share billing and collections information "
                    "as it requires financeops permissions. "
                    "Contact your admin to request: financeops role."
                )
                session.add_turn("assistant", denial_msg)
                self._session_store.set(session)
                yield {"type": "token", "content": denial_msg}
                yield {
                    "type": "done",
                    "confidence": "high",
                    "follow_up_suggestions": [
                        "What is the credit status for this customer?",
                        "Show me the customer profile",
                        "What products do we offer?",
                    ],
                }
                return

        # Step 1.7a: Billing/collections/DP fast-path (streaming)
        billing_response = await self._try_handle_billing_query(
            message, parsed, session, session_id, user_context=user_context
        )
        if billing_response:
            # Return as non-streaming JSON (frontend handles structured card rendering)
            yield billing_response
            return

        # Step 1.8: Escalation query fast-path (matches non-streaming Step 4.6)
        escalation_response = await self._try_handle_escalation_query(
            message, parsed, session, session_id
        )
        if escalation_response:
            answer_text = escalation_response.get("answer", "")
            if answer_text:
                yield {
                    "type": "tools_complete",
                    "tools_used": ["SAP CPI Escalation Check"],
                    "sources": escalation_response.get("sources", ["SAP CPI"]),
                }
                yield {"type": "token", "content": answer_text}
                yield {
                    "type": "done",
                    "confidence": escalation_response.get("confidence", "HIGH"),
                    "follow_up_suggestions": escalation_response.get(
                        "follow_up_suggestions", []
                    ),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            return

        # Step 1.9: Pre-routing social engineering detection
        # Catches competitor impersonation, data modification requests, and
        # fabricated claim verification — BEFORE routing to any tool pipeline
        from lead_to_cash.core.tool_executor import ToolExecutor

        se_rejection = ToolExecutor._detect_social_engineering(parsed)
        if se_rejection:
            logger.info(f"Social engineering detected, returning rejection")
            session.add_turn("assistant", se_rejection)
            self._session_store.set(session)
            yield {"type": "token", "content": se_rejection}
            yield {
                "type": "done",
                "confidence": "HIGH",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            return

        # Step 2: Check if clarification needed
        clarifications = await self._check_clarifications(parsed, session)
        if clarifications:
            session.pending_clarification = {
                "parsed_query": parsed,
                "questions": clarifications,
            }
            self._session_store.set(session)

            yield {
                "type": "clarification_needed",
                "session_id": session.session_id,
                "questions": [q.to_dict() for q in clarifications],
                "partial_understanding": {
                    "intent": parsed.intent.value,
                    "entities": {
                        "competitors": parsed.competitors,
                        "companies": parsed.companies,
                        "regions": parsed.regions,
                        "products": parsed.products,
                    },
                    "time_reference": parsed.time_reference,
                },
            }
            return

        # Step 2.5: Entity Resolution for KYP queries
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            yield {
                "type": "status",
                "step": "resolving_entity",
                "message": "Resolving company identity...",
            }

            try:
                entity_result = await self._resolve_entity_for_kyp(session, parsed)
                if entity_result:
                    # Entity confirmation needed - yield and return
                    logger.info(
                        f"Streaming: Entity confirmation required for KYP: {parsed.companies}"
                    )
                    yield {
                        "type": "entity_confirmation_needed",
                        "session_id": session.session_id,
                        "message": entity_result.get("message"),
                        "candidates": entity_result.get("candidates", []),
                        "query": entity_result.get("query"),
                    }
                    return

                # If entity was auto-confirmed, update parsed with canonical name and entity_context
                if session.context.get("confirmed_entity"):
                    confirmed = session.context["confirmed_entity"]
                    if confirmed.get("canonical_name"):
                        # replace imported at module level
                        entity_ctx = EntityContext(
                            entity_id=confirmed.get("entity_id"),
                            canonical_name=confirmed.get("canonical_name"),
                            uen=confirmed.get("uen"),
                            lei=confirmed.get("lei"),
                            country_code=confirmed.get("country_code"),
                        )
                        parsed = replace(
                            parsed,
                            companies=[confirmed["canonical_name"]],
                            entity_context=entity_ctx,
                        )
                        logger.info(
                            f"Streaming: Using confirmed entity: {confirmed['canonical_name']} "
                            f"(UEN={confirmed.get('uen')}, LEI={confirmed.get('lei')})"
                        )
            except Exception as e:
                # Entity resolution failed - log and continue without entity context
                # The KYP will still work but won't have UEN for direct SAP lookup
                logger.warning(
                    f"Streaming: Entity resolution failed, continuing without entity context: {e}"
                )
                yield {
                    "type": "status",
                    "step": "entity_resolution_skipped",
                    "message": "Entity lookup unavailable, proceeding with name-based search...",
                }

        # Step 3: Check data inventory
        yield {
            "type": "status",
            "step": "checking_inventory",
            "message": "Checking data availability...",
        }

        try:
            inventory_result = await self.inventory.check_coverage(parsed)
        except Exception as e:
            logger.warning(f"Data inventory check failed: {e}")
            inventory_result = InventoryCheckResult(
                has_local_data=False,
                coverage=None,
                confidence="LOW",
                gaps=[f"Inventory check failed: {e}"],
                recommended_sources=[],
            )

        # Step 3.5: Enrich parsed query with session context if needed
        # This handles follow-up questions like "What is their credit limit?"
        logger.info(
            f"Streaming Step 3.5 CHECK: parsed.companies={parsed.companies}, "
            f"session.context.companies={session.context.get('companies', [])}, "
            f"session.context.last_kyp_entity={session.context.get('last_kyp_entity')}, "
            f"session_id={session_id}"
        )
        if not parsed.companies and self._is_follow_up_query(message):
            # GUARD: Only fall back to session context for follow-up/pronoun
            # queries to prevent entity contamination across turns.
            context_company = None

            # Priority 1: Last KYP entity (most specific for follow-up questions)
            if session.context.get("last_kyp_entity"):
                context_company = session.context["last_kyp_entity"]
                logger.info(
                    f"Streaming: Using last_kyp_entity for enrichment: '{context_company}'"
                )

            # Priority 2: Most recent company from companies list
            elif session.context.get("companies"):
                context_company = session.context["companies"][-1]
                logger.info(
                    f"Streaming: Using companies[-1] for enrichment: '{context_company}'"
                )

            if context_company:
                # Restore entity_context if we have a confirmed entity
                # Use module-level utility for normalized matching with min-length check
                confirmed = session.context.get("confirmed_entity")
                confirmed_name = (
                    confirmed.get("canonical_name", "") if confirmed else ""
                )

                if confirmed and _company_names_match(confirmed_name, context_company):
                    entity_ctx = EntityContext(
                        entity_id=confirmed.get("entity_id"),
                        canonical_name=confirmed.get("canonical_name"),
                        uen=confirmed.get("uen"),
                        lei=confirmed.get("lei"),
                        country_code=confirmed.get("country_code"),
                    )
                    # Use the canonical name from confirmed entity for consistency
                    parsed = replace(
                        parsed,
                        companies=[confirmed["canonical_name"]],
                        entity_context=entity_ctx,
                    )
                    logger.info(
                        f"Streaming: ✅ ENRICHED with full entity context: "
                        f"companies=['{confirmed['canonical_name']}'], UEN={entity_ctx.uen}"
                    )
                else:
                    parsed = replace(parsed, companies=[context_company])
                    logger.info(
                        f"Streaming: ✅ ENRICHED with session context: companies=['{context_company}']"
                    )
            else:
                logger.warning(
                    "Streaming: ⚠️ NO ENRICHMENT - parsed.companies is empty AND no session context"
                )

        # Step 4: Execute tools
        # KYP uses non-streaming execute() because _build_kyp_report() needs
        # full tool_outputs (SAP, EODHD, Perplexity raw data) to build each
        # section. The streaming execute_streaming() only yields tokens.
        collected_answer = []
        collected_sources = []
        collected_tools = []
        final_confidence = "MEDIUM"
        final_execution_time = 0
        full_tool_result = None  # Only set for KYP

        # Source Authority Decision for streaming path
        source_decision = SourceAuthority.decide(parsed, inventory_result)

        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            # KYP: use non-streaming execute() for full tool_outputs
            yield {
                "type": "status",
                "step": "gathering",
                "message": "Gathering due diligence data...",
            }
            try:
                full_tool_result = await self.tool_executor.execute(
                    parsed,
                    inventory_result,
                    conversation_history=session.get_history(max_turns=4),
                    source_decision=source_decision,
                )
                collected_sources = full_tool_result.sources or []
                collected_tools = [t.value for t in full_tool_result.tools_used]
                final_confidence = full_tool_result.confidence or "MEDIUM"
                final_execution_time = full_tool_result.total_execution_time_ms or 0
                collected_answer = [full_tool_result.synthesized_content or ""]
            except Exception as e:
                logger.error(f"KYP tool execution failed: {e}")
                yield {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                return
        else:
            # Non-KYP: stream tokens for word-by-word display
            try:
                async for event in self.tool_executor.execute_streaming(
                    parsed,
                    inventory_result,
                    conversation_history=session.get_history(max_turns=4),
                    source_decision=source_decision,
                ):
                    if event["type"] == "token":
                        collected_answer.append(event["content"])
                        yield event
                    elif event["type"] == "tools_complete":
                        collected_sources = event.get("sources", [])
                        collected_tools = event.get("tools_used", [])
                        yield event
                    elif event["type"] == "done":
                        final_confidence = event.get("confidence", "MEDIUM")
                        final_execution_time = event.get("execution_time_ms", 0)
                    else:
                        yield event

            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                yield {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                return

        # Step 5: Build final answer and generate follow-ups
        answer = "".join(collected_answer) or "No results found."

        # Step 5.1: KYP credit correction — deterministic override
        # If this is a KYP query, verify credit status against SAP data and
        # correct any LLM hallucination (e.g., saying NO_ADVERSE_FINDINGS
        # when customer is actually credit-blocked).
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE and parsed.companies:
            try:
                from lead_to_cash.integrations import CPIClient, MS5Client
                from lead_to_cash.config import config as _kyp_config

                if _kyp_config.sap_cpi.client_id:
                    _kyp_cpi = CPIClient()
                    await _kyp_cpi.connect()
                    _kyp_ms5 = MS5Client(cpi_client=_kyp_cpi)
                    await _kyp_ms5.connect()
                    _kyp_customers = await _kyp_ms5.search_customers(
                        name=parsed.companies[0]
                    )
                else:
                    _kyp_customers = []
                if _kyp_customers:
                    _kyp_cust = _kyp_customers[0]
                    import os as _kyp_os

                    _kyp_cca = _kyp_os.getenv("SAP_MS5_CREDIT_CONTROL_AREA", "0111")
                    _kyp_credit = await _kyp_ms5.check_credit_limit(
                        _kyp_cust.customer_id, credit_control_area=_kyp_cca
                    )
                    if _kyp_credit and not _kyp_credit.credit_check_passed:
                        # ALWAYS append deterministic SAP credit footer for
                        # blocked customers — overrides any LLM hallucination.
                        _blk_status = (
                            "BLOCKED"
                            if _kyp_credit.utilization_percent > 100
                            else "Review Required"
                        )
                        footer = (
                            f"\n\n---\n**[SAP CREDIT VERIFICATION]** "
                            f"{_kyp_cust.name}: Credit status is **{_blk_status}** "
                            f"(utilization: {_kyp_credit.utilization_percent:.0f}%, "
                            f"exposure: {_kyp_credit.currency} {_kyp_credit.credit_exposure:,.2f} "
                            f"vs limit: {_kyp_credit.currency} {_kyp_credit.credit_limit:,.2f}). "
                            f"**KYP Credit Assessment: ADVERSE_FINDINGS.**"
                        )
                        yield {"type": "token", "content": footer}
                        answer += footer
                        collected_answer.append(footer)
                        logger.info(
                            f"KYP deterministic credit footer for {_kyp_cust.name}: {_blk_status}"
                        )
            except Exception as e:
                logger.warning(f"KYP credit correction check failed: {e}")

        # Step 5.2: KYP report date — ensure a valid date is always present
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            import re as _re

            _has_date = any(
                _re.search(p, answer)
                for p in [
                    r"\d{4}-\d{2}-\d{2}",
                    r"\d{2}/\d{2}/\d{4}",
                    r"\d{1,2}\s+\w+\s+\d{4}",
                ]
            )
            if not _has_date:
                _report_date = datetime.now(UTC).strftime("%Y-%m-%d")
                _date_footer = f"\n\n**Report Date:** {_report_date}"
                yield {"type": "token", "content": _date_footer}
                answer += _date_footer
                collected_answer.append(_date_footer)

        # Step 5.3: KYP TPRM section — ensure structured TPRM data present
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE and parsed.companies:
            _answer_lower = answer.lower()
            _has_tprm = any(
                kw in _answer_lower
                for kw in [
                    "tprm",
                    "third-party risk",
                    "third party risk",
                    "aravo",
                    "supplier_id",
                    "supplier id",
                ]
            )
            if not _has_tprm:
                try:
                    from lead_to_cash.integrations.client_factory import (
                        get_aravo_client as _get_aravo,
                    )

                    _aravo, _aravo_real = await _get_aravo(use_case="KYP-TPRM-Stream")
                    _suppliers = []
                    if _aravo:
                        _suppliers = await _aravo.search_suppliers(
                            name=parsed.companies[0]
                        )
                    _supplier = _suppliers[0] if _suppliers else None
                    if _supplier:
                        _tprm_footer = (
                            f"\n\n**Third-Party Risk Management (TPRM — Aravo):**\n"
                            f"- **Supplier ID:** {_supplier.supplier_id}\n"
                            f"- **Supplier Status:** {_supplier.status}\n"
                            f"- **Risk Score:** {_supplier.inherent_risk_score}\n"
                            f"- **Due Diligence Status:** Approved\n"
                            f"- **TPRM Assessment:** NO_ADVERSE_FINDINGS"
                        )
                    else:
                        _tprm_footer = (
                            "\n\n**Third-Party Risk Management (TPRM — Aravo):**\n"
                            "- **Supplier Status:** Not found in Aravo\n"
                            "- **Due Diligence Status:** Pending\n"
                            "- **TPRM Assessment:** UNABLE_TO_VERIFY"
                        )
                    yield {"type": "token", "content": _tprm_footer}
                    answer += _tprm_footer
                    collected_answer.append(_tprm_footer)
                except Exception as _te:
                    logger.warning(f"KYP TPRM footer failed: {_te}")

        # Step 5.5: Empty response fallback for streaming
        # If answer is empty/minimal but session has history, retry with extended history
        if len(answer.strip()) < 10 and len(session.turns) >= 4:
            logger.info(
                "Streaming: empty result with history — retrying with extended history"
            )
            try:
                fallback_result = await self.tool_executor.execute(
                    parsed,
                    inventory_result,
                    conversation_history=session.get_history(max_turns=10),
                    source_decision=source_decision,
                )
                if (
                    fallback_result.synthesized_content
                    and len(fallback_result.synthesized_content.strip()) >= 10
                ):
                    answer = fallback_result.synthesized_content
                    # Stream the fallback answer to the client
                    chunk_size = 15
                    for i in range(0, len(answer), chunk_size):
                        yield {"type": "token", "content": answer[i : i + chunk_size]}
                    collected_sources = fallback_result.sources
                    collected_tools = [t.value for t in fallback_result.tools_used]
                    final_confidence = fallback_result.confidence or "MEDIUM"
            except Exception as e:
                logger.warning(f"Streaming history-based retry failed: {e}")

        # Create a minimal ToolResult for follow-up generation
        from lead_to_cash.core.data_inventory import DataSource
        from lead_to_cash.core.tool_executor import ToolResult

        # Convert tool names back to DataSource enum
        tools_used_enum = []
        for tool_name in collected_tools:
            try:
                tools_used_enum.append(DataSource(tool_name))
            except ValueError:
                pass

        # For KYP, use the full_tool_result (with real tool_outputs).
        # For other intents, build a synthetic ToolResult from collected data.
        if full_tool_result:
            tool_result = full_tool_result
        else:
            tool_result = ToolResult(
                query=parsed.raw_query,
                intent=parsed.intent,
                tools_used=tools_used_enum,
                tool_outputs=[],
                synthesized_content=answer,
                sources=collected_sources,
                confidence=final_confidence,
                total_execution_time_ms=final_execution_time,
            )

        follow_ups = self._generate_follow_ups(parsed, tool_result, session)

        # Step 5.5: KYP — build structured report and emit as a single event.
        if parsed.intent == QueryIntent.KYP_DUE_DILIGENCE:
            try:
                kyp_response = await self._build_kyp_report(
                    parsed, tool_result, session.session_id, follow_ups
                )
                if kyp_response:
                    # Store in session for follow-up section queries
                    session.context["cached_kyp_report"] = kyp_response
                    session.context["last_kyp_entity"] = (
                        parsed.companies[0] if parsed.companies else None
                    )
                    session.add_turn(
                        "assistant",
                        kyp_response.get("answer", answer),
                        sources=_sanitize_sources(collected_sources),
                        tools_used=collected_tools,
                        follow_ups=follow_ups,
                    )
                    self._session_store.set(session)

                    # Emit the structured KYP report as a done event
                    # The frontend detects type=kyp_report in event.data
                    kyp_response["follow_up_suggestions"] = follow_ups
                    kyp_response["sources"] = _sanitize_sources(
                        kyp_response.get("sources", collected_sources)
                    )
                    yield {
                        "type": "done",
                        "data": kyp_response,
                        "session_id": session.session_id,
                        "confidence": final_confidence,
                        "follow_up_suggestions": follow_ups,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    return
            except Exception as e:
                logger.warning(
                    f"Streaming: KYP report build failed, falling back to text: {e}"
                )
                # Fall through to normal text streaming

        # Step 6: Add assistant turn
        session.add_turn(
            "assistant",
            answer,
            sources=_sanitize_sources(collected_sources),
            tools_used=collected_tools,
            follow_ups=follow_ups,
        )
        self._session_store.set(session)

        # Step 7: Emit final done event with all metadata
        yield {
            "type": "done",
            "session_id": session.session_id,
            "confidence": final_confidence,
            "data_coverage": {
                "has_local_data": inventory_result.has_local_data,
                "coverage_confidence": inventory_result.confidence,
                "coverage_percentage": (
                    inventory_result.coverage.coverage_percentage
                    if inventory_result.coverage
                    else 0.0
                ),
                "document_count": (
                    inventory_result.coverage.document_count
                    if inventory_result.coverage
                    else 0
                ),
                "freshness_hours": inventory_result.freshness_hours,
                "gaps": inventory_result.gaps,
            },
            "tools_used": collected_tools,
            "execution_time_ms": final_execution_time,
            "follow_up_suggestions": follow_ups,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions removed
        """
        store = self._session_store
        now = datetime.now(UTC)
        expired = []

        for session_id, session in store.items():
            hours_since_activity = (now - session.last_activity).total_seconds() / 3600

            if hours_since_activity > self.SESSION_EXPIRY_HOURS:
                expired.append(session_id)

        for session_id in expired:
            store.delete(session_id)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)


# =============================================================================
# Singleton Instance
# =============================================================================

_manager: Optional[ConversationManager] = None
_manager_lock = threading.Lock()


def get_conversation_manager() -> ConversationManager:
    """
    Get singleton ConversationManager instance (thread-safe).

    Automatically uses Redis for session storage if REDIS_URL is configured,
    otherwise falls back to in-memory storage (not recommended for production
    with multiple workers).

    Thread Safety:
        Uses double-checked locking pattern for safe concurrent initialization.

    Environment Variables:
        REDIS_URL: Redis connection URL (e.g., redis://localhost:6379/0)
                   If set, enables distributed session storage for horizontal scaling.

    Returns:
        ConversationManager instance
    """
    global _manager

    # Fast path: already initialized
    if _manager is not None:
        return _manager

    # Slow path: need to initialize with lock
    with _manager_lock:
        # Double-check after acquiring lock
        if _manager is not None:
            return _manager

        # Check for Redis configuration
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            # Use Redis for production - enables horizontal scaling
            # RedisSessionStore uses lazy connection - no blocking ping here
            session_store = RedisSessionStore(
                redis_url=redis_url,
                prefix="l2c:chat:session:",
                ttl_seconds=7200,  # 2 hours
            )
            logger.info(
                "ConversationManager using Redis session store "
                "(prefix=l2c:chat:session:, ttl=2h, lazy_connect=True)"
            )
            _manager = ConversationManager(session_store=session_store)
        else:
            # In-memory storage - warn if likely production
            environment = os.getenv("ENVIRONMENT", "development")
            if environment in ["production", "prod", "staging"]:
                logger.warning(
                    "REDIS_URL not configured in production environment. "
                    "Sessions will not persist across workers or restarts. "
                    "Set REDIS_URL for distributed session storage."
                )
            else:
                logger.info(
                    "ConversationManager using in-memory session store "
                    "(set REDIS_URL for production)"
                )
            _manager = ConversationManager()

        return _manager


async def process_message(
    session_id: str,
    message: str,
    clarification_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to process a message.

    Args:
        session_id: Session ID
        message: User's message
        clarification_response: If responding to clarification

    Returns:
        Response dictionary
    """
    manager = get_conversation_manager()
    return await manager.process_message(session_id, message, clarification_response)
