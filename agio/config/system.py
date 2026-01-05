"""
ConfigSystem - Configuration system facade/coordinator (refactored version).

Responsibilities:
- Coordinate work of all modules (Registry, Container, DependencyResolver, BuilderRegistry, HotReloadManager)
- Provide unified external interface
- Handle component building process
"""

import asyncio
import threading
from pathlib import Path
from typing import Any

from agio.config.builder_registry import BuilderRegistry
from agio.config.container import ComponentContainer, ComponentMetadata
from agio.config.dependency import DependencyResolver
from agio.config.exceptions import (
    ComponentBuildError,
    ComponentNotFoundError,
    ConfigNotFoundError,
)
from agio.config.hot_reload import HotReloadManager
from agio.config.loader import ConfigLoader
from agio.config.registry import ConfigRegistry
from agio.config.schema import (
    AgentConfig,
    CitationStoreConfig,
    ComponentConfig,
    ComponentType,
    ModelConfig,
    RunnableToolConfig,
    SessionStoreConfig,
    ToolConfig,
    TraceStoreConfig,
    WorkflowConfig,
)
from agio.config.tool_reference import parse_tool_reference
from agio.tools import get_tool_registry
from agio.utils.logging import get_logger
from agio.workflow import as_tool

logger = get_logger(__name__)


