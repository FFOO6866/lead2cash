"""
Agent Response Contracts - Typed Response Classes

This module defines the typed response contract that all agents must return.
These contracts ensure consistency between backend agents and frontend rendering.

MANDATORY: All agents MUST return AgentResponse instances to ensure
the frontend can properly handle responses.

Frontend expectations (chat.html:1867-1912):
- type="kyp_report" → formatKYPReport()
- type="answer" → addMessage(data.answer)
- type="clarification_needed" → show questions
- type="entity_confirmation_needed" → show confirmation
- type="error" → show error message

Usage:
    from lead_to_cash.agents.contracts import AgentResponse, ResponseType

    # Create answer response
    response = AgentResponse.create_answer(
        session_id="abc123",
        answer="The market shows growth...",
        sources=["Marine Intel DB", "Perplexity"],
        confidence="HIGH",
    )

    # Create error response
    response = AgentResponse.create_error(
        session_id="abc123",
        error="Failed to connect to SAP",
    )

    # Serialize for JSON response
    return response.to_dict()
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional


class ResponseType(str, Enum):
    """
    Response types matching frontend expectations.

    These MUST match the checks in chat.html:1867-1912.
    """

    ANSWER = "answer"
    KYP_REPORT = "kyp_report"
    CLARIFICATION_NEEDED = "clarification_needed"
    ENTITY_CONFIRMATION_NEEDED = "entity_confirmation_needed"
    ERROR = "error"


class ConfidenceLevel(str, Enum):
    """Confidence levels for response quality."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ClarificationQuestion:
    """A question to ask the user for clarification."""

    question: str
    options: list[str] = field(default_factory=list)
    field_name: str = ""  # Which field this clarifies (e.g., "region", "competitor")

    def to_dict(self) -> dict[str, Any]:
        result = {"question": self.question}
        if self.options:
            result["options"] = self.options
        if self.field_name:
            result["field_name"] = self.field_name
        return result


