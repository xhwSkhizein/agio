"""
Configuration models for Agio components.

This module defines the Pydantic models for all configurable components
in the Agio framework, including Models, Agents, Tools, Memory, and Knowledge.
"""

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
import os


class ComponentType(str, Enum):
    """Component type enumeration."""
    
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    HOOK = "hook"
    REPOSITORY = "repository"
    STORAGE = "storage"


class BaseComponentConfig(BaseModel):
    """
    Base configuration for all components.
    
    All component configurations inherit from this base class,
    providing common fields like name, description, enabled status, etc.
    """
    
    # Required fields
    type: ComponentType = Field(description="Component type")
    name: str = Field(description="Unique component identifier")
    
    # Optional fields
    description: str | None = Field(default=None, description="Component description")
    enabled: bool = Field(default=True, description="Whether the component is enabled")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    
    # Inheritance support
    extends: str | None = Field(default=None, description="Parent configuration name")
    
    class Config:
        extra = "forbid"  # Disallow extra fields
        use_enum_values = True


class ModelProvider(str, Enum):
    """Supported model providers."""
    
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    CUSTOM = "custom"


class ModelConfig(BaseComponentConfig):
    """Model component configuration."""
    
    type: Literal[ComponentType.MODEL] = ComponentType.MODEL
    
    # Provider configuration
    provider: ModelProvider = Field(description="Model provider")
    model: str = Field(description="Model name, e.g., gpt-4-turbo-preview")
    
    # API configuration
    api_key: str | None = Field(default=None, description="API Key, supports ${ENV_VAR}")
    api_base: str | None = Field(default=None, description="API Base URL")
    
    # Model parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    
    # Advanced configuration
    timeout: int = Field(default=60, description="Request timeout (seconds)")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Custom provider
    custom_class: str | None = Field(
        default=None, 
        description="Custom Model class path, e.g., 'mypackage.MyModel'"
    )
    custom_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to custom class"
    )
    
    @field_validator("api_key", "api_base")
    @classmethod
    def resolve_env_vars(cls, v: str | None) -> str | None:
        """Resolve environment variable references."""
        if v and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class AgentConfig(BaseComponentConfig):
    """Agent component configuration."""
    
    type: Literal[ComponentType.AGENT] = ComponentType.AGENT
    
    # Core component references
    model: str = Field(description="Model reference, e.g., 'gpt4' or 'ref:gpt4'")
    tools: list[str] = Field(default_factory=list, description="Tool reference list")
    memory: str | None = Field(default=None, description="Memory reference")
    knowledge: str | None = Field(default=None, description="Knowledge reference")
    hooks: list[str] = Field(default_factory=list, description="Hook reference list")
    
    # Agent configuration
    system_prompt: str | None = Field(default=None, description="System prompt")
    system_prompt_file: str | None = Field(
        default=None, 
        description="System prompt file path"
    )
    
    # Execution configuration
    max_steps: int = Field(default=10, ge=1, description="Maximum execution steps")
    enable_memory_update: bool = Field(default=True, description="Whether to update memory")
    
    # Storage configuration
    storage: str | None = Field(default=None, description="Storage reference")
    repository: str | None = Field(default=None, description="Repository reference")
    
    @field_validator("system_prompt_file")
    @classmethod
    def load_prompt_file(cls, v: str | None) -> str | None:
        """Load system prompt from file."""
        if v:
            from pathlib import Path
            return Path(v).read_text(encoding="utf-8")
        return None


class ToolType(str, Enum):
    """Tool implementation type."""
    
    FUNCTION = "function"
    CLASS = "class"
    MCP = "mcp"


class ToolConfig(BaseComponentConfig):
    """Tool component configuration."""
    
    type: Literal[ComponentType.TOOL] = ComponentType.TOOL
    tool_type: ToolType = Field(description="Tool implementation type")
    
    # Function Tool
    function_path: str | None = Field(
        default=None,
        description="Function path, e.g., 'mypackage.my_function'"
    )
    
    # Class Tool
    class_path: str | None = Field(
        default=None,
        description="Class path, e.g., 'mypackage.MyTool'"
    )
    class_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Class initialization parameters"
    )
    
    # MCP Tool
    mcp_server: str | None = Field(default=None, description="MCP server name")
    mcp_tool_name: str | None = Field(default=None, description="MCP Tool name")
    
    # Tool Schema (optional, to override auto-generated schema)
    schema_override: dict[str, Any] | None = Field(
        default=None,
        description="Override auto-generated Tool Schema"
    )


