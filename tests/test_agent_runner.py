"""
测试 AgentRunner 和新架构

注意：旧的 EventHandler 和 ModelEvent 测试已过时，因为新架构中：
- 不再有 EventHandler
- 不再有 ModelEvent  
- AgentRunner 现在只消费 Executor 产生的 AgentEvent

这些测试已被 test_full_arch.py 和 test_new_arch.py 替代。
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from agio.runners.base import AgentRunner
from agio.agent.base import Agent
from agio.sessions.base import AgentSession
from agio.protocol.events import EventType
from agio.execution.agent_executor import AgentExecutor


@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=Agent)
    agent.id = "test_agent"
    agent.model = MagicMock()
    agent.tools = []
    agent.memory = None
    return agent


@pytest.fixture
def mock_session():
    session = MagicMock(spec=AgentSession)
    session.user_id = "test_user"
    session.session_id = "test_session"
    return session


@pytest.mark.asyncio
async def test_agent_runner_basic_flow(mock_agent, mock_session):
    """Test basic AgentRunner flow with mocked Executor"""
    runner = AgentRunner(agent=mock_agent, hooks=[])
    runner.context_builder.build = AsyncMock(return_value=[
        {"role": "user", "content": "test"}
    ])
    
    # Mock AgentExecutor to yield simple events
    async def mock_execute(*args, **kwargs):
        from agio.protocol.events import AgentEvent
        yield AgentEvent(
            type=EventType.TEXT_DELTA,
            run_id="test_run",
            data={"content": "Hello", "step": 1}
        )
        yield AgentEvent(
            type=EventType.USAGE_UPDATE,
            run_id="test_run",
            data={"usage": {"total_tokens": 10}, "step": 1}
        )
    
    # Patch AgentExecutor
    original_executor = AgentExecutor
    try:
        # Mock the execute method
        AgentExecutor.execute = mock_execute
        
        events = []
        async for event in runner.run_stream(mock_session, "test query"):
            events.append(event)
        
        # Verify event sequence
        event_types = [e.type for e in events]
        assert EventType.RUN_STARTED in event_types
        assert EventType.TEXT_DELTA in event_types
        assert EventType.USAGE_UPDATE in event_types
        assert EventType.RUN_COMPLETED in event_types
        
    finally:
        # Restore
        AgentExecutor.execute = original_executor.execute


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
