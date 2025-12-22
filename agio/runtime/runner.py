"""
StepRunner - Step-based Agent Runner

Responsibilities:
- Manage Step lifecycle (NOT Run lifecycle - handled by RunnableExecutor)
- Use StepExecutor for execution
- Write Step events to Wire (event streaming channel)
- Save Steps to repository
- Return RunOutput with metrics

Wire-based Architecture:
- Wire is created at API entry point
- All events are written to Wire
- Nested executions share the same Wire

Note: Run lifecycle (create/save Run, emit RUN_STARTED/COMPLETED events)
is handled by RunnableExecutor, not StepRunner.
"""

import asyncio
import time
from typing import TYPE_CHECKING, NamedTuple
from uuid import uuid4

from agio.domain import (
    AgentSession,
    MessageRole,
    Step,
    StepEventType,
)
from agio.domain.adapters import StepAdapter
from agio.observability.tracker import set_tracking_context, clear_tracking_context
from agio.runtime.control import AbortSignal
from agio.runtime.context import build_context_from_steps
from agio.domain import ExecutionContext
from agio.runtime.event_factory import EventFactory
from agio.runtime.executor import StepExecutor
from agio.runtime.wire import Wire
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.agent import Agent
    from agio.providers.storage import SessionStore
    from agio.config import ExecutionConfig
    from agio.domain.protocol import RunOutput


logger = get_logger(__name__)


