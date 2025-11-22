"""
Step-based event protocol for streaming.

This replaces the old AgentEvent system with a simpler model where
events are just incremental updates (deltas) to Steps.
"""

from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from agio.domain.step import Step


class StepEventType(str, Enum):
    """Event types for Step-based streaming"""
    
    # Step-level events
    STEP_DELTA = "step_delta"  # Incremental update to a step
    STEP_COMPLETED = "step_completed"  # Step is complete (final snapshot)
    
    # Run-level events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    
    # Error events
    ERROR = "error"


class StepDelta(BaseModel):
    """
    Incremental update to a Step.
    
    Used for streaming text content and tool calls as they arrive.
    """
    content: str | None = None  # Text to append
    tool_calls: list[dict] | None = None  # Tool calls to append/update


class StepEvent(BaseModel):
    """
    Unified event for Step-based streaming.
    
    Frontend receives these events via SSE and uses them to:
    1. Build up Steps incrementally (via delta)
    2. Finalize Steps (via snapshot)
    3. Track run status
    
    Examples:
        Delta event (streaming text):
            StepEvent(
                type=StepEventType.STEP_DELTA,
                step_id="step_123",
                run_id="run_456",
                delta=StepDelta(content="Hello")
            )
        
        Completed event (final state):
            StepEvent(
                type=StepEventType.STEP_COMPLETED,
                step_id="step_123",
                run_id="run_456",
                snapshot=Step(...)
            )
        
        Run started:
            StepEvent(
                type=StepEventType.RUN_STARTED,
                run_id="run_456",
                data={"query": "Hello"}
            )
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
    
    def to_sse(self) -> str:
        """
        Convert to Server-Sent Events format.
        
        Returns:
            str: SSE-formatted string ready to send to client
        """
        import json
        data = self.model_dump(mode='json')
        return f"data: {json.dumps(data)}\n\n"


# Convenience functions for creating events

def create_run_started_event(run_id: str, query: str) -> StepEvent:
    """Create a RUN_STARTED event"""
    return StepEvent(
        type=StepEventType.RUN_STARTED,
        run_id=run_id,
        data={"query": query}
    )


def create_run_completed_event(
    run_id: str,
    response: str,
    metrics: dict
) -> StepEvent:
    """Create a RUN_COMPLETED event"""
    return StepEvent(
        type=StepEventType.RUN_COMPLETED,
        run_id=run_id,
        data={
            "response": response,
            "metrics": metrics
        }
    )


def create_run_failed_event(run_id: str, error: str) -> StepEvent:
    """Create a RUN_FAILED event"""
    return StepEvent(
        type=StepEventType.RUN_FAILED,
        run_id=run_id,
        data={"error": error}
    )


def create_step_delta_event(
    step_id: str,
    run_id: str,
    delta: StepDelta
) -> StepEvent:
    """Create a STEP_DELTA event"""
    return StepEvent(
        type=StepEventType.STEP_DELTA,
        step_id=step_id,
        run_id=run_id,
        delta=delta
    )


def create_step_completed_event(
    step_id: str,
    run_id: str,
    snapshot: Step
) -> StepEvent:
    """Create a STEP_COMPLETED event"""
    return StepEvent(
        type=StepEventType.STEP_COMPLETED,
        step_id=step_id,
        run_id=run_id,
        snapshot=snapshot
    )


def create_error_event(run_id: str, error: str, error_type: str = "unknown") -> StepEvent:
    """Create an ERROR event"""
    return StepEvent(
        type=StepEventType.ERROR,
        run_id=run_id,
        data={"error": error, "error_type": error_type}
    )
