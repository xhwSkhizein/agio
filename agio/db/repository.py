from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from agio.protocol.events import AgentEvent
from agio.domain.run import AgentRun


class StoredEvent(BaseModel):
    """持久化的事件模型"""
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
    负责 Run 和 Event 的持久化与查询。
    """
    
    @abstractmethod
    async def save_run(self, run: AgentRun) -> None:
        """保存 Run"""
        pass
    
    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        """获取 Run"""
        pass
    
    @abstractmethod
    async def save_event(self, event: AgentEvent, sequence: int) -> None:
        """保存事件"""
        pass
    
    @abstractmethod
    async def get_events(
        self, 
        run_id: str, 
        offset: int = 0, 
        limit: int = 100
    ) -> List[AgentEvent]:
        """获取事件列表（分页）"""
        pass
    
    @abstractmethod
    async def get_event_count(self, run_id: str) -> int:
        """获取事件总数"""
        pass
    
    @abstractmethod
    async def list_runs(
        self, 
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[AgentRun]:
        """列出 Runs"""
        pass


class InMemoryRepository(AgentRunRepository):
    """
    内存实现（用于测试和开发）
    """
    
    def __init__(self):
        self.runs: dict[str, AgentRun] = {}
        self.events: dict[str, List[StoredEvent]] = {}
    
    async def save_run(self, run: AgentRun) -> None:
        self.runs[run.id] = run
    
    async def get_run(self, run_id: str) -> Optional[AgentRun]:
        return self.runs.get(run_id)
    
    async def save_event(self, event: AgentEvent, sequence: int) -> None:
        if event.run_id not in self.events:
            self.events[event.run_id] = []
        
        stored_event = StoredEvent(
            run_id=event.run_id,
            sequence=sequence,
            event_type=event.type.value,
            timestamp=event.timestamp,
            data=event.data,
            metadata=event.metadata
        )
        self.events[event.run_id].append(stored_event)
    
    async def get_events(
        self, 
        run_id: str, 
        offset: int = 0, 
        limit: int = 100
    ) -> List[AgentEvent]:
        events = self.events.get(run_id, [])
        events_slice = events[offset:offset + limit]
        
        # 转换回 AgentEvent
        from agio.protocol.events import EventType
        result = []
        for stored in events_slice:
            result.append(AgentEvent(
                type=EventType(stored.event_type),
                run_id=stored.run_id,
                timestamp=stored.timestamp,
                data=stored.data,
                metadata=stored.metadata
            ))
        return result
    
    async def get_event_count(self, run_id: str) -> int:
        return len(self.events.get(run_id, []))
    
    async def list_runs(
        self, 
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[AgentRun]:
        runs = list(self.runs.values())
        
        if user_id:
            runs = [r for r in runs if r.user_id == user_id]
        
        # 按创建时间倒序
        runs.sort(key=lambda r: r.created_at, reverse=True)
        
        return runs[offset:offset + limit]
