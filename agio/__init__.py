"""
Agio - Agent Framework

Top-level exports for easy access to core functionality.
"""

# Top-level Agent class
from agio.agent.agent import Agent

# Config
from agio.config import ConfigSystem, ExecutionConfig, get_config_system, settings

# Domain models
from agio.domain import (
    AgentSession,
    MessageRole,
    Run,
    RunMetrics,
    RunStatus,
    Step,
    StepDelta,
    StepEvent,
    StepEventType,
    StepMetrics,
    ToolResult,
)

# LLM
from agio.llm import AnthropicModel, DeepseekModel, Model, OpenAIModel

# Storage
from agio.storage.session import InMemorySessionStore, MongoSessionStore, SessionStore

# Tools
from agio.tools import BaseTool, get_tool_registry

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
    # LLM
    "Model",
    "OpenAIModel",
    "AnthropicModel",
    "DeepseekModel",
    # Storage
    "SessionStore",
    "InMemorySessionStore",
    "MongoSessionStore",
    # Tools
    "BaseTool",
    "get_tool_registry",
    # Config
    "settings",
    "ExecutionConfig",
    "ConfigSystem",
    "get_config_system",
]
