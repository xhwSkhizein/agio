"""
Utility function to load components from configuration directory.

This provides a convenient way to initialize the registry from YAML configs.
"""

from pathlib import Path
from .base import ComponentRegistry, get_registry
from .loader import ConfigLoader
from .factory import ComponentFactory
from .validator import ConfigValidator

from agio.utils.logging import get_logger

logger = get_logger(__name__)


def load_from_config(
    config_dir: str | Path, registry: ComponentRegistry | None = None
) -> ComponentRegistry:
    """
    Load all components from configuration directory.

    Args:
        config_dir: Path to configuration directory
        registry: Optional registry instance (uses global if None)

    Returns:
        ComponentRegistry with loaded components
    """
    if registry is None:
        registry = get_registry()

    loader = ConfigLoader(config_dir)
    validator = ConfigValidator()
    factory = ComponentFactory(registry)

    # Load all configurations
    all_configs = loader.load_directory()

    # Validate all configurations
    validated_configs = validator.validate_batch(all_configs)

    # Sort configs by dependency order: Model -> Memory/Knowledge/Tool -> Hook -> Agent
    from .models import ComponentType

    type_priority = {
        ComponentType.MODEL: 0,
        ComponentType.MEMORY: 1,
        ComponentType.KNOWLEDGE: 1,
        ComponentType.TOOL: 1,
        ComponentType.HOOK: 2,
        ComponentType.AGENT: 3,
    }

    sorted_items = sorted(
        validated_configs.items(), key=lambda item: type_priority.get(item[1].type, 99)
    )

    # Create and register components
    for name, config in sorted_items:
        if not config.enabled:
            continue

        try:
            component = factory.create(config)
            registry.register(name, component, config)
            logger.info("✓ Registered", config_type=config.type, name=name)
        except Exception as e:
            logger.error("✗ Failed to register", name=name, err=e)

    return registry
