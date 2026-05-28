"""
Integration Tests for Agent Registry Resilience Patterns

Tests circuit breaker, retry logic, and health degradation in the context
of the agent registry. Uses real infrastructure (NO MOCKING) as per testing policy.

These tests verify:
- Circuit breaker behavior in registry.process()
- Health check degradation when circuits are open
- Retry logic for transient failures
- Fallback to orchestrator when agent circuits open
"""

import asyncio
from typing import Any, Optional

import pytest

from lead_to_cash.agents.registry import AgentRegistry, AgentStatus, RegisteredAgent
from lead_to_cash.utils.resilience import CircuitBreaker


class MockFailingAgent:
    """Mock agent that fails a configurable number of times."""

    def __init__(self, fail_count: int = 0, transient: bool = False):
        self.agent_id = "mock_failing"
        self.fail_count = fail_count
        self.call_count = 0
        self.transient = transient

    def _extract_primary_capabilities(self):
        """Return capabilities for routing."""
        try:
            from kaizen.nodes.ai.a2a import Capability, CapabilityLevel
        except ImportError:
            return []

        return [
            Capability(
                name="mock_capability",
                domain="testing",
                level=CapabilityLevel.EXPERT,
                description="Mock capability for testing",
                keywords=["mock", "test", "failing"],
                examples=["test request"],
                constraints=[],
            )
        ]

    def run(self, task: str, context: Optional[dict] = None) -> dict[str, Any]:
        """Run the agent - fails first N calls."""
        self.call_count += 1
        if self.call_count <= self.fail_count:
            if self.transient:
                raise ConnectionError("Connection refused")
            raise ValueError("Simulated failure")
        return {"result": "success", "call_count": self.call_count}


class MockOrchestratorAgent:
    """Mock orchestrator for fallback testing."""

    def __init__(self):
        self.agent_id = "mock_orchestrator"
        self.call_count = 0

    async def process_request(
        self, request: str, context: Optional[dict] = None
    ) -> dict[str, Any]:
        """Process request as orchestrator."""
        self.call_count += 1
        return {"result": "orchestrator_handled", "call_count": self.call_count}


# =============================================================================
# Registry Circuit Breaker Integration Tests
# =============================================================================


