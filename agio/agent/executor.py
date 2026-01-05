"""
Agent Executor - LLM agent execution loop with tool calling.

This module implements the core agent execution loop:
- Streams LLM responses and accumulates tool calls
- Executes tools in parallel
- Tracks metrics and state
- Handles termination and summary generation
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from agio.agent.summarizer import build_termination_messages
from agio.config import ExecutionConfig
from agio.domain import (
    RunMetrics,
    Step,
    StepAdapter,
    StepDelta,
    StepMetrics,
    normalize_usage_metrics,
)
from agio.llm import Model
from agio.runtime.control import AbortSignal
from agio.runtime.event_factory import EventFactory
from agio.runtime.permission.manager import PermissionManager
from agio.runtime.protocol import ExecutionContext, RunOutput
from agio.runtime.sequence_manager import SequenceManager
from agio.runtime.step_factory import StepFactory
from agio.runtime.step_repository import StepRepository
from agio.storage.session import SessionStore
from agio.tools import BaseTool
from agio.tools.executor import ToolExecutor
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from typing import Self


logger = get_logger(__name__)


class ToolCallAccumulator:
    """Accumulate streaming tool calls."""

    def __init__(self) -> None:
        self._calls: dict[int, dict] = {}

    def accumulate(self, delta_calls: list[dict]) -> None:
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
        return [call for call in self._calls.values() if call["id"] is not None]


class MetricsTracker:
    """Internal metrics tracker for aggregating execution statistics."""

    def __init__(self) -> None:
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.steps_count = 0
        self.tool_calls_count = 0
        self.assistant_steps_count = 0
        self.pending_tool_calls = None
        self.response_content = None

    def track(self, step: Step) -> None:
        self.steps_count += 1

        if step.metrics:
            if step.metrics.total_tokens:
                self.total_tokens += step.metrics.total_tokens
            if step.metrics.input_tokens:
                self.input_tokens += step.metrics.input_tokens
            if step.metrics.output_tokens:
                self.output_tokens += step.metrics.output_tokens

        if step.is_assistant_step():
            self.assistant_steps_count += 1
            if step.content:
                self.response_content = step.content
            if step.tool_calls:
                self.tool_calls_count += len(step.tool_calls)
                self.pending_tool_calls = step.tool_calls
        elif step.role.value == "tool":
            self.pending_tool_calls = None


# ═══════════════════════════════════════════════════════════════════════════
# Run State
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RunState:
    """Encapsulates all mutable state for a single execution run."""

    context: "ExecutionContext"
    config: "ExecutionConfig"
    messages: list[dict]
    repo: "StepRepository"
    tracker: "MetricsTracker"
    ef: "EventFactory"
    sf: "StepFactory"
    start_time: float = field(default_factory=time.time)
    current_step: int = 0
    termination_reason: str | None = None

    @classmethod
    def create(
        cls,
        context: "ExecutionContext",
        config: "ExecutionConfig",
        messages: list[dict],
        session_store: "SessionStore | None",
    ) -> "Self":
        return cls(
            context=context,
            config=config,
            messages=messages,
            repo=StepRepository(session_store, auto_flush_size=10),
            tracker=MetricsTracker(),
            ef=EventFactory(context),
            sf=StepFactory(context),
        )

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def check_limits(self) -> str | None:
        """Check all execution limits. Returns termination reason or None."""
        if self.current_step >= self.config.max_steps:
            return "max_steps"

        if self.config.run_timeout and self.elapsed > self.config.run_timeout:
            return "timeout"

        if (
            self.config.max_total_tokens
            and self.tracker.total_tokens >= self.config.max_total_tokens
        ):
            return "max_tokens"

        return None

    async def record_step(self, step: "Step", *, append_message: bool = True) -> None:
        """Queue for persistence, track metrics, emit event, optionally append to messages."""
        await self.repo.queue(step)
        self.tracker.track(step)
        await self.context.wire.write(self.ef.step_completed(step.id, step))
        if append_message:
            self.messages.append(StepAdapter.to_llm_message(step))

    async def emit_delta(self, step_id: str, delta: "StepDelta") -> None:
        await self.context.wire.write(self.ef.step_delta(step_id, delta))

    def build_output(self) -> "RunOutput":
        return RunOutput(
            response=self.tracker.response_content,
            run_id=self.context.run_id,
            session_id=self.context.session_id,
            metrics=RunMetrics(
                duration=self.elapsed,
                total_tokens=self.tracker.total_tokens,
                input_tokens=self.tracker.input_tokens,
                output_tokens=self.tracker.output_tokens,
                steps_count=self.tracker.steps_count,
                tool_calls_count=self.tracker.tool_calls_count,
            ),
            termination_reason=self.termination_reason,
        )

    async def cleanup(self) -> None:
        await self.repo.flush()


# ═══════════════════════════════════════════════════════════════════════════
# Step Builder (handles streaming accumulation)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class StepBuilder:
    """Accumulates streaming chunks into a complete Step."""

    step: "Step"
    state: "RunState"
    step_start_time: float = field(default_factory=time.time)
    tool_accumulator: "ToolCallAccumulator" = field(default_factory=ToolCallAccumulator)
    first_token_received: bool = False

    async def process_chunk(self, chunk) -> None:
        """Process a single stream chunk."""
        delta = StepDelta()
        has_content = chunk.content or chunk.reasoning_content or chunk.tool_calls

        # Track first token latency
        if has_content and not self.first_token_received:
            self.first_token_received = True
            if self.step.metrics:
                self.step.metrics.first_token_latency_ms = (
                    time.time() - self.step_start_time
                ) * 1000

        # Accumulate content
        if chunk.content:
            self.step.content = (self.step.content or "") + chunk.content
            delta.content = chunk.content

        if chunk.reasoning_content:
            self.step.reasoning_content = (
                self.step.reasoning_content or ""
            ) + chunk.reasoning_content
            delta.reasoning_content = chunk.reasoning_content

        if chunk.tool_calls:
            self.tool_accumulator.accumulate(chunk.tool_calls)
            delta.tool_calls = chunk.tool_calls

        # Usage (typically only in final chunk)
        if chunk.usage and self.step.metrics:
            normalized = normalize_usage_metrics(chunk.usage)
            self.step.metrics.input_tokens = normalized["input_tokens"]
            self.step.metrics.output_tokens = normalized["output_tokens"]
            self.step.metrics.total_tokens = normalized["total_tokens"]

        # Emit delta
        if has_content:
            await self.state.emit_delta(self.step.id, delta)

    def finalize(self) -> "Step":
        """Finalize step with accumulated data and metrics."""
        self.step.content = self.step.content or None
        self.step.reasoning_content = self.step.reasoning_content or None
        self.step.tool_calls = self.tool_accumulator.finalize() or None

        if self.step.metrics:
            self.step.metrics.exec_end_at = datetime.now(timezone.utc)
            self.step.metrics.duration_ms = (time.time() - self.step_start_time) * 1000

        return self.step


# ═══════════════════════════════════════════════════════════════════════════
# Agent Executor
# ═══════════════════════════════════════════════════════════════════════════


class AgentExecutor:
    """
    Executes LLM agent loop with tool calling.

    Flow: LLM → tools → repeat until completion or limit.
    """

    _SUMMARY_REASONS = frozenset(
        {"max_steps", "timeout", "max_tokens", "error_with_context"}
    )

    def __init__(
        self,
        model: "Model",
        tools: list["BaseTool"],
        session_store: "SessionStore | None" = None,
        sequence_manager: "SequenceManager | None" = None,
        config: "ExecutionConfig | None" = None,
        permission_manager: PermissionManager | None = None,
    ):
        self.model = model
        self.tools = tools
        self.session_store = session_store
        self.sequence_manager = sequence_manager
        self.config = config or ExecutionConfig()
        self.tool_executor = ToolExecutor(
            tools,
            permission_manager=permission_manager,
            default_timeout=config.tool_timeout,
        )
        self._tool_schemas = [t.to_openai_schema() for t in tools] if tools else None

    # ───────────────────────────────────────────────────────────────────
    # Public API
    # ───────────────────────────────────────────────────────────────────

    async def execute(
        self,
        messages: list[dict],
        context: "ExecutionContext",
        *,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> "RunOutput":
        state = RunState.create(context, self.config, messages, self.session_store)

        try:
            await self._run_loop(state, pending_tool_calls, abort_signal)
        except asyncio.CancelledError:
            state.termination_reason = "cancelled"
        except Exception:
            state.termination_reason = (
                "error_with_context"
                if state.tracker.assistant_steps_count > 0
                else "error"
            )
        finally:
            await self._maybe_generate_summary(state, abort_signal)
            await state.cleanup()

        return state.build_output()

    # ───────────────────────────────────────────────────────────────────
    # Core Loop
    # ───────────────────────────────────────────────────────────────────

    async def _run_loop(
        self,
        state: RunState,
        pending_tool_calls: list[dict] | None,
        abort_signal: "AbortSignal | None",
    ) -> None:
        # Resume pending tools from previous run
        if pending_tool_calls:
            await self._execute_tools(state, pending_tool_calls, abort_signal)

        # Main agent loop
        while True:
            self._check_abort(abort_signal)

            if reason := state.check_limits():
                state.termination_reason = reason
                break

            state.current_step += 1
            step = await self._stream_assistant_step(state, abort_signal)

            if not step.tool_calls:
                return  # Normal completion

            await self._execute_tools(state, step.tool_calls, abort_signal)

    # ───────────────────────────────────────────────────────────────────
    # LLM Streaming
    # ───────────────────────────────────────────────────────────────────

    async def _stream_assistant_step(
        self,
        state: RunState,
        abort_signal: "AbortSignal | None",
        *,
        messages: list[dict] | None = None,
        tools: list[dict] | None = ...,  # sentinel: use default
        append_message: bool = True,
    ) -> "Step":
        """Stream LLM response, build step, record it."""
        messages = messages if messages is not None else state.messages
        tools = self._tool_schemas if tools is ... else tools

        builder = await self._create_step_builder(state, messages, tools)

        async for chunk in self.model.arun_stream(messages, tools=tools):
            self._check_abort(abort_signal)
            await builder.process_chunk(chunk)

        step = builder.finalize()
        await state.record_step(step, append_message=append_message)
        return step

    async def _create_step_builder(
        self,
        state: RunState,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> StepBuilder:
        seq = await self._allocate_sequence(state.context)
        step = state.sf.assistant_step(
            sequence=seq,
            content="",
            tool_calls=None,
            llm_messages=messages.copy(),
            llm_tools=tools.copy() if tools else None,
            llm_request_params=self._get_request_params(),
            metrics=StepMetrics(
                exec_start_at=datetime.now(timezone.utc),
                model_name=getattr(self.model, "model_name", None),
                provider=getattr(self.model, "provider", None),
            ),
        )
        return StepBuilder(step=step, state=state)

    # ───────────────────────────────────────────────────────────────────
    # Tool Execution
    # ───────────────────────────────────────────────────────────────────

    async def _execute_tools(
        self,
        state: RunState,
        tool_calls: list[dict],
        abort_signal: "AbortSignal | None",
    ) -> None:
        results = await self.tool_executor.execute_batch(
            tool_calls, context=state.context, abort_signal=abort_signal
        )

        for result in results:
            seq = await self._allocate_sequence(state.context)
            step = state.sf.tool_step(
                sequence=seq,
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                content=result.content,
                content_for_user=result.content_for_user,
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
            await state.record_step(step)

    # ───────────────────────────────────────────────────────────────────
    # Summary Generation
    # ───────────────────────────────────────────────────────────────────

    async def _maybe_generate_summary(
        self,
        state: RunState,
        abort_signal: "AbortSignal | None",
    ) -> None:
        if not self.config.enable_termination_summary:
            return
        if state.termination_reason not in self._SUMMARY_REASONS:
            return

        summary_messages = build_termination_messages(
            messages=state.messages,
            termination_reason=state.termination_reason,
            pending_tool_calls=state.tracker.pending_tool_calls,
            custom_prompt=self.config.termination_summary_prompt,
        )

        step = await self._stream_assistant_step(
            state,
            abort_signal,
            messages=summary_messages,
            tools=None,
            append_message=False,
        )

        logger.info(
            "summary_generated",
            tokens=step.metrics.total_tokens if step.metrics else 0,
        )

    # ───────────────────────────────────────────────────────────────────
    # Helpers
    # ───────────────────────────────────────────────────────────────────

    def _check_abort(self, abort_signal: "AbortSignal | None") -> None:
        if abort_signal and abort_signal.is_aborted():
            raise asyncio.CancelledError(abort_signal.reason)

    async def _allocate_sequence(self, context: "ExecutionContext") -> int:
        if self.sequence_manager:
            return await self.sequence_manager.allocate(context.session_id, context)
        return 1

    def _get_request_params(self) -> dict | None:
        if hasattr(self.model, "temperature"):
            return {
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
                "top_p": self.model.top_p,
            }
        return None
