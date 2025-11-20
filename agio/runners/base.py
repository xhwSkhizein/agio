"""
AgentRunner - Agent 运行编排器

职责：
- 管理 Run 生命周期
- 构建上下文
- 消费 Executor 产生的 AgentEvent
- 持久化事件和状态
- 调用 Hooks

不负责：
- LLM 调用
- Tool 执行
- 事件生成
"""

import time
from typing import AsyncIterator, TYPE_CHECKING

from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun, RunStatus
from agio.utils.logger import log_error
from agio.sessions.base import AgentSession
from agio.runners.context import ContextBuilder
from agio.runners.config import AgentRunConfig
from agio.runners.state_tracker import RunStateTracker
from agio.execution.agent_executor import AgentExecutor, ExecutorConfig
from agio.protocol.events import (
    AgentEvent,
    EventType,
    create_run_started_event,
    create_run_completed_event,
)
from agio.db.repository import AgentRunRepository

if TYPE_CHECKING:
    from agio.agent.base import Agent


class AgentRunner:
    """
    Agent 运行编排器。

    职责：
    1. 管理 Run 生命周期
    2. 构建上下文（通过 ContextBuilder）
    3. 消费 Executor 产生的 AgentEvent
    4. 持久化事件和状态
    5. 调用 Hooks

    Examples:
        >>> runner = AgentRunner(agent, hooks)
        >>> async for event in runner.run_stream(session, query):
        ...     if event.type == EventType.TEXT_DELTA:
        ...         print(event.data["content"], end="")
    """

    def __init__(
        self,
        agent: "Agent",
        hooks: list[AgentHook],
        config: AgentRunConfig | None = None,
        repository: AgentRunRepository | None = None,
    ):
        """
        初始化 Runner。

        Args:
            agent: Agent 实例
            hooks: Hook 列表
            config: 运行配置
            repository: 事件存储仓库
        """
        self.agent = agent
        self.hooks = hooks
        self.config = config or AgentRunConfig()
        self.repository = repository
        self.context_builder = ContextBuilder(agent=agent, config=self.config)
        self._event_sequence = 0

    async def _emit_and_store(self, event: AgentEvent) -> AgentEvent:
        """存储并返回事件"""
        if self.repository:
            await self.repository.save_event(event, self._event_sequence)
            self._event_sequence += 1
        return event

    async def run(self, session: AgentSession, query: str) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流（向后兼容）。

        Args:
            session: 会话
            query: 用户查询

        Yields:
            str: 文本增量
        """
        async for event in self.run_stream(session, query):
            if event.type == EventType.TEXT_DELTA:
                yield event.data.get("content", "")

    async def run_stream(
        self, session: AgentSession, query: str
    ) -> AsyncIterator[AgentEvent]:
        """
        执行 Agent，返回 AgentEvent 流。

        Args:
            session: 会话
            query: 用户查询

        Yields:
            AgentEvent: 统一的事件流

        流程:
            1. 创建 Run
            2. 构建上下文
            3. 创建 Executor
            4. 消费 Executor 事件流
            5. 更新状态和 Metrics
            6. 持久化
        """
        # 1. 创建 Run
        run = AgentRun(
            agent_id=self.agent.id,
            user_id=session.user_id,
            session_id=session.session_id,
            input_query=query,
            status=RunStatus.STARTING,
        )
        run.metrics.start_time = time.time()

        # 2. 调用 Hooks
        for hook in self.hooks:
            await hook.on_run_start(run)

        # 3. 发送 Run 开始事件
        yield await self._emit_and_store(
            create_run_started_event(run_id=run.id, query=query)
        )

        # 4. 构建上下文
        messages = await self.context_builder.build(query, session)

        # 将 Message 对象转换为 dict 格式
        dict_messages = []
        for msg in messages:
            if hasattr(msg, "model_dump"):
                # Pydantic model - 使用 mode='json' 以正确序列化 datetime
                dict_messages.append(msg.model_dump(mode="json", exclude_none=True))
            else:
                dict_messages.append(msg)

        run.status = RunStatus.RUNNING

        # 5. 创建 Executor
        executor = AgentExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=ExecutorConfig(max_steps=self.config.max_steps),
        )

        # 6. 状态追踪器
        state = RunStateTracker(run)

        try:
            # 7. 消费 Executor 事件流
            async for event in executor.execute(dict_messages, run_id=run.id):
                # 更新状态
                state.update(event)

                # 存储并转发事件
                yield await self._emit_and_store(event)

            # 8. 完成
            run.status = RunStatus.COMPLETED
            run.response_content = state.get_full_response()
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time

            # 从 state 构建 metrics
            state_metrics = state.build_metrics()
            run.metrics.total_tokens = state_metrics.total_tokens
            run.metrics.prompt_tokens = state_metrics.prompt_tokens
            run.metrics.completion_tokens = state_metrics.completion_tokens
            run.metrics.tool_calls_count = state_metrics.tool_calls_count
            run.metrics.tool_errors_count = state_metrics.tool_errors_count

            for hook in self.hooks:
                await hook.on_run_end(run)

            # 发送 Run 完成事件
            yield await self._emit_and_store(
                create_run_completed_event(
                    run_id=run.id,
                    response=run.response_content,
                    metrics={
                        "duration": run.metrics.duration,
                        "tool_calls_count": run.metrics.tool_calls_count,
                        "total_tokens": run.metrics.total_tokens,
                    },
                )
            )

            # 保存最终的 Run 状态
            if self.repository:
                await self.repository.save_run(run)

            # 更新记忆（如果启用）
            if self.agent.memory and self.config.enable_memory_update:
                # TODO: 需要重新设计记忆更新逻辑
                pass

        except Exception as e:
            log_error(f"Run failed: {e}")
            run.status = RunStatus.FAILED
            # Note: AgentRun doesn't have error field, errors are tracked in steps

            for hook in self.hooks:
                await hook.on_error(run, e)

            raise e
