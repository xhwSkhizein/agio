"""
Agent module - Agent execution engine.

This module contains:
- Agent: Agent configuration and execution entry point
- AgentExecutor: LLM call loop
- Context building, summarization, and control flow utilities
"""

from .agent import Agent
from .executor import AgentExecutor, ToolCallAccumulator, MetricsTracker
from .context import (
    build_context_from_steps,
    build_context_from_sequence_range,
    validate_context,
)
from .summarizer import (
    build_termination_messages,
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
)

__all__ = [
    "Agent",
    "AgentExecutor",
    "ToolCallAccumulator",
    "MetricsTracker",
    "build_context_from_steps",
    "build_context_from_sequence_range",
    "validate_context",
    "build_termination_messages",
    "DEFAULT_TERMINATION_USER_PROMPT",
    "_format_termination_reason",
]
