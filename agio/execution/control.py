"""
Execution Controller for managing run execution (pause/resume/cancel).
"""

import asyncio
from enum import Enum
from typing import Optional


class ExecutionState(str, Enum):
    """Execution state."""
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionController:
    """
    Execution Controller.
    
    Controls Run execution (pause, resume, cancel).
    """
    
    def __init__(self):
        self._states: dict[str, ExecutionState] = {}
        self._pause_events: dict[str, asyncio.Event] = {}
    
    def start_run(self, run_id: str) -> None:
        """Start a run."""
        self._states[run_id] = ExecutionState.RUNNING
        self._pause_events[run_id] = asyncio.Event()
        self._pause_events[run_id].set()  # Initially running
    
    def pause_run(self, run_id: str) -> bool:
        """Pause a run."""
        if run_id not in self._states:
            return False
        
        if self._states[run_id] != ExecutionState.RUNNING:
            return False
        
        self._states[run_id] = ExecutionState.PAUSED
        self._pause_events[run_id].clear()  # Clear event, block execution
        return True
    
    def resume_run(self, run_id: str) -> bool:
        """Resume a run."""
        if run_id not in self._states:
            return False
        
        if self._states[run_id] != ExecutionState.PAUSED:
            return False
        
        self._states[run_id] = ExecutionState.RUNNING
        self._pause_events[run_id].set()  # Set event, continue execution
        return True
    
    def cancel_run(self, run_id: str) -> bool:
        """Cancel a run."""
        if run_id not in self._states:
            return False
        
        self._states[run_id] = ExecutionState.CANCELLED
        self._pause_events[run_id].set()  # Set event to let execution continue to check cancel status
        return True
    
    async def check_pause(self, run_id: str) -> None:
        """Check if paused (called in execution loop)."""
        if run_id in self._pause_events:
            await self._pause_events[run_id].wait()
    
    def is_cancelled(self, run_id: str) -> bool:
        """Check if cancelled."""
        return self._states.get(run_id) == ExecutionState.CANCELLED
    
    def get_state(self, run_id: str) -> Optional[ExecutionState]:
        """Get execution state."""
        return self._states.get(run_id)
    
    def complete_run(self, run_id: str) -> None:
        """Mark run as completed."""
        if run_id in self._states:
            self._states[run_id] = ExecutionState.COMPLETED
    
    def fail_run(self, run_id: str) -> None:
        """Mark run as failed."""
        if run_id in self._states:
            self._states[run_id] = ExecutionState.FAILED


# Global execution controller
_global_controller = ExecutionController()


def get_execution_controller() -> ExecutionController:
    """Get global execution controller."""
    return _global_controller