class TerminationSummaryResult(NamedTuple):
    """Result from termination summary generation."""

    summary: str
    tokens_used: int
    prompt_tokens_used: int
    completion_tokens_used: int


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
        session_store: "SessionStore | None" = None,
    ):
        """
        Initialize Runner.

        Args:
            agent: Agent instance
            config: Run configuration
            session_store: SessionStore for saving steps
        """
        self.agent = agent
        self.session_store = session_store

        # Import here to avoid circular dependency
        from agio.config import ExecutionConfig

        self.config = config or ExecutionConfig()

    async def run(
        self,
        session: AgentSession,
        query: str,
        wire: Wire,
        abort_signal: AbortSignal | None = None,
        context: "ExecutionContext | None" = None,
    ) -> "RunOutput":
        """
        Execute Agent, writing Step events to Wire.

        Wire is created at API entry point and passed here.
        Step events are written to wire, which is consumed by API layer.

        Note: Run lifecycle (RUN_STARTED/COMPLETED/FAILED events) is handled
        by RunnableExecutor, not here.

        Args:
            session: Session
            query: User query
            wire: Event streaming channel (created by API layer)
            abort_signal: Abort signal
            context: Execution context (required, contains run_id from RunnableExecutor)

        Returns:
            RunOutput with response and metrics
        """
        from agio.workflow.protocol import RunOutput, RunMetrics

        if context is None:
            raise ValueError("ExecutionContext is required (must contain run_id)")

        # Use run_id from context (created by RunnableExecutor)
        run_id = context.run_id
        start_time = time.time()

        # Set tracking context for LLM call logging
        set_tracking_context(
            agent_name=self.agent.id,
            session_id=session.session_id,
            run_id=run_id,
        )

        # Create EventFactory for simplified event creation
        ef = EventFactory(context)

        logger.info(
            "step_runner_started",
            run_id=run_id,
            session_id=session.session_id,
            query=query,
            depth=context.depth,
            parent_run_id=context.parent_run_id,
        )

        # 1. Create User Step
        user_step = Step(
            id=str(uuid4()),
            session_id=session.session_id,
            run_id=run_id,
            sequence=await self._get_next_sequence(session.session_id),
            role=MessageRole.USER,
            content=query,
            # Extract metadata from ExecutionContext
            workflow_id=context.workflow_id,
            node_id=context.node_id,
            parent_run_id=context.parent_run_id,
            branch_key=context.metadata.get("branch_key"),
            iteration=context.iteration,
        )

        if self.session_store:
            await self.session_store.save_step(user_step)

        # 2. Build context - filter by run_id to isolate agent context
        if self.session_store:
            messages = await build_context_from_steps(
                session.session_id,
                self.session_store,
                system_prompt=self.agent.system_prompt,
                run_id=run_id,  # Only load Steps for this run_id
            )
        else:
            messages = []
            if self.agent.system_prompt:
                messages.append({"role": "system", "content": self.agent.system_prompt})
            messages.append(StepAdapter.to_llm_message(user_step))

        # 3. Create StepExecutor with Wire
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
        pending_tool_calls: list[dict] | None = None  # Track unprocessed tool calls
        last_step_sequence = user_step.sequence  # Track last sequence for summary generation

        response_content = None
        termination_reason = None

        try:
            # 4. Execute with Wire - events written directly to wire
            start_sequence = user_step.sequence + 1

            async for event in executor.execute(
                messages=messages,
                ctx=context,
                start_sequence=start_sequence,
                abort_signal=abort_signal,
            ):
                # Write event to wire
                await wire.write(event)
                # handle Completed event
                if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                    step = event.snapshot

                    if self.session_store:
                        await self.session_store.save_step(step)

                    # Track last sequence
                    last_step_sequence = step.sequence

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
                            # Track pending tool calls (will be cleared if tool results follow)
                            pending_tool_calls = step.tool_calls
                    elif step.role.value == "tool":
                        # Tool result received, clear pending
                        pending_tool_calls = None

            # 5. Complete - extract response from messages
            if messages:
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        response_content = msg["content"]
                        break

            if last_assistant_had_tools and assistant_steps_count >= self.config.max_steps:
                termination_reason = "max_steps"

            # Generate termination summary if configured and there's a termination reason
            if termination_reason and self.config.enable_termination_summary:
                summary_result = await self._generate_termination_summary(
                    session=session,
                    run_id=run_id,
                    messages=messages,
                    termination_reason=termination_reason,
                    pending_tool_calls=pending_tool_calls,
                    wire=wire,
                    current_sequence=last_step_sequence,
                )
                response_content = summary_result.summary
                # Update metrics from summary generation
                total_tokens += summary_result.tokens_used
                prompt_tokens += summary_result.prompt_tokens_used
                completion_tokens += summary_result.completion_tokens_used

            # Calculate duration
            end_time = time.time()
            duration = end_time - start_time

            logger.info(
                "step_runner_completed",
                run_id=run_id,
                duration=duration,
                tokens=total_tokens,
                tool_calls=tool_calls_count,
                termination_reason=termination_reason,
            )

            # Return RunOutput with metrics (Run events handled by RunnableExecutor)
            return RunOutput(
                response=response_content,
                run_id=run_id,
                session_id=session.session_id,
                metrics=RunMetrics(
                    duration=duration,
                    total_tokens=total_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    tool_calls_count=tool_calls_count,
                ),
                termination_reason=termination_reason,
            )

        except asyncio.CancelledError:
            reason = abort_signal.reason if abort_signal else "Unknown reason"
            logger.info("step_runner_cancelled", run_id=run_id, reason=reason)
            # Re-raise - RunnableExecutor will handle the Run failure
            raise

        except Exception as e:
            logger.error("step_runner_failed", run_id=run_id, error=str(e), exc_info=True)
            # Re-raise - RunnableExecutor will handle the Run failure
            raise
        finally:
            clear_tracking_context()

    async def _get_next_sequence(self, session_id: str) -> int:
        """Get next sequence number."""
        if not self.session_store:
            return 1

        last_step = await self.session_store.get_last_step(session_id)
        if last_step:
            return last_step.sequence + 1
        return 1

    async def _generate_termination_summary(
        self,
        session: AgentSession,
        run_id: str,
        messages: list[dict],
        termination_reason: str,
        pending_tool_calls: list[dict] | None,
        wire: Wire,
        current_sequence: int,
    ) -> TerminationSummaryResult:
        """
        Generate summary when execution is terminated.

        This continues the conversation by appending appropriate messages,
        saves the new steps, and sends wire events.

        Args:
            session: Current session
            run_id: Run ID
            messages: Conversation history
            termination_reason: Reason for termination
            pending_tool_calls: Unprocessed tool calls if any
            wire: Wire for event streaming
            current_sequence: Current sequence number

        Returns:
            TerminationSummaryResult with summary and metrics
        """
        from agio.domain.models import Step, MessageRole, StepMetrics
        from agio.domain.events import StepEvent, StepEventType

        next_sequence = current_sequence + 1
        tokens_used = 0
        prompt_tokens_used = 0
        completion_tokens_used = 0

        # 1. Add placeholder tool results if needed
        if pending_tool_calls:
            for tool_call in pending_tool_calls:
                call_id = tool_call.get("id", "unknown")
                tool_name = tool_call.get("function", {}).get("name", "unknown")

                tool_step = Step(
                    session_id=session.session_id,
                    run_id=run_id,
                    sequence=next_sequence,
                    role=MessageRole.TOOL,
                    tool_call_id=call_id,
                    name=tool_name,
                    content=f"[Execution interrupted: {termination_reason}. This tool call was not executed.]",
                )

                if self.session_store:
                    await self.session_store.save_step(tool_step)

                await wire.write(
                    StepEvent(
                        type=StepEventType.STEP_COMPLETED,
                        run_id=run_id,
                        snapshot=tool_step,
                    )
                )

                next_sequence += 1

        # 2. Add user message requesting summary
        from agio.runtime.summarizer import (
            DEFAULT_TERMINATION_USER_PROMPT,
            _format_termination_reason,
        )

        prompt_template = self.config.termination_summary_prompt or DEFAULT_TERMINATION_USER_PROMPT
        user_prompt = prompt_template.format(
            termination_reason=_format_termination_reason(termination_reason),
        )

        user_step = Step(
            session_id=session.session_id,
            run_id=run_id,
            sequence=next_sequence,
            role=MessageRole.USER,
            content=user_prompt,
        )

        if self.session_store:
            await self.session_store.save_step(user_step)

        await wire.write(
            StepEvent(
                type=StepEventType.STEP_COMPLETED,
                run_id=run_id,
                snapshot=user_step,
            )
        )

        next_sequence += 1

        # 3. Generate summary via LLM
        summary_messages = list(messages)

        # Add placeholder tool results to messages
        if pending_tool_calls:
            for tool_call in pending_tool_calls:
                call_id = tool_call.get("id", "unknown")
                tool_name = tool_call.get("function", {}).get("name", "unknown")
                summary_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": f"[Execution interrupted: {termination_reason}. This tool call was not executed.]",
                    }
                )

        # Add user summary request
        summary_messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        logger.debug(
            "generating_termination_summary",
            termination_reason=termination_reason,
            message_count=len(summary_messages),
            has_pending_tool_calls=bool(pending_tool_calls),
        )

        try:
            # Call LLM via streaming and collect full response
            tool_schemas = [t.to_openai_schema() for t in self.agent.tools] if self.agent.tools else None
            summary = ""
            usage_data = None

            async for chunk in self.agent.model.arun_stream(summary_messages, tools=tool_schemas):
                if chunk.content:
                    summary += chunk.content
                if chunk.usage:
                    usage_data = chunk.usage

            # Track token usage
            if usage_data:
                tokens_used = usage_data.get("total_tokens", 0)
                prompt_tokens_used = usage_data.get("prompt_tokens", 0)
                completion_tokens_used = usage_data.get("completion_tokens", 0)

            logger.info(
                "termination_summary_generated",
                termination_reason=termination_reason,
                summary_length=len(summary),
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(
                "termination_summary_failed",
                error=str(e),
                exc_info=True,
            )
            # Fallback summary
            summary = (
                f"**Execution Interrupted**\n\n"
                f"Terminated due to: {_format_termination_reason(termination_reason)}\n\n"
                f"Note: Unable to generate detailed summary due to: {str(e)}"
            )

        # 4. Save assistant response step
        assistant_step = Step(
            session_id=session.session_id,
            run_id=run_id,
            sequence=next_sequence,
            role=MessageRole.ASSISTANT,
            content=summary,
            metrics=(
                StepMetrics(
                    total_tokens=tokens_used,
                    input_tokens=prompt_tokens_used,
                    output_tokens=completion_tokens_used,
                )
                if tokens_used > 0
                else None
            ),
        )

        if self.session_store:
            await self.session_store.save_step(assistant_step)

        await wire.write(
            StepEvent(
                type=StepEventType.STEP_COMPLETED,
                run_id=run_id,
                snapshot=assistant_step,
            )
        )

        return TerminationSummaryResult(
            summary=summary,
            tokens_used=tokens_used,
            prompt_tokens_used=prompt_tokens_used,
            completion_tokens_used=completion_tokens_used,
        )

    # --- Resume methods ---

    async def resume_from_user_step(
        self,
        session_id: str,
        last_step: Step,
        wire: Wire,
        context: "ExecutionContext",
    ) -> "RunOutput":
        """
        Resume execution from a user step.
        
        Note: Run lifecycle (RUN_STARTED/COMPLETED/FAILED events) is handled
        by RunnableExecutor, not here. This method only manages Steps.
        
        Args:
            session_id: Session ID
            last_step: Last step to resume from
            wire: Event streaming channel
            context: Execution context (required, contains run_id from RunnableExecutor)
            
        Returns:
            RunOutput with response and metrics
        """
        from agio.workflow.protocol import RunOutput, RunMetrics

        logger.info(
            "resuming_from_user_step",
            session_id=session_id,
            step_id=last_step.id,
            run_id=context.run_id,
        )

        if not self.session_store:
            raise ValueError("SessionStore required for resume")

        start_time = time.time()
        run_id = context.run_id

        messages = await build_context_from_steps(
            session_id,
            self.session_store,
            system_prompt=self.agent.system_prompt,
            run_id=run_id,
        )

        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        start_sequence = last_step.sequence + 1
        response_content = None
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0

        async for event in executor.execute(
            messages=messages,
            ctx=context,
            start_sequence=start_sequence,
        ):
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                step = event.snapshot
                await self.session_store.save_step(step)
                if step.metrics:
                    total_tokens += step.metrics.total_tokens or 0
                    prompt_tokens += step.metrics.input_tokens or 0
                    completion_tokens += step.metrics.output_tokens or 0
            await wire.write(event)

        # Get response from messages
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                response_content = msg["content"]
                break

        duration = time.time() - start_time

        return RunOutput(
            response=response_content,
            run_id=run_id,
            session_id=session_id,
            metrics=RunMetrics(
                duration=duration,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

    async def resume_from_tool_step(
        self,
        session_id: str,
        last_step: Step,
        wire: Wire,
        context: "ExecutionContext",
    ) -> "RunOutput":
        """Resume from a tool step."""
        return await self.resume_from_user_step(session_id, last_step, wire, context)

    async def resume_from_assistant_with_tools(
        self,
        session_id: str,
        last_step: Step,
        wire: Wire,
        context: "ExecutionContext",
    ) -> "RunOutput":
        """
        Resume execution from an assistant step that has pending tool calls.
        
        Note: Run lifecycle (RUN_STARTED/COMPLETED/FAILED events) is handled
        by RunnableExecutor, not here. This method only manages Steps.
        
        Args:
            session_id: Session ID
            last_step: Last step with tool calls to resume from
            wire: Event streaming channel
            context: Execution context (required, contains run_id from RunnableExecutor)
            
        Returns:
            RunOutput with response and metrics
        """
        from agio.workflow.protocol import RunOutput, RunMetrics

        logger.info(
            "resuming_from_assistant_with_tools",
            session_id=session_id,
            step_id=last_step.id,
            run_id=context.run_id,
        )

        if not self.session_store:
            raise ValueError("SessionStore required for resume")

        start_time = time.time()
        run_id = context.run_id

        messages = await build_context_from_steps(
            session_id,
            self.session_store,
            system_prompt=self.agent.system_prompt,
            run_id=run_id,
        )

        executor = StepExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        start_sequence = last_step.sequence + 1
        response_content = None
        total_tokens = 0
        prompt_tokens = 0
        completion_tokens = 0

        async for event in executor.execute(
            messages=messages,
            ctx=context,
            start_sequence=start_sequence,
            pending_tool_calls=last_step.tool_calls,
        ):
            if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                step = event.snapshot
                await self.session_store.save_step(step)
                if step.metrics:
                    total_tokens += step.metrics.total_tokens or 0
                    prompt_tokens += step.metrics.input_tokens or 0
                    completion_tokens += step.metrics.output_tokens or 0
            await wire.write(event)

        # Get response from messages
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                response_content = msg["content"]
                break

        duration = time.time() - start_time

        return RunOutput(
            response=response_content,
            run_id=run_id,
            session_id=session_id,
            metrics=RunMetrics(
                duration=duration,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )


__all__ = ["StepRunner"]
