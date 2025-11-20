"""
测试 Model 层（替代旧的 test_driver.py）

注意：旧的 OpenAIModelDriver 测试已过时，因为新架构中：
- ModelDriver 已删除
- 使用 Model.arun_stream() 替代
- LLM Call Loop 逻辑移到了 AgentExecutor

这些测试已被 test_new_arch.py 替代。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from agio.models.base import Model, StreamChunk
from agio.tools.base import Tool


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
async def test_model_stream_basic():
    """Test Model.arun_stream basic functionality"""

    # Create a mock model
    class MockModel(Model):
        id: str = "test/mock"
        name: str = "mock"

        async def arun_stream(self, messages, tools=None):
            yield StreamChunk(content="Hello")
            yield StreamChunk(content=" World")
            yield StreamChunk(usage={"total_tokens": 10})

    model = MockModel()

    chunks = []
    async for chunk in model.arun_stream([{"role": "user", "content": "Hi"}]):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0].content == "Hello"
    assert chunks[1].content == " World"
    assert chunks[2].usage == {"total_tokens": 10}


@pytest.mark.asyncio
async def test_model_stream_with_tool_calls():
    """Test Model.arun_stream with tool calls"""

    class MockModel(Model):
        id: str = "test/mock"
        name: str = "mock"

        async def arun_stream(self, messages, tools=None):
            yield StreamChunk(
                tool_calls=[
                    {
                        "index": 0,
                        "id": "call_123",
                        "function": {"name": "mock_tool", "arguments": "{}"},
                    }
                ]
            )
            yield StreamChunk(finish_reason="tool_calls")

    model = MockModel()

    chunks = []
    async for chunk in model.arun_stream(
        [{"role": "user", "content": "Use tool"}], tools=[MockTool().to_openai_schema()]
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0].tool_calls is not None
    assert chunks[0].tool_calls[0]["id"] == "call_123"
    assert chunks[1].finish_reason == "tool_calls"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
