"""
Core module - Unified exports for all core models, events, and configuration.

This module provides a single import point for all core Agio types.
"""

# Models
from .models import (
    AgentMemoriedContent,
    AgentRun,
    AgentRunMetrics,
    AgentRunSummary,
    AgentSession,
    GenerationReference,
    MemoryCategory,
    MessageRole,
    RunStatus,
    Step,
    StepMetrics,
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

# Configuration
from .config import (
    AgioSettings,
    ComponentConfig,
    ExecutionConfig,
    KnowledgeConfig,
    MemoryConfig,
    ModelConfig,
    ToolConfig,
    settings,
)

__all__ = [
    # Models
    "Step",
    "StepMetrics",
    "AgentRun",
    "AgentRunMetrics",
    "AgentRunSummary",
    "AgentSession",
    "GenerationReference",
    "MessageRole",
    "RunStatus",
    "MemoryCategory",
    "AgentMemoriedContent",
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
    # Configuration
    "settings",
    "AgioSettings",
    "ExecutionConfig",
    "ComponentConfig",
    "ModelConfig",
    "ToolConfig",
    "MemoryConfig",
    "KnowledgeConfig",
]