class ConfigSystem:
    """
    Configuration system facade - coordinates all modules.

    Architecture:
    - ConfigRegistry: Configuration storage
    - ComponentContainer: Instance management
    - DependencyResolver: Dependency resolution and topological sorting
    - BuilderRegistry: Builder management
    - HotReloadManager: Hot reload
    """

    CONFIG_CLASSES = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.SESSION_STORE: SessionStoreConfig,
        ComponentType.TRACE_STORE: TraceStoreConfig,
        ComponentType.CITATION_STORE: CitationStoreConfig,
        ComponentType.AGENT: AgentConfig,
        ComponentType.WORKFLOW: WorkflowConfig,
    }

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.registry = ConfigRegistry()
        self.container = ComponentContainer()
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(
            self.container, self.dependency_resolver, self.builder_registry
        )

    async def load_from_directory(self, config_dir: str | Path) -> dict[str, int]:
        """
        Load all configuration files from directory.

        Args:
            config_dir: Configuration file directory

        Returns:
            Loading statistics {"loaded": count, "failed": count}
        """
        logger.info(f"Loading configs from: {config_dir}")

        loader = ConfigLoader(config_dir)
        configs_by_type = await loader.load_all_configs()

        stats = {"loaded": 0, "failed": 0}

        all_config_dicts = []
        for configs in configs_by_type.values():
            all_config_dicts.extend(configs)

        async with self._lock:
            for config_dict in all_config_dicts:
                name = config_dict.get("name", "unknown")
                try:
                    config = self._parse_config(config_dict)
                    self.registry.register(config)
                    logger.info(f"Loaded config: {config.type}/{config.name}")
                    stats["loaded"] += 1
                except Exception as e:
                    logger.error(f"Failed to parse config {name}: {e}")
                    stats["failed"] += 1

        logger.info(f"Config loading completed: {stats}")
        return stats

    def _parse_config(self, config_dict: dict) -> ComponentConfig:
        """Parse config dictionary to Pydantic model."""
        component_type = ComponentType(config_dict["type"])
        config_class = self.CONFIG_CLASSES.get(component_type)

        if not config_class:
            raise ConfigNotFoundError(f"Unknown component type: {component_type}")

        return config_class(**config_dict)

    async def save_config(self, config: ComponentConfig) -> None:
        """
        Save configuration (triggers hot reload).

        Args:
            config: Component configuration
        """
        component_type = ComponentType(config.type)
        name = config.name

        async with self._lock:
            is_update = self.registry.has(component_type, name)

            self.registry.register(config)
            logger.info(f"Config saved: {component_type.value}/{name}")

            if is_update and self.container.has(name):
                await self.hot_reload.handle_change(
                    name, "update", lambda n: self._build_by_name(n)
                )
            else:
                await self._build_component(config)
                self.hot_reload._notify_callbacks(name, "create")

    async def delete_config(self, component_type: ComponentType, name: str) -> None:
        """
        Delete configuration.

        Args:
            component_type: Component type
            name: Component name
        """
        async with self._lock:
            if not self.registry.has(component_type, name):
                raise ConfigNotFoundError(f"Config {component_type.value}/{name} not found")

            await self.hot_reload.handle_change(name, "delete", None)

            self.registry.remove(component_type, name)
            logger.info(f"Config deleted: {component_type.value}/{name}")

    def get_config(self, component_type: ComponentType, name: str) -> dict | None:
        """Get configuration (returns dict format for backward compatibility)."""
        config = self.registry.get(component_type, name)
        return config.model_dump(exclude_none=True) if config else None

    def list_configs(self, component_type: ComponentType | None = None) -> list[dict]:
        """List configurations (returns dict list for backward compatibility)."""
        if component_type is None:
            configs = self.registry.list_all()
        else:
            configs = self.registry.list_by_type(component_type)
        # Use model_dump with exclude_none=False to ensure all fields are included
        return [config.model_dump(exclude_none=True) for config in configs]

    async def build_all(self) -> dict[str, int]:
        """
        Build all components in dependency order.

        Returns:
            Build statistics {"built": count, "failed": count}
        """
        logger.info("Building all components...")

        async with self._lock:
            configs = self.registry.list_all()
            available_names = self.registry.get_all_names()

            sorted_configs = self.dependency_resolver.topological_sort(configs, available_names)

            stats = {"built": 0, "failed": 0}

            for config in sorted_configs:
                if self.container.has(config.name):
                    continue

                try:
                    await self._build_component(config)
                    stats["built"] += 1
                except Exception as e:
                    logger.exception(f"Failed to build {config.type}/{config.name}: {e}")
                    stats["failed"] += 1

        logger.info(f"Build completed: {stats}")
        return stats

    async def rebuild(self, name: str) -> None:
        """
        Rebuild single component and its dependents.

        Args:
            name: Component name
        """
        async with self._lock:
            await self.hot_reload.handle_change(
                name, "update", lambda n: self._build_by_name(n)
            )

    def get(self, name: str) -> Any:
        """Get component instance."""
        return self.container.get(name)

    def get_or_none(self, name: str) -> Any | None:
        """Get component instance (returns None if not found)."""
        return self.container.get_or_none(name)

    def get_instance(self, name: str) -> Any:
        """Get component instance (alias for get)."""
        return self.get(name)

    def get_all_instances(self) -> dict[str, Any]:
        """Get all component instances."""
        return self.container.get_all_instances()

    def list_components(self) -> list[dict]:
        """List all built components."""
        result = []
        for name in self.container.list_names():
            metadata = self.container.get_metadata(name)
            if metadata:
                result.append(
                    {
                        "name": name,
                        "type": metadata.component_type.value,
                        "dependencies": metadata.dependencies,
                        "created_at": metadata.created_at.isoformat(),
                    }
                )
        return result

    def get_component_info(self, name: str) -> dict | None:
        """Get component detailed information."""
        if not self.container.has(name):
            return None

        metadata = self.container.get_metadata(name)
        if not metadata:
            return None

        return {
            "name": name,
            "type": metadata.component_type.value,
            "config": metadata.config.model_dump(exclude_none=True),
            "dependencies": metadata.dependencies,
            "created_at": metadata.created_at.isoformat(),
        }

    def on_change(self, callback) -> None:
        """Register configuration change callback."""
        self.hot_reload.register_callback(callback)

    async def _build_component(self, config: ComponentConfig) -> Any:
        """Build single component."""
        dependencies = await self._resolve_dependencies(config)

        component_type = ComponentType(config.type)
        builder = self.builder_registry.get(component_type)
        if not builder:
            raise ComponentBuildError(f"No builder for type: {component_type}")

        instance = await builder.build(config, dependencies)

        metadata = ComponentMetadata(
            component_type=component_type,
            config=config,
            dependencies=list(dependencies.keys()),
        )
        self.container.register(config.name, instance, metadata)

        logger.info(f"Component built: {component_type.value}/{config.name}")
        return instance

    async def _build_by_name(self, name: str) -> Any:
        """Build component by name (for hot reload)."""
        for config in self.registry.list_all():
            if config.name == name:
                return await self._build_component(config)

        raise ConfigNotFoundError(f"Config for component '{name}' not found")

    async def _resolve_dependencies(self, config: ComponentConfig) -> dict[str, Any]:
        """Resolve component dependencies."""
        if isinstance(config, AgentConfig):
            return await self._resolve_agent_dependencies(config)
        elif isinstance(config, ToolConfig):
            return await self._resolve_tool_dependencies(config)
        elif isinstance(config, WorkflowConfig):
            return await self._resolve_workflow_dependencies(config)
        return {}

    async def _resolve_agent_dependencies(self, config: AgentConfig) -> dict[str, Any]:
        """Resolve Agent dependencies."""
        dependencies = {}

        dependencies["model"] = self.container.get(config.model)

        tools = []
        for tool_ref in config.tools:
            tool = await self._resolve_tool_reference(
                tool_ref,
                current_component=config.name,
                session_store_name=config.session_store,
            )
            tools.append(tool)
        dependencies["tools"] = tools

        if config.memory:
            dependencies["memory"] = self.container.get(config.memory)

        if config.knowledge:
            dependencies["knowledge"] = self.container.get(config.knowledge)

        if config.session_store:
            dependencies["session_store"] = self.container.get(config.session_store)

        return dependencies

    async def _resolve_tool_dependencies(self, config: ToolConfig) -> dict[str, Any]:
        """Resolve Tool dependencies."""
        dependencies = {}
        for param_name, dep_name in config.effective_dependencies.items():
            dependencies[param_name] = self.container.get(dep_name)
        return dependencies

    async def _resolve_workflow_dependencies(self, config: WorkflowConfig) -> dict[str, Any]:
        """Resolve Workflow dependencies."""
        dependencies = {}

        dependencies["_all_instances"] = self.container.get_all_instances()

        if config.session_store:
            dependencies["session_store"] = self.container.get(config.session_store)

        return dependencies

    async def _resolve_tool_reference(
        self,
        tool_ref: str | dict | RunnableToolConfig,
        current_component: str | None = None,
        session_store_name: str | None = None,
    ) -> Any:
        """Resolve tool reference."""
        if isinstance(tool_ref, str):
            return await self._get_or_create_tool(tool_ref)

        if isinstance(tool_ref, RunnableToolConfig):
            parsed = parse_tool_reference(tool_ref.model_dump(exclude_none=True))
        elif isinstance(tool_ref, dict):
            parsed = parse_tool_reference(tool_ref)
        else:
            raise ComponentBuildError(f"Invalid tool reference type: {type(tool_ref)}")

        if parsed.type in ("agent_tool", "workflow_tool"):
            return await self._create_runnable_tool(
                parsed.type, parsed.raw, current_component, session_store_name
            )

        raise ComponentBuildError(
            f"Unknown tool reference format: {tool_ref}. "
            f"Expected string or dict with type='agent_tool'/'workflow_tool'"
        )

    async def _create_runnable_tool(
        self,
        tool_type: str,
        config: dict,
        current_component: str | None = None,
        session_store_name: str | None = None,
    ) -> Any:
        """Create RunnableTool."""
        id_field = "agent" if tool_type == "agent_tool" else "workflow"
        runnable_id = config.get(id_field)
        if not runnable_id:
            raise ComponentBuildError(f"{tool_type} config missing '{id_field}' field")

        if current_component and runnable_id == current_component:
            raise ComponentBuildError(
                f"Self-reference detected: '{current_component}' cannot use itself as a tool."
            )

        session_store = (
            self.container.get_or_none(session_store_name) if session_store_name else None
        )

        runnable = self.container.get(runnable_id)
        tool = as_tool(
            runnable,
            description=config.get("description"),
            name=config.get("name"),
            session_store=session_store,
        )
        logger.info(f"Created {tool_type}: {tool.get_name()} (wrapping {runnable_id})")
        return tool

    async def _get_or_create_tool(self, tool_name: str) -> Any:
        """Get or create tool."""
        if self.container.has(tool_name):
            return self.container.get(tool_name)

        config = self.registry.get(ComponentType.TOOL, tool_name)
        if config:
            return await self._build_component(config)

        registry = get_tool_registry()

        if registry.is_registered(tool_name):
            tool = registry.create(tool_name)
            metadata = ComponentMetadata(
                component_type=ComponentType.TOOL,
                config=ToolConfig(type="tool", name=tool_name, tool_name=tool_name),
                dependencies=[],
            )
            self.container.register(tool_name, tool, metadata)
            logger.info(f"Created built-in tool: {tool_name}")
            return tool

        raise ComponentNotFoundError(
            f"Tool '{tool_name}' not found. "
            f"Available: configs={list(self.registry.get_names_by_type(ComponentType.TOOL))}, "
            f"builtin={registry.list_builtin()}"
        )


_config_system: ConfigSystem | None = None
_config_system_lock = threading.Lock()


def get_config_system() -> ConfigSystem:
    """Get global ConfigSystem instance (thread-safe)."""
    global _config_system

    if _config_system is None:
        with _config_system_lock:
            if _config_system is None:
                _config_system = ConfigSystem()

    return _config_system


def reset_config_system() -> None:
    """Reset global ConfigSystem (for testing)."""
    global _config_system
    with _config_system_lock:
        _config_system = None


async def init_config_system(config_dir: str | Path) -> ConfigSystem:
    """
    Initialize global ConfigSystem.

    Args:
        config_dir: Configuration file directory

    Returns:
        ConfigSystem instance
    """
    system = get_config_system()
    await system.load_from_directory(config_dir)
    await system.build_all()
    return system
