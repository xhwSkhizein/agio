"""
Bash tool manager module.

Manages shell sessions and process execution for bash tool operations.
"""

import asyncio
import os
import uuid

import psutil

from agio.utils.logging import get_logger

from .shell_session import (
    ProcessInfo,
    ProcessStatus,
    ShellSession,
)

logger = get_logger(__name__)


class BashToolManager:
    """Bash tool manager."""

    def __init__(self, base_dir: str, resource_limits: dict | None = None) -> None:
        self.base_dir = base_dir
        self.sessions: dict[str, ShellSession] = {}
        self.resource_limits = resource_limits or {
            "max_sessions": 10,
            "max_processes_per_session": 20,
            "max_cpu_percent": 80,
            "max_memory_mb": 2048,
        }
        self._monitor_task = None

    async def create_session(self, project_dir: str, session_id: str | None = None) -> str:
        """Create new shell session."""
        session_id = session_id or str(uuid.uuid4())

        if len(self.sessions) >= self.resource_limits["max_sessions"]:
            raise RuntimeError("Maximum number of sessions reached")

        working_dir = os.path.join(self.base_dir, project_dir)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        self.sessions[session_id] = ShellSession(working_dir)
        return session_id

    async def execute_in_session(self, session_id: str, command: str, **kwargs) -> ProcessInfo:
        """Execute command in specified session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]

        # Check process count limit
        running_processes = sum(
            1 for p in session.processes.values() if p.status == ProcessStatus.RUNNING
        )
        if running_processes >= self.resource_limits["max_processes_per_session"]:
            raise RuntimeError("Maximum number of processes per session reached")

        return await session.execute(command, **kwargs)

    async def execute_background_in_session(self, session_id: str, command: str) -> ProcessInfo:
        """Execute command in background in session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        return await self.sessions[session_id].execute_background(command)

    async def get_process_info(self, session_id: str, process_id: str) -> ProcessInfo | None:
        """Get process information."""
        if session_id in self.sessions:
            return self.sessions[session_id].processes.get(process_id)
        return None

    async def list_processes(self, session_id: str) -> list[ProcessInfo]:
        """List all processes in session."""
        if session_id in self.sessions:
            return list(self.sessions[session_id].processes.values())
        return []

    async def terminate_process(self, session_id: str, process_id: str):
        """Terminate specified process."""
        if session_id in self.sessions:
            await self.sessions[session_id].terminate_process(process_id)

    async def cleanup_session(self, session_id: str):
        """Clean up session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # Terminate all running processes
            for process_id, process_info in session.processes.items():
                if process_info.status == ProcessStatus.RUNNING:
                    await session.terminate_process(process_id)
            del self.sessions[session_id]

    async def start_monitoring(self):
        """Start resource monitoring."""
        if not self._monitor_task:
            self._monitor_task = asyncio.create_task(self._monitor_resources())

    async def _monitor_resources(self):
        """Monitor system resource usage."""
        while True:
            try:
                # Check CPU and memory usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()

                if cpu_percent > self.resource_limits["max_cpu_percent"]:
                    # Can implement throttling strategies
                    pass

                if memory_info.used / 1024 / 1024 > self.resource_limits["max_memory_mb"]:
                    # Can implement cleanup strategies
                    pass

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(10)
