"""
AgentRunner - Step-based Agent Runner

Responsibilities:
- Manage Step lifecycle (NOT Run lifecycle - handled by RunnableExecutor)
- Use AgentExecutor for execution
- Write Step events to Wire (event streaming channel)
- Save Steps to repository
- Return RunOutput with metrics

Wire-based Architecture:
- Wire is created at API entry point
- All events are written to Wire
- Nested executions share the same Wire

Note: Run lifecycle (create/save Run, emit RUN_STARTED/COMPLETED events)
is handled by RunnableExecutor, not AgentRunner.
"""

import asyncio
import time
from typing import TYPE_CHECKING, NamedTuple

from agio.domain import (
    AgentSession,
    StepEventType,
    RunOutput,
    RunMetrics,
    StepAdapter,
    ExecutionContext,
)

from agio.agent.control import AbortSignal
from agio.agent.context import build_context_from_steps
from agio.agent.executor import AgentExecutor
from agio.runtime.step_factory import StepFactory
from agio.utils.logging import get_logger
from agio.config import ExecutionConfig

if TYPE_CHECKING:
    from agio.agent import Agent
    from agio.providers.storage import SessionStore


logger = get_logger(__name__)


class TerminationSummaryResult(NamedTuple):
    """Result from termination summary generation."""

    summary: str
    tokens_used: int
    input_tokens_used: int
    output_tokens_used: int


