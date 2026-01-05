import pytest

from agio.config import ConfigSystem
from agio.config.builder_registry import BuilderRegistry
from agio.config.container import ComponentMetadata
from agio.config.schema import AgentConfig, ComponentType, ModelConfig


class DummyBuilder:
    def __init__(self, name: str, record: list[str]) -> None:
        self.name = name
        self.record = record

    async def build(self, config, dependencies):
        self.record.append(config.name)
        return {"component": config.name, "deps": dependencies}

    async def cleanup(self, instance):
        return None


@pytest.mark.asyncio
async def test_agent_builds_missing_model_from_registry():
    """Agent build should auto-build its model dependency from registry before use."""
    config_sys = ConfigSystem()
    build_order: list[str] = []

    # Replace builder registry with dummy builders to avoid real provider requirements
    dummy_registry = BuilderRegistry()
    dummy_registry.register(ComponentType.MODEL, DummyBuilder("model", build_order))
    dummy_registry.register(ComponentType.AGENT, DummyBuilder("agent", build_order))
    config_sys.builder_registry = dummy_registry

    # Register model and agent configs
    model_cfg = ModelConfig(
        name="dummy_model",
        provider="test",
        model_name="dummy-model",
    )
    agent_cfg = AgentConfig(
        type="agent",
        name="needs_model",
        model="dummy_model",
        tools=[],
    )
    config_sys.registry.register(model_cfg)
    config_sys.registry.register(agent_cfg)

    container = config_sys._active_container

    # Build agent; should auto-build model first
    await config_sys._build_component(agent_cfg, container)

    # Assertions
    assert container.has("dummy_model")
    assert container.has("needs_model")
    assert build_order == ["dummy_model", "needs_model"]

    # Verify metadata recorded
    model_meta = container.get_metadata("dummy_model")
    agent_meta = container.get_metadata("needs_model")
    assert model_meta and model_meta.component_type == ComponentType.MODEL
    assert agent_meta and agent_meta.component_type == ComponentType.AGENT
    assert "dummy_model" in agent_meta.dependencies
