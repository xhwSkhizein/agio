"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
Agent is the first-class citizen for execution.

Wire-based Architecture:
- run_stream() creates Wire internally and yields events
- run() requires ExecutionContext with wire (for nested calls)
- All nested executions share the same wire
"""

import asyncio
import datetime
import os
from typing import AsyncIterator
from uuid import uuid4

from agio.agent.helper import build_context_from_steps
from agio.agent.executor import AgentExecutor
from agio.config.schema import ExecutionConfig
from agio.config.template import renderer
from agio.domain import StepEvent
from agio.domain.models import RunOutput
from agio.llm import Model
from agio.runtime.control import AbortSignal
from agio.runtime.context import ExecutionContext, RunnableType
from agio.runtime.lifecycle import RunLifecycle
from agio.runtime.pipeline import StepPipeline
from agio.runtime.permission.manager import PermissionManager
from agio.runtime.step_factory import StepFactory
from agio.runtime.wire import Wire
from agio.skills.manager import SkillManager
from agio.storage.session.base import SessionStore
from agio.tools import BaseTool
from agio.utils.logging import get_logger
from agio.observability import TraceCollector
from agio.storage.trace.store import TraceStore


logger = get_logger(__name__)


class Agent:
    """
    Agent - First-class execution unit.

    Holds the configuration for Model and Tools.
    Provides direct execution methods:
    - run(input, context) -> RunOutput (for nested calls, requires context with wire)
    - run_stream(input, ...) -> AsyncIterator[StepEvent] (creates Wire internally)

    Run lifecycle (RUN_STARTED/COMPLETED/FAILED) is managed internally.
    """

    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        session_store: SessionStore | None = None,
        permission_manager: PermissionManager | None = None,
        skill_manager: SkillManager | None = None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
        max_steps: int = 10,
        enable_termination_summary: bool = False,
        termination_summary_prompt: str | None = None,
    ):
        self._id = name
        self.model = model
        self.tools: list[BaseTool] = tools or []
        self.session_store: SessionStore | None = session_store
        self.permission_manager: PermissionManager | None = permission_manager
        self.skill_manager: SkillManager | None = skill_manager
        self.user_id: str | None = user_id
        self.system_prompt: str | None = system_prompt
        self.max_steps: int = max_steps
        self.enable_termination_summary: bool = enable_termination_summary
        self.termination_summary_prompt: str | None = termination_summary_prompt

    @property
    def id(self) -> str:
        """Unique identifier for the agent."""
        return self._id

    @property
    def runnable_type(self) -> RunnableType:
        """Return runnable type identifier."""
        return RunnableType.AGENT

    async def run(
        self,
        user_input: str,
        *,
        context: "ExecutionContext",
        pipeline: "StepPipeline | None" = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> "RunOutput":
        """Execute Agent with Run lifecycle management."""
        # 1. Initialize Pipeline if not provided
        if pipeline is None:
            # Note: We don't pass trace_collector here by default to avoid double collection
            # if run_stream is wrapping the stream.
            pipeline = StepPipeline(context, self.session_store)

        # 2. Use Lifecycle Management
        # We need access to the Lifecycle object to set output.
        lifecycle = RunLifecycle(
            context, pipeline, user_input, self.id, RunnableType.AGENT
        )
        async with lifecycle:
            result = await self._execute_core(
                user_input, context, pipeline, abort_signal
            )
            lifecycle.set_output(result)
            return result

    async def _execute_core(
        self,
        user_input: str,
        context: "ExecutionContext",
        pipeline: "StepPipeline",
        abort_signal: "AbortSignal | None" = None,
    ) -> "RunOutput":
        """Core execution logic."""
        session_id = context.session_id
        config = ExecutionConfig(
            max_steps=self.max_steps,
            enable_termination_summary=self.enable_termination_summary,
            termination_summary_prompt=self.termination_summary_prompt,
        )

        # 1) Handle Sequence & User Step
        seq = await pipeline.allocate_sequence()

        user_step = StepFactory(context).user_step(
            sequence=seq,
            content=user_input,
            runnable_id=self.id,
            runnable_type=RunnableType.AGENT,
        )

        await pipeline.commit_step(user_step)

        # 2) Render Prompt
        rendered_prompt = self._build_system_prompt()

        # 3) Build LLM messages
        if self.session_store:
            messages = await build_context_from_steps(
                session_id,
                self.session_store,
                system_prompt=rendered_prompt,
                runnable_id=self.id,
            )
        else:
            messages = (
                [{"role": "system", "content": rendered_prompt}]
                if rendered_prompt
                else []
            )

        # 4) Execute
        return await AgentExecutor(
            model=self.model,
            tools=self.tools,
            pipeline=pipeline,
            config=config,
            permission_manager=self.permission_manager,
        ).execute(messages=messages, context=context, abort_signal=abort_signal)

    def _build_system_prompt(self) -> str:
        prompt_context = {
            "work_dir": os.getcwd(),
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        }
        parts: list[str] = []
        base_prompt = renderer.render(self.system_prompt or "", **prompt_context)
        if base_prompt:
            parts.append(base_prompt)

        if self.skill_manager:
            skills_section = self.skill_manager.render_skills_section()
            if skills_section:
                parts.append(skills_section)

        return "\n\n".join(parts)

    def _build_execution_context(
        self,
        run_id: str,
        session_id: str,
        wire: Wire,
        user_id: str | None = None,
        metadata: dict | None = None,
    ) -> ExecutionContext:
        """Internal helper to build ExecutionContext."""
        return ExecutionContext(
            run_id=run_id,
            session_id=session_id,
            wire=wire,
            user_id=user_id or self.user_id,
            runnable_type=RunnableType.AGENT,
            runnable_id=self.id,
            metadata=metadata or {},
        )

    async def run_stream(
        self,
        user_input: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        trace_store: "TraceStore | None" = None,
        cleanup_timeout: float = 5.0,
    ) -> AsyncIterator[StepEvent]:
        """
        Streaming execution - creates Wire internally and yields events.

        This is the primary entry point for top-level execution.
        Wire and ExecutionContext are created internally.
        """
        run_id = str(uuid4())
        session_id = session_id or str(uuid4())
        wire = Wire()

        context = self._build_execution_context(
            run_id, session_id, wire, user_id, metadata
        )

        pipeline = StepPipeline(context, self.session_store)

        async def _run_task():
            try:
                await self.run(user_input, context=context, pipeline=pipeline)
            except Exception as e:
                logger.exception(
                    "run_stream_failed",
                    run_id=run_id,
                    agent_id=self.id,
                    error=str(e),
                    exc_info=True,
                )
                raise

        # Prepare event stream
        event_stream = wire.read()
        if trace_store:
            collector = TraceCollector(store=trace_store)
            # Use wrap_stream (Pull Mode) for now to ensure we catch all events,
            # including those from AgentExecutor which might not use Pipeline yet.
            event_stream = collector.wrap_stream(
                event_stream,
                agent_id=self.id,
                session_id=session_id,
                user_id=user_id,
                input_query=user_input,
            )

        # Start execution task
        async def _run_and_close():
            """Run task and close wire when done."""
            try:
                await _run_task()
            finally:
                # Close wire immediately after task completes
                # This signals the event stream to stop
                await wire.close()

        # Execute and stream events
        task = asyncio.create_task(_run_and_close())
        try:
            async for event in event_stream:
                yield event
        finally:
            # Wait for task to complete if still running
            if not task.done():
                try:
                    async with asyncio.timeout(cleanup_timeout):
                        await task
                except asyncio.TimeoutError:
                    logger.warning(
                        "run_stream_cleanup_timeout",
                        agent_id=self.id,
                        timeout=cleanup_timeout,
                    )
                    task.cancel()


__all__ = ["Agent"]
