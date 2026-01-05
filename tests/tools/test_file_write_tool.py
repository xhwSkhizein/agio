"""FileWriteTool 测试用例"""

import pytest
from pathlib import Path

from agio.tools.builtin.file_write_tool import FileWriteTool
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime import Wire


class TestFileWriteTool:
    """FileWriteTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return FileWriteTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(
            run_id="test_run", session_id="test_session", wire=Wire()
        )

    @pytest.fixture
    def test_dir(self):
        """创建测试目录"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_file_write"
        test_dir.mkdir(exist_ok=True)

        yield test_dir

        import shutil

        if test_dir.exists():
            shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_write_new_file(self, tool, test_dir, context):
        """测试创建新文件"""
        file_path = str(test_dir / "new_file.txt")
        content = "This is a new file\nWith multiple lines\n"

        result = await tool.execute(
            {
                "tool_call_id": "test_123",
                "file_path": file_path,
                "content": content,
            },
            context=context,
        )

        assert result.is_success
        assert result.tool_name == tool.name
        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, tool, test_dir, context):
        """测试覆盖现有文件"""
        file_path = test_dir / "existing.txt"
        file_path.write_text("Old content")

        result = await tool.execute(
            {
                "tool_call_id": "test_overwrite",
                "file_path": str(file_path),
                "content": "New content",
            },
            context=context,
        )

        assert result.is_success
        assert Path(file_path).read_text() == "New content"

    @pytest.mark.asyncio
    async def test_create_directory_structure(self, tool, test_dir, context):
        """测试自动创建目录结构"""
        file_path = str(test_dir / "subdir" / "nested" / "file.txt")

        result = await tool.execute(
            {
                "tool_call_id": "test_dir",
                "file_path": file_path,
                "content": "Content",
            },
            context=context,
        )

        assert result.is_success
        assert Path(file_path).exists()
        assert Path(file_path).parent.exists()

    @pytest.mark.asyncio
    async def test_relative_path_error(self, tool, context):
        """测试相对路径错误"""
        result = await tool.execute(
            {
                "tool_call_id": "test_relative",
                "file_path": "relative/path.txt",
                "content": "Content",
            },
            context=context,
        )

        assert not result.is_success
        assert "absolute" in result.content.lower() or "Error" in result.content

    @pytest.mark.asyncio
    async def test_empty_content(self, tool, test_dir, context):
        """测试写入空内容"""
        file_path = str(test_dir / "empty.txt")

        result = await tool.execute(
            {
                "tool_call_id": "test_empty",
                "file_path": file_path,
                "content": "",
            },
            context=context,
        )

        assert result.is_success
        assert Path(file_path).exists()
        assert Path(file_path).read_text() == ""

    @pytest.mark.asyncio
    async def test_large_content(self, tool, test_dir, context):
        """测试写入大内容"""
        file_path = str(test_dir / "large.txt")
        content = "Line\n" * 1000

        result = await tool.execute(
            {
                "tool_call_id": "test_large",
                "file_path": file_path,
                "content": content,
            },
            context=context,
        )

        assert result.is_success
        assert len(Path(file_path).read_text()) == len(content)

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, test_dir, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        file_path = str(test_dir / "abort.txt")
        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "file_path": file_path,
                "content": "Content",
            },
            context=context,
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted"

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, test_dir, context):
        """测试输出结构"""
        file_path = str(test_dir / "output.txt")
        result = await tool.execute(
            {
                "tool_call_id": "test_output",
                "file_path": file_path,
                "content": "Test content",
            },
            context=context,
        )

        assert result.is_success
        assert result.output is not None
        assert "file_path" in result.output
        assert "content_length" in result.output or "content" in result.output

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, test_dir, context):
        """测试时间信息"""
        file_path = str(test_dir / "timing.txt")
        result = await tool.execute(
            {
                "tool_call_id": "test_timing",
                "file_path": file_path,
                "content": "Content",
            },
            context=context,
        )

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time >= result.start_time
        assert result.duration >= 0
