"""
Test incremental trace saving.

This test verifies that traces are saved incrementally at critical checkpoints
instead of only at the end.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agio.domain.events import StepEvent, StepEventType
from agio.observability.collector import TraceCollector


@pytest.mark.asyncio
async def test_incremental_trace_saving():
    """Test that traces are saved at critical checkpoints."""
    # Mock store
    mock_store = MagicMock()
    mock_store.save_trace = AsyncMock()
    
    # Create collector
    collector = TraceCollector(store=mock_store)
    
    # Start trace
    collector.start(
        trace_id="test_trace_001",
        agent_id="test_agent",
        session_id="test_session",
        input_query="test query",
    )
    
    # Track save calls
    save_count = 0
    original_save = mock_store.save_trace
    
    async def track_saves(*args, **kwargs):
        nonlocal save_count
        save_count += 1
        await original_save(*args, **kwargs)
    
    mock_store.save_trace = track_saves
    
    # Test checkpoints
    checkpoints = [
        ("run_started", StepEventType.RUN_STARTED),
        ("step_completed", StepEventType.STEP_COMPLETED),
        ("run_completed", StepEventType.RUN_COMPLETED),
    ]
    
    for i, (event_name, event_type) in enumerate(checkpoints):
        event = StepEvent(
            type=event_type,
            run_id="test_run",
            data={"test": event_name},
        )
        
        await collector.collect(event)
        
        # Give a moment for async task to complete
        await asyncio.sleep(0.1)
        
        # Should have saved once for each checkpoint
        assert save_count == i + 1, f"Expected {i+1} saves after {event_name}, got {save_count}"
    
    # Final stop should also save
    await collector.stop()
    
    # Total saves: 3 checkpoints + 1 final = 4
    assert save_count == 4, f"Expected 4 total saves, got {save_count}"


@pytest.mark.asyncio
async def test_no_save_for_non_checkpoint_events():
    """Test that non-checkpoint events don't trigger saves."""
    mock_store = MagicMock()
    mock_store.save_trace = AsyncMock()
    
    collector = TraceCollector(store=mock_store)
    collector.start(trace_id="test_trace_002", agent_id="test_agent")
    
    save_count = 0
    
    async def count_saves(*args, **kwargs):
        nonlocal save_count
        save_count += 1
    
    mock_store.save_trace = count_saves
    
    # Send a STEP_DELTA event (not a checkpoint)
    event = StepEvent(
        type=StepEventType.STEP_DELTA,
        run_id="test_run",
        data={"delta": "content"},
    )
    
    await collector.collect(event)
    await asyncio.sleep(0.1)
    
    # Should NOT have saved
    assert save_count == 0, "STEP_DELTA should not trigger save"


@pytest.mark.asyncio
async def test_save_failure_does_not_break_execution():
    """Test that save failures are logged but don't break execution."""
    mock_store = MagicMock()
    
    # Make save fail
    async def failing_save(*args, **kwargs):
        raise Exception("Database error")
    
    mock_store.save_trace = failing_save
    
    collector = TraceCollector(store=mock_store)
    collector.start(trace_id="test_trace_003", agent_id="test_agent")
    
    # Should not raise exception
    event = StepEvent(
        type=StepEventType.RUN_STARTED,
        run_id="test_run",
        data={},
    )
    
    try:
        await collector.collect(event)
        await asyncio.sleep(0.1)  # Let background task complete
        # Should reach here without exception
        assert True
    except Exception as e:
        pytest.fail(f"Incremental save failure should not break execution: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
