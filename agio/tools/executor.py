"""
Unified tool executor.
"""

import asyncio
import contextlib
import json
import time
from dataclasses import replace
from typing import Any

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.permission.manager import PermissionManager
from agio.runtime.context import ExecutionContext
from agio.tools import BaseTool
from agio.tools.cache import ToolResultCache, get_tool_cache
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """Unified tool executor that returns ToolResult directly."""

    def __init__(
        self,
        tools: list["BaseTool"],
        cache: "ToolResultCache | None" = None,
        permission_manager: "PermissionManager | None" = None,
        default_timeout: float | None = None,
    ) -> None:
        """
        Initialize tool executor.

        Args:
            tools: List of tools (BaseTool only)
            cache: Optional cache for expensive tool results
            permission_manager: Optional PermissionManager for permission checking
            default_timeout: Optional default timeout in seconds for tool execution
        """
        self.tools_map = {t.name: t for t in tools}
        self._cache = cache or get_tool_cache()
        self._permission_manager = permission_manager
        self._default_timeout = default_timeout

    async def execute(
        self,
        tool_call: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            tool_call: OpenAI format tool call
            context: Execution context
            abort_signal: Abort signal

        Returns:
            ToolResult: Tool execution result
        """
        fn_name = tool_call.get("function", {}).get("name")
        fn_args_str = tool_call.get("function", {}).get("arguments", "{}")
        call_id = tool_call.get("id")
        start_time = time.time()

        if not fn_name:
            return self._create_error_result(
                call_id=call_id,
                tool_name="unknown",
                error="Tool name missing in tool call",
                start_time=start_time,
            )

        tool = self.tools_map.get(fn_name)
        if not tool:
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Tool {fn_name} not found",
                start_time=start_time,
            )

        try:
            if isinstance(fn_args_str, str):
                args = json.loads(fn_args_str)
            elif isinstance(fn_args_str, dict):
                args = fn_args_str
            else:
                args = {}
        except json.JSONDecodeError as e:
            # Check if it's a fallback dictionary from Anthropic conversion
            try:
                # If the string itself looks like a dict that was stringified
                if fn_args_str.startswith("{") and fn_args_str.endswith("}"):
                    import ast
                    args = ast.literal_eval(fn_args_str)
                    if not isinstance(args, dict):
                        raise ValueError("Not a dict")
                else:
                    raise e
            except Exception:
                return self._create_error_result(
                    call_id=call_id,
                    tool_name=fn_name,
                    error=f"Invalid JSON arguments: {e}. Raw: {fn_args_str[:100]}...",
                    start_time=start_time,
                )

        args["tool_call_id"] = call_id

        # ===== Permission check (if permission manager is configured) =====
        if self._permission_manager:
            try:
                consent_result = await self._permission_manager.check_and_wait_consent(
                    tool_call_id=call_id,
                    tool_name=fn_name,
                    tool_args=args,
                    context=context,
                    timeout=300.0,
                )

                # Critical: Return explicit ToolResult if authorization failed
                if not consent_result.allowed:
                    return self._create_denied_result(
                        call_id=call_id,
                        tool_name=fn_name,
                        reason=consent_result.reason,
                        start_time=start_time,
                    )
            except Exception as e:
                logger.error(
                    "permission_check_failed",
                    tool_name=fn_name,
                    tool_call_id=call_id,
                    error=str(e),
                    exc_info=True,
                )
                # On error, treat as requires consent and deny
                return self._create_denied_result(
                    call_id=call_id,
                    tool_name=fn_name,
                    reason=f"Permission check failed: {e}",
                    start_time=start_time,
                )

        # Authorization passed or not required, continue with tool execution
        # Check cache for cacheable tools
        session_id = context.session_id
        if session_id and tool.cacheable:
            cached = self._cache.get(session_id, fn_name, args)
            if cached is not None:
                # Update tool_call_id to match current call
                return ToolResult(
                    tool_name=cached.tool_name,
                    tool_call_id=call_id,
                    input_args=cached.input_args,
                    content=cached.content,
                    output=cached.output,
                    error=cached.error,
                    start_time=start_time,
                    end_time=time.time(),
                    duration=0.0,  # Instant from cache
                    is_success=cached.is_success,
                )

        timeout_seconds = self._default_timeout or getattr(
            tool, "timeout_seconds", None
        )

        # Pass timeout to context instead of forcing cancellation
        # This allows nested Agents to handle timeout gracefully (e.g., summarize)
        execution_context = context
        if timeout_seconds:
            timeout_at = time.time() + timeout_seconds
            execution_context = replace(context, timeout_at=timeout_at)

        try:
            logger.debug("executing_tool", tool_name=fn_name, tool_call_id=call_id)
            result: ToolResult = await tool.execute(
                args, context=execution_context, abort_signal=abort_signal
            )
            logger.debug(
                "tool_execution_completed",
                tool_name=fn_name,
                success=result.is_success,
                duration=result.duration,
            )

            # Cache successful results for cacheable tools
            if session_id and tool.cacheable and result.is_success:
                self._cache.set(session_id, fn_name, args, result)

            return result
        except asyncio.CancelledError:
            logger.info("tool_execution_cancelled", tool_name=fn_name)
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error="Tool execution was cancelled",
                start_time=start_time,
            )

        except Exception as e:
            logger.error(
                "tool_execution_exception",
                tool_name=fn_name,
                error=str(e),
                exc_info=True,
            )
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Tool execution failed: {e}",
                start_time=start_time,
            )

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> list[ToolResult]:
        """
        Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool calls
            context: Execution context
            abort_signal: Abort signal

        Returns:
            list[ToolResult]: List of tool execution results
        """

        async def _run_single(tc: dict[str, Any]) -> ToolResult:
            try:
                return await self.execute(
                    tc, context=context, abort_signal=abort_signal
                )
            except Exception as e:  # Defensive: should not propagate
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                tool_name = fn.get("name", "unknown")
                call_id = tc.get("id", "") if isinstance(tc, dict) else ""
                logger.error(
                    "tool_batch_execute_error",
                    tool_name=tool_name,
                    tool_call_id=call_id,
                    error=str(e),
                    exc_info=True,
                )
                return self._create_error_result(
                    call_id=call_id,
                    tool_name=tool_name,
                    error=f"Tool execution failed: {e}",
                    start_time=time.time(),
                )

        tasks = [asyncio.create_task(_run_single(tc)) for tc in tool_calls]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

        results: list[ToolResult] = []
        for task in tasks:
            try:
                results.append(task.result())
            except asyncio.CancelledError:
                results.append(
                    self._create_error_result(
                        call_id="",
                        tool_name="unknown",
                        error="Tool execution was cancelled",
                        start_time=time.time(),
                    )
                )
            except Exception as e:
                results.append(
                    self._create_error_result(
                        call_id="",
                        tool_name="unknown",
                        error=f"Tool execution failed: {e}",
                        start_time=time.time(),
                    )
                )

        return results

    def _create_error_result(
        self,
        call_id: str,
        tool_name: str,
        error: str,
        start_time: float,
    ) -> ToolResult:
        """Create error result."""
        end_time = time.time()
        return ToolResult(
            tool_name=tool_name,
            tool_call_id=call_id,
            input_args={},
            content=error,
            output=None,
            error=error,
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            is_success=False,
        )

    def _create_denied_result(
        self,
        call_id: str,
        tool_name: str,
        reason: str,
        start_time: float,
    ) -> ToolResult:
        """
        Create authorization denied ToolResult.

        Critical: Must return explicit ToolResult with error information,
        so LLM can understand why tool call failed.
        """
        end_time = time.time()
        return ToolResult(
            tool_name=tool_name,
            tool_call_id=call_id,
            input_args={},
            content=(
                f"Tool execution denied: {reason}. "
                "Please ask the user for permission or use a different approach."
            ),
            output=None,
            error=f"Permission denied: {reason}",
            start_time=start_time,
            end_time=end_time,
            duration=end_time - start_time,
            is_success=False,
        )


__all__ = ["ToolExecutor"]
