from dataclasses import dataclass
from typing import Dict, Optional
import asyncio
import os
import psutil
from enum import Enum
import uuid
from datetime import datetime


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
    pid: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""


class ShellSession:
    """持久化的 Shell 会话"""

    def __init__(self, working_dir: str, env: Optional[Dict[str, str]] = None):
        self.working_dir = working_dir
        self.env = env or os.environ.copy()
        self.processes: Dict[str, ProcessInfo] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self, command: str, timeout: Optional[float] = None, stream_output: bool = False
    ) -> ProcessInfo:
        """执行命令"""
        process_id = str(uuid.uuid4())
        process_info = ProcessInfo(
            id=process_id, command=command, status=ProcessStatus.PENDING
        )

        async with self._lock:
            self.processes[process_id] = process_info

        try:
            process_info.status = ProcessStatus.RUNNING
            process_info.start_time = datetime.now()

            # 创建子进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=self.env,
            )

            process_info.pid = process.pid

            if stream_output:
                # 流式输出
                await self._stream_output(process, process_info)
            else:
                # 批量输出
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
            await self._terminate_process(process_info.pid)
            process_info.status = ProcessStatus.TERMINATED
            raise
        finally:
            process_info.end_time = datetime.now()

        return process_info

    async def execute_background(self, command: str) -> ProcessInfo:
        """后台执行长时间运行的命令"""
        process_id = str(uuid.uuid4())
        process_info = ProcessInfo(
            id=process_id, command=command, status=ProcessStatus.PENDING
        )

        async with self._lock:
            self.processes[process_id] = process_info

        # 在后台任务中执行
        asyncio.create_task(self._run_background_process(process_info))

        return process_info

    async def _run_background_process(self, process_info: ProcessInfo):
        """运行后台进程"""
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

            # 持续读取输出
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

    async def _stream_output(self, process: asyncio.subprocess.Process, process_info: ProcessInfo):
        """流式读取进程输出"""

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

        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )
        await process.wait()

    async def terminate_process(self, process_id: str):
        """终止指定进程"""
        if process_id in self.processes:
            process_info = self.processes[process_id]
            if process_info.pid and process_info.status == ProcessStatus.RUNNING:
                await self._terminate_process(process_info.pid)
                process_info.status = ProcessStatus.TERMINATED
                process_info.end_time = datetime.now()

    async def _terminate_process(self, pid: int):
        """终止进程及其子进程"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # 先发送 SIGTERM
            for child in children:
                child.terminate()
            parent.terminate()

            # 等待进程结束
            gone, alive = psutil.wait_procs(children + [parent], timeout=5)

            # 如果还有存活的进程，发送 SIGKILL
            for p in alive:
                p.kill()

        except psutil.NoSuchProcess:
            pass

