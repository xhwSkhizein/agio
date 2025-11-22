"""
Tests for extended ComponentFactory
"""

import pytest
from unittest.mock import MagicMock, patch
from agio.registry.factory import ComponentFactory
from agio.registry.models import (
    MemoryConfig,
    KnowledgeConfig,
    HookConfig
)


@pytest.fixture
def factory():
    registry = MagicMock()
    return ComponentFactory(registry)


@patch("agio.registry.factory.import_module")
def test_create_memory(mock_import, factory):
    """Test creating memory component."""
    # Mock class
    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.MemoryClass = mock_class
    mock_import.return_value = mock_module
    
    config = MemoryConfig(
        name="test_memory",
        class_path="pkg.module.MemoryClass",
        max_history_length=10,
        storage_backend="memory"
    )
    
    factory.create_memory(config)
    
    mock_class.assert_called_once()
    call_kwargs = mock_class.call_args[1]
    assert call_kwargs["max_history_length"] == 10
    assert call_kwargs["storage_backend"] == "memory"


@patch("agio.registry.factory.import_module")
def test_create_knowledge(mock_import, factory):
    """Test creating knowledge component."""
    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.KnowledgeClass = mock_class
    mock_import.return_value = mock_module
    
    # Mock embedding model resolution
    factory._resolve_reference = MagicMock(return_value="mock_embedding")
    
    config = KnowledgeConfig(
        name="test_knowledge",
        class_path="pkg.module.KnowledgeClass",
        vector_store="chroma",
        embedding_model="openai",
        chunk_size=100
    )
    
    factory.create_knowledge(config)
    
    mock_class.assert_called_once()
    call_kwargs = mock_class.call_args[1]
    assert call_kwargs["vector_store"] == "chroma"
    assert call_kwargs["embedding_model"] == "mock_embedding"
    assert call_kwargs["chunk_size"] == 100


@patch("agio.registry.factory.import_module")
def test_create_hook(mock_import, factory):
    """Test creating hook component."""
    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.HookClass = mock_class
    mock_import.return_value = mock_module
    
    config = HookConfig(
        name="test_hook",
        class_path="pkg.module.HookClass",
        params={"a": 1}
    )
    
    factory.create_hook(config)
    
    mock_class.assert_called_once_with(a=1)
