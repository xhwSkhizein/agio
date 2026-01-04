from typing import Any, Callable

from agio.config.builder_registry import BuilderRegistry
from agio.config.container import ComponentContainer
from agio.config.dependency import DependencyResolver
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class HotReloadManager:
    """
    热重载管理器

    职责：
    - 配置变更检测
    - 级联重建受影响的组件
    - 通知变更回调
    """

    def __init__(
        self,
        container: ComponentContainer,
        dependency_resolver: DependencyResolver,
        builder_registry: BuilderRegistry,
    ):
        self._container = container
        self._dependency_resolver = dependency_resolver
        self._builder_registry = builder_registry
        self._callbacks: list[Callable[[str, str], None]] = []

    def register_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        注册变更回调

        Args:
            callback: 回调函数 (name, change_type) -> None
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        注销变更回调

        Args:
            callback: 回调函数
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def handle_change(
        self,
        name: str,
        change_type: str,
        rebuild_func: Callable[[str], Any] | None = None,
    ) -> None:
        """
        处理配置变更

        Args:
            name: 变更的组件名称
            change_type: 变更类型（create/update/delete）
            rebuild_func: 重建函数（可选）
        """
        logger.info(f"Handling config change: {name} ({change_type})")

        affected = self._get_affected_components(name)
        logger.debug(f"Affected components: {affected}")

        await self._destroy_affected(affected)

        if rebuild_func and change_type in ("create", "update"):
            await self._rebuild_affected(affected, rebuild_func)

        self._notify_callbacks(name, change_type)

    async def _destroy_affected(self, affected: list[str]) -> None:
        """
        销毁受影响的组件（逆序）

        Args:
            affected: 受影响的组件名称列表
        """
        for comp_name in reversed(affected):
            instance, metadata = self._container.remove(comp_name)

            if instance is not None and metadata is not None:
                builder = self._builder_registry.get(metadata.component_type)
                if builder:
                    try:
                        await builder.cleanup(instance)
                    except Exception as e:
                        logger.error(f"Failed to cleanup {comp_name}: {e}")

    async def _rebuild_affected(
        self, affected: list[str], rebuild_func: Callable[[str], Any]
    ) -> None:
        """
        重建受影响的组件（正序）

        Args:
            affected: 受影响的组件名称列表
            rebuild_func: 重建函数
        """
        for comp_name in affected:
            try:
                await rebuild_func(comp_name)
            except Exception as e:
                logger.error(f"Failed to rebuild {comp_name}: {e}")

    def _get_affected_components(self, name: str) -> list[str]:
        """
        获取受影响的组件列表（BFS 遍历依赖图）

        Args:
            name: 组件名称

        Returns:
            受影响的组件名称列表（拓扑顺序）
        """
        all_metadata = self._container.get_all_metadata()
        return self._dependency_resolver.get_affected_components(name, all_metadata)

    def _notify_callbacks(self, name: str, change_type: str) -> None:
        """
        通知变更回调

        Args:
            name: 组件名称
            change_type: 变更类型
        """
        for callback in self._callbacks:
            try:
                callback(name, change_type)
            except Exception as e:
                logger.error(f"Hot reload callback error: {e}")
