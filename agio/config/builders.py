"""Component builders for configuration system."""

import importlib
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agio.config.exceptions import ComponentBuildError
from agio.config.schema import (
    AgentConfig,
    KnowledgeConfig,
    MemoryConfig,
    ModelConfig,
    RepositoryConfig,
    StorageConfig,
    ToolConfig,
)


class ComponentBuilder(ABC):
    """Base class for component builders."""

    @abstractmethod
    async def build(self, config: BaseModel, dependencies: dict[str, Any]) -> Any:
        """
        Build a component instance from configuration.
        
        Args:
            config: Component configuration
            dependencies: Resolved dependencies
        
        Returns:
            Component instance
        """
        pass

    async def cleanup(self, instance: Any) -> None:
        """
        Cleanup component resources.
        
        Args:
            instance: Component instance to cleanup
        """
        if hasattr(instance, "cleanup"):
            await instance.cleanup()


class ModelBuilder(ComponentBuilder):
    """Builder for model components."""

    async def build(self, config: ModelConfig, dependencies: dict[str, Any]) -> Any:
        """Build model instance."""
        try:
            if config.provider == "openai":
                from agio.providers.llm import OpenAIModel

                return OpenAIModel(
                    id=f"{config.provider}/{config.model_name}",
                    name=config.name,
                    api_key=config.api_key,
                    model_name=config.model_name,
                    base_url=config.base_url,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

            elif config.provider == "anthropic":
                from agio.providers.llm import AnthropicModel

                return AnthropicModel(
                    id=f"{config.provider}/{config.model_name}",
                    name=config.name,
                    api_key=config.api_key,
                    model_name=config.model_name,
                    base_url=config.base_url,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

            elif config.provider == "deepseek":
                from agio.providers.llm import DeepseekModel

                return DeepseekModel(
                    id=f"{config.provider}/{config.model_name}",
                    name=config.name,
                    api_key=config.api_key,
                    model_name=config.model_name,
                    base_url=config.base_url,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

            else:
                raise ComponentBuildError(f"Unknown model provider: {config.provider}")

        except Exception as e:
            raise ComponentBuildError(f"Failed to build model {config.name}: {e}")


class ToolBuilder(ComponentBuilder):
    """Builder for tool components."""

    async def build(self, config: ToolConfig, dependencies: dict[str, Any]) -> Any:
        """
        Build tool instance with dependency injection.
        
        Supports two modes:
        1. Built-in tools: Use `tool_name` to reference registered tools
        2. Custom tools: Use `module` and `class_name` for dynamic import
        """
        try:
            # Get tool class
            tool_class = self._get_tool_class(config)

            # Merge parameters: config.params + resolved dependencies
            kwargs = {**config.effective_params}
            
            # Resolve dependencies: map param names to resolved instances
            # dependencies dict is keyed by param_name, not dep_name
            for param_name, dep_name in config.effective_dependencies.items():
                if param_name not in dependencies:
                    raise ComponentBuildError(
                        f"Dependency '{dep_name}' (param: {param_name}) not found for tool '{config.name}'"
                    )
                kwargs[param_name] = dependencies[param_name]

            # Filter kwargs to only include valid parameters
            kwargs = self._filter_valid_params(tool_class, kwargs)

            # Instantiate with merged params
            return tool_class(**kwargs)

        except ComponentBuildError:
            raise
        except Exception as e:
            raise ComponentBuildError(f"Failed to build tool {config.name}: {e}")
    
    def _get_tool_class(self, config: ToolConfig) -> type:
        """Get tool class from config."""
        # Mode 1: Built-in tool by name
        if config.tool_name:
            from agio.providers.tools import get_tool_registry
            registry = get_tool_registry()
            
            if not registry.is_registered(config.tool_name):
                raise ComponentBuildError(
                    f"Tool '{config.tool_name}' not found in registry. "
                    f"Available tools: {registry.list_available()}"
                )
            return registry.get_tool_class(config.tool_name)
        
        # Mode 2: Custom tool by module/class
        if config.module and config.class_name:
            module = importlib.import_module(config.module)
            return getattr(module, config.class_name)
        
        # Mode 3: Infer from config name (backward compatibility)
        # If name matches a built-in tool, use it
        from agio.components.tools.registry import get_tool_registry
        registry = get_tool_registry()
        if registry.is_registered(config.name):
            return registry.get_tool_class(config.name)
        
        raise ComponentBuildError(
            f"Tool config '{config.name}' must specify either 'tool_name' "
            f"(for built-in tools) or 'module' + 'class_name' (for custom tools)"
        )
    
    def _filter_valid_params(self, tool_class: type, kwargs: dict) -> dict:
        """Filter kwargs to only include parameters accepted by the tool class."""
        import inspect
        sig = inspect.signature(tool_class.__init__)
        valid_params = {}
        
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD 
            for p in sig.parameters.values()
        )
        
        for key, value in kwargs.items():
            if key in sig.parameters or has_var_keyword:
                valid_params[key] = value
        
        return valid_params


class MemoryBuilder(ComponentBuilder):
    """Builder for memory components."""

    async def build(self, config: MemoryConfig, dependencies: dict[str, Any]) -> Any:
        """Build memory instance."""
        try:
            if config.backend == "redis":
                from agio.components.memory.redis import RedisMemory

                return RedisMemory(**config.params)

            elif config.backend == "inmemory":
                from agio.components.memory.base import InMemoryMemory

                return InMemoryMemory(**config.params)

            else:
                raise ComponentBuildError(f"Unknown memory backend: {config.backend}")

        except Exception as e:
            raise ComponentBuildError(f"Failed to build memory {config.name}: {e}")


class KnowledgeBuilder(ComponentBuilder):
    """Builder for knowledge components."""

    async def build(
        self, config: KnowledgeConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build knowledge instance."""
        try:
            if config.backend == "chroma":
                from agio.components.knowledge.chroma import ChromaKnowledge

                return ChromaKnowledge(**config.params)

            elif config.backend == "pinecone":
                from agio.components.knowledge.pinecone import PineconeKnowledge

                return PineconeKnowledge(**config.params)

            else:
                raise ComponentBuildError(
                    f"Unknown knowledge backend: {config.backend}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build knowledge {config.name}: {e}")


class StorageBuilder(ComponentBuilder):
    """Builder for storage components."""

    async def build(self, config: StorageConfig, dependencies: dict[str, Any]) -> Any:
        """Build storage instance."""
        try:
            if config.storage_type == "redis":
                from agio.components.memory.storage.redis import RedisStorage

                storage = RedisStorage(
                    redis_url=config.redis_url, **config.redis_params
                )

                # Initialize connection
                if hasattr(storage, "connect"):
                    await storage.connect()

                return storage

            elif config.storage_type == "inmemory":
                from agio.components.memory.storage.memory import InMemoryStorage

                return InMemoryStorage()

            else:
                raise ComponentBuildError(
                    f"Unknown storage type: {config.storage_type}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build storage {config.name}: {e}")

    async def cleanup(self, instance: Any) -> None:
        """Cleanup storage resources."""
        if hasattr(instance, "disconnect"):
            await instance.disconnect()


class RepositoryBuilder(ComponentBuilder):
    """Builder for repository components."""

    async def build(
        self, config: RepositoryConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build repository instance."""
        try:
            if config.repository_type == "mongodb":
                from agio.providers.storage import MongoRepository

                repo = MongoRepository(
                    uri=config.mongo_uri, db_name=config.mongo_db_name
                )

                # Initialize connection
                if hasattr(repo, "connect"):
                    await repo.connect()

                return repo

            elif config.repository_type == "inmemory":
                from agio.providers.storage import InMemoryRepository

                return InMemoryRepository()

            else:
                raise ComponentBuildError(
                    f"Unknown repository type: {config.repository_type}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build repository {config.name}: {e}")

    async def cleanup(self, instance: Any) -> None:
        """Cleanup repository resources."""
        if hasattr(instance, "disconnect"):
            await instance.disconnect()


class AgentBuilder(ComponentBuilder):
    """Builder for agent components."""

    async def build(self, config: AgentConfig, dependencies: dict[str, Any]) -> Any:
        """Build agent instance."""
        try:
            from agio.agent import Agent

            # Build kwargs from dependencies
            kwargs = {
                "name": config.name,
                "model": dependencies["model"],
                "tools": dependencies.get("tools", []),
                "system_prompt": config.system_prompt,
                "user_id": config.user_id,
            }

            # Add optional dependencies
            if "memory" in dependencies:
                kwargs["memory"] = dependencies["memory"]

            if "knowledge" in dependencies:
                kwargs["knowledge"] = dependencies["knowledge"]

            if "repository" in dependencies:
                kwargs["repository"] = dependencies["repository"]

            return Agent(**kwargs)

        except Exception as e:
            raise ComponentBuildError(f"Failed to build agent {config.name}: {e}")
