"""GrepTool - 内容搜索工具"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from agio.providers.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry, get_logger
from agio.domain import ToolResult

if TYPE_CHECKING:
    from agio.agent.control import AbortSignal
    from agio.domain import ExecutionContext


class GrepToolOutput(BaseModel):
    """GrepTool 输出结果"""

    duration_ms: int
    num_files: int
    filenames: list[str]


class GrepTool(BaseTool):
    """内容搜索工具"""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self._logger = get_logger(__name__)

        self._project_root: Path = self._settings.project_root.resolve()
        self.category = ToolCategory.ANALYSIS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._settings.tool.grep_tool_timeout_seconds
        self.max_results = self._settings.tool.grep_tool_max_results

    def get_name(self) -> str:
        return "grep"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """基于 ripgrep 构建的强大搜索工具

使用说明: 
- 始终使用此工具进行搜索任务。永远不要调用 `grep` 或 `rg` 作为 Bash 命令
- 不要在可能有大量结果的初始搜索中使用
- 设置 pattern 支持完整的正则表达式语法(例如, "log.*Error", "function\\\\s+\\\\w+")
- 使用 include 参数以 glob 格式过滤文件(例如, "*.js", "**/*.tsx")
- 如果结果被截断, 使用更具体的查询或更多过滤器缩小搜索范围

该工具已针对正确的权限和访问进行了优化。
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式搜索模式"},
                "path": {
                    "type": "string",
                    "description": "搜索目录(可选, 默认当前目录)",
                },
                "include": {"type": "string", "description": "文件模式过滤(可选)"},
            },
            "required": ["pattern"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return True

    def validate_input(
        self, pattern: str, path: str | None = None, include: str | None = None
    ) -> dict[str, Any]:
        """验证输入参数"""
        if not pattern.strip():
            return {"valid": False, "message": "Search pattern cannot be empty"}

        try:
            resolved_path = self._resolve_search_path(path)
        except ValueError as error:
            return {"valid": False, "message": str(error)}

        if not resolved_path.exists():
            return {
                "valid": False,
                "message": f"Search path does not exist: {resolved_path.as_posix()}",
            }

        if not resolved_path.is_dir():
            return {
                "valid": False,
                "message": f"Search path is not a directory: {resolved_path.as_posix()}",
            }

        return {"valid": True, "resolved_path": resolved_path}

    def _resolve_search_path(self, path: str | None) -> Path:
        if not path:
            return self._project_root

        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._project_root):
            raise ValueError("Search path must be within the project root directory")

        return resolved

    async def _run_ripgrep(
        self,
        args: list[str],
        search_path: Path,
    ) -> list[Path]:
        """运行 ripgrep 命令"""
        try:
            process = await asyncio.create_subprocess_exec(
                "rg",
                *args,
                ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(search_path),
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "ripgrep (rg) is not installed. Please install ripgrep first."
            ) from error

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(),
                timeout=float(self.timeout_seconds),
            )
        except asyncio.TimeoutError as error:
            process.kill()
            await process.wait()
            raise RuntimeError(
                f"Search timed out after {self.timeout_seconds}s"
            ) from error
        except Exception:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise

        return_code = process.returncode or 0
        stderr_text = (stderr_data or b"").decode("utf-8", errors="ignore")
        if return_code not in (0, 1):
            raise RuntimeError(f"ripgrep failed: {stderr_text.strip()}")

        stdout_text = (stdout_data or b"").decode("utf-8", errors="ignore")
        results: list[Path] = []
        for line in stdout_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            candidate = Path(stripped)
            if not candidate.is_absolute():
                candidate = (search_path / candidate).resolve()
            else:
                candidate = candidate.resolve()

            try:
                if not candidate.is_relative_to(self._project_root):
                    continue
            except ValueError:
                continue

            results.append(candidate)

        return results

    def _sort_results(self, files: list[Path]) -> list[Path]:
        """排序搜索结果"""

        def sort_key(path: Path) -> tuple[float, str]:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            return (-mtime, path.as_posix())

        return sorted(files, key=sort_key)

    def _format_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self._project_root).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _format_result_for_assistant(self, output: GrepToolOutput) -> str:
        """格式化给助手的结果"""
        if output.num_files == 0:
            return "No files found"

        visible_files = output.filenames[: self.max_results]
        result = f"Found {output.num_files} file{'s' if output.num_files != 1 else ''}"
        if visible_files:
            result += "\n" + "\n".join(visible_files)

        if output.num_files > self.max_results:
            result += "\n(Results are truncated. Consider using a more specific path or pattern.)"

        return result

    def _format_result_for_user(self, output: GrepToolOutput) -> str:
        """格式化给用户的结果"""
        return self._format_result_for_assistant(output)

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行搜索"""
        start_time = time.time()
        pattern = parameters.get("pattern", "")
        path = parameters.get("path")
        include = parameters.get("include")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self.validate_input(pattern, path, include)
            if not validation["valid"]:
                return self._create_error_result(parameters, validation["message"], start_time)

            search_path: Path = validation.get("resolved_path") or self._resolve_search_path(path)

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 构建 ripgrep 参数
            args = ["--color=never", "-l", "-i", pattern]
            if include:
                args.extend(["--glob", include])

            # 执行搜索
            results = await self._run_ripgrep(args, search_path)

            # 检查中断（在搜索后）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 获取文件统计信息并排序
            sorted_paths = self._sort_results(results)
            formatted_filenames = [self._format_path(path_obj) for path_obj in sorted_paths]

            duration_ms = int((time.time() - start_time) * 1000)

            output_payload = GrepToolOutput(
                duration_ms=duration_ms,
                num_files=len(formatted_filenames),
                filenames=formatted_filenames,
            )

            result_text = self._format_result_for_assistant(output_payload)

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_text,
                output={
                    "duration_ms": duration_ms,
                    "num_files": len(formatted_filenames),
                    "filenames": formatted_filenames,
                    "search_path": search_path.as_posix(),
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except asyncio.CancelledError:
            self._logger.info("Grep search cancelled")
            return self._create_abort_result(parameters, start_time)
        except Exception as error:
            self._logger.exception("Error during grep search")
            return self._create_error_result(parameters, f"Search failed: {error!s}", start_time)
