"""
Global settings from environment variables.
"""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgioSettings(BaseSettings):
    """
    Global configuration loaded from environment variables.

    Environment variables should be prefixed with AGIO_
    Example: AGIO_DEBUG=true, AGIO_MONGO_URI=mongodb://localhost:27017
    """

    model_config = SettingsConfigDict(
        env_prefix="AGIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # Core settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Storage settings
    mongo_uri: str | None = None
    mongo_db_name: str = "agio"

    # Vector DB settings
    vector_db_path: str | None = None

    # Repository and Storage settings
    default_repository: str = "mongodb_repo"
    default_storage: str = "inmemory_storage"

    # Model Provider Settings
    # OpenAI
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None

    # Deepseek
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"

    # Anthropic
    anthropic_api_key: SecretStr | None = None

    # Observability - OTLP Export
    otlp_enabled: bool = False
    otlp_endpoint: str | None = None  # e.g., "http://localhost:4317" for gRPC
    otlp_protocol: Literal["grpc", "http"] = "grpc"
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    otlp_sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)  # 1.0 = 100% sampling


# Global settings instance (singleton)
settings = AgioSettings()


__all__ = ["AgioSettings", "settings"]
