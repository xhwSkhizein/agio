"""
ResumeExecutor - Unified Session Resume mechanism.

This module provides unified Resume functionality for both Agent and Workflow:
- Automatically infers runnable_id from Steps
- Analyzes execution state (completed, pending tools, etc.)
- Resumes execution with idempotency

Wire-based Architecture:
- Events are written to context.wire
- Returns RunOutput with response and metrics
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from agio.domain import MessageRole, ExecutionContext
from agio.runtime.wire import Wire
from agio.runtime.runnable_executor import RunnableExecutor
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.storage import SessionStore
    from agio.config import ConfigSystem
    from agio.domain.protocol import RunOutput

logger = get_logger(__name__)


class ExecutionState:
    """Analysis result of execution state from Steps."""

    def __init__(
        self,
        is_completed: bool,
        has_pending_tools: bool,
        runnable_id: str | None,
        runnable_type: str | None,
        last_step_sequence: int,
        final_output: str | None = None,
    ):
        self.is_completed = is_completed
        self.has_pending_tools = has_pending_tools
        self.runnable_id = runnable_id
        self.runnable_type = runnable_type
        self.last_step_sequence = last_step_sequence
        self.final_output = final_output


class ResumeExecutor:
    """
    Unified Session Resume executor.

    Provides unified Resume functionality for both Agent and Workflow:
    1. Loads Steps from session
    2. Infers runnable_id (if not provided)
    3. Analyzes execution state
    4. Resumes with appropriate strategy
    """

    def __init__(
        self,
        store: "SessionStore",
        config_system: "ConfigSystem",
    ):
        """
        Initialize ResumeExecutor.

        Args:
            store: SessionStore for loading Steps
            config_system: ConfigSystem for getting Runnable instances
        """
        self.store = store
        self.config_system = config_system

    async def resume_session(
        self,
        session_id: str,
        runnable_id: str | None = None,
        wire: Wire | None = None,
    ) -> "RunOutput":
        """
        Resume a session with unified logic.

        Args:
            session_id: Session ID to resume
            runnable_id: Optional Runnable ID (auto-inferred if not provided)
            wire: Wire for event streaming (required)

        Returns:
            RunOutput with response and metrics

        Raises:
            ValueError: If session not found or runnable cannot be inferred
        """
        if not wire:
            raise ValueError("Wire is required for resume execution")

        logger.info("resume_session_started", session_id=session_id, runnable_id=runnable_id)

        # 1. Load Steps
        steps = await self.store.get_steps(session_id, limit=10000)
        if not steps:
            raise ValueError(f"Session {session_id} not found or has no steps")

        # 2. Analyze execution state
        state = self._analyze_execution_state(steps)

        # 3. Infer runnable_id if not provided
        if not runnable_id:
            runnable_id = state.runnable_id
            if not runnable_id:
                raise ValueError(
                    f"Cannot infer runnable_id from steps. "
                    f"Please provide runnable_id explicitly."
                )

        logger.info(
            "resume_execution_state",
            session_id=session_id,
            runnable_id=runnable_id,
            is_completed=state.is_completed,
            has_pending_tools=state.has_pending_tools,
        )

        # 4. Check if already completed
        if state.is_completed and not state.has_pending_tools:
            logger.info("resume_already_completed", session_id=session_id)
            from agio.domain.protocol import RunOutput, RunMetrics

            return RunOutput(
                response=state.final_output or "",
                run_id=str(uuid4()),
                session_id=session_id,
                metrics=RunMetrics(),
            )

        # 5. Get Runnable instance
        try:
            runnable = self.config_system.get_instance(runnable_id)
        except Exception as e:
            raise ValueError(f"Runnable {runnable_id} not found: {e}")

        # 6. Create ExecutionContext
        context = ExecutionContext(
            run_id=str(uuid4()),  # New run_id for resume
            session_id=session_id,
            wire=wire,
            runnable_id=runnable_id,
            runnable_type=runnable.runnable_type,
        )

        # 7. Execute via RunnableExecutor (idempotent execution)
        executor = RunnableExecutor(store=self.store)
        
        # For resume, we don't need new input - just re-run
        # The Runnable will handle idempotency (Workflow skips completed nodes)
        input_query = ""  # Empty for resume
        if steps and steps[0].role == MessageRole.USER:
            input_query = steps[0].content or ""

        logger.info("resume_executing", session_id=session_id, runnable_id=runnable_id)
        
        return await executor.execute(runnable, input_query, context)

    def _analyze_execution_state(self, steps: list) -> ExecutionState:
        """
        Analyze execution state from Steps.

        Args:
            steps: List of Steps

        Returns:
            ExecutionState with analysis results
        """
        if not steps:
            return ExecutionState(
                is_completed=False,
                has_pending_tools=False,
                runnable_id=None,
                runnable_type=None,
                last_step_sequence=0,
            )

        last_step = steps[-1]
        
        # Infer runnable_id from the most recent step
        runnable_id = last_step.runnable_id
        runnable_type = last_step.runnable_type

        # Check if last step is assistant with pending tool_calls
        has_pending_tools = (
            last_step.role == MessageRole.ASSISTANT
            and last_step.tool_calls is not None
            and len(last_step.tool_calls) > 0
        )

        # Check if completed (last step is assistant without tool_calls)
        is_completed = (
            last_step.role == MessageRole.ASSISTANT
            and not has_pending_tools
        )

        final_output = None
        if is_completed:
            final_output = last_step.content

        return ExecutionState(
            is_completed=is_completed,
            has_pending_tools=has_pending_tools,
            runnable_id=runnable_id,
            runnable_type=runnable_type,
            last_step_sequence=last_step.sequence,
            final_output=final_output,
        )


__all__ = ["ResumeExecutor", "ExecutionState"]
