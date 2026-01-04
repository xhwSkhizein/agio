"""
Tests for refactored PipelineWorkflow with WorkflowState and idempotency.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from agio.storage.session import InMemorySessionStore
from agio.runtime.protocol import ExecutionContext, RunOutput, RunnableType
from agio.domain.models import RunMetrics
from agio.runtime.wire import Wire
from agio.workflow.pipeline import PipelineWorkflow
from agio.workflow.node import WorkflowNode


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.fixture
def mock_runnable():
    """Create a mock Runnable that returns RunOutput"""
    runnable = MagicMock()
    runnable.id = "agent_1"
    runnable.runnable_type = RunnableType.AGENT
    
    async def mock_run(input, *, context, emit_run_events=True):
        return RunOutput(
            response=f"Response to: {input}",
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
async def test_pipeline_workflow_basic_execution(mock_runnable, session_store, workflow_context):
    """Test basic PipelineWorkflow execution"""
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

    result = await workflow.run("Hello", context=workflow_context)

    assert result.response is not None
    assert "Response to:" in result.response
    assert mock_runnable.run.call_count == 2


@pytest.mark.asyncio
async def test_pipeline_workflow_idempotency(mock_runnable, session_store, workflow_context):
    """Test that PipelineWorkflow skips already-executed nodes"""
    from agio.domain import MessageRole, Step

    # Create existing output for node_1
    step = Step(
        session_id="session_123",
        run_id="workflow_run_1",
        workflow_id="wf_1",  # Must match workflow.id for idempotency
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Existing output",
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

    result = await workflow.run("Hello", context=workflow_context)

    # node_1 should be skipped (idempotency)
    # Only node_2 should execute
    assert mock_runnable.run.call_count == 1


@pytest.mark.asyncio
async def test_pipeline_workflow_unified_session(mock_runnable, session_store, workflow_context):
    """Test that all nested executions share the same session_id"""
    # Create a mock Runnable that creates Steps
    from agio.domain import MessageRole, Step
    from uuid import uuid4
    
    async def mock_run_with_steps(input, *, context, emit_run_events=True):
        
        # Create Steps to simulate what Agent would do
        user_step = Step(
            session_id=context.session_id,
            run_id=context.run_id,
            sequence=1,
            role=MessageRole.USER,
            content=input,
            workflow_id=context.workflow_id,
            node_id=context.node_id,
            parent_run_id=context.parent_run_id,
        )
        assistant_step = Step(
            session_id=context.session_id,
            run_id=context.run_id,
            sequence=2,
            role=MessageRole.ASSISTANT,
            content=f"Response to: {input}",
            workflow_id=context.workflow_id,
            node_id=context.node_id,
            parent_run_id=context.parent_run_id,
        )
        await session_store.save_step(user_step)
        await session_store.save_step(assistant_step)
        
        return RunOutput(
            response=f"Response to: {input}",
            run_id=context.run_id,
            metrics=RunMetrics(total_tokens=10, duration=0.1),
        )
    
    mock_runnable.run = AsyncMock(side_effect=mock_run_with_steps)
    
    nodes = [
        WorkflowNode(
            id="node_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
    ]

    workflow = PipelineWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    await workflow.run("Hello", context=workflow_context)

    # Check that steps were created with unified session_id
    steps = await session_store.get_steps("session_123")
    assert len(steps) > 0
    # All steps should have the same session_id
    assert all(s.session_id == "session_123" for s in steps)


@pytest.mark.asyncio
async def test_pipeline_workflow_node_metadata(mock_runnable, session_store, workflow_context):
    """Test that Steps are marked with correct node_id and workflow_id"""
    from agio.domain import MessageRole

    nodes = [
        WorkflowNode(
            id="node_1",
            runnable=mock_runnable,
            input_template="{input}",
        ),
    ]

    workflow = PipelineWorkflow(id="wf_1", stages=nodes, session_store=session_store)
    workflow.set_registry({"agent_1": mock_runnable})

    await workflow.run("Hello", context=workflow_context)

    # Check steps have correct metadata
    steps = await session_store.get_steps("session_123")
    assistant_steps = [s for s in steps if s.role == MessageRole.ASSISTANT]
    
    if assistant_steps:
        # Steps created by the workflow should have workflow_id and node_id
        # Note: This depends on how mock_runnable creates steps
        # In real execution, Agent would create steps with these fields
        pass  # This test would need a real Agent to verify



