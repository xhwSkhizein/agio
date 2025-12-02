"""LSTool - 目录列表工具"""

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


class FileInfo(BaseModel):
    """文件信息模型"""

    name: str
    type: str
    size: int
    modified: float
    permissions: str


class LSToolOutput(BaseModel):
    """LSTool 输出结果"""

    directory_path: str
    items: list[str]
    total_items: int


class TreeNode:
    """File/directory tree node structure"""

    def __init__(self, name: str, path: str, node_type: str):
        self.name = name
        self.path = path
        self.type = node_type  # 'file' or 'directory'
        self.children: list[TreeNode] = []


def skip(path: str) -> bool:
    """Skip hidden files/directories and __pycache__ directories"""
    if os.path.basename(path).startswith("."):
        return True
    # Check for __pycache__ directory (with or without trailing separator)
    if f"__pycache__{os.sep}" in path or path.endswith("__pycache__"):
        return True
    return False


def create_file_tree(sorted_paths: list[str]) -> list[TreeNode]:
    """Convert flat path list to hierarchical tree structure"""
    root = []

    for path in sorted_paths:
        is_directory = path.endswith("/")
        normalized = path[:-1] if is_directory else path
        parts = [p for p in normalized.split("/") if p]
        current_level = root
        current_path = ""

        for i, part in enumerate(parts):
            current_path = f"{current_path}/{part}" if current_path else part
            is_last = i == len(parts) - 1

            # Check if node exists in current level
            node = next((n for n in current_level if n.name == part), None)

            if node:
                current_level = node.children
            else:
                # Determine node type (directories have trailing separator in path)
                node_type = "directory" if (not is_last or is_directory) else "file"
                new_node = TreeNode(part, current_path, node_type)
                current_level.append(new_node)
                current_level = new_node.children

    return root


def print_tree(
    tree: list[TreeNode], root_label: str | None = None, level: int = 0, prefix: str = ""
) -> str:
    """Render tree structure as formatted string"""
    result = ""

    if level == 0 and root_label is not None:
        label = root_label.rstrip("/") + "/"
        result += f"- {label}\n"
        prefix = "  "

    for node in tree:
        # Add trailing separator for directories
        suffix = os.sep if node.type == "directory" else ""
        result += f"{prefix}- {node.name}{suffix}\n"

        if node.children:
            result += print_tree(
                node.children, root_label=None, level=level + 1, prefix=prefix + "  "
            )

    return result


