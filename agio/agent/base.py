import uuid
from typing import AsyncIterator

from agio.components.knowledge.base import Knowledge
from agio.components.memory.base import Memory
from agio.components.models.base import Model
from agio.components.tools import BaseTool
from agio.core import AgentSession, StepEvent
from agio.storage.repository import AgentRunRepository


class Agent:
    """
    Agent Configuration Container.
    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to StepRunner.
    """

    def __init__(
        self,
        model: Model,
        tools: list[BaseTool] | None = None,
        memory: Memory | None = None,
        knowledge: Knowledge | None = None,
        repository: AgentRunRepository | None = None,
        name: str = "agio_agent",
        user_id: str | None = None,
        system_prompt: str | None = None,
    ):
        self.id = name
        self.model = model
        self.tools = tools or []
        self.memory = memory
        self.knowledge = knowledge
        self.repository = repository
        self.user_id = user_id
        self.system_prompt = system_prompt

    async def arun(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流。

        This uses the Step-based architecture for zero-conversion context building.
        """
        from agio.core import ExecutionConfig, StepEventType
        from agio.execution.runner import StepRunner

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id

        session = AgentSession(session_id=current_session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            repository=self.repository,
        )

        async for event in runner.run_stream(session, query):
            # Extract text from step deltas
            if event.type == StepEventType.STEP_DELTA and event.delta and event.delta.content:
                yield event.delta.content

    async def arun_stream(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[StepEvent]:
        """
        执行 Agent，返回 StepEvent 流。

        This is the recommended API for full control over the execution flow.
        """
        from agio.core import ExecutionConfig
        from agio.execution.runner import StepRunner

        current_session_id = session_id or str(uuid.uuid4())
        current_user_id = user_id or self.user_id

        session = AgentSession(session_id=current_session_id, user_id=current_user_id)

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            repository=self.repository,
        )

        async for event in runner.run_stream(session, query):
            yield event

    async def get_steps(self, session_id: str):
        """
        获取 Session 的所有 Steps。

        Returns:
            List[Step]: Steps in chronological order
        """
        if not self.repository:
            raise ValueError("Repository not configured")

        return await self.repository.get_steps(session_id)

    async def retry_from_sequence(self, session_id: str, sequence: int) -> AsyncIterator[StepEvent]:
        """
        从指定 sequence 重试。

        Args:
            session_id: Session ID
            sequence: Sequence number to retry from (will delete this and all after)

        Yields:
            StepEvent: Events from retry
        """
        from agio.execution.retry import retry_from_sequence
        from agio.execution.runner import StepRunner, ExecutionConfig

        if not self.repository:
            raise ValueError("Repository not configured")

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            repository=self.repository,
        )

        async for event in retry_from_sequence(session_id, sequence, self.repository, runner):
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

    async def list_runs(self, user_id: str | None = None, limit: int = 20, offset: int = 0):
        """
        列出历史 Runs。
        """
        if not self.repository:
            raise ValueError("Repository not configured")

        return await self.repository.list_runs(user_id=user_id, limit=limit, offset=offset)
