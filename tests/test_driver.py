"""
测试 Model 层

测试 Model.arun_stream() 的基本功能。
"""

import time

import pytest

from agio.components.models.base import Model, StreamChunk
from agio.components.tools import BaseTool
from agio.core.events import ToolResult


class MockTool(BaseTool):
    """A mock tool for testing"""

    def get_name(self) -> str:
        return "mock_tool"

    def get_description(self) -> str:
        return "A mock tool for testing"

    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    def is_concurrency_safe(self) -> bool:
        return True

    async def execute(self, parameters: dict, abort_signal=None) -> ToolResult:
        start_time = time.time()
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content="mock_result",
            output="mock_result",
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            is_success=True,
        )


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
