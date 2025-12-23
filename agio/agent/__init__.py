"""
Agent module - Agent execution engine.

This module contains:
- Agent: Agent configuration and execution entry point
- AgentRunner: Step lifecycle management
- AgentExecutor: LLM call loop
- Context building, summarization, and control flow utilities
"""

from .agent import Agent
from .runner import AgentRunner, TerminationSummaryResult
from .executor import AgentExecutor, ToolCallAccumulator
from .context import build_context_from_steps, build_context_from_sequence_range, validate_context
from .summarizer import (
    build_termination_messages,
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)
from .control import AbortSignal, fork_session

__all__ = [
    "Agent",
    "AgentRunner",
    "TerminationSummaryResult",
    "AgentExecutor",
    "ToolCallAccumulator",
    "build_context_from_steps",
    "build_context_from_sequence_range",
    "validate_context",
    "build_termination_messages",
    "DEFAULT_TERMINATION_USER_PROMPT",
    "_format_termination_reason",
    "AbortSignal",
    "fork_session",
]

