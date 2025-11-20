import time
import asyncio
from typing import AsyncIterator, Union

from agio.agent.hooks.base import AgentHook
from agio.domain.run import (
    AgentRun,
    AgentRunStep,
    RunStatus,
    RequestSnapshot,
)
from agio.domain.messages import Message, UserMessage
from agio.domain.tools import ToolResult
from agio.utils.logger import log_error, log_debug
from agio.sessions.base import AgentSession
from agio.core.loop import LoopConfig
from agio.core.events import ModelEventType
from agio.drivers.openai_driver import OpenAIModelDriver
from agio.runners.context import ContextBuilder
from agio.runners.config import AgentRunConfig
from agio.protocol.events import (
    AgentEvent,
    create_run_started_event,
    create_run_completed_event,
    create_text_delta_event,
    create_metrics_snapshot_event,
    create_error_event,
    EventType as AgentEventType,
)
from agio.protocol.converter import EventConverter
from agio.db.repository import AgentRunRepository

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agio.agent.base import Agent

class AgentRunner:
    """
    Stateless execution engine for an Agent.
    Orchestrates ModelDriver and manages Run lifecycle.
    """
    
    def __init__(
        self, 
        agent: "Agent", 
        hooks: list[AgentHook], 
        config: AgentRunConfig | None = None,
        repository: AgentRunRepository | None = None
    ):
        self.agent = agent
        self.hooks = hooks
        self.config = config or AgentRunConfig()
        self.repository = repository
        self.driver = OpenAIModelDriver(model=agent.model)
        self.context_builder = ContextBuilder(agent=agent, config=self.config)
        self.event_converter = EventConverter()
        self._event_sequence = 0
    
    async def _store_and_yield(self, event: AgentEvent) -> AgentEvent:
        """存储并返回事件"""
        if self.repository:
            await self.repository.save_event(event, self._event_sequence)
            self._event_sequence += 1
        return event

    async def run(self, session: AgentSession, query: str) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流（向后兼容）。
        """
        async for event in self.run_stream(session, query):
            if event.type == AgentEventType.TEXT_DELTA:
                yield event.data.get("content", "")
    
    async def run_stream(self, session: AgentSession, query: str) -> AsyncIterator[AgentEvent]:
        run = AgentRun(
            agent_id=self.agent.id,
            user_id=session.user_id,
            session_id=session.session_id,
            input_query=query,
            status=RunStatus.STARTING,
        )
        run.metrics.start_time = time.time()

        for hook in self.hooks:
            await hook.on_run_start(run)
        
        # 发送 Run 开始事件
        yield await self._store_and_yield(
            create_run_started_event(run_id=run.id, query=query)
        )

        messages = await self.context_builder.build(query, session)
        run.status = RunStatus.RUNNING

        loop_config = LoopConfig(
            max_steps=self.config.max_steps,
            temperature=self.agent.model.temperature,
            max_tokens=self.agent.model.max_tokens,
        )

        try:
            current_step: AgentRunStep | None = None
            step_num = 0
            full_response = ""
            is_first_token = True

            async for event in self.driver.run(messages, self.agent.tools, loop_config):
                if event.type == ModelEventType.TEXT_DELTA:
                    if is_first_token:
                        if run.metrics.first_token_timestamp is None:
                            run.metrics.first_token_timestamp = time.time()
                            run.metrics.response_latency = (
                                time.time() - run.metrics.start_time
                            ) * 1000
                        is_first_token = False
                    
                    full_response += event.content
                    
                    # 转换并发送 AgentEvent
                    yield await self._store_and_yield(
                        create_text_delta_event(
                            run_id=run.id,
                            content=event.content,
                            step=event.step
                        )
                    )

                elif event.type == ModelEventType.USAGE:
                    if current_step:
                        current_step.metrics.prompt_tokens = event.usage.get("prompt_tokens", 0)
                        current_step.metrics.completion_tokens = event.usage.get("completion_tokens", 0)
                        current_step.metrics.total_tokens = event.usage.get("total_tokens", 0)
                    
                    # 发送 Usage 事件
                    from agio.protocol.events import create_usage_update_event
                    yield await self._store_and_yield(
                        create_usage_update_event(
                            run_id=run.id,
                            prompt_tokens=event.usage.get("prompt_tokens", 0),
                            completion_tokens=event.usage.get("completion_tokens", 0),
                            total_tokens=event.usage.get("total_tokens", 0),
                            step=event.step
                        )
                    )

                elif event.type == ModelEventType.TOOL_CALL_STARTED:
                    if event.step > step_num:
                        step_num = event.step
                        if current_step:
                            current_step.metrics.end_time = time.time()
                            current_step.metrics.duration = current_step.metrics.end_time - current_step.metrics.start_time
                            run.steps.append(current_step)
                            for hook in self.hooks:
                                await hook.on_step_end(run, current_step)
                        
                        current_step = AgentRunStep(
                            run_id=run.id,
                            agent_id=self.agent.id,
                            step_num=step_num,
                            messages_context=messages.copy(),
                            request_snapshot=RequestSnapshot(
                                url=self.agent.model.base_url or "unknown",
                                model=self.agent.model.name,
                                model_settings={
                                    "temperature": self.agent.model.temperature,
                                    "max_tokens": self.agent.model.max_tokens,
                                },
                                messages=[m.model_dump() for m in messages],
                                tools=(
                                    [t.to_openai_schema() for t in self.agent.tools]
                                    if self.agent.tools
                                    else None
                                ),
                            ),
                        )
                        current_step.metrics.start_time = time.time()
                        for hook in self.hooks:
                            await hook.on_step_start(run, current_step)
                    
                    for tc in event.tool_calls:
                        for hook in self.hooks:
                            await hook.on_tool_start(run, current_step, tc)
                        
                        # 发送工具调用开始事件
                        from agio.protocol.events import create_tool_call_started_event
                        import json
                        yield await self._store_and_yield(
                            create_tool_call_started_event(
                                run_id=run.id,
                                tool_name=tc.get("function", {}).get("name", "unknown"),
                                tool_call_id=tc.get("id", ""),
                                arguments=json.loads(tc.get("function", {}).get("arguments", "{}")),
                                step=event.step
                            )
                        )

                elif event.type == ModelEventType.TOOL_CALL_FINISHED:
                    tool_result = ToolResult(**event.tool_result)
                    if current_step:
                        current_step.tool_results.append(tool_result)
                    
                    for hook in self.hooks:
                        await hook.on_tool_end(run, current_step, tool_result)
                    
                    run.metrics.tool_calls_count += 1
                    if not tool_result.is_success:
                        run.metrics.tool_errors_count += 1
                    
                    # 发送工具调用完成事件
                    from agio.protocol.events import create_tool_call_completed_event
                    yield await self._store_and_yield(
                        create_tool_call_completed_event(
                            run_id=run.id,
                            tool_name=tool_result.tool_name,
                            tool_call_id=tool_result.tool_call_id,
                            result=tool_result.content,
                            duration=tool_result.duration,
                            step=event.step
                        )
                    )

                elif event.type == ModelEventType.METRICS_SNAPSHOT:
                    # 发送 metrics 快照事件
                    yield await self._store_and_yield(
                        create_metrics_snapshot_event(
                            run_id=run.id,
                            metrics=event.metadata
                        )
                    )
                
                elif event.type == ModelEventType.ERROR:
                    log_error(f"ModelDriver error: {event.content}")
                    run.status = RunStatus.FAILED
                    run.error = event.content
                    
                    # 发送错误事件
                    yield await self._store_and_yield(
                        create_error_event(
                            run_id=run.id,
                            error=event.content,
                            error_type=event.metadata.get("error_type", "unknown")
                        )
                    )
                    
                    for hook in self.hooks:
                        await hook.on_error(run, Exception(event.content))
                    break

            if current_step and step_num > 0:
                current_step.metrics.end_time = time.time()
                current_step.metrics.duration = current_step.metrics.end_time - current_step.metrics.start_time
                run.steps.append(current_step)
                for hook in self.hooks:
                    await hook.on_step_end(run, current_step)

            run.response_content = full_response
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time
            run.metrics.steps_count = step_num
            
            if run.status != RunStatus.FAILED:
                run.status = RunStatus.COMPLETED
            
            for hook in self.hooks:
                await hook.on_run_end(run)
            
            # 发送 Run 完成事件
            yield await self._store_and_yield(
                create_run_completed_event(
                    run_id=run.id,
                    response=full_response,
                    metrics={
                        "duration": run.metrics.duration,
                        "steps_count": run.metrics.steps_count,
                        "tool_calls_count": run.metrics.tool_calls_count,
                        "total_tokens": sum(s.metrics.total_tokens for s in run.steps),
                        "response_latency": run.metrics.response_latency,
                    }
                )
            )
            
            # 保存最终的 Run 状态
            if self.repository:
                await self.repository.save_run(run)

            if self.agent.memory and self.config.enable_memory_update:
                new_messages = [UserMessage(content=query)]
                for s in run.steps:
                    if s.model_response:
                        new_messages.append(s.model_response)
                
                if self.config.memory_update_async:
                    asyncio.create_task(
                        self.agent.memory.history.add_messages(session.session_id, new_messages)
                    )
                else:
                    await self.agent.memory.history.add_messages(session.session_id, new_messages)

        except Exception as e:
            log_error(f"Run failed: {e}")
            run.status = RunStatus.FAILED
            run.error = str(e)
            for hook in self.hooks:
                await hook.on_error(run, e)
            raise e

