"""
Example code tools.
"""

from pathlib import Path


class CodeSearchTool:
    """Code search tool."""

    name = "code_search"
    
    def __init__(
        self,
        repository_path: str,
        file_extensions: list[str] = None,
        exclude_dirs: list[str] = None
    ):
        self.repository_path = Path(repository_path) if repository_path else Path.cwd()
        self.file_extensions = file_extensions or [".py"]
        self.exclude_dirs = exclude_dirs or ["node_modules", ".git", "__pycache__"]
    
    def search(self, pattern: str) -> str:
        """
        Search through codebase for specific patterns.
        
        Args:
            pattern: Search pattern
            
        Returns:
            Search results
        """
        # This is a mock implementation
        return f"Searching for '{pattern}' in {self.repository_path}:\n[Mock search results: ....]"
    
    def __call__(self, pattern: str) -> str:
        """Make the tool callable."""
        return self.search(pattern)
