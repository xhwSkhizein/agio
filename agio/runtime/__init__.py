"""
Runtime module - Common runtime infrastructure.

This module contains:
- ExecutionContext: Immutable execution context
- AgentTool: Adapter to convert Agent into Tool
- Wire: Event streaming channel
- EventFactory: Context-bound event factory
"""

from agio.runtime.agent_tool import (
    AgentTool,
    CircularReferenceError,
    MaxDepthExceededError,
    as_tool,
)
from agio.runtime.context import ExecutionContext, RunnableType
from agio.runtime.control import AbortSignal, fork_session
from agio.runtime.event_factory import EventFactory
from agio.runtime.wire import Wire

__all__ = [
    "RunnableType",
    "ExecutionContext",
    "Wire",
    "EventFactory",
    "AgentTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "AbortSignal",
    "fork_session",
]
