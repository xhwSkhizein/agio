from enum import Enum
from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field


class ModelEventType(str, Enum):
    """
    ModelDriver 内部事件类型。
    这些是 ModelDriver 层使用的简化事件类型，
    会通过 EventConverter 转换为对外的 AgentEvent。
    """
    TEXT_DELTA = "text_delta"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_FINISHED = "tool_call_finished"
    USAGE = "usage"
    METRICS_SNAPSHOT = "metrics_snapshot"
    ERROR = "error"


class ModelEvent(BaseModel):
    """
    模型层事件。
    用于 ModelDriver 内部的事件传递。
    """
    type: ModelEventType
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_result: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None
    step: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LoopState(BaseModel):
    step_num: int = 0
    total_tokens: int = 0
    pending_tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    messages: List[Any] = Field(default_factory=list)
    status: str = "idle"
