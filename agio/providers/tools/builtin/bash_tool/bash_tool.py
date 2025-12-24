"""
BashTool - 命令执行工具
"""

import asyncio
import os
import shlex
import subprocess
import time
from typing import Any

from pydantic import BaseModel

from agio.providers.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry
from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext


class BashToolInput(BaseModel):
    """BashTool 输入参数"""

    command: str
    timeout: int | None = None


class BashToolOutput(BaseModel):
    """BashTool 输出结果"""

    stdout: str
    stdout_lines: int
    stderr: str
    stderr_lines: int
    interrupted: bool


class PersistentShell:
    """持久化 Shell 会话管理器"""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.cwd = os.getcwd()
        self.original_cwd = os.getcwd()

    async def start(self):
        """启动持久化 Shell 进程"""
        if self.process is None:
            self.process = subprocess.Popen(
                ["/bin/bash"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.cwd,
            )

    async def exec(
        self,
        command: str,
        signal: asyncio.Event | None = None,
        timeout: int = 120000,
    ) -> dict[str, Any]:
        """执行命令"""
        await self.start()

        # 检查中断信号
        if signal and signal.is_set():
            raise asyncio.CancelledError("Command cancelled before execution")

        try:
            # 执行命令并获取结果
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )

            # 等待命令完成, 支持超时和中断
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(), timeout=timeout / 1000.0
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout / 1000}s",
                    "code": -1,
                    "interrupted": True,
                }

            # 检查中断信号
            if signal and signal.is_set():
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise asyncio.CancelledError("Command cancelled during execution")

            return {
                "stdout": stdout_data.decode() if stdout_data else "",
                "stderr": stderr_data.decode() if stderr_data else "",
                "code": process.returncode,
                "interrupted": False,
            }

        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "code": -1,
                "interrupted": isinstance(e, asyncio.CancelledError),
            }

    def set_cwd(self, new_cwd: str):
        """设置工作目录"""
        self.cwd = new_cwd


