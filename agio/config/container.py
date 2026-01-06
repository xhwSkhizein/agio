"""
Component Container - Component instance storage and lifecycle management.

Manages built component instances, stores component metadata, and handles component lifecycle.
"""

import asyncio
from datetime import datetime
from typing import Any

from agio.config.exceptions import ComponentNotFoundError
from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ComponentMetadata:
    """Component metadata."""

    def __init__(
        self,
        component_type: ComponentType,
        config: ComponentConfig,
        dependencies: list[str],
    ):
        self.component_type = component_type
        self.config = config
        self.dependencies = dependencies
        self.created_at = datetime.now()


class ComponentContainer:
    """
    Component container - Manages instance storage and lifecycle.

    Responsibilities:
    - Cache built component instances
    - Store component metadata
    - Manage component lifecycle
    """

    def __init__(self) -> None:
        self._instances: dict[tuple[ComponentType, str], Any] = {}
        self._metadata: dict[tuple[ComponentType, str], ComponentMetadata] = {}
        self._ref_counts: dict[tuple[ComponentType, str], int] = {}
        self._ref_cond = asyncio.Condition()

    def register(self, name: str, instance: Any, metadata: ComponentMetadata) -> None:
        """
        Register component instance.

        Args:
            name: Component name
            instance: Component instance
            metadata: Component metadata
        """
        key = (metadata.component_type, name)
        self._instances[key] = instance
        self._metadata[key] = metadata
        self._ref_counts[key] = 0
        logger.debug(
            f"Registered component: {metadata.component_type.value}/{name} "
            f"(deps={metadata.dependencies})"
        )

    def get(self, name: str, component_type: ComponentType | None = None) -> Any:
        """
        Get component instance.

        Args:
            name: Component name
            component_type: Optional component type for isolated lookup

        Returns:
            Component instance

        Raises:
            ComponentNotFoundError: Component not found
        """
        if component_type:
            key = (component_type, name)
            if key in self._instances:
                return self._instances[key]
        else:
            # Fallback to searching all types for backward compatibility
            for key, instance in self._instances.items():
                if key[1] == name:
                    return instance
        
        raise ComponentNotFoundError(f"Component '{name}' (type={component_type}) not found")

    def get_or_none(self, name: str, component_type: ComponentType | None = None) -> Any | None:
        """
        Get component instance (returns None if not found).

        Args:
            name: Component name
            component_type: Optional component type for isolated lookup

        Returns:
            Component instance, or None if not found
        """
        try:
            return self.get(name, component_type)
        except ComponentNotFoundError:
            return None

    def has(self, name: str, component_type: ComponentType | None = None) -> bool:
        """
        Check if component exists.

        Args:
            name: Component name
            component_type: Optional component type for isolated lookup

        Returns:
            Whether component exists
        """
        if component_type:
            return (component_type, name) in self._instances
        
        return any(key[1] == name for key in self._instances)

    def get_metadata(self, name: str, component_type: ComponentType | None = None) -> ComponentMetadata | None:
        """
        Get component metadata.

        Args:
            name: Component name
            component_type: Optional component type for isolated lookup

        Returns:
            Component metadata, or None if not found
        """
        if component_type:
            return self._metadata.get((component_type, name))
        
        for key, metadata in self._metadata.items():
            if key[1] == name:
                return metadata
        return None

    def get_all_instances(self) -> dict[tuple[ComponentType, str], Any]:
        """
        Get all component instances.

        Returns:
            Mapping from (type, name) to instance
        """
        return dict(self._instances)

    def get_all_metadata(self) -> dict[tuple[ComponentType, str], ComponentMetadata]:
        """
        Get all component metadata.

        Returns:
            Mapping from (type, name) to metadata
        """
        return dict(self._metadata)

    def list_names(self) -> list[str]:
        """
        List all component names.

        Returns:
            List of component names
        """
        return [key[1] for key in self._instances.keys()]

    def list_components(self) -> list[tuple[ComponentType, str]]:
        """List all components as (type, name) tuples."""
        return list(self._instances.keys())

    def remove(self, name: str, component_type: ComponentType | None = None) -> tuple[Any | None, ComponentMetadata | None]:
        """
        Remove component (without cleanup).

        Args:
            name: Component name
            component_type: Optional component type

        Returns:
            Tuple of (instance, metadata), or (None, None) if not found
        """
        target_key = None
        if component_type:
            target_key = (component_type, name)
        else:
            for key in self._instances:
                if key[1] == name:
                    target_key = key
                    break
        
        if not target_key or target_key not in self._instances:
            return None, None

        instance = self._instances.pop(target_key)
        metadata = self._metadata.pop(target_key)
        self._ref_counts.pop(target_key, None)

        logger.debug(f"Removed component: {target_key[0].value}/{target_key[1]}")
        return instance, metadata

    def clear(self) -> None:
        """Clear all components."""
        self._instances.clear()
        self._metadata.clear()
        self._ref_counts.clear()
        logger.debug("Cleared all components")

    def count(self) -> int:
        """Get total component count."""
        return len(self._instances)

    def acquire(self, name: str, component_type: ComponentType | None = None) -> Any:
        """Acquire component instance and increase reference count."""
        instance = self.get(name, component_type)
        # We need the actual key to increment ref count
        metadata = self.get_metadata(name, component_type)
        if metadata:
            key = (metadata.component_type, name)
            self._ref_counts[key] = self._ref_counts.get(key, 0) + 1
        return instance

    def release(self, name: str, component_type: ComponentType | None = None) -> None:
        """Release component instance and decrease reference count."""
        metadata = self.get_metadata(name, component_type)
        if not metadata:
            return
            
        key = (metadata.component_type, name)
        if key not in self._ref_counts:
            return
            
        current = self._ref_counts.get(key, 0)
        self._ref_counts[key] = max(0, current - 1)

        async def _notify():
            async with self._ref_cond:
                self._ref_cond.notify_all()

        # fire-and-forget notification
        asyncio.create_task(_notify())

    def ref_count(self, name: str, component_type: ComponentType | None = None) -> int:
        """Get reference count for component."""
        metadata = self.get_metadata(name, component_type)
        if not metadata:
            return 0
        return self._ref_counts.get((metadata.component_type, name), 0)

    def total_ref_count(self) -> int:
        """Get total reference count across all components."""
        return sum(self._ref_counts.values())

    async def wait_for_zero(self, timeout: float | None = 5.0) -> bool:
        """Wait until all reference counts drop to zero."""
        async with self._ref_cond:
            try:
                await asyncio.wait_for(
                    self._ref_cond.wait_for(lambda: self.total_ref_count() == 0),
                    timeout=timeout,
                )
                return True
            except asyncio.TimeoutError:
                return self.total_ref_count() == 0

    def get_dependents(self, name: str) -> list[str]:
        """
        Get components that depend on the specified component.

        Args:
            name: Component name

        Returns:
            List of component names that depend on this component
        """
        dependents = []
        for comp_name, metadata in self._metadata.items():
            if name in metadata.dependencies:
                dependents.append(comp_name)
        return dependents
