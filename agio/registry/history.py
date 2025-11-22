"""
Configuration change history tracking.
"""

from datetime import datetime
from .events import ConfigChangeEvent


class ConfigHistory:
    """Configuration change history tracker."""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: list[ConfigChangeEvent] = []
    
    def add(self, event: ConfigChangeEvent) -> None:
        """Add a history record."""
        self._history.append(event)
        
        # Trim if exceeds max
        if len(self._history) > self.max_history:
            self._history.pop(0)
    
    def get_history(
        self,
        component_name: str | None = None,
        limit: int = 10
    ) -> list[ConfigChangeEvent]:
        """
        Get history records.
        
        Args:
            component_name: Filter by component name (optional)
            limit: Maximum number of records to return
            
        Returns:
            List of configuration change events
        """
        if component_name:
            filtered = [
                e for e in self._history
                if e.component_name == component_name
            ]
        else:
            filtered = self._history
        
        return filtered[-limit:]
    
    def get_latest(self, component_name: str) -> ConfigChangeEvent | None:
        """Get the latest change event for a component."""
        history = self.get_history(component_name, limit=1)
        return history[0] if history else None
    
    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
