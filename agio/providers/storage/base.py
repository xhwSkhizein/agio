"""
Repository interface and in-memory implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from agio.domain import Run, Step


class SessionStore(ABC):
    """
    Session store interface.
    Responsible for Run and Step persistence and queries.
    """

    # --- Run Operations ---

    @abstractmethod
    async def save_run(self, run: Run) -> None:
        """Save Run"""
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[Run]:
        """Get Run"""
        pass

    @abstractmethod
    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Run]:
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
        run_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
        branch_key: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Step]:
        """
        Get Steps (sorted by sequence)

        Args:
            session_id: Session ID
            start_seq: Start sequence (inclusive), None = from beginning
            end_seq: End sequence (inclusive), None = to end
            run_id: Filter by run_id (optional)
            workflow_id: Filter by workflow_id (optional)
            node_id: Filter by node_id (optional)
            branch_key: Filter by branch_key (optional)
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

    @abstractmethod
    async def get_max_sequence(self, session_id: str) -> int:
        """
        Get the maximum sequence number in the session.
        
        Returns:
            Maximum sequence number, or 0 if no steps exist
        """
        pass

    async def get_last_assistant_content(
        self,
        session_id: str,
        node_id: str,
        workflow_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the last assistant step content for a specific node.

        Args:
            session_id: Session ID
            node_id: Node ID to filter by
            workflow_id: Workflow ID for isolation (persists across run_id changes)

        Returns:
            Content of the last assistant step for the node, or None if not found
        """
        steps = await self.get_steps(
            session_id=session_id,
            workflow_id=workflow_id,
            node_id=node_id,
            limit=1000,
        )
        # Find last assistant step
        for step in reversed(steps):
            if step.role.value == "assistant" and step.content:
                return step.content
        return None

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
        self.runs: dict[str, Run] = {}
        self.steps: dict[str, List[Step]] = {}  # session_id -> List[Step]

    async def save_run(self, run: Run) -> None:
        self.runs[run.id] = run

    async def get_run(self, run_id: str) -> Optional[Run]:
        return self.runs.get(run_id)

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Run]:
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
        run_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        node_id: Optional[str] = None,
        branch_key: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Step]:
        steps = self.steps.get(session_id, [])

        if start_seq is not None:
            steps = [s for s in steps if s.sequence >= start_seq]
        if end_seq is not None:
            steps = [s for s in steps if s.sequence <= end_seq]
        if run_id is not None:
            steps = [s for s in steps if s.run_id == run_id]
        if workflow_id is not None:
            steps = [s for s in steps if s.workflow_id == workflow_id]
        if node_id is not None:
            steps = [s for s in steps if s.node_id == node_id]
        if branch_key is not None:
            steps = [s for s in steps if s.branch_key == branch_key]

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

    async def get_max_sequence(self, session_id: str) -> int:
        steps = self.steps.get(session_id, [])
        if not steps:
            return 0
        return max(s.sequence for s in steps)


__all__ = ["SessionStore", "InMemorySessionStore"]
