# ============================================================================
# DEPRECATION NOTICE
# ============================================================================
#
# This file is DEPRECATED and will be removed in a future version.
#
# Replacement:
#   - Old: agio/protocol/events.py (AgentEvent system)
#   - New: agio/protocol/step_events.py (StepEvent system)
#
# Migration Guide:
#   See docs/STEP_INTEGRATION_GUIDE.md for migration instructions.
#
# Why Deprecated?
#   The old event system required complex conversion logic to transform
#   events into LLM messages. The new Step-based system stores data in
#   native LLM message format, eliminating conversion overhead.
#
# Timeline:
#   - Deprecated: 2025-11-22
#   - Removal: TBD (after full migration)
#
# ============================================================================


"""
Agent Event Protocol - DEPRECATED

Use agio.protocol.step_events instead.
"""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class EventType(str, Enum):
    """Event types - DEPRECATED"""

    # Run lifecycle
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"

    # Step lifecycle
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"

    # Streaming
    TEXT_DELTA = "text_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"

    # Errors
    ERROR = "error"


class AgentEvent(BaseModel):
    """
    Agent Event - DEPRECATED

    Use StepEvent instead for new code.
    """

    type: EventType
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    step: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format"""
        import json

        return f"data: {json.dumps(self.model_dump(mode='json'))}\n\n"


# Event creation helpers - DEPRECATED


def run_started(run_id: str, query: str) -> AgentEvent:
    """DEPRECATED: Use create_run_started_event from step_events"""
    return AgentEvent(type=EventType.RUN_STARTED, run_id=run_id, data={"query": query})


def run_completed(
    run_id: str, response: str, metrics: dict | None = None
) -> AgentEvent:
    """DEPRECATED: Use create_run_completed_event from step_events"""
    return AgentEvent(
        type=EventType.RUN_COMPLETED,
        run_id=run_id,
        data={"response": response, "metrics": metrics or {}},
    )


def run_failed(run_id: str, error: str) -> AgentEvent:
    """DEPRECATED: Use create_run_failed_event from step_events"""
    return AgentEvent(type=EventType.RUN_FAILED, run_id=run_id, data={"error": error})


def step_started(run_id: str, step: int) -> AgentEvent:
    """DEPRECATED: Steps are now created directly"""
    return AgentEvent(type=EventType.STEP_STARTED, run_id=run_id, step=step)


def step_completed(run_id: str, step: int) -> AgentEvent:
    """DEPRECATED: Use create_step_completed_event from step_events"""
    return AgentEvent(type=EventType.STEP_COMPLETED, run_id=run_id, step=step)


def text_delta(run_id: str, content: str, step: int) -> AgentEvent:
    """DEPRECATED: Use create_step_delta_event from step_events"""
    return AgentEvent(
        type=EventType.TEXT_DELTA, run_id=run_id, step=step, data={"content": content}
    )


def tool_call_started(run_id: str, tool_name: str, step: int) -> AgentEvent:
    """DEPRECATED: Tool calls are now part of Step"""
    return AgentEvent(
        type=EventType.TOOL_CALL_STARTED,
        run_id=run_id,
        step=step,
        data={"tool_name": tool_name},
    )


def tool_call_delta(run_id: str, delta: dict, step: int) -> AgentEvent:
    """DEPRECATED: Use create_step_delta_event from step_events"""
    return AgentEvent(
        type=EventType.TOOL_CALL_DELTA, run_id=run_id, step=step, data=delta
    )


def tool_call_completed(run_id: str, tool_call: dict, step: int) -> AgentEvent:
    """DEPRECATED: Tool calls are now part of Step"""
    return AgentEvent(
        type=EventType.TOOL_CALL_COMPLETED,
        run_id=run_id,
        step=step,
        data={"tool_call": tool_call},
    )


def tool_execution_started(run_id: str, tool_name: str, step: int) -> AgentEvent:
    """DEPRECATED: Tool execution creates Tool Steps"""
    return AgentEvent(
        type=EventType.TOOL_EXECUTION_STARTED,
        run_id=run_id,
        step=step,
        data={"tool_name": tool_name},
    )


def tool_execution_completed(
    run_id: str, tool_name: str, result: str, step: int
) -> AgentEvent:
    """DEPRECATED: Tool execution creates Tool Steps"""
    return AgentEvent(
        type=EventType.TOOL_EXECUTION_COMPLETED,
        run_id=run_id,
        step=step,
        data={"tool_name": tool_name, "result": result},
    )


def error_event(run_id: str, error: str, step: int | None = None) -> AgentEvent:
    """DEPRECATED: Use create_run_failed_event from step_events"""
    return AgentEvent(
        type=EventType.ERROR, run_id=run_id, step=step, data={"error": error}
    )


# Aliases for backward compatibility
create_run_started_event = run_started
create_run_completed_event = run_completed
create_run_failed_event = run_failed
