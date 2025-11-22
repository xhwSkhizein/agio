"""
Component factory for creating component instances from configurations.

This module provides the ComponentFactory class which creates actual component
instances based on their configuration models.
"""

from agio.registry.base import ComponentRegistry
from typing import Any
from importlib import import_module
from .models import (
    BaseComponentConfig,
    ModelConfig,
    AgentConfig,
    ToolConfig,
    MemoryConfig,
    KnowledgeConfig,
    HookConfig,
    RepositoryConfig,
    StorageConfig,
)


class ComponentFactory:
    """
    Component Factory.

    Responsibilities:
    1. Create component instances from configurations
    2. Resolve component references
    3. Handle dependency injection
    """

    def __init__(self, registry: ComponentRegistry):
        self.registry: ComponentRegistry = registry

    def create(self, config: BaseComponentConfig) -> Any:
        """Create a component from its configuration."""
        if isinstance(config, ModelConfig):
            return self.create_model(config)
        elif isinstance(config, AgentConfig):
            return self.create_agent(config)
        elif isinstance(config, ToolConfig):
            return self.create_tool(config)
        elif isinstance(config, MemoryConfig):
            return self.create_memory(config)
        elif isinstance(config, KnowledgeConfig):
            return self.create_knowledge(config)
        elif isinstance(config, HookConfig):
            return self.create_hook(config)
        elif isinstance(config, RepositoryConfig):
            return self.create_repository(config)
        elif isinstance(config, StorageConfig):
            return self.create_storage(config)
        else:
            raise ValueError(f"Unsupported config type: {type(config)}")

    def create_model(self, config: ModelConfig) -> Any:
        """Create a Model instance."""
        if config.provider == "custom":
            # Custom Model
            model_class = self._import_class(config.custom_class)
            return model_class(
                id=f"{config.provider}/{config.model}",
                name=config.name,
                **config.custom_params,
            )

        # Built-in Model
        provider_map = {
            "openai": "agio.models.openai.OpenAIModel",
            "deepseek": "agio.models.deepseek.DeepSeekModel",
            "anthropic": "agio.models.anthropic.AnthropicModel",
        }

        model_class_path = provider_map.get(config.provider)
        if not model_class_path:
            raise ValueError(f"Unsupported provider: {config.provider}")

        model_class = self._import_class(model_class_path)

        return model_class(
            id=f"{config.provider}/{config.model}",
            name=config.name,
            model=config.model,
            api_key=config.api_key,
            base_url=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )

    def create_agent(self, config: AgentConfig) -> Any:
        """Create an Agent instance."""
        from agio.agent.base import Agent
        from agio.utils.logging import get_logger
        
        logger = get_logger(__name__)

        # Resolve Model reference
        model = self._resolve_reference(config.model)

        # Resolve Tools references
        tools = [self._resolve_reference(tool_ref) for tool_ref in config.tools]

        # Resolve Memory reference
        memory = None
        if config.memory:
            memory = self._resolve_reference(config.memory)

        # Resolve Knowledge reference
        knowledge = None
        if config.knowledge:
            knowledge = self._resolve_reference(config.knowledge)

        # Load system prompt
        system_prompt = config.system_prompt
        if config.system_prompt_file:
            from pathlib import Path
            system_prompt = Path(config.system_prompt_file).read_text()

        # Resolve Repository reference (no fallback - must be explicitly configured)
        repository = None
        if config.repository:
            repository = self._resolve_reference(config.repository)
        else:
            logger.warning(
                "agent_no_repository",
                agent=config.name,
                message="Agent created without repository - runs will not be persisted"
            )
        
        # Resolve Storage reference
        storage = None
        if config.storage:
            storage = self._resolve_reference(config.storage)
        
        # Resolve Hooks references
        hooks = []
        if config.hooks:
            hooks = [self._resolve_reference(hook_ref) for hook_ref in config.hooks]

        return Agent(
            model=model,
            tools=tools,
            memory=memory,
            knowledge=knowledge,
            repository=repository,
            storage=storage,
            hooks=hooks,
            name=config.name,
            system_prompt=system_prompt,
        )

    def create_tool(self, config: ToolConfig) -> Any:
        """Create a Tool instance."""
        if config.tool_type == "function":
            # Function Tool
            func = self._import_function(config.function_path)
            from agio.tools import tool

            return tool(func)

        elif config.tool_type == "class":
            # Class Tool
            tool_class = self._import_class(config.class_path)
            return tool_class(**config.class_params)

        elif config.tool_type == "mcp":
            # MCP Tool
            from agio.tools.mcp import MCPTool

            return MCPTool.from_server(config.mcp_server, config.mcp_tool_name)

        raise ValueError(f"Unsupported tool_type: {config.tool_type}")

    def create_memory(self, config: MemoryConfig) -> Any:
        """Create a Memory instance."""
        memory_class = self._import_class(config.class_path)

        # Resolve embedding_model reference if present
        embedding_model = None
        if config.embedding_model:
            embedding_model = self._resolve_reference(config.embedding_model)

        return memory_class(
            max_history_length=config.max_history_length,
            max_tokens=config.max_tokens,
            storage_backend=config.storage_backend,
            storage_params=config.storage_params,
            vector_store=config.vector_store,
            embedding_model=embedding_model,
            **config.params,
        )

    def create_knowledge(self, config: KnowledgeConfig) -> Any:
        """Create a Knowledge instance."""
        knowledge_class = self._import_class(config.class_path)

        # Resolve embedding_model reference
        embedding_model = self._resolve_reference(config.embedding_model)

        # Filter out params that are already passed explicitly
        params = config.params.copy()
        explicit_args = [
            "vector_store",
            "embedding_model",
            "chunk_size",
            "chunk_overlap",
            "data_path",
            "similarity_threshold",
        ]
        for arg in explicit_args:
            params.pop(arg, None)

        return knowledge_class(
            vector_store=config.vector_store,
            embedding_model=embedding_model,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            data_path=config.data_path,
            similarity_threshold=config.similarity_threshold,
            **params,
        )

    def create_hook(self, config: HookConfig) -> Any:
        """Create a Hook instance."""
        hook_class = self._import_class(config.class_path)
        return hook_class(**config.params)
    
    def create_repository(self, config: RepositoryConfig) -> Any:
        """Create a Repository instance."""
        import os
        from .models import RepositoryType
        
        if config.repository_type == RepositoryType.MONGODB:
            from agio.db.mongo import MongoDBRepository
            
            # Resolve URI with priority: config > env var > default
            uri = config.uri or os.getenv("AGIO_MONGO_URI") or os.getenv("MONGO_URI", "mongodb://localhost:27017")
            db_name = config.db_name or os.getenv("AGIO_MONGO_DB_NAME", "agio")
            
            return MongoDBRepository(uri=uri, db_name=db_name)
        
        elif config.repository_type == RepositoryType.INMEMORY:
            from agio.db.repository import InMemoryRepository
            return InMemoryRepository()
        
        elif config.repository_type == RepositoryType.POSTGRES:
            # TODO: Implement PostgreSQL repository
            raise NotImplementedError("PostgreSQL repository not yet implemented")
        
        elif config.repository_type == RepositoryType.CUSTOM:
            if not config.custom_class:
                raise ValueError("custom_class is required for custom repository")
            repo_class = self._import_class(config.custom_class)
            return repo_class(**config.custom_params)
        
        else:
            raise ValueError(f"Unsupported repository_type: {config.repository_type}")
    
    def create_storage(self, config: StorageConfig) -> Any:
        """Create a Storage instance."""
        import os
        from .models import StorageType
        
        if config.storage_type == StorageType.MEMORY:
            from agio.db.base import InMemoryStorage
            return InMemoryStorage()
        
        elif config.storage_type == StorageType.REDIS:
            from agio.db.base import RedisStorage
            redis_url = config.redis_url or os.getenv("AGIO_REDIS_URL")
            if not redis_url:
                raise ValueError("redis_url must be provided in config or AGIO_REDIS_URL env var")
            return RedisStorage(url=redis_url, **config.redis_params)
        
        elif config.storage_type == StorageType.POSTGRES:
            # TODO: Implement PostgreSQL storage
            raise NotImplementedError("PostgreSQL storage not yet implemented")
        
        elif config.storage_type == StorageType.CUSTOM:
            if not config.custom_class:
                raise ValueError("custom_class is required for custom storage")
            storage_class = self._import_class(config.custom_class)
            return storage_class(**config.custom_params)
        
        else:
            raise ValueError(f"Unsupported storage_type: {config.storage_type}")

    def _resolve_reference(self, ref: str) -> Any:
        """Resolve a component reference."""
        # Support two formats:
        # 1. Direct name: "gpt4"
        # 2. Explicit reference: "ref:gpt4"

        if ref.startswith("ref:"):
            ref = ref[4:]

        component = self.registry.get(ref)
        if component is None:
            raise ValueError(f"Component '{ref}' not found in registry")

        return component

    def _import_class(self, class_path: str) -> type:
        """Dynamically import a class."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = import_module(module_path)
        return getattr(module, class_name)

    def _import_function(self, func_path: str):
        """Dynamically import a function."""
        module_path, func_name = func_path.rsplit(".", 1)
        module = import_module(module_path)
        return getattr(module, func_name)