class MemoryConfig(BaseComponentConfig):
    """Memory component configuration."""
    
    type: Literal[ComponentType.MEMORY] = ComponentType.MEMORY
    
    # Implementation class path
    class_path: str = Field(description="Memory class path, e.g., 'agio.memory.conversation.ConversationMemory'")
    
    # Memory parameters
    max_history_length: int = Field(default=20, ge=1, description="Maximum number of history messages")
    max_tokens: int = Field(default=4000, ge=1, description="Maximum token count")
    
    # Storage backend
    storage_backend: str = Field(default="memory", description="Storage backend: memory, redis, postgres")
    storage_params: dict[str, Any] = Field(default_factory=dict, description="Storage backend parameters")
    
    # Vector store (for SemanticMemory)
    vector_store: str | None = Field(default=None, description="Vector store: chroma, pinecone")
    embedding_model: str | None = Field(default=None, description="Embedding model reference")
    
    # Other parameters
    params: dict[str, Any] = Field(default_factory=dict, description="Other initialization parameters")


class KnowledgeConfig(BaseComponentConfig):
    """Knowledge component configuration."""
    
    type: Literal[ComponentType.KNOWLEDGE] = ComponentType.KNOWLEDGE
    
    # Implementation class path
    class_path: str = Field(description="Knowledge class path, e.g., 'agio.knowledge.vector_knowledge.VectorKnowledge'")
    
    # Vector store
    vector_store: str = Field(description="Vector store: chroma, pinecone, weaviate")
    embedding_model: str = Field(description="Embedding model reference")
    
    # Document processing
    chunk_size: int = Field(default=1000, ge=100, description="Text chunk size")
    chunk_overlap: int = Field(default=200, ge=0, description="Chunk overlap size")
    
    # Data source
    data_path: str | None = Field(default=None, description="Data directory path")
    
    # Retrieval parameters
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    
    # Other parameters
    params: dict[str, Any] = Field(default_factory=dict, description="Other initialization parameters")


class HookConfig(BaseComponentConfig):
    """Hook component configuration."""
    
    type: Literal[ComponentType.HOOK] = ComponentType.HOOK
    
    # Implementation class path
    class_path: str = Field(description="Hook class path, e.g., 'agio.hooks.logging.LoggingHook'")
    
    # Hook parameters
    params: dict[str, Any] = Field(default_factory=dict, description="Initialization parameters")


class RepositoryType(str, Enum):
    """Repository implementation type."""
    
    MONGODB = "mongodb"
    POSTGRES = "postgres"
    INMEMORY = "inmemory"
    CUSTOM = "custom"


class RepositoryConfig(BaseComponentConfig):
    """Repository component configuration."""
    
    type: Literal[ComponentType.REPOSITORY] = ComponentType.REPOSITORY
    
    # Repository type
    repository_type: RepositoryType = Field(description="Repository implementation type")
    
    # MongoDB configuration
    uri: str | None = Field(default=None, description="Database connection URI, supports ${ENV_VAR}")
    db_name: str = Field(default="agio", description="Database name")
    
    # PostgreSQL configuration
    postgres_url: str | None = Field(default=None, description="PostgreSQL connection URL")
    postgres_params: dict[str, Any] = Field(default_factory=dict, description="PostgreSQL parameters")
    
    # Custom repository
    custom_class: str | None = Field(default=None, description="Custom repository class path")
    custom_params: dict[str, Any] = Field(default_factory=dict, description="Custom repository parameters")
    
    @field_validator("uri", "postgres_url")
    @classmethod
    def resolve_env_vars(cls, v: str | None) -> str | None:
        """Resolve environment variable references."""
        if v and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v


class StorageType(str, Enum):
    """Storage backend type."""
    
    MEMORY = "memory"
    REDIS = "redis"
    POSTGRES = "postgres"
    CUSTOM = "custom"


class StorageConfig(BaseComponentConfig):
    """Storage backend configuration."""
    
    type: Literal[ComponentType.STORAGE] = ComponentType.STORAGE
    
    # Storage type
    storage_type: StorageType = Field(description="Storage backend type")
    
    # Redis configuration
    redis_url: str | None = Field(default=None, description="Redis connection URL, supports ${ENV_VAR}")
    redis_params: dict[str, Any] = Field(default_factory=dict, description="Redis client parameters")
    
    # PostgreSQL configuration
    postgres_url: str | None = Field(default=None, description="PostgreSQL connection URL")
    postgres_params: dict[str, Any] = Field(default_factory=dict, description="PostgreSQL parameters")
    
    # Custom storage
    custom_class: str | None = Field(default=None, description="Custom storage class path")
    custom_params: dict[str, Any] = Field(default_factory=dict, description="Custom storage parameters")
    
    @field_validator("redis_url", "postgres_url")
    @classmethod
    def resolve_env_vars(cls, v: str | None) -> str | None:
        """Resolve environment variable references."""
        if v and v.startswith("${") and v.endswith("}"):
            env_var = v[2:-1]
            return os.getenv(env_var)
        return v
