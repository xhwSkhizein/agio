"""
Tests for ConfigSystem.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
import yaml

from agio.config.system import ConfigSystem
from agio.config.exceptions import ConfigNotFoundError, ComponentNotFoundError
from agio.config import ComponentType, ModelConfig


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


@pytest.fixture
def nested_config_dir():
    """Create a temporary config directory with nested folder structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested directory structure
        production_dir = Path(tmpdir) / "production"
        dev_dir = Path(tmpdir) / "development"
        shared_dir = Path(tmpdir) / "shared"

        production_dir.mkdir()
        dev_dir.mkdir()
        shared_dir.mkdir()

        # Create nested subdirectories
        (production_dir / "models").mkdir()
        (production_dir / "agents").mkdir()
        (dev_dir / "models").mkdir()
        (shared_dir / "storages").mkdir()

        # Create configs in nested directories
        prod_model_config = {
            "type": "model",
            "name": "prod_model",
            "provider": "openai",
            "model_name": "gpt-4",
            "api_key": "prod-key",
        }
        with open(production_dir / "models" / "prod_model.yaml", "w") as f:
            yaml.dump(prod_model_config, f)

        dev_model_config = {
            "type": "model",
            "name": "dev_model",
            "provider": "openai",
            "model_name": "gpt-3.5-turbo",
            "api_key": "dev-key",
        }
        with open(dev_dir / "models" / "dev_model.yaml", "w") as f:
            yaml.dump(dev_model_config, f)

        storage_config = {
            "type": "session_store",
            "name": "shared_storage",
            "backend": {
                "type": "inmemory",
            },
            "enable_indexing": False,
            "batch_size": 100,
        }
        with open(shared_dir / "storages" / "shared_storage.yaml", "w") as f:
            yaml.dump(storage_config, f)

        # Create a config directly in root (no subdirectory)
        root_tool_config = {
            "type": "tool",
            "name": "root_tool",
            "tool_name": "bash",
        }
        with open(Path(tmpdir) / "root_tool.yaml", "w") as f:
            yaml.dump(root_tool_config, f)

        yield tmpdir


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
    async def test_use_context_release(self, config_system, temp_config_dir):
        """Ensure use() context acquires and releases component references."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()

        container = config_system._active_container  # noqa: SLF001 test access
        assert container.ref_count("test_model") == 0

        async with config_system.use("test_model") as model:
            assert model is not None
            assert container.ref_count("test_model") == 1

        # after context exit, ref count should drop to zero
        await container.wait_for_zero()
        assert container.ref_count("test_model") == 0

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


class TestConfigSystemReloadSafety:
    """Integration-like tests for reload swap, draining, and failure rollback."""

    @pytest.mark.asyncio
    async def test_reload_waits_for_inflight_refs_and_cleans_old(self, monkeypatch):
        """Ensure reload swaps after build, waits for refs, and cleans old container."""

        class TrackingBuilder:
            def __init__(self):
                self.build_count = 0
                self.cleanup_count = 0
                self.last_cleaned = None

            async def build(self, config, dependencies):
                self.build_count += 1
                return {"version": self.build_count}

            async def cleanup(self, instance):
                self.cleanup_count += 1
                self.last_cleaned = instance

        builder = TrackingBuilder()
        system = ConfigSystem()
        # Registry: single model
        model_cfg = ModelConfig(
            name="m1", provider="mock", model_name="mock-gpt", api_key="k"
        )
        system.registry.register(model_cfg)

        # monkeypatch builder registry
        orig_get = system.builder_registry.get

        def fake_get(component_type):
            if component_type == ComponentType.MODEL:
                return builder
            return orig_get(component_type)

        monkeypatch.setattr(system.builder_registry, "get", fake_get)

        # initial build
        stats = await system.build_all()
        assert stats["built"] == 1
        first_instance = system.get("m1")

        # hold reference during reload
        async with system.use("m1"):
            reload_stats = await system.build_all()
            assert reload_stats["built"] == 1
            # old instance still referenced
            assert system._draining_containers  # noqa: SLF001 test access
            assert builder.build_count == 2

        # ensure drain completes
        await system._drain_containers()  # noqa: SLF001 test access

        # old instance cleaned after ref released
        assert builder.cleanup_count >= 1
        assert builder.last_cleaned == first_instance

        # active instance is the new one
        new_instance = system.get("m1")
        assert new_instance != first_instance

    @pytest.mark.asyncio
    async def test_reload_failure_keeps_active_container(self, monkeypatch):
        """On build failure, active container should remain unchanged."""

        class FailingBuilder:
            async def build(self, config, dependencies):
                raise RuntimeError("boom")

            async def cleanup(self, instance):
                return None

        system = ConfigSystem()
        model_cfg = ModelConfig(
            name="m_fail", provider="mock", model_name="mock-gpt", api_key="k"
        )
        system.registry.register(model_cfg)

        # initial successful build with tracking builder
        class OkBuilder:
            def __init__(self):
                self.build_count = 0

            async def build(self, config, dependencies):
                self.build_count += 1
                return {"v": self.build_count}

            async def cleanup(self, instance):
                return None

        ok_builder = OkBuilder()
        orig_get = system.builder_registry.get

        def ok_get(component_type):
            if component_type == ComponentType.MODEL:
                return ok_builder
            return orig_get(component_type)

        monkeypatch.setattr(system.builder_registry, "get", ok_get)
        stats = await system.build_all()
        assert stats["built"] == 1
        active_before = system._active_container  # noqa: SLF001 test access
        instance_before = system.get("m_fail")

        # now force failure
        def failing_get(component_type):
            if component_type == ComponentType.MODEL:
                return FailingBuilder()
            return orig_get(component_type)

        monkeypatch.setattr(system.builder_registry, "get", failing_get)
        stats_fail = await system.build_all()
        assert stats_fail["failed"] >= 1

        # container and instance stay unchanged
        assert system._active_container is active_before  # noqa: SLF001
        assert system.get("m_fail") == instance_before


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


class TestConfigLoaderRefactor:
    """Test ConfigLoader refactored functionality."""

    @pytest.mark.asyncio
    async def test_load_recursive_scan(self, config_system, nested_config_dir):
        """Test recursive scanning of nested directories."""
        stats = await config_system.load_from_directory(nested_config_dir)

        # Should load configs from nested directories
        assert stats["loaded"] >= 4  # prod_model, dev_model, shared_storage, root_tool
        assert stats["failed"] == 0

        # Verify configs are loaded correctly
        prod_model = config_system.get_config(ComponentType.MODEL, "prod_model")
        assert prod_model is not None
        assert prod_model["model_name"] == "gpt-4"

        dev_model = config_system.get_config(ComponentType.MODEL, "dev_model")
        assert dev_model is not None
        assert dev_model["model_name"] == "gpt-3.5-turbo"

        storage = config_system.get_config(
            ComponentType.SESSION_STORE, "shared_storage"
        )
        assert storage is not None

        tool = config_system.get_config(ComponentType.TOOL, "root_tool")
        assert tool is not None

    @pytest.mark.asyncio
    async def test_type_identification_from_content(self, config_system):
        """Test type identification from config content, not folder structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create configs in arbitrary folder structure
            custom_dir = Path(tmpdir) / "custom" / "nested" / "path"
            custom_dir.mkdir(parents=True)

            # Model config in a non-standard folder
            model_config = {
                "type": "model",
                "name": "custom_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "test-key",
            }
            with open(custom_dir / "model.yaml", "w") as f:
                yaml.dump(model_config, f)

            # Agent config in same folder
            agent_config = {
                "type": "agent",
                "name": "custom_agent",
                "model": "custom_model",
                "tools": [],
            }
            with open(custom_dir / "agent.yaml", "w") as f:
                yaml.dump(agent_config, f)

            stats = await config_system.load_from_directory(tmpdir)

            # Should load both configs correctly based on type field
            assert stats["loaded"] == 2
            assert stats["failed"] == 0

            model = config_system.get_config(ComponentType.MODEL, "custom_model")
            assert model is not None

            agent = config_system.get_config(ComponentType.AGENT, "custom_agent")
            assert agent is not None

    @pytest.mark.asyncio
    async def test_duplicate_name_detection(self, config_system):
        """Test duplicate config name detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two configs with same type and name in different folders
            dir1 = Path(tmpdir) / "folder1"
            dir2 = Path(tmpdir) / "folder2"
            dir1.mkdir()
            dir2.mkdir()

            config1 = {
                "type": "model",
                "name": "duplicate_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "key1",
            }
            with open(dir1 / "model.yaml", "w") as f:
                yaml.dump(config1, f)

            config2 = {
                "type": "model",
                "name": "duplicate_model",
                "provider": "openai",
                "model_name": "gpt-3.5-turbo",
                "api_key": "key2",
            }
            with open(dir2 / "model.yaml", "w") as f:
                yaml.dump(config2, f)

            stats = await config_system.load_from_directory(tmpdir)

            # Both should be loaded, but second one overwrites first
            assert stats["loaded"] == 2  # Both files are loaded
            assert stats["failed"] == 0

            # The last loaded config should be the one stored
            final_config = config_system.get_config(
                ComponentType.MODEL, "duplicate_model"
            )
            assert final_config is not None
            # Note: Which one wins depends on file iteration order, but one should win

    @pytest.mark.asyncio
    async def test_flexible_folder_structure(self, config_system):
        """Test flexible folder structure organization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create completely custom folder structure
            team_a = Path(tmpdir) / "teams" / "team-a" / "configs"
            team_b = Path(tmpdir) / "teams" / "team-b" / "configs"
            team_a.mkdir(parents=True)
            team_b.mkdir(parents=True)

            # Team A configs
            team_a_model = {
                "type": "model",
                "name": "team_a_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "team-a-key",
            }
            with open(team_a / "model.yaml", "w") as f:
                yaml.dump(team_a_model, f)

            # Team B configs
            team_b_model = {
                "type": "model",
                "name": "team_b_model",
                "provider": "openai",
                "model_name": "gpt-3.5-turbo",
                "api_key": "team-b-key",
            }
            with open(team_b / "model.yaml", "w") as f:
                yaml.dump(team_b_model, f)

            # Shared config at root
            shared_tool = {
                "type": "tool",
                "name": "shared_tool",
                "tool_name": "bash",
            }
            with open(Path(tmpdir) / "shared_tool.yaml", "w") as f:
                yaml.dump(shared_tool, f)

            stats = await config_system.load_from_directory(tmpdir)

            # All configs should be loaded regardless of folder structure
            assert stats["loaded"] == 3
            assert stats["failed"] == 0

            # Verify all configs are accessible
            assert (
                config_system.get_config(ComponentType.MODEL, "team_a_model")
                is not None
            )
            assert (
                config_system.get_config(ComponentType.MODEL, "team_b_model")
                is not None
            )
            assert (
                config_system.get_config(ComponentType.TOOL, "shared_tool") is not None
            )

    @pytest.mark.asyncio
    async def test_missing_type_field(self, config_system):
        """Test handling of configs with missing type field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_config = {
                "name": "invalid_config",
                "provider": "openai",
                "model_name": "gpt-4",
            }
            with open(Path(tmpdir) / "invalid.yaml", "w") as f:
                yaml.dump(invalid_config, f)

            stats = await config_system.load_from_directory(tmpdir)

            # Should skip invalid config
            assert stats["loaded"] == 0
            assert stats["failed"] == 0  # Not counted as failed, just skipped

    @pytest.mark.asyncio
    async def test_unknown_type(self, config_system):
        """Test handling of configs with unknown type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            unknown_type_config = {
                "type": "unknown_type",
                "name": "unknown_config",
            }
            with open(Path(tmpdir) / "unknown.yaml", "w") as f:
                yaml.dump(unknown_type_config, f)

            stats = await config_system.load_from_directory(tmpdir)

            # Should skip unknown type config
            assert stats["loaded"] == 0
            assert stats["failed"] == 0  # Not counted as failed, just skipped

    @pytest.mark.asyncio
    async def test_disabled_config(self, config_system):
        """Test handling of disabled configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disabled_config = {
                "type": "model",
                "name": "disabled_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "test-key",
                "enabled": False,
            }
            with open(Path(tmpdir) / "disabled.yaml", "w") as f:
                yaml.dump(disabled_config, f)

            stats = await config_system.load_from_directory(tmpdir)

            # Disabled config should be skipped
            assert stats["loaded"] == 0
            assert stats["failed"] == 0

            # Config should not be registered
            assert (
                config_system.get_config(ComponentType.MODEL, "disabled_model") is None
            )


class TestConfigSystemDeepDependencies:
    """Test deep dependency resolution scenarios."""

    @pytest.mark.asyncio
    async def test_agent_tool_with_nested_dependencies(self, config_system):
        """Test agent_tool that uses tools with unbuilt dependencies (e.g., citation_store)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # 1. Create a citation_store (will be built last in topological order)
            citation_store_config = {
                "type": "citation_store",
                "name": "test_citation_store",
                "backend": {
                    "type": "inmemory",
                },
                "auto_cleanup": False,
            }
            with open(tmpdir / "citation_store.yaml", "w") as f:
                yaml.dump(citation_store_config, f)
            
            # 2. Create a tool that depends on citation_store
            tool_config = {
                "type": "tool",
                "name": "web_fetch_test",
                "tool_name": "bash",  # Use built-in tool as base
                "dependencies": {
                    "citation_source_store": "test_citation_store",
                },
            }
            with open(tmpdir / "web_fetch.yaml", "w") as f:
                yaml.dump(tool_config, f)
            
            # 3. Create a model for agents
            model_config = {
                "type": "model",
                "name": "test_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "test-key",
            }
            with open(tmpdir / "model.yaml", "w") as f:
                yaml.dump(model_config, f)
            
            # 4. Create collector agent that uses the tool
            collector_config = {
                "type": "agent",
                "name": "collector_test",
                "model": "test_model",
                "tools": ["web_fetch_test"],
                "system_prompt": "You are a collector.",
            }
            with open(tmpdir / "collector.yaml", "w") as f:
                yaml.dump(collector_config, f)
            
            # 5. Create master agent that uses collector as agent_tool
            master_config = {
                "type": "agent",
                "name": "master_test",
                "model": "test_model",
                "tools": [
                    {
                        "type": "agent_tool",
                        "agent": "collector_test",
                        "description": "Collector agent tool",
                    }
                ],
                "system_prompt": "You are a master.",
            }
            with open(tmpdir / "master.yaml", "w") as f:
                yaml.dump(master_config, f)
            
            # Load and build all
            await config_system.load_from_directory(tmpdir)
            stats = await config_system.build_all()
            
            # All components should build successfully
            assert stats["failed"] == 0
            assert stats["built"] >= 5  # citation_store, tool, model, collector, master
            
            # Verify all components are accessible
            assert config_system.get_or_none("test_citation_store") is not None
            assert config_system.get_or_none("web_fetch_test") is not None
            assert config_system.get_or_none("test_model") is not None
            assert config_system.get_or_none("collector_test") is not None
            assert config_system.get_or_none("master_test") is not None

    @pytest.mark.asyncio
    async def test_missing_dependency_in_agent_tool_chain(self, config_system):
        """Test error handling when a dependency in agent_tool chain is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # 1. Create a tool that depends on non-existent component
            tool_config = {
                "type": "tool",
                "name": "tool_with_missing_dep",
                "tool_name": "bash",
                "dependencies": {
                    "missing_store": "nonexistent_store",
                },
            }
            with open(tmpdir / "tool.yaml", "w") as f:
                yaml.dump(tool_config, f)
            
            # 2. Create a model
            model_config = {
                "type": "model",
                "name": "test_model",
                "provider": "openai",
                "model_name": "gpt-4",
                "api_key": "test-key",
            }
            with open(tmpdir / "model.yaml", "w") as f:
                yaml.dump(model_config, f)
            
            # 3. Create agent that uses the tool
            agent_config = {
                "type": "agent",
                "name": "agent_with_bad_tool",
                "model": "test_model",
                "tools": ["tool_with_missing_dep"],
            }
            with open(tmpdir / "agent.yaml", "w") as f:
                yaml.dump(agent_config, f)
            
            # Load configs
            await config_system.load_from_directory(tmpdir)
            
            # Build should fail for agent due to missing dependency
            stats = await config_system.build_all()
            assert stats["failed"] >= 1  # agent should fail

    @pytest.mark.asyncio
    async def test_tool_dependency_auto_build(self, config_system):
        """Test that tool dependencies are automatically built when needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create session_store
            session_store_config = {
                "type": "session_store",
                "name": "auto_session_store",
                "backend": {
                    "type": "inmemory",
                },
            }
            with open(tmpdir / "session_store.yaml", "w") as f:
                yaml.dump(session_store_config, f)
            
            # Create tool that depends on session_store
            tool_config = {
                "type": "tool",
                "name": "tool_auto_build",
                "tool_name": "bash",
                "dependencies": {
                    "store": "auto_session_store",
                },
            }
            with open(tmpdir / "tool.yaml", "w") as f:
                yaml.dump(tool_config, f)
            
            # Load configs
            await config_system.load_from_directory(tmpdir)
            
            # Build should succeed with auto-building of dependencies
            stats = await config_system.build_all()
            assert stats["failed"] == 0
            assert stats["built"] == 2  # session_store + tool
            
            # Both should be accessible
            assert config_system.get_or_none("auto_session_store") is not None
            assert config_system.get_or_none("tool_auto_build") is not None


