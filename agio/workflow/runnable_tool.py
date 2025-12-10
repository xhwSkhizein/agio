"""
RunnableTool - Adapter to convert Runnable (Agent/Workflow) into Tool.

This module provides:
- RunnableTool: Adapter class that wraps a Runnable as a Tool
- as_tool: Factory function for convenient creation

Wire-based Architecture:
- Wire is passed via parameters from ToolExecutor
- Nested execution context includes wire for unified event streaming
- All events from nested Runnables go to the same Wire

Safety features:
- Maximum depth limit to prevent infinite nesting
- Call stack tracking to detect circular references at runtime
"""

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agio.domain import StepEvent, StepEventType, ToolResult
from agio.providers.tools import BaseTool
from agio.workflow.protocol import Runnable, RunContext

if TYPE_CHECKING:
    from agio.runtime.control import AbortSignal
    from agio.runtime.wire import Wire


# Default maximum nesting depth for Runnable as Tool
DEFAULT_MAX_DEPTH = 5


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected in Runnable call chain."""
    pass


class MaxDepthExceededError(Exception):
    """Raised when the maximum nesting depth is exceeded."""
    pass


class RunnableTool(BaseTool):
    """
    Adapter that converts a Runnable (Agent/Workflow) into a Tool.

    Features:
    1. Supports event callback for streaming nested execution events
    2. Properly passes nested execution context (trace_id, depth, parent_run_id)
    3. Collects complete output as ToolResult

    Safety:
    - max_depth: Limits nesting depth to prevent stack overflow
    - Call stack tracking: Detects circular references at runtime

    Usage:
        research_agent = Agent(model=claude, name="research_agent")
        research_tool = RunnableTool(research_agent, description="Research expert")

        orchestra = Agent(model=gpt4, tools=[research_tool])
    """

    def __init__(
        self,
        runnable: Runnable,
        description: str | None = None,
        name: str | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ):
        """
        Initialize RunnableTool.

        Args:
            runnable: The Runnable instance to wrap (Agent or Workflow)
            description: Tool description for LLM
            name: Tool name, defaults to call_{runnable.id}
            max_depth: Maximum nesting depth allowed (default: 5)
        """
        self.runnable = runnable
        self._description = description or f"Delegate task to {runnable.id}"
        self._name = name or f"call_{runnable.id}"
        self.max_depth = max_depth
        super().__init__()

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task to delegate to this agent/workflow",
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context for the task",
                },
            },
            "required": ["task"],
        }

    def is_concurrency_safe(self) -> bool:
        # Each execution uses independent session
        return True

    async def execute(
        self,
        parameters: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """
        Execute the wrapped Runnable.

        Execution flow:
        1. Check depth limit and circular references
        2. Build input and context
        3. Execute Runnable, collect event stream
        4. Forward events via event_callback (if provided)
        5. Return final output as ToolResult

        Safety checks:
        - Raises MaxDepthExceededError if depth > max_depth
        - Raises CircularReferenceError if runnable.id is in call stack
        """
        start_time = time.time()
        task = parameters.get("task", "")
        extra_context = parameters.get("context", "")
        
        # Get current depth and call stack from parameters
        current_depth = parameters.get("_depth", 0) + 1
        call_stack: list[str] = parameters.get("_call_stack", []).copy()
        
        # Safety check 1: Depth limit
        if current_depth > self.max_depth:
            error_msg = (
                f"Maximum nesting depth ({self.max_depth}) exceeded. "
                f"Current call chain: {' -> '.join(call_stack)} -> {self.runnable.id}"
            )
            return self._create_error_result(
                parameters, error_msg, start_time
            )
        
        # Safety check 2: Circular reference detection
        if self.runnable.id in call_stack:
            error_msg = (
                f"Circular reference detected: {self.runnable.id} is already in call chain. "
                f"Call chain: {' -> '.join(call_stack)} -> {self.runnable.id}"
            )
            return self._create_error_result(
                parameters, error_msg, start_time
            )
        
        # Add current runnable to call stack
        call_stack.append(self.runnable.id)

        # Build input
        input_text = task
        if extra_context:
            input_text = f"{task}\n\nContext: {extra_context}"

        # Get wire and parent_run_id from parameters (passed by ToolExecutor)
        wire: "Wire | None" = parameters.get("_wire")
        parent_run_id: str | None = parameters.get("_parent_run_id")
        
        # Build execution context with wire for unified event streaming
        context = RunContext(
            wire=wire,  # Pass wire to nested execution
            session_id=str(uuid4()),  # Independent session
            trace_id=parameters.get("_trace_id"),
            parent_span_id=parameters.get("_parent_span_id"),
            parent_run_id=parent_run_id,  # Parent run ID for grouping nested events
            nested_runnable_id=self.runnable.id,  # Identify which Runnable is executing
            depth=current_depth,
            metadata={
                "_call_stack": call_stack,  # Pass call stack for nested detection
            },
        )

        # Execute nested Runnable
        # Events are written directly to wire by the nested execution
        output = ""
        error = None

        try:
            # run() writes events to wire and returns RunOutput
            result = await self.runnable.run(input_text, context=context)
            output = result.response or ""

        except CircularReferenceError as e:
            error = str(e)
            output = f"Circular reference error: {error}"
        except MaxDepthExceededError as e:
            error = str(e)
            output = f"Max depth exceeded: {error}"
        except Exception as e:
            error = str(e)
            output = f"Error executing {self.runnable.id}: {error}"

        end_time = time.time()

        return ToolResult(
            tool_name=self.get_name(),
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args={"task": task, "context": extra_context},
            content=output,
            output=output,
            error=error,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            is_success=error is None,
        )


def as_tool(
    runnable: Runnable,
    description: str | None = None,
    name: str | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> RunnableTool:
    """
    Convert a Runnable (Agent/Workflow) to a Tool.

    This is a convenience factory function.

    Usage:
        research_tool = as_tool(research_agent, "Expert at research tasks")
        orchestra = Agent(model=gpt4, tools=[research_tool])

    Args:
        runnable: Agent or Workflow instance
        description: Tool description for LLM reference
        name: Tool name, defaults to call_{runnable.id}
        max_depth: Maximum nesting depth allowed (default: 5)

    Returns:
        RunnableTool instance
    """
    return RunnableTool(runnable, description, name, max_depth=max_depth)


__all__ = [
    "RunnableTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "DEFAULT_MAX_DEPTH",
]
