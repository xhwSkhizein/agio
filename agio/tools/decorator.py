"""
Tool decorator
"""

from typing import Callable
from .local import FunctionTool


def tool(func: Callable) -> FunctionTool:
    """
    Decorator to convert a function into a FunctionTool.
    
    Args:
        func: The function to decorate
        
    Returns:
        FunctionTool instance
    """
    return FunctionTool(func)
