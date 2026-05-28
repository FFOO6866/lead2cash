"""
Response Adapter - Bridge between AgentResponse and legacy dict format.

This adapter enables gradual migration from raw dict responses to typed
AgentResponse without breaking existing code.

Phase 2 Integration Strategy:
- conversation.py continues to return raw dicts to frontend
- New autonomous agents return AgentResponse
- This adapter converts between formats

Usage:
    from lead_to_cash.agents.response_adapter import to_dict, from_dict, AgentResponseAdapter

    # Convert AgentResponse to dict for frontend
    agent_response = agent.execute(task, session_id)
    legacy_dict = to_dict(agent_response)

    # Convert legacy dict to AgentResponse
    legacy_result = {"type": "answer", "answer": "...", ...}
    agent_response = from_dict(legacy_result, session_id)
"""

import logging
from typing import Any, Optional

from lead_to_cash.agents.contracts import (
    AgentResponse,
    ClarificationQuestion,
    ConfidenceLevel,
    EntityCandidate,
    ResponseType,
)

logger = logging.getLogger(__name__)


def to_dict(response: AgentResponse) -> dict[str, Any]:
    """
    Convert AgentResponse to legacy dict format for backwards compatibility.

    This allows new autonomous agents to return AgentResponse while
    conversation.py continues to work with dicts.

    Args:
        response: Typed AgentResponse from autonomous agent

    Returns:
        Dict in format expected by conversation.py and frontend
    """
    return response.to_dict()


def from_dict(data: dict[str, Any], session_id: Optional[str] = None) -> AgentResponse:
    """
    Convert legacy dict response to AgentResponse.

    Enables existing code that returns dicts to be wrapped in typed responses.

    Args:
        data: Legacy dict response from existing code
        session_id: Session ID (uses data["session_id"] if not provided)

    Returns:
        Typed AgentResponse
    """
    session_id = session_id or data.get("session_id", "")
    response_type = data.get("type", "answer")

    # Map string type to ResponseType enum
    type_map = {
        "answer": ResponseType.ANSWER,
        "kyp_report": ResponseType.KYP_REPORT,
        "clarification_needed": ResponseType.CLARIFICATION_NEEDED,
        "entity_confirmation_needed": ResponseType.ENTITY_CONFIRMATION_NEEDED,
        "error": ResponseType.ERROR,
    }

    resp_type = type_map.get(response_type, ResponseType.ANSWER)

    if resp_type == ResponseType.ANSWER:
        return AgentResponse.create_answer(
            session_id=session_id,
            answer=data.get("answer", ""),
            sources=data.get("sources", []),
            confidence=_parse_confidence(data.get("confidence", "MEDIUM")),
            tools_used=data.get("tools_used", []),
            execution_time_ms=data.get("execution_time_ms", 0),
            follow_up_suggestions=data.get("follow_up_suggestions", []),
        )

    elif resp_type == ResponseType.KYP_REPORT:
        return AgentResponse.kyp_report(
            session_id=session_id,
            entity_name=data.get("entity_name", ""),
            sections=data.get("sections", []),
            overall_status=data.get("overall_status"),
            can_proceed=data.get("can_proceed"),
            risk_score=data.get("risk_score"),
            sources=data.get("sources", []),
        )

    elif resp_type == ResponseType.CLARIFICATION_NEEDED:
        questions = [
            ClarificationQuestion(
                question=q.get("question", ""),
                options=q.get("options", []),
                field_name=q.get("field_name", ""),
            )
            for q in data.get("questions", [])
        ]
        return AgentResponse.clarification_needed(
            session_id=session_id,
            questions=questions,
            partial_understanding=data.get("partial_understanding"),
        )

    elif resp_type == ResponseType.ENTITY_CONFIRMATION_NEEDED:
        candidates = [
            EntityCandidate(
                entity_id=c.get("entity_id", ""),
                name=c.get("name", ""),
                match_type=c.get("match_type", "unknown"),
                confidence=c.get("confidence", 0.0),
                metadata=c.get("metadata", {}),
            )
            for c in data.get("candidates", [])
        ]
        return AgentResponse.entity_confirmation_needed(
            session_id=session_id,
            message=data.get("message", ""),
            candidates=candidates,
            original_query=data.get("original_query"),
        )

    elif resp_type == ResponseType.ERROR:
        return AgentResponse.create_error(
            session_id=session_id,
            error=data.get("error", "Unknown error"),
        )

    # Fallback
    return AgentResponse.create_answer(
        session_id=session_id,
        answer=data.get("answer", data.get("response", "")),
    )


def _parse_confidence(confidence: Any) -> ConfidenceLevel:
    """Parse confidence from various formats."""
    if isinstance(confidence, ConfidenceLevel):
        return confidence

    if isinstance(confidence, str):
        confidence_upper = confidence.upper()
        if confidence_upper == "HIGH":
            return ConfidenceLevel.HIGH
        elif confidence_upper == "LOW":
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.MEDIUM


class AgentResponseAdapter:
    """
    Adapter class for bidirectional conversion.

    Provides a class-based interface for the conversion functions.
    """

    @staticmethod
    def to_legacy_dict(response: AgentResponse) -> dict[str, Any]:
        """Convert AgentResponse to legacy dict."""
        return to_dict(response)

    @staticmethod
    def from_legacy_dict(
        data: dict[str, Any], session_id: Optional[str] = None
    ) -> AgentResponse:
        """Convert legacy dict to AgentResponse."""
        return from_dict(data, session_id)

    @staticmethod
    def ensure_typed(
        response: AgentResponse | dict[str, Any], session_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Ensure response is an AgentResponse.

        If already AgentResponse, returns as-is.
        If dict, converts to AgentResponse.
        """
        if isinstance(response, AgentResponse):
            return response
        return from_dict(response, session_id)

    @staticmethod
    def ensure_dict(response: AgentResponse | dict[str, Any]) -> dict[str, Any]:
        """
        Ensure response is a dict.

        If already dict, returns as-is.
        If AgentResponse, converts to dict.
        """
        if isinstance(response, dict):
            return response
        return to_dict(response)
