"""
Trace API routes for observability.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agio.api.deps import get_trace_store
from agio.observability.trace import Span, SpanKind, SpanStatus, Trace
from agio.storage.trace.store import TraceQuery

router = APIRouter(prefix="/traces", tags=["Observability"])


# === Response Models ===


class TraceSummary(BaseModel):
    """Trace summary for list display"""

    trace_id: str
    agent_id: str | None
    session_id: str | None
    start_time: datetime
    duration_ms: float | None
    status: str
    total_tokens: int
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
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
    llm_details: dict[str, Any] | None = (
        None  # Complete LLM call details (for LLM_CALL spans)
    )
    tool_details: dict[str, Any] | None = (
        None  # Complete tool call details (for TOOL_CALL spans)
    )


class TraceDetail(BaseModel):
    """Trace detail with full information"""

    trace_id: str
    agent_id: str | None
    session_id: str | None
    user_id: str | None
    start_time: datetime
    end_time: datetime | None
    duration_ms: float | None
    status: str
    spans: list[SpanSummary]
    total_tokens: int
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
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
    metrics: dict[str, Any] | None = None
    llm_details: dict[str, Any] | None = (
        None  # Complete LLM call details (for LLM_CALL spans)
    )
    tool_details: dict[str, Any] | None = (
        None  # Complete tool call details (for TOOL_CALL spans)
    )


class WaterfallData(BaseModel):
    """Waterfall chart complete data"""

    trace_id: str
    total_duration_ms: float
    spans: list[WaterfallSpan]

    # Aggregated metrics
    metrics: dict[str, Any]


class LLMCallSummary(BaseModel):
    """LLM call summary extracted from Trace spans"""

    span_id: str
    trace_id: str
    agent_id: str | None
    session_id: str | None
    run_id: str | None
    start_time: datetime
    duration_ms: float | None
    model_name: str | None
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    llm_details: dict[str, Any] | None = None


# === API Endpoints ===


@router.get("/", response_model=list[TraceSummary])
async def list_traces(
    request: Request,
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
    store = get_trace_store(request)
    if not store:
        return []
    query = TraceQuery(
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
async def get_trace(
    trace_id: str,
    request: Request,
):
    """
    Get single trace detail.

    Returns:
        Complete trace (with all spans)
    """
    store = get_trace_store(request)
    if not store:
        raise HTTPException(status_code=404, detail="Trace store not configured")
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _to_detail(trace)


@router.get("/{trace_id}/waterfall", response_model=WaterfallData)
async def get_trace_waterfall(
    trace_id: str,
    request: Request,
):
    """
    Get trace waterfall chart data.

    Returns optimized format for frontend rendering.
    """
    store = get_trace_store(request)
    if not store:
        raise HTTPException(status_code=404, detail="Trace store not configured")
    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return _build_waterfall(trace)


@router.get("/stream")
async def stream_traces(
    request: Request,
):
    """SSE real-time push for new traces"""
    store = get_trace_store(request)
    if not store:
        raise HTTPException(status_code=404, detail="Trace store not configured")
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


@router.get("/spans/llm-calls", response_model=list[LLMCallSummary])
async def list_llm_calls(
    request: Request,
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    session_id: str | None = Query(None, description="Filter by session ID"),
    run_id: str | None = Query(None, description="Filter by run ID"),
    model_id: str | None = Query(None, description="Filter by model ID"),
    provider: str | None = Query(None, description="Filter by provider"),
    start_time: datetime | None = Query(None, description="Start time filter"),
    end_time: datetime | None = Query(None, description="End time filter"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Query LLM calls from all traces.

    Returns:
        List of LLM call summaries extracted from Trace spans
    """
    store = get_trace_store(request)
    if not store:
        return []

    # Query traces with filters
    query = TraceQuery(
        agent_id=agent_id,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        limit=500,  # Get more traces to extract LLM calls from
        offset=0,
    )
    traces = await store.query_traces(query)

    # Extract LLM_CALL spans
    llm_calls = []
    for trace in traces:
        for span in trace.spans:
            if span.kind == SpanKind.LLM_CALL:
                # Apply additional filters
                if run_id and span.run_id != run_id:
                    continue
                if model_id and span.attributes.get("model_name") != model_id:
                    continue
                if provider and span.metrics.get("provider") != provider:
                    continue

                llm_calls.append(_span_to_llm_call(span, trace))

    # Apply pagination
    start = offset
    end = start + limit
    return llm_calls[start:end]


# === Helper Functions ===


def _to_summary(trace: Trace) -> TraceSummary:
    """Convert Trace to TraceSummary"""
    return TraceSummary(
        trace_id=trace.trace_id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        start_time=trace.start_time,
        duration_ms=trace.duration_ms,
        status=trace.status.value,
        total_tokens=trace.total_tokens,
        total_cache_read_tokens=trace.total_cache_read_tokens,
        total_cache_creation_tokens=trace.total_cache_creation_tokens,
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
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        user_id=trace.user_id,
        start_time=trace.start_time,
        end_time=trace.end_time,
        duration_ms=trace.duration_ms,
        status=trace.status.value,
        spans=[_span_to_summary(s) for s in trace.spans],
        total_tokens=trace.total_tokens,
        total_cache_read_tokens=trace.total_cache_read_tokens,
        total_cache_creation_tokens=trace.total_cache_creation_tokens,
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
        llm_details=span.llm_details,
        tool_details=span.tool_details,
    )


def _build_waterfall(trace: Trace) -> WaterfallData:
    """Build waterfall chart data"""
    from datetime import timezone

    trace_start = trace.start_time
    # Ensure trace_start is timezone-aware
    if trace_start.tzinfo is None:
        trace_start = trace_start.replace(tzinfo=timezone.utc)

    spans = []

    for span in trace.spans:
        # Ensure span.start_time is timezone-aware
        span_start = span.start_time
        if span_start.tzinfo is None:
            span_start = span_start.replace(tzinfo=timezone.utc)

        # Calculate relative offset
        offset = (span_start - trace_start).total_seconds() * 1000

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
                metrics=span.metrics or {},
                llm_details=span.llm_details,
                tool_details=span.tool_details,
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


def _span_to_llm_call(span: Span, trace: Trace) -> LLMCallSummary:
    """Convert LLM_CALL Span to LLMCallSummary"""
    return LLMCallSummary(
        span_id=span.span_id,
        trace_id=trace.trace_id,
        agent_id=trace.agent_id,
        session_id=trace.session_id,
        run_id=span.run_id,
        start_time=span.start_time,
        duration_ms=span.duration_ms,
        model_name=span.metrics.get("model") or span.attributes.get("model_name"),
        provider=span.metrics.get("provider") or span.attributes.get("provider"),
        input_tokens=span.metrics.get("tokens.input") or span.metrics.get("input_tokens"),
        output_tokens=span.metrics.get("tokens.output") or span.metrics.get("output_tokens"),
        total_tokens=span.metrics.get("tokens.total") or span.metrics.get("total_tokens"),
        cache_read_tokens=span.metrics.get("cache_read_tokens") or span.metrics.get("tokens.cache_read"),
        cache_creation_tokens=span.metrics.get("cache_creation_tokens") or span.metrics.get("tokens.cache_creation"),
        llm_details=span.llm_details,
    )
