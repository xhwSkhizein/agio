"""
RunnableExecutor - Unified execution engine for Run lifecycle management.

This module provides:
- Unified Run lifecycle management for all Runnable types
- Run event emission (RUN_STARTED, RUN_COMPLETED, RUN_FAILED)
- Run persistence to SessionStore

The executor wraps any Runnable.run() call with Run management,
without modifying the Runnable.run() signature.
"""

import time

from agio.domain import RunStatus, Run
from agio.runtime.protocol import Runnable, RunOutput
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext
from agio.utils.logging import get_logger
from agio.storage.session.base import SessionStore


logger = get_logger(__name__)


class RunnableExecutor:
    """
    Unified execution engine for Run lifecycle management.

    Responsibilities:
    1. Create Run record
    2. Manage Run status (RUNNING → COMPLETED/FAILED)
    3. Emit Run-level events
    4. Save Run to SessionStore

    Does NOT:
    - Manage state (Agent/Workflow handle their own)
    - Modify Runnable internal logic
    """

    def __init__(self, store: "SessionStore | None" = None):
        """
        Initialize RunnableExecutor.

        Args:
            store: SessionStore for Run persistence (optional)
        """
        self.store = store

    async def execute(
        self,
        runnable: Runnable,
        input: str,
        context: ExecutionContext,
    ) -> RunOutput:
        """
        Execute a Runnable with Run lifecycle management.

        Flow:
        1. Create Run record
        2. Emit RUN_STARTED event
        3. Delegate to runnable.run() (signature unchanged)
        4. Update Run status
        5. Emit RUN_COMPLETED/FAILED event
        6. Save Run

        Args:
            runnable: The Runnable to execute
            input: Input string
            context: Execution context with wire

        Returns:
            RunOutput from the Runnable
        """

        # 1. Create Run record
        run = Run(
            id=context.run_id,
            runnable_id=runnable.id,
            runnable_type=runnable.runnable_type,
            session_id=context.session_id,
            input_query=input,
            status=RunStatus.RUNNING,
            workflow_id=context.workflow_id,
            parent_run_id=context.parent_run_id,
        )
        run.metrics.start_time = time.time()

        # Create EventFactory
        ef = EventFactory(context)

        logger.info(
            "run_started",
            run_id=run.id,
            runnable_id=runnable.id,
            runnable_type=runnable.runnable_type,
            session_id=context.session_id,
            depth=context.depth,
        )

        # 2. Emit RUN_STARTED event
        await context.wire.write(ef.run_started(input))

        try:
            # 3. Delegate to runnable.run()
            result: RunOutput = await runnable.run(input, context=context)

            # 4. Update Run
            run.status = RunStatus.COMPLETED
            run.response_content = result.response
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time

            # Merge metrics from result if available
            if result.metrics:
                run.metrics.total_tokens = result.metrics.total_tokens
                run.metrics.input_tokens = result.metrics.input_tokens
                run.metrics.output_tokens = result.metrics.output_tokens
                run.metrics.tool_calls_count = result.metrics.tool_calls_count

            logger.info(
                "run_completed",
                run_id=run.id,
                duration=run.metrics.duration,
                tokens=run.metrics.total_tokens,
            )

            # 5. Emit RUN_COMPLETED event
            await context.wire.write(
                ef.run_completed(
                    response=result.response or "",
                    metrics={
                        "duration": run.metrics.duration,
                        "total_tokens": run.metrics.total_tokens,
                    },
                    termination_reason=result.termination_reason,
                )
            )

            # 6. Save Run
            if self.store:
                await self.store.save_run(run)
                logger.debug("run_saved", run_id=run.id)

            return result

        except Exception as e:
            run.status = RunStatus.FAILED
            run.metrics.end_time = time.time()
            run.metrics.duration = run.metrics.end_time - run.metrics.start_time

            logger.error("run_failed", run_id=run.id, error=str(e))

            # Emit RUN_FAILED event
            await context.wire.write(ef.run_failed(str(e)))

            if self.store:
                await self.store.save_run(run)

            raise


__all__ = ["RunnableExecutor"]
