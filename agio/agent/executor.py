"""
AgentExecutor - Complete LLM execution unit.

This module implements the core execution logic for Agent:
- Complete encapsulation of execution details
- LLM loop with tool execution
- Event streaming to wire (internal)
- Step persistence via StepRepository (internal)
- Metrics tracking (internal)
- Summary generation (internal)
- Returns clean ExecutionResult
"""

import asyncio
import time
from datetime import datetime, timezone

from agio.config import ExecutionConfig
from agio.domain import (
    RunMetrics,
    Step,
    StepAdapter,
    StepDelta,
    StepMetrics,
    normalize_usage_metrics,
)
from agio.runtime.event_factory import EventFactory
from agio.runtime.step_factory import StepFactory
from agio.runtime.step_repository import StepRepository
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime.protocol import RunOutput
from agio.tools.executor import ToolExecutor
from agio.utils.logging import get_logger
from agio.agent.summarizer import build_termination_messages
from agio.providers.llm import Model
from agio.providers.storage import SessionStore
from agio.providers.tools import BaseTool


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


class MetricsTracker:
    """Internal metrics tracker for aggregating execution statistics."""

    def __init__(self):
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.steps_count = 0
        self.tool_calls_count = 0
        self.assistant_steps_count = 0
        self.last_assistant_had_tools = False
        self.pending_tool_calls = None
        self.response_content = None

    def track(self, step: Step):
        """Track step metrics."""
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
            self.last_assistant_had_tools = step.has_tool_calls()
            if step.tool_calls:
                self.tool_calls_count += len(step.tool_calls)
                self.pending_tool_calls = step.tool_calls
        elif step.role.value == "tool":
            self.pending_tool_calls = None


