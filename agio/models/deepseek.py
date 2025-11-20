import os
from typing import Any
from pydantic import Field, ConfigDict
from agio.models.openai import OpenAIModel
from agio.config import settings

class Deepseek(OpenAIModel):
    # Inherit arbitrary_types_allowed=True from OpenAIModel
    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(default="deepseek")
    name: str = Field(default="deepseek-chat")
    base_url: str | None = Field(default=None) # Will use default from config if None
    
    def model_post_init(self, __context: Any) -> None:
        # Override base_url/api_key resolution logic for Deepseek specific keys
        
        resolved_api_key = None
        if self.api_key:
            resolved_api_key = self.api_key.get_secret_value()
        elif settings.deepseek_api_key:
            resolved_api_key = settings.deepseek_api_key.get_secret_value()
        else:
            resolved_api_key = os.getenv("DEEPSEEK_API_KEY")

        resolved_base_url = self.base_url or settings.deepseek_base_url or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"

        if self.client is None:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )
