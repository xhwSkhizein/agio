"""
Retry logic for re-executing from a specific sequence point.

This module implements the retry functionality as specified in the refactor design:
1. Delete steps with sequence >= N
2. Get the last remaining step
3. Resume agent loop from that point
"""

from typing import AsyncIterator, TYPE_CHECKING
from agio.domain.step import Step, MessageRole
from agio.protocol.step_events import StepEvent
from agio.db.repository import AgentRunRepository
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.runners.step_runner import StepRunner

logger = get_logger(__name__)


async def retry_from_sequence(
    session_id: str,
    sequence: int,
    repository: AgentRunRepository,
    runner: "StepRunner",
) -> AsyncIterator[StepEvent]:
    """
    Retry from a specific sequence.
    
    This deletes all steps with sequence >= N and resumes execution
    from the last remaining step.
    
    Args:
        session_id: Session ID to retry
        sequence: Sequence number to retry from (inclusive)
        repository: Repository for step operations
        runner: Agent runner to resume execution
    
    Yields:
        StepEvent: Events from the resumed execution
    
    Example:
        # User conversation:
        # 1. User: "Search for Python"
        # 2. Assistant: "Let me search..." + tool_calls
        # 3. Tool: search results
        # 4. Assistant: "Here are the results..."
        
        # Retry from sequence 2 (delete 2, 3, 4 and regenerate from step 1)
        async for event in retry_from_sequence(session_id, 2, repo, runner):
            print(event)
    """
    logger.info(
        "retry_started",
        session_id=session_id,
        sequence=sequence
    )
    
    # 1. Delete steps with sequence >= N
    deleted_count = await repository.delete_steps(session_id, start_seq=sequence)
    
    logger.info(
        "retry_steps_deleted",
        session_id=session_id,
        sequence=sequence,
        deleted_count=deleted_count
    )
    
    # 2. Get the last remaining step
    last_step = await repository.get_last_step(session_id)
    
    if not last_step:
        logger.warning(
            "retry_no_steps_remaining",
            session_id=session_id
        )
        # No steps remaining - need to start fresh
        # This would require the original user query
        raise ValueError("No steps remaining after deletion. Cannot retry.")
    
    logger.info(
        "retry_resuming_from",
        session_id=session_id,
        last_step_id=last_step.id,
        last_step_sequence=last_step.sequence,
        last_step_role=last_step.role
    )
    
    # 3. Determine what to do based on the last step's role
    if last_step.is_user_step():
        # Last step is user input - regenerate assistant response
        # This is the most common retry case
        async for event in runner.resume_from_user_step(session_id, last_step):
            yield event
    
    elif last_step.is_tool_step():
        # Last step is tool result - regenerate assistant response with tool results
        async for event in runner.resume_from_tool_step(session_id, last_step):
            yield event
    
    elif last_step.is_assistant_step():
        if last_step.has_tool_calls():
            # Assistant made tool calls - re-execute tools and continue
            async for event in runner.resume_from_assistant_with_tools(session_id, last_step):
                yield event
        else:
            # Assistant gave final response - this is unusual for retry
            # User probably wants to regenerate this response
            logger.warning(
                "retry_from_final_assistant",
                session_id=session_id,
                step_id=last_step.id
            )
            # Delete this assistant step too and retry from previous
            await repository.delete_steps(session_id, start_seq=last_step.sequence)
            # Recursive retry from previous step
            async for event in retry_from_sequence(
                session_id,
                last_step.sequence,
                repository,
                runner
            ):
                yield event
    
    else:
        # System message or unknown - shouldn't happen
        raise ValueError(f"Cannot retry from step with role: {last_step.role}")


async def retry_last_response(
    session_id: str,
    repository: AgentRunRepository,
    runner: "AgentRunner",
) -> AsyncIterator[StepEvent]:
    """
    Convenience function to retry the last assistant response.
    
    This finds the last assistant step and retries from there.
    
    Args:
        session_id: Session ID
        repository: Repository
        runner: Agent runner
    
    Yields:
        StepEvent: Events from retry
    """
    # Get all steps
    steps = await repository.get_steps(session_id)
    
    if not steps:
        raise ValueError("No steps found in session")
    
    # Find last assistant step
    last_assistant_seq = None
    for step in reversed(steps):
        if step.is_assistant_step():
            last_assistant_seq = step.sequence
            break
    
    if last_assistant_seq is None:
        raise ValueError("No assistant steps found to retry")
    
    # Retry from that sequence
    async for event in retry_from_sequence(
        session_id,
        last_assistant_seq,
        repository,
        runner
    ):
        yield event
