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
        self._instances: dict[str, Any] = {}
        self._metadata: dict[str, ComponentMetadata] = {}
        self._ref_counts: dict[str, int] = {}
        self._ref_cond = asyncio.Condition()

    def register(self, name: str, instance: Any, metadata: ComponentMetadata) -> None:
        """
        Register component instance.

        Args:
            name: Component name
            instance: Component instance
            metadata: Component metadata
        """
        self._instances[name] = instance
        self._metadata[name] = metadata
        self._ref_counts[name] = 0
        logger.debug(
            f"Registered component: {name} "
            f"(type={metadata.component_type.value}, deps={metadata.dependencies})"
        )

    def get(self, name: str) -> Any:
        """
        Get component instance.

        Args:
            name: Component name

        Returns:
            Component instance

        Raises:
            ComponentNotFoundError: Component not found
        """
        if name not in self._instances:
            raise ComponentNotFoundError(f"Component '{name}' not found")
        return self._instances[name]

    def get_or_none(self, name: str) -> Any | None:
        """
        Get component instance (returns None if not found).

        Args:
            name: Component name

        Returns:
            Component instance, or None if not found
        """
        return self._instances.get(name)

    def has(self, name: str) -> bool:
        """
        Check if component exists.

        Args:
            name: Component name

        Returns:
            Whether component exists
        """
        return name in self._instances

    def get_metadata(self, name: str) -> ComponentMetadata | None:
        """
        Get component metadata.

        Args:
            name: Component name

        Returns:
            Component metadata, or None if not found
        """
        return self._metadata.get(name)

    def get_all_instances(self) -> dict[str, Any]:
        """
        Get all component instances.

        Returns:
            Mapping from component name to instance
        """
        return dict(self._instances)

    def get_all_metadata(self) -> dict[str, ComponentMetadata]:
        """
        Get all component metadata.

        Returns:
            Mapping from component name to metadata
        """
        return dict(self._metadata)

    def list_names(self) -> list[str]:
        """
        List all component names.

        Returns:
            List of component names
        """
        return list(self._instances.keys())

    def remove(self, name: str) -> tuple[Any | None, ComponentMetadata | None]:
        """
        Remove component (without cleanup).

        Args:
            name: Component name

        Returns:
            Tuple of (instance, metadata), or (None, None) if not found
        """
        instance = self._instances.pop(name, None)
        metadata = self._metadata.pop(name, None)
        self._ref_counts.pop(name, None)

        if instance is not None:
            logger.debug(f"Removed component: {name}")

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

    def acquire(self, name: str) -> Any:
        """Acquire component instance and increase reference count."""
        instance = self.get(name)
        self._ref_counts[name] = self._ref_counts.get(name, 0) + 1
        return instance

    def release(self, name: str) -> None:
        """Release component instance and decrease reference count."""
        if name not in self._ref_counts:
            return
        current = self._ref_counts.get(name, 0)
        self._ref_counts[name] = max(0, current - 1)

        async def _notify():
            async with self._ref_cond:
                self._ref_cond.notify_all()

        # fire-and-forget notification
        asyncio.create_task(_notify())

    def ref_count(self, name: str) -> int:
        """Get reference count for component."""
        return self._ref_counts.get(name, 0)

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
