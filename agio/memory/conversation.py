"""
Production-grade Conversation Memory implementation
"""

import tiktoken
from agio.domain.messages import Message
from agio.memory.base import ChatHistoryManager, Memory
from agio.memory.storage import InMemoryStorage, RedisStorage


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
        **kwargs
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
    
    def _count_tokens(self, messages: list[Message]) -> int:
        """Count total tokens in messages."""
        if not self.encoding:
            # Fallback: estimate 4 chars per token
            total_chars = sum(len(msg.content or "") for msg in messages)
            return total_chars // 4
        
        total_tokens = 0
        for msg in messages:
            # Count message overhead (role, etc.)
            total_tokens += 4
            
            # Count content tokens
            if msg.content:
                total_tokens += len(self.encoding.encode(msg.content))
        
        return total_tokens
    
    def _trim_messages(self, messages: list[Message]) -> list[Message]:
        """Trim messages to fit within max_tokens and max_history_length."""
        # First, trim by count
        if len(messages) > self.max_history_length:
            messages = messages[-self.max_history_length:]
        
        # Then, trim by tokens
        while len(messages) > 1:
            token_count = self._count_tokens(messages)
            if token_count <= self.max_tokens:
                break
            # Remove oldest message
            messages = messages[1:]
        
        return messages
    
    async def add_messages(self, session_id: str, messages: list[Message]):
        """Add messages to history with auto-trimming."""
        # Get existing messages
        existing = await self.storage.get_messages(session_id)
        
        # Combine and trim
        all_messages = existing + messages
        trimmed = self._trim_messages(all_messages)
        
        # Clear and save
        await self.storage.clear_messages(session_id)
        await self.storage.save_messages(session_id, trimmed)
    
    async def get_recent_history(
        self,
        session_id: str,
        limit: int = 10,
        max_tokens: int | None = None
    ) -> list[Message]:
        """Get recent history with optional token limit."""
        messages = await self.storage.get_messages(session_id)
        
        # Apply limit
        if limit:
            messages = messages[-limit:]
        
        # Apply token limit
        if max_tokens:
            while len(messages) > 1:
                token_count = self._count_tokens(messages)
                if token_count <= max_tokens:
                    break
                messages = messages[1:]
        
        return messages
    
    async def clear_history(self, session_id: str):
        """Clear all history for a session."""
        await self.storage.clear_messages(session_id)
    
    async def close(self):
        """Close storage connection."""
        await self.storage.close()
