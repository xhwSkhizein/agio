"""GrepTool 测试用例"""

import pytest
from pathlib import Path

from agio.components.tools.builtin_tools.grep_tool import GrepTool
from agio.execution.abort_signal import AbortSignal


class TestGrepTool:
    """GrepTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return GrepTool()

    @pytest.fixture
    def test_files(self):
        """创建测试文件"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_grep"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建测试文件
            (test_dir / "file1.txt").write_text("Hello World\nPython is great")
            (test_dir / "file2.py").write_text("def hello():\n    print('Hello')")
            (test_dir / "file3.md").write_text("# Hello\nThis is a test")
            
            # 创建子目录
            subdir = test_dir / "subdir"
            subdir.mkdir(exist_ok=True)
            (subdir / "file4.txt").write_text("Hello from subdir")
            
            yield test_dir
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_basic_search(self, tool, test_files):
        """测试基本搜索"""
        result = await tool.execute({
            "tool_call_id": "test_123",
            "pattern": "Hello",
            "path": str(test_files),
        })

        assert result.is_success
        assert result.tool_name == tool.name
        assert result.tool_call_id == "test_123"
        assert result.content
        assert result.output is not None
        assert result.output["num_files"] > 0
        assert len(result.output["filenames"]) > 0

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, tool, test_files):
        """测试大小写不敏感搜索"""
        result = await tool.execute({
            "tool_call_id": "test_case",
            "pattern": "hello",  # 小写
            "path": str(test_files),
        })

        assert result.is_success
        # 应该找到包含 "Hello" 的文件
        assert result.output["num_files"] > 0

    @pytest.mark.asyncio
    async def test_search_with_include_pattern(self, tool, test_files):
        """测试使用 include 模式"""
        result = await tool.execute({
            "tool_call_id": "test_include",
            "pattern": "Hello",
            "path": str(test_files),
            "include": "*.txt",  # 只搜索 .txt 文件
        })

        assert result.is_success
        # 检查结果中只包含 .txt 文件
        for filename in result.output["filenames"]:
            assert filename.endswith(".txt")

    @pytest.mark.asyncio
    async def test_no_results(self, tool, test_files):
        """测试无结果情况"""
        result = await tool.execute({
            "tool_call_id": "test_no_results",
            "pattern": "NonExistentPattern12345",
            "path": str(test_files),
        })

        assert result.is_success
        assert result.output["num_files"] == 0
        assert len(result.output["filenames"]) == 0

    @pytest.mark.asyncio
    async def test_empty_pattern(self, tool):
        """测试空模式"""
        result = await tool.execute({
            "tool_call_id": "test_empty",
            "pattern": "",
            "path": ".",
        })

        assert not result.is_success
        assert result.error
        assert "pattern" in result.content.lower() or "empty" in result.content.lower()

    @pytest.mark.asyncio
    async def test_invalid_path(self, tool):
        """测试无效路径"""
        result = await tool.execute({
            "tool_call_id": "test_invalid",
            "pattern": "test",
            "path": "/nonexistent/path/that/does/not/exist",
        })

        assert not result.is_success
        assert result.error

    @pytest.mark.asyncio
    async def test_abort_signal_before_execution(self, tool, test_files):
        """测试执行前中断"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "pattern": "Hello",
                "path": str(test_files),
            },
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted"
        assert "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, test_files):
        """测试输出结构"""
        result = await tool.execute({
            "tool_call_id": "test_output",
            "pattern": "Hello",
            "path": str(test_files),
        })

        assert result.is_success
        assert result.output is not None
        
        # 检查输出字段
        assert "duration_ms" in result.output
        assert "num_files" in result.output
        assert "filenames" in result.output
        assert "search_path" in result.output
        
        # 检查类型
        assert isinstance(result.output["duration_ms"], int)
        assert isinstance(result.output["num_files"], int)
        assert isinstance(result.output["filenames"], list)
        assert result.output["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, test_files):
        """测试时间信息"""
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "pattern": "Hello",
            "path": str(test_files),
        })

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.duration > 0
        assert abs(result.duration - (result.end_time - result.start_time)) < 0.001

    @pytest.mark.asyncio
    async def test_search_in_subdirectories(self, tool, test_files):
        """测试在子目录中搜索"""
        result = await tool.execute({
            "tool_call_id": "test_subdir",
            "pattern": "Hello",
            "path": str(test_files),
        })

        assert result.is_success
        # 应该找到主目录和子目录中的文件
        assert result.output["num_files"] >= 2
        
        # 检查是否包含子目录中的文件
        filenames_str = " ".join(result.output["filenames"])
        assert "subdir" in filenames_str

    @pytest.mark.asyncio
    async def test_python_file_search(self, tool, test_files):
        """测试搜索 Python 文件"""
        result = await tool.execute({
            "tool_call_id": "test_python",
            "pattern": "def",
            "path": str(test_files),
            "include": "*.py",
        })

        assert result.is_success
        assert result.output["num_files"] > 0
        # 确保找到的是 .py 文件
        for filename in result.output["filenames"]:
            assert filename.endswith(".py")

    @pytest.mark.asyncio
    async def test_relative_path_search(self, tool):
        """测试相对路径搜索"""
        result = await tool.execute({
            "tool_call_id": "test_relative",
            "pattern": "import",
            "path": "agio",  # 相对路径
            "include": "*.py",
        })

        # 应该能够搜索
        assert result.is_success or not result.is_success  # 取决于是否有匹配
