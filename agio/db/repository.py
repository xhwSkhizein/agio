from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from agio.protocol.events import AgentEvent
from agio.domain.run import AgentRun
from agio.domain.step import Step


class StoredEvent(BaseModel):
    """持久化的事件模型 (DEPRECATED - use Step instead)"""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    run_id: str
    sequence: int
    event_type: str
    timestamp: datetime
    data: dict
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


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

    # --- Step Operations (NEW) ---

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
        获取会话的 Steps，可选按 sequence 范围过滤。

        Args:
            session_id: 会话 ID
            start_seq: 最小 sequence (包含), None = 无下限
            end_seq: 最大 sequence (包含), None = 无上限
            limit: 最大返回数量

        Returns:
            按 sequence 排序的 Step 列表
        """
        pass

    @abstractmethod
    async def get_last_step(self, session_id: str) -> Optional[Step]:
        """获取会话的最后一个 Step"""
        pass

    @abstractmethod
    async def delete_steps(self, session_id: str, start_seq: int) -> int:
        """
        删除 sequence >= start_seq 的 Steps。
        返回删除的数量。
        用于 retry 操作。
        """
        pass

    @abstractmethod
    async def get_step_count(self, session_id: str) -> int:
        """获取会话的 Step 总数"""
        pass

    # --- Event Operations (DEPRECATED - kept for backward compatibility) ---

    @abstractmethod
    async def save_event(self, event: AgentEvent, sequence: int) -> None:
        """保存事件 (DEPRECATED)"""
        pass

    @abstractmethod
    async def get_events(
        self, run_id: str, offset: int = 0, limit: int = 100
    ) -> List[AgentEvent]:
        """获取事件列表（分页）(DEPRECATED)"""
        pass

    @abstractmethod
    async def get_event_count(self, run_id: str) -> int:
        """获取事件总数 (DEPRECATED)"""
        pass


class InMemoryRepository(AgentRunRepository):
    """
    内存实现（用于测试和开发）
    """

    def __init__(self):
        self.runs: dict[str, AgentRun] = {}
        self.events: dict[str, List[StoredEvent]] = {}
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

        # 按创建时间倒序
        runs.sort(key=lambda r: r.created_at, reverse=True)

        return runs[offset : offset + limit]

    # --- Step Operations ---

    async def save_step(self, step: Step) -> None:
        if step.session_id not in self.steps:
            self.steps[step.session_id] = []
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

        # Apply limit
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
        deleted_count = original_count - len(self.steps[session_id])
        return deleted_count

    async def get_step_count(self, session_id: str) -> int:
        return len(self.steps.get(session_id, []))

    # --- Event Operations (DEPRECATED) ---

    async def save_event(self, event: AgentEvent, sequence: int) -> None:
        if event.run_id not in self.events:
            self.events[event.run_id] = []

        stored_event = StoredEvent(
            run_id=event.run_id,
            sequence=sequence,
            event_type=event.type.value,
            timestamp=event.timestamp,
            data=event.data,
            metadata=event.metadata,
        )
        self.events[event.run_id].append(stored_event)

    async def get_events(
        self, run_id: str, offset: int = 0, limit: int = 100
    ) -> List[AgentEvent]:
        events = self.events.get(run_id, [])
        events_slice = events[offset : offset + limit]

        # 转换回 AgentEvent
        from agio.protocol.events import EventType

        result = []
        for stored in events_slice:
            result.append(
                AgentEvent(
                    type=EventType(stored.event_type),
                    run_id=stored.run_id,
                    timestamp=stored.timestamp,
                    data=stored.data,
                    metadata=stored.metadata,
                )
            )
        return result

    async def get_event_count(self, run_id: str) -> int:
        return len(self.events.get(run_id, []))

