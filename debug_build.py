
import asyncio
from agio.config.system import ConfigSystem
from agio.config.schema import ModelConfig, AgentConfig, ComponentType

async def debug():
    system = ConfigSystem()
    
    model_cfg = ModelConfig(
        name="common_name",
        provider="openai",
        model_name="gpt-4",
        api_key="test-key"
    )
    
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
    
    print(f"Registry count: {system.registry.count()}")
    for cfg in system.registry.list_all():
        print(f"  - {cfg.type}/{cfg.name}")
        
    stats = await system.build_all()
    print(f"Build stats: {stats}")
    
    print(f"Container instances: {system.container.count()}")
    for key in system.container.list_components():
        print(f"  - {key}")

if __name__ == "__main__":
    asyncio.run(debug())
