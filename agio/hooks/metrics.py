"""
Metrics Hook implementation
"""

import time
from typing import Any

from agio.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsHook:
    """
    Hook for collecting agent metrics.
    """

    def __init__(self, **kwargs):
        self.metrics = {
            "agent_runs": 0,
            "tool_calls": 0,
            "errors": 0,
            "total_duration": 0.0,
        }
        self.start_times = {}

    async def on_agent_start(self, agent_id: str, **kwargs):
        """Called when agent starts."""
        self.metrics["agent_runs"] += 1
        self.start_times[f"agent_{agent_id}"] = time.time()

    async def on_agent_finish(self, agent_id: str, **kwargs):
        """Called when agent finishes."""
        start_time = self.start_times.pop(f"agent_{agent_id}", None)
        if start_time:
            duration = time.time() - start_time
            self.metrics["total_duration"] += duration
            logger.info(f"Agent {agent_id} duration: {duration:.2f}s")

    async def on_tool_start(self, tool_name: str, **kwargs):
        """Called when tool starts."""
        self.metrics["tool_calls"] += 1

    async def on_tool_finish(self, tool_name: str, result: Any, **kwargs):
        """Called when tool finishes."""
        pass

    async def on_error(self, error: Exception, **kwargs):
        """Called on error."""
        self.metrics["errors"] += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get collected metrics."""
        return self.metrics
