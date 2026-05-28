"""
Unit Tests for Autonomous Agent Base Class

Tests the AutonomousAgent base class including:
- Configuration
- Execution state
- Convergence detection
- Extension points
"""

from datetime import UTC, datetime

import pytest

from lead_to_cash.agents.autonomous_base import (
    AutonomousAgent,
    AutonomousConfig,
    ExecutionState,
    SimpleAutonomousAgent,
)
from lead_to_cash.agents.contracts import (
    AgentResponse,
    ResponseType,
)
from lead_to_cash.agents.signatures import (
    AgentSignature,
    InputField,
    OutputField,
)


class TestAutonomousConfig:
    """Tests for AutonomousConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AutonomousConfig()

        assert config.max_cycles == 20
        assert config.checkpoint_frequency == 5
        assert config.enable_interrupts is True
        assert config.graceful_shutdown_timeout == 5.0
        assert config.tool_approval_required is False
        assert config.llm_provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.7

    def test_custom_config(self):
        """Test custom configuration."""
        config = AutonomousConfig(
            max_cycles=10,
            checkpoint_frequency=2,
            dangerous_tools=["bash_command"],
            tool_approval_required=True,
        )

        assert config.max_cycles == 10
        assert config.checkpoint_frequency == 2
        assert config.dangerous_tools == ["bash_command"]
        assert config.tool_approval_required is True


class TestExecutionState:
    """Tests for ExecutionState."""

    def test_initial_state(self):
        """Test initial execution state."""
        state = ExecutionState()

        assert state.current_cycle == 0
        assert state.converged is False
        assert state.tool_results == []
        assert state.cycle_history == []
        assert state.started_at is None
        assert state.completed_at is None
        assert state.error is None

    def test_elapsed_ms_not_started(self):
        """Test elapsed_ms when not started."""
        state = ExecutionState()
        assert state.elapsed_ms() == 0

    def test_elapsed_ms_in_progress(self):
        """Test elapsed_ms during execution."""
        state = ExecutionState()
        state.started_at = datetime.now(UTC)
        # Should return non-zero
        elapsed = state.elapsed_ms()
        assert elapsed >= 0

    def test_elapsed_ms_completed(self):
        """Test elapsed_ms after completion."""
        state = ExecutionState()
        state.started_at = datetime.now(UTC)
        state.completed_at = datetime.now(UTC)
        elapsed = state.elapsed_ms()
        assert elapsed >= 0


# Create a test signature for testing
class TestSignature(AgentSignature):
    """Test signature for unit tests."""

    query = InputField(description="Test query")
    result = OutputField(description="Test result")
    tool_calls = OutputField(description="Tools to call", default=[])


class ConcreteAutonomousAgent(AutonomousAgent):
    """Concrete implementation for testing."""

    def __init__(self, config: AutonomousConfig):
        super().__init__(
            agent_id="test_agent",
            config=config,
            signature_class=TestSignature,
        )
        self._cycle_results = []

    def _generate_system_prompt(self) -> str:
        return "You are a test agent."

    async def _execute_cycle(self, inputs: dict) -> dict:
        # Return predefined results or converge
        if self._cycle_results:
            return self._cycle_results.pop(0)
        return {"answer": "Done", "tool_calls": []}

    async def _call_tool(self, tool_name: str, params: dict) -> dict:
        return {"tool": tool_name, "result": "success"}

    def _build_response(self, result: dict, session_id: str) -> AgentResponse:
        return AgentResponse.create_answer(
            session_id=session_id,
            answer=result.get("answer", ""),
            tools_used=[r["tool"] for r in self.tool_results],
            execution_time_ms=self.execution_time_ms,
        )

    def set_cycle_results(self, results: list[dict]):
        """Set predefined results for testing."""
        self._cycle_results = results.copy()


class TestAutonomousAgentInit:
    """Tests for AutonomousAgent initialization."""

    def test_initialization(self):
        """Test agent initialization."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        assert agent.agent_id == "test_agent"
        assert agent.config == config
        assert agent.signature_class == TestSignature
        assert agent._state is None

    def test_register_tool(self):
        """Test tool registration."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        agent.register_tool(
            name="test_tool",
            description="A test tool",
            capabilities=["testing"],
        )

        catalog = agent._get_tool_catalog()
        assert len(catalog) == 1
        assert catalog[0]["name"] == "test_tool"


class TestAutonomousAgentExecution:
    """Tests for AutonomousAgent execution."""

    @pytest.mark.asyncio
    async def test_single_cycle_execution(self):
        """Test execution that converges in one cycle."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        response = await agent.execute(
            task="Test task",
            session_id="session123",
        )

        assert response.type == ResponseType.ANSWER
        assert response.session_id == "session123"
        assert agent.cycles_used == 1
        assert agent.is_converged is True

    @pytest.mark.asyncio
    async def test_multi_cycle_execution(self):
        """Test execution with multiple cycles."""
        config = AutonomousConfig(max_cycles=5)
        agent = ConcreteAutonomousAgent(config)

        # Set up results that require multiple cycles
        agent.set_cycle_results(
            [
                {"answer": "Cycle 1", "tool_calls": [{"tool": "tool1", "params": {}}]},
                {"answer": "Cycle 2", "tool_calls": [{"tool": "tool2", "params": {}}]},
                {"answer": "Final", "tool_calls": []},  # Converge
            ]
        )

        response = await agent.execute(
            task="Multi-cycle task",
            session_id="session123",
        )

        assert response.type == ResponseType.ANSWER
        assert agent.cycles_used == 3
        assert agent.is_converged is True

    @pytest.mark.asyncio
    async def test_max_cycles_limit(self):
        """Test that max_cycles limits execution."""
        config = AutonomousConfig(max_cycles=2)
        agent = ConcreteAutonomousAgent(config)

        # Set up results that never converge
        agent.set_cycle_results(
            [
                {"answer": "Cycle 1", "tool_calls": [{"tool": "tool1"}]},
                {"answer": "Cycle 2", "tool_calls": [{"tool": "tool2"}]},
                {"answer": "Cycle 3", "tool_calls": [{"tool": "tool3"}]},
            ]
        )

        await agent.execute(
            task="Non-converging task",
            session_id="session123",
        )

        # Should stop at max_cycles
        assert agent.cycles_used == 2
        assert agent.is_converged is False

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling during execution."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        # Override _execute_cycle to raise an error
        async def failing_cycle(inputs):
            raise ValueError("Test error")

        agent._execute_cycle = failing_cycle

        response = await agent.execute(
            task="Failing task",
            session_id="session123",
        )

        assert response.type == ResponseType.ERROR
        assert "Test error" in response.error


