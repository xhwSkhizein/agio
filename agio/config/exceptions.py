"""Configuration system exceptions."""


class ConfigError(Exception):
    """Base exception for configuration errors."""

    pass


class ConfigNotFoundError(ConfigError):
    """Configuration not found."""

    pass


class ComponentNotFoundError(ConfigError):
    """Component not found."""

    pass


class ComponentBuildError(ConfigError):
    """Failed to build component."""

    pass
