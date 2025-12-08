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

# System
from agio.config.system import (
    ConfigSystem,
    get_config_system,
    init_config_system,
)

__all__ = [
    "ConfigSystem",
    "get_config_system",
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
    # System
    "ConfigSystem",
    "get_config_system",
    "init_config_system",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ComponentNotFoundError",
    "ComponentBuildError",
]
