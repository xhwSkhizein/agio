"""
Runnable protocol and RunContext for unified execution interface.

This module defines:
- RunContext: execution context carrying metadata and Wire for event streaming
- RunOutput: execution result including response and metrics
- Runnable: protocol for executable units (Agent/Workflow)

Wire-based Architecture:
- Wire is created at API entry point
- run() writes events to context.wire
- run() returns RunOutput (response + metrics)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agio.runtime.wire import Wire


@dataclass
class RunMetrics:
    """Execution metrics."""
    duration: float = 0.0  # seconds
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls_count: int = 0
    # For workflow
    iterations: int | None = None
    stages_executed: int | None = None


@dataclass
class RunOutput:
    """
    Execution result from Runnable.run().
    
    Contains both the response and execution metrics,
    replacing the previous str | None return type.
    """
    response: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    metrics: RunMetrics = field(default_factory=RunMetrics)
    
    # Additional context
    workflow_id: str | None = None
    termination_reason: str | None = None  # "max_steps", "max_iterations", etc.
    error: str | None = None


@dataclass
class RunContext:
    """
    Execution context carrying metadata for the run.

    Design points:
    1. All fields are optional - Agent can run standalone without context
    2. wire: Event streaming channel, created at entry point, shared across all nested executions
    3. trace_id/span_id reserved for observability
    4. depth tracks nesting level in workflow execution
    """

    # Event streaming channel - single Wire for entire execution tree
    wire: "Wire | None" = None

    # Session isolation: each Agent uses independent session
    session_id: str | None = None
    user_id: str | None = None

    # Workflow context
    workflow_id: str | None = None  # Parent workflow ID for grouping sessions

    # Observability reserved fields
    trace_id: str | None = None
    parent_span_id: str | None = None

    # Nested execution context
    parent_stage_id: str | None = None
    parent_run_id: str | None = None  # Parent run ID for nested RunnableTool
    nested_runnable_id: str | None = None  # ID of the nested Runnable being executed
    depth: int = 0

    # Extension metadata
    metadata: dict = field(default_factory=dict)
    
    def child(self, **overrides) -> "RunContext":
        """
        Create a child context for nested execution.
        
        Preserves wire (event channel) and trace_id, increments depth.
        
        Args:
            **overrides: Fields to override in child context
            
        Returns:
            New RunContext with incremented depth
        """
        return RunContext(
            wire=overrides.get("wire", self.wire),  # Preserve wire
            session_id=overrides.get("session_id", self.session_id),
            user_id=overrides.get("user_id", self.user_id),
            workflow_id=overrides.get("workflow_id", self.workflow_id),
            trace_id=overrides.get("trace_id", self.trace_id),  # Preserve trace
            parent_span_id=overrides.get("parent_span_id", self.parent_span_id),
            parent_stage_id=overrides.get("parent_stage_id", self.parent_stage_id),
            parent_run_id=overrides.get("parent_run_id", self.parent_run_id),
            nested_runnable_id=overrides.get("nested_runnable_id", self.nested_runnable_id),
            depth=overrides.get("depth", self.depth + 1),  # Increment depth
            metadata=overrides.get("metadata", dict(self.metadata)),
        )


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

    async def run(
        self,
        input: str,
        *,
        context: "RunContext",
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
