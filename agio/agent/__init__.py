"""
Agent module - Agent execution engine.

This module contains:
- Agent: Agent configuration and execution entry point
- AgentExecutor: LLM call loop
- Context building, summarization, and control flow utilities
"""

from agio.runtime.context import ExecutionContext, RunnableType

from .agent import Agent
from .helper import build_context_from_steps
from .executor import AgentExecutor, MetricsTracker, ToolCallAccumulator
from .summarizer import (
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
    build_termination_messages,
)

__all__ = [
    "Agent",
    "ExecutionContext",
    "RunnableType",
    "AgentExecutor",
    "ToolCallAccumulator",
    "MetricsTracker",
    "build_context_from_steps",
    "build_termination_messages",
    "DEFAULT_TERMINATION_USER_PROMPT",
    "_format_termination_reason",
]
