"""
Autonomous Agents Package

This package contains truly autonomous agents that:
- Inherit from AutonomousAgent base class
- Use signatures for capability declaration
- Return typed AgentResponse
- Autonomously select tools (not hardcoded pipelines)
- Detect convergence via tool_calls field

Available Agents:
- MarineIntelAgent: Market intelligence and opportunity discovery
"""

from lead_to_cash.agents.autonomous.marine_intel_agent import (
    AutonomousMarineIntelAgent,
)

__all__ = [
    "AutonomousMarineIntelAgent",
]
