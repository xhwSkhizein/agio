"""
Example knowledge tools.
"""


class KnowledgeSearchTool:
    """Knowledge base search tool."""
    
    def __init__(
        self,
        knowledge_base: str,
        max_results: int = 5,
        similarity_threshold: float = 0.7
    ):
        self.knowledge_base = knowledge_base
        self.max_results = max_results
        self.similarity_threshold = similarity_threshold
    
    def search(self, query: str) -> str:
        """
        Search the knowledge base for relevant information.
        
        Args:
            query: Search query
            
        Returns:
            Search results from knowledge base
        """
        # This is a mock implementation
        return f"Searching knowledge base '{self.knowledge_base}' for '{query}':\n1. Relevant document 1\n2. Relevant document 2"
    
    def __call__(self, query: str) -> str:
        """Make the tool callable."""
        return self.search(query)
