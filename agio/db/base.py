from abc import ABC, abstractmethod
from agio.domain.run import AgentRun

class Storage(ABC):
    @abstractmethod
    async def upsert_run(self, run: AgentRun) -> None:
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> AgentRun | None:
        pass
        
    @abstractmethod
    async def list_runs(self, agent_id: str, limit: int = 10) -> list[AgentRun]:
        pass

# Alias for main.py compatibility if needed, or we can expose Storage as DB
DB = Storage

