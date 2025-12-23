"""
BaseWorkflow - abstract base class for all workflow types.

Provides common functionality for workflow execution including:
- Runnable protocol implementation
- Child context creation
- Runnable resolution from registry

Wire-based Architecture:
- run() writes events to context.wire
- run() returns RunOutput (response + metrics)
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import uuid4

from agio.domain import ExecutionContext
from agio.domain.protocol import Runnable, RunOutput
from agio.workflow.node import WorkflowNode

if TYPE_CHECKING:
    from agio.providers.storage.base import SessionStore


class BaseWorkflow(ABC):
    """
    Abstract base class for all Workflow types.

    Implements the Runnable protocol, enabling workflows to be:
    - Called via unified API
    - Nested within other workflows
    - Used as tools (WorkflowAsTool)
    """

    def __init__(
        self,
        id: str,
        stages: list[WorkflowNode],
        session_store: "SessionStore | None" = None,
    ):
        self._id = id
        self._nodes = stages
        self._session_store = session_store
        self._registry: dict[str, Runnable] = {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def runnable_type(self) -> str:
        """Return runnable type identifier."""
        return "workflow"

    @property
    def nodes(self) -> list[WorkflowNode]:
        """Get the list of nodes."""
        return self._nodes


    def set_registry(self, registry: dict[str, Runnable]):
        """Set the runnable registry for resolving references."""
        self._registry = registry

    async def run(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
        """
        Execute the workflow, writing events to context.wire.
        
        Note: Run lifecycle events (RUN_STARTED/COMPLETED/FAILED) are handled
        by RunnableExecutor, not here.
        
        Args:
            input: Input string
            context: Execution context with wire (required)
            
        Returns:
            RunOutput with response and metrics
        """
        if not context.wire:
            raise ValueError("context.wire is required for workflow execution")

        return await self._execute(input, context=context)

    @abstractmethod
    async def _execute(
        self,
        input: str,
        *,
        context: ExecutionContext,
    ) -> RunOutput:
        """Subclass implementation of workflow execution logic."""
        ...

    def _create_child_context(
        self,
        context: ExecutionContext,
        node: WorkflowNode,
    ) -> ExecutionContext:
        """
        Create execution context for child Runnable.

        Unified Session: All nested executions share the same session_id.
        Each child gets a new run_id for isolation at run level.
        Wire is shared across all nested executions.
        """
        # Generate new run_id for the child runnable
        new_run_id = str(uuid4())

        node_id = node.id
        runnable_id = node.runnable if isinstance(node.runnable, str) else node.runnable.id

        # Unified Session: use parent's session_id (no new session)
        # This allows all Steps to be stored in the same session
        return context.child(
            run_id=new_run_id,
            session_id=context.session_id,  # Unified session - no new session_id
            nested_runnable_id=runnable_id,
            workflow_id=self._id,  # Pass current workflow ID
            node_id=node_id,  # node_id for WorkflowNode tracking
            nesting_type="workflow_node",  # Mark as workflow internal node
        )

    def _resolve_runnable(self, ref: Runnable | str) -> Runnable:
        """
        Resolve a Runnable reference to an instance.

        Args:
            ref: Either a Runnable instance or a string ID

        Returns:
            Runnable instance

        Raises:
            ValueError: If reference cannot be resolved
        """
        if isinstance(ref, str):
            if ref not in self._registry:
                raise ValueError(f"Runnable not found in registry: {ref}")
            return self._registry[ref]
        return ref

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id!r}, nodes={len(self._nodes)})"
