"""WebFetchTool 测试用例"""

import pytest

from agio.tools.builtin.web_fetch_tool import WebFetchTool
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime import Wire


class TestWebFetchTool:
    """WebFetchTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return WebFetchTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.mark.asyncio
    async def test_tool_creation(self, tool):
        """测试工具创建"""
        assert tool is not None
        assert tool.name == "web_fetch"
        assert tool.timeout_seconds > 0
        assert hasattr(tool, '_config')

    @pytest.mark.asyncio
    async def test_missing_url_and_index(self, tool, context):
        """测试缺少 URL 和 index"""
        result = await tool.execute({
            "tool_call_id": "test_missing",
        }, context=context)

        assert not result.is_success
        assert "url" in result.content.lower() or "index" in result.content.lower() or result.error

    @pytest.mark.asyncio
    async def test_invalid_url(self, tool, context):
        """测试无效 URL"""
        result = await tool.execute({
            "tool_call_id": "test_invalid",
            "url": "not-a-valid-url",
        }, context=context)

        # 应该返回错误或处理无效 URL
        assert not result.is_success or "invalid" in result.content.lower()

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")
        
        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "url": "https://example.com",
            },
            context=context,
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted" or "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, context):
        """测试输出结构（如果成功获取内容）"""
        # 使用一个简单的测试 URL
        result = await tool.execute({
            "tool_call_id": "test_output",
            "url": "https://example.com",
        }, context=context)

        # 如果成功，检查输出结构
        if result.is_success:
            assert result.output is not None
            assert isinstance(result.output, dict)

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, context):
        """测试时间信息"""
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "url": "https://example.com",
        }, context=context)

        if result.is_success:
            assert result.start_time > 0
            assert result.end_time > result.start_time
            assert result.duration > 0

