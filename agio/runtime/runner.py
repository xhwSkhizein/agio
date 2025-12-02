"""
StepRunner - Step-based Agent Runner

Responsibilities:
- Manage Run lifecycle
- Use StepExecutor for execution
- Save Steps to repository
- Save Run metadata at run_end
- Provide resume methods for retry
"""

import asyncio
import time
from typing import TYPE_CHECKING, AsyncIterator
from uuid import uuid4

from agio.domain import (
    AgentRun,
    AgentRunMetrics,
    AgentSession,
    MessageRole,
    RunStatus,
    Step,
    StepEvent,
    StepEventType,
    create_run_completed_event,
    create_run_failed_event,
    create_run_started_event,
)
from agio.domain.adapters import StepAdapter
from agio.runtime.control import AbortSignal
from agio.runtime.context import build_context_from_steps
from agio.runtime.executor import StepExecutor
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.agent import Agent
    from agio.providers.storage import AgentRunRepository
    from agio.config import ExecutionConfig

logger = get_logger(__name__)


class StepRunner:
    """
    Step-based Agent Runner.

    Key improvements:
    1. Uses StepExecutor instead of AgentExecutor
    2. Saves Steps to repository
    3. Uses build_context_from_steps for context building
    4. Provides resume methods for retry
    """

    def __init__(
        self,
        agent: "Agent",
        config: "ExecutionConfig | None" = None,
        repository: "AgentRunRepository | None" = None,
    ):
        """
        Initialize Runner.

        Args:
            agent: Agent instance
            config: Run configuration
            repository: Repository for saving steps
        """
        self.agent = agent
        self.repository = repository
        
        # Import here to avoid circular dependency
        from agio.config import ExecutionConfig
        self.config = config or ExecutionConfig()

    async def run_stream(
        self,
        session: AgentSession,
        query: str,
        abort_signal: AbortSignal | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute Agent, return StepEvent stream.

        Args:
            session: Session
            query: User query
            abort_signal: Abort signal (created and managed by caller)

        Yields:
            StepEvent: Step event stream
        """
        # 1. Create Run
        run = AgentRun(
            id=str(uuid4()),
            agent_id=self.agent.id,
            user_id=session.user_id,
            session_id=session.session_id,
            input_query=query,
            status=RunStatus.STARTING,
        )
        run.metrics.start_time = time.time()
        
        logger.info("run_started", run_id=run.id, session_id=session.session_id, query=query)

        # 2. Send Run started event
        yield create_run_started_event(run_id=run.id, query=query)

        # 3. Create User Step
        user_step = Step(
            id=str(uuid4()),
            session_id=session.session_id,
            run_id=run.id,
            sequence=await self._get_next_sequence(session.session_id),
            role=MessageRole.USER,
            content=query,
        )

        if self.repository:
            await self.repository.save_step(user_step)

        # 4. Build context
        if self.repository:
            messages = await build_context_from_steps(
                session.session_id, self.repository, system_prompt=self.agent.system_prompt
            )
        else:
            messages = []
            if self.agent.system_prompt:
                messages.append({"role": "system", "content": self.agent.system_prompt})
            messages.append(StepAdapter.to_llm_message(user_step))

        run.status = RunStatus.RUNNING

        # 5. Create StepExecutor
        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        # Track metrics
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0
        tool_calls_count = 0
        assistant_steps_count = 0
        last_assistant_had_tools = False

        try:
            # 6. Consume StepExecutor event stream
            start_sequence = user_step.sequence + 1

            async for event in executor.execute(
                session_id=session.session_id,
                run_id=run.id,
                messages=messages,
                start_sequence=start_sequence,
                abort_signal=abort_signal,
            ):
                if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                    step = event.snapshot

                    if self.repository:
                        await self.repository.save_step(step)

                    if step.metrics:
                        if step.metrics.total_tokens:
                            total_tokens += step.metrics.total_tokens
                        if step.metrics.input_tokens:
                            prompt_tokens += step.metrics.input_tokens
                        if step.metrics.output_tokens:
                            completion_tokens += step.metrics.output_tokens

                    if step.is_assistant_step():
                        assistant_steps_count += 1
                        last_assistant_had_tools = step.has_tool_calls()
                        if step.has_tool_calls():
                            tool_calls_count += len(step.tool_calls or [])

                yield event

            # 7. Complete
            run.status = RunStatus.COMPLETED
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time
            run.metrics.total_tokens = total_tokens
            run.metrics.prompt_tokens = prompt_tokens
            run.metrics.completion_tokens = completion_tokens
            run.metrics.tool_calls_count = tool_calls_count

            if messages:
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        run.response_content = msg["content"]
                        break
            
            termination_reason = None
            if last_assistant_had_tools and assistant_steps_count >= self.config.max_steps:
                termination_reason = "max_steps"
            
            logger.info(
                "run_completed",
                run_id=run.id,
                duration=run.metrics.duration,
                tokens=run.metrics.total_tokens,
                tool_calls=run.metrics.tool_calls_count,
                termination_reason=termination_reason,
            )

            yield create_run_completed_event(
                run_id=run.id,
                response=run.response_content or "",
                metrics={
                    "duration": run.metrics.duration,
                    "tool_calls_count": run.metrics.tool_calls_count,
                    "total_tokens": run.metrics.total_tokens,
                },
                termination_reason=termination_reason,
                max_steps=self.config.max_steps if termination_reason else None,
            )

            if self.repository:
                await self.repository.save_run(run)
                logger.debug("run_saved", run_id=run.id)

        except asyncio.CancelledError:
            reason = abort_signal.reason if abort_signal else "Unknown reason"
            logger.info("run_cancelled", run_id=run.id, reason=reason)
            run.status = RunStatus.FAILED
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time
            
            if self.repository:
                await self.repository.save_run(run)

            yield create_run_failed_event(run_id=run.id, error=f"Run was cancelled: {reason}")

        except Exception as e:
            logger.error("run_failed", run_id=run.id, error=str(e), exc_info=True)
            run.status = RunStatus.FAILED
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time
            
            if self.repository:
                await self.repository.save_run(run)

            yield create_run_failed_event(run_id=run.id, error=str(e))
            raise e

    async def _get_next_sequence(self, session_id: str) -> int:
        """Get next sequence number."""
        if not self.repository:
            return 1

        last_step = await self.repository.get_last_step(session_id)
        if last_step:
            return last_step.sequence + 1
        return 1

    # --- Resume methods for retry ---

    async def resume_from_user_step(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume from a user step (most common retry case)."""
        logger.info("resuming_from_user_step", session_id=session_id, step_id=last_step.id)

        if self.repository:
            messages = await build_context_from_steps(
                session_id, self.repository, system_prompt=self.agent.system_prompt
            )
        else:
            raise ValueError("Repository required for resume")

        run_id = str(uuid4())

        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        start_sequence = last_step.sequence + 1

        async for event in executor.execute(
            session_id=session_id, run_id=run_id, messages=messages, start_sequence=start_sequence
        ):
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                if self.repository:
                    await self.repository.save_step(event.snapshot)

            yield event

    async def resume_from_tool_step(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume from a tool step."""
        async for event in self.resume_from_user_step(session_id, last_step):
            yield event

    async def resume_from_assistant_with_tools(
        self, session_id: str, last_step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume from an assistant step that has tool calls."""
        logger.info(
            "resuming_from_assistant_with_tools", session_id=session_id, step_id=last_step.id
        )

        if self.repository:
            messages = await build_context_from_steps(
                session_id, self.repository, system_prompt=self.agent.system_prompt
            )
        else:
            raise ValueError("Repository required for resume")

        run_id = str(uuid4())

        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        start_sequence = last_step.sequence + 1

        async for event in executor.execute(
            session_id=session_id, run_id=run_id, messages=messages, start_sequence=start_sequence
        ):
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                if self.repository:
                    await self.repository.save_step(event.snapshot)

            yield event


__all__ = ["StepRunner"]
