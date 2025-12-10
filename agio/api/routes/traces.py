"""
Trace API routes for observability.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from agio.observability.trace import Trace, Span, SpanKind, SpanStatus
from agio.observability.trace_store import get_trace_store, TraceQuery

router = APIRouter(prefix="/traces", tags=["Observability"])


# === Response Models ===


class TraceSummary(BaseModel):
    """Trace summary for list display"""

    trace_id: str
    workflow_id: str | None
    agent_id: str | None
    session_id: str | None
    start_time: datetime
    duration_ms: float | None
    status: str
    total_tokens: int
    total_llm_calls: int
    total_tool_calls: int
    max_depth: int
    input_preview: str | None
    output_preview: str | None


class SpanSummary(BaseModel):
    """Span summary"""

    span_id: str
    parent_span_id: str | None
    kind: str
    name: str
    depth: int
    start_time: datetime
    duration_ms: float | None
    status: str
    error_message: str | None
    attributes: dict[str, Any]
    metrics: dict[str, Any]


class TraceDetail(BaseModel):
    """Trace detail with full information"""

    trace_id: str
    workflow_id: str | None
    agent_id: str | None
    session_id: str | None
    user_id: str | None
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    status: str
    spans: list[SpanSummary]
    total_tokens: int
    total_llm_calls: int
    total_tool_calls: int
    max_depth: int
    input_query: str | None
    final_output: str | None


class WaterfallSpan(BaseModel):
    """Waterfall chart span data"""

    span_id: str
    parent_span_id: str | None
    kind: str
    name: str
    depth: int

    # Relative time (relative to trace start)
    start_offset_ms: float
    duration_ms: float

    status: str
    error_message: str | None

    # Display info
    label: str
    sublabel: str | None
    tokens: int | None


class WaterfallData(BaseModel):
    """Waterfall chart complete data"""

    trace_id: str
    total_duration_ms: float
    spans: list[WaterfallSpan]

    # Aggregated metrics
    metrics: dict[str, Any]


# === API Endpoints ===


@router.get("/", response_model=list[TraceSummary])
async def list_traces(
    workflow_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Query trace list.

    Returns:
        Trace summary list (without full span details)
    """
    store = get_trace_store()
    query = TraceQuery(
        workflow_id=workflow_id,
        agent_id=agent_id,
        session_id=session_id,
        status=SpanStatus(status) if status else None,
        start_time=start_time,
        end_time=end_time,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        limit=limit,
        offset=offset,
    )
    traces = await store.query_traces(query)
    return [_to_summary(t) for t in traces]


@router.get("/{trace_id}", response_model=TraceDetail)
async def get_trace(trace_id: str):
    """
    Get single trace detail.

    Returns:
        Complete trace (with all spans)
    """
    store = get_trace_store()
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _to_detail(trace)


@router.get("/{trace_id}/waterfall", response_model=WaterfallData)
async def get_trace_waterfall(trace_id: str):
    """
    Get trace waterfall chart data.

    Returns optimized format for frontend rendering.
    """
    store = get_trace_store()
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _build_waterfall(trace)


@router.get("/stream")
async def stream_traces():
    """SSE real-time push for new traces"""
    store = get_trace_store()
    queue = store.subscribe()

    async def event_generator():
        try:
            while True:
                trace = await queue.get()
                yield {
                    "event": "trace",
                    "data": _to_summary(trace).model_dump_json(),
                }
        finally:
            store.unsubscribe(queue)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Connection": "close",
            "X-Accel-Buffering": "no",
        },
    )


# === Helper Functions ===


def _to_summary(trace: Trace) -> TraceSummary:
    """Convert Trace to TraceSummary"""
    return TraceSummary(
        trace_id=trace.trace_id,
        workflow_id=trace.workflow_id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        start_time=trace.start_time,
        duration_ms=trace.duration_ms,
        status=trace.status.value,
        total_tokens=trace.total_tokens,
        total_llm_calls=trace.total_llm_calls,
        total_tool_calls=trace.total_tool_calls,
        max_depth=trace.max_depth,
        input_preview=trace.input_query[:200] if trace.input_query else None,
        output_preview=trace.final_output[:200] if trace.final_output else None,
    )


def _to_detail(trace: Trace) -> TraceDetail:
    """Convert Trace to TraceDetail"""
    return TraceDetail(
        trace_id=trace.trace_id,
        workflow_id=trace.workflow_id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        user_id=trace.user_id,
        start_time=trace.start_time,
        end_time=trace.end_time,
        duration_ms=trace.duration_ms,
        status=trace.status.value,
        spans=[_span_to_summary(s) for s in trace.spans],
        total_tokens=trace.total_tokens,
        total_llm_calls=trace.total_llm_calls,
        total_tool_calls=trace.total_tool_calls,
        max_depth=trace.max_depth,
        input_query=trace.input_query,
        final_output=trace.final_output,
    )


def _span_to_summary(span: Span) -> SpanSummary:
    """Convert Span to SpanSummary"""
    return SpanSummary(
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        kind=span.kind.value,
        name=span.name,
        depth=span.depth,
        start_time=span.start_time,
        duration_ms=span.duration_ms,
        status=span.status.value,
        error_message=span.error_message,
        attributes=span.attributes,
        metrics=span.metrics,
    )


def _build_waterfall(trace: Trace) -> WaterfallData:
    """Build waterfall chart data"""
    trace_start = trace.start_time
    spans = []

    for span in trace.spans:
        # Calculate relative offset
        offset = (span.start_time - trace_start).total_seconds() * 1000

        # Build label
        label = span.name
        sublabel = None
        tokens = None

        if span.kind == SpanKind.LLM_CALL:
            tokens = span.metrics.get("tokens.total")
            sublabel = f"{tokens} tokens" if tokens else None
        elif span.kind == SpanKind.TOOL_CALL:
            sublabel = f"{span.duration_ms:.0f}ms" if span.duration_ms else None

        spans.append(
            WaterfallSpan(
                span_id=span.span_id,
                parent_span_id=span.parent_span_id,
                kind=span.kind.value,
                name=span.name,
                depth=span.depth,
                start_offset_ms=offset,
                duration_ms=span.duration_ms or 0,
                status=span.status.value,
                error_message=span.error_message,
                label=label,
                sublabel=sublabel,
                tokens=tokens,
            )
        )

    return WaterfallData(
        trace_id=trace.trace_id,
        total_duration_ms=trace.duration_ms or 0,
        spans=spans,
        metrics={
            "total_tokens": trace.total_tokens,
            "total_llm_calls": trace.total_llm_calls,
            "total_tool_calls": trace.total_tool_calls,
            "max_depth": trace.max_depth,
        },
    )
