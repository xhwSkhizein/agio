"""FileEditTool 测试用例"""

import pytest
from pathlib import Path

from agio.providers.tools.builtin.file_edit_tool import FileEditTool
from agio.agent import AbortSignal
from agio.domain import ExecutionContext
from agio.runtime import Wire


class TestFileEditTool:
    """FileEditTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return FileEditTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.fixture
    def test_file(self):
        """创建测试文件"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_file_edit"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建测试文件
            test_file = test_dir / "test.py"
            content = '''def hello():
    print("Hello")
    return True

def world():
    print("World")
    return False
'''
            test_file.write_text(content)
            
            yield test_file
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_simple_edit(self, tool, test_file, context):
        """测试简单编辑"""
        result = await tool.execute({
            "tool_call_id": "test_123",
            "file_path": str(test_file),
            "old_string": '    print("Hello")',
            "new_string": '    print("Hello, World!")',
        }, context=context)

        assert result.is_success
        assert result.tool_name == tool.name
        assert result.tool_call_id == "test_123"
        
        # 验证文件已更新
        content = test_file.read_text()
        assert 'print("Hello, World!")' in content
        assert 'print("Hello")' not in content

    @pytest.mark.asyncio
    async def test_multiline_edit(self, tool, test_file, context):
        """测试多行编辑"""
        result = await tool.execute({
            "tool_call_id": "test_multiline",
            "file_path": str(test_file),
            "old_string": '''def hello():
    print("Hello")
    return True''',
            "new_string": '''def hello(name="World"):
    print(f"Hello, {name}!")
    return True''',
        }, context=context)

        assert result.is_success
        content = test_file.read_text()
        assert 'def hello(name="World")' in content
        assert 'print(f"Hello, {name}!")' in content

    @pytest.mark.asyncio
    async def test_create_new_file(self, tool, context):
        """测试创建新文件"""
        project_root = Path.cwd()
        new_file = project_root / "tests" / "_temp_file_edit" / "new_file.txt"
        new_file.parent.mkdir(exist_ok=True)
        
        try:
            result = await tool.execute({
                "tool_call_id": "test_create",
                "file_path": str(new_file),
                "old_string": "",  # 空字符串表示创建新文件
                "new_string": "This is a new file\nWith multiple lines\n",
            }, context=context)

            assert result.is_success
            assert new_file.exists()
            content = new_file.read_text()
            assert "This is a new file" in content
        finally:
            if new_file.exists():
                new_file.unlink()

    @pytest.mark.asyncio
    async def test_nonexistent_file_error(self, tool, context):
        """测试编辑不存在的文件（非创建）"""
        result = await tool.execute({
            "tool_call_id": "test_nonexistent",
            "file_path": "/tmp/nonexistent_file_12345.txt",
            "old_string": "old text",
            "new_string": "new text",
        }, context=context)

        assert not result.is_success
        assert result.error

    @pytest.mark.asyncio
    async def test_string_not_found(self, tool, test_file, context):
        """测试要替换的字符串不存在"""
        result = await tool.execute({
            "tool_call_id": "test_not_found",
            "file_path": str(test_file),
            "old_string": "NonExistentString12345",
            "new_string": "replacement",
        }, context=context)

        assert not result.is_success
        assert result.error

    @pytest.mark.asyncio
    async def test_multiple_occurrences_error(self, tool, context):
        """测试字符串出现多次的错误"""
        project_root = Path.cwd()
        test_file = project_root / "tests" / "_temp_file_edit" / "multi.txt"
        test_file.parent.mkdir(exist_ok=True)
        
        try:
            # 创建有重复内容的文件
            test_file.write_text("Hello\nHello\nHello\n")
            
            result = await tool.execute({
                "tool_call_id": "test_multi",
                "file_path": str(test_file),
                "old_string": "Hello",
                "new_string": "Hi",
            }, context=context)

            # 应该失败，因为有多个匹配
            assert not result.is_success
        finally:
            if test_file.exists():
                test_file.unlink()

    @pytest.mark.asyncio
    async def test_abort_signal(self, tool, test_file, context):
        """测试中断信号"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        result = await tool.execute(
            {
                "tool_call_id": "test_abort",
                "file_path": str(test_file),
                "old_string": "old",
                "new_string": "new",
            },
            abort_signal=abort_signal,
            context=context,
        )

        assert not result.is_success
        assert result.error == "Aborted"
        assert "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, test_file, context):
        """测试输出结构"""
        result = await tool.execute({
            "tool_call_id": "test_output",
            "file_path": str(test_file),
            "old_string": '    print("Hello")',
            "new_string": '    print("Hi")',
        }, context=context)

        assert result.is_success
        assert result.output is not None
        
        # 检查输出字段
        assert "file_path" in result.output
        assert "old_string_length" in result.output
        assert "new_string_length" in result.output
        assert "patch_length" in result.output

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, test_file, context):
        """测试时间信息"""
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "file_path": str(test_file),
            "old_string": '    print("Hello")',
            "new_string": '    print("Greetings")',
        }, context=context)

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.duration > 0
        assert abs(result.duration - (result.end_time - result.start_time)) < 0.001

    @pytest.mark.asyncio
    async def test_relative_path_error(self, tool, context):
        """测试相对路径错误"""
        result = await tool.execute({
            "tool_call_id": "test_relative",
            "file_path": "relative/path.txt",
            "old_string": "old",
            "new_string": "new",
        }, context=context)

        assert not result.is_success
        assert "absolute" in result.content.lower() or "Error" in result.content
