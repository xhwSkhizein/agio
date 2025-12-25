"""
Runnable protocol and RunOutput for unified execution interface.

This module defines the core abstractions for executable units:
- Runnable: protocol for Agent and Workflow
- RunOutput: execution result with response and metrics
- ExecutionContext: Unified execution context abstraction
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agio.domain.models import RunMetrics
from agio.runtime.wire import Wire


@dataclass
class RunOutput:
    """
    Execution result from Runnable.run().

    Contains both the response and execution metrics.
    """

    response: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    metrics: "RunMetrics | None" = None

    # Additional context
    workflow_id: str | None = None
    termination_reason: str | None = None  # "max_steps", "max_iterations", etc.
    error: str | None = None


@runtime_checkable
class Runnable(Protocol):
    """
    Unified protocol for executable units.

    Both Agent and Workflow implement this interface, enabling:
    1. Unified API invocation
    2. Mutual nesting and composition
    3. Use as Tool (AgentAsTool, WorkflowAsTool)

    Wire-based execution:
    - run() requires context.wire
    - Events are written to wire
    - Returns RunOutput (response + metrics)
    """

    @property
    def id(self) -> str:
        """Unique identifier."""
        ...

    @property
    def runnable_type(self) -> str:
        """
        Return the type of this Runnable.

        - Agent returns "agent"
        - Workflow returns "workflow"

        Used by RunnableExecutor to determine run type without
        instanceof checks on concrete classes.
        """
        ...

    async def run(
        self,
        input: str,
        *,
        context: "ExecutionContext",
    ) -> "RunOutput":
        """
        Execute and write events to context.wire.

        Args:
            input: Input string
            context: Execution context with wire (required)

        Returns:
            RunOutput containing response and metrics
        """
        ...


@dataclass(frozen=True)
class ExecutionContext:
    """
    Immutable execution context.

    All execution components share this context. Use child() to create
    nested contexts with incremented depth and updated parent references.

    Attributes:
        run_id: Current run identifier
        session_id: Session identifier
        wire: Event streaming channel
        user_id: User identifier (optional)
        workflow_id: Workflow identifier (optional)
        depth: Nesting depth (0 = top-level)
        parent_run_id: Parent run ID for nested executions
        nested_runnable_id: ID of the nested Runnable being executed
        runnable_type: Type of Runnable ("agent" | "workflow")
        runnable_id: Runnable configuration ID
        nesting_type: How this execution was triggered ("tool_call" | "workflow_node" | None)
        node_id: Current WorkflowNode.id being executed
        trace_id: Distributed tracing ID
        span_id: Current span ID
        metadata: Additional metadata
    """

    # Execution identity
    run_id: str
    session_id: str

    # Session-level resources
    wire: Wire

    # User & Workflow Context
    user_id: str | None = None
    workflow_id: str | None = None

    # Hierarchy information
    depth: int = 0
    parent_run_id: str | None = None
    nested_runnable_id: str | None = None
    
    # Runnable identity (for unified display)
    runnable_type: str = "agent"           # "agent" | "workflow"
    runnable_id: str | None = None         # Runnable config ID
    nesting_type: str | None = None        # "tool_call" | "workflow_node" | None
    
    node_id: str | None = None  # Current WorkflowNode.id being executed
    iteration: int | None = None  # Current loop iteration (for LoopWorkflow)

    # Observability
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def child(
        self,
        run_id: str,
        nested_runnable_id: str | None = None,
        session_id: str | None = None,
        **overrides,
    ) -> "ExecutionContext":
        """
        Create a child context for nested execution.

        Args:
            run_id: New run ID for the nested execution
            nested_runnable_id: ID of the nested Runnable
            session_id: Optional new session ID (defaults to parent's)
            **overrides: Additional fields to override

        Returns:
            New ExecutionContext with incremented depth
        """
        # Copy metadata to avoid shared mutable state
        # If metadata is provided in overrides, merge it with parent's metadata
        # Otherwise, create a shallow copy of parent's metadata
        metadata_override = overrides.get("metadata")
        if metadata_override is None:
            metadata = dict(self.metadata)  # Create a shallow copy
        else:
            # Merge parent's metadata with overrides
            metadata = dict(self.metadata)  # Start with parent's copy
            metadata.update(metadata_override)  # Update with overrides

        return ExecutionContext(
            run_id=run_id,
            session_id=session_id or self.session_id,
            wire=self.wire,
            user_id=overrides.get("user_id", self.user_id),
            workflow_id=overrides.get("workflow_id", self.workflow_id),
            depth=self.depth + 1,
            parent_run_id=self.run_id,
            nested_runnable_id=nested_runnable_id,
            runnable_type=overrides.get("runnable_type", "agent"),
            runnable_id=overrides.get("runnable_id"),
            nesting_type=overrides.get("nesting_type"),
            node_id=overrides.get("node_id", None),
            iteration=overrides.get("iteration", None),
            trace_id=self.trace_id,
            span_id=None,  # New span for child
            parent_span_id=self.span_id,
            metadata=metadata,
        )

    def with_metadata(self, **kvs) -> "ExecutionContext":
        """
        Create a copy with updated metadata.

        This is a convenience method for adding metadata without
        changing other fields. Useful for adding branch_key etc.

        Args:
            **kvs: Key-value pairs to add/update in metadata

        Returns:
            New ExecutionContext with merged metadata
        """
        new_metadata = dict(self.metadata)
        new_metadata.update(kvs)
        return ExecutionContext(
            run_id=self.run_id,
            session_id=self.session_id,
            wire=self.wire,
            user_id=self.user_id,
            workflow_id=self.workflow_id,
            depth=self.depth,
            parent_run_id=self.parent_run_id,
            nested_runnable_id=self.nested_runnable_id,
            runnable_type=self.runnable_type,
            runnable_id=self.runnable_id,
            nesting_type=self.nesting_type,
            node_id=self.node_id,
            iteration=self.iteration,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            metadata=new_metadata,
        )

    def with_iteration(self, iteration: int) -> "ExecutionContext":
        """
        Create a copy with updated iteration number.

        Args:
            iteration: Loop iteration number (1-indexed)

        Returns:
            New ExecutionContext with updated iteration
        """
        return ExecutionContext(
            run_id=self.run_id,
            session_id=self.session_id,
            wire=self.wire,
            user_id=self.user_id,
            workflow_id=self.workflow_id,
            depth=self.depth,
            parent_run_id=self.parent_run_id,
            nested_runnable_id=self.nested_runnable_id,
            runnable_type=self.runnable_type,
            runnable_id=self.runnable_id,
            nesting_type=self.nesting_type,
            node_id=self.node_id,
            iteration=iteration,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            metadata=dict(self.metadata),
        )

    @property
    def is_nested(self) -> bool:
        """Check if this is a nested execution context."""
        return self.depth > 0

    def __repr__(self) -> str:
        return (
            f"ExecutionContext(run_id={self.run_id!r}, "
            f"session_id={self.session_id!r}, "
            f"depth={self.depth}, "
            f"parent_run_id={self.parent_run_id!r})"
        )


__all__ = ["Runnable", "RunOutput", "ExecutionContext"]
