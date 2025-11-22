"""
Semantic Memory implementation
"""

from agio.memory.base import SemanticMemoryManager, AgentMemoriedContent, MemoryCategory, Memory
from agio.knowledge.vector_knowledge import VectorKnowledge
from agio.knowledge.embeddings import EmbeddingModel
from agio.memory.conversation import ConversationMemory


class SemanticMemory(SemanticMemoryManager, Memory):
    """
    Semantic memory implementation using VectorKnowledge.
    Also includes ConversationMemory for chat history.
    """
    
    def __init__(
        self,
        vector_store: str,
        embedding_model: EmbeddingModel,
        collection_name: str = "semantic_memory",
        similarity_threshold: float = 0.75,
        **kwargs
    ):
        # Initialize Memory aggregate interface
        self.semantic = self
        # Initialize history with passed kwargs (e.g. max_history_length)
        self.history = ConversationMemory(**kwargs)

        # We reuse VectorKnowledge for storage and retrieval
        self.knowledge = VectorKnowledge(
            vector_store=vector_store,
            embedding_model=embedding_model,
            collection_name=collection_name,
            similarity_threshold=similarity_threshold,
            **kwargs
        )
    
    async def remember(self, user_id: str, memory: AgentMemoriedContent):
        """Store a memory item."""
        # Combine content and metadata
        content = memory.content
        metadata = {
            "user_id": user_id,
            "category": memory.category.value,
            "timestamp": memory.timestamp.isoformat(),
            "importance": memory.importance
        }
        if memory.tags:
            metadata["tags"] = ",".join(memory.tags)
            
        await self.knowledge.add_documents([content], [metadata])
    
    async def recall(
        self, 
        user_id: str, 
        query: str, 
        limit: int = 5, 
        categories: list[MemoryCategory] | None = None
    ) -> list[AgentMemoriedContent]:
        """Recall memories relevant to query."""
        # Note: VectorKnowledge.search currently returns text chunks.
        # To fully implement this, VectorKnowledge needs to return metadata too.
        # For now, this is a placeholder implementation that searches but might fail to reconstruct AgentMemoriedContent
        # accurately without metadata return support in VectorKnowledge.
        
        # TODO: Enhance VectorKnowledge to return metadata
        results = await self.knowledge.search(query, limit=limit)
        
        # Mock return for now since we can't reconstruct full objects yet
        memories = []
        for text in results:
            # Create a dummy memory object
            memories.append(AgentMemoriedContent(
                content=text,
                category=MemoryCategory.OBSERVATION, # Default
                importance=0.5
            ))
            
        return memories
