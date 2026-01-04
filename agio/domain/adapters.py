"""
Adapters for converting between domain models and external formats.

This module handles all format conversions, keeping domain models pure.
"""

from typing import Any

from .models import MessageRole, Step


class StepAdapter:
    """Adapter for converting Step to/from LLM message format"""

    @staticmethod
    def to_llm_message(step: Step) -> dict[str, Any]:
        """
        Convert Step to LLM message format (OpenAI-compatible).

        Args:
            step: Step instance

        Returns:
            dict: Message in OpenAI format
        """
        msg: dict[str, Any] = {"role": step.role.value}

        if step.content is not None:
            msg["content"] = step.content

        # Include reasoning_content if present (will be handled by DeepseekModel preprocessing)
        if step.reasoning_content is not None:
            msg["reasoning_content"] = step.reasoning_content

        if step.tool_calls is not None:
            msg["tool_calls"] = step.tool_calls

        if step.tool_call_id is not None:
            msg["tool_call_id"] = step.tool_call_id

        if step.name is not None:
            msg["name"] = step.name

        return msg

    @staticmethod
    def from_llm_message(msg: dict, session_id: str, run_id: str, sequence: int) -> Step:
        """
        Create Step from LLM message format.

        Args:
            msg: Message in OpenAI format
            session_id: Session ID
            run_id: Run ID
            sequence: Sequence number

        Returns:
            Step: Step instance
        """
        return Step(
            session_id=session_id,
            run_id=run_id,
            sequence=sequence,
            role=MessageRole(msg["role"]),
            content=msg.get("content"),
            reasoning_content=msg.get("reasoning_content"),
            tool_calls=msg.get("tool_calls"),
            tool_call_id=msg.get("tool_call_id"),
            name=msg.get("name"),
        )

    @staticmethod
    def steps_to_messages(steps: list[Step]) -> list[dict[str, Any]]:
        """
        Convert list of Steps to list of LLM messages.

        Args:
            steps: List of Step instances

        Returns:
            list: List of messages in OpenAI format
        """
        return [StepAdapter.to_llm_message(step) for step in steps]
