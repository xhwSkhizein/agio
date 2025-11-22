"""
Test Phase 1 implementation - Configuration loading
"""

import asyncio
import os
from agio.registry import load_from_config


async def test_config_loading():
    """Test loading all configurations."""
    # Set mock env vars for testing
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-mock"
    os.environ["OPENAI_API_KEY"] = "sk-mock"
    os.environ["DEEPSEEK_API_KEY"] = "sk-mock"
    os.environ["TICKETING_API_URL"] = "http://mock"
    os.environ["TICKETING_API_KEY"] = "mock-key"
    os.environ["SMTP_SERVER"] = "smtp.mock"
    os.environ["SMTP_USERNAME"] = "mock-user"
    os.environ["SMTP_PASSWORD"] = "mock-pass"
    os.environ["REPO_PATH"] = "."
    
    print("=" * 60)
    print("Testing Phase 1 Implementation")
    print("=" * 60)
    
    # Load all configurations
    print("\n1. Loading configurations from ./configs...")
    registry = load_from_config("./configs")
    
    # Get all registered components
    print("   Registry loaded successfully")
    
    # Test Models
    print("\n2. Testing Models...")
    models = ["gpt-4o-mini", "deepseek", "claude"]
    for model_name in models:
        model = registry.get(model_name)
        if model:
            print(f"   ✓ {model_name}: {type(model).__name__}")
        else:
            print(f"   ✗ {model_name}: Not found")
    
    # Test Agents
    print("\n3. Testing Agents...")
    agents = ["customer_support", "code_assistant", "simple_assistant"]
    for agent_name in agents:
        agent = registry.get(agent_name)
        if agent:
            print(f"   ✓ {agent_name}: {type(agent).__name__}")
        else:
            print(f"   ✗ {agent_name}: Not found")
    
    # Test Memory
    print("\n4. Testing Memory...")
    memories = ["conversation_memory", "semantic_memory"]
    for memory_name in memories:
        memory = registry.get(memory_name)
        if memory:
            print(f"   ✓ {memory_name}: {type(memory).__name__}")
        else:
            print(f"   ✗ {memory_name}: Not found")
    
    # Test Knowledge
    print("\n5. Testing Knowledge...")
    knowledges = ["product_docs", "research_database"]
    for knowledge_name in knowledges:
        knowledge = registry.get(knowledge_name)
        if knowledge:
            print(f"   ✓ {knowledge_name}: {type(knowledge).__name__}")
        else:
            print(f"   ✗ {knowledge_name}: Not found")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_config_loading())
