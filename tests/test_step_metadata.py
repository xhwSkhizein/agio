"""
Tests for Step model metadata fields (node_id, parent_run_id, branch_key).
"""

import pytest

from agio.domain import MessageRole, Step
from agio.storage.session import InMemorySessionStore


@pytest.mark.asyncio
async def test_step_with_node_id():
    """Test Step with node_id field"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.USER,
        content="Hello",
        node_id="node_abc",
    )

    assert step.node_id == "node_abc"
    assert step.workflow_id is None
    assert step.parent_run_id is None


@pytest.mark.asyncio
async def test_step_with_workflow_metadata():
    """Test Step with workflow-related metadata"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Response",
        workflow_id="workflow_123",
        node_id="node_abc",
        parent_run_id="parent_run_789",
    )

    assert step.workflow_id == "workflow_123"
    assert step.node_id == "node_abc"
    assert step.parent_run_id == "parent_run_789"


@pytest.mark.asyncio
async def test_step_with_branch_key():
    """Test Step with branch_key for parallel execution"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Branch output",
        node_id="node_abc",
        branch_key="branch_node_abc",
    )

    assert step.branch_key == "branch_node_abc"
    assert step.node_id == "node_abc"


@pytest.mark.asyncio
async def test_step_metadata_persistence():
    """Test that Step metadata is persisted correctly"""
    store = InMemorySessionStore()

    step = Step(
        session_id="session_123",
        run_id="run_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Test",
        workflow_id="wf_1",
        node_id="node_1",
        parent_run_id="parent_1",
        branch_key="branch_1",
    )

    await store.save_step(step)

    # Retrieve and verify
    steps = await store.get_steps("session_123")
    assert len(steps) == 1
    retrieved = steps[0]

    assert retrieved.workflow_id == "wf_1"
    assert retrieved.node_id == "node_1"
    assert retrieved.parent_run_id == "parent_1"
    assert retrieved.branch_key == "branch_1"



