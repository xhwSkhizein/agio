"""
RunnableExecutor - Unified execution engine for Run lifecycle management.

This module provides:
- Unified Run lifecycle management for all Runnable types
- Run event emission (RUN_STARTED, RUN_COMPLETED, RUN_FAILED)
- Run persistence to SessionStore

The executor wraps any Runnable.run() call with Run management,
without modifying the Runnable.run() signature.
"""

import asyncio
import time
from typing import AsyncIterator
from uuid import uuid4

from agio.domain import Run, RunStatus, StepEvent
from agio.runtime.event_factory import EventFactory
from agio.runtime.protocol import ExecutionContext, Runnable, RunOutput, RunnableType
from agio.runtime.wire import Wire
from agio.storage.session.base import SessionStore
from agio.utils.logging import get_logger

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

    def __init__(self, store: "SessionStore | None" = None) -> None:
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

        # Get runnable_type as string (handle both enum and string)
        runnable_type_value = runnable.runnable_type
        if isinstance(runnable_type_value, RunnableType):
            runnable_type_value = runnable_type_value.value
        elif not isinstance(runnable_type_value, str):
            runnable_type_value = str(runnable_type_value)

        # Create Run record
        run = Run(
            id=context.run_id,
            runnable_id=runnable.id,
            runnable_type=runnable_type_value,
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

    async def execute_with_wire(
        self,
        runnable: Runnable,
        input: str,
        wire: Wire,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        _parent_context: ExecutionContext | None = None,
    ) -> RunOutput:
        """
        Execute a Runnable with Wire, automatically constructing ExecutionContext.

        This is a simplified version of execute() that accepts Wire and business parameters,
        and constructs ExecutionContext internally.

        Args:
            runnable: The Runnable to execute
            input: Input string
            wire: Wire instance (must be created by caller for stream consumption)
            session_id: Session ID (auto-generated if not provided)
            user_id: User ID (optional)
            metadata: Additional metadata (optional)
            _parent_context: Parent context for nested execution (internal use)

        Returns:
            RunOutput from the Runnable

        Note:
            - Wire must be created by caller (typically at API layer) for stream consumption
            - For nested execution (Workflow), use execute() with pre-constructed context
        """
        # Generate run_id internally
        run_id = str(uuid4())

        # Construct ExecutionContext
        if _parent_context:
            # Nested execution: use child context
            context = _parent_context.child(
                run_id=run_id,
                nested_runnable_id=runnable.id,
                runnable_type=runnable.runnable_type,
                runnable_id=runnable.id,
            )
        else:
            # Top-level execution: create new context
            context = ExecutionContext(
                run_id=run_id,
                session_id=session_id or str(uuid4()),
                wire=wire,
                user_id=user_id,
                runnable_type=runnable.runnable_type,
                runnable_id=runnable.id,
                metadata=metadata or {},
            )

        # Delegate to execute()
        return await self.execute(runnable, input, context)

    async def execute_stream(
        self,
        runnable: Runnable,
        input: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
    ) -> AsyncIterator[StepEvent]:
        """
        Execute a Runnable in streaming mode, automatically managing Wire and Task lifecycle.

        This method creates Wire internally, starts execution in a background task,
        and yields events from the wire. Wire cleanup is handled automatically.

        Args:
            runnable: The Runnable to execute
            input: Input string
            session_id: Session ID (auto-generated if not provided)
            user_id: User ID (optional)
            metadata: Additional metadata (optional)

        Yields:
            StepEvent: Events from the execution

        Example:
            async for event in executor.execute_stream(agent, query, session_id="sess_123"):
                print(event.type, event.data)
        """
        wire = Wire()

        async def _run():
            try:
                await self.execute_with_wire(
                    runnable,
                    input,
                    wire,
                    session_id=session_id,
                    user_id=user_id,
                    metadata=metadata,
                )
            finally:
                await wire.close()

        task = asyncio.create_task(_run())

        try:
            async for event in wire.read():
                yield event
        finally:
            # Ensure task is cleaned up
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


__all__ = ["RunnableExecutor"]
