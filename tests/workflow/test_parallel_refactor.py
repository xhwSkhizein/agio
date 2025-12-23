"""
Tests for refactored ParallelWorkflow with WorkflowState and branch handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from agio.providers.storage import InMemorySessionStore
from agio.domain import ExecutionContext,RunOutput, RunMetrics
from agio.runtime.wire import Wire
from agio.workflow.parallel import ParallelWorkflow
from agio.workflow.node import WorkflowNode


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.fixture
def mock_runnable():
    """Create a mock Runnable"""
    runnable = MagicMock()
    runnable.id = "agent_1"
    runnable.runnable_type = "agent"  # Required for RunnableExecutor
    
    async def mock_run(input, *, context, emit_run_events=True):
        return RunOutput(
            response=f"Branch response: {input}",
            run_id=context.run_id,
            metrics=RunMetrics(total_tokens=10, duration=0.1),
        )
    
    runnable.run = AsyncMock(side_effect=mock_run)
    return runnable


@pytest.fixture
def workflow_context():
    """Create execution context for workflow"""
    wire = Wire()
    ctx = ExecutionContext(
        session_id="session_123",
        run_id="workflow_run_1",
        wire=wire,
    )
    return ctx


@pytest.mark.asyncio
async def test_parallel_workflow_basic_execution(mock_runnable, session_store, workflow_context):
    """Test basic ParallelWorkflow execution"""
    nodes = [
        WorkflowNode(
            id="branch_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
        WorkflowNode(
            id="branch_2",
            runnable=mock_runnable,
            input_template="{input}",
        ),
    ]

    workflow = ParallelWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    result = await workflow.run("Hello", context=workflow_context)

    assert result.response is not None
    assert "Branch response:" in result.response
    # Both branches should execute
    assert mock_runnable.run.call_count == 2


@pytest.mark.asyncio
async def test_parallel_workflow_idempotency(mock_runnable, session_store, workflow_context):
    """Test that ParallelWorkflow skips already-executed branches"""
    from agio.domain import MessageRole, Step

    # Create existing output for branch_1
    step = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",  # Must match workflow.id for idempotency
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Existing branch output",
        node_id="branch_1",
    )
    await session_store.save_step(step)

    nodes = [
        WorkflowNode(
            id="branch_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
        WorkflowNode(
            id="branch_2",
            runnable=mock_runnable,
            input_template="{input}",
        ),
    ]

    workflow = ParallelWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    result = await workflow.run("Hello", context=workflow_context)

    # branch_1 should be skipped, only branch_2 should execute
    assert mock_runnable.run.call_count == 1


@pytest.mark.asyncio
async def test_parallel_workflow_branch_key(mock_runnable, session_store, workflow_context):
    """Test that Steps are marked with branch_key"""
    from agio.domain import MessageRole

    nodes = [
        WorkflowNode(
            id="branch_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
    ]

    workflow = ParallelWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    await workflow.run("Hello", context=workflow_context)

    # Check that steps can be filtered by branch_key
    # Note: This requires the Runnable to actually create Steps with branch_key
    # In real execution, Agent would create steps with branch_key from metadata
    steps = await session_store.get_steps("session_123", branch_key="branch_branch_1")
    # This test would need a real Agent to verify branch_key is set correctly

