"""
Tests for SessionStore filtering capabilities (run_id, workflow_id, node_id, branch_key).
"""

import pytest

from agio.domain import MessageRole, Step
from agio.providers.storage import InMemorySessionStore


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.mark.asyncio
async def test_filter_by_run_id(session_store):
    """Test filtering steps by run_id"""
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

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by run_id
    steps_run1 = await session_store.get_steps("session_123", run_id="run_1")
    assert len(steps_run1) == 2
    assert all(s.run_id == "run_1" for s in steps_run1)

    steps_run2 = await session_store.get_steps("session_123", run_id="run_2")
    assert len(steps_run2) == 1
    assert steps_run2[0].run_id == "run_2"


@pytest.mark.asyncio
async def test_filter_by_workflow_id(session_store):
    """Test filtering steps by workflow_id"""
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
    steps_wf1 = await session_store.get_steps("session_123", workflow_id="wf_1")
    assert len(steps_wf1) == 2
    assert all(s.workflow_id == "wf_1" for s in steps_wf1)


@pytest.mark.asyncio
async def test_filter_by_node_id(session_store):
    """Test filtering steps by node_id"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.USER,
        content="Step 1",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Response 1",
        node_id="node_a",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=3,
        role=MessageRole.USER,
        content="Step 2",
        node_id="node_b",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by node_id
    steps_node_a = await session_store.get_steps("session_123", node_id="node_a")
    assert len(steps_node_a) == 2
    assert all(s.node_id == "node_a" for s in steps_node_a)


@pytest.mark.asyncio
async def test_filter_by_branch_key(session_store):
    """Test filtering steps by branch_key"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Branch A",
        branch_key="branch_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Branch B",
        branch_key="branch_b",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=3,
        role=MessageRole.ASSISTANT,
        content="No branch",
        branch_key=None,
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by branch_key
    steps_branch_a = await session_store.get_steps("session_123", branch_key="branch_a")
    assert len(steps_branch_a) == 1
    assert steps_branch_a[0].branch_key == "branch_a"


@pytest.mark.asyncio
async def test_filter_combination(session_store):
    """Test combining multiple filters"""
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Step 1",
        workflow_id="wf_1",
        node_id="node_a",
        branch_key="branch_1",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Step 2",
        workflow_id="wf_1",
        node_id="node_a",
        branch_key="branch_2",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_1",
        sequence=3,
        role=MessageRole.ASSISTANT,
        content="Step 3",
        workflow_id="wf_1",
        node_id="node_b",
        branch_key="branch_1",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Filter by workflow_id + node_id + branch_key
    steps = await session_store.get_steps(
        "session_123",
        workflow_id="wf_1",
        node_id="node_a",
        branch_key="branch_1",
    )
    assert len(steps) == 1
    assert steps[0].content == "Step 1"


@pytest.mark.asyncio
async def test_get_last_assistant_content(session_store):
    """Test get_last_assistant_content helper method"""
    # Create steps for a node
    step1 = Step(
        session_id="session_123",
        run_id="run_1",
        workflow_id="workflow_1",
        sequence=1,
        role=MessageRole.USER,
        content="Query",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_1",
        workflow_id="workflow_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="First response",
        node_id="node_a",
    )
    step3 = Step(
        session_id="session_123",
        run_id="run_1",
        workflow_id="workflow_1",
        sequence=3,
        role=MessageRole.ASSISTANT,
        content="Second response",
        node_id="node_a",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)
    await session_store.save_step(step3)

    # Get last assistant content for node_a (uses workflow_id for isolation)
    content = await session_store.get_last_assistant_content("session_123", "node_a", workflow_id="workflow_1")
    assert content == "Second response"

    # Test with non-existent node
    content_none = await session_store.get_last_assistant_content("session_123", "node_none", workflow_id="workflow_1")
    assert content_none is None

