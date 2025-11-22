"""
Embedding models package
"""

from .base import EmbeddingModel
from .openai import OpenAIEmbedding

__all__ = ["EmbeddingModel", "OpenAIEmbedding"]
