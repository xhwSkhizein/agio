"""
ContextResolver - Resolve template variables from SessionStore.

This module provides template variable resolution for workflow execution,
allowing nodes to reference outputs from previous nodes and other context.

Supported variables (Jinja2 syntax):
- {{ nodes.node_id.output }} - Output from a specific node
- {{ input }} - Original workflow input
- {{ loop.iteration }} - Current loop iteration (for LoopWorkflow)
- {{ loop.last.node_id }} - Last iteration output for a node
- {{ env.VAR_NAME }} - Environment variable
"""

import os
from typing import Any

from agio.config.template import renderer
from agio.storage.session.base import SessionStore
from agio.workflow.state import WorkflowState


class ContextResolver:
    """
    Resolve template variables from workflow context using Jinja2.

    Supports variable references (Jinja2 syntax):
    - {{ nodes.node_a.output }} - Get output from node_a
    - {{ input }} - Original workflow input
    - {{ loop.iteration }} - Current loop iteration
    - {{ loop.last.node_id }} - Last iteration output
    - {{ env.VAR_NAME }} - Environment variable
    """

    def __init__(
        self,
        session_id: str,
        workflow_id: str,
        store: "SessionStore",
        state: WorkflowState | None = None,
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
        self._input: str | None = None
        self._loop_context: dict[str, Any] = {}

    def set_input(self, input: str) -> None:
        """Set the original workflow input."""
        self._input = input

    def set_loop_context(self, iteration: int, last_outputs: dict[str, str]) -> None:
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

    async def get_node_output(self, node_id: str) -> str | None:
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
        additional_vars: dict[str, Any] | None = None,
    ) -> str:
        """
        Resolve template string using Jinja2.

        Supported variable patterns (Jinja2 syntax):
        - {{ nodes.node_id.output }} - Node output
        - {{ input }} - Workflow input
        - {{ loop.iteration }} - Loop iteration
        - {{ loop.last.node_id }} - Last iteration output
        - {{ env.VAR_NAME }} - Environment variable

        Args:
            template: Template string with Jinja2 syntax
            additional_vars: Additional variables to inject

        Returns:
            Rendered template string
        """
        # Build nodes dictionary (lazy-loaded as needed)
        nodes = await self._build_nodes_dict()

        # Build context with all available variables
        context = {
            "input": self._input or "",
            "nodes": nodes,
            "env": os.environ,
        }

        if self._loop_context:
            context["loop"] = self._loop_context

        if additional_vars:
            context.update(additional_vars)

        # Render using Jinja2
        return renderer.render(template, **context)

    async def _build_nodes_dict(self) -> dict[str, dict[str, str]]:
        """Build nodes dictionary from state cache.

        Returns:
            Dictionary mapping node_id to {output: content}
        """
        nodes = {}

        # If we have state, use it to get available nodes
        if self.state:
            for node_id in self.state._outputs.keys():
                output = self.state.get_output(node_id)
                if output is not None:
                    nodes[node_id] = {"output": output}

        return nodes
