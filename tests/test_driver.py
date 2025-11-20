import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from agio.drivers.openai_driver import OpenAIModelDriver
from agio.core.loop import LoopConfig
from agio.core.events import ModelEventType
from agio.models.base import ModelDelta
from agio.tools.base import Tool
from agio.domain.messages import UserMessage


class MockTool(Tool):
    def __init__(self):
        self.name = "mock_tool"
        self.description = "A mock tool for testing"
    
    async def execute(self, **kwargs):
        return "mock_result"
    
    def to_openai_schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}}
            }
        }


@pytest.mark.asyncio
async def test_model_driver_text_only():
    """Test ModelDriver with text-only response (no tool calls)"""
    mock_model = MagicMock()
    
    async def mock_stream(*args, **kwargs):
        yield ModelDelta(content="Hello")
        yield ModelDelta(content=" World")
        yield ModelDelta(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    
    mock_model.astream = mock_stream
    
    driver = OpenAIModelDriver(model=mock_model)
    messages = [UserMessage(content="Hi")]
    config = LoopConfig(max_steps=1)
    
    events = []
    async for event in driver.run(messages, [], config):
        events.append(event)
    
    # Verify we got text deltas and usage
    text_events = [e for e in events if e.type == ModelEventType.TEXT_DELTA]
    usage_events = [e for e in events if e.type == ModelEventType.USAGE]
    
    assert len(text_events) == 2
    assert text_events[0].content == "Hello"
    assert text_events[1].content == " World"
    assert len(usage_events) == 1


@pytest.mark.asyncio
async def test_model_driver_with_tool_call():
    """Test ModelDriver with tool call"""
    mock_model = MagicMock()
    
    call_count = 0
    
    async def mock_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call: model wants to use a tool
            yield ModelDelta(tool_calls=[{
                "index": 0,
                "id": "call_123",
                "function": {"name": "mock_tool", "arguments": "{}"}
            }])
            yield ModelDelta(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        else:
            # Second call: model responds with result
            yield ModelDelta(content="Tool executed successfully")
            yield ModelDelta(usage={"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23})
    
    mock_model.astream = mock_stream
    
    driver = OpenAIModelDriver(model=mock_model)
    messages = [UserMessage(content="Use the tool")]
    tools = [MockTool()]
    config = LoopConfig(max_steps=5)
    
    events = []
    async for event in driver.run(messages, tools, config):
        events.append(event)
    
    # Verify we got tool call events
    tool_start_events = [e for e in events if e.type == ModelEventType.TOOL_CALL_STARTED]
    tool_finish_events = [e for e in events if e.type == ModelEventType.TOOL_CALL_FINISHED]
    text_events = [e for e in events if e.type == ModelEventType.TEXT_DELTA]
    
    assert len(tool_start_events) == 1
    assert len(tool_finish_events) == 1
    assert len(text_events) >= 1
    assert tool_finish_events[0].tool_result["is_success"] is True


@pytest.mark.asyncio
async def test_model_driver_max_steps():
    """Test ModelDriver respects max_steps limit"""
    mock_model = MagicMock()
    
    async def mock_stream(*args, **kwargs):
        # Always request a tool call (infinite loop scenario)
        yield ModelDelta(tool_calls=[{
            "index": 0,
            "id": "call_123",
            "function": {"name": "mock_tool", "arguments": "{}"}
        }])
        yield ModelDelta(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    
    mock_model.astream = mock_stream
    
    driver = OpenAIModelDriver(model=mock_model)
    messages = [UserMessage(content="Keep using tools")]
    tools = [MockTool()]
    config = LoopConfig(max_steps=3)
    
    events = []
    async for event in driver.run(messages, tools, config):
        events.append(event)
    
    # Should stop after 3 steps
    tool_start_events = [e for e in events if e.type == ModelEventType.TOOL_CALL_STARTED]
    assert len(tool_start_events) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
