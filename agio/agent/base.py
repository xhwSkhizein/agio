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

from agio.protocol.events import AgentEvent
from agio.db.repository import AgentRunRepository

class Agent:
    """
    Agent Configuration Container.
    Holds the configuration for Model, Tools, Memory, etc.
    Delegates execution to AgentRunner.
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
    async def arun(
        self, query: str, user_id: str | None = None, session_id: str | None = None
    ) -> AsyncIterator[str]:
        """
        执行 Agent，返回文本流（向后兼容）。
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
        执行 Agent，返回事件流（新 API）。
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
        """
        if not self.repository:
            raise ValueError("Repository not configured")
        
        events = await self.repository.get_events(run_id)
        for event in events:
            yield event
    
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
