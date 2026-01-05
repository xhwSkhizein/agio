"""
Tests for SkillTool.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from agio.domain.events import ToolResult
from agio.runtime.protocol import ExecutionContext
from agio.skills.loader import SkillLoader
from agio.skills.registry import SkillRegistry
from agio.skills.tool import SkillTool


@pytest.fixture
def temp_skill_dir():
    """Create temporary skill directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def registry_with_skill(temp_skill_dir):
    """Create registry with skill discovered."""
    skill_dir = temp_skill_dir / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test-skill
description: A test skill.
---

# Test Skill

Body content.
"""
    )

    registry = SkillRegistry()
    await registry.discover_skills([temp_skill_dir])
    return registry


@pytest.fixture
def loader(registry_with_skill):
    """Create loader."""
    return SkillLoader(registry_with_skill)


@pytest.fixture
def skill_tool(registry_with_skill, loader):
    """Create skill tool."""
    return SkillTool(registry=registry_with_skill, loader=loader)


@pytest.fixture
def mock_context():
    """Create mock execution context."""
    context = MagicMock(spec=ExecutionContext)
    context.run_id = "test-run-id"
    context.session_id = "test-session-id"
    return context


def test_get_name(skill_tool):
    """Test tool name."""
    assert skill_tool.get_name() == "Skill"


def test_get_description(skill_tool):
    """Test tool description."""
    description = skill_tool.get_description()
    assert "activate" in description.lower()
    assert "skill" in description.lower()


def test_get_parameters(skill_tool):
    """Test tool parameters."""
    params = skill_tool.get_parameters()
    assert params["type"] == "object"
    assert "skill_name" in params["properties"]
    assert "skill_name" in params["required"]


def test_is_concurrency_safe(skill_tool):
    """Test concurrency safety."""
    assert skill_tool.is_concurrency_safe() is True


@pytest.mark.asyncio
async def test_execute_success(skill_tool, mock_context):
    """Test successful skill activation."""
    parameters = {
        "skill_name": "test-skill",
        "tool_call_id": "call_123",
    }

    result = await skill_tool.execute(parameters, mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is True
    assert result.tool_name == "Skill"
    assert "# Test Skill" in result.content
    assert result.content_for_user is not None
    assert "test-skill" in result.content_for_user.lower()


@pytest.mark.asyncio
async def test_execute_missing_skill_name(skill_tool, mock_context):
    """Test execution with missing skill_name."""
    parameters = {"tool_call_id": "call_123"}

    result = await skill_tool.execute(parameters, mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert "Missing required parameter" in result.error


@pytest.mark.asyncio
async def test_execute_nonexistent_skill(skill_tool, mock_context):
    """Test execution with nonexistent skill."""
    parameters = {
        "skill_name": "nonexistent-skill",
        "tool_call_id": "call_123",
    }

    result = await skill_tool.execute(parameters, mock_context)

    assert isinstance(result, ToolResult)
    assert result.is_success is False
    assert "not found" in result.error.lower()
