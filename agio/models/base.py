from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from pydantic import BaseModel
from agio.domain.messages import Message

class ModelResponse(BaseModel):
    content: str
    raw_response: Any
    usage: dict[str, int]
    first_token_timestamp: float | None = None # timestamp

class ModelDelta(BaseModel):
    content: str | None = None
    tool_calls: list[dict] | None = None
    role: str | None = None
    usage: dict | None = None # Usage might come in the last chunk

class Model(BaseModel, ABC):
    id: str
    name: str
    
    @abstractmethod
    async def aresponse(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> ModelResponse:
        """非流式异步响应"""
        pass

    @abstractmethod
    async def astream(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> AsyncIterator[ModelDelta]:
        """
        流式异步响应. 
        Yields: ModelDelta
        """
        pass
