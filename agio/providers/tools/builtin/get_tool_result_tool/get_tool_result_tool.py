"""
GetToolResultTool - Retrieve historical tool call results by tool_call_id.

This tool enables cross-agent reference:
1. Collector Agent executes tools, results are stored as Tool Steps
2. Collector returns report with tool_call_ids
3. Processor Agent uses get_tool_result to fetch specific results
"""

import time
from typing import Any, TYPE_CHECKING

from agio.providers.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.domain import ToolResult
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.agent.control import AbortSignal
    from agio.domain import ExecutionContext
    from agio.providers.storage.base import SessionStore

logger = get_logger(__name__)


class GetToolResultTool(BaseTool):
    """
    Retrieve a historical tool call result by tool_call_id.
    
    This enables cross-agent information sharing:
    - Collector executes tools, stores results as Steps
    - Collector reports: "Found auth code (tool_call: tc_001)"
    - Processor calls: get_tool_result("tc_001") to fetch full content
    """

    def __init__(self, session_store: "SessionStore | None" = None):
        self._session_store = session_store
        self.category = ToolCategory.MEMORY
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = 10
        super().__init__()

    def get_name(self) -> str:
        return "get_tool_result"

    def get_description(self) -> str:
        return """Retrieve a historical tool call result by tool_call_id.

Use this when you receive a tool_call_id reference from another agent's report
and need to see the full result.

Example:
  You receive: "Auth logic analyzed (tool_call: tc_abc123)"
  Call: get_tool_result("tc_abc123")
  Returns: The full content from that tool execution
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_call_id": {
                    "type": "string",
                    "description": "The tool_call_id to retrieve results for",
                },
            },
            "required": ["tool_call_id"],
        }

    def is_concurrency_safe(self) -> bool:
        return True

    def set_session_store(self, session_store: "SessionStore") -> None:
        """Set the session store (called by runtime)"""
        self._session_store = session_store

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        start_time = time.time()

        try:
            tool_call_id = parameters.get("tool_call_id", "")
            session_id = context.session_id

            if not tool_call_id:
                return self._create_error_result(
                    parameters, "tool_call_id is required", start_time
                )

            if not self._session_store:
                return self._create_error_result(
                    parameters, "Session store not available", start_time
                )

            if not session_id:
                return self._create_error_result(
                    parameters, "Session ID not available", start_time
                )

            # Query the Tool Step by tool_call_id
            step = await self._session_store.get_step_by_tool_call_id(
                session_id, tool_call_id
            )

            if not step:
                return self._create_error_result(
                    parameters, f"Tool result not found: {tool_call_id}", start_time
                )

            result_text = f"""## Tool Result: {step.name or 'unknown'}
**tool_call_id**: {tool_call_id}

### Content:
{step.content}
"""

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_text,
                output={
                    "tool_call_id": tool_call_id,
                    "tool_name": step.name,
                    "content": step.content,
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            logger.error("get_tool_result_failed", error=str(e), tool_call_id=parameters.get("tool_call_id"))
            return self._create_error_result(parameters, str(e), start_time)


__all__ = ["GetToolResultTool"]
