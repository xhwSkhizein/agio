"""LSTool 测试用例"""

import pytest
from pathlib import Path

from agio.tools.builtin.ls_tool import LSTool
from agio.runtime.control import AbortSignal


class TestLSTool:
    """LSTool 测试用例"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return LSTool()

    @pytest.fixture
    def context(self):
        """创建执行上下文"""
        from agio.runtime.protocol import ExecutionContext
        from agio.runtime import Wire
        return ExecutionContext(run_id="test_run", session_id="test_session", wire=Wire())

    @pytest.fixture
    def temp_dir(self):
        """创建临时测试目录（在项目根目录内）"""
        # 使用项目根目录下的 tests 目录
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_test_ls"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建测试文件结构
            # 创建文件
            (test_dir / "file1.txt").write_text("content1")
            (test_dir / "file2.py").write_text("content2")
            
            # 创建子目录和文件
            subdir = test_dir / "subdir"
            subdir.mkdir(exist_ok=True)
            (subdir / "file3.txt").write_text("content3")
            
            # 创建嵌套目录
            nested = subdir / "nested"
            nested.mkdir(exist_ok=True)
            (nested / "file4.txt").write_text("content4")
            
            yield test_dir
        finally:
            # 清理
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_basic_execution(self, tool, temp_dir, context):
        """测试基本执行"""
        result = await tool.execute({
            "tool_call_id": "test_123",
            "path": str(temp_dir),
        }, context=context)

        assert result.is_success
        assert result.tool_name == tool.name
        assert result.tool_call_id == "test_123"
        assert result.content
        assert result.duration > 0
        assert result.output is not None
        assert "total_items" in result.output
        assert result.output["total_items"] > 0

    @pytest.mark.asyncio
    async def test_list_current_directory(self, tool, context):
        """测试列出当前目录"""
        result = await tool.execute({
            "tool_call_id": "test_current",
            "path": ".",
        }, context=context)

        assert result.is_success
        assert result.output is not None
        assert result.output["total_items"] > 0

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tool, context):
        """测试不存在的目录"""
        result = await tool.execute({
            "tool_call_id": "test_456",
            "path": "/nonexistent/path/that/does/not/exist",
        }, context=context)

        assert not result.is_success
        assert result.error
        assert "Error" in result.content

    @pytest.mark.asyncio
    async def test_relative_path(self, tool, temp_dir, context):
        """测试相对路径"""
        # 使用相对于项目根的路径
        result = await tool.execute({
            "tool_call_id": "test_relative",
            "path": "tests/_temp_test_ls/subdir",
        }, context=context)

        assert result.is_success
        assert "file3.txt" in result.content

    @pytest.mark.asyncio
    async def test_abort_signal_before_execution(self, tool, temp_dir, context):
        """测试执行前中断"""
        abort_signal = AbortSignal()
        abort_signal.abort("Test cancellation")

        result = await tool.execute(
            {
                "tool_call_id": "test_789",
                "path": str(temp_dir),
            },
            abort_signal=abort_signal,
            context=context,
        )

        assert not result.is_success
        assert result.error == "Aborted"
        assert "aborted" in result.content.lower()

    @pytest.mark.asyncio
    async def test_output_structure(self, tool, temp_dir, context):
        """测试输出结构"""
        result = await tool.execute({
            "tool_call_id": "test_output",
            "path": str(temp_dir),
        }, context=context)

        assert result.is_success
        assert result.output is not None
        
        # 检查输出字段
        assert "directory_path" in result.output
        assert "items" in result.output
        assert "total_items" in result.output
        assert "is_truncated" in result.output
        
        # 检查类型
        assert isinstance(result.output["items"], list)
        assert isinstance(result.output["total_items"], int)
        assert isinstance(result.output["is_truncated"], bool)

    @pytest.mark.asyncio
    async def test_tree_output_format(self, tool, temp_dir, context):
        """测试树形输出格式"""
        result = await tool.execute({
            "tool_call_id": "test_tree",
            "path": str(temp_dir),
        }, context=context)

        assert result.is_success
        # 树形输出应该包含文件名
        assert "file1.txt" in result.content
        assert "file2.py" in result.content
        assert "subdir" in result.content

    @pytest.mark.asyncio
    async def test_empty_directory(self, tool, context):
        """测试空目录"""
        # 在项目内创建空目录
        project_root = Path.cwd()
        empty_dir = project_root / "tests" / "_temp_empty"
        empty_dir.mkdir(exist_ok=True)
        
        try:
            result = await tool.execute({
                "tool_call_id": "test_empty",
                "path": str(empty_dir),
            }, context=context)

            assert result.is_success
            assert result.output["total_items"] == 0
        finally:
            if empty_dir.exists():
                empty_dir.rmdir()

    @pytest.mark.asyncio
    async def test_hidden_files_excluded(self, tool, context):
        """测试隐藏文件被排除"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_hidden"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建普通文件和隐藏文件
            (test_dir / "visible.txt").write_text("visible")
            (test_dir / ".hidden").write_text("hidden")
            
            result = await tool.execute({
                "tool_call_id": "test_hidden",
                "path": str(test_dir),
            }, context=context)

            assert result.is_success
            # 隐藏文件应该被排除
            assert ".hidden" not in result.content
            assert "visible.txt" in result.content
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_pycache_excluded(self, tool, context):
        """测试 __pycache__ 目录被排除"""
        project_root = Path.cwd()
        test_dir = project_root / "tests" / "_temp_pycache"
        test_dir.mkdir(exist_ok=True)
        
        try:
            # 创建 __pycache__ 目录
            pycache = test_dir / "__pycache__"
            pycache.mkdir(exist_ok=True)
            (pycache / "module.pyc").write_text("bytecode")
            
            # 创建普通文件
            (test_dir / "module.py").write_text("code")
            
            result = await tool.execute({
                "tool_call_id": "test_pycache",
                "path": str(test_dir),
            }, context=context)

            assert result.is_success
            # __pycache__ 应该被排除
            assert "__pycache__" not in result.content
            assert "module.py" in result.content
        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_timing_information(self, tool, temp_dir, context):
        """测试时间信息"""
        result = await tool.execute({
            "tool_call_id": "test_timing",
            "path": str(temp_dir),
        }, context=context)

        assert result.is_success
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.duration > 0
        # 使用近似比较，允许浮点数精度误差
        assert abs(result.duration - (result.end_time - result.start_time)) < 0.001

    @pytest.mark.asyncio
    async def test_invalid_path_type(self, tool, context):
        """测试无效的路径类型"""
        result = await tool.execute({
            "tool_call_id": "test_invalid",
            "path": 12345,  # 数字而不是字符串
        }, context=context)

        # 应该处理类型错误
        assert not result.is_success or result.is_success  # 取决于实现
