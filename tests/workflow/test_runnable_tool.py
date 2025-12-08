"""Tests for RunnableTool - Agent/Workflow as Tool functionality."""

import pytest

from agio.domain import StepEvent, StepEventType
from agio.workflow.runnable_tool import (
    RunnableTool,
    as_tool,
    DEFAULT_MAX_DEPTH,
    CircularReferenceError,
    MaxDepthExceededError,
)


class MockRunnable:
    """Mock Runnable for testing."""

    def __init__(self, output: str = "test output", should_fail: bool = False):
        self._id = "mock_agent"
        self._output = output
        self._should_fail = should_fail
        self._last_output: str | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def last_output(self) -> str | None:
        return self._last_output

    async def run(self, input: str, *, context=None):
        if self._should_fail:
            raise RuntimeError("Mock error")
        
        self._last_output = self._output
        yield StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id="test_run",
        )
        yield StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id="test_run",
            data={"response": self._output},
        )


class TestRunnableTool:
    """Tests for RunnableTool class."""

    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """Test basic tool execution returns correct output."""
        mock_runnable = MockRunnable(output="Hello from mock")
        tool = as_tool(mock_runnable, "Test tool")

        result = await tool.execute({"task": "Do something"})

        assert result.is_success
        assert result.content == "Hello from mock"
        assert result.tool_name == "call_mock_agent"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_custom_name(self):
        """Test custom tool name."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, description="Test", name="my_custom_tool")

        assert tool.get_name() == "my_custom_tool"

    @pytest.mark.asyncio
    async def test_default_name(self):
        """Test default tool name is call_{runnable.id}."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        assert tool.get_name() == "call_mock_agent"

    @pytest.mark.asyncio
    async def test_description(self):
        """Test tool description."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, "Expert at research tasks")

        assert tool.get_description() == "Expert at research tasks"

    @pytest.mark.asyncio
    async def test_default_description(self):
        """Test default description."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        assert "mock_agent" in tool.get_description()

    @pytest.mark.asyncio
    async def test_event_callback(self):
        """Test event callback is called for each event."""
        mock_runnable = MockRunnable()
        events_received = []

        async def callback(event):
            events_received.append(event)

        tool = RunnableTool(mock_runnable, event_callback=callback)
        await tool.execute({"task": "Test"})

        assert len(events_received) == 2  # RUN_STARTED + RUN_COMPLETED
        assert events_received[0].type == StepEventType.RUN_STARTED
        assert events_received[1].type == StepEventType.RUN_COMPLETED

    @pytest.mark.asyncio
    async def test_event_callback_receives_depth(self):
        """Test event callback receives correct depth."""
        mock_runnable = MockRunnable()
        events_received = []

        async def callback(event):
            events_received.append(event)

        tool = RunnableTool(mock_runnable, event_callback=callback)
        await tool.execute({"task": "Test", "_depth": 1})

        # All events should have depth = 2 (parent depth + 1)
        for event in events_received:
            assert event.depth == 2

    @pytest.mark.asyncio
    async def test_task_with_context(self):
        """Test task execution with additional context."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        result = await tool.execute({
            "task": "Do something",
            "context": "Additional context here",
        })

        assert result.is_success
        assert result.input_args["task"] == "Do something"
        assert result.input_args["context"] == "Additional context here"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling when runnable fails."""
        mock_runnable = MockRunnable(should_fail=True)
        tool = as_tool(mock_runnable)

        result = await tool.execute({"task": "This will fail"})

        assert not result.is_success
        assert result.error is not None
        assert "Mock error" in result.error
        assert "Error executing mock_agent" in result.content

    def test_tool_schema(self):
        """Test tool generates correct OpenAI schema."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, "My description")

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "call_mock_agent"
        assert schema["function"]["description"] == "My description"
        assert "task" in schema["function"]["parameters"]["properties"]
        assert "context" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["task"]

    def test_is_concurrency_safe(self):
        """Test that RunnableTool is concurrency safe."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        assert tool.is_concurrency_safe() is True

    @pytest.mark.asyncio
    async def test_duration_tracking(self):
        """Test that execution duration is tracked."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        result = await tool.execute({"task": "Test"})

        assert result.duration > 0
        assert result.start_time < result.end_time


class TestAsTool:
    """Tests for as_tool factory function."""

    def test_creates_runnable_tool(self):
        """Test as_tool creates RunnableTool instance."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        assert isinstance(tool, RunnableTool)

    def test_passes_description(self):
        """Test as_tool passes description correctly."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, description="Custom description")

        assert tool.get_description() == "Custom description"

    def test_passes_name(self):
        """Test as_tool passes name correctly."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, name="custom_name")

        assert tool.get_name() == "custom_name"

    def test_passes_max_depth(self):
        """Test as_tool passes max_depth correctly."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, max_depth=3)

        assert tool.max_depth == 3


class TestSafetyFeatures:
    """Tests for safety features: depth limit and circular reference detection."""

    @pytest.mark.asyncio
    async def test_max_depth_exceeded(self):
        """Test that max depth limit is enforced."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable, max_depth=2)

        # Simulate being called at depth 2 (will become depth 3)
        result = await tool.execute({
            "task": "Test",
            "_depth": 2,
            "_call_stack": ["agent_a", "agent_b"],
        })

        assert not result.is_success
        assert "Maximum nesting depth" in result.content
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_circular_reference_detected(self):
        """Test that circular reference is detected."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        # Simulate mock_agent already being in the call stack
        result = await tool.execute({
            "task": "Test",
            "_call_stack": ["agent_a", "mock_agent", "agent_b"],
        })

        assert not result.is_success
        assert "Circular reference detected" in result.content
        assert "mock_agent" in result.content
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_call_stack_propagation(self):
        """Test that call stack is properly passed to nested executions."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        # First call - no call stack yet
        result = await tool.execute({"task": "Test"})
        assert result.is_success

    @pytest.mark.asyncio
    async def test_default_max_depth(self):
        """Test default max depth is used."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        assert tool.max_depth == DEFAULT_MAX_DEPTH

    @pytest.mark.asyncio
    async def test_depth_increments_correctly(self):
        """Test that depth increments on each nested call."""
        events_with_depth = []
        
        async def callback(event):
            events_with_depth.append(event.depth)
        
        mock_runnable = MockRunnable()
        tool = RunnableTool(mock_runnable, event_callback=callback)
        
        # Call at depth 0
        await tool.execute({"task": "Test", "_depth": 0})
        
        # Events should have depth 1
        for depth in events_with_depth:
            assert depth == 1

    @pytest.mark.asyncio
    async def test_self_reference_in_call_stack(self):
        """Test self-reference detection via call stack."""
        mock_runnable = MockRunnable()
        tool = as_tool(mock_runnable)

        # Self-reference: mock_agent is already in call stack
        result = await tool.execute({
            "task": "Test",
            "_call_stack": ["mock_agent"],
        })

        assert not result.is_success
        assert "Circular reference detected" in result.content
