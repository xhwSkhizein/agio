from agio.core.events import ModelEvent, ModelEventType
from agio.protocol.events import (
    AgentEvent,
    create_text_delta_event,
    create_tool_call_started_event,
    create_tool_call_completed_event,
    create_usage_update_event,
    create_error_event,
    create_metrics_snapshot_event,
)
from agio.domain.tools import ToolResult


class EventConverter:
    """
    将 ModelEvent 转换为 AgentEvent。
    ModelDriver 使用简化的 ModelEventType，
    转换为对外的完整 AgentEvent（使用 EventType）。
    """
    
    @staticmethod
    def convert_model_event(model_event: ModelEvent, run_id: str) -> AgentEvent | None:
        """
        将 ModelEvent 转换为 AgentEvent。
        
        Args:
            model_event: 模型层事件
            run_id: 运行 ID
            
        Returns:
            AgentEvent 或 None（如果不需要转换）
        """
        if model_event.type == ModelEventType.TEXT_DELTA:
            return create_text_delta_event(
                run_id=run_id,
                content=model_event.content,
                step=model_event.step
            )
        
        elif model_event.type == ModelEventType.TOOL_CALL_STARTED:
            # 为每个工具调用创建事件
            events = []
            for tc in model_event.tool_calls:
                events.append(create_tool_call_started_event(
                    run_id=run_id,
                    tool_name=tc.get("function", {}).get("name", "unknown"),
                    tool_call_id=tc.get("id", ""),
                    arguments=tc.get("function", {}).get("arguments", "{}"),
                    step=model_event.step
                ))
            return events if len(events) > 1 else (events[0] if events else None)
        
        elif model_event.type == ModelEventType.TOOL_CALL_FINISHED:
            tool_result = model_event.tool_result
            return create_tool_call_completed_event(
                run_id=run_id,
                tool_name=tool_result.get("tool_name", "unknown"),
                tool_call_id=tool_result.get("tool_call_id", ""),
                result=tool_result.get("content", ""),
                duration=tool_result.get("duration", 0.0),
                step=model_event.step
            )
        
        elif model_event.type == ModelEventType.USAGE:
            usage = model_event.usage
            return create_usage_update_event(
                run_id=run_id,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                step=model_event.step
            )
        
        elif model_event.type == ModelEventType.METRICS_SNAPSHOT:
            return create_metrics_snapshot_event(
                run_id=run_id,
                metrics=model_event.metadata
            )
        
        elif model_event.type == ModelEventType.ERROR:
            return create_error_event(
                run_id=run_id,
                error=model_event.content,
                error_type=model_event.metadata.get("error_type", "unknown")
            )
        
        # 其他类型暂不转换
        return None
    
    @staticmethod
    def convert_tool_result(tool_result: ToolResult, run_id: str, step: int) -> AgentEvent:
        """将 ToolResult 转换为 AgentEvent"""
        return create_tool_call_completed_event(
            run_id=run_id,
            tool_name=tool_result.tool_name,
            tool_call_id=tool_result.tool_call_id,
            result=tool_result.content,
            duration=tool_result.duration,
            step=step
        )
