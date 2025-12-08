"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
Implements the Runnable protocol for multi-agent orchestration.
"""

import uuid
from typing import TYPE_CHECKING, AsyncIterator

from agio.domain import AgentSession, StepEvent, StepEventType
from agio.domain.models import Step
from agio.providers.llm import Model
from agio.providers.tools import BaseTool

if TYPE_CHECKING:
    from agio.workflow.protocol import RunContext


class Agent:
    """
    Agent Configuration Container.

    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to StepRunner.

    Implements the Runnable protocol for multi-agent orchestration:
    - run(input, context) -> AsyncIterator[StepEvent]
    - last_output property
    """

    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        memory=None,
        knowledge=None,
        session_store=None,
        trace_store=None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
    ):
        self._id = name
        self.model = model
        self.tools = tools or []
        self.memory = memory
        self.knowledge = knowledge
        self.session_store = session_store
        self.trace_store = trace_store
        self.user_id = user_id
        self.system_prompt = system_prompt
        self._last_output: str | None = None

    @property
    def id(self) -> str:
        """Unique identifier for the agent."""
        return self._id

    @property
    def last_output(self) -> str | None:
        """Get the final output of the most recent execution."""
        return self._last_output

    async def run(
        self,
        input: str,
        *,
        context: "RunContext | None" = None,
        enable_tracing: bool = True,
    ) -> AsyncIterator[StepEvent]:
        """
        Runnable protocol implementation.

        Executes the agent with the given input and returns an event stream.

        Args:
            input: Input string (user message)
            context: Optional execution context with session info
            enable_tracing: Enable distributed tracing (default: True)

        Yields:
            StepEvent: Events during execution
        """
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner
        from agio.observability import TraceCollector, get_otlp_exporter

        self._last_output = None

        # Use context session_id if provided, otherwise create new
        if context:
            session_id = context.session_id or str(uuid.uuid4())
            current_user_id = context.user_id or self.user_id
            trace_id = context.trace_id
        else:
            session_id = str(uuid.uuid4())
            current_user_id = self.user_id
            trace_id = None

        session = AgentSession(session_id=session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
        )

        # Create event stream
        event_stream = runner.run_stream(session, input, context=context)

        # Wrap with TraceCollector if tracing is enabled and trace_store is configured
        if enable_tracing and self.trace_store:
            try:
                collector = TraceCollector(store=self.trace_store)
                event_stream = collector.wrap_stream(
                    event_stream,
                    trace_id=trace_id,
                    agent_id=self._id,
                    session_id=session_id,
                    user_id=current_user_id,
                    input_query=input,
                )
                # Export to OTLP after completion (async)
                # Note: Export happens in TraceCollector.wrap_stream's finally block
            except Exception as e:
                # If tracing fails, log and continue without tracing
                from agio.utils.logging import get_logger
                logger = get_logger(__name__)
                logger.warning("trace_collection_failed", error=str(e))

        async for event in event_stream:
            # Add observability context if provided
            if context:
                if context.trace_id:
                    event.trace_id = context.trace_id
                if context.parent_span_id:
                    event.parent_span_id = context.parent_span_id
                event.depth = context.depth

            yield event

            # Track final output
            if event.type == StepEventType.RUN_COMPLETED and event.data:
                self._last_output = event.data.get("response", "")

    async def arun_stream(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[StepEvent]:
        """
        Execute Agent, return StepEvent stream.

        This is the convenience API that wraps run() with session parameters.
        """
        from agio.workflow.protocol import RunContext

        context = RunContext(
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id or self.user_id,
        )

        async for event in self.run(query, context=context):
            yield event

    async def get_steps(self, session_id: str):
        """Get all Steps for a Session."""
        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await self.session_store.get_steps(session_id)

    async def retry_from_sequence(
        self, session_id: str, sequence: int
    ) -> AsyncIterator[StepEvent]:
        """Retry from a specific sequence."""
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner, retry_from_sequence

        if not self.session_store:
            raise ValueError("SessionStore not configured")

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
        )

        async for event in retry_from_sequence(
            session_id, sequence, self.session_store, runner
        ):
            yield event

    async def fork_session(self, session_id: str, sequence: int) -> str:
        """Fork a session at a specific sequence."""
        from agio.runtime import fork_session

        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await fork_session(session_id, sequence, self.session_store)

    async def resume_from_step(
        self, session_id: str, step: Step
    ) -> AsyncIterator[StepEvent]:
        """Resume execution from a specific step (typically assistant with tool_calls)."""
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner

        if not self.session_store:
            raise ValueError("SessionStore not configured")

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
        )

        if step.role.value == "assistant" and step.tool_calls:
            async for event in runner.resume_from_assistant_with_tools(session_id, step):
                yield event
        elif step.role.value == "user":
            async for event in runner.resume_from_user_step(session_id, step):
                yield event
        elif step.role.value == "tool":
            async for event in runner.resume_from_tool_step(session_id, step):
                yield event
        else:
            raise ValueError(f"Cannot resume from step with role: {step.role.value}")

    async def list_runs(
        self, user_id: str | None = None, limit: int = 20, offset: int = 0
    ):
        """List historical Runs."""
        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await self.session_store.list_runs(
            user_id=user_id, limit=limit, offset=offset
        )


__all__ = ["Agent"]
