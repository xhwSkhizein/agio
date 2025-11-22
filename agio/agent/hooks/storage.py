from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun
from agio.domain.step import Step
from agio.db.base import Storage
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class StorageHook(AgentHook):
    """
    Hook responsible for persisting Agent Run state to the Storage backend.
    """

    def __init__(self, storage: Storage):
        self.storage = storage

    async def on_run_start(self, run: AgentRun) -> None:
        await self._upsert(run, "run_start")

    async def on_step_end(self, run: AgentRun, step: Step) -> None:
        await self._upsert(run, "step_end")

    async def on_run_end(self, run: AgentRun) -> None:
        await self._upsert(run, "run_end")

    async def on_error(self, run: AgentRun, error: Exception) -> None:
        await self._upsert(run, "error")

    async def _upsert(self, run: AgentRun, phase: str):
        try:
            await self.storage.upsert_run(run)
        except Exception as e:
            logger.error("StorageHook failed at", phase=phase, err=e)
