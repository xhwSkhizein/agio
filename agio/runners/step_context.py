"""
Step-based context builder.

This module provides zero-conversion context building from Steps.
"""

from typing import List
from agio.domain.step import Step
from agio.db.repository import AgentRunRepository
from agio.utils.logging import get_logger

logger = get_logger(__name__)


async def build_context_from_steps(
    session_id: str,
    repository: AgentRunRepository,
    system_prompt: str | None = None
) -> List[dict]:
    """
    Build LLM context from Steps - ZERO conversion needed!
    
    This is the core benefit of the Step-based architecture:
    Steps are stored in native LLM message format, so building
    context is just a simple query + conversion to dict.
    
    Args:
        session_id: Session ID
        repository: Repository to fetch steps from
        system_prompt: Optional system prompt to prepend
    
    Returns:
        List[dict]: Messages in OpenAI format, ready to send to LLM
    
    Example:
        messages = await build_context_from_steps(session_id, repo)
        response = await llm.chat(messages)
    """
    logger.debug("building_context", session_id=session_id)
    
    # 1. Query: SELECT * FROM steps WHERE session_id = ? ORDER BY sequence
    steps = await repository.get_steps(session_id)
    
    logger.debug("context_steps_loaded", session_id=session_id, count=len(steps))
    
    # 2. Convert: step.to_message_dict() for each step
    messages = [step.to_message_dict() for step in steps]
    
    # 3. Optionally prepend system prompt
    if system_prompt:
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })
    
    logger.debug("context_built", session_id=session_id, message_count=len(messages))
    
    return messages


async def build_context_from_sequence_range(
    session_id: str,
    repository: AgentRunRepository,
    start_seq: int | None = None,
    end_seq: int | None = None,
    system_prompt: str | None = None
) -> List[dict]:
    """
    Build context from a specific sequence range.
    
    Useful for:
    - Replaying a specific portion of conversation
    - Building context for fork/retry operations
    - Debugging specific interactions
    
    Args:
        session_id: Session ID
        repository: Repository
        start_seq: Start sequence (inclusive), None = from beginning
        end_seq: End sequence (inclusive), None = to end
        system_prompt: Optional system prompt
    
    Returns:
        List[dict]: Messages in OpenAI format
    """
    logger.debug(
        "building_context_range",
        session_id=session_id,
        start_seq=start_seq,
        end_seq=end_seq
    )
    
    # Query with sequence range
    steps = await repository.get_steps(
        session_id,
        start_seq=start_seq,
        end_seq=end_seq
    )
    
    logger.debug(
        "context_range_steps_loaded",
        session_id=session_id,
        count=len(steps)
    )
    
    # Convert to messages
    messages = [step.to_message_dict() for step in steps]
    
    # Optionally prepend system prompt
    if system_prompt:
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })
    
    return messages


def validate_context(messages: List[dict]) -> bool:
    """
    Validate that context is in correct format for LLM.
    
    Checks:
    - All messages have 'role' field
    - Roles are valid
    - Tool messages have tool_call_id
    - Assistant tool_calls reference valid tool_call_ids
    
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
        # Check role exists
        if "role" not in msg:
            raise ValueError(f"Message {i} missing 'role' field")
        
        role = msg["role"]
        
        # Check role is valid
        if role not in valid_roles:
            raise ValueError(f"Message {i} has invalid role: {role}")
        
        # Collect tool_call_ids from assistant messages
        if role == "assistant" and "tool_calls" in msg:
            for tc in msg.get("tool_calls", []):
                if "id" in tc:
                    tool_call_ids.add(tc["id"])
        
        # Validate tool messages have tool_call_id
        if role == "tool":
            if "tool_call_id" not in msg:
                raise ValueError(f"Tool message {i} missing 'tool_call_id'")
            
            # Check tool_call_id references a valid tool call
            # (This is a soft check - LLM might still accept it)
            if msg["tool_call_id"] not in tool_call_ids:
                logger.warning(
                    "tool_call_id_not_found",
                    message_index=i,
                    tool_call_id=msg["tool_call_id"]
                )
    
    return True


async def get_context_summary(
    session_id: str,
    repository: AgentRunRepository
) -> dict:
    """
    Get a summary of the context without building full messages.
    
    Useful for:
    - Checking context size before building
    - Displaying conversation stats
    - Debugging
    
    Args:
        session_id: Session ID
        repository: Repository
    
    Returns:
        dict: Summary with counts and stats
    """
    steps = await repository.get_steps(session_id)
    
    summary = {
        "total_steps": len(steps),
        "user_steps": sum(1 for s in steps if s.is_user_step()),
        "assistant_steps": sum(1 for s in steps if s.is_assistant_step()),
        "tool_steps": sum(1 for s in steps if s.is_tool_step()),
        "total_tool_calls": sum(
            len(s.tool_calls) for s in steps
            if s.is_assistant_step() and s.tool_calls
        ),
        "sequence_range": {
            "min": steps[0].sequence if steps else None,
            "max": steps[-1].sequence if steps else None
        },
        "time_range": {
            "first": steps[0].created_at if steps else None,
            "last": steps[-1].created_at if steps else None
        }
    }
    
    return summary
