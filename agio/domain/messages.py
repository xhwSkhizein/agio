from typing import Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    # 额外元数据，用于存储 token 统计等
    meta: dict[str, Any] = Field(default_factory=dict)

class UserMessage(Message):
    role: Literal["user"] = "user"

class SystemMessage(Message):
    role: Literal["system"] = "system"

class AssistantMessage(Message):
    role: Literal["assistant"] = "assistant"
    tool_calls: list[dict[str, Any]] | None = None

class ToolMessage(Message):
    role: Literal["tool"] = "tool"
    tool_call_id: str

