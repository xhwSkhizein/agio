# Old event system (DEPRECATED)
from agio.protocol.events import AgentEvent, EventType

# New Step-based event system (RECOMMENDED)
from agio.protocol.step_events import (
    StepEvent,
    StepEventType,
    StepDelta,
    create_run_started_event,
    create_run_completed_event,
    create_run_failed_event,
    create_step_delta_event,
    create_step_completed_event,
    create_error_event,
)

__all__ = [
    # Old (deprecated)
    "AgentEvent",
    "EventType",
    # New (recommended)
    "StepEvent",
    "StepEventType",
    "StepDelta",
    "create_run_started_event",
    "create_run_completed_event",
    "create_run_failed_event",
    "create_step_delta_event",
    "create_step_completed_event",
    "create_error_event",
]
