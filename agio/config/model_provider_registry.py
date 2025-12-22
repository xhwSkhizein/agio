from typing import Any, Callable, Protocol

from agio.config.schema import ModelConfig
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ModelProvider(Protocol):
    """模型 Provider 协议"""

    def __init__(
        self,
        id: str,
        name: str,
        api_key: str | None,
        model_name: str,
        base_url: str | None,
        temperature: float,
        max_tokens: int | None,
    ):
        ...


ModelProviderFactory = Callable[..., Any]


class ModelProviderRegistry:
    """
    模型 Provider 注册表
    
    职责：
    - 注册和查询 Provider 工厂函数
    - 支持动态扩展
    - 遵循开闭原则（OCP）
    """

    def __init__(self):
        self._providers: dict[str, ModelProviderFactory] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认 Provider"""
        from agio.providers.llm import AnthropicModel, DeepseekModel, OpenAIModel

        self.register("openai", OpenAIModel)
        self.register("anthropic", AnthropicModel)
        self.register("deepseek", DeepseekModel)

        logger.debug("Registered default model providers")

    def register(self, provider: str, factory: ModelProviderFactory) -> None:
        """
        注册 Provider
        
        Args:
            provider: Provider 名称
            factory: Provider 工厂函数
        """
        self._providers[provider] = factory
        logger.debug(f"Registered model provider: {provider}")

    def get(self, provider: str) -> ModelProviderFactory | None:
        """
        获取 Provider 工厂函数
        
        Args:
            provider: Provider 名称
            
        Returns:
            工厂函数，不存在返回 None
        """
        return self._providers.get(provider)

    def has(self, provider: str) -> bool:
        """
        检查 Provider 是否存在
        
        Args:
            provider: Provider 名称
            
        Returns:
            是否存在
        """
        return provider in self._providers

    def list_providers(self) -> list[str]:
        """
        列出所有已注册的 Provider
        
        Returns:
            Provider 名称列表
        """
        return list(self._providers.keys())

    def create_model(self, config: ModelConfig) -> Any:
        """
        根据配置创建模型实例
        
        Args:
            config: 模型配置
            
        Returns:
            模型实例
            
        Raises:
            ValueError: Provider 不存在
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
    """获取全局 ModelProviderRegistry 实例"""
    global _model_provider_registry

    if _model_provider_registry is None:
        _model_provider_registry = ModelProviderRegistry()

    return _model_provider_registry
