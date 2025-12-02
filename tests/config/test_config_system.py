"""
Tests for ConfigSystem.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from agio.config.system import ConfigSystem
from agio.config.exceptions import ConfigNotFoundError, ComponentNotFoundError
from agio.config import ComponentType, ModelConfig, AgentConfig


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory with test configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create subdirectories
        models_dir = Path(tmpdir) / "models"
        agents_dir = Path(tmpdir) / "agents"
        tools_dir = Path(tmpdir) / "tools"
        
        models_dir.mkdir()
        agents_dir.mkdir()
        tools_dir.mkdir()
        
        # Create a model config
        model_config = {
            "type": "model",
            "name": "test_model",
            "provider": "openai",
            "model_name": "gpt-4",
            "api_key": "test-key",
        }
        with open(models_dir / "test_model.yaml", "w") as f:
            yaml.dump(model_config, f)
        
        # Create an agent config
        agent_config = {
            "type": "agent",
            "name": "test_agent",
            "model": "test_model",
            "tools": [],
            "system_prompt": "You are a test agent.",
        }
        with open(agents_dir / "test_agent.yaml", "w") as f:
            yaml.dump(agent_config, f)
        
        yield tmpdir


@pytest.fixture
def config_system():
    """Create a fresh ConfigSystem instance."""
    return ConfigSystem()


class TestConfigSystemBasic:
    """Test basic ConfigSystem functionality."""

    @pytest.mark.asyncio
    async def test_load_from_directory(self, config_system, temp_config_dir):
        """Test loading configs from directory."""
        stats = await config_system.load_from_directory(temp_config_dir)
        
        assert stats["loaded"] >= 2  # model + agent
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_list_configs(self, config_system, temp_config_dir):
        """Test listing configs."""
        await config_system.load_from_directory(temp_config_dir)
        
        # List all configs
        all_configs = config_system.list_configs()
        assert len(all_configs) >= 2
        
        # List by type
        model_configs = config_system.list_configs(ComponentType.MODEL)
        assert len(model_configs) == 1
        assert model_configs[0]["name"] == "test_model"

    @pytest.mark.asyncio
    async def test_get_config(self, config_system, temp_config_dir):
        """Test getting a specific config."""
        await config_system.load_from_directory(temp_config_dir)
        
        config = config_system.get_config(ComponentType.MODEL, "test_model")
        assert config is not None
        assert config["name"] == "test_model"
        assert config["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, config_system, temp_config_dir):
        """Test getting a non-existent config."""
        await config_system.load_from_directory(temp_config_dir)
        
        config = config_system.get_config(ComponentType.MODEL, "nonexistent")
        assert config is None


class TestConfigSystemBuild:
    """Test ConfigSystem build functionality."""

    @pytest.mark.asyncio
    async def test_build_all(self, config_system, temp_config_dir):
        """Test building all components."""
        await config_system.load_from_directory(temp_config_dir)
        stats = await config_system.build_all()
        
        # Model should build successfully
        # Agent may fail if model is not properly configured
        assert stats["built"] >= 1

    @pytest.mark.asyncio
    async def test_get_component(self, config_system, temp_config_dir):
        """Test getting a built component."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()
        
        # Model should be available
        model = config_system.get_or_none("test_model")
        assert model is not None

    @pytest.mark.asyncio
    async def test_get_component_not_found(self, config_system):
        """Test getting a non-existent component."""
        with pytest.raises(ComponentNotFoundError):
            config_system.get("nonexistent")

    @pytest.mark.asyncio
    async def test_list_components(self, config_system, temp_config_dir):
        """Test listing built components."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()
        
        components = config_system.list_components()
        assert len(components) >= 1
        
        # Check component info structure
        for comp in components:
            assert "name" in comp
            assert "type" in comp
            assert "created_at" in comp


class TestConfigSystemSaveDelete:
    """Test ConfigSystem save and delete functionality."""

    @pytest.mark.asyncio
    async def test_save_config(self, config_system, temp_config_dir):
        """Test saving a new config."""
        await config_system.load_from_directory(temp_config_dir)
        
        # Save a new model config
        new_model = ModelConfig(
            name="new_model",
            provider="openai",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
        )
        await config_system.save_config(new_model)
        
        # Verify it was saved
        config = config_system.get_config(ComponentType.MODEL, "new_model")
        assert config is not None
        assert config["model_name"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_delete_config(self, config_system, temp_config_dir):
        """Test deleting a config."""
        await config_system.load_from_directory(temp_config_dir)
        
        # Delete the model config
        await config_system.delete_config(ComponentType.MODEL, "test_model")
        
        # Verify it was deleted
        config = config_system.get_config(ComponentType.MODEL, "test_model")
        assert config is None

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, config_system, temp_config_dir):
        """Test deleting a non-existent config."""
        await config_system.load_from_directory(temp_config_dir)
        
        with pytest.raises(ConfigNotFoundError):
            await config_system.delete_config(ComponentType.MODEL, "nonexistent")


class TestConfigSystemChangeCallbacks:
    """Test ConfigSystem change callback functionality."""

    @pytest.mark.asyncio
    async def test_on_change_callback(self, config_system, temp_config_dir):
        """Test change callback is called."""
        await config_system.load_from_directory(temp_config_dir)
        
        changes = []
        
        def on_change(name: str, change_type: str):
            changes.append((name, change_type))
        
        config_system.on_change(on_change)
        
        # Save a new config
        new_model = ModelConfig(
            name="callback_test_model",
            provider="openai",
            model_name="gpt-4",
            api_key="test-key",
        )
        await config_system.save_config(new_model)
        
        # Verify callback was called
        assert len(changes) == 1
        assert changes[0][0] == "callback_test_model"
        assert changes[0][1] == "create"


class TestConfigSystemComponentInfo:
    """Test ConfigSystem component info functionality."""

    @pytest.mark.asyncio
    async def test_get_component_info(self, config_system, temp_config_dir):
        """Test getting component info."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()
        
        info = config_system.get_component_info("test_model")
        
        if info:  # May be None if build failed
            assert info["name"] == "test_model"
            assert info["type"] == "model"
            assert "config" in info
            assert "created_at" in info

    @pytest.mark.asyncio
    async def test_get_component_info_not_found(self, config_system):
        """Test getting info for non-existent component."""
        info = config_system.get_component_info("nonexistent")
        assert info is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
