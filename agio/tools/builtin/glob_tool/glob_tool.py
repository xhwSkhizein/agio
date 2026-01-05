"""
GlobTool - File pattern matching tool.

Provides fast file pattern matching using glob patterns for codebase searching.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.protocol import ExecutionContext
from agio.tools.base import BaseTool, RiskLevel, ToolCategory
from agio.tools.builtin.common.configurable_tool import ConfigurableToolMixin
from agio.tools.builtin.config import GlobConfig
from agio.utils.logging import get_logger


class GlobOutput(BaseModel):
    """GlobTool output result."""

    duration_ms: int
    num_files: int
    filenames: list[str]
    truncated: bool


class GlobTool(BaseTool, ConfigurableToolMixin):
    """File pattern matching tool."""

    def __init__(
        self,
        *,
        config: GlobConfig | None = None,
        project_root: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__()
        self._config = self._init_config(GlobConfig, config, **kwargs)
        self._logger = get_logger(__name__)
        self._project_root: Path = (project_root or Path.cwd()).resolve()
        self.current_dir = self._project_root.as_posix()
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._config.timeout_seconds

        # Configuration
        self.default_limit = 100
        self.default_offset = 0
        self.max_search_depth = self._config.max_search_depth
        self.max_path_length = self._config.max_path_length
        self.max_pattern_length = self._config.max_pattern_length

    def get_name(self) -> str:
        return "glob"

    def get_description(self) -> str:
        """Get tool prompt description."""
        return (
            "Fast file pattern matching tool for searching files "
            "matching specific patterns in codebase.\n\n"
            "Usage:\n"
            "- Supports standard glob patterns (e.g., `**/*.js`, `src/**/*.ts`)\n"
            "- Efficiently handles large codebases\n"
            "- Sorted by file modification time\n"
            "- Supports relative and absolute paths\n"
            "- Automatic working directory resolution\n"
            "- Path permission validation\n"
            "- Supports result count limits and pagination\n"
            "- Truncation status indication\n"
            "- Read-only operations, thread-safe\n"
            "- Path security checks\n"
            "- Permission validation mechanism"
        )

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files",
                },
                "path": {
                    "type": "string",
                    "description": "Path to search for files, default is current working directory",
                },
            },
            "required": ["pattern"],
        }

    def is_concurrency_safe(self) -> bool:
        """Whether tool supports concurrent execution."""
        return True

    def validate_input(self, pattern: str, path: str | None = None) -> dict[str, Any]:
        """Validate input parameters."""
        if not pattern or not isinstance(pattern, str):
            return {
                "valid": False,
                "message": "Pattern is required and must be a string",
            }

        # Validate pattern length
        if len(pattern) > self.max_pattern_length:
            return {
                "valid": False,
                "message": f"Pattern too long (max {self.max_pattern_length} characters)",
            }

        # Check for dangerous characters
        dangerous_chars = ["\0", "~"]
        if any(char in pattern for char in dangerous_chars):
            return {"valid": False, "message": "Pattern contains dangerous characters"}

        # Validate path
        if path and not isinstance(path, str):
            return {"valid": False, "message": "Path must be a string"}

        # Validate path length
        if path and len(path) > self.max_path_length:
            return {
                "valid": False,
                "message": f"Path too long (max {self.max_path_length} characters)",
            }

        return {"valid": True}

    def _resolve_path(self, path: str | None = None) -> Path:
        """Resolve search path."""
        if not path:
            return self._project_root

        candidate = Path(path)

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        return candidate.resolve()

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is allowed to access."""
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
        """Normalize glob pattern."""
        # Handle Windows path separators
        pattern = pattern.replace("\\", "/")

        # Ensure pattern ends with correct format
        if pattern.endswith("/"):
            pattern += "*"

        return pattern

    async def _glob_search(
        self, pattern: str, search_path: Path
    ) -> tuple[list[str], bool]:
        """Execute glob search."""
        try:
            # Use pathlib for glob search
            search_dir = search_path
            if not search_dir.exists():
                return [], False

            # Normalize pattern
            normalized_pattern = self._normalize_pattern(pattern)

            # Execute glob pattern matching
            matched_files = []

            # Handle different pattern types
            if normalized_pattern.startswith("**/"):
                # Recursive search: use rglob for **/ patterns
                # rglob(pattern) is equivalent to glob('**/' + pattern), but handles ** correctly
                sub_pattern = normalized_pattern[3:]  # Remove "**/" prefix
                for file_path in search_dir.rglob(sub_pattern):
                    if file_path.is_file():
                        matched_files.append(file_path)
            elif normalized_pattern.startswith("**"):
                # Handle standalone ** pattern (entire directory tree)
                for file_path in search_dir.rglob("*"):
                    if file_path.is_file():
                        matched_files.append(file_path)
            else:
                # Non-recursive search
                for file_path in search_dir.glob(normalized_pattern):
                    if file_path.is_file():
                        matched_files.append(file_path)

            # Sort by modification time
            sorted_files = self._sort_by_mtime(matched_files)

            # Apply pagination
            total_files = len(sorted_files)
            truncated = total_files > self.default_offset + self.default_limit

            result_files = sorted_files[
                self.default_offset : self.default_offset + self.default_limit
            ]

            formatted_results = [self._format_path(result) for result in result_files]

            return formatted_results, truncated

        except Exception:
            # Log error but don't raise exception
            self._logger.exception(
                "Glob search failed",
                extra={"pattern": pattern, "path": str(search_path)},
            )
            return [], False

    def _sort_by_mtime(self, files: list[Path]) -> list[Path]:
        """Sort files by modification time."""

        def get_mtime(file_path: str) -> float:
            try:
                return os.path.getmtime(file_path)
            except OSError:
                return 0.0

        # Sort by modification time, newest first
        return sorted(files, key=get_mtime, reverse=True)

    def _format_path(self, file_path: Path) -> str:
        try:
            return file_path.resolve().relative_to(self._project_root).as_posix()
        except ValueError:
            return file_path.resolve().as_posix()

    def _format_result_for_assistant(self, output: GlobOutput) -> str:
        """Format result for assistant."""
        if output.num_files == 0:
            return "No files found"

        # Join file paths
        result = "\n".join(output.filenames)

        # Add truncation notice
        if output.truncated:
            result += "\n(Results are truncated. Consider using a more specific path or pattern.)"

        return result

    def _format_result_for_user(self, output: GlobOutput) -> str:
        """Format result for user display."""
        file_word = "file" if output.num_files == 1 else "files"

        return f"Found {output.num_files} {file_word} in {output.duration_ms}ms"

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """Execute glob search."""
        start_time = time.time()
        pattern = parameters.get("pattern", "")
        path = parameters.get("path")

        try:
            # Check for abort signal
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Validate input
            validation = self.validate_input(pattern, path)
            if not validation["valid"]:
                return self._create_error_result(
                    parameters, validation["message"], start_time
                )

            # Resolve search path
            search_path = self._resolve_path(path)

            # Check path permissions
            if not self._is_path_allowed(search_path):
                return self._create_error_result(
                    parameters,
                    f"Path not allowed: {search_path.as_posix()}",
                    start_time,
                )

            # Check if path exists
            if not search_path.exists():
                return self._create_error_result(
                    parameters,
                    f"Directory not found: {search_path.as_posix()}",
                    start_time,
                )

            if not search_path.is_dir():
                return self._create_error_result(
                    parameters,
                    f"Path is not a directory: {search_path.as_posix()}",
                    start_time,
                )

            # Check abort signal again
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Execute glob search
            files, truncated = await self._glob_search(pattern, search_path)

            # Check abort signal after search
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            duration_ms = int((time.time() - start_time) * 1000)

            result_text = self._format_result_for_assistant(
                GlobOutput(
                    duration_ms=duration_ms,
                    num_files=len(files),
                    filenames=files,
                    truncated=truncated,
                )
            )

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
            return self._create_error_result(
                parameters, f"Glob search failed: {e!s}", start_time
            )
