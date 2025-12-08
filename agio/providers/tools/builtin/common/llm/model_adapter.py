"""Model to LLM Service Adapter

将 Model 的流式接口适配为工具友好的请求-响应接口。
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from agio.providers.llm.base import Model
    from agio.runtime.control import AbortSignal

from agio.utils.logging import get_logger

logger = get_logger(__name__)


class LLMMessage(BaseModel):
    """LLM 消息"""

    role: str
    content: str


class LLMResult(BaseModel):
    """LLM 响应结果"""

    content: str
    model: str | None = None
    usage: dict | None = None


class ModelLLMAdapter:
    """将 Model 适配为简单的 LLM 服务接口

    用于工具中需要简单 LLM 调用的场景。
    将 Model 的流式接口转换为请求-响应模式。
    """

    def __init__(self, model: "Model"):
        """初始化适配器

        Args:
            model: Model 实例
        """
        self.model = model

    async def invoke(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        abort_signal: "AbortSignal | None" = None,
    ) -> LLMResult | None:
        """调用 LLM

        Args:
            messages: 消息列表
            system_prompt: 系统提示（可选）
            abort_signal: 中断信号（可选）

        Returns:
            LLM 响应结果或 None
        """
        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                logger.info("LLM call aborted before request")
                return None

            # 构建消息（OpenAI 格式）
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})

            for msg in messages:
                api_messages.append({"role": msg.role, "content": msg.content})

            # 调用 Model 流式接口并聚合结果
            content_parts = []
            usage = None
            model_name = None

            async for chunk in self.model.arun_stream(messages=api_messages, tools=None):
                # 检查中断
                if abort_signal and abort_signal.is_aborted():
                    logger.info("LLM call aborted during streaming")
                    return None

                if chunk.content:
                    content_parts.append(chunk.content)

                if chunk.usage:
                    usage = chunk.usage

                # 从 model.id 提取模型名称
                if not model_name:
                    model_name = self.model.id

            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                logger.info("LLM call aborted after response")
                return None

            if not content_parts:
                return None

            return LLMResult(
                content="".join(content_parts),
                model=model_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
