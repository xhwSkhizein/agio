"""
Tests for SkillManager.
"""

import os
import tempfile
from pathlib import Path

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
description: A test skill for unit testing.
---

# Test Skill

Body content.
"""
    )
    return skill_dir


@pytest.mark.asyncio
async def test_initialize(temp_skill_dir, sample_skill):
    """Test manager initialization."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    assert len(manager._metadata_cache) == 1
    assert manager._metadata_cache[0].name == "test-skill"


@pytest.mark.asyncio
async def test_get_skill_tool(temp_skill_dir, sample_skill):
    """Test getting skill tool."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    tool = manager.get_skill_tool()
    assert tool is not None
    assert tool.get_name() == "Skill"


@pytest.mark.asyncio
async def test_render_skills_section(temp_skill_dir, sample_skill):
    """Test rendering skills section."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    section = manager.render_skills_section()
    assert "## Available Skills" in section
    assert "test-skill" in section
    assert "A test skill for unit testing" in section
    assert "How to use skills" in section


@pytest.mark.asyncio
async def test_render_skills_section_empty():
    """Test rendering skills section with no skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SkillManager(skill_dirs=[Path(tmpdir)])
        await manager.initialize()

        section = manager.render_skills_section()
        assert section == ""


@pytest.mark.asyncio
async def test_reload(temp_skill_dir, sample_skill):
    """Test skill reload."""
    manager = SkillManager(skill_dirs=[temp_skill_dir])
    await manager.initialize()

    assert len(manager._metadata_cache) == 1

    # Add a new skill
    skill_dir2 = temp_skill_dir / "test-skill-2"
    skill_dir2.mkdir()
    skill_md2 = skill_dir2 / "SKILL.md"
    skill_md2.write_text(
        """---
name: test-skill-2
description: Another test skill.
---

# Test Skill 2
"""
    )

    await manager.reload()

    assert len(manager._metadata_cache) == 2


@pytest.mark.asyncio
async def test_resolve_skill_dirs_env_var(temp_skill_dir, sample_skill):
    """Test resolving skill directories from environment variable."""
    env_dir = tempfile.mkdtemp()
    env_skill_dir = Path(env_dir) / "env-skill"
    env_skill_dir.mkdir()
    env_skill_md = env_skill_dir / "SKILL.md"
    env_skill_md.write_text(
        """---
name: env-skill
description: Skill from environment variable.
---

# Env Skill
"""
    )

    os.environ["AGIO_SKILLS_DIR"] = env_dir

    try:
        manager = SkillManager(skill_dirs=[temp_skill_dir])
        await manager.initialize()

        # Should discover skills from both configured dir and env var
        skill_names = [s.name for s in manager._metadata_cache]
        assert "test-skill" in skill_names
        assert "env-skill" in skill_names
    finally:
        os.environ.pop("AGIO_SKILLS_DIR", None)