class BashTool(BaseTool):
    """Bash 命令执行工具"""

    # 禁用的危险命令
    BANNED_COMMANDS = [
        "alias",
        "curl",
        "curlie",
        "wget",
        "axel",
        "aria2c",
        "nc",
        "telnet",
        "lynx",
        "w3m",
        "links",
        "httpie",
        "xh",
        "http-prompt",
        "chrome",
        "firefox",
        "safari",
    ]

    # 从配置中获取最大输出长度
    @property
    def max_output_length(self) -> int:
        return self._settings.tool.bash_tool_max_output_length

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        self._settings = settings or SettingsRegistry.get()
        super().__init__()
        self.shell = PersistentShell()
        self.original_cwd = os.getcwd()
        self.category = ToolCategory.SYSTEM
        self.risk_level = RiskLevel.HIGH
        self.timeout_seconds = self._settings.tool.bash_tool_timeout_seconds

    def get_name(self) -> str:
        return "bash"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return f"""执行给定的 bash 命令, 在持久化 Shell 会话中运行, 确保适当的处理和安全措施。

执行命令前, 请遵循以下步骤: 

1. 目录验证: 
   - 如果命令将创建新目录或文件, 首先使用 LS 工具验证父目录存在且位置正确
   - 例如, 运行 "mkdir foo/bar" 前, 先用 LS 检查 "foo" 存在且是预期的父目录

2. 安全检查: 
   - 为了安全和限制提示注入攻击的威胁, 某些命令是受限或禁用的
   - 验证命令不在禁用列表中: {", ".join(self.BANNED_COMMANDS)}

3. 命令执行: 
   - 确保正确引用后, 执行命令
   - 捕获命令的输出

4. 输出处理: 
   - 如果输出超过 {self.max_output_length} 字符, 输出将被截断
   - 准备输出以显示给用户

5. 返回结果: 
   - 提供命令的处理输出
   - 如果执行期间发生任何错误, 将其包含在输出中

使用说明: 
- command 参数是必需的
- 可以指定可选的超时时间(毫秒, 最多600000ms/10分钟)
- 重要: 必须避免使用 `find` 和 `grep` 等搜索命令, 使用 GrepTool、GlobTool 代替
- 必须避免使用 `cat`、`head`、`tail`、`ls` 等读取工具, 使用 FileReadTool 和 LSTool
- 发出多个命令时, 使用 ';' 或 '&&' 操作符分隔, 不要使用换行符
- 重要: 所有命令共享同一个 shell 会话, 状态(环境变量、虚拟环境、当前目录等)在命令间持续存在
- 尽量通过使用绝对路径和避免使用 `cd` 来维护当前工作目录
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {
                    "type": "integer",
                    "description": "超时时间(毫秒, 最大600000)",
                    "default": 120000,
                },
            },
            "required": ["command"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return False

    async def get_command_description(self, command: str) -> str:
        """使用 LLM 生成命令描述"""
        try:
            # 这里应该调用你的 LLM 服务
            # 示例: 简单的命令描述映射
            command_descriptions = {
                "ls": "Lists files in current directory",
                "git status": "Shows working tree status",
                "npm install": "Installs package dependencies",
                "mkdir": "Creates directory",
            }

            base_cmd = command.split()[0] if command.split() else command
            return command_descriptions.get(base_cmd, "Executes a bash command")

        except Exception:
            return "Executes a bash command"

    def validate_input(self, command: str) -> dict[str, Any]:
        """验证输入参数"""
        if not command.strip():
            return {"valid": False, "message": "Command cannot be empty"}

        # 分割命令(处理管道、分号等)
        commands: list[str] = self._split_command(command)

        for cmd in commands:
            parts = shlex.split(cmd.strip())
            if not parts:
                continue

            base_cmd = parts[0].lower()

            # 检查禁用命令
            if base_cmd in self.BANNED_COMMANDS:
                return {
                    "valid": False,
                    "message": f"Command '{base_cmd}' is not allowed for security reasons",
                }

            # 特殊处理 cd 命令
            if base_cmd == "cd" and len(parts) > 1:
                target_dir = parts[1].strip("'\"")
                full_target_dir = os.path.abspath(
                    target_dir
                    if os.path.isabs(target_dir)
                    else os.path.join(self.shell.cwd, target_dir)
                )

                # 检查是否在允许的目录范围内
                if not self._is_in_directory(full_target_dir, self.original_cwd):
                    return {
                        "valid": False,
                        "message": f"cd to '{full_target_dir}' was blocked. For security, only child directories of {self.original_cwd} are allowed.",
                    }

        return {"valid": True}

    def _split_command(self, command: str) -> list:
        """分割复合命令"""
        # 简单实现, 可以根据需要扩展
        return [cmd.strip() for cmd in command.split(";") if cmd.strip()]

    def _is_in_directory(self, path: str, parent: str) -> bool:
        """检查路径是否在父目录内"""
        try:
            path = os.path.abspath(path)
            parent = os.path.abspath(parent)
            return path.startswith(parent + os.sep) or path == parent
        except Exception:
            return False

    def _format_output(self, content: str) -> dict[str, Any]:
        """格式化输出内容"""
        lines = content.split("\n")
        total_lines = len(lines)

        if len(content) > self.max_output_length:
            # 截断内容, 截取开头和结尾
            mid = self.max_output_length // 2
            truncated_content = (
                content[:mid] + "\n... (output truncated)\n" + content[-mid:]
            )
            return {
                "content": truncated_content,
                "total_lines": total_lines,
                "truncated": True,
            }

        return {"content": content, "total_lines": total_lines, "truncated": False}

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行命令"""
        start_time = time.time()
        command = parameters.get("command", "")
        timeout = parameters.get("timeout", 120000)

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self.validate_input(command)
            if not validation["valid"]:
                return self._create_error_result(
                    parameters, validation["message"], start_time
                )

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 执行命令
            result = await self.shell.exec(command, None, timeout)

            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()

            if result.get("code", 0) != 0:
                stderr += f"\nExit code {result['code']}"

            # 检查工作目录是否超出范围
            if not self._is_in_directory(self.shell.cwd, self.original_cwd):
                self.shell.set_cwd(self.original_cwd)
                stderr += f"\nShell cwd was reset to {self.original_cwd}"

            # 格式化输出
            stdout_formatted = self._format_output(stdout)
            stderr_formatted = self._format_output(stderr)

            text_for_assistant = self._render_result_for_assistant(
                result.get("interrupted", False),
                stdout_formatted["content"],
                stderr_formatted["content"],
            )

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=text_for_assistant,
                output={
                    "stdout": stdout_formatted["content"],
                    "stdout_lines": stdout_formatted["total_lines"],
                    "stderr": stderr_formatted["content"],
                    "stderr_lines": stderr_formatted["total_lines"],
                    "interrupted": result.get("interrupted", False),
                    "exit_code": result.get("code", 0),
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except asyncio.CancelledError:
            return self._create_abort_result(parameters, start_time)
        except Exception as e:
            return self._create_error_result(
                parameters, f"Command failed: {e!s}", start_time
            )

    def _render_result_for_assistant(self, interrupted, stdout, stderr):
        error_message = stderr.strip()
        if interrupted:
            if error_message:
                error_message += "\n"
            error_message += "<error>Command was aborted before completion</error>"

        has_both = bool(stdout.strip()) and bool(error_message)
        result = stdout.strip()
        if has_both:
            result += "\n"
        result += error_message
        return result
