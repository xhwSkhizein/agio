from abc import ABC, abstractmethod
from agio.domain.messages import Message
from agio.domain.memory import AgentMemoriedContent, MemoryCategory

class ChatHistoryManager(ABC):
    """
    Short-term Memory: 管理当前会话的上下文窗口。
    职责：存储原始对话流，提供滑动窗口或 Token 截断。
    """
    @abstractmethod
    async def add_messages(self, session_id: str, messages: list[Message]):
        pass
        
    @abstractmethod
    async def get_recent_history(self, session_id: str, limit: int = 10, max_tokens: int | None = None) -> list[Message]:
        pass
        
    @abstractmethod
    async def clear_history(self, session_id: str):
        pass

class SemanticMemoryManager(ABC):
    """
    Long-term Memory: 管理基于向量的用户记忆。
    职责：存储、检索个性化事实和偏好。
    """
    @abstractmethod
    async def remember(self, user_id: str, memory: AgentMemoriedContent):
        """写入一条新记忆"""
        pass
        
    @abstractmethod
    async def recall(self, user_id: str, query: str, limit: int = 5, categories: list[MemoryCategory] | None = None) -> list[AgentMemoriedContent]:
        """基于语义检索相关记忆"""
        pass

class Memory(ABC):
    """
    聚合接口：Agent 通常持有这个聚合对象
    """
    history: ChatHistoryManager
    semantic: SemanticMemoryManager

