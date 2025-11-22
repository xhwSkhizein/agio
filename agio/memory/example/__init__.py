"""
Example memory implementations.
"""


class ConversationMemory:
    """Simple conversation memory for maintaining context."""
    
    def __init__(self, max_history_length: int = 20, max_tokens: int = 4000):
        self.max_history_length = max_history_length
        self.max_tokens = max_tokens
        self.messages = []
    
    def add_message(self, role: str, content: str):
        """Add a message to memory."""
        self.messages.append({"role": role, "content": content})
        
        # Trim if exceeds max length
        if len(self.messages) > self.max_history_length:
            self.messages = self.messages[-self.max_history_length:]
    
    def get_messages(self) -> list[dict]:
        """Get all messages from memory."""
        return self.messages.copy()
    
    def clear(self):
        """Clear all messages."""
        self.messages = []


class SemanticMemory:
    """Semantic memory with vector storage for long-term context."""
    
    def __init__(
        self,
        max_history_length: int = 100,
        vector_store: str = "chroma",
        embedding_model: str = "text-embedding-ada-002",
        params: dict = None
    ):
        self.max_history_length = max_history_length
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.params = params or {}
        self.messages = []
    
    def add_message(self, role: str, content: str):
        """Add a message to semantic memory."""
        # Mock implementation - would use vector embeddings in production
        self.messages.append({
            "role": role,
            "content": content,
            "embedding": f"[mock embedding for: {content[:50]}...]"
        })
        
        if len(self.messages) > self.max_history_length:
            self.messages = self.messages[-self.max_history_length:]
    
    def search_similar(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for similar messages."""
        # Mock implementation
        return self.messages[-top_k:]
    
    def get_messages(self) -> list[dict]:
        """Get all messages."""
        return self.messages.copy()
