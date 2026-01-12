"""
Routes package initialization.
"""

from . import agents, health, metrics, sessions, tool_consent, traces

__all__ = [
    "agents",
    "health",
    "metrics",
    "sessions",
    "tool_consent",
    "traces",
]
