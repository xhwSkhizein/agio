"""
Tests for configuration models
"""

import pytest
from pydantic import ValidationError
from agio.registry.models import (
    MemoryConfig,
    KnowledgeConfig,
    HookConfig,
    ComponentType
)


def test_memory_config_valid():
    """Test valid MemoryConfig."""
    config = MemoryConfig(
        name="test_memory",
        class_path="agio.memory.conversation.ConversationMemory",
        max_history_length=50,
        storage_backend="redis",
        params={"url": "redis://localhost"}
    )
    assert config.type == ComponentType.MEMORY
    assert config.max_history_length == 50
    assert config.storage_backend == "redis"


def test_memory_config_defaults():
    """Test MemoryConfig defaults."""
    config = MemoryConfig(
        name="test_memory",
        class_path="pkg.cls"
    )
    assert config.max_history_length == 20
    assert config.max_tokens == 4000
    assert config.storage_backend == "memory"


def test_knowledge_config_valid():
    """Test valid KnowledgeConfig."""
    config = KnowledgeConfig(
        name="test_knowledge",
        class_path="pkg.cls",
        vector_store="chroma",
        embedding_model="openai/embed",
        chunk_size=500
    )
    assert config.type == ComponentType.KNOWLEDGE
    assert config.vector_store == "chroma"
    assert config.chunk_size == 500


def test_hook_config_valid():
    """Test valid HookConfig."""
    config = HookConfig(
        name="test_hook",
        class_path="pkg.cls",
        params={"level": "INFO"}
    )
    assert config.type == ComponentType.HOOK
    assert config.params["level"] == "INFO"


def test_invalid_config():
    """Test invalid configuration."""
    with pytest.raises(ValidationError):
        MemoryConfig(
            name="test",
            # Missing class_path
        ) 
