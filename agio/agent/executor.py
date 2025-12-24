"""
AgentExecutor - Step-based LLM Call Loop

Responsibilities:
- Implement LLM ↔ Tool loop logic
- Create Steps (User, Assistant, Tool)
- Emit StepEvents (deltas + snapshots)
- Call ToolExecutor for tool execution

Does NOT handle:
- Run state management
- Persistence (handled by Runner)
"""

import asyncio
import time
from typing import AsyncIterator, TYPE_CHECKING

from agio.domain import (
    StepDelta,
    StepEvent,
    StepMetrics,
    ExecutionContext,
    StepAdapter,
    normalize_usage_metrics,
)
from agio.tools.executor import ToolExecutor
from agio.utils.logging import get_logger
from agio.runtime.event_factory import EventFactory
from agio.runtime.step_factory import StepFactory
from agio.config import ExecutionConfig

if TYPE_CHECKING:
    from agio.providers.llm import Model
    from agio.providers.tools import BaseTool
    from agio.agent.control import AbortSignal

logger = get_logger(__name__)


class ToolCallAccumulator:
    """
    Accumulate streaming tool calls.

    OpenAI returns tool calls incrementally, need to accumulate before execution.
    """

    def __init__(self):
        self._calls: dict[int, dict] = {}

    def accumulate(self, delta_calls: list[dict]):
        """Accumulate incremental tool calls."""
        for tc in delta_calls:
            idx = tc.get("index", 0)

            if idx not in self._calls:
                self._calls[idx] = {
                    "id": None,
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }

            acc = self._calls[idx]

            if tc.get("id"):
                acc["id"] = tc["id"]

            if tc.get("type"):
                acc["type"] = tc["type"]

            if tc.get("function"):
                fn = tc["function"]
                if fn.get("name"):
                    acc["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    acc["function"]["arguments"] += fn["arguments"]

    def finalize(self) -> list[dict]:
        """Get final complete tool calls."""
        return [call for call in self._calls.values() if call["id"] is not None]

    def clear(self):
        """Clear accumulator."""
        self._calls.clear()


class AgentExecutor:
    """
    Step-based LLM Call Loop executor.

    Key improvements:
    1. Creates Steps directly instead of Events
    2. Steps are LLM Messages, zero conversion
    3. Emits StepEvents (delta + snapshot)
    """

    def __init__(
        self,
        model: "Model",
        tools: list["BaseTool"],
        config: "ExecutionConfig | None" = None,
    ):
        """
        Initialize Executor.

        Args:
            model: LLM Model instance
            tools: Available tools list
            config: Execution config
        """
        self.model = model
        self.tools = tools
        self.tool_executor = ToolExecutor(tools)
        self.config = config or ExecutionConfig()

    async def execute(
        self,
        messages: list[dict],
        ctx: "ExecutionContext",
        *,
        allocate_sequence_fn,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute LLM Call Loop, yield StepEvent stream.

        Args:
            messages: Initial message list (OpenAI format), modified in place
            ctx: ExecutionContext containing run_id, session_id, wire, depth, etc.
            allocate_sequence_fn: Async callback to allocate next sequence number
            pending_tool_calls: Tool calls to execute before starting LLM loop (for resume)
            abort_signal: Abort signal (optional)

        Yields:
            StepEvent: Step event stream
        """

        ef = EventFactory(ctx)
        current_step = 0

        # Execute pending tool_calls first (for resume from assistant with tools)
        if pending_tool_calls:
            logger.debug(
                "executor_executing_pending_tools",
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                tool_count=len(pending_tool_calls),
            )

            async for event in self._execute_tool_calls(
                pending_tool_calls,
                ctx,
                allocate_sequence_fn,
                messages,
                abort_signal,
            ):
                yield event

        tool_schemas = self._get_tool_schemas() if self.tools else None

        while current_step < self.config.max_steps:
            # Check abort
            if abort_signal and abort_signal.is_aborted():
                logger.info("step_executor_aborted", reason=abort_signal.reason)
                raise asyncio.CancelledError(abort_signal.reason or "Execution aborted")

            current_step += 1
            step_start_time = time.time()

            # Allocate sequence for assistant step
            current_sequence = await allocate_sequence_fn()
            
            logger.debug(
                "executor_step_started",
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                step=current_step,
                sequence=current_sequence,
            )

            # Record LLM call start time
            from datetime import datetime, timezone

            llm_start_time = datetime.now(timezone.utc)

            # 1. Call LLM, create Assistant Step using StepFactory
            sf = StepFactory(ctx)
            assistant_step = sf.assistant_step(
                sequence=current_sequence,
                content="",
                tool_calls=None,
                llm_messages=messages.copy() if messages else None,
                llm_tools=tool_schemas.copy() if tool_schemas else None,
                llm_request_params={
                    "temperature": self.model.temperature,
                    "max_tokens": self.model.max_tokens,
                    "top_p": self.model.top_p,
                }
                if hasattr(self.model, "temperature")
                else None,
                metrics=StepMetrics(exec_start_at=llm_start_time),
            )

            full_content = ""
            full_reasoning_content = ""
            accumulator = ToolCallAccumulator()
            first_token_time = None
            usage_data = None

            # Stream LLM response
            async for chunk in self.model.arun_stream(messages, tools=tool_schemas):
                if first_token_time is None and (
                    chunk.content or chunk.reasoning_content or chunk.tool_calls
                ):
                    first_token_time = time.time()

                if chunk.content:
                    full_content += chunk.content
                    yield ef.step_delta(
                        assistant_step.id, StepDelta(content=chunk.content)
                    )

                if chunk.reasoning_content:
                    full_reasoning_content += chunk.reasoning_content
                    yield ef.step_delta(
                        assistant_step.id,
                        StepDelta(reasoning_content=chunk.reasoning_content),
                    )

                if chunk.tool_calls:
                    accumulator.accumulate(chunk.tool_calls)
                    yield ef.step_delta(
                        assistant_step.id, StepDelta(tool_calls=chunk.tool_calls)
                    )

                if chunk.usage:
                    usage_data = chunk.usage

            # 2. Finalize Assistant Step
            step_end_time = time.time()
            llm_end_time = datetime.now(timezone.utc)
            final_tool_calls = accumulator.finalize()

            assistant_step.content = full_content or None
            assistant_step.reasoning_content = full_reasoning_content or None
            assistant_step.tool_calls = final_tool_calls or None

            if assistant_step.metrics:
                assistant_step.metrics.exec_end_at = llm_end_time
                assistant_step.metrics.duration_ms = (
                    step_end_time - step_start_time
                ) * 1000
                if first_token_time:
                    assistant_step.metrics.first_token_latency_ms = (
                        first_token_time - step_start_time
                    ) * 1000

                if usage_data:
                    # Normalize metrics to handle both OpenAI-style and unified-style keys
                    normalized = normalize_usage_metrics(usage_data)
                    assistant_step.metrics.input_tokens = normalized["input_tokens"]
                    assistant_step.metrics.output_tokens = normalized["output_tokens"]
                    assistant_step.metrics.total_tokens = normalized["total_tokens"]

                assistant_step.metrics.model_name = getattr(
                    self.model, "model_name", None
                )
                assistant_step.metrics.provider = getattr(self.model, "provider", None)

            yield ef.step_completed(assistant_step.id, assistant_step)

            messages.append(StepAdapter.to_llm_message(assistant_step))

            # 3. Check if we need to execute tools
            if not final_tool_calls:
                logger.debug(
                    "executor_completed",
                    session_id=ctx.session_id,
                    run_id=ctx.run_id,
                    total_steps=current_step,
                )
                break

            # 4. Execute tools and create Tool Steps
            logger.debug(
                "executor_executing_tools",
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                tool_count=len(final_tool_calls),
            )

            async for event in self._execute_tool_calls(
                final_tool_calls,
                ctx,
                allocate_sequence_fn,
                messages,
                abort_signal,
            ):
                yield event

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        ctx: "ExecutionContext",
        allocate_sequence_fn,
        messages: list[dict],
        abort_signal: "AbortSignal | None" = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute tool calls and yield step events.

        Args:
            tool_calls: Tool calls to execute
            ctx: ExecutionContext
            allocate_sequence_fn: Async callback to allocate sequence
            messages: Messages list (modified in place)
            abort_signal: Abort signal

        Yields:
            StepEvent: step_completed events
        """
        ef = EventFactory(ctx)
        sf = StepFactory(ctx)

        results = await self.tool_executor.execute_batch(
            tool_calls,
            context=ctx,
            abort_signal=abort_signal,
        )

        for result in results:
            # Allocate sequence for tool step
            tool_sequence = await allocate_sequence_fn()
            
            # Create Tool Step using StepFactory
            from datetime import datetime, timezone

            tool_step = sf.tool_step(
                sequence=tool_sequence,
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                content=result.content,
                metrics=StepMetrics(
                    duration_ms=result.duration * 1000 if result.duration else None,
                    tool_exec_time_ms=result.duration * 1000
                    if result.duration
                    else None,
                    exec_start_at=datetime.fromtimestamp(
                        result.start_time, tz=timezone.utc
                    ),
                    exec_end_at=datetime.fromtimestamp(
                        result.end_time, tz=timezone.utc
                    ),
                ),
            )

            messages.append(StepAdapter.to_llm_message(tool_step))

            yield ef.step_completed(tool_step.id, tool_step)

    def _get_tool_schemas(self) -> list[dict]:
        """Get OpenAI schema for tools."""
        return [tool.to_openai_schema() for tool in self.tools]


__all__ = ["AgentExecutor", "ToolCallAccumulator"]
