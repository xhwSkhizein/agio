"""
Fork logic for creating session branches from a specific sequence point.

This module implements the fork functionality as specified in the refactor design:
1. Create new session ID
2. Copy steps up to sequence N
3. Return new session ID for continued execution
"""

from typing import List
from uuid import uuid4

from agio.storage.repository import AgentRunRepository
from agio.core import Step
from agio.utils.logging import get_logger

logger = get_logger(__name__)


async def fork_session(
    original_session_id: str, sequence: int, repository: AgentRunRepository
) -> str:
    """
    Fork a session at a specific sequence.

    This creates a new session with a copy of all steps up to and including
    the specified sequence. The new session can then be continued independently.

    Args:
        original_session_id: Original session ID to fork from
        sequence: Sequence number to fork at (inclusive)
        repository: Repository for step operations

    Returns:
        str: New session ID

    Example:
        # Original session has steps 1-10
        # Fork at sequence 5
        new_session_id = await fork_session(original_session_id, 5, repo)
        # New session now has steps 1-5
        # Can continue execution in new session independently

    Raises:
        ValueError: If no steps found or sequence is invalid
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
        # Create a copy with new session_id
        # Keep the same sequence numbers for consistency
        new_step = step.model_copy(update={"session_id": new_session_id})
        new_steps.append(new_step)

    # 4. Batch save to new session
    await repository.save_steps_batch(new_steps)

    logger.info(
        "fork_completed",
        original_session_id=original_session_id,
        new_session_id=new_session_id,
        copied_steps=len(new_steps),
        last_sequence=steps[-1].sequence if steps else None,
    )

    return new_session_id


async def fork_from_step_id(step_id: str, repository: AgentRunRepository) -> str:
    """
    Fork a session from a specific step ID.

    This is a convenience function that looks up the step by ID,
    finds its sequence, and forks at that point.

    Args:
        step_id: Step ID to fork from
        repository: Repository

    Returns:
        str: New session ID

    Raises:
        ValueError: If step not found
    """
    # This would require a get_step_by_id method in the repository
    # For now, we'll need to scan through sessions
    # In practice, you'd want to add an index on step.id

    # TODO: Implement get_step_by_id in repository
    raise NotImplementedError("fork_from_step_id requires get_step_by_id in repository")
