from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EventType(str, Enum):
    """统一的事件类型枚举"""
    
    # Run 级别事件
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    
    # Step 级别事件
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    
    # 流式输出事件
    TEXT_DELTA = "text_delta"
    TEXT_COMPLETED = "text_completed"
    
    # 工具事件
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    
    # Metrics 事件
    USAGE_UPDATE = "usage_update"
    METRICS_SNAPSHOT = "metrics_snapshot"
    
    # 错误事件
    ERROR = "error"
    WARNING = "warning"
    
    # 调试事件
    DEBUG = "debug"


class AgentEvent(BaseModel):
    """
    统一的 Agent 事件模型。
    用于实时流式输出和历史回放。
    """
    
    type: EventType
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # 事件负载（根据类型不同而不同）
    data: Dict[str, Any] = Field(default_factory=dict)
    
    # 可选的元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_json(self) -> dict:
        """转换为 JSON 格式"""
        return self.model_dump(mode='json')
    
    def to_sse(self) -> str:
        """转换为 Server-Sent Events 格式"""
        import json
        data = self.to_json()
        return f"data: {json.dumps(data)}\n\n"


# 便捷的事件构造函数

def create_run_started_event(run_id: str, query: str, **metadata) -> AgentEvent:
    """创建 Run 开始事件"""
    return AgentEvent(
        type=EventType.RUN_STARTED,
        run_id=run_id,
        data={"query": query},
        metadata=metadata
    )


def create_run_completed_event(run_id: str, response: str, metrics: dict, **metadata) -> AgentEvent:
    """创建 Run 完成事件"""
    return AgentEvent(
        type=EventType.RUN_COMPLETED,
        run_id=run_id,
        data={"response": response, "metrics": metrics},
        metadata=metadata
    )


def create_text_delta_event(run_id: str, content: str, step: int = 0) -> AgentEvent:
    """创建文本增量事件"""
    return AgentEvent(
        type=EventType.TEXT_DELTA,
        run_id=run_id,
        data={"content": content, "step": step}
    )


def create_tool_call_started_event(
    run_id: str, 
    tool_name: str, 
    tool_call_id: str,
    arguments: dict,
    step: int = 0
) -> AgentEvent:
    """创建工具调用开始事件"""
    return AgentEvent(
        type=EventType.TOOL_CALL_STARTED,
        run_id=run_id,
        data={
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "arguments": arguments,
            "step": step
        }
    )


def create_tool_call_completed_event(
    run_id: str,
    tool_name: str,
    tool_call_id: str,
    result: str,
    duration: float,
    step: int = 0
) -> AgentEvent:
    """创建工具调用完成事件"""
    return AgentEvent(
        type=EventType.TOOL_CALL_COMPLETED,
        run_id=run_id,
        data={
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "result": result,
            "duration": duration,
            "step": step
        }
    )


def create_usage_update_event(
    run_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    step: int = 0
) -> AgentEvent:
    """创建 Token 使用更新事件"""
    return AgentEvent(
        type=EventType.USAGE_UPDATE,
        run_id=run_id,
        data={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "step": step
        }
    )


def create_error_event(run_id: str, error: str, error_type: str = "unknown") -> AgentEvent:
    """创建错误事件"""
    return AgentEvent(
        type=EventType.ERROR,
        run_id=run_id,
        data={"error": error, "error_type": error_type}
    )


def create_metrics_snapshot_event(run_id: str, metrics: dict) -> AgentEvent:
    """创建 Metrics 快照事件"""
    return AgentEvent(
        type=EventType.METRICS_SNAPSHOT,
        run_id=run_id,
        data=metrics
    )
