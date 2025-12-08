"""Shared file utility helpers for tools."""

from __future__ import annotations

import time
from pathlib import Path

from agio.providers.tools.builtin.adapter import AppSettings, SettingsRegistry
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class FileUtils:
    """Utility helper for detecting encodings and line endings."""

    def __init__(self, *, settings: AppSettings | None = None) -> None:
        self._settings = settings or SettingsRegistry.get()
        self._encoding_cache: dict[str, tuple[str, float]] = {}
        self._line_ending_cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes

    def detect_encoding(self, file_path: str) -> str:
        """Detect file encoding with caching."""
        cache_key = Path(file_path).resolve().as_posix()
        cached = self._encoding_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[1] < self._cache_ttl_seconds:
            return cached[0]

        encoding = "utf-8"
        try:
            with open(file_path, "rb") as fh:
                header = fh.read(4)
                if header.startswith(b"\xff\xfe"):
                    encoding = "utf-16le"
                elif header.startswith(b"\xfe\xff"):
                    encoding = "utf-16be"
                elif header.startswith(b"\xef\xbb\xbf"):
                    encoding = "utf-8"
                else:
                    fh.seek(0)
                    sample = fh.read(1024)
                    try:
                        import chardet

                        detected = chardet.detect(sample)
                        encoding = detected.get("encoding") or encoding
                    except ImportError:
                        pass
        except Exception:
            logger.debug("Failed to detect encoding; fallback to utf-8", exc_info=True)

        self._encoding_cache[cache_key] = (encoding, now)
        return encoding

    def detect_line_endings(self, file_path: str) -> str:
        """Detect line endings (LF or CRLF) with caching."""
        cache_key = Path(file_path).resolve().as_posix()
        cached = self._line_ending_cache.get(cache_key)
        now = time.time()
        if cached and now - cached[1] < self._cache_ttl_seconds:
            return cached[0]

        line_endings = "LF"
        try:
            with open(file_path, "rb") as fh:
                content = fh.read(4096)
            crlf = content.count(b"\r\n")
            lf = content.count(b"\n") - crlf
            line_endings = "CRLF" if crlf > lf else "LF"
        except Exception:
            logger.debug("Failed to detect line endings; default to LF", exc_info=True)

        self._line_ending_cache[cache_key] = (line_endings, now)
        return line_endings

    def normalize_line_endings(self, content: str, line_endings: str = "LF") -> str:
        """Normalize line endings to specified format."""
        normalized = content.replace("\r\n", "\n")
        ending = line_endings.upper()
        if ending == "CRLF":
            normalized = normalized.replace("\n", "\r\n")
        return normalized

    def write_text_content(
        self,
        file_path: str,
        content: str,
        *,
        line_endings: str = "LF",
        encoding: str = "utf-8",
    ) -> str:
        """Write text content to file with proper line endings."""
        normalized = self.normalize_line_endings(content, line_endings)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding=encoding, newline="") as fh:
            fh.write(normalized)
        return normalized


class FileEditTracker:
    """Track recent file reads/edits to support tools metadata."""

    def __init__(self) -> None:
        self._read_timestamps: dict[str, float] = {}

    def record_file_read(self, file_path: str) -> None:
        """Record a file read timestamp."""
        full_path = Path(file_path).resolve().as_posix()
        self._read_timestamps[full_path] = time.time()

    def get_read_timestamp(self, file_path: str) -> float | None:
        """Get the last read timestamp for a file."""
        full_path = Path(file_path).resolve().as_posix()
        return self._read_timestamps.get(full_path)

    def record_file_edit(self, file_path: str, content: str | None = None) -> None:
        """Record a file edit."""
        full_path = Path(file_path).resolve().as_posix()
        self._read_timestamps[full_path] = time.time()
        logger.debug("Recorded edit for file %s", full_path)


# Singleton instances
_SHARED_TRACKER: FileEditTracker | None = None
_FILE_UTILS_CACHE: dict[int, FileUtils] = {}


def get_file_edit_tracker() -> FileEditTracker:
    """Get the shared FileEditTracker instance."""
    global _SHARED_TRACKER
    if _SHARED_TRACKER is None:
        _SHARED_TRACKER = FileEditTracker()
    return _SHARED_TRACKER


def get_file_utils(settings: AppSettings | None = None) -> FileUtils:
    """Get a FileUtils instance (cached by settings)."""
    if settings is None:
        resolved_settings = SettingsRegistry.get()
        key = 0
    else:
        resolved_settings = settings
        key = id(settings)

    utils = _FILE_UTILS_CACHE.get(key)
    if utils is None:
        utils = FileUtils(settings=resolved_settings)
        _FILE_UTILS_CACHE[key] = utils
    return utils
