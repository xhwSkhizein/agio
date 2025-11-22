"""
File watcher for configuration hot reload.
"""

from pathlib import Path
from typing import Callable
import time
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigFileWatcher:
    """
    Configuration file watcher using watchdog.
    
    Monitors configuration files for changes and triggers reload.
    """
    
    def __init__(
        self,
        watch_dir: str | Path,
        on_change: Callable[[Path], None],
        patterns: list[str] | None = None
    ):
        self.watch_dir = Path(watch_dir)
        self.on_change = on_change
        self.patterns = patterns or ["*.yaml", "*.yml"]
        self.observer = None
        self._running = False
    
    def start(self) -> None:
        """Start watching for file changes."""
        # Guard: Don't start if already running
        if self._running and self.observer:
            logger.warning("file_watcher_already_running", watch_dir=str(self.watch_dir))
            return
            
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
            
            class ConfigChangeHandler(FileSystemEventHandler):
                def __init__(self, watcher: ConfigFileWatcher):
                    self.watcher = watcher
                    self._last_modified = {}
                
                def on_modified(self, event: FileSystemEvent) -> None:
                    """Handle file modification events."""
                    if event.is_directory:
                        return
                    
                    file_path = Path(event.src_path)
                    
                    # Check file extension
                    if not any(file_path.match(pattern) for pattern in self.watcher.patterns):
                        return
                    
                    # Debounce: ignore if modified within last 0.5 seconds
                    now = time.time()
                    last_time = self._last_modified.get(str(file_path), 0)
                    if now - last_time < 0.5:
                        return
                    
                    self._last_modified[str(file_path)] = now
                    
                    # Trigger callback
                    try:
                        self.watcher.on_change(file_path)
                    except Exception as e:
                        logger.error(
                            "file_change_handler_error",
                            file_path=str(file_path),
                            error=str(e),
                            exc_info=True
                        )
            
            self.observer = Observer()
            handler = ConfigChangeHandler(self)
            self.observer.schedule(handler, str(self.watch_dir), recursive=True)
            self.observer.start()
            self._running = True
            
            logger.info(
                "file_watcher_started",
                watch_dir=str(self.watch_dir),
                patterns=self.patterns
            )
            
        except ImportError:
            logger.warning(
                "watchdog_not_installed",
                message="File watching disabled. Install with: pip install watchdog"
            )
    
    def stop(self) -> None:
        """Stop watching for file changes."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join()
            self._running = False
            logger.info("file_watcher_stopped", watch_dir=str(self.watch_dir))
    
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running
