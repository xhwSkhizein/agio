"""
Logging Hook implementation
"""

import logging
from typing import Any


class LoggingHook:
    """
    Hook for logging agent events.
    """
    
    def __init__(self, log_level: str = "INFO", **kwargs):
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = logging.getLogger("agio.hooks.logging")
        self.logger.setLevel(self.log_level)
        
        # Add handler if not present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    async def on_agent_start(self, agent_id: str, **kwargs):
        """Called when agent starts."""
        self.logger.info(f"Agent {agent_id} started")
    
    async def on_agent_finish(self, agent_id: str, **kwargs):
        """Called when agent finishes."""
        self.logger.info(f"Agent {agent_id} finished")
    
    async def on_tool_start(self, tool_name: str, **kwargs):
        """Called when tool starts."""
        self.logger.debug(f"Tool {tool_name} started")
    
    async def on_tool_finish(self, tool_name: str, result: Any, **kwargs):
        """Called when tool finishes."""
        self.logger.debug(f"Tool {tool_name} finished with result: {str(result)[:100]}...")
    
    async def on_error(self, error: Exception, **kwargs):
        """Called on error."""
        self.logger.error(f"Error occurred: {error}")
