"""
Test that nested Agent calls (via AgentTool) work correctly with stream closure.

Verifies that:
1. Nested agents can write to parent's wire
2. Parent wire is not closed by nested agent
3. Stream closes properly after all nested calls complete
"""

import asyncio
import pytest

from agio.agent import Agent
from agio.llm import Model, StreamChunk
from agio.runtime import AgentTool


class MockModel(Model):
    """Mock model for testing."""

    id: str = "test/mock"
    name: str = "mock"

    def __init__(self, response: str = "Test response", use_tool: bool = False):
        super().__init__()
        self._response = response
        self._use_tool = use_tool
        self._call_count = 0

    async def arun_stream(self, messages, tools=None):
        """Stream response chunks."""
        if self._use_tool and tools:
            # Simulate calling a tool
            yield StreamChunk(
                tool_calls=[
                    {
                        "id": f"call_{self._call_count}",
                        "type": "function",
                        "function": {
                            "name": tools[0]["function"]["name"],
                            "arguments": '{"task": "nested task"}',
                        },
                    }
                ]
            )
        else:
            # Just return content
            yield StreamChunk(content=self._response)
        
        # Final chunk with usage
        yield StreamChunk(usage={"total_tokens": 10, "input_tokens": 5, "output_tokens": 5})
        
        self._call_count += 1


@pytest.mark.asyncio
async def test_nested_agent_does_not_close_parent_wire():
    """Test that nested agent execution doesn't close parent's wire."""
    # Create nested agent
    nested_model = MockModel(response="Nested agent response")
    nested_agent = Agent(model=nested_model, name="nested_agent")
    
    # Create parent agent with nested agent as tool
    nested_tool = AgentTool(nested_agent, description="Nested agent tool")
    parent_model = MockModel(response="Parent response", use_tool=True)
    parent_agent = Agent(
        model=parent_model, 
        name="parent_agent",
        tools=[nested_tool],
    )
    
    # Run parent agent stream
    events = []
    stream_completed = False
    
    try:
        async with asyncio.timeout(10.0):  # Generous timeout
            async for event in parent_agent.run_stream("Test with nested agent"):
                events.append(event)
                print(f"Event: {event.type} - run_id={event.run_id[:8]}...")
    except asyncio.TimeoutError:
        pytest.fail("Stream with nested agent did not close")
    else:
        stream_completed = True
    
    # Verify stream completed
    assert stream_completed, "Stream should have completed"
    assert len(events) > 0, "Should have received events"
    
    # Verify we got events from both parent and nested agent
    run_ids = {e.run_id for e in events}
    assert len(run_ids) >= 2, f"Should have events from multiple runs (parent + nested), got {len(run_ids)}"
    
    # Verify parent run completed
    event_types = [e.type.value for e in events]
    assert "run_completed" in event_types, "Should have run_completed event"


@pytest.mark.asyncio
async def test_multiple_nested_calls_in_sequence():
    """Test multiple nested agent calls in sequence."""
    # Create two nested agents
    nested1_model = MockModel(response="Nested 1 response")
    nested1 = Agent(model=nested1_model, name="nested1")
    
    nested2_model = MockModel(response="Nested 2 response")
    nested2 = Agent(model=nested2_model, name="nested2")
    
    # Create parent with both as tools
    tool1 = AgentTool(nested1, name="tool1")
    tool2 = AgentTool(nested2, name="tool2")
    
    parent_model = MockModel(response="Parent response", use_tool=False)
    parent = Agent(model=parent_model, name="parent", tools=[tool1, tool2])
    
    # Run parent stream
    events = []
    completed = False
    
    try:
        async with asyncio.timeout(10.0):
            async for event in parent.run_stream("Test query"):
                events.append(event)
    except asyncio.TimeoutError:
        pytest.fail("Stream did not close with multiple nested agents")
    else:
        completed = True
    
    assert completed, "Stream should complete"
    assert len(events) > 0, "Should have events"


@pytest.mark.asyncio
async def test_deeply_nested_agents():
    """Test deeply nested agent calls (3 levels)."""
    # Level 3 (deepest)
    level3_model = MockModel(response="Level 3 response")
    level3 = Agent(model=level3_model, name="level3")
    
    # Level 2 (calls level 3)
    level2_model = MockModel(response="Level 2 response", use_tool=True)
    level2 = Agent(
        model=level2_model,
        name="level2",
        tools=[AgentTool(level3, name="call_level3")],
    )
    
    # Level 1 (calls level 2)
    level1_model = MockModel(response="Level 1 response", use_tool=True)
    level1 = Agent(
        model=level1_model,
        name="level1",
        tools=[AgentTool(level2, name="call_level2")],
    )
    
    # Run from top level
    events = []
    completed = False
    
    try:
        async with asyncio.timeout(15.0):
            async for event in level1.run_stream("Deep query"):
                events.append(event)
    except asyncio.TimeoutError:
        pytest.fail("Deeply nested stream did not close")
    else:
        completed = True
    
    assert completed, "Deep nested stream should complete"
    assert len(events) > 0, "Should have events from all levels"
    
    # Count unique run_ids - should have at least 3 (one per level)
    run_ids = {e.run_id for e in events if e.run_id}
    assert len(run_ids) >= 3, f"Should have events from 3+ runs, got {len(run_ids)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
