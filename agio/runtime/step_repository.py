"""
Step Repository - Unified Step persistence layer.

Provides a unified interface for Step persistence with support for:
- Single step persistence
- Batch persistence
- Transaction-like semantics via async context manager
"""

from agio.domain import Step
from agio.storage.session.base import SessionStore


class StepRepository:
    """
    Step persistence repository.

    Provides unified interface for Step persistence with support for
    batch operations and transaction-like semantics.

    Usage:
        # Context manager for automatic flush
        async with StepRepository(session_store) as repo:
            await repo.save(user_step)

            # Queue steps for batch save
            repo.queue(assistant_step)
            repo.queue(tool_step)
            # Automatically flushed on exit

        # Manual control
        repo = StepRepository(session_store)
        await repo.save(step)
        repo.queue(step1)
        repo.queue(step2)
        await repo.flush()
    """

    def __init__(self, session_store: "SessionStore | None", auto_flush_size: int = 2):
        """
        Initialize repository.

        Args:
            session_store: Session store for persistence
            auto_flush_size: Automatically flush when batch reaches this size (default: 2)
        """
        self.session_store = session_store
        self.auto_flush_size = auto_flush_size
        self._batch: list["Step"] = []

    async def save(self, step: "Step"):
        """
        Save a single step immediately.

        Args:
            step: Step to save
        """
        if self.session_store:
            await self.session_store.save_step(step)

    async def queue(self, step: "Step"):
        """
        Queue a step for batch save.

        Steps are saved when flush() is called, when batch reaches
        auto_flush_size, or when the context manager exits.

        Args:
            step: Step to queue
        """
        self._batch.append(step)

        # Auto flush if batch size reached
        if len(self._batch) >= self.auto_flush_size:
            await self.flush()

    async def flush(self):
        """
        Flush queued steps to storage.

        Uses batch save if available, otherwise saves individually.
        """
        if not self._batch:
            return

        if self.session_store:
            # Try batch save if available
            if hasattr(self.session_store, "save_steps_batch"):
                await self.session_store.save_steps_batch(self._batch)
            else:
                # Fallback to individual saves
                for step in self._batch:
                    await self.session_store.save_step(step)

        self._batch.clear()

    async def __aenter__(self):
        """Enter context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager.

        Automatically flushes queued steps if no exception occurred.
        """
        if exc_type is None:
            await self.flush()
        else:
            # On exception, clear batch without saving
            self._batch.clear()


__all__ = ["StepRepository"]
