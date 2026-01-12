"""
BashTool - Command execution tool.
"""

import asyncio
import os
import shlex
import subprocess
import time
from typing import Any

from pydantic import BaseModel

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.context import ExecutionContext
from agio.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.tools.builtin.common.configurable_tool import ConfigurableToolMixin
from agio.tools.builtin.config import BashConfig


class BashToolInput(BaseModel):
    """BashTool input parameters."""

    command: str
    timeout: int | None = None


class BashToolOutput(BaseModel):
    """BashTool output result."""

    stdout: str
    stdout_lines: int
    stderr: str
    stderr_lines: int
    interrupted: bool


class PersistentShell:
    """Persistent shell session manager."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.cwd = os.getcwd()
        self.original_cwd = os.getcwd()

    async def start(self):
        """Start persistent shell process."""
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
        """Execute command."""
        await self.start()

        # Check abort signal
        if signal and signal.is_set():
            raise asyncio.CancelledError("Command cancelled before execution")

        try:
            # Execute command and get result
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )

            # Wait for command completion, support timeout and interruption
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

            # Check abort signal
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
        """Set working directory."""
        self.cwd = new_cwd


class BashTool(BaseTool, ConfigurableToolMixin):
    """Bash command execution tool."""

    # Banned dangerous commands
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

    def __init__(
        self,
        *,
        config: BashConfig | None = None,
        **kwargs,
    ) -> None:
        self._config = self._init_config(BashConfig, config, **kwargs)
        super().__init__()
        self.shell = PersistentShell()
        self.original_cwd = os.getcwd()
        self.category = ToolCategory.SYSTEM
        self.risk_level = RiskLevel.HIGH
        self.timeout_seconds = self._config.timeout_seconds

    # Get maximum output length from config
    @property
    def max_output_length(self) -> int:
        return self._config.max_output_length

    def get_name(self) -> str:
        return "bash"

    def get_description(self) -> str:
        """Get tool prompt description."""
        return f"""Execute the given bash command in a persistent shell session, ensuring proper handling and security measures.

Before executing commands, follow these steps:

1. Directory validation:
   - If the command will create new directories or files, first use LS tool to verify the parent directory exists and is in the correct location
   - For example, before running "mkdir foo/bar", first check with LS that "foo" exists and is the expected parent directory

2. Security check:
   - For security and to limit prompt injection attack threats, certain commands are restricted or disabled
   - Verify the command is not in the banned list: {", ".join(self.BANNED_COMMANDS)}

3. Command execution:
   - After ensuring proper quoting, execute the command
   - Capture the command output

4. Output processing:
   - If output exceeds {self.max_output_length} characters, output will be truncated
   - Prepare output for display to user

5. Return results:
   - Provide processed command output
   - Include any errors that occurred during execution in the output

Usage notes:
- command parameter is required
- Optional timeout can be specified (milliseconds, max 600000ms/10 minutes)
- Important: Must avoid using search commands like `find` and `grep`, use GrepTool and GlobTool instead
- Must avoid using read tools like `cat`, `head`, `tail`, `ls`, use FileReadTool and LSTool instead
- When issuing multiple commands, use ';' or '&&' operators to separate, do not use newlines
- Important: All commands share the same shell session, state (environment variables, virtual environments, current directory, etc.) persists between commands
- Try to maintain current working directory by using absolute paths and avoiding `cd`
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in milliseconds (max 600000)",
                    "default": 120000,
                },
            },
            "required": ["command"],
        }

    def is_concurrency_safe(self) -> bool:
        """Whether the tool supports concurrency."""
        return False

    async def get_command_description(self, command: str) -> str:
        """Generate command description using LLM."""
        try:
            # Should call your LLM service here
            # Example: simple command description mapping
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
        """Validate input parameters."""
        if not command.strip():
            return {"valid": False, "message": "Command cannot be empty"}

        # Split command (handle pipes, semicolons, etc.)
        commands: list[str] = self._split_command(command)

        for cmd in commands:
            parts = shlex.split(cmd.strip())
            if not parts:
                continue

            base_cmd = parts[0].lower()

            # Check banned commands
            if base_cmd in self.BANNED_COMMANDS:
                return {
                    "valid": False,
                    "message": f"Command '{base_cmd}' is not allowed for security reasons",
                }

            # Special handling for cd command
            if base_cmd == "cd" and len(parts) > 1:
                target_dir = parts[1].strip("'\"")
                full_target_dir = os.path.abspath(
                    target_dir
                    if os.path.isabs(target_dir)
                    else os.path.join(self.shell.cwd, target_dir)
                )

                # Check if within allowed directory range
                if not self._is_in_directory(full_target_dir, self.original_cwd):
                    return {
                        "valid": False,
                        "message": (
                            f"cd to '{full_target_dir}' was blocked. "
                            f"For security, only child directories of "
                            f"{self.original_cwd} are allowed."
                        ),
                    }

        return {"valid": True}

    def _split_command(self, command: str) -> list:
        """Split compound command."""
        # Simple implementation, can be extended as needed
        return [cmd.strip() for cmd in command.split(";") if cmd.strip()]

    def _is_in_directory(self, path: str, parent: str) -> bool:
        """Check if path is within parent directory."""
        try:
            path = os.path.abspath(path)
            parent = os.path.abspath(parent)
            return path.startswith(parent + os.sep) or path == parent
        except Exception:
            return False

    def _format_output(self, content: str) -> dict[str, Any]:
        """Format output content."""
        lines = content.split("\n")
        total_lines = len(lines)

        if len(content) > self.max_output_length:
            # Truncate content, take beginning and end
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
        """Execute command."""
        start_time = time.time()
        command = parameters.get("command", "")
        timeout = parameters.get("timeout", 120000)

        try:
            # Check abort signal
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Validate input
            validation = self.validate_input(command)
            if not validation["valid"]:
                return self._create_error_result(
                    parameters, validation["message"], start_time
                )

            # Check abort signal again
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Execute command
            result = await self.shell.exec(command, None, timeout)

            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()

            if result.get("code", 0) != 0:
                stderr += f"\nExit code {result['code']}"

            # Check if working directory is out of range
            if not self._is_in_directory(self.shell.cwd, self.original_cwd):
                self.shell.set_cwd(self.original_cwd)
                stderr += f"\nShell cwd was reset to {self.original_cwd}"

            # Format output
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
