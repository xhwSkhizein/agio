"""
LLM Log Store - MongoDB persistence for LLM call logs.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from agio.observability.models import LLMCallLog, LLMLogQuery
from agio.utils.logging import get_logger

logger = get_logger(__name__)

# Global store instance
_store: "LLMLogStore | None" = None


class LLMLogStore:
    """
    LLM call log storage with MongoDB persistence.

    Features:
    - Async MongoDB operations via motor
    - In-memory buffer for real-time access
    - Event subscribers for SSE streaming
    """

    def __init__(
        self,
        mongo_uri: str | None = None,
        db_name: str = "agio",
        collection_name: str = "llm_logs",
        buffer_size: int = 500,
    ):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.buffer_size = buffer_size

        # In-memory ring buffer for recent logs
        self._buffer: deque[LLMCallLog] = deque(maxlen=buffer_size)

        # SSE subscribers
        self._subscribers: list[asyncio.Queue] = []

        # MongoDB client (lazy init)
        self._client = None
        self._collection = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize MongoDB connection if configured."""
        if self._initialized:
            return

        if self.mongo_uri:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient

                self._client = AsyncIOMotorClient(self.mongo_uri)
                db = self._client[self.db_name]
                self._collection = db[self.collection_name]

                # Create indexes
                await self._collection.create_index("timestamp")
                await self._collection.create_index("agent_name")
                await self._collection.create_index("session_id")
                await self._collection.create_index("run_id")
                await self._collection.create_index("model_id")
                await self._collection.create_index("status")

                logger.info(
                    "llm_log_store_initialized",
                    db=self.db_name,
                    collection=self.collection_name,
                )
            except ImportError:
                logger.warning(
                    "motor_not_installed",
                    message="MongoDB logging disabled. Install motor: pip install motor",
                )
            except Exception as e:
                logger.error("llm_log_store_init_failed", error=str(e))

        self._initialized = True

    async def add(self, log: LLMCallLog) -> None:
        """Add a new log entry."""
        # Add to buffer
        self._buffer.append(log)

        # Persist to MongoDB
        if self._collection is not None:
            try:
                await self._collection.insert_one(log.model_dump(mode="json"))
            except Exception as e:
                logger.error("llm_log_persist_failed", log_id=log.id, error=str(e))

        # Notify subscribers
        await self._notify_subscribers(log)

    async def update(self, log: LLMCallLog) -> None:
        """Update an existing log entry."""
        # Update in buffer
        for i, existing in enumerate(self._buffer):
            if existing.id == log.id:
                self._buffer[i] = log
                break

        # Update in MongoDB
        if self._collection is not None:
            try:
                await self._collection.update_one(
                    {"id": log.id}, {"$set": log.model_dump(mode="json")}
                )
            except Exception as e:
                logger.error("llm_log_update_failed", log_id=log.id, error=str(e))

        # Notify subscribers
        await self._notify_subscribers(log)

    async def query(self, query: LLMLogQuery) -> list[LLMCallLog]:
        """Query logs with filters."""
        # Build MongoDB query
        mongo_query: dict[str, Any] = {}

        if query.agent_name:
            mongo_query["agent_name"] = query.agent_name
        if query.session_id:
            mongo_query["session_id"] = query.session_id
        if query.run_id:
            mongo_query["run_id"] = query.run_id
        if query.model_id:
            mongo_query["model_id"] = query.model_id
        if query.provider:
            mongo_query["provider"] = query.provider
        if query.status:
            mongo_query["status"] = query.status

        if query.start_time or query.end_time:
            mongo_query["timestamp"] = {}
            if query.start_time:
                mongo_query["timestamp"]["$gte"] = query.start_time.isoformat()
            if query.end_time:
                mongo_query["timestamp"]["$lte"] = query.end_time.isoformat()

        # Query from MongoDB if available
        if self._collection is not None:
            try:
                cursor = (
                    self._collection.find(mongo_query)
                    .sort("timestamp", -1)
                    .skip(query.offset)
                    .limit(query.limit)
                )
                docs = await cursor.to_list(length=query.limit)
                return [LLMCallLog(**doc) for doc in docs]
            except Exception as e:
                logger.error("llm_log_query_failed", error=str(e))

        # Fallback to in-memory buffer
        return self._query_buffer(query)

    async def count(self, query: LLMLogQuery) -> int:
        """Count logs matching query."""
        mongo_query: dict[str, Any] = {}

        if query.agent_name:
            mongo_query["agent_name"] = query.agent_name
        if query.session_id:
            mongo_query["session_id"] = query.session_id
        if query.run_id:
            mongo_query["run_id"] = query.run_id
        if query.status:
            mongo_query["status"] = query.status

        if self._collection is not None:
            try:
                return await self._collection.count_documents(mongo_query)
            except Exception as e:
                logger.error("llm_log_count_failed", error=str(e))

        # Fallback to buffer count
        return len(self._query_buffer(query))

    def _query_buffer(self, query: LLMLogQuery) -> list[LLMCallLog]:
        """Query from in-memory buffer."""
        results = []
        for log in reversed(self._buffer):
            if query.agent_name and log.agent_name != query.agent_name:
                continue
            if query.session_id and log.session_id != query.session_id:
                continue
            if query.run_id and log.run_id != query.run_id:
                continue
            if query.model_id and log.model_id != query.model_id:
                continue
            if query.provider and log.provider != query.provider:
                continue
            if query.status and log.status != query.status:
                continue
            if query.start_time and log.timestamp < query.start_time:
                continue
            if query.end_time and log.timestamp > query.end_time:
                continue
            results.append(log)

        # Apply pagination
        start = query.offset
        end = start + query.limit
        return results[start:end]

    def get_recent(self, limit: int = 50) -> list[LLMCallLog]:
        """Get recent logs from buffer."""
        return list(reversed(list(self._buffer)))[:limit]

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to real-time log updates."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from updates."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def _notify_subscribers(self, log: LLMCallLog) -> None:
        """Notify all subscribers of a log update."""
        for queue in self._subscribers:
            try:
                queue.put_nowait(log)
            except asyncio.QueueFull:
                pass  # Skip if queue is full

    async def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()


def get_llm_log_store() -> LLMLogStore:
    """Get the global LLM log store instance."""
    global _store
    if _store is None:
        from agio.config import settings

        _store = LLMLogStore(
            mongo_uri=settings.mongo_uri,
            db_name=settings.mongo_db_name,
        )
    return _store


async def initialize_store() -> LLMLogStore:
    """Initialize and return the global store."""
    store = get_llm_log_store()
    await store.initialize()
    return store


__all__ = ["LLMLogStore", "get_llm_log_store", "initialize_store"]