class AgentExecutor:
    """
    Complete LLM execution unit.

    Responsibilities:
    1. LLM loop execution
    2. Tool batch execution
    3. Event streaming to wire (internal)
    4. Step persistence via StepRepository (internal)
    5. Metrics tracking (internal)
    6. Summary generation (internal)
    7. Returns ExecutionResult
    """

    def __init__(
        self,
        model: "Model",
        tools: list["BaseTool"],
        session_store: "SessionStore | None" = None,
        sequence_manager=None,
        config: "ExecutionConfig | None" = None,
        permission_manager=None,
    ):
        """
        Initialize AgentExecutor.

        Args:
            model: LLM model instance
            tools: Available tools
            session_store: SessionStore for persistence
            sequence_manager: SequenceManager for sequence allocation
            config: Execution configuration
            permission_manager: PermissionManager for tool permission checking
        """
        self.model = model
        self.tools = tools
        self.session_store = session_store
        self.sequence_manager = sequence_manager
        self.config = config or ExecutionConfig()
        self.tool_executor = ToolExecutor(tools, permission_manager=permission_manager)

    async def execute(
        self,
        messages: list[dict],
        context: ExecutionContext,
        *,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> RunOutput:
        """
        Execute LLM loop and return result.

        Internal handling:
        1. LLM loop (max_steps, timeout, max_tokens controlled)
        2. Tool batch execution
        3. Event streaming to wire
        4. Step persistence via StepRepository (auto-flush)
        5. Metrics tracking
        6. Summary generation (if needed)

        Args:
            messages: Initial LLM messages (modified in place)
            context: ExecutionContext with wire, sequence_manager, etc.
            pending_tool_calls: Pending tool calls from previous execution
            abort_signal: Abort signal

        Returns:
            ExecutionResult with response and metrics
        """
        start_time = time.time()
        repo = StepRepository(self.session_store, auto_flush_size=10)
        tracker = MetricsTracker()
        ef = EventFactory(context)
        termination_reason = None

        try:
            # Execute pending tool calls first (if any)
            if pending_tool_calls:
                await self._execute_tool_calls(
                    tool_calls=pending_tool_calls,
                    messages=messages,
                    context=context,
                    repo=repo,
                    tracker=tracker,
                    ef=ef,
                    abort_signal=abort_signal,
                )

            # LLM loop
            tool_schemas = self._get_tool_schemas() if self.tools else None
            current_step = 0

            while current_step < self.config.max_steps:
                # Check abort
                if abort_signal and abort_signal.is_aborted():
                    raise asyncio.CancelledError(abort_signal.reason)

                # Check timeout
                if self.config.run_timeout:
                    elapsed = time.time() - start_time
                    if elapsed > self.config.run_timeout:
                        await self._execute_summary_if_needed(
                            messages=messages,
                            context=context,
                            repo=repo,
                            tracker=tracker,
                            ef=ef,
                            termination_reason="timeout",
                            pending_tool_calls=tracker.pending_tool_calls,
                            abort_signal=abort_signal,
                        )
                        termination_reason = "timeout"
                        break

                # Check max_tokens
                if (
                    self.config.max_total_tokens
                    and tracker.total_tokens >= self.config.max_total_tokens
                ):
                    await self._execute_summary_if_needed(
                        messages=messages,
                        context=context,
                        repo=repo,
                        tracker=tracker,
                        ef=ef,
                        termination_reason="max_tokens",
                        pending_tool_calls=tracker.pending_tool_calls,
                        abort_signal=abort_signal,
                    )
                    termination_reason = "max_tokens"
                    break

                current_step += 1

                # Call LLM and stream
                assistant_step = await self._call_llm_and_stream(
                    messages=messages,
                    tool_schemas=tool_schemas,
                    context=context,
                    ef=ef,
                    abort_signal=abort_signal,
                )

                # Process assistant step (queue, track, event, add to messages)
                await self._process_step(
                    step=assistant_step,
                    repo=repo,
                    tracker=tracker,
                    context=context,
                    ef=ef,
                    messages=messages,
                )

                # Check if there are tool calls
                if not assistant_step.tool_calls:
                    # Normal completion
                    break

                # Execute tool calls
                await self._execute_tool_calls(
                    tool_calls=assistant_step.tool_calls,
                    messages=messages,
                    context=context,
                    repo=repo,
                    tracker=tracker,
                    ef=ef,
                    abort_signal=abort_signal,
                )
            else:
                # Reached max_steps with pending tool calls
                await self._execute_summary_if_needed(
                    messages=messages,
                    context=context,
                    repo=repo,
                    tracker=tracker,
                    ef=ef,
                    termination_reason="max_steps",
                    pending_tool_calls=tracker.pending_tool_calls,
                    abort_signal=abort_signal,
                )
                termination_reason = "max_steps"

            # Build return result
            end_time = time.time()
            duration = end_time - start_time
            return RunOutput(
                response=tracker.response_content,
                run_id=context.run_id,
                session_id=context.session_id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=tracker.total_tokens,
                    input_tokens=tracker.input_tokens,
                    output_tokens=tracker.output_tokens,
                    steps_count=tracker.steps_count,
                    tool_calls_count=tracker.tool_calls_count,
                ),
                termination_reason=termination_reason,
            )

        except asyncio.CancelledError:
            termination_reason = "cancelled"
            end_time = time.time()
            duration = end_time - start_time
            return RunOutput(
                response=tracker.response_content,
                run_id=context.run_id,
                session_id=context.session_id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=tracker.total_tokens,
                    input_tokens=tracker.input_tokens,
                    output_tokens=tracker.output_tokens,
                    steps_count=tracker.steps_count,
                    tool_calls_count=tracker.tool_calls_count,
                ),
                termination_reason=termination_reason,
            )

        except Exception as e:
            # If we have successful LLM calls, return error_with_context
            # Otherwise return error (nothing to summarize)
            error_reason = (
                "error_with_context" if tracker.assistant_steps_count > 0 else "error"
            )

            end_time = time.time()
            duration = end_time - start_time
            return RunOutput(
                response=tracker.response_content,
                run_id=context.run_id,
                session_id=context.session_id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=tracker.total_tokens,
                    input_tokens=tracker.input_tokens,
                    output_tokens=tracker.output_tokens,
                    steps_count=tracker.steps_count,
                    tool_calls_count=tracker.tool_calls_count,
                ),
                termination_reason=error_reason,
            )

        finally:
            # Always flush remaining steps
            await repo.flush()

    async def _process_step(
        self,
        step: Step,
        repo: StepRepository,
        tracker: MetricsTracker,
        context: ExecutionContext,
        ef: EventFactory,
        messages: list[dict],
    ):
        """Process step: queue, track, send event, add to messages."""
        await repo.queue(step)
        tracker.track(step)
        await context.wire.write(ef.step_completed(step.id, step))
        messages.append(StepAdapter.to_llm_message(step))

    async def _call_llm_and_stream(
        self,
        messages: list[dict],
        tool_schemas: list[dict] | None,
        context: ExecutionContext,
        ef: EventFactory,
        abort_signal: "AbortSignal | None" = None,
    ) -> Step:
        """
        Call LLM and stream response.

        Returns complete Assistant Step.
        """
        # Allocate sequence
        if self.sequence_manager:
            seq = await self.sequence_manager.allocate(context.session_id, context)
        else:
            seq = 1

        # Create assistant step
        sf = StepFactory(context)

        llm_start_time = datetime.now(timezone.utc)
        step_start_time = time.time()

        assistant_step = sf.assistant_step(
            sequence=seq,
            content="",
            tool_calls=None,
            llm_messages=messages.copy(),
            llm_tools=tool_schemas.copy() if tool_schemas else None,
            llm_request_params=self._get_request_params(),
            metrics=StepMetrics(exec_start_at=llm_start_time),
        )

        # Stream processing
        full_content = ""
        full_reasoning_content = ""
        accumulator = ToolCallAccumulator()
        first_token_time = None
        usage_data = None

        async for chunk in self.model.arun_stream(messages, tools=tool_schemas):
            # Check abort during streaming
            if abort_signal and abort_signal.is_aborted():
                raise asyncio.CancelledError(abort_signal.reason)

            if first_token_time is None and (
                chunk.content or chunk.reasoning_content or chunk.tool_calls
            ):
                first_token_time = time.time()

            # Content delta
            if chunk.content:
                full_content += chunk.content
                await context.wire.write(
                    ef.step_delta(assistant_step.id, StepDelta(content=chunk.content))
                )

            # Reasoning delta
            if chunk.reasoning_content:
                full_reasoning_content += chunk.reasoning_content
                await context.wire.write(
                    ef.step_delta(
                        assistant_step.id,
                        StepDelta(reasoning_content=chunk.reasoning_content),
                    )
                )

            # Tool calls delta
            if chunk.tool_calls:
                accumulator.accumulate(chunk.tool_calls)
                await context.wire.write(
                    ef.step_delta(
                        assistant_step.id, StepDelta(tool_calls=chunk.tool_calls)
                    )
                )

            # Usage
            if chunk.usage:
                usage_data = chunk.usage

        # Complete step
        step_end_time = time.time()
        llm_end_time = datetime.now(timezone.utc)

        assistant_step.content = full_content or None
        assistant_step.reasoning_content = full_reasoning_content or None
        assistant_step.tool_calls = accumulator.finalize() or None

        # Update metrics
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
                normalized = normalize_usage_metrics(usage_data)
                assistant_step.metrics.input_tokens = normalized["input_tokens"]
                assistant_step.metrics.output_tokens = normalized["output_tokens"]
                assistant_step.metrics.total_tokens = normalized["total_tokens"]

            assistant_step.metrics.model_name = getattr(self.model, "model_name", None)
            assistant_step.metrics.provider = getattr(self.model, "provider", None)

        return assistant_step

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        messages: list[dict],
        context: ExecutionContext,
        repo: StepRepository,
        tracker: MetricsTracker,
        ef: EventFactory,
        abort_signal: "AbortSignal | None",
    ):
        """Execute tool calls."""
        sf = StepFactory(context)

        results = await self.tool_executor.execute_batch(
            tool_calls,
            context=context,
            abort_signal=abort_signal,
        )

        for result in results:
            # Allocate sequence
            if self.sequence_manager:
                seq = await self.sequence_manager.allocate(
                    context.session_id, context
                )
            else:
                seq = 1

            # Create tool step
            tool_step = sf.tool_step(
                sequence=seq,
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

            # Process tool step
            await self._process_step(
                step=tool_step,
                repo=repo,
                tracker=tracker,
                context=context,
                ef=ef,
                messages=messages,
            )

    async def _execute_summary_if_needed(
        self,
        messages: list[dict],
        context: ExecutionContext,
        repo: StepRepository,
        tracker: MetricsTracker,
        ef: EventFactory,
        termination_reason: str,
        pending_tool_calls: list[dict] | None,
        abort_signal: "AbortSignal | None",
    ):
        """
        Execute summary if config enabled and reason requires summary.

        Summary is generated for:
        - max_steps: Hit step limit with pending tool calls
        - timeout: Execution timeout
        - max_tokens: Token limit exceeded
        - error_with_context: Error after successful LLM calls

        Summary is NOT generated for:
        - None: Normal completion
        - cancelled: User cancelled
        - error: Error without context
        """
        if not self.config.enable_termination_summary:
            return

        if termination_reason not in (
            "max_steps",
            "timeout",
            "max_tokens",
            "error_with_context",
        ):
            return

        # Execute summary generation.
        logger.debug(
            "executing_summary",
            termination_reason=termination_reason,
            pending_tool_calls=bool(pending_tool_calls),
        )

        # Build summary messages
        summary_messages = build_termination_messages(
            messages=messages,
            termination_reason=termination_reason,
            pending_tool_calls=pending_tool_calls,
            custom_prompt=self.config.termination_summary_prompt,
        )

        # Call LLM (no tools)
        summary_step = await self._call_llm_and_stream(
            messages=summary_messages,
            tool_schemas=None,
            context=context,
            ef=ef,
            abort_signal=abort_signal,
        )

        # Process summary step
        await self._process_step(
            step=summary_step,
            repo=repo,
            tracker=tracker,
            context=context,
            ef=ef,
            messages=[],  # Don't add summary to messages
        )

        logger.info(
            "summary_generated",
            tokens=summary_step.metrics.total_tokens if summary_step.metrics else 0,
        )

    def _get_tool_schemas(self) -> list[dict]:
        """Get tool schemas."""
        return [tool.to_openai_schema() for tool in self.tools]

    def _get_request_params(self) -> dict | None:
        """Get LLM request parameters."""
        if hasattr(self.model, "temperature"):
            return {
                "temperature": self.model.temperature,
                "max_tokens": self.model.max_tokens,
                "top_p": self.model.top_p,
            }
        return None


__all__ = ["AgentExecutor", "ToolCallAccumulator", "MetricsTracker"]
