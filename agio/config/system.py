"""
ConfigSystem - 配置系统门面/协调者（重构版）

职责：
- 协调各模块工作（Registry, Container, DependencyResolver, BuilderRegistry, HotReloadManager）
- 提供统一的外部接口
- 处理组件构建流程
"""

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
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigSystem:
    """
    配置系统门面 - 协调各模块
    
    架构：
    - ConfigRegistry: 配置存储
    - ComponentContainer: 实例管理
    - DependencyResolver: 依赖解析和拓扑排序
    - BuilderRegistry: 构建器管理
    - HotReloadManager: 热重载
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

    def __init__(self):
        self.registry = ConfigRegistry()
        self.container = ComponentContainer()
        self.dependency_resolver = DependencyResolver()
        self.builder_registry = BuilderRegistry()
        self.hot_reload = HotReloadManager(
            self.container, self.dependency_resolver, self.builder_registry
        )

    async def load_from_directory(self, config_dir: str | Path) -> dict[str, int]:
        """
        从目录加载所有配置文件
        
        Args:
            config_dir: 配置文件目录
            
        Returns:
            加载统计 {"loaded": count, "failed": count}
        """
        logger.info(f"Loading configs from: {config_dir}")

        loader = ConfigLoader(config_dir)
        configs_by_type = await loader.load_all_configs()

        stats = {"loaded": 0, "failed": 0}

        all_config_dicts = []
        for configs in configs_by_type.values():
            all_config_dicts.extend(configs)

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
        """解析配置字典为 Pydantic 模型"""
        component_type = ComponentType(config_dict["type"])
        config_class = self.CONFIG_CLASSES.get(component_type)
        
        if not config_class:
            raise ConfigNotFoundError(f"Unknown component type: {component_type}")
        
        return config_class(**config_dict)

    async def save_config(self, config: ComponentConfig) -> None:
        """
        保存配置（触发热重载）
        
        Args:
            config: 组件配置
        """
        component_type = ComponentType(config.type)
        name = config.name

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
        删除配置
        
        Args:
            component_type: 组件类型
            name: 组件名称
        """
        if not self.registry.has(component_type, name):
            raise ConfigNotFoundError(f"Config {component_type.value}/{name} not found")

        await self.hot_reload.handle_change(name, "delete", None)

        self.registry.remove(component_type, name)
        logger.info(f"Config deleted: {component_type.value}/{name}")

    def get_config(
        self, component_type: ComponentType, name: str
    ) -> dict | None:
        """获取配置（返回 dict 格式以保持向后兼容）"""
        config = self.registry.get(component_type, name)
        return config.model_dump() if config else None

    def list_configs(
        self, component_type: ComponentType | None = None
    ) -> list[dict]:
        """列出配置（返回 dict 列表以保持向后兼容）"""
        if component_type is None:
            configs = self.registry.list_all()
        else:
            configs = self.registry.list_by_type(component_type)
        return [config.model_dump() for config in configs]

    async def build_all(self) -> dict[str, int]:
        """
        按依赖顺序构建所有组件
        
        Returns:
            构建统计 {"built": count, "failed": count}
        """
        logger.info("Building all components...")

        configs = self.registry.list_all()
        available_names = self.registry.get_all_names()

        sorted_configs = self.dependency_resolver.topological_sort(
            configs, available_names
        )

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
        重建单个组件及其依赖者
        
        Args:
            name: 组件名称
        """
        await self.hot_reload.handle_change(
            name, "update", lambda n: self._build_by_name(n)
        )

    def get(self, name: str) -> Any:
        """获取组件实例"""
        return self.container.get(name)

    def get_or_none(self, name: str) -> Any | None:
        """获取组件实例（不存在返回 None）"""
        return self.container.get_or_none(name)

    def get_instance(self, name: str) -> Any:
        """获取组件实例（get 的别名）"""
        return self.get(name)

    def get_all_instances(self) -> dict[str, Any]:
        """获取所有组件实例"""
        return self.container.get_all_instances()

    def list_components(self) -> list[dict]:
        """列出所有已构建的组件"""
        result = []
        for name in self.container.list_names():
            metadata = self.container.get_metadata(name)
            if metadata:
                result.append({
                    "name": name,
                    "type": metadata.component_type.value,
                    "dependencies": metadata.dependencies,
                    "created_at": metadata.created_at.isoformat(),
                })
        return result

    def get_component_info(self, name: str) -> dict | None:
        """获取组件详细信息"""
        if not self.container.has(name):
            return None

        metadata = self.container.get_metadata(name)
        if not metadata:
            return None

        return {
            "name": name,
            "type": metadata.component_type.value,
            "config": metadata.config.model_dump(),
            "dependencies": metadata.dependencies,
            "created_at": metadata.created_at.isoformat(),
        }

    def on_change(self, callback) -> None:
        """注册配置变更回调"""
        self.hot_reload.register_callback(callback)

    async def _build_component(self, config: ComponentConfig) -> Any:
        """构建单个组件"""
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
        """根据名称构建组件（用于热重载）"""
        for config in self.registry.list_all():
            if config.name == name:
                return await self._build_component(config)
        
        raise ConfigNotFoundError(f"Config for component '{name}' not found")

    async def _resolve_dependencies(self, config: ComponentConfig) -> dict[str, Any]:
        """解析组件依赖"""
        if isinstance(config, AgentConfig):
            return await self._resolve_agent_dependencies(config)
        elif isinstance(config, ToolConfig):
            return await self._resolve_tool_dependencies(config)
        elif isinstance(config, WorkflowConfig):
            return await self._resolve_workflow_dependencies(config)
        return {}

    async def _resolve_agent_dependencies(self, config: AgentConfig) -> dict[str, Any]:
        """解析 Agent 依赖"""
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
        """解析 Tool 依赖"""
        dependencies = {}
        for param_name, dep_name in config.effective_dependencies.items():
            dependencies[param_name] = self.container.get(dep_name)
        return dependencies

    async def _resolve_workflow_dependencies(
        self, config: WorkflowConfig
    ) -> dict[str, Any]:
        """解析 Workflow 依赖"""
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
        """解析工具引用"""
        if isinstance(tool_ref, str):
            return await self._get_or_create_tool(tool_ref)

        from agio.config.tool_reference import parse_tool_reference

        if isinstance(tool_ref, RunnableToolConfig):
            parsed = parse_tool_reference(tool_ref.model_dump())
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
        """创建 RunnableTool"""
        from agio.workflow import as_tool

        id_field = "agent" if tool_type == "agent_tool" else "workflow"
        runnable_id = config.get(id_field)
        if not runnable_id:
            raise ComponentBuildError(f"{tool_type} config missing '{id_field}' field")

        if current_component and runnable_id == current_component:
            raise ComponentBuildError(
                f"Self-reference detected: '{current_component}' cannot use itself as a tool."
            )

        session_store = (
            self.container.get_or_none(session_store_name)
            if session_store_name
            else None
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
        """获取或创建工具"""
        if self.container.has(tool_name):
            return self.container.get(tool_name)

        config = self.registry.get(ComponentType.TOOL, tool_name)
        if config:
            return await self._build_component(config)

        from agio.providers.tools import get_tool_registry

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
    """获取全局 ConfigSystem 实例（线程安全）"""
    global _config_system

    if _config_system is None:
        with _config_system_lock:
            if _config_system is None:
                _config_system = ConfigSystem()

    return _config_system


def reset_config_system() -> None:
    """重置全局 ConfigSystem（用于测试）"""
    global _config_system
    with _config_system_lock:
        _config_system = None


async def init_config_system(config_dir: str | Path) -> ConfigSystem:
    """
    初始化全局 ConfigSystem
    
    Args:
        config_dir: 配置文件目录
        
    Returns:
        ConfigSystem 实例
    """
    system = get_config_system()
    await system.load_from_directory(config_dir)
    await system.build_all()
    return system
