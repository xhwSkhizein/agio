"""
Tool reference parsing utilities.

Provides unified handling of tool references in configurations.
"""

from typing import Any
from pydantic import BaseModel

from agio.config.schema import RunnableToolConfig, ToolReference


class ParsedToolReference(BaseModel):
    """Parsed tool reference with normalized structure."""
    
    # Tool type: "function", "agent_tool", "workflow_tool"
    type: str
    
    # For function tools: tool name
    name: str | None = None
    
    # For agent_tool: agent reference
    agent: str | None = None
    
    # For workflow_tool: workflow reference
    workflow: str | None = None
    
    # Optional description
    description: str | None = None
    
    # Original raw reference
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
        ParsedToolReference(type="function", name="web_search")
        
        >>> parse_tool_reference({"type": "agent_tool", "agent": "researcher"})
        ParsedToolReference(type="agent_tool", agent="researcher")
    """
    # Case 1: String reference (built-in or custom tool name)
    if isinstance(tool_ref, str):
        return ParsedToolReference(
            type="function",
            name=tool_ref,
            raw=tool_ref,
        )
    
    # Case 2: RunnableToolConfig object
    if isinstance(tool_ref, RunnableToolConfig):
        return ParsedToolReference(
            type=tool_ref.type,
            agent=tool_ref.agent,
            workflow=tool_ref.workflow,
            description=tool_ref.description,
            name=tool_ref.name,
            raw=tool_ref,
        )
    
    # Case 3: Dict (from YAML/JSON)
    if isinstance(tool_ref, dict):
        tool_type = tool_ref.get("type", "function")
        
        # agent_tool or workflow_tool
        if tool_type in ("agent_tool", "workflow_tool"):
            return ParsedToolReference(
                type=tool_type,
                agent=tool_ref.get("agent"),
                workflow=tool_ref.get("workflow"),
                description=tool_ref.get("description"),
                name=tool_ref.get("name"),
                raw=tool_ref,
            )
        
        # Fallback: treat as function tool with name
        return ParsedToolReference(
            type="function",
            name=tool_ref.get("name"),
            description=tool_ref.get("description"),
            raw=tool_ref,
        )
    
    # Unsupported type
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
