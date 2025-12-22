"""
Event protocol for streaming Step-based execution.

This module defines the event types used for real-time streaming
of agent execution to clients via SSE.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .models import Step


class StepEventType(str, Enum):
    """Event types for Step-based streaming"""

    # Step-level events
    STEP_DELTA = "step_delta"  # Incremental update to a step
    STEP_COMPLETED = "step_completed"  # Step is complete (final snapshot)

    # Run-level events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"

    # Workflow events
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_SKIPPED = "node_skipped"  # Condition not met
    ITERATION_STARTED = "iteration_started"  # Loop only
    BRANCH_STARTED = "branch_started"  # Parallel only
    BRANCH_COMPLETED = "branch_completed"  # Parallel only

    # Error events
    ERROR = "error"


class StepDelta(BaseModel):
    """
    Incremental update to a Step.

    Used for streaming text content and tool calls as they arrive.
    """

    content: str | None = None  # Text to append
    reasoning_content: str | None = (
        None  # Reasoning content to append (e.g., DeepSeek thinking mode)
    )
    tool_calls: list[dict] | None = None  # Tool calls to append/update


class StepEvent(BaseModel):
    """
    Unified event for Step-based streaming.

    Frontend receives these events via SSE and uses them to:
    1. Build up Steps incrementally (via delta)
    2. Finalize Steps (via snapshot)
    3. Track run status
    4. Build hierarchical workflow display
    """

    type: StepEventType
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)

    # For STEP_DELTA and STEP_COMPLETED
    step_id: str | None = None

    # For STEP_DELTA - incremental updates
    delta: StepDelta | None = None

    # For STEP_COMPLETED - final state
    snapshot: Step | None = None

    # For RUN_* and ERROR events
    data: dict | None = None

    # Workflow context - for hierarchical display
    node_id: str | None = None  # Node ID
    branch_id: str | None = None
    iteration: int | None = None

    # Workflow hierarchy info (for frontend to build tree structure)
    workflow_type: str | None = None  # "pipeline" | "parallel" | "loop"
    workflow_id: str | None = None    # ID of the workflow
    parent_run_id: str | None = None  # Parent run ID for nesting
    node_name: str | None = None      # Human-readable node name
    node_index: int | None = None     # 0-based index in sequence
    total_nodes: int | None = None    # Total number of nodes

    # Observability reserved
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    depth: int = 0

    # Nested execution context
    nested_runnable_id: str | None = None  # ID of nested Agent/Workflow

    # Runnable identity (for unified display)
    runnable_type: str | None = None   # "agent" | "workflow"
    runnable_id: str | None = None     # Agent/Workflow config ID
    nesting_type: str | None = None    # "tool_call" | "workflow_node" | None

    def to_sse(self) -> str:
        """
        Convert to Server-Sent Events format.

        Returns:
            str: SSE-formatted string ready to send to client
        """
        import json

        data = self.model_dump(mode="json")
        return f"data: {json.dumps(data)}\n\n"


class ToolResult(BaseModel):
    """Result of a tool execution"""

    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    content: str  # Result for LLM
    output: Any  # Raw execution result
    error: str | None = None
    start_time: float
    end_time: float
    duration: float
    is_success: bool = True


# ============================================================================
# Event Factory Functions
# ============================================================================


def create_run_started_event(
    run_id: str, 
    query: str, 
    session_id: str,
    *,
    depth: int = 0,
    parent_run_id: str | None = None,
    nested_runnable_id: str | None = None,
    runnable_type: str | None = None,
    runnable_id: str | None = None,
    nesting_type: str | None = None,
) -> StepEvent:
    """Create a RUN_STARTED event with optional nested context"""
    return StepEvent(
        type=StepEventType.RUN_STARTED,
        run_id=run_id,
        data={"query": query, "session_id": session_id},
        depth=depth,
        parent_run_id=parent_run_id,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type,
        runnable_id=runnable_id,
        nesting_type=nesting_type,
    )


def create_run_completed_event(
    run_id: str, 
    response: str, 
    metrics: dict,
    termination_reason: str | None = None,
    max_steps: int | None = None,
    *,
    depth: int = 0,
    parent_run_id: str | None = None,
    nested_runnable_id: str | None = None,
    runnable_type: str | None = None,
    runnable_id: str | None = None,
    nesting_type: str | None = None,
) -> StepEvent:
    """Create a RUN_COMPLETED event with optional nested context"""
    data = {"response": response, "metrics": metrics}
    if termination_reason:
        data["termination_reason"] = termination_reason
    if max_steps:
        data["max_steps"] = max_steps
    return StepEvent(
        type=StepEventType.RUN_COMPLETED,
        run_id=run_id,
        data=data,
        depth=depth,
        parent_run_id=parent_run_id,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type,
        runnable_id=runnable_id,
        nesting_type=nesting_type,
    )


def create_run_failed_event(
    run_id: str, 
    error: str,
    *,
    depth: int = 0,
    parent_run_id: str | None = None,
    nested_runnable_id: str | None = None,
    runnable_type: str | None = None,
    runnable_id: str | None = None,
    nesting_type: str | None = None,
) -> StepEvent:
    """Create a RUN_FAILED event with optional nested context"""
    return StepEvent(
        type=StepEventType.RUN_FAILED, 
        run_id=run_id, 
        data={"error": error},
        depth=depth,
        parent_run_id=parent_run_id,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type,
        runnable_id=runnable_id,
        nesting_type=nesting_type,
    )


def create_step_delta_event(
    step_id: str, 
    run_id: str, 
    delta: StepDelta,
    *,
    depth: int = 0,
    parent_run_id: str | None = None,
    nested_runnable_id: str | None = None,
    runnable_type: str | None = None,
    runnable_id: str | None = None,
    nesting_type: str | None = None,
) -> StepEvent:
    """Create a STEP_DELTA event with optional nested context"""
    return StepEvent(
        type=StepEventType.STEP_DELTA, 
        step_id=step_id, 
        run_id=run_id, 
        delta=delta,
        depth=depth,
        parent_run_id=parent_run_id,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type,
        runnable_id=runnable_id,
        nesting_type=nesting_type,
    )


def create_step_completed_event(
    step_id: str, 
    run_id: str, 
    snapshot: Step,
    *,
    depth: int = 0,
    parent_run_id: str | None = None,
    nested_runnable_id: str | None = None,
    runnable_type: str | None = None,
    runnable_id: str | None = None,
    nesting_type: str | None = None,
) -> StepEvent:
    """Create a STEP_COMPLETED event with optional nested context"""
    return StepEvent(
        type=StepEventType.STEP_COMPLETED, 
        step_id=step_id, 
        run_id=run_id, 
        snapshot=snapshot,
        depth=depth,
        parent_run_id=parent_run_id,
        nested_runnable_id=nested_runnable_id,
        runnable_type=runnable_type,
        runnable_id=runnable_id,
        nesting_type=nesting_type,
    )


def create_error_event(run_id: str, error: str, error_type: str = "unknown") -> StepEvent:
    """Create an ERROR event"""
    return StepEvent(
        type=StepEventType.ERROR, run_id=run_id, data={"error": error, "error_type": error_type}
    )
