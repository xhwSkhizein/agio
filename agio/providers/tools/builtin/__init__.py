"""Builtin tools for agio agents."""

from agio.providers.tools.builtin.bash_tool import BashTool
from agio.providers.tools.builtin.file_edit_tool import FileEditTool
from agio.providers.tools.builtin.get_tool_result_tool import GetToolResultTool
from agio.providers.tools.builtin.file_read_tool import FileReadTool
from agio.providers.tools.builtin.file_write_tool import FileWriteTool
from agio.providers.tools.builtin.glob_tool import GlobTool
from agio.providers.tools.builtin.grep_tool import GrepTool
from agio.providers.tools.builtin.ls_tool import LSTool
from agio.providers.tools.builtin.web_fetch_tool import WebFetchTool
from agio.providers.tools.builtin.web_search_tool import WebSearchTool

# All available builtin tool classes
ALL_BUILTIN_TOOL_CLASSES = [
    FileReadTool,
    FileEditTool,
    FileWriteTool,
    GrepTool,
    GlobTool,
    LSTool,
    BashTool,
    WebSearchTool,
    WebFetchTool,
    GetToolResultTool,
]


def create_all_tools(*, settings=None, **kwargs):
    """
    Create instances of all builtin tools.
    
    Args:
        settings: Optional AppSettings instance
        **kwargs: Additional arguments passed to tool constructors
        
    Returns:
        List of tool instances
    """
    tools = []
    for tool_class in ALL_BUILTIN_TOOL_CLASSES:
        try:
            if settings:
                tools.append(tool_class(settings=settings, **kwargs))
            else:
                tools.append(tool_class(**kwargs))
        except TypeError:
            # Some tools may not accept all kwargs
            tools.append(tool_class())
    return tools


def create_file_tools(*, settings=None):
    """Create file operation tools only."""
    return [
        FileReadTool(settings=settings) if settings else FileReadTool(),
        FileEditTool(settings=settings) if settings else FileEditTool(),
        FileWriteTool(settings=settings) if settings else FileWriteTool(),
        GrepTool(settings=settings) if settings else GrepTool(),
        GlobTool(settings=settings) if settings else GlobTool(),
        LSTool(settings=settings) if settings else LSTool(),
    ]


__all__ = [
    # Tool classes
    "BashTool",
    "FileEditTool",
    "GetToolResultTool",
    "FileReadTool",
    "FileWriteTool",
    "GlobTool",
    "GrepTool",
    "LSTool",
    "WebFetchTool",
    "WebSearchTool",
    # Collections
    "ALL_BUILTIN_TOOL_CLASSES",
    # Factory functions
    "create_all_tools",
    "create_file_tools",
]
