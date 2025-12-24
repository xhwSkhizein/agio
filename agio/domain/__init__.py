"""
Domain module - Pure domain models with no external dependencies.

This module contains all core data models, events, and adapters.
"""

# Models
from .models import (
    AgentMemoriedContent,
    AgentRunSummary,
    AgentSession,
    GenerationReference,
    MemoryCategory,
    MessageRole,
    Run,
    RunMetrics,
    RunStatus,
    Step,
    StepMetrics,
    normalize_usage_metrics,
)

# Events
from .events import (
    StepDelta,
    StepEvent,
    StepEventType,
    ToolResult,
    create_error_event,
    create_run_completed_event,
    create_run_failed_event,
    create_run_started_event,
    create_step_completed_event,
    create_step_delta_event,
)

# Adapters
from .adapters import StepAdapter

__all__ = [
    # Models
    "Step",
    "StepMetrics",
    "Run",
    "RunMetrics",
    "AgentRunSummary",
    "AgentSession",
    "GenerationReference",
    "MessageRole",
    "RunStatus",
    "MemoryCategory",
    "AgentMemoriedContent",
    "normalize_usage_metrics",
    # Events
    "StepEvent",
    "StepEventType",
    "StepDelta",
    "ToolResult",
    "create_run_started_event",
    "create_run_completed_event",
    "create_run_failed_event",
    "create_step_delta_event",
    "create_step_completed_event",
    "create_error_event",
    # Adapters
    "StepAdapter",
]
