import pytest

from agio.config import ConfigSystem
from agio.config.container import ComponentContainer, ComponentMetadata
from agio.config.schema import AgentConfig, ComponentType, ModelConfig
from agio.config.tool_reference import RunnableToolConfig


@pytest.mark.asyncio
async def test_agent_tool_builds_dependency_first():
    """agent_tool should auto-build referenced agent before wrapping it."""
    config_sys = ConfigSystem()
    # Use the system's active container to mirror real build flow
    container = config_sys._active_container

    # Pre-register a dummy model so agent builds can resolve it
    dummy_model = object()
    dummy_model_config = ModelConfig(
        name="dummy_model",
        provider="test",
        model_name="dummy-model",
    )
    container.register(
        "dummy_model",
        dummy_model,
        ComponentMetadata(
            component_type=ComponentType.MODEL,
            config=dummy_model_config,
            dependencies=[],
        ),
    )

    # Collector agent (dependency)
    collector_config = AgentConfig(
        type="agent",
        name="collector",
        model="dummy_model",
        tools=[],
    )
    config_sys.registry.register(collector_config)

    # Orchestrator agent that uses collector as agent_tool
    orchestrator_config = AgentConfig(
        type="agent",
        name="orchestrator",
        model="dummy_model",
        tools=[RunnableToolConfig(agent="collector", description="collect")],
    )
    config_sys.registry.register(orchestrator_config)

    # Build orchestrator; should auto-build collector first
    await config_sys._build_component(orchestrator_config, container)

    assert container.has("collector")
    assert container.has("orchestrator")
