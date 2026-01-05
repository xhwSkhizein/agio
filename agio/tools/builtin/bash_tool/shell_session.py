"""
Shell session module.

Manages individual shell sessions and process execution tracking.
"""

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import psutil


class ProcessStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class ProcessInfo:
    id: str
    command: str
    status: ProcessStatus
    pid: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class ShellSession:
    """Persistent shell session."""

    def __init__(self, working_dir: str, env: dict[str, str] | None = None) -> None:
        self.working_dir = working_dir
        self.env = env or os.environ.copy()
        self.processes: dict[str, ProcessInfo] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self, command: str, timeout: float | None = None, stream_output: bool = False
    ) -> ProcessInfo:
        """Execute command."""
        process_id = str(uuid.uuid4())
        process_info = ProcessInfo(
            id=process_id, command=command, status=ProcessStatus.PENDING
        )

        async with self._lock:
            self.processes[process_id] = process_info

        try:
            process_info.status = ProcessStatus.RUNNING
            process_info.start_time = datetime.now()

            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=self.env,
            )

            process_info.pid = process.pid

            if stream_output:
                # Stream output
                await self._stream_output(process, process_info)
            else:
                # Batch output
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                process_info.stdout = stdout.decode("utf-8", errors="replace")
                process_info.stderr = stderr.decode("utf-8", errors="replace")

            process_info.exit_code = process.returncode
            process_info.status = (
                ProcessStatus.COMPLETED
                if process.returncode == 0
                else ProcessStatus.FAILED
            )

        except asyncio.TimeoutError:
            if process_info.pid is not None:
                await self._terminate_process(process_info.pid)
            process_info.status = ProcessStatus.TERMINATED
            raise
        finally:
            process_info.end_time = datetime.now()

        return process_info

    async def execute_background(self, command: str) -> ProcessInfo:
        """Execute long-running command in background."""
        process_id = str(uuid.uuid4())
        process_info = ProcessInfo(
            id=process_id, command=command, status=ProcessStatus.PENDING
        )

        async with self._lock:
            self.processes[process_id] = process_info

        # Execute in background task
        asyncio.create_task(self._run_background_process(process_info))

        return process_info

    async def _run_background_process(self, process_info: ProcessInfo):
        """Run background process."""
        try:
            process_info.status = ProcessStatus.RUNNING
            process_info.start_time = datetime.now()

            process = await asyncio.create_subprocess_shell(
                process_info.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=self.env,
            )

            process_info.pid = process.pid

            # Continuously read output
            await self._stream_output(process, process_info)

            process_info.exit_code = process.returncode
            process_info.status = (
                ProcessStatus.COMPLETED
                if process.returncode == 0
                else ProcessStatus.FAILED
            )

        except Exception as e:
            process_info.status = ProcessStatus.FAILED
            process_info.stderr += f"\nError: {str(e)}"
        finally:
            process_info.end_time = datetime.now()

    async def _stream_output(
        self, process: asyncio.subprocess.Process, process_info: ProcessInfo
    ):
        """Stream process output."""

        async def read_stream(stream: asyncio.StreamReader, output_type: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded_line = line.decode("utf-8", errors="replace")
                if output_type == "stdout":
                    process_info.stdout += decoded_line
                else:
                    process_info.stderr += decoded_line

        if process.stdout is not None and process.stderr is not None:
            await asyncio.gather(
                read_stream(process.stdout, "stdout"),
                read_stream(process.stderr, "stderr"),
            )
        await process.wait()

    async def terminate_process(self, process_id: str):
        """Terminate specified process."""
        if process_id in self.processes:
            process_info = self.processes[process_id]
            if process_info.pid and process_info.status == ProcessStatus.RUNNING:
                await self._terminate_process(process_info.pid)
                process_info.status = ProcessStatus.TERMINATED
                process_info.end_time = datetime.now()

    async def _terminate_process(self, pid: int):
        """Terminate process and its child processes."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # Send SIGTERM first
            for child in children:
                child.terminate()
            parent.terminate()

            # Wait for processes to end
            gone, alive = psutil.wait_procs(children + [parent], timeout=5)

            # If there are still alive processes, send SIGKILL
            for p in alive:
                p.kill()

        except psutil.NoSuchProcess:
            pass
