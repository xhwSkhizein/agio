from typing import Dict, List, Optional
import asyncio
import os
import psutil
import uuid

from .shell_session import (
    ShellSession,
    ProcessInfo,
    ProcessStatus,
)


class BashToolManager:
    """Bash 工具管理器"""

    def __init__(self, base_dir: str, resource_limits: Optional[Dict] = None):
        self.base_dir = base_dir
        self.sessions: Dict[str, ShellSession] = {}
        self.resource_limits = resource_limits or {
            "max_sessions": 10,
            "max_processes_per_session": 20,
            "max_cpu_percent": 80,
            "max_memory_mb": 2048,
        }
        self._monitor_task = None

    async def create_session(
        self, project_dir: str, session_id: Optional[str] = None
    ) -> str:
        """创建新的 Shell 会话"""
        session_id = session_id or str(uuid.uuid4())

        if len(self.sessions) >= self.resource_limits["max_sessions"]:
            raise RuntimeError("Maximum number of sessions reached")

        working_dir = os.path.join(self.base_dir, project_dir)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        self.sessions[session_id] = ShellSession(working_dir)
        return session_id

    async def execute_in_session(
        self, session_id: str, command: str, **kwargs
    ) -> ProcessInfo:
        """在指定会话中执行命令"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.sessions[session_id]

        # 检查进程数限制
        running_processes = sum(
            1 for p in session.processes.values() if p.status == ProcessStatus.RUNNING
        )
        if running_processes >= self.resource_limits["max_processes_per_session"]:
            raise RuntimeError("Maximum number of processes per session reached")

        return await session.execute(command, **kwargs)

    async def execute_background_in_session(
        self, session_id: str, command: str
    ) -> ProcessInfo:
        """在会话中后台执行命令"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        return await self.sessions[session_id].execute_background(command)

    async def get_process_info(
        self, session_id: str, process_id: str
    ) -> Optional[ProcessInfo]:
        """获取进程信息"""
        if session_id in self.sessions:
            return self.sessions[session_id].processes.get(process_id)
        return None

    async def list_processes(self, session_id: str) -> List[ProcessInfo]:
        """列出会话中的所有进程"""
        if session_id in self.sessions:
            return list(self.sessions[session_id].processes.values())
        return []

    async def terminate_process(self, session_id: str, process_id: str):
        """终止指定进程"""
        if session_id in self.sessions:
            await self.sessions[session_id].terminate_process(process_id)

    async def cleanup_session(self, session_id: str):
        """清理会话"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # 终止所有运行中的进程
            for process_id, process_info in session.processes.items():
                if process_info.status == ProcessStatus.RUNNING:
                    await session.terminate_process(process_id)
            del self.sessions[session_id]

    async def start_monitoring(self):
        """启动资源监控"""
        if not self._monitor_task:
            self._monitor_task = asyncio.create_task(self._monitor_resources())

    async def _monitor_resources(self):
        """监控系统资源使用"""
        while True:
            try:
                # 检查 CPU 和内存使用
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()

                if cpu_percent > self.resource_limits["max_cpu_percent"]:
                    # 可以实现一些限流策略
                    pass

                if (
                    memory_info.used / 1024 / 1024
                    > self.resource_limits["max_memory_mb"]
                ):
                    # 可以实现一些清理策略
                    pass

                await asyncio.sleep(5)
            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(10)
