"""
Builder Registry - Component builder registration and management.

Manages component builders and provides query interfaces for building components.
"""

from typing import Any, Protocol

from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ComponentBuilder(Protocol):
    """Builder protocol."""

    async def build(self, config: ComponentConfig, dependencies: dict[str, Any]) -> Any:
        """
        Build component instance.

        Args:
            config: Component configuration
            dependencies: Resolved dependencies

        Returns:
            Component instance
        """
        ...

    async def cleanup(self, instance: Any) -> None:
        """
        Cleanup component resources.

        Args:
            instance: Component instance
        """
        ...


class BuilderRegistry:
    """
    Builder registry - manages component builders.

    Responsibilities:
    - Register and query builders
    - Support dynamic registration (extensibility)
    """

    def __init__(self) -> None:
        self._builders: dict[ComponentType, ComponentBuilder] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default builders."""
        from agio.config.builders import (
            AgentBuilder,
            CitationStoreBuilder,
            ModelBuilder,
            SessionStoreBuilder,
            ToolBuilder,
            TraceStoreBuilder,
        )

        self.register(ComponentType.MODEL, ModelBuilder())
        self.register(ComponentType.TOOL, ToolBuilder())
        self.register(ComponentType.SESSION_STORE, SessionStoreBuilder())
        self.register(ComponentType.TRACE_STORE, TraceStoreBuilder())
        self.register(ComponentType.CITATION_STORE, CitationStoreBuilder())
        self.register(ComponentType.AGENT, AgentBuilder())

        logger.debug("Registered default builders")

    def register(
        self, component_type: ComponentType, builder: ComponentBuilder
    ) -> None:
        """
        Register builder.

        Args:
            component_type: Component type
            builder: Builder instance
        """
        self._builders[component_type] = builder
        logger.debug(f"Registered builder for type: {component_type.value}")

    def get(self, component_type: ComponentType) -> ComponentBuilder | None:
        """
        Get builder for component type.

        Args:
            component_type: Component type

        Returns:
            Builder instance, or None if not found
        """
        return self._builders.get(component_type)

    def has(self, component_type: ComponentType) -> bool:
        """
        Check if builder exists for component type.

        Args:
            component_type: Component type

        Returns:
            Whether builder exists
        """
        return component_type in self._builders

    def list_types(self) -> list[ComponentType]:
        """
        List all registered component types.

        Returns:
            List of component types
        """
        return list(self._builders.keys())

    def unregister(self, component_type: ComponentType) -> None:
        """
        Unregister builder for component type.

        Args:
            component_type: Component type
        """
        if component_type in self._builders:
            del self._builders[component_type]
            logger.debug(f"Unregistered builder for type: {component_type.value}")
