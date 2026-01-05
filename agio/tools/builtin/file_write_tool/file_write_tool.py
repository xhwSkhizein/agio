"""
FileWriteTool - File write tool.

Provides file writing functionality with safety checks and diff generation.
"""

import difflib
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.tools.base import RiskLevel, ToolCategory
from agio.tools.builtin.common.configurable_tool import ConfigurableToolMixin
from agio.tools.builtin.common.file_operation_base import FileOperationBaseTool
from agio.tools.builtin.config import FileWriteConfig
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class Hunk(BaseModel):
    """Diff hunk."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


class FileWriteOutput(BaseModel):
    """File write output."""

    type: str  # "create" or "update"
    file_path: str
    content: str
    structured_patch: list[Hunk]


class FileStatus(BaseModel):
    """File status."""

    exists: bool
    old_content: str | None = None
    encoding: str = "utf-8"
    line_endings: str = "LF"


class FileWriteTool(FileOperationBaseTool, ConfigurableToolMixin):
    """File write tool."""

    def __init__(
        self,
        *,
        config: FileWriteConfig | None = None,
        project_root: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(project_root=project_root)
        self._config = self._init_config(FileWriteConfig, config, **kwargs)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.MEDIUM
        self.timeout_seconds = self._config.timeout_seconds

        # Configuration
        self.max_lines_to_render = 5
        self.max_lines_for_assistant = 16000
        self.max_file_size = int(self._config.max_file_size_mb * 1024 * 1024)
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
        """Get tool prompt description."""
        return """File write tool for creating or updating files in local filesystem.

Usage:
- file_path parameter must be absolute path, not relative path
- content parameter is the complete content to write to file
- If file does not exist, new file will be created
- If file exists, will completely overwrite file content
- Tool automatically creates necessary directory structure
- Supports multiple file formats and encodings

Security features:
- Automatic file encoding and line ending detection
- Provides detailed diff comparison information
- Validates file path security
- Checks filesystem permissions

Notes:
- This operation will completely overwrite existing file content
- Please ensure important files are backed up
- Some system paths may be restricted from access
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Absolute path to file to write "
                        "(must be absolute path, not relative)"
                    ),
                },
                "content": {"type": "string", "description": "要写入文件的内容"},
            },
            "required": ["file_path", "content"],
        }

    def is_concurrency_safe(self) -> bool:
        """Whether concurrent execution is supported."""
        return False

    def _validate_input(self, file_path: str, content: str) -> dict[str, Any]:
        """Validate input parameters."""
        valid_path, path_message = self._require_absolute_path(file_path)
        if not valid_path:
            return {"valid": False, "message": path_message}

        # Validate content
        if content is None or not isinstance(content, str):
            return {
                "valid": False,
                "message": "Content is required and must be a string",
            }

        # Validate file size
        if len(content) > self.max_file_size:
            return {
                "valid": False,
                "message": f"Content size exceeds maximum limit of {self.max_file_size} bytes",
            }

        # Check path safety
        if not self._is_path_safe(file_path):
            return {
                "valid": False,
                "message": "File path is not allowed for security reasons",
            }

        return {"valid": True}

    def _is_path_safe(self, file_path: str) -> bool:
        """Check if path is safe."""
        full_path = self._normalize_path(file_path)

        # Check if path is in blocked paths
        if self._is_blocked_path(full_path):
            return False

        # Allow creating files in temporary directories
        temp_dirs: list[str] = ["/tmp"]
        if any(full_path.startswith(temp_dir) for temp_dir in temp_dirs):
            # For files in temp directories, only check extension
            ext = Path(full_path).suffix.lower()
            if ext and ext not in self.allowed_extensions:
                return False
            return True

        # Check file extension
        ext = Path(full_path).suffix.lower()
        if ext and ext not in self.allowed_extensions:
            return False

        return True

    def _check_file_status(self, file_path: str) -> FileStatus:
        """Check file status."""
        full_path = self._normalize_path(file_path)

        # Check if file exists
        file_exists = os.path.exists(full_path)

        if not file_exists:
            return FileStatus(
                exists=False, old_content=None, encoding="utf-8", line_endings="LF"
            )

        # Get file information
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
        """Read file content."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try other encodings
            try:
                with open(file_path, encoding="latin-1") as f:
                    return f.read()
            except Exception:
                return ""
        except Exception:
            return ""

    def _process_content(self, content: str, line_endings: str) -> str:
        """Process content format."""
        if line_endings == "CRLF":
            # Convert LF to CRLF
            content = content.replace("\n", "\r\n")
        else:
            # Convert CRLF to LF
            content = content.replace("\r\n", "\n")

        return content

    def _ensure_directory_exists(self, file_path: str):
        """Ensure directory exists."""
        directory = os.path.dirname(self._normalize_path(file_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _generate_patch(
        self, file_path: str, old_content: str, new_content: str
    ) -> list[Hunk]:
        """Generate diff patch."""
        try:
            # Generate unified diff format
            diff = difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
                lineterm="",
            )

            # Parse diff into structured format
            hunks = []
            current_hunk = None

            for line in diff:
                if line.startswith("@@"):
                    # New diff hunk
                    if current_hunk:
                        hunks.append(current_hunk)

                    # Parse @@ line
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
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """Execute file write operation."""
        start_time = time.time()
        file_path = parameters.get("file_path")
        content = parameters.get("content")

        try:
            # Check for abort signal
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Validate input
            validation = self._validate_input(file_path, content)
            if not validation["valid"]:
                return self._create_error_result(
                    parameters, validation["message"], start_time
                )

            full_file_path = os.path.abspath(file_path)

            # Check abort signal again
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Check file status
            file_status = self._check_file_status(full_file_path)

            # Ensure directory exists
            self._ensure_directory_exists(full_file_path)

            # Process content format
            processed_content = self._process_content(content, file_status.line_endings)

            # Check abort signal after processing content
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Write file
            self.file_utils.write_text_content(
                full_file_path,
                processed_content,
                line_endings=file_status.line_endings,
            )

            # Update edit tracking
            self.file_edit_tracker.record_file_edit(full_file_path)

            # Generate result
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
            return self._create_error_result(
                parameters, f"File write failed: {e!s}", start_time
            )
