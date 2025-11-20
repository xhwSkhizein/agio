import pytest
import asyncio
from agio.execution.tool_executor import ToolExecutor
from agio.tools.base import Tool
from agio.domain.tools import ToolResult


class SuccessTool(Tool):
    def __init__(self):
        self.name = "success_tool"
        self.description = "A tool that succeeds"
    
    async def execute(self, **kwargs):
        return "success"
    
    def to_openai_schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}}
            }
        }


class FailureTool(Tool):
    def __init__(self):
        self.name = "failure_tool"
        self.description = "A tool that fails"
    
    async def execute(self, **kwargs):
        raise ValueError("Intentional failure")
    
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
async def test_tool_executor_success():
    """Test successful tool execution"""
    tools = [SuccessTool()]
    executor = ToolExecutor(tools)
    
    tool_call = {
        "id": "call_123",
        "function": {
            "name": "success_tool",
            "arguments": "{}"
        }
    }
    
    result = await executor.execute(tool_call)
    
    assert isinstance(result, ToolResult)
    assert result.is_success is True
    assert result.tool_name == "success_tool"
    assert result.tool_call_id == "call_123"
    assert result.content == "success"
    assert result.error is None


@pytest.mark.asyncio
async def test_tool_executor_failure():
    """Test tool execution with error"""
    tools = [FailureTool()]
    executor = ToolExecutor(tools)
    
    tool_call = {
        "id": "call_456",
        "function": {
            "name": "failure_tool",
            "arguments": "{}"
        }
    }
    
    result = await executor.execute(tool_call)
    
    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert result.tool_name == "failure_tool"
    assert result.tool_call_id == "call_456"
    assert "Intentional failure" in result.error


@pytest.mark.asyncio
async def test_tool_executor_not_found():
    """Test tool execution when tool is not found"""
    tools = [SuccessTool()]
    executor = ToolExecutor(tools)
    
    tool_call = {
        "id": "call_789",
        "function": {
            "name": "nonexistent_tool",
            "arguments": "{}"
        }
    }
    
    result = await executor.execute(tool_call)
    
    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert result.tool_name == "nonexistent_tool"
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_executor_batch():
    """Test batch execution of multiple tools"""
    tools = [SuccessTool(), FailureTool()]
    executor = ToolExecutor(tools)
    
    tool_calls = [
        {
            "id": "call_1",
            "function": {"name": "success_tool", "arguments": "{}"}
        },
        {
            "id": "call_2",
            "function": {"name": "failure_tool", "arguments": "{}"}
        }
    ]
    
    results = await executor.execute_batch(tool_calls)
    
    assert len(results) == 2
    assert results[0].is_success is True
    assert results[1].is_success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
