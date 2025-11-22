from abc import ABC
from agio.domain.run import AgentRun
from agio.domain.step import Step
from agio.domain.tools import ToolResult

class AgentHook(ABC):
    """
    Base class for all agent hooks.
    Most methods include `run` context to allow full access to state.
    """

    def __init__(self, **kwargs):
        """Initialize hook with optional parameters."""
        pass

    async def on_run_start(self, run: AgentRun) -> None:
        pass

    async def on_step_start(self, run: AgentRun, step: Step) -> None:
        pass

    async def on_model_start(
        self, run: AgentRun, step: Step, messages: list[dict]
    ) -> None:
        pass

    async def on_model_end(self, run: AgentRun, step: Step) -> None:
        pass

    async def on_tool_start(self, run: AgentRun, step: Step, tool_call: dict) -> None:
        pass

    async def on_tool_end(
        self, run: AgentRun, step: Step, tool_result: ToolResult
    ) -> None:
        pass

    async def on_step_end(self, run: AgentRun, step: Step) -> None:
        pass

    async def on_run_end(self, run: AgentRun) -> None:
        pass

    async def on_error(self, run: AgentRun, error: Exception) -> None:
        pass
