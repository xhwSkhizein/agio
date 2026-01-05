"""Configuration loader for cold start from YAML files."""

import os
from pathlib import Path
from typing import Any

import yaml

from agio.config.exceptions import ConfigError
from agio.config.schema import ComponentType
from agio.config.template import renderer
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Load configuration from YAML files.

    Responsibilities:
    - Recursively scan all YAML files in the configuration directory
    - Parse YAML file contents
    - Identify component types based on the 'type' field in config files
    - Detect duplicate configuration names
    - Return configuration dictionary grouped by type

    Supports arbitrary folder organization, no directory structure restrictions.
    """

    def __init__(self, config_dir: str | Path) -> None:
        """Initialize configuration loader.

        Args:
            config_dir: Root directory for configuration files
        """
        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {config_dir}")

    async def load_all_configs(self) -> dict[ComponentType, list[dict[str, Any]]]:
        """Load all configuration files.

        Recursively scan all YAML files and identify component types
        based on the 'type' field in config files.

        Returns:
            Configuration dictionary grouped by type: {ComponentType: [config_dict, ...]}
        """
        # Initialize lists for all types (dynamically generated)
        configs_by_type: dict[ComponentType, list[dict[str, Any]]] = {
            ct: [] for ct in ComponentType
        }

        # Track seen configs to detect duplicates
        seen_configs: dict[tuple[ComponentType, str], Path] = {}

        # Recursively scan all YAML files
        yaml_files = list(self.config_dir.rglob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} YAML files in {self.config_dir}")

        for yaml_file in yaml_files:
            try:
                config_data = self._load_yaml_file(yaml_file)
                if not config_data:
                    continue

                # Validate required fields
                if "type" not in config_data:
                    rel_path = yaml_file.relative_to(self.config_dir)
                    logger.warning(f"Missing 'type' field in {rel_path}, skipping")
                    continue

                if "name" not in config_data:
                    rel_path = yaml_file.relative_to(self.config_dir)
                    logger.warning(f"Missing 'name' field in {rel_path}, skipping")
                    continue

                # Identify type from config content
                try:
                    component_type = ComponentType(config_data["type"])
                except ValueError:
                    logger.warning(
                        f"Unknown component type '{config_data['type']}' in "
                        f"{yaml_file.relative_to(self.config_dir)}, skipping"
                    )
                    continue

                # Check if enabled
                if not config_data.get("enabled", True):
                    logger.info(
                        f"Skipped disabled config: {yaml_file.relative_to(self.config_dir)} "
                        f"(type={component_type.value}, name={config_data['name']})"
                    )
                    continue

                # Detect duplicate config names
                config_key = (component_type, config_data["name"])
                if config_key in seen_configs:
                    previous_path = seen_configs[config_key].relative_to(
                        self.config_dir
                    )
                    logger.warning(
                        f"Duplicate config found: {component_type.value}/{config_data['name']} "
                        f"at {yaml_file.relative_to(self.config_dir)}, "
                        f"previous: {previous_path}"
                    )

                seen_configs[config_key] = yaml_file
                configs_by_type[component_type].append(config_data)
                logger.info(
                    f"Loaded config: {yaml_file.relative_to(self.config_dir)} "
                    f"(type={component_type.value}, name={config_data['name']})"
                )

            except Exception as e:
                logger.error(
                    f"Failed to load {yaml_file.relative_to(self.config_dir)}: {e}",
                    exc_info=True,
                )

        # Statistics
        total = sum(len(configs) for configs in configs_by_type.values())
        logger.info(f"Loaded {total} configs across {len(ComponentType)} types")

        return configs_by_type

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any] | None:
        """Load a single YAML file.

        Args:
            file_path: YAML file path

        Returns:
            Configuration dictionary or None
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty config file: {file_path}")
                return None

            # Validate required fields
            if "type" not in data:
                raise ConfigError(f"Missing 'type' field in {file_path}")
            if "name" not in data:
                raise ConfigError(f"Missing 'name' field in {file_path}")

            # Resolve environment variables
            data = self._resolve_env_vars(data)

            return data

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {file_path}: {e}")
        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Failed to load {file_path}: {e}")

    def _resolve_env_vars(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively render Jinja2 templates in configuration.

        Only renders environment variable references ({{ env.VAR_NAME }}).
        Other template variables (like {{ work_dir }}, {{ date }}) are preserved
        for runtime rendering.

        Supported formats:
        - {{ env.VAR_NAME }}
        - {{ env.VAR_NAME | default('default_value') }}
        - {% if env.VAR %}...{% endif %}

        Args:
            data: Configuration dictionary

        Returns:
            Rendered configuration dictionary
        """

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # Only render if it contains env variable references
                # Skip rendering if it only contains runtime variables like {{ work_dir }}, {{ date }}
                if "{{ env." in value or "{% if env." in value:
                    try:
                        return renderer.render(value, env=os.environ)
                    except Exception as e:
                        logger.warning(
                            f"Template render failed: {e}, using original value: {value[:100]}..."
                        )
                        return value
                # Preserve runtime variables ({{ work_dir }}, {{ date }}, etc.)
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        return resolve_value(data)
