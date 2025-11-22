"""
Memory storage backends
"""

from abc import ABC, abstractmethod
from agio.domain.step import Step


class MemoryStorage(ABC):
    """Abstract storage backend for memory."""
    
    @abstractmethod
    async def save_steps(
        self, session_id: str, steps: list[Step], ttl: int | None = None
    ):
        """Save steps to storage."""
        pass
    
    @abstractmethod
    async def get_steps(self, session_id: str, limit: int | None = None) -> list[Step]:
        """Get steps from storage."""
        pass
    
    @abstractmethod
    async def clear_steps(self, session_id: str):
        """Clear all steps for a session."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close storage connection."""
        pass
