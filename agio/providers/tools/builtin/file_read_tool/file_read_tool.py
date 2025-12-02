"""
FileReadTool - 文件读取工具
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Union, TYPE_CHECKING

from pydantic import BaseModel

from agio.providers.tools.base import RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings
from agio.providers.tools.builtin.common.file_operation_base import FileOperationBaseTool
from agio.domain import ToolResult

if TYPE_CHECKING:
    from agio.runtime.control import AbortSignal

try:
    import io

    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None


class TextFileOutput(BaseModel):
    """文本文件输出"""

    type: str = "text"
    file: dict  # 包含 filePath, content, numLines, startLine, totalLines


class ImageFileOutput(BaseModel):
    """图片文件输出"""

    type: str = "image"
    file: dict  # 包含 base64, media_type


FileReadToolOutput = Union[TextFileOutput, ImageFileOutput]


class FileReadTool(FileOperationBaseTool):
    """文件读取工具"""

    # 支持的图片扩展名
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

    # 从配置中获取最大输出大小限制
    @property
    def max_output_size(self) -> int:
        return int(self._settings.tool.file_read_max_output_size_mb * 1024 * 1024)

    @property
    def max_image_size(self) -> int:
        return int(self._settings.tool.file_read_max_image_size_mb * 1024 * 1024)

    @property
    def max_width(self) -> int:
        return self._settings.tool.file_read_max_image_width

    @property
    def max_height(self) -> int:
        return self._settings.tool.file_read_max_image_height

    def __init__(self, *, settings: AppSettings | None = None):
        super().__init__(settings=settings)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.LOW
        self.timeout_seconds = self._settings.tool.file_read_tool_timeout_seconds

    def get_name(self) -> str:
        return "file_read"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """根据指定行号读取指定绝对路径文件的内容。当想快速了解代码文件内容时优先使用 CodeReadTool 读取代码结构, 如需读取具体代码实现, 在读取代码文件结构信息后根据行号读取代码细节。

使用说明: 
- file_path 参数必须是绝对路径, 不是相对路径
- 对于大文件, 可以选择指定行偏移量和限制
- 超过 2000 字符的行将被截断
- 文本文件以 cat -n 格式返回, 带有 1 索引行号
- 图片文件自动以可视化方式呈现
- 您可以在单个响应中调用多个工具进行批量读取

