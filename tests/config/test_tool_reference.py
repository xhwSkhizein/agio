"""
Tests for tool reference parsing.
"""

import pytest

from agio.config.tool_reference import parse_tool_reference, parse_tool_references, ParsedToolReference
from agio.config.schema import RunnableToolConfig


def test_parse_string_tool_reference():
    """Test parsing string tool reference (built-in tool)."""
    result = parse_tool_reference("web_search")
    
    assert result.type == "function"
    assert result.name == "web_search"
    assert result.agent is None
    assert result.workflow is None
    assert result.description is None


def test_parse_agent_tool_dict():
    """Test parsing agent_tool dict reference."""
    tool_ref = {
        "type": "agent_tool",
        "agent": "researcher",
        "description": "Expert at research",
        "name": "call_researcher",
    }
    
    result = parse_tool_reference(tool_ref)
    
    assert result.type == "agent_tool"
    assert result.agent == "researcher"
    assert result.description == "Expert at research"
    assert result.name == "call_researcher"
    assert result.workflow is None


def test_parse_workflow_tool_dict():
    """Test parsing workflow_tool dict reference."""
    tool_ref = {
        "type": "workflow_tool",
        "workflow": "analysis_pipeline",
        "description": "Complete analysis workflow",
    }
    
    result = parse_tool_reference(tool_ref)
    
    assert result.type == "workflow_tool"
    assert result.workflow == "analysis_pipeline"
    assert result.description == "Complete analysis workflow"
    assert result.agent is None


def test_parse_runnable_tool_config():
    """Test parsing RunnableToolConfig object."""
    config = RunnableToolConfig(
        type="agent_tool",
        agent="code_assistant",
        description="Coding expert",
    )
    
    result = parse_tool_reference(config)
    
    assert result.type == "agent_tool"
    assert result.agent == "code_assistant"
    assert result.description == "Coding expert"


def test_parse_dict_without_type():
    """Test parsing dict without type field (fallback to function)."""
    tool_ref = {
        "name": "custom_tool",
        "description": "Custom tool",
    }
    
    result = parse_tool_reference(tool_ref)
    
    assert result.type == "function"
    assert result.name == "custom_tool"
    assert result.description == "Custom tool"


def test_parse_tool_references_list():
    """Test parsing a list of mixed tool references."""
    tool_refs = [
        "web_search",
        {"type": "agent_tool", "agent": "researcher"},
        {"type": "workflow_tool", "workflow": "pipeline"},
        "file_read",
    ]
    
    results = parse_tool_references(tool_refs)
    
    assert len(results) == 4
    
    # String tool
    assert results[0].type == "function"
    assert results[0].name == "web_search"
    
    # Agent tool
    assert results[1].type == "agent_tool"
    assert results[1].agent == "researcher"
    
    # Workflow tool
    assert results[2].type == "workflow_tool"
    assert results[2].workflow == "pipeline"
    
    # String tool
    assert results[3].type == "function"
    assert results[3].name == "file_read"


def test_parse_invalid_type():
    """Test parsing invalid tool reference type."""
    with pytest.raises(ValueError, match="Unsupported tool reference type"):
        parse_tool_reference(123)


def test_parsed_tool_reference_raw_field():
    """Test that raw field preserves original reference."""
    tool_ref = {"type": "agent_tool", "agent": "test"}
    result = parse_tool_reference(tool_ref)
    
    assert result.raw == tool_ref
    assert result.raw is tool_ref  # Same object


def test_parse_empty_list():
    """Test parsing empty tool references list."""
    results = parse_tool_references([])
    assert results == []


def test_parse_agent_tool_minimal():
    """Test parsing agent_tool with minimal fields."""
    tool_ref = {
        "type": "agent_tool",
        "agent": "minimal_agent",
    }
    
    result = parse_tool_reference(tool_ref)
    
    assert result.type == "agent_tool"
    assert result.agent == "minimal_agent"
    assert result.description is None
    assert result.name is None


def test_parse_workflow_tool_minimal():
    """Test parsing workflow_tool with minimal fields."""
    tool_ref = {
        "type": "workflow_tool",
        "workflow": "minimal_workflow",
    }
    
    result = parse_tool_reference(tool_ref)
    
    assert result.type == "workflow_tool"
    assert result.workflow == "minimal_workflow"
    assert result.description is None
    assert result.name is None
