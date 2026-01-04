"""
Backend configuration definitions for unified storage/cache/vector abstractions.

This module provides unified backend configurations for all store types:
- Storage backends: MongoDB, SQLite, InMemory
- Cache backends: Redis, InMemory
- Vector backends: Chroma, Pinecone

All backend configs follow a consistent pattern with a `type` field for discrimination.
"""

from typing import Literal

from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    """Base class for all backend configurations."""

    type: str = Field(..., description="Backend type identifier")

    model_config = {"extra": "forbid"}


# ========== Storage Backends (for Session/Trace/Citation Stores) ==========


class MongoDBBackend(BackendConfig):
    """MongoDB backend configuration."""

    type: Literal["mongodb"] = "mongodb"
    uri: str = Field(..., description="MongoDB connection URI")
    db_name: str = Field(default="agio", description="Database name")
    collection_name: str | None = Field(
        default=None,
        description="Collection name (optional, each store may use different defaults)",
    )


class SQLiteBackend(BackendConfig):
    """SQLite backend configuration."""

    type: Literal["sqlite"] = "sqlite"
    db_path: str = Field(..., description="SQLite database file path")


class InMemoryBackend(BackendConfig):
    """In-memory backend configuration (no persistence)."""

    type: Literal["inmemory"] = "inmemory"


# ========== Cache Backends (for Memory components) ==========


class RedisBackend(BackendConfig):
    """Redis backend configuration."""

    type: Literal["redis"] = "redis"
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    db: int = Field(default=0, ge=0, description="Redis database number")
    password: str | None = Field(default=None, description="Redis password (optional)")


# ========== Vector Database Backends (for Knowledge components) ==========


class ChromaBackend(BackendConfig):
    """Chroma vector database backend configuration."""

    type: Literal["chroma"] = "chroma"
    host: str = Field(default="localhost", description="Chroma host")
    port: int = Field(default=8000, description="Chroma port")
    collection_name: str = Field(..., description="Collection name")


class PineconeBackend(BackendConfig):
    """Pinecone vector database backend configuration."""

    type: Literal["pinecone"] = "pinecone"
    api_key: str = Field(..., description="Pinecone API key")
    environment: str = Field(..., description="Pinecone environment")
    index_name: str = Field(..., description="Index name")


# ========== Union Types for Type Hints ==========


StorageBackend = MongoDBBackend | SQLiteBackend | InMemoryBackend
"""Union type for storage backends (used by Session/Trace/Citation stores)."""

CacheBackend = RedisBackend | InMemoryBackend
"""Union type for cache backends (used by Memory components)."""

VectorBackend = ChromaBackend | PineconeBackend
"""Union type for vector database backends (used by Knowledge components)."""


__all__ = [
    "BackendConfig",
    "MongoDBBackend",
    "SQLiteBackend",
    "InMemoryBackend",
    "RedisBackend",
    "ChromaBackend",
    "PineconeBackend",
    "StorageBackend",
    "CacheBackend",
    "VectorBackend",
]
