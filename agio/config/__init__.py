"""
Configuration system for Agio.

This module provides configuration management capabilities:
- Global settings from environment variables
- Component configuration schemas
- Dynamic component loading and hot reload
"""

# Settings
from agio.config.settings import AgioSettings, settings

# Schema
from agio.config.schema import (
    AgentConfig,
    ComponentConfig,
    ComponentType,
    ExecutionConfig,
    KnowledgeConfig,
    MemoryConfig,
    ModelConfig,
    SessionStoreConfig,
    TraceStoreConfig,
    RunnableToolConfig,
    StageConfig,
    ToolConfig,
    ToolReference,
    WorkflowConfig,
)
from .tool_reference import (
    ParsedToolReference,
    parse_tool_reference,
    parse_tool_references,
)

# Exceptions
from agio.config.exceptions import (
    ComponentBuildError,
    ComponentNotFoundError,
    ConfigError,
    ConfigNotFoundError,
)

# Core modules
from agio.config.registry import ConfigRegistry
from agio.config.container import ComponentContainer, ComponentMetadata
from agio.config.dependency import DependencyResolver, DependencyNode
from agio.config.builder_registry import BuilderRegistry
from agio.config.hot_reload import HotReloadManager
from agio.config.model_provider_registry import (
    ModelProviderRegistry,
    get_model_provider_registry,
)

# System
from agio.config.system import (
    ConfigSystem,
    get_config_system,
    init_config_system,
    reset_config_system,
)

__all__ = [
    # Settings
    "AgioSettings",
    "settings",
    # Schema
    "ComponentType",
    "ComponentConfig",
    "ExecutionConfig",
    "ModelConfig",
    "ToolConfig",
    "RunnableToolConfig",
    "ToolReference",
    "ParsedToolReference",
    "parse_tool_reference",
    "parse_tool_references",
    "MemoryConfig",
    "KnowledgeConfig",
    "SessionStoreConfig",
    "TraceStoreConfig",
    "AgentConfig",
    "StageConfig",
    "WorkflowConfig",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ComponentNotFoundError",
    "ComponentBuildError",
    # Core modules
    "ConfigRegistry",
    "ComponentContainer",
    "ComponentMetadata",
    "DependencyResolver",
    "DependencyNode",
    "BuilderRegistry",
    "HotReloadManager",
    "ModelProviderRegistry",
    "get_model_provider_registry",
    # System
    "ConfigSystem",
    "get_config_system",
    "init_config_system",
    "reset_config_system",
]
