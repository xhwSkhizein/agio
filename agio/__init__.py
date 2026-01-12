"""
Agio - Agent Framework

Top-level exports for easy access to core functionality.
"""

# Top-level Agent class
from agio.agent import Agent

# API
from agio.api import AgioApp

# Config
from agio.config import ExecutionConfig, settings

# Runtime
from agio.runtime import (
    AgentTool,
    ExecutionContext,
    RunnableType,
    Wire,
    as_tool,
)

# Domain models
from agio.domain import (
    AgentSession,
    MessageRole,
    Run,
    RunOutput,
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
    # API
    "AgioApp",
    # Runtime
    "ExecutionContext",
    "RunnableType",
    "Wire",
    "AgentTool",
    "as_tool",
    # Domain
    "Step",
    "StepMetrics",
    "Run",
    "RunOutput",
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
]