class AgentRunner:
    """
    Step-based Agent Runner.

    Key improvements:
    1. Uses AgentExecutor instead of StepExecutor
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
        self.config = config or ExecutionConfig()

    async def run(
        self,
        session: AgentSession,
        query: str,
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

        if context is None:
            raise ValueError("ExecutionContext is required (must contain run_id)")

        # Use run_id from context (created by RunnableExecutor)
        run_id = context.run_id
        start_time = time.time()

        # Create StepFactory for simplified step creation
        sf = StepFactory(context)

        logger.info(
            "step_runner_started",
            run_id=run_id,
            session_id=session.session_id,
            query=query,
            depth=context.depth,
            parent_run_id=context.parent_run_id,
        )

        # 1. Create User Step using StepFactory
        user_sequence = await self._allocate_sequence(session.session_id, context)
        user_step = sf.user_step(
            sequence=user_sequence,
            content=query,
            runnable_id=self.agent.id,
            runnable_type="agent",
        )

        if self.session_store:
            await self.session_store.save_step(user_step)

        # 2. Build context - filter by runnable_id to isolate agent context
        # Query current Agent's Steps and parent Agent's Steps (if exists)
        if self.session_store:
            # Query current Agent's Steps (by runnable_id and run_id)
            messages = await build_context_from_steps(
                session.session_id,
                self.session_store,
                system_prompt=self.agent.system_prompt,
                run_id=run_id,  # Current run's Steps
                runnable_id=self.agent.id,  # Current Agent's Steps
            )

            # If there's a parent_run_id, also query parent Agent's Steps
            if context.parent_run_id:
                parent_messages = await build_context_from_steps(
                    session.session_id,
                    self.session_store,
                    run_id=context.parent_run_id,  # Parent Agent's run_id
                    runnable_id=context.runnable_id,  # Parent Agent's runnable_id
                )
                # Merge and sort by sequence
                all_messages = parent_messages + messages
                # Remove duplicates (by sequence) and sort
                seen_sequences = set()
                unique_messages = []
                for msg in sorted(all_messages, key=lambda m: m.get("_sequence", 0)):
                    seq = msg.get("_sequence")
                    if seq is None or seq not in seen_sequences:
                        seen_sequences.add(seq)
                        unique_messages.append(msg)
                messages = unique_messages
        else:
            messages = []
            if self.agent.system_prompt:
                messages.append({"role": "system", "content": self.agent.system_prompt})
            messages.append(StepAdapter.to_llm_message(user_step))

        # 3. Create AgentExecutor with Wire
        executor = AgentExecutor(
            model=self.agent.model,
            tools=self.agent.tools or [],
            config=self.config,
        )

        # Track metrics
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        tool_calls_count = 0
        assistant_steps_count = 0
        last_assistant_had_tools = False
        pending_tool_calls: list[dict] | None = None  # Track unprocessed tool calls

        response_content = None
        termination_reason = None

        try:
            # 4. Execute with Wire - events written directly to wire
            # Create sequence allocation callback
            async def allocate_seq():
                return await self._allocate_sequence(session.session_id, context)

            async for event in executor.execute(
                messages=messages,
                ctx=context,
                allocate_sequence_fn=allocate_seq,
                abort_signal=abort_signal,
            ):
                # Write event to wire
                await context.wire.write(event)
                # handle Completed event
                if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                    step = event.snapshot

                    if self.session_store:
                        await self.session_store.save_step(step)

                    if step.metrics:
                        if step.metrics.total_tokens:
                            total_tokens += step.metrics.total_tokens
                        if step.metrics.input_tokens:
                            input_tokens += step.metrics.input_tokens
                        if step.metrics.output_tokens:
                            output_tokens += step.metrics.output_tokens

                    if step.is_assistant_step():
                        assistant_steps_count += 1
                        last_assistant_had_tools = step.has_tool_calls()
                        # Extract response content directly from step
                        if step.content:
                            response_content = step.content
                        if step.has_tool_calls():
                            tool_calls_count += len(step.tool_calls or [])
                            # Track pending tool calls (will be cleared if tool results follow)
                            pending_tool_calls = step.tool_calls
                    elif step.role.value == "tool":
                        # Tool result received, clear pending
                        pending_tool_calls = None

            if (
                last_assistant_had_tools
                and assistant_steps_count >= self.config.max_steps
            ):
                termination_reason = "max_steps"

            # Generate termination summary if configured and there's a termination reason
            if termination_reason and self.config.enable_termination_summary:
                summary_result = await self._generate_termination_summary(
                    session=session,
                    run_id=run_id,
                    messages=messages,
                    termination_reason=termination_reason,
                    pending_tool_calls=pending_tool_calls,
                    context=context,
                    abort_signal=abort_signal,
                )
                response_content = summary_result.summary
                # Update metrics from summary generation
                total_tokens += summary_result.tokens_used
                input_tokens += summary_result.input_tokens_used
                output_tokens += summary_result.output_tokens_used

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
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
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
            logger.error(
                "step_runner_failed", run_id=run_id, error=str(e), exc_info=True
            )
            # Re-raise - RunnableExecutor will handle the Run failure
            raise

    async def _allocate_sequence(
        self,
        session_id: str,
        context: ExecutionContext | None = None,
    ) -> int:
        """
        Allocate next sequence number atomically.

        Uses SessionStore.allocate_sequence for atomic allocation.
        Thread-safe and concurrent-safe.

        Args:
            session_id: Session ID
            context: Execution context (optional). If provided and contains seq_start in metadata,
                    uses the pre-allocated sequence for parallel workflow branches.

        Returns:
            Next sequence number
        """
        # For parallel workflow branches, use pre-allocated sequence
        if context and "seq_start" in context.metadata:
            seq_start = context.metadata["seq_start"]
            context.metadata.pop("seq_start")
            return seq_start

        # Use SessionStore's atomic allocation
        if self.session_store:
            return await self.session_store.allocate_sequence(session_id)
        else:
            # Fallback for testing without session store
            return 1

    async def _generate_termination_summary(
        self,
        session: AgentSession,
        run_id: str,
        messages: list[dict],
        termination_reason: str,
        pending_tool_calls: list[dict] | None,
        context: ExecutionContext,
        abort_signal: AbortSignal | None = None,
    ) -> TerminationSummaryResult:
        """
        Generate summary when execution is terminated.

        Uses AgentExecutor to generate the summary, ensuring consistency
        with normal execution flow.

        Args:
            session: Current session
            run_id: Run ID
            messages: Conversation history
            termination_reason: Reason for termination
            pending_tool_calls: Unprocessed tool calls if any
            context: Execution context

        Returns:
            TerminationSummaryResult with summary and metrics
        """
        from agio.agent.summarizer import build_termination_messages

        # 1. Build termination messages using summarizer utility
        summary_messages = build_termination_messages(
            messages=messages,
            termination_reason=termination_reason,
            pending_tool_calls=pending_tool_calls,
            custom_prompt=self.config.termination_summary_prompt,
        )

        logger.debug(
            "generating_termination_summary",
            termination_reason=termination_reason,
            message_count=len(summary_messages),
            has_pending_tool_calls=bool(pending_tool_calls),
        )

        # 2. Create AgentExecutor without tools to avoid recursive tool calls
        executor = AgentExecutor(
            model=self.agent.model,
            tools=[],
            config=self.config,
        )

        # Track metrics
        tokens_used = 0
        input_tokens_used = 0
        output_tokens_used = 0
        summary = ""

        try:
            # 3. Use AgentExecutor to generate summary (reuses all event/step logic)
            # Create sequence allocation callback
            async def allocate_seq():
                return await self._allocate_sequence(session.session_id, context)

            async for event in executor.execute(
                messages=summary_messages,
                ctx=context,
                allocate_sequence_fn=allocate_seq,
                abort_signal=abort_signal,
            ):
                # Write events to wire
                await context.wire.write(event)

                # Save completed steps
                if event.type == StepEventType.STEP_COMPLETED and event.snapshot:
                    step = event.snapshot

                    if self.session_store:
                        await self.session_store.save_step(step)

                    # Track metrics
                    if step.metrics:
                        if step.metrics.total_tokens:
                            tokens_used += step.metrics.total_tokens
                        if step.metrics.input_tokens:
                            input_tokens_used += step.metrics.input_tokens
                        if step.metrics.output_tokens:
                            output_tokens_used += step.metrics.output_tokens

                    # Extract summary from assistant step
                    if step.is_assistant_step() and step.content:
                        summary = step.content

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
            from agio.agent.summarizer import _format_termination_reason

            summary = (
                f"**Execution Interrupted**\n\n"
                f"Terminated due to: {_format_termination_reason(termination_reason)}\n\n"
                f"Note: Unable to generate detailed summary due to: {str(e)}"
            )

        return TerminationSummaryResult(
            summary=summary,
            tokens_used=tokens_used,
            input_tokens_used=input_tokens_used,
            output_tokens_used=output_tokens_used,
        )


__all__ = ["AgentRunner", "TerminationSummaryResult"]
