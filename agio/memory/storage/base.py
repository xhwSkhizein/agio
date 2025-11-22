"""
Memory storage backends
"""

from abc import ABC, abstractmethod
from agio.domain.messages import Message


class MemoryStorage(ABC):
    """Abstract storage backend for memory."""
    
    @abstractmethod
    async def save_messages(self, session_id: str, messages: list[Message], ttl: int | None = None):
        """Save messages to storage."""
        pass
    
    @abstractmethod
    async def get_messages(self, session_id: str, limit: int | None = None) -> list[Message]:
        """Get messages from storage."""
        pass
    
    @abstractmethod
    async def clear_messages(self, session_id: str):
        """Clear all messages for a session."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close storage connection."""
        pass
