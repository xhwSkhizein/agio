"""
Tests for AnthropicModel
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from agio.models.anthropic import AnthropicModel, StreamChunk


@pytest.fixture
def mock_anthropic():
    with patch("agio.models.anthropic.AsyncAnthropic") as mock:
        yield mock


@pytest.mark.asyncio
async def test_anthropic_init(mock_anthropic):
    """Test initialization."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        provider="anthropic",
        api_key="sk-test"
    )
    assert model.name == "claude-3-opus"
    mock_anthropic.assert_called_once_with(api_key="sk-test")


@pytest.mark.asyncio
async def test_convert_messages(mock_anthropic):
    """Test message conversion."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        provider="anthropic",
        api_key="sk-test"
    )
    
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "tool", "tool_call_id": "call_1", "content": "result"}
    ]
    
    system, converted = model._convert_messages(messages)
    
    assert system == "System prompt"
    assert len(converted) == 3
    assert converted[0] == {"role": "user", "content": "Hello"}
    assert converted[1] == {"role": "assistant", "content": "Hi"}
    assert converted[2]["role"] == "user"
    assert converted[2]["content"][0]["type"] == "tool_result"


@pytest.mark.asyncio
async def test_arun_stream(mock_anthropic):
    """Test streaming execution."""
    # Mock client and stream
    mock_client = mock_anthropic.return_value
    mock_stream = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_stream)
    
    # Mock stream events
    async def stream_generator():
        # Content delta
        event1 = MagicMock()
        event1.type = "content_block_delta"
        event1.delta.type = "text_delta"
        event1.delta.text = "Hello"
        yield event1
        
        # Stop reason
        event2 = MagicMock()
        event2.type = "message_delta"
        event2.delta.stop_reason = "end_turn"
        yield event2
    
    mock_stream.__aiter__.side_effect = stream_generator
    
    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        provider="anthropic",
        api_key="sk-test"
    )
    
    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)
    
    assert len(chunks) == 2
    assert chunks[0].content == "Hello"
    assert chunks[1].finish_reason == "end_turn"
