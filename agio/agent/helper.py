"""
Step-based context builder.

This module provides context building from Steps using the StepAdapter.
"""

from agio.domain import StepAdapter
from agio.storage.session import SessionStore
from agio.utils.logging import get_logger

logger = get_logger(__name__)


async def build_context_from_steps(
    session_id: str,
    session_store: "SessionStore",
    system_prompt: str | None = None,
    run_id: str | None = None,
    runnable_id: str | None = None,
) -> list[dict]:
    """
    Build LLM context from Steps using StepAdapter.

    Args:
        session_id: Session ID
        session_store: Repository to fetch steps from
        system_prompt: Optional system prompt to prepend
        run_id: Filter by run_id (optional, for isolating agent context)
        runnable_id: Filter by runnable_id (optional, for isolating agent steps)

    Returns:
        list[dict]: Messages in OpenAI format, ready to send to LLM
    """
    logger.debug(
        "building_context",
        session_id=session_id,
        run_id=run_id,
        runnable_id=runnable_id,
    )

    # 1. Query steps from session_store with optional filters
    steps = await session_store.get_steps(
        session_id=session_id,
        run_id=run_id,
        runnable_id=runnable_id,
    )

    logger.debug("context_steps_loaded", session_id=session_id, count=len(steps))

    # 2. Convert using StepAdapter
    messages = StepAdapter.steps_to_messages(steps)

    # 3. Optionally prepend system prompt
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    logger.debug("context_built", session_id=session_id, message_count=len(messages))

    return messages


__all__ = ["build_context_from_steps"]
