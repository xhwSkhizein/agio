"""
Tests for VectorKnowledge
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from agio.knowledge.vector_knowledge import VectorKnowledge
from agio.knowledge.embeddings import EmbeddingModel


class MockEmbedding(EmbeddingModel):
    async def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def mock_chroma():
    with patch("agio.knowledge.vector_knowledge.chromadb") as mock:
        # Mock client and collection
        client = MagicMock()
        collection = MagicMock()
        client.get_or_create_collection.return_value = collection
        mock.Client.return_value = client
        yield mock


@pytest.fixture
def knowledge(mock_chroma):
    return VectorKnowledge(
        vector_store="chroma",
        embedding_model=MockEmbedding(),
        chunk_size=100,
        chunk_overlap=10
    )


def test_init(knowledge, mock_chroma):
    """Test initialization."""
    mock_chroma.Client.assert_called_once()
    knowledge.client.get_or_create_collection.assert_called_once_with(name="knowledge")


@pytest.mark.asyncio
async def test_add_documents(knowledge):
    """Test adding documents."""
    docs = ["This is a test document.", "Another document."]
    metas = [{"source": "doc1"}, {"source": "doc2"}]
    
    await knowledge.add_documents(docs, metas)
    
    # Verify collection.add called
    knowledge.collection.add.assert_called_once()
    call_kwargs = knowledge.collection.add.call_args[1]
    assert len(call_kwargs["documents"]) >= 2
    assert len(call_kwargs["embeddings"]) >= 2
    assert len(call_kwargs["ids"]) >= 2


@pytest.mark.asyncio
async def test_search(knowledge):
    """Test searching."""
    # Mock query result
    knowledge.collection.query.return_value = {
        "documents": [["Result 1", "Result 2"]]
    }
    
    results = await knowledge.search("query", limit=2)
    
    assert len(results) == 2
    assert results[0] == "Result 1"
    assert results[1] == "Result 2"
    
    # Verify query called
    knowledge.collection.query.assert_called_once()
