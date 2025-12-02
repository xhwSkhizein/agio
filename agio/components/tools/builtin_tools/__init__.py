"""Builtin tools for agio agents."""

from agio.components.tools.builtin_tools.bash_tool import BashTool
from agio.components.tools.builtin_tools.file_edit_tool import FileEditTool
from agio.components.tools.builtin_tools.file_read_tool import FileReadTool
from agio.components.tools.builtin_tools.file_write_tool import FileWriteTool
from agio.components.tools.builtin_tools.glob_tool import GlobTool
from agio.components.tools.builtin_tools.grep_tool import GrepTool
from agio.components.tools.builtin_tools.ls_tool import LSTool
from agio.components.tools.builtin_tools.web_fetch_tool import WebFetchTool
from agio.components.tools.builtin_tools.web_search_tool import WebSearchTool

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
