"""
Execution package - Agent execution engine.

This package consolidates the execution logic from the old
runners/ and execution/ packages.
"""

from .context import (
    build_context_from_sequence_range,
    build_context_from_steps,
    get_context_summary,
    validate_context,
)
from .fork import fork_session
from .retry import retry_from_sequence
from .runner import StepRunner
from .step_executor import StepExecutor
from .tool_executor import ToolExecutor

__all__ = [
    # Executor
    "StepExecutor",
    "ToolExecutor",
    # Runner
    "StepRunner",
    # Context
    "build_context_from_steps",
    "build_context_from_sequence_range",
    "validate_context",
    "get_context_summary",
    # Operations
    "fork_session",
    "retry_from_sequence",
]
