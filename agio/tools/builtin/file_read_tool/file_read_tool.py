"""
FileReadTool - File reading tool.
"""

import base64
import json
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
from agio.tools.builtin.config import FileReadConfig

try:
    import io

    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None


class TextFileOutput(BaseModel):
    """Text file output."""

    type: str = "text"
    file: dict  # Contains filePath, content, numLines, startLine, totalLines


class ImageFileOutput(BaseModel):
    """Image file output."""

    type: str = "image"
    file: dict  # Contains base64, media_type


FileReadToolOutput = TextFileOutput | ImageFileOutput


class FileReadTool(FileOperationBaseTool, ConfigurableToolMixin):
    """File reading tool."""

    # Supported image extensions
    IMAGE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".svg",
        ".tiff",
        ".ico",
        ".heic",
        ".heif",
    }

    # Get maximum output size limit from config
    @property
    def max_output_size(self) -> int:
        return int(self._config.max_output_size_mb * 1024 * 1024)

    @property
    def max_image_size(self) -> int:
        return int(self._config.max_image_size_mb * 1024 * 1024)

    @property
    def max_width(self) -> int:
        return self._config.max_image_width

    @property
    def max_height(self) -> int:
        return self._config.max_image_height

    def __init__(
        self,
        *,
        config: FileReadConfig | None = None,
        project_root: Path | None = None,
        **kwargs,
    ):
        super().__init__(project_root=project_root)
        self._config = self._init_config(FileReadConfig, config, **kwargs)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._config.timeout_seconds

    def get_name(self) -> str:
        return "file_read"

    def get_description(self) -> str:
        """Get tool prompt description."""
        return (
            "Read file content by line numbers from absolute path. "
            "For quick code overview, use CodeReadTool to read code structure first. "
            "For specific implementation details, read code details by line numbers "
            "after reading code structure information.\n\n"
            "Usage:\n"
            "- file_path parameter must be absolute path, not relative path\n"
            "- For large files, you can specify line offset and limit\n"
            "- Lines exceeding 2000 characters will be truncated\n"
            "- Text files are returned in cat -n format with 1-indexed line numbers\n"
            "- Image files are automatically displayed visually\n"
            "- You can call multiple tools in a single response for batch reading\n\n"
            "If you read a file that exists but has empty content, "
            "you will receive a system warning."
        )

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件绝对路径"},
                "offset": {
                    "type": "integer",
                    "description": "起始行号",
                    "default": 1,
                },
                "limit": {"type": "integer", "description": "读取行数"},
            },
            "required": ["file_path", "offset", "limit"],
        }

    def is_concurrency_safe(self) -> bool:
        """Whether tool supports concurrent execution."""
        return True

    def validate_input(
        self, file_path: str, offset: int | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Validate input parameters."""
        is_absolute, message = self._require_absolute_path(file_path)
        if not is_absolute:
            return {"valid": False, "message": message}

        full_file_path = self._normalize_path(file_path)

        if not os.path.exists(full_file_path):
            # Try to find similar file
            similar_file = self._find_similar_file(full_file_path)
            message = "File does not exist."
            if similar_file:
                message += f" Did you mean {similar_file}?"
            return {"valid": False, "message": message}

        # Get file statistics to check size
        try:
            stat = os.stat(full_file_path)
            file_size = stat.st_size
            ext = Path(full_file_path).suffix.lower()

            # Skip size check for image files - they have their own size limits
            if ext not in self.IMAGE_EXTENSIONS:
                # If file is too large and no offset/limit provided
                if file_size > self.max_output_size and not offset and not limit:
                    return {
                        "valid": False,
                        "message": self._format_file_size_error(file_size),
                        "meta": {"fileSize": file_size},
                    }
        except OSError as e:
            return {"valid": False, "message": f"Cannot access file: {e!s}"}

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

    def _format_file_size_error(self, size_in_bytes: int) -> str:
        """Format file size error message."""
        size_kb = round(size_in_bytes / 1024)
        max_kb = round(self.max_output_size / 1024)
        return (
            f"File content ({size_kb}KB) exceeds maximum allowed size ({max_kb}KB). "
            "Please use offset and limit parameters to read specific portions of the file, "
            "or use the GrepTool to search for specific content."
        )

    def _read_text_content(
        self, file_path: str, line_offset: int = 0, limit: int | None = None
    ) -> dict[str, Any]:
        """Read text file content."""
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Apply offset and limit
            if line_offset > 0:
                lines = lines[line_offset:]

            if limit is not None:
                lines = lines[:limit]

            content = "".join(lines).rstrip("\n")
            line_count = len(lines)

            return {
                "content": content,
                "line_count": line_count,
                "total_lines": total_lines,
            }

        except UnicodeDecodeError:
            # Try other encodings
            try:
                with open(file_path, encoding="latin-1") as f:
                    lines = f.readlines()

                total_lines = len(lines)
                if line_offset > 0:
                    lines = lines[line_offset:]
                if limit is not None:
                    lines = lines[:limit]

                content = "".join(lines).rstrip("\n")
                line_count = len(lines)

                return {
                    "content": content,
                    "line_count": line_count,
                    "total_lines": total_lines,
                }
            except Exception as e:
                raise Exception(f"Cannot read file with any encoding: {e!s}")

        except Exception as e:
            raise Exception(f"Error reading file: {e!s}")

    def _read_image_content(self, file_path: str) -> dict[str, Any]:
        """Read image file content."""
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()

            # Get file extension
            ext = Path(file_path).suffix.lower()

            # Check original file size
            if len(image_data) <= self.max_image_size:
                # Try to check image dimensions with PIL
                if PIL_AVAILABLE:
                    try:
                        with Image.open(io.BytesIO(image_data)) as img:
                            width, height = img.size
                            if width <= self.max_width and height <= self.max_height:
                                # Image meets all requirements, return directly
                                return {
                                    "base64": base64.b64encode(image_data).decode("utf-8"),
                                    "media_type": (
                                        f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg"
                                    ),
                                }
                    except Exception:
                        # If PIL cannot process, return raw data
                        return {
                            "base64": base64.b64encode(image_data).decode("utf-8"),
                            "media_type": (f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg"),
                        }
                else:
                    # PIL not available, return raw data
                    return {
                        "base64": base64.b64encode(image_data).decode("utf-8"),
                        "media_type": (f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg"),
                    }

            # Need to resize or compress
            if PIL_AVAILABLE:
                return self._resize_image(image_data, ext)
            else:
                # PIL not available, return raw data
                return {
                    "base64": base64.b64encode(image_data).decode("utf-8"),
                    "media_type": f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg",
                }

        except Exception as e:
            raise Exception(f"Error reading image file: {e!s}")

    def _resize_image(self, image_data: bytes, ext: str) -> dict[str, Any]:
        """Resize image."""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                width, height = img.size

                # Calculate new size maintaining aspect ratio
                if width > self.max_width:
                    height = int((height * self.max_width) / width)
                    width = self.max_width

                if height > self.max_height:
                    width = int((width * self.max_height) / height)
                    height = self.max_height

                # Resize
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)

                # Save to byte stream
                output = io.BytesIO()
                format_name = "JPEG" if ext in [".jpg", ".jpeg"] else ext[1:].upper()

                if format_name == "JPEG":
                    resized_img = resized_img.convert("RGB")

                resized_img.save(output, format=format_name, quality=85)
                resized_data = output.getvalue()

                # If still too large, compress further
                if len(resized_data) > self.max_image_size:
                    output = io.BytesIO()
                    resized_img.save(output, format="JPEG", quality=60)
                    resized_data = output.getvalue()
                    format_name = "JPEG"

                return {
                    "base64": base64.b64encode(resized_data).decode("utf-8"),
                    "media_type": f"image/{format_name.lower()}",
                }

        except Exception:
            # If processing fails, return original image
            return {
                "base64": base64.b64encode(image_data).decode("utf-8"),
                "media_type": f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg",
            }

    def _add_line_numbers(self, content: str, start_line: int = 1) -> str:
        """Add line numbers."""
        if not content or len(content) == 0 or len(content.strip()) == 0:
            return "(Notice from FileReadTool)\nWARNING: File content is empty. "

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
        """Execute file reading."""
        start_time = time.time()
        file_path = parameters.get("file_path")
        offset = parameters.get("offset", 1)
        limit = parameters.get("limit")

        try:
            # Check abort signal
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Validate input
            validation = self.validate_input(file_path, offset, limit)
            if not validation["valid"]:
                result_text = validation["message"]
                if validation.get("meta", {}):
                    result_text += f"\n{validation.get('meta', {})}"
                return self._create_error_result(parameters, result_text, start_time)

            full_file_path = os.path.abspath(file_path)
            ext = Path(full_file_path).suffix.lower()

            # Check abort signal again
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Check if it's an image file
            if ext in self.IMAGE_EXTENSIONS:
                image_data = self._read_image_content(full_file_path)
                output = {"type": "image", "file": image_data}
                result_text = f"{json.dumps(output, ensure_ascii=False)}"

                return ToolResult(
                    tool_name=self.name,
                    tool_call_id=parameters.get("tool_call_id", ""),
                    input_args=parameters,
                    content=result_text,
                    output=output,
                    start_time=start_time,
                    end_time=time.time(),
                    duration=time.time() - start_time,
                    is_success=True,
                )

            # Process text file
            line_offset = 0 if offset == 0 else offset - 1
            text_data = self._read_text_content(full_file_path, line_offset, limit)

            # Check content size
            if len(text_data["content"]) > self.max_output_size:
                text_error = self._format_file_size_error(len(text_data["content"]))
                return self._create_error_result(parameters, text_error, start_time)

            # Check abort signal (after reading large file)
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # Generate result with line numbers
            result_for_assistant = self._add_line_numbers(text_data["content"], offset)

            return ToolResult(
                tool_name=self.name,
                tool_call_id=parameters.get("tool_call_id", ""),
                input_args=parameters,
                content=result_for_assistant,
                output={
                    "type": "text",
                    "file_path": file_path,
                    "content": text_data["content"],
                    "num_lines": text_data["line_count"],
                    "start_line": offset,
                    "total_lines": text_data["total_lines"],
                },
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time,
                is_success=True,
            )

        except Exception as e:
            return self._create_error_result(parameters, f"File read failed: {e!s}", start_time)

    def get_read_timestamp(self, file_path: str) -> float | None:
        """Get file read timestamp."""
        # Disabled in agio
        return None
