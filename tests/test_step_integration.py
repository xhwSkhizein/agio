"""
Integration test for Step-based execution flow.

Tests the complete flow:
1. StepRunner creates Steps
2. StepExecutor emits StepEvents
3. Steps are saved to repository
4. Context is built from Steps
5. Retry works correctly
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agio.storage.repository import InMemoryRepository
from agio.core import MessageRole, Step
from agio.execution.retry import retry_from_sequence
from agio.execution.step_executor import StepExecutor
from agio.components.models.base import StreamChunk
from agio.core import StepEventType
from agio.execution.runner import StepRunner, ExecutionConfig
from agio.core import AgentSession


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
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    model.arun_stream = mock_stream
    return model


@pytest.fixture
def mock_agent(mock_model):
    """Create a mock agent"""
    agent = MagicMock()
    agent.id = "agent_123"
    agent.model = mock_model
    agent.tools = []
    agent.system_prompt = "You are a helpful assistant"
    return agent


@pytest.fixture
def repository():
    """Create in-memory repository"""
    return InMemoryRepository()


@pytest.fixture
def session():
    """Create test session"""
    return AgentSession(session_id="session_123", user_id="user_456")


@pytest.mark.asyncio
async def test_step_executor_creates_steps(mock_model, repository):
    """Test that StepExecutor creates proper Steps"""
    executor = StepExecutor(model=mock_model, tools=[])

    messages = [{"role": "user", "content": "Hello"}]

    events = []
    async for event in executor.execute(
        session_id="session_123", run_id="run_456", messages=messages, start_sequence=1
    ):
        events.append(event)

    # Check we got delta and completed events
    delta_events = [e for e in events if e.type == StepEventType.STEP_DELTA]
    completed_events = [e for e in events if e.type == StepEventType.STEP_COMPLETED]

    assert len(delta_events) > 0  # Should have text deltas
    assert len(completed_events) == 1  # One assistant step completed

    # Check the completed step
    assistant_step = completed_events[0].snapshot
    assert assistant_step.role == MessageRole.ASSISTANT
    assert assistant_step.content == "Hello there!"
    assert assistant_step.session_id == "session_123"
    assert assistant_step.run_id == "run_456"
    assert assistant_step.sequence == 1
    assert assistant_step.metrics is not None
    assert assistant_step.metrics.total_tokens == 15


@pytest.mark.asyncio
async def test_step_runner_end_to_end(mock_agent, repository, session):
    """Test complete StepRunner flow"""
    runner = StepRunner(
        agent=mock_agent, config=ExecutionConfig(max_steps=5), repository=repository
    )

    events = []
    async for event in runner.run_stream(session, "Hello"):
        events.append(event)

    # Check event types
    run_started = [e for e in events if e.type == StepEventType.RUN_STARTED]
    run_completed = [e for e in events if e.type == StepEventType.RUN_COMPLETED]
    step_completed = [e for e in events if e.type == StepEventType.STEP_COMPLETED]

    assert len(run_started) == 1
    assert len(run_completed) == 1
    assert len(step_completed) >= 1  # At least assistant step

    # Check steps were saved to repository
    steps = await repository.get_steps("session_123")

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
async def test_context_building_from_steps(mock_agent, repository, session):
    """Test that context is correctly built from saved steps"""
    from agio.execution.context import build_context_from_steps

    runner = StepRunner(agent=mock_agent, repository=repository)

    # Run first conversation
    async for event in runner.run_stream(session, "Hello"):
        pass

    # Build context
    messages = await build_context_from_steps(
        "session_123", repository, system_prompt="You are helpful"
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
async def test_retry_deletes_and_regenerates(mock_agent, repository, session):
    """Test retry functionality"""
    runner = StepRunner(agent=mock_agent, repository=repository)

    # Run initial conversation
    async for event in runner.run_stream(session, "Hello"):
        pass

    # Check we have steps
    steps_before = await repository.get_steps("session_123")
    assert len(steps_before) >= 2

    # Retry from sequence 2 (delete assistant response)
    deleted = await repository.delete_steps("session_123", start_seq=2)
    assert deleted >= 1

    # Check steps were deleted
    steps_after_delete = await repository.get_steps("session_123")
    assert len(steps_after_delete) == 1  # Only user step remains
    assert steps_after_delete[0].role == MessageRole.USER

    # Resume from last step
    last_step = await repository.get_last_step("session_123")

    events = []
    async for event in runner.resume_from_user_step("session_123", last_step):
        events.append(event)

    # Check new steps were created
    steps_after_retry = await repository.get_steps("session_123")
    assert len(steps_after_retry) >= 2

    # New assistant response should be there
    new_assistant = steps_after_retry[1]
    assert new_assistant.role == MessageRole.ASSISTANT
    assert new_assistant.sequence == 2


@pytest.mark.asyncio
async def test_fork_creates_new_session(repository):
    """Test fork functionality"""
    from agio.execution.fork import fork_session

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
        await repository.save_step(step)

    # Fork at sequence 2
    new_session_id = await fork_session("original_session", 2, repository)

    # Check new session has copied steps
    new_steps = await repository.get_steps(new_session_id)
    assert len(new_steps) == 2  # Steps 1 and 2
    assert new_steps[0].content == "Step 1"
    assert new_steps[1].content == "Response 1"
    assert new_steps[0].session_id == new_session_id
    assert new_steps[1].session_id == new_session_id

    # Original session should be unchanged
    original_steps = await repository.get_steps("original_session")
    assert len(original_steps) == 3


@pytest.mark.asyncio
async def test_step_metrics_tracking(mock_agent, repository, session):
    """Test that metrics are properly tracked"""
    runner = StepRunner(agent=mock_agent, repository=repository)

    async for event in runner.run_stream(session, "Hello"):
        pass

    # Get assistant step
    steps = await repository.get_steps("session_123")
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
