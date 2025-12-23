"""
Runtime module - Agent execution engine.

This module contains the core execution logic:
- StepRunner: Main agent loop with lifecycle management
- StepExecutor: LLM call loop
- RunnableExecutor: Unified Run lifecycle management
- ToolExecutor: Tool execution
- Wire: Event streaming channel
- ExecutionContext: Re-exported from agio.domain
- EventFactory: Context-bound event factory
- Context building and control flow

Note: WorkflowState and ContextResolver are in agio.workflow module.
"""

from .runner import StepRunner
from .executor import StepExecutor
from .runnable_executor import RunnableExecutor
from .resume_executor import ResumeExecutor
from .tool_executor import ToolExecutor
from .tool_cache import ToolResultCache, get_tool_cache
from .wire import Wire
from agio.domain import ExecutionContext
from .event_factory import EventFactory
from .context import build_context_from_steps
from .control import AbortSignal, fork_session
from .summarizer import (
    build_termination_messages,
    DEFAULT_TERMINATION_USER_PROMPT,
)

__all__ = [
    "StepRunner",
    "StepExecutor",
    "RunnableExecutor",
    "ResumeExecutor",
    "ToolExecutor",
    "ToolResultCache",
    "get_tool_cache",
    "Wire",
    "ExecutionContext",
    "EventFactory",
    "build_context_from_steps",
    "AbortSignal",
    "fork_session",
    "build_termination_messages",
    "DEFAULT_TERMINATION_USER_PROMPT",
]
