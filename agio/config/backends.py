"""
Backend configuration definitions for unified storage abstractions.

This module provides unified backend configurations for all store types:
- Storage backends: MongoDB, SQLite, InMemory
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


# ========== Union Types for Type Hints ==========


StorageBackend = MongoDBBackend | SQLiteBackend | InMemoryBackend
"""Union type for storage backends (used by Session/Trace/Citation stores)."""


__all__ = [
    "BackendConfig",
    "MongoDBBackend",
    "SQLiteBackend",
    "InMemoryBackend",
    "StorageBackend",
]
