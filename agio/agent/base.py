from typing import AsyncIterator
import uuid

from agio.models.base import Model
from agio.tools.base import Tool
from agio.memory.base import Memory
from agio.knowledge.base import Knowledge
from agio.db.base import Storage
from agio.agent.hooks.base import AgentHook
from agio.agent.hooks.storage import StorageHook
from agio.agent.hooks.logging import LoggingHook
from agio.sessions.base import AgentSession

from agio.protocol.events import AgentEvent  # DEPRECATED
from agio.protocol.step_events import StepEvent  # NEW
from agio.db.repository import AgentRunRepository

class Agent:
    """
    Agent Configuration Container.
    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to AgentRunner or StepRunner.
    """
    def __init__(
        self,
        model: Model,
        tools: list[Tool] = [],
        memory: Memory | None = None,
        knowledge: Knowledge | None = None,
        storage: Storage | None = None,
        repository: AgentRunRepository | None = None,
        hooks: list[AgentHook] | None = None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
    ):
        self.id = name
        self.model = model
        self.tools = tools
        self.memory = memory
        self.knowledge = knowledge
        self.storage = storage
        self.repository = repository
        self.user_id = user_id
        self.system_prompt = system_prompt

        # Initialize Hooks
        self.hooks = hooks or []
        if self.storage:
             self.hooks.append(StorageHook(self.storage))
        self.hooks.append(LoggingHook())

    # --- Old API (DEPRECATED - kept for backward compatibility) ---

    async def arun(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流（向后兼容）。

        DEPRECATED: Use arun_step() for new code.
        """
        from agio.runners.base import AgentRunner

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id
        
        session = AgentSession(
            session_id=current_session_id,
            user_id=current_user_id
        )
        
        runner = AgentRunner(agent=self, hooks=self.hooks, repository=self.repository)
        
        async for chunk in runner.run(session, query):
            yield chunk
    
    async def arun_stream(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        """
        执行 Agent，返回事件流（旧 API）。

        DEPRECATED: Use arun_step_stream() for new code.
        """
        from agio.runners.base import AgentRunner

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id
        
        session = AgentSession(
            session_id=current_session_id,
            user_id=current_user_id
        )
        
        runner = AgentRunner(agent=self, hooks=self.hooks, repository=self.repository)
        
        async for event in runner.run_stream(session, query):
            yield event
    
    async def get_run_history(self, run_id: str) -> AsyncIterator[AgentEvent]:
        """
        获取历史 Run 的事件流（回放）。

        DEPRECATED: Use get_session_steps() for new code.
        """
        if not self.repository:
            raise ValueError("Repository not configured")
        
        events = await self.repository.get_events(run_id)
        for event in events:
            yield event

    # --- New Step-based API ---

    async def arun_step(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流（Step-based）。

        This is the new recommended API that uses the Step-based architecture.
        """
        from agio.runners.step_runner import StepRunner, StepRunnerConfig
        from agio.protocol.step_events import StepEventType

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id

        session = AgentSession(session_id=current_session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            hooks=self.hooks,
            config=StepRunnerConfig(),
            repository=self.repository,
        )

        async for event in runner.run_stream(session, query):
            # Extract text from step deltas
            if (
                event.type == StepEventType.STEP_DELTA
                and event.delta
                and event.delta.content
            ):
                yield event.delta.content

    async def arun_step_stream(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[StepEvent]:
        """
        执行 Agent，返回 StepEvent 流（新 API）。

        This is the new recommended API that uses the Step-based architecture.
        """
        from agio.runners.step_runner import StepRunner, StepRunnerConfig

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id

        session = AgentSession(session_id=current_session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            hooks=self.hooks,
            config=StepRunnerConfig(),
            repository=self.repository,
        )

        async for event in runner.run_stream(session, query):
            yield event

    async def get_session_steps(self, session_id: str):
        """
        获取 Session 的所有 Steps。

        Returns:
            List[Step]: Steps in chronological order
        """
        if not self.repository:
            raise ValueError("Repository not configured")

        return await self.repository.get_steps(session_id)

    async def retry_from_sequence(
        self, session_id: str, sequence: int
    ) -> AsyncIterator[StepEvent]:
        """
        从指定 sequence 重试。

        Args:
            session_id: Session ID
            sequence: Sequence number to retry from (will delete this and all after)

        Yields:
            StepEvent: Events from retry
        """
        from agio.execution.retry import retry_from_sequence
        from agio.runners.step_runner import StepRunner, StepRunnerConfig

        if not self.repository:
            raise ValueError("Repository not configured")

        runner = StepRunner(
            agent=self,
            hooks=self.hooks,
            config=StepRunnerConfig(),
            repository=self.repository,
        )

        async for event in retry_from_sequence(
            session_id, sequence, self.repository, runner
        ):
            yield event

    async def fork_session(self, session_id: str, sequence: int) -> str:
        """
        Fork a session at a specific sequence.

        Args:
            session_id: Original session ID
            sequence: Sequence to fork at

        Returns:
            str: New session ID
        """
        from agio.execution.fork import fork_session

        if not self.repository:
            raise ValueError("Repository not configured")

        return await fork_session(session_id, sequence, self.repository)

    # --- Common methods ---

    async def list_runs(
        self, 
        user_id: str | None = None, 
        limit: int = 20, 
        offset: int = 0
    ):
        """
        列出历史 Runs。
        """
        if not self.repository:
            raise ValueError("Repository not configured")
        
        return await self.repository.list_runs(user_id=user_id, limit=limit, offset=offset)

