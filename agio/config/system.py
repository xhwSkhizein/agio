"""
ConfigSystem - 配置系统核心入口

提供统一的配置管理和组件生命周期管理：
- 配置加载和存储
- 组件构建和依赖注入
- 配置变更和热重载
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from agio.config.builders import (
    AgentBuilder,
    ComponentBuilder,
    KnowledgeBuilder,
    MemoryBuilder,
    ModelBuilder,
    RepositoryBuilder,
    StorageBuilder,
    ToolBuilder,
    WorkflowBuilder,
)
from agio.config.exceptions import (
    ComponentBuildError,
    ComponentNotFoundError,
    ConfigNotFoundError,
)
from agio.config.loader import ConfigLoader
from agio.config.schema import (
    AgentConfig,
    ComponentConfig,
    ComponentType,
    KnowledgeConfig,
    MemoryConfig,
    ModelConfig,
    RepositoryConfig,
    StorageConfig,
    ToolConfig,
    WorkflowConfig,
)

logger = logging.getLogger(__name__)


class ComponentMeta:
    """组件元数据"""

    def __init__(
        self,
        component_type: ComponentType,
        config: ComponentConfig,
        dependencies: list[str],
    ):
        self.component_type = component_type
        self.config = config
        self.dependencies = dependencies
        self.created_at = datetime.now()


class ConfigSystem:
    """
    配置系统核心类 - 单一入口点

    职责：
    - 配置加载和存储
    - 组件构建和生命周期管理
    - 依赖解析和自动装配
    - 配置变更和热重载
    """

    # 组件类型优先级（用于确定构建顺序）
    TYPE_PRIORITY = {
        ComponentType.MODEL: 0,
        ComponentType.STORAGE: 0,
        ComponentType.REPOSITORY: 0,
        ComponentType.MEMORY: 1,
        ComponentType.KNOWLEDGE: 1,
        ComponentType.TOOL: 2,
        ComponentType.AGENT: 3,
        ComponentType.WORKFLOW: 4,  # Workflows depend on agents
    }

    # 配置类型映射
    CONFIG_CLASSES = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.MEMORY: MemoryConfig,
        ComponentType.KNOWLEDGE: KnowledgeConfig,
        ComponentType.STORAGE: StorageConfig,
        ComponentType.REPOSITORY: RepositoryConfig,
        ComponentType.AGENT: AgentConfig,
        ComponentType.WORKFLOW: WorkflowConfig,
    }

    def __init__(self):
        # 配置存储 {(type, name): config_dict}
        self._configs: dict[tuple[ComponentType, str], dict] = {}

        # 组件实例池 {name: instance}
        self._instances: dict[str, Any] = {}

        # 组件元数据 {name: ComponentMeta}
        self._metadata: dict[str, ComponentMeta] = {}

        # 组件构建器
        self._builders: dict[ComponentType, ComponentBuilder] = {
            ComponentType.MODEL: ModelBuilder(),
            ComponentType.TOOL: ToolBuilder(),
            ComponentType.MEMORY: MemoryBuilder(),
            ComponentType.KNOWLEDGE: KnowledgeBuilder(),
            ComponentType.STORAGE: StorageBuilder(),
            ComponentType.REPOSITORY: RepositoryBuilder(),
            ComponentType.AGENT: AgentBuilder(),
            ComponentType.WORKFLOW: WorkflowBuilder(),
        }

        # 变更回调
        self._change_callbacks: list[Callable[[str, str], None]] = []

    # ========================================================================
    # 配置管理
    # ========================================================================

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
        load_order = loader.get_load_order(configs_by_type)

        stats = {"loaded": 0, "failed": 0}

        for component_type, config_data in load_order:
            name = config_data.get("name")
            try:
                self._configs[(component_type, name)] = config_data
                logger.info(f"Loaded config: {component_type.value}/{name}")
                stats["loaded"] += 1
            except Exception as e:
                logger.error(f"Failed to load {component_type.value}/{name}: {e}")
                stats["failed"] += 1

        logger.info(f"Config loading completed: {stats}")
        return stats

    async def save_config(self, config: ComponentConfig) -> None:
        """
        保存配置（触发热重载）

        Args:
            config: 组件配置
        """
        component_type = ComponentType(config.type)
        name = config.name

        # 检查是否是更新
        is_update = (component_type, name) in self._configs

        # 保存配置
        self._configs[(component_type, name)] = config.model_dump()

        logger.info(f"Config saved: {component_type.value}/{name}")

        # 触发热重载
        if is_update and name in self._instances:
            await self._handle_config_change(name, "update")
        else:
            # 新配置，尝试构建
            await self._build_component(component_type, name)
            await self._notify_change(name, "create")

    async def delete_config(self, component_type: ComponentType, name: str) -> None:
        """
        删除配置

        Args:
            component_type: 组件类型
            name: 组件名称
        """
        key = (component_type, name)
        if key not in self._configs:
            raise ConfigNotFoundError(f"Config {component_type.value}/{name} not found")

        # 获取受影响的组件
        affected = self._get_affected_components(name)

        # 逆序销毁组件
        for comp_name in reversed(affected):
            await self._destroy_component(comp_name)

        # 删除配置
        del self._configs[key]

        logger.info(f"Config deleted: {component_type.value}/{name}")
        await self._notify_change(name, "delete")

    def get_config(
        self, component_type: ComponentType, name: str
    ) -> dict | None:
        """获取配置"""
        return self._configs.get((component_type, name))

    def list_configs(
        self, component_type: ComponentType | None = None
    ) -> list[dict]:
        """列出配置"""
        result = []
        for (ct, name), config in self._configs.items():
            if component_type is None or ct == component_type:
                result.append({"type": ct.value, "name": name, "config": config})
        return result

    # ========================================================================
    # 组件管理
    # ========================================================================

    def get(self, name: str) -> Any:
        """
        获取组件实例

        Args:
            name: 组件名称

        Returns:
            组件实例

        Raises:
            ComponentNotFoundError: 组件不存在
        """
        if name not in self._instances:
            raise ComponentNotFoundError(f"Component '{name}' not found")
        return self._instances[name]

    def get_or_none(self, name: str) -> Any | None:
        """获取组件实例，不存在返回 None"""
        return self._instances.get(name)

    def get_instance(self, name: str) -> Any:
        """
        获取组件实例 (get 的别名)

        Args:
            name: 组件名称

        Returns:
            组件实例

        Raises:
            ComponentNotFoundError: 组件不存在
        """
        return self.get(name)

    def get_all_instances(self) -> dict[str, Any]:
        """
        获取所有组件实例

        Returns:
            组件名称到实例的映射
        """
        return dict(self._instances)

    async def build_all(self) -> dict[str, int]:
        """
        按依赖顺序构建所有组件

        Returns:
            构建统计 {"built": count, "failed": count}
        """
        logger.info("Building all components...")

        # 按优先级排序配置
        sorted_configs = sorted(
            self._configs.items(),
            key=lambda x: self.TYPE_PRIORITY.get(x[0][0], 99),
        )

        stats = {"built": 0, "failed": 0}

        for (component_type, name), config_data in sorted_configs:
            try:
                await self._build_component(component_type, name)
                stats["built"] += 1
            except Exception as e:
                logger.error(f"Failed to build {component_type.value}/{name}: {e}")
                stats["failed"] += 1

        logger.info(f"Build completed: {stats}")
        return stats

    async def rebuild(self, name: str) -> None:
        """
        重建单个组件及其依赖者

        Args:
            name: 组件名称
        """
        affected = self._get_affected_components(name)

        # 逆序销毁
        for comp_name in reversed(affected):
            await self._destroy_component(comp_name)

        # 正序重建
        for comp_name in affected:
            meta = self._metadata.get(comp_name)
            if meta:
                await self._build_component(meta.component_type, comp_name)

    # ========================================================================
    # 热重载
    # ========================================================================

    def on_change(self, callback: Callable[[str, str], None]) -> None:
        """
        注册配置变更回调

        Args:
            callback: 回调函数 (name, change_type) -> None
        """
        self._change_callbacks.append(callback)

    async def _handle_config_change(self, name: str, change_type: str) -> None:
        """处理配置变更"""
        logger.info(f"Handling config change: {name} ({change_type})")

        affected = self._get_affected_components(name)

        # 逆序销毁
        for comp_name in reversed(affected):
            await self._destroy_component(comp_name)

        # 正序重建
        for comp_name in affected:
            # 查找配置
            for (ct, n), _ in self._configs.items():
                if n == comp_name:
                    await self._build_component(ct, comp_name)
                    break

        await self._notify_change(name, change_type)

    async def _notify_change(self, name: str, change_type: str) -> None:
        """通知变更回调"""
        for callback in self._change_callbacks:
            try:
                callback(name, change_type)
            except Exception as e:
                logger.error(f"Change callback error: {e}")

    # ========================================================================
    # 内部方法
    # ========================================================================

    async def _build_component(
        self, component_type: ComponentType, name: str
    ) -> Any:
        """构建单个组件"""
        config_data = self._configs.get((component_type, name))
        if not config_data:
            raise ConfigNotFoundError(f"Config {component_type.value}/{name} not found")

        # 解析配置
        config_class = self.CONFIG_CLASSES.get(component_type)
        if not config_class:
            raise ComponentBuildError(f"Unknown component type: {component_type}")

        config = config_class(**config_data)

        # 解析依赖
        dependencies = await self._resolve_dependencies(config)
        dependency_names = list(dependencies.keys())

        # 构建组件
        builder = self._builders.get(component_type)
        if not builder:
            raise ComponentBuildError(f"No builder for type: {component_type}")

        instance = await builder.build(config, dependencies)

        # 存储实例和元数据
        self._instances[name] = instance
        self._metadata[name] = ComponentMeta(
            component_type=component_type,
            config=config,
            dependencies=dependency_names,
        )

        logger.info(f"Component built: {component_type.value}/{name}")
        return instance

    async def _destroy_component(self, name: str) -> None:
        """销毁组件"""
        if name not in self._instances:
            return

        instance = self._instances.pop(name)
        meta = self._metadata.pop(name, None)

        # 清理资源
        if meta:
            builder = self._builders.get(meta.component_type)
            if builder:
                try:
                    await builder.cleanup(instance)
                except Exception as e:
                    logger.error(f"Cleanup error for {name}: {e}")

        logger.info(f"Component destroyed: {name}")

    async def _resolve_dependencies(self, config: ComponentConfig) -> dict[str, Any]:
        """解析组件依赖"""
        dependencies = {}

        if isinstance(config, AgentConfig):
            # Model (required)
            dependencies["model"] = self.get(config.model)

            # Tools (list) - support both registered tools and built-in tools
            tools = []
            for tool_name in config.tools:
                tool = await self._get_or_create_tool(tool_name)
                tools.append(tool)
            dependencies["tools"] = tools

            # Optional dependencies
            if config.memory:
                dependencies["memory"] = self.get(config.memory)

            if config.knowledge:
                dependencies["knowledge"] = self.get(config.knowledge)

            if config.repository:
                dependencies["repository"] = self.get(config.repository)

        elif isinstance(config, ToolConfig):
            # Tool dependencies (e.g., llm_model)
            for param_name, dep_name in config.effective_dependencies.items():
                dependencies[param_name] = self.get(dep_name)

        elif isinstance(config, WorkflowConfig):
            # Workflow needs access to all instances (agents, other workflows)
            dependencies["_all_instances"] = self._instances

        return dependencies
    
    async def _get_or_create_tool(self, tool_name: str) -> Any:
        """
        Get tool instance by name.
        
        Priority:
        1. Already built tool in ConfigSystem
        2. Tool config exists -> build it
        3. Built-in tool from registry -> create with default params
        """
        # 1. Check if already built
        if tool_name in self._instances:
            return self._instances[tool_name]
        
        # 2. Check if config exists -> build it
        tool_config = self.get_config(ComponentType.TOOL, tool_name)
        if tool_config:
            return await self._build_component(ComponentType.TOOL, tool_name)
        
        # 3. Try to create from registry (built-in tools)
        from agio.providers.tools import get_tool_registry
        registry = get_tool_registry()
        
        if registry.is_registered(tool_name):
            tool = registry.create(tool_name)
            # Cache the instance
            self._instances[tool_name] = tool
            logger.info(f"Created built-in tool: {tool_name}")
            return tool
        
        raise ComponentNotFoundError(
            f"Tool '{tool_name}' not found. "
            f"Available: configs={[n for (t, n) in self._configs.keys() if t == ComponentType.TOOL]}, "
            f"builtin={registry.list_builtin()}"
        )

    def _get_affected_components(self, name: str) -> list[str]:
        """
        获取受影响的组件列表（包括依赖者）

        使用 BFS 遍历依赖图
        """
        affected = [name]
        queue = [name]

        while queue:
            current = queue.pop(0)
            for comp_name, meta in self._metadata.items():
                if current in meta.dependencies and comp_name not in affected:
                    affected.append(comp_name)
                    queue.append(comp_name)

        return affected

    def _parse_config(
        self, component_type: ComponentType, config_data: dict
    ) -> ComponentConfig:
        """解析配置数据为配置对象"""
        config_class = self.CONFIG_CLASSES.get(component_type)
        if not config_class:
            raise ComponentBuildError(f"Unknown component type: {component_type}")
        return config_class(**config_data)

    # ========================================================================
    # 状态查询
    # ========================================================================

    def list_components(self) -> list[dict]:
        """列出所有已构建的组件"""
        result = []
        for name, instance in self._instances.items():
            meta = self._metadata.get(name)
            result.append({
                "name": name,
                "type": meta.component_type.value if meta else None,
                "dependencies": meta.dependencies if meta else [],
                "created_at": meta.created_at.isoformat() if meta else None,
            })
        return result

    def get_component_info(self, name: str) -> dict | None:
        """获取组件详细信息"""
        if name not in self._instances:
            return None

        meta = self._metadata.get(name)
        return {
            "name": name,
            "type": meta.component_type.value if meta else None,
            "config": meta.config.model_dump() if meta else None,
            "dependencies": meta.dependencies if meta else [],
            "created_at": meta.created_at.isoformat() if meta else None,
        }


# 全局单例
_config_system: ConfigSystem | None = None


def get_config_system() -> ConfigSystem:
    """获取全局 ConfigSystem 实例"""
    global _config_system
    if _config_system is None:
        _config_system = ConfigSystem()
    return _config_system


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
