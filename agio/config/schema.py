"""
Configuration schema definitions.

This module contains all component configuration classes:
- ExecutionConfig: Runtime execution configuration
- ComponentConfig: Base for dynamic component configs
- ModelConfig, ToolConfig, etc.: Specific component configs
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ============================================================================
# Runtime Execution Configuration
# ============================================================================


class ExecutionConfig(BaseModel):
    """
    Runtime execution configuration.
    """

    # Loop configuration
    max_steps: int = Field(default=30, ge=1, le=100, description="Maximum execution steps")
    timeout_per_step: float = Field(default=120.0, ge=1.0, description="Timeout per step (seconds)")
    parallel_tool_calls: bool = Field(default=True, description="Execute tools in parallel")

    # Context configuration
    max_history_messages: int = Field(default=10, description="Maximum history messages")
    max_rag_docs: int = Field(default=3, description="Maximum RAG documents")
    max_memories: int = Field(default=5, description="Maximum semantic memories")

    # Memory configuration
    enable_memory_update: bool = Field(default=False, description="Enable memory updates")
    memory_update_async: bool = Field(default=True, description="Async memory updates")

    # Timeout configuration
    tool_timeout: float | None = Field(default=None, description="Tool execution timeout (seconds)")
    run_timeout: float | None = Field(default=None, description="Overall run timeout (seconds)")

    # Concurrency configuration
    max_parallel_tools: int = Field(default=10, description="Maximum parallel tools")

    # Debug configuration
    debug_mode: bool = Field(default=False, description="Debug mode")
    verbose_logging: bool = Field(default=False, description="Verbose logging")


# ============================================================================
# Component Configuration (for dynamic loading)
# ============================================================================


class ComponentType(str, Enum):
    """Component types for configuration system."""

    MODEL = "model"
    TOOL = "tool"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    AGENT = "agent"
    STORAGE = "storage"
    REPOSITORY = "repository"
    WORKFLOW = "workflow"


class ComponentConfig(BaseModel):
    """Base configuration for dynamically loaded components"""

    type: str
    name: str
    enabled: bool = True


class ModelConfig(ComponentConfig):
    """Configuration for LLM model components"""

    type: Literal["model"] = "model"
    provider: str  # "openai", "anthropic", "deepseek"
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class ToolConfig(ComponentConfig):
    """Configuration for tool components."""

    type: Literal["tool"] = "tool"
    
    # For built-in tools: just specify the tool name
    tool_name: str | None = None
    
    # For custom tools: specify module and class
    module: str | None = None
    class_name: str | None = None
    
    # Tool configuration parameters
    params: dict | None = Field(
        default=None,
        description="Configuration parameters passed to tool constructor",
    )
    
    # Dependencies on other components
    dependencies: dict[str, str] | None = Field(
        default=None,
        description="Dependencies mapping: {param_name: component_name}",
    )
    
    # Optional metadata
    description: str | None = None
    tags: list[str] | None = None
    
    @property
    def effective_params(self) -> dict:
        """Get params, defaulting to empty dict if None."""
        return self.params or {}
    
    @property
    def effective_dependencies(self) -> dict[str, str]:
        """Get dependencies, defaulting to empty dict if None."""
        return self.dependencies or {}
    
    @property
    def effective_tags(self) -> list[str]:
        """Get tags, defaulting to empty list if None."""
        return self.tags or []


class MemoryConfig(ComponentConfig):
    """Configuration for memory components"""

    type: Literal["memory"] = "memory"
    backend: str  # "redis", "inmemory"
    params: dict = Field(default_factory=dict)


class KnowledgeConfig(ComponentConfig):
    """Configuration for knowledge base components"""

    type: Literal["knowledge"] = "knowledge"
    backend: str  # "chroma", "pinecone"
    params: dict = Field(default_factory=dict)


class StorageConfig(ComponentConfig):
    """Configuration for storage components"""

    type: Literal["storage"] = "storage"
    storage_type: str  # "redis", "inmemory", "mongodb"
    params: dict = Field(default_factory=dict)

    # Redis specific
    redis_url: str | None = None
    redis_params: dict = Field(default_factory=dict)

    # MongoDB specific
    mongo_uri: str | None = None
    mongo_db_name: str | None = None


class RepositoryConfig(ComponentConfig):
    """Configuration for repository components"""

    type: Literal["repository"] = "repository"
    repository_type: str  # "mongodb", "inmemory", "postgres"
    params: dict = Field(default_factory=dict)

    # MongoDB specific
    mongo_uri: str | None = None
    mongo_db_name: str | None = None

    # Postgres specific
    postgres_url: str | None = None


class AgentConfig(ComponentConfig):
    """Configuration for agent components"""

    type: Literal["agent"] = "agent"
    model: str  # Reference to model config name
    tools: list[str] = Field(default_factory=list)
    memory: str | None = None
    knowledge: str | None = None
    repository: str | None = None

    system_prompt: str | None = None
    max_steps: int = 10
    enable_memory_update: bool = False
    user_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class StageConfig(BaseModel):
    """Configuration for a workflow stage"""

    id: str
    runnable: str | dict  # Agent/Workflow ID or inline workflow config
    input: str = "{query}"  # Input template
    condition: str | None = None  # Condition expression


class WorkflowConfig(ComponentConfig):
    """Configuration for workflow components"""

    type: Literal["workflow"] = "workflow"
    workflow_type: Literal["pipeline", "loop", "parallel"] = "pipeline"

    # Stages (for pipeline and loop)
    stages: list[StageConfig] = Field(default_factory=list)

    # Loop specific
    condition: str | None = None  # Continue condition for loop
    max_iterations: int = 10

    # Parallel specific
    merge_template: str | None = None  # Template for merging branch outputs

    tags: list[str] = Field(default_factory=list)


__all__ = [
    "ExecutionConfig",
    "ComponentType",
    "ComponentConfig",
    "ModelConfig",
    "ToolConfig",
    "MemoryConfig",
    "KnowledgeConfig",
    "StorageConfig",
    "RepositoryConfig",
    "AgentConfig",
    "StageConfig",
    "WorkflowConfig",
]
