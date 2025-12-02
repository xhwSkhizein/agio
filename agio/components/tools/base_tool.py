"""Base abstractions for tools within the agio stack."""

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from agio.execution.abort_signal import AbortSignal
    from agio.core.events import ToolResult


class RiskLevel(str, Enum):
    """Tool risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolCategory(str, Enum):
    """Tool category classification."""

    FILE_OPS = "file_ops"
    ANALYSIS = "analysis"
    WEB = "web"
    SYSTEM = "system"
    MEMORY = "memory"
    OTHER = "other"


class ToolDefinition(BaseModel):
    """Tool definition for LLM-facing registration."""

    name: str
    description: str
    parameters: dict[str, Any]
    category: ToolCategory | None = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    is_concurrency_safe: bool = True
    timeout_seconds: int = 30


class BaseTool(ABC):
    """Common interface that every concrete tool must implement."""

    def __init__(self) -> None:
        self.name = self.get_name()
        self.description = self.get_description()

    @abstractmethod
    def get_name(self) -> str:
        """Return the tool name."""

    @abstractmethod
    def get_description(self) -> str:
        """Return the tool description used for prompting."""

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        """Return the JSON schema describing `execute` parameters."""

    @abstractmethod
    def is_concurrency_safe(self) -> bool:
        """Whether the tool can be executed concurrently."""

    @abstractmethod
    async def execute(
        self,
        parameters: dict[str, Any],
        abort_signal: "AbortSignal | None" = None,
    ) -> "ToolResult":
        """
        Execute the tool and return ToolResult directly.
        
        Args:
            parameters: Tool parameters
            abort_signal: Optional abort signal for cancellation
            
        Returns:
            ToolResult: Tool execution result from agio.core.events
        """

    def get_definition(self) -> ToolDefinition:
        """Construct a `ToolDefinition` for LLM-facing registration."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.get_parameters(),
            category=getattr(self, "category", None),
            risk_level=getattr(self, "risk_level", RiskLevel.MEDIUM),
            is_concurrency_safe=self.is_concurrency_safe(),
            timeout_seconds=getattr(self, "timeout_seconds", 30),
        )

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters(),
            },
        }
    
    def _create_error_result(
        self,
        parameters: dict,
        error: str,
        start_time: float,
    ) -> "ToolResult":
        """
        创建错误结果的辅助方法。
        
        Args:
            parameters: 工具参数
            error: 错误信息
            start_time: 开始时间
            
        Returns:
            ToolResult: 错误结果
        """
        from agio.core.events import ToolResult
        
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content=f"Error: {error}",
            output=None,
            error=error,
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            is_success=False,
        )
    
    def _create_abort_result(
        self,
        parameters: dict,
        start_time: float,
    ) -> "ToolResult":
        """
        创建中断结果的辅助方法。
        
        Args:
            parameters: 工具参数
            start_time: 开始时间
            
        Returns:
            ToolResult: 中断结果
        """
        from agio.core.events import ToolResult
        
        return ToolResult(
            tool_name=self.name,
            tool_call_id=parameters.get("tool_call_id", ""),
            input_args=parameters,
            content="Operation was aborted",
            output=None,
            error="Aborted",
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            is_success=False,
        )
