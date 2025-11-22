"""
StepRunner - Step-based Agent Runner

This is the new Step-based runner that replaces AgentRunner.
It uses StepExecutor and saves Steps to the repository.

职责：
- 管理 Run 生命周期
- 使用 StepExecutor 执行
- 保存 Steps 到 repository
- 调用 Hooks
- 提供 resume 方法用于 retry
"""

import time
from typing import AsyncIterator, TYPE_CHECKING
from uuid import uuid4

from agio.sessions.base import AgentSession
from agio.runners.step_context import build_context_from_steps
from agio.execution.step_executor import StepExecutor, StepExecutorConfig
from agio.protocol.step_events import (
    StepEvent,
    StepEventType,
    create_run_started_event,
    create_run_completed_event,
    create_run_failed_event,
)
from agio.db.repository import AgentRunRepository
from agio.domain.run import AgentRun, RunStatus
from agio.domain.step import Step, MessageRole
from agio.domain.metrics import AgentRunMetrics

if TYPE_CHECKING:
    from agio.agent.base import Agent
from agio.agent.hooks.base import AgentHook

from agio.utils.logging import get_logger

logger = get_logger(__name__)


class StepRunnerConfig:
    """Runner 配置"""
    def __init__(
        self,
        max_steps: int = 10,
        enable_memory_update: bool = False,
    ):
        self.max_steps = max_steps
        self.enable_memory_update = enable_memory_update


