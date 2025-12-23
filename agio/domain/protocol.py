"""
Runnable protocol and RunOutput for unified execution interface.

This module defines the core abstractions for executable units:
- Runnable: protocol for Agent and Workflow
- RunOutput: execution result with response and metrics
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agio.domain.execution_context import ExecutionContext
    from agio.domain.models import RunMetrics


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


__all__ = ["Runnable", "RunOutput"]
