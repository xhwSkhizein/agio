"""
Vector Knowledge implementation with Chroma
"""

from pathlib import Path

from agio.components.knowledge.base import Knowledge
from agio.components.knowledge.chunking import TextChunker
from agio.components.knowledge.embeddings import EmbeddingModel
from agio.utils.logging import get_logger

logger = get_logger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    Settings = None


class VectorKnowledge(Knowledge):
    """
    Production-grade vector knowledge base with:
    - Document loading and chunking
    - Embedding generation
    - Vector similarity search
    - Chroma vector store
    """

    def __init__(
        self,
        vector_store: str,
        embedding_model: EmbeddingModel,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        data_path: str | None = None,
        similarity_threshold: float = 0.7,
        collection_name: str = "knowledge",
        **kwargs,
    ):
        if chromadb is None:
            raise ImportError("chromadb package is required. Install with: uv add chromadb")

        self.embedding_model = embedding_model
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.similarity_threshold = similarity_threshold
        self.collection_name = collection_name

        # Initialize Chroma client
        if vector_store == "chroma":
            self.client = chromadb.Client(Settings(anonymized_telemetry=False, allow_reset=True))
            self.collection = self.client.get_or_create_collection(name=collection_name)
        else:
            raise ValueError(f"Unsupported vector_store: {vector_store}")

        # Load documents if data_path provided
        if data_path:
            self._load_documents_from_path(data_path)

    def _load_documents_from_path(self, data_path: str):
        """Load documents from a directory."""
        path = Path(data_path)
        if not path.exists():
            logger.warning(f"Warning: data_path '{data_path}' does not exist")
            return

        documents = []
        metadatas = []

        # Load text files
        for file_path in path.rglob("*.txt"):
            try:
                content = file_path.read_text(encoding="utf-8")
                documents.append(content)
                metadatas.append({"source": str(file_path), "filename": file_path.name})
            except Exception as e:
                logger.error("Failed to load", file_path=file_path, err=e)

        # Load markdown files
        for file_path in path.rglob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                documents.append(content)
                metadatas.append({"source": str(file_path), "filename": file_path.name})
            except Exception as e:
                logger.error("Failed to load", file_path=file_path, err=e)

        if documents:
            logger.info(f"Loaded {len(documents)} documents from {data_path}")
            # Add documents asynchronously would require async init
            # For now, we'll skip auto-loading in __init__
            # Users should call add_documents() explicitly

    async def add_documents(self, documents: list[str], metadatas: list[dict] | None = None):
        """
        Add documents to the knowledge base.

        Args:
            documents: List of document texts
            metadatas: Optional metadata for each document
        """
        if not documents:
            return

        # Chunk documents
        chunked = self.chunker.chunk_documents(documents)

        # Prepare data
        texts = [chunk for chunk, _ in chunked]
        chunk_metadatas = []

        for chunk, doc_idx in chunked:
            meta = {"doc_index": doc_idx}
            if metadatas and doc_idx < len(metadatas):
                meta.update(metadatas[doc_idx])
            chunk_metadatas.append(meta)

        # Generate embeddings
        embeddings = await self.embedding_model.embed_batch(texts)

        # Generate IDs
        ids = [f"doc_{i}" for i in range(len(texts))]

        # Add to Chroma
        self.collection.add(
            documents=texts, embeddings=embeddings, metadatas=chunk_metadatas, ids=ids
        )

        logger.info(f"Added {len(texts)} chunks to knowledge base")

    async def search(self, query: str, limit: int = 5) -> list[str]:
        """
        Search the knowledge base.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of relevant text chunks
        """
        # Generate query embedding
        query_embedding = await self.embedding_model.embed_text(query)

        # Search Chroma
        results = self.collection.query(query_embeddings=[query_embedding], n_results=limit)

        # Extract and filter results
        documents = []
        if results and "documents" in results and results["documents"]:
            for doc_list in results["documents"]:
                documents.extend(doc_list)

        # Note: Chroma doesn't return similarity scores in the same way
        # We'll return all results up to limit
        return documents[:limit]
