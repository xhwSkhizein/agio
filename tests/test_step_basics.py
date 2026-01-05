"""
Basic tests for Step model and session_store operations.
"""

import pytest

from agio.storage.session import InMemorySessionStore
from agio.domain import MessageRole, Step, StepAdapter, StepMetrics


@pytest.mark.asyncio
async def test_step_creation():
    """Test creating a Step"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.USER,
        content="Hello, world!",
    )

    assert step.session_id == "session_123"
    assert step.run_id == "run_456"
    assert step.sequence == 1
    assert step.role == MessageRole.USER
    assert step.content == "Hello, world!"
    assert step.id is not None  # Auto-generated


@pytest.mark.asyncio
async def test_step_to_message_dict():
    """Test converting Step to LLM message format using StepAdapter"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.USER,
        content="Hello",
    )

    msg = StepAdapter.to_llm_message(step)

    assert msg == {"role": "user", "content": "Hello"}
    # Metadata should not be included
    assert "session_id" not in msg
    assert "sequence" not in msg
    assert "metrics" not in msg


@pytest.mark.asyncio
async def test_assistant_step_with_tool_calls():
    """Test assistant step with tool calls"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Let me search for that",
        tool_calls=[
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "search", "arguments": '{"query": "Python"}'},
            }
        ],
    )

    assert step.has_tool_calls()

    msg = StepAdapter.to_llm_message(step)
    assert msg["role"] == "assistant"
    assert msg["content"] == "Let me search for that"
    assert len(msg["tool_calls"]) == 1
    assert msg["tool_calls"][0]["id"] == "call_123"


@pytest.mark.asyncio
async def test_tool_step():
    """Test tool result step"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=3,
        role=MessageRole.TOOL,
        content="Search results: ...",
        tool_call_id="call_123",
        name="search",
    )

    assert step.is_tool_step()

    msg = StepAdapter.to_llm_message(step)
    assert msg["role"] == "tool"
    assert msg["content"] == "Search results: ..."
    assert msg["tool_call_id"] == "call_123"
    assert msg["name"] == "search"


@pytest.mark.asyncio
async def test_session_store_save_and_get():
    """Test saving and retrieving steps"""
    store = InMemorySessionStore()

    step1 = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.USER,
        content="Hello",
    )

    step2 = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Hi there!",
    )

    await store.save_step(step1)
    await store.save_step(step2)

    # Get all steps
    steps = await store.get_steps("session_123")
    assert len(steps) == 2
    assert steps[0].sequence == 1
    assert steps[1].sequence == 2


@pytest.mark.asyncio
async def test_session_store_get_steps_with_range():
    """Test getting steps with sequence range"""
    store = InMemorySessionStore()

    # Create 5 steps
    for i in range(1, 6):
        step = Step(
            session_id="session_123",
            run_id="run_456",
            sequence=i,
            role=MessageRole.USER,
            content=f"Message {i}",
        )
        await store.save_step(step)

    # Get steps 2-4
    steps = await store.get_steps("session_123", start_seq=2, end_seq=4)
    assert len(steps) == 3
    assert steps[0].sequence == 2
    assert steps[2].sequence == 4


@pytest.mark.asyncio
async def test_session_store_delete_steps():
    """Test deleting steps from a sequence"""
    store = InMemorySessionStore()

    # Create 5 steps
    for i in range(1, 6):
        step = Step(
            session_id="session_123",
            run_id="run_456",
            sequence=i,
            role=MessageRole.USER,
            content=f"Message {i}",
        )
        await store.save_step(step)

    # Delete from sequence 3
    deleted = await store.delete_steps("session_123", start_seq=3)
    assert deleted == 3  # Deleted steps 3, 4, 5

    # Verify remaining steps
    steps = await store.get_steps("session_123")
    assert len(steps) == 2
    assert steps[0].sequence == 1
    assert steps[1].sequence == 2


@pytest.mark.asyncio
async def test_session_store_get_last_step():
    """Test getting the last step"""
    store = InMemorySessionStore()

    step1 = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.USER,
        content="First",
    )

    step2 = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Second",
    )

    await store.save_step(step1)
    await store.save_step(step2)

    last = await store.get_last_step("session_123")
    assert last is not None
    assert last.sequence == 2
    assert last.content == "Second"


@pytest.mark.asyncio
async def test_step_metrics():
    """Test Step with metrics"""
    metrics = StepMetrics(
        duration_ms=150.5,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model_name="gpt-4",
        provider="openai",
        first_token_latency_ms=25.3,
    )

    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Response",
        metrics=metrics,
    )

    assert step.metrics.total_tokens == 150
    assert step.metrics.model_name == "gpt-4"
    assert step.metrics.first_token_latency_ms == 25.3


@pytest.mark.asyncio
async def test_context_building():
    """Test building context from steps"""
    from agio.agent import build_context_from_steps

    store = InMemorySessionStore()

    # Create conversation
    steps = [
        Step(
            session_id="session_123",
            run_id="run_456",
            sequence=1,
            role=MessageRole.USER,
            content="What is Python?",
        ),
        Step(
            session_id="session_123",
            run_id="run_456",
            sequence=2,
            role=MessageRole.ASSISTANT,
            content="Python is a programming language.",
        ),
        Step(
            session_id="session_123",
            run_id="run_456",
            sequence=3,
            role=MessageRole.USER,
            content="Tell me more",
        ),
    ]

    for step in steps:
        await store.save_step(step)

    # Build context
    messages = await build_context_from_steps("session_123", store)

    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is Python?"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"

    # With system prompt
    messages_with_system = await build_context_from_steps(
        "session_123", store, system_prompt="You are a helpful assistant"
    )

    assert len(messages_with_system) == 4
    assert messages_with_system[0]["role"] == "system"
    assert messages_with_system[0]["content"] == "You are a helpful assistant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
