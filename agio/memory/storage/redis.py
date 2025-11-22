"""
Redis storage backend
"""

from agio.domain.messages import Message
from .base import MemoryStorage
from agio.utils.logging import get_logger

logger = get_logger(__name__)

try:
    import redis.asyncio as redis
except ImportError:
    redis = None


class RedisStorage(MemoryStorage):
    """Redis storage backend for persistent memory."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", **kwargs):
        if redis is None:
            raise ImportError(
                "redis package is required for RedisStorage. Install with: uv add redis"
            )

        self.redis_url = redis_url
        self.client = None
        self.kwargs = kwargs

    async def _get_client(self):
        """Lazy initialization of Redis client."""
        if self.client is None:
            self.client = await redis.from_url(self.redis_url, **self.kwargs)
        return self.client

    async def save_messages(
        self, session_id: str, messages: list[Message], ttl: int | None = 3600
    ):
        """Save messages to Redis."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"

        # Serialize messages
        serialized = [msg.model_dump_json() for msg in messages]

        # Push to Redis list
        if serialized:
            await client.rpush(key, *serialized)

        # Set TTL
        if ttl:
            await client.expire(key, ttl)

    async def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[Message]:
        """Get messages from Redis."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"

        # Get messages
        if limit:
            data = await client.lrange(key, -limit, -1)
        else:
            data = await client.lrange(key, 0, -1)

        # Deserialize
        messages = []
        for item in data:
            try:
                messages.append(Message.model_validate_json(item))
            except Exception as e:
                logger.error("Failed to deserialize message", err=e)

        return messages

    async def clear_messages(self, session_id: str):
        """Clear all messages for a session."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"
        await client.delete(key)

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
