from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None

    summarizer_max_messages: int = Field(default=20, ge=1, le=100)
    summarizer_max_normalized_chars: int = Field(default=100_000, ge=1_000)
    summarizer_provider_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    summarizer_retry_delay_seconds: float = Field(default=0.25, ge=0, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
