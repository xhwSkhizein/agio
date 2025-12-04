"""
OutputStore for managing workflow execution outputs.

This module provides storage for stage outputs during workflow execution,
with support for loop iteration history and parallel branch isolation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputStore:
    """
    Output storage - manages all outputs during workflow execution.

    Features:
    1. Store stage outputs
    2. Support loop iteration history
    3. Provide snapshots for parallel execution isolation
    """

    # Main output storage
    _outputs: dict[str, Any] = field(default_factory=dict)

    # Loop related
    _loop_iteration: int = 0
    _loop_history: list[dict[str, str]] = field(default_factory=list)
    _loop_last: dict[str, str] = field(default_factory=dict)

    def set(self, key: str, value: str):
        """Store an output."""
        self._outputs[key] = value

    def get(self, key: str, default: str = "") -> str:
        """Get an output."""
        return self._outputs.get(key, default)

    def has(self, key: str) -> bool:
        """Check if an output exists and is non-empty."""
        return key in self._outputs and bool(self._outputs[key])

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for InputMapping.

        Includes loop-related variables.
        """
        result = dict(self._outputs)

        # Add loop-related variables
        result["loop"] = {
            "iteration": self._loop_iteration,
            "last": self._loop_last,
            "history": self._loop_history,
        }

        return result

    def start_iteration(self):
        """
        Start a new loop iteration.

        Saves current outputs to history before incrementing.
        """
        if self._loop_iteration > 0:
            # Save current iteration outputs to history
            current_outputs = {
                k: v for k, v in self._outputs.items() if k not in ("query", "loop")
            }
            self._loop_history.append(current_outputs)
            self._loop_last = current_outputs

        self._loop_iteration += 1

    def get_iteration(self) -> int:
        """Get current iteration number."""
        return self._loop_iteration

    def snapshot(self) -> dict[str, str]:
        """
        Create a snapshot of current state.

        Used for parallel execution isolation.
        """
        return dict(self._outputs)

    def merge(self, branch_id: str, output: str):
        """Merge branch output into the store."""
        self._outputs[branch_id] = output

    def clear_loop_state(self):
        """Clear loop-related state."""
        self._loop_iteration = 0
        self._loop_history = []
        self._loop_last = {}

    def keys(self) -> list[str]:
        """Get all output keys."""
        return list(self._outputs.keys())
