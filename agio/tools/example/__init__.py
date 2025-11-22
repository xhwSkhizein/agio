"""
Example tools for demonstration purposes.
"""

from .math import calculator
from .web import search, WebScraperTool
from .text import TextSummarizerTool
from .code import CodeSearchTool
from .testing import run_tests, format_code
from .knowledge import KnowledgeSearchTool
from .ticketing import CreateTicketTool
from .email import SendEmailTool

__all__ = [
    "calculator",
    "search",
    "WebScraperTool",
    "TextSummarizerTool",
    "CodeSearchTool",
    "run_tests",
    "format_code",
    "KnowledgeSearchTool",
    "CreateTicketTool",
    "SendEmailTool",
]
