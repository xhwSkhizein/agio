"""
WorkflowNode - Configuration model for workflow nodes.

This module provides the WorkflowNode configuration model, which replaces
Stage as a pure configuration object (no runtime state).

WorkflowNode is used at configuration time to define workflow structure,
while execution happens at Step level.
"""

from typing import Union, Any
from pydantic import BaseModel
from agio.workflow.mapping import InputMapping


class WorkflowNode(BaseModel):
    """
    Pure configuration object for a workflow node.

    This is a static configuration that defines:
    - What to run (runnable)
    - How to build input (input_template)
    - When to run (condition)

    No runtime state is stored here - all execution state is in Steps.
    """

    id: str  # Node unique identifier (replaces stage_id)
    runnable: Union[Any, str]  # Agent or SubWorkflow (instance or reference ID)
    input_template: (
        str  # Input template string, e.g., "用户说: {input}, 上一步结果: {node_a.output}"
    )
    condition: str | None = None  # Optional execution condition

    model_config = {"arbitrary_types_allowed": True}

    def get_dependencies(self) -> list[str]:
        """
        Get all node IDs this node depends on based on input_template.

        Handles both {node_id.output} and {loop.last.node_id} patterns.

        Returns:
            List of node IDs referenced in input_template (e.g., ["node_a", "node_b"])
        """

        mapping = InputMapping(template=self.input_template)
        return mapping.get_node_dependencies()

    def __repr__(self) -> str:
        runnable_ref = self.runnable if isinstance(self.runnable, str) else self.runnable.id
        return (
            f"WorkflowNode(id={self.id!r}, runnable={runnable_ref!r}, condition={self.condition!r})"
        )