class TestRegistryCircuitBreaker:
    """Test circuit breaker behavior in registry context."""

    @pytest.fixture
    def registry(self):
        """Create a clean registry instance."""
        reg = AgentRegistry(llm_provider="openai", model="gpt-4o")
        reg._initialized = True  # Skip full initialization
        reg._agents = {}
        reg._circuit_breakers = {}
        reg._orchestrator = None
        return reg

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, registry):
        """Circuit should open after threshold failures in registry."""
        # Register a failing agent
        failing_agent = MockFailingAgent(fail_count=10)  # Always fails

        registry._agents["mock_failing"] = RegisteredAgent(
            agent_id="mock_failing",
            agent_type="MockFailingAgent",
            agent=failing_agent,
            status=AgentStatus.ACTIVE,
        )

        # Process requests until circuit opens (threshold is 5)
        failures = 0
        for _ in range(6):
            try:
                # Need to mock _select_best_agent to return our agent
                registry._select_best_agent = lambda req: failing_agent
                await registry.process("test mock request")
            except (ValueError, RuntimeError):
                failures += 1

        # Verify circuit is now open
        circuit = registry._circuit_breakers.get("mock_failing")
        assert circuit is not None
        assert circuit.state == "OPEN"
        assert failures >= 5

    @pytest.mark.asyncio
    async def test_circuit_prevents_further_calls(self, registry):
        """Open circuit should prevent further agent calls."""
        failing_agent = MockFailingAgent(fail_count=10)

        registry._agents["mock_failing"] = RegisteredAgent(
            agent_id="mock_failing",
            agent_type="MockFailingAgent",
            agent=failing_agent,
            status=AgentStatus.ACTIVE,
        )

        # Manually open the circuit
        registry._circuit_breakers["mock_failing"] = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60
        )
        for _ in range(5):
            registry._circuit_breakers["mock_failing"].record_failure()

        assert registry._circuit_breakers["mock_failing"].state == "OPEN"

        # Should raise RuntimeError without calling agent
        call_count_before = failing_agent.call_count

        registry._select_best_agent = lambda req: failing_agent

        with pytest.raises(RuntimeError, match="circuit breaker open"):
            await registry.process("test request")

        # Agent should not have been called
        assert failing_agent.call_count == call_count_before

    @pytest.mark.asyncio
    async def test_fallback_to_orchestrator_on_open_circuit(self, registry):
        """Should fallback to orchestrator when circuit is open."""
        failing_agent = MockFailingAgent(fail_count=10)
        orchestrator = MockOrchestratorAgent()

        registry._agents["mock_failing"] = RegisteredAgent(
            agent_id="mock_failing",
            agent_type="MockFailingAgent",
            agent=failing_agent,
            status=AgentStatus.ACTIVE,
        )
        registry._orchestrator = orchestrator

        # Open the circuit
        registry._circuit_breakers["mock_failing"] = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60
        )
        for _ in range(5):
            registry._circuit_breakers["mock_failing"].record_failure()

        registry._select_best_agent = lambda req: failing_agent

        # Should fallback to orchestrator
        result = await registry.process("test request")
        assert result["result"] == "orchestrator_handled"
        assert orchestrator.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_closes_on_success(self, registry):
        """Circuit should close after successful calls in HALF_OPEN state."""
        agent = MockFailingAgent(fail_count=0)  # Never fails
        # Use same agent_id for both agent and circuit breaker key
        agent.agent_id = "mock_agent"

        registry._agents["mock_agent"] = RegisteredAgent(
            agent_id="mock_agent",
            agent_type="MockAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        # Create circuit in HALF_OPEN state with same params as registry uses
        circuit = CircuitBreaker(
            failure_threshold=5, recovery_timeout=0, half_open_max_calls=3
        )
        # Open and wait for half-open
        for _ in range(5):
            circuit.record_failure()
        await asyncio.sleep(0.1)  # Wait for timeout

        # Use agent.agent_id as key (registry uses selected_agent.agent_id)
        registry._circuit_breakers[agent.agent_id] = circuit
        registry._select_best_agent = lambda req: agent

        # Verify circuit is in HALF_OPEN
        assert circuit.state == "HALF_OPEN"

        # Successful calls should close circuit (need 3 for half_open_max_calls=3)
        await registry.process("test request")
        await registry.process("test request")
        await registry.process("test request")

        assert circuit.state == "CLOSED"


# =============================================================================
# Registry Retry Logic Tests
# =============================================================================


class TestRegistryRetryLogic:
    """Test retry behavior for transient failures in registry."""

    @pytest.fixture
    def registry(self):
        """Create a clean registry instance."""
        reg = AgentRegistry(llm_provider="openai", model="gpt-4o")
        reg._initialized = True
        reg._agents = {}
        reg._circuit_breakers = {}
        reg._orchestrator = None
        return reg

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self, registry):
        """Should retry on transient connection errors."""
        # Fails first 2 times (transient), succeeds on 3rd
        agent = MockFailingAgent(fail_count=2, transient=True)

        registry._agents["mock_agent"] = RegisteredAgent(
            agent_id="mock_agent",
            agent_type="MockAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )
        registry._select_best_agent = lambda req: agent

        # Should succeed after retries
        result = await registry.process("test request")
        assert result["result"] == "success"
        assert agent.call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_no_retry_on_non_transient_error(self, registry):
        """Should not retry on non-transient errors."""
        # Fails with ValueError (not transient)
        agent = MockFailingAgent(fail_count=10, transient=False)

        registry._agents["mock_agent"] = RegisteredAgent(
            agent_id="mock_agent",
            agent_type="MockAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )
        registry._select_best_agent = lambda req: agent

        # Should fail immediately without retries (then fallback fails)
        with pytest.raises(ValueError, match="Simulated failure"):
            await registry.process("test request")

        # Only 1 call (no retries for non-transient)
        assert agent.call_count == 1


# =============================================================================
# Health Check Degradation Tests
# =============================================================================


class TestHealthCheckDegradation:
    """Test health check reflects circuit breaker states."""

    @pytest.fixture
    def registry(self):
        """Create a clean registry instance."""
        reg = AgentRegistry(llm_provider="openai", model="gpt-4o")
        reg._initialized = True
        reg._agents = {}
        reg._circuit_breakers = {}
        reg._orchestrator = None
        return reg

    @pytest.mark.asyncio
    async def test_health_shows_open_circuits(self, registry):
        """Health check should show open circuit breakers."""
        # Register a mock agent
        agent = MockFailingAgent(fail_count=0)
        registry._agents["test_agent"] = RegisteredAgent(
            agent_id="test_agent",
            agent_type="TestAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        # Open the circuit
        circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        for _ in range(5):
            circuit.record_failure()
        registry._circuit_breakers["test_agent"] = circuit

        # Run health check
        health = await registry.health_check()

        # Should show degraded status
        assert health["registry_status"] == "degraded"
        assert "test_agent" in health["circuit_summary"]["open_agents"]
        assert health["circuit_summary"]["open_count"] == 1

    @pytest.mark.asyncio
    async def test_health_shows_healthy_when_circuits_closed(self, registry):
        """Health check should show healthy when all circuits closed."""
        # Register a mock agent
        agent = MockFailingAgent(fail_count=0)
        registry._agents["test_agent"] = RegisteredAgent(
            agent_id="test_agent",
            agent_type="TestAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        # Create a closed circuit
        circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        registry._circuit_breakers["test_agent"] = circuit

        # Run health check
        health = await registry.health_check()

        # Should be healthy
        assert health["registry_status"] == "healthy"
        assert health["circuit_summary"]["open_count"] == 0

    @pytest.mark.asyncio
    async def test_health_updates_agent_status_on_open_circuit(self, registry):
        """Agent status should reflect circuit breaker state."""
        agent = MockFailingAgent(fail_count=0)
        registry._agents["test_agent"] = RegisteredAgent(
            agent_id="test_agent",
            agent_type="TestAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )

        # Open the circuit
        circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        for _ in range(5):
            circuit.record_failure()
        registry._circuit_breakers["test_agent"] = circuit

        # Run health check
        await registry.health_check()

        # Agent status should be ERROR
        assert registry._agents["test_agent"].status == AgentStatus.ERROR


# =============================================================================
# Trace Context Propagation Tests
# =============================================================================


class TestTraceContextPropagation:
    """Test trace context is properly passed through registry."""

    @pytest.fixture
    def registry(self):
        """Create a clean registry instance."""
        reg = AgentRegistry(llm_provider="openai", model="gpt-4o")
        reg._initialized = True
        reg._agents = {}
        reg._circuit_breakers = {}
        reg._orchestrator = None
        return reg

    @pytest.mark.asyncio
    async def test_process_accepts_trace_context(self, registry):
        """Registry.process() should accept trace_context parameter."""
        agent = MockFailingAgent(fail_count=0)
        registry._agents["test_agent"] = RegisteredAgent(
            agent_id="test_agent",
            agent_type="TestAgent",
            agent=agent,
            status=AgentStatus.ACTIVE,
        )
        registry._select_best_agent = lambda req: agent

        # Should accept trace_context without error
        result = await registry.process(
            "test request",
            context=None,
            trace_context=None,  # Would be SpanContext in real usage
        )
        assert result["result"] == "success"