class StepRunner:
    """
    Step-based Agent Runner.
    
    核心改进：
    1. 使用 StepExecutor 而不是 AgentExecutor
    2. 保存 Steps 到 repository
    3. 使用 build_context_from_steps 构建上下文
    4. 提供 resume 方法用于 retry
    
    Examples:
        >>> runner = StepRunner(agent, hooks, repository=repo)
        >>> async for event in runner.run_stream(session, "Hello"):
        ...     if event.type == StepEventType.STEP_DELTA:
        ...         print(event.delta.content, end="")
    """
    
    def __init__(
        self,
        agent: "Agent",
        hooks: list[AgentHook],
        config: StepRunnerConfig | None = None,
        repository: AgentRunRepository | None = None,
    ):
        """
        初始化 Runner。
        
        Args:
            agent: Agent 实例
            hooks: Hook 列表
            config: 运行配置
            repository: Repository for saving steps
        """
        self.agent = agent
        self.hooks = hooks
        self.config = config or StepRunnerConfig()
        self.repository = repository
    
    async def run_stream(
        self,
        session: AgentSession,
        query: str
    ) -> AsyncIterator[StepEvent]:
        """
        执行 Agent，返回 StepEvent 流。
        
        Args:
            session: 会话
            query: 用户查询
        
        Yields:
            StepEvent: Step 事件流
        
        流程:
            1. 创建 Run
            2. 创建 User Step
            3. 构建上下文
            4. 创建 StepExecutor
            5. 消费 StepExecutor 事件流
            6. 保存所有 Steps
            7. 更新 Run metrics
        """
        # 1. 创建 Run
        run = AgentRun(
            id=str(uuid4()),
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
        yield create_run_started_event(run_id=run.id, query=query)
        
        # 4. 创建 User Step
        user_step = Step(
            id=str(uuid4()),
            session_id=session.session_id,
            run_id=run.id,
            sequence=await self._get_next_sequence(session.session_id),
            role=MessageRole.USER,
            content=query,
        )
        
        # Save user step
        if self.repository:
            await self.repository.save_step(user_step)
        
        # 5. 构建上下文
        if self.repository:
            # Load existing steps from repository
            messages = await build_context_from_steps(
                session.session_id,
                self.repository,
                system_prompt=self.agent.system_prompt
            )
        else:
            # No repository - start fresh
            messages = []
            if self.agent.system_prompt:
                messages.append({
                    "role": "system",
                    "content": self.agent.system_prompt
                })
            messages.append(user_step.to_message_dict())
        
        run.status = RunStatus.RUNNING
        
        # 6. 创建 StepExecutor
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=StepExecutorConfig(max_steps=self.config.max_steps),
        )
        
        # Track metrics
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        tool_calls_count = 0
        
        try:
            # 7. 消费 StepExecutor 事件流
            start_sequence = user_step.sequence + 1
            
            async for event in executor.execute(
                session_id=session.session_id,
                run_id=run.id,
                messages=messages,
                start_sequence=start_sequence
            ):
                # Save steps when completed
                if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                    step = event.snapshot
                    
                    # Save to repository
                    if self.repository:
                        await self.repository.save_step(step)
                    
                    # Update metrics
                    if step.metrics:
                        if step.metrics.total_tokens:
                            total_tokens += step.metrics.total_tokens
                        if step.metrics.input_tokens:
                            prompt_tokens += step.metrics.input_tokens
                        if step.metrics.output_tokens:
                            completion_tokens += step.metrics.output_tokens
                    
                    if step.is_assistant_step() and step.has_tool_calls():
                        tool_calls_count += len(step.tool_calls or [])
                
                # Forward event to client
                yield event
            
            # 8. 完成
            run.status = RunStatus.COMPLETED
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time
            run.metrics.total_tokens = total_tokens
            run.metrics.prompt_tokens = prompt_tokens
            run.metrics.completion_tokens = completion_tokens
            run.metrics.tool_calls_count = tool_calls_count
            
            # Get final response (last assistant step content)
            if messages:
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        run.response_content = msg["content"]
                        break
            
            for hook in self.hooks:
                await hook.on_run_end(run)
            
            # 发送 Run 完成事件
            yield create_run_completed_event(
                run_id=run.id,
                response=run.response_content or "",
                metrics={
                    "duration": run.metrics.duration,
                    "tool_calls_count": run.metrics.tool_calls_count,
                    "total_tokens": run.metrics.total_tokens,
                }
            )
            
            # 保存最终的 Run 状态
            if self.repository:
                await self.repository.save_run(run)
        
        except Exception as e:
            logger.error("step_run_failed", run_id=run.id, error=str(e), exc_info=True)
            run.status = RunStatus.FAILED
            
            for hook in self.hooks:
                await hook.on_error(run, e)
            
            # Send failed event
            yield create_run_failed_event(run_id=run.id, error=str(e))
            
            raise e
    
    async def _get_next_sequence(self, session_id: str) -> int:
        """获取下一个 sequence 编号"""
        if not self.repository:
            return 1
        
        last_step = await self.repository.get_last_step(session_id)
        if last_step:
            return last_step.sequence + 1
        return 1
    
    # --- Resume methods for retry ---
    
    async def resume_from_user_step(
        self,
        session_id: str,
        last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """
        Resume from a user step (most common retry case).
        
        The user step is already in the database, we just need to
        regenerate the assistant response.
        """
        logger.info(
            "resuming_from_user_step",
            session_id=session_id,
            step_id=last_step.id
        )
        
        # Build context up to this point
        if self.repository:
            messages = await build_context_from_steps(
                session_id,
                self.repository,
                system_prompt=self.agent.system_prompt
            )
        else:
            raise ValueError("Repository required for resume")
        
        # Create new run for this retry
        run_id = str(uuid4())
        
        # Create executor
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=StepExecutorConfig(max_steps=self.config.max_steps),
        )
        
        # Execute from this point
        start_sequence = last_step.sequence + 1
        
        async for event in executor.execute(
            session_id=session_id,
            run_id=run_id,
            messages=messages,
            start_sequence=start_sequence
        ):
            # Save steps
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                if self.repository:
                    await self.repository.save_step(event.snapshot)
            
            yield event
    
    async def resume_from_tool_step(
        self,
        session_id: str,
        last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """
        Resume from a tool step.
        
        Tool results are already in the database, regenerate assistant response.
        """
        # Same as resume_from_user_step
        async for event in self.resume_from_user_step(session_id, last_step):
            yield event
    
    async def resume_from_assistant_with_tools(
        self,
        session_id: str,
        last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """
        Resume from an assistant step that has tool calls.
        
        Re-execute the tools and continue.
        """
        logger.info(
            "resuming_from_assistant_with_tools",
            session_id=session_id,
            step_id=last_step.id
        )
        
        # Build context
        if self.repository:
            messages = await build_context_from_steps(
                session_id,
                self.repository,
                system_prompt=self.agent.system_prompt
            )
        else:
            raise ValueError("Repository required for resume")
        
        # Create new run
        run_id = str(uuid4())
        
        # Create executor
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=StepExecutorConfig(max_steps=self.config.max_steps),
        )
        
        # Execute (will re-execute tools)
        start_sequence = last_step.sequence + 1
        
        async for event in executor.execute(
            session_id=session_id,
            run_id=run_id,
            messages=messages,
            start_sequence=start_sequence
        ):
            # Save steps
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                if self.repository:
                    await self.repository.save_step(event.snapshot)
            
            yield event
