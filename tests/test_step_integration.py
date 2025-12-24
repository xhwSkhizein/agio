"""
Integration test for Step-based execution flow.

Tests the complete flow:
1. AgentRunner creates Steps
2. AgentExecutor emits StepEvents
3. Steps are saved to session_store
4. Context is built from Steps
5. Retry works correctly
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from agio.providers.storage import InMemorySessionStore
from agio.domain import MessageRole, Step, StepEventType, AgentSession
from agio.agent import Agent, AgentExecutor
from agio.runtime import Wire
from agio.runtime.control import fork_session
from agio.runtime.protocol import ExecutionContext
from agio.providers.llm import StreamChunk


async def run_with_wire(agent, session, query, session_store=None):
    """Helper to run with Wire and collect events."""
    from agio.runtime import SequenceManager

    wire = Wire()
    sequence_manager = SequenceManager(session_store) if session_store else None

    context = ExecutionContext(
        wire=wire,
        sequence_manager=sequence_manager,
        session_id=session.session_id,
        run_id="run_123",
    )
    events = []

    async def _run():
        try:
            await agent.run(query, abort_signal=None, context=context)
        finally:
            await wire.close()

    task = asyncio.create_task(_run())

    async for event in wire.read():
        events.append(event)

    await task
    return events


@pytest.fixture
def mock_model():
    """Create a mock model that returns simple responses"""
    model = MagicMock()
    model.model_name = "mock-gpt"
    model.provider = "mock"

    async def mock_stream(messages, tools=None):
        # Simulate streaming response
        yield StreamChunk(content="Hello", tool_calls=None, usage=None)
        yield StreamChunk(content=" there", tool_calls=None, usage=None)
        yield StreamChunk(content="!", tool_calls=None, usage=None)
        yield StreamChunk(
            content=None,
            tool_calls=None,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )

    model.arun_stream = mock_stream
    return model


@pytest.fixture
def mock_agent(mock_model, session_store):
    """Create a real Agent for integration tests"""
    return Agent(
        model=mock_model,
        tools=[],
        session_store=session_store,
        system_prompt="You are a helpful assistant",
        max_steps=5,
        name="agent_123",
    )


@pytest.fixture
def session_store():
    """Create in-memory session store"""
    return InMemorySessionStore()


@pytest.fixture
def session():
    """Create test session"""
    return AgentSession(session_id="session_123", user_id="user_456")


@pytest.mark.asyncio
async def test_step_executor_creates_steps(mock_model, session_store):
    """Test that AgentExecutor creates proper Steps"""
    executor = AgentExecutor(model=mock_model, tools=[])

    messages = [{"role": "user", "content": "Hello"}]

    from agio.runtime.protocol import ExecutionContext
    from agio.runtime import Wire, SequenceManager
    from agio.providers.storage.base import InMemorySessionStore

    # Create SequenceManager for testing
    session_store = InMemorySessionStore()
    sequence_manager = SequenceManager(session_store)

    wire = Wire()
    ctx = ExecutionContext(
        session_id="session_123",
        run_id="run_456",
        wire=wire,
        sequence_manager=sequence_manager,
        workflow_id="wf_1",
        node_id="node_1",
        parent_run_id="parent_1",
    )

    # Execute and get result
    result = await executor.execute(messages, ctx)

    # Check RunOutput
    assert result.response == "Hello there!"
    assert result.metrics.total_tokens == 15
    assert result.metrics.steps_count == 1
    assert result.metrics.tool_calls_count == 0
    assert result.termination_reason is None  # Normal completion
    assert result.metrics.duration > 0

    # Close wire and read events
    await wire.close()
    events = []
    async for event in wire.read():
        events.append(event)

    delta_events = [e for e in events if e.type == StepEventType.STEP_DELTA]
    completed_events = [e for e in events if e.type == StepEventType.STEP_COMPLETED]

    assert len(delta_events) > 0  # Should have text deltas
    assert len(completed_events) == 1  # One assistant step completed

    # Check the completed step from wire
    assistant_step = completed_events[0].snapshot
    assert assistant_step.role == MessageRole.ASSISTANT
    assert assistant_step.content == "Hello there!"
    assert assistant_step.session_id == "session_123"
    assert assistant_step.run_id == "run_456"
    assert assistant_step.sequence == 1
    assert assistant_step.metrics is not None
    assert assistant_step.metrics.total_tokens == 15
    # Check metadata fields are set from ExecutionContext
    assert assistant_step.workflow_id == "wf_1"
    assert assistant_step.node_id == "node_1"
    assert assistant_step.parent_run_id == "parent_1"


@pytest.mark.asyncio
async def test_step_runner_end_to_end(mock_agent, session_store, session):
    """Test complete AgentRunner flow.

    Note: AgentRunner no longer emits RUN_STARTED/RUN_COMPLETED events.
    Run lifecycle events are handled by RunnableExecutor.
    AgentRunner only emits Step-level events.
    """
    events = await run_with_wire(
        mock_agent, session, "Hello", session_store=session_store
    )

    # Check event types - AgentRunner only emits Step events (not Run events)
    step_completed = [e for e in events if e.type == StepEventType.STEP_COMPLETED]
    step_delta = [e for e in events if e.type == StepEventType.STEP_DELTA]

    # AgentRunner should emit Step events
    assert len(step_completed) >= 1  # At least assistant step
    assert len(step_delta) >= 0  # May have delta events

    # Check steps were saved to session_store
    steps = await session_store.get_steps("session_123")

    # Should have user step + assistant step
    assert len(steps) >= 2

    # Check user step
    user_step = steps[0]
    assert user_step.role == MessageRole.USER
    assert user_step.content == "Hello"
    assert user_step.sequence == 1

    # Check assistant step
    assistant_step = steps[1]
    assert assistant_step.role == MessageRole.ASSISTANT
    assert assistant_step.content == "Hello there!"
    assert assistant_step.sequence == 2


@pytest.mark.asyncio
async def test_context_building_from_steps(mock_agent, session_store, session):
    """Test that context is correctly built from saved steps"""
    from agio.agent import build_context_from_steps

    # Run first conversation
    await run_with_wire(mock_agent, session, "Hello", session_store=session_store)

    # Build context
    messages = await build_context_from_steps(
        "session_123", session_store, system_prompt="You are helpful"
    )

    # Should have: system + user + assistant
    assert len(messages) >= 3
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are helpful"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Hello there!"


@pytest.mark.asyncio
async def test_retry_deletes_and_regenerates(mock_agent, session_store, session):
    """Test retry functionality"""
    # Run initial conversation
    await run_with_wire(mock_agent, session, "Hello", session_store=session_store)

    # Check we have steps
    steps_before = await session_store.get_steps("session_123")
    assert len(steps_before) >= 2

    # Retry from sequence 2 (delete assistant response)
    deleted = await session_store.delete_steps("session_123", start_seq=2)
    assert deleted >= 1

    # Check steps were deleted
    steps_after_delete = await session_store.get_steps("session_123")
    assert len(steps_after_delete) == 1  # Only user step remains
    assert steps_after_delete[0].role == MessageRole.USER
    
    # Test passed - delete_steps works correctly
    # Note: Resume functionality is now handled by unified ResumeExecutor
    # and is tested separately in dedicated Resume tests


@pytest.mark.asyncio
async def test_fork_creates_new_session(session_store):
    """Test fork functionality"""
    # Create some steps
    steps = [
        Step(
            session_id="original_session",
            run_id="run_1",
            sequence=1,
            role=MessageRole.USER,
            content="Step 1",
        ),
        Step(
            session_id="original_session",
            run_id="run_1",
            sequence=2,
            role=MessageRole.ASSISTANT,
            content="Response 1",
        ),
        Step(
            session_id="original_session",
            run_id="run_1",
            sequence=3,
            role=MessageRole.USER,
            content="Step 2",
        ),
    ]

    for step in steps:
        await session_store.save_step(step)

    # Fork at sequence 2
    new_session_id, last_sequence, _ = await fork_session(
        original_session_id="original_session",
        sequence=2,
        session_store=session_store,
        exclude_last=False
    )

    # Check new session has copied steps
    new_steps = await session_store.get_steps(new_session_id)
    assert len(new_steps) == 2  # Steps 1 and 2
    assert new_steps[0].content == "Step 1"
    assert new_steps[1].content == "Response 1"
    assert new_steps[0].session_id == new_session_id
    assert new_steps[1].session_id == new_session_id
    assert last_sequence == 2  # Last sequence number should be 2

    # Original session should be unchanged
    original_steps = await session_store.get_steps("original_session")
    assert len(original_steps) == 3


@pytest.mark.asyncio
async def test_step_metrics_tracking(mock_agent, session_store, session):
    """Test that metrics are properly tracked"""
    await run_with_wire(mock_agent, session, "Hello", session_store=session_store)

    # Get assistant step
    steps = await session_store.get_steps("session_123")
    assistant_step = next(s for s in steps if s.is_assistant_step())

    # Check metrics
    assert assistant_step.metrics is not None
    assert assistant_step.metrics.total_tokens == 15
    assert assistant_step.metrics.input_tokens == 10
    assert assistant_step.metrics.output_tokens == 5
    assert assistant_step.metrics.model_name == "mock-gpt"
    assert assistant_step.metrics.provider == "mock"
    assert assistant_step.metrics.duration_ms is not None
    assert assistant_step.metrics.duration_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
