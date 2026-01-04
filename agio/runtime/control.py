"""
Control flow utilities for agent execution.

This module consolidates:
- AbortSignal: Graceful cancellation mechanism
- fork_session: Create session branches
"""

import asyncio
from uuid import uuid4

from agio.domain import MessageRole, Step
from agio.storage.session import SessionStore
from agio.utils.logging import get_logger

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

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._reason: str | None = None

    def abort(self, reason: str = "Operation cancelled") -> None:
        """Trigger abort signal."""
        self._reason = reason
        self._event.set()

    def is_aborted(self) -> bool:
        """Check if abort has been triggered."""
        return self._event.is_set()

    async def wait(self) -> None:
        """Async wait for abort signal."""
        await self._event.wait()

    @property
    def reason(self) -> str | None:
        """Get abort reason."""
        return self._reason

    def reset(self) -> None:
        """Reset abort signal for reuse."""
        self._event.clear()
        self._reason = None


# ============================================================================
# Fork
# ============================================================================


async def fork_session(
    original_session_id: str,
    sequence: int,
    session_store: "SessionStore",
    modified_content: str | None = None,
    modified_tool_calls: list[dict] | None = None,
    exclude_last: bool = False,
) -> tuple[str, int, str | None]:
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
        tuple[str, int, str | None]: (new_session_id, last_step_sequence, pending_user_message)
            - str: 新创建的 session_id
            - int: 最后一个 step 的 sequence 号
            - str | None: 如果是 user step fork，返回待处理的 user message；否则为 None
    """
    logger.info("fork_started", original_session_id=original_session_id, sequence=sequence)

    # 1. Get steps up to sequence
    steps = await session_store.get_steps(original_session_id, end_seq=sequence)

    if not steps:
        raise ValueError(
            f"No steps found in session {original_session_id} up to sequence {sequence}"
        )

    target_step = steps[-1]
    pending_user_message: str | None = None

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
    new_steps: list[Step] = []
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


__all__ = ["AbortSignal", "fork_session"]
