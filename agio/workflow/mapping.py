"""
InputMapping for extracting dependencies from Jinja2 templates.

This module provides a lightweight wrapper for dependency analysis
on Jinja2 templates used in workflow nodes.
"""

from dataclasses import dataclass

from jinja2 import Environment, meta


@dataclass
class InputMapping:
    """
    Input mapping - extract dependencies from Jinja2 templates.

    Template syntax (Jinja2):
    - {{ input }}              : original workflow input
    - {{ nodes.node_id.output }}: output of a specific node
    - {{ loop.iteration }}     : current loop iteration number
    - {{ loop.last.node_id }}  : output of a node from previous iteration
    """

    template: str

    def get_node_dependencies(self) -> list[str]:
        """
        Extract node IDs from template references.

        Handles {{ nodes.node_id.output }} and {{ loop.last.node_id }} patterns.
        Returns only node IDs, filtering out special variables.

        Examples:
            "{{ nodes.analyze.output }}" -> ["analyze"]
            "{{ loop.last.retrieve }}" -> ["retrieve"]
            "{{ input }}" -> []
        """
        env = Environment()
        try:
            ast = env.parse(self.template)
            variables = meta.find_undeclared_variables(ast)
        except Exception:
            return []

        node_ids = set()
        for var in variables:
            # Handle "nodes" prefix: nodes.node_id.output
            if var == "nodes":
                # Need to parse more carefully - look for attribute access
                # For now, use simple heuristic: extract node_id from template
                import re

                # Match {{ nodes.NODE_ID.output }}
                pattern = r"\{\{\s*nodes\.(\w+)\.output\s*\}\}"
                matches = re.findall(pattern, self.template)
                node_ids.update(matches)

            # Handle "loop.last" prefix: loop.last.node_id
            if var == "loop":
                import re

                # Match {{ loop.last.NODE_ID }}
                pattern = r"\{\{\s*loop\.last\.(\w+)\s*\}\}"
                matches = re.findall(pattern, self.template)
                node_ids.update(matches)

        return list(node_ids)