如果您读取存在但内容为空的文件, 将收到系统提醒警告。
"""
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
        """是否支持并发"""
        return True


    def validate_input(
        self, file_path: str, offset: int | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """验证输入参数"""
        is_absolute, message = self._require_absolute_path(file_path)
        if not is_absolute:
            return {"valid": False, "message": message}

        full_file_path = self._normalize_path(file_path)

        if not os.path.exists(full_file_path):
            # 尝试查找类似文件
            similar_file = self._find_similar_file(full_file_path)
            message = "File does not exist."
            if similar_file:
                message += f" Did you mean {similar_file}?"
            return {"valid": False, "message": message}

        # 获取文件统计信息检查大小
        try:
            stat = os.stat(full_file_path)
            file_size = stat.st_size
            ext = Path(full_file_path).suffix.lower()

            # 跳过图片文件的大小检查 - 它们有自己的大小限制
            if ext not in self.IMAGE_EXTENSIONS:
                # 如果文件太大且没有提供 offset/limit
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
        """查找类似的文件"""
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
        """格式化文件大小错误消息"""
        return f"File content ({round(size_in_bytes / 1024)}KB) exceeds maximum allowed size ({round(self.max_output_size / 1024)}KB). Please use offset and limit parameters to read specific portions of the file, or use the GrepTool to search for specific content."

    def _read_text_content(
        self, file_path: str, line_offset: int = 0, limit: int | None = None
    ) -> dict[str, Any]:
        """读取文本文件内容"""
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # 应用偏移和限制
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
            # 尝试其他编码
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
        """读取图片文件内容"""
        try:
            with open(file_path, "rb") as f:
                image_data = f.read()

            # 获取文件扩展名
            ext = Path(file_path).suffix.lower()

            # 检查原始文件大小
            if len(image_data) <= self.max_image_size:
                # 尝试用 PIL 检查图片尺寸
                if PIL_AVAILABLE:
                    try:
                        with Image.open(io.BytesIO(image_data)) as img:
                            width, height = img.size
                            if width <= self.max_width and height <= self.max_height:
                                # 图片符合所有要求, 直接返回
                                return {
                                    "base64": base64.b64encode(image_data).decode(
                                        "utf-8"
                                    ),
                                    "media_type": (
                                        f"image/{ext[1:]}"
                                        if ext != ".jpg"
                                        else "image/jpeg"
                                    ),
                                }
                    except Exception:
                        # 如果无法用 PIL 处理, 直接返回原始数据
                        return {
                            "base64": base64.b64encode(image_data).decode("utf-8"),
                            "media_type": (
                                f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg"
                            ),
                        }
                else:
                    # PIL 不可用, 直接返回原始数据
                    return {
                        "base64": base64.b64encode(image_data).decode("utf-8"),
                        "media_type": (
                            f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg"
                        ),
                    }

            # 需要调整大小或压缩
            if PIL_AVAILABLE:
                return self._resize_image(image_data, ext)
            else:
                # PIL 不可用, 返回原始数据
                return {
                    "base64": base64.b64encode(image_data).decode("utf-8"),
                    "media_type": f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg",
                }

        except Exception as e:
            raise Exception(f"Error reading image file: {e!s}")

    def _resize_image(self, image_data: bytes, ext: str) -> dict[str, Any]:
        """调整图片大小"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                width, height = img.size

                # 计算新尺寸保持宽高比
                if width > self.max_width:
                    height = int((height * self.max_width) / width)
                    width = self.max_width

                if height > self.max_height:
                    width = int((width * self.max_height) / height)
                    height = self.max_height

                # 调整大小
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)

                # 保存到字节流
                output = io.BytesIO()
                format_name = "JPEG" if ext in [".jpg", ".jpeg"] else ext[1:].upper()

                if format_name == "JPEG":
                    resized_img = resized_img.convert("RGB")

                resized_img.save(output, format=format_name, quality=85)
                resized_data = output.getvalue()

                # 如果仍然太大, 进一步压缩
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
            # 如果处理失败, 返回原始图片
            return {
                "base64": base64.b64encode(image_data).decode("utf-8"),
                "media_type": f"image/{ext[1:]}" if ext != ".jpg" else "image/jpeg",
            }

    def _add_line_numbers(self, content: str, start_line: int = 1) -> str:
        """添加行号"""
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
        abort_signal: "AbortSignal | None" = None,
    ) -> ToolResult:
        """执行文件读取"""
        start_time = time.time()
        file_path = parameters.get("file_path")
        offset = parameters.get("offset", 1)
        limit = parameters.get("limit")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self.validate_input(file_path, offset, limit)
            if not validation["valid"]:
                result_text = validation["message"]
                if validation.get("meta", {}):
                    result_text += f"\n{validation.get('meta', {})}"
                return self._create_error_result(parameters, result_text, start_time)

            full_file_path = os.path.abspath(file_path)
            ext = Path(full_file_path).suffix.lower()

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 检查是否是图片文件
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

            # 处理文本文件
            line_offset = 0 if offset == 0 else offset - 1
            text_data = self._read_text_content(full_file_path, line_offset, limit)

            # 检查内容大小
            if len(text_data["content"]) > self.max_output_size:
                text_error = self._format_file_size_error(len(text_data["content"]))
                return self._create_error_result(parameters, text_error, start_time)

            # 检查中断（在读取大文件后）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 生成带行号的结果
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
        """获取文件读取时间戳"""
        # Disabled in agio
        return None
