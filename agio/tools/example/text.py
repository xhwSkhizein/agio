"""
Example text processing tools.
"""


class TextSummarizerTool:
    """Text summarization tool."""
    
    def __init__(self, model: str = "gpt35", max_summary_length: int = 500, style: str = "concise"):
        self.model = model
        self.max_summary_length = max_summary_length
        self.style = style
    
    def summarize(self, text: str) -> str:
        """
        Summarize long text documents.
        
        Args:
            text: Text to summarize
            
        Returns:
            Summary of the text
        """
        # This is a mock implementation
        words = text.split()
        if len(words) <= 50:
            return text
        
        summary = " ".join(words[:50]) + "..."
        return f"Summary ({self.style} style): {summary}"
    
    def __call__(self, text: str) -> str:
        """Make the tool callable."""
        return self.summarize(text)
