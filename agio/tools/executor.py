"""
Unified tool executor.
"""

import asyncio
import json
import time
from typing import Any

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.permission.manager import PermissionManager
from agio.runtime.protocol import ExecutionContext
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
    ) -> None:
        """
        Initialize tool executor.

        Args:
            tools: List of tools (BaseTool only)
            cache: Optional cache for expensive tool results
            permission_manager: Optional PermissionManager for permission checking
        """
        self.tools_map = {t.name: t for t in tools}
        self._cache = cache or get_tool_cache()
        self._permission_manager = permission_manager

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
            else:
                args = fn_args_str or {}
        except json.JSONDecodeError as e:
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Invalid JSON arguments: {e}",
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

        try:
            logger.debug("executing_tool", tool_name=fn_name, tool_call_id=call_id)
            result: ToolResult = await tool.execute(
                args, context=context, abort_signal=abort_signal
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
        tasks = [
            self.execute(tc, context=context, abort_signal=abort_signal)
            for tc in tool_calls
        ]
        return await asyncio.gather(*tasks)

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
