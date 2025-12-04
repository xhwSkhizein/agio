"""
Runnable protocol and RunContext for unified execution interface.

This module defines:
- RunContext: execution context carrying metadata
- Runnable: protocol for executable units (Agent/Workflow)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agio.domain.events import StepEvent


@dataclass
class RunContext:
    """
    Execution context carrying metadata for the run.

    Design points:
    1. All fields are optional - Agent can run standalone without context
    2. trace_id/span_id reserved for observability
    3. depth tracks nesting level in workflow execution
    """

    # Session isolation: each Agent uses independent session
    session_id: str | None = None
    user_id: str | None = None

    # Observability reserved fields
    trace_id: str | None = None
    parent_span_id: str | None = None

    # Nested execution context
    parent_stage_id: str | None = None
    depth: int = 0

    # Extension metadata
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class Runnable(Protocol):
    """
    Unified protocol for executable units.

    Both Agent and Workflow implement this interface, enabling:
    1. Unified API invocation
    2. Mutual nesting and composition
    3. Use as Tool (AgentAsTool, WorkflowAsTool)
    """

    @property
    def id(self) -> str:
        """Unique identifier."""
        ...

    async def run(
        self,
        input: str,
        *,
        context: RunContext | None = None,
    ) -> AsyncIterator["StepEvent"]:
        """
        Execute and return event stream.

        Args:
            input: constructed input string
            context: optional execution context

        Yields:
            StepEvent: event stream during execution
        """
        ...

    @property
    def last_output(self) -> str | None:
        """Get the final output of the most recent execution."""
        ...
