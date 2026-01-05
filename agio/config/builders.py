"""Component builders for configuration system."""

import importlib
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agio.config.exceptions import ComponentBuildError
from agio.config.schema import (
    AgentConfig,
    CitationStoreConfig,
    ModelConfig,
    SessionStoreConfig,
    ToolConfig,
    TraceStoreConfig,
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
            import inspect
            from pathlib import Path

            # Get tool class
            tool_class = self._get_tool_class(config)

            # Merge parameters: config.params + resolved dependencies
            kwargs = {**config.effective_params}

            # Check if tool needs config object
            sig = inspect.signature(tool_class.__init__)
            if "config" in sig.parameters:
                # Build config object from params
                config_obj = self._build_config_object(
                    config.tool_name or config.name, kwargs
                )
                if config_obj:
                    kwargs["config"] = config_obj
                    # Remove config params from kwargs (they're now in config object)
                    config_params = self._get_config_params(
                        config.tool_name or config.name
                    )
                    kwargs = {k: v for k, v in kwargs.items() if k not in config_params}

            # Handle project_root parameter
            if "project_root" in sig.parameters and "project_root" not in kwargs:
                kwargs["project_root"] = Path.cwd()

            # Resolve dependencies: map param names to resolved instances
            # dependencies dict is keyed by param_name, not dep_name
            for param_name, dep_name in config.effective_dependencies.items():
                if param_name not in dependencies:
                    raise ComponentBuildError(
                        f"Dependency '{dep_name}' (param: {param_name}) "
                        f"not found for tool '{config.name}'"
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
            from agio.tools import get_tool_registry

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
        from agio.tools import get_tool_registry

        registry = get_tool_registry()
        if registry.is_registered(config.name):
            return registry.get_tool_class(config.name)

        raise ComponentBuildError(
            f"Tool config '{config.name}' must specify either 'tool_name' "
            f"(for built-in tools) or 'module' + 'class_name' (for custom tools)"
        )

    def _build_config_object(self, tool_name: str, params: dict) -> Any:
        """Build config object from params based on tool name."""
        from agio.tools.builtin.config import (
            BashConfig,
            FileEditConfig,
            FileReadConfig,
            FileWriteConfig,
            GlobConfig,
            GrepConfig,
            LSConfig,
            WebFetchConfig,
            WebSearchConfig,
            create_config_from_dict,
        )

        config_map = {
            "file_read": FileReadConfig,
            "file_write": FileWriteConfig,
            "file_edit": FileEditConfig,
            "grep": GrepConfig,
            "glob": GlobConfig,
            "ls": LSConfig,
            "bash": BashConfig,
            "web_search": WebSearchConfig,
            "web_fetch": WebFetchConfig,
        }

        config_class = config_map.get(tool_name)
        if config_class:
            return create_config_from_dict(config_class, params)
        return None

    def _get_config_params(self, tool_name: str) -> set[str]:
        """Get config class parameter field names."""
        import dataclasses

        from agio.tools.builtin.config import (
            BashConfig,
            FileEditConfig,
            FileReadConfig,
            FileWriteConfig,
            GlobConfig,
            GrepConfig,
            LSConfig,
            WebFetchConfig,
            WebSearchConfig,
        )

        config_map = {
            "file_read": FileReadConfig,
            "file_write": FileWriteConfig,
            "file_edit": FileEditConfig,
            "grep": GrepConfig,
            "glob": GlobConfig,
            "ls": LSConfig,
            "bash": BashConfig,
            "web_search": WebSearchConfig,
            "web_fetch": WebFetchConfig,
        }

        config_class = config_map.get(tool_name)
        if config_class:
            return {f.name for f in dataclasses.fields(config_class)}
        return set()

    def _filter_valid_params(self, tool_class: type, kwargs: dict) -> dict:
        """Filter kwargs to only include parameters accepted by the tool class."""
        import inspect

        sig = inspect.signature(tool_class.__init__)
        valid_params = {}

        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

        for key, value in kwargs.items():
            if key in sig.parameters or has_var_keyword:
                valid_params[key] = value

        return valid_params


class SessionStoreBuilder(ComponentBuilder):
    """Builder for session store components (stores Run and Step data)."""

    async def build(
        self, config: SessionStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build session store instance."""
        try:
            backend = config.backend

            if backend.type == "mongodb":
                from agio.storage.session import MongoSessionStore

                store = MongoSessionStore(
                    uri=backend.uri,
                    db_name=backend.db_name,
                )

                # Initialize connection
                if hasattr(store, "connect"):
                    await store.connect()

                return store

            elif backend.type == "sqlite":
                from agio.storage.session import SQLiteSessionStore

                store = SQLiteSessionStore(
                    db_path=backend.db_path,
                )

                if hasattr(store, "connect"):
                    await store.connect()

                return store

            elif backend.type == "inmemory":
                from agio.storage.session import InMemorySessionStore

                return InMemorySessionStore()

            else:
                raise ComponentBuildError(
                    f"Unknown session store backend type: {backend.type}"
                )

        except Exception as e:
            raise ComponentBuildError(
                f"Failed to build session_store {config.name}: {e}"
            )

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

            if "session_store" in dependencies:
                kwargs["session_store"] = dependencies["session_store"]

            # Auto-inject PermissionManager if enabled
            if config.enable_permission:
                from agio.runtime.permission.factory import get_permission_manager

                kwargs["permission_manager"] = get_permission_manager()

            # Initialize skills if enabled
            if config.enable_skills:
                from pathlib import Path

                from agio.config.settings import settings
                from agio.skills.manager import SkillManager

                skill_dirs = config.skill_dirs or settings.skills_dirs
                skill_manager = SkillManager(
                    skill_dirs=[Path(d) for d in skill_dirs],
                )
                await skill_manager.initialize()

                # Add Skill tool to tools list
                skill_tool = skill_manager.get_skill_tool()
                kwargs["tools"].append(skill_tool)

                # Inject skill_manager through constructor
                kwargs["skill_manager"] = skill_manager

            return Agent(**kwargs)

        except Exception as e:
            raise ComponentBuildError(f"Failed to build agent {config.name}: {e}")


class TraceStoreBuilder(ComponentBuilder):
    """Builder for TraceStore components."""

    async def build(
        self, config: TraceStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build TraceStore instance."""
        from agio.storage.trace.store import TraceStore

        try:
            backend = config.backend

            if backend.type == "mongodb":
                store = TraceStore(
                    mongo_uri=backend.uri,
                    db_name=backend.db_name,
                    buffer_size=config.buffer_size,
                )

                # Initialize MongoDB connection
                await store.initialize()

                return store

            elif backend.type == "sqlite":
                from agio.storage.trace import SQLiteTraceStore

                store = SQLiteTraceStore(
                    db_path=backend.db_path,
                    buffer_size=config.buffer_size,
                )

                await store.initialize()

                return store

            elif backend.type == "inmemory":
                # TraceStore with in-memory only mode
                store = TraceStore(
                    mongo_uri=None,
                    db_name=None,
                    buffer_size=config.buffer_size,
                )

                await store.initialize()

                return store

            else:
                raise ComponentBuildError(
                    f"Unknown trace store backend type: {backend.type}"
                )

        except Exception as e:
            raise ComponentBuildError(f"Failed to build trace_store {config.name}: {e}")


class CitationStoreBuilder(ComponentBuilder):
    """Builder for CitationStore components."""

    async def build(
        self, config: CitationStoreConfig, dependencies: dict[str, Any]
    ) -> Any:
        """Build CitationStore instance."""
        try:
            backend = config.backend

            if backend.type == "mongodb":
                from agio.storage.citation import MongoCitationStore

                store = MongoCitationStore(
                    uri=backend.uri,
                    db_name=backend.db_name,
                )

                # Initialize connection
                await store._ensure_connection()

                return store

            elif backend.type == "sqlite":
                from agio.storage.citation import SQLiteCitationStore

                store = SQLiteCitationStore(
                    db_path=backend.db_path,
                )

                if hasattr(store, "connect"):
                    await store.connect()

                return store

            elif backend.type == "inmemory":
                from agio.storage.citation import InMemoryCitationStore

                return InMemoryCitationStore()

            else:
                raise ComponentBuildError(
                    f"Unknown citation store backend type: {backend.type}"
                )

        except Exception as e:
            raise ComponentBuildError(
                f"Failed to build citation_store {config.name}: {e}"
            )

    async def cleanup(self, instance: Any) -> None:
        """Cleanup citation store resources."""
        if hasattr(instance, "disconnect"):
            await instance.disconnect()
