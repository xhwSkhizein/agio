"""
Tests for SkillRegistry.
"""

import tempfile
from pathlib import Path

import pytest

from agio.skills.registry import SkillRegistry


@pytest.fixture
def temp_skill_dir():
    """Create temporary skill directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_skill_md(temp_skill_dir):
    """Create a sample SKILL.md file."""
    skill_dir = temp_skill_dir / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test-skill
description: A test skill for unit testing.
license: MIT
metadata:
  author: test
  version: "1.0"
---

# Test Skill

This is a test skill.
"""
    )
    return skill_md


@pytest.mark.asyncio
async def test_discover_skills(temp_skill_dir, sample_skill_md):
    """Test skill discovery."""
    registry = SkillRegistry()
    skills = await registry.discover_skills([temp_skill_dir])

    assert len(skills) == 1
    assert skills[0].name == "test-skill"
    assert skills[0].description == "A test skill for unit testing."


@pytest.mark.asyncio
async def test_get_metadata(temp_skill_dir, sample_skill_md):
    """Test getting metadata by name."""
    registry = SkillRegistry()
    await registry.discover_skills([temp_skill_dir])

    metadata = registry.get_metadata("test-skill")
    assert metadata is not None
    assert metadata.name == "test-skill"

    metadata = registry.get_metadata("nonexistent")
    assert metadata is None


@pytest.mark.asyncio
async def test_list_available(temp_skill_dir, sample_skill_md):
    """Test listing available skills."""
    registry = SkillRegistry()
    await registry.discover_skills([temp_skill_dir])

    available = registry.list_available()
    assert "test-skill" in available


@pytest.mark.asyncio
async def test_invalid_skill_name(temp_skill_dir):
    """Test invalid skill name validation."""
    skill_dir = temp_skill_dir / "invalid-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: Invalid-Skill
description: Invalid name with uppercase.
---

# Invalid Skill
"""
    )

    registry = SkillRegistry()
    skills = await registry.discover_skills([temp_skill_dir])

    # Invalid skill should be skipped with warning
    assert len(skills) == 0


@pytest.mark.asyncio
async def test_missing_required_fields(temp_skill_dir):
    """Test missing required fields."""
    skill_dir = temp_skill_dir / "incomplete-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: incomplete-skill
---

# Incomplete Skill
"""
    )

    registry = SkillRegistry()
    skills = await registry.discover_skills([temp_skill_dir])

    # Skill with missing description should be skipped
    assert len(skills) == 0


@pytest.mark.asyncio
async def test_reload(temp_skill_dir, sample_skill_md):
    """Test skill reload."""
    registry = SkillRegistry()
    await registry.discover_skills([temp_skill_dir])

    assert len(registry.list_available()) == 1

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

    await registry.reload()

    assert len(registry.list_available()) == 2
    assert "test-skill" in registry.list_available()
    assert "test-skill-2" in registry.list_available()
