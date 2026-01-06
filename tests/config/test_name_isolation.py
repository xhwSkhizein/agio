
import pytest
import asyncio
from agio.config.system import ConfigSystem
from agio.config.schema import ModelConfig, AgentConfig, ComponentType
from agio.config.exceptions import ConfigError

@pytest.mark.asyncio
async def test_component_name_collision_different_types():
    """
    Test that components of different types with the same name now correctly coexist
    due to the implemented name isolation (type-scoped lookup).
    """
    system = ConfigSystem()
    
    # Register a model and an agent with the same name 'common_name'
    model_cfg = ModelConfig(
        name="common_name",
        provider="openai",
        model_name="gpt-4",
        api_key="test-key"
    )
    
    # Use a different name for the model the agent depends on
    agent_cfg = AgentConfig(
        name="common_name",
        model="other_model",
        tools=[],
        system_prompt="test"
    )
    
    other_model_cfg = ModelConfig(
        name="other_model",
        provider="openai",
        model_name="gpt-4",
        api_key="test-key"
    )
    
    system.registry.register(model_cfg)
    system.registry.register(other_model_cfg)
    system.registry.register(agent_cfg)
    
    # Build all
    stats = await system.build_all()
    
    assert stats["built"] == 3
    
    # Verify both can be retrieved using their respective types
    model_instance = system.container.get("common_name", ComponentType.MODEL)
    agent_instance = system.container.get("common_name", ComponentType.AGENT)
    
    from agio.agent.agent import Agent
    assert isinstance(agent_instance, Agent)
    assert not isinstance(model_instance, Agent)
    # The model instance should be a model object (e.g. OpenAIModel)
    assert hasattr(model_instance, 'model_name')
    assert model_instance.model_name == "gpt-4"
