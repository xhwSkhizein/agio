"""
Stage definition for workflow execution.

A Stage represents a single execution step within a workflow,
containing a Runnable reference, input mapping, and optional condition.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union

from agio.workflow.condition import ConditionEvaluator
from agio.workflow.mapping import InputMapping

if TYPE_CHECKING:
    from agio.workflow.protocol import Runnable


@dataclass
class Stage:
    """
    A single execution stage within a Workflow.

    Each Stage contains:
    1. id: unique identifier, also the output reference name
    2. runnable: the unit to execute (Agent/Workflow ID or instance)
    3. input: input template string
    4. condition: optional execution condition
    """

    id: str
    runnable: Union["Runnable", str]  # Runnable instance or reference ID
    input: str  # Template string, e.g., "{query}\n{intent}"
    condition: str | None = None  # Condition expression

    def get_input_mapping(self) -> InputMapping:
        """Get the InputMapping for this stage."""
        return InputMapping(template=self.input)

    def build_input(self, outputs: dict[str, Any]) -> str:
        """Build the input string from available outputs."""
        return self.get_input_mapping().build(outputs)

    def should_execute(self, outputs: dict[str, Any]) -> bool:
        """
        Check if this stage should execute based on condition.

        Returns True if:
        - No condition is set
        - Condition evaluates to True
        """
        if self.condition is None:
            return True
        return ConditionEvaluator.evaluate(self.condition, outputs)

    def get_dependencies(self) -> list[str]:
        """Get all stage IDs this stage depends on."""
        return self.get_input_mapping().get_top_level_dependencies()

    def __repr__(self) -> str:
        runnable_ref = self.runnable if isinstance(self.runnable, str) else self.runnable.id
        return f"Stage(id={self.id!r}, runnable={runnable_ref!r}, condition={self.condition!r})"
