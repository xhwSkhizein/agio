"""
ConfigSystem - Configuration system facade/coordinator (refactored version).

Responsibilities:
- Coordinate work of all modules (Registry, Container, DependencyResolver, BuilderRegistry, HotReloadManager)
- Provide unified external interface
- Handle component building process
"""

import asyncio
import threading
from contextlib import asynccontextmanager
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
)
from agio.config.tool_reference import parse_tool_reference
from agio.runtime import as_tool
from agio.tools import get_tool_registry
from agio.utils.logging import get_logger

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
    }

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.registry = ConfigRegistry()
        self._active_container = ComponentContainer()
        self.container = self._active_container  # backward compatibility
        self._draining_containers: list[ComponentContainer] = []
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(
            self._active_container, self.dependency_resolver, self.builder_registry
        )
        self._config_dir: Path | None = None

    @property
    def config_dir(self) -> Path | None:
        """Get current configuration directory."""
        return self._config_dir

    async def load_from_directory(self, config_dir: str | Path) -> dict[str, int]:
        """
        Load all configuration files from directory.

        Args:
            config_dir: Configuration file directory

        Returns:
            Loading statistics {"loaded": count, "failed": count}
        """
        config_dir = Path(config_dir)
        logger.info(f"Loading configs from: {config_dir}")

        loader = ConfigLoader(config_dir)
        configs_by_type = await loader.load_all_configs()

        stats = {"loaded": 0, "failed": 0}

        all_config_dicts = []
        for configs in configs_by_type.values():
            all_config_dicts.extend(configs)

        async with self._lock:
            self._config_dir = config_dir
            for config_dict in all_config_dicts:
                name = config_dict.get("name", "unknown")
                try:
                    config = self._parse_config(config_dict)
                    self.registry.register(config)
                    logger.info(f"Loaded config: {config.type}/{config.name}")
                    stats["loaded"] += 1
                except Exception as e:
                    logger.exception(f"Failed to parse config {name}: {e}")
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

            await self._reload_active_container()
            self.hot_reload._notify_callbacks(
                name, "create" if not is_update else "update"
            )

    async def delete_config(self, component_type: ComponentType, name: str) -> None:
        """
        Delete configuration.

        Args:
            component_type: Component type
            name: Component name
        """
        async with self._lock:
            if not self.registry.has(component_type, name):
                raise ConfigNotFoundError(
                    f"Config {component_type.value}/{name} not found"
                )

            self.registry.remove(component_type, name)
            logger.info(f"Config deleted: {component_type.value}/{name}")
            await self._reload_active_container()

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
            return await self._reload_active_container()

    async def rebuild(self, name: str, component_type: ComponentType | None = None) -> None:
        """
        Rebuild single component and its dependents.

        Args:
            name: Component name
            component_type: Component type
        """
        async with self._lock:
            if component_type:
                # Use HotReloadManager for fine-grained rebuild
                await self.hot_reload.handle_change(
                    name, 
                    component_type, 
                    "update", 
                    rebuild_func=self._build_by_key
                )
            else:
                # Fallback to full reload if type is not specified
                await self._reload_active_container()

    def get(self, name: str, component_type: ComponentType | None = None) -> Any:
        """Get component instance."""
        return self._active_container.acquire(name, component_type)

    def get_or_none(self, name: str, component_type: ComponentType | None = None) -> Any | None:
        """Get component instance or None."""
        try:
            return self._active_container.acquire(name, component_type)
        except ComponentNotFoundError:
            return None

    def release(self, name: str, component_type: ComponentType | None = None) -> None:
        """Release component instance."""
        self._active_container.release(name, component_type)

    def get_instance(self, name: str, component_type: ComponentType | None = None) -> Any:
        """Get component instance (alias for get)."""
        return self.get(name, component_type)

    def get_all_instances(self) -> dict[tuple[ComponentType, str], Any]:
        """Get all component instances."""
        return self._active_container.get_all_instances()

    @asynccontextmanager
    async def use(self, name: str, component_type: ComponentType | None = None):
        """
        Async context manager to auto release component reference.
        """
        instance = self.get(name, component_type)
        try:
            yield instance
        finally:
            self.release(name, component_type)

    async def _reload_active_container(self) -> dict[str, int]:
        """
        Build components into a new container, then atomically swap and drain old containers.
        """
        new_container = ComponentContainer()
        configs = self.registry.list_all()
        available_names = self.registry.get_all_names()

        sorted_configs = self.dependency_resolver.topological_sort(configs)

        stats = {"built": 0, "failed": 0}

        for config in sorted_configs:
            try:
                await self._build_component(config, new_container)
                stats["built"] += 1
            except Exception as e:
                logger.exception(f"Failed to build {config.type}/{config.name}: {e}")
                stats["failed"] += 1
                # Abort swap on failure
                return stats

        # Swap containers
        old_container = self._active_container
        self._active_container = new_container
        self.container = new_container
        self.hot_reload.set_container(new_container)
        
        # Only drain if the old container actually had instances
        if old_container.count() > 0:
            self._draining_containers.append(old_container)
            # Begin draining old containers (fire and forget)
            asyncio.create_task(self._drain_containers())

        logger.info(f"Build completed and swapped: {stats}")
        return stats

    async def _drain_containers(self) -> None:
        """Wait for draining containers to have zero refs, then cleanup."""
        while self._draining_containers:
            container = self._draining_containers.pop(0)
            drained = await container.wait_for_zero(timeout=5.0)
            if not drained:
                logger.warning("Draining container timeout; forcing cleanup")
            await self._cleanup_container(container)

    async def _cleanup_container(self, container: ComponentContainer) -> None:
        """Cleanup all instances in a container using builders."""
        for (comp_type, name), metadata in container._metadata.items():
            instance = container.get_or_none(name, comp_type)
            builder = self.builder_registry.get(comp_type)
            if instance is not None and builder:
                try:
                    await builder.cleanup(instance)
                except Exception as e:
                    logger.error(f"Failed to cleanup {comp_type.value}/{name}: {e}")
        container.clear()

    def list_components(self) -> list[dict]:
        """List all built components."""
        result = []
        for comp_type, name in self.container.list_components():
            metadata = self.container.get_metadata(name, comp_type)
            if metadata:
                result.append(
                    {
                        "name": name,
                        "type": comp_type.value,
                        "dependencies": metadata.dependencies,
                        "created_at": metadata.created_at.isoformat(),
                    }
                )
        return result

    def get_component_info(self, name: str, component_type: ComponentType | None = None) -> dict | None:
        """Get component detailed information."""
        if not self.container.has(name, component_type):
            return None

        metadata = self.container.get_metadata(name, component_type)
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

    async def _build_component(
        self, config: ComponentConfig, container: ComponentContainer
    ) -> Any:
        """Build single component."""
        dependencies = await self._resolve_dependencies(config, container)

        component_type = ComponentType(config.type)
        builder = self.builder_registry.get(component_type)
        if not builder:
            raise ComponentBuildError(f"No builder for type: {component_type}")

        instance = await builder.build(config, dependencies)

        # Record logical dependency names (not param keys)
        dependency_names = self.dependency_resolver.extract_dependencies(config)

        metadata = ComponentMetadata(
            component_type=component_type,
            config=config,
            dependencies=list(dependency_names),
        )
        container.register(config.name, instance, metadata)

        logger.info(f"Component built: {component_type.value}/{config.name}")
        return instance

    async def _build_by_key(self, name: str, component_type: ComponentType) -> Any:
        """Build component by key (name and type)."""
        config = self.registry.get(component_type, name)
        if config:
            return await self._build_component(config, self._active_container)

        raise ConfigNotFoundError(f"Config for component {component_type.value}/{name} not found")

    def _find_dependency_config(self, dep_name: str) -> ComponentConfig | None:
        """
        Find dependency config by name, searching all component types.
        
        Args:
            dep_name: Dependency component name
            
        Returns:
            Component config if found, None otherwise
        """
        for component_type in ComponentType:
            config = self.registry.get(component_type, dep_name)
            if config:
                return config
        return None

    async def _ensure_dependency_built(
        self,
        dep_name: str,
        container: ComponentContainer,
        context: str = "component",
    ) -> Any:
        """
        Ensure dependency is built and return its instance.
        
        Unified method to handle dependency resolution:
        1. Check if already built in container
        2. Find config from registry
        3. Build if necessary
        4. Return instance
        
        Args:
            dep_name: Dependency component name
            container: Target container
            context: Context for error messages (e.g., "agent 'xxx'")
            
        Returns:
            Component instance
            
        Raises:
            ComponentNotFoundError: If dependency config not found and not in container
        """
        # 1. Check if already built in container (backward compatibility/manual registration)
        instance = container.get_or_none(dep_name)
        if instance is not None:
            return instance

        # 2. Find config from registry
        dep_config = self._find_dependency_config(dep_name)
        if not dep_config:
            raise ComponentNotFoundError(
                f"Dependency '{dep_name}' not found for {context}"
            )
        
        # 3. Build if necessary
        dep_type = ComponentType(dep_config.type)
        if not container.has(dep_name, dep_type):
            await self._build_component(dep_config, container)
        
        # 4. Return instance
        return container.get(dep_name, dep_type)

    async def _resolve_dependencies(
        self, config: ComponentConfig, container: ComponentContainer
    ) -> dict[str, Any]:
        """Resolve component dependencies."""
        if isinstance(config, AgentConfig):
            return await self._resolve_agent_dependencies(config, container)
        elif isinstance(config, ToolConfig):
            return await self._resolve_tool_dependencies(config, container)
        return {}

    async def _resolve_agent_dependencies(
        self, config: AgentConfig, container: ComponentContainer
    ) -> dict[str, Any]:
        """Resolve Agent dependencies."""
        dependencies = {}
        context = f"agent '{config.name}'"

        # Ensure model is built
        dependencies["model"] = await self._ensure_dependency_built(
            config.model, container, context
        )

        # Ensure session_store is built first (if needed)
        if config.session_store:
            dependencies["session_store"] = await self._ensure_dependency_built(
                config.session_store, container, context
            )

        # Resolve tools
        tools = []
        for tool_ref in config.tools:
            tool = await self._resolve_tool_reference(
                tool_ref,
                current_component=config.name,
                session_store_name=config.session_store,
                container=container,
            )
            tools.append(tool)
        dependencies["tools"] = tools

        return dependencies

    async def _resolve_tool_dependencies(
        self, config: ToolConfig, container: ComponentContainer
    ) -> dict[str, Any]:
        """Resolve Tool dependencies."""
        dependencies = {}
        context = f"tool '{config.name}'"
        
        for param_name, dep_name in config.effective_dependencies.items():
            dependencies[param_name] = await self._ensure_dependency_built(
                dep_name, container, context
            )
        return dependencies

    async def _resolve_tool_reference(
        self,
        tool_ref: str | dict | RunnableToolConfig,
        current_component: str | None = None,
        session_store_name: str | None = None,
        container: ComponentContainer | None = None,
    ) -> Any:
        """Resolve tool reference."""
        container = container or self._active_container
        if isinstance(tool_ref, str):
            return await self._get_or_create_tool(tool_ref, container)

        if isinstance(tool_ref, RunnableToolConfig):
            parsed = parse_tool_reference(tool_ref.model_dump(exclude_none=True))
        elif isinstance(tool_ref, dict):
            parsed = parse_tool_reference(tool_ref)
        else:
            raise ComponentBuildError(f"Invalid tool reference type: {type(tool_ref)}")

        if parsed.tool_type == "agent_tool":
            return await self._create_runnable_tool(
                parsed.tool_type, parsed.raw, current_component, session_store_name
            )

        raise ComponentBuildError(
            f"Unknown tool reference format: {tool_ref}. "
            f"Expected string or dict with type='agent_tool'"
        )

    async def _create_runnable_tool(
        self,
        tool_type: str,
        config: dict,
        current_component: str,
        session_store_name: str | None = None,
        container: ComponentContainer | None = None,
    ) -> Any:
        """Create RunnableTool for agent_tool."""
        runnable_id = config.get("agent")
        if not runnable_id:
            raise ComponentBuildError(f"{tool_type} config missing 'agent' field")

        if current_component and runnable_id == current_component:
            raise ComponentBuildError(
                f"Self-reference detected: '{current_component}' cannot use itself as a tool."
            )

        session_store = (
            container.get_or_none(session_store_name, ComponentType.SESSION_STORE)
            if container and session_store_name
            else None
        )

        target_container = container or self._active_container
        
        # Ensure the referenced agent is built first
        if not target_container.has(runnable_id, ComponentType.AGENT):
            agent_config = self.registry.get(ComponentType.AGENT, runnable_id)
            if not agent_config:
                raise ComponentNotFoundError(
                    f"Agent '{runnable_id}' not found in registry. "
                    f"Referenced by {current_component or 'unknown component'}"
                )
            # Build the agent first
            await self._build_component(agent_config, target_container)
        
        runnable = target_container.get(runnable_id, ComponentType.AGENT)
        tool = as_tool(
            runnable,
            description=config.get("description"),
            name=config.get("name"),
            session_store=session_store,
        )
        logger.info(f"Created {tool_type}: {tool.get_name()} (wrapping {runnable_id})")
        return tool

    async def _get_or_create_tool(
        self, tool_name: str, container: ComponentContainer | None = None
    ) -> Any:
        """Get or create tool."""
        container = container or self._active_container
        if container.has(tool_name, ComponentType.TOOL):
            return container.get(tool_name, ComponentType.TOOL)

        config = self.registry.get(ComponentType.TOOL, tool_name)
        if config:
            return await self._build_component(config, container)

        registry = get_tool_registry()

        if registry.is_registered(tool_name):
            tool = registry.create(tool_name)
            metadata = ComponentMetadata(
                component_type=ComponentType.TOOL,
                config=ToolConfig(type="tool", name=tool_name, tool_name=tool_name),
                dependencies=[],
            )
            container.register(tool_name, tool, metadata)
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
