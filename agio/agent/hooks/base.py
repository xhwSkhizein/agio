from abc import ABC
from typing import Any
from agio.domain.run import AgentRun, AgentRunStep
from agio.domain.messages import Message
from agio.domain.tools import ToolResult
from agio.models.base import ModelDelta

class AgentHook(ABC):
    """
    Base class for all agent hooks.
    Most methods include `run` context to allow full access to state.
    """

    async def on_run_start(self, run: AgentRun) -> None:
        pass

    async def on_step_start(self, run: AgentRun, step: AgentRunStep) -> None:
        pass

    async def on_model_start(self, run: AgentRun, step: AgentRunStep, messages: list[Message]) -> None:
        pass
    
    async def on_model_chunk(self, run: AgentRun, chunk: ModelDelta) -> None:
        """Called for each streaming chunk received from the model"""
        pass

    async def on_model_end(self, run: AgentRun, step: AgentRunStep) -> None:
        pass

    async def on_tool_start(self, run: AgentRun, step: AgentRunStep, tool_call: dict) -> None:
        pass

    async def on_tool_end(self, run: AgentRun, step: AgentRunStep, tool_result: ToolResult) -> None:
        pass
    
    async def on_step_end(self, run: AgentRun, step: AgentRunStep) -> None:
        pass

    async def on_run_end(self, run: AgentRun) -> None:
        pass

    async def on_error(self, run: AgentRun, error: Exception) -> None:
        pass
