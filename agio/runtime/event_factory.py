"""
EventFactory - Context-bound event factory.

This module provides a factory class that binds to an ExecutionContext
and creates StepEvents without requiring repetitive parameter passing.

Usage:
    ctx = ExecutionContext(run_id="...", session_id="...", wire=wire)
    ef = EventFactory(ctx)

    # Create events without passing context parameters
    yield ef.step_delta(step_id, delta)
    yield ef.step_completed(step_id, snapshot)
    yield ef.run_completed(response, metrics)
"""

from agio.domain import (
    Step,
    StepDelta,
    StepEvent,
    create_error_event,
    create_run_completed_event,
    create_run_failed_event,
    create_run_started_event,
    create_step_completed_event,
    create_step_delta_event,
)
from agio.runtime.context import ExecutionContext, RunnableType


class EventFactory:
    """
    Context-bound event factory.

    Binds to an ExecutionContext and provides methods to create StepEvents
    without repetitive parameter passing of depth, parent_run_id, etc.

    This eliminates the "Repetitive Context Building" code smell where
    every event creation requires passing the same 4 context parameters.

    Example:
        ef = EventFactory(ctx)

        # Before (5 lines per event):
        yield create_step_delta_event(
            step_id=step.id,
            run_id=run_id,
            delta=delta,
            depth=depth,
            parent_run_id=parent_run_id,
            nested_runnable_id=nested_runnable_id,
        )

        # After (1 line per event):
        yield ef.step_delta(step.id, delta)
    """

    def __init__(self, ctx: "ExecutionContext") -> None:
        """
        Initialize factory with execution context.

        Args:
            ctx: ExecutionContext to bind to
        """
        self._ctx = ctx

    @property
    def ctx(self) -> "ExecutionContext":
        """Get the bound execution context."""
        return self._ctx

    def run_started(self, query: str) -> StepEvent:
        """Create a RUN_STARTED event."""
        return create_run_started_event(
            run_id=self._ctx.run_id,
            query=query,
            session_id=self._ctx.session_id,
            depth=self._ctx.depth,
            parent_run_id=self._ctx.parent_run_id,
            nested_runnable_id=self._ctx.nested_runnable_id,
            runnable_type=(
                self._ctx.runnable_type.value
                if isinstance(self._ctx.runnable_type, RunnableType)
                else self._ctx.runnable_type
            ),
            runnable_id=self._ctx.runnable_id,
            nesting_type=self._ctx.nesting_type,
        )

    def run_completed(
        self,
        response: str,
        metrics: dict,
        termination_reason: str | None = None,
        max_steps: int | None = None,
    ) -> StepEvent:
        """Create a RUN_COMPLETED event."""
        return create_run_completed_event(
            run_id=self._ctx.run_id,
            response=response,
            metrics=metrics,
            termination_reason=termination_reason,
            max_steps=max_steps,
            depth=self._ctx.depth,
            parent_run_id=self._ctx.parent_run_id,
            nested_runnable_id=self._ctx.nested_runnable_id,
            runnable_type=(
                self._ctx.runnable_type.value
                if isinstance(self._ctx.runnable_type, RunnableType)
                else self._ctx.runnable_type
            ),
            runnable_id=self._ctx.runnable_id,
            nesting_type=self._ctx.nesting_type,
        )

    def run_failed(self, error: str) -> StepEvent:
        """Create a RUN_FAILED event."""
        return create_run_failed_event(
            run_id=self._ctx.run_id,
            error=error,
            depth=self._ctx.depth,
            parent_run_id=self._ctx.parent_run_id,
            nested_runnable_id=self._ctx.nested_runnable_id,
            runnable_type=(
                self._ctx.runnable_type.value
                if isinstance(self._ctx.runnable_type, RunnableType)
                else self._ctx.runnable_type
            ),
            runnable_id=self._ctx.runnable_id,
            nesting_type=self._ctx.nesting_type,
        )

    def step_delta(self, step_id: str, delta: StepDelta) -> StepEvent:
        """Create a STEP_DELTA event."""
        return create_step_delta_event(
            step_id=step_id,
            run_id=self._ctx.run_id,
            delta=delta,
            depth=self._ctx.depth,
            parent_run_id=self._ctx.parent_run_id,
            nested_runnable_id=self._ctx.nested_runnable_id,
            runnable_type=(
                self._ctx.runnable_type.value
                if isinstance(self._ctx.runnable_type, RunnableType)
                else self._ctx.runnable_type
            ),
            runnable_id=self._ctx.runnable_id,
            nesting_type=self._ctx.nesting_type,
        )

    def step_completed(self, step_id: str, snapshot: Step) -> StepEvent:
        """Create a STEP_COMPLETED event."""
        return create_step_completed_event(
            step_id=step_id,
            run_id=self._ctx.run_id,
            snapshot=snapshot,
            depth=self._ctx.depth,
            parent_run_id=self._ctx.parent_run_id,
            nested_runnable_id=self._ctx.nested_runnable_id,
            runnable_type=(
                self._ctx.runnable_type.value
                if isinstance(self._ctx.runnable_type, RunnableType)
                else self._ctx.runnable_type
            ),
            runnable_id=self._ctx.runnable_id,
            nesting_type=self._ctx.nesting_type,
        )

    def error(self, error: str, error_type: str = "unknown") -> StepEvent:
        """Create an ERROR event."""
        return create_error_event(
            run_id=self._ctx.run_id,
            error=error,
            error_type=error_type,
        )


__all__ = ["EventFactory"]
