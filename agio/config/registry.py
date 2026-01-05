"""
Config Registry - Configuration storage and query.

Manages validated Pydantic configuration models and provides query interfaces.
"""

from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigRegistry:
    """
    Configuration registry - Manages configuration storage and query.

    Responsibilities:
    - Store validated Pydantic configuration models
    - Provide configuration query interfaces
    - Support CRUD operations on configurations
    """

    def __init__(self) -> None:
        self._configs: dict[tuple[ComponentType, str], ComponentConfig] = {}

    def register(self, config: ComponentConfig) -> None:
        """
        Register configuration (auto-validated).

        Args:
            config: Component configuration (validated Pydantic model)
        """
        component_type = ComponentType(config.type)
        key = (component_type, config.name)
        self._configs[key] = config
        logger.debug(f"Registered config: {component_type.value}/{config.name}")

    def get(self, component_type: ComponentType, name: str) -> ComponentConfig | None:
        """
        Get configuration.

        Args:
            component_type: Component type
            name: Component name

        Returns:
            Configuration object, or None if not found
        """
        return self._configs.get((component_type, name))

    def has(self, component_type: ComponentType, name: str) -> bool:
        """
        Check if configuration exists.

        Args:
            component_type: Component type
            name: Component name

        Returns:
            Whether configuration exists
        """
        return (component_type, name) in self._configs

    def list_by_type(self, component_type: ComponentType) -> list[ComponentConfig]:
        """
        List all configurations of specified type.

        Args:
            component_type: Component type

        Returns:
            List of configurations
        """
        return [
            config for (ct, _), config in self._configs.items() if ct == component_type
        ]

    def list_all(self) -> list[ComponentConfig]:
        """
        List all configurations.

        Returns:
            List of all configurations
        """
        return list(self._configs.values())

    def remove(self, component_type: ComponentType, name: str) -> None:
        """
        Remove configuration.

        Args:
            component_type: Component type
            name: Component name
        """
        key = (component_type, name)
        if key in self._configs:
            del self._configs[key]
            logger.debug(f"Removed config: {component_type.value}/{name}")

    def clear(self) -> None:
        """Clear all configurations."""
        self._configs.clear()
        logger.debug("Cleared all configs")

    def count(self) -> int:
        """Get total number of configurations."""
        return len(self._configs)

    def get_names_by_type(self, component_type: ComponentType) -> set[str]:
        """
        Get all component names of specified type.

        Args:
            component_type: Component type

        Returns:
            Set of component names
        """
        return {name for (ct, name) in self._configs.keys() if ct == component_type}

    def get_all_names(self) -> set[str]:
        """
        Get all component names.

        Returns:
            Set of all component names
        """
        return {name for (_, name) in self._configs.keys()}
