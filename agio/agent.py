"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
Implements the Runnable protocol for multi-agent orchestration.

Wire-based Architecture:
- Wire is created at API entry point
- Agent.run() writes events to wire, returns RunOutput
- All nested executions share the same wire
"""

import uuid
from typing import TYPE_CHECKING

from agio.domain import AgentSession
from agio.domain.models import Step
from agio.providers.llm import Model
from agio.providers.storage.base import SessionStore
from agio.providers.tools import BaseTool

if TYPE_CHECKING:
    from agio.workflow.protocol import RunContext, RunOutput
    from agio.runtime.wire import Wire


class Agent:
    """
    Agent Configuration Container.

    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to StepRunner.

    Implements the Runnable protocol for multi-agent orchestration:
    - run(input, context) -> RunOutput (writes events to context.wire)
    """

    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        memory=None,
        knowledge=None,
        session_store=None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
    ):
        self._id = name
        self.model = model
        self.tools = tools or []
        self.memory = memory
        self.knowledge = knowledge
        self.session_store: SessionStore = session_store
        self.user_id = user_id
        self.system_prompt = system_prompt

    @property
    def id(self) -> str:
        """Unique identifier for the agent."""
        return self._id

    async def run(
        self,
        input: str,
        *,
        context: "RunContext",
    ) -> "RunOutput":
        """
        Execute Agent, writing events to context.wire.
        
        This is the core execution method. Events are written to wire,
        which is created and consumed by the API layer.

        Args:
            input: Input string (user message)
            context: Execution context with wire (required)

        Returns:
            RunOutput with response and metrics
        """
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner

        if not context.wire:
            raise ValueError("context.wire is required for Agent.run()")

        # Use context session_id if provided, otherwise create new
        session_id = context.session_id or str(uuid.uuid4())
        current_user_id = context.user_id or self.user_id

        session = AgentSession(session_id=session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            session_store=self.session_store,
        )

        # Execute and write events to wire, return RunOutput
        return await runner.run(session, input, context.wire, context=context)

    async def get_steps(self, session_id: str):
        """Get all Steps for a Session."""
        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await self.session_store.get_steps(session_id)

    async def fork_session(self, session_id: str, sequence: int) -> str:
        """Fork a session at a specific sequence."""
        from agio.runtime import fork_session

        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await fork_session(session_id, sequence, self.session_store)

    async def resume_from_step(
        self, session_id: str, step: Step, wire: "Wire"
    ) -> "RunOutput":
        """
        Resume execution from a specific step.
        
        Args:
            session_id: Session ID
            step: Step to resume from
            wire: Wire for event streaming
            
        Returns:
            RunOutput with response and metrics
        """
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
            return await runner.resume_from_assistant_with_tools(session_id, step, wire)
        elif step.role.value == "user":
            return await runner.resume_from_user_step(session_id, step, wire)
        elif step.role.value == "tool":
            return await runner.resume_from_tool_step(session_id, step, wire)
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
