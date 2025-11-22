from abc import ABC, abstractmethod
from typing import List, Optional

from agio.domain.run import AgentRun
from agio.domain.step import Step


class AgentRunRepository(ABC):
    """
    Agent Run 仓储接口。
    负责 Run 和 Step 的持久化与查询。
    """

    # --- Run Operations ---

    @abstractmethod
    async def save_run(self, run: AgentRun) -> None:
        """保存 Run"""
        pass

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        """获取 Run"""
        pass

    @abstractmethod
    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[AgentRun]:
        """列出 Runs"""
        pass

    @abstractmethod
    async def delete_run(self, run_id: str) -> None:
        """删除 Run"""
        pass

    # --- Step Operations ---

    @abstractmethod
    async def save_step(self, step: Step) -> None:
        """保存单个 Step"""
        pass

    @abstractmethod
    async def save_steps_batch(self, steps: List[Step]) -> None:
        """批量保存 Steps (用于 fork 操作)"""
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
        获取 Steps (按 sequence 排序)

        Args:
            session_id: Session ID
            start_seq: 起始 sequence (包含), None 表示从头开始
            end_seq: 结束 sequence (包含), None 表示到最后
            limit: 最大返回数量
        """
        pass

    @abstractmethod
    async def get_last_step(self, session_id: str) -> Optional[Step]:
        """获取最后一个 Step"""
        pass

    @abstractmethod
    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        """
        删除 Steps (sequence >= start_seq)

        Returns:
            删除的 Step 数量
        """
        pass

    @abstractmethod
    async def get_step_count(self, session_id: str) -> int:
        """获取会话的 Step 总数"""
        pass


class InMemoryRepository(AgentRunRepository):
    """
    内存实现（用于测试和开发）
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

        # Sort by created_at descending
        runs.sort(key=lambda r: r.created_at, reverse=True)

        return runs[offset : offset + limit]

    async def delete_run(self, run_id: str) -> None:
        if run_id in self.runs:
            del self.runs[run_id]

    # --- Step Operations ---

    async def save_step(self, step: Step) -> None:
        if step.session_id not in self.steps:
            self.steps[step.session_id] = []

        # Check if step already exists (upsert behavior)
        existing_idx = None
        for i, s in enumerate(self.steps[step.session_id]):
            if s.id == step.id:
                existing_idx = i
                break

        if existing_idx is not None:
            self.steps[step.session_id][existing_idx] = step
        else:
            self.steps[step.session_id].append(step)
            # Keep sorted by sequence
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

        # Filter by sequence range
        if start_seq is not None:
            steps = [s for s in steps if s.sequence >= start_seq]
        if end_seq is not None:
            steps = [s for s in steps if s.sequence <= end_seq]

        # Already sorted by sequence
        return steps[:limit]

    async def get_last_step(self, session_id: str) -> Optional[Step]:
        steps = self.steps.get(session_id, [])
        return steps[-1] if steps else None

    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        if session_id not in self.steps:
            return 0

        original_count = len(self.steps[session_id])
        self.steps[session_id] = [
            s for s in self.steps[session_id] if s.sequence < start_seq
        ]
        return original_count - len(self.steps[session_id])

    async def get_step_count(self, session_id: str) -> int:
        return len(self.steps.get(session_id, []))
