"""
Tool reference parsing utilities.

Provides unified handling of tool references in configurations.
"""

from typing import Any

from pydantic import BaseModel

from agio.config.schema import RunnableToolConfig, ToolReference


class ParsedToolReference(BaseModel):
    """Standardized tool reference structure."""

    tool_type: str  # "regular_tool" or "agent_tool"
    tool_name: str | None = None  # For regular_tool
    agent_name: str | None = None  # For agent_tool
    description: str | None = None
    custom_name: str | None = None
    raw: Any = None


def parse_tool_reference(tool_ref: ToolReference) -> ParsedToolReference:
    """
    Parse a tool reference into a normalized structure.

    Args:
        tool_ref: Tool reference (string, RunnableToolConfig, or dict)

    Returns:
        ParsedToolReference with normalized fields

    Examples:
        >>> parse_tool_reference("web_search")
        ParsedToolReference(tool_type="regular_tool", tool_name="web_search")

        >>> parse_tool_reference({"type": "agent_tool", "agent": "researcher"})
        ParsedToolReference(tool_type="agent_tool", agent_name="researcher")
    """
    # Case 1: String reference (built-in or custom tool name)
    if isinstance(tool_ref, str):
        return ParsedToolReference(
            tool_type="regular_tool",
            tool_name=tool_ref,
            raw=tool_ref,
        )

    # Case 2: RunnableToolConfig object (agent_tool only)
    if isinstance(tool_ref, RunnableToolConfig):
        return ParsedToolReference(
            tool_type="agent_tool",
            agent_name=tool_ref.agent,
            description=tool_ref.description,
            custom_name=tool_ref.name,
            raw=tool_ref,
        )

    # Case 3: Dict (from YAML/JSON)
    if isinstance(tool_ref, dict):
        tool_type = tool_ref.get("type", "regular_tool")

        if tool_type == "agent_tool":
            return ParsedToolReference(
                tool_type="agent_tool",
                agent_name=tool_ref.get("agent"),
                description=tool_ref.get("description"),
                custom_name=tool_ref.get("name"),
                raw=tool_ref,
            )

        # Fallback: treat as regular tool
        return ParsedToolReference(
            tool_type="regular_tool",
            tool_name=tool_ref.get("name") or tool_ref.get("tool_name"),
            description=tool_ref.get("description"),
            raw=tool_ref,
        )

    raise ValueError(f"Unsupported tool reference type: {type(tool_ref)}")


def parse_tool_references(tool_refs: list[ToolReference]) -> list[ParsedToolReference]:
    """
    Parse a list of tool references.

    Args:
        tool_refs: List of tool references

    Returns:
        List of parsed tool references
    """
    return [parse_tool_reference(ref) for ref in tool_refs]


__all__ = [
    "ParsedToolReference",
    "parse_tool_reference",
    "parse_tool_references",
]
