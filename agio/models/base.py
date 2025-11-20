"""
Model 抽象层 - Pure LLM Interface

职责：
- 封装不同 LLM 提供商的 API
- 提供统一的流式接口
- 标准化输出格式

不负责：
- Tool Loop 逻辑
- 事件封装
- 状态管理
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel, Field


class StreamChunk(BaseModel):
    """
    LLM 流式输出的最小单元。

    所有 Model 实现必须将各自厂商的流式输出标准化为此格式。
    """

    content: str | None = Field(default=None, description="文本内容增量")
    tool_calls: list[dict] | None = Field(
        default=None, description="工具调用增量（OpenAI 格式）"
    )
    usage: dict[str, int] | None = Field(
        default=None,
        description="Token 使用统计 {prompt_tokens, completion_tokens, total_tokens}",
    )
    finish_reason: str | None = Field(
        default=None, description="结束原因: stop, tool_calls, length, etc."
    )

    class Config:
        frozen = False


class Model(BaseModel, ABC):
    """
    统一的 Model 抽象基类。

    所有 LLM 实现（OpenAI, DeepSeek, Anthropic 等）都应继承此类，
    并实现 arun_stream() 方法。

    Examples:
        >>> model = OpenAIModel(
        ...     id="openai/gpt-4",
        ...     name="gpt-4",
        ...     api_key="sk-xxx"
        ... )
        >>> async for chunk in model.arun_stream(messages, tools):
        ...     if chunk.content:
        ...         print(chunk.content, end="")
    """

    # 基础字段
    id: str = Field(description="模型标识符，格式: provider/model-name")
    name: str = Field(description="模型名称")

    # 可选参数
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        统一的流式接口。

        Args:
            messages: 消息列表，标准 OpenAI 格式
                [
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "..."},
                    {"role": "assistant", "content": "...", "tool_calls": [...]},
                    {"role": "tool", "tool_call_id": "...", "content": "..."}
                ]
            tools: 工具定义列表，OpenAI 格式
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "...",
                            "description": "...",
                            "parameters": {...}
                        }
                    }
                ]

        Yields:
            StreamChunk: 流式输出块

        职责：
            1. 调用 LLM API
            2. 将厂商特定格式转换为 StreamChunk
            3. 处理 API 错误和重试

        不负责：
            - Tool 执行
            - 循环调用
            - 事件封装

        Raises:
            Exception: API 调用失败时抛出异常
        """
        pass
