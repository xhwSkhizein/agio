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
from uuid import uuid4

from agio.workflow.protocol import Runnable, RunContext, RunOutput
from agio.workflow.stage import Stage


class BaseWorkflow(ABC):
    """
    Abstract base class for all Workflow types.

    Implements the Runnable protocol, enabling workflows to be:
    - Called via unified API
    - Nested within other workflows
    - Used as tools (WorkflowAsTool)
    """

    def __init__(self, id: str, stages: list[Stage]):
        self._id = id
        self._stages = stages
        self._registry: dict[str, Runnable] = {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def stages(self) -> list[Stage]:
        """Get the list of stages."""
        return self._stages

    def set_registry(self, registry: dict[str, Runnable]):
        """Set the runnable registry for resolving references."""
        self._registry = registry

    async def run(
        self,
        input: str,
        *,
        context: RunContext,
    ) -> RunOutput:
        """
        Execute the workflow, writing events to context.wire.
        
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
        context: RunContext,
    ) -> RunOutput:
        """Subclass implementation of workflow execution logic."""
        ...

    def _create_child_context(
        self,
        context: RunContext,
        stage: Stage,
    ) -> RunContext:
        """
        Create execution context for child Runnable.

        Each Agent gets an independent session for isolation.
        Wire is shared across all nested executions.
        """
        return RunContext(
            wire=context.wire,  # Share wire for event streaming
            session_id=str(uuid4()),  # Independent session per Agent
            user_id=context.user_id,
            workflow_id=self._id,  # Pass workflow ID for session grouping
            trace_id=context.trace_id or str(uuid4()),
            parent_span_id=context.parent_span_id,
            parent_stage_id=stage.id,
            depth=context.depth + 1,
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
        return f"{self.__class__.__name__}(id={self._id!r}, stages={len(self._stages)})"
