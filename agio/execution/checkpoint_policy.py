"""
Checkpoint policy for determining when to create checkpoints.
"""

from enum import Enum
from typing import Callable


class CheckpointStrategy(str, Enum):
    """Checkpoint creation strategy."""
    
    MANUAL = "manual"              # Manual creation only
    EVERY_STEP = "every_step"      # Auto-create after each step
    ON_TOOL_CALL = "on_tool_call"  # Create before tool calls
    ON_ERROR = "on_error"          # Create on errors
    CUSTOM = "custom"              # Custom predicate


class CheckpointPolicy:
    """
    Checkpoint Policy Manager.
    
    Determines when to automatically create checkpoints.
    """
    
    def __init__(self, strategy: CheckpointStrategy = CheckpointStrategy.MANUAL):
        self.strategy = strategy
        self._custom_predicate: Callable | None = None
    
    def set_custom_predicate(self, predicate: Callable[[dict], bool]) -> None:
        """Set custom judgment function."""
        self.strategy = CheckpointStrategy.CUSTOM
        self._custom_predicate = predicate
    
    def should_create_checkpoint(self, context: dict) -> bool:
        """Determine if checkpoint should be created."""
        
        if self.strategy == CheckpointStrategy.MANUAL:
            return False
        
        elif self.strategy == CheckpointStrategy.EVERY_STEP:
            return True
        
        elif self.strategy == CheckpointStrategy.ON_TOOL_CALL:
            return context.get("has_tool_calls", False)
        
        elif self.strategy == CheckpointStrategy.ON_ERROR:
            return context.get("has_error", False)
        
        elif self.strategy == CheckpointStrategy.CUSTOM:
            if self._custom_predicate:
                return self._custom_predicate(context)
            return False
        
        return False
