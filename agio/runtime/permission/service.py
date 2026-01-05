"""
PermissionService - Permission policy service.

Generates permission decisions based on tool configuration and context.
"""

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel

from agio.config import ConfigSystem, get_config_system
from agio.runtime.protocol import ExecutionContext
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class PermissionDecision(BaseModel):
    """Permission decision result"""

    decision: Literal["allowed", "denied", "requires_consent"]
    reason: str
    suggested_patterns: list[str] | None = None  # Suggested patterns
    expires_at_hint: datetime | None = None  # Suggested expiration time


class PermissionService:
    """
    Permission policy service.

    Generates permission decisions based on tool configuration and context.
    """

    def __init__(self, config_system: ConfigSystem | None = None) -> None:
        """
        Initialize permission service.

        Args:
            config_system: ConfigSystem instance (default: get from global)
        """
        self.config_system = config_system or get_config_system()

    async def check_permission(
        self,
        user_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        context: ExecutionContext,
    ) -> PermissionDecision:
        """
        Check tool execution permission.

        Decision logic:
        1. If tool config requires_consent=False → allowed
        2. If tool config requires_consent=True → requires_consent
        3. Agent can override default policy (e.g., read-only tool set)

        Args:
            user_id: User identifier
            tool_name: Tool name
            tool_args: Tool arguments
            context: Execution context

        Returns:
            PermissionDecision: Permission decision
        """
        # Get tool configuration
        tool_config = self._get_tool_config(tool_name)

        if not tool_config:
            # Tool not found in config, default to requires_consent
            return PermissionDecision(
                decision="requires_consent",
                reason=f"Tool {tool_name} configuration not found",
                suggested_patterns=self._generate_suggested_patterns(
                    tool_name, tool_args
                ),
            )

        requires_consent = tool_config.get("requires_consent", False)

        if not requires_consent:
            return PermissionDecision(
                decision="allowed",
                reason="Tool does not require consent",
            )

        # Tool requires consent
        return PermissionDecision(
            decision="requires_consent",
            reason="Tool requires user consent",
            suggested_patterns=self._generate_suggested_patterns(tool_name, tool_args),
            expires_at_hint=datetime.now() + timedelta(days=30),  # Default: 30 days
        )

    def _get_tool_config(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get tool configuration from ConfigSystem.

        Args:
            tool_name: Tool name

        Returns:
            Tool configuration dict or None if not found
        """
        try:
            # Try to get tool instance from ConfigSystem
            tool_instance = self.config_system.get_or_none(tool_name)
            if tool_instance:
                # If we have the instance, try to get config
                configs = self.config_system.list_configs("tool")
                for config_doc in configs:
                    config = config_doc.get("config", {})
                    if config.get("name") == tool_name:
                        return config

            # Fallback: search configs directly
            from agio.config import ComponentType

            configs = self.config_system.list_configs(ComponentType.TOOL)
            for config in configs:
                if (
                    config.get("name") == tool_name
                    or config.get("tool_name") == tool_name
                ):
                    return config

            return None

        except Exception as e:
            logger.warning(
                "get_tool_config_failed",
                tool_name=tool_name,
                error=str(e),
            )
            return None

    def _generate_suggested_patterns(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> list[str]:
        """
        Generate suggested patterns for user consent.

        Args:
            tool_name: Tool name
            tool_args: Tool arguments

        Returns:
            List of suggested patterns
        """
        patterns = []

        # Generate pattern based on tool type
        if tool_name == "bash":
            # For bash, suggest pattern based on command
            command = tool_args.get("command", "")
            if command:
                # Exact match pattern
                patterns.append(f"bash({command})")
                # If command contains common patterns, suggest wildcard
                if "run" in command.lower():
                    # Suggest pattern for npm/yarn run commands
                    parts = command.split()
                    if len(parts) >= 2:
                        base_cmd = " ".join(parts[:2])
                        patterns.append(f"bash({base_cmd} *)")

        elif tool_name in ["file_read", "file_edit", "file_write"]:
            # For file operations, suggest pattern based on file path
            path = tool_args.get("path") or tool_args.get("file_path")
            if path:
                patterns.append(f"{tool_name}({path})")
                # Suggest parent directory pattern
                if "/" in path:
                    parent = "/".join(path.split("/")[:-1])
                    if parent:
                        patterns.append(f"{tool_name}({parent}/*)")

        else:
            # Generic pattern: exact match
            args_str = self._serialize_args(tool_args)
            if args_str:
                patterns.append(f"{tool_name}({args_str})")

        return patterns[:3]  # Limit to 3 suggestions

    def _serialize_args(self, args: dict[str, Any]) -> str:
        """Serialize arguments to string for pattern generation"""
        items = sorted([(k, v) for k, v in args.items() if k != "tool_call_id"])
        return " ".join(f"{k}={v}" for k, v in items)


__all__ = ["PermissionService", "PermissionDecision"]
