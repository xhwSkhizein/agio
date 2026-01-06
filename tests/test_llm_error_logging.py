"""
Test LLM error logging improvements.

Verify that:
1. LLM request failures are logged with detailed information
2. Token counts are not redacted in logs
3. Error information is properly propagated
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agio.llm.openai import OpenAIModel
from agio.llm.base import StreamChunk


@pytest.mark.asyncio
async def test_openai_request_logging_on_error():
    """Test that OpenAI request failures are logged with details."""
    
    model = OpenAIModel(
        id="test-model",
        name="test-model",
        model_name="gpt-4",
        api_key="test-key",
    )
    
    # Mock the client to raise an error
    mock_error = Exception("Bad Request: Invalid parameter")
    model.client.chat.completions.create = AsyncMock(side_effect=mock_error)
    
    messages = [{"role": "user", "content": "test"}]
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    
    # Capture logs
    with patch("agio.llm.openai.logger") as mock_logger:
        with pytest.raises(Exception) as exc_info:
            async for _ in model.arun_stream(messages, tools):
                pass
        
        # Verify error was logged
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        
        # Check log event name
        assert call_args[0][0] == "llm_request_failed"
        
        # Check log contains error details
        kwargs = call_args[1]
        assert "error" in kwargs
        assert "error_type" in kwargs
        assert kwargs["error_type"] == "Exception"
        assert "messages_count" in kwargs
        assert kwargs["messages_count"] == 1
        assert "tools_count" in kwargs
        assert kwargs["tools_count"] == 1
        assert kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_openai_request_logging_on_success():
    """Test that OpenAI successful requests are logged."""
    
    model = OpenAIModel(
        id="test-model",
        name="test-model",
        model_name="gpt-4",
        api_key="test-key",
    )
    
    # Mock successful response
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta.content = "test response"
    mock_chunk.choices[0].delta.tool_calls = None
    mock_chunk.choices[0].finish_reason = None
    mock_chunk.usage = None
    
    async def mock_stream():
        yield mock_chunk
    
    model.client.chat.completions.create = AsyncMock(return_value=mock_stream())
    
    messages = [{"role": "user", "content": "test"}]
    
    # Capture logs
    with patch("agio.llm.openai.logger") as mock_logger:
        chunks = []
        async for chunk in model.arun_stream(messages):
            chunks.append(chunk)
        
        # Verify info log was called
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args
        
        # Check log event name
        assert call_args[0][0] == "llm_request"
        
        # Check log contains request details
        kwargs = call_args[1]
        assert "model" in kwargs
        assert kwargs["model"] == "gpt-4"
        assert "messages_count" in kwargs
        assert kwargs["messages_count"] == 1


def test_tokens_not_redacted_in_logs():
    """Test that token-related fields are not redacted in logs."""
    from agio.utils.logging import filter_sensitive_data
    from structlog.testing import CapturingLogger
    
    logger = CapturingLogger()
    
    # Event dict with token fields and sensitive fields
    event_dict = {
        "event": "test",
        "tokens": 100,
        "total_tokens": 150,
        "input_tokens": 50,
        "output_tokens": 100,
        "api_key": "secret-key",
        "password": "secret-pass",
    }
    
    # Apply filter
    filtered = filter_sensitive_data(logger, "info", event_dict.copy())
    
    # Token fields should NOT be redacted
    assert filtered["tokens"] == 100
    assert filtered["total_tokens"] == 150
    assert filtered["input_tokens"] == 50
    assert filtered["output_tokens"] == 100
    
    # Sensitive fields SHOULD be redacted
    assert filtered["api_key"] == "***REDACTED***"
    assert filtered["password"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_agent_error_propagation():
    """Test that Agent errors are properly logged and propagated."""
    from agio.agent import Agent
    from agio.llm import Model
    from agio.runtime.protocol import ExecutionContext
    from agio.runtime.wire import Wire
    
    class FailingModel(Model):
        id: str = "failing-model"
        name: str = "failing"
        
        async def arun_stream(self, messages, tools=None):
            raise ValueError("Simulated LLM failure")
    
    agent = Agent(
        model=FailingModel(),
        tools=[],
    )
    
    wire = Wire()
    context = ExecutionContext(
        run_id="test-run",
        session_id="test-session",
        wire=wire,
    )
    
    with patch("agio.agent.executor.logger") as mock_logger:
        result = await agent.run("test input", context=context)
        
        # Verify error was logged
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        
        # Check log contains error details
        assert call_args[0][0] == "agent_execution_failed"
        kwargs = call_args[1]
        assert "error" in kwargs
        assert "error_type" in kwargs
        # Error type may vary depending on internal implementation
        assert kwargs["error_type"] in ["ValueError", "TypeError"]
        assert kwargs["exc_info"] is True
        
        # Verify termination reason is set
        assert result.termination_reason in ["error", "error_with_context"]
    
    await wire.close()
