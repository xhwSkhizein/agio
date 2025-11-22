"""
Unit tests for the execution control system.
"""

import pytest
import asyncio
from datetime import datetime
from agio.execution import (
    ExecutionCheckpoint,
    CheckpointMetadata,
    CheckpointPolicy,
    CheckpointStrategy,
    ExecutionController,
    ExecutionState,
)
from agio.domain.run import RunStatus


class TestExecutionCheckpoint:
    """Test ExecutionCheckpoint."""
    
    def test_create_checkpoint(self):
        checkpoint = ExecutionCheckpoint(
            run_id="run_123",
            step_num=2,
            status=RunStatus.RUNNING,
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"}
            ],
            metrics={"total_tokens": 100},
            agent_config={"model": "gpt4"}
        )
        
        assert checkpoint.run_id == "run_123"
        assert checkpoint.step_num == 2
        assert len(checkpoint.messages) == 2
        assert checkpoint.metrics["total_tokens"] == 100
    
    def test_checkpoint_with_tags(self):
        checkpoint = ExecutionCheckpoint(
            run_id="run_123",
            step_num=1,
            status=RunStatus.RUNNING,
            messages=[],
            metrics={},
            agent_config={},
            tags=["important", "before_tool_call"]
        )
        
        assert "important" in checkpoint.tags
        assert len(checkpoint.tags) == 2


class TestCheckpointPolicy:
    """Test CheckpointPolicy."""
    
    def test_manual_strategy(self):
        policy = CheckpointPolicy(CheckpointStrategy.MANUAL)
        assert not policy.should_create_checkpoint({})
    
    def test_every_step_strategy(self):
        policy = CheckpointPolicy(CheckpointStrategy.EVERY_STEP)
        assert policy.should_create_checkpoint({})
    
    def test_on_tool_call_strategy(self):
        policy = CheckpointPolicy(CheckpointStrategy.ON_TOOL_CALL)
        
        # No tool calls
        assert not policy.should_create_checkpoint({"has_tool_calls": False})
        
        # Has tool calls
        assert policy.should_create_checkpoint({"has_tool_calls": True})
    
    def test_custom_strategy(self):
        policy = CheckpointPolicy(CheckpointStrategy.CUSTOM)
        
        # Set custom predicate
        policy.set_custom_predicate(lambda ctx: ctx.get("step_num", 0) % 2 == 0)
        
        assert policy.should_create_checkpoint({"step_num": 2})
        assert not policy.should_create_checkpoint({"step_num": 3})


class TestExecutionController:
    """Test ExecutionController."""
    
    def test_start_run(self):
        controller = ExecutionController()
        controller.start_run("run_123")
        
        assert controller.get_state("run_123") == ExecutionState.RUNNING
    
    def test_pause_and_resume(self):
        controller = ExecutionController()
        controller.start_run("run_123")
        
        # Pause
        assert controller.pause_run("run_123")
        assert controller.get_state("run_123") == ExecutionState.PAUSED
        
        # Resume
        assert controller.resume_run("run_123")
        assert controller.get_state("run_123") == ExecutionState.RUNNING
    
    def test_cancel(self):
        controller = ExecutionController()
        controller.start_run("run_123")
        
        assert controller.cancel_run("run_123")
        assert controller.is_cancelled("run_123")
    
    @pytest.mark.asyncio
    async def test_check_pause(self):
        controller = ExecutionController()
        controller.start_run("run_123")
        
        # Should not block when running
        await asyncio.wait_for(
            controller.check_pause("run_123"),
            timeout=0.1
        )
        
        # Pause
        controller.pause_run("run_123")
        
        # Should block when paused
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                controller.check_pause("run_123"),
                timeout=0.1
            )


class TestCheckpointMetadata:
    """Test CheckpointMetadata."""
    
    def test_create_metadata(self):
        metadata = CheckpointMetadata(
            id="ckpt_123",
            run_id="run_456",
            step_num=2,
            created_at=datetime.now(),
            status=RunStatus.RUNNING,
            description="Test checkpoint",
            tags=["test"],
            message_count=5,
            total_tokens=150,
            has_modifications=False
        )
        
        assert metadata.id == "ckpt_123"
        assert metadata.message_count == 5
        assert metadata.total_tokens == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
