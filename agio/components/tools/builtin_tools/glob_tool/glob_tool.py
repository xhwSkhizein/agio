"""GlobTool - 文件模式匹配工具。"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from agio.components.tools.base_tool import BaseTool, RiskLevel, ToolCategory
from agio.components.tools.builtin_tools.adapter import AppSettings, SettingsRegistry, get_logger
from agio.core.events import ToolResult

if TYPE_CHECKING:
    from agio.execution.abort_signal import AbortSignal


class GlobOutput(BaseModel):
    """GlobTool 输出结果"""

    duration_ms: int
    num_files: int
    filenames: list[str]
    truncated: bool


class GlobTool(BaseTool):
    """文件模式匹配工具"""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self._logger = get_logger(__name__)

        self._project_root: Path = self._settings.project_root.resolve()
        self.current_dir = self._project_root.as_posix()
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._settings.tool.glob_tool_timeout_seconds

        # 配置
        self.default_limit = 100
        self.default_offset = 0
        self.max_search_depth = self._settings.tool.glob_tool_max_search_depth
        self.max_path_length = self._settings.tool.glob_tool_max_path_length
        self.max_pattern_length = self._settings.tool.glob_tool_max_pattern_length

    def get_name(self) -> str:
        return "glob"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """快速的文件模式匹配工具, 用于在代码库中搜索符合特定模式的文件。

使用说明: 
- 支持标准 glob 模式(如 `**/*.js`、`src/**/*.ts`)
- 高效处理大型代码库
- 基于文件修改时间排序
- 支持相对路径和绝对路径
- 自动解析工作目录
- 路径权限验证
- 支持结果数量限制和分页查询
- 截断状态指示
- 只读操作, 线程安全
- 路径安全检查
- 权限验证机制
"""
    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "用于匹配文件的 glob 模式",
                },
                "path": {
                    "type": "string",
                    "description": "搜索的目录路径, 默认为当前工作目录",
                },
            },
            "required": ["pattern"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return True

    def validate_input(self, pattern: str, path: str | None = None) -> dict[str, Any]:
        """验证输入参数"""
        if not pattern or not isinstance(pattern, str):
            return {
                "valid": False,
                "message": "Pattern is required and must be a string",
            }

        # 验证模式长度
        if len(pattern) > self.max_pattern_length:
            return {
                "valid": False,
                "message": f"Pattern too long (max {self.max_pattern_length} characters)",
            }

        # 检查危险字符
        dangerous_chars = ["\0", "~"]
        if any(char in pattern for char in dangerous_chars):
            return {"valid": False, "message": "Pattern contains dangerous characters"}

        # 验证路径
        if path and not isinstance(path, str):
            return {"valid": False, "message": "Path must be a string"}

        # 验证路径长度
        if path and len(path) > self.max_path_length:
            return {
                "valid": False,
                "message": f"Path too long (max {self.max_path_length} characters)",
            }

        return {"valid": True}

    def _resolve_path(self, path: str | None = None) -> Path:
        """解析搜索路径"""
        if not path:
            return self._project_root

        candidate = Path(path)

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        return candidate.resolve()

    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否允许访问"""
        try:
            candidate = path.resolve()

            if len(str(candidate)) > self.max_path_length:
                return False

            return candidate.is_relative_to(self._project_root)
        except ValueError:
            return False
        except Exception:
            return False

    def _normalize_pattern(self, pattern: str) -> str:
        """标准化 glob 模式"""
        # 处理 Windows 路径分隔符
        pattern = pattern.replace("\\", "/")

        # 确保模式以正确的格式结束
        if pattern.endswith("/"):
            pattern += "*"

        return pattern

    async def _glob_search(
        self, pattern: str, search_path: Path
    ) -> tuple[list[str], bool]:
        """执行 glob 搜索"""
        try:
            # 使用 pathlib 进行 glob 搜索
            search_dir = search_path
            if not search_dir.exists():
                return [], False

            # 标准化模式
            normalized_pattern = self._normalize_pattern(pattern)

            # 执行 glob 模式匹配
            matched_files = []

            # 处理不同的模式类型
            if "**/*" in normalized_pattern:
                # 递归搜索
                glob_pattern = normalized_pattern.replace("**/*", "**")
                for file_path in search_dir.glob(glob_pattern):
                    if file_path.is_file():
                        matched_files.append(file_path)
            else:
                # 非递归搜索
                for file_path in search_dir.glob(normalized_pattern):
                    if file_path.is_file():
                        matched_files.append(file_path)

            # 按修改时间排序
            sorted_files = self._sort_by_mtime(matched_files)

            # 应用分页
            total_files = len(sorted_files)
            truncated = total_files > self.default_offset + self.default_limit

            result_files = sorted_files[
                self.default_offset : self.default_offset + self.default_limit
            ]

            formatted_results = [self._format_path(result) for result in result_files]

            return formatted_results, truncated

        except Exception:
            # 记录错误但不抛出异常
            self._logger.exception(
                "Glob search failed", extra={"pattern": pattern, "path": str(search_path)}
            )
            return [], False

    def _sort_by_mtime(self, files: list[Path]) -> list[Path]:
        """按修改时间排序文件"""

        def get_mtime(file_path: str) -> float:
            try:
                return os.path.getmtime(file_path)
            except OSError:
                return 0.0

        return sorted(files, key=get_mtime, reverse=True)  # 最新的在前

    def _format_path(self, file_path: Path) -> str:
        try:
            return file_path.resolve().relative_to(self._project_root).as_posix()
        except ValueError:
            return file_path.resolve().as_posix()

    def _format_result_for_assistant(self, output: GlobOutput) -> str:
        """为助手格式化结果"""
        if output.num_files == 0:
            return "No files found"

        # 连接文件路径
        result = "\n".join(output.filenames)

        # 添加截断提示
        if output.truncated:
            result += "\n(Results are truncated. Consider using a more specific path or pattern.)"

        return result

    def _format_result_for_user(self, output: GlobOutput) -> str:
        """为用户格式化结果"""
        file_word = "file" if output.num_files == 1 else "files"

        return f"Found {output.num_files} {file_word} in {output.duration_ms}ms"

    async def execute(
        self,
        parameters: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行 glob 搜索"""
        start_time = time.time()
        pattern = parameters.get("pattern", "")
        path = parameters.get("path")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self.validate_input(pattern, path)
            if not validation["valid"]:
                return self._create_error_result(parameters, validation["message"], start_time)

            # 解析搜索路径
            search_path = self._resolve_path(path)

            # 检查路径权限
            if not self._is_path_allowed(search_path):
                return self._create_error_result(parameters, f"Path not allowed: {search_path.as_posix()}", start_time)

            # 检查路径是否存在
            if not search_path.exists():
                return self._create_error_result(parameters, f"Directory not found: {search_path.as_posix()}", start_time)

            if not search_path.is_dir():
                return self._create_error_result(parameters, f"Path is not a directory: {search_path.as_posix()}", start_time)

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 执行 glob 搜索
            files, truncated = await self._glob_search(pattern, search_path)
            
            # 检查中断（在搜索后）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)
            
            duration_ms = int((time.time() - start_time) * 1000)

            result_text = self._format_result_for_assistant(GlobOutput(
                duration_ms=duration_ms,
                num_files=len(files),
                filenames=files,
                truncated=truncated,
            ))

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_text,
                output={
                    "duration_ms": duration_ms,
                    "num_files": len(files),
                    "filenames": files,
                    "truncated": truncated,
                    "search_path": search_path.as_posix(),
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(parameters, f"Glob search failed: {e!s}", start_time)
