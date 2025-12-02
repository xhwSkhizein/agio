"""
Tool Registry - Unified tool management system.

Provides:
- Built-in tool registration and discovery
- Custom tool registration
- Tool instantiation with configuration parameters
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agio.components.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for all available tools.
    
    Supports:
    - Registering built-in tools by name
    - Registering custom tools dynamically
    - Creating tool instances with custom parameters
    """
    
    # Built-in tool mappings: name -> (module_path, class_name)
    BUILTIN_TOOLS: dict[str, tuple[str, str]] = {
        # File operations
        "file_read": (
            "agio.components.tools.builtin_tools.file_read_tool",
            "FileReadTool",
        ),
        "file_edit": (
            "agio.components.tools.builtin_tools.file_edit_tool",
            "FileEditTool",
        ),
        "file_write": (
            "agio.components.tools.builtin_tools.file_write_tool",
            "FileWriteTool",
        ),
        # Search tools
        "grep": (
            "agio.components.tools.builtin_tools.grep_tool",
            "GrepTool",
        ),
        "glob": (
            "agio.components.tools.builtin_tools.glob_tool",
            "GlobTool",
        ),
        "ls": (
            "agio.components.tools.builtin_tools.ls_tool",
            "LSTool",
        ),
        # System tools
        "bash": (
            "agio.components.tools.builtin_tools.bash_tool",
            "BashTool",
        ),
        # Web tools
        "web_search": (
            "agio.components.tools.builtin_tools.web_search_tool",
            "WebSearchTool",
        ),
        "web_fetch": (
            "agio.components.tools.builtin_tools.web_fetch_tool",
            "WebFetchTool",
        ),
    }
    
    def __init__(self) -> None:
        # Custom tool registrations: name -> (module_path, class_name)
        self._custom_tools: dict[str, tuple[str, str]] = {}
        # Cached tool classes
        self._class_cache: dict[str, type] = {}
    
    def register(
        self,
        name: str,
        module_path: str,
        class_name: str,
    ) -> None:
        """
        Register a custom tool.
        
        Args:
            name: Tool name (used in configs)
            module_path: Full module path (e.g., "myapp.tools.custom")
            class_name: Class name in the module
        """
        if name in self.BUILTIN_TOOLS:
            logger.warning(f"Overriding built-in tool: {name}")
        self._custom_tools[name] = (module_path, class_name)
        # Clear cache for this tool
        self._class_cache.pop(name, None)
        logger.info(f"Registered custom tool: {name} -> {module_path}.{class_name}")
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a custom tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._custom_tools:
            del self._custom_tools[name]
            self._class_cache.pop(name, None)
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get_tool_class(self, name: str) -> type:
        """
        Get tool class by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool class
            
        Raises:
            KeyError: Tool not found
            ImportError: Failed to import tool module
        """
        # Check cache first
        if name in self._class_cache:
            return self._class_cache[name]
        
        # Look up tool location
        if name in self._custom_tools:
            module_path, class_name = self._custom_tools[name]
        elif name in self.BUILTIN_TOOLS:
            module_path, class_name = self.BUILTIN_TOOLS[name]
        else:
            raise KeyError(f"Tool not found: {name}. Available: {self.list_available()}")
        
        # Import and cache
        import importlib
        module = importlib.import_module(module_path)
        tool_class = getattr(module, class_name)
        self._class_cache[name] = tool_class
        return tool_class
    
    def create(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "BaseTool":
        """
        Create a tool instance.
        
        Args:
            name: Tool name
            params: Configuration parameters for the tool
            **kwargs: Additional keyword arguments
            
        Returns:
            Tool instance
        """
        tool_class = self.get_tool_class(name)
        merged_params = {**(params or {}), **kwargs}
        
        # Filter out params that the tool doesn't accept
        import inspect
        sig = inspect.signature(tool_class.__init__)
        valid_params = {}
        for key, value in merged_params.items():
            if key in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD 
                for p in sig.parameters.values()
            ):
                valid_params[key] = value
        
        return tool_class(**valid_params)
    
    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._custom_tools or name in self.BUILTIN_TOOLS
    
    def is_builtin(self, name: str) -> bool:
        """Check if a tool is a built-in tool."""
        return name in self.BUILTIN_TOOLS
    
    def list_available(self) -> list[str]:
        """List all available tool names."""
        return list(set(self.BUILTIN_TOOLS.keys()) | set(self._custom_tools.keys()))
    
    def list_builtin(self) -> list[str]:
        """List built-in tool names."""
        return list(self.BUILTIN_TOOLS.keys())
    
    def list_custom(self) -> list[str]:
        """List custom tool names."""
        return list(self._custom_tools.keys())
    
    def get_tool_info(self, name: str) -> dict[str, Any]:
        """
        Get tool information.
        
        Args:
            name: Tool name
            
        Returns:
            Tool info dict with module_path, class_name, is_builtin
        """
        if name in self._custom_tools:
            module_path, class_name = self._custom_tools[name]
            is_builtin = False
        elif name in self.BUILTIN_TOOLS:
            module_path, class_name = self.BUILTIN_TOOLS[name]
            is_builtin = True
        else:
            raise KeyError(f"Tool not found: {name}")
        
        return {
            "name": name,
            "module_path": module_path,
            "class_name": class_name,
            "is_builtin": is_builtin,
        }


# Global singleton instance
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(name: str, module_path: str, class_name: str) -> None:
    """Register a custom tool (convenience function)."""
    get_tool_registry().register(name, module_path, class_name)


def create_tool(name: str, params: dict[str, Any] | None = None, **kwargs: Any) -> "BaseTool":
    """Create a tool instance (convenience function)."""
    return get_tool_registry().create(name, params, **kwargs)


def list_tools() -> list[str]:
    """List all available tools (convenience function)."""
    return get_tool_registry().list_available()
