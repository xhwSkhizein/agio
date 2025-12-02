"""
Unified configuration management for Agio.

This module consolidates all configuration classes:
- AgioSettings: Global settings from environment variables
- ExecutionConfig: Runtime execution configuration
- ComponentConfig: Dynamic component configuration
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# Global Settings (from environment variables)
# ============================================================================


class AgioSettings(BaseSettings):
    """
    Global configuration loaded from environment variables.

    Environment variables should be prefixed with AGIO_
    Example: AGIO_DEBUG=true, AGIO_MONGO_URI=mongodb://localhost:27017
    """

    model_config = SettingsConfigDict(
        env_prefix="AGIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # Core settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Storage settings
    mongo_uri: str | None = None
    mongo_db_name: str = "agio"

    # Vector DB settings
    vector_db_path: str | None = None

    # Repository and Storage settings
    default_repository: str = "mongodb_repo"
    default_storage: str = "inmemory_storage"

    # Model Provider Settings
    # OpenAI
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None

    # Deepseek
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"

    # Anthropic
    anthropic_api_key: SecretStr | None = None


# Global settings instance (singleton)
settings = AgioSettings()


# ============================================================================
# Runtime Execution Configuration
# ============================================================================


class ExecutionConfig(BaseModel):
    """
    Runtime execution configuration.

    This consolidates configuration from the old AgentRunConfig and
    ExecutionConfig to eliminate duplication.
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
    """
    Configuration for tool components.
    
    Supports two modes:
    1. Built-in tools: Just specify `tool_name` (e.g., "file_read", "grep")
    2. Custom tools: Specify `module` and `class_name`
    
    Example YAML configs:
    
    # Built-in tool with custom params
    type: tool
    name: my_grep
    tool_name: grep  # References built-in tool
    params:
      timeout_seconds: 60
      max_results: 500
    
    # Custom tool
    type: tool
    name: my_custom_tool
    module: myapp.tools.custom
    class_name: CustomTool
    params:
      api_key: ${MY_API_KEY}
    """

    type: Literal["tool"] = "tool"
    
    # For built-in tools: just specify the tool name
    tool_name: str | None = None
    
    # For custom tools: specify module and class
    module: str | None = None
    class_name: str | None = None
    
    # Tool configuration parameters (None is converted to empty dict)
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


class ComponentType(str, Enum):
    """Component types for configuration system."""

    MODEL = "model"
    TOOL = "tool"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    AGENT = "agent"
    STORAGE = "storage"
    REPOSITORY = "repository"


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
    tools: list[str] = Field(default_factory=list)  # References to tool config names
    memory: str | None = None  # Reference to memory config name
    knowledge: str | None = None  # Reference to knowledge config name
    repository: str | None = None  # Reference to repository config name

    system_prompt: str | None = None
    max_steps: int = 10
    enable_memory_update: bool = False
    user_id: str | None = None
    tags: list[str] = Field(default_factory=list)
