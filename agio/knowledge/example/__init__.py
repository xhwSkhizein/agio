"""
Example knowledge base implementations.
"""

from pathlib import Path


class VectorKnowledge:
    """Vector-based knowledge base."""
    
    def __init__(
        self,
        vector_store: str = "chroma",
        embedding_model: str = "text-embedding-ada-002",
        params: dict = None
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.params = params or {}
        
        # Extract params
        self.collection_name = self.params.get("collection_name", "default")
        self.chunk_size = self.params.get("chunk_size", 1000)
        self.chunk_overlap = self.params.get("chunk_overlap", 200)
        self.data_path = self.params.get("data_path", "./data")
        
        self.documents = []
    
    def add_document(self, content: str, metadata: dict = None):
        """Add a document to the knowledge base."""
        self.documents.append({
            "content": content,
            "metadata": metadata or {},
            "embedding": f"[mock embedding for: {content[:50]}...]"
        })
    
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the knowledge base."""
        # Mock implementation - would use vector similarity in production
        return self.documents[:top_k]
    
    def load_from_directory(self, directory: str):
        """Load documents from a directory."""
        # Mock implementation
        data_dir = Path(directory)
        if data_dir.exists():
            # Would load actual files in production
            self.add_document(
                f"Mock document loaded from {directory}",
                {"source": directory}
            )
