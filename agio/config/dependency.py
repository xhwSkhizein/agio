"""
Dependency Resolver - Dependency extraction and topological sorting.

Extracts configuration dependencies, performs topological sorting,
and detects circular dependencies.
"""

from collections import deque
from dataclasses import dataclass

from agio.config.container import ComponentMetadata
from agio.config.exceptions import ConfigError
from agio.config.schema import (
    AgentConfig,
    ComponentConfig,
    ComponentType,
    SessionStoreConfig,
    ToolConfig,
    TraceStoreConfig,
)
from agio.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyNode:
    """Dependency node."""

    name: str
    component_type: ComponentType
    dependencies: set[str]


class DependencyResolver:
    """
    Dependency resolver - unified dependency handling.

    Responsibilities:
    - Extract configuration dependencies
    - Topological sorting
    - Circular dependency detection (fail fast)
    """

    def extract_dependencies(
        self, config: ComponentConfig
    ) -> set[str]:
        """
        Extract configuration dependencies (unified entry point).

        Args:
            config: Component configuration

        Returns:
            Set of dependency names
        """
        deps = set()

        if isinstance(config, AgentConfig):
            deps.update(self._extract_agent_deps(config))
        elif isinstance(config, ToolConfig):
            deps.update(self._extract_tool_deps(config))

        return deps

    def _extract_agent_deps(self, config: AgentConfig) -> set[str]:
        """Extract Agent dependencies."""
        deps = {config.model}

        for tool_ref in config.tools:
            from agio.config.tool_reference import parse_tool_reference

            parsed = parse_tool_reference(tool_ref)

            if parsed.tool_type == "regular_tool" and parsed.tool_name:
                deps.add(parsed.tool_name)
            elif parsed.tool_type == "agent_tool" and parsed.agent_name:
                deps.add(parsed.agent_name)

        if config.session_store:
            deps.add(config.session_store)

        return deps

    def _extract_tool_deps(self, config: ToolConfig) -> set[str]:
        """Extract Tool dependencies."""
        return set(config.effective_dependencies.values())

    def _extract_tool_reference_dependencies(self, stage: dict) -> set[str]:
        """Extract Tool reference dependencies."""
        deps = set()

        if "runnable" in stage:
            runnable = stage["runnable"]
        else:
            return deps

        if isinstance(runnable, str):
            deps.add(runnable)
        elif isinstance(runnable, dict):
            nested_stages = runnable.get("stages", [])
            for stage in nested_stages:
                deps.update(self._extract_tool_reference_dependencies(stage))

        return deps

    def topological_sort(
        self, configs: list[ComponentConfig]
    ) -> list[ComponentConfig]:
        """
        Topological sort (Kahn's algorithm) with type-name isolation.

        Args:
            configs: List of configurations to sort

        Returns:
            Sorted list of configurations
        """
        nodes = {}
        # Key by (type, name) to support name reuse across different types
        available_configs = {(ComponentType(c.type), c.name) for c in configs}

        for config in configs:
            ctype = ComponentType(config.type)
            deps = self.extract_dependencies(config)

            # Validate dependencies: must exist in available_configs
            for dep_name in deps:
                found_dep = False
                for prov_type in ComponentType:
                    if (prov_type, dep_name) in available_configs:
                        if self._is_compatible_dependency(ctype, prov_type):
                            found_dep = True
                            break
                
                if not found_dep:
                    # Check if it might be an internal tool or other built-in
                    # For now, if it's not in configs, it's missing or disabled
                    logger.warning(
                        f"Component '{ctype.value}/{config.name}' depends on '{dep_name}', "
                        f"but no enabled component with that name was found."
                    )

            nodes[(ctype, config.name)] = DependencyNode(
                name=config.name,
                component_type=ctype,
                dependencies=deps,
            )

        # Build adjacency list: name -> set of (type, name)
        # This helps mapping a dependency 'name' to all possible component nodes
        name_to_nodes = {}
        for key in nodes:
            name = key[1]
            if name not in name_to_nodes:
                name_to_nodes[name] = set()
            name_to_nodes[name].add(key)

        in_degree = {key: 0 for key in nodes}
        for key, node in nodes.items():
            for dep_name in node.dependencies:
                # If dep_name exists as a built-in or other component
                if dep_name in name_to_nodes:
                    for dep_key in name_to_nodes[dep_name]:
                        # Cross-type dependency handling:
                        # Agents depend on Models and Tools.
                        # Tools depend on other Stores.
                        # We only count it as an edge if the types are compatible.
                        if self._is_compatible_dependency(node.component_type, dep_key[0]):
                            in_degree[key] += 1

        queue = deque([key for key, degree in in_degree.items() if degree == 0])
        sorted_keys = []

        while queue:
            key = queue.popleft()
            sorted_keys.append(key)

            # Find nodes that depend on this one
            for other_key, node in nodes.items():
                if key[1] in node.dependencies and self._is_compatible_dependency(node.component_type, key[0]):
                    in_degree[other_key] -= 1
                    if in_degree[other_key] == 0:
                        queue.append(other_key)

        if len(sorted_keys) < len(nodes):
            unresolved = set(nodes.keys()) - set(sorted_keys)
            raise ConfigError(f"Circular dependency detected among: {unresolved}")

        key_to_config = {(ComponentType(c.type), c.name): c for c in configs}
        return [key_to_config[key] for key in sorted_keys]

    def _is_compatible_dependency(self, consumer_type: ComponentType, provider_type: ComponentType) -> bool:
        """Check if provider_type is a valid dependency for consumer_type."""
        if consumer_type == ComponentType.AGENT:
            return provider_type in [
                ComponentType.MODEL,
                ComponentType.TOOL,
                ComponentType.SESSION_STORE,
                ComponentType.AGENT,
            ]
        if consumer_type == ComponentType.TOOL:
            return provider_type in [
                ComponentType.SESSION_STORE,
                ComponentType.TRACE_STORE,
                ComponentType.CITATION_STORE,
                ComponentType.MODEL,
                ComponentType.AGENT,
            ]
        return False

    def get_affected_components(
        self, 
        target_name: str, 
        target_type: ComponentType,
        all_metadata: dict[tuple[ComponentType, str], ComponentMetadata]
    ) -> list[tuple[ComponentType, str]]:
        """
        Get list of affected components (including dependents) - BFS traversal.

        Args:
            target_name: Target component name
            target_type: Target component type
            all_metadata: Metadata of all components

        Returns:
            List of affected component (type, name) tuples (target first)
        """
        target_key = (target_type, target_name)
        affected = [target_key]
        queue = [target_key]

        while queue:
            current_type, current_name = queue.pop(0)
            for comp_key, metadata in all_metadata.items():
                # Check if current component is a dependency of comp_key
                # We check by name and compatibility
                if current_name in metadata.dependencies:
                    # Verify if the dependency is actually this specific component type
                    # (In a real scenario, the consumer knows which type it depends on)
                    if self._is_compatible_dependency(comp_key[0], current_type):
                        if comp_key not in affected:
                            affected.append(comp_key)
                            queue.append(comp_key)

        return affected
