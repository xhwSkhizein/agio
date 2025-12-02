"""
Production-grade Conversation Memory implementation
"""

import tiktoken

from agio.core import Step
from agio.components.memory.base import ChatHistoryManager, Memory
from agio.components.memory.storage import InMemoryStorage, RedisStorage


class ConversationMemory(ChatHistoryManager, Memory):
    """
    Production-grade conversation memory with:
    - Multiple storage backends (memory, redis)
    - Token counting and auto-trimming
    - Session isolation
    """

    def __init__(
        self,
        max_history_length: int = 20,
        max_tokens: int = 4000,
        storage_backend: str = "memory",
        storage_params: dict | None = None,
        **kwargs,
    ):
        self.max_history_length = max_history_length
        self.max_tokens = max_tokens

        # Initialize Memory aggregate interface
        self.history = self
        self.semantic = None

        # Initialize storage backend
        storage_params = storage_params or {}
        if storage_backend == "redis":
            self.storage = RedisStorage(**storage_params)
        else:
            self.storage = InMemoryStorage()

        # Initialize token counter (using cl100k_base for GPT-4)
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoding = None

    def _count_tokens(self, steps: list[Step]) -> int:
        """Count total tokens in steps."""
        if not self.encoding:
            # Fallback: estimate 4 chars per token
            total_chars = sum(len(step.content or "") for step in steps)
            return total_chars // 4

        total_tokens = 0
        for step in steps:
            # Count message overhead (role, etc.)
            total_tokens += 4

            # Count content tokens
            if step.content:
                total_tokens += len(self.encoding.encode(step.content))

        return total_tokens

    def _trim_steps(self, steps: list[Step]) -> list[Step]:
        """Trim steps to fit within max_tokens and max_history_length."""
        # First, trim by count
        if len(steps) > self.max_history_length:
            steps = steps[-self.max_history_length :]

        # Then, trim by tokens
        while len(steps) > 1:
            token_count = self._count_tokens(steps)
            if token_count <= self.max_tokens:
                break
            # Remove oldest step
            steps = steps[1:]

        return steps

    async def add_steps(self, session_id: str, steps: list[Step]):
        """Add steps to history with auto-trimming."""
        # Get existing steps
        existing = await self.storage.get_steps(session_id)

        # Combine and trim
        all_steps = existing + steps
        trimmed = self._trim_steps(all_steps)

        # Clear and save
        await self.storage.clear_steps(session_id)
        await self.storage.save_steps(session_id, trimmed)

    async def get_recent_history(
        self, session_id: str, limit: int = 10, max_tokens: int | None = None
    ) -> list[Step]:
        """Get recent history with optional token limit."""
        steps = await self.storage.get_steps(session_id)

        # Apply limit
        if limit:
            steps = steps[-limit:]

        # Apply token limit
        if max_tokens:
            while len(steps) > 1:
                token_count = self._count_tokens(steps)
                if token_count <= max_tokens:
                    break
                steps = steps[1:]

        return steps

    async def clear_history(self, session_id: str):
        """Clear all history for a session."""
        await self.storage.clear_steps(session_id)

    async def close(self):
        """Close storage connection."""
        await self.storage.close()
