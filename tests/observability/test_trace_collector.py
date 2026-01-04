"""
Tests for TraceCollector.
"""

import pytest
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.domain.models import Step, MessageRole, StepMetrics
from agio.observability.collector import TraceCollector
from agio.observability.trace import SpanKind, SpanStatus


@pytest.mark.asyncio
async def test_collector_builds_trace_from_events():
    """Test TraceCollector builds Trace from event stream"""
    run_id = str(uuid4())
    session_id = str(uuid4())

    events = [
        StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            data={"agent_id": "test_agent", "session_id": session_id},
        ),
        StepEvent(
            type=StepEventType.STEP_COMPLETED,
            run_id=run_id,
            step_id=str(uuid4()),
            snapshot=Step(
                id=str(uuid4()),
                session_id=session_id,
                run_id=run_id,
                sequence=1,
                role=MessageRole.ASSISTANT,
                content="Test response",
                metrics=StepMetrics(
                    model_name="gpt-4o",
                    provider="openai",
                    input_tokens=100,
                    output_tokens=200,
                    total_tokens=300,
                    duration_ms=1500,
                ),
            ),
        ),
        StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"response": "Test response"},
        ),
    ]

    collector = TraceCollector()
    collected = []

    async def event_gen():
        for e in events:
            yield e

    trace_id = str(uuid4())
    async for event in collector.wrap_stream(
        event_gen(),
        trace_id=trace_id,
        agent_id="test_agent",
        session_id=session_id,
        input_query="Test query",
    ):
        collected.append(event)
        assert event.trace_id == trace_id

    assert len(collected) == len(events)


@pytest.mark.asyncio
async def test_collector_creates_correct_span_types():
    """Test TraceCollector creates correct span types"""
    run_id = str(uuid4())

    events = [
        StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            data={"workflow_id": "test_workflow", "type": "pipeline"},
        ),
        StepEvent(
            type=StepEventType.NODE_STARTED,
            run_id=run_id,
            node_id="node1",
        ),
        StepEvent(
            type=StepEventType.NODE_COMPLETED,
            run_id=run_id,
            node_id="node1",
        ),
        StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"response": "Done"},
        ),
    ]

    # Mock store to capture trace
    class MockStore:
        def __init__(self):
            self.saved_trace = None

        async def save_trace(self, trace):
            self.saved_trace = trace

    store = MockStore()
    collector = TraceCollector(store=store)

    async def event_gen():
        for e in events:
            yield e

    async for _ in collector.wrap_stream(
        event_gen(),
        workflow_id="test_workflow",
        input_query="Test",
    ):
        pass

    # Verify trace was saved
    assert store.saved_trace is not None
    trace = store.saved_trace

    # Verify span types
    assert len(trace.spans) == 2
    assert trace.spans[0].kind == SpanKind.WORKFLOW
    assert trace.spans[1].kind == SpanKind.STAGE


@pytest.mark.asyncio
async def test_collector_handles_errors():
    """Test TraceCollector handles errors correctly"""
    run_id = str(uuid4())

    events = [
        StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            data={"agent_id": "test_agent"},
        ),
        StepEvent(
            type=StepEventType.RUN_FAILED,
            run_id=run_id,
            data={"error": "Test error"},
        ),
    ]

    class MockStore:
        def __init__(self):
            self.saved_trace = None

        async def save_trace(self, trace):
            self.saved_trace = trace

    store = MockStore()
    collector = TraceCollector(store=store)

    async def event_gen():
        for e in events:
            yield e

    async for _ in collector.wrap_stream(event_gen(), agent_id="test_agent"):
        pass

    # Verify error was captured
    assert store.saved_trace is not None
    trace = store.saved_trace
    assert len(trace.spans) == 1
    assert trace.spans[0].status == SpanStatus.ERROR
    assert trace.spans[0].error_message == "Test error"


@pytest.mark.asyncio
async def test_collector_tracks_llm_metrics():
    """Test TraceCollector tracks LLM call metrics"""
    run_id = str(uuid4())
    session_id = str(uuid4())

    events = [
        StepEvent(
            type=StepEventType.RUN_STARTED,
            run_id=run_id,
            data={"agent_id": "test_agent"},
        ),
        StepEvent(
            type=StepEventType.STEP_COMPLETED,
            run_id=run_id,
            step_id=str(uuid4()),
            snapshot=Step(
                id=str(uuid4()),
                session_id=session_id,
                run_id=run_id,
                sequence=1,
                role=MessageRole.ASSISTANT,
                content="Response",
                metrics=StepMetrics(
                    model_name="gpt-4o",
                    input_tokens=150,
                    output_tokens=250,
                    total_tokens=400,
                    duration_ms=2000,
                ),
            ),
        ),
        StepEvent(
            type=StepEventType.RUN_COMPLETED,
            run_id=run_id,
            data={"response": "Response"},
        ),
    ]

    class MockStore:
        def __init__(self):
            self.saved_trace = None

        async def save_trace(self, trace):
            self.saved_trace = trace

    store = MockStore()
    collector = TraceCollector(store=store)

    async def event_gen():
        for e in events:
            yield e

    async for _ in collector.wrap_stream(event_gen(), agent_id="test_agent"):
        pass

    # Verify metrics
    trace = store.saved_trace
    assert trace.total_tokens == 400
    assert trace.total_llm_calls == 1

    # Verify LLM span metrics
    llm_span = next(s for s in trace.spans if s.kind == SpanKind.LLM_CALL)
    assert llm_span.metrics["tokens.total"] == 400
    assert llm_span.metrics["tokens.input"] == 150
    assert llm_span.metrics["tokens.output"] == 250
    assert llm_span.duration_ms == 2000
