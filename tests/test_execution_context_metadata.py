"""
Tests for ExecutionContext metadata propagation to Steps.
"""

import pytest

from agio.domain import MessageRole, Step
from agio.runtime.protocol import ExecutionContext
from agio.runtime.wire import Wire


@pytest.mark.asyncio
async def test_execution_context_metadata_propagation():
    """Test that ExecutionContext metadata is correctly propagated to Steps"""
    wire = Wire()
    ctx = ExecutionContext(
        session_id="session_123",
        run_id="run_456",
        wire=wire,
        workflow_id="wf_1",
        node_id="node_1",
        parent_run_id="parent_1",
        metadata={"branch_key": "branch_1"},
    )

    # Create a Step with metadata from context
    step = Step(
        session_id=ctx.session_id,
        run_id=ctx.run_id,
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Test",
        workflow_id=ctx.workflow_id,
        node_id=ctx.node_id,
        parent_run_id=ctx.parent_run_id,
        branch_key=ctx.metadata.get("branch_key"),
    )

    assert step.workflow_id == "wf_1"
    assert step.node_id == "node_1"
    assert step.parent_run_id == "parent_1"
    assert step.branch_key == "branch_1"


@pytest.mark.asyncio
async def test_execution_context_child_preserves_metadata():
    """Test that child ExecutionContext preserves parent metadata"""
    wire = Wire()
    parent_ctx = ExecutionContext(
        session_id="session_123",
        run_id="parent_run",
        wire=wire,
        workflow_id="wf_1",
        metadata={"key": "value"},
    )

    child_ctx = parent_ctx.child(
        run_id="child_run",
        node_id="node_1",
    )

    assert child_ctx.session_id == "session_123"  # Unified session
    assert child_ctx.run_id == "child_run"
    assert child_ctx.workflow_id == "wf_1"  # Inherited
    assert child_ctx.parent_run_id == "parent_run"
    assert child_ctx.node_id == "node_1"
    assert child_ctx.metadata == {"key": "value"}  # Inherited


@pytest.mark.asyncio
async def test_execution_context_unified_session():
    """Test that child contexts use unified session_id"""
    wire = Wire()
    parent_ctx = ExecutionContext(
        session_id="session_123",
        run_id="parent_run",
        wire=wire,
    )

    # Create child without specifying session_id
    child_ctx = parent_ctx.child(run_id="child_run")

    # Should use parent's session_id (unified session)
    assert child_ctx.session_id == "session_123"
    assert child_ctx.run_id == "child_run"
    assert child_ctx.parent_run_id == "parent_run"
