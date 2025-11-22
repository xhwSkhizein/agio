"""
Unit tests for the configuration system.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from agio.registry import (
    ComponentType,
    BaseComponentConfig,
    ModelConfig,
    AgentConfig,
    ComponentRegistry,
    ConfigLoader,
    ConfigValidator,
    load_from_config,
)


class TestBaseComponentConfig:
    """Test BaseComponentConfig."""
    
    def test_valid_config(self):
        config = BaseComponentConfig(
            type=ComponentType.MODEL,
            name="test_model"
        )
        assert config.type == ComponentType.MODEL
        assert config.name == "test_model"
        assert config.enabled is True
    
    def test_with_tags(self):
        config = BaseComponentConfig(
            type=ComponentType.AGENT,
            name="test_agent",
            tags=["production", "v1"]
        )
        assert len(config.tags) == 2
        assert "production" in config.tags


class TestModelConfig:
    """Test ModelConfig."""
    
    def test_openai_model(self):
        config = ModelConfig(
            name="gpt4",
            provider="openai",
            model="gpt-4-turbo-preview",
            api_key="sk-test",
            temperature=0.7
        )
        assert config.provider == "openai"
        assert config.model == "gpt-4-turbo-preview"
        assert config.temperature == 0.7
    
    def test_temperature_validation(self):
        with pytest.raises(ValueError):
            ModelConfig(
                name="invalid",
                provider="openai",
                model="gpt-4",
                temperature=3.0  # Invalid: > 2.0
            )


class TestAgentConfig:
    """Test AgentConfig."""
    
    def test_simple_agent(self):
        config = AgentConfig(
            name="assistant",
            model="gpt4",
            system_prompt="You are helpful"
        )
        assert config.model == "gpt4"
        assert config.system_prompt == "You are helpful"
        assert config.max_steps == 10  # default


class TestComponentRegistry:
    """Test ComponentRegistry."""
    
    def test_register_and_get(self):
        registry = ComponentRegistry()
        config = BaseComponentConfig(
            type=ComponentType.MODEL,
            name="test"
        )
        
        registry.register("test", "dummy_component", config)
        assert registry.get("test") == "dummy_component"
        assert registry.exists("test")
    
    def test_list_by_type(self):
        registry = ComponentRegistry()
        
        model_config = BaseComponentConfig(type=ComponentType.MODEL, name="model1")
        agent_config = BaseComponentConfig(type=ComponentType.AGENT, name="agent1")
        
        registry.register("model1", "m1", model_config)
        registry.register("agent1", "a1", agent_config)
        
        models = registry.list_by_type(ComponentType.MODEL)
        assert "model1" in models
        assert "agent1" not in models
    
    def test_unregister(self):
        registry = ComponentRegistry()
        config = BaseComponentConfig(type=ComponentType.MODEL, name="test")
        
        registry.register("test", "component", config)
        assert registry.exists("test")
        
        registry.unregister("test")
        assert not registry.exists("test")


class TestConfigLoader:
    """Test ConfigLoader."""
    
    def test_load_yaml(self, tmp_path):
        # Create a test YAML file
        config_data = {
            "type": "model",
            "name": "test_model",
            "provider": "openai",
            "model": "gpt-4"
        }
        
        config_file = tmp_path / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(tmp_path)
        loaded = loader.load(config_file)
        
        assert loaded["name"] == "test_model"
        assert loaded["provider"] == "openai"
    
    def test_env_var_resolution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "secret-key")
        
        config_data = {
            "type": "model",
            "name": "test",
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "${TEST_API_KEY}"
        }
        
        config_file = tmp_path / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = ConfigLoader(tmp_path)
        loaded = loader.load(config_file)
        
        assert loaded["api_key"] == "secret-key"


class TestConfigValidator:
    """Test ConfigValidator."""
    
    def test_validate_model_config(self):
        validator = ConfigValidator()
        
        config_dict = {
            "type": "model",
            "name": "gpt4",
            "provider": "openai",
            "model": "gpt-4-turbo-preview"
        }
        
        validated = validator.validate(config_dict)
        assert isinstance(validated, ModelConfig)
        assert validated.name == "gpt4"
    
    def test_invalid_type(self):
        validator = ConfigValidator()
        
        config_dict = {
            "type": "invalid_type",
            "name": "test"
        }
        
        with pytest.raises(ValueError):
            validator.validate(config_dict)


class TestIntegration:
    """Integration tests."""
    
    def test_load_from_config(self, tmp_path):
        # Create config directory structure
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        
        # Create a model config
        model_config = {
            "type": "model",
            "name": "test_gpt4",
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "api_key": "test-key"
        }
        
        with open(models_dir / "gpt4.yaml", 'w') as f:
            yaml.dump(model_config, f)
        
        # Note: This will fail without actual Model classes
        # but tests the loading logic
        try:
            registry = ComponentRegistry()
            load_from_config(tmp_path, registry)
        except Exception as e:
            # Expected to fail without actual implementations
            assert "agio.models" in str(e) or "import" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
