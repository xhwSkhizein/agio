import json
import time
import asyncio
from typing import List, Any, Dict
from agio.domain.tools import ToolResult
from agio.tools.base import Tool

class ToolExecutor:
    def __init__(self, tools: List[Tool]):
        self.tools_map = {t.name: t for t in tools}

    async def execute(self, tool_call: Dict[str, Any]) -> ToolResult:
        """
        Executes a single tool call.
        """
        # Handle different tool call formats if necessary, but assuming OpenAI format here
        # tool_call structure: {"id": "...", "function": {"name": "...", "arguments": "..."}}
        
        fn_name = tool_call.get("function", {}).get("name")
        fn_args_str = tool_call.get("function", {}).get("arguments", "{}")
        call_id = tool_call.get("id")
        start_time = time.time()

        if not fn_name:
             return self._create_error_result(
                call_id=call_id,
                tool_name="unknown",
                error="Tool name missing in tool call.",
                start_time=start_time
            )

        target_tool = self.tools_map.get(fn_name)

        if not target_tool:
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Tool {fn_name} not found.",
                start_time=start_time
            )

        try:
            # Handle arguments being either string (JSON) or dict
            if isinstance(fn_args_str, str):
                args = json.loads(fn_args_str)
            else:
                args = fn_args_str or {}
                
            result = await target_tool.execute(**args)
            end_time = time.time()
            
            return ToolResult(
                tool_name=fn_name,
                tool_call_id=call_id,
                input_args=args,
                content=str(result),
                output=result,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                is_success=True,
            )
        except Exception as e:
            return self._create_error_result(
                call_id=call_id,
                tool_name=fn_name,
                error=f"Error executing tool: {str(e)}",
                start_time=start_time
            )

    def _create_error_result(self, call_id: str, tool_name: str, error: str, start_time: float) -> ToolResult:
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

    async def execute_batch(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """
        Executes a batch of tool calls in parallel.
        """
        tasks = [self.execute(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks)
