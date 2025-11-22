"""
Configuration validator for validating configuration dictionaries.

This module provides the ConfigValidator class which validates raw configuration
dictionaries against Pydantic models.
"""

from typing import Any
from pydantic import ValidationError
from .models import (
    BaseComponentConfig, 
    ComponentType,
    ModelConfig,
    AgentConfig,
    ToolConfig,
    MemoryConfig,
    KnowledgeConfig,
    HookConfig,
    RepositoryConfig,
    StorageConfig,
)


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


class BatchValidationError(Exception):
    """Batch validation error."""
    
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(self._format_errors())
    
    def _format_errors(self) -> str:
        lines = ["Configuration validation failed:"]
        for name, error in self.errors.items():
            lines.append(f"  - {name}: {error}")
        return "\n".join(lines)


class ConfigValidator:
    """Configuration Validator."""
    
    CONFIG_MODEL_MAP = {
        ComponentType.MODEL: ModelConfig,
        ComponentType.AGENT: AgentConfig,
        ComponentType.TOOL: ToolConfig,
        ComponentType.MEMORY: MemoryConfig,
        ComponentType.KNOWLEDGE: KnowledgeConfig,
        ComponentType.HOOK: HookConfig,
        ComponentType.REPOSITORY: RepositoryConfig,
        ComponentType.STORAGE: StorageConfig,
    }
    
    def validate(self, config: dict[str, Any]) -> BaseComponentConfig:
        """
        Validate configuration and return Pydantic model.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Validated Pydantic model
            
        Raises:
            ConfigValidationError: If validation fails
        """
        component_type = config.get("type")
        if not component_type:
            raise ValueError("Missing 'type' field in config")
        
        try:
            component_type = ComponentType(component_type)
        except ValueError:
            raise ValueError(f"Invalid component type: {component_type}")
        
        model_class = self.CONFIG_MODEL_MAP.get(component_type)
        if not model_class:
            raise ValueError(f"No validator for type: {component_type}")
        
        try:
            return model_class(**config)
        except ValidationError as e:
            raise ConfigValidationError(
                f"Validation failed for {config.get('name', 'unknown')}: {e}"
            )
    
    def validate_batch(
        self, 
        configs: dict[str, dict]
    ) -> dict[str, BaseComponentConfig]:
        """
        Batch validate configurations.
        
        Args:
            configs: Dictionary of configurations
            
        Returns:
            Dictionary of validated Pydantic models
            
        Raises:
            BatchValidationError: If any validation fails
        """
        validated = {}
        errors = {}
        
        for name, config in configs.items():
            try:
                validated[name] = self.validate(config)
            except Exception as e:
                errors[name] = str(e)
        
        if errors:
            raise BatchValidationError(errors)
        
        return validated
