"""BashTool 测试用例"""

import sys

import pytest

from agio.tools.builtin.bash_tool import BashTool
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime import Wire

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="BashTool is not supported on Windows (requires /bin/bash)",
)


class TestBashTool:
    """BashTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return BashTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(
            run_id="test_run", session_id="test_session", wire=Wire()
        )

    @pytest.mark.asyncio
    async def test_simple_command(self, tool, context):
        """测试简单命令"""
        result = await tool.execute(
            {
                "tool_call_id": "test_123",
                "command": "echo 'Hello World'",
            },
            context=context,
        )

        assert result.is_success
        assert result.tool_name == tool.name
        assert "Hello World" in result.content or "Hello World" in str(result.output)

    @pytest.mark.asyncio
    async def test_command_with_output(self, tool, context):
        """测试有输出的命令"""
        result = await tool.execute(
            {
                "tool_call_id": "test_output",
                "command": "echo 'Test output'",
            },
            context=context,
        )

        assert result.is_success
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_banned_command(self, tool, context):
        """测试禁用命令"""
        result = await tool.execute(
            {
                "tool_call_id": "test_banned",
                "command": "curl https://example.com",
            },
            context=context,
        )

        # 应该被验证拒绝
        assert not result.is_success or "not allowed" in result.content.lower()

    @pytest.mark.asyncio
    async def test_empty_command(self, tool, context):
        """测试空命令"""
        result = await tool.execute(
            {
                "tool_call_id": "test_empty",
                "command": "",
            },
            context=context,
        )

        assert not result.is_success
        assert "empty" in result.content.lower() or result.error

    @pytest.mark.asyncio
    async def test_command_with_timeout(self, tool, context):
        """测试带超时的命令"""
        result = await tool.execute(
            {
                "tool_call_id": "test_timeout",
                "command": "echo 'Test'",
                "timeout": 5000,
            },
            context=context,
        )

        assert result.is_success

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "command": "sleep 1",
            },
            context=context,
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted" or "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, context):
        """测试输出结构"""
        result = await tool.execute(
            {
                "tool_call_id": "test_output",
                "command": "echo 'Test'",
            },
            context=context,
        )

        assert result.is_success
        assert result.output is not None
        # BashTool 输出应该包含 stdout, stderr, code 等字段
        assert isinstance(result.output, dict)

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, context):
        """测试时间信息"""
        result = await tool.execute(
            {
                "tool_call_id": "test_timing",
                "command": "echo 'Test'",
            },
            context=context,
        )

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time >= result.start_time
        assert result.duration >= 0
