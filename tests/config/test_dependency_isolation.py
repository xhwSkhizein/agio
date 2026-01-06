
import pytest
from agio.config.dependency import DependencyResolver, DependencyNode
from agio.config.schema import ModelConfig, AgentConfig, ToolConfig, ComponentType, SessionStoreConfig
from agio.config.exceptions import ConfigError

def test_dependency_resolution_with_name_reuse():
    """
    Test that DependencyResolver correctly handles name reuse across different types.
    """
    resolver = DependencyResolver()
    
    # Components with same name 'db'
    session_db = SessionStoreConfig(
        name="db",
        backend={"type": "inmemory"}
    )
    
    # Tool 'db' depends on session store 'db'
    tool_db = ToolConfig(
        name="db",
        tool_name="bash",
        dependencies={"store": "db"}
    )
    
    # Agent 'my_agent' depends on tool 'db'
    agent = AgentConfig(
        name="my_agent",
        model="gpt4",
        tools=["db"]
    )
    
    model = ModelConfig(
        name="gpt4",
        provider="openai",
        model_name="gpt-4",
        api_key="key"
    )
    
    configs = [session_db, tool_db, agent, model]
    available_names = {"db", "my_agent", "gpt4"}
    
    # topological_sort should not fail with circular dep error 
    # even though 'db' depends on 'db' (Tool depends on SessionStore)
    sorted_configs = resolver.topological_sort(configs)
    
    assert len(sorted_configs) == 4
    
    # Verify order: 
    # 1. session_db must be before tool_db
    # 2. tool_db and model must be before agent
    
    names = [c.name for c in sorted_configs]
    types = [c.type for c in sorted_configs]
    
    session_idx = -1
    tool_idx = -1
    model_idx = -1
    agent_idx = -1
    
    for i, (n, t) in enumerate(zip(names, types)):
        if n == "db" and t == "session_store": session_idx = i
        if n == "db" and t == "tool": tool_idx = i
        if n == "gpt4": model_idx = i
        if n == "my_agent": agent_idx = i
        
    assert session_idx < tool_idx
    assert tool_idx < agent_idx
    assert model_idx < agent_idx

def test_real_circular_dependency():
    """
    Ensure it still detects real circular dependencies.
    """
    resolver = DependencyResolver()
    
    # Agent A -> Tool B -> Agent A (agent_tool)
    agent_a = AgentConfig(
        name="A",
        model="m",
        tools=["B"]
    )
    
    tool_b = ToolConfig(
        name="B",
        tool_name="agent_tool",
        dependencies={"agent": "A"}
    )
    
    model = ModelConfig(name="m", provider="openai", model_name="gpt4", api_key="k")
    
    configs = [agent_a, tool_b, model]
    
    with pytest.raises(ConfigError) as excinfo:
        resolver.topological_sort(configs)
    
    assert "Circular dependency" in str(excinfo.value)

def test_cross_type_name_collision_no_dep():
    """
    Test that unrelated components with same name don't create fake dependencies.
    """
    resolver = DependencyResolver()
    
    # Model 'X' and SessionStore 'X'
    model_x = ModelConfig(name="X", provider="openai", model_name="gpt4", api_key="k")
    store_x = SessionStoreConfig(name="X", backend={"type": "inmemory"})
    
    # Agent 'Y' depends on Model 'X'
    agent_y = AgentConfig(name="Y", model="X", tools=[])
    
    configs = [model_x, store_x, agent_y]
    
    sorted_configs = resolver.topological_sort(configs)
    assert len(sorted_configs) == 3
    
    # Agent Y must be after Model X
    model_idx = -1
    agent_idx = -1
    for i, c in enumerate(sorted_configs):
        if c.name == "X" and c.type == "model": model_idx = i
        if c.name == "Y": agent_idx = i
        
    assert model_idx < agent_idx
