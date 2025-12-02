"""Shared helpers for file operation tools."""

import os
from datetime import datetime
from typing import Any

from agio.components.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolResultOutput,
    ToolResultOutputType,
    ToolResultType,
)


class FileOperationBaseTool(BaseTool):
    """Base class that provides shared validation and error helpers."""

    blocked_paths = ["/etc", "/var", "/proc", "/sys", "/boot", "/root"]

    def __init__(self) -> None:
        super().__init__()

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

    def _build_error_result(
        self,
        *,
        parameters: dict[str, Any],
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> ToolResult:
        return ToolResult(
            type=ToolResultType.ERROR,
            tool_call_id=parameters.get("tool_call_id", ""),
            tool_name=self.get_name(),
            parameters=parameters,
            output=ToolResultOutput(
                type=ToolResultOutputType.TEXT,
                result_for_llm=message,
                result_for_user=message,
                detail=self._build_detail(extra=detail),
            ),
        )

    def _build_detail(
        self,
        *,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
        }
        if extra:
            detail.update(extra)
        return detail
