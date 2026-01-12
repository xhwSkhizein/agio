"""
Step Pipeline - Unified pipeline for Step processing and side effects.

This module provides the central pipeline for handling execution Steps.
It orchestrates:
- Event streaming via Wire
- Persistence via SessionStore
- Observability via TraceCollector
- Sequence allocation
"""

from typing import TYPE_CHECKING

from agio.domain import Run, Step, StepDelta
from agio.observability.collector import TraceCollector
from agio.runtime.context import ExecutionContext
from agio.runtime.event_factory import EventFactory
from agio.runtime.sequence_manager import SequenceManager

if TYPE_CHECKING:
    from agio.domain.models import RunOutput
    from agio.storage.session.base import SessionStore


class StepPipeline:
    """
    Unified pipeline for Step processing and side effects.

    Decouples execution logic from storage, observability, and event streaming.
    """

    def __init__(
        self,
        context: ExecutionContext,
        session_store: "SessionStore | None" = None,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self.context = context
        self.wire = context.wire
        self.session_store = session_store
        self.trace_collector = trace_collector
        self.sequence_manager = (
            SequenceManager(session_store) if session_store else None
        )
        self.ef = EventFactory(context)

    async def allocate_sequence(self) -> int:
        """Allocate next sequence number for the current session."""
        if self.sequence_manager:
            return await self.sequence_manager.allocate(
                self.context.session_id, self.context
            )
        return 1

    async def emit_run_started(self, run: Run) -> None:
        """Handle Run Started event."""
        # Start Trace
        if self.trace_collector:
            self.trace_collector.start(
                trace_id=self.context.trace_id,
                agent_id=run.runnable_id,
                session_id=run.session_id,
                user_id=self.context.user_id,
                input_query=run.input_query,
            )

        # Emit Event
        event = self.ef.run_started(run.input_query)
        await self.wire.write(event)

        # Update Trace
        if self.trace_collector:
            await self.trace_collector.collect(event)

        # Persist Run (Initial state)
        if self.session_store:
            await self.session_store.save_run(run)

    async def emit_step_delta(self, step_id: str, delta: StepDelta) -> None:
        """Handle streaming Step Delta."""
        # Emit Event
        event = self.ef.step_delta(step_id, delta)
        await self.wire.write(event)

        # Update Trace (Optional: some trace implementations might want streaming updates)
        if self.trace_collector:
            await self.trace_collector.collect(event)

    async def commit_step(self, step: Step) -> None:
        """Commit a completed Step."""
        # Emit Event
        event = self.ef.step_completed(step.id, step)
        await self.wire.write(event)

        # Update Trace
        if self.trace_collector:
            await self.trace_collector.collect(event)

        # Persist Step
        if self.session_store:
            await self.session_store.save_step(step)

    async def emit_run_completed(self, run: Run, output: "RunOutput") -> None:
        """Handle Run Completed event."""
        # Emit Event
        event = self.ef.run_completed(
            response=output.response or "",
            metrics={
                "duration": run.metrics.duration,
                "total_tokens": run.metrics.total_tokens,
            },
            termination_reason=output.termination_reason,
        )
        await self.wire.write(event)

        # Update Trace (Finish)
        if self.trace_collector:
            await self.trace_collector.collect(event)
            await self.trace_collector.stop()

        # Persist Run (Final state)
        if self.session_store:
            await self.session_store.save_run(run)

    async def emit_run_failed(self, run: Run, error: Exception) -> None:
        """Handle Run Failed event."""
        # Emit Event
        event = self.ef.run_failed(str(error))
        await self.wire.write(event)

        # Update Trace (Fail)
        if self.trace_collector:
            # We collect the event first so the trace log shows the failure event
            await self.trace_collector.collect(event)
            self.trace_collector.fail(error)
            await self.trace_collector.stop()

        # Persist Run (Final state)
        if self.session_store:
            await self.session_store.save_run(run)
