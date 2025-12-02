"""
StepExecutor - Step-based LLM Call Loop

This is the new Step-based executor that replaces AgentExecutor.
It creates and emits Steps directly instead of generic events.

职责：
- 实现 LLM ↔ Tool 循环逻辑
- 创建 Steps (User, Assistant, Tool)
- 发送 StepEvents (deltas + snapshots)
- 调用 ToolExecutor 执行工具

不负责：
- Run 状态管理
- 持久化 (由 Runner 负责)
"""

import asyncio
import time
from typing import AsyncIterator
from uuid import uuid4

from agio.components.models.base import Model
from agio.components.tools.base_tool import BaseTool
from agio.execution.abort_signal import AbortSignal
from agio.core import (
    ExecutionConfig,
    MessageRole,
    Step,
    StepDelta,
    StepEvent,
    StepMetrics,
    create_step_completed_event,
    create_step_delta_event,
)
from agio.core.adapters import StepAdapter
from agio.execution.tool_executor import ToolExecutor
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ToolCallAccumulator:
    """
    累加流式 tool calls。

    OpenAI 返回的 tool calls 是增量式的，需要累加后才能执行。
    """

    def __init__(self):
        self._calls: dict[int, dict] = {}

    def accumulate(self, delta_calls: list[dict]):
        """累加增量 tool calls"""
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
        """获取最终的完整 tool calls"""
        return [call for call in self._calls.values() if call["id"] is not None]

    def clear(self):
        """清空累加器"""
        self._calls.clear()


class StepExecutor:
    """
    Step-based LLM Call Loop 执行器。

    核心改进：
    1. 直接创建 Steps 而不是 Events
    2. Steps 就是 LLM Messages，零转换
    3. 发送 StepEvents (delta + snapshot)

    Examples:
        >>> executor = StepExecutor(
        ...     model=OpenAIModel(...),
        ...     tools=[SearchTool()],
        ... )
        >>> async for event in executor.execute(
        ...     session_id="session_123",
        ...     run_id="run_456",
        ...     messages=[{"role": "user", "content": "Search Python"}]
        ... ):
        ...     if event.type == StepEventType.STEP_DELTA:
        ...         print(event.delta.content, end="")
    """

    def __init__(
        self,
        model: Model,
        tools: list[BaseTool],
        config: ExecutionConfig | None = None,
    ):
        """
        初始化 Executor。

        Args:
            model: LLM Model 实例
            tools: 可用工具列表
            config: 执行配置
        """
        self.model = model
        self.tools = tools
        self.config = config or ExecutionConfig()
        self.tool_executor = ToolExecutor(tools)

    async def execute(
        self,
        session_id: str,
        run_id: str,
        messages: list[dict],
        start_sequence: int = 1,
        abort_signal: AbortSignal | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        执行 LLM Call Loop，产生 StepEvent 流。

        Args:
            session_id: Session ID
            run_id: Run ID
            messages: 初始消息列表（OpenAI 格式），会被原地修改
            start_sequence: 起始 sequence 编号
            abort_signal: 中断信号（可选）

        Yields:
            StepEvent: Step 事件流
                - STEP_DELTA: Step 增量更新
                - STEP_COMPLETED: Step 完成（最终快照）

        流程:
            1. 调用 LLM，流式接收响应
            2. 创建 Assistant Step，发送 deltas
            3. 如果有 tool calls，执行工具
            4. 创建 Tool Steps
            5. 继续循环或结束
        """
        current_step = 0
        current_sequence = start_sequence

        # 获取工具的 OpenAI schema
        tool_schemas = self._get_tool_schemas() if self.tools else None

        while current_step < self.config.max_steps:
            # 检查中断
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

            # 1. 调用 LLM，创建 Assistant Step
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
                # Track first token latency
                if first_token_time is None and (chunk.content or chunk.tool_calls):
                    first_token_time = time.time()

                # Accumulate content
                if chunk.content:
                    full_content += chunk.content

                    # Send delta event
                    yield create_step_delta_event(
                        step_id=assistant_step.id,
                        run_id=run_id,
                        delta=StepDelta(content=chunk.content),
                    )

                # Accumulate tool calls
                if chunk.tool_calls:
                    accumulator.accumulate(chunk.tool_calls)

                    # Send tool_calls delta
                    yield create_step_delta_event(
                        step_id=assistant_step.id,
                        run_id=run_id,
                        delta=StepDelta(tool_calls=chunk.tool_calls),
                    )

                # Capture usage
                if chunk.usage:
                    usage_data = chunk.usage

            # 2. Finalize Assistant Step
            step_end_time = time.time()
            final_tool_calls = accumulator.finalize()

            assistant_step.content = full_content or None
            assistant_step.tool_calls = final_tool_calls or None

            # Build metrics
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

                # Model info (would come from model config)
                assistant_step.metrics.model_name = getattr(self.model, "model_name", None)
                assistant_step.metrics.provider = getattr(self.model, "provider", None)

            # Send completed event
            yield create_step_completed_event(
                step_id=assistant_step.id, run_id=run_id, snapshot=assistant_step
            )

            # Add to messages
            messages.append(StepAdapter.to_llm_message(assistant_step))
            current_sequence += 1

            # 3. Check if we need to execute tools
            if not final_tool_calls:
                # No tool calls, we're done
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

            results = await self.tool_executor.execute_batch(final_tool_calls, abort_signal=abort_signal)

            for result in results:
                # Create Tool Step
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

                # Send completed event (tools don't stream)
                yield create_step_completed_event(
                    step_id=tool_step.id, run_id=run_id, snapshot=tool_step
                )

                # Add to messages
                messages.append(StepAdapter.to_llm_message(tool_step))
                current_sequence += 1

            # Continue loop to get next assistant response

    def _get_tool_schemas(self) -> list[dict]:
        """获取工具的 OpenAI schema"""
        return [tool.to_openai_schema() for tool in self.tools]
    
