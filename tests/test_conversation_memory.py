"""
Tests for ConversationMemory
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from agio.domain.messages import Message
from agio.memory.conversation import ConversationMemory
from agio.memory.storage import InMemoryStorage


@pytest.fixture
def memory():
    return ConversationMemory(
        max_history_length=5,
        max_tokens=100,
        storage_backend="memory"
    )


def test_init(memory):
    """Test initialization."""
    assert isinstance(memory.storage, InMemoryStorage)
    assert memory.max_history_length == 5
    assert memory.max_tokens == 100


def test_count_tokens(memory):
    """Test token counting."""
    messages = [
        Message(role="user", content="Hello world"), # ~2 tokens + 4 overhead = 6
        Message(role="assistant", content="Hi")      # ~1 token + 4 overhead = 5
    ]
    # Exact count depends on tiktoken, but should be > 0
    count = memory._count_tokens(messages)
    assert count > 0


def test_trim_messages(memory):
    """Test message trimming."""
    # Create 10 messages
    messages = [
        Message(role="user", content=f"Msg {i}") 
        for i in range(10)
    ]
    
    # Trim by count (max 5)
    trimmed = memory._trim_messages(messages)
    assert len(trimmed) == 5
    assert trimmed[0].content == "Msg 5"
    assert trimmed[-1].content == "Msg 9"


@pytest.mark.asyncio
async def test_add_and_get_messages(memory):
    """Test adding and retrieving messages."""
    session_id = "test_session"
    
    msgs = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi")
    ]
    
    await memory.add_messages(session_id, msgs)
    
    history = await memory.get_recent_history(session_id)
    assert len(history) == 2
    assert history[0].content == "Hello"
    assert history[1].content == "Hi"


@pytest.mark.asyncio
async def test_auto_trimming(memory):
    """Test auto-trimming when adding messages."""
    session_id = "test_session"
    
    # Add 4 messages
    msgs1 = [Message(role="user", content=f"Msg {i}") for i in range(4)]
    await memory.add_messages(session_id, msgs1)
    
    # Add 3 more (total 7 > max 5)
    msgs2 = [Message(role="user", content=f"Msg {i}") for i in range(4, 7)]
    await memory.add_messages(session_id, msgs2)
    
    history = await memory.get_recent_history(session_id)
    assert len(history) == 5
    assert history[0].content == "Msg 2"
    assert history[-1].content == "Msg 6"
