"""
Integration tests for Agent Skills system.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agio.skills.manager import SkillManager


@pytest.fixture
def temp_skill_dir():
    """Create temporary skill directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_skill(temp_skill_dir):
    """Create a sample skill."""
    skill_dir = temp_skill_dir / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test-skill
description: A test skill for integration testing.
---

# Test Skill

This is a test skill for integration testing.

## Steps

1. Understand the task
2. Execute the steps
3. Verify results
"""
    )
    return skill_dir


@pytest.mark.asyncio
async def test_skill_discovery_on_startup(temp_skill_dir, sample_skill):
    """Test that skills are discovered on manager initialization."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    assert len(manager._metadata_cache) == 1
    assert manager._metadata_cache[0].name == "test-skill"


@pytest.mark.asyncio
async def test_skill_tool_integration(temp_skill_dir, sample_skill):
    """Test that skill tool is properly integrated."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    tool = manager.get_skill_tool()
    assert tool is not None

    # Test tool can be called
    mock_context = MagicMock()
    mock_context.run_id = "test-run"
    mock_context.session_id = "test-session"

    result = await tool.execute(
        {"skill_name": "test-skill", "tool_call_id": "call_123"},
        mock_context,
    )

    assert result.is_success is True
    assert "# Test Skill" in result.content
    assert result.content_for_user is not None


@pytest.mark.asyncio
async def test_skill_activation_context_injection(temp_skill_dir, sample_skill):
    """Test that skill content is properly injected into context."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    tool = manager.get_skill_tool()
    mock_context = MagicMock()
    mock_context.run_id = "test-run"
    mock_context.session_id = "test-session"

    result = await tool.execute(
        {"skill_name": "test-skill", "tool_call_id": "call_123"},
        mock_context,
    )

    # Content should contain full skill body
    assert "This is a test skill" in result.content
    assert "## Steps" in result.content

    # Content for user should be concise
    assert result.content_for_user is not None
    assert len(result.content_for_user) < len(result.content)


@pytest.mark.asyncio
async def test_skills_section_in_prompt(temp_skill_dir, sample_skill):
    """Test that skills section is generated for system prompt."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    section = manager.render_skills_section()

    assert "## Available Skills" in section
    assert "test-skill" in section
    assert "A test skill for integration testing" in section
    assert "How to use skills" in section

