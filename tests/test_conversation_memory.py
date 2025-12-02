"""
Tests for ConversationMemory
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agio.core import MessageRole, Step
from agio.components.memory.conversation import ConversationMemory
from agio.components.memory.storage import InMemoryStorage


@pytest.fixture
def memory():
    return ConversationMemory(max_history_length=5, max_tokens=100, storage_backend="memory")


def create_step(role: str, content: str, sequence: int = 1) -> Step:
    return Step(
        role=MessageRole(role),
        content=content,
        session_id="test_session",
        run_id="test_run",
        sequence=sequence,
    )


def test_init(memory):
    """Test initialization."""
    assert isinstance(memory.storage, InMemoryStorage)
    assert memory.max_history_length == 5
    assert memory.max_tokens == 100


def test_count_tokens(memory):
    """Test token counting."""
    steps = [
        create_step(role="user", content="Hello world"),  # ~2 tokens + 4 overhead = 6
        create_step(role="assistant", content="Hi"),  # ~1 token + 4 overhead = 5
    ]
    # Exact count depends on tiktoken, but should be > 0
    count = memory._count_tokens(steps)
    assert count > 0


def test_trim_steps(memory):
    """Test step trimming."""
    # Create 10 steps
    steps = [create_step(role="user", content=f"Msg {i}", sequence=i) for i in range(10)]

    # Trim by count (max 5)
    trimmed = memory._trim_steps(steps)
    assert len(trimmed) == 5
    assert trimmed[0].content == "Msg 5"
    assert trimmed[-1].content == "Msg 9"


@pytest.mark.asyncio
async def test_add_and_get_steps(memory):
    """Test adding and retrieving steps."""
    session_id = "test_session"

    steps = [
        create_step(role="user", content="Hello", sequence=1),
        create_step(role="assistant", content="Hi", sequence=2),
    ]

    await memory.add_steps(session_id, steps)

    history = await memory.get_recent_history(session_id)
    assert len(history) == 2
    assert history[0].content == "Hello"
    assert history[1].content == "Hi"


@pytest.mark.asyncio
async def test_auto_trimming(memory):
    """Test auto-trimming when adding steps."""
    session_id = "test_session"

    # Add 4 steps
    steps1 = [create_step(role="user", content=f"Msg {i}", sequence=i) for i in range(4)]
    await memory.add_steps(session_id, steps1)

    # Add 3 more (total 7 > max 5)
    steps2 = [create_step(role="user", content=f"Msg {i}", sequence=i) for i in range(4, 7)]
    await memory.add_steps(session_id, steps2)

    history = await memory.get_recent_history(session_id)
    assert len(history) == 5
    assert history[0].content == "Msg 2"
    assert history[-1].content == "Msg 6"
