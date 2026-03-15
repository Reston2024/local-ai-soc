"""
Application configuration loaded from environment / .env file.

Uses pydantic-settings for type-validated settings with .env file support.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    All values can be overridden via environment variables or a .env file
    in the project root.  Field names are case-insensitive at load time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Storage
    DATA_DIR: str = "data"

    # Ollama
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3:14b"
    OLLAMA_EMBED_MODEL: str = "mxbai-embed-large"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000


# Module-level singleton so importers can do: from backend.core.config import settings
settings = Settings()
