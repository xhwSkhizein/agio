"""统一的工具执行器 - 最终简化版本"""

import asyncio
import json
import time
from typing import Any, TYPE_CHECKING

from agio.components.tools.base_tool import BaseTool
from agio.core.events import ToolResult
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.execution.abort_signal import AbortSignal

logger = get_logger(__name__)


class ToolExecutor:
    """统一的工具执行器，直接返回 ToolResult"""
    
    def __init__(self, tools: list[BaseTool]):
        """
        初始化工具执行器。
        
        Args:
            tools: 工具列表（只支持 BaseTool）
        """
        self.tools_map = {t.name: t for t in tools}
        self._logger = logger
    
    async def execute(
        self,
        tool_call: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """
        执行单个工具调用，直接返回 ToolResult。
        
        Args:
            tool_call: OpenAI 格式的工具调用
            abort_signal: 中断信号
            
        Returns:
            ToolResult: 工具执行结果
        """
        fn_name = tool_call.get("function", {}).get("name")
        fn_args_str = tool_call.get("function", {}).get("arguments", "{}")
        call_id = tool_call.get("id")
        start_time = time.time()

        # 验证工具名称
        if not fn_name:
            return self._create_error_result(
                call_id=call_id,
                tool_name="unknown",
                error="Tool name missing in tool call",
                start_time=start_time,
            )

        # 获取工具
        tool = self.tools_map.get(fn_name)
        if not tool:
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Tool {fn_name} not found",
                start_time=start_time,
            )

        # 解析参数
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

        # 添加 tool_call_id 到参数中
        args["tool_call_id"] = call_id

        # 直接执行工具并返回结果
        try:
            self._logger.debug("executing_tool", tool_name=fn_name, tool_call_id=call_id)
            result:ToolResult = await tool.execute(args, abort_signal=abort_signal)
            self._logger.debug(
                "tool_execution_completed",
                tool_name=fn_name,
                success=result.is_success,
                duration=result.duration,
            )
            return result
        
        except asyncio.CancelledError:
            self._logger.info("tool_execution_cancelled", tool_name=fn_name)
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error="Tool execution was cancelled",
                start_time=start_time,
            )
        
        except Exception as e:
            self._logger.error(
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
        abort_signal: "AbortSignal | None" = None,
    ) -> list[ToolResult]:
        """
        并行执行多个工具调用。
        
        Args:
            tool_calls: 工具调用列表
            abort_signal: 中断信号
            
        Returns:
            list[ToolResult]: 工具执行结果列表
        """
        tasks = [self.execute(tc, abort_signal=abort_signal) for tc in tool_calls]
        return await asyncio.gather(*tasks)
    
    def _create_error_result(
        self,
        call_id: str,
        tool_name: str,
        error: str,
        start_time: float,
    ) -> ToolResult:
        """创建错误结果"""
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


__all__ = ["ToolExecutor"]
