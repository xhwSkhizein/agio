"""
Tests for SkillLoader.
"""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from agio.skills.exceptions import SkillNotFoundError
from agio.skills.loader import SkillLoader
from agio.skills.registry import SkillRegistry


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
description: A test skill.
---

# Test Skill

This is the body content.

Use {baseDir} to reference the skill directory.
"""
    )
    return skill_dir


@pytest_asyncio.fixture
async def registry_with_skill(temp_skill_dir, sample_skill):
    """Create registry with skill discovered."""
    registry = SkillRegistry()
    await registry.discover_skills([temp_skill_dir])
    return registry


@pytest.mark.asyncio
async def test_load_skill(registry_with_skill):
    """Test loading a skill."""
    loader = SkillLoader(registry_with_skill)
    content = await loader.load_skill("test-skill")

    assert content.metadata.name == "test-skill"
    assert "# Test Skill" in content.body
    assert "{baseDir}" not in content.body  # Should be resolved


@pytest.mark.asyncio
async def test_load_nonexistent_skill(registry_with_skill):
    """Test loading nonexistent skill."""
    loader = SkillLoader(registry_with_skill)

    with pytest.raises(SkillNotFoundError):
        await loader.load_skill("nonexistent-skill")


@pytest.mark.asyncio
async def test_resolve_base_dir(registry_with_skill, sample_skill):
    """Test {baseDir} variable resolution."""
    loader = SkillLoader(registry_with_skill)

    content = "Path: {baseDir}/scripts/init.py"
    resolved = loader.resolve_base_dir("test-skill", content)

    assert "{baseDir}" not in resolved
    # Use resolve() to normalize paths (handles Windows short names like RUNNER~1)
    expected_path = sample_skill.resolve()
    # Extract the base directory path from resolved string
    # Format: "Path: <path>/scripts/init.py"
    path_part = resolved.replace("Path: ", "").replace("/scripts/init.py", "")
    resolved_path = Path(path_part).resolve()
    assert resolved_path == expected_path


@pytest.mark.asyncio
async def test_load_reference(registry_with_skill, temp_skill_dir, sample_skill):
    """Test loading reference file."""
    ref_dir = sample_skill / "references"
    ref_dir.mkdir()
    ref_file = ref_dir / "REFERENCE.md"
    ref_file.write_text("# Reference\n\nReference content.")

    loader = SkillLoader(registry_with_skill)
    content = await loader.load_reference("test-skill", "REFERENCE.md")

    assert "# Reference" in content
    assert "Reference content" in content


@pytest.mark.asyncio
async def test_get_script_path(registry_with_skill, sample_skill):
    """Test getting script path."""
    scripts_dir = sample_skill / "scripts"
    scripts_dir.mkdir()
    script_file = scripts_dir / "init.py"
    script_file.write_text("print('hello')")

    loader = SkillLoader(registry_with_skill)
    path = await loader.get_script_path("test-skill", "init.py")

    assert path.exists()
    assert path.name == "init.py"


@pytest.mark.asyncio
async def test_get_asset_path(registry_with_skill, sample_skill):
    """Test getting asset path."""
    assets_dir = sample_skill / "assets"
    assets_dir.mkdir()
    asset_file = assets_dir / "template.html"
    asset_file.write_text("<html></html>")

    loader = SkillLoader(registry_with_skill)
    path = await loader.get_asset_path("test-skill", "template.html")

    assert path.exists()
    assert path.name == "template.html"
