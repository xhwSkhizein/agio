"""
Tests for Agent API routes.
"""

import pytest
from fastapi.testclient import TestClient

from agio.api.app import app
from agio.config import ComponentType, ConfigSystem


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def config_system(tmp_path, monkeypatch):
    """Create a test ConfigSystem with temp directory."""
    from pathlib import Path
    
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    monkeypatch.setenv("AGIO_CONFIG_PATH", str(config_dir))
    
    # Create fresh ConfigSystem instance
    config_sys = ConfigSystem()
    config_sys.config_path = Path(config_dir)
    
    # Override the dependency
    from agio.api import deps
    def override_get_config_sys():
        return config_sys
    
    app.dependency_overrides[deps.get_config_sys] = override_get_config_sys
    
    yield config_sys
    
    # Clean up
    app.dependency_overrides.clear()


def test_list_agents_with_tool_configs(client, config_system):
    """Test listing agents with various tool configurations."""
    # Create test config directory
    config_dir = config_system.config_path / "agents"
    config_dir.mkdir(parents=True)
    
    # Agent with string tools (legacy format)
    agent1_config = """
type: agent
name: test_agent_1
model: gpt-4o
tools:
  - web_search
  - file_read
tags:
  - test
"""
    (config_dir / "test_agent_1.yaml").write_text(agent1_config)
    
    # Agent with dict tools (new format)
    agent2_config = """
type: agent
name: test_agent_2
model: gpt-4o
tools:
  - web_search
  - type: agent_tool
    agent: researcher
    description: Research expert
  - type: workflow_tool
    workflow: analysis_pipeline
    description: Analysis workflow
tags:
  - test
"""
    (config_dir / "test_agent_2.yaml").write_text(agent2_config)
    
    # Agent with mixed tools
    agent3_config = """
type: agent
name: test_agent_3
model: deepseek
tools:
  - file_read
  - type: agent_tool
    agent: code_assistant
    description: Coding expert
"""
    (config_dir / "test_agent_3.yaml").write_text(agent3_config)
    
    # Load configs
    import asyncio
    asyncio.run(config_system.load_from_directory(config_system.config_path))
    
    # Test list agents
    response = client.get("/agio/agents")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    
    # Verify agent 1 (string tools)
    agent1 = next(a for a in data["items"] if a["name"] == "test_agent_1")
    assert len(agent1["tools"]) == 2
    assert agent1["tools"][0]["type"] == "function"
    assert agent1["tools"][0]["name"] == "web_search"
    assert agent1["tools"][1]["type"] == "function"
    assert agent1["tools"][1]["name"] == "file_read"
    
    # Verify agent 2 (dict tools)
    agent2 = next(a for a in data["items"] if a["name"] == "test_agent_2")
    assert len(agent2["tools"]) == 3
    assert agent2["tools"][0]["type"] == "function"
    assert agent2["tools"][0]["name"] == "web_search"
    assert agent2["tools"][1]["type"] == "agent_tool"
    assert agent2["tools"][1]["agent"] == "researcher"
    assert agent2["tools"][1]["description"] == "Research expert"
    assert agent2["tools"][2]["type"] == "workflow_tool"
    assert agent2["tools"][2]["workflow"] == "analysis_pipeline"
    
    # Verify agent 3 (mixed tools)
    agent3 = next(a for a in data["items"] if a["name"] == "test_agent_3")
    assert len(agent3["tools"]) == 2
    assert agent3["tools"][0]["type"] == "function"
    assert agent3["tools"][0]["name"] == "file_read"
    assert agent3["tools"][1]["type"] == "agent_tool"
    assert agent3["tools"][1]["agent"] == "code_assistant"


def test_get_agent_with_tool_configs(client, config_system):
    """Test getting single agent with tool configurations."""
    # Create test config directory
    config_dir = config_system.config_path / "agents"
    config_dir.mkdir(parents=True)
    
    # Agent with complex tool config
    agent_config = """
type: agent
name: orchestra
model: gpt-4o
system_prompt: You are an orchestrator
tools:
  - web_search
  - type: agent_tool
    agent: researcher
    description: Research expert
  - type: agent_tool
    agent: code_assistant
    description: Coding expert
  - type: workflow_tool
    workflow: analysis_pipeline
    description: Complete analysis
memory: conversation_memory
knowledge: product_docs
tags:
  - orchestrator
  - multi-agent
"""
    (config_dir / "orchestra.yaml").write_text(agent_config)
    
    # Load configs
    import asyncio
    asyncio.run(config_system.load_from_directory(config_system.config_path))
    
    # Test get agent
    response = client.get("/agio/agents/orchestra")
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "orchestra"
    assert data["model"] == "gpt-4o"
    assert data["memory"] == "conversation_memory"
    assert data["knowledge"] == "product_docs"
    assert len(data["tools"]) == 4
    
    # Verify string tool
    assert data["tools"][0]["type"] == "function"
    assert data["tools"][0]["name"] == "web_search"
    
    # Verify agent tools
    assert data["tools"][1]["type"] == "agent_tool"
    assert data["tools"][1]["agent"] == "researcher"
    assert data["tools"][1]["description"] == "Research expert"
    
    assert data["tools"][2]["type"] == "agent_tool"
    assert data["tools"][2]["agent"] == "code_assistant"
    
    # Verify workflow tool
    assert data["tools"][3]["type"] == "workflow_tool"
    assert data["tools"][3]["workflow"] == "analysis_pipeline"


def test_get_agent_not_found(client):
    """Test getting non-existent agent."""
    response = client.get("/agio/agents/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_agents_empty(client, config_system):
    """Test listing agents when no agents exist."""
    # Create empty config directory
    config_dir = config_system.config_path / "agents"
    config_dir.mkdir(parents=True)
    
    import asyncio
    asyncio.run(config_system.load_from_directory(config_system.config_path))
    
    response = client.get("/agio/agents")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


def test_list_agents_pagination(client, config_system):
    """Test agent list pagination."""
    # Create test config directory
    config_dir = config_system.config_path / "agents"
    config_dir.mkdir(parents=True)
    
    # Create 5 test agents
    for i in range(5):
        agent_config = f"""
type: agent
name: test_agent_{i}
model: gpt-4o
tools:
  - web_search
  - file_read
"""
        (config_dir / f"test_agent_{i}.yaml").write_text(agent_config)
    
    import asyncio
    asyncio.run(config_system.load_from_directory(config_system.config_path))
    
    # Test pagination
    response = client.get("/agio/agents?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    
    # Test second page
    response = client.get("/agio/agents?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["offset"] == 2
