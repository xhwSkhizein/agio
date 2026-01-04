"""
Tool configuration classes for builtin tools.

All configuration classes support:
1. Constructor parameters (highest priority)
2. Environment variables (fallback)
3. Default values (lowest priority)
"""

import os
from dataclasses import dataclass, field
from typing import Any


def _get_env_float(key: str, default: str) -> float:
    """Get float from environment variable."""
    return float(os.getenv(key, default))


def _get_env_int(key: str, default: str) -> int:
    """Get int from environment variable."""
    return int(os.getenv(key, default))


def _get_env_bool(key: str, default: str) -> bool:
    """Get bool from environment variable."""
    return os.getenv(key, default).lower() == "true"


def _get_env_str(key: str, default: str) -> str:
    """Get string from environment variable."""
    return os.getenv(key, default)


@dataclass
class FileReadConfig:
    """Configuration for FileReadTool."""

    max_output_size_mb: float = field(
        default_factory=lambda: _get_env_float("AGIO_FILE_READ_MAX_SIZE_MB", "10.0")
    )
    max_image_size_mb: float = field(
        default_factory=lambda: _get_env_float("AGIO_FILE_READ_MAX_IMAGE_SIZE_MB", "5.0")
    )
    max_image_width: int = field(
        default_factory=lambda: _get_env_int("AGIO_FILE_READ_MAX_IMAGE_WIDTH", "1920")
    )
    max_image_height: int = field(
        default_factory=lambda: _get_env_int("AGIO_FILE_READ_MAX_IMAGE_HEIGHT", "1080")
    )
    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("AGIO_FILE_READ_TIMEOUT", "30")
    )


@dataclass
class FileWriteConfig:
    """Configuration for FileWriteTool."""

    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("AGIO_FILE_WRITE_TIMEOUT", "30")
    )
    max_file_size_mb: float = field(
        default_factory=lambda: _get_env_float("AGIO_FILE_WRITE_MAX_SIZE_MB", "10.0")
    )


@dataclass
class FileEditConfig:
    """Configuration for FileEditTool."""

    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("AGIO_FILE_EDIT_TIMEOUT", "60")
    )


@dataclass
class GrepConfig:
    """Configuration for GrepTool."""

    timeout_seconds: int = field(default_factory=lambda: _get_env_int("AGIO_GREP_TIMEOUT", "30"))
    max_results: int = field(default_factory=lambda: _get_env_int("AGIO_GREP_MAX_RESULTS", "1000"))


@dataclass
class GlobConfig:
    """Configuration for GlobTool."""

    timeout_seconds: int = field(default_factory=lambda: _get_env_int("AGIO_GLOB_TIMEOUT", "30"))
    max_results: int = field(default_factory=lambda: _get_env_int("AGIO_GLOB_MAX_RESULTS", "1000"))
    max_search_depth: int = field(
        default_factory=lambda: _get_env_int("AGIO_GLOB_MAX_SEARCH_DEPTH", "10")
    )
    max_path_length: int = field(
        default_factory=lambda: _get_env_int("AGIO_GLOB_MAX_PATH_LENGTH", "500")
    )
    max_pattern_length: int = field(
        default_factory=lambda: _get_env_int("AGIO_GLOB_MAX_PATTERN_LENGTH", "200")
    )


@dataclass
class LSConfig:
    """Configuration for LSTool."""

    timeout_seconds: int = field(default_factory=lambda: _get_env_int("AGIO_LS_TIMEOUT", "30"))
    max_files: int = field(default_factory=lambda: _get_env_int("AGIO_LS_MAX_FILES", "1000"))
    max_lines: int = field(default_factory=lambda: _get_env_int("AGIO_LS_MAX_LINES", "100"))


@dataclass
class BashConfig:
    """Configuration for BashTool."""

    timeout_seconds: int = field(default_factory=lambda: _get_env_int("AGIO_BASH_TIMEOUT", "300"))
    max_output_size_kb: int = field(
        default_factory=lambda: _get_env_int("AGIO_BASH_MAX_OUTPUT_SIZE_KB", "1024")
    )
    max_output_length: int = field(
        default_factory=lambda: _get_env_int("AGIO_BASH_MAX_OUTPUT_LENGTH", "30000")
    )


@dataclass
class WebSearchConfig:
    """Configuration for WebSearchTool."""

    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_SEARCH_TIMEOUT", "30")
    )
    max_results: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_SEARCH_MAX_RESULTS", "10")
    )


@dataclass
class WebFetchConfig:
    """Configuration for WebFetchTool."""

    timeout_seconds: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_FETCH_TIMEOUT", "30")
    )
    max_content_length: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_FETCH_MAX_CONTENT_LENGTH", "4096")
    )
    max_retries: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_FETCH_MAX_RETRIES", "1")
    )
    wait_strategy: str = field(
        default_factory=lambda: _get_env_str("AGIO_WEB_FETCH_WAIT_STRATEGY", "domcontentloaded")
    )
    max_size_mb: float = field(
        default_factory=lambda: _get_env_float("AGIO_WEB_FETCH_MAX_SIZE_MB", "10.0")
    )
    headless: bool = field(default_factory=lambda: _get_env_bool("AGIO_WEB_FETCH_HEADLESS", "true"))
    save_login_state: bool = field(
        default_factory=lambda: _get_env_bool("AGIO_WEB_FETCH_SAVE_LOGIN_STATE", "false")
    )
    user_data_dir: str = field(
        default_factory=lambda: _get_env_str("AGIO_WEB_FETCH_USER_DATA_DIR", "chrome_user_data")
    )
    browser_launch_timeout: int = field(
        default_factory=lambda: _get_env_int("AGIO_WEB_FETCH_BROWSER_LAUNCH_TIMEOUT", "30")
    )


def create_config_from_dict(config_class: type, data: dict) -> Any:
    """Create config object from dictionary, supporting partial fields."""
    import dataclasses
    import inspect

    # Get dataclass field names (more accurate)
    if dataclasses.is_dataclass(config_class):
        field_names = {f.name for f in dataclasses.fields(config_class)}
        valid_params = {k: v for k, v in data.items() if k in field_names}
    else:
        # Fallback to inspect method
        sig = inspect.signature(config_class.__init__)
        valid_params = {k: v for k, v in data.items() if k in sig.parameters}

    return config_class(**valid_params)


def filter_config_kwargs(config_class: type, kwargs: dict) -> dict:
    """Filter kwargs to only include valid config fields."""
    import dataclasses

    if dataclasses.is_dataclass(config_class):
        field_names = {f.name for f in dataclasses.fields(config_class)}
        return {k: v for k, v in kwargs.items() if k in field_names}
    return kwargs


__all__ = [
    "FileReadConfig",
    "FileWriteConfig",
    "FileEditConfig",
    "GrepConfig",
    "GlobConfig",
    "LSConfig",
    "BashConfig",
    "WebSearchConfig",
    "WebFetchConfig",
    "create_config_from_dict",
    "filter_config_kwargs",
]
