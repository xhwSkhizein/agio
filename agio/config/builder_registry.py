from typing import Any, Protocol

from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ComponentBuilder(Protocol):
    """构建器协议"""

    async def build(
        self, config: ComponentConfig, dependencies: dict[str, Any]
    ) -> Any:
        """
        构建组件实例
        
        Args:
            config: 组件配置
            dependencies: 已解析的依赖
            
        Returns:
            组件实例
        """
        ...

    async def cleanup(self, instance: Any) -> None:
        """
        清理组件资源
        
        Args:
            instance: 组件实例
        """
        ...


class BuilderRegistry:
    """
    构建器注册表 - 管理组件构建器
    
    职责：
    - 注册和查询构建器
    - 支持动态注册（扩展性）
    """

    def __init__(self):
        self._builders: dict[ComponentType, ComponentBuilder] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认构建器"""
        from agio.config.builders import (
            AgentBuilder,
            CitationStoreBuilder,
            KnowledgeBuilder,
            MemoryBuilder,
            ModelBuilder,
            SessionStoreBuilder,
            ToolBuilder,
            TraceStoreBuilder,
            WorkflowBuilder,
        )

        self.register(ComponentType.MODEL, ModelBuilder())
        self.register(ComponentType.TOOL, ToolBuilder())
        self.register(ComponentType.MEMORY, MemoryBuilder())
        self.register(ComponentType.KNOWLEDGE, KnowledgeBuilder())
        self.register(ComponentType.SESSION_STORE, SessionStoreBuilder())
        self.register(ComponentType.TRACE_STORE, TraceStoreBuilder())
        self.register(ComponentType.CITATION_STORE, CitationStoreBuilder())
        self.register(ComponentType.AGENT, AgentBuilder())
        self.register(ComponentType.WORKFLOW, WorkflowBuilder())

        logger.debug("Registered default builders")

    def register(
        self, component_type: ComponentType, builder: ComponentBuilder
    ) -> None:
        """
        注册构建器
        
        Args:
            component_type: 组件类型
            builder: 构建器实例
        """
        self._builders[component_type] = builder
        logger.debug(f"Registered builder for type: {component_type.value}")

    def get(self, component_type: ComponentType) -> ComponentBuilder | None:
        """
        获取构建器
        
        Args:
            component_type: 组件类型
            
        Returns:
            构建器实例，不存在返回 None
        """
        return self._builders.get(component_type)

    def has(self, component_type: ComponentType) -> bool:
        """
        检查构建器是否存在
        
        Args:
            component_type: 组件类型
            
        Returns:
            是否存在
        """
        return component_type in self._builders

    def list_types(self) -> list[ComponentType]:
        """
        列出所有已注册的组件类型
        
        Returns:
            组件类型列表
        """
        return list(self._builders.keys())

    def unregister(self, component_type: ComponentType) -> None:
        """
        注销构建器
        
        Args:
            component_type: 组件类型
        """
        if component_type in self._builders:
            del self._builders[component_type]
            logger.debug(f"Unregistered builder for type: {component_type.value}")
