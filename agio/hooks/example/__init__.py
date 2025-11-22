"""
Example hook implementations.
"""

import logging
from pathlib import Path


class LoggingHook:
    """Hook for logging agent events."""
    
    def __init__(self, params: dict = None):
        params = params or {}
        
        log_level = params.get("log_level", "INFO")
        log_file = params.get("log_file", "./logs/agent.log")
        log_format = params.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Setup logger
        self.logger = logging.getLogger("AgentHook")
        self.logger.setLevel(getattr(logging, log_level))
        
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(log_format))
        self.logger.addHandler(handler)
    
    def on_start(self, event: dict):
        """Called when agent starts."""
        self.logger.info(f"Agent started: {event}")
    
    def on_step(self, event: dict):
        """Called on each step."""
        self.logger.debug(f"Agent step: {event}")
    
    def on_complete(self, event: dict):
        """Called when agent completes."""
        self.logger.info(f"Agent completed: {event}")
    
    def on_error(self, event: dict):
        """Called on error."""
        self.logger.error(f"Agent error: {event}")


class MetricsHook:
    """Hook for collecting agent metrics."""
    
    def __init__(self, params: dict = None):
        params = params or {}
        
        self.metrics_backend = params.get("metrics_backend", "prometheus")
        self.push_interval = params.get("push_interval", 60)
        self.metrics = {
            "total_runs": 0,
            "total_steps": 0,
            "total_errors": 0,
        }
    
    def on_start(self, event: dict):
        """Called when agent starts."""
        self.metrics["total_runs"] += 1
    
    def on_step(self, event: dict):
        """Called on each step."""
        self.metrics["total_steps"] += 1
    
    def on_error(self, event: dict):
        """Called on error."""
        self.metrics["total_errors"] += 1
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()