class LSTool(BaseTool):
    """目录列表工具 - 与JavaScript实现保持一致的树形输出格式"""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self._logger = get_logger(__name__)

        self._project_root: Path = self._settings.project_root.resolve()
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._settings.tool.ls_tool_timeout_seconds
        self.max_files = self._settings.tool.ls_tool_max_files
        self.max_lines = self._settings.tool.ls_tool_max_lines

        self._truncated_message = (
            "There are more than "
            f"{self.max_files} files in the repository. Use the LS tool "
            "(passing a specific path), Bash tool, and other tools to explore "
            "nested directories. The first "
            f"{self.max_files} files and directories are included below:\n\n"
        )

    def get_name(self) -> str:
        return "ls"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """列出给定路径中的文件和目录。
使用说明: 
- path 参数必须是绝对路径
- 以树形格式输出目录结构
- 最多显示1000个文件/目录
- 当文件数量超过1000时显示截断消息
- 输出格式示例: 
  - /current/working/directory/
    - src/
      - index.ts
      - utils/
        - file.ts
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径(必须是绝对路径)",
                }
            },
            "required": ["path"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return True

    def validate_input(self, path: str) -> dict[str, Any]:
        """验证输入参数"""
        if not path.strip():
            return {"valid": False, "message": "Path cannot be empty"}

        resolved_path = self._resolve_path(path)

        if not resolved_path.exists():
            return {
                "valid": False,
                "message": f"Path does not exist: {resolved_path.as_posix()}",
            }

        if not resolved_path.is_dir():
            return {
                "valid": False,
                "message": f"Path is not a directory: {resolved_path.as_posix()}",
            }

        if not os.access(resolved_path, os.R_OK):
            return {
                "valid": False,
                "message": (
                    "Permission denied: cannot read directory "
                    f"{resolved_path.as_posix()}"
                ),
            }

        return {"valid": True, "resolved_path": resolved_path}

    def _resolve_path(self, path: str) -> Path:
        candidate = Path(path.strip())

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._project_root):
            raise ValueError("Path must be within the project root directory")

        return resolved

    def _format_result_for_user(self, tree_output: str, is_truncated: bool) -> str:
        """格式化给用户的输出"""
        if is_truncated:
            return self._truncated_message + tree_output

        lines = tree_output.strip().split("\n")
        if len(lines) <= self.max_lines + 1:  # +1 for the root directory line
            return tree_output

        # Keep MAX_LINES lines of content plus the root directory line
        result = "\n".join(lines[: self.max_lines + 1])
        result += f"\n... (+{len(lines) - (self.max_lines + 1)} items)"
        return result

    def _format_result_for_assistant(self, tree_output: str, is_truncated: bool) -> str:
        """格式化给助手的结果"""
        if is_truncated:
            return self._truncated_message + tree_output
        return tree_output

    def _list_directory(self, initial_path: Path) -> list[Path]:
        """List directory contents using BFS traversal respecting max_files."""
        results: list[Path] = []
        queue: list[Path] = [initial_path]

        while queue:
            if len(results) >= self.max_files:
                return results[: self.max_files]

            path = queue.pop(0)
            path_posix = path.as_posix()
            if skip(path_posix):
                continue

            if path != initial_path:
                results.append(path)
                if len(results) >= self.max_files:
                    return results[: self.max_files]

            try:
                for entry in path.iterdir():
                    if entry.name in {".", ".."}:
                        continue
                    resolved_entry = entry.resolve()
                    resolved_posix = resolved_entry.as_posix()
                    if skip(resolved_posix):
                        continue
                    try:
                        resolved_entry.relative_to(self._project_root)
                    except ValueError:
                        continue

                    if entry.is_dir():
                        queue.append(resolved_entry)
                    else:
                        results.append(resolved_entry)
                        if len(results) >= self.max_files:
                            return results[: self.max_files]
            except (PermissionError, FileNotFoundError):
                continue
            except Exception as error:  # noqa: BLE001
                self._logger.debug(
                    "Skipping entry due to unexpected error",
                    path=path.as_posix(),
                    error=str(error),
                )
                continue

        return results

    def _format_paths_for_output(self, paths: list[Path]) -> list[str]:
        formatted: list[str] = []
        for path in paths:
            try:
                relative = path.resolve().relative_to(self._project_root)
            except ValueError:
                continue
            display = relative.as_posix()
            if path.is_dir():
                display = display.rstrip("/") + "/"
            formatted.append(display)
        return formatted

    def _create_tree_output(self, sorted_paths: list[str]) -> str:
        tree_nodes = create_file_tree(sorted_paths)
        return print_tree(tree_nodes, self._project_root.as_posix())

    async def execute(
        self,
        parameters: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行目录列表"""
        start_time = time.time()
        path = parameters.get("path", ".")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            try:
                validation = self.validate_input(path)
            except ValueError as error:
                return self._create_error_result(parameters, str(error), start_time)

            if not validation["valid"]:
                return self._create_error_result(parameters, validation["message"], start_time)

            resolved_path: Path = validation["resolved_path"]

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # List directory contents
            files = self._list_directory(resolved_path)
            formatted_files = self._format_paths_for_output(files)
            formatted_files.sort()

            # 检查中断（在处理大量文件后）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Generate tree visualization
            tree_output = self._create_tree_output(formatted_files)

            # Check if results were truncated
            is_truncated = len(formatted_files) >= self.max_files

            # Format outputs
            assistant_output = self._format_result_for_assistant(tree_output, is_truncated)

            # Prepare output data
            output = LSToolOutput(
                directory_path=resolved_path.as_posix(),
                items=formatted_files,
                total_items=len(formatted_files),
            )

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=assistant_output,
                output={
                    "directory_path": resolved_path.as_posix(),
                    "items": formatted_files,
                    "total_items": len(formatted_files),
                    "is_truncated": is_truncated,
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(parameters, f"Directory listing failed: {e!s}", start_time)
