"""
Tests for build_context_from_steps filtering capabilities.
"""

import pytest

from agio.domain import MessageRole, Step
from agio.providers.storage import InMemorySessionStore
from agio.runtime.context import build_context_from_steps


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.mark.asyncio
async def test_filter_by_run_id(session_store):
    """Test filtering context by run_id"""
    # Create steps with different run_ids
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Query 1",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Response 1",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_2",
        sequence=3,
        role=MessageRole.USER,
        content="Query 2",
    )
    step4 = Step(
        session_id="session_123",
        run_id="run_2",
        sequence=4,
        role=MessageRole.ASSISTANT,
        content="Response 2",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)
    await session_store.save_step(step4)

    # Build context filtered by run_id
    messages_run1 = await build_context_from_steps(
        "session_123", session_store, run_id="run_1"
    )
    assert len(messages_run1) == 2
    assert messages_run1[0]["content"] == "Query 1"
    assert messages_run1[1]["content"] == "Response 1"

    messages_run2 = await build_context_from_steps(
        "session_123", session_store, run_id="run_2"
    )
    assert len(messages_run2) == 2
    assert messages_run2[0]["content"] == "Query 2"
    assert messages_run2[1]["content"] == "Response 2"


@pytest.mark.asyncio
async def test_filter_by_workflow_id(session_store):
    """Test filtering context by workflow_id"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Step 1",
        workflow_id="wf_1",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_2",
        sequence=2,
        role=MessageRole.USER,
        content="Step 2",
        workflow_id="wf_2",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_3",
        sequence=3,
        role=MessageRole.USER,
        content="Step 3",
        workflow_id="wf_1",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by workflow_id
    messages_wf1 = await build_context_from_steps(
        "session_123", session_store, workflow_id="wf_1"
    )
    assert len(messages_wf1) == 2
    assert all(msg["content"] in ["Step 1", "Step 3"] for msg in messages_wf1)


@pytest.mark.asyncio
async def test_filter_by_node_id(session_store):
    """Test filtering context by node_id"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Node A step",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Node A response",
        node_id="node_a",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=3,
        role=MessageRole.USER,
        content="Node B step",
        node_id="node_b",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by node_id
    messages_node_a = await build_context_from_steps(
        "session_123", session_store, node_id="node_a"
    )
    assert len(messages_node_a) == 2
    assert messages_node_a[0]["content"] == "Node A step"
    assert messages_node_a[1]["content"] == "Node A response"


@pytest.mark.asyncio
async def test_backward_compatibility_no_filter(session_store):
    """Test that default behavior (no filter) still works"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Step 1",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_2",
        sequence=2,
        role=MessageRole.USER,
        content="Step 2",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)

    # No filter - should get all steps
    messages = await build_context_from_steps("session_123", session_store)
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_filter_with_system_prompt(session_store):
    """Test filtering with system prompt"""
    step = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Query",
    )
    await session_store.save_step(step)

    messages = await build_context_from_steps(
        "session_123",
        session_store,
        system_prompt="You are helpful",
        run_id="run_1",
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are helpful"
    assert messages[1]["role"] == "user"

