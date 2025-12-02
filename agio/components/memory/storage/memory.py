"""
In-memory storage backend
"""

from agio.core import Step

from .base import MemoryStorage


class InMemoryStorage(MemoryStorage):
    """Simple in-memory storage backend."""

    def __init__(self):
        self.sessions: dict[str, list[Step]] = {}

    async def save_steps(self, session_id: str, steps: list[Step], ttl: int | None = None):
        """Save steps to memory."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].extend(steps)

    async def get_steps(self, session_id: str, limit: int | None = None) -> list[Step]:
        """Get steps from memory."""
        steps = self.sessions.get(session_id, [])
        if limit:
            return steps[-limit:]
        return steps

    async def clear_steps(self, session_id: str):
        """Clear all steps for a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def close(self):
        """No-op for in-memory storage."""
        pass
