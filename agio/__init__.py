"""
Agio - Agent Framework

Top-level exports for easy access to core functionality.
"""

# Top-level Agent class
from agio.agent import Agent

# Domain models
from agio.domain import (
    Step,
    StepMetrics,
    Run,
    RunMetrics,
    AgentSession,
    MessageRole,
    RunStatus,
    StepEvent,
    StepEventType,
    StepDelta,
    ToolResult,
)

# Providers
from agio.providers.llm import Model, OpenAIModel, AnthropicModel, DeepseekModel
from agio.providers.storage import SessionStore, InMemorySessionStore, MongoSessionStore
from agio.providers.tools import BaseTool, get_tool_registry

# Config
from agio.config import settings, ExecutionConfig, ConfigSystem, get_config_system

__version__ = "0.1.0"

__all__ = [
    # Agent
    "Agent",
    # Domain
    "Step",
    "StepMetrics",
    "Run",
    "RunMetrics",
    "AgentSession",
    "MessageRole",
    "RunStatus",
    "StepEvent",
    "StepEventType",
    "StepDelta",
    "ToolResult",
    # Providers - LLM
    "Model",
    "OpenAIModel",
    "AnthropicModel",
    "DeepseekModel",
    # Providers - Storage
    "SessionStore",
    "InMemorySessionStore",
    "MongoSessionStore",
    # Providers - Tools
    "BaseTool",
    "get_tool_registry",
    # Config
    "settings",
    "ExecutionConfig",
    "ConfigSystem",
    "get_config_system",
]
