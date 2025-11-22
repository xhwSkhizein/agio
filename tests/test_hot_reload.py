"""
Unit tests for configuration hot reload functionality.
"""

import pytest
import tempfile
import time
from pathlib import Path
from agio.registry import (
    ConfigManager,
    ConfigEventBus,
    ConfigHistory,
    ConfigChangeEvent,
    get_registry,
    ConfigLoader,
    ComponentFactory,
    ConfigValidator,
    get_event_bus,
)


def test_config_event_bus():
    """Test configuration event bus."""
    bus = ConfigEventBus()
    events_received = []
    
    def listener(event: ConfigChangeEvent):
        events_received.append(event)
    
    # Subscribe
    bus.subscribe(listener)
    
    # Publish event
    event = ConfigChangeEvent(
        component_name="test",
        component_type="model",
        change_type="created",
        old_config=None,
        new_config=None
    )
    bus.publish(event)
    
    # Check event received
    assert len(events_received) == 1
    assert events_received[0].component_name == "test"
    
    # Unsubscribe
    bus.unsubscribe(listener)
    bus.publish(event)
    
    # Should not receive new event
    assert len(events_received) == 1


def test_config_history():
    """Test configuration history tracking."""
    history = ConfigHistory(max_history=5)
    
    # Add events
    for i in range(10):
        event = ConfigChangeEvent(
            component_name=f"component_{i}",
            component_type="model",
            change_type="created",
            old_config=None,
            new_config=None
        )
        history.add(event)
    
    # Should only keep last 5
    all_history = history.get_history(limit=100)
    assert len(all_history) == 5
    assert all_history[0].component_name == "component_5"
    
    # Filter by component name
    event = ConfigChangeEvent(
        component_name="specific",
        component_type="model",
        change_type="created",
        old_config=None,
        new_config=None
    )
    history.add(event)
    
    specific_history = history.get_history(component_name="specific")
    assert len(specific_history) == 1
    assert specific_history[0].component_name == "specific"


def test_config_manager_update():
    """Test configuration manager update functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        
        #  Create manager
        registry = get_registry()
        loader = ConfigLoader(config_dir)
        factory = ComponentFactory(registry)
        validator = ConfigValidator()
        history = ConfigHistory()
        event_bus = get_event_bus()
        
        manager = ConfigManager(
            config_dir=config_dir, 
            registry=registry,
            loader=loader,
            factory=factory,
            validator=validator,
            history=history,
            event_bus=event_bus,
            auto_reload=False
        )
        
        # Create test config file
        model_config = config_dir / "models"
        model_config.mkdir()
        
        config_file = model_config / "test_model.yaml"
        config_file.write_text("""
type: model
name: test_model
provider: openai
model: gpt-3.5-turbo
api_key: test-key
temperature: 0.7
""")
        
        # Load initial config
        success, message = manager.reload_from_file(config_file)
        assert success
        assert "test_model" in message
        
        # Check registry
        registry = manager.registry
        assert registry.get("test_model") is not None
        
        # Update config
        new_config = {
            "type": "model",
            "name": "test_model",
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
            "temperature": 0.5
        }
        
        success, message = manager.update_component("test_model", new_config)
        assert success
        assert "updated" in message
        
        # Check history
        history = manager.history.get_history("test_model")
        assert len(history) >= 1


def test_config_manager_rollback():
    """Test configuration rollback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)  # Define config_dir first
        
        # Create manager
        registry = get_registry()
        loader = ConfigLoader(config_dir)
        factory = ComponentFactory(registry)
        validator = ConfigValidator()
        history = ConfigHistory()
        event_bus = get_event_bus()
        
        manager = ConfigManager(
            config_dir=config_dir,
            registry=registry,
            loader=loader,
            factory=factory,
            validator=validator,
            history=history,
            event_bus=event_bus,
            auto_reload=False
        )
        
        # Create initial config
        config_v1 = {
            "type": "model",
            "name": "test",
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "api_key": "key1",
            "temperature": 0.7
        }
        manager.update_component("test", config_v1)
        
        # Update to v2
        config_v2 = {**config_v1, "temperature": 0.5}
        manager.update_component("test", config_v2)
        
        # Update to v3
        config_v3 = {**config_v1, "temperature": 0.3}
        manager.update_component("test", config_v3)
        
        # Rollback 1 step
        success, message = manager.rollback("test", steps=1)
        assert success
        
        # Check current config
        current_config = manager.registry.get_config("test")
        assert current_config.temperature == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
