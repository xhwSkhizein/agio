"""
Adapter module to bridge kumr tool implementations to agio.

This module provides compatibility shims for kumr tools to work in agio.
"""

# Re-export base tool classes
from agio.providers.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
    ToolDefinition,
)
from agio.domain import ToolResult

# Provide stubs for kumr-specific imports that we don't need


class AbortController:
    """Stub for AbortController - not used in agio."""

    def is_aborted(self) -> bool:
        return False


class AppSettings:
    """Stub settings class."""

    class ToolSettings:
        # File read settings
        file_read_max_output_size_mb: float = 10.0
        file_read_max_image_size_mb: float = 5.0
        file_read_max_image_width: int = 1920
        file_read_max_image_height: int = 1080
        file_read_tool_timeout_seconds: int = 30

        # Grep settings
        grep_tool_timeout_seconds: int = 30
        grep_tool_max_results: int = 1000

        # LS settings
        ls_tool_timeout_seconds: int = 30
        ls_tool_max_files: int = 1000
        ls_tool_max_lines: int = 100

        # File write settings
        file_write_tool_timeout_seconds: int = 30
        file_write_max_file_size_mb: float = 10.0

        # File edit settings
        file_edit_tool_timeout_seconds: int = 60

        # Glob settings
        glob_tool_timeout_seconds: int = 30
        glob_tool_max_results: int = 1000
        glob_tool_max_search_depth: int = 10
        glob_tool_max_path_length: int = 500
        glob_tool_max_pattern_length: int = 200

        # Bash settings
        bash_tool_timeout_seconds: int = 300
        bash_tool_max_output_size_kb: int = 1024
        bash_tool_max_output_length: int = 30000  # characters

        # Web settings
        web_search_max_results: int = 10
        web_search_tool_timeout_seconds: int = 30
        web_fetch_tool_timeout_seconds: int = 30
        web_fetch_max_content_length: int = 4096
        web_fetch_max_retries: int = 1
        web_fetch_wait_strategy: str = "domcontentloaded"
        web_fetch_tool_max_size_mb: float = 10.0
        web_fetch_headless: bool = False

    def __init__(self):
        import os
        from pathlib import Path

        self.tool = self.ToolSettings()
        # Set project root to current working directory or a sensible default
        self.project_root = Path(os.getcwd())


class SettingsRegistry:
    """Stub settings registry."""

    _settings = AppSettings()

    @classmethod
    def get(cls) -> AppSettings:
        return cls._settings

    @classmethod
    def set_project_root(cls, root):
        """Set the project root directory."""
        from pathlib import Path

        cls._settings.project_root = Path(root).resolve()


def get_logger(name: str):
    """Get logger stub."""
    from agio.utils.logging import get_logger as agio_get_logger

    return agio_get_logger(name)


__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolCategory",
    "ToolDefinition",
    "ToolResult",
    "AbortController",
    "AppSettings",
    "SettingsRegistry",
    "get_logger",
]