@dataclass
class EntityCandidate:
    """A candidate entity for confirmation."""

    entity_id: str
    name: str
    match_type: str  # "exact", "alias", "fuzzy", "semantic"
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class AgentResponse:
    """
    Typed response contract for all agents.

    This ensures consistency between backend agents and frontend rendering.
    All fields are optional except `type` and `session_id`.

    Use the class methods (answer, error, kyp_report, etc.) to create
    properly typed responses.
    """

    type: ResponseType
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Answer-specific fields
    answer: Optional[str] = None
    sources: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    # KYP Report-specific fields
    entity_name: Optional[str] = None
    report_date: Optional[str] = None
    overall_status: Optional[str] = None
    can_proceed: Optional[bool] = None
    sections: Optional[list[dict]] = None
    assessment: Optional[dict] = None
    recommendation: Optional[dict] = None

    # Clarification-specific fields
    questions: Optional[list[ClarificationQuestion]] = None
    partial_understanding: Optional[dict] = None

    # Entity confirmation-specific fields
    message: Optional[str] = None
    candidates: Optional[list[EntityCandidate]] = None
    original_query: Optional[str] = None

    # Error-specific fields
    error: Optional[str] = None

    # Metadata
    tools_used: list[str] = field(default_factory=list)
    execution_time_ms: int = 0
    follow_up_suggestions: list[str] = field(default_factory=list)
    data_coverage: Optional[dict] = None

    # Autonomy tracking (for Kaizen A2A)
    cycles_used: int = 0
    converged: bool = True
    tool_calls_made: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict for JSON serialization.

        Only includes fields relevant to the response type.
        """
        result = {
            "type": self.type.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }

        if self.type == ResponseType.ANSWER:
            result.update(
                {
                    "answer": self.answer or "",
                    "sources": self.sources,
                    "confidence": self.confidence.value,
                    "tools_used": self.tools_used,
                    "execution_time_ms": self.execution_time_ms,
                    "follow_up_suggestions": self.follow_up_suggestions,
                }
            )
            if self.data_coverage:
                result["data_coverage"] = self.data_coverage

        elif self.type == ResponseType.KYP_REPORT:
            result.update(
                {
                    "entity_name": self.entity_name or "Unknown Entity",
                    "report_date": self.report_date
                    or datetime.now(UTC).strftime("%Y-%m-%d"),
                    "overall_status": self.overall_status or "PENDING_REVIEW",
                    "can_proceed": (
                        self.can_proceed if self.can_proceed is not None else True
                    ),
                    "sections": self.sections or [],
                    "assessment": self.assessment or {"summary": []},
                    "recommendation": self.recommendation
                    or {"decision": "PENDING_REVIEW", "text": ""},
                    "sources": self.sources,
                    "follow_up_suggestions": self.follow_up_suggestions,
                }
            )

        elif self.type == ResponseType.CLARIFICATION_NEEDED:
            result.update(
                {
                    "questions": [q.to_dict() for q in (self.questions or [])],
                    "partial_understanding": self.partial_understanding or {},
                }
            )

        elif self.type == ResponseType.ENTITY_CONFIRMATION_NEEDED:
            result.update(
                {
                    "message": self.message or "Please confirm the entity.",
                    "candidates": [c.to_dict() for c in (self.candidates or [])],
                    "original_query": self.original_query or "",
                }
            )

        elif self.type == ResponseType.ERROR:
            result.update(
                {
                    "error": self.error or "Unknown error occurred",
                    "success": False,
                }
            )

        return result

    # =========================================================================
    # Factory Methods for Creating Typed Responses
    # =========================================================================

    @classmethod
    def create_answer(
        cls,
        session_id: str,
        answer: str,
        sources: list[str] = None,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        tools_used: list[str] = None,
        execution_time_ms: int = 0,
        follow_up_suggestions: list[str] = None,
        data_coverage: dict = None,
    ) -> "AgentResponse":
        """Create an answer response."""
        return cls(
            type=ResponseType.ANSWER,
            session_id=session_id,
            answer=answer,
            sources=sources or [],
            confidence=confidence,
            tools_used=tools_used or [],
            execution_time_ms=execution_time_ms,
            follow_up_suggestions=follow_up_suggestions or [],
            data_coverage=data_coverage,
        )

    @classmethod
    def kyp_report(
        cls,
        session_id: str,
        entity_name: str,
        sections: list[dict],
        overall_status: str = "PROCEED",
        can_proceed: bool = True,
        assessment: dict = None,
        recommendation: dict = None,
        sources: list[str] = None,
        follow_up_suggestions: list[str] = None,
    ) -> "AgentResponse":
        """Create a KYP report response."""
        return cls(
            type=ResponseType.KYP_REPORT,
            session_id=session_id,
            entity_name=entity_name,
            report_date=datetime.now(UTC).strftime("%Y-%m-%d"),
            overall_status=overall_status,
            can_proceed=can_proceed,
            sections=sections,
            assessment=assessment or {"summary": []},
            recommendation=recommendation or {"decision": overall_status, "text": ""},
            sources=sources or [],
            follow_up_suggestions=follow_up_suggestions or [],
        )

    @classmethod
    def clarification_needed(
        cls,
        session_id: str,
        questions: list[ClarificationQuestion],
        partial_understanding: dict = None,
    ) -> "AgentResponse":
        """Create a clarification request response."""
        return cls(
            type=ResponseType.CLARIFICATION_NEEDED,
            session_id=session_id,
            questions=questions,
            partial_understanding=partial_understanding or {},
        )

    @classmethod
    def entity_confirmation_needed(
        cls,
        session_id: str,
        message: str,
        candidates: list[EntityCandidate],
        original_query: str = "",
    ) -> "AgentResponse":
        """Create an entity confirmation request response."""
        return cls(
            type=ResponseType.ENTITY_CONFIRMATION_NEEDED,
            session_id=session_id,
            message=message,
            candidates=candidates,
            original_query=original_query,
        )

    @classmethod
    def create_error(
        cls,
        session_id: str,
        error: str,
    ) -> "AgentResponse":
        """Create an error response."""
        return cls(
            type=ResponseType.ERROR,
            session_id=session_id,
            error=error,
        )

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> list[str]:
        """
        Validate that response has all required fields for its type.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        if not self.session_id:
            errors.append("session_id is required")

        if self.type == ResponseType.ANSWER:
            if not self.answer:
                errors.append("answer is required for ANSWER type")

        elif self.type == ResponseType.KYP_REPORT:
            if not self.entity_name:
                errors.append("entity_name is required for KYP_REPORT type")
            if not self.sections:
                errors.append("sections is required for KYP_REPORT type")

        elif self.type == ResponseType.CLARIFICATION_NEEDED:
            if not self.questions:
                errors.append("questions is required for CLARIFICATION_NEEDED type")

        elif self.type == ResponseType.ENTITY_CONFIRMATION_NEEDED:
            if not self.candidates:
                errors.append(
                    "candidates is required for ENTITY_CONFIRMATION_NEEDED type"
                )

        elif self.type == ResponseType.ERROR:
            if not self.error:
                errors.append("error is required for ERROR type")

        return errors

    def is_valid(self) -> bool:
        """Check if response is valid."""
        return len(self.validate()) == 0


