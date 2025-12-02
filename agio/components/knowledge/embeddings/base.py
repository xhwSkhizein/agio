"""
Embedding models for vector operations
"""

from abc import ABC, abstractmethod


class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass
