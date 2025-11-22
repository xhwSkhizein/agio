"""
OpenAI Embeddings implementation
"""

import os
from .base import EmbeddingModel

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("openai package is required. Install with: uv add openai")


class OpenAIEmbedding(EmbeddingModel):
    """OpenAI Embeddings API implementation."""
    
    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        api_key: str | None = None,
        id: str | None = None,
        name: str | None = None,
        **kwargs
    ):
        self.model = model
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key, **kwargs)
    
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text using OpenAI API."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch using OpenAI API."""
        if not texts:
            return []
        
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [d.embedding for d in response.data]
