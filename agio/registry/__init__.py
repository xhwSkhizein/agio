"""
Registry package for configuration-based component instantiation.

This package provides:
- Configuration models (models.py)
- Component registry (base.py)
- 

Configuration registry system for Agio.

This module provides a configuration-driven approach to instantiate
and manage Agio components (Models, Agents, Tools, etc.).
"""

from .models import ComponentType, BaseComponentConfig, ModelConfig, AgentConfig, ToolConfig
from .base import ComponentRegistry, get_registry
from .loader import ConfigLoader
from .factory import ComponentFactory
from .validator import ConfigValidator
from .utils import load_from_config
from .events import ConfigChangeEvent, ConfigEventBus, get_event_bus
from .history import ConfigHistory
from .watcher import ConfigFileWatcher
from .manager import ConfigManager

__all__ = [
    "ComponentType",
    "BaseComponentConfig",
    "ModelConfig",
    "AgentConfig",
    "ToolConfig",
    "ComponentRegistry",
    "get_registry",
    "ConfigLoader",
    "ComponentFactory",
    "ConfigValidator",
    "load_from_config",
    "ConfigChangeEvent",
    "ConfigEventBus",
    "get_event_bus",
    "ConfigHistory",
    "ConfigFileWatcher",
    "ConfigManager",
]
