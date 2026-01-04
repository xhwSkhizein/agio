"""FileReadTool 测试用例"""

import pytest
from pathlib import Path

from agio.tools.builtin.file_read_tool import FileReadTool
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.runtime import Wire


class TestFileReadTool:
    """FileReadTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return FileReadTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.fixture
    def test_files(self):
        """创建测试文件"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_file_read"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建小文本文件
            small_file = test_dir / "small.txt"
            small_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
            
            # 创建大文本文件
            large_file = test_dir / "large.txt"
            lines = [f"Line {i}\n" for i in range(1, 101)]
            large_file.write_text("".join(lines))
            
            # 创建 Python 文件
            py_file = test_dir / "test.py"
            py_file.write_text('def hello():\n    print("Hello")\n    return True\n')
            
            yield test_dir
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_read_small_file(self, tool, test_files, context):
        """测试读取小文件"""
        file_path = str(test_files / "small.txt")
        result = await tool.execute({
            "tool_call_id": "test_123",
            "file_path": file_path,
        }, context=context)

        assert result.is_success
        assert result.tool_name == tool.name
        assert result.tool_call_id == "test_123"
        assert result.content
        assert "Line 1" in result.content
        assert result.output is not None
        assert result.output["type"] == "text"
        assert result.output["total_lines"] == 5

    @pytest.mark.asyncio
    async def test_read_with_offset(self, tool, test_files, context):
        """测试带偏移量读取"""
        file_path = str(test_files / "small.txt")
        result = await tool.execute({
            "tool_call_id": "test_offset",
            "file_path": file_path,
            "offset": 3,  # 从第3行开始
        }, context=context)

        assert result.is_success
        assert "Line 3" in result.content
        assert "Line 1" not in result.content or "     1" not in result.content

    @pytest.mark.asyncio
    async def test_read_with_limit(self, tool, test_files, context):
        """测试带限制读取"""
        file_path = str(test_files / "large.txt")
        result = await tool.execute({
            "tool_call_id": "test_limit",
            "file_path": file_path,
            "offset": 1,
            "limit": 10,  # 只读10行
        }, context=context)

        assert result.is_success
        assert result.output["num_lines"] == 10
        assert "Line 1" in result.content
        assert "Line 10" in result.content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tool, context):
        """测试读取不存在的文件"""
        result = await tool.execute({
            "tool_call_id": "test_nonexistent",
            "file_path": "/tmp/nonexistent_file_12345.txt",
        }, context=context)

        assert not result.is_success
        assert result.error
        assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_read_with_line_numbers(self, tool, test_files, context):
        """测试带行号的输出"""
        file_path = str(test_files / "test.py")
        result = await tool.execute({
            "tool_call_id": "test_numbers",
            "file_path": file_path,
        }, context=context)

        assert result.is_success
        # 检查行号格式
        assert "     1\t" in result.content
        assert "def hello" in result.content

    @pytest.mark.asyncio
    async def test_relative_path_error(self, tool, context):
        """测试相对路径错误"""
        result = await tool.execute({
            "tool_call_id": "test_relative",
            "file_path": "relative/path.txt",  # 相对路径
        }, context=context)

        assert not result.is_success
        assert "absolute" in result.content.lower() or "Error" in result.content

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, test_files, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        file_path = str(test_files / "small.txt")
        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "file_path": file_path,
            },
            context=context,
            abort_signal=abort_signal,
        )

        assert not result.is_success
        assert result.error == "Aborted"
        assert "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, test_files, context):
        """测试输出结构"""
        file_path = str(test_files / "small.txt")
        result = await tool.execute({
            "tool_call_id": "test_output",
            "file_path": file_path,
        }, context=context)

        assert result.is_success
        assert result.output is not None
        
        # 检查输出字段
        assert "type" in result.output
        assert "file_path" in result.output
        assert "content" in result.output
        assert "num_lines" in result.output
        assert "start_line" in result.output
        assert "total_lines" in result.output
        
        # 检查类型
        assert isinstance(result.output["num_lines"], int)
        assert isinstance(result.output["total_lines"], int)

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, test_files, context):
        """测试时间信息"""
        file_path = str(test_files / "small.txt")
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "file_path": file_path,
        }, context=context)

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.duration > 0
        assert abs(result.duration - (result.end_time - result.start_time)) < 0.001

    @pytest.mark.asyncio
    async def test_empty_file(self, tool, test_files, context):
        """测试空文件"""
        empty_file = test_files / "empty.txt"
        empty_file.write_text("")
        
        result = await tool.execute({
            "tool_call_id": "test_empty",
            "file_path": str(empty_file),
        }, context=context)

        assert result.is_success
        assert result.output["total_lines"] == 0

    @pytest.mark.asyncio
    async def test_read_existing_project_file(self, tool, context):
        """测试读取项目中的实际文件"""
        # 读取 README.md
        project_root = Path.cwd()
        readme = project_root / "README.md"
        
        if readme.exists():
            result = await tool.execute({
                "tool_call_id": "test_real",
                "file_path": str(readme),
                "limit": 5,
            }, context=context)

            assert result.is_success
            assert result.output["num_lines"] <= 5
