from collections import deque
from dataclasses import dataclass

from agio.config.exceptions import ConfigError
from agio.config.schema import (
    AgentConfig,
    ComponentConfig,
    ComponentType,
    ToolConfig,
    WorkflowConfig,
)
from agio.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyNode:
    """依赖节点"""

    name: str
    component_type: ComponentType
    dependencies: set[str]


class DependencyResolver:
    """
    依赖解析器 - 统一处理依赖关系
    
    职责：
    - 提取配置的依赖关系
    - 拓扑排序
    - 循环依赖检测（fail fast）
    """

    def extract_dependencies(
        self, config: ComponentConfig, available_names: set[str] | None = None
    ) -> set[str]:
        """
        提取配置的依赖（统一入口）
        
        Args:
            config: 组件配置
            available_names: 可用的组件名称集合（用于过滤 built-in 依赖）
            
        Returns:
            依赖名称集合
        """
        deps = set()

        if isinstance(config, AgentConfig):
            deps.update(self._extract_agent_deps(config))
        elif isinstance(config, ToolConfig):
            deps.update(self._extract_tool_deps(config))
        elif isinstance(config, WorkflowConfig):
            deps.update(self._extract_workflow_deps(config))

        if available_names:
            deps = deps & available_names

        return deps

    def _extract_agent_deps(self, config: AgentConfig) -> set[str]:
        """提取 Agent 依赖"""
        deps = {config.model}

        for tool_ref in config.tools:
            from agio.config.tool_reference import parse_tool_reference

            parsed = parse_tool_reference(tool_ref)

            if parsed.type == "function" and parsed.name:
                deps.add(parsed.name)
            elif parsed.type == "agent_tool" and parsed.agent:
                deps.add(parsed.agent)
            elif parsed.type == "workflow_tool" and parsed.workflow:
                deps.add(parsed.workflow)

        if config.memory:
            deps.add(config.memory)
        if config.knowledge:
            deps.add(config.knowledge)
        if config.session_store:
            deps.add(config.session_store)

        return deps

    def _extract_tool_deps(self, config: ToolConfig) -> set[str]:
        """提取 Tool 依赖"""
        return set(config.effective_dependencies.values())

    def _extract_workflow_deps(self, config: WorkflowConfig) -> set[str]:
        """提取 Workflow 依赖（递归处理嵌套）"""
        deps = set()

        if config.session_store:
            deps.add(config.session_store)

        def extract_from_stages(stages: list) -> None:
            for stage in stages:
                if hasattr(stage, "runnable"):
                    runnable = stage.runnable
                elif isinstance(stage, dict):
                    runnable = stage.get("runnable")
                else:
                    continue

                if isinstance(runnable, str):
                    deps.add(runnable)
                elif isinstance(runnable, dict):
                    nested_stages = runnable.get("stages", [])
                    extract_from_stages(nested_stages)

        if hasattr(config, "stages") and config.stages:
            extract_from_stages(config.stages)

        return deps

    def topological_sort(
        self, configs: list[ComponentConfig], available_names: set[str] | None = None
    ) -> list[ComponentConfig]:
        """
        拓扑排序（Kahn's algorithm）
        
        Args:
            configs: 待排序的配置列表
            available_names: 可用的组件名称集合（用于过滤 built-in 依赖）
            
        Returns:
            排序后的配置列表
            
        Raises:
            ConfigError: 检测到循环依赖
        """
        nodes = {}
        for config in configs:
            deps = self.extract_dependencies(config, available_names)

            nodes[config.name] = DependencyNode(
                name=config.name,
                component_type=ComponentType(config.type),
                dependencies=deps,
            )

        in_degree = {name: len(node.dependencies) for name, node in nodes.items()}
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        sorted_names = []

        while queue:
            name = queue.popleft()
            sorted_names.append(name)

            for other_name, node in nodes.items():
                if name in node.dependencies:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        if len(sorted_names) < len(nodes):
            unresolved = set(nodes.keys()) - set(sorted_names)
            
            cycle_info = []
            for name in unresolved:
                deps = nodes[name].dependencies & unresolved
                if deps:
                    cycle_info.append(f"{name} -> {deps}")
            
            raise ConfigError(
                f"Circular dependency detected among: {unresolved}. "
                f"Dependency chains: {'; '.join(cycle_info)}. "
                f"Please check your configuration and break the cycle."
            )

        name_to_config = {config.name: config for config in configs}
        return [name_to_config[name] for name in sorted_names]

    def get_affected_components(
        self, target_name: str, all_metadata: dict[str, "ComponentMetadata"]
    ) -> list[str]:
        """
        获取受影响的组件列表（包括依赖者）- BFS 遍历
        
        Args:
            target_name: 目标组件名称
            all_metadata: 所有组件的元数据
            
        Returns:
            受影响的组件名称列表（拓扑顺序，target_name 在最前）
        """
        affected = [target_name]
        queue = [target_name]

        while queue:
            current = queue.pop(0)
            for comp_name, metadata in all_metadata.items():
                if current in metadata.dependencies and comp_name not in affected:
                    affected.append(comp_name)
                    queue.append(comp_name)

        return affected
