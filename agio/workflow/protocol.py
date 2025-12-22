"""
Runnable protocol and RunOutput - re-exported from domain.protocol.

This module re-exports core protocol types for backward compatibility.
The canonical definitions are now in agio.domain.protocol.
"""

from agio.domain.protocol import Runnable, RunOutput
from agio.domain.models import RunMetrics


__all__ = ["Runnable", "RunOutput", "RunMetrics"]
