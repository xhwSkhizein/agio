from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgioSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=()  # Disable warning globally for settings
    )
    
    # Core settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # Storage settings
    mongo_uri: str | None = None
    mongo_db_name: str = "agio"
    
    # Vector DB settings
    vector_db_path: str | None = None
    
    # Model Provider Settings
    # OpenAI
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    
    # Deepseek
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"

settings = AgioSettings()
