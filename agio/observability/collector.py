"""
Trace collector - builds Trace from StepEvent stream.

Uses middleware pattern to wrap event streams without modifying core execution logic.
"""

from typing import AsyncIterator
from uuid import uuid4

from agio.domain.events import StepEvent, StepEventType
from agio.observability.trace import Trace, Span, SpanKind, SpanStatus
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class TraceCollector:
    """
    Trace collector - constructs Trace from StepEvent stream.

    Usage:
        collector = TraceCollector(store)

        async for event in collector.wrap_stream(event_stream):
            yield event  # Events are passed through while building trace
    """

    PREVIEW_LENGTH = 500  # Input/output preview length

    def __init__(self, store=None):
        """
        Initialize collector.

        Args:
            store: Optional TraceStore for persistence
        """
        self.store = store

    async def wrap_stream(
        self,
        event_stream: AsyncIterator[StepEvent],
        trace_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        input_query: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Wrap event stream to automatically collect trace information.

        Args:
            event_stream: Original event stream
            trace_id: Optional trace ID
            workflow_id: Workflow ID (if workflow execution)
            agent_id: Agent ID (if single agent execution)
            session_id: Session ID
            user_id: User ID
            input_query: User input

        Yields:
            StepEvent: Original events with injected trace_id/span_id
        """
        # Initialize trace
        trace = Trace(
            trace_id=trace_id or str(uuid4()),
            workflow_id=workflow_id,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            input_query=input_query,
        )

        # Span stack: track currently active span hierarchy
        span_stack: dict[str, Span] = {}  # key: run_id or stage_id
        current_span: Span | None = None

        try:
            async for event in event_stream:
                # Skip processing for nested events (they have their own trace collection)
                # but still yield them for real-time streaming
                if event.nested_runnable_id:
                    # Nested events already have trace context from inner execution
                    # Just pass them through without modification
                    yield event
                    continue
                
                # Process event and update trace
                current_span = self._process_event(event, trace, span_stack, current_span)

                # Inject trace fields into event
                event.trace_id = trace.trace_id
                if current_span:
                    event.span_id = current_span.span_id
                    event.parent_span_id = current_span.parent_span_id

                yield event

        except Exception as e:
            # Mark trace as failed on exception
            trace.complete(status=SpanStatus.ERROR)
            if current_span:
                current_span.complete(
                    status=SpanStatus.ERROR,
                    error_message=str(e),
                )
            logger.error("trace_collection_failed", trace_id=trace.trace_id, error=str(e))
            raise
        finally:
            # Save trace
            if not trace.end_time:
                trace.complete(status=SpanStatus.OK)

            if self.store:
                try:
                    await self.store.save_trace(trace)
                except Exception as e:
                    logger.error(
                        "trace_save_failed", trace_id=trace.trace_id, error=str(e)
                    )

            # Export to OTLP (async, non-blocking)
            try:
                from agio.observability import get_otlp_exporter
                exporter = get_otlp_exporter()
                if exporter.enabled:
                    await exporter.export_trace(trace)
            except Exception as e:
                logger.warning("otlp_export_failed", trace_id=trace.trace_id, error=str(e))

    def _process_event(
        self,
        event: StepEvent,
        trace: Trace,
        span_stack: dict[str, Span],
        current_span: Span | None,
    ) -> Span | None:
        """Process single event, return currently active span"""

        event_type = event.type

        # === RUN_STARTED ===
        if event_type == StepEventType.RUN_STARTED:
            data = event.data or {}

            # Determine if workflow or agent
            if data.get("workflow_id") or data.get("type") in (
                "pipeline",
                "loop",
                "parallel",
            ):
                # Workflow top-level span
                span = Span(
                    trace_id=trace.trace_id,
                    kind=SpanKind.WORKFLOW,
                    name=data.get("workflow_id", "workflow"),
                    depth=0,
                    attributes={
                        "workflow_id": data.get("workflow_id"),
                        "workflow_type": data.get("type"),
                    },
                    input_preview=trace.input_query[: self.PREVIEW_LENGTH]
                    if trace.input_query
                    else None,
                )
                trace.root_span_id = span.span_id
            else:
                # Agent span
                parent = current_span
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.AGENT,
                    name=data.get("agent_id", "agent"),
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "agent_id": data.get("agent_id"),
                        "session_id": data.get("session_id"),
                    },
                )
                if not trace.root_span_id:
                    trace.root_span_id = span.span_id

            trace.add_span(span)
            span_stack[event.run_id] = span
            return span

        # === NODE_STARTED ===
        elif event_type == StepEventType.NODE_STARTED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=event.node_id or "node",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "node_id": event.node_id,
                    "iteration": event.iteration,
                },
            )
            trace.add_span(span)
            span_stack[f"node:{event.node_id}"] = span
            return span

        # === NODE_COMPLETED ===
        elif event_type == StepEventType.NODE_COMPLETED:
            span = span_stack.get(f"node:{event.node_id}")
            if span:
                output_len = event.data.get("output_length") if event.data else None
                span.complete(
                    status=SpanStatus.OK,
                    output_preview=f"[{output_len} chars]" if output_len else None,
                )
            return span_stack.get(event.run_id) or current_span

        # === NODE_SKIPPED ===
        elif event_type == StepEventType.NODE_SKIPPED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=event.node_id or "node",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "node_id": event.node_id,
                    "skipped": True,
                    "condition": event.data.get("condition") if event.data else None,
                },
            )
            span.complete(status=SpanStatus.OK)  # Skipped is still OK
            trace.add_span(span)
            return current_span

        # === STEP_COMPLETED ===
        elif event_type == StepEventType.STEP_COMPLETED:
            if not event.snapshot:
                return current_span

            step = event.snapshot
            parent = current_span

            if step.role.value == "tool":
                # Tool 调用 Span
                from datetime import datetime, timezone, timedelta
                
                # 计算真实的开始时间（根据 duration 反推）
                end_time = datetime.now(timezone.utc)
                duration_ms = step.metrics.tool_exec_time_ms if step.metrics else None
                if duration_ms is not None:
                    start_time = end_time - timedelta(milliseconds=duration_ms)
                else:
                    start_time = end_time
                
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.TOOL_CALL,
                    name=step.name or "tool",
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "tool_name": step.name,
                        "tool_call_id": step.tool_call_id,
                    },
                    step_id=step.id,
                    run_id=step.run_id,
                )
                span.start_time = start_time
                span.end_time = end_time
                span.duration_ms = duration_ms or 0
                span.status = SpanStatus.OK

            elif step.role.value == "assistant":
                # LLM 调用 Span
                from datetime import datetime, timezone, timedelta
                
                # 计算真实的开始时间（根据 duration 反推）
                end_time = datetime.now(timezone.utc)
                duration_ms = step.metrics.duration_ms if step.metrics else None
                if duration_ms is not None:
                    start_time = end_time - timedelta(milliseconds=duration_ms)
                else:
                    start_time = end_time
                
                span = Span(
                    trace_id=trace.trace_id,
                    parent_span_id=parent.span_id if parent else None,
                    kind=SpanKind.LLM_CALL,
                    name=(step.metrics.model_name if step.metrics and step.metrics.model_name else "llm"),
                    depth=(parent.depth + 1) if parent else 0,
                    attributes={
                        "model_name": step.metrics.model_name if step.metrics else None,
                        "provider": step.metrics.provider if step.metrics else None,
                        "has_tool_calls": bool(step.tool_calls),
                    },
                    step_id=step.id,
                    run_id=step.run_id,
                    output_preview=step.content[: self.PREVIEW_LENGTH]
                    if step.content
                    else None,
                )
                span.start_time = start_time
                span.end_time = end_time
                span.duration_ms = duration_ms or 0
                span.status = SpanStatus.OK
                
                if step.metrics:
                    span.metrics = {
                        "tokens.input": step.metrics.input_tokens,
                        "tokens.output": step.metrics.output_tokens,
                        "tokens.total": step.metrics.total_tokens,
                        "first_token_ms": step.metrics.first_token_latency_ms,
                    }
            else:
                return current_span

            trace.add_span(span)
            return current_span

        # === RUN_COMPLETED ===
        elif event_type == StepEventType.RUN_COMPLETED:
            span = span_stack.get(event.run_id)
            if span:
                response = event.data.get("response") if event.data else None
                span.complete(
                    status=SpanStatus.OK,
                    output_preview=response[: self.PREVIEW_LENGTH] if response else None,
                )
                trace.final_output = response
            return span_stack.get(event.run_id)

        # === RUN_FAILED ===
        elif event_type == StepEventType.RUN_FAILED:
            span = span_stack.get(event.run_id)
            if span:
                error = event.data.get("error") if event.data else "Unknown error"
                span.complete(status=SpanStatus.ERROR, error_message=error)
            return span_stack.get(event.run_id)

        # === ITERATION_STARTED ===
        elif event_type == StepEventType.ITERATION_STARTED:
            # Update current workflow span's iteration count
            span = span_stack.get(event.run_id)
            if span:
                span.attributes["current_iteration"] = event.iteration
            return current_span

        # === BRANCH_STARTED ===
        elif event_type == StepEventType.BRANCH_STARTED:
            parent = span_stack.get(event.run_id) or current_span
            span = Span(
                trace_id=trace.trace_id,
                parent_span_id=parent.span_id if parent else None,
                kind=SpanKind.STAGE,
                name=f"branch:{event.branch_id}",
                depth=(parent.depth + 1) if parent else 1,
                attributes={
                    "branch_id": event.branch_id,
                    "parallel": True,
                },
            )
            trace.add_span(span)
            span_stack[f"branch:{event.branch_id}"] = span
            return span

        # === BRANCH_COMPLETED ===
        elif event_type == StepEventType.BRANCH_COMPLETED:
            span = span_stack.get(f"branch:{event.branch_id}")
            if span:
                span.complete(status=SpanStatus.OK)
            return span_stack.get(event.run_id) or current_span

        return current_span


def create_collector(store=None) -> TraceCollector:
    """Create TraceCollector instance"""
    return TraceCollector(store)


__all__ = ["TraceCollector", "create_collector"]
