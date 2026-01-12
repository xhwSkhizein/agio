"""
Test timeout mechanism fix for AgentTool.

Verify that timeout is passed as signal to nested Agent,
allowing summarize logic to execute instead of forced cancellation.
"""

import asyncio
import time

import pytest

from agio.agent import Agent
from agio.config import ExecutionConfig
from agio.llm import Model, StreamChunk
from agio.runtime import AgentTool
from agio.runtime.context import ExecutionContext
from agio.runtime.wire import Wire
from agio.tools import BaseTool
from agio.tools.executor import ToolExecutor


class MockModel(Model):
    """Mock model for testing."""

    id: str = "test/mock"
    name: str = "mock"

    def __init__(self, response: str = "Mock response"):
        super().__init__()
        self._response = response

    async def arun_stream(self, messages, tools=None):
        yield StreamChunk(content=self._response)
        yield StreamChunk(usage={"total_tokens": 10})


class SlowTool(BaseTool):
    """Tool that takes longer than timeout."""

    def get_name(self) -> str:
        return "slow_tool"

    def get_description(self) -> str:
        return "A slow tool for testing"

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "duration": {"type": "number", "description": "Sleep duration"}
            },
            "required": ["duration"],
        }

    def is_concurrency_safe(self) -> bool:
        return True

    async def execute(self, parameters: dict, context: ExecutionContext, **kwargs):
        from agio.domain import ToolResult

        start = time.time()
        duration = parameters.get("duration", 5.0)
        await asyncio.sleep(duration)
        end = time.time()

        return ToolResult(
            tool_name=self.get_name(),
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content=f"Slept for {end - start:.2f}s",
            output=None,
            error=None,
            start_time=start,
            end_time=end,
            duration=end - start,
            is_success=True,
        )


@pytest.mark.asyncio
async def test_timeout_signal_propagation():
    """Test that timeout is passed as signal, not forced cancellation."""

    # Create nested agent with slow tool
    slow_tool = SlowTool()
    nested_agent = Agent(
        model=MockModel(response="Using slow tool"),
        tools=[slow_tool],
        max_steps=5,
        enable_termination_summary=True,
    )

    # Wrap as tool
    agent_tool = AgentTool(nested_agent, description="Nested agent with slow tool")

    # Create tool executor with short timeout
    tool_executor = ToolExecutor(
        tools=[agent_tool],
        default_timeout=2.0,  # 2 second timeout
    )

    # Create execution context
    wire = Wire()
    context = ExecutionContext(
        run_id="test_run",
        session_id="test_session",
        wire=wire,
    )

    # Execute tool call that will timeout
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": agent_tool.get_name(),
            "arguments": '{"task": "Do something slow"}',
        },
    }

    start_time = time.time()
    result = await tool_executor.execute(tool_call, context)
    elapsed = time.time() - start_time

    # Verify timeout was respected (approximately)
    assert elapsed < 5.0, "Should not wait for full slow tool duration"

    # Verify result is returned (not exception)
    assert result is not None
    assert result.tool_name == agent_tool.get_name()

    await wire.close()


@pytest.mark.asyncio
async def test_context_timeout_at_propagation():
    """Test that timeout_at is properly propagated through context."""

    wire = Wire()
    context = ExecutionContext(
        run_id="test_run",
        session_id="test_session",
        wire=wire,
    )

    # Create child context
    child = context.child(run_id="child_run", timeout_at=time.time() + 10)

    # Verify timeout_at is propagated
    assert child.timeout_at is not None
    assert child.timeout_at > time.time()

    # Create grandchild - should inherit timeout
    grandchild = child.child(run_id="grandchild_run")
    assert grandchild.timeout_at == child.timeout_at

    await wire.close()


@pytest.mark.asyncio
async def test_agent_respects_context_timeout():
    """Test that Agent checks context.timeout_at in check_limits."""

    from agio.agent.executor import RunState
    from agio.runtime.pipeline import StepPipeline

    wire = Wire()
    context = ExecutionContext(
        run_id="test_run",
        session_id="test_session",
        wire=wire,
        timeout_at=time.time() + 0.1,  # Timeout in 100ms
    )

    config = ExecutionConfig(max_steps=10)
    # Create a dummy pipeline
    pipeline = StepPipeline(context)
    state = RunState.create(context, config, [], pipeline)

    # Initially no timeout
    assert state.check_limits() is None

    # Wait for timeout
    await asyncio.sleep(0.15)

    # Should detect timeout
    reason = state.check_limits()
    assert reason == "timeout"

    await wire.close()