class TestConvergenceDetection:
    """Tests for convergence detection."""

    def test_converged_empty_tool_calls(self):
        """Test convergence with empty tool_calls."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        result = {"answer": "Done", "tool_calls": []}
        assert agent._check_convergence(result) is True

    def test_converged_none_tool_calls(self):
        """Test convergence with None tool_calls."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        result = {"answer": "Done", "tool_calls": None}
        assert agent._check_convergence(result) is True

    def test_converged_explicit_flag(self):
        """Test convergence with explicit converged flag."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        result = {"answer": "Done", "converged": True}
        assert agent._check_convergence(result) is True

    def test_not_converged_with_tool_calls(self):
        """Test non-convergence with pending tool calls."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        result = {"answer": "In progress", "tool_calls": [{"tool": "next_tool"}]}
        assert agent._check_convergence(result) is False


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test tool call execution."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        # Set up a cycle that calls a tool
        agent.set_cycle_results(
            [
                {
                    "answer": "Need data",
                    "tool_calls": [{"tool": "test_tool", "params": {"key": "value"}}],
                },
                {"answer": "Done", "tool_calls": []},
            ]
        )

        await agent.execute(task="Test", session_id="s1")

        # Check tool results were captured
        assert len(agent.tool_results) == 1
        assert agent.tool_results[0]["tool"] == "test_tool"
        assert agent.tool_results[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_dangerous_tool_approval(self):
        """Test that dangerous tools are blocked when approval required."""
        config = AutonomousConfig(
            tool_approval_required=True,
            dangerous_tools=["dangerous_tool"],
        )
        agent = ConcreteAutonomousAgent(config)

        # Set up a cycle that calls a dangerous tool
        agent.set_cycle_results(
            [
                {
                    "answer": "Need dangerous",
                    "tool_calls": [{"tool": "dangerous_tool"}],
                },
                {"answer": "Done", "tool_calls": []},
            ]
        )

        await agent.execute(task="Test", session_id="s1")

        # Dangerous tool should be blocked
        dangerous_result = agent.tool_results[0]
        assert dangerous_result["status"] == "approval_required"


class TestExtensionPoints:
    """Tests for extension points."""

    @pytest.mark.asyncio
    async def test_pre_execution_hook(self):
        """Test pre-execution hook is called."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        hook_called = []

        original_hook = agent._pre_execution_hook

        def tracking_hook(inputs):
            hook_called.append(True)
            return original_hook(inputs)

        agent._pre_execution_hook = tracking_hook

        await agent.execute(task="Test", session_id="s1")

        assert len(hook_called) == 1

    @pytest.mark.asyncio
    async def test_post_execution_hook(self):
        """Test post-execution hook is called."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        hook_called = []

        original_hook = agent._post_execution_hook

        def tracking_hook(result):
            hook_called.append(True)
            return original_hook(result)

        agent._post_execution_hook = tracking_hook

        await agent.execute(task="Test", session_id="s1")

        assert len(hook_called) == 1


class TestA2ACard:
    """Tests for A2A capability card."""

    def test_a2a_card_generation(self):
        """Test A2A card is generated correctly."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        card = agent.to_a2a_card()

        assert card["agent_id"] == "test_agent"
        assert card["status"] == "active"
        assert "capabilities" in card
        assert "input_schema" in card
        assert "output_schema" in card

    def test_a2a_card_includes_tools(self):
        """Test A2A card includes registered tools."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        agent.register_tool("tool1", "First tool", ["cap1"])
        agent.register_tool("tool2", "Second tool", ["cap2"])

        card = agent.to_a2a_card()

        assert "tool1" in card["tools"]
        assert "tool2" in card["tools"]


class TestSimpleAutonomousAgent:
    """Tests for SimpleAutonomousAgent helper class."""

    @pytest.mark.asyncio
    async def test_simple_agent_execution(self):
        """Test SimpleAutonomousAgent execution."""

        class TestSimpleAgent(SimpleAutonomousAgent):
            async def _process_task(self, task, tool_results, context):
                return {"answer": f"Processed: {task}", "tool_calls": []}

        config = AutonomousConfig()
        agent = TestSimpleAgent(
            agent_id="simple_test",
            config=config,
            signature_class=TestSignature,
            system_prompt="You are a simple test agent.",
        )

        response = await agent.execute(
            task="Simple task",
            session_id="session123",
        )

        assert response.type == ResponseType.ANSWER
        assert "Simple task" in response.answer

    @pytest.mark.asyncio
    async def test_simple_agent_default_tool_call(self):
        """Test SimpleAutonomousAgent default tool calling."""

        class TestSimpleAgent(SimpleAutonomousAgent):
            async def _process_task(self, task, tool_results, context):
                return {"answer": "Done", "tool_calls": []}

        config = AutonomousConfig()
        agent = TestSimpleAgent(
            agent_id="simple_test",
            config=config,
            signature_class=TestSignature,
            system_prompt="Test prompt",
        )

        # Default _call_tool should return error
        result = await agent._call_tool("unknown_tool", {})
        assert "not implemented" in result.get("error", "").lower()


class TestAgentProperties:
    """Tests for agent properties."""

    @pytest.mark.asyncio
    async def test_cycles_used_property(self):
        """Test cycles_used property."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        # Before execution
        assert agent.cycles_used == 0

        await agent.execute(task="Test", session_id="s1")

        # After execution
        assert agent.cycles_used > 0

    @pytest.mark.asyncio
    async def test_execution_time_property(self):
        """Test execution_time_ms property."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        await agent.execute(task="Test", session_id="s1")

        # Should have non-zero execution time
        assert agent.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_is_converged_property(self):
        """Test is_converged property."""
        config = AutonomousConfig()
        agent = ConcreteAutonomousAgent(config)

        # Before execution
        assert agent.is_converged is False

        await agent.execute(task="Test", session_id="s1")

        # After successful execution
        assert agent.is_converged is True
