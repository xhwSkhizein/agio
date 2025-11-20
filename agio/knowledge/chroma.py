import chromadb
from chromadb.config import Settings
from agio.knowledge.base import Knowledge
from agio.config import settings

class ChromaKnowledge(Knowledge):
    def __init__(self, collection_name: str = "agio_knowledge", persist_directory: str | None = None):
        self.persist_directory = persist_directory or settings.vector_db_path or "./chroma_db"
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # TODO: Accept custom embedding function. Defaults to all-MiniLM-L6-v2 (onnx)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    async def search(self, query: str, limit: int = 5) -> list[str]:
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        # Chroma returns list of lists (batch query support)
        if results["documents"] and len(results["documents"]) > 0:
            return results["documents"][0]
        return []
    
    # Helper to add documents (sync for now as chroma client is sync)
    def add_documents(self, documents: list[str], metadatas: list[dict] | None = None, ids: list[str] | None = None):
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
            
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

