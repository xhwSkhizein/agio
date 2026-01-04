"""
StepFactory - Context-bound step factory.

This module provides a factory class that binds to an ExecutionContext
and creates Steps without requiring repetitive parameter passing.

Usage:
    ctx = ExecutionContext(run_id="...", session_id="...", wire=wire)
    sf = StepFactory(ctx)

    # Create steps without passing context parameters
    user_step = sf.user_step(sequence=1, content="Hello")
    assistant_step = sf.assistant_step(sequence=2, content="Hi", tool_calls=[...])
    tool_step = sf.tool_step(sequence=3, tool_call_id="call_123", name="file_read", content="...")
"""

from typing import Any
from uuid import uuid4

from agio.domain import MessageRole, Step, StepMetrics
from agio.runtime.protocol import ExecutionContext, RunnableType


class StepFactory:
    """
    Context-bound step factory.

    Binds to an ExecutionContext and provides methods to create Steps
    without repetitive parameter passing of session_id, run_id, depth, etc.
    """

    def __init__(self, ctx: "ExecutionContext") -> None:
        """
        Initialize factory with execution context.

        Args:
            ctx: ExecutionContext to bind to
        """
        self._ctx = ctx

    @property
    def ctx(self) -> "ExecutionContext":
        """Get the bound execution context."""
        return self._ctx

    def _convert_runnable_type(
        self, runnable_type: RunnableType | str | None
    ) -> str | None:
        """Convert RunnableType enum to string value for Step model."""
        if runnable_type is None:
            return None
        if isinstance(runnable_type, RunnableType):
            return runnable_type.value
        return runnable_type

    def user_step(
        self,
        sequence: int,
        content: str,
        **overrides,
    ) -> Step:
        """Create a USER step."""
        return Step(
            id=str(uuid4()),
            session_id=self._ctx.session_id,
            run_id=self._ctx.run_id,
            sequence=sequence,
            role=MessageRole.USER,
            content=content,
            # Runnable binding
            runnable_id=overrides.get("runnable_id", self._ctx.runnable_id),
            runnable_type=self._convert_runnable_type(
                overrides.get("runnable_type", self._ctx.runnable_type)
            ),
            # Extract metadata from ExecutionContext
            workflow_id=overrides.get("workflow_id", self._ctx.workflow_id),
            node_id=overrides.get("node_id", self._ctx.node_id),
            parent_run_id=overrides.get("parent_run_id", self._ctx.parent_run_id),
            branch_key=overrides.get(
                "branch_key", self._ctx.metadata.get("branch_key")
            ),
            iteration=overrides.get("iteration", self._ctx.metadata.get("iteration")),
            # Observability
            trace_id=overrides.get("trace_id", self._ctx.trace_id),
            span_id=overrides.get("span_id"),
            parent_span_id=overrides.get("parent_span_id", self._ctx.span_id),
            depth=overrides.get("depth", self._ctx.depth),
        )

    def assistant_step(
        self,
        sequence: int,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        reasoning_content: str | None = None,
        llm_messages: list[dict] | None = None,
        llm_tools: list[dict] | None = None,
        llm_request_params: dict[str, Any] | None = None,
        metrics: StepMetrics | None = None,
        **overrides,
    ) -> Step:
        """Create an ASSISTANT step."""
        return Step(
            id=str(uuid4()),
            session_id=self._ctx.session_id,
            run_id=self._ctx.run_id,
            sequence=sequence,
            role=MessageRole.ASSISTANT,
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            # Runnable binding
            runnable_id=overrides.get("runnable_id", self._ctx.runnable_id),
            runnable_type=self._convert_runnable_type(
                overrides.get("runnable_type", self._ctx.runnable_type)
            ),
            # Extract metadata from ExecutionContext
            workflow_id=overrides.get("workflow_id", self._ctx.workflow_id),
            node_id=overrides.get("node_id", self._ctx.node_id),
            parent_run_id=overrides.get("parent_run_id", self._ctx.parent_run_id),
            branch_key=overrides.get(
                "branch_key", self._ctx.metadata.get("branch_key")
            ),
            iteration=overrides.get("iteration", self._ctx.metadata.get("iteration")),
            # LLM call context
            llm_messages=llm_messages,
            llm_tools=llm_tools,
            llm_request_params=llm_request_params,
            # Metadata
            metrics=metrics,
            # Observability
            trace_id=overrides.get("trace_id", self._ctx.trace_id),
            span_id=overrides.get("span_id"),
            parent_span_id=overrides.get("parent_span_id", self._ctx.span_id),
            depth=overrides.get("depth", self._ctx.depth),
        )

    def tool_step(
        self,
        sequence: int,
        tool_call_id: str,
        name: str,
        content: str,
        content_for_user: str | None = None,
        metrics: StepMetrics | None = None,
        **overrides,
    ) -> Step:
        """Create a TOOL step."""
        return Step(
            id=str(uuid4()),
            session_id=self._ctx.session_id,
            run_id=self._ctx.run_id,
            sequence=sequence,
            role=MessageRole.TOOL,
            content=content,
            content_for_user=content_for_user,
            tool_call_id=tool_call_id,
            name=name,
            # Runnable binding
            runnable_id=overrides.get("runnable_id", self._ctx.runnable_id),
            runnable_type=self._convert_runnable_type(
                overrides.get("runnable_type", self._ctx.runnable_type)
            ),
            # Extract metadata from ExecutionContext
            workflow_id=overrides.get("workflow_id", self._ctx.workflow_id),
            node_id=overrides.get("node_id", self._ctx.node_id),
            parent_run_id=overrides.get("parent_run_id", self._ctx.parent_run_id),
            branch_key=overrides.get(
                "branch_key", self._ctx.metadata.get("branch_key")
            ),
            # Metadata
            metrics=metrics,
            # Observability
            trace_id=overrides.get("trace_id", self._ctx.trace_id),
            span_id=overrides.get("span_id"),
            parent_span_id=overrides.get("parent_span_id", self._ctx.span_id),
            depth=overrides.get("depth", self._ctx.depth),
        )


__all__ = ["StepFactory"]
