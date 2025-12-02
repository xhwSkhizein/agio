"""
Control flow utilities for agent execution.

This module consolidates:
- AbortSignal: Graceful cancellation mechanism
- retry_from_sequence: Retry from a specific point
- fork_session: Create session branches
"""

import asyncio
from typing import TYPE_CHECKING, AsyncIterator, List
from uuid import uuid4

from agio.domain import Step, StepEvent
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.storage import AgentRunRepository
    from agio.runtime.runner import StepRunner

logger = get_logger(__name__)


# ============================================================================
# AbortSignal
# ============================================================================


class AbortSignal:
    """
    Abort signal for graceful cancellation of long-running operations.
    
    Based on asyncio.Event, supports:
    - Synchronous abort status check
    - Async wait for abort signal
    - Recording abort reason
    
    Examples:
        >>> signal = AbortSignal()
        >>> 
        >>> # Trigger abort in another task
        >>> signal.abort("User cancelled")
        >>> 
        >>> # Check in tool execution
        >>> if signal.is_aborted():
        >>>     return  # Early exit
        >>> 
        >>> # Or async wait
        >>> await signal.wait()
    """
    
    def __init__(self):
        self._event = asyncio.Event()
        self._reason: str | None = None
    
    def abort(self, reason: str = "Operation cancelled"):
        """Trigger abort signal."""
        self._reason = reason
        self._event.set()
    
    def is_aborted(self) -> bool:
        """Check if abort has been triggered."""
        return self._event.is_set()
    
    async def wait(self):
        """Async wait for abort signal."""
        await self._event.wait()
    
    @property
    def reason(self) -> str | None:
        """Get abort reason."""
        return self._reason
    
    def reset(self):
        """Reset abort signal for reuse."""
        self._event.clear()
        self._reason = None


# ============================================================================
# Retry
# ============================================================================


async def retry_from_sequence(
    session_id: str,
    sequence: int,
    repository: "AgentRunRepository",
    runner: "StepRunner",
) -> AsyncIterator[StepEvent]:
    """
    Retry from a specific sequence.

    Deletes all steps with sequence >= N and resumes execution
    from the last remaining step.

    Args:
        session_id: Session ID to retry
        sequence: Sequence number to retry from (inclusive)
        repository: Repository for step operations
        runner: Agent runner to resume execution

    Yields:
        StepEvent: Events from the resumed execution
    """
    logger.info("retry_started", session_id=session_id, sequence=sequence)

    # 1. Delete steps with sequence >= N
    deleted_count = await repository.delete_steps(session_id, start_seq=sequence)
    logger.info("retry_steps_deleted", session_id=session_id, deleted_count=deleted_count)

    # 2. Get the last remaining step
    last_step = await repository.get_last_step(session_id)

    if not last_step:
        raise ValueError("No steps remaining after deletion. Cannot retry.")

    logger.info(
        "retry_resuming_from",
        session_id=session_id,
        last_step_sequence=last_step.sequence,
        last_step_role=last_step.role,
    )

    # 3. Determine what to do based on the last step's role
    if last_step.is_user_step():
        async for event in runner.resume_from_user_step(session_id, last_step):
            yield event

    elif last_step.is_tool_step():
        async for event in runner.resume_from_tool_step(session_id, last_step):
            yield event

    elif last_step.is_assistant_step():
        if last_step.has_tool_calls():
            async for event in runner.resume_from_assistant_with_tools(session_id, last_step):
                yield event
        else:
            # Delete this assistant step too and retry from previous
            await repository.delete_steps(session_id, start_seq=last_step.sequence)
            async for event in retry_from_sequence(
                session_id, last_step.sequence, repository, runner
            ):
                yield event
    else:
        raise ValueError(f"Cannot retry from step with role: {last_step.role}")


# ============================================================================
# Fork
# ============================================================================


async def fork_session(
    original_session_id: str,
    sequence: int,
    repository: "AgentRunRepository",
) -> str:
    """
    Fork a session at a specific sequence.

    Creates a new session with a copy of all steps up to and including
    the specified sequence.

    Args:
        original_session_id: Original session ID to fork from
        sequence: Sequence number to fork at (inclusive)
        repository: Repository for step operations

    Returns:
        str: New session ID
    """
    logger.info("fork_started", original_session_id=original_session_id, sequence=sequence)

    # 1. Get steps up to sequence
    steps = await repository.get_steps(original_session_id, end_seq=sequence)

    if not steps:
        raise ValueError(
            f"No steps found in session {original_session_id} up to sequence {sequence}"
        )

    # 2. Create new session ID
    new_session_id = str(uuid4())

    logger.info(
        "fork_creating_session",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        steps_to_copy=len(steps),
    )

    # 3. Copy steps to new session
    new_steps: List[Step] = []
    for step in steps:
        new_step = step.model_copy(update={"session_id": new_session_id})
        new_steps.append(new_step)

    # 4. Batch save to new session
    await repository.save_steps_batch(new_steps)

    logger.info(
        "fork_completed",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        copied_steps=len(new_steps),
    )

    return new_session_id


__all__ = ["AbortSignal", "retry_from_sequence", "fork_session"]
