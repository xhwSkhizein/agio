"""测试工具配置对象和工具构造"""

from pathlib import Path

from agio.tools.builtin.config import (
    FileReadConfig,
    GrepConfig,
    BashConfig,
    WebFetchConfig,
)
from agio.tools.builtin.file_read_tool import FileReadTool
from agio.tools.builtin.file_write_tool import FileWriteTool
from agio.tools.builtin.file_edit_tool import FileEditTool
from agio.tools.builtin.grep_tool import GrepTool
from agio.tools.builtin.glob_tool import GlobTool
from agio.tools.builtin.ls_tool import LSTool
from agio.tools.builtin.bash_tool import BashTool
from agio.tools.builtin.web_search_tool import WebSearchTool
from agio.tools.builtin.web_fetch_tool import WebFetchTool


class TestToolConfigs:
    """测试配置对象"""

    def test_file_read_config_defaults(self):
        """测试 FileReadConfig 默认值"""
        config = FileReadConfig()
        assert config.max_output_size_mb == 10.0
        assert config.max_image_size_mb == 5.0
        assert config.max_image_width == 1920
        assert config.max_image_height == 1080
        assert config.timeout_seconds == 30

    def test_file_read_config_custom(self):
        """测试 FileReadConfig 自定义值"""
        config = FileReadConfig(max_output_size_mb=5.0, timeout_seconds=60)
        assert config.max_output_size_mb == 5.0
        assert config.timeout_seconds == 60
        assert config.max_image_size_mb == 5.0  # 默认值

    def test_web_fetch_config_defaults(self):
        """测试 WebFetchConfig 默认值"""
        config = WebFetchConfig()
        assert config.timeout_seconds == 30
        assert config.max_content_length == 4096
        assert config.max_retries == 1
        assert config.wait_strategy == "domcontentloaded"
        assert config.headless is True
        assert config.save_login_state is False

    def test_web_fetch_config_custom(self):
        """测试 WebFetchConfig 自定义值"""
        config = WebFetchConfig(headless=False, timeout_seconds=60, max_retries=3)
        assert config.headless is False
        assert config.timeout_seconds == 60
        assert config.max_retries == 3

    def test_grep_config_defaults(self):
        """测试 GrepConfig 默认值"""
        config = GrepConfig()
        assert config.timeout_seconds == 30
        assert config.max_results == 1000

    def test_bash_config_defaults(self):
        """测试 BashConfig 默认值"""
        config = BashConfig()
        assert config.timeout_seconds == 300
        assert config.max_output_size_kb == 1024
        assert config.max_output_length == 30000


class TestToolConstruction:
    """测试工具构造"""

    def test_file_read_tool_default(self):
        """测试 FileReadTool 默认构造"""
        tool = FileReadTool()
        assert tool.timeout_seconds == 30
        assert tool._config.max_output_size_mb == 10.0

    def test_file_read_tool_with_config(self):
        """测试 FileReadTool 使用配置对象"""
        config = FileReadConfig(max_output_size_mb=5.0, timeout_seconds=60)
        tool = FileReadTool(config=config)
        assert tool.timeout_seconds == 60
        assert tool._config.max_output_size_mb == 5.0

    def test_file_read_tool_with_kwargs(self):
        """测试 FileReadTool 使用 kwargs"""
        tool = FileReadTool(max_output_size_mb=15.0, timeout_seconds=45)
        assert tool.timeout_seconds == 45
        assert tool._config.max_output_size_mb == 15.0

    def test_file_read_tool_config_override(self):
        """测试 FileReadTool kwargs 覆盖 config"""
        config = FileReadConfig(max_output_size_mb=5.0)
        tool = FileReadTool(config=config, max_output_size_mb=20.0)
        assert tool._config.max_output_size_mb == 20.0  # kwargs 覆盖 config

    def test_web_fetch_tool_default(self):
        """测试 WebFetchTool 默认构造"""
        tool = WebFetchTool()
        assert tool.timeout_seconds == 30
        assert tool._config.headless is True

    def test_web_fetch_tool_with_config(self):
        """测试 WebFetchTool 使用配置对象"""
        config = WebFetchConfig(headless=False, timeout_seconds=60)
        tool = WebFetchTool(config=config)
        assert tool.timeout_seconds == 60
        assert tool._config.headless is False

    def test_grep_tool_with_project_root(self):
        """测试 GrepTool 使用 project_root"""
        project_root = Path("/tmp/test")
        tool = GrepTool(project_root=project_root)
        assert tool._project_root == project_root.resolve()

    def test_all_tools_constructible(self):
        """测试所有工具都能正常构造"""
        tools = [
            FileReadTool(),
            FileWriteTool(),
            FileEditTool(),
            GrepTool(),
            GlobTool(),
            LSTool(),
            BashTool(),
            WebSearchTool(),
            WebFetchTool(),
        ]
        assert len(tools) == 9
        for tool in tools:
            assert tool is not None
            assert hasattr(tool, "timeout_seconds") or hasattr(tool, "_config")


class TestToolConfigEnvironmentVariables:
    """测试环境变量配置"""

    def test_file_read_config_env_var(self, monkeypatch):
        """测试 FileReadConfig 环境变量"""
        monkeypatch.setenv("AGIO_FILE_READ_MAX_SIZE_MB", "15.0")
        monkeypatch.setenv("AGIO_FILE_READ_TIMEOUT", "45")

        config = FileReadConfig()
        assert config.max_output_size_mb == 15.0
        assert config.timeout_seconds == 45

    def test_web_fetch_config_env_var(self, monkeypatch):
        """测试 WebFetchConfig 环境变量"""
        monkeypatch.setenv("AGIO_WEB_FETCH_HEADLESS", "false")
        monkeypatch.setenv("AGIO_WEB_FETCH_TIMEOUT", "60")

        config = WebFetchConfig()
        assert config.headless is False
        assert config.timeout_seconds == 60

    def test_env_var_override_by_kwargs(self, monkeypatch):
        """测试 kwargs 覆盖环境变量"""
        monkeypatch.setenv("AGIO_FILE_READ_MAX_SIZE_MB", "15.0")

        tool = FileReadTool(max_output_size_mb=20.0)
        assert tool._config.max_output_size_mb == 20.0  # kwargs 优先级最高
