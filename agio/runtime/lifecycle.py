"""
Run Lifecycle - Context Manager for Run execution.

This module provides the RunLifecycle context manager that handles
the state transitions, error handling, and metrics finalization for a Run.
"""

import time
from typing import TYPE_CHECKING

from agio.domain import Run, RunStatus
from agio.runtime.context import ExecutionContext, RunnableType
from agio.runtime.pipeline import StepPipeline
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.domain.models import RunOutput

logger = get_logger(__name__)


class RunLifecycle:
    """
    Context Manager for Run lifecycle management.

    Usage:
        async with RunLifecycle(context, pipeline, input_query, agent_id) as run:
            result = await executor.execute(...)
            run_lifecycle.set_output(result)
            return result
    """

    def __init__(
        self,
        context: ExecutionContext,
        pipeline: StepPipeline,
        input_query: str,
        runnable_id: str,
        runnable_type: RunnableType = RunnableType.AGENT,
    ) -> None:
        self.context = context
        self.pipeline = pipeline
        self.input_query = input_query
        self.runnable_id = runnable_id
        self.runnable_type = runnable_type
        
        self.run: Run | None = None
        self._output: "RunOutput | None" = None

    def set_output(self, output: "RunOutput") -> None:
        """Set the execution output (success case)."""
        self._output = output

    async def __aenter__(self) -> Run:
        """Start the Run."""
        self.run = Run(
            id=self.context.run_id,
            runnable_id=self.runnable_id,
            runnable_type=self.runnable_type.value,
            session_id=self.context.session_id,
            input_query=self.input_query,
            status=RunStatus.RUNNING,
            parent_run_id=self.context.parent_run_id,
        )
        self.run.metrics.start_time = time.time()
        
        await self.pipeline.emit_run_started(self.run)
        return self.run

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Finalize the Run."""
        if not self.run:
            return

        # Calculate Duration
        self.run.metrics.end_time = time.time()
        self.run.metrics.duration = (
            self.run.metrics.end_time - self.run.metrics.start_time
        )

        if exc_val:
            # === FAILURE CASE ===
            self.run.status = RunStatus.FAILED
            logger.error(
                "run_failed",
                run_id=self.run.id,
                agent_id=self.run.runnable_id,
                error=str(exc_val),
                exc_info=True,
            )
            await self.pipeline.emit_run_failed(self.run, exc_val)
        
        elif self._output:
            # === SUCCESS CASE ===
            self.run.status = RunStatus.COMPLETED
            self.run.response_content = self._output.response
            
            # Sync Metrics
            if self._output.metrics:
                self.run.metrics.total_tokens = self._output.metrics.total_tokens
                self.run.metrics.input_tokens = self._output.metrics.input_tokens
                self.run.metrics.output_tokens = self._output.metrics.output_tokens
                self.run.metrics.tool_calls_count = self._output.metrics.tool_calls_count

            await self.pipeline.emit_run_completed(self.run, self._output)
            
        else:
            # === UNEXPECTED EMPTY CASE ===
            # This happens if code exited without exception but set_output wasn't called.
            # We treat this as a failure or incomplete run.
            self.run.status = RunStatus.FAILED
            msg = "Run exited without output or exception"
            logger.error("run_incomplete", run_id=self.run.id, error=msg)
            await self.pipeline.emit_run_failed(self.run, Exception(msg))
