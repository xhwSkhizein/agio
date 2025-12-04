"""
BaseWorkflow - abstract base class for all workflow types.

Provides common functionality for workflow execution including:
- Runnable protocol implementation
- Child context creation
- Runnable resolution from registry
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator
from uuid import uuid4

from agio.workflow.protocol import Runnable, RunContext
from agio.workflow.stage import Stage

if TYPE_CHECKING:
    from agio.domain.events import StepEvent


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
        self._last_output: str | None = None
        self._registry: dict[str, Runnable] = {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def last_output(self) -> str | None:
        return self._last_output

    @property
    def stages(self) -> list[Stage]:
        """Get the list of stages."""
        return self._stages

    def set_registry(self, registry: dict[str, Runnable]):
        """Set the runnable registry for resolving references."""
        self._registry = registry

    @abstractmethod
    async def run(
        self,
        input: str,
        *,
        context: RunContext | None = None,
    ) -> AsyncIterator["StepEvent"]:
        """Execute the workflow and yield events."""
        ...

    def _create_child_context(
        self,
        context: RunContext | None,
        stage: Stage,
    ) -> RunContext:
        """
        Create execution context for child Runnable.

        Each Agent gets an independent session for isolation.
        """
        return RunContext(
            session_id=str(uuid4()),  # Independent session per Agent
            user_id=context.user_id if context else None,
            workflow_id=self._id,  # Pass workflow ID for session grouping
            trace_id=context.trace_id if context else str(uuid4()),
            parent_span_id=context.parent_span_id if context else None,
            parent_stage_id=stage.id,
            depth=(context.depth if context else 0) + 1,
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
