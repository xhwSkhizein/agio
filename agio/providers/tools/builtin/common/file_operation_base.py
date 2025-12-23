"""Shared helpers for file operation tools."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, TYPE_CHECKING

from agio.providers.tools.base import BaseTool
from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry
from agio.providers.tools.builtin.common.file_utils import (
    FileEditTracker,
    FileUtils,
    get_file_edit_tracker,
    get_file_utils,
)
from agio.domain import ToolResult

if TYPE_CHECKING:
    from agio.agent.control import AbortSignal


class FileOperationBaseTool(BaseTool):
    """Base class that provides shared validation and error helpers."""

    blocked_paths = ["/etc", "/var", "/proc", "/sys", "/boot", "/root"]

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or SettingsRegistry.get()
        self.file_utils: FileUtils = get_file_utils(self._settings)
        self.file_edit_tracker: FileEditTracker = get_file_edit_tracker()

    def _normalize_path(self, file_path: str) -> str:
        return os.path.abspath(file_path)

    def _is_blocked_path(self, file_path: str) -> bool:
        normalized = self._normalize_path(file_path)
        return any(normalized.startswith(path) for path in self.blocked_paths)

    def _require_absolute_path(self, file_path: str) -> tuple[bool, str | None]:
        if not file_path or not isinstance(file_path, str):
            return False, "File path is required and must be a string"
        if not os.path.isabs(file_path):
            return False, "File path must be absolute, not relative"
        if self._is_blocked_path(file_path):
            return False, "File path is not allowed for security reasons"
        return True, None

    def _validate_file_path(self, file_path: str) -> tuple[bool, str | None, Path | None]:
        """
        验证文件路径。
        
        Returns:
            (is_valid, error_message, resolved_path)
        """
        if not file_path or not isinstance(file_path, str):
            return False, "File path is required and must be a string", None
        
        if not os.path.isabs(file_path):
            return False, "File path must be absolute, not relative", None
        
        if self._is_blocked_path(file_path):
            return False, "File path is not allowed for security reasons", None
        
        try:
            resolved = Path(file_path).resolve()
            return True, None, resolved
        except Exception as e:
            return False, f"Invalid file path: {e}", None
    
    def _read_file_content(self, file_path: Path) -> tuple[bool, str | None, str | None]:
        """
        读取文件内容。
        
        Returns:
            (success, content, error_message)
        """
        try:
            if not file_path.exists():
                return False, None, f"File does not exist: {file_path}"
            
            if not file_path.is_file():
                return False, None, f"Path is not a file: {file_path}"
            
            content = file_path.read_text(encoding="utf-8")
            return True, content, None
        except UnicodeDecodeError:
            return False, None, "File is not a valid UTF-8 text file"
        except PermissionError:
            return False, None, f"Permission denied: {file_path}"
        except Exception as e:
            return False, None, f"Failed to read file: {e}"
    
    def _write_file_content(
        self,
        file_path: Path,
        content: str,
        create_dirs: bool = True,
    ) -> tuple[bool, str | None]:
        """
        写入文件内容。
        
        Returns:
            (success, error_message)
        """
        try:
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content, encoding="utf-8")
            return True, None
        except PermissionError:
            return False, f"Permission denied: {file_path}"
        except Exception as e:
            return False, f"Failed to write file: {e}"
    
    def _format_numbered_lines(self, content: str, start_line: int = 1) -> str:
        """
        格式化带行号的内容。
        """
        lines = content.splitlines()
        numbered_lines = []
        for i, line in enumerate(lines, start=start_line):
            numbered_lines.append(f"{i:6d}\t{line}")
        return "\n".join(numbered_lines)

