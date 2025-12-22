from typing import Any

from agio.config.schema import ComponentConfig, ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigRegistry:
    """
    配置注册表 - 负责配置的存储和查询
    
    职责：
    - 存储已验证的 Pydantic 配置模型
    - 提供配置查询接口
    - 支持配置的增删改查
    """

    def __init__(self):
        self._configs: dict[tuple[ComponentType, str], ComponentConfig] = {}

    def register(self, config: ComponentConfig) -> None:
        """
        注册配置（自动验证）
        
        Args:
            config: 组件配置（已验证的 Pydantic 模型）
        """
        component_type = ComponentType(config.type)
        key = (component_type, config.name)
        self._configs[key] = config
        logger.debug(f"Registered config: {component_type.value}/{config.name}")

    def get(
        self, component_type: ComponentType, name: str
    ) -> ComponentConfig | None:
        """
        获取配置
        
        Args:
            component_type: 组件类型
            name: 组件名称
            
        Returns:
            配置对象，不存在返回 None
        """
        return self._configs.get((component_type, name))

    def has(self, component_type: ComponentType, name: str) -> bool:
        """
        检查配置是否存在
        
        Args:
            component_type: 组件类型
            name: 组件名称
            
        Returns:
            是否存在
        """
        return (component_type, name) in self._configs

    def list_by_type(self, component_type: ComponentType) -> list[ComponentConfig]:
        """
        列出指定类型的所有配置
        
        Args:
            component_type: 组件类型
            
        Returns:
            配置列表
        """
        return [
            config
            for (ct, _), config in self._configs.items()
            if ct == component_type
        ]

    def list_all(self) -> list[ComponentConfig]:
        """
        列出所有配置
        
        Returns:
            所有配置列表
        """
        return list(self._configs.values())

    def remove(self, component_type: ComponentType, name: str) -> None:
        """
        删除配置
        
        Args:
            component_type: 组件类型
            name: 组件名称
        """
        key = (component_type, name)
        if key in self._configs:
            del self._configs[key]
            logger.debug(f"Removed config: {component_type.value}/{name}")

    def clear(self) -> None:
        """清空所有配置"""
        self._configs.clear()
        logger.debug("Cleared all configs")

    def count(self) -> int:
        """获取配置总数"""
        return len(self._configs)

    def get_names_by_type(self, component_type: ComponentType) -> set[str]:
        """
        获取指定类型的所有组件名称
        
        Args:
            component_type: 组件类型
            
        Returns:
            名称集合
        """
        return {name for (ct, name) in self._configs.keys() if ct == component_type}

    def get_all_names(self) -> set[str]:
        """
        获取所有组件名称
        
        Returns:
            名称集合
        """
        return {name for (_, name) in self._configs.keys()}
