"""
Control flow utilities for agent execution.

This module consolidates:
- AbortSignal: Graceful cancellation mechanism
- retry_from_sequence: Retry from a specific point
- fork_session: Create session branches
"""

import asyncio
from typing import TYPE_CHECKING, AsyncIterator, List, Optional
from uuid import uuid4

from agio.domain import Step, StepEvent, MessageRole
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.storage import SessionStore
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
    session_store: "SessionStore",
    runner: "StepRunner",
) -> AsyncIterator[StepEvent]:
    """
    Retry from a specific sequence.

    Deletes all steps with sequence >= N and resumes execution
    from the last remaining step.

    Args:
        session_id: Session ID to retry
        sequence: Sequence number to retry from (inclusive)
        session_store: SessionStore for step operations
        runner: Agent runner to resume execution

    Yields:
        StepEvent: Events from the resumed execution
    """
    logger.info("retry_started", session_id=session_id, sequence=sequence)

    # 1. Delete steps with sequence >= N
    deleted_count = await session_store.delete_steps(session_id, start_seq=sequence)
    logger.info("retry_steps_deleted", session_id=session_id, deleted_count=deleted_count)

    # 2. Get the last remaining step
    last_step = await session_store.get_last_step(session_id)

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
            await session_store.delete_steps(session_id, start_seq=last_step.sequence)
            async for event in retry_from_sequence(
                session_id, last_step.sequence, session_store, runner
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
    session_store: "SessionStore",
    modified_content: Optional[str] = None,
    modified_tool_calls: Optional[List[dict]] = None,
    exclude_last: bool = False,
) -> tuple[str, int, Optional[str]]:
    """
    Fork a session at a specific sequence.

    Creates a new session with a copy of all steps up to and including
    the specified sequence. Target can be assistant or user step.
    
    For assistant steps:
        - Can modify content and/or tool_calls
    For user steps:
        - Use exclude_last=True to copy steps BEFORE the user step
        - Returns the user message content for client to use

    Args:
        original_session_id: Original session ID to fork from
        sequence: Sequence number to fork at (inclusive)
        session_store: Repository for step operations
        modified_content: Optional new content for assistant step
        modified_tool_calls: Optional new tool_calls for assistant step
        exclude_last: If True, exclude the target step (for user step fork)

    Returns:
        tuple[str, int, Optional[str]]: (new_session_id, last_step_sequence, pending_user_message)
    """
    logger.info("fork_started", original_session_id=original_session_id, sequence=sequence)

    # 1. Get steps up to sequence
    steps = await session_store.get_steps(original_session_id, end_seq=sequence)

    if not steps:
        raise ValueError(
            f"No steps found in session {original_session_id} up to sequence {sequence}"
        )

    target_step = steps[-1]
    pending_user_message: Optional[str] = None

    # 2. Handle user step fork - exclude the user step and return its content
    if target_step.role == MessageRole.USER:
        if not exclude_last:
            # For user step, we must exclude it and return content for input box
            exclude_last = True
        pending_user_message = target_step.content
        steps = steps[:-1]  # Remove user step
        
        if not steps:
            raise ValueError("Cannot fork from first user message - no prior context")

    # 3. Create new session ID
    new_session_id = str(uuid4())

    logger.info(
        "fork_creating_session",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        steps_to_copy=len(steps),
        modified=modified_content is not None or modified_tool_calls is not None,
        has_pending_user_message=pending_user_message is not None,
    )

    # 4. Copy steps to new session with new IDs
    new_steps: List[Step] = []
    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1
        
        update_fields = {
            "id": str(uuid4()),
            "session_id": new_session_id,
        }
        
        # Modify the last assistant step if modifications provided
        if is_last and step.role == MessageRole.ASSISTANT:
            if modified_content is not None:
                update_fields["content"] = modified_content
            if modified_tool_calls is not None:
                update_fields["tool_calls"] = modified_tool_calls if modified_tool_calls else None
        
        new_step = step.model_copy(update=update_fields)
        new_steps.append(new_step)

    # 5. Batch save to new session
    if new_steps:
        await session_store.save_steps_batch(new_steps)

    last_sequence = new_steps[-1].sequence if new_steps else 0

    logger.info(
        "fork_completed",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        copied_steps=len(new_steps),
        last_sequence=last_sequence,
    )

    return new_session_id, last_sequence, pending_user_message


__all__ = ["AbortSignal", "retry_from_sequence", "fork_session"]
