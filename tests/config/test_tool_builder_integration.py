"""ToolBuilder 集成测试 - 验证通过 YAML 配置创建工具"""

import pytest

from agio.config.builders import ToolBuilder
from agio.config.schema import ToolConfig
from agio.tools.builtin.file_read_tool import FileReadTool
from agio.tools.builtin.web_fetch_tool import WebFetchTool
from agio.tools.builtin.grep_tool import GrepTool


class TestToolBuilderIntegration:
    """ToolBuilder 集成测试"""

    @pytest.fixture
    def builder(self):
        """创建 ToolBuilder 实例"""
        return ToolBuilder()

    @pytest.mark.asyncio
    async def test_build_file_read_tool_with_params(self, builder):
        """测试通过 params 构建 FileReadTool"""
        config = ToolConfig(
            type="tool",
            name="file_read",
            tool_name="file_read",
            params={
                "max_output_size_mb": 5.0,
                "timeout_seconds": 60,
            }
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, FileReadTool)
        assert tool._config.max_output_size_mb == 5.0
        assert tool.timeout_seconds == 60

    @pytest.mark.asyncio
    async def test_build_file_read_tool_default(self, builder):
        """测试使用默认配置构建 FileReadTool"""
        config = ToolConfig(
            type="tool",
            name="file_read",
            tool_name="file_read",
            params={}
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, FileReadTool)
        assert tool._config.max_output_size_mb == 10.0  # 默认值
        assert tool.timeout_seconds == 30  # 默认值

    @pytest.mark.asyncio
    async def test_build_web_fetch_tool_with_params(self, builder):
        """测试通过 params 构建 WebFetchTool"""
        config = ToolConfig(
            type="tool",
            name="web_fetch",
            tool_name="web_fetch",
            params={
                "headless": False,
                "timeout_seconds": 60,
                "max_retries": 3,
            }
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, WebFetchTool)
        assert tool._config.headless is False
        assert tool.timeout_seconds == 60
        assert tool._config.max_retries == 3

    @pytest.mark.asyncio
    async def test_build_grep_tool_with_project_root(self, builder):
        """测试构建 GrepTool 时自动设置 project_root"""
        config = ToolConfig(
            type="tool",
            name="grep",
            tool_name="grep",
            params={}
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, GrepTool)
        assert tool._project_root is not None
        assert tool._project_root.exists()

    @pytest.mark.asyncio
    async def test_build_tool_with_dependencies(self, builder):
        """测试构建带依赖的工具"""
        # 创建模拟的依赖
        mock_citation_store = object()
        mock_llm_model = object()
        
        config = ToolConfig(
            type="tool",
            name="web_fetch",
            tool_name="web_fetch",
            params={},
            dependencies={
                "citation_source_store": "citation_store",
                "llm_model": "llm_model",
            }
        )
        
        dependencies = {
            "citation_source_store": mock_citation_store,
            "llm_model": mock_llm_model,
        }
        
        tool = await builder.build(config, dependencies)
        
        assert isinstance(tool, WebFetchTool)
        assert tool._citation_source_store == mock_citation_store
        assert tool._llm_model == mock_llm_model  # 直接使用 Model 实例

    @pytest.mark.asyncio
    async def test_build_tool_partial_params(self, builder):
        """测试部分参数配置"""
        config = ToolConfig(
            type="tool",
            name="file_read",
            tool_name="file_read",
            params={
                "max_output_size_mb": 15.0,
                # timeout_seconds 使用默认值
            }
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, FileReadTool)
        assert tool._config.max_output_size_mb == 15.0
        assert tool.timeout_seconds == 30  # 默认值

    @pytest.mark.asyncio
    async def test_build_tool_config_object_created(self, builder):
        """测试配置对象被正确创建"""
        config = ToolConfig(
            type="tool",
            name="file_read",
            tool_name="file_read",
            params={
                "max_output_size_mb": 5.0,
                "max_image_size_mb": 3.0,
            }
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, FileReadTool)
        assert hasattr(tool, '_config')
        assert tool._config.max_output_size_mb == 5.0
        assert tool._config.max_image_size_mb == 3.0
        # 其他字段应该使用默认值
        assert tool._config.max_image_width == 1920

    @pytest.mark.asyncio
    async def test_build_tool_params_filtered(self, builder):
        """测试无效参数被过滤"""
        config = ToolConfig(
            type="tool",
            name="file_read",
            tool_name="file_read",
            params={
                "max_output_size_mb": 5.0,
                "invalid_param": "should_be_filtered",  # 无效参数
            }
        )
        
        tool = await builder.build(config, {})
        
        assert isinstance(tool, FileReadTool)
        assert tool._config.max_output_size_mb == 5.0
        # 无效参数不应该影响工具创建

