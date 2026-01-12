"""
AgentTool - Adapter to convert Agent into Tool.

This module provides:
- AgentTool: Adapter class that wraps an Agent as a Tool
- as_tool: Factory function for convenient creation

Wire-based Architecture:
- Wire is passed via ExecutionContext from parent execution
- Nested execution context includes wire for unified event streaming
- All events from nested Agents go to the same Wire

Safety features:
- Maximum depth limit to prevent infinite nesting
- Call stack tracking to detect circular references at runtime
"""

import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.context import ExecutionContext
from agio.tools import BaseTool

if TYPE_CHECKING:
    from agio.agent import Agent

# Default maximum nesting depth for Agent as Tool
DEFAULT_MAX_DEPTH = 5


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected in Agent call chain."""

    pass


class MaxDepthExceededError(Exception):
    """Raised when the maximum nesting depth is exceeded."""

    pass


class AgentTool(BaseTool):
    """
    Adapter that converts an Agent into a Tool.

    Features:
    1. Supports event callback for streaming nested execution events
    2. Properly passes nested execution context (trace_id, depth, parent_run_id)
    3. Collects complete output as ToolResult

    Safety:
    - max_depth: Limits nesting depth to prevent stack overflow
    - Call stack tracking: Detects circular references at runtime

    Usage:
        research_agent = Agent(model=claude, name="research_agent")
        research_tool = AgentTool(research_agent, description="Research expert")

        orchestra = Agent(model=gpt4, tools=[research_tool])
    """

    def __init__(
        self,
        agent: "Agent",
        description: str | None = None,
        name: str | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ):
        """
        Initialize AgentTool.

        Args:
            agent: The Agent instance to wrap
            description: Tool description for LLM
            name: Tool name, defaults to call_{agent.id}
            max_depth: Maximum nesting depth allowed (default: 5)
        """
        self.agent = agent
        self._description = description or f"Delegate task to {agent.id}"
        self._name = name or f"call_{agent.id}"
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
                    "description": "The task to delegate to this agent",
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context for the task",
                },
            },
            "required": ["task"],
        }

    def is_concurrency_safe(self) -> bool:
        return True

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """
        Execute the wrapped Agent.

        Execution flow:
        1. Check depth limit and circular references
        2. Build input and context
        3. Execute Agent.run() directly
        4. Return final output as ToolResult

        Safety checks:
        - Raises MaxDepthExceededError if depth > max_depth
        - Raises CircularReferenceError if agent.id is in call stack
        """
        start_time = time.time()
        task = parameters.get("task", "")
        extra_context = parameters.get("context", "")

        # Get current depth and call stack from context metadata
        current_depth = context.depth + 1
        call_stack: list[str] = context.metadata.get("_call_stack", []).copy()

        # Safety check 1: Depth limit
        if current_depth > self.max_depth:
            error_msg = (
                f"Maximum nesting depth ({self.max_depth}) exceeded. "
                f"Current call chain: {' -> '.join(call_stack)} -> {self.agent.id}"
            )
            return self._create_error_result(parameters, error_msg, start_time)

        # Safety check 2: Circular reference detection
        if self.agent.id in call_stack:
            error_msg = (
                f"Circular reference detected: {self.agent.id} is already in call chain. "
                f"Call chain: {' -> '.join(call_stack)} -> {self.agent.id}"
            )
            return self._create_error_result(parameters, error_msg, start_time)

        # Add current agent to call stack
        call_stack.append(self.agent.id)

        # Build input
        input_text = task
        if extra_context:
            input_text = f"{task}\n\nContext: {extra_context}"

        # Build execution context with wire for unified event streaming
        # Use parent's session_id to keep all Steps in the same Session
        run_id = str(uuid4())
        child_context = context.child(
            run_id=run_id,
            nested_runnable_id=self.agent.id,
            runnable_type=self.agent.runnable_type,
            runnable_id=self.agent.id,
            nesting_type="tool_call",
            metadata={
                "_call_stack": call_stack,
            },
        )

        # Execute nested Agent directly via Agent.run()
        output = ""
        error = None

        try:
            result = await self.agent.run(input_text, context=child_context)
            output = result.response or ""

        except CircularReferenceError as e:
            error = str(e)
            output = f"Circular reference error: {error}"
        except MaxDepthExceededError as e:
            error = str(e)
            output = f"Max depth exceeded: {error}"
        except Exception as e:
            error = str(e)
            output = f"Error executing {self.agent.id}: {error}"

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

    def _create_error_result(
        self, parameters: dict[str, Any], error_msg: str, start_time: float
    ) -> ToolResult:
        """Create error ToolResult."""
        end_time = time.time()
        return ToolResult(
            tool_name=self.get_name(),
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content=error_msg,
            output=error_msg,
            error=error_msg,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            is_success=False,
        )


def as_tool(
    agent: "Agent",
    description: str | None = None,
    name: str | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> AgentTool:
    """
    Convert an Agent to a Tool.

    This is a convenience factory function.

    Usage:
        research_tool = as_tool(research_agent, "Expert at research tasks")
        orchestra = Agent(model=gpt4, tools=[research_tool])

    Args:
        agent: Agent instance
        description: Tool description for LLM reference
        name: Tool name, defaults to call_{agent.id}
        max_depth: Maximum nesting depth allowed (default: 5)

    Returns:
        AgentTool instance
    """
    return AgentTool(
        agent,
        description,
        name,
        max_depth=max_depth,
    )


__all__ = [
    "AgentTool",
    "as_tool",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "DEFAULT_MAX_DEPTH",
]
