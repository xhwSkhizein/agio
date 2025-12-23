"""
FileEditTool - 文件编辑工具
"""

import difflib
import os
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

from agio.domain import ToolResult
from agio.providers.tools.base import RiskLevel, ToolCategory
from agio.providers.tools.builtin.adapter import AppSettings
from agio.providers.tools.builtin.common.file_operation_base import FileOperationBaseTool
from agio.utils.logging import get_logger

if TYPE_CHECKING:
    from agio.agent.control import AbortSignal

logger = get_logger(__name__)


class FileEditToolOutput(BaseModel):
    """文件编辑工具输出"""

    file_path: str
    old_string: str
    new_string: str
    original_file: str
    structured_patch: list[str]


class FileEditTool(FileOperationBaseTool):
    """文件编辑工具"""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        super().__init__(settings=settings)
        self.category = ToolCategory.FILE_OPS
        self.risk_level = RiskLevel.MEDIUM
        self.timeout_seconds = self._settings.tool.file_edit_tool_timeout_seconds

    def get_name(self) -> str:
        return "file_edit"

    def get_description(self) -> str:
        """获取工具的 Prompt 描述"""
        return """这是一个文件编辑工具。对于移动或重命名文件, 通常应该使用 Bash 工具的 'mv' 命令。对于大型编辑, 使用 Write 工具覆盖文件。对于 Jupyter notebook (.ipynb 文件), 使用 NotebookEditTool。

使用此工具前: 

1. 使用 FileReadTool 工具了解文件内容和上下文

2. 验证目录路径正确(仅在创建新文件时适用): 
   - 使用 LSTool 工具验证父目录存在且位置正确

要进行文件编辑, 请提供以下内容: 
1. file_path: 要修改的文件的绝对路径(必须是绝对路径, 不是相对路径)
2. old_string: 要替换的文本(必须在文件中唯一, 且必须与文件内容完全匹配, 包括所有空白和缩进)
3. new_string: 用于替换 old_string 的编辑文本

工具将用 new_string 替换文件中 old_string 的一个出现。

使用此工具的关键要求: 

1. 唯一性: old_string 必须唯一标识您要更改的特定实例。这意味着: 
   - 在更改点前包含至少 3-5 行上下文
   - 在更改点后包含至少 3-5 行上下文
   - 包含所有空白、缩进和周围代码, 与文件中显示的完全一致

2. 单实例: 此工具一次只能更改一个实例。如果需要更改多个实例: 
   - 为每个实例单独调用此工具
   - 每次调用必须使用大量上下文唯一标识其特定实例

3. 验证: 使用此工具前: 
   - 检查文件中目标文本存在多少个实例
   - 如果存在多个实例, 收集足够的上下文来唯一标识每一个
   - 为每个实例规划单独的工具调用

警告: 如果不遵循这些要求: 
   - 如果 old_string 匹配多个位置, 工具将失败
   - 如果 old_string 不完全匹配(包括空白), 工具将失败
   - 如果没有包含足够的上下文, 可能会更改错误的实例

进行编辑时: 
   - 确保编辑结果是惯用的、正确的代码
   - 不要让代码处于损坏状态
   - 始终使用绝对文件路径(以 / 开头)

如果要创建新文件, 使用: 
   - 新文件路径, 如需要包括目录名
   - 空的 old_string
   - 新文件内容作为 new_string

记住: 对同一文件连续进行多次文件编辑时, 应该在单个消息中多次调用此工具, 而不是每次调用一个消息。
"""

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要修改的文件的绝对路径(必须是绝对路径, 不是相对路径)",
                },
                "old_string": {
                    "type": "string",
                    "description": "要替换的文本(必须在文件中唯一, 且必须与文件内容完全匹配, 包括所有空白和缩进)",
                },
                "new_string": {
                    "type": "string",
                    "description": "用于替换 old_string 的编辑文本",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def is_concurrency_safe(self) -> bool:
        """是否支持并发"""
        return False

    def validate_input(
        self, file_path: str, old_string: str, new_string: str
    ) -> dict[str, Any]:
        """验证输入参数"""

        is_absolute, message = self._require_absolute_path(file_path)
        if not is_absolute:
            return {"valid": False, "message": message}

        # 检查是否有实际变更
        if old_string == new_string:
            return {
                "valid": False,
                "message": "No changes to make: old_string and new_string are exactly the same.",
                "meta": {"old_string": old_string},
            }

        full_file_path = self._normalize_path(file_path)

        # 检查文件创建情况
        if os.path.exists(full_file_path) and old_string == "":
            return {
                "valid": False,
                "message": "Cannot create new file - file already exists.",
            }

        # 新文件创建
        if not os.path.exists(full_file_path) and old_string == "":
            return {"valid": True}

        # 文件不存在
        if not os.path.exists(full_file_path):
            # 尝试查找类似文件
            similar_file = self._find_similar_file(full_file_path)
            message = "File does not exist."
            if similar_file:
                message += f" Did you mean {similar_file}?"
            return {"valid": False, "message": message}

        # Jupyter notebook 检查
        if full_file_path.endswith(".ipynb"):
            return {
                "valid": False,
                "message": "File is a Jupyter Notebook. Use the NotebookEditTool to edit this file.",
            }

        # 跳过文件读取时间戳检查（简化实现）

        # 检查字符串是否存在
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

        # 检查唯一性
        matches = file_content.count(old_string)
        if matches > 1:
            return {
                "valid": False,
                "message": f"Found {matches} matches of the string to replace. For safety, this tool only supports replacing exactly one occurrence at a time. Add more lines of context to your edit and try again.",
                "meta": {"isFilePathAbsolute": str(os.path.isabs(file_path))},
            }

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

    def _apply_edit(
        self, file_path: str, old_string: str, new_string: str
    ) -> dict[str, Any]:
        """应用编辑并生成补丁"""
        full_file_path = self._normalize_path(file_path)

        # 读取原始文件
        if os.path.exists(full_file_path):
            with open(full_file_path, encoding="utf-8") as f:
                original_content = f.read()
        else:
            original_content = ""

        # 应用替换
        if old_string == "":
            # 创建新文件
            updated_content = new_string
        else:
            # 替换内容
            updated_content = original_content.replace(old_string, new_string, 1)

        # 生成结构化补丁
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
        """获取编辑周围的代码片段"""
        if not old_string:
            # 新文件创建
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
        """添加行号"""
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
        """执行文件编辑"""
        start_time = time.time()
        file_path = parameters.get("file_path")
        old_string = parameters.get("old_string")
        new_string = parameters.get("new_string")

        try:
            # 检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 验证输入
            validation = self.validate_input(file_path, old_string, new_string)
            if not validation["valid"]:
                result_text = validation["message"]
                if validation.get("meta", {}):
                    result_text += f"\n{validation.get('meta', {})}"
                return self._create_error_result(parameters, result_text, start_time)

            # 再次检查中断
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 应用编辑
            edit_result = self._apply_edit(file_path, old_string, new_string)
            normalized_path = self._normalize_path(file_path)

            # 确保目录存在
            os.makedirs(os.path.dirname(normalized_path), exist_ok=True)

            # 检查中断（在写入前）
            if abort_signal and abort_signal.is_aborted():
                return self._create_abort_result(parameters, start_time)

            # 写入文件
            Path(normalized_path).write_text(edit_result["updated_content"], encoding="utf-8")

            snippet_info = self._get_snippet(
                edit_result["original_content"], old_string, new_string
            )

            result_for_assistant = (
                f"The file {file_path} has been updated. Here's the result of running `cat -n` on a snippet "
                f"of the edited file:\n{self._add_line_numbers(snippet_info['snippet'], snippet_info['start_line'])}"
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
            return self._create_error_result(parameters, f"File edit failed: {e!s}", start_time)

    def update_read_timestamp(self, file_path: str, timestamp: float | None = None):
        """更新文件读取时间戳（简化实现，不再追踪）"""
        pass
