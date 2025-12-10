"""
Repository interface and in-memory implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from agio.domain import AgentRun, Step


class SessionStore(ABC):
    """
    Session store interface.
    Responsible for AgentRun and Step persistence and queries.
    """

    # --- Run Operations ---

    @abstractmethod
    async def save_run(self, run: AgentRun) -> None:
        """Save Run"""
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        """Get Run"""
        pass

    @abstractmethod
    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AgentRun]:
        """List Runs"""
        pass

    @abstractmethod
    async def delete_run(self, run_id: str) -> None:
        """Delete Run"""
        pass

    # --- Step Operations ---

    @abstractmethod
    async def save_step(self, step: Step) -> None:
        """Save single Step"""
        pass

    @abstractmethod
    async def save_steps_batch(self, steps: List[Step]) -> None:
        """Batch save Steps (for fork operations)"""
        pass

    @abstractmethod
    async def get_steps(
        self,
        session_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Step]:
        """
        Get Steps (sorted by sequence)

        Args:
            session_id: Session ID
            start_seq: Start sequence (inclusive), None = from beginning
            end_seq: End sequence (inclusive), None = to end
            limit: Maximum return count
        """
        pass

    @abstractmethod
    async def get_last_step(self, session_id: str) -> Optional[Step]:
        """Get last Step"""
        pass

    @abstractmethod
    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        """
        Delete Steps (sequence >= start_seq)

        Returns:
            Number of deleted Steps
        """
        pass

    @abstractmethod
    async def get_step_count(self, session_id: str) -> int:
        """Get total Step count for session"""
        pass

    # --- Tool Result Query (for cross-agent reference) ---

    async def get_step_by_tool_call_id(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> Optional[Step]:
        """Get a Tool Step by tool_call_id"""
        steps = await self.get_steps(session_id)
        for step in steps:
            if step.tool_call_id == tool_call_id:
                return step
        return None


class InMemorySessionStore(SessionStore):
    """
    In-memory implementation (for testing and development)
    """

    def __init__(self):
        self.runs: dict[str, AgentRun] = {}
        self.steps: dict[str, List[Step]] = {}  # session_id -> List[Step]

    async def save_run(self, run: AgentRun) -> None:
        self.runs[run.id] = run

    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        return self.runs.get(run_id)

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AgentRun]:
        runs = list(self.runs.values())

        if user_id:
            runs = [r for r in runs if r.user_id == user_id]

        if session_id:
            runs = [r for r in runs if r.session_id == session_id]

        runs.sort(key=lambda r: r.created_at, reverse=True)

        return runs[offset : offset + limit]

    async def delete_run(self, run_id: str) -> None:
        if run_id in self.runs:
            del self.runs[run_id]

    # --- Step Operations ---

    async def save_step(self, step: Step) -> None:
        if step.session_id not in self.steps:
            self.steps[step.session_id] = []

        existing_idx = None
        for i, s in enumerate(self.steps[step.session_id]):
            if s.id == step.id:
                existing_idx = i
                break

        if existing_idx is not None:
            self.steps[step.session_id][existing_idx] = step
        else:
            self.steps[step.session_id].append(step)
            self.steps[step.session_id].sort(key=lambda s: s.sequence)

    async def save_steps_batch(self, steps: List[Step]) -> None:
        for step in steps:
            await self.save_step(step)

    async def get_steps(
        self,
        session_id: str,
        start_seq: Optional[int] = None,
        end_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Step]:
        steps = self.steps.get(session_id, [])

        if start_seq is not None:
            steps = [s for s in steps if s.sequence >= start_seq]
        if end_seq is not None:
            steps = [s for s in steps if s.sequence <= end_seq]

        return steps[:limit]

    async def get_last_step(self, session_id: str) -> Optional[Step]:
        steps = self.steps.get(session_id, [])
        return steps[-1] if steps else None

    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        if session_id not in self.steps:
            return 0

        original_count = len(self.steps[session_id])
        self.steps[session_id] = [s for s in self.steps[session_id] if s.sequence < start_seq]
        return original_count - len(self.steps[session_id])

    async def get_step_count(self, session_id: str) -> int:
        return len(self.steps.get(session_id, []))


__all__ = ["SessionStore", "InMemorySessionStore"]
