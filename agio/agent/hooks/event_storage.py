from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun, AgentRunStep
from agio.domain.tools import ToolResult
from agio.domain.messages import Message
from agio.db.repository import AgentRunRepository
from agio.utils.logger import log_debug, log_error


class EventStorageHook(AgentHook):
    """
    事件存储 Hook。
    将 Run 和事件持久化到存储。
    
    注意：这个 Hook 不再使用，被 AgentRunner 直接集成的事件存储替代。
    保留用于向后兼容。
    """
    
    def __init__(self, repository: AgentRunRepository):
        self.repository = repository
    
    async def on_run_start(self, run: AgentRun) -> None:
        try:
            await self.repository.save_run(run)
            log_debug(f"Saved run start: {run.id}")
        except Exception as e:
            log_error(f"Failed to save run start: {e}")
    
    async def on_run_end(self, run: AgentRun) -> None:
        try:
            await self.repository.save_run(run)
            log_debug(f"Saved run end: {run.id}")
        except Exception as e:
            log_error(f"Failed to save run end: {e}")
