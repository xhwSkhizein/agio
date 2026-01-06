"""
Model Provider Registry - Model provider registration and management.

Manages model provider factories and creates model instances from configuration.
"""

from typing import Any, Callable, Protocol

from agio.config.schema import ModelConfig
from agio.llm import AnthropicModel, DeepseekModel, NvidiaModel, OpenAIModel
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ModelProvider(Protocol):
    """Model Provider protocol."""

    def __init__(
        self,
        id: str,
        name: str,
        api_key: str | None,
        model_name: str,
        base_url: str | None,
        temperature: float,
        max_tokens: int | None,
    ): ...


ModelProviderFactory = Callable[..., Any]


class ModelProviderRegistry:
    """
    Model Provider registry.

    Responsibilities:
    - Register and query Provider factory functions
    - Support dynamic extension
    - Follow Open-Closed Principle (OCP)
    """

    def __init__(self) -> None:
        self._providers: dict[str, ModelProviderFactory] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default Providers."""
        self.register("openai", OpenAIModel)
        self.register("anthropic", AnthropicModel)
        self.register("deepseek", DeepseekModel)
        self.register("nvidia", NvidiaModel)

        logger.debug("Registered default model providers")

    def register(self, provider: str, factory: ModelProviderFactory) -> None:
        """
        Register Provider.

        Args:
            provider: Provider name
            factory: Provider factory function
        """
        self._providers[provider] = factory
        logger.debug(f"Registered model provider: {provider}")

    def get(self, provider: str) -> ModelProviderFactory | None:
        """
        Get Provider factory function.

        Args:
            provider: Provider name

        Returns:
            Factory function, or None if not found
        """
        return self._providers.get(provider)

    def has(self, provider: str) -> bool:
        """
        Check if Provider exists.

        Args:
            provider: Provider name

        Returns:
            True if provider exists, False otherwise
        """
        return provider in self._providers

    def list_providers(self) -> list[str]:
        """
        List all registered Providers.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def create_model(self, config: ModelConfig) -> Any:
        """
        Create model instance from configuration.

        Args:
            config: Model configuration

        Returns:
            Model instance

        Raises:
            ValueError: Provider does not exist
        """
        factory = self.get(config.provider)
        if not factory:
            available = ", ".join(self.list_providers())
            raise ValueError(
                f"Unknown model provider: {config.provider}. "
                f"Available providers: {available}"
            )

        return factory(
            id=f"{config.provider}/{config.model_name}",
            name=config.name,
            api_key=config.api_key,
            model_name=config.model_name,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )


_model_provider_registry: ModelProviderRegistry | None = None


def get_model_provider_registry() -> ModelProviderRegistry:
    """Get global ModelProviderRegistry instance."""
    global _model_provider_registry

    if _model_provider_registry is None:
        _model_provider_registry = ModelProviderRegistry()

    return _model_provider_registry
