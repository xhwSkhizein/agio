"""
Runtime module - Common runtime infrastructure.

This module contains:
- RunnableExecutor: Unified Run lifecycle management for all Runnable types
- ResumeExecutor: Unified Session Resume mechanism for Agent
- Wire: Event streaming channel
- EventFactory: Context-bound event factory
"""

from agio.runtime.control import AbortSignal, fork_session
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext, Runnable, RunnableType, RunOutput
from agio.runtime.runnable_executor import RunnableExecutor
from agio.runtime.runnable_tool import (
    CircularReferenceError,
    MaxDepthExceededError,
    RunnableTool,
    as_tool,
)
from agio.runtime.wire import Wire

__all__ = [
    "Runnable",
    "RunnableType",
    "RunOutput",
    "ExecutionContext",
    "RunnableExecutor",
    "Wire",
    "RunnableTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "AbortSignal",
    "fork_session",
]
