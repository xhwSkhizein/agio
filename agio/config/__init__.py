"""Configuration module for Agio.

This module provides:
- Global settings from environment variables
- ExecutionConfig for runtime configuration
- Storage backend configurations
"""

from agio.config.backends import StorageBackend
from agio.config.exceptions import ConfigError, ConfigNotFoundError
from agio.config.schema import ComponentType, ExecutionConfig
from agio.config.settings import AgioSettings, settings

__all__ = [
    # Settings
    "settings",
    "AgioSettings",
    # Schema
    "ExecutionConfig",
    "ComponentType",
    # Backends
    "StorageBackend",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
]
