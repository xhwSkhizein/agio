"""
Tests for AnthropicModel
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agio.llm.anthropic import AnthropicModel


@pytest.fixture
def mock_anthropic():
    with patch("agio.llm.anthropic.AsyncAnthropic") as mock:
        yield mock


@pytest.mark.asyncio
async def test_anthropic_init(mock_anthropic):
    """Test initialization."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus", name="claude-3-opus", api_key="sk-test"
    )
    assert model.name == "claude-3-opus"
    mock_anthropic.assert_called_once_with(api_key="sk-test")


@pytest.mark.asyncio
async def test_convert_messages(mock_anthropic):
    """Test message conversion."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus", name="claude-3-opus", api_key="sk-test"
    )

    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "tool", "tool_call_id": "call_1", "content": "result"},
    ]

    system, converted = model._convert_messages(messages)

    assert system == "System prompt"
    assert len(converted) == 3
    assert converted[0] == {"role": "user", "content": "Hello"}
    assert converted[1] == {"role": "assistant", "content": "Hi"}
    assert converted[2]["role"] == "user"
    assert converted[2]["content"][0]["type"] == "tool_result"


@pytest.mark.asyncio
async def test_convert_messages_with_tool_use(mock_anthropic):
    """Test message conversion with tool_use."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus", name="claude-3-opus", api_key="sk-test"
    )

    messages = [
        {
            "role": "assistant",
            "content": "I will use a tool",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Shanghai"}',
                    },
                }
            ],
        }
    ]

    _, converted = model._convert_messages(messages)

    assert len(converted) == 1
    assert converted[0]["role"] == "assistant"
    content = converted[0]["content"]
    assert len(content) == 2
    assert content[0] == {"type": "text", "text": "I will use a tool"}
    assert content[1]["type"] == "tool_use"
    assert content[1]["id"] == "call_1"
    assert content[1]["name"] == "get_weather"
    assert content[1]["input"] == {"location": "Shanghai"}


@pytest.mark.asyncio
async def test_arun_stream_tool_use(mock_anthropic):
    """Test streaming with tool_use events."""
    mock_client = mock_anthropic.return_value
    mock_stream = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_stream)

    async def tool_stream_generator():
        # Start tool use
        event1 = MagicMock()
        event1.type = "content_block_start"
        event1.index = 0
        event1.content_block.type = "tool_use"
        event1.content_block.id = "call_123"
        event1.content_block.name = "search"
        yield event1

        # Input delta
        event2 = MagicMock()
        event2.type = "content_block_delta"
        event2.index = 0
        event2.delta.type = "input_json_delta"
        event2.delta.partial_json = '{"query": "test"}'
        yield event2

        # Block stop
        event3 = MagicMock()
        event3.type = "content_block_stop"
        event3.index = 0
        yield event3

        # Message delta with stop reason
        event4 = MagicMock()
        event4.type = "message_delta"
        event4.delta.stop_reason = "tool_use"
        yield event4

    mock_stream.__aiter__.side_effect = tool_stream_generator

    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        api_key="sk-test",
    )

    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Search for something"}]):
        chunks.append(chunk)

    # chunks:
    # 0: content_block_start (no output unless we change implementation)
    # 1: content_block_delta (no output)
    # 2: content_block_stop (tool_calls)
    # 3: message_delta (finish_reason)

    assert any(c.tool_calls for c in chunks)
    tool_call_chunk = next(c for c in chunks if c.tool_calls)
    assert tool_call_chunk.tool_calls[0]["id"] == "call_123"
    assert tool_call_chunk.tool_calls[0]["function"]["name"] == "search"
    assert tool_call_chunk.tool_calls[0]["function"]["arguments"] == '{"query": "test"}'

    finish_chunk = next(c for c in chunks if c.finish_reason)
    assert finish_chunk.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_convert_messages_with_thinking(mock_anthropic):
    """Test message conversion with thinking block."""
    model = AnthropicModel(
        id="anthropic/claude-3-opus", name="claude-3-opus", api_key="sk-test"
    )

    messages = [
        {
            "role": "assistant",
            "content": "Final answer",
            "reasoning_content": "Chain of thought",
        }
    ]

    _, converted = model._convert_messages(messages)

    assert len(converted) == 1
    assert converted[0]["role"] == "assistant"
    content = converted[0]["content"]
    assert len(content) == 2
    assert content[0] == {"type": "thinking", "thinking": "Chain of thought"}
    assert content[1] == {"type": "text", "text": "Final answer"}


@pytest.mark.asyncio
async def test_arun_stream_thinking(mock_anthropic):
    """Test streaming with thinking_delta events."""
    mock_client = mock_anthropic.return_value
    mock_stream = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_stream)

    async def thinking_stream_generator():
        # Thinking delta
        event1 = MagicMock()
        event1.type = "content_block_delta"
        event1.delta.type = "thinking_delta"
        event1.delta.thinking = "Thinking..."
        yield event1

        # Text delta
        event2 = MagicMock()
        event2.type = "content_block_delta"
        event2.delta.type = "text_delta"
        event2.delta.text = "Hello"
        yield event2

    mock_stream.__aiter__.side_effect = thinking_stream_generator

    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        api_key="sk-test",
    )

    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert chunks[0].reasoning_content == "Thinking..."
    assert chunks[1].content == "Hello"


@pytest.mark.asyncio
async def test_arun_stream_usage(mock_anthropic):
    """Test streaming with usage events."""
    mock_client = mock_anthropic.return_value
    mock_stream = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_stream)

    async def usage_stream_generator():
        # message_start with usage
        event1 = MagicMock()
        event1.type = "message_start"
        event1.message.usage.input_tokens = 10
        event1.message.usage.output_tokens = 5
        yield event1

        # message_delta with usage
        event2 = MagicMock()
        event2.type = "message_delta"
        event2.usage.output_tokens = 15
        event2.delta.stop_reason = "end_turn"
        yield event2

    mock_stream.__aiter__.side_effect = usage_stream_generator

    model = AnthropicModel(
        id="anthropic/claude-3-opus",
        name="claude-3-opus",
        api_key="sk-test",
    )

    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert chunks[0].usage["input_tokens"] == 10
    assert chunks[0].usage["output_tokens"] == 5
    assert chunks[0].usage["total_tokens"] == 15

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
        api_key="sk-test",
    )

    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0].content == "Hello"
    assert chunks[1].finish_reason == "end_turn"