class TestConfigSystemConcurrency:
    """Concurrency regression tests."""

    @pytest.mark.asyncio
    async def test_concurrent_save_and_delete(self, config_system, temp_config_dir):
        """Save and delete concurrently should not corrupt registry."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()

        new_model = ModelConfig(
            name="new_model_concurrent",
            provider="openai",
            model_name="gpt-4",
            api_key="test-key",
        )

        await asyncio.gather(
            config_system.save_config(new_model),
            config_system.delete_config(ComponentType.MODEL, "test_model"),
        )

        assert (
            config_system.get_config(ComponentType.MODEL, "new_model_concurrent")
            is not None
        )
        assert config_system.get_config(ComponentType.MODEL, "test_model") is None

    @pytest.mark.asyncio
    async def test_concurrent_rebuild_and_save(self, config_system, temp_config_dir):
        """Rebuild and save concurrently should serialize without races."""
        await config_system.load_from_directory(temp_config_dir)
        await config_system.build_all()

        updated_model = ModelConfig(
            name="test_model",
            provider="openai",
            model_name="gpt-4-extended",
            api_key="updated-key",
        )

        await asyncio.gather(
            config_system.rebuild("test_agent"),
            config_system.save_config(updated_model),
        )

        config = config_system.get_config(ComponentType.MODEL, "test_model")
        assert config is not None
        assert config["model_name"] == "gpt-4-extended"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
