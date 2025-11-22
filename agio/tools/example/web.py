"""
Example web tools.
"""


def search(query: str, max_results: int = 5) -> str:
    """
    Search the web for information.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        Search results as formatted string
        
    Example:
        >>> search("Python programming")
        "Search results for 'Python programming'..."
    """
    # This is a mock implementation
    return f"Search results for '{query}':\n1. Example result 1\n2. Example result 2\n3. Example result 3"


class WebScraperTool:
    """Web scraping tool."""

    name = "web_scraper"
    
    def __init__(self, timeout: int = 30, user_agent: str = "Agio/1.0", max_content_length: int = 100000):
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_content_length = max_content_length
    
    def scrape(self, url: str) -> str:
        """
        Scrape content from a web page.
        
        Args:
            url: URL to scrape
            
        Returns:
            Scraped content
        """
        # This is a mock implementation
        return f"Scraped content from {url}:\n[Mock content would appear here]"
    
    def __call__(self, url: str) -> str:
        """Make the tool callable."""
        return self.scrape(url)
