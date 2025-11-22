"""
Redis storage backend
"""

from agio.domain.step import Step
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

    async def save_steps(
        self, session_id: str, steps: list[Step], ttl: int | None = 3600
    ):
        """Save steps to Redis."""
        client = await self._get_client()
        key = f"session:{session_id}:steps"

        # Serialize steps
        serialized = [step.model_dump_json() for step in steps]

        # Push to Redis list
        if serialized:
            await client.rpush(key, *serialized)

        # Set TTL
        if ttl:
            await client.expire(key, ttl)

    async def get_steps(self, session_id: str, limit: int | None = None) -> list[Step]:
        """Get steps from Redis."""
        client = await self._get_client()
        key = f"session:{session_id}:steps"

        # Get steps
        if limit:
            data = await client.lrange(key, -limit, -1)
        else:
            data = await client.lrange(key, 0, -1)

        # Deserialize
        steps = []
        for item in data:
            try:
                steps.append(Step.model_validate_json(item))
            except Exception as e:
                logger.error("Failed to deserialize step", err=e)

        return steps

    async def clear_steps(self, session_id: str):
        """Clear all steps for a session."""
        client = await self._get_client()
        key = f"session:{session_id}:steps"
        await client.delete(key)

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
