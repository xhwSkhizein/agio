"""
Configuration loader for reading and parsing YAML configuration files.

This module provides the ConfigLoader class which handles:
- Reading YAML files
- Resolving environment variables
- Processing configuration inheritance
- Caching loaded configurations
"""

import os
import yaml
from pathlib import Path
from typing import Any
from .models import ComponentType

from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """
    Configuration Loader.

    Responsibilities:
    1. Read YAML files
    2. Parse environment variable references
    3. Handle configuration inheritance
    4. Validate configuration structure
    """

    def __init__(self, config_dir: str | Path):
        self.config_dir = Path(config_dir).resolve()  # Resolve to absolute path
        self._cache: dict[str, dict] = {}

    def load(self, config_path: str | Path) -> dict[str, Any]:
        """
        Load a configuration file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Parsed configuration dictionary
        """
        path = Path(config_path)

        # Only prepend config_dir if path is relative
        if not path.is_absolute():
            path = self.config_dir / path

        # Resolve to absolute path
        path = path.resolve()

        # Check cache
        cache_key = str(path)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Read YAML
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Resolve environment variables
        config = self._resolve_env_vars(config)

        # Handle inheritance
        if "extends" in config:
            config = self._resolve_inheritance(config)

        # Cache
        self._cache[cache_key] = config
        return config

    def load_directory(
        self, component_type: ComponentType | None = None
    ) -> dict[str, dict]:
        """
        Load all configurations from a directory.

        Args:
            component_type: Optional component type to filter by

        Returns:
            Dictionary mapping component names to their configurations
        """
        configs = {}

        # Determine search path
        if component_type:
            search_dir = self.config_dir / f"{component_type.value}s"
        else:
            search_dir = self.config_dir

        if not search_dir.exists():
            return configs

        # Traverse YAML files
        for yaml_file in search_dir.rglob("*.yaml"):
            try:
                # yaml_file from rglob is already absolute, pass it directly
                config = self.load(yaml_file)
                name = config.get("name")
                if name:
                    configs[name] = config
            except Exception as e:
                logger.error("Warning: Failed to load", yaml_file=yaml_file, err=e)

        return configs

    def _resolve_env_vars(self, config: Any) -> Any:
        """Recursively resolve environment variable references."""
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str):
            if config.startswith("${") and config.endswith("}"):
                env_var = config[2:-1]
                value = os.getenv(env_var)
                # Return None if not found instead of raising error
                # This allows optional env vars in configs
                return value
        return config

    def _resolve_inheritance(self, config: dict) -> dict:
        """Handle configuration inheritance."""
        extends = config.pop("extends")

        # Load parent configuration
        parent_path = self.config_dir / f"{extends}.yaml"
        if not parent_path.exists():
            # Try to find by type
            component_type = config.get("type")
            if component_type:
                parent_path = self.config_dir / f"{component_type}s" / f"{extends}.yaml"

        if not parent_path.exists():
            raise ValueError(f"Parent config '{extends}' not found")

        parent_config = self.load(parent_path)

        # Merge configurations (child overrides parent)
        merged = {**parent_config, **config}
        return merged

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()
