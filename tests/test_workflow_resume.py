"""
Tests for Workflow resume functionality using WorkflowState idempotency.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from agio.domain import MessageRole, Step
from agio.runtime import RunOutput
from agio.domain.models import RunMetrics
from agio.providers.storage import InMemorySessionStore
from agio.runtime.protocol import ExecutionContext
from agio.runtime.wire import Wire
from agio.workflow.pipeline import PipelineWorkflow
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
            response=f"Response: {input}",
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
async def test_workflow_resume_skips_completed_nodes(mock_runnable, session_store, workflow_context):
    """Test that resuming a workflow skips already-completed nodes"""
    # Create existing output for node_1 (simulating previous execution)
    step = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",  # Must match workflow.id for idempotency
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Previous output",
        node_id="node_1",
    )
    await session_store.save_step(step)

    nodes = [
        WorkflowNode(
            id="node_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
        WorkflowNode(
            id="node_2",
            runnable=mock_runnable,
            input_template="Previous: {node_1.output}",
        ),
    ]

    workflow = PipelineWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    # Reset call count
    mock_runnable.run.reset_mock()

    # Resume workflow
    result = await workflow.run("Hello", context=workflow_context)

    # node_1 should be skipped (idempotency)
    # Only node_2 should execute
    assert mock_runnable.run.call_count == 1
    # node_2 should receive the previous output
    call_args = mock_runnable.run.call_args
    assert "Previous output" in call_args[0][0]  # input argument


@pytest.mark.asyncio
async def test_workflow_resume_all_nodes_completed(mock_runnable, session_store, workflow_context):
    """Test resuming when all nodes are already completed"""
    # Create outputs for both nodes
    step1 = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Output 1",
        node_id="node_1",
    )
    step2 = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Output 2",
        node_id="node_2",
    )
    await session_store.save_step(step1)
    await session_store.save_step(step2)

    nodes = [
        WorkflowNode(
            id="node_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
        WorkflowNode(
            id="node_2",
            runnable=mock_runnable,
            input_template="{node_1.output}",
        ),
    ]

    workflow = PipelineWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    mock_runnable.run.reset_mock()

    # Resume - both nodes should be skipped
    result = await workflow.run("Hello", context=workflow_context)

    # No nodes should execute
    assert mock_runnable.run.call_count == 0


@pytest.mark.asyncio
async def test_workflow_resume_partial_execution(mock_runnable, session_store, workflow_context):
    """Test resuming when only some nodes are completed"""
    # Only node_1 is completed
    step = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Node 1 output",
        node_id="node_1",
    )
    await session_store.save_step(step)

    nodes = [
        WorkflowNode(
            id="node_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
        WorkflowNode(
            id="node_2",
            runnable=mock_runnable,
            input_template="{node_1.output}",
        ),
        WorkflowNode(
            id="node_3",
            runnable=mock_runnable,
            input_template="{node_2.output}",
        ),
    ]

    workflow = PipelineWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    mock_runnable.run.reset_mock()

    # Resume - node_1 skipped, node_2 and node_3 execute
    result = await workflow.run("Hello", context=workflow_context)

    # node_2 and node_3 should execute
    assert mock_runnable.run.call_count == 2

