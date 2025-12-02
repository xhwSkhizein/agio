"""
Agent - Top-level agent class.

This is the main entry point for creating and running agents.
"""

import uuid
from typing import AsyncIterator

from agio.domain import AgentSession, StepEvent, StepEventType
from agio.providers.llm import Model
from agio.providers.tools import BaseTool


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
        memory=None,
        knowledge=None,
        repository=None,
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

    async def arun_stream(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[StepEvent]:
        """
        Execute Agent, return StepEvent stream.

        This is the recommended API for full control over the execution flow.
        """
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner

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
        """Get all Steps for a Session."""
        if not self.repository:
            raise ValueError("Repository not configured")

        return await self.repository.get_steps(session_id)

    async def retry_from_sequence(
        self, session_id: str, sequence: int
    ) -> AsyncIterator[StepEvent]:
        """Retry from a specific sequence."""
        from agio.config import ExecutionConfig
        from agio.runtime import StepRunner, retry_from_sequence

        if not self.repository:
            raise ValueError("Repository not configured")

        runner = StepRunner(
            agent=self,
            config=ExecutionConfig(),
            repository=self.repository,
        )

        async for event in retry_from_sequence(
            session_id, sequence, self.repository, runner
        ):
            yield event

    async def fork_session(self, session_id: str, sequence: int) -> str:
        """Fork a session at a specific sequence."""
        from agio.runtime import fork_session

        if not self.repository:
            raise ValueError("Repository not configured")

        return await fork_session(session_id, sequence, self.repository)

    async def list_runs(
        self, user_id: str | None = None, limit: int = 20, offset: int = 0
    ):
        """List historical Runs."""
        if not self.repository:
            raise ValueError("Repository not configured")

        return await self.repository.list_runs(
            user_id=user_id, limit=limit, offset=offset
        )


__all__ = ["Agent"]
