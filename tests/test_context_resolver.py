"""
Tests for ContextResolver - template variable resolution.
"""

import pytest

from agio.domain import MessageRole, Step
from agio.storage.session import InMemorySessionStore
from agio.workflow.state import WorkflowState
from agio.workflow.resolver import ContextResolver


@pytest.fixture
def session_store():
    return InMemorySessionStore()


@pytest.mark.asyncio
async def test_resolve_simple_variables(session_store):
    """Test resolving simple variables like {input}"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    resolver = ContextResolver(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
        state=state,
    )
    resolver.set_input("User query")

    # Resolve simple variable
    result = await resolver.resolve_template("User said: {{ input }}")
    assert result == "User said: User query"


@pytest.mark.asyncio
async def test_resolve_node_output(session_store):
    """Test resolving node output variables"""
    # Create steps with node outputs
    step1 = Step(
        session_id="session_123",
        run_id="run_456",
        workflow_id="workflow_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Node A output",
        node_id="node_a",
    )
    step2 = Step(
        session_id="session_123",
        run_id="run_456",
        workflow_id="workflow_456",
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Node B output",
        node_id="node_b",
    )

    await session_store.save_step(step1)
    await session_store.save_step(step2)

    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )
    await state.load_from_history()

    resolver = ContextResolver(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
        state=state,
    )
    resolver.set_input("Original input")

    # Resolve node output
    result = await resolver.resolve_template(
        "Input: {{ input }}, Node A: {{ nodes.node_a.output }}, Node B: {{ nodes.node_b.output }}"
    )
    assert (
        result == "Input: Original input, Node A: Node A output, Node B: Node B output"
    )


@pytest.mark.asyncio
async def test_resolve_loop_variables(session_store):
    """Test resolving loop-related variables"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    resolver = ContextResolver(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
        state=state,
    )
    resolver.set_input("Query")
    resolver.set_loop_context(
        iteration=3,
        last_outputs={"node_a": "Last iteration output"},
    )

    # Resolve loop variables
    result = await resolver.resolve_template(
        "Iteration {{ loop.iteration }}, Last: {{ loop.last.node_a }}"
    )
    assert result == "Iteration 3, Last: Last iteration output"


@pytest.mark.asyncio
async def test_resolve_missing_node_output(session_store):
    """Test resolving missing node output (should return empty string)"""
    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    resolver = ContextResolver(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
        state=state,
    )
    resolver.set_input("Input")

    # Resolve non-existent node
    result = await resolver.resolve_template("Node output: {{ nodes.node_x.output }}")
    assert result == "Node output: "


@pytest.mark.asyncio
async def test_get_node_output_directly(session_store):
    """Test getting node output directly"""
    step = Step(
        session_id="session_123",
        run_id="run_456",
        workflow_id="workflow_456",
        sequence=1,
        role=MessageRole.ASSISTANT,
        content="Direct output",
        node_id="node_direct",
    )
    await session_store.save_step(step)

    state = WorkflowState(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
    )

    resolver = ContextResolver(
        session_id="session_123",
        workflow_id="workflow_456",
        store=session_store,
        state=state,
    )

    # Get output directly
    output = await resolver.get_node_output("node_direct")
    assert output == "Direct output"

    # Non-existent node
    output_none = await resolver.get_node_output("node_none")
    assert output_none is None
