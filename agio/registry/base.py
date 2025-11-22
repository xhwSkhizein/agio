"""
Component Registry for managing configured components.

The registry provides thread-safe storage and retrieval of component instances
and their configurations.
"""

from typing import TypeVar, Generic
from collections import defaultdict
import threading
from .models import BaseComponentConfig, ComponentType

T = TypeVar('T')


class ComponentRegistry(Generic[T]):
    """
    Component Registry - Thread-safe component management.
    
    Responsibilities:
    1. Register and store component instances/configurations
    2. Query components by type, name, or tags
    3. Support hot reload
    4. Manage dependencies
    """
    
    def __init__(self):
        self._components: dict[str, T] = {}
        self._configs: dict[str, BaseComponentConfig] = {}
        self._type_index: dict[ComponentType, set[str]] = defaultdict(set)
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()
    
    def register(
        self, 
        name: str, 
        component: T, 
        config: BaseComponentConfig
    ) -> None:
        """Register a component."""
        with self._lock:
            self._components[name] = component
            self._configs[name] = config
            self._type_index[config.type].add(name)
            for tag in config.tags:
                self._tag_index[tag].add(name)
    
    def get(self, name: str) -> T | None:
        """Get component instance by name."""
        return self._components.get(name)
    
    def get_config(self, name: str) -> BaseComponentConfig | None:
        """Get component configuration by name."""
        return self._configs.get(name)
    
    def list_by_type(self, component_type: ComponentType) -> list[str]:
        """List components by type."""
        return list(self._type_index.get(component_type, set()))
    
    def list_by_tag(self, tag: str) -> list[str]:
        """List components by tag."""
        return list(self._tag_index.get(tag, set()))
    
    def unregister(self, name: str) -> None:
        """Unregister a component."""
        with self._lock:
            if name in self._components:
                config = self._configs[name]
                del self._components[name]
                del self._configs[name]
                self._type_index[config.type].discard(name)
                for tag in config.tags:
                    self._tag_index[tag].discard(name)
    
    def reload(self, name: str, component: T, config: BaseComponentConfig) -> None:
        """Reload a component."""
        self.unregister(name)
        self.register(name, component, config)
    
    def exists(self, name: str) -> bool:
        """Check if component exists."""
        return name in self._components
    
    def list_all(self) -> list[str]:
        """List all component names."""
        return list(self._components.keys())

    def list_configs(self) -> dict[str, BaseComponentConfig]:
        """List all component configurations."""
        return self._configs.copy()


# Global registry instance
_global_registry = ComponentRegistry()


def get_registry() -> ComponentRegistry:
    """Get the global component registry."""
    return _global_registry
