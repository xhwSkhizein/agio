"""
FileWriteTool - 文件写入工具
"""

import difflib
import logging
import os
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from agio.providers.tools.base import RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings
from agio.providers.tools.builtin.common.file_operation_base import FileOperationBaseTool
from agio.domain import ToolResult

if TYPE_CHECKING:
    from agio.runtime.control import AbortSignal
logger = logging.getLogger(__name__)


class Hunk(BaseModel):
    """差异块"""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


class FileWriteOutput(BaseModel):
    """文件写入输出"""

    type: str  # "create" or "update"
    file_path: str
    content: str
    structured_patch: list[Hunk]


class FileStatus(BaseModel):
    """文件状态"""

    exists: bool
    old_content: str | None = None
    encoding: str = "utf-8"
    line_endings: str = "LF"


class FileWriteTool(FileOperationBaseTool):
    """文件写入工具"""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__(settings=settings)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.MEDIUM
        self.timeout_seconds = self._settings.tool.file_write_tool_timeout_seconds

        # 配置
        self.max_lines_to_render = 5
        self.max_lines_for_assistant = 16000
        self.max_file_size = (
            self._settings.tool.file_write_max_file_size_mb * 1024 * 1024
        )
        self.allowed_extensions = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".css",
            ".scss",
            ".sql",
            ".sh",
            ".bat",
            ".ps1",
            ".ini",
            ".cfg",
            ".conf",
            ".log",
        }
        self.blocked_paths = ["/etc", "/var", "/proc", "/sys", "/boot", "/root"]

    def get_name(self) -> str:
        return "file_write"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """这是一个文件写入工具, 用于在本地文件系统中创建或更新文件。

使用说明: 
- file_path 参数必须是绝对路径, 不能是相对路径
- content 参数是要写入文件的完整内容
- 如果文件不存在, 将创建新文件
- 如果文件已存在, 将完全覆盖文件内容
- 工具会自动创建必要的目录结构
- 支持多种文件格式和编码

安全特性: 
- 自动检测文件编码和行尾格式
- 提供详细的差异对比信息
- 验证文件路径安全性
- 检查文件系统权限

注意事项: 
- 此操作将完全覆盖现有文件内容
- 请确保备份重要文件
- 某些系统路径可能被限制访问
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要写入文件的绝对路径(必须是绝对路径, 不能是相对路径)",
                },
                "content": {"type": "string", "description": "要写入文件的内容"},
            },
            "required": ["file_path", "content"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return False

    def _validate_input(self, file_path: str, content: str) -> dict[str, Any]:
        """验证输入参数"""
        valid_path, path_message = self._require_absolute_path(file_path)
        if not valid_path:
            return {"valid": False, "message": path_message}

        # 验证内容
        if content is None or not isinstance(content, str):
            return {
                "valid": False,
                "message": "Content is required and must be a string",
            }

        # 验证文件大小
        if len(content) > self.max_file_size:
            return {
                "valid": False,
                "message": f"Content size exceeds maximum limit of {self.max_file_size} bytes",
            }

        # 检查路径安全性
        if not self._is_path_safe(file_path):
            return {
                "valid": False,
                "message": "File path is not allowed for security reasons",
            }

        return {"valid": True}

    def _is_path_safe(self, file_path: str) -> bool:
        """检查路径是否安全"""
        full_path = self._normalize_path(file_path)

        # 检查是否在阻止的路径中
        if self._is_blocked_path(full_path):
            return False

        # 允许在临时目录中创建文件
        temp_dirs: list[str] = ["/tmp"]
        if any(full_path.startswith(temp_dir) for temp_dir in temp_dirs):
            # 临时目录中的文件, 只检查扩展名
            ext = Path(full_path).suffix.lower()
            if ext and ext not in self.allowed_extensions:
                return False
            return True

        # 检查文件扩展名
        ext = Path(full_path).suffix.lower()
        if ext and ext not in self.allowed_extensions:
            return False

        return True

    def _check_file_status(self, file_path: str) -> FileStatus:
        """检查文件状态"""
        full_path = self._normalize_path(file_path)

        # 检查文件是否存在
        file_exists = os.path.exists(full_path)

        if not file_exists:
            return FileStatus(
                exists=False, old_content=None, encoding="utf-8", line_endings="LF"
            )

        # 获取文件信息
        old_content = self._read_file_content(full_path)
        encoding = self.file_utils.detect_encoding(full_path)
        line_endings = self.file_utils.detect_line_endings(full_path)

        return FileStatus(
            exists=True,
            old_content=old_content,
            encoding=encoding,
            line_endings=line_endings,
        )

    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, encoding="latin-1") as f:
                    return f.read()
            except Exception:
                return ""
        except Exception:
            return ""

    def _process_content(self, content: str, line_endings: str) -> str:
        """处理内容格式"""
        if line_endings == "CRLF":
            # 将 LF 转换为 CRLF
            content = content.replace("\n", "\r\n")
        else:
            # 将 CRLF 转换为 LF
            content = content.replace("\r\n", "\n")

        return content

    def _ensure_directory_exists(self, file_path: str):
        """确保目录存在"""
        directory = os.path.dirname(self._normalize_path(file_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _generate_patch(
        self, file_path: str, old_content: str, new_content: str
    ) -> list[Hunk]:
        """生成差异补丁"""
        try:
            # 生成统一格式的差异
            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
                lineterm="",
            )

            # 解析差异为结构化格式
            hunks = []
            current_hunk = None

            for line in diff:
                if line.startswith("@@"):
                    # 新的差异块
                    if current_hunk:
                        hunks.append(current_hunk)

                    # 解析 @@ 行
                    parts = line.split(" ")
                    if len(parts) >= 3:
                        old_info = parts[1]
                        new_info = parts[2]

                        old_start = int(old_info.split(",")[0][1:])
                        old_count = (
                            int(old_info.split(",")[1]) if "," in old_info else 1
                        )
                        new_start = int(new_info.split(",")[0][1:])
                        new_count = (
                            int(new_info.split(",")[1]) if "," in new_info else 1
                        )

                        current_hunk = Hunk(
                            old_start=old_start,
                            old_count=old_count,
                            new_start=new_start,
                            new_count=new_count,
                            lines=[],
                        )
                elif current_hunk:
                    current_hunk.lines.append(line)

            if current_hunk:
                hunks.append(current_hunk)

            return hunks

        except Exception as e:
            logger.exception(f"Failed to generate diff: {e}")
            return []

    async def execute(
        self,
        parameters: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行文件写入"""
        start_time = time.time()
        file_path = parameters.get("file_path")
        content = parameters.get("content")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self._validate_input(file_path, content)
            if not validation["valid"]:
                return self._create_error_result(parameters, validation["message"], start_time)

            full_file_path = os.path.abspath(file_path)

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 检查文件状态
            file_status = self._check_file_status(full_file_path)

            # 确保目录存在
            self._ensure_directory_exists(full_file_path)

            # 处理内容格式
            processed_content = self._process_content(content, file_status.line_endings)

            # 检查中断（在处理内容后）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 写入文件
            self.file_utils.write_text_content(
                full_file_path,
                processed_content,
                line_endings=file_status.line_endings,
            )

            # 更新编辑追踪
            self.file_edit_tracker.record_file_edit(full_file_path)

            # 生成结果
            if file_status.exists:
                structured_patch = self._generate_patch(
                    file_path, file_status.old_content or "", processed_content
                )
                operation_type = "update"
                result_message = f"File '{file_path}' has been updated successfully."
                if structured_patch:
                    result_message += f" {len(structured_patch)} changes were made."
            else:
                structured_patch = []
                operation_type = "create"
                result_message = f"File '{file_path}' has been created successfully."

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_message,
                output={
                    "type": operation_type,
                    "file_path": file_path,
                    "content_length": len(processed_content),
                    "num_changes": len(structured_patch),
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(parameters, f"File write failed: {e!s}", start_time)
