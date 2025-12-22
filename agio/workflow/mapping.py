"""
InputMapping for constructing node inputs from outputs.

This module provides template-based input construction using
variable references like {input}, {node_id.output}, {loop.iteration}.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class InputMapping:
    """
    Input mapping - defines how to construct a node's input.

    Template syntax (aligned with ContextResolver):
    - {input}              : original workflow input
    - {node_id.output}     : output of a specific node
    - {loop.iteration}     : current loop iteration number
    - {loop.last.node_id}  : output of a node from previous iteration
    """

    template: str

    # Variable matching pattern
    VAR_PATTERN = re.compile(r"\{([^}]+)\}")

    def build(self, outputs: dict[str, Any]) -> str:
        """
        Build input string from template and available outputs.

        Args:
            outputs: available outputs {"node_id": "output_content", ...}

        Returns:
            constructed input string
        """

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)

            # Support dot notation for nested access, e.g., loop.last.retrieve
            if "." in var_name:
                return self._resolve_nested(var_name, outputs)

            value = outputs.get(var_name)
            return str(value) if value is not None else ""

        return self.VAR_PATTERN.sub(replace_var, self.template)

    def _resolve_nested(self, var_path: str, outputs: dict) -> str:
        """Resolve nested variable like loop.last.node_id or node_id.output."""
        parts = var_path.split(".")
        current: Any = outputs

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return ""
            else:
                return ""

        return str(current) if current is not None else ""

    def get_dependencies(self) -> list[str]:
        """
        Get all variable names referenced in the template.

        Useful for dependency analysis.
        """
        return self.VAR_PATTERN.findall(self.template)

    def get_top_level_dependencies(self) -> list[str]:
        """
        Get top-level variable names (without nested paths).

        For example, "{loop.last.node_id}" returns "loop".
        """
        deps = self.get_dependencies()
        return list({d.split(".")[0] for d in deps})

    def get_node_dependencies(self) -> list[str]:
        """
        Extract node IDs from template references.

        Handles both {node_id.output} and {loop.last.node_id} patterns.
        Returns only node IDs, filtering out special variables.
        """
        deps = self.get_dependencies()
        node_ids = set()
        special_vars = {"input", "loop", "query"}

        for dep in deps:
            if dep.endswith(".output"):
                # {node_id.output} -> node_id
                node_ids.add(dep[:-7])
            elif dep.startswith("loop.last."):
                # {loop.last.node_id} -> node_id
                node_ids.add(dep[10:])
            elif "." not in dep and dep not in special_vars:
                # Simple reference like {node_id}
                node_ids.add(dep)

        return list(node_ids)
