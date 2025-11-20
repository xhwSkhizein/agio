from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional, Any
from pydantic import BaseModel

from agio.domain.messages import Message
from agio.tools.base import Tool
from agio.core.events import ModelEvent

class LoopConfig(BaseModel):
    max_steps: int = 10
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    stop_sequences: List[str] = []
    extra_params: dict = {}

class ModelDriver(ABC):
    """
    Abstract base class for Model Drivers.
    Responsible for the LLM <-> Tool loop.
    """

    @abstractmethod
    def run(
        self, 
        messages: List[Message], 
        tools: List[Tool], 
        config: LoopConfig
    ) -> AsyncIterator[ModelEvent]:
        """
        Executes the model loop.
        Yields events for text deltas, tool calls, tool results, usage, etc.
        """
        pass
