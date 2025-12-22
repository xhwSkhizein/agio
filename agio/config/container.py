from datetime import datetime
from typing import Any

from agio.config.exceptions import ComponentNotFoundError
from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ComponentMetadata:
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


class ComponentContainer:
    """
    组件容器 - 负责实例的存储和生命周期管理
    
    职责：
    - 缓存已构建的组件实例
    - 存储组件元数据
    - 管理组件生命周期
    """

    def __init__(self):
        self._instances: dict[str, Any] = {}
        self._metadata: dict[str, ComponentMetadata] = {}

    def register(
        self, name: str, instance: Any, metadata: ComponentMetadata
    ) -> None:
        """
        注册组件实例
        
        Args:
            name: 组件名称
            instance: 组件实例
            metadata: 组件元数据
        """
        self._instances[name] = instance
        self._metadata[name] = metadata
        logger.debug(
            f"Registered component: {name} "
            f"(type={metadata.component_type.value}, deps={metadata.dependencies})"
        )

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
        """
        获取组件实例（不存在返回 None）
        
        Args:
            name: 组件名称
            
        Returns:
            组件实例，不存在返回 None
        """
        return self._instances.get(name)

    def has(self, name: str) -> bool:
        """
        检查组件是否存在
        
        Args:
            name: 组件名称
            
        Returns:
            是否存在
        """
        return name in self._instances

    def get_metadata(self, name: str) -> ComponentMetadata | None:
        """
        获取组件元数据
        
        Args:
            name: 组件名称
            
        Returns:
            组件元数据，不存在返回 None
        """
        return self._metadata.get(name)

    def get_all_instances(self) -> dict[str, Any]:
        """
        获取所有组件实例
        
        Returns:
            组件名称到实例的映射
        """
        return dict(self._instances)

    def get_all_metadata(self) -> dict[str, ComponentMetadata]:
        """
        获取所有组件元数据
        
        Returns:
            组件名称到元数据的映射
        """
        return dict(self._metadata)

    def list_names(self) -> list[str]:
        """
        列出所有组件名称
        
        Returns:
            组件名称列表
        """
        return list(self._instances.keys())

    def remove(self, name: str) -> tuple[Any | None, ComponentMetadata | None]:
        """
        移除组件（不清理资源）
        
        Args:
            name: 组件名称
            
        Returns:
            (实例, 元数据) 元组，不存在返回 (None, None)
        """
        instance = self._instances.pop(name, None)
        metadata = self._metadata.pop(name, None)
        
        if instance is not None:
            logger.debug(f"Removed component: {name}")
        
        return instance, metadata

    def clear(self) -> None:
        """清空所有组件"""
        self._instances.clear()
        self._metadata.clear()
        logger.debug("Cleared all components")

    def count(self) -> int:
        """获取组件总数"""
        return len(self._instances)

    def get_dependents(self, name: str) -> list[str]:
        """
        获取依赖指定组件的其他组件名称
        
        Args:
            name: 组件名称
            
        Returns:
            依赖此组件的组件名称列表
        """
        dependents = []
        for comp_name, metadata in self._metadata.items():
            if name in metadata.dependencies:
                dependents.append(comp_name)
        return dependents
