"""
InputMapping for constructing stage inputs from outputs.

This module provides template-based input construction using
variable references like {query}, {stage_id}, {loop.iteration}.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class InputMapping:
    """
    Input mapping - defines how to construct a Stage's input.

    Template syntax:
    - {query}              : original user input
    - {stage_id}           : output of a specific stage
    - {loop.iteration}     : current loop iteration number
    - {loop.last.stage_id} : output of a stage from previous iteration
    """

    template: str

    # Variable matching pattern
    VAR_PATTERN = re.compile(r"\{([^}]+)\}")

    def build(self, outputs: dict[str, Any]) -> str:
        """
        Build input string from template and available outputs.

        Args:
            outputs: available outputs {"stage_id": "output_content", ...}

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
        """Resolve nested variable like loop.last.retrieve."""
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

        For example, "{loop.last.stage_id}" returns "loop".
        """
        deps = self.get_dependencies()
        return list({d.split(".")[0] for d in deps})
