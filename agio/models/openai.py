import os
from typing import Any, AsyncIterator
from pydantic import Field, SecretStr, ConfigDict

try:
    from openai import AsyncOpenAI, APIConnectionError, RateLimitError, InternalServerError, APITimeoutError
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
except ImportError:
    raise ImportError("Please install openai package: pip install openai")

from agio.config import settings
from agio.models.base import Model, ModelResponse, ModelDelta
from agio.domain.messages import Message, SystemMessage, UserMessage, AssistantMessage, ToolMessage
from agio.utils.retry import retry_async

# Define specific retryable exceptions for OpenAI
OPENAI_RETRYABLE = (
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    APITimeoutError
)

class OpenAIModel(Model):
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    id: str = Field(default="openai")
    name: str = Field(default="gpt-4o")
    api_key: SecretStr | None = Field(default=None, exclude=True)
    base_url: str | None = Field(default=None)
    client: AsyncOpenAI | None = Field(default=None, exclude=True)
    
    # Model Config
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    def model_post_init(self, __context: Any) -> None:
        """
        Pydantic V2 hook called after the model is initialized.
        We use this to initialize the AsyncOpenAI client if it wasn't provided.
        """
        # Resolve API Key: 1. Argument 2. Config/Env
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.openai_api_key:
            resolved_api_key = settings.openai_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("OPENAI_API_KEY") # Fallback to direct env var if settings failed
            
        # Resolve Base URL
        resolved_base_url = self.base_url or settings.openai_base_url or os.getenv("OPENAI_BASE_URL")

        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )
        
        super().model_post_init(__context)
            
    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, UserMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AssistantMessage):
                d = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    d["tool_calls"] = msg.tool_calls
                formatted.append(d)
            elif isinstance(msg, ToolMessage):
                formatted.append({
                    "role": "tool", 
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content
                })
        return formatted

    @retry_async(exceptions=OPENAI_RETRYABLE)
    async def aresponse(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> ModelResponse:
        formatted_msgs = self._format_messages(messages)
        
        openai_tools = None
        if tools:
            openai_tools = [t.to_openai_schema() for t in tools]

        params = {
            "model": self.name,
            "messages": formatted_msgs,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
            "presence_penalty": kwargs.get("presence_penalty", self.presence_penalty),
        }
        if openai_tools:
            params["tools"] = openai_tools

        response: ChatCompletion = await self.client.chat.completions.create(**params)
        
        choice = response.choices[0]
        content = choice.message.content or ""
        
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        return ModelResponse(
            content=content,
            raw_response=response.model_dump(),
            usage=usage,
            first_token_timestamp=None 
        )

    # Note: Retrying a stream is tricky. If it fails mid-stream, we might duplicate content if we just retry.
    # Usually, for streams, we retry only on the connection establishment. Once streaming starts, if it breaks, 
    # the caller needs to handle it (e.g., resume). 
    # Here, tenacity will retry the whole function call if it fails before yielding anything or if an error bubbles up.
    @retry_async(exceptions=OPENAI_RETRYABLE)
    async def astream(self, messages: list[Message], tools: list[Any] | None = None, **kwargs) -> AsyncIterator[ModelDelta]:
        formatted_msgs = self._format_messages(messages)
        
        openai_tools = None
        if tools:
            openai_tools = [t.to_openai_schema() for t in tools]

        params = {
            "model": self.name,
            "messages": formatted_msgs,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
            "presence_penalty": kwargs.get("presence_penalty", self.presence_penalty),
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        if openai_tools:
            params["tools"] = openai_tools

        stream = await self.client.chat.completions.create(**params)
        
        async for chunk in stream:
            delta = ModelDelta()
            
            if chunk.usage:
                delta.usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens
                }
            
            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                if choice.delta.content:
                    delta.content = choice.delta.content
                if choice.delta.tool_calls:
                    # OpenAI returns tool calls as list of ChoiceDeltaToolCall
                    delta.tool_calls = [tc.model_dump() for tc in choice.delta.tool_calls]
                if choice.delta.role:
                    delta.role = choice.delta.role
            
            # Only yield if there is something (usage or content or tool_calls)
            if delta.content is not None or delta.tool_calls is not None or delta.usage is not None:
                yield delta
