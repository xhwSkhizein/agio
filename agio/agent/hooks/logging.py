from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun, AgentRunStep
from agio.domain.messages import Message
from agio.domain.tools import ToolResult
from agio.utils.logger import log_info, log_debug, log_error, logger

class LoggingHook(AgentHook):
    """
    Hook responsible for logging agent activities to the console/file.
    """
    
    async def on_run_start(self, run: AgentRun) -> None:
        log_info(f"Agent Run Started: {run.id} (User: {run.user_id})")

    async def on_step_start(self, run: AgentRun, step: AgentRunStep) -> None:
        log_debug(f"Step {step.step_num} Started")

    async def on_model_start(self, run: AgentRun, step: AgentRunStep, messages: list[Message]) -> None:
        log_debug(f"Calling Model: {len(messages)} messages in context")

    async def on_tool_start(self, run: AgentRun, step: AgentRunStep, tool_call: dict) -> None:
        fn_name = tool_call.get("function", {}).get("name", "unknown")
        log_info(f"Executing Tool: {fn_name}")

    async def on_tool_end(self, run: AgentRun, step: AgentRunStep, tool_result: ToolResult) -> None:
        status = "Success" if tool_result.is_success else "Failed"
        log_debug(f"Tool {tool_result.tool_name} finished: {status} ({tool_result.duration:.2f}s)")

    async def on_run_end(self, run: AgentRun) -> None:
        log_info(f"Agent Run Completed: {run.status} in {run.metrics.duration:.2f}s")

    async def on_error(self, run: AgentRun, error: Exception) -> None:
        log_error(f"Agent Run Failed: {error}")
