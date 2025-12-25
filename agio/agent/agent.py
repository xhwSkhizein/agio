"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
Implements the Runnable protocol for multi-agent orchestration.

Wire-based Architecture:
- Wire is created at API entry point
- Agent.run() writes events to wire, returns RunOutput
- All nested executions share the same wire
"""

from agio.domain import AgentSession
from agio.runtime.step_factory import StepFactory
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime.protocol import RunOutput
from agio.config import ExecutionConfig
from agio.agent.context import build_context_from_steps
from agio.agent.executor import AgentExecutor
from agio.providers.llm import Model
from agio.storage.session.base import SessionStore
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
        permission_manager=None,
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
        self.permission_manager = permission_manager
        self.user_id = user_id
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.enable_termination_summary = enable_termination_summary
        self.termination_summary_prompt = termination_summary_prompt
        self._sequence_manager = None

    @property
    def id(self) -> str:
        """Unique identifier for the agent."""
        return self._id

    @property
    def runnable_type(self) -> str:
        """Return runnable type identifier."""
        return "agent"

    def _get_sequence_manager(self):
        """Get or create sequence manager (internal resource)."""
        if not self.session_store:
            return None

        if self._sequence_manager is None:
            from agio.runtime.sequence_manager import SequenceManager

            self._sequence_manager = SequenceManager(self.session_store)

        return self._sequence_manager

    async def run(
        self,
        input: str,
        *,
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
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

        # Get sequence manager (internal resource)
        seq_mgr = self._get_sequence_manager()

        # 1) Create and save user step
        if seq_mgr:
            seq = await seq_mgr.allocate(session.session_id, context)
        else:
            seq = 1

        sf = StepFactory(context)
        user_step = sf.user_step(
            sequence=seq,
            content=input,
            runnable_id=self.id,
            runnable_type="agent",
        )

        if self.session_store:
            await self.session_store.save_step(user_step)

        # 2) Build LLM messages
        if self.session_store:
            messages = await build_context_from_steps(
                session.session_id,
                self.session_store,
                system_prompt=self.system_prompt,
                # 移除 run_id=context.run_id，这样才能获取整个 session 的历史
                runnable_id=self.id,  # 保留 runnable_id 用于隔离不同 agent
            )
        else:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})

        # 3) Execute with AgentExecutor (returns RunOutput)
        executor = AgentExecutor(
            model=self.model,
            tools=self.tools or [],
            session_store=self.session_store,
            sequence_manager=seq_mgr,
            config=config,
            permission_manager=self.permission_manager,
        )

        return await executor.execute(
            messages=messages,
            context=context,
            abort_signal=abort_signal,
        )


__all__ = ["Agent"]
