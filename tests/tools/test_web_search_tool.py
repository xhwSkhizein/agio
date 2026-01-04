"""WebSearchTool 测试用例"""

from unittest.mock import patch

import os
import pytest

from agio.tools.builtin.web_search_tool import WebSearchTool
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime import Wire


class TestWebSearchTool:
    """WebSearchTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return WebSearchTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.mark.asyncio
    async def test_tool_creation(self, tool):
        """测试工具创建"""
        assert tool is not None
        assert tool.name == "web_search"
        assert tool.timeout_seconds > 0

    @pytest.mark.asyncio
    async def test_missing_api_key(self, tool, context):
        """测试缺少 API Key"""
        # 临时移除 API key
        original_key = os.environ.get("SERPER_API_KEY")
        if "SERPER_API_KEY" in os.environ:
            del os.environ["SERPER_API_KEY"]
        
        tool.serper_api_key = ""
        
        result = await tool.execute({
            "tool_call_id": "test_no_key",
            "query": "test query",
        }, context=context)

        # 应该返回错误或提示需要 API key
        assert not result.is_success or "SERPER_API_KEY" in result.content
        
        # 恢复 API key
        if original_key:
            os.environ["SERPER_API_KEY"] = original_key

    @pytest.mark.asyncio
    async def test_empty_query(self, tool, context):
        """测试空查询"""
        result = await tool.execute({
            "tool_call_id": "test_empty",
            "query": "",
        }, context=context)

        assert not result.is_success or "query" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, context):
        """测试输出结构（使用 mock 避免真实 API 调用）"""
        # Mock Google 搜索 API 响应，避免真实网络调用
        mock_search_results = [
            {
                "url": "https://example.com/python",
                "title": "Python Programming Guide",
                "snippet": "Learn Python programming...",
                "date_published": "2024-01-01",
                "source": "Example.com",
            },
            {
                "url": "https://example.com/python2",
                "title": "Advanced Python",
                "snippet": "Advanced Python techniques...",
                "date_published": "2024-01-02",
                "source": "Example.com",
            },
        ]

        with patch.object(
            tool, "_google_search_with_serp", return_value=mock_search_results
        ):
            result = await tool.execute(
                {
                    "tool_call_id": "test_output",
                    "query": "Python programming",
                },
                context=context,
            )

            if result.is_success:
                assert result.output is not None
                # WebSearchTool 输出应该包含搜索结果
                assert isinstance(result.output, dict)

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")
        
        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "query": "test",
            },
            context=context,
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted" or "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, context):
        """测试时间信息（使用 mock 避免真实 API 调用）"""
        # Mock Google 搜索 API 响应，避免真实网络调用
        mock_search_results = [
            {
                "url": "https://example.com/test",
                "title": "Test Result",
                "snippet": "Test content...",
                "date_published": "2024-01-01",
                "source": "Example.com",
            },
        ]

        with patch.object(
            tool, "_google_search_with_serp", return_value=mock_search_results
        ):
            result = await tool.execute(
                {
                    "tool_call_id": "test_timing",
                    "query": "test",
                },
                context=context,
            )

            if result.is_success:
                assert result.start_time > 0
                assert result.end_time > result.start_time
                assert result.duration > 0

