from typing import Any
from pydantic import BaseModel

class ToolResult(BaseModel):
    tool_name: str
    tool_call_id: str
    input_args: dict[str, Any]
    content: str  # 给 LLM 看的结果
    output: Any   # 原始执行结果
    error: str | None = None
    start_time: float
    end_time: float
    duration: float
    is_success: bool = True

