"""
AgentExecutor - LLM Call Loop 执行引擎

职责：
- 实现 LLM ↔ Tool 循环逻辑
- 累加流式 tool calls
- 调用 ToolExecutor 执行工具
- 将所有输出封装为 AgentEvent

不负责：
- Run/Step 状态管理
- 持久化
- Metrics 构建（只发送原始数据）
"""

from typing import AsyncIterator
from pydantic import BaseModel, Field

from agio.models.base import Model
from agio.tools.base import Tool
from agio.execution.tool_executor import ToolExecutor
from agio.protocol.events import AgentEvent, EventType


class ExecutorConfig(BaseModel):
    """Executor 配置"""
    max_steps: int = Field(default=10, ge=1, le=100, description="最大执行步数")
    timeout_per_step: float = Field(default=120.0, ge=1.0, description="每步超时时间（秒）")
    parallel_tool_calls: bool = Field(default=True, description="是否并行执行工具调用")


class ToolCallAccumulator:
    """
    累加流式 tool calls。
    
    OpenAI 返回的 tool calls 是增量式的，需要累加后才能执行。
    """
    
    def __init__(self):
        self._calls: dict[int, dict] = {}
    
    def accumulate(self, delta_calls: list[dict]):
        """
        累加增量 tool calls。
        
        Args:
            delta_calls: 增量 tool calls，格式:
                [
                    {
                        "index": 0,
                        "id": "call_xxx",
                        "function": {"name": "search", "arguments": "{..."}
                    }
                ]
        """
        for tc in delta_calls:
            idx = tc.get("index", 0)
            
            # 初始化累加器
            if idx not in self._calls:
                self._calls[idx] = {
                    "id": None,
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            
            acc = self._calls[idx]
            
            # 累加各个字段
            if tc.get("id"):
                acc["id"] = tc["id"]
            
            if tc.get("type"):
                acc["type"] = tc["type"]
            
            if tc.get("function"):
                fn = tc["function"]
                if fn.get("name"):
                    acc["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    acc["function"]["arguments"] += fn["arguments"]
    
    def finalize(self) -> list[dict]:
        """
        获取最终的完整 tool calls。
        
        Returns:
            完整的 tool calls 列表，格式:
                [
                    {
                        "id": "call_xxx",
                        "type": "function",
                        "function": {
                            "name": "search",
                            "arguments": "{\"query\": \"...\"}"
                        }
                    }
                ]
        """
        return [
            call for call in self._calls.values()
            if call["id"] is not None  # 只返回有效的 tool calls
        ]
    
    def clear(self):
        """清空累加器"""
        self._calls.clear()


class AgentExecutor:
    """
    LLM Call Loop 执行器。
    
    职责：
    1. 管理 LLM ↔ Tool 循环
    2. 累加流式 tool calls
    3. 调用 ToolExecutor
    4. 将所有输出封装为 AgentEvent
    
    Examples:
        >>> executor = AgentExecutor(
        ...     model=OpenAIModel(...),
        ...     tools=[SearchTool(), CalculatorTool()],
        ... )
        >>> messages = [{"role": "user", "content": "搜索 Python"}]
        >>> async for event in executor.execute(messages, run_id="run_123"):
        ...     if event.type == EventType.TEXT_DELTA:
        ...         print(event.data["content"], end="")
    """
    
    def __init__(
        self,
        model: Model,
        tools: list[Tool],
        config: ExecutorConfig | None = None,
    ):
        """
        初始化 Executor。
        
        Args:
            model: LLM Model 实例
            tools: 可用工具列表
            config: 执行配置
        """
        self.model = model
        self.tools = tools
        self.config = config or ExecutorConfig()
        self.tool_executor = ToolExecutor(tools)
    
    async def execute(
        self,
        messages: list[dict],
        run_id: str,
    ) -> AsyncIterator[AgentEvent]:
        """
        执行 LLM Call Loop，产生 AgentEvent 流。
        
        Args:
            messages: 消息列表（OpenAI 格式），会被原地修改
            run_id: Run ID，用于事件关联
        
        Yields:
            AgentEvent: 统一的事件流
                - TEXT_DELTA: 文本增量
                - USAGE_UPDATE: Token 使用更新
                - TOOL_CALL_STARTED: 工具调用开始
                - TOOL_CALL_COMPLETED: 工具调用完成
                - TOOL_CALL_FAILED: 工具调用失败
        
        流程:
            1. 调用 LLM
            2. 累加 tool calls
            3. 如果有 tool calls，执行工具并继续循环
            4. 如果没有 tool calls，结束循环
        """
        current_step = 0
        
        # 获取工具的 OpenAI schema
        tool_schemas = self._get_tool_schemas() if self.tools else None
        
        while current_step < self.config.max_steps:
            current_step += 1
            
            # 1. 调用 LLM
            full_content = ""
            accumulator = ToolCallAccumulator()
            
            async for chunk in self.model.arun_stream(messages, tools=tool_schemas):
                # 发送文本增量事件
                if chunk.content:
                    full_content += chunk.content
                    yield AgentEvent(
                        type=EventType.TEXT_DELTA,
                        run_id=run_id,
                        data={
                            "content": chunk.content,
                            "step": current_step,
                        }
                    )
                
                # 累加 tool calls
                if chunk.tool_calls:
                    accumulator.accumulate(chunk.tool_calls)
                
                # 发送 usage 事件
                if chunk.usage:
                    yield AgentEvent(
                        type=EventType.USAGE_UPDATE,
                        run_id=run_id,
                        data={
                            "usage": chunk.usage,
                            "step": current_step,
                        }
                    )
            
            # 2. 处理 tool calls 或结束
            final_tool_calls = accumulator.finalize()
            
            # 添加 assistant 消息到 messages
            messages.append({
                "role": "assistant",
                "content": full_content or None,
                "tool_calls": final_tool_calls or None,
            })
            
            if not final_tool_calls:
                # 没有工具调用，循环结束
                break
            
            # 3. 发送工具调用开始事件
            for tc in final_tool_calls:
                yield AgentEvent(
                    type=EventType.TOOL_CALL_STARTED,
                    run_id=run_id,
                    data={
                        "tool_name": tc["function"]["name"],
                        "tool_call_id": tc["id"],
                        "arguments": tc["function"]["arguments"],
                        "step": current_step,
                    }
                )
            
            # 4. 执行工具
            results = await self.tool_executor.execute_batch(final_tool_calls)
            
            # 5. 发送工具调用完成事件 + 添加 tool messages
            for result in results:
                # 发送事件
                event_type = (
                    EventType.TOOL_CALL_COMPLETED 
                    if result.is_success 
                    else EventType.TOOL_CALL_FAILED
                )
                
                yield AgentEvent(
                    type=event_type,
                    run_id=run_id,
                    data={
                        "tool_name": result.tool_name,
                        "tool_call_id": result.tool_call_id,
                        "result": result.content,
                        "is_success": result.is_success,
                        "duration": result.duration,
                        "step": current_step,
                    }
                )
                
                # 添加 tool message
                messages.append({
                    "role": "tool",
                    "tool_call_id": result.tool_call_id,
                    "content": result.content,
                })
    
    def _get_tool_schemas(self) -> list[dict]:
        """获取工具的 OpenAI schema"""
        return [tool.to_openai_schema() for tool in self.tools]
