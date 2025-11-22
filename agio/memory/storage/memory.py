"""
In-memory storage backend
"""

from agio.domain.messages import Message
from .base import MemoryStorage


class InMemoryStorage(MemoryStorage):
    """Simple in-memory storage backend."""
    
    def __init__(self):
        self.sessions: dict[str, list[Message]] = {}
    
    async def save_messages(self, session_id: str, messages: list[Message], ttl: int | None = None):
        """Save messages to memory."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].extend(messages)
    
    async def get_messages(self, session_id: str, limit: int | None = None) -> list[Message]:
        """Get messages from memory."""
        messages = self.sessions.get(session_id, [])
        if limit:
            return messages[-limit:]
        return messages
    
    async def clear_messages(self, session_id: str):
        """Clear all messages for a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def close(self):
        """No-op for in-memory storage."""
        pass
