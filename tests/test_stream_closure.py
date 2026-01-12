"""
Test SSE stream closure after run_completed event.

Verifies that the SSE stream correctly closes after the Agent completes execution.
"""

import asyncio
import pytest

from agio.agent import Agent
from agio.llm import Model, StreamChunk


class MockModel(Model):
    """Mock model for testing stream closure."""

    id: str = "test/mock"
    name: str = "mock"

    def __init__(self, response: str = "Test response", chunks: list[str] | None = None):
        super().__init__()
        self._response = response
        self._chunks = chunks or [response]
        self._call_count = 0

    async def arun_stream(self, messages, tools=None):
        """Stream response chunks."""
        # Stream content chunks
        for chunk in self._chunks:
            yield StreamChunk(content=chunk)
        
        # Final chunk with usage
        yield StreamChunk(usage={"total_tokens": 10, "input_tokens": 5, "output_tokens": 5})
        
        self._call_count += 1


@pytest.mark.asyncio
async def test_stream_closes_after_completion():
    """Test that event stream closes properly after Agent completes."""
    # Create agent with mock model
    model = MockModel(
        response="Test response",
        chunks=["Test", " ", "response"],
    )
    agent = Agent(model=model, name="test_agent")
    
    # Collect events
    events = []
    stream_completed = False
    
    try:
        async for event in agent.run_stream("test query"):
            events.append(event)
            print(f"Received event: {event.type}")
    except asyncio.TimeoutError:
        pytest.fail("Stream did not close - timed out waiting for events")
    else:
        stream_completed = True
    
    # Verify stream completed
    assert stream_completed, "Event stream should have completed"
    
    # Verify we got events
    assert len(events) > 0, "Should have received events"
    
    # Verify we got run_completed event
    event_types = [e.type.value for e in events]
    assert "run_completed" in event_types, f"Should have run_completed event, got: {event_types}"
    
    # Verify run_completed is the last event (or one of the last)
    run_completed_idx = event_types.index("run_completed")
    # Allow for step_completed events after run_completed in some cases
    assert run_completed_idx >= len(event_types) - 3, "run_completed should be near the end"


@pytest.mark.asyncio
async def test_stream_closes_with_timeout():
    """Test that stream closes within reasonable time."""
    model = MockModel(response="Quick response")
    agent = Agent(model=model, name="test_agent")
    
    # Use timeout to verify stream closes quickly
    timeout_seconds = 5.0
    
    try:
        async with asyncio.timeout(timeout_seconds):
            events = []
            async for event in agent.run_stream("test query"):
                events.append(event)
            
            # If we reach here, stream closed successfully
            assert len(events) > 0
    except asyncio.TimeoutError:
        pytest.fail(f"Stream did not close within {timeout_seconds} seconds")


@pytest.mark.asyncio  
async def test_multiple_sequential_streams():
    """Test that multiple sequential stream calls work correctly."""
    model1 = MockModel(response="Response 1")
    model2 = MockModel(response="Response 2")
    model3 = MockModel(response="Response 3")
    
    # Create separate agents for each call
    agents = [
        Agent(model=model1, name="test_agent1"),
        Agent(model=model2, name="test_agent2"),
        Agent(model=model3, name="test_agent3"),
    ]
    
    # Run multiple streams sequentially
    for i, agent in enumerate(agents):
        events = []
        completed = False
        
        try:
            async with asyncio.timeout(5.0):
                async for event in agent.run_stream(f"Query {i}"):
                    events.append(event)
                completed = True
        except asyncio.TimeoutError:
            pytest.fail(f"Stream {i} did not close")
        
        assert completed, f"Stream {i} should have completed"
        assert len(events) > 0, f"Stream {i} should have events"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
