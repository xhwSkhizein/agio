"""
FileEditTool - File editing tool.

Provides safe file editing capabilities with validation and diff generation.
"""

import difflib
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agio.domain import ToolResult
from agio.runtime.control import AbortSignal
from agio.runtime.context import ExecutionContext
from agio.tools.base import RiskLevel, ToolCategory
from agio.tools.builtin.common.configurable_tool import ConfigurableToolMixin
from agio.tools.builtin.common.file_operation_base import FileOperationBaseTool
from agio.tools.builtin.config import FileEditConfig
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class FileEditToolOutput(BaseModel):
    """File editing tool output."""

    file_path: str
    old_string: str
    new_string: str
    original_file: str
    structured_patch: list[str]


class FileEditTool(FileOperationBaseTool, ConfigurableToolMixin):
    """File editing tool."""

    def __init__(
        self,
        *,
        config: FileEditConfig | None = None,
        project_root: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(project_root=project_root)
        self._config = self._init_config(FileEditConfig, config, **kwargs)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.MEDIUM
        self.timeout_seconds = self._config.timeout_seconds

    def get_name(self) -> str:
        return "file_edit"

    def get_description(self) -> str:
        """Get tool prompt description."""
        return (
            "A file editing tool. For moving or renaming files, usually use the 'mv' command "
            "from Bash tool. For large edits, use Write tool to overwrite files. "
            "For Jupyter notebook (.ipynb files), use NotebookEditTool.\n\n"
            "Before using this tool:\n\n"
            "1. Use FileReadTool to understand file content and context\n\n"
            "2. Verify directory path is correct (only when creating new files):\n"
            "   - Use LSTool to verify parent directory exists and is in correct location\n\n"
            "To edit a file, provide:\n"
            "1. file_path: Absolute path of file to modify (must be absolute, not relative)\n"
            "2. old_string: Text to replace (must be unique in file and match exactly "
            "including all whitespace and indentation)\n"
            "3. new_string: Edit text to replace old_string\n\n"
            "The tool will replace one occurrence of old_string in the file with new_string.\n\n"
            "Key requirements:\n\n"
            "1. Uniqueness: old_string must uniquely identify the specific instance to change:\n"
            "   - Include at least 3-5 lines of context before the change point\n"
            "   - Include at least 3-5 lines of context after the change point\n"
            "   - Include all whitespace, indentation, and surrounding code exactly as shown "
            "in the file\n\n"
            "2. Single instance: This tool can only change one instance at a time:\n"
            "   - Call this tool separately for each instance\n"
            "   - Each call must use extensive context to uniquely identify its specific instance\n\n"
            "3. Verification: Before using this tool:\n"
            "   - Check how many instances of target text exist in the file\n"
            "   - If multiple instances exist, gather enough context to uniquely identify each\n"
            "   - Plan separate tool calls for each instance\n\n"
            "Warnings: If requirements are not followed:\n"
            "   - If old_string matches multiple locations, tool will fail\n"
            "   - If old_string doesn't match exactly (including whitespace), tool will fail\n"
            "   - Without enough context, may change wrong instance\n\n"
            "When editing:\n"
            "   - Ensure edit results are idiomatic, correct code\n"
            "   - Don't leave code in broken state\n"
            "   - Always use absolute file paths (starting with /)\n\n"
            "To create new file:\n"
            "   - New file path, include directory name if needed\n"
            "   - Empty old_string\n"
            "   - New file content as new_string\n\n"
            "Remember: When making multiple consecutive file edits to the same file, "
            "call this tool multiple times in a single message, not one call per message."
        )

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Absolute path of file to modify "
                        "(must be absolute path, not relative path)"
                    ),
                },
                "old_string": {
                    "type": "string",
                    "description": (
                        "Text to replace (must be unique in file and match exactly, "
                        "including all whitespace and indentation)"
                    ),
                },
                "new_string": {
                    "type": "string",
                    "description": "Edit text to replace old_string",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def is_concurrency_safe(self) -> bool:
        """Check if tool supports concurrency."""
        return False

    def validate_input(
        self, file_path: str, old_string: str, new_string: str
    ) -> dict[str, Any]:
        """Validate input parameters."""

        is_absolute, message = self._require_absolute_path(file_path)
        if not is_absolute:
            return {"valid": False, "message": message}

        # Check if there are actual changes
        if old_string == new_string:
            return {
                "valid": False,
                "message": "No changes to make: old_string and new_string are exactly the same.",
                "meta": {"old_string": old_string},
            }

        full_file_path = self._normalize_path(file_path)

        # Check file creation scenario
        if os.path.exists(full_file_path) and old_string == "":
            return {
                "valid": False,
                "message": "Cannot create new file - file already exists.",
            }

        # New file creation
        if not os.path.exists(full_file_path) and old_string == "":
            return {"valid": True}

        # File does not exist
        if not os.path.exists(full_file_path):
            # Try to find similar file
            similar_file = self._find_similar_file(full_file_path)
            message = "File does not exist."
            if similar_file:
                message += f" Did you mean {similar_file}?"
            return {"valid": False, "message": message}

        # Jupyter notebook check
        if full_file_path.endswith(".ipynb"):
            return {
                "valid": False,
                "message": (
                    "File is a Jupyter Notebook. "
                    "Use the NotebookEditTool to edit this file."
                ),
            }

        # Skip file read timestamp check (simplified implementation)

        # Check if string exists
        try:
            with open(full_file_path, encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            return {"valid": False, "message": f"Cannot read file: {e!s}"}

        if old_string not in file_content:
            return {
                "valid": False,
                "message": "String to replace not found in file.",
                "meta": {"isFilePathAbsolute": str(os.path.isabs(file_path))},
            }

        # Check uniqueness
        matches = file_content.count(old_string)
        if matches > 1:
            return {
                "valid": False,
                "message": (
                    f"Found {matches} matches of the string to replace. "
                    "For safety, this tool only supports replacing exactly "
                    "one occurrence at a time. Add more lines of context "
                    "to your edit and try again."
                ),
                "meta": {"isFilePathAbsolute": str(os.path.isabs(file_path))},
            }

        return {"valid": True}

    def _find_similar_file(self, file_path: str) -> str | None:
        """Find similar file."""
        try:
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]

            if os.path.exists(directory):
                for file in os.listdir(directory):
                    if file.startswith(name_without_ext) and file != filename:
                        return os.path.join(directory, file)
        except Exception:
            pass
        return None

    def _apply_edit(
        self, file_path: str, old_string: str, new_string: str
    ) -> dict[str, Any]:
        """Apply edit and generate patch."""
        full_file_path = self._normalize_path(file_path)

        # Read original file
        if os.path.exists(full_file_path):
            with open(full_file_path, encoding="utf-8") as f:
                original_content = f.read()
        else:
            original_content = ""

        # Apply replacement
        if old_string == "":
            # Create new file
            updated_content = new_string
        else:
            # Replace content
            updated_content = original_content.replace(old_string, new_string, 1)

        # Generate structured patch
        original_lines = original_content.splitlines(keepends=True)
        updated_lines = updated_content.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                original_lines,
                updated_lines,
                fromfile=f"a/{os.path.basename(file_path)}",
                tofile=f"b/{os.path.basename(file_path)}",
                lineterm="",
            )
        )

        return {
            "original_content": original_content,
            "updated_content": updated_content,
            "patch": diff,
        }

    def _get_snippet(
        self, original_content: str, old_string: str, new_string: str, n_lines: int = 4
    ) -> dict[str, Any]:
        """Get code snippet around the edit."""
        if not old_string:
            # New file creation
            lines = new_string.split("\n")
            return {"snippet": "\n".join(lines[: n_lines * 2 + 1]), "start_line": 1}

        before = original_content.split(old_string)[0]
        replacement_line = len(before.split("\n")) - 1
        new_file_lines = original_content.replace(old_string, new_string, 1).split("\n")

        start_line = max(0, replacement_line - n_lines)
        end_line = replacement_line + n_lines + len(new_string.split("\n"))

        snippet_lines = new_file_lines[start_line : end_line + 1]
        snippet = "\n".join(snippet_lines)

        return {"snippet": snippet, "start_line": start_line + 1}

    def _add_line_numbers(self, content: str, start_line: int = 1) -> str:
        """Add line numbers to content."""
        lines = content.split("\n")
        numbered_lines = []
        for i, line in enumerate(lines):
            line_num = start_line + i
            numbered_lines.append(f"{line_num:6d}\t{line}")
        return "\n".join(numbered_lines)

    async def execute(
        self,
        parameters: dict[str, Any],
        context: "ExecutionContext",
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """Execute file editing."""
        start_time = time.time()
        file_path = parameters.get("file_path")
        old_string = parameters.get("old_string")
        new_string = parameters.get("new_string")

        try:
            # Check abort signal
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Validate input
            validation = self.validate_input(file_path, old_string, new_string)
            if not validation["valid"]:
                result_text = validation["message"]
                if validation.get("meta", {}):
                    result_text += f"\n{validation.get('meta', {})}"
                return self._create_error_result(parameters, result_text, start_time)

            # Check abort signal again
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Apply edit
            edit_result = self._apply_edit(file_path, old_string, new_string)
            normalized_path = self._normalize_path(file_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(normalized_path), exist_ok=True)

            # Check abort signal before writing
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Write file
            Path(normalized_path).write_text(
                edit_result["updated_content"], encoding="utf-8"
            )

            snippet_info = self._get_snippet(
                edit_result["original_content"], old_string, new_string
            )

            result_for_assistant = (
                f"The file {file_path} has been updated. "
                "Here's the result of running `cat -n` on a snippet "
                f"of the edited file:\n"
                f"{self._add_line_numbers(snippet_info['snippet'], snippet_info['start_line'])}"
            )

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_for_assistant,
                output={
                    "file_path": file_path,
                    "old_string_length": len(old_string),
                    "new_string_length": len(new_string),
                    "patch_length": len(edit_result["patch"]),
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(
                parameters, f"File edit failed: {e!s}", start_time
            )

    def update_read_timestamp(self, file_path: str, timestamp: float | None = None):
        """Update file read timestamp (simplified implementation, no longer tracked)."""
        pass
