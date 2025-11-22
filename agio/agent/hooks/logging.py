from agio.agent.hooks.base import AgentHook
from agio.domain.run import AgentRun, AgentRunStep
from agio.domain.messages import Message
from agio.domain.tools import ToolResult
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class LoggingHook(AgentHook):
    """
    Hook responsible for logging agent activities to the console/file.
    """

    async def on_run_start(self, run: AgentRun) -> None:
        logger.info("Agent Run Started", run_id=run.id, user_id=run.user_id)

    async def on_step_start(self, run: AgentRun, step: AgentRunStep) -> None:
        logger.info("Step Started", step_num=step.step_num)

    async def on_model_start(
        self, run: AgentRun, step: AgentRunStep, messages: list[Message]
    ) -> None:
        logger.info(f"Calling Model: {len(messages)} messages in context")

    async def on_tool_start(
        self, run: AgentRun, step: AgentRunStep, tool_call: dict
    ) -> None:
        fn_name = tool_call.get("function", {}).get("name", "unknown")
        logger.info(f"Executing Tool: {fn_name}")

    async def on_tool_end(
        self, run: AgentRun, step: AgentRunStep, tool_result: ToolResult
    ) -> None:
        status = "Success" if tool_result.is_success else "Failed"
        logger.info(
            f"Tool {tool_result.tool_name} finished: {status} ({tool_result.duration:.2f}s)"
        )

    async def on_run_end(self, run: AgentRun) -> None:
        logger.info(f"Agent Run Completed: {run.status} in {run.metrics.duration:.2f}s")

    async def on_error(self, run: AgentRun, error: Exception) -> None:
        logger.error("Agent Run Failed", run_id=run.id, msg=str(error), err=error)
