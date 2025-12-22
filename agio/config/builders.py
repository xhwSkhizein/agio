"""Component builders for configuration system."""

import importlib
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agio.config.exceptions import ComponentBuildError
from agio.config.schema import (
    AgentConfig,
    CitationStoreConfig,
    KnowledgeConfig,
    MemoryConfig,
    ModelConfig,
    SessionStoreConfig,
    ToolConfig,
    TraceStoreConfig,
    WorkflowConfig,
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
        """Build model instance using ModelProviderRegistry."""
        try:
            from agio.config.model_provider_registry import get_model_provider_registry

            registry = get_model_provider_registry()
            return registry.create_model(config)

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


class SessionStoreBuilder(ComponentBuilder):
    """Builder for session store components (stores Run and Step data)."""

    async def build(
        self, config: SessionStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build session store instance."""
        try:
            if config.store_type == "mongodb":
                from agio.providers.storage import MongoSessionStore

                store = MongoSessionStore(
                    uri=config.mongo_uri, db_name=config.mongo_db_name
                )

                # Initialize connection
                if hasattr(store, "connect"):
                    await store.connect()

                return store

            elif config.store_type == "inmemory":
                from agio.providers.storage import InMemorySessionStore

                return InMemorySessionStore()

            else:
                raise ComponentBuildError(
                    f"Unknown session store type: {config.store_type}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build session_store {config.name}: {e}")

    async def cleanup(self, instance: Any) -> None:
        """Cleanup session store resources."""
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
                "max_steps": config.max_steps,
                "enable_termination_summary": config.enable_termination_summary,
                "termination_summary_prompt": config.termination_summary_prompt,
            }

            # Add optional dependencies
            if "memory" in dependencies:
                kwargs["memory"] = dependencies["memory"]

            if "knowledge" in dependencies:
                kwargs["knowledge"] = dependencies["knowledge"]

            if "session_store" in dependencies:
                kwargs["session_store"] = dependencies["session_store"]

            return Agent(**kwargs)

        except Exception as e:
            raise ComponentBuildError(f"Failed to build agent {config.name}: {e}")


class WorkflowBuilder(ComponentBuilder):
    """Builder for workflow components."""

    async def build(
        self, config: WorkflowConfig, dependencies: dict[str, Any]
    ) -> Any:
        """
        Build workflow instance.

        Dependencies:
            - _all_instances: dict of all component instances (agents, etc.)
        """
        try:
            from agio.workflow import (
                LoopWorkflow,
                ParallelWorkflow,
                PipelineWorkflow,
            )
            from agio.workflow.node import WorkflowNode

            # Get all instances as registry (passed from ConfigSystem)
            registry = dependencies.get("_all_instances", {})

            # Get session_store from dependencies (resolved by ConfigSystem)
            session_store = dependencies.get("session_store")

            # Build stages
            stages = []
            for stage_config in config.stages:
                # Handle inline workflow config
                runnable_ref = stage_config.runnable
                if isinstance(runnable_ref, dict):
                    # Recursively build nested workflow
                    # Inherit session_store from parent if not specified
                    nested_config_dict = dict(runnable_ref)
                    if "session_store" not in nested_config_dict and config.session_store:
                        nested_config_dict["session_store"] = config.session_store

                    nested_config = WorkflowConfig(
                        name=nested_config_dict.get("id", f"{config.name}_nested"),
                        **nested_config_dict,
                    )
                    nested_workflow = await self.build(nested_config, dependencies)
                    registry[nested_workflow.id] = nested_workflow
                    runnable_ref = nested_workflow.id

                stages.append(
                    WorkflowNode(
                        id=stage_config.id,
                        runnable=runnable_ref,
                        input_template=stage_config.input,
                        condition=stage_config.condition,
                    )
                )

            # Build workflow based on type
            if config.workflow_type == "pipeline":
                workflow = PipelineWorkflow(
                    id=config.name,
                    stages=stages,
                    session_store=session_store,
                )
            elif config.workflow_type == "loop":
                workflow = LoopWorkflow(
                    id=config.name,
                    stages=stages,
                    condition=config.condition or "true",
                    max_iterations=config.max_iterations,
                    session_store=session_store,
                )
            elif config.workflow_type == "parallel":
                workflow = ParallelWorkflow(
                    id=config.name,
                    stages=stages,
                    merge_template=config.merge_template,
                    session_store=session_store,
                )
            else:
                raise ComponentBuildError(
                    f"Unknown workflow type: {config.workflow_type}"
                )

            # Set registry so workflow can resolve runnable references
            workflow.set_registry(registry)

            return workflow

        except Exception as e:
            raise ComponentBuildError(f"Failed to build workflow {config.name}: {e}")


class TraceStoreBuilder(ComponentBuilder):
    """Builder for TraceStore components."""

    async def build(self, config: TraceStoreConfig, dependencies: dict[str, Any]) -> Any:
        """Build TraceStore instance."""
        from agio.observability.trace_store import TraceStore

        try:
            store = TraceStore(
                mongo_uri=config.mongo_uri,
                db_name=config.mongo_db_name,
                buffer_size=config.buffer_size,
            )
            
            # Initialize MongoDB connection
            await store.initialize()
            
            return store

        except Exception as e:
            raise ComponentBuildError(f"Failed to build trace_store {config.name}: {e}")


class CitationStoreBuilder(ComponentBuilder):
    """Builder for CitationStore components."""

    async def build(self, config: CitationStoreConfig, dependencies: dict[str, Any]) -> Any:
        """Build CitationStore instance."""
        try:
            if config.store_type == "mongodb":
                from agio.providers.tools.builtin.common.citation import MongoCitationStore

                store = MongoCitationStore(
                    uri=config.mongo_uri,
                    db_name=config.mongo_db_name,
                )
                
                # Initialize connection
                await store._ensure_connection()
                
                return store

            elif config.store_type == "inmemory":
                from agio.providers.tools.builtin.common.citation import InMemoryCitationStore

                return InMemoryCitationStore()

            else:
                raise ComponentBuildError(
                    f"Unknown citation store type: {config.store_type}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build citation_store {config.name}: {e}")

    async def cleanup(self, instance: Any) -> None:
        """Cleanup citation store resources."""
        if hasattr(instance, "disconnect"):
            await instance.disconnect()
