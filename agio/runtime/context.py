"""
Step-based context builder.

This module provides context building from Steps using the StepAdapter.
"""

from typing import TYPE_CHECKING

from agio.domain import Step, StepAdapter
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.providers.storage import AgentRunRepository

logger = get_logger(__name__)


async def build_context_from_steps(
    session_id: str,
    repository: "AgentRunRepository",
    system_prompt: str | None = None,
) -> list[dict]:
    """
    Build LLM context from Steps using StepAdapter.

    Args:
        session_id: Session ID
        repository: Repository to fetch steps from
        system_prompt: Optional system prompt to prepend

    Returns:
        list[dict]: Messages in OpenAI format, ready to send to LLM
    """
    logger.debug("building_context", session_id=session_id)

    # 1. Query steps from repository
    steps = await repository.get_steps(session_id)

    logger.debug("context_steps_loaded", session_id=session_id, count=len(steps))

    # 2. Convert using StepAdapter
    messages = StepAdapter.steps_to_messages(steps)

    # 3. Optionally prepend system prompt
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    logger.debug("context_built", session_id=session_id, message_count=len(messages))

    return messages


async def build_context_from_sequence_range(
    session_id: str,
    repository: "AgentRunRepository",
    start_seq: int | None = None,
    end_seq: int | None = None,
    system_prompt: str | None = None,
) -> list[dict]:
    """
    Build context from a specific sequence range.

    Args:
        session_id: Session ID
        repository: Repository
        start_seq: Start sequence (inclusive), None = from beginning
        end_seq: End sequence (inclusive), None = to end
        system_prompt: Optional system prompt

    Returns:
        list[dict]: Messages in OpenAI format
    """
    steps = await repository.get_steps(session_id, start_seq=start_seq, end_seq=end_seq)
    messages = StepAdapter.steps_to_messages(steps)

    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    return messages


def validate_context(messages: list[dict]) -> bool:
    """
    Validate that context is in correct format for LLM.

    Args:
        messages: Messages to validate

    Returns:
        bool: True if valid

    Raises:
        ValueError: If validation fails
    """
    valid_roles = {"system", "user", "assistant", "tool"}
    tool_call_ids = set()

    for i, msg in enumerate(messages):
        if "role" not in msg:
            raise ValueError(f"Message {i} missing 'role' field")

        role = msg["role"]

        if role not in valid_roles:
            raise ValueError(f"Message {i} has invalid role: {role}")

        if role == "assistant" and "tool_calls" in msg:
            for tc in msg.get("tool_calls", []):
                if "id" in tc:
                    tool_call_ids.add(tc["id"])

        if role == "tool":
            if "tool_call_id" not in msg:
                raise ValueError(f"Tool message {i} missing 'tool_call_id'")

            if msg["tool_call_id"] not in tool_call_ids:
                logger.warning(
                    "tool_call_id_not_found",
                    message_index=i,
                    tool_call_id=msg["tool_call_id"],
                )

    return True


async def get_context_summary(
    session_id: str,
    repository: "AgentRunRepository",
) -> dict:
    """
    Get a summary of the context without building full messages.

    Args:
        session_id: Session ID
        repository: Repository

    Returns:
        dict: Summary with counts and stats
    """
    steps = await repository.get_steps(session_id)

    return {
        "total_steps": len(steps),
        "user_steps": sum(1 for s in steps if s.is_user_step()),
        "assistant_steps": sum(1 for s in steps if s.is_assistant_step()),
        "tool_steps": sum(1 for s in steps if s.is_tool_step()),
        "total_tool_calls": sum(
            len(s.tool_calls) for s in steps if s.is_assistant_step() and s.tool_calls
        ),
        "sequence_range": {
            "min": steps[0].sequence if steps else None,
            "max": steps[-1].sequence if steps else None,
        },
    }


__all__ = [
    "build_context_from_steps",
    "build_context_from_sequence_range",
    "validate_context",
    "get_context_summary",
]
