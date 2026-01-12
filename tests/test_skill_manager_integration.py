"""
Test SkillManager integration with Agent.

Verify that SkillManager is correctly passed to Agent and
System Prompt includes Skills information.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agio.agent import Agent
# from agio.config.builders import AgentBuilder
from agio.config.schema import AgentConfig
from agio.llm import Model, StreamChunk


class MockModel(Model):
    """Mock model for testing."""

    id: str = "test-model"
    name: str = "test-model"

    async def arun_stream(self, messages, tools=None):
        yield StreamChunk(content="test response")
        yield StreamChunk(usage={"total_tokens": 10})


# @pytest.mark.asyncio
# async def test_agent_builder_creates_skill_manager_when_enabled():
#     """Test that AgentBuilder creates and passes SkillManager when enable_skills=True."""
#     
#     config = AgentConfig(
#         type="agent",
#         name="test_agent",
#         model="test_model",
#         enable_skills=True,
#         skill_dirs=["/tmp/test_skills"],
#     )
#     
#     dependencies = {
#         "model": MockModel(),
#         "tools": [],
#     }
#     
#     builder = AgentBuilder()
#     
#     # Mock SkillManager to avoid actual file system operations
#     with patch("agio.skills.manager.SkillManager") as MockSkillManager:
#         mock_skill_manager = MagicMock()
#         mock_skill_manager.initialize = AsyncMock()
#         mock_skill_manager.get_skill_tool = MagicMock(return_value=MagicMock())
#         MockSkillManager.return_value = mock_skill_manager
#         
#         agent = await builder.build(config, dependencies)
#         
#         # Verify SkillManager was created
#         assert MockSkillManager.called
#         
#         # Verify SkillManager was initialized
#         assert mock_skill_manager.initialize.called
#         
#         # Verify SkillManager was passed to Agent
#         assert agent.skill_manager is not None
#         assert agent.skill_manager == mock_skill_manager


# @pytest.mark.asyncio
# async def test_agent_builder_skips_skill_manager_when_disabled():
#     """Test that AgentBuilder skips SkillManager when enable_skills=False."""
#     
#     config = AgentConfig(
#         type="agent",
#         name="test_agent",
#         model="test_model",
#         enable_skills=False,
#     )
#     
#     dependencies = {
#         "model": MockModel(),
#         "tools": [],
#     }
#     
#     builder = AgentBuilder()
#     agent = await builder.build(config, dependencies)
#     
#     # Verify SkillManager was NOT passed to Agent
#     assert agent.skill_manager is None


@pytest.mark.asyncio
async def test_agent_renders_skills_section_in_system_prompt():
    """Test that Agent includes Skills section in System Prompt when SkillManager is present."""
    
    from agio.runtime.context import ExecutionContext
    from agio.runtime.wire import Wire
    
    # Create mock SkillManager
    mock_skill_manager = MagicMock()
    mock_skill_manager.render_skills_section = MagicMock(
        return_value="## Available Skills\n- skill1: Description 1\n- skill2: Description 2"
    )
    
    agent = Agent(
        model=MockModel(),
        tools=[],
        system_prompt="You are a helpful assistant.",
        skill_manager=mock_skill_manager,
    )
    
    wire = Wire()
    context = ExecutionContext(
        run_id="test-run",
        session_id="test-session",
        wire=wire,
    )
    
    # Mock the executor to capture the messages
    with patch("agio.agent.agent.AgentExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            response="test",
            metrics=None,
            termination_reason=None,
        ))
        MockExecutor.return_value = mock_executor
        
        await agent.run("test input", context=context)
        
        # Verify render_skills_section was called
        assert mock_skill_manager.render_skills_section.called
        
        # Verify executor.execute was called with messages
        assert mock_executor.execute.called
        call_kwargs = mock_executor.execute.call_args[1]
        messages = call_kwargs["messages"]
        
        # Find system message
        system_message = next((m for m in messages if m["role"] == "system"), None)
        assert system_message is not None
        
        # Verify system prompt includes Skills section
        assert "Available Skills" in system_message["content"]
        assert "skill1" in system_message["content"]
        assert "skill2" in system_message["content"]
    
    await wire.close()


@pytest.mark.asyncio
async def test_agent_without_skill_manager_has_no_skills_section():
    """Test that Agent without SkillManager has no Skills section in System Prompt."""
    
    from agio.runtime.context import ExecutionContext
    from agio.runtime.wire import Wire
    
    agent = Agent(
        model=MockModel(),
        tools=[],
        system_prompt="You are a helpful assistant.",
        skill_manager=None,  # No SkillManager
    )
    
    wire = Wire()
    context = ExecutionContext(
        run_id="test-run",
        session_id="test-session",
        wire=wire,
    )
    
    # Mock the executor to capture the messages
    with patch("agio.agent.agent.AgentExecutor") as MockExecutor:
        mock_executor = MagicMock()
        mock_executor.execute = AsyncMock(return_value=MagicMock(
            response="test",
            metrics=None,
            termination_reason=None,
        ))
        MockExecutor.return_value = mock_executor
        
        await agent.run("test input", context=context)
        
        # Verify executor.execute was called with messages
        assert mock_executor.execute.called
        call_kwargs = mock_executor.execute.call_args[1]
        messages = call_kwargs["messages"]
        
        # Find system message
        system_message = next((m for m in messages if m["role"] == "system"), None)
        assert system_message is not None
        
        # Verify system prompt does NOT include Skills section
        assert "Available Skills" not in system_message["content"]
        assert system_message["content"] == "You are a helpful assistant."
    
    await wire.close()
