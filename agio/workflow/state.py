"""
WorkflowState - In-memory cache for workflow node outputs.

This module provides state management for workflow execution, caching
intermediate results to avoid repeated database queries.

Key features:
- O(1) lookup for node outputs
- Batch loading from history for resume scenarios
- Idempotency support: check if node already executed
"""

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from agio.providers.storage.base import SessionStore


class WorkflowState:
    """
    In-memory state cache for workflow execution.

    Manages node outputs within a single workflow run, providing:
    - Fast O(1) access to cached outputs
    - Batch loading from database for resume scenarios
    - Idempotency checks (has node executed?)

    Each WorkflowState instance is bound to a specific workflow_id and session_id,
    managing outputs of nodes across all runs of that workflow in the session.
    This supports Fork+Resume scenarios where run_id changes but workflow state persists.
    """

    def __init__(
        self,
        session_id: str,
        workflow_id: str,
        store: "SessionStore",
    ):
        """
        Initialize WorkflowState.

        Args:
            session_id: Session ID
            workflow_id: Workflow ID (state persists across run_id changes)
            store: SessionStore for loading history
        """
        self.session_id = session_id
        self.workflow_id = workflow_id
        self._store = store
        # Memory cache: node_id -> output_content
        self._outputs: Dict[str, str] = {}
        self._loaded = False

    async def load_from_history(self) -> None:
        """
        Batch load historical outputs from database.

        This method should be called once at the start of workflow execution
        (especially for resume scenarios) to populate the cache with existing
        node outputs.

        After loading, get_output() will return cached values without
        database queries.
        """
        if self._loaded:
            return

        # Load all steps for this workflow_id (persists across run_id changes)
        steps = await self._store.get_steps(
            session_id=self.session_id,
            workflow_id=self.workflow_id,
            limit=10000,  # Large limit to get all steps
        )

        # Rebuild cache: find last assistant step for each node_id
        # Process in sequence order to ensure we get the latest output
        # Note: We check for node_id existence, not content, to cache empty outputs too
        for step in steps:
            if step.role.value == "assistant" and step.node_id is not None:
                # Cache the output even if it's an empty string
                # This ensures idempotency: empty output means node executed, None means not executed
                self._outputs[step.node_id] = step.content or ""

        self._loaded = True

    def _make_key(self, node_id: str, iteration: Optional[int] = None) -> str:
        """Create cache key, optionally including iteration for LoopWorkflow."""
        if iteration is not None:
            return f"{node_id}:iter_{iteration}"
        return node_id

    def get_output(self, node_id: str, iteration: Optional[int] = None) -> Optional[str]:
        """
        Get cached output for a node.

        Args:
            node_id: Node ID
            iteration: Loop iteration (optional, for LoopWorkflow)

        Returns:
            Cached output content, or None if not found
        """
        key = self._make_key(node_id, iteration)
        return self._outputs.get(key)

    def set_output(self, node_id: str, content: str, iteration: Optional[int] = None) -> None:
        """
        Update cached output for a node.

        Args:
            node_id: Node ID
            content: Output content
            iteration: Loop iteration (optional, for LoopWorkflow)
        """
        key = self._make_key(node_id, iteration)
        self._outputs[key] = content

    def has_output(self, node_id: str, iteration: Optional[int] = None) -> bool:
        """
        Check if a node has cached output (idempotency check).

        Distinguishes between:
        - "output exists but is empty" (node executed, return True)
        - "output doesn't exist yet" (node not executed, return False)

        Args:
            node_id: Node ID
            iteration: Loop iteration (optional, for LoopWorkflow)

        Returns:
            True if node output exists in cache (even if empty string)
        """
        key = self._make_key(node_id, iteration)
        return key in self._outputs

    def clear(self) -> None:
        """Clear all cached outputs."""
        self._outputs.clear()
        self._loaded = False

    def to_dict(self) -> Dict[str, str]:
        """
        Convert state to dictionary (for debugging/logging).

        Returns:
            Dictionary mapping node_id to output content
        """
        return dict(self._outputs)

