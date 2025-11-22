from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun
from agio.db.repository import AgentRunRepository
from agio.utils.logging import get_logger

logger = get_logger(__name__)


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
            logger.info("Saved run start", run_id=run.id)
        except Exception as e:
            logger.error("Failed to save run start:", run_id=run.id, err=e)

    async def on_run_end(self, run: AgentRun) -> None:
        try:
            await self.repository.save_run(run)
            logger.info("Saved run end", run_id=run.id)
        except Exception as e:
            logger.error("Failed to save run end:", run_id=run.id, err=e)
