"""
Tests for WorkflowState - in-memory cache for workflow node outputs.
"""

import pytest

from agio.domain import MessageRole, Step
from agio.storage.session import InMemorySessionStore
from agio.workflow.state import WorkflowState


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.mark.asyncio
async def test_workflow_state_basic_operations(session_store):
    """Test basic WorkflowState operations"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    # Initially empty
    assert state.get_output("node_a") is None
    assert not state.has_output("node_a")

    # Set output
    state.set_output("node_a", "Output A")
    assert state.get_output("node_a") == "Output A"
    assert state.has_output("node_a")


@pytest.mark.asyncio
async def test_workflow_state_load_from_history(session_store):
    """Test loading state from historical steps"""
    # Create steps with assistant outputs
    step1 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=1,
        role=MessageRole.USER,
        content="Query",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Response A",
        node_id="node_a",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=3,
        role=MessageRole.ASSISTANT,
        content="Response B",
        node_id="node_b",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Load state from history
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )
    await state.load_from_history()

    # Should have loaded outputs
    assert state.get_output("node_a") == "Response A"
    assert state.get_output("node_b") == "Response B"
    assert state.has_output("node_a")
    assert state.has_output("node_b")


@pytest.mark.asyncio
async def test_workflow_state_idempotency(session_store):
    """Test idempotency check using WorkflowState"""
    # Create existing output
    step = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Existing output",
        node_id="node_a",
    )
    await session_store.save_step(step)

    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )
    await state.load_from_history()

    # Should detect existing output
    assert state.has_output("node_a")
    assert state.get_output("node_a") == "Existing output"

    # New node should not exist
    assert not state.has_output("node_b")


@pytest.mark.asyncio
async def test_workflow_state_clear(session_store):
    """Test clearing WorkflowState"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    state.set_output("node_a", "Output A")
    state.set_output("node_b", "Output B")

    assert state.has_output("node_a")
    assert state.has_output("node_b")

    state.clear()

    assert not state.has_output("node_a")
    assert not state.has_output("node_b")


@pytest.mark.asyncio
async def test_workflow_state_to_dict(session_store):
    """Test converting state to dictionary"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    state.set_output("node_a", "Output A")
    state.set_output("node_b", "Output B")

    state_dict = state.to_dict()
    assert state_dict == {"node_a": "Output A", "node_b": "Output B"}


@pytest.mark.asyncio
async def test_workflow_state_only_last_assistant(session_store):
    """Test that only last assistant step is loaded for each node"""
    # Create multiple assistant steps for same node
    step1 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="First response",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Second response",
        node_id="node_a",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_789",
        workflow_id="workflow_456",
        sequence=3,
        role=MessageRole.ASSISTANT,
        content="Third response",
        node_id="node_a",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )
    await state.load_from_history()

    # Should only have the last one
    assert state.get_output("node_a") == "Third response"
