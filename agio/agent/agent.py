"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
Implements the Runnable protocol for multi-agent orchestration.

Wire-based Architecture:
- Wire is created at API entry point
- Agent.run() writes events to wire, returns RunOutput
- All nested executions share the same wire
"""

from agio.domain import AgentSession, ExecutionContext, RunOutput
from agio.config import ExecutionConfig
from agio.agent.runner import AgentRunner
from agio.providers.llm import Model
from agio.providers.storage.base import SessionStore
from agio.providers.tools import BaseTool


class Agent:
    """
    Agent Configuration Container.

    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to AgentRunner.

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
        max_steps: int = 10,
        enable_termination_summary: bool = False,
        termination_summary_prompt: str | None = None,
    ):
        self._id = name
        self.model = model
        self.tools: list[BaseTool] = tools or []
        self.memory = memory
        self.knowledge = knowledge
        self.session_store: SessionStore = session_store
        self.user_id = user_id
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.enable_termination_summary = enable_termination_summary
        self.termination_summary_prompt = termination_summary_prompt

    @property
    def id(self) -> str:
        """Unique identifier for the agent."""
        return self._id

    @property
    def runnable_type(self) -> str:
        """Return runnable type identifier."""
        return "agent"

    async def run(
        self,
        input: str,
        *,
        context: "ExecutionContext",
    ) -> "RunOutput":
        """
        Execute Agent, writing Step events to context.wire.
        
        This is the core execution method. Step events are written to wire,
        which is created and consumed by the API layer.
        
        Note: Run lifecycle events (RUN_STARTED/COMPLETED/FAILED) are handled
        by RunnableExecutor, not here.

        Args:
            input: Input string (user message)
            context: Execution context with wire and run_id (required)

        Returns:
            RunOutput with response and metrics
        """

        # Use context session_id (ExecutionContext guarantees session_id is present)
        session_id = context.session_id
        current_user_id = context.user_id or self.user_id

        session = AgentSession(session_id=session_id, user_id=current_user_id)

        config = ExecutionConfig(
            max_steps=self.max_steps,
            enable_termination_summary=self.enable_termination_summary,
            termination_summary_prompt=self.termination_summary_prompt,
        )

        runner = AgentRunner(
            agent=self,
            config=config,
            session_store=self.session_store,
        )

        # Execute and write Step events to wire, return RunOutput
        return await runner.run(session, input, context.wire, context=context)

    async def get_steps(self, session_id: str):
        """Get all Steps for a Session."""
        if not self.session_store:
            raise ValueError("SessionStore not configured")

        return await self.session_store.get_steps(session_id)

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
