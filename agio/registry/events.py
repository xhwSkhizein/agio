"""
Configuration event bus for notifying listeners of configuration changes.
"""

from typing import Callable, Any
from datetime import datetime
from .models import BaseComponentConfig
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigChangeEvent:
    """Configuration change event."""
    
    def __init__(
        self,
        component_name: str,
        component_type: str,
        change_type: str,  # "created", "updated", "deleted"
        old_config: BaseComponentConfig | None,
        new_config: BaseComponentConfig | None,
        timestamp: datetime | None = None
    ):
        self.component_name = component_name
        self.component_type = component_type
        self.change_type = change_type
        self.old_config = old_config
        self.new_config = new_config
        self.timestamp = timestamp or datetime.now()
    
    def __repr__(self) -> str:
        return (
            f"ConfigChangeEvent(name={self.component_name}, "
            f"type={self.component_type}, change={self.change_type})"
        )


class ConfigEventBus:
    """
    Event bus for configuration changes.
    
    Allows components to subscribe to configuration change events.
    """
    
    def __init__(self):
        self._listeners: list[Callable[[ConfigChangeEvent], Any]] = []
    
    def subscribe(self, listener: Callable[[ConfigChangeEvent], Any]) -> None:
        """Subscribe to configuration change events."""
        if listener not in self._listeners:
            self._listeners.append(listener)
    
    def unsubscribe(self, listener: Callable[[ConfigChangeEvent], Any]) -> None:
        """Unsubscribe from configuration change events."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def publish(self, event: ConfigChangeEvent) -> None:
        """Publish a configuration change event to all listeners."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(
                    "event_listener_error",
                    event_name=event.component_name,
                    event_type=event.change_type,
                    error=str(e),
                    exc_info=True
                )
    
    def clear(self) -> None:
        """Clear all listeners."""
        self._listeners.clear()


# Global event bus instance
_event_bus = ConfigEventBus()


def get_event_bus() -> ConfigEventBus:
    """Get the global configuration event bus."""
    return _event_bus
