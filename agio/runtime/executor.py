"""
StepExecutor - Step-based LLM Call Loop

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
from uuid import uuid4

from agio.domain import (
    MessageRole,
    Step,
    StepDelta,
    StepEvent,
    StepMetrics,
    create_step_completed_event,
    create_step_delta_event,
)
from agio.domain.adapters import StepAdapter
from agio.runtime.tool_executor import ToolExecutor
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.llm import Model
    from agio.providers.tools import BaseTool
    from agio.runtime.control import AbortSignal
    from agio.runtime.wire import Wire
    from agio.config import ExecutionConfig

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


class StepExecutor:
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
        
        # Import here to avoid circular dependency
        from agio.config import ExecutionConfig
        self.config = config or ExecutionConfig()

    async def execute(
        self,
        session_id: str,
        run_id: str,
        messages: list[dict],
        start_sequence: int = 1,
        pending_tool_calls: list[dict] | None = None,
        abort_signal: "AbortSignal | None" = None,
        wire: "Wire | None" = None,
        depth: int = 0,
        parent_run_id: str | None = None,
        nested_runnable_id: str | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute LLM Call Loop, yield StepEvent stream.

        Args:
            session_id: Session ID
            run_id: Run ID
            messages: Initial message list (OpenAI format), modified in place
            start_sequence: Starting sequence number
            pending_tool_calls: Tool calls to execute before starting LLM loop (for resume)
            abort_signal: Abort signal (optional)
            wire: Wire for nested RunnableTool event streaming
            depth: Nesting depth for nested execution
            parent_run_id: Parent run ID for nested execution
            nested_runnable_id: ID of the nested Runnable being executed

        Yields:
            StepEvent: Step event stream
        """
        current_step = 0
        current_sequence = start_sequence

        # Execute pending tool_calls first (for resume from assistant with tools)
        if pending_tool_calls:
            logger.debug(
                "executor_executing_pending_tools",
                session_id=session_id,
                run_id=run_id,
                tool_count=len(pending_tool_calls),
            )
            
            async for event, new_seq in self._execute_tool_calls(
                pending_tool_calls, session_id, run_id, current_sequence, messages, abort_signal, wire,
                depth=depth, parent_run_id=parent_run_id, nested_runnable_id=nested_runnable_id,
            ):
                current_sequence = new_seq
                yield event

        tool_schemas = self._get_tool_schemas() if self.tools else None

        while current_step < self.config.max_steps:
            # Check abort
            if abort_signal and abort_signal.is_aborted():
                logger.info("step_executor_aborted", reason=abort_signal.reason)
                raise asyncio.CancelledError(abort_signal.reason or "Execution aborted")
            
            current_step += 1
            step_start_time = time.time()

            logger.debug(
                "executor_step_started",
                session_id=session_id,
                run_id=run_id,
                step=current_step,
                sequence=current_sequence,
            )

            # 1. Call LLM, create Assistant Step
            assistant_step = Step(
                id=str(uuid4()),
                session_id=session_id,
                run_id=run_id,
                sequence=current_sequence,
                role=MessageRole.ASSISTANT,
                content="",
                tool_calls=None,
                metrics=StepMetrics(),
            )

            full_content = ""
            accumulator = ToolCallAccumulator()
            first_token_time = None
            usage_data = None

            # Stream LLM response
            async for chunk in self.model.arun_stream(messages, tools=tool_schemas):
                if first_token_time is None and (chunk.content or chunk.tool_calls):
                    first_token_time = time.time()

                if chunk.content:
                    full_content += chunk.content
                    yield create_step_delta_event(
                        step_id=assistant_step.id,
                        run_id=run_id,
                        delta=StepDelta(content=chunk.content),
                        depth=depth,
                        parent_run_id=parent_run_id,
                        nested_runnable_id=nested_runnable_id,
                    )

                if chunk.tool_calls:
                    accumulator.accumulate(chunk.tool_calls)
                    yield create_step_delta_event(
                        step_id=assistant_step.id,
                        run_id=run_id,
                        delta=StepDelta(tool_calls=chunk.tool_calls),
                        depth=depth,
                        parent_run_id=parent_run_id,
                        nested_runnable_id=nested_runnable_id,
                    )

                if chunk.usage:
                    usage_data = chunk.usage

            # 2. Finalize Assistant Step
            step_end_time = time.time()
            final_tool_calls = accumulator.finalize()

            assistant_step.content = full_content or None
            assistant_step.tool_calls = final_tool_calls or None

            if assistant_step.metrics:
                assistant_step.metrics.duration_ms = (step_end_time - step_start_time) * 1000
                if first_token_time:
                    assistant_step.metrics.first_token_latency_ms = (
                        first_token_time - step_start_time
                    ) * 1000

                if usage_data:
                    assistant_step.metrics.input_tokens = usage_data.get("prompt_tokens")
                    assistant_step.metrics.output_tokens = usage_data.get("completion_tokens")
                    assistant_step.metrics.total_tokens = usage_data.get("total_tokens")

                assistant_step.metrics.model_name = getattr(self.model, "model_name", None)
                assistant_step.metrics.provider = getattr(self.model, "provider", None)

            yield create_step_completed_event(
                step_id=assistant_step.id, 
                run_id=run_id, 
                snapshot=assistant_step,
                depth=depth,
                parent_run_id=parent_run_id,
                nested_runnable_id=nested_runnable_id,
            )

            messages.append(StepAdapter.to_llm_message(assistant_step))
            current_sequence += 1

            # 3. Check if we need to execute tools
            if not final_tool_calls:
                logger.debug(
                    "executor_completed",
                    session_id=session_id,
                    run_id=run_id,
                    total_steps=current_step,
                )
                break

            # 4. Execute tools and create Tool Steps
            logger.debug(
                "executor_executing_tools",
                session_id=session_id,
                run_id=run_id,
                tool_count=len(final_tool_calls),
            )

            async for event, new_seq in self._execute_tool_calls(
                final_tool_calls, session_id, run_id, current_sequence, messages, abort_signal, wire,
                depth=depth, parent_run_id=parent_run_id, nested_runnable_id=nested_runnable_id,
            ):
                current_sequence = new_seq
                yield event

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        session_id: str,
        run_id: str,
        current_sequence: int,
        messages: list[dict],
        abort_signal: "AbortSignal | None" = None,
        wire: "Wire | None" = None,
        depth: int = 0,
        parent_run_id: str | None = None,
        nested_runnable_id: str | None = None,
    ) -> AsyncIterator[tuple[StepEvent, int]]:
        """
        Execute tool calls and yield (event, new_sequence) tuples.
        
        Args:
            tool_calls: Tool calls to execute
            session_id: Session ID
            run_id: Run ID  
            current_sequence: Current sequence number
            messages: Messages list (modified in place)
            abort_signal: Abort signal
            wire: Wire for nested RunnableTool event streaming
            depth: Nesting depth for nested execution
            parent_run_id: Parent run ID for nested execution
            nested_runnable_id: ID of the nested Runnable being executed
            
        Yields:
            tuple[StepEvent, int]: (step_completed_event, updated_sequence)
        """
        results = await self.tool_executor.execute_batch(
            tool_calls, abort_signal=abort_signal, wire=wire, session_id=session_id,
            parent_run_id=run_id,  # Pass current run_id as parent for nested RunnableTool
        )
        
        for result in results:
            tool_step = Step(
                id=str(uuid4()),
                session_id=session_id,
                run_id=run_id,
                sequence=current_sequence,
                role=MessageRole.TOOL,
                content=result.content,
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                metrics=StepMetrics(
                    duration_ms=result.duration * 1000 if result.duration else None,
                    tool_exec_time_ms=result.duration * 1000 if result.duration else None,
                ),
            )
            
            messages.append(StepAdapter.to_llm_message(tool_step))
            current_sequence += 1
            
            yield create_step_completed_event(
                step_id=tool_step.id, 
                run_id=run_id, 
                snapshot=tool_step,
                depth=depth,
                parent_run_id=parent_run_id,
                nested_runnable_id=nested_runnable_id,
            ), current_sequence

    def _get_tool_schemas(self) -> list[dict]:
        """Get OpenAI schema for tools."""
        return [tool.to_openai_schema() for tool in self.tools]


__all__ = ["StepExecutor", "ToolCallAccumulator"]
