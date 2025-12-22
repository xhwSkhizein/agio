"""
ContextResolver - Resolve template variables from SessionStore.

This module provides template variable resolution for workflow execution,
allowing nodes to reference outputs from previous nodes and other context.

Supported variables:
- {node_id.output} - Output from a specific node
- {input} - Original workflow input
- {loop.iteration} - Current loop iteration (for LoopWorkflow)
- {loop.last.node_id} - Last iteration output for a node
"""

import re
from typing import TYPE_CHECKING, Dict, Optional, Any

if TYPE_CHECKING:
    from agio.providers.storage.base import SessionStore
    from agio.workflow.state import WorkflowState


class ContextResolver:
    """
    Resolve template variables from workflow context.

    Supports variable references like:
    - {node_a.output} - Get output from node_a
    - {input} - Original workflow input
    - {loop.iteration} - Current loop iteration
    - {loop.last.node_id} - Last iteration output
    """

    def __init__(
        self,
        session_id: str,
        workflow_id: str,
        store: "SessionStore",
        state: Optional["WorkflowState"] = None,
    ):
        """
        Initialize ContextResolver.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID for querying steps (persists across run_id changes)
            store: SessionStore for querying steps
            state: Optional WorkflowState for cached lookups
        """
        self.session_id = session_id
        self.workflow_id = workflow_id
        self.store = store
        self.state = state
        self._input: Optional[str] = None
        self._loop_context: Dict[str, Any] = {}

    def set_input(self, input: str) -> None:
        """Set the original workflow input."""
        self._input = input

    def set_loop_context(self, iteration: int, last_outputs: Dict[str, str]) -> None:
        """
        Set loop context for LoopWorkflow.

        Args:
            iteration: Current iteration number
            last_outputs: Dictionary of node_id -> last iteration output
        """
        self._loop_context = {
            "iteration": iteration,
            "last": last_outputs,
        }

    async def get_node_output(self, node_id: str) -> Optional[str]:
        """
        Get output for a specific node.

        First checks WorkflowState cache, then falls back to database query.

        Args:
            node_id: Node ID

        Returns:
            Node output content, or None if not found
        """
        # Try cache first
        if self.state:
            cached = self.state.get_output(node_id)
            if cached is not None:
                return cached

        # Fall back to database query with workflow_id isolation
        return await self.store.get_last_assistant_content(
            session_id=self.session_id,
            workflow_id=self.workflow_id,
            node_id=node_id,
        )

    async def resolve_template(
        self,
        template: str,
        additional_vars: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Resolve template string with variable substitution.

        Supported variable patterns:
        - {node_id.output} - Node output
        - {input} - Workflow input
        - {loop.iteration} - Loop iteration
        - {loop.last.node_id} - Last iteration output

        Args:
            template: Template string with {variable} placeholders
            additional_vars: Additional variables to inject

        Returns:
            Resolved template string
        """
        vars_dict: Dict[str, Any] = {}
        if additional_vars:
            vars_dict.update(additional_vars)

        # Add input variable
        if self._input is not None:
            vars_dict["input"] = self._input

        # Add loop context
        if self._loop_context:
            vars_dict["loop"] = self._loop_context

        # Find all variable references: {variable} or {node_id.output}
        pattern = r"\{([^}]+)\}"
        matches = re.findall(pattern, template)

        resolved_vars: Dict[str, str] = {}

        for var_expr in matches:
            if var_expr in resolved_vars:
                continue

            # Handle node output references: {node_id.output}
            if var_expr.endswith(".output"):
                node_id = var_expr[:-7]  # Remove ".output"
                output = await self.get_node_output(node_id)
                resolved_vars[var_expr] = output or ""
            # Handle loop.last.node_id
            elif var_expr.startswith("loop.last."):
                node_id = var_expr[10:]  # Remove "loop.last."
                if self._loop_context and "last" in self._loop_context:
                    last_outputs = self._loop_context["last"]
                    resolved_vars[var_expr] = last_outputs.get(node_id, "")
                else:
                    resolved_vars[var_expr] = ""
            # Handle nested variables: {loop.iteration}
            elif "." in var_expr:
                parts = var_expr.split(".")
                current = vars_dict
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                        if current is None:
                            break
                    else:
                        current = None
                        break
                resolved_vars[var_expr] = str(current) if current is not None else ""
            # Handle simple variables: {input}
            elif var_expr in vars_dict:
                value = vars_dict[var_expr]
                resolved_vars[var_expr] = str(value) if value is not None else ""
            else:
                # Unknown variable, leave as-is or empty
                resolved_vars[var_expr] = ""

        # Replace all variables in template
        result = template
        for var_expr, value in resolved_vars.items():
            result = result.replace(f"{{{var_expr}}}", value)

        return result
