import time

import pytest

from agio.domain import ToolResult
from agio.tools.executor import ToolExecutor
from agio.runtime import Wire
from agio.tools import BaseTool
from agio.runtime.context import ExecutionContext


class SuccessTool(BaseTool):
    """A tool that succeeds"""

    def get_name(self) -> str:
        return "success_tool"

    def get_description(self) -> str:
        return "A tool that succeeds"

    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    def is_concurrency_safe(self) -> bool:
        return True

    async def execute(
        self, parameters: dict, context: ExecutionContext, abort_signal=None
    ) -> ToolResult:
        start_time = time.time()
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content="success",
            output="success",
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            is_success=True,
        )


class FailureTool(BaseTool):
    """A tool that fails"""

    def get_name(self) -> str:
        return "failure_tool"

    def get_description(self) -> str:
        return "A tool that fails"

    def get_parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    def is_concurrency_safe(self) -> bool:
        return True

    async def execute(
        self, parameters: dict, context: ExecutionContext, abort_signal=None
    ) -> ToolResult:
        raise ValueError("Intentional failure")


@pytest.fixture
def mock_context():
    return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())


@pytest.mark.asyncio
async def test_tool_executor_success(mock_context):
    """Test successful tool execution"""
    tools = [SuccessTool()]
    executor = ToolExecutor(tools)

    tool_call = {
        "id": "call_123",
        "function": {"name": "success_tool", "arguments": "{}"},
    }

    result = await executor.execute(tool_call, context=mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is True
    assert result.tool_name == "success_tool"
    assert result.tool_call_id == "call_123"
    assert result.content == "success"
    assert result.error is None


@pytest.mark.asyncio
async def test_tool_executor_failure(mock_context):
    """Test tool execution with error"""
    tools = [FailureTool()]
    executor = ToolExecutor(tools)

    tool_call = {
        "id": "call_456",
        "function": {"name": "failure_tool", "arguments": "{}"},
    }

    result = await executor.execute(tool_call, context=mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert result.tool_name == "failure_tool"
    assert result.tool_call_id == "call_456"
    assert "Intentional failure" in result.error


@pytest.mark.asyncio
async def test_tool_executor_not_found(mock_context):
    """Test tool execution when tool is not found"""
    tools = [SuccessTool()]
    executor = ToolExecutor(tools)

    tool_call = {
        "id": "call_789",
        "function": {"name": "nonexistent_tool", "arguments": "{}"},
    }

    result = await executor.execute(tool_call, context=mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert result.tool_name == "nonexistent_tool"
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_executor_batch(mock_context):
    """Test batch execution of multiple tools"""
    tools = [SuccessTool(), FailureTool()]
    executor = ToolExecutor(tools)

    tool_calls = [
        {"id": "call_1", "function": {"name": "success_tool", "arguments": "{}"}},
        {"id": "call_2", "function": {"name": "failure_tool", "arguments": "{}"}},
    ]

    results = await executor.execute_batch(tool_calls, context=mock_context)

    assert len(results) == 2
    assert results[0].is_success is True
    assert results[1].is_success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
