"""
Standardized Agent Response Structure

Provides a consistent response format for all agents to ensure
uniform handling by the A2A routing system and orchestrators.

Usage:
    from lead_to_cash.agents.base_response import AgentResponse

    def run(self, **kwargs) -> dict:
        result = await self._execute_task(...)
        return AgentResponse(
            success=True,
            agent_id=self.agent_id,
            result_data=result,
        ).to_dict()
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class AgentResponse:
    """Standardized response structure for all agents.

    This ensures consistent response handling across the A2A architecture,
    enabling orchestrators and Pipeline.router() to process agent outputs
    uniformly.

    Attributes:
        success: Whether the agent task completed successfully
        agent_id: Identifier of the agent that produced this response
        result_data: The actual result data from the agent
        error_message: Error description if success=False
        metadata: Additional context (timing, routing info, etc.)
    """

    success: bool
    agent_id: str
    result_data: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Add timestamp to metadata if not present."""
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with all response fields
        """
        return {
            "success": self.success,
            "agent_id": self.agent_id,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentResponse":
        """Create AgentResponse from dictionary.

        Args:
            data: Dictionary with response fields

        Returns:
            AgentResponse instance
        """
        return cls(
            success=data.get("success", False),
            agent_id=data.get("agent_id", "unknown"),
            result_data=data.get("result_data", {}),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def success_response(
        cls,
        agent_id: str,
        result_data: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> "AgentResponse":
        """Create a successful response.

        Args:
            agent_id: Agent identifier
            result_data: Result data
            metadata: Optional metadata

        Returns:
            AgentResponse with success=True
        """
        return cls(
            success=True,
            agent_id=agent_id,
            result_data=result_data,
            metadata=metadata or {},
        )

    @classmethod
    def error_response(
        cls,
        agent_id: str,
        error_message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "AgentResponse":
        """Create an error response.

        Args:
            agent_id: Agent identifier
            error_message: Error description
            metadata: Optional metadata

        Returns:
            AgentResponse with success=False
        """
        return cls(
            success=False,
            agent_id=agent_id,
            error_message=error_message,
            metadata=metadata or {},
        )
