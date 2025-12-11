"""
DeepSeek Model implementation - Inherits from OpenAIModel

DeepSeek API is compatible with OpenAI format.
"""

import os
from typing import AsyncIterator

from pydantic import ConfigDict, Field

from agio.providers.llm.base import StreamChunk
from agio.providers.llm.openai import OpenAIModel


class DeepseekModel(OpenAIModel):
    """
    DeepSeek Model implementation.

    DeepSeek uses OpenAI-compatible API format, so inherits OpenAIModel.
    Handles DeepSeek-specific logic including thinking mode (reasoning_content).
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default="deepseek/deepseek-chat")
    name: str = Field(default="deepseek-chat")
    base_url: str | None = Field(default=None)

    def model_post_init(self, __context) -> None:
        """Override to use DeepSeek-specific API key and base URL."""
        from agio.config import settings

        # Resolve API Key: deepseek_api_key > DEEPSEEK_API_KEY
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.deepseek_api_key:
            resolved_api_key = settings.deepseek_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("DEEPSEEK_API_KEY")

        # Resolve Base URL
        resolved_base_url = (
            self.base_url
            or settings.deepseek_base_url
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )

        # Create client
        if self.client is None:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

        # Call grandparent's model_post_init (skip OpenAIModel to avoid double client init)
        from agio.providers.llm.base import Model

        Model.model_post_init(self, __context)

    def _preprocess_messages_for_thinking_mode(self, messages: list[dict]) -> list[dict]:
        """
        Preprocess messages for DeepSeek thinking mode.

        According to DeepSeek API docs:
        - If the last message is a user message (new turn), remove reasoning_content from all history assistant messages
        - If using deepseek-reasoner model, ensure all assistant messages have reasoning_content field (set to None if missing)

        Args:
            messages: List of messages in OpenAI format

        Returns:
            Preprocessed messages ready for API call
        """
        if not messages:
            return messages

        # Check if this is a thinking mode model
        model_name = self.model_name or self.name
        is_thinking_mode = (
            "reasoner" in model_name.lower() or "deepseek-reasoner" in model_name.lower()
        )

        # Check if last message is a user message (new conversation turn)
        last_message = messages[-1]
        is_new_turn = last_message.get("role") == "user"

        # Create a copy to avoid modifying the original
        processed_messages = []

        for i, msg in enumerate(messages):
            msg_copy = msg.copy()

            # Only process assistant messages
            if msg_copy.get("role") == "assistant":
                if is_new_turn:
                    # New turn: remove reasoning_content from history messages
                    # (per DeepSeek docs: only include content, not reasoning_content in history)
                    if "reasoning_content" in msg_copy:
                        del msg_copy["reasoning_content"]
                else:
                    # Same turn: preserve reasoning_content if present
                    # If thinking mode and reasoning_content not present, set to None
                    if is_thinking_mode and "reasoning_content" not in msg_copy:
                        msg_copy["reasoning_content"] = None

            processed_messages.append(msg_copy)

        return processed_messages

    async def arun_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Call DeepSeek API with thinking mode support.

        Preprocesses messages according to DeepSeek thinking mode requirements:
        - If last message is user (new turn), removes reasoning_content from history
        - If using deepseek-reasoner, ensures all assistant messages have reasoning_content field

        Args:
            messages: OpenAI format message list
            tools: Tool definition list, OpenAI format

        Yields:
            StreamChunk: Standardized streaming output chunk
        """
        # Preprocess messages for thinking mode
        processed_messages = self._preprocess_messages_for_thinking_mode(messages)

        # Call parent's arun_stream with processed messages
        async for chunk in super().arun_stream(processed_messages, tools=tools):
            yield chunk


__all__ = ["DeepseekModel"]
