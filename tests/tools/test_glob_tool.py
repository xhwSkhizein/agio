"""GlobTool 测试用例"""

import pytest
from pathlib import Path

from agio.providers.tools.builtin.glob_tool import GlobTool
from agio.domain import ExecutionContext
from agio.runtime import Wire
from agio.agent import AbortSignal


class TestGlobTool:
    """GlobTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return GlobTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.mark.asyncio
    async def test_basic_glob(self, tool, context):
        """测试基本 glob 搜索"""
        result = await tool.execute({
            "tool_call_id": "test_123",
            "pattern": "*.py",
            "path": "agio",
        }, context=context)

        assert result.is_success
        assert result.tool_name == tool.name
        assert result.output is not None
        assert result.output["num_files"] >= 0

    @pytest.mark.asyncio
    async def test_recursive_glob(self, tool, context):
        """测试递归搜索"""
        result = await tool.execute({
            "tool_call_id": "test_recursive",
            "pattern": "**/*.py",
            "path": "tests",
        }, context=context)

        assert result.is_success
        assert result.output["num_files"] >= 0

    @pytest.mark.asyncio
    async def test_recursive_glob_json(self, tool, context):
        """测试递归搜索 JSON 文件（修复 **/*.json 模式问题）"""
        result = await tool.execute(
            {
                "tool_call_id": "test_recursive_json",
                "pattern": "**/*.json",
                "path": ".",
            },
            context=context,
        )

        assert result.is_success
        assert result.output["num_files"] >= 0

    @pytest.mark.asyncio
    async def test_no_results(self, tool, context):
        """测试无结果"""
        result = await tool.execute({
            "tool_call_id": "test_no_results",
            "pattern": "*.nonexistent12345",
            "path": ".",
        }, context=context)

        assert result.is_success
        assert result.output["num_files"] == 0

    @pytest.mark.asyncio
    async def test_invalid_pattern(self, tool, context):
        """测试无效模式"""
        result = await tool.execute({
            "tool_call_id": "test_invalid",
            "pattern": "",
            "path": ".",
        }, context=context)

        assert not result.is_success
        assert result.error

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tool, context):
        """测试不存在的路径"""
        result = await tool.execute({
            "tool_call_id": "test_nonexistent",
            "pattern": "*.py",
            "path": "/nonexistent/path/12345",
        }, context=context)

        assert not result.is_success
        assert "not found" in result.content.lower() or "Error" in result.content

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "pattern": "*.py",
                "path": ".",
            },
            abort_signal=abort_signal,
            context=context,
        )

        assert not result.is_success
        assert result.error == "Aborted"

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, context):
        """测试输出结构"""
        result = await tool.execute({
            "tool_call_id": "test_output",
            "pattern": "*.md",
            "path": ".",
        }, context=context)

        assert result.is_success
        assert "duration_ms" in result.output
        assert "num_files" in result.output
        assert "filenames" in result.output
        assert "truncated" in result.output
        assert isinstance(result.output["filenames"], list)

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, context):
        """测试时间信息"""
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "pattern": "*.py",
            "path": "agio",
        }, context=context)

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.duration > 0
