"""
Agent module - Agent execution engine.

This module contains:
- Agent: Agent configuration and execution entry point
- AgentExecutor: LLM call loop
- Context building, summarization, and control flow utilities
"""

from .agent import Agent
from .context import (
    build_context_from_sequence_range,
    build_context_from_steps,
    validate_context,
)
from .executor import AgentExecutor, MetricsTracker, ToolCallAccumulator
from .summarizer import (
    DEFAULT_TERMINATION_USER_PROMPT,
    _format_termination_reason,
    build_termination_messages,
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
