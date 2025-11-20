from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具逻辑"""
        pass
    
    @abstractmethod
    def to_openai_schema(self) -> dict:
        """转换为 OpenAI Function Calling 格式"""
        pass