# =============================================================================
# Response Builder for Complex Scenarios
# =============================================================================


class ResponseBuilder:
    """
    Builder pattern for constructing complex responses.

    Usage:
        response = (
            ResponseBuilder(session_id="abc123")
            .with_answer("Analysis complete...")
            .with_sources(["Marine DB", "Perplexity"])
            .with_confidence(ConfidenceLevel.HIGH)
            .with_tools(["local_vectordb", "perplexity"])
            .with_follow_ups(["See competitor analysis?", "Check credit?"])
            .build()
        )
    """

    def __init__(self, session_id: str):
        self._session_id = session_id
        self._type = ResponseType.ANSWER
        self._answer = None
        self._sources = []
        self._confidence = ConfidenceLevel.MEDIUM
        self._tools_used = []
        self._follow_up_suggestions = []
        self._execution_time_ms = 0
        self._data_coverage = None
        self._error = None
        self._entity_name = None
        self._sections = None
        self._questions = None
        self._candidates = None
        self._message = None

    def as_answer(self) -> "ResponseBuilder":
        self._type = ResponseType.ANSWER
        return self

    def as_kyp_report(self) -> "ResponseBuilder":
        self._type = ResponseType.KYP_REPORT
        return self

    def as_error(self) -> "ResponseBuilder":
        self._type = ResponseType.ERROR
        return self

    def as_clarification(self) -> "ResponseBuilder":
        self._type = ResponseType.CLARIFICATION_NEEDED
        return self

    def with_answer(self, answer: str) -> "ResponseBuilder":
        self._answer = answer
        return self

    def with_error(self, error: str) -> "ResponseBuilder":
        self._error = error
        return self

    def with_sources(self, sources: list[str]) -> "ResponseBuilder":
        self._sources = sources
        return self

    def with_confidence(self, confidence: ConfidenceLevel) -> "ResponseBuilder":
        self._confidence = confidence
        return self

    def with_tools(self, tools: list[str]) -> "ResponseBuilder":
        self._tools_used = tools
        return self

    def with_follow_ups(self, suggestions: list[str]) -> "ResponseBuilder":
        self._follow_up_suggestions = suggestions
        return self

    def with_execution_time(self, ms: int) -> "ResponseBuilder":
        self._execution_time_ms = ms
        return self

    def with_data_coverage(self, coverage: dict) -> "ResponseBuilder":
        self._data_coverage = coverage
        return self

    def with_entity(self, name: str) -> "ResponseBuilder":
        self._entity_name = name
        return self

    def with_sections(self, sections: list[dict]) -> "ResponseBuilder":
        self._sections = sections
        return self

    def with_questions(
        self, questions: list[ClarificationQuestion]
    ) -> "ResponseBuilder":
        self._questions = questions
        return self

    def with_candidates(self, candidates: list[EntityCandidate]) -> "ResponseBuilder":
        self._candidates = candidates
        return self

    def with_message(self, message: str) -> "ResponseBuilder":
        self._message = message
        return self

    def build(self) -> AgentResponse:
        """Build the final AgentResponse."""
        if self._type == ResponseType.ANSWER:
            return AgentResponse.create_answer(
                session_id=self._session_id,
                answer=self._answer or "",
                sources=self._sources,
                confidence=self._confidence,
                tools_used=self._tools_used,
                execution_time_ms=self._execution_time_ms,
                follow_up_suggestions=self._follow_up_suggestions,
                data_coverage=self._data_coverage,
            )
        elif self._type == ResponseType.ERROR:
            return AgentResponse.create_error(
                session_id=self._session_id,
                error=self._error or "Unknown error",
            )
        elif self._type == ResponseType.KYP_REPORT:
            return AgentResponse.kyp_report(
                session_id=self._session_id,
                entity_name=self._entity_name or "Unknown",
                sections=self._sections or [],
                sources=self._sources,
                follow_up_suggestions=self._follow_up_suggestions,
            )
        elif self._type == ResponseType.CLARIFICATION_NEEDED:
            return AgentResponse.clarification_needed(
                session_id=self._session_id,
                questions=self._questions or [],
            )
        elif self._type == ResponseType.ENTITY_CONFIRMATION_NEEDED:
            return AgentResponse.entity_confirmation_needed(
                session_id=self._session_id,
                message=self._message or "Please confirm.",
                candidates=self._candidates or [],
            )
        else:
            return AgentResponse.create_error(
                session_id=self._session_id,
                error=f"Unknown response type: {self._type}",
            )
