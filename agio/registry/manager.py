"""
Configuration manager for dynamic configuration updates.
"""

from pathlib import Path
from typing import Any
from .base import ComponentRegistry
from .loader import ConfigLoader
from .factory import ComponentFactory
from .validator import ConfigValidator
from .events import ConfigChangeEvent
from .history import ConfigHistory
from .watcher import ConfigFileWatcher
from .models import ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """
    Configuration Manager - Core of dynamic configuration.

    Responsibilities:
    1. Manage configuration lifecycle
    2. Validate configuration changes
    3. Apply configuration changes
    4. Send change events
    5. Support rollback
    6. Hot reload from files
    """

    def __init__(
        self,
        config_dir: str | Path,
        registry: ComponentRegistry,
        loader: ConfigLoader,
        factory: ComponentFactory,
        validator: ConfigValidator,
        history: ConfigHistory,
        event_bus: Any,
        auto_reload: bool = False,
    ):
        self.config_dir = Path(config_dir)
        self.registry = registry
        self.loader = loader
        self.factory = factory
        self.validator = validator
        self.history = history
        self.event_bus = event_bus

        # File watcher
        self._watcher: ConfigFileWatcher | None = None
        if auto_reload:
            self.start_auto_reload()

        # File watcher
        self._watcher: ConfigFileWatcher | None = None
        if auto_reload:
            self.start_auto_reload()

    def start_auto_reload(self) -> None:
        """Start automatic file watching for hot reload."""
        if self._watcher and self._watcher.is_running():
            return

        self._watcher = ConfigFileWatcher(
            watch_dir=self.config_dir, on_change=self._handle_file_change
        )
        self._watcher.start()

    def stop_auto_reload(self) -> None:
        """Stop automatic file watching."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def update_component(
        self,
        component_name: str,
        new_config: dict[str, Any],
        validate_only: bool = False,
    ) -> tuple[bool, str]:
        """
        Update component configuration.

        Args:
            component_name: Component name
            new_config: New configuration (dict format)
            validate_only: Only validate, don't apply

        Returns:
            (success, message)
        """
        try:
            # 1. Validate new configuration
            validated_config = self.validator.validate(new_config)

            # 2. If only validating, return early
            if validate_only:
                return True, "Configuration is valid"

            # 3. Get old configuration
            old_config = self.registry.get_config(component_name)

            # 4. Create new component instance
            new_component = self.factory.create(validated_config)

            # 5. Update registry
            if old_config:
                self.registry.reload(component_name, new_component, validated_config)
                change_type = "updated"
            else:
                self.registry.register(component_name, new_component, validated_config)
                change_type = "created"

            # 6. Record history
            event = ConfigChangeEvent(
                component_name=component_name,
                component_type=validated_config.type,
                change_type=change_type,
                old_config=old_config,
                new_config=validated_config,
            )
            self.history.add(event)

            # 7. Notify listeners
            self.event_bus.publish(event)

            return True, f"Component '{component_name}' {change_type} successfully"

        except Exception as e:
            return False, f"Failed to update component: {str(e)}"

    def delete_component(self, component_name: str) -> tuple[bool, str]:
        """Delete a component."""
        try:
            old_config = self.registry.get_config(component_name)
            if not old_config:
                return False, f"Component '{component_name}' not found"

            # Unregister component
            self.registry.unregister(component_name)

            # Record history
            event = ConfigChangeEvent(
                component_name=component_name,
                component_type=old_config.type,
                change_type="deleted",
                old_config=old_config,
                new_config=None,
            )
            self.history.add(event)

            # Notify listeners
            self.event_bus.publish(event)

            return True, f"Component '{component_name}' deleted successfully"

        except Exception as e:
            return False, f"Failed to delete component: {str(e)}"

    def reload_from_file(self, file_path: str | Path) -> tuple[bool, str]:
        """Reload configuration from a file."""
        try:
            # Load configuration
            config_dict = self.loader.load(file_path)
            component_name = config_dict.get("name")

            if not component_name:
                return False, "Configuration missing 'name' field"

            # Update component
            return self.update_component(component_name, config_dict)

        except Exception as e:
            return False, f"Failed to reload from file: {str(e)}"

    def reload_all(self) -> dict[str, tuple[bool, str]]:
        """Reload all configuration files."""
        results = {}

        # Load all configurations
        all_configs = self.loader.load_directory()

        # Sort configs by dependency order: Model/Repository/Storage -> Memory/Knowledge/Tool -> Hook -> Agent
        type_priority = {
            ComponentType.MODEL.value: 0,
            ComponentType.REPOSITORY.value: 0,
            ComponentType.STORAGE.value: 0,
            ComponentType.MEMORY.value: 1,
            ComponentType.KNOWLEDGE.value: 1,
            ComponentType.TOOL.value: 1,
            ComponentType.HOOK.value: 2,
            ComponentType.AGENT.value: 3,
        }

        sorted_items = sorted(
            all_configs.items(),
            key=lambda item: type_priority.get(item[1].get("type"), 99),
        )

        for name, config in sorted_items:
            success, message = self.update_component(name, config)
            results[name] = (success, message)

        return results

    def rollback(self, component_name: str, steps: int = 1) -> tuple[bool, str]:
        """
        Rollback to a previous configuration.

        Args:
            component_name: Component name
            steps: Number of steps to rollback

        Returns:
            (success, message)
        """
        try:
            # Get history
            history = self.history.get_history(component_name, limit=steps + 1)

            if len(history) < steps + 1:
                return False, f"Not enough history to rollback {steps} steps"

            # Get target configuration
            target_event = history[-(steps + 1)]
            target_config = target_event.old_config

            if not target_config:
                return False, "Cannot rollback to deleted state"

            # Apply old configuration
            config_dict = target_config.model_dump()
            return self.update_component(component_name, config_dict)

        except Exception as e:
            return False, f"Failed to rollback: {str(e)}"

    def _handle_file_change(self, file_path: Path) -> None:
        """Handle file change event from watcher."""
        logger.info("config_file_changed", file_path=str(file_path))
        success, message = self.reload_from_file(file_path)
        if success:
            logger.info("config_reload_success", file_path=str(file_path), message=message)
        else:
            logger.error("config_reload_failed", file_path=str(file_path), message=message)

    def stop(self) -> None:
        """Stop the configuration manager."""
        self.stop_auto_reload()
