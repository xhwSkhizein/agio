from typing import Optional
from pathlib import Path

from agio.registry.manager import ConfigManager
from agio.registry.base import ComponentRegistry, get_registry
from agio.registry.loader import ConfigLoader
from agio.registry.factory import ComponentFactory
from agio.registry.validator import ConfigValidator
from agio.registry.history import ConfigHistory
from agio.registry.events import get_event_bus, ConfigEventBus
from agio.db.repository import AgentRunRepository
from agio.config import settings
from agio.utils.logging import get_logger

logger = get_logger(__name__)

class DependencyContainer:
    _instance: Optional['DependencyContainer'] = None
    
    def __init__(self):
        self.registry: Optional[ComponentRegistry] = None
        self.config_manager: Optional[ConfigManager] = None
        self.event_bus: Optional[ConfigEventBus] = None
        self.repository: Optional[AgentRunRepository] = None
        
    @classmethod
    def get_instance(cls) -> 'DependencyContainer':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, config_dir: str | Path):
        # Guard: Don't re-initialize if already done
        if self.config_manager is not None:
            return
            
        # 1. Core dependencies
        self.event_bus = get_event_bus()
        self.registry = get_registry()
        
        # 2. Config Manager dependencies
        loader = ConfigLoader(config_dir)
        factory = ComponentFactory(self.registry)
        validator = ConfigValidator()
        history = ConfigHistory()
        
        # 3. Config Manager
        self.config_manager = ConfigManager(
            config_dir=config_dir,
            registry=self.registry,
            loader=loader,
            factory=factory,
            validator=validator,
            history=history,
            event_bus=self.event_bus,
            auto_reload=True # Default to True for now, could be config driven
        )
        
        # 4. Load all configurations
        logger.info("loading_configurations", config_dir=str(config_dir))
        self.config_manager.reload_all()
        
        # 5. Initialize global repository singleton
        self._initialize_repository()
    
    def _initialize_repository(self):
        """Initialize global repository singleton from configuration."""
        try:
            # Get repository from registry using default name from settings
            repo_name = settings.default_repository
            logger.info("initializing_repository", repo_name=repo_name)
            
            self.repository = self.registry.get(repo_name)
            
            if not self.repository:
                logger.warning(
                    "default_repository_not_found",
                    repo_name=repo_name,
                    message="Falling back to in-memory repository"
                )
                # Fallback to in-memory if configured repo not found
                from agio.db.repository import InMemoryRepository
                self.repository = InMemoryRepository()
            else:
                logger.info(
                    "repository_initialized",
                    repo_name=repo_name,
                    repo_type=type(self.repository).__name__
                )
        except Exception as e:
            logger.error("repository_init_failed", error=str(e), exc_info=True)
            # Ultimate fallback to in-memory
            from agio.db.repository import InMemoryRepository
            self.repository = InMemoryRepository()
            logger.warning("using_fallback_repository", repo_type="InMemoryRepository")

def get_container() -> DependencyContainer:
    return DependencyContainer.get_instance()

def get_config_manager() -> ConfigManager:
    container = get_container()
    if not container.config_manager:
        raise RuntimeError("DependencyContainer not initialized")
    return container.config_manager

def get_registry_dep() -> ComponentRegistry:
    container = get_container()
    if not container.registry:
        raise RuntimeError("DependencyContainer not initialized")
    return container.registry

def get_repository() -> AgentRunRepository:
    """Get global repository singleton."""
    container = get_container()
    if not container.repository:
        raise RuntimeError("Repository not initialized")
    return container.repository
