"""
Configuration system for Agio.

This module provides configuration management capabilities:
- Global settings from environment variables
- Component configuration schemas
- Dynamic component loading and hot reload
"""

from agio.config.builder_registry import BuilderRegistry
from agio.config.container import ComponentContainer, ComponentMetadata
from agio.config.dependency import DependencyNode, DependencyResolver

# Exceptions
from agio.config.exceptions import (
    ComponentBuildError,
    ComponentNotFoundError,
    ConfigError,
    ConfigNotFoundError,
)
from agio.config.hot_reload import HotReloadManager
from agio.config.model_provider_registry import (
    ModelProviderRegistry,
    get_model_provider_registry,
)

# Core modules
from agio.config.registry import ConfigRegistry

# Schema
from agio.config.schema import (
    AgentConfig,
    CitationStoreConfig,
    ComponentConfig,
    ComponentType,
    ExecutionConfig,
    ModelConfig,
    RunnableToolConfig,
    SessionStoreConfig,
    ToolConfig,
    ToolReference,
    TraceStoreConfig,
)

# Settings
from agio.config.settings import AgioSettings, settings

# System
from agio.config.system import (
    ConfigSystem,
    get_config_system,
    init_config_system,
    reset_config_system,
)

from .tool_reference import (
    ParsedToolReference,
    parse_tool_reference,
    parse_tool_references,
)

__all__ = [
    # Core
    "ConfigSystem",
    "get_config_system",
    # Schema
    "ExecutionConfig",
    "ComponentType",
    "ComponentConfig",
    "ModelConfig",
    "ToolConfig",
    "RunnableToolConfig",
    "ToolReference",
    "SessionStoreConfig",
    "TraceStoreConfig",
    "CitationStoreConfig",
    "AgentConfig",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ComponentBuildError",
    # Dependency
    "DependencyNode",
    "DependencyResolver",
    # Core modules
    "ConfigRegistry",
    "ComponentContainer",
    "ComponentMetadata",
    "DependencyResolver",
    "DependencyNode",
    "BuilderRegistry",
    "ModelProviderRegistry",
    "get_model_provider_registry",
    # System
    "ConfigSystem",
    "get_config_system",
    "init_config_system",
    "reset_config_system",
]
